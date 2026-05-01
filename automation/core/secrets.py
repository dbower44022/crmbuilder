"""Keyring-backed secret storage for CRM Builder.

Provides a thin abstraction over the OS keyring (macOS Keychain, Linux
Secret Service, Windows Credential Manager) so the rest of the
codebase persists opaque reference IDs in SQLite while the actual
secret values live in the keyring.

Reference IDs use the form ``crmbuilder:{uuid4}``. The keyring service
name is ``crmbuilder``.

In headless environments without a real backend (CI, Docker without
dbus), set ``CRMBUILDER_KEYRING_DISABLE=1`` to fall back to an
in-process dict — **for tests only**. Production code paths require a
real backend.

See PRDs/product/features/feat-server-management.md §5.2.
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
    """Return True iff the keyring is disabled by environment variable."""
    return os.environ.get(DISABLE_ENV_VAR, "").strip() in {"1", "true", "yes"}


def _new_ref() -> str:
    """Generate a new opaque reference id."""
    return f"{REF_PREFIX}{uuid.uuid4()}"


def put_secret(value: str) -> str:
    """Store a secret value and return an opaque reference id.

    :param value: The secret value to store.
    :returns: A reference id that can be passed to ``get_secret``.
    :raises RuntimeError: If the keyring backend rejects the write
        (e.g., no usable backend on a headless system) and the
        in-memory fallback is not enabled.
    """
    ref = _new_ref()
    if _is_disabled():
        _in_memory_store[ref] = value
        return ref

    try:
        keyring.set_password(SERVICE_NAME, ref, value)
    except keyring.errors.KeyringError as exc:
        raise RuntimeError(
            "Could not write secret to OS keyring. On a headless "
            f"system, set {DISABLE_ENV_VAR}=1 for tests only."
        ) from exc
    return ref


def get_secret(ref: str) -> str:
    """Resolve a reference id back to its stored secret value.

    :param ref: A reference id previously returned by ``put_secret``.
    :returns: The stored secret value.
    :raises KeyError: If no value is stored under ``ref``.
    :raises ValueError: If ``ref`` does not look like a CRM Builder
        reference id.
    """
    if not ref or not ref.startswith(REF_PREFIX):
        raise ValueError(f"Not a CRM Builder secret reference: {ref!r}")

    if _is_disabled():
        if ref not in _in_memory_store:
            raise KeyError(ref)
        return _in_memory_store[ref]

    value = keyring.get_password(SERVICE_NAME, ref)
    if value is None:
        raise KeyError(ref)
    return value


def delete_secret(ref: str) -> None:
    """Remove a secret from the keyring. No-op if it does not exist.

    :param ref: A reference id previously returned by ``put_secret``.
    """
    if not ref or not ref.startswith(REF_PREFIX):
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
