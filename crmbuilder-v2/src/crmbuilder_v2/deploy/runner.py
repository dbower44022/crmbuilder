"""The deploy-run phase state machine — PI-419 (REQ-522, DEC-945).

:func:`run_deploy` drives one claimed deploy run through the ordered deploy
phases (``DEPLOY_RUN_PHASE_ORDER``), checkpointing after every phase so a run
abandoned mid-way (service restart) resumes at the phase that did not
complete. Each phase is idempotent against the checkpoint:

* ``validate`` — resolve tokens + secrets into memory, prove both provider
  tokens work, refuse a protected host, and register the run's SSH key.
* ``create_droplet`` — skipped when a droplet id is checkpointed; otherwise
  recover one by the run's tag before creating (a crash between the API call
  and the checkpoint must not create two servers).
* ``wait_droplet`` — poll to active + IP.
* ``create_dns`` — in Cloudflare mode create the DNS-only A record, never
  overwriting a record that points elsewhere; in manual DNS show the record
  the client must create. Nothing waits for DNS here.
* ``server_prep`` / ``install_espocrm`` / ``post_install`` — the SSH phases in
  :mod:`crmbuilder_v2.deploy.ssh` (PI-556 / REQ-638 / DEC-1140). The install
  uses the certificate only when DNS already points at the server; otherwise
  it installs the plain web mode for the same address (PI-571 / REQ-648).
* ``check_dns`` — diagnose DNS in plain words (:mod:`crmbuilder_v2.deploy.dns_check`),
  waiting only while the diagnosis says the problem fixes itself, and never
  more than ``dns_wait_limit_seconds``.
* ``certificate`` — when the install had no certificate, leave the
  self-healing job on the server (:mod:`crmbuilder_v2.deploy.certificate_job`)
  and, if DNS is already correct, run it at once.
* ``verify`` — the checks that fit how the server was installed.
* ``create_instance`` — register the instance and its deploy config, or bring
  an already-registered one up to date on a resumed run.

Manual DNS (PI-566 / REQ-642, DEC-1146): no Cloudflare credential is read and
the client creates the record by hand.

A problem that a person must fix — a DNS record, a certificate check — does not
fail the run (PI-571 / REQ-650). The phase ends ``needs_action`` (or
``waiting``, when it will finish by itself once another step is fixed), the
finding is kept as an **open item**, and the run carries on with every step
that does not depend on it. A run that ends with open items ends
``needs_action``; the items are written to the instance's deploy config, where
Check DNS now and the self-healing job close them. A phase *failure* — the
server could not be built — still lands ``failed`` with everything built kept
in the checkpoint and named in the log; nothing is destroyed (DEC-945).
Cancellation is honoured between phases only.

Every external dependency is injectable through :class:`RunnerDeps` so the
whole machine is unit-testable with fakes: provider clients, the SSH module,
the secret resolver, the clock.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from crmbuilder_v2 import secrets
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.engagement_scope import active_engagement
from crmbuilder_v2.access.repositories import (
    deploy_runs,
    instance_deploy_config,
    instances,
    provider_credentials,
)
from crmbuilder_v2.access.vocab import DEPLOY_RUN_PHASE_ORDER
from crmbuilder_v2.deploy import certificate_job, dns_check
from crmbuilder_v2.deploy.errors import DeployPhaseError, ProviderError
from crmbuilder_v2.deploy.keys import (
    generate_keypair,
    private_key_file,
    public_key_fingerprint,
)
from crmbuilder_v2.deploy.providers.cloudflare import CloudflareClient
from crmbuilder_v2.deploy.providers.digitalocean import DigitalOceanClient
from crmbuilder_v2.deploy.spec import DeploySpec, is_protected_host

_log = logging.getLogger("crmbuilder_v2.deploy.runner")

#: Phases whose completed state is honoured on resume (skipped when ``done``).
_RESUMABLE_DONE = frozenset({"server_prep", "install_espocrm", "post_install"})


class CancelledRun(Exception):
    """Raised between phases when the operator asked the run to stop."""


#: Resolvers asked when waiting for a new record. The host's own resolver is
#: deliberately *not* used: the run's first check usually lands before the
#: record has propagated, and a negative answer ("no such name") is then
#: cached locally for the zone's negative TTL — Cloudflare's is 30 minutes —
#: so every later check keeps failing long after the record is live
#: (PI-419 live-proof finding, DEP-001). Public resolvers see the record
#: within seconds of Cloudflare publishing it.
PUBLIC_RESOLVERS: tuple[str, ...] = ("1.1.1.1", "8.8.8.8", "9.9.9.9")

#: The longest a run waits for DNS that the diagnosis says will fix itself
#: (PI-571 / REQ-650). A problem that will not fix itself is not waited on.
DNS_WAIT_LIMIT_SECONDS = 900

#: Phase statuses for a step a person must act on, and for a step that will
#: finish by itself once another step is fixed (PI-571 / REQ-650).
NEEDS_ACTION = "needs_action"
WAITING = "waiting"


def manual_dns_record_text(domain: str, ip: str, *, name: str | None = None,
                           host: str | None = None) -> str:
    """The record the client adds by hand in manual DNS, in one line."""
    where = host or "the domain's DNS host"
    return (
        f"Add this DNS record at {where}: type A, name {name or domain}, value {ip}. "
        "Leave any proxy or forwarding off."
    )


def resolve_a_public(name: str) -> set[str]:
    """Return the A addresses for ``name`` as seen by the public resolvers.

    Each resolver is asked independently with a short timeout; the union of
    their answers is returned, so one lagging resolver cannot hold the run
    back and one that has cached a negative answer cannot mask the others.
    """
    import dns.exception
    import dns.resolver

    found: set[str] = set()
    for server in PUBLIC_RESOLVERS:
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = [server]
        resolver.lifetime = 5
        try:
            answer = resolver.resolve(name, "A")
        except (dns.exception.DNSException, OSError):
            continue
        found.update(r.address for r in answer)
    return found


@dataclass
class RunnerDeps:
    """Injectable collaborators (defaults are the real ones)."""

    do_client: Callable[[str], Any] = DigitalOceanClient
    cf_client: Callable[[str], Any] = CloudflareClient
    #: Module exposing the SSH phase functions (:mod:`crmbuilder_v2.deploy.ssh`).
    ssh: Any = None
    resolve_secret: Callable[[str], str] = secrets.get_secret
    store_secret: Callable[[str], str] = secrets.put_secret
    keypair: Callable[[str], tuple[str, str]] = generate_keypair
    #: The DNS questions the diagnostic asks (:class:`dns_check.DnsLookup`).
    dns_lookup: Any = None
    #: The self-healing certificate job's functions (:mod:`certificate_job`).
    cert_job: Any = None
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    droplet_wait_seconds: int = 600
    droplet_poll_seconds: int = 10
    dns_wait_limit_seconds: int = DNS_WAIT_LIMIT_SECONDS
    dns_poll_seconds: int = 30
    #: How long to keep trying to log in to a server that is not accepting
    #: SSH yet — a new server reports "active" before its SSH service listens.
    ssh_wait_seconds: int = 300
    ssh_poll_seconds: int = 10

    def __post_init__(self) -> None:
        if self.ssh is None:
            from crmbuilder_v2.deploy import ssh as ssh_phases

            self.ssh = ssh_phases
        if self.dns_lookup is None:
            self.dns_lookup = dns_check.PublicDnsLookup()
        if self.cert_job is None:
            self.cert_job = certificate_job


@dataclass
class _Run:
    """The in-memory view of the run the phases operate on."""

    identifier: str
    engagement_id: str
    spec: DeploySpec
    secret_refs: dict[str, str]
    state: dict[str, Any]
    secrets: dict[str, str] = field(default_factory=dict)
    do: Any = None
    cf: Any = None


class _Log:
    """Batches log lines so a chatty SSH phase does not write per line."""

    def __init__(self, identifier: str, *, flush_every: int = 20) -> None:
        self._identifier = identifier
        self._buffer: list[tuple[str, str]] = []
        self._flush_every = flush_every
        self.masks: list[str] = []

    def __call__(self, message: str, level: str = "info") -> None:
        text = str(message)
        for secret in self.masks:
            if secret:
                text = text.replace(secret, "[secret]")
        _log.debug("%s %s: %s", self._identifier, level, text)
        self._buffer.append((level, text))
        if len(self._buffer) >= self._flush_every:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        lines, self._buffer = self._buffer, []
        with session_scope() as s:
            deploy_runs.append_log(s, self._identifier, lines)


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


def run_deploy(
    identifier: str,
    *,
    engagement_id: str,
    worker_id: str,
    deps: RunnerDeps | None = None,
) -> str:
    """Execute (or resume) the claimed run ``identifier``; return its terminal status."""
    deps = deps or RunnerDeps()
    with active_engagement(engagement_id):
        with session_scope() as s:
            record = deploy_runs.get_deploy_run(s, identifier)
        if record is None:
            raise DeployPhaseError("validate", f"{identifier} not found")
        run = _Run(
            identifier=identifier,
            engagement_id=engagement_id,
            spec=DeploySpec.from_dict(record.get("deploy_run_spec") or {}),
            secret_refs=dict(record.get("deploy_run_secret_refs") or {}),
            state=dict(record.get("deploy_run_state") or {}),
        )
        log = _Log(identifier)
        resumed = any(
            (p or {}).get("status") in ("done", "retry", "failed", "running")
            for p in (run.state.get("phases") or {}).values()
        )
        log(
            f"{'Resuming' if resumed else 'Starting'} deploy run {identifier} "
            f"for {run.spec.domain} (worker {worker_id})",
            "info",
        )
        status = "succeeded"
        error: str | None = None
        try:
            for phase in DEPLOY_RUN_PHASE_ORDER:
                _check_cancel(run)
                if _phase_done(run, phase) and (
                    phase in _RESUMABLE_DONE
                    or phase in ("create_droplet", "create_instance")
                ):
                    log(f"↷ {phase}: already complete, skipping", "info")
                    continue
                _mark(run, phase, "running")
                log(f"▸ {phase}", "info")
                try:
                    updates = _PHASES[phase](run, deps, log)
                except CancelledRun:
                    raise
                except (ProviderError, DeployPhaseError) as exc:
                    _mark(run, phase, "failed", error=str(exc))
                    raise DeployPhaseError(phase, str(exc)) from exc
                except Exception as exc:  # a bug or a transport surprise
                    _log.exception("%s: %s raised", identifier, phase)
                    _mark(run, phase, "failed", error=f"{type(exc).__name__}: {exc}")
                    raise DeployPhaseError(phase, f"{type(exc).__name__}: {exc}") from exc
                updates = dict(updates or {})
                item = updates.pop("_open_item", None)
                items = dict(run.state.get("open_items") or {})
                if item:
                    items[item["key"]] = item
                    outcome = NEEDS_ACTION if item.get("state") == NEEDS_ACTION else WAITING
                    level = "warning" if outcome == NEEDS_ACTION else "info"
                    log(f"⚑ {item['title']}. {item.get('action') or ''}".strip(), level)
                else:
                    outcome = "done"
                    for key in _CLOSES.get(phase, ()):
                        items.pop(key, None)
                updates["open_items"] = items
                _mark(run, phase, outcome, state=updates)
                run.state.update(updates)
            _sync_instance(run, log)
            if run.state.get("open_items"):
                status = "needs_action"
                log(
                    "The CRM is installed. Still outstanding: "
                    + "; ".join(i["title"] for i in run.state["open_items"].values())
                    + ". These are kept as open items on the instance.",
                    "warning",
                )
            elif run.state.get("verify_failed"):
                status = "succeeded_with_issues"
        except CancelledRun:
            status, error = "cancelled", "cancelled by operator"
            log("■ Run cancelled between phases; everything built is kept.", "warning")
        except DeployPhaseError as exc:
            status, error = "failed", str(exc)
            log(f"✗ {exc}", "error")
            _report_kept(run, log)
        finally:
            log.flush()
        with session_scope() as s:
            deploy_runs.finish(
                s,
                identifier,
                status=status,
                error=error,
                instance_identifier=run.state.get("instance_identifier"),
            )
        return status


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------


def _phase_done(run: _Run, phase: str) -> bool:
    return ((run.state.get("phases") or {}).get(phase) or {}).get("status") == "done"


def _mark(
    run: _Run,
    phase: str,
    status: str,
    *,
    state: dict | None = None,
    error: str | None = None,
) -> None:
    with session_scope() as s:
        row = deploy_runs.set_phase(
            s, run.identifier, phase, state=state, phase_status=status, error=error
        )
    run.state = dict(row.get("deploy_run_state") or {})


def _check_cancel(run: _Run) -> None:
    with session_scope() as s:
        current = deploy_runs.get_deploy_run(s, run.identifier) or {}
    if (current.get("deploy_run_state") or {}).get("cancel_requested"):
        raise CancelledRun()


def _report_kept(run: _Run, log: _Log) -> None:
    kept = []
    if run.state.get("droplet_id"):
        kept.append(
            f"server {run.state['droplet_id']}"
            + (f" at {run.state['droplet_ip']}" if run.state.get("droplet_ip") else "")
        )
    if run.state.get("dns_record_id"):
        kept.append(f"DNS record {run.spec.domain}")
    if kept:
        log(
            "Kept (not destroyed): " + ", ".join(kept)
            + ". Retry the run to resume, or clean up in the provider console.",
            "warning",
        )


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------


def _parse_iso(value: str | None) -> datetime | None:
    """A checkpointed ISO timestamp back to a datetime (PI-442)."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _key_fingerprint(public_line: str | None) -> str | None:
    """Fingerprint of the run's public key, or None if it cannot be read."""
    if not public_line:
        return None
    try:
        return public_key_fingerprint(public_line)
    except (ValueError, IndexError):
        return None


