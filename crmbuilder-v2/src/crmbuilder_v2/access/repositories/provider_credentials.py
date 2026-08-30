"""Provider-credential repository — PI-419 (REQ-522, PRJ-111).

An engagement's API token for an infrastructure provider (DigitalOcean,
Cloudflare), one row per provider. The row holds only an opaque secret
reference — translating a plaintext token into a ref is the router's job (the
REQ-157 boundary, as in ``instances`` / ``instance_deploy_config``). Engagement
scoping is applied by the session, so this repo just resolves, upserts, and
deletes by provider.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.models import ProviderCredential
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import PROVIDER_CREDENTIAL_PROVIDERS


def _find(session: Session, provider: str) -> ProviderCredential | None:
    return session.scalars(
        select(ProviderCredential).where(ProviderCredential.provider == provider)
    ).first()


def list_provider_credentials(session: Session) -> list[dict]:
    """Return the engagement's provider credentials, ordered by provider."""
    rows = session.scalars(
        select(ProviderCredential).order_by(ProviderCredential.provider)
    ).all()
    return [to_dict(r) for r in rows]


def get_provider_credential(session: Session, provider: str) -> dict | None:
    """Return the credential row for ``provider``, or ``None`` if none is set."""
    provider = gov.require_in(
        provider, PROVIDER_CREDENTIAL_PROVIDERS, field="provider"
    )
    row = _find(session, provider)
    return to_dict(row) if row is not None else None


def upsert_provider_credential(
    session: Session,
    provider: str,
    *,
    token_ref: str,
    label: str | None = None,
) -> dict:
    """Create or replace the engagement's credential for ``provider``.

    ``token_ref`` must already be an opaque secret reference; the previous
    ref (if any) is returned to the caller via the row's prior value so the
    router can delete the old secret — see :func:`replace_token_ref`.
    """
    provider = gov.require_in(
        provider, PROVIDER_CREDENTIAL_PROVIDERS, field="provider"
    )
    token_ref = gov.require_nonempty(token_ref, field="token_ref")
    row = _find(session, provider)
    if row is None:
        row = ProviderCredential(provider=provider, token_ref=token_ref)
        session.add(row)
    else:
        row.token_ref = token_ref
    row.label = label
    session.flush()
    return to_dict(row)


def delete_provider_credential(session: Session, provider: str) -> str | None:
    """Delete the credential for ``provider``; return its ``token_ref`` (or None).

    The caller owns deleting the referenced secret — the repo never touches the
    secret store.
    """
    provider = gov.require_in(
        provider, PROVIDER_CREDENTIAL_PROVIDERS, field="provider"
    )
    row = _find(session, provider)
    if row is None:
        return None
    ref = row.token_ref
    session.delete(row)
    session.flush()
    return ref
