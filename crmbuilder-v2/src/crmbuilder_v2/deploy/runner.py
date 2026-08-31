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
* ``wait_droplet`` / ``create_dns`` / ``wait_dns`` — poll to active + IP,
  upsert the DNS-only A record, wait for the name to resolve.
* ``server_prep`` / ``install_espocrm`` / ``post_install`` / ``verify`` — the
  v1 SSH phases from ``automation.core.deployment.ssh_deploy``, unchanged.
* ``create_instance`` — register the instance and its deploy config in one
  transaction with the terminal status.

A phase failure lands ``failed`` with everything built kept in the checkpoint
and named in the log — nothing is destroyed (DEC-945). Cancellation is
honoured between phases only.

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
_RESUMABLE_DONE = frozenset(
    {"server_prep", "install_espocrm", "post_install", "verify"}
)


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
    #: Module exposing the v1 SSH phase functions (``ssh_deploy`` by default).
    ssh: Any = None
    resolve_secret: Callable[[str], str] = secrets.get_secret
    store_secret: Callable[[str], str] = secrets.put_secret
    keypair: Callable[[str], tuple[str, str]] = generate_keypair
    #: Resolve a name to its A records — see :func:`resolve_a_public`.
    resolve_a: Callable[[str], set[str]] = None  # type: ignore[assignment]
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    droplet_wait_seconds: int = 600
    droplet_poll_seconds: int = 10
    dns_wait_seconds: int = 600
    dns_poll_seconds: int = 30

    def __post_init__(self) -> None:
        if self.ssh is None:
            from automation.core.deployment import ssh_deploy

            self.ssh = ssh_deploy
        if self.resolve_a is None:
            self.resolve_a = resolve_a_public


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
                _mark(run, phase, "done", state=updates or None)
                if updates:
                    run.state.update(updates)
            if run.state.get("verify_failed"):
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
    with session_scope() as s:
        do_row = provider_credentials.get_provider_credential(s, "digitalocean")
        cf_row = provider_credentials.get_provider_credential(s, "cloudflare")
    for name, row in (("digitalocean", do_row), ("cloudflare", cf_row)):
        if not row:
            raise DeployPhaseError("validate", f"no {name} credential configured")
    do_token = deps.resolve_secret(do_row["token_ref"])
    cf_token = deps.resolve_secret(cf_row["token_ref"])
    log.masks.extend([do_token, cf_token])
    for name in ("admin_password", "db_password", "db_root_password"):
        ref = run.secret_refs.get(name)
        if not ref:
            raise DeployPhaseError("validate", f"run has no {name} secret")
        run.secrets[name] = deps.resolve_secret(ref)
        log.masks.append(run.secrets[name])
    run.do = deps.do_client(do_token)
    run.cf = deps.cf_client(cf_token)
    account = run.do.verify_token()
    log(f"DigitalOcean token ok ({account.get('email', 'account')})", "success")
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


def _phase_create_dns(run: _Run, deps: RunnerDeps, log: _Log) -> dict:
    rec = run.cf.upsert_a_record(
        run.spec.zone_id, name=run.spec.domain, ip=run.state["droplet_ip"], proxied=False
    )
    log(f"DNS A record {run.spec.domain} → {run.state['droplet_ip']} (DNS-only)", "success")
    return {"dns_record_id": rec.get("id")}


def _phase_wait_dns(run: _Run, deps: RunnerDeps, log: _Log) -> dict:
    """Wait until public resolvers return the server's IP for the domain.

    Replaces the v1 ``wait_for_dns`` (which used the host resolver) for the
    reason given at :data:`PUBLIC_RESOLVERS`.
    """
    domain, ip = run.spec.domain, run.state["droplet_ip"]
    deadline = deps.clock() + deps.dns_wait_seconds
    while True:
        seen = deps.resolve_a(domain)
        if ip in seen:
            log(f"{domain} resolves to {ip} on public resolvers", "success")
            return {}
        remaining = int(deadline - deps.clock())
        if remaining <= 0:
            raise DeployPhaseError(
                "wait_dns",
                f"{domain} did not resolve to {ip} within {deps.dns_wait_seconds}s "
                f"(public resolvers returned {sorted(seen) or 'nothing'})",
            )
        what = f"resolves to {sorted(seen)}" if seen else "does not resolve yet"
        log(f"DNS not ready: {domain} {what}. Retrying in {deps.dns_poll_seconds}s ({remaining}s remaining)…", "info")
        deps.sleep(deps.dns_poll_seconds)


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


def _with_ssh(run: _Run, deps: RunnerDeps, fn):
    with private_key_file(run.secrets["ssh_private_key"]) as key_path:
        _, fields = _ssh_config(run, key_path)
        config = deps.ssh.SelfHostedConfig(**fields)
        client = deps.ssh.connect_ssh(config)
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

    return _with_ssh(run, deps, go)


def _phase_install(run: _Run, deps: RunnerDeps, log: _Log) -> dict:
    def go(client, config):
        ok, err = deps.ssh.phase_install_espocrm(client, config, log)
        if not ok:
            raise DeployPhaseError("install_espocrm", err)
        return {}

    return _with_ssh(run, deps, go)


def _phase_post_install(run: _Run, deps: RunnerDeps, log: _Log) -> dict:
    def go(client, config):
        ok, err, cert_expiry = deps.ssh.phase_post_install(client, config, log)
        if not ok:
            raise DeployPhaseError("post_install", err)
        return {"cert_expiry": cert_expiry} if cert_expiry else {}

    return _with_ssh(run, deps, go)


def _phase_verify(run: _Run, deps: RunnerDeps, log: _Log) -> dict:
    def go(client, config):
        ok, checks = deps.ssh.phase_verify(client, run.spec.domain, log)
        failed = [c["check"] for c in checks if not c.get("passed")]
        if failed:
            log(f"Verification found gaps: {', '.join(failed)}", "warning")
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
            dns_provider="cloudflare",
            droplet_id=run.state.get("droplet_id"),
            droplet_ip=run.state.get("droplet_ip"),
            droplet_region=run.state.get("droplet_region") or run.spec.region,
            droplet_size=run.state.get("droplet_size") or run.spec.size,
            dns_record_id=run.state.get("dns_record_id"),
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
        )
    log(f"Registered instance {ident} at https://{run.spec.domain}", "success")
    return {"instance_identifier": ident}


_PHASES: dict[str, Callable[[_Run, RunnerDeps, _Log], dict]] = {
    "validate": _phase_validate,
    "create_droplet": _phase_create_droplet,
    "wait_droplet": _phase_wait_droplet,
    "create_dns": _phase_create_dns,
    "wait_dns": _phase_wait_dns,
    "server_prep": _phase_server_prep,
    "install_espocrm": _phase_install,
    "post_install": _phase_post_install,
    "verify": _phase_verify,
    "create_instance": _phase_create_instance,
}
assert set(_PHASES) == set(DEPLOY_RUN_PHASE_ORDER)