def _phase_validate(run: _Run, deps: RunnerDeps, log: _Log) -> dict:
    if is_protected_host(run.spec.domain):
        raise DeployPhaseError(
            "validate", f"{run.spec.domain} is CRMBuilder's production host (GVR-240)"
        )
    manual = run.spec.manual_dns
    with session_scope() as s:
        do_row = provider_credentials.get_provider_credential(s, "digitalocean")
        cf_row = (
            None if manual else provider_credentials.get_provider_credential(s, "cloudflare")
        )
    needed = (("digitalocean", do_row),) if manual else (
        ("digitalocean", do_row), ("cloudflare", cf_row)
    )
    for name, row in needed:
        if not row:
            raise DeployPhaseError("validate", f"no {name} credential configured")
    do_token = deps.resolve_secret(do_row["token_ref"])
    log.masks.append(do_token)
    cf_token = None
    if not manual:
        cf_token = deps.resolve_secret(cf_row["token_ref"])
        log.masks.append(cf_token)
    for name in ("admin_password", "db_password", "db_root_password"):
        ref = run.secret_refs.get(name)
        if not ref:
            raise DeployPhaseError("validate", f"run has no {name} secret")
        run.secrets[name] = deps.resolve_secret(ref)
        log.masks.append(run.secrets[name])
    run.do = deps.do_client(do_token)
    account = run.do.verify_token()
    log(f"DigitalOcean token ok ({account.get('email', 'account')})", "success")
    if manual:
        log(
            f"Manual DNS: you will add the record for {run.spec.domain} at its DNS "
            "provider once the server has its IP address.",
            "info",
        )
    else:
        run.cf = deps.cf_client(cf_token)
        zone = run.cf.get_zone(run.spec.zone_id)
        if zone.get("name") and zone["name"] != run.spec.zone_name:
            raise DeployPhaseError(
                "validate", f"zone {run.spec.zone_id} is {zone['name']}, not {run.spec.zone_name}"
            )
        log(f"Cloudflare token ok (zone {run.spec.zone_name})", "success")

    # PI-442 (REQ-544): keep the provider account identity for the
    # deploy-config write-back at instance registration.
    updates: dict[str, Any] = {"provider_account": account.get("email")}
    key_ref = run.secret_refs.get("ssh_private_key")
    if key_ref:
        run.secrets["ssh_private_key"] = deps.resolve_secret(key_ref)
        public_line = run.state.get("ssh_public_key")
    else:
        private_pem, public_line = deps.keypair(f"crmbuilder-{run.identifier}")
        key_ref = deps.store_secret(private_pem)
        run.secrets["ssh_private_key"] = private_pem
        run.secret_refs["ssh_private_key"] = key_ref
        with session_scope() as s:
            row = deploy_runs._require(s, run.identifier)
            row.deploy_run_secret_refs = dict(run.secret_refs)
        updates["ssh_public_key"] = public_line
    if not run.state.get("ssh_key_id"):
        key = run.do.add_ssh_key(name=f"crmbuilder-{run.identifier}", public_key=public_line)
        updates["ssh_key_id"] = key.get("id")
        log(f"Registered SSH key crmbuilder-{run.identifier}", "success")
    return updates


