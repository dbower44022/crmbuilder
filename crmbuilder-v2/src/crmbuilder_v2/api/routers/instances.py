"""Instance endpoints — PI-186 entity (PRJ-027).

Standard eight-endpoint set delegating to
:mod:`crmbuilder_v2.access.repositories.instances`. This router owns the
secret boundary (REQ-157): the write-only plaintext ``secret`` / ``secret_key``
inputs are stored in the OS keyring via :mod:`crmbuilder_v2.secrets` and only
the opaque references reach the data layer; plaintext is never persisted and
never echoed back. Request bodies may also carry an inline ``references`` array
and, on a backfill create, a ``timestamps`` dict. All responses use the
``{data, meta, errors}`` envelope.
"""

from __future__ import annotations

import dataclasses
import logging
from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from crmbuilder_v2 import secrets
from crmbuilder_v2.access.engagement_scope import get_active_engagement
from crmbuilder_v2.access.exceptions import (
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import (
    instance_membership,
    instances,
    inventory,
    publish_runs,
)
from crmbuilder_v2.adapters.espocrm.client import RestDesignClient
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    InstanceCreateIn,
    InstancePatchIn,
    InstanceReplaceIn,
)
from crmbuilder_v2.config import get_settings
from crmbuilder_v2.introspect.espo_client import EspoIntrospectionClient
from crmbuilder_v2.introspect.reconcile import (
    ReconcileError,
    reconcile_associations,
    reconcile_entities,
    reconcile_field_permissions,
    reconcile_fields,
    reconcile_filtered_tabs,
    reconcile_layouts,
    reconcile_roles,
    reconcile_teams,
)
from crmbuilder_v2.publish import service as publish_service

router = APIRouter(prefix="/instances", tags=["instances"])
_FIELD_PREFIX = "instance_"


def _edges(body) -> list[dict] | None:
    return [e.model_dump() for e in body.references] if body.references else None


def _store(value: str | None) -> str | None:
    """Store a plaintext secret in the keyring, returning its opaque reference.

    :param value: A plaintext secret, or ``None``/empty for no secret.
    :returns: The keyring reference, or ``None`` when no secret was supplied.
    """
    return secrets.put_secret(value) if value else None


@router.get("")
def list_all(
    include_deleted: bool = False,
    status: str | None = None,
    role: str | None = None,
):
    with readonly_session() as s:
        return ok(
            instances.list_instances(
                s, include_deleted=include_deleted, status=status, role=role
            )
        )


