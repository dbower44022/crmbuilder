"""Explain a web address's DNS state in plain words — PI-571 (REQ-649).

One diagnostic serves the deploy run, the Check DNS now action, the handover
sheet and the wizard's address lookup. It does not just ask "does the name
resolve yet?" — the question the old wait loop asked, which could only answer
"not yet" for an hour. It asks four questions in order, and the first one that
finds a problem decides the answer:

1. **Which name servers answer for the domain?** A record created at a DNS
   host the internet does not use will never appear, however long anyone waits.
2. **Does the record exist on those name servers?** If not, it is missing or
   was created under the wrong name.
3. **Does it hold the right value?** An old address, a Cloudflare proxy address
   or a conflicting AAAA or CNAME record each has its own fix.
4. **Is it only a delay?** The name servers are right but public resolvers have
   not caught up; this fixes itself, and the record's cache lifetime says when.

Every result is ``correct``, ``will_fix_itself`` (with an expected wait) or
``needs_action``, and carries what was found, what it means, what to do, who
does it, and how to confirm the fix. All network access goes through a
:class:`DnsLookup`, so the reasoning is tested with a fake.
"""

from __future__ import annotations

import ipaddress
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

_log = logging.getLogger("crmbuilder_v2.deploy.dns_check")

#: Public resolvers asked for what the internet sees. The service's own
#: resolver is never used: it caches a "no such name" answer for the zone's
#: negative lifetime, which once blocked a run for 30 minutes after the record
#: was live (PI-419 live-proof finding, DEP-001).
PUBLIC_RESOLVERS: tuple[str, ...] = ("1.1.1.1", "8.8.8.8", "9.9.9.9")

CORRECT = "correct"
WILL_FIX_ITSELF = "will_fix_itself"
NEEDS_ACTION = "needs_action"

#: Who acts on a finding.
WHO_OPERATOR = "operator"
WHO_CLIENT = "client"
WHO_NOBODY = "nobody"

#: The longest wait a propagation estimate ever reports.
MAX_WAIT_SECONDS = 3600
#: The wait assumed when no cache lifetime could be read.
DEFAULT_WAIT_SECONDS = 300

#: Cloudflare's published proxy address ranges (IPv4). A record that resolves
#: into one of them has Cloudflare's proxy switched on, which stops the
#: certificate check and SSH reaching the server.
CLOUDFLARE_PROXY_RANGES: tuple[ipaddress.IPv4Network, ...] = tuple(
    ipaddress.ip_network(n)
    for n in (
        "173.245.48.0/20",
        "103.21.244.0/22",
        "103.22.200.0/22",
        "103.31.4.0/22",
        "141.101.64.0/18",
        "108.162.192.0/18",
        "190.93.240.0/20",
        "188.114.96.0/20",
        "197.234.240.0/22",
        "198.41.128.0/17",
        "162.158.0.0/15",
        "104.16.0.0/13",
        "104.24.0.0/14",
        "172.64.0.0/13",
        "131.0.72.0/22",
    )
)

#: Name-server suffix → the DNS host's name as a person would say it.
_DNS_HOSTS: tuple[tuple[str, str], ...] = (
    ("ns.cloudflare.com", "Cloudflare"),
    ("domaincontrol.com", "GoDaddy"),
    ("registrar-servers.com", "Namecheap"),
    ("awsdns", "Amazon Route 53"),
    ("googledomains.com", "Google Domains"),
    ("google.com", "Google Cloud DNS"),
    ("azure-dns", "Microsoft Azure DNS"),
    ("digitalocean.com", "DigitalOcean"),
    ("linode.com", "Linode"),
    ("name.com", "Name.com"),
    ("dnsimple.com", "DNSimple"),
    ("nsone.net", "NS1"),
    ("ui-dns", "IONOS"),
    ("wixdns.net", "Wix"),
    ("squarespacedns.com", "Squarespace"),
    ("hostgator.com", "HostGator"),
    ("bluehost.com", "Bluehost"),
    ("dreamhost.com", "DreamHost"),
    ("gandi.net", "Gandi"),
    ("hover.com", "Hover"),
    ("porkbun.com", "Porkbun"),
    ("worldnic.com", "Network Solutions"),
    ("dynect.net", "Oracle Dyn"),
    ("ultradns", "UltraDNS"),
)


