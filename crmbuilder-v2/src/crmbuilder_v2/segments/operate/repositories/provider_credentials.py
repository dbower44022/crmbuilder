"""Provider-credential repository — PI-419 (REQ-522, PRJ-111).

An API token for an infrastructure provider (DigitalOcean, Cloudflare). One
row per provider at the application level, and since PI-576 one row per
provider per deployment as well: a deployment's own row wins, the
application's is the fallback (DEC-945). The row holds only an opaque secret
reference — translating a plaintext token into a ref is the router's job (the
REQ-157 boundary, as in ``instances`` / ``instance_deploy_config``). Engagement
scoping is applied by the session, so this repo resolves, upserts and deletes
by provider and scope.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.segments.operate.models import ProviderCredential
from crmbuilder_v2.segments.operate.vocab import PROVIDER_CREDENTIAL_PROVIDERS


def _scope_clause(deployment_identifier: str | None):
    if deployment_identifier is None:
        return ProviderCredential.deployment_identifier.is_(None)
    return ProviderCredential.deployment_identifier == deployment_identifier


def _find(
    session: Session, provider: str, deployment_identifier: str | None = None
) -> ProviderCredential | None:
    return session.scalars(
        select(ProviderCredential).where(
            ProviderCredential.provider == provider,
            _scope_clause(deployment_identifier),
        )
    ).first()


def list_provider_credentials(
    session: Session, *, deployment_identifier: str | None = None
) -> list[dict]:
    """Return the credentials at one scope, ordered by provider: the
    application's own rows by default, or the rows of one deployment."""
    rows = session.scalars(
        select(ProviderCredential)
        .where(_scope_clause(deployment_identifier))
        .order_by(ProviderCredential.provider)
    ).all()
    return [to_dict(r) for r in rows]


def effective_provider_credentials(
    session: Session, *, deployment_identifier: str | None = None
) -> dict[str, dict]:
    """The credentials that apply to a deployment, by provider: the
    deployment's own row where one exists, else the application's
    (PI-576 / DEC-1185; DEC-945 for the application-level default)."""
    out = {r["provider"]: r for r in list_provider_credentials(session)}
    if deployment_identifier is not None:
        for r in list_provider_credentials(
            session, deployment_identifier=deployment_identifier
        ):
            out[r["provider"]] = r
    return out


def get_provider_credential(
    session: Session, provider: str, *, deployment_identifier: str | None = None
) -> dict | None:
    """Return the credential row for ``provider`` at one scope, or ``None``."""
    provider = gov.require_in(provider, PROVIDER_CREDENTIAL_PROVIDERS, field="provider")
    row = _find(session, provider, deployment_identifier)
    return to_dict(row) if row is not None else None


def resolve_provider_credential(
    session: Session, provider: str, *, deployment_identifier: str | None = None
) -> dict | None:
    """The credential a deployment uses for ``provider``: its own, else the
    application's, else ``None``."""
    provider = gov.require_in(provider, PROVIDER_CREDENTIAL_PROVIDERS, field="provider")
    if deployment_identifier is not None:
        row = _find(session, provider, deployment_identifier)
        if row is not None:
            return to_dict(row)
    row = _find(session, provider, None)
    return to_dict(row) if row is not None else None


def upsert_provider_credential(
    session: Session,
    provider: str,
    *,
    token_ref: str,
    label: str | None = None,
    deployment_identifier: str | None = None,
) -> dict:
    """Create or replace the engagement's credential for ``provider``.

    ``token_ref`` must already be an opaque secret reference; the previous
    ref (if any) is returned to the caller via the row's prior value so the
    router can delete the old secret — see :func:`replace_token_ref`.
    """
    provider = gov.require_in(provider, PROVIDER_CREDENTIAL_PROVIDERS, field="provider")
    token_ref = gov.require_nonempty(token_ref, field="token_ref")
    row = _find(session, provider, deployment_identifier)
    if row is None:
        row = ProviderCredential(
            provider=provider,
            token_ref=token_ref,
            deployment_identifier=deployment_identifier,
        )
        session.add(row)
    else:
        row.token_ref = token_ref
    row.label = label
    session.flush()
    return to_dict(row)


def delete_provider_credential(
    session: Session, provider: str, *, deployment_identifier: str | None = None
) -> str | None:
    """Delete the credential for ``provider`` at one scope; return its
    ``token_ref`` (or None).

    The caller owns deleting the referenced secret — the repo never touches the
    secret store.
    """
    provider = gov.require_in(provider, PROVIDER_CREDENTIAL_PROVIDERS, field="provider")
    row = _find(session, provider, deployment_identifier)
    if row is None:
        return None
    ref = row.token_ref
    session.delete(row)
    session.flush()
    return ref
