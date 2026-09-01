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
from crmbuilder_v2.access import reconcile_apply
from crmbuilder_v2.access.engagement_scope import get_active_engagement
from crmbuilder_v2.access.exceptions import (
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.freeze import band_for_status
from crmbuilder_v2.access.repositories import (
    instance_deploy_config,
    instance_membership,
    instances,
    inventory,
    publish_runs,
    releases,
)
from crmbuilder_v2.adapters.espocrm.client import AccessDesignClient
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    InstanceCreateIn,
    InstanceDeployConfigIn,
    InstancePatchIn,
    InstanceReplaceIn,
    RecordExportIn,
)
from crmbuilder_v2.api.secret_boundary import (
    resolve_secret_or_none,
    store_secret,
)
from crmbuilder_v2.introspect.entity_audit import reconcile_entity_slice
from crmbuilder_v2.introspect.espo_client import EspoIntrospectionClient
from crmbuilder_v2.introspect.reconcile import (
    ReconcileError,
    classify_audit_completion,
    reconcile_associations,
    reconcile_email_templates,
    reconcile_entities,
    reconcile_field_permissions,
    reconcile_field_rules,
    reconcile_fields,
    reconcile_filtered_tabs,
    reconcile_layouts,
    reconcile_roles,
    reconcile_system_settings,
    reconcile_teams,
)
from crmbuilder_v2.introspect.record_export import export_records
from crmbuilder_v2.introspect.utilization import reconcile_utilization
from crmbuilder_v2.publish import service as publish_service

router = APIRouter(prefix="/instances", tags=["instances"])
_FIELD_PREFIX = "instance_"


def _edges(body) -> list[dict] | None:
    return [e.model_dump() for e in body.references] if body.references else None


