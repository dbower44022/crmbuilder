"""The REST secret boundary (REQ-157) shared by every router that takes a secret.

Plaintext secrets cross the API only in request bodies; routers turn them into
opaque ``crmbuilder:{uuid}`` references here and hand only the reference to the
data layer. Resolution happens in the same place so a store that is
unavailable on this host (no key, no keyring — the REQ-481 defect) surfaces as
an actionable 422, never a 500. Lifted from ``routers/instances.py`` for
PI-419 so provider credentials and deploy runs share one implementation.
"""

from __future__ import annotations

from crmbuilder_v2 import secrets
from crmbuilder_v2.access.exceptions import FieldError, UnprocessableError


def store_secret(value: str | None, *, field: str = "secret") -> str | None:
    """Store a plaintext secret and return its opaque reference.

    :param value: A plaintext secret, or ``None``/empty for no secret.
    :param field: The request field named in the 422 when the store is down.
    :returns: The opaque reference, or ``None`` when no secret was supplied.
    """
    if not value:
        return None
    try:
        return secrets.put_secret(value)
    except secrets.SecretBackendError as exc:
        raise UnprocessableError(
            [FieldError(field, "secret_backend_unavailable", str(exc))]
        ) from exc


def replace_secret(
    value: str | None, previous_ref: str | None, *, field: str = "secret"
) -> str | None:
    """Store ``value`` as a new reference and delete ``previous_ref`` if it was one.

    The old secret is deleted only after the new one is safely stored, so a
    store failure leaves the previous credential intact.
    """
    ref = store_secret(value, field=field)
    if previous_ref and secrets.is_ref(previous_ref):
        secrets.delete_secret(previous_ref)
    return ref


def resolve_secret_or_none(ref: str | None, *, field: str = "secret") -> str | None:
    """Resolve a reference to its plaintext, ``None`` when absent or unknown.

    A missing secret is an ordinary outcome the caller reports (for example as
    ``missing_credentials``); a backend that cannot be reached at all is a 422.
    """
    if not ref:
        return None
    try:
        return secrets.get_secret(ref)
    except KeyError:
        return None
    except secrets.SecretBackendError as exc:
        raise UnprocessableError(
            [FieldError(field, "secret_backend_unavailable", str(exc))]
        ) from exc