def _phase_create_droplet(run: _Run, deps: RunnerDeps, log: _Log) -> dict:
    if run.state.get("droplet_id"):
        return {}
    existing = run.do.find_droplets_by_tag(run.identifier)
    if existing:
        d = existing[0]
        log(f"Found server {d['id']} already tagged {run.identifier}; reusing it", "warning")
        return {"droplet_id": str(d["id"]), "droplet_ip": d.get("ip"),
                "droplet_created_at": datetime.now(UTC).isoformat()}
    key_ids: list[Any] = list(run.spec.ssh_key_ids)
    if run.state.get("ssh_key_id") is not None:
        key_ids.append(run.state["ssh_key_id"])
    d = run.do.create_droplet(
        name=run.spec.domain,
        region=run.spec.region,
        size=run.spec.size,
        image=run.spec.image,
        ssh_key_ids=key_ids,
        tags=[run.identifier, run.engagement_id],
    )
    log(f"Created server {d['id']} ({run.spec.size} in {run.spec.region})", "success")
    return {"droplet_id": str(d["id"]), "droplet_region": run.spec.region,
            "droplet_size": run.spec.size,
            "droplet_created_at": datetime.now(UTC).isoformat()}


def _phase_wait_droplet(run: _Run, deps: RunnerDeps, log: _Log) -> dict:
    deadline = deps.clock() + deps.droplet_wait_seconds
    while True:
        d = run.do.get_droplet(run.state["droplet_id"])
        if d.get("status") == "active" and d.get("ip"):
            log(f"Server active at {d['ip']}", "success")
            return {"droplet_ip": d["ip"]}
        if deps.clock() >= deadline:
            raise DeployPhaseError(
                "wait_droplet",
                f"server {run.state['droplet_id']} not active after {deps.droplet_wait_seconds}s",
            )
        log(f"Waiting for server (status {d.get('status')})…", "info")
        deps.sleep(deps.droplet_poll_seconds)


