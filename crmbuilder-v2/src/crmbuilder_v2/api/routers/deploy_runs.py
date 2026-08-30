"""Deploy-run endpoints — PI-419 (REQ-522, PRJ-111, DEC-945).

``POST /deploy-runs`` validates a provisioning request, stores its passwords
behind the secret boundary (REQ-157), and queues a deploy run (202) for the
deploy worker. The desktop polls ``GET /deploy-runs/{id}`` (``log_after``
returns only new log lines) and can cancel or retry. Administrator-only:
a run creates billable infrastructure and changes public DNS. Literal
sub-paths (``/worker``) precede ``/{identifier}`` (GVR-153). All responses
use the ``{data, meta, errors}`` envelope; secret references are never
returned.
"""

from __future__ import annotations

import secrets as _random
from typing import Any

from fastapi import APIRouter, Depends

from crmbuilder_v2.access.exceptions import (
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.principal_scope import get_active_principal
from crmbuilder_v2.access.repositories import deploy_runs, provider_credentials
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.principal_deps import require_permission
from crmbuilder_v2.api.schemas import DeployRunCreateIn
from crmbuilder_v2.api.secret_boundary import store_secret
from crmbuilder_v2.deploy.spec import validate_spec

router = APIRouter(
    prefix="/deploy-runs",
    tags=["deploy-runs"],
    dependencies=[Depends(require_permission("admin"))],
)

#: Set by the API lifespan when an in-process worker is running.
_worker_ref: dict[str, Any] = {"worker": None}


def register_worker(worker: Any | None) -> None:
    """Let ``GET /deploy-runs/worker`` report the in-process worker's health."""
    _worker_ref["worker"] = worker


def _public(row: dict, *, log_after: int | None = None) -> dict:
    """Strip secret refs; optionally return only log lines from ``log_after``."""
    out = {k: v for k, v in row.items() if k != "deploy_run_secret_refs"}
    out["secrets_configured"] = sorted((row.get("deploy_run_secret_refs") or {}).keys())
    if "deploy_run_log" in out:
        log = out["deploy_run_log"] or []
        out["log_length"] = len(log)
        if log_after is not None:
            out["deploy_run_log"] = log[max(log_after, 0):]
    return out


@router.get("/worker")
def worker_status():
    """Whether a deploy worker is executing runs from this service."""
    worker = _worker_ref["worker"]
    return ok(
        {
            "worker_active": bool(worker and worker.alive),
            "worker_id": getattr(worker, "worker_id", None),
            "last_poll_at": getattr(worker, "last_poll_at", None),
            "current_run": getattr(worker, "current_run", None),
        }
    )


@router.get("")
def list_all(instance: str | None = None, status: str | None = None, limit: int | None = None):
    """Deploy runs newest first (log omitted), optionally filtered."""
    with readonly_session() as s:
        rows = deploy_runs.list_deploy_runs(
            s, instance_identifier=instance, status=status, limit=limit
        )
        return ok([_public(r) for r in rows])


@router.get("/{identifier}")
def get(identifier: str, log_after: int | None = None):
    """One run in full; ``log_after=N`` returns only log lines at index ≥ N."""
    with readonly_session() as s:
        row = deploy_runs.get_deploy_run(s, identifier)
        if row is None:
            raise NotFoundError("deploy_run", identifier)
        return ok(_public(row, log_after=log_after))


@router.post("", status_code=202)
def create(body: DeployRunCreateIn):
    """Validate and queue a deploy run; the worker picks it up."""
    spec = validate_spec(body.model_dump(exclude={"admin_password", "db_password", "db_root_password"}))
    if not body.admin_password.strip():
        raise UnprocessableError([FieldError("admin_password", "required", "admin_password is required")])
    with readonly_session() as s:
        have = {r["provider"] for r in provider_credentials.list_provider_credentials(s)}
        active = deploy_runs.active_run_for_domain(s, spec.domain)
    missing = sorted({"digitalocean", "cloudflare"} - have)
    if missing:
        raise UnprocessableError(
            [
                FieldError(
                    p, "missing_provider_credential", f"no {p} credential is configured"
                )
                for p in missing
            ]
        )
    if active:
        raise UnprocessableError(
            [
                FieldError(
                    "subdomain",
                    "run_in_progress",
                    f"{active['deploy_run_identifier']} is already "
                    f"{active['deploy_run_status']} for {spec.domain}",
                )
            ]
        )
    secret_refs = {
        "admin_password": store_secret(body.admin_password.strip(), field="admin_password"),
        "db_password": store_secret(
            (body.db_password or "").strip() or _random.token_urlsafe(18), field="db_password"
        ),
        "db_root_password": store_secret(
            (body.db_root_password or "").strip() or _random.token_urlsafe(18),
            field="db_root_password",
        ),
    }
    principal = get_active_principal()
    with writable_session() as s:
        row = deploy_runs.create_deploy_run(
            s,
            spec=spec.to_dict(),
            secret_refs=secret_refs,
            requested_by=getattr(principal, "principal_id", None),
        )
        return ok(_public(row))


@router.post("/{identifier}/cancel")
def cancel(identifier: str):
    """Cancel a queued run now, or ask a running one to stop between phases."""
    with writable_session() as s:
        if deploy_runs.get_deploy_run(s, identifier) is None:
            raise NotFoundError("deploy_run", identifier)
        return ok(_public(deploy_runs.request_cancel(s, identifier)))


@router.post("/{identifier}/retry")
def retry(identifier: str):
    """Re-queue a failed or cancelled run; it resumes at the phase that did not finish."""
    with writable_session() as s:
        if deploy_runs.get_deploy_run(s, identifier) is None:
            raise NotFoundError("deploy_run", identifier)
        return ok(_public(deploy_runs.requeue(s, identifier)))