def _store(value: str | None) -> str | None:
    """Store a plaintext secret, returning its opaque reference (REQ-157).

    Delegates to the shared :mod:`crmbuilder_v2.api.secret_boundary` so every
    router that takes a secret turns a missing backend into the same 422.
    """
    return store_secret(value)


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
    # Secrets are stored before the row transaction opens: on SQLite the
    # store's own connection cannot begin while this request holds the write
    # lock (PI-419 live-proof finding — "database is locked").
    secret_ref = _store(body.secret)
    secret_key_ref = _store(body.secret_key)
    with writable_session() as s:
        return ok(
            instances.create_instance(
                s,
                name=body.instance_name,
                url=body.instance_url,
                vendor=body.instance_vendor or "espocrm",
                role=body.instance_role or "both",
                auth_method=body.instance_auth_method or "api_key",
                secret_ref=secret_ref,
                secret_key_ref=secret_key_ref,
                status=body.instance_status or "active",
                notes=body.instance_notes,
                feature_selection=body.instance_feature_selection,
                identifier=body.instance_identifier,
                references=_edges(body),
                timestamps=body.timestamps,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: InstanceReplaceIn):
    # Read → store secrets → write; never store inside the transaction
    # (SQLite deadlock — PI-419 live-proof finding).
    with readonly_session() as s:
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
    with writable_session() as s:
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
                feature_selection=body.instance_feature_selection,
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
    with readonly_session() as s:
        current = instances.get_instance(s, identifier, include_deleted=True)
    if current is None:
        raise NotFoundError("instance", identifier)
    # Secrets cross the boundary outside the row transaction (PI-419 finding).
    if has_secret:
        secrets.delete_secret(current.get("instance_secret_ref"))
        fields["secret_ref"] = _store(secret)
    if has_secret_key:
        secrets.delete_secret(current.get("instance_secret_key_ref"))
        fields["secret_key_ref"] = _store(secret_key)
    with writable_session() as s:
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


def _audit_introspection_client(identifier: str) -> EspoIntrospectionClient:
    """Resolve an auditable instance + its stored creds into an introspection
    client, or raise the same 404 / not_auditable / missing_credentials errors
    the audit endpoints share.

    Opens (and closes) its own read session before touching the secret store:
    resolving a store-backed secret inside a caller's transaction deadlocks on
    SQLite (PI-419 live-proof finding — the audit's "database is locked" 500).
    """
    with readonly_session() as s:
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
    api_key = _resolve_secret_or_none(rec.get("instance_secret_ref"))
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
    return EspoIntrospectionClient(
        base_url=rec["instance_url"],
        api_key=api_key,
        secret_key=_resolve_secret_or_none(rec.get("instance_secret_key_ref")),
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
    # PI-420 / REQ-124 — email templates, after the entity-bound areas.
    "email-templates": ("Email templates", reconcile_email_templates),
    # PI-421 / REQ-123 — field dynamic logic, after fields exist.
    "field-rules": ("Field rules", reconcile_field_rules),
    # PI-406 / REQ-485 — governed setting values, read with the instance's
    # ordinary credential so a missing role grant surfaces as its own outcome.
    "system-settings": ("System settings", reconcile_system_settings),
    # PI-426 / REQ-524 — record utilization profiled into evidence. Last, and
    # opt-in (see ``_OPT_IN_AUDIT_AREAS``): it reads every record on the instance.
    "utilization": ("Utilization", reconcile_utilization),
}

#: The area slugs in run order — the order the desktop issues per-area calls.
AUDIT_AREA_ORDER: list[str] = list(_AUDIT_AREAS)

#: Areas the all-in-one audit does **not** run (REQ-524). A structural audit
#: stays fast; an opt-in area is run only when asked for by name through the
#: per-area endpoint, and is flagged ``opt_in`` in the area list so the desktop
#: offers it as a separate choice rather than as a step of "Audit now".
_OPT_IN_AUDIT_AREAS: frozenset[str] = frozenset({"utilization"})

#: Areas reconciled on a ``source`` audit (DEC-653). A source audit is the
#: candidate-gated design-input pass over entities / fields / associations only;
#: layouts / roles / field-permissions / teams / filtered-tabs are a deploy-fidelity
#: concern and are not reconciled on a source audit. A ``both`` audit is *not*
#: source (REQ-393 / WTK-256) and runs the full area set.
_SOURCE_AUDIT_AREAS: frozenset[str] = frozenset(
    {"entities", "fields", "associations"}
)


def _is_source_audit(s, identifier: str) -> bool:
    """Whether this audit is candidate-gated — ``source`` role only.

    REQ-393 / WTK-256 narrowed this from ``("source", "both")``: a ``both`` audit
    is a deployed-to instance and runs the full drift reconcile over every area,
    so only a purely external ``source`` selects the candidate-gated path.
    """
    rec = instances.get_instance(s, identifier)
    return bool(rec) and rec.get("instance_role") == "source"


@router.get("/audit/areas")
def audit_areas():
    """The ordered audit areas the desktop drives, for the progress view."""
    return ok(
        [
            {
                "area": a,
                "label": _AUDIT_AREAS[a][0],
                "opt_in": a in _OPT_IN_AUDIT_AREAS,
            }
            for a in AUDIT_AREA_ORDER
        ]
    )


@router.post("/{identifier}/audit")
def audit(identifier: str):
    """Audit (pull) this instance, reconciling its structure into the inventory.

    Runs every applicable reconcile area in one request and returns the
    per-object-type summary. A ``source`` audit runs only the candidate-gated
    areas (entities / fields / associations — DEC-653); a ``target`` or ``both``
    audit runs the full drift set (REQ-393 / WTK-256). This all-in-one form is
    retained for non-interactive callers;
    the desktop drives the per-area endpoint below for live progress (PI-274).
    Opt-in areas (``_OPT_IN_AUDIT_AREAS`` — utilization, REQ-524) never run
    here; they are reached only by name through the per-area endpoint.
    """
    client = _audit_introspection_client(identifier)
    with writable_session() as s:
        keys = [a for a in AUDIT_AREA_ORDER if a not in _OPT_IN_AUDIT_AREAS]
        if _is_source_audit(s, identifier):
            keys = [a for a in keys if a in _SOURCE_AUDIT_AREAS]
        try:
            result: dict[str, object] = {
                key.replace("-", "_"): _AUDIT_AREAS[key][1](
                    s, instance_identifier=identifier, client=client
                )
                for key in keys
            }
        except ReconcileError as exc:
            raise UnprocessableError(
                [FieldError("audit", "introspection_failed", str(exc))]
            ) from exc
        # REQ-395 / PI-354: a successful audit that populated no inventory must
        # say so plainly, not read as a successful complete audit. (A read
        # failure never reaches here — it raised ReconcileError above.)
        result["completion"] = classify_audit_completion(result)
        return ok(result)


@router.post("/{identifier}/audit/{area}")
def audit_area(identifier: str, area: str):
    """Reconcile a single audit area (PI-274 — REQ-308/309/310).

    Runs exactly one reconcile step so the desktop can drive the areas in
    sequence and show live progress. Returns the area's ``summary`` plus a
    ``log`` of ``[message, level]`` lines the step surfaced (e.g. an entity
    whose fields could not be read), for the operator's running audit log. On a
    ``source`` audit a non-candidate-gated area (layouts/roles/teams/etc.) is
    not reconciled (DEC-653) and returns a ``skipped`` summary; a ``both`` audit
    runs every area (REQ-393 / WTK-256).
    """
    spec = _AUDIT_AREAS.get(area)
    if spec is None:
        raise NotFoundError("audit area", area)
    label, fn = spec
    log: list[list[str]] = []
    client = _audit_introspection_client(identifier)
    with writable_session() as s:
        if _is_source_audit(s, identifier) and area not in _SOURCE_AUDIT_AREAS:
            return ok({
                "area": area,
                "label": label,
                "summary": {
                    "skipped": True,
                    "reason": (
                        "not reconciled on a source audit — candidate-gating "
                        "covers entities / fields / associations only (DEC-653)"
                    ),
                },
                "log": [],
            })
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


@router.post("/{identifier}/audit-entity/{entity_identifier}")
def audit_entity(identifier: str, entity_identifier: str):
    """Fast entity-only re-audit (REQ-392 / PI-351).

    Re-reads just one entity's slice (presence + settings + fields + relationships
    + layouts) from the live instance and refreshes only that entity's stored
    membership — a quick targeted refresh before reconciling, without a
    full-instance audit. Returns the per-section ``summary`` plus a ``log``.
    """
    log: list[list[str]] = []
    client = _audit_introspection_client(identifier)
    with writable_session() as s:
        try:
            summary = reconcile_entity_slice(
                s,
                instance_identifier=identifier,
                entity_identifier=entity_identifier,
                client=client,
                progress=lambda m, lvl: log.append([m, lvl]),
            )
        except ReconcileError as exc:
            raise UnprocessableError(
                [FieldError("audit", "introspection_failed", str(exc))]
            ) from exc
        return ok({"summary": summary, "log": log})


# ── Deploy config (PI-201 — REQ-172) ──────────────────────────────────────


@router.get("/{identifier}/deploy-config")
def get_deploy_config(identifier: str):
    """The instance's deploy/provisioning config, or ``null`` if it has none."""
    with readonly_session() as s:
        if instances.get_instance(s, identifier) is None:
            raise NotFoundError("instance", identifier)
        return ok(instance_deploy_config.get_deploy_config(s, identifier))


@router.put("/{identifier}/deploy-config")
def put_deploy_config(identifier: str, body: InstanceDeployConfigIn):
    """Create or update the instance's deploy config (PI-201 / REQ-172).

    Write-only plaintext secrets cross the secret boundary here: ``ssh_credential``
    becomes ``ssh_credential_ref`` — the key file path inline for key auth, a
    secret reference for password auth — and the three passwords become secret
    references. Omitted keys are left unchanged; an explicit null clears.

    Secrets are stored *between* the read and the write transactions, never
    inside one: on SQLite the encrypted store's own connection cannot begin a
    write while the request's transaction holds the lock (PI-419 live-proof
    finding — ``database is locked``). Postgres never minded; SQLite does.
    """
    provided = body.model_dump(exclude_unset=True)
    with readonly_session() as s:
        if instances.get_instance(s, identifier) is None:
            raise NotFoundError("instance", identifier)
        current = instance_deploy_config.get_deploy_config(s, identifier) or {}
    fields = {
        k: v for k, v in provided.items()
        if k not in (
            "ssh_credential", "db_root_password", "db_password", "admin_password"
        )
    }
    stale_refs: list[str] = []
    # SSH credential: a key path is stored inline; a password is a secret ref.
    if "ssh_credential" in provided:
        cred = provided["ssh_credential"]
        auth = fields.get("ssh_auth_type", current.get("ssh_auth_type"))
        if cred and auth == "password":
            fields["ssh_credential_ref"] = _store(cred)
            old = current.get("ssh_credential_ref")
            if old and (old or "").startswith(secrets.REF_PREFIX):
                stale_refs.append(old)
        else:
            fields["ssh_credential_ref"] = cred  # key path inline, or cleared
    # The three passwords are always secret refs (db_password / admin_password
    # were added by PI-419 for the facts a deploy run records).
    for plain, ref_col in (
        ("db_root_password", "db_root_password_ref"),
        ("db_password", "db_password_ref"),
        ("admin_password", "admin_password_ref"),
    ):
        if plain in provided:
            pw = provided[plain]
            fields[ref_col] = _store(pw)
            old = current.get(ref_col)
            if pw and old:
                stale_refs.append(old)
    with writable_session() as s:
        result = instance_deploy_config.upsert_deploy_config(s, identifier, **fields)
    for old in stale_refs:
        secrets.delete_secret(old)
    return ok(result)


# ── Record-data export (PI-234 — REQ-130) ─────────────────────────────────


@router.post("/{identifier}/export-records")
def export_records_endpoint(identifier: str, body: RecordExportIn):
    """Export selected seed/reference records from a source instance (PI-234).

    Reads the operator-selected entities' records via the introspection client
    (the same source/both role + credential gate as the audit — a target-only
    instance cannot be read) and returns an import-ready artifact plus a ``log``
    of any per-entity read warnings. Seed/reference data only (DEC-693).
    """
    client = _audit_introspection_client(identifier)
    log: list[list[str]] = []
    # Reads only the live instance; no store transaction is needed here.
    artifact = export_records(
        client,
        entity_names=body.entities,
        max_size=body.max_size or 200,
        progress=lambda m, lvl: log.append([m, lvl]),
    )
    return ok({"artifact": artifact, "log": log})


# ── Publish (PRJ-042 — REQ-287 + REQ-288) ─────────────────────────────────


def _serialize_publish_result(result: publish_service.PublishResult) -> dict:
    """Render a :class:`PublishResult` as a JSON-safe envelope payload.

    Each program reports what it *generated* — its entities, its field names and
    count, its relationship count — not only whether the run finished. Status
    alone is not enough to tell a healthy publish from a hollow one: the number
    of programs follows the count of confirmed entities and is independent of
    fields, so a design whose field-to-entity edges went missing generates the
    same programs, passes the same validation, and returns the same 200. That is
    exactly how one such defect stayed invisible while every run reported green
    (REQ-483 / LSN-052). These counts are what the publish check asserts against.
    """
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
        # REQ-496 / PI-411: the run's derived plan identity, and whether the
        # apply refused because it no longer matched the approved plan.
        "plan_fingerprint": result.plan_fingerprint,
        "plan_moved": result.plan_moved,
        # PI-406 / REQ-485: the governed-settings apply outcome, when the
        # instance has declared per-instance values.
        "settings": (
            {
                "entity": result.settings.entity,
                "status": result.settings.status.value,
                "changes": result.settings.changes,
                "error": result.settings.error,
                "log": [list(line) for line in result.settings_log],
            }
            if result.settings is not None
            else None
        ),
        # REQ-495: the design-version stamp write outcome, when the run
        # qualified to write one.
        "stamp": (
            {
                "entity": result.stamp.entity,
                "status": result.stamp.status.value,
                "changes": result.stamp.changes,
                "error": result.stamp.error,
                "log": [list(line) for line in result.stamp_log],
            }
            if result.stamp is not None
            else None
        ),
        "programs": [
            {
                "filename": p.filename,
                "deployed": p.deployed,
                "validation_errors": p.validation_errors,
                "entities": p.entities,
                "field_count": len(p.field_names),
                "field_names": p.field_names,
                "relationship_count": p.relationship_count,
                "summary": (
                    dataclasses.asdict(p.report.summary) if p.report else None
                ),
                "log": [list(line) for line in p.log],
            }
            for p in result.programs
        ],
    }