def dns_host_name(name_servers: list[str]) -> str:
    """The DNS host behind ``name_servers``, by name when it is recognised."""
    joined = " ".join(ns.lower().rstrip(".") for ns in name_servers)
    for suffix, host in _DNS_HOSTS:
        if suffix in joined:
            return host
    if name_servers:
        return "the DNS host at " + ", ".join(ns.rstrip(".") for ns in name_servers[:2])
    return "an unknown DNS host"


def is_cloudflare_host(name_servers: list[str]) -> bool:
    """Whether the internet asks Cloudflare for this domain."""
    return bool(name_servers) and all(
        ns.lower().rstrip(".").endswith("ns.cloudflare.com") for ns in name_servers
    )


def is_cloudflare_proxy(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(ip in net for net in CLOUDFLARE_PROXY_RANGES)


def record_name(domain: str, zone: str | None) -> str:
    """What to type in a DNS host's name box: the part before the zone, or @."""
    if not zone or domain == zone:
        return "@"
    suffix = "." + zone
    return domain[: -len(suffix)] if domain.endswith(suffix) else domain


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


@dataclass
class AuthAnswer:
    """What the domain's own name servers say about one name and type.

    ``values`` is empty when the name has no record of that type. ``cname`` is
    set when the name is an alias instead.
    """

    values: list[str] = field(default_factory=list)
    ttl: int | None = None
    cname: str | None = None


class DnsLookup(Protocol):
    """The network questions the diagnostic asks."""

    def zone_and_name_servers(self, domain: str) -> tuple[str | None, list[str]]:
        """The zone that holds ``domain`` and the name servers the internet asks."""

    def authoritative(self, name_servers: list[str], name: str, rdtype: str) -> AuthAnswer | None:
        """Ask the name servers directly; ``None`` when none of them answered."""

    def public(self, name: str, rdtype: str = "A") -> set[str]:
        """What the public resolvers return for ``name``."""

    def negative_ttl(self, name_servers: list[str], zone: str) -> int | None:
        """How long a resolver caches "no such name" for the zone."""


class PublicDnsLookup:
    """The real lookups, through public resolvers and the zone's own servers."""

    def __init__(self, resolvers: tuple[str, ...] = PUBLIC_RESOLVERS, timeout: float = 4.0) -> None:
        self._resolvers = resolvers
        self._timeout = timeout

    def _resolver(self, server: str):
        import dns.resolver

        r = dns.resolver.Resolver(configure=False)
        r.nameservers = [server]
        r.lifetime = self._timeout
        return r

    def zone_and_name_servers(self, domain: str) -> tuple[str | None, list[str]]:
        import dns.exception
        import dns.resolver

        labels = domain.rstrip(".").lower().split(".")
        for i in range(len(labels) - 1):
            candidate = ".".join(labels[i:])
            for server in self._resolvers:
                try:
                    answer = self._resolver(server).resolve(candidate, "NS")
                except dns.resolver.NXDOMAIN:
                    break  # this name does not exist; try its parent
                except dns.resolver.NoAnswer:
                    break  # a name inside a zone; the zone is higher up
                except (dns.exception.DNSException, OSError):
                    continue  # this resolver failed; ask the next
                names = sorted(str(r.target).rstrip(".").lower() for r in answer)
                if names:
                    return candidate, names
                break
        return None, []

    def _server_addresses(self, name_servers: list[str]) -> list[str]:
        found: list[str] = []
        for ns in name_servers:
            for addr in sorted(self.public(ns, "A")):
                if addr not in found:
                    found.append(addr)
        return found

    def authoritative(self, name_servers: list[str], name: str, rdtype: str) -> AuthAnswer | None:
        import dns.exception
        import dns.message
        import dns.query
        import dns.rcode
        import dns.rdatatype

        wanted = dns.rdatatype.from_text(rdtype)
        for address in self._server_addresses(name_servers):
            try:
                reply = dns.query.udp(
                    dns.message.make_query(name, wanted), address, timeout=self._timeout
                )
            except (dns.exception.DNSException, OSError):
                continue
            if reply.rcode() == dns.rcode.NXDOMAIN:
                return AuthAnswer()
            out = AuthAnswer()
            for rrset in reply.answer:
                if rrset.rdtype == dns.rdatatype.CNAME:
                    out.cname = str(rrset[0].target).rstrip(".")
                    out.ttl = rrset.ttl
                elif rrset.rdtype == wanted:
                    out.values.extend(r.to_text() for r in rrset)
                    out.ttl = rrset.ttl
            return out
        return None

    def public(self, name: str, rdtype: str = "A") -> set[str]:
        import dns.exception

        found: set[str] = set()
        for server in self._resolvers:
            try:
                answer = self._resolver(server).resolve(name, rdtype)
            except (dns.exception.DNSException, OSError):
                continue
            found.update(r.to_text() for r in answer)
        return found

    def negative_ttl(self, name_servers: list[str], zone: str) -> int | None:
        import dns.exception
        import dns.message
        import dns.query
        import dns.rdatatype

        for address in self._server_addresses(name_servers):
            try:
                reply = dns.query.udp(
                    dns.message.make_query(zone, dns.rdatatype.SOA), address, timeout=self._timeout
                )
            except (dns.exception.DNSException, OSError):
                continue
            for rrset in reply.answer:
                if rrset.rdtype == dns.rdatatype.SOA:
                    return min(int(rrset[0].minimum), int(rrset.ttl))
        return None


# ---------------------------------------------------------------------------
# The diagnosis
# ---------------------------------------------------------------------------


@dataclass
class DnsDiagnosis:
    """One answer to "is this web address pointing at this server?"."""

    state: str
    code: str
    title: str
    found: str
    meaning: str
    action: str
    who: str
    verify: str
    domain: str
    expected_ip: str
    wait_seconds: int = 0
    zone: str | None = None
    name_servers: list[str] = field(default_factory=list)
    dns_host: str = ""
    record_name: str = "@"
    public_addresses: list[str] = field(default_factory=list)

    @property
    def is_correct(self) -> bool:
        return self.state == CORRECT

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DnsDiagnosis:
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})

    def summary(self) -> str:
        """The finding in one paragraph, for a log line or a status message."""
        parts = [f"{self.title}.", self.found, self.meaning]
        if self.action:
            parts.append(f"What to do: {self.action}")
        if self.verify and self.state != CORRECT:
            parts.append(f"To confirm: {self.verify}")
        return " ".join(p for p in parts if p)