def _automatic_host(run: _Run) -> str | None:
    """``"cloudflare"`` when the run creates the record itself, else ``None``."""
    return None if run.spec.manual_dns else "cloudflare"


def _item_from_diagnosis(key: str, step: str, diag: dns_check.DnsDiagnosis) -> dict:
    """An open item that carries a DNS diagnosis."""
    return {
        "key": key,
        "step": step,
        "state": NEEDS_ACTION if diag.state == dns_check.NEEDS_ACTION else WAITING,
        "title": diag.title,
        "found": diag.found,
        "meaning": diag.meaning,
        "action": diag.action,
        "who": diag.who,
        "verify": diag.verify,
        "code": diag.code,
        "opened_at": datetime.now(UTC).isoformat(),
    }


def _phase_create_dns(run: _Run, deps: RunnerDeps, log: _Log) -> dict:
    domain, ip = run.spec.domain, run.state["droplet_ip"]
    if run.spec.manual_dns:
        # Manual DNS: show the record; the client adds it by hand. Nothing
        # waits here — the install goes ahead, and check_dns reports later.
        try:
            zone, name_servers = deps.dns_lookup.zone_and_name_servers(domain)
        except Exception:  # a lookup failure must not stop the build
            zone, name_servers = None, []
        name = dns_check.record_name(domain, zone)
        host = dns_check.dns_host_name(name_servers) if zone else None
        log(manual_dns_record_text(domain, ip, name=name, host=host), "warning")
        log("The build carries on while the record is added; nothing waits for it.", "info")
        return {"manual_dns_record": {"type": "A", "name": domain, "value": ip,
                                      "host_name": name, "dns_host": host}}
    existing = run.cf.find_a_record(run.spec.zone_id, domain)
    if existing and existing.get("content") not in (None, ip):
        # Never overwrite a record that points somewhere else (REQ-648): it may
        # be the client's live website or email.
        return {"_open_item": {
            "key": "dns",
            "step": "create_dns",
            "state": NEEDS_ACTION,
            "title": "A DNS record for this address already exists",
            "found": f"In Cloudflare, {domain} already points at {existing.get('content')}.",
            "meaning": "CRMBuilder does not overwrite an existing record, because it may "
                       "be serving something else.",
            "action": f"If that record is no longer needed, change its value to {ip} in "
                      f"Cloudflare (DNS only), or delete it and press Try again. If it is "
                      "needed, deploy with a different web address.",
            "who": dns_check.WHO_OPERATOR,
            "verify": dns_check._verify_text(domain, ip),
            "code": "record_exists",
            "opened_at": datetime.now(UTC).isoformat(),
        }}
    rec = run.cf.upsert_a_record(run.spec.zone_id, name=domain, ip=ip, proxied=False)
    log(f"DNS record created in Cloudflare: {domain} → {ip} (DNS only)", "success")
    return {"dns_record_id": rec.get("id")}