def _publish_run_status(result: publish_service.PublishResult) -> str:
    """Map a publish result to a terminal ``publish_run`` status (REQ-293).

    Delegates to the service so the stamp gate (DEC-981) and the recorded
    run agree on what "succeeded" means.
    """
    return publish_service.publish_run_status(result)


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
    scope_source: str | None = None,
    feature_selection: list[str] | None = None,
) -> str | None:
    """Persist a publish_run row for a completed real publish (best-effort).

    Recording failure never breaks the publish response — the live CRM was
    already written; a lost log entry is surfaced as a warning, not an error.
    ``scope_source`` / ``feature_selection`` stamp how the run's scope came to
    be (REQ-546 / PI-444) so the history shows which selection applied.
    """
    summary = _publish_run_summary(result)
    if scope_source is not None:
        summary["scope_source"] = scope_source
    if feature_selection:
        summary["feature_selection"] = feature_selection
    try:
        with writable_session() as s:
            row = publish_runs.create_publish_run(
                s,
                instance_identifier=identifier,
                status=_publish_run_status(result),
                scope=scope,
                backup=result.backup,
                summary=summary,
                started_at=started_at,
                ended_at=ended_at,
                plan_fingerprint=result.plan_fingerprint,
            )
        return row["publish_run_identifier"]
    except Exception:  # pragma: no cover - defensive; logged, never fatal
        logging.getLogger(__name__).warning(
            "failed to record publish_run for %s", identifier, exc_info=True
        )
        return None


