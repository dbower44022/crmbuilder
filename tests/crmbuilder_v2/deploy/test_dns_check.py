"""The DNS diagnostic — PI-571 (REQ-649).

Each case the diagnostic promises to recognise is driven through a fake
lookup, and each answer is checked for its state, who acts, and that it says
what to do in words that name the record to create.
"""

from __future__ import annotations

from crmbuilder_v2.deploy import dns_check
from crmbuilder_v2.deploy.dns_check import diagnose, describe_address

from tests.crmbuilder_v2.deploy.fakes import FakeDnsLookup

IP = "203.0.113.7"
GODADDY = ("ns51.domaincontrol.com", "ns52.domaincontrol.com")


def test_correct_when_the_name_servers_and_public_dns_agree():
    lookup = FakeDnsLookup(records={("crm.example.org", "A"): [IP]})
    d = diagnose("crm.example.org", IP, lookup=lookup, automatic_host="cloudflare")
    assert d.is_correct and d.state == dns_check.CORRECT and d.who == dns_check.WHO_NOBODY
    assert d.dns_host == "Cloudflare" and d.record_name == "crm"


def test_no_name_servers_means_the_domain_is_wrong_or_unregistered():
    d = diagnose("crm.exmaple.org", IP, lookup=FakeDnsLookup())
    assert d.state == dns_check.NEEDS_ACTION and d.code == "no_name_servers"
    assert "misspelled" in d.meaning and d.who == dns_check.WHO_OPERATOR


def test_cloudflare_record_at_a_host_the_internet_does_not_use_is_caught_first():
    lookup = FakeDnsLookup(name_servers=GODADDY)
    d = diagnose("crm.example.org", IP, lookup=lookup, automatic_host="cloudflare")
    assert d.code == "record_at_unused_host" and d.state == dns_check.NEEDS_ACTION
    assert "GoDaddy" in d.found and "never be seen" in d.meaning


def test_missing_record_names_the_record_to_create_at_the_detected_host():
    d = diagnose("crm.example.org", IP, lookup=FakeDnsLookup(name_servers=GODADDY))
    assert d.code == "record_missing" and d.who == dns_check.WHO_CLIENT
    assert d.action == (
        f"At GoDaddy, create a DNS record: type A, name crm, value {IP}. "
        "Leave any proxy, forwarding or parking switched off."
    )
    assert f"Address: {IP}" in d.verify


def test_record_created_with_the_domain_typed_twice():
    lookup = FakeDnsLookup(records={("crm.example.org.example.org", "A"): [IP]})
    d = diagnose("crm.example.org", IP, lookup=lookup)
    assert d.code == "record_wrong_name"
    assert "only crm in the name box" in d.action


def test_wrong_address_and_extra_address():
    d = diagnose("crm.example.org", IP, lookup=FakeDnsLookup(records={("crm.example.org", "A"): ["198.51.100.9"]}))
    assert d.code == "wrong_address" and "198.51.100.9" in d.found
    d = diagnose("crm.example.org", IP,
                 lookup=FakeDnsLookup(records={("crm.example.org", "A"): [IP, "198.51.100.9"]}))
    assert d.code == "extra_address" and "198.51.100.9" in d.found


def test_cloudflare_proxy_address_means_the_proxy_is_on():
    d = diagnose("crm.example.org", IP, lookup=FakeDnsLookup(records={("crm.example.org", "A"): ["104.21.3.4"]}))
    assert d.code == "proxy_on" and "grey" in d.action


def test_cname_and_aaaa_conflicts():
    d = diagnose("crm.example.org", IP,
                 lookup=FakeDnsLookup(records={("crm.example.org", "CNAME"): "old.host.net"}))
    assert d.code == "cname_conflict" and "old.host.net" in d.found
    d = diagnose("crm.example.org", IP, lookup=FakeDnsLookup(records={
        ("crm.example.org", "A"): [IP], ("crm.example.org", "AAAA"): ["2001:db8::1"]}))
    assert d.code == "aaaa_conflict" and "delete the AAAA record" in d.action


def test_correct_record_not_yet_public_will_fix_itself_with_an_estimate():
    lookup = FakeDnsLookup(records={("crm.example.org", "A"): [IP]},
                           public={("crm.example.org", "A"): set()}, negative_ttl=1800, ttl=300)
    d = diagnose("crm.example.org", IP, lookup=lookup)
    assert d.state == dns_check.WILL_FIX_ITSELF and d.code == "propagating"
    assert d.wait_seconds == 1800 and "30 minutes" in d.meaning
    assert d.who == dns_check.WHO_NOBODY


def test_unreachable_name_servers_are_not_blamed_on_anyone():
    d = diagnose("crm.example.org", IP, lookup=FakeDnsLookup(unreachable=True))
    assert d.state == dns_check.WILL_FIX_ITSELF and d.code == "name_servers_unreachable"
    d = diagnose("crm.example.org", IP, lookup=FakeDnsLookup(
        unreachable=True, public={("crm.example.org", "A"): {IP}}))
    assert d.is_correct


def test_summary_reads_as_one_paragraph_and_round_trips():
    d = diagnose("crm.example.org", IP, lookup=FakeDnsLookup(name_servers=GODADDY))
    text = d.summary()
    assert text.startswith("The DNS record has not been created yet.") and "What to do:" in text
    assert dns_check.DnsDiagnosis.from_dict(d.to_dict()) == d


def test_dns_host_names_and_record_names():
    assert dns_check.dns_host_name(["dns1.registrar-servers.com"]) == "Namecheap"
    assert dns_check.dns_host_name(["ns1.example-host.net"]).startswith("the DNS host at ns1.example-host.net")
    assert dns_check.record_name("example.org", "example.org") == "@"
    assert dns_check.record_name("crm.members.example.org", "example.org") == "crm.members"


def test_describe_address_reports_the_host_and_existing_records():
    lookup = FakeDnsLookup(name_servers=GODADDY, records={("crm.example.org", "A"): ["198.51.100.9"]})
    info = describe_address("CRM.example.org.", lookup=lookup)
    assert info["domain"] == "crm.example.org" and info["zone"] == "example.org"
    assert info["dns_host"] == "GoDaddy" and info["uses_cloudflare"] is False
    assert info["existing_records"] == {"A": ["198.51.100.9"]}
    assert describe_address("crm.nowhere.test", lookup=lookup)["zone"] is None