@router.get("/next-identifier")
def next_identifier():
    with readonly_session() as s:
        return ok({"next": instances.next_instance_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = instances.get_instance(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("instance", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: InstanceCreateIn):
    with writable_session() as s:
        return ok(
            instances.create_instance(
                s,
                name=body.instance_name,
                url=body.instance_url,
                vendor=body.instance_vendor or "espocrm",
                role=body.instance_role or "both",
                auth_method=body.instance_auth_method or "api_key",
                secret_ref=_store(body.secret),
                secret_key_ref=_store(body.secret_key),
                status=body.instance_status or "active",
                notes=body.instance_notes,
                identifier=body.instance_identifier,
                references=_edges(body),
                timestamps=body.timestamps,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: InstanceReplaceIn):
    with writable_session() as s:
        current = instances.get_instance(s, identifier, include_deleted=True)
        if current is None:
            raise NotFoundError("instance", identifier)
        # PUT preserves the existing secret unless a new plaintext is supplied.
        if body.secret is not None:
            secret_ref = _store(body.secret)
            secrets.delete_secret(current.get("instance_secret_ref"))
        else:
            secret_ref = current.get("instance_secret_ref")
        if body.secret_key is not None:
            secret_key_ref = _store(body.secret_key)
            secrets.delete_secret(current.get("instance_secret_key_ref"))
        else:
            secret_key_ref = current.get("instance_secret_key_ref")
        return ok(
            instances.update_instance(
                s,
                identifier,
                instance_identifier=body.instance_identifier,
                name=body.instance_name,
                url=body.instance_url,
                vendor=body.instance_vendor or "espocrm",
                role=body.instance_role or "both",
                auth_method=body.instance_auth_method or "api_key",
                secret_ref=secret_ref,
                secret_key_ref=secret_key_ref,
                status=body.instance_status or "active",
                notes=body.instance_notes,
                references=_edges(body),
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: InstancePatchIn):
    provided = body.model_dump(exclude_unset=True)
    references = provided.pop("references", None)
    has_secret = "secret" in provided
    has_secret_key = "secret_key" in provided
    secret = provided.pop("secret", None)
    secret_key = provided.pop("secret_key", None)
    fields = {key[len(_FIELD_PREFIX):]: value for key, value in provided.items()}
    with writable_session() as s:
        current = instances.get_instance(s, identifier, include_deleted=True)
        if current is None:
            raise NotFoundError("instance", identifier)
        if has_secret:
            secrets.delete_secret(current.get("instance_secret_ref"))
            fields["secret_ref"] = _store(secret)
        if has_secret_key:
            secrets.delete_secret(current.get("instance_secret_key_ref"))
            fields["secret_key_ref"] = _store(secret_key)
        return ok(
            instances.patch_instance(s, identifier, references=references, **fields)
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(instances.delete_instance(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(instances.restore_instance(s, identifier))


@router.get("/{identifier}/memberships")
def list_memberships(
    identifier: str, member_type: str | None = None, state: str | None = None
):
    """Per-(object, instance) membership rows for this instance (PI-185)."""
    with readonly_session() as s:
        if instances.get_instance(s, identifier, include_deleted=True) is None:
            raise NotFoundError("instance", identifier)
        return ok(
            instance_membership.list_memberships(
                s,
                instance_identifier=identifier,
                member_type=member_type,
                state=state,
            )
        )


@router.get("/{identifier}/membership-summary")
def membership_summary(identifier: str):
    """Per-member-type present/drifted/absent counts for this instance (PI-188)."""
    with readonly_session() as s:
        if instances.get_instance(s, identifier, include_deleted=True) is None:
            raise NotFoundError("instance", identifier)
        return ok(inventory.membership_summary(s, instance_identifier=identifier))


@router.get("/{identifier}/publish-plan")
def publish_plan(identifier: str):
    """The PRJ-025 publish handoff: canonical objects to push to this target.

    Every canonical design object not already ``present`` in the target
    (drifted / absent / never audited) — the set PRJ-025 generates and applies.
    """
    with readonly_session() as s:
        if instances.get_instance(s, identifier, include_deleted=True) is None:
            raise NotFoundError("instance", identifier)
        return ok(inventory.publish_plan(s, instance_identifier=identifier))


def _audit_introspection_client(s, identifier: str) -> EspoIntrospectionClient:
    """Resolve an auditable instance + its keyring creds into an introspection
    client, or raise the same 404 / not_auditable / missing_credentials errors
    the audit endpoints share."""
    rec = instances.get_instance(s, identifier)
    if rec is None:
        raise NotFoundError("instance", identifier)
    if rec.get("instance_role") == "target":
        raise UnprocessableError(
            [
                FieldError(
                    "instance_role",
                    "not_auditable",
                    "a target-only instance cannot be audited; set its "
                    "role to source or both",
                )
            ]
        )
    ref = rec.get("instance_secret_ref")
    api_key = secrets.get_secret(ref) if ref else ""
    if not api_key:
        raise UnprocessableError(
            [
                FieldError(
                    "secret",
                    "missing_credentials",
                    "instance has no stored credentials to authenticate the "
                    "audit",
                )
            ]
        )
    key_ref = rec.get("instance_secret_key_ref")
    return EspoIntrospectionClient(
        base_url=rec["instance_url"],
        api_key=api_key,
        secret_key=secrets.get_secret(key_ref) if key_ref else None,
        auth_method=rec.get("instance_auth_method") or "api_key",
    )


#: The audit's reconcile areas in run order (PI-274 — REQ-309). Each maps a URL
#: slug to a human label + its reconcile function; the per-area endpoint runs
#: exactly one, so the desktop can drive them in sequence and show live progress.
_AUDIT_AREAS: dict[str, tuple[str, object]] = {
    "entities": ("Entities", reconcile_entities),
    "fields": ("Fields", reconcile_fields),
    "associations": ("Relationships", reconcile_associations),
    "layouts": ("Layouts", reconcile_layouts),
    "roles": ("Roles", reconcile_roles),
    "field-permissions": ("Field permissions", reconcile_field_permissions),
    "teams": ("Teams", reconcile_teams),
    "filtered-tabs": ("Filtered tabs", reconcile_filtered_tabs),
}

#: The area slugs in run order — the order the desktop issues per-area calls.
AUDIT_AREA_ORDER: list[str] = list(_AUDIT_AREAS)


@router.get("/audit/areas")
def audit_areas():
    """The ordered audit areas the desktop drives, for the progress view."""
    return ok(
        [{"area": a, "label": _AUDIT_AREAS[a][0]} for a in AUDIT_AREA_ORDER]
    )


@router.post("/{identifier}/audit")
def audit(identifier: str):
    """Audit (pull) this instance, reconciling its structure into the inventory.

    Runs every reconcile area in one request and returns the per-object-type
    summary. This all-in-one form is retained for non-interactive callers; the
    desktop drives the per-area endpoint below for live progress (PI-274).
    """
    with writable_session() as s:
        client = _audit_introspection_client(s, identifier)
        try:
            return ok(
                {
                    key.replace("-", "_"): fn(
                        s, instance_identifier=identifier, client=client
                    )
                    for key, (_label, fn) in _AUDIT_AREAS.items()
                }
            )
        except ReconcileError as exc:
            raise UnprocessableError(
                [FieldError("audit", "introspection_failed", str(exc))]
            ) from exc


@router.post("/{identifier}/audit/{area}")
def audit_area(identifier: str, area: str):
    """Reconcile a single audit area (PI-274 — REQ-308/309/310).

    Runs exactly one reconcile step so the desktop can drive the areas in
    sequence and show live progress. Returns the area's ``summary`` plus a
    ``log`` of ``[message, level]`` lines the step surfaced (e.g. an entity
    whose fields could not be read), for the operator's running audit log.
    """
    spec = _AUDIT_AREAS.get(area)
    if spec is None:
        raise NotFoundError("audit area", area)
    label, fn = spec
    log: list[list[str]] = []
    with writable_session() as s:
        client = _audit_introspection_client(s, identifier)
        try:
            summary = fn(
                s,
                instance_identifier=identifier,
                client=client,
                progress=lambda m, lvl: log.append([m, lvl]),
            )
        except ReconcileError as exc:
            raise UnprocessableError(
                [FieldError("audit", "introspection_failed", str(exc))]
            ) from exc
        return ok(
            {"area": area, "label": label, "summary": summary, "log": log}
        )


# ── Publish (PRJ-042 — REQ-287 + REQ-288) ─────────────────────────────────


def _serialize_publish_result(result: publish_service.PublishResult) -> dict:
    """Render a :class:`PublishResult` as a JSON-safe envelope payload."""
    return {
        "engine": result.engine,
        "target_instance": result.target_instance,
        "validate_only": result.validate_only,
        "preview": result.preview,
        "validation_failed": result.validation_failed,
        "deferrals": [dataclasses.asdict(d) for d in result.deferrals],
        "manual_config": result.manual_config,
        "verification": (
            dataclasses.asdict(result.verification)
            if result.verification is not None
            else None
        ),
        "aborted": result.aborted,
        "abort_reason": result.abort_reason,
        "backup_captured": result.backup is not None,
        "programs": [
            {
                "filename": p.filename,
                "deployed": p.deployed,
                "validation_errors": p.validation_errors,
                "summary": (
                    dataclasses.asdict(p.report.summary) if p.report else None
                ),
                "log": [list(line) for line in p.log],
            }
            for p in result.programs
        ],
    }


def _publish_run_status(result: publish_service.PublishResult) -> str:
    """Map a publish result to a terminal ``publish_run`` status (REQ-293)."""
    if result.aborted:
        return "aborted"
    if result.validation_failed or any(
        not p.deployed for p in result.programs
    ):
        return "failed"
    verify = result.verification
    if verify is not None and verify.ran and verify.conclusive and not (
        verify.all_present
    ):
        return "succeeded_with_issues"
    return "succeeded"


def _publish_run_summary(result: publish_service.PublishResult) -> dict:
    """A compact outcome summary stored on the publish_run row (REQ-293)."""
    return {
        "deployed": [p.filename for p in result.programs if p.deployed],
        "not_deployed": [
            p.filename for p in result.programs if not p.deployed
        ],
        "verification": (
            dataclasses.asdict(result.verification)
            if result.verification is not None
            else None
        ),
        "manual_config_items": len(result.deferrals),
    }


def _record_publish_run(
    identifier: str,
    result: publish_service.PublishResult,
    *,
    scope: list[str] | None,
    started_at: datetime,
    ended_at: datetime,
) -> str | None:
    """Persist a publish_run row for a completed real publish (best-effort).

    Recording failure never breaks the publish response — the live CRM was
    already written; a lost log entry is surfaced as a warning, not an error.
    """
    try:
        with writable_session() as s:
            row = publish_runs.create_publish_run(
                s,
                instance_identifier=identifier,
                status=_publish_run_status(result),
                scope=scope,
                backup=result.backup,
                summary=_publish_run_summary(result),
                started_at=started_at,
                ended_at=ended_at,
            )
        return row["publish_run_identifier"]
    except Exception:  # pragma: no cover - defensive; logged, never fatal
        logging.getLogger(__name__).warning(
            "failed to record publish_run for %s", identifier, exc_info=True
        )
        return None


def _resolve_publish_target(identifier: str) -> tuple[dict, str, str | None]:
    """Fetch the target instance and resolve its keyring credentials.

    Mirrors the audit resolution, inverted for the target role: a
    ``source``-only instance cannot be published to, and a target with no
    stored credentials cannot authenticate the publish.
    """
    with readonly_session() as s:
        rec = instances.get_instance(s, identifier)
        if rec is None:
            raise NotFoundError("instance", identifier)
        if rec.get("instance_role") == "source":
            raise UnprocessableError(
                [
                    FieldError(
                        "instance_role",
                        "not_publishable",
                        "a source-only instance cannot be a publish target; "
                        "set its role to target or both",
                    )
                ]
            )
        ref = rec.get("instance_secret_ref")
        api_key = secrets.get_secret(ref) if ref else ""
        if not api_key:
            raise UnprocessableError(
                [
                    FieldError(
                        "secret",
                        "missing_credentials",
                        "instance has no stored credentials to authenticate "
                        "the publish",
                    )
                ]
            )
        key_ref = rec.get("instance_secret_key_ref")
        secret_key = secrets.get_secret(key_ref) if key_ref else None
    return rec, api_key, secret_key


def _run_publish(
    identifier: str,
    *,
    validate_only: bool = False,
    preview: bool = False,
    scope: list[str] | None = None,
    allow_no_backup: bool = False,
):
    """Resolve the target + active-engagement design source, then publish.

    A real publish (not validate-only / preview) captures a pre-publish backup
    of the target (REQ-292) and records a ``publish_run`` row with the outcome
    (REQ-293); the run identifier is returned in the response.
    """
    rec, api_key, secret_key = _resolve_publish_target(identifier)
    engagement = get_active_engagement()
    design_client = RestDesignClient(
        base_url=get_settings().api_base_url, engagement=engagement
    )
    started_at = datetime.now(UTC)
    result = publish_service.publish(
        rec,
        design_client,
        api_key=api_key,
        secret_key=secret_key,
        rendered_at=started_at.isoformat(),
        engagement=engagement,
        validate_only=validate_only,
        preview=preview,
        scope=set(scope) if scope else None,
        allow_no_backup=allow_no_backup,
    )
    payload = _serialize_publish_result(result)
    # Record the run for a real publish only (preview/validate write nothing).
    if not validate_only and not preview:
        payload["publish_run"] = _record_publish_run(
            identifier,
            result,
            scope=scope,
            started_at=started_at,
            ended_at=datetime.now(UTC),
        )
    return ok(payload)


class PublishScopeIn(BaseModel):
    """Optional request body for a publish.

    ``scope`` is a list of generated program filenames (e.g. ``Contact.yaml``);
    omitting it (or sending an empty list) publishes the whole design (REQ-290).
    ``allow_no_backup`` overrides the pre-publish backup gate so a publish
    proceeds even when the target snapshot cannot be captured (REQ-292).
    """

    model_config = ConfigDict(extra="forbid")
    scope: list[str] | None = None
    allow_no_backup: bool = False


@router.post("/{identifier}/publish")
def publish_instance(identifier: str, body: PublishScopeIn | None = None):
    """Generate the canonical design, validate it against this target, capture a
    pre-publish backup, and deploy it. A program that fails validation is never
    deployed (REQ-288); an optional ``scope`` publishes only a subset (REQ-290);
    a failed backup aborts unless ``allow_no_backup`` (REQ-292)."""
    return _run_publish(
        identifier,
        scope=body.scope if body else None,
        allow_no_backup=body.allow_no_backup if body else False,
    )


@router.post("/{identifier}/publish-validate")
def publish_validate_instance(
    identifier: str, body: PublishScopeIn | None = None
):
    """Generate + validate against this target without deploying (REQ-288).
    An optional ``scope`` body validates only a subset of programs (REQ-290)."""
    return _run_publish(
        identifier, validate_only=True, scope=body.scope if body else None
    )


@router.post("/{identifier}/publish-preview")
def publish_preview_instance(
    identifier: str, body: PublishScopeIn | None = None
):
    """Generate + validate, then dry-run the deploy to report the actions each
    object WOULD take, without writing to the target (REQ-289). An optional
    ``scope`` body previews only a subset of programs (REQ-290)."""
    return _run_publish(
        identifier, preview=True, scope=body.scope if body else None
    )