def _resolve_secret_or_none(ref: str | None) -> str | None:
    """Resolve one secret reference, mapping "not stored here" to ``None``.

    A missing value is a missing credential (the caller's 422); a backend that
    cannot answer at all is its own 422 naming the cause — never a 500. Shared
    with the other secret-taking routers via :mod:`api.secret_boundary`.
    """
    return resolve_secret_or_none(ref)


def _resolve_publish_target(identifier: str) -> tuple[dict, str, str | None]:
    """Fetch the target instance and resolve its stored credentials.

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
    # Secrets resolve outside the session (SQLite deadlock — PI-419 finding).
    api_key = _resolve_secret_or_none(rec.get("instance_secret_ref"))
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
    secret_key = _resolve_secret_or_none(rec.get("instance_secret_key_ref"))
    return rec, api_key, secret_key


def _run_publish(
    identifier: str,
    *,
    validate_only: bool = False,
    preview: bool = False,
    scope: list[str] | None = None,
    allow_no_backup: bool = False,
    expected_plan_fingerprint: str | None = None,
    release_identifier: str | None = None,
):
    """Resolve the target + active-engagement design source, then publish.

    A real publish (not validate-only / preview) captures a pre-publish backup
    of the target (REQ-292) and records a ``publish_run`` row with the outcome
    (REQ-293); the run identifier is returned in the response.
    """
    rec, api_key, secret_key = _resolve_publish_target(identifier)
    # REQ-495 / DEC-980: the stamp's version only means something the release
    # train pinned, so a named release must exist and be frozen (its status in
    # the amend_window or locked band) before the run may claim it.
    if release_identifier is not None:
        with readonly_session() as s:
            release = releases.get_release(s, release_identifier)
        if release is None:
            raise NotFoundError("release", release_identifier)
        band = band_for_status(release["release_status"])
        if band not in ("amend_window", "locked"):
            raise UnprocessableError(
                [
                    FieldError(
                        "release_identifier",
                        "release_not_frozen",
                        f"{release_identifier} has status "
                        f"{release['release_status']!r}, which is not a "
                        "frozen state; a publish outside a frozen release "
                        "does not write the design-version stamp (DEC-980)",
                    )
                ]
            )
    engagement = get_active_engagement()
    # Stored feature selection (REQ-546 / PI-444): an explicit per-run scope
    # wins for that run only; otherwise a non-empty stored selection on the
    # instance record resolves to the effective scope; no selection publishes
    # the full design (unchanged behaviour). A validate-only run stays
    # full-design — it is the dialog's discovery surface — but the resolution
    # is reported so the UI can pre-check the operator's scope list.
    stored = rec.get("instance_feature_selection") or None
    selection_info = None
    if stored:
        with readonly_session() as s:
            selection_info = reconcile_apply.feature_selection_scope(
                s, stored
            )
    effective_scope = scope
    scope_source = "explicit_scope" if scope else "full_design"
    if scope is None and stored and not validate_only:
        if not selection_info["filenames"]:
            raise UnprocessableError(
                [
                    FieldError(
                        "instance_feature_selection",
                        "selection_matches_nothing",
                        "the stored feature selection names no current "
                        "design entity; publishing would silently fall back "
                        "to the full design — fix or clear the selection "
                        "first",
                    )
                ]
            )
        effective_scope = selection_info["filenames"]
        scope_source = "stored_selection"
    # In-process: read the design straight from the store rather than having the
    # service authenticate to its own API, which it cannot do on a host with
    # PRINCIPAL_AUTH_ENABLED and no credential of its own (REQ-482).
    design_client = AccessDesignClient(engagement=engagement)
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
        scope=set(effective_scope) if effective_scope else None,
        allow_no_backup=allow_no_backup,
        expected_plan_fingerprint=expected_plan_fingerprint,
        release_identifier=release_identifier,
    )
    payload = _serialize_publish_result(result)
    payload["scope_source"] = scope_source
    if selection_info is not None:
        payload["feature_selection"] = selection_info
    # Record the run for a real publish only (preview/validate write nothing).
    if not validate_only and not preview:
        payload["publish_run"] = _record_publish_run(
            identifier,
            result,
            scope=effective_scope,
            started_at=started_at,
            ended_at=datetime.now(UTC),
            scope_source=scope_source,
            feature_selection=(
                stored if scope_source == "stored_selection" else None
            ),
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
    # REQ-496 / PI-411: the plan identity the operator approved (from a
    # preview). A real publish re-derives the plan and refuses on mismatch.
    expected_plan_fingerprint: str | None = None
    # REQ-495 / PI-411: the frozen release this publish runs under. A fully
    # successful run then writes the design-version stamp to the instance; a
    # publish outside a frozen release never writes it (DEC-980).
    release_identifier: str | None = None


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
        expected_plan_fingerprint=(
            body.expected_plan_fingerprint if body else None
        ),
        release_identifier=body.release_identifier if body else None,
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
