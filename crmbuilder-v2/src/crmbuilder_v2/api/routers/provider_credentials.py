"""Provider-credential endpoints — PI-419 (REQ-522, PRJ-111).

An engagement's DigitalOcean / Cloudflare API tokens, stored behind the secret
boundary (REQ-157) and readable only as "configured or not" — the token itself
is never echoed. Also the two live catalog reads the deploy wizard needs
(DigitalOcean regions / sizes / images / SSH keys; Cloudflare zones), which
double as a proof that the stored token works. Administrator-only throughout
(DEC-945): creating servers spends money and changes public DNS. Literal
sub-paths are declared before ``/{provider}`` (GVR-153). All responses use the
``{data, meta, errors}`` envelope.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from crmbuilder_v2 import secrets
from crmbuilder_v2.access.exceptions import (
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import provider_credentials as repo
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.principal_deps import require_permission
from crmbuilder_v2.api.schemas import ProviderCredentialIn
from crmbuilder_v2.api.secret_boundary import (
    replace_secret,
    resolve_secret_or_none,
)
from crmbuilder_v2.deploy.errors import ProviderError
from crmbuilder_v2.deploy.providers.cloudflare import CloudflareClient
from crmbuilder_v2.deploy.providers.digitalocean import DigitalOceanClient

router = APIRouter(
    prefix="/provider-credentials",
    tags=["provider-credentials"],
    dependencies=[Depends(require_permission("admin"))],
)


def _public(row: dict) -> dict:
    """The credential as the API shows it — configured flag, never the ref."""
    return {
        "provider": row["provider"],
        "label": row.get("label"),
        "configured": bool(row.get("token_ref")),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _provider_error(exc: ProviderError) -> UnprocessableError:
    return UnprocessableError(
        [FieldError(exc.provider, "provider_error", str(exc))]
    )


def _token(provider: str) -> str:
    """Resolve the engagement's token for ``provider`` or raise a 422.

    A missing credential and an unreachable secret store are both told apart
    from a provider rejecting the token (which is a ``provider_error``).
    """
    with readonly_session() as s:
        row = repo.get_provider_credential(s, provider)
    token = resolve_secret_or_none(row["token_ref"] if row else None, field=provider)
    if not token:
        raise UnprocessableError(
            [
                FieldError(
                    provider,
                    "missing_provider_credential",
                    f"no {provider} credential is configured for this engagement",
                )
            ]
        )
    return token


# -- literal sub-paths first (GVR-153) ----------------------------------------


@router.get("/digitalocean/options")
def digitalocean_options():
    """Live DigitalOcean catalog for the deploy wizard: regions, sizes, images, keys."""
    do = DigitalOceanClient(_token("digitalocean"))
    try:
        return ok(
            {
                "regions": do.list_regions(),
                "sizes": do.list_sizes(),
                "images": do.list_images(),
                "ssh_keys": do.list_ssh_keys(),
            }
        )
    except ProviderError as exc:
        raise _provider_error(exc) from exc


@router.get("/cloudflare/zones")
def cloudflare_zones():
    """Zones the engagement's Cloudflare token can manage."""
    cf = CloudflareClient(_token("cloudflare"))
    try:
        return ok(cf.list_zones())
    except ProviderError as exc:
        raise _provider_error(exc) from exc


# -- the credential rows ------------------------------------------------------


@router.get("")
def list_all():
    """Every provider credential the engagement holds, as configured flags."""
    with readonly_session() as s:
        return ok([_public(r) for r in repo.list_provider_credentials(s)])


@router.get("/{provider}")
def get(provider: str):
    """One provider's credential status (404 when none is set)."""
    with readonly_session() as s:
        row = repo.get_provider_credential(s, provider)
        if row is None:
            raise NotFoundError("provider_credential", provider)
        return ok(_public(row))


@router.put("/{provider}")
def put(provider: str, body: ProviderCredentialIn):
    """Set or replace the engagement's token for ``provider``.

    The plaintext token is stored behind the secret boundary; the previous
    secret (if any) is deleted only after the new one is safely stored.
    """
    if not body.token.strip():
        raise UnprocessableError([FieldError("token", "required", "token is required")])
    with writable_session() as s:
        current = repo.get_provider_credential(s, provider)
        ref = replace_secret(
            body.token.strip(),
            current["token_ref"] if current else None,
            field="token",
        )
        row = repo.upsert_provider_credential(
            s, provider, token_ref=ref, label=body.label
        )
        return ok(_public(row))


@router.delete("/{provider}")
def delete(provider: str):
    """Remove the credential and its stored secret."""
    with writable_session() as s:
        ref = repo.delete_provider_credential(s, provider)
        if ref is None:
            raise NotFoundError("provider_credential", provider)
    if secrets.is_ref(ref):
        secrets.delete_secret(ref)
    return ok({"provider": provider, "deleted": True})