def _verify_text(domain: str, ip: str) -> str:
    return (
        f"run  nslookup {domain} 1.1.1.1  on any computer; the answer should show "
        f"Address: {ip}. Or press Check DNS now on the instance in CRMBuilder."
    )


def diagnose(
    domain: str,
    expected_ip: str,
    *,
    lookup: DnsLookup | None = None,
    automatic_host: str | None = None,
) -> DnsDiagnosis:
    """Explain whether ``domain`` points at ``expected_ip``, and if not, why.

    :param automatic_host: ``"cloudflare"`` when CRMBuilder created the record
        itself (Cloudflare mode). Findings then name the operator as the one who
        acts, and a record created at a DNS host the internet does not use is
        caught first. ``None`` for manual DNS: the client acts.
    """
    lookup = lookup or PublicDnsLookup()
    domain = domain.strip().lower().rstrip(".")
    who = WHO_OPERATOR if automatic_host else WHO_CLIENT
    verify = _verify_text(domain, expected_ip)

    zone, name_servers = lookup.zone_and_name_servers(domain)
    host = dns_host_name(name_servers)
    name = record_name(domain, zone)
    base: dict[str, Any] = {
        "domain": domain,
        "expected_ip": expected_ip,
        "zone": zone,
        "name_servers": list(name_servers),
        "dns_host": host,
        "record_name": name,
        "verify": verify,
    }
    create_text = (
        f"At {host}, create a DNS record: type A, name {name}, value {expected_ip}. "
        "Leave any proxy, forwarding or parking switched off."
    )

    def result(state: str, code: str, title: str, found: str, meaning: str,
               action: str, who_acts: str = who, wait: int = 0,
               public: set[str] | None = None) -> DnsDiagnosis:
        return DnsDiagnosis(
            state=state, code=code, title=title, found=found, meaning=meaning,
            action=action, who=who_acts, wait_seconds=wait,
            public_addresses=sorted(public or ()), **base,
        )

    # 1. Which name servers answer?
    if not zone:
        return result(
            NEEDS_ACTION, "no_name_servers", "No DNS host answers for this address",
            f"No name servers were found for {domain} or any domain above it.",
            "The domain may be misspelled, not registered, or expired. No record can "
            "be created until a DNS host answers for it.",
            "Check the spelling of the web address. If it is right, check with the "
            "domain's registrar that the domain is registered and has name servers.",
            WHO_OPERATOR,
        )
    if automatic_host == "cloudflare" and not is_cloudflare_host(name_servers):
        return result(
            NEEDS_ACTION, "record_at_unused_host",
            "The record was created at a DNS host the internet does not use",
            f"CRMBuilder created the record in Cloudflare, but the internet asks {host} "
            f"for {zone} (name servers {', '.join(name_servers)}).",
            "The Cloudflare record will never be seen, however long you wait.",
            f"Either create the record at {host} yourself (type A, name {name}, value "
            f"{expected_ip}), or change {zone}'s name servers at its registrar to the "
            "two Cloudflare name servers shown in the Cloudflare dashboard.",
            WHO_OPERATOR,
        )

    # 2 and 3. What do the name servers hold? The public resolvers are not
    # asked until the name servers hold the right record: asking them about a
    # name that does not exist yet makes them remember "no such name" for the
    # zone's negative lifetime, which delays the record once it is created —
    # the trap behind the slow waits this diagnostic replaces (DEP-001).
    a = lookup.authoritative(name_servers, domain, "A")
    if a is None:
        public = lookup.public(domain, "A")
        if expected_ip in public and public == {expected_ip}:
            return result(
                CORRECT, "correct", "DNS is correct",
                f"{domain} points at {expected_ip}.", "", "",
                WHO_NOBODY, public=public,
            )
        return result(
            WILL_FIX_ITSELF, "name_servers_unreachable",
            "The domain's name servers did not answer",
            f"{host}'s name servers ({', '.join(name_servers)}) did not answer in time.",
            "This is usually brief. CRMBuilder will ask again.",
            "Nothing yet. If this keeps happening, check the domain's status with its "
            "registrar.",
            WHO_NOBODY, DEFAULT_WAIT_SECONDS, public,
        )

    if a.cname:
        return result(
            NEEDS_ACTION, "cname_conflict", "The name is an alias (CNAME), not an address",
            f"At {host}, {domain} is a CNAME record pointing to {a.cname}.",
            "The certificate check and the CRM need the name to point straight at the "
            "server.",
            f"At {host}, delete the CNAME record for {name}, then create a record: "
            f"type A, name {name}, value {expected_ip}.",
        )

    aaaa = lookup.authoritative(name_servers, domain, "AAAA")
    if not a.values:
        doubled = f"{domain}.{zone}"
        wrong = lookup.authoritative(name_servers, doubled, "A")
        if wrong is not None and expected_ip in wrong.values:
            return result(
                NEEDS_ACTION, "record_wrong_name", "The record was created under the wrong name",
                f"At {host}, the record exists as {doubled} instead of {domain}.",
                "Most DNS hosts add the domain to the name you type, so typing the full "
                "address doubles it.",
                f"At {host}, delete the record named {name}.{zone} and create it again "
                f"with only {name} in the name box.",
            )
        return result(
            NEEDS_ACTION, "record_missing", "The DNS record has not been created yet",
            f"{host} has no address record for {domain}.",
            "The CRM cannot be reached by its web address, and the certificate cannot "
            "be issued, until this record exists.",
            create_text,
        )

    values = sorted(set(a.values))
    if expected_ip not in values:
        if all(is_cloudflare_proxy(v) for v in values):
            return result(
                NEEDS_ACTION, "proxy_on", "Cloudflare's proxy is switched on for this record",
                f"{domain} points at Cloudflare's proxy ({', '.join(values)}), not at the "
                f"server ({expected_ip}).",
                "Through the proxy, the certificate check and SSH cannot reach the server.",
                f"In Cloudflare, edit the record for {name} and switch the orange cloud "
                "to grey (DNS only). Its value must be " + expected_ip + ".",
            )
        return result(
            NEEDS_ACTION, "wrong_address", "The record points at a different server",
            f"At {host}, {domain} points at {', '.join(values)} instead of {expected_ip}.",
            "Visitors and the certificate check would reach the other server.",
            f"At {host}, change the record for {name} so its value is {expected_ip}. "
            "If there are several address records for this name, keep only that one.",
        )
    if len(values) > 1:
        others = [v for v in values if v != expected_ip]
        return result(
            NEEDS_ACTION, "extra_address", "The name has more than one address record",
            f"At {host}, {domain} points at {expected_ip} and also at {', '.join(others)}.",
            "Some visitors, and some certificate checks, would reach the other address.",
            f"At {host}, delete the address records for {name} whose value is not "
            f"{expected_ip}.",
        )
    if aaaa is not None and aaaa.values:
        return result(
            NEEDS_ACTION, "aaaa_conflict", "An IPv6 (AAAA) record also exists for this name",
            f"At {host}, {domain} also has an AAAA record ({', '.join(sorted(aaaa.values))}).",
            "The server has no IPv6 address, and the certificate check prefers IPv6, so "
            "it would go to the wrong place.",
            f"At {host}, delete the AAAA record for {name}.",
        )

    # 4. The name servers are right; do the public resolvers agree yet?
    public = lookup.public(domain, "A")
    if public == {expected_ip}:
        return result(
            CORRECT, "correct", "DNS is correct",
            f"{domain} points at {expected_ip}, and public DNS sees it.", "", "",
            WHO_NOBODY, public=public,
        )
    negative = lookup.negative_ttl(name_servers, zone) or 0
    wait = min(max(a.ttl or 0, negative, 60), MAX_WAIT_SECONDS)
    seen = f"public DNS still returns {', '.join(sorted(public))}" if public else (
        "public DNS does not return it yet"
    )
    return result(
        WILL_FIX_ITSELF, "propagating", "DNS is correct and spreading",
        f"{host} has the right record ({domain} → {expected_ip}), but {seen}.",
        f"This fixes itself as caches expire, usually within {_minutes(wait)}.",
        "Nothing. Wait, then check again.",
        WHO_NOBODY, wait, public,
    )