def _diagnose(run: _Run, deps: RunnerDeps) -> dns_check.DnsDiagnosis:
    return dns_check.diagnose(
        run.spec.domain,
        run.state["droplet_ip"],
        lookup=deps.dns_lookup,
        automatic_host=_automatic_host(run),
    )


def _phase_check_dns(run: _Run, deps: RunnerDeps, log: _Log) -> dict:
    """Diagnose DNS; wait only while the diagnosis says it will fix itself."""
    started = deps.clock()
    while True:
        diag = _diagnose(run, deps)
        if diag.is_correct:
            log(f"DNS is correct: {run.spec.domain} points at {diag.expected_ip}.", "success")
            return {"dns": diag.to_dict()}
        elapsed = deps.clock() - started
        allowed = min(diag.wait_seconds + 60, deps.dns_wait_limit_seconds)
        if diag.state == dns_check.WILL_FIX_ITSELF and elapsed < allowed:
            log(
                f"{diag.title}. {diag.found} {diag.meaning} "
                f"Checking again in {deps.dns_poll_seconds} seconds.",
                "info",
            )
            deps.sleep(deps.dns_poll_seconds)
            continue
        log(diag.summary(), "warning" if diag.state == dns_check.NEEDS_ACTION else "info")
        return {"dns": diag.to_dict(), "_open_item": _item_from_diagnosis("dns", "check_dns", diag)}


