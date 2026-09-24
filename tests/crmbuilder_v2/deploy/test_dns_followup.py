"""Check DNS now — PI-571 (REQ-651).

The instance's open items are rewritten from a fresh diagnosis and the
certificate job's status; the job is started in the background only when DNS
is correct and the certificate is missing; a server that cannot be reached
still gets its DNS answer.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError
from crmbuilder_v2.access.repositories import instance_deploy_config, instances
from crmbuilder_v2.deploy.dns_followup import check_instance_dns

from tests.crmbuilder_v2.deploy.fakes import FakeDnsLookup

GODADDY = ("ns51.domaincontrol.com",)


@pytest.fixture(autouse=True)
def _secrets_in_memory(monkeypatch):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    yield
    secrets._reset_in_memory_store_for_tests()


class FakeSSH:
    class SelfHostedConfig:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    def __init__(self, fail=False):
        self.fail = fail
        self.hosts: list[str] = []

    def connect_ssh(self, config):
        if self.fail:
            raise OSError("timed out")
        self.hosts.append(config.ssh_host)

        class _C:
            def close(self_inner):
                pass

        return _C()


class FakeJob:
    def __init__(self, status=None, expiry=None, installed=True):
        self.status, self.expiry, self.installed = status, expiry, installed
        self.started: list[bool] = []

    def read_certificate_expiry(self, ssh, domain):
        return self.expiry

    def read_status(self, ssh):
        return self.status

    def run_job_now(self, ssh, log=None, *, background=False):
        self.started.append(background)

    def job_installed(self, ssh):
        return self.installed


def _instance(open_items=None) -> str:
    with session_scope() as s:
        inst = instances.create_instance(
            s, name="Chapter CRM", url="https://crm.bbmentors.org", vendor="espocrm",
            role="both", auth_method="basic",
        )
        ident = inst["instance_identifier"]
        instance_deploy_config.upsert_deploy_config(
            s, ident, ssh_host="203.0.113.7", ssh_auth_type="key",
            ssh_credential_ref=secrets.put_secret("-----BEGIN OPENSSH PRIVATE KEY-----\nx"),
            domain="crm.bbmentors.org", droplet_ip="203.0.113.7", dns_provider="manual",
            open_items=open_items or [
                {"key": "dns", "state": "needs_action", "title": "old", "opened_at": "2026-09-23T00:00:00"},
                {"key": "certificate", "state": "waiting", "title": "old"},
            ],
        )
    return ident


def _lookup(correct: bool):
    records = {("crm.bbmentors.org", "A"): ["203.0.113.7"]} if correct else {}
    return FakeDnsLookup(zone="bbmentors.org", name_servers=GODADDY, records=records)


def _items(ident):
    with session_scope() as s:
        cfg = instance_deploy_config.get_deploy_config(s, ident)
    return {i["key"]: i for i in cfg["open_items"]}, cfg


def test_dns_still_missing_keeps_the_dns_item_and_reports_the_job(v2_env):
    ident = _instance()
    job = FakeJob(status={"state": "waiting_dns", "detail": "Public DNS returns nothing"})
    out = check_instance_dns(ident, lookup=_lookup(False), ssh_module=FakeSSH(), cert_job=job)
    assert out["dns"]["code"] == "record_missing" and job.started == []
    items, _ = _items(ident)
    assert items["dns"]["title"] == "The DNS record has not been created yet"
    assert items["dns"]["opened_at"] == "2026-09-23T00:00:00"  # first opened, kept
    assert items["certificate"]["state"] == "waiting"
    assert "Waiting for DNS" in items["certificate"]["found"]


def test_dns_correct_starts_the_job_in_the_background(v2_env):
    ident = _instance()
    job = FakeJob(status={"state": "waiting_dns"})
    out = check_instance_dns(ident, lookup=_lookup(True), ssh_module=FakeSSH(), cert_job=job)
    assert out["certificate_job_started"] is True and job.started == [True]
    items, _ = _items(ident)
    assert "dns" not in items
    assert items["certificate"]["title"] == "The certificate is being installed"


def test_certificate_in_place_closes_everything_and_records_the_expiry(v2_env):
    ident = _instance()
    job = FakeJob(status={"state": "done"}, expiry="2026-12-22")
    out = check_instance_dns(ident, lookup=_lookup(True), ssh_module=FakeSSH(), cert_job=job)
    assert out["open_items"] == [] and job.started == []
    items, cfg = _items(ident)
    assert items == {} and cfg["cert_expiry_date"] == "2026-12-22"


def test_a_failed_certificate_test_needs_the_operator(v2_env):
    ident = _instance()
    job = FakeJob(status={"state": "test_failed", "detail": "Timeout during connect"})
    # DNS is not correct now, so no new attempt starts; the last one failed.
    check_instance_dns(ident, lookup=_lookup(False), ssh_module=FakeSSH(), cert_job=job)
    items, _ = _items(ident)
    assert items["certificate"]["state"] == "needs_action" and items["certificate"]["who"] == "operator"
    assert "Timeout during connect" in items["certificate"]["found"]


def test_an_unreachable_server_still_gets_its_dns_answer(v2_env):
    ident = _instance()
    out = check_instance_dns(ident, lookup=_lookup(True), ssh_module=FakeSSH(fail=True), cert_job=FakeJob())
    assert out["ssh_error"].startswith("Could not reach the server over SSH")
    items, _ = _items(ident)
    assert "dns" not in items and items["certificate"]["title"] == "old"


def test_an_instance_without_a_deploy_config_is_refused(v2_env):
    with session_scope() as s:
        ident = instances.create_instance(
            s, name="Hand-made", url="https://x.example.org", vendor="espocrm",
            role="both", auth_method="basic",
        )["instance_identifier"]
    with pytest.raises(UnprocessableError):
        check_instance_dns(ident, lookup=_lookup(True), ssh_module=FakeSSH(), cert_job=FakeJob())


def test_the_job_is_not_started_where_it_was_never_installed(v2_env):
    ident = _instance()
    job = FakeJob(status=None, installed=False)
    out = check_instance_dns(ident, lookup=_lookup(True), ssh_module=FakeSSH(), cert_job=job)
    assert out["certificate_job_started"] is False and job.started == []