def _minutes(seconds: int) -> str:
    minutes = max(1, round(seconds / 60))
    return "1 minute" if minutes == 1 else f"{minutes} minutes"


def describe_address(domain: str, *, lookup: DnsLookup | None = None) -> dict[str, Any]:
    """Who hosts DNS for ``domain`` and what is already there — for the wizard.

    Runs before any server exists, so there is no expected address to judge
    against; it reports facts the operator needs before choosing a DNS mode.
    """
    lookup = lookup or PublicDnsLookup()
    domain = domain.strip().lower().rstrip(".")
    zone, name_servers = lookup.zone_and_name_servers(domain)
    existing: dict[str, list[str]] = {}
    if zone:
        for rdtype in ("A", "AAAA", "CNAME"):
            answer = lookup.authoritative(name_servers, domain, rdtype)
            if answer is None:
                continue
            if rdtype == "CNAME" and answer.cname:
                existing["CNAME"] = [answer.cname]
            elif answer.values:
                existing[rdtype] = sorted(set(answer.values))
            elif answer.cname and "CNAME" not in existing:
                existing["CNAME"] = [answer.cname]
    return {
        "domain": domain,
        "zone": zone,
        "name_servers": list(name_servers),
        "dns_host": dns_host_name(name_servers) if zone else "",
        "uses_cloudflare": is_cloudflare_host(name_servers),
        "record_name": record_name(domain, zone),
        "existing_records": existing,
    }