def _ssh_config(run: _Run, key_path: str):
    return run.spec, {
        "ssh_host": run.state["droplet_ip"],
        "ssh_port": 22,
        "ssh_username": "root",
        "ssh_credential": key_path,
        "ssh_auth_type": "key",
        "domain": run.spec.domain,
        "letsencrypt_email": run.spec.letsencrypt_email,
        "db_password": run.secrets["db_password"],
        "db_root_password": run.secrets["db_root_password"],
        "admin_username": run.spec.admin_username,
        "admin_password": run.secrets["admin_password"],
        "admin_email": run.spec.admin_email,
    }


def _connect_when_ready(run: _Run, deps: RunnerDeps, config, log: _Log | None):
    """Log in to the server, waiting while it does not accept SSH yet.

    DigitalOcean reports a new server active before its SSH service listens.
    Until PI-571 the DNS wait sat between the two and hid the gap; with the
    install ahead of DNS, the first login met "Unable to connect to port 22"
    (DEP-002, 09-23-26). Every login now waits up to ``ssh_wait_seconds``.
    """
    deadline = deps.clock() + deps.ssh_wait_seconds
    told = False
    while True:
        try:
            client = deps.ssh.connect_ssh(config)
        except Exception as exc:  # refused, reset, no banner or key not yet installed
            if deps.clock() >= deadline:
                raise DeployPhaseError(
                    "ssh",
                    f"the server at {config.ssh_host} did not accept an SSH login within "
                    f"{deps.ssh_wait_seconds // 60} minutes ({type(exc).__name__}: {exc}). "
                    "Press Try again; the run resumes on the same server.",
                ) from exc
            if log is not None and not told:
                log("Waiting for the new server to accept SSH logins…", "info")
                told = True
            deps.sleep(deps.ssh_poll_seconds)
            continue
        if log is not None and told:
            log("The server accepts SSH logins.", "success")
        return client


def _with_ssh(run: _Run, deps: RunnerDeps, fn, log: _Log | None = None):
    with private_key_file(run.secrets["ssh_private_key"]) as key_path:
        _, fields = _ssh_config(run, key_path)
        config = deps.ssh.SelfHostedConfig(**fields)
        client = _connect_when_ready(run, deps, config, log)
        try:
            return fn(client, config)
        finally:
            try:
                client.close()
            except Exception:  # pragma: no cover - best effort
                pass


def _phase_server_prep(run: _Run, deps: RunnerDeps, log: _Log) -> dict:
    def go(client, config):
        ok, err = deps.ssh.phase_server_prep(client, log)
        if not ok:
            raise DeployPhaseError("server_prep", err)
        return {}

    return _with_ssh(run, deps, go, log)


def _secure(run: _Run) -> bool:
    """Whether the CRM on the server was installed with its certificate."""
    return run.state.get("install_mode", "letsencrypt") == "letsencrypt"


def _phase_install(run: _Run, deps: RunnerDeps, log: _Log) -> dict:
    installed = run.state.get("installed_domain")
    if installed and installed != run.spec.domain:
        # Try again with a corrected web address after the install (REQ-650):
        # point the installed CRM at the new address rather than reinstalling.
        def change(client, config):
            ok, err = deps.cert_job.apply_domain(client, installed, run.spec.domain, log)
            if not ok:
                raise DeployPhaseError("install_espocrm", err)
            return {"installed_domain": run.spec.domain}

        return _with_ssh(run, deps, change)

    diag = _diagnose(run, deps)
    secure = diag.is_correct
    if secure:
        log("DNS already points at the server, so the CRM is installed with its certificate.", "info")
    else:
        log(
            f"DNS is not ready ({diag.title.lower()}), so the CRM is installed without a "
            "certificate for now. The certificate is added automatically once DNS is correct.",
            "info",
        )

    def go(client, config):
        ok, err = deps.ssh.phase_install_espocrm(client, config, log, secure=secure)
        if not ok:
            raise DeployPhaseError("install_espocrm", err)
        return {"install_mode": "letsencrypt" if secure else "http",
                "installed_domain": run.spec.domain}

    return _with_ssh(run, deps, go)


