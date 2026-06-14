"""Keyring-backed secret storage for CRMBuilder V2.

Ported from the V1 helper ``automation/core/secrets.py`` for PI-186 (the
instance entity, PRJ-027). Provides a thin abstraction over the OS keyring
(macOS Keychain, Linux Secret Service, Windows Credential Manager) so the V2
store persists only opaque reference ids in the database while the actual
secret values live in the keyring (requirement REQ-157: connection secrets
are stored securely outside the database and referenced indirectly; secret
values are never held in plaintext columns).

Reference ids use the form ``crmbuilder:{uuid4}``; the keyring service name is
``crmbuilder`` (shared with V1 so a single keyring serves both apps). In
headless environments without a real backend (CI, Docker without dbus), set
``CRMBUILDER_KEYRING_DISABLE=1`` to fall back to an in-process dict — for tests
only; production paths require a real backend.
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


def put_secret(value: str) -> str:
    """Store a secret value and return an opaque reference id.

    :param value: The secret value to store.
    :returns: A reference id that resolves via :func:`get_secret`.
    :raises RuntimeError: If the keyring backend rejects the write (e.g. no
        usable backend on a headless system) and the in-memory fallback is
        not enabled.
    """
    ref = _new_ref()
    if _is_disabled():
        _in_memory_store[ref] = value
        return ref

    try:
        keyring.set_password(SERVICE_NAME, ref, value)
    except keyring.errors.KeyringError as exc:
        raise RuntimeError(
            "Could not write secret to OS keyring. On a headless system, set "
            f"{DISABLE_ENV_VAR}=1 for tests only."
        ) from exc
    return ref


def get_secret(ref: str) -> str:
    """Resolve a reference id back to its stored secret value.

    :param ref: A reference id previously returned by :func:`put_secret`.
    :returns: The stored secret value.
    :raises ValueError: If ``ref`` is not a CRMBuilder reference id.
    :raises KeyError: If no value is stored under ``ref``.
    """
    if not is_ref(ref):
        raise ValueError(f"Not a CRMBuilder secret reference: {ref!r}")

    if _is_disabled():
        if ref not in _in_memory_store:
            raise KeyError(ref)
        return _in_memory_store[ref]

    value = keyring.get_password(SERVICE_NAME, ref)
    if value is None:
        raise KeyError(ref)
    return value


def delete_secret(ref: str | None) -> None:
    """Remove a secret from the keyring. No-op if absent or not a reference.

    :param ref: A reference id previously returned by :func:`put_secret`.
    """
    if not is_ref(ref):
        return

    if _is_disabled():
        _in_memory_store.pop(ref, None)
        return

    try:
        keyring.delete_password(SERVICE_NAME, ref)
    except keyring.errors.PasswordDeleteError:
        pass


def _reset_in_memory_store_for_tests() -> None:
    """Clear the in-memory fallback store. Test-only helper."""
    _in_memory_store.clear()
