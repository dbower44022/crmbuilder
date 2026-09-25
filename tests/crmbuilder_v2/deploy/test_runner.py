"""Runner state-machine tests — PI-419 (REQ-522, DEC-945).

Every collaborator is faked through ``RunnerDeps``: provider clients, the v1
SSH module, the secret resolver, the clock. Proves the happy path registers
the instance and its deploy config; a failure after the server exists keeps
the server in the checkpoint and names it in the log; a resumed run skips the
phases already done and does not create a second server; cancel is honoured
between phases; and the production host is refused before anything is created.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import (
    deploy_runs,
    instance_deploy_config,
    instances,
    provider_credentials,
)
from crmbuilder_v2.deploy.errors import ProviderError
from crmbuilder_v2.deploy.runner import RunnerDeps, run_deploy

from tests.crmbuilder_v2.deploy.fakes import FakeDnsLookup

SPEC = {
    "instance_name": "Chapter CRM",
    "region": "nyc3",
    "size": "s-2vcpu-4gb",
    "image": "ubuntu-24-04-x64",
    "zone_id": "z1",
    "zone_name": "example.org",
    "subdomain": "crm",
    "domain": "crm.example.org",
    "letsencrypt_email": "ops@example.org",
    "admin_username": "admin",
    "admin_email": "admin@example.org",
    "ssh_key_ids": [11],
}


@pytest.fixture(autouse=True)
def _secrets_in_memory(monkeypatch):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    yield
    secrets._reset_in_memory_store_for_tests()


class FakeDO:
    def __init__(self, token, *, fail_create=False):
        self.token = token
        self.droplets: dict[str, dict] = {}
        self.created = 0
        self.keys: list[dict] = []
        self.fail_create = fail_create
        self.polls_until_active = 1

    def verify_token(self):
        return {"email": "ops@example.org"}

    def add_ssh_key(self, *, name, public_key):
        self.keys.append({"id": 77, "name": name, "public_key": public_key})
        return {"id": 77, "name": name, "fingerprint": "ff"}

    def find_droplets_by_tag(self, tag):
        return [d for d in self.droplets.values() if tag in d["tags"]]

    def create_droplet(self, *, name, region, size, image, ssh_key_ids, tags):
        if self.fail_create:
            raise ProviderError("digitalocean", "Region not available", status=422)
        self.created += 1
        d = {"id": 4242, "name": name, "status": "new", "ip": None, "region": region,
             "size": size, "tags": tags, "ssh_keys": ssh_key_ids}
        self.droplets["4242"] = d
        return dict(d)

    def get_droplet(self, droplet_id):
        d = self.droplets[str(droplet_id)]
        self.polls_until_active -= 1
        if self.polls_until_active <= 0:
            d["status"], d["ip"] = "active", "203.0.113.7"
        return dict(d)


class FakeCF:
    def __init__(self, token, *, fail=False, existing=None):
        self.token = token
        self.records: dict[str, dict] = dict(existing or {})
        self.fail = fail
        self.upserts = 0

    def get_zone(self, zone_id):
        return {"id": zone_id, "name": "example.org"}

    def find_a_record(self, zone_id, name):
        rec = self.records.get(name)
        return dict(rec) if rec else None

    def upsert_a_record(self, zone_id, *, name, ip, ttl=60, proxied=False):
        if self.fail:
            raise ProviderError("cloudflare", "Authentication error", status=403)
        assert proxied is False
        self.upserts += 1
        rec = self.records.get(name) or {"id": f"rec-{name}"}
        rec.update({"name": name, "content": ip, "proxied": proxied})
        self.records[name] = rec
        return dict(rec)


class FakeSSHModule:
    """Stands in for :mod:`crmbuilder_v2.deploy.ssh`."""

    class SelfHostedConfig:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    def __init__(self, *, verify_ok=True, install_ok=True):
        self.calls: list[str] = []
        self.verify_ok = verify_ok
        self.install_ok = install_ok
        self.configs: list[dict] = []
        self.secure: dict[str, bool] = {}

    def connect_ssh(self, config):
        self.configs.append(dict(config.__dict__))
        self.calls.append("connect")

        class _Client:
            def close(self_inner):
                pass

        return _Client()

    def phase_server_prep(self, ssh, log):
        self.calls.append("server_prep")
        log("$ apt-get update", "info")
        return True, ""

    def phase_install_espocrm(self, ssh, config, log, *, secure=True):
        self.calls.append("install")
        self.secure["install"] = secure
        log(f"$ install.sh --admin-password={config.admin_password}", "info")
        return (True, "") if self.install_ok else (False, "installer failed (exit 1)")

    def phase_post_install(self, ssh, config, log, *, secure=True):
        self.calls.append("post_install")
        self.secure["post_install"] = secure
        return True, "", ("2026-11-28" if secure else None)

    def phase_verify(self, ssh, domain, log, *, secure=True):
        self.calls.append("verify")
        self.secure["verify"] = secure
        checks = [{"check": "https", "passed": True, "detail": ""},
                  {"check": "cron", "passed": self.verify_ok, "detail": "" if self.verify_ok else "no cron"}]
        return self.verify_ok, checks


class FakeCertJob:
    """Stands in for :mod:`crmbuilder_v2.deploy.certificate_job` (PI-571)."""

    def __init__(self, *, outcome="done"):
        self.calls: list[tuple] = []
        self.outcome = outcome

    def install_job(self, ssh, domain, email, ip, log, *, zone=None):
        self.calls.append(("install_job", domain, ip))
        self.zone = zone
        return True, ""

    def run_job_now(self, ssh, log=None, *, background=False):
        self.calls.append(("run_job_now", background))

    def read_status(self, ssh):
        return {"state": self.outcome, "detail": "Connection refused on port 80" if self.outcome != "done" else ""}

    def read_certificate_expiry(self, ssh, domain):
        return "2026-12-22" if self.outcome == "done" else None

    def apply_domain(self, ssh, old, new, log):
        self.calls.append(("apply_domain", old, new))
        return True, ""


def _dns(correct=True, domain="crm.example.org", **kw):
    records = {(domain, "A"): ["203.0.113.7"]} if correct else {}
    records.update(kw.pop("records", {}))
    return FakeDnsLookup(records=records, **kw)


def _deps(do=None, cf=None, ssh=None, **kw) -> RunnerDeps:
    holder = {}

    def do_factory(token):
        holder["do"] = do or FakeDO(token)
        return holder["do"]

    def cf_factory(token):
        holder["cf"] = cf or FakeCF(token)
        return holder["cf"]

    sleeps: list[float] = []
    kw.setdefault("dns_lookup", _dns())
    kw.setdefault("cert_job", FakeCertJob())
    kw.setdefault("sleep", sleeps.append)
    deps = RunnerDeps(
        do_client=do_factory, cf_client=cf_factory, ssh=ssh or FakeSSHModule(),
        keypair=lambda c: ("PRIVATE-PEM", f"ssh-ed25519 AAAA {c}"), **kw,
    )
    deps.holder = holder  # type: ignore[attr-defined]
    deps.sleeps = sleeps  # type: ignore[attr-defined]
    return deps


def _queue(spec=SPEC) -> str:
    with session_scope() as s:
        provider_credentials.upsert_provider_credential(s, "digitalocean", token_ref=secrets.put_secret("do-tok"))
        provider_credentials.upsert_provider_credential(s, "cloudflare", token_ref=secrets.put_secret("cf-tok"))
        row = deploy_runs.create_deploy_run(
            s, spec=spec,
            secret_refs={"admin_password": secrets.put_secret("Adm1n!"),
                         "db_password": secrets.put_secret("dbpw"),
                         "db_root_password": secrets.put_secret("rootpw")},
        )
        deploy_runs.claim_next_run(s, worker_id="w1")
        return row["deploy_run_identifier"]


def _run(ident):
    with session_scope() as s:
        return deploy_runs.get_deploy_run(s, ident)


def test_happy_path_registers_instance_and_config(v2_env):
    ident = _queue()
    deps = _deps()
    status = run_deploy(ident, engagement_id="ENG-001", worker_id="w1", deps=deps)
    assert status == "succeeded"
    run = _run(ident)
    assert run["deploy_run_status"] == "succeeded"
    st = run["deploy_run_state"]
    assert st["droplet_id"] == "4242" and st["droplet_ip"] == "203.0.113.7"
    assert st["dns_record_id"] == "rec-crm.example.org"
    assert st["cert_expiry"] == "2026-11-28"
    assert st["ssh_key_id"] == 77 and st["ssh_public_key"].startswith("ssh-ed25519")
    assert all(st["phases"][p]["status"] == "done" for p in st["phases"])
    assert run["instance_identifier"] == st["instance_identifier"]

    ssh = deps.ssh
    assert ssh.calls == ["connect", "server_prep", "connect", "install",
                         "connect", "post_install", "connect", "verify"]
    cfg = ssh.configs[0]
    assert cfg["ssh_host"] == "203.0.113.7" and cfg["ssh_auth_type"] == "key"
    assert cfg["admin_password"] == "Adm1n!" and cfg["db_root_password"] == "rootpw"
    # The private key was materialized to a file for the session, then removed.
    import os
    assert not os.path.exists(cfg["ssh_credential"])
    # The generated key was registered on the account and passed to the droplet.
    do = deps.holder["do"]
    assert do.droplets["4242"]["ssh_keys"] == [11, 77]
    assert "DEP-001" in do.droplets["4242"]["tags"]

    with session_scope() as s:
        inst = instances.get_instance(s, run["instance_identifier"])
        cfg_row = instance_deploy_config.get_deploy_config(s, run["instance_identifier"])
    assert inst["instance_url"] == "https://crm.example.org"
    assert inst["instance_role"] == "both" and inst["instance_auth_method"] == "basic"
    assert secrets.get_secret(inst["instance_secret_ref"]) == "admin"
    assert secrets.get_secret(inst["instance_secret_key_ref"]) == "Adm1n!"
    assert cfg_row["droplet_id"] == "4242" and cfg_row["droplet_ip"] == "203.0.113.7"
    assert cfg_row["ssh_auth_type"] == "key" and secrets.get_secret(cfg_row["ssh_credential_ref"]) == "PRIVATE-PEM"
    assert cfg_row["dns_provider"] == "cloudflare" and cfg_row["last_deploy_run_identifier"] == ident
    assert cfg_row["cert_expiry_date"] == "2026-11-28"
    # PI-442 (REQ-544): server-management facts recorded at registration.
    assert cfg_row["hosting_provider"] == "digitalocean"
    assert cfg_row["hosting_account"] == "ops@example.org"
    assert cfg_row["hosting_console_url"] == "https://cloud.digitalocean.com/droplets/4242"
    assert cfg_row["ssh_key_public"].startswith("ssh-ed25519")
    assert cfg_row["ssh_key_fingerprint"].startswith("SHA256:")
    assert cfg_row["ssh_key_name"] == f"crmbuilder-{ident}"
    assert cfg_row["ssh_key_provider_id"] == "77"
    assert cfg_row["server_image"] == "ubuntu-24-04-x64"
    assert cfg_row["provisioned_at"] and cfg_row["last_verified_at"]

    # Secrets are masked in the log.
    log_text = "\n".join(e[2] for e in run["deploy_run_log"])
    assert "Adm1n!" not in log_text and "[secret]" in log_text
    assert "Registered instance" in log_text


def test_failure_after_server_exists_keeps_it_and_reports(v2_env):
    ident = _queue()
    deps = _deps(cf=FakeCF("x", fail=True))
    status = run_deploy(ident, engagement_id="ENG-001", worker_id="w1", deps=deps)
    assert status == "failed"
    run = _run(ident)
    assert run["deploy_run_phase"] == "create_dns"
    assert run["deploy_run_state"]["droplet_id"] == "4242"
    assert run["deploy_run_state"]["phases"]["create_dns"]["status"] == "failed"
    assert "Authentication error" in run["deploy_run_error"]
    log_text = "\n".join(e[2] for e in run["deploy_run_log"])
    assert "Kept (not destroyed): server 4242 at 203.0.113.7" in log_text
    assert run["instance_identifier"] is None
    with session_scope() as s:
        assert instances.list_instances(s) == []


def test_retry_resumes_without_a_second_server(v2_env):
    ident = _queue()
    do = FakeDO("t")
    failing_ssh = FakeSSHModule(install_ok=False)
    assert run_deploy(ident, engagement_id="ENG-001", worker_id="w1", deps=_deps(do=do, ssh=failing_ssh)) == "failed"
    assert do.created == 1
    with session_scope() as s:
        deploy_runs.requeue(s, ident)
        deploy_runs.claim_next_run(s, worker_id="w2")
    ssh = FakeSSHModule()
    status = run_deploy(ident, engagement_id="ENG-001", worker_id="w2", deps=_deps(do=do, ssh=ssh))
    assert status == "succeeded"
    assert do.created == 1  # no second server
    assert len(do.keys) == 1  # key registered once
    assert "server_prep" not in ssh.calls  # already done before the failure
    assert ssh.calls[0] == "connect" and "install" in ssh.calls
    run = _run(ident)
    log_text = "\n".join(e[2] for e in run["deploy_run_log"])
    assert "Resuming deploy run" in log_text and "already complete, skipping" in log_text


def test_verification_gaps_land_succeeded_with_issues(v2_env):
    ident = _queue()
    status = run_deploy(ident, engagement_id="ENG-001", worker_id="w1", deps=_deps(ssh=FakeSSHModule(verify_ok=False)))
    assert status == "succeeded_with_issues"
    run = _run(ident)
    assert run["instance_identifier"] is not None
    assert run["deploy_run_state"]["verify_failed"] is True


def test_cancel_between_phases(v2_env):
    ident = _queue()

    class CancellingDO(FakeDO):
        def create_droplet(self, **kw):
            with session_scope() as s:
                deploy_runs.request_cancel(s, ident)
            return super().create_droplet(**kw)

    do = CancellingDO("t")
    status = run_deploy(ident, engagement_id="ENG-001", worker_id="w1", deps=_deps(do=do))
    assert status == "cancelled"
    run = _run(ident)
    assert run["deploy_run_state"]["droplet_id"] == "4242"  # kept
    assert run["deploy_run_state"]["phases"]["create_droplet"]["status"] == "done"
    assert "wait_droplet" not in run["deploy_run_state"]["phases"]


def test_protected_host_is_refused_before_anything_is_created(v2_env):
    ident = _queue({**SPEC, "zone_name": "crmbuilder.ai", "subdomain": "api", "domain": "api.crmbuilder.ai"})
    do = FakeDO("t")
    status = run_deploy(ident, engagement_id="ENG-001", worker_id="w1", deps=_deps(do=do))
    assert status == "failed"
    assert do.created == 0 and do.keys == []
    assert "GVR-240" in _run(ident)["deploy_run_error"]


def test_missing_provider_credential_fails_validate(v2_env):
    with session_scope() as s:
        row = deploy_runs.create_deploy_run(
            s, spec=SPEC,
            secret_refs={"admin_password": secrets.put_secret("a"), "db_password": secrets.put_secret("b"),
                         "db_root_password": secrets.put_secret("c")},
        )
        deploy_runs.claim_next_run(s, worker_id="w1")
    status = run_deploy(row["deploy_run_identifier"], engagement_id="ENG-001", worker_id="w1", deps=_deps())
    assert status == "failed"
    assert "no digitalocean credential" in _run(row["deploy_run_identifier"])["deploy_run_error"]


# --- DNS never blocks the install (PI-571 / REQ-648, REQ-650, REQ-651) --------

MANUAL_SPEC = {
    **{k: v for k, v in SPEC.items() if k not in ("zone_id", "zone_name", "subdomain")},
    "domain": "crm.bbmentors.org",
    "dns_mode": "manual",
}
GODADDY = ("ns51.domaincontrol.com", "ns52.domaincontrol.com")


def _queue_manual(spec=MANUAL_SPEC) -> str:
    with session_scope() as s:
        provider_credentials.upsert_provider_credential(s, "digitalocean", token_ref=secrets.put_secret("do-tok"))
        row = deploy_runs.create_deploy_run(
            s, spec=spec,
            secret_refs={"admin_password": secrets.put_secret("Adm1n!"),
                         "db_password": secrets.put_secret("dbpw"),
                         "db_root_password": secrets.put_secret("rootpw")},
        )
        deploy_runs.claim_next_run(s, worker_id="w1")
        return row["deploy_run_identifier"]


def _manual_lookup(correct: bool, domain="crm.bbmentors.org"):
    records = {(domain, "A"): ["203.0.113.7"]} if correct else {}
    return FakeDnsLookup(zone="bbmentors.org", name_servers=GODADDY, records=records)


def _log(ident):
    return "\n".join(e[2] for e in _run(ident)["deploy_run_log"])


def _config(ident):
    with session_scope() as s:
        return instance_deploy_config.get_deploy_config(s, _run(ident)["instance_identifier"])


def test_missing_dns_record_installs_anyway_and_ends_needing_action(v2_env):
    ident = _queue_manual()
    ssh, job = FakeSSHModule(), FakeCertJob()
    deps = _deps(ssh=ssh, cert_job=job, dns_lookup=_manual_lookup(False))
    status = run_deploy(ident, engagement_id="ENG-001", worker_id="w1", deps=deps)

    assert status == "needs_action"
    assert "cf" not in deps.holder  # manual DNS never builds a Cloudflare client
    assert deps.sleeps == []  # a problem that will not fix itself is not waited on
    # Installed without a certificate, verified in the matching mode.
    assert ssh.secure == {"install": False, "post_install": False, "verify": False}
    assert job.calls == [("install_job", "crm.bbmentors.org", "203.0.113.7")]
    assert job.zone == "bbmentors.org"  # the job asks the DNS host before public DNS
    run = _run(ident)
    phases = run["deploy_run_state"]["phases"]
    assert phases["check_dns"]["status"] == "needs_action"
    assert phases["certificate"]["status"] == "waiting"
    assert phases["create_instance"]["status"] == "done"
    assert run["instance_identifier"]  # the instance is registered regardless

    items = {i["key"]: i for i in _config(ident)["open_items"]}
    assert items["dns"]["state"] == "needs_action" and items["dns"]["who"] == "client"
    assert items["dns"]["title"] == "The DNS record has not been created yet"
    assert "At GoDaddy, create a DNS record: type A, name crm, value 203.0.113.7" in items["dns"]["action"]
    assert items["certificate"]["state"] == "waiting" and items["certificate"]["who"] == "nobody"
    log = _log(ident)
    assert "Add this DNS record at GoDaddy: type A, name crm, value 203.0.113.7" in log
    assert "installed without a certificate for now" in log
    assert "Still outstanding: The DNS record has not been created yet; The certificate is waiting for DNS" in log


def test_try_again_after_dns_is_fixed_finishes_the_certificate_on_the_same_server(v2_env):
    ident = _queue_manual()
    do = FakeDO("t")
    assert run_deploy(ident, engagement_id="ENG-001", worker_id="w1",
                      deps=_deps(do=do, dns_lookup=_manual_lookup(False))) == "needs_action"
    first_instance = _run(ident)["instance_identifier"]

    with session_scope() as s:
        deploy_runs.requeue(s, ident)
        deploy_runs.claim_next_run(s, worker_id="w2")
    ssh, job = FakeSSHModule(), FakeCertJob(outcome="done")
    status = run_deploy(ident, engagement_id="ENG-001", worker_id="w2",
                        deps=_deps(do=do, ssh=ssh, cert_job=job, dns_lookup=_manual_lookup(True)))
    assert status == "succeeded"
    assert do.created == 1
    assert "install" not in ssh.calls  # the CRM is not reinstalled
    assert ("run_job_now", False) in job.calls  # DNS was correct, so the job ran at once
    assert ssh.secure["verify"] is True  # verified as a secure site afterwards
    run = _run(ident)
    assert run["instance_identifier"] == first_instance
    cfg = _config(ident)
    assert cfg["open_items"] == [] and cfg["cert_expiry_date"] == "2026-12-22"


def test_certificate_test_failure_is_reported_with_its_cause(v2_env):
    ident = _queue_manual()
    job = FakeCertJob(outcome="test_failed")
    status = run_deploy(ident, engagement_id="ENG-001", worker_id="w1",
                        deps=_deps(cert_job=job, dns_lookup=_manual_lookup(True)))
    # DNS was already correct, so the CRM went in with its certificate: the job never ran.
    assert status == "succeeded" and job.calls == []

    ident2 = _queue_manual({**MANUAL_SPEC, "domain": "crm2.bbmentors.org"})
    lookups = iter([_manual_lookup(False, "crm2.bbmentors.org")])
    deps = _deps(cert_job=job, dns_lookup=next(lookups))
    # DNS is wrong at install time but correct by the check: install without, then the job fails its test.
    deps.dns_lookup.records[("crm2.bbmentors.org", "A")] = []
    real_diag = deps.dns_lookup.authoritative

    calls = {"n": 0}

    def flip(name_servers, name, rdtype):
        calls["n"] += 1
        if calls["n"] > 3:
            deps.dns_lookup.records[("crm2.bbmentors.org", "A")] = ["203.0.113.7"]
        return real_diag(name_servers, name, rdtype)

    deps.dns_lookup.authoritative = flip
    assert run_deploy(ident2, engagement_id="ENG-001", worker_id="w1", deps=deps) == "needs_action"
    items = {i["key"]: i for i in _config(ident2)["open_items"]}
    assert list(items) == ["certificate"]
    assert items["certificate"]["state"] == "needs_action" and items["certificate"]["who"] == "operator"
    assert "Connection refused on port 80" in items["certificate"]["found"]


def test_dns_that_is_only_spreading_is_waited_on_then_passes(v2_env):
    ident = _queue()
    lookup = _dns(public={("crm.example.org", "A"): set()})
    # Empty for the install's check and the first two checks of check_dns.
    answers = iter([set()] * 5)

    def public(name, rdtype="A"):
        return next(answers, {"203.0.113.7"}) if name == "crm.example.org" and rdtype == "A" else set()

    lookup.public = public
    deps = _deps(dns_lookup=lookup)
    assert run_deploy(ident, engagement_id="ENG-001", worker_id="w1", deps=deps) == "succeeded"
    assert deps.sleeps  # it waited, because the diagnosis said the problem fixes itself
    assert "DNS is correct and spreading" in _log(ident)


def test_spreading_dns_is_not_waited_on_past_the_limit(v2_env):
    ident = _queue()
    clock = iter(range(0, 100_000, 120))
    lookup = _dns(public={("crm.example.org", "A"): set()}, negative_ttl=3600)
    deps = _deps(dns_lookup=lookup, clock=lambda: next(clock), dns_wait_limit_seconds=900)
    assert run_deploy(ident, engagement_id="ENG-001", worker_id="w1", deps=deps) == "needs_action"
    assert len(deps.sleeps) <= 900 // 120 + 1
    items = {i["key"]: i for i in _config(ident)["open_items"]}
    assert items["dns"]["state"] == "waiting" and items["dns"]["code"] == "propagating"


def test_an_existing_cloudflare_record_pointing_elsewhere_is_never_overwritten(v2_env):
    ident = _queue()
    cf = FakeCF("t", existing={"crm.example.org": {"id": "old", "content": "198.51.100.9", "proxied": False}})
    lookup = _dns(correct=False, records={("crm.example.org", "A"): ["198.51.100.9"]})
    status = run_deploy(ident, engagement_id="ENG-001", worker_id="w1", deps=_deps(cf=cf, dns_lookup=lookup))
    assert status == "needs_action"
    assert cf.upserts == 0 and cf.records["crm.example.org"]["content"] == "198.51.100.9"
    items = {i["key"]: i for i in _config(ident)["open_items"]}
    assert items["dns"]["code"] == "wrong_address"  # the diagnosis after the install replaced the first finding
    phases = _run(ident)["deploy_run_state"]["phases"]
    assert phases["create_dns"]["status"] == "needs_action"


def test_try_again_with_a_corrected_address_changes_the_installed_crm(v2_env):
    ident = _queue_manual({**MANUAL_SPEC, "domain": "crm.bbmentor.org"})  # typo
    do = FakeDO("t")
    wrong = FakeDnsLookup(zone=None)
    assert run_deploy(ident, engagement_id="ENG-001", worker_id="w1",
                      deps=_deps(do=do, dns_lookup=wrong)) == "needs_action"
    items = {i["key"]: i for i in _config(ident)["open_items"]}
    assert items["dns"]["code"] == "no_name_servers"

    with session_scope() as s:
        deploy_runs.requeue(s, ident, spec={**MANUAL_SPEC, "domain": "crm.bbmentors.org"})
        deploy_runs.claim_next_run(s, worker_id="w2")
    ssh, job = FakeSSHModule(), FakeCertJob(outcome="done")
    status = run_deploy(ident, engagement_id="ENG-001", worker_id="w2",
                        deps=_deps(do=do, ssh=ssh, cert_job=job, dns_lookup=_manual_lookup(True)))
    assert status == "succeeded"
    assert ("apply_domain", "crm.bbmentor.org", "crm.bbmentors.org") in job.calls
    assert "install" not in ssh.calls and do.created == 1
    run = _run(ident)
    with session_scope() as s:
        inst = instances.get_instance(s, run["instance_identifier"])
    assert inst["instance_url"] == "https://crm.bbmentors.org"
    assert _config(ident)["domain"] == "crm.bbmentors.org"


def test_happy_path_logs_a_plain_dns_verdict(v2_env):
    ident = _queue()
    assert run_deploy(ident, engagement_id="ENG-001", worker_id="w1", deps=_deps()) == "succeeded"
    log = _log(ident)
    assert "DNS already points at the server, so the CRM is installed with its certificate." in log
    assert "DNS is correct: crm.example.org points at 203.0.113.7." in log



def test_a_new_server_that_refuses_ssh_at_first_is_waited_for(v2_env):
    """DEP-002 (09-23-26): the server was active but not yet listening on port 22."""
    ident = _queue()

    class SlowSSH(FakeSSHModule):
        refusals = 2

        def connect_ssh(self, config):
            if SlowSSH.refusals:
                SlowSSH.refusals -= 1
                raise OSError("[Errno None] Unable to connect to port 22 on 203.0.113.7")
            return super().connect_ssh(config)

    deps = _deps(ssh=SlowSSH())
    assert run_deploy(ident, engagement_id="ENG-001", worker_id="w1", deps=deps) == "succeeded"
    assert deps.sleeps.count(10) == 2
    log = _log(ident)
    assert "Waiting for the new server to accept SSH logins…" in log
    assert "The server accepts SSH logins." in log


def test_a_server_that_never_accepts_ssh_fails_with_try_again(v2_env):
    ident = _queue()

    class DeadSSH(FakeSSHModule):
        def connect_ssh(self, config):
            raise OSError("Unable to connect to port 22")

    clock = iter(range(0, 10_000, 60))
    deps = _deps(ssh=DeadSSH(), clock=lambda: next(clock))
    assert run_deploy(ident, engagement_id="ENG-001", worker_id="w1", deps=deps) == "failed"
    err = _run(ident)["deploy_run_error"]
    assert "did not accept an SSH login within 5 minutes" in err and "Try again" in err
    assert _run(ident)["deploy_run_state"]["phases"]["server_prep"]["status"] == "failed"


def test_a_run_for_a_deployment_uses_its_credentials_and_attaches_the_instance(v2_env):
    """PI-576: a run queued for a deployment resolves the deployment's own
    DigitalOcean token over the application's and attaches the instance it
    registers to that deployment."""
    from crmbuilder_v2.segments.client_management.repositories import (
        client as client_repo,
    )
    from crmbuilder_v2.segments.operate.repositories import deployments

    with session_scope() as s:
        client_repo.create_client(s, name="Rochester Business Mentors")
        client_repo.set_engagement_clients(
            s, "ENG-001", clients=["CLI-001"], primary="CLI-001"
        )
        deployments.create_deployment(
            s, purpose="client_own", client="CLI-001", application="ENG-001", name="Rochester"
        )
        provider_credentials.upsert_provider_credential(
            s, "digitalocean", token_ref=secrets.put_secret("app-do-tok")
        )
        provider_credentials.upsert_provider_credential(
            s, "cloudflare", token_ref=secrets.put_secret("cf-tok")
        )
        provider_credentials.upsert_provider_credential(
            s,
            "digitalocean",
            token_ref=secrets.put_secret("dpl-do-tok"),
            deployment_identifier="DPL-001",
        )
        row = deploy_runs.create_deploy_run(
            s,
            spec=SPEC,
            secret_refs={
                "admin_password": secrets.put_secret("Adm1n!"),
                "db_password": secrets.put_secret("dbpw"),
                "db_root_password": secrets.put_secret("rootpw"),
            },
            deployment_identifier="DPL-001",
        )
        deploy_runs.claim_next_run(s, worker_id="w1")
        ident = row["deploy_run_identifier"]
    deps = _deps()
    assert run_deploy(ident, engagement_id="ENG-001", worker_id="w1", deps=deps) == "succeeded"
    assert deps.holder["do"].token == "dpl-do-tok"
    run = _run(ident)
    assert run["deployment_identifier"] == "DPL-001"
    with session_scope() as s:
        d = deployments.get_deployment(s, "DPL-001")
    assert d["deployment_instance_identifier"] == run["instance_identifier"]
    assert d["instance"]["instance_url"] == "https://crm.example.org"
    log_text = "\n".join(e[2] for e in run["deploy_run_log"])
    assert "Deployment DPL-001 now holds" in log_text