def _phase_post_install(run: _Run, deps: RunnerDeps, log: _Log) -> dict:
    def go(client, config):
        ok, err, cert_expiry = deps.ssh.phase_post_install(
            client, config, log, secure=_secure(run)
        )
        if not ok:
            raise DeployPhaseError("post_install", err)
        return {"cert_expiry": cert_expiry} if cert_expiry else {}

    return _with_ssh(run, deps, go)


def _certificate_item(state: str, title: str, found: str, meaning: str, action: str,
                      who: str, verify: str) -> dict:
    return {
        "key": "certificate",
        "step": "certificate",
        "state": state,
        "title": title,
        "found": found,
        "meaning": meaning,
        "action": action,
        "who": who,
        "verify": verify,
        "code": "certificate",
        "opened_at": datetime.now(UTC).isoformat(),
    }


def _phase_certificate(run: _Run, deps: RunnerDeps, log: _Log) -> dict:
    """Leave the self-healing job on a server installed without a certificate."""
    if _secure(run):
        return {}
    domain, ip = run.spec.domain, run.state["droplet_ip"]
    dns_ok = (run.state.get("dns") or {}).get("state") == dns_check.CORRECT
    verify = (
        f"open https://{domain} in a browser; it should show a padlock and the CRM's "
        "login page. Or press Check DNS now on the instance in CRMBuilder."
    )

    def go(client, config):
        ok, err = deps.cert_job.install_job(
            client, domain, run.spec.letsencrypt_email, ip, log,
            zone=(run.state.get("dns") or {}).get("zone"),
        )
        if not ok:
            raise DeployPhaseError("certificate", err)
        if not dns_ok:
            return {"_open_item": _certificate_item(
                WAITING,
                "The certificate is waiting for DNS",
                f"The CRM is installed without a certificate because {domain} does not "
                "point at the server yet.",
                "A job on the server checks every 15 minutes and installs the "
                "certificate by itself once DNS is correct.",
                "Nothing, once the DNS record is fixed.",
                dns_check.WHO_NOBODY, verify,
            )}
        log("DNS is correct, so the certificate job runs now.", "info")
        deps.cert_job.run_job_now(client, log)
        status = deps.cert_job.read_status(client) or {}
        if status.get("state") == "done":
            expiry = deps.cert_job.read_certificate_expiry(client, domain)
            log(f"Certificate installed{f'; it expires {expiry}' if expiry else ''}.", "success")
            out: dict[str, Any] = {"install_mode": "letsencrypt", "certificate_job": status}
            if expiry:
                out["cert_expiry"] = expiry
            return out
        text = certificate_job.STATE_TEXT.get(status.get("state", ""), "The certificate job did not finish.")
        return {"certificate_job": status, "_open_item": _certificate_item(
            NEEDS_ACTION,
            "The certificate could not be installed yet",
            f"{text} {status.get('detail') or ''}".strip(),
            "The CRM works without a certificate but must not be used until it has one. "
            "The job keeps trying every 15 minutes.",
            "The usual causes are a firewall blocking port 80, or DNS that changed very "
            "recently. Fix the cause if the detail names one, then press Check DNS now.",
            dns_check.WHO_OPERATOR, verify,
        )}

    return _with_ssh(run, deps, go)


def _phase_verify(run: _Run, deps: RunnerDeps, log: _Log) -> dict:
    secure = _secure(run)

    def go(client, config):
        ok, checks = deps.ssh.phase_verify(client, run.spec.domain, log, secure=secure)
        failed = [c["check"] for c in checks if not c.get("passed")]
        if failed:
            log(f"Verification found gaps: {', '.join(failed)}", "warning")
        elif not secure:
            log("The checks that need the web address and certificate run once they are in place.", "info")
        return {"verify_checks": checks, "verify_failed": bool(failed),
                "verified_at": datetime.now(UTC).isoformat()}

    return _with_ssh(run, deps, go)


