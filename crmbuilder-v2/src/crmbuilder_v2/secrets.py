"""Secret storage for CRMBuilder V2 — encrypted store first, OS keyring second.

Ported from the V1 helper ``automation/core/secrets.py`` for PI-186 (the
instance entity, PRJ-027). The owning row never holds a secret value: it holds
an opaque ``crmbuilder:{uuid4}`` reference that this module resolves. REQ-157's
two guarantees — never plaintext, referenced indirectly — are unchanged.

**Where the value lives (REQ-157 amended / REQ-481, DEC-913).** Originally: the
OS keyring, always. That stranded every secret on the machine that created it,
and the hosted API has no keyring backend at all — so the droplet could neither
save an instance's credentials (``put_secret`` raised) nor resolve them to
publish (``get_secret`` raised ``NoKeyringError`` straight past the caller's
error handling, surfacing as a 500). Now the primary home is the shared store:
Fernet ciphertext in ``secret_values``, keyed by ``CRMBUILDER_V2_SECRET_KEY``
from the service environment. Secrets travel with the database instead of with a
laptop.

**Resolution order.** ``get_secret`` reads the encrypted store first, then falls
back to the keyring; ``put_secret`` writes to the store when a key is configured
and to the keyring when one is not. So:

* the hosted service (key set, no keyring) works entirely through the store;
* a developer machine (keyring, key optional) still resolves secrets it holds
  locally, and picks up store-held ones too once a key is configured;
* a secret written before this change keeps resolving from the keyring until it
  is migrated, so nothing breaks on the way across.

Store-first rather than keyring-first is deliberate: once a secret is migrated,
every host must resolve the *same* value, and a stale local keyring copy must
never shadow the shared one.

In headless environments without a backend *or* a key (CI, Docker without dbus),
set ``CRMBUILDER_KEYRING_DISABLE=1`` to fall back to an in-process dict — for
tests only.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Final

import keyring
import keyring.errors

logger = logging.getLogger(__name__)

SERVICE_NAME: Final[str] = "crmbuilder"
REF_PREFIX: Final[str] = "crmbuilder:"
DISABLE_ENV_VAR: Final[str] = "CRMBUILDER_KEYRING_DISABLE"

_in_memory_store: dict[str, str] = {}


class SecretBackendError(RuntimeError):
    """No usable backend could store or resolve a secret.

    Raised instead of letting a backend-specific failure (``NoKeyringError``, a
    bad key, an unreachable store) escape to a caller that cannot interpret it.
    The publish path turning ``NoKeyringError`` into an opaque 500 is exactly the
    failure this type exists to prevent.
    """


def _cipher():
    """The Fernet cipher for ``CRMBUILDER_V2_SECRET_KEY``, or ``None`` if unset.

    A malformed key raises rather than silently degrading to the keyring: a host
    that was *given* a key is meant to use the store, and quietly writing
    somewhere else would strand the secret exactly as before.
    """
    from crmbuilder_v2.config import get_settings

    key = (get_settings().secret_key or "").strip()
    if not key:
        return None
    from cryptography.fernet import Fernet

    try:
        return Fernet(key.encode())
    except Exception as exc:  # noqa: BLE001 — malformed/short/not-base64 key
        raise SecretBackendError(
            "CRMBUILDER_V2_SECRET_KEY is not a valid Fernet key (expected a "
            "urlsafe-base64 32-byte key, as produced by "
            "`python -c \"from cryptography.fernet import Fernet; "
            'print(Fernet.generate_key().decode())"`)'
        ) from exc


def store_available() -> bool:
    """Whether the encrypted store is configured on this host."""
    return _cipher() is not None


def _store_put(ref: str, value: str) -> None:
    """Encrypt and upsert one secret into the shared store."""
    from crmbuilder_v2.access.db import session_scope
    from crmbuilder_v2.access.models import SecretValue

    token = _cipher().encrypt(value.encode())
    with session_scope() as s:
        row = s.get(SecretValue, ref)
        if row is None:
            s.add(SecretValue(secret_ref=ref, secret_ciphertext=token))
        else:
            row.secret_ciphertext = token


def _store_get(ref: str) -> str | None:
    """Resolve one secret from the shared store, or ``None`` if it is not there.

    A row that exists but will not decrypt is a *wrong key*, not a miss — falling
    through to the keyring would mask a misconfigured host as a missing secret.
    """
    if _cipher() is None:
        return None
    from crmbuilder_v2.access.db import session_scope
    from crmbuilder_v2.access.models import SecretValue

    with session_scope() as s:
        row = s.get(SecretValue, ref)
        token = row.secret_ciphertext if row is not None else None
    if token is None:
        return None
    from cryptography.fernet import InvalidToken

    try:
        return _cipher().decrypt(token).decode()
    except InvalidToken as exc:
        raise SecretBackendError(
            f"stored secret {ref} could not be decrypted — "
            "CRMBUILDER_V2_SECRET_KEY does not match the key it was written with"
        ) from exc


def _is_disabled() -> bool:
    """Return ``True`` iff the keyring is disabled by environment variable.

    :returns: Whether the in-memory test fallback is active.
    """
    return os.environ.get(DISABLE_ENV_VAR, "").strip() in {"1", "true", "yes"}


def _new_ref() -> str:
    """Generate a new opaque reference id.

    :returns: A fresh ``crmbuilder:{uuid4}`` reference id.
    """
    return f"{REF_PREFIX}{uuid.uuid4()}"


def is_ref(value: str | None) -> bool:
    """Return ``True`` iff ``value`` looks like a CRMBuilder secret reference.

    :param value: A candidate string.
    :returns: Whether the value carries the reference prefix.
    """
    return bool(value) and value.startswith(REF_PREFIX)


def put_secret(value: str, *, ref: str | None = None) -> str:
    """Store a secret value and return an opaque reference id.

    Writes to the encrypted store when ``CRMBUILDER_V2_SECRET_KEY`` is set —
    which is what lets a headless host save credentials at all — and to the OS
    keyring otherwise.

    :param value: The secret value to store.
    :param ref: Reuse an existing reference instead of minting one. Used by the
        migration path to move a value under the reference already recorded on
        the owning row, so nothing has to be re-pointed.
    :returns: A reference id that resolves via :func:`get_secret`.
    :raises SecretBackendError: If neither the encrypted store nor the keyring
        can accept the write.
    """
    ref = ref or _new_ref()
    if _is_disabled():
        _in_memory_store[ref] = value
        return ref

    if store_available():
        _store_put(ref, value)
        return ref

    try:
        keyring.set_password(SERVICE_NAME, ref, value)
    except keyring.errors.KeyringError as exc:
        raise SecretBackendError(
            "Cannot store the secret: this host has no OS keyring backend and "
            "CRMBUILDER_V2_SECRET_KEY is not set, so there is nowhere to put it. "
            "Set CRMBUILDER_V2_SECRET_KEY in the service environment to use the "
            "encrypted store."
        ) from exc
    return ref


def get_secret(ref: str) -> str:
    """Resolve a reference id back to its stored secret value.

    Resolves from the encrypted store first, then the OS keyring — so a migrated
    secret resolves to the same value on every host, while one not yet migrated
    still resolves on the machine that holds it.

    :param ref: A reference id previously returned by :func:`put_secret`.
    :returns: The stored secret value.
    :raises ValueError: If ``ref`` is not a CRMBuilder reference id.
    :raises KeyError: If no value is stored under ``ref`` anywhere reachable.
    :raises SecretBackendError: If a backend is present but unusable — a wrong
        encryption key, or no backend at all on this host. Distinguished from
        ``KeyError`` so a caller can tell "this secret was never stored" from
        "this host cannot read secrets".
    """
    if not is_ref(ref):
        raise ValueError(f"Not a CRMBuilder secret reference: {ref!r}")

    if _is_disabled():
        if ref not in _in_memory_store:
            raise KeyError(ref)
        return _in_memory_store[ref]

    # Encrypted store first: once migrated, every host must agree on the value,
    # and a stale local keyring copy must never shadow the shared one.
    value = _store_get(ref)
    if value is not None:
        return value

    try:
        value = keyring.get_password(SERVICE_NAME, ref)
    except keyring.errors.KeyringError as exc:
        # No keyring here. If the store is configured, the secret simply isn't in
        # it yet — that's a miss. If neither backend exists, this host cannot
        # resolve secrets at all, which is a configuration fault, not a miss.
        if store_available():
            raise KeyError(ref) from exc
        raise SecretBackendError(
            "Cannot resolve the secret: this host has no OS keyring backend and "
            "CRMBUILDER_V2_SECRET_KEY is not set. Set CRMBUILDER_V2_SECRET_KEY in "
            "the service environment so secrets resolve from the encrypted store."
        ) from exc
    if value is None:
        raise KeyError(ref)
    return value


def delete_secret(ref: str | None) -> None:
    """Remove a secret from every backend. No-op if absent or not a reference.

    Deletes from the encrypted store *and* the keyring: a secret that survived in
    one of them would resurface as a resolvable credential for a deleted
    instance. Failure in either backend is swallowed, matching the pre-existing
    contract that deleting an already-absent secret is not an error.

    :param ref: A reference id previously returned by :func:`put_secret`.
    """
    if not is_ref(ref):
        return

    if _is_disabled():
        _in_memory_store.pop(ref, None)
        return

    if store_available():
        try:
            from crmbuilder_v2.access.db import session_scope
            from crmbuilder_v2.access.models import SecretValue

            with session_scope() as s:
                row = s.get(SecretValue, ref)
                if row is not None:
                    s.delete(row)
        except Exception:  # noqa: BLE001 — mirrors the keyring path's tolerance
            logger.debug("encrypted-store delete failed for %s", ref, exc_info=True)

    try:
        keyring.delete_password(SERVICE_NAME, ref)
    except keyring.errors.KeyringError:
        # PasswordDeleteError (absent) and NoKeyringError (headless) alike: on a
        # host with no keyring there is nothing of ours to delete.
        pass


def _reset_in_memory_store_for_tests() -> None:
    """Clear the in-memory fallback store. Test-only helper."""
    _in_memory_store.clear()
