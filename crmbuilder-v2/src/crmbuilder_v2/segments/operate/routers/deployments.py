"""Deployment endpoints — PI-576 (REQ-653, DEC-1155, DEC-1175, DEC-1185).

``/deployments`` is the record people and the connector use for one
installation of one application for one client. Reads compose the deployment
with the instance it holds, that instance's deploy configuration and the
provider credentials that apply to it; writes create or change the
deployment and may create its instance in the same request. Writes are
administrator-only, as the credential and deploy-run routes are (DEC-945).
The table is system-wide, so a list is narrowed to the applications the
principal may act on, and to one application or client on request.

Secrets cross the boundary here and never reach the repository (REQ-157):
an instance's ``secret`` / ``secret_key`` and a deployment credential's
``token`` are stored before the row transaction opens (the PI-419 live-proof
finding: storing inside the write transaction deadlocks SQLite). All
responses use the ``{data, meta, errors}`` envelope.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from crmbuilder_v2 import secrets
from crmbuilder_v2.access.engagement_scope import (
    active_engagement,
    get_active_engagement,
)
from crmbuilder_v2.access.exceptions import (
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.principal_scope import get_active_principal
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.principal_deps import require_permission
from crmbuilder_v2.api.secret_boundary import replace_secret, store_secret
from crmbuilder_v2.segments.operate.repositories import deployments as repo
from crmbuilder_v2.segments.operate.repositories import (
    provider_credentials as credential_repo,
)
from crmbuilder_v2.segments.operate.schemas import (
    DeploymentCreateIn,
    DeploymentPatchIn,
    ProviderCredentialIn,
)

router = APIRouter(prefix="/deployments", tags=["deployments"])

_admin = Depends(require_permission("admin"))


def _visible(rows: list[dict]) -> list[dict]:
    """Keep the deployments whose application the principal may act on."""
    principal = get_active_principal()
    if principal is None or principal.all_engagements:
        return rows
    return [
        r for r in rows if principal.is_engagement_allowed(r["deployment_application"])
    ]


def _require_visible(record: dict, identifier: str) -> dict:
    principal = get_active_principal()
    if principal is not None and not principal.is_engagement_allowed(
        record["deployment_application"]
    ):
        raise NotFoundError("deployment", identifier)
    return record


@router.get("")
def list_all(
    application: str | None = None,
    client: str | None = None,
    for_client: str | None = None,
    include_deleted: bool = False,
):
    """Deployments, each carrying its purpose. ``client`` narrows to the
    deployments a client runs; ``for_client`` (PI-577 / REQ-654) returns
    what a client may see: its own, plus the demo/test deployment of every
    application it may deploy."""
    with readonly_session() as s:
        if for_client is not None:
            rows = repo.list_deployments_for_client(
                s, for_client, include_deleted=include_deleted
            )
            if application is not None:
                rows = [r for r in rows if r["deployment_application"] == application]
            return ok(_visible(rows))
        return ok(
            _visible(
                repo.list_deployments(
                    s,
                    application=application,
                    client=client,
                    include_deleted=include_deleted,
                )
            )
        )


@router.get("/next-identifier")
def next_identifier():
    with readonly_session() as s:
        return ok({"next": repo.next_deployment_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = repo.get_deployment(s, identifier, include_deleted=include_deleted)
        if record is None:
            raise NotFoundError("deployment", identifier)
        return ok(_require_visible(record, identifier))


@router.post("", status_code=201, dependencies=[_admin])
def create(body: DeploymentCreateIn):
    application = body.deployment_application or get_active_engagement()
    if not application:
        raise UnprocessableError(
            [
                FieldError(
                    "deployment_application",
                    "required",
                    "name the application or select an engagement",
                )
            ]
        )
    instance_kw = None
    if body.instance is not None:
        # Store the plaintext secrets before the row transaction opens.
        secret_ref = store_secret(body.instance.secret)
        secret_key_ref = store_secret(body.instance.secret_key, field="secret_key")
        instance_kw = {
            "name": body.instance.instance_name,
            "url": body.instance.instance_url,
            "vendor": body.instance.instance_vendor or "espocrm",
            "role": body.instance.instance_role or "both",
            "auth_method": body.instance.instance_auth_method or "api_key",
            "secret_ref": secret_ref,
            "secret_key_ref": secret_key_ref,
            "status": body.instance.instance_status or "active",
            "notes": body.instance.instance_notes,
            "feature_selection": body.instance.instance_feature_selection,
        }
    with writable_session() as s:
        return ok(
            repo.create_deployment(
                s,
                client=body.deployment_client,
                application=application,
                name=body.deployment_name,
                purpose=body.deployment_purpose,
                hosting_provider=body.deployment_hosting_provider,
                status=body.deployment_status or "active",
                notes=body.deployment_notes,
                identifier=body.deployment_identifier,
                instance_identifier=body.instance_identifier,
                instance=instance_kw,
                deploy_config=body.deploy_config,
            )
        )


@router.patch("/{identifier}", dependencies=[_admin])
def patch(identifier: str, body: DeploymentPatchIn):
    fields = body.model_dump(exclude_unset=True)
    renamed = {
        "deployment_name": "name",
        "deployment_status": "status",
        "deployment_purpose": "purpose",
        "deployment_notes": "notes",
        "deployment_hosting_provider": "hosting_provider",
        "deployment_client": "client",
    }
    with writable_session() as s:
        return ok(
            repo.patch_deployment(
                s, identifier, **{renamed[k]: v for k, v in fields.items()}
            )
        )


@router.delete("/{identifier}", dependencies=[_admin])
def delete(identifier: str):
    with writable_session() as s:
        return ok(repo.delete_deployment(s, identifier))


@router.post("/{identifier}/restore", dependencies=[_admin])
def restore(identifier: str):
    with writable_session() as s:
        return ok(repo.restore_deployment(s, identifier))


# --- the deployment's own provider credentials ------------------------------


def _application_of(session, identifier: str) -> str:
    record = repo.get_deployment(session, identifier)
    if record is None:
        raise NotFoundError("deployment", identifier)
    return _require_visible(record, identifier)["deployment_application"]


@router.get("/{identifier}/provider-credentials")
def list_credentials(identifier: str):
    """The credentials that apply to the deployment: its own, then the
    application's fallback, each marked with its scope. Never the token."""
    with readonly_session() as s:
        record = repo.get_deployment(s, identifier)
        if record is None:
            raise NotFoundError("deployment", identifier)
        return ok(_require_visible(record, identifier)["provider_credentials"])