def _phase_create_instance(run: _Run, deps: RunnerDeps, log: _Log) -> dict:
    if run.state.get("instance_identifier"):
        return {}
    username_ref = deps.store_secret(run.spec.admin_username)
    with session_scope() as s:
        inst = instances.create_instance(
            s,
            name=run.spec.instance_name,
            url=f"https://{run.spec.domain}",
            vendor="espocrm",
            role="both",
            auth_method="basic",
            secret_ref=username_ref,
            secret_key_ref=run.secret_refs["admin_password"],
            notes=f"Provisioned by deploy run {run.identifier}.",
        )
        ident = inst["instance_identifier"]
        instance_deploy_config.upsert_deploy_config(
            s,
            ident,
            scenario="self_hosted",
            ssh_host=run.state.get("droplet_ip"),
            ssh_port=22,
            ssh_username="root",
            ssh_auth_type="key",
            ssh_credential_ref=run.secret_refs.get("ssh_private_key"),
            domain=run.spec.domain,
            letsencrypt_email=run.spec.letsencrypt_email,
            db_root_password_ref=run.secret_refs.get("db_root_password"),
            db_password_ref=run.secret_refs.get("db_password"),
            admin_username=run.spec.admin_username,
            admin_password_ref=run.secret_refs.get("admin_password"),
            admin_email=run.spec.admin_email,
            cert_expiry_date=run.state.get("cert_expiry"),
            dns_provider="manual" if run.spec.manual_dns else "cloudflare",
            droplet_id=run.state.get("droplet_id"),
            droplet_ip=run.state.get("droplet_ip"),
            droplet_region=run.state.get("droplet_region") or run.spec.region,
            droplet_size=run.state.get("droplet_size") or run.spec.size,
            dns_record_id=None if run.spec.manual_dns else run.state.get("dns_record_id"),
            last_deploy_run_identifier=run.identifier,
            # PI-442 (REQ-544): the server-management facts known at
            # registration — provider identity, console, SSH-key identity,
            # image and timestamps. Operator-editable afterwards.
            hosting_provider="digitalocean",
            hosting_account=run.state.get("provider_account"),
            hosting_console_url=(
                "https://cloud.digitalocean.com/droplets/"
                + str(run.state["droplet_id"])
                if run.state.get("droplet_id")
                else None
            ),
            ssh_key_public=run.state.get("ssh_public_key"),
            ssh_key_fingerprint=_key_fingerprint(run.state.get("ssh_public_key")),
            ssh_key_name=(
                f"crmbuilder-{run.identifier}"
                if run.state.get("ssh_key_id") is not None
                else None
            ),
            ssh_key_provider_id=(
                str(run.state["ssh_key_id"])
                if run.state.get("ssh_key_id") is not None
                else None
            ),
            server_image=run.spec.image,
            provisioned_at=_parse_iso(run.state.get("droplet_created_at")),
            last_verified_at=_parse_iso(run.state.get("verified_at")),
            open_items=_open_items_list(run),
        )
    log(f"Registered instance {ident} at https://{run.spec.domain}", "success")
    return {"instance_identifier": ident}


def _open_items_list(run: _Run) -> list[dict]:
    return list((run.state.get("open_items") or {}).values())


def _sync_instance(run: _Run, log: _Log) -> None:
    """Bring an already-registered instance up to date at the end of a run.

    A resumed run skips ``create_instance``, but what it found — open items
    closed or opened, a corrected web address, a new certificate — belongs on
    the instance too.
    """
    ident = run.state.get("instance_identifier")
    if not ident:
        return
    with session_scope() as s:
        inst = instances.get_instance(s, ident)
        url = f"https://{run.spec.domain}"
        if inst and inst.get("instance_url") != url:
            instances.patch_instance(s, ident, url=url)
            log(f"The instance's address is now {url}.", "info")
        fields: dict[str, Any] = {
            "open_items": _open_items_list(run),
            "domain": run.spec.domain,
            "last_deploy_run_identifier": run.identifier,
        }
        if run.state.get("cert_expiry"):
            fields["cert_expiry_date"] = run.state["cert_expiry"]
        instance_deploy_config.upsert_deploy_config(s, ident, **fields)


#: The open items a step closes when it finishes cleanly on a later attempt.
_CLOSES: dict[str, tuple[str, ...]] = {
    "create_dns": ("dns",),
    "check_dns": ("dns",),
    "certificate": ("certificate",),
}


_PHASES: dict[str, Callable[[_Run, RunnerDeps, _Log], dict]] = {
    "validate": _phase_validate,
    "create_droplet": _phase_create_droplet,
    "wait_droplet": _phase_wait_droplet,
    "create_dns": _phase_create_dns,
    "server_prep": _phase_server_prep,
    "install_espocrm": _phase_install,
    "post_install": _phase_post_install,
    "check_dns": _phase_check_dns,
    "certificate": _phase_certificate,
    "verify": _phase_verify,
    "create_instance": _phase_create_instance,
}
assert set(_PHASES) == set(DEPLOY_RUN_PHASE_ORDER)
