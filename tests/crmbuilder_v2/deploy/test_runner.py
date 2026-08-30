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
    def __init__(self, token, *, fail=False):
        self.token = token
        self.records: dict[str, dict] = {}
        self.fail = fail

    def get_zone(self, zone_id):
        return {"id": zone_id, "name": "example.org"}

    def upsert_a_record(self, zone_id, *, name, ip, ttl=60, proxied=False):
        if self.fail:
            raise ProviderError("cloudflare", "Authentication error", status=403)
        assert proxied is False
        rec = self.records.get(name) or {"id": f"rec-{name}"}
        rec.update({"name": name, "content": ip, "proxied": proxied})
        self.records[name] = rec
        return dict(rec)


class FakeSSHModule:
    """Stands in for ``automation.core.deployment.ssh_deploy``."""

    class SelfHostedConfig:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    def __init__(self, *, verify_ok=True, install_ok=True):
        self.calls: list[str] = []
        self.verify_ok = verify_ok
        self.install_ok = install_ok
        self.configs: list[dict] = []

    def wait_for_dns(self, domain, ip, log, *, timeout, interval):
        self.calls.append("wait_for_dns")
        log(f"{domain} resolves to {ip}", "info")
        return True

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

    def phase_install_espocrm(self, ssh, config, log):
        self.calls.append("install")
        log(f"$ install.sh --admin-password={config.admin_password}", "info")
        return (True, "") if self.install_ok else (False, "installer failed (exit 1)")

    def phase_post_install(self, ssh, config, log):
        self.calls.append("post_install")
        return True, "", "2026-11-28"

    def phase_verify(self, ssh, domain, log):
        self.calls.append("verify")
        checks = [{"check": "https", "passed": True, "detail": ""},
                  {"check": "cron", "passed": self.verify_ok, "detail": "" if self.verify_ok else "no cron"}]
        return self.verify_ok, checks


def _deps(do=None, cf=None, ssh=None, **kw) -> RunnerDeps:
    holder = {}

    def do_factory(token):
        holder["do"] = do or FakeDO(token)
        return holder["do"]

    def cf_factory(token):
        holder["cf"] = cf or FakeCF(token)
        return holder["cf"]

    deps = RunnerDeps(
        do_client=do_factory, cf_client=cf_factory, ssh=ssh or FakeSSHModule(),
        sleep=lambda _s: None, keypair=lambda c: ("PRIVATE-PEM", f"ssh-ed25519 AAAA {c}"),
        **kw,
    )
    deps.holder = holder  # type: ignore[attr-defined]
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
    assert ssh.calls == ["wait_for_dns", "connect", "server_prep", "connect", "install",
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
    assert ssh.calls[:2] == ["wait_for_dns", "connect"] and "install" in ssh.calls
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