@router.put("/{identifier}/provider-credentials/{provider}", dependencies=[_admin])
def put_credential(identifier: str, provider: str, body: ProviderCredentialIn):
    """Set or replace the deployment's own token for ``provider``; it takes
    precedence over the application's. Read → store → write (PI-419)."""
    if not body.token.strip():
        raise UnprocessableError([FieldError("token", "required", "token is required")])
    with readonly_session() as s:
        application = _application_of(s, identifier)
        with active_engagement(application):
            current = credential_repo.get_provider_credential(
                s, provider, deployment_identifier=identifier
            )
    previous_ref = current["token_ref"] if current else None
    ref = replace_secret(body.token.strip(), previous_ref, field="token")
    with writable_session() as s:
        with active_engagement(application):
            credential_repo.upsert_provider_credential(
                s,
                provider,
                token_ref=ref,
                label=body.label,
                deployment_identifier=identifier,
            )
        return ok(repo.get_deployment(s, identifier)["provider_credentials"])


@router.delete("/{identifier}/provider-credentials/{provider}", dependencies=[_admin])
def delete_credential(identifier: str, provider: str):
    """Remove the deployment's own credential and its secret; the
    application's fallback, if any, applies again."""
    with writable_session() as s:
        application = _application_of(s, identifier)
        with active_engagement(application):
            ref = credential_repo.delete_provider_credential(
                s, provider, deployment_identifier=identifier
            )
        if ref is None:
            raise NotFoundError("provider_credential", provider)
    if secrets.is_ref(ref):
        secrets.delete_secret(ref)
    return ok({"provider": provider, "deleted": True, "scope": "deployment"})
