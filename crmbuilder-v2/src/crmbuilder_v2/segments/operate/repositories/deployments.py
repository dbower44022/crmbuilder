"""Deployment repository — PI-576 (REQ-653, DEC-1155, DEC-1175, DEC-1185).

A deployment (``DPL-NNN``) is one installation of one application on one
hosting provider for one client. It holds the instance, the instance's
deploy configuration and the client's provider credentials by composition:
those three tables stay keyed as they are, and the deployment row names the
application, the client, the hosting provider and the instance it holds.

The table is system-wide (no engagement scope). Everything that touches the
held instance or its configuration runs under the deployment's application
scope, so a deployment can be read and written from any active engagement.
Secrets never reach this layer (REQ-157): an instance created through a
deployment is handed opaque references, as ``instances.create_instance`` is.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    next_prefixed_identifier,
    serialize_identifier_assignment,
    to_dict,
)
from crmbuilder_v2.access.engagement_scope import active_engagement
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.segments.client_management.models import ClientRow
from crmbuilder_v2.segments.client_management.repositories import (
    engagement as engagement_repo,
)
from crmbuilder_v2.segments.operate.models import Deployment
from crmbuilder_v2.segments.operate.repositories import instance_deploy_config
from crmbuilder_v2.segments.operate.repositories import instances as instance_repo
from crmbuilder_v2.segments.operate.repositories import (
    provider_credentials as credential_repo,
)
from crmbuilder_v2.segments.operate.vocab import (
    DEFAULT_DEPLOYMENT_HOSTING_PROVIDER,
    DEPLOYMENT_HOSTING_PROVIDERS,
    DEPLOYMENT_STATUSES,
)

_IDENTIFIER_PREFIX = "DPL"
_IDENTIFIER_RE = re.compile(r"^DPL-\d{3,}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE_FIELDS = frozenset({"name", "status", "notes", "hosting_provider", "client"})


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _require_client(session: Session, identifier: object) -> ClientRow:
    """The deploying client must exist and not be soft-deleted
    (``client_not_found``, the REQ-596 refusal shape)."""
    row = session.get(ClientRow, identifier) if isinstance(identifier, str) else None
    if row is None or row.client_deleted_at is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "deployment_client",
                    "client_not_found",
                    f"client {identifier!r} does not exist or is deleted",
                )
            ]
        )
    return row


def _require_application(session: Session, identifier: object):
    """The application must exist, be live and have a defining client
    (``application_not_found`` / ``no_defining_client``)."""
    engagement = (
        engagement_repo.get_engagement(session, identifier)
        if isinstance(identifier, str)
        else None
    )
    if engagement is None or engagement.engagement_deleted_at is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "deployment_application",
                    "application_not_found",
                    f"application {identifier!r} does not exist or is deleted",
                )
            ]
        )
    if engagement.engagement_defining_client is None:
        raise UnprocessableError(
            [
                FieldError(
                    "deployment_application",
                    "no_defining_client",
                    f"engagement {identifier!r} has no defining client and "
                    "is not an application",
                )
            ]
        )
    return engagement


def _require_may_deploy(application, client_identifier: str) -> None:
    """A private application accepts a deployment only from its defining
    client (REQ-653); ``application_private`` otherwise."""
    if (
        application.engagement_visibility == "private"
        and application.engagement_defining_client != client_identifier
    ):
        raise UnprocessableError(
            [
                FieldError(
                    "deployment_client",
                    "application_private",
                    f"application {application.engagement_identifier!r} is "
                    f"private to {application.engagement_defining_client!r}; "
                    f"{client_identifier!r} may not deploy it",
                )
            ]
        )


def _require_hosting_provider(value: object) -> str:
    return gov.require_in(
        value, DEPLOYMENT_HOSTING_PROVIDERS, field="deployment_hosting_provider"
    )


def _require_status(value: object) -> str:
    return gov.require_in(value, DEPLOYMENT_STATUSES, field="deployment_status")


def _require_instance(session: Session, application: str, identifier: str) -> dict:
    """The instance must exist under the application and not already be
    held by another deployment."""
    with active_engagement(application):
        record = instance_repo.get_instance(session, identifier)
    if record is None:
        raise UnprocessableError(
            [
                FieldError(
                    "deployment_instance_identifier",
                    "instance_not_found",
                    f"instance {identifier!r} does not exist in {application!r}",
                )
            ]
        )
    holder = session.scalars(
        select(Deployment).where(
            Deployment.deployment_application == application,
            Deployment.deployment_instance_identifier == identifier,
        )
    ).first()
    if holder is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "deployment_instance_identifier",
                    "instance_already_deployed",
                    f"instance {identifier!r} is already held by "
                    f"{holder.deployment_identifier}",
                )
            ]
        )
    return record


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def _get_row(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> Deployment | None:
    row = session.get(Deployment, identifier)
    if row is None:
        return None
    if row.deployment_deleted_at is not None and not include_deleted:
        return None
    return row


def _credential_public(row: dict, *, scope: str) -> dict:
    return {
        "provider": row["provider"],
        "label": row.get("label"),
        "configured": bool(row.get("token_ref")),
        "scope": scope,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def compose(session: Session, row: Deployment) -> dict:
    """The deployment as the API returns it: its own columns plus the
    instance it holds, that instance's deploy configuration and the
    provider credentials that apply to it (the deployment's own first, then
    the application's), read under the deployment's application scope."""
    out = to_dict(row)
    instance = None
    deploy_config = None
    with active_engagement(row.deployment_application):
        if row.deployment_instance_identifier:
            instance = instance_repo.get_instance(
                session, row.deployment_instance_identifier, include_deleted=True
            )
            deploy_config = instance_deploy_config.get_deploy_config(
                session, row.deployment_instance_identifier
            )
        effective = credential_repo.effective_provider_credentials(
            session, deployment_identifier=row.deployment_identifier
        )
    out["instance"] = instance
    out["deploy_config"] = deploy_config
    out["provider_credentials"] = [
        _credential_public(
            cred,
            scope=(
                "deployment"
                if cred.get("deployment_identifier") == row.deployment_identifier
                else "application"
            ),
        )
        for _, cred in sorted(effective.items())
    ]
    return out


def list_deployments(
    session: Session,
    *,
    application: str | None = None,
    client: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    """Deployments in identifier order, optionally narrowed to one
    application and/or one client, each composed with what it holds."""
    stmt = select(Deployment)
    if application is not None:
        stmt = stmt.where(Deployment.deployment_application == application)
    if client is not None:
        stmt = stmt.where(Deployment.deployment_client == client)
    if not include_deleted:
        stmt = stmt.where(Deployment.deployment_deleted_at.is_(None))
    rows = session.scalars(stmt.order_by(Deployment.deployment_identifier)).all()
    return [compose(session, r) for r in rows]


def get_deployment(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = _get_row(session, identifier, include_deleted=include_deleted)
    return compose(session, row) if row is not None else None


def deployment_for_instance(
    session: Session, application: str, instance_identifier: str
) -> dict | None:
    """The deployment holding ``instance_identifier`` under ``application``,
    composed, or ``None``."""
    row = session.scalars(
        select(Deployment).where(
            Deployment.deployment_application == application,
            Deployment.deployment_instance_identifier == instance_identifier,
        )
    ).first()
    return compose(session, row) if row is not None else None


def next_deployment_identifier(session: Session) -> str:
    """The next free ``DPL-NNN`` across every application (the identifier is
    unique store-wide, unlike ``INST-NNN``)."""
    ids = session.scalars(select(Deployment.deployment_identifier)).all()
    return next_prefixed_identifier(list(ids), _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(identifier: str, **kw) -> Deployment:
    return Deployment(
        deployment_identifier=identifier,
        deployment_application=kw["application"],
        deployment_client=kw["client"],
        deployment_hosting_provider=kw["hosting_provider"],
        deployment_name=kw["name"],
        deployment_status=kw["status"],
        deployment_instance_identifier=kw.get("instance_identifier"),
        deployment_notes=kw.get("notes"),
    )


def _insert_with_autoassign(session: Session, **kw) -> Deployment:
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
    candidate = next_deployment_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(candidate, **kw)
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last_error = exc
            savepoint.rollback()
            candidate = next_prefixed_identifier([candidate], _IDENTIFIER_PREFIX)
            continue
        savepoint.commit()
        return row
    raise ConflictError(
        "could not assign a unique deployment identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_deployment(
    session: Session,
    *,
    client: str,
    application: str,
    name: str,
    hosting_provider: str | None = None,
    status: str = "active",
    notes: str | None = None,
    identifier: str | None = None,
    instance_identifier: str | None = None,
    instance: dict | None = None,
    deploy_config: dict | None = None,
) -> dict:
    """Create a deployment of ``application`` for ``client``.

    Refused before any row is written when the client or the application is
    missing (``client_not_found`` / ``application_not_found``), when the
    application has no defining client (``no_defining_client``), or when the
    application is private to another client (``application_private``).

    Either ``instance_identifier`` names an existing instance of the
    application to hold, or ``instance`` is a dict of
    ``instances.create_instance`` keyword arguments (opaque secret
    references only) and the instance is created under the application in
    the same transaction. ``deploy_config`` is applied to the held instance
    with ``instance_deploy_config.upsert_deploy_config``.
    """
    name = gov.require_nonempty(name, field="deployment_name")
    client = gov.require_nonempty(client, field="deployment_client")
    application = gov.require_nonempty(application, field="deployment_application")
    hosting_provider = _require_hosting_provider(
        hosting_provider or DEFAULT_DEPLOYMENT_HOSTING_PROVIDER
    )
    status = _require_status(status or "active")
    _require_client(session, client)
    app = _require_application(session, application)
    _require_may_deploy(app, client)
    if instance is not None and instance_identifier is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "instance",
                    "ambiguous_instance",
                    "pass either instance_identifier or instance, not both",
                )
            ]
        )
    if instance_identifier is not None:
        _require_instance(session, application, instance_identifier)

    with active_engagement(application):
        if instance is not None:
            created = instance_repo.create_instance(session, **instance)
            instance_identifier = created["instance_identifier"]

    kw = {
        "application": application,
        "client": client,
        "hosting_provider": hosting_provider,
        "name": name,
        "status": status,
        "notes": notes,
        "instance_identifier": instance_identifier,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **kw)
    else:
        gov.require_identifier_format(
            identifier,
            regex=_IDENTIFIER_RE,
            field="deployment_identifier",
            example="DPL-001",
        )
        if session.get(Deployment, identifier) is not None:
            raise ConflictError(f"deployment {identifier!r} already exists")
        row = _new_row(identifier, **kw)
        session.add(row)
        session.flush()

    if deploy_config and instance_identifier is not None:
        with active_engagement(application):
            instance_deploy_config.upsert_deploy_config(
                session, instance_identifier, **deploy_config
            )
    session.flush()
    return compose(session, row)


def patch_deployment(session: Session, identifier: str, **fields) -> dict:
    """Change the name, status, notes, hosting provider or client of a
    deployment. A client change is subject to the private-application rule."""
    unknown = set(fields) - _PATCHABLE_FIELDS
    if unknown:
        raise UnprocessableError(
            [
                FieldError(
                    f, "unknown_field", f"{f} is not a patchable deployment field"
                )
                for f in sorted(unknown)
            ]
        )
    row = _get_row(session, identifier)
    if row is None:
        raise NotFoundError("deployment", identifier)
    if "name" in fields:
        row.deployment_name = gov.require_nonempty(
            fields["name"], field="deployment_name"
        )
    if "status" in fields:
        row.deployment_status = _require_status(fields["status"])
    if "hosting_provider" in fields:
        row.deployment_hosting_provider = _require_hosting_provider(
            fields["hosting_provider"]
        )
    if "notes" in fields:
        row.deployment_notes = fields["notes"]
    if "client" in fields:
        client = gov.require_nonempty(fields["client"], field="deployment_client")
        _require_client(session, client)
        app = _require_application(session, row.deployment_application)
        _require_may_deploy(app, client)
        row.deployment_client = client
    session.flush()
    return compose(session, row)


def attach_instance(
    session: Session, identifier: str, instance_identifier: str
) -> dict:
    """Record that the deployment now holds ``instance_identifier`` (the
    deploy run registers the instance at its last phase)."""
    row = _get_row(session, identifier)
    if row is None:
        raise NotFoundError("deployment", identifier)
    if row.deployment_instance_identifier == instance_identifier:
        return compose(session, row)
    if row.deployment_instance_identifier is not None:
        raise ConflictError(
            f"deployment {identifier!r} already holds "
            f"{row.deployment_instance_identifier!r}"
        )
    _require_instance(session, row.deployment_application, instance_identifier)
    row.deployment_instance_identifier = instance_identifier
    session.flush()
    return compose(session, row)


def delete_deployment(session: Session, identifier: str) -> dict:
    """Soft-delete (retain, not delete)."""
    row = _get_row(session, identifier)
    if row is None:
        raise NotFoundError("deployment", identifier)
    row.deployment_deleted_at = datetime.now(UTC)
    session.flush()
    return compose(session, row)


def restore_deployment(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier, include_deleted=True)
    if row is None:
        raise NotFoundError("deployment", identifier)
    row.deployment_deleted_at = None
    session.flush()
    return compose(session, row)
