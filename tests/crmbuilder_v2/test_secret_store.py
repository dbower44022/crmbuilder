"""The encrypted secret store and its fallback order — REQ-481 / REQ-157 / PI-402.

:mod:`crmbuilder_v2.secrets` grew a second backend: Fernet ciphertext in the
shared store, keyed by ``CRMBUILDER_V2_SECRET_KEY``. These tests pin the parts
that are easy to get subtly wrong and expensive to get wrong in production —
which backend wins, what happens on a host with no backend at all, and what a
mismatched key does. The pre-existing ``test_secrets.py`` still covers the
keyring-only contract; nothing there changes, because a host with no key
configured behaves exactly as it did.
"""

from __future__ import annotations

import keyring
import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.config import reset_settings_cache
from cryptography.fernet import Fernet
from keyring.backend import KeyringBackend


class _MemoryBackend(KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    def delete_password(self, service: str, username: str) -> None:
        from keyring.errors import PasswordDeleteError

        if (service, username) not in self._store:
            raise PasswordDeleteError(username)
        del self._store[(service, username)]


class _NoKeyringBackend(KeyringBackend):
    """The droplet's situation: a backend that refuses every operation."""

    priority = 1

    def _fail(self, *a, **k):
        from keyring.errors import NoKeyringError

        raise NoKeyringError("no backend")

    set_password = get_password = delete_password = _fail


@pytest.fixture
def memory_keyring(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(secrets.DISABLE_ENV_VAR, raising=False)
    original = keyring.get_keyring()
    keyring.set_keyring(_MemoryBackend())
    try:
        yield
    finally:
        keyring.set_keyring(original)


@pytest.fixture
def no_keyring(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(secrets.DISABLE_ENV_VAR, raising=False)
    original = keyring.get_keyring()
    keyring.set_keyring(_NoKeyringBackend())
    try:
        yield
    finally:
        keyring.set_keyring(original)


@pytest.fixture
def with_key(monkeypatch: pytest.MonkeyPatch):
    """Configure an encryption key, as the droplet's environment file does."""
    monkeypatch.setenv("CRMBUILDER_V2_SECRET_KEY", Fernet.generate_key().decode())
    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.fixture
def without_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CRMBUILDER_V2_SECRET_KEY", "")
    reset_settings_cache()
    yield
    reset_settings_cache()


# --- the headless case this whole change exists for --------------------------


def test_headless_host_with_a_key_can_store_and_resolve(v2_env, no_keyring, with_key):
    """The droplet: no keyring backend at all, but an encryption key. Both saving
    and resolving must work — before this change each raised."""
    ref = secrets.put_secret("espo-api-key")
    assert secrets.get_secret(ref) == "espo-api-key"


def test_headless_host_without_a_key_fails_clearly_on_write(v2_env, no_keyring, without_key):
    """No keyring and no key: nowhere to put a secret. That must be a typed,
    actionable error — not a bare NoKeyringError escaping as a 500."""
    with pytest.raises(secrets.SecretBackendError) as exc:
        secrets.put_secret("espo-api-key")
    assert "CRMBUILDER_V2_SECRET_KEY" in str(exc.value)


def test_headless_host_without_a_key_fails_clearly_on_read(v2_env, no_keyring, without_key):
    """The reported 500: get_secret on a host that can read from nowhere."""
    with pytest.raises(secrets.SecretBackendError):
        secrets.get_secret("crmbuilder:00000000-0000-0000-0000-000000000000")


def test_ciphertext_in_the_store_is_not_the_plaintext(v2_env, no_keyring, with_key):
    """REQ-157's surviving guarantee: no column holds a readable secret."""
    from crmbuilder_v2.access.db import session_scope
    from crmbuilder_v2.access.models import SecretValue

    ref = secrets.put_secret("hunter2")
    with session_scope() as s:
        row = s.get(SecretValue, ref)
    assert row is not None
    assert b"hunter2" not in row.secret_ciphertext


# --- resolution order --------------------------------------------------------


def test_store_wins_over_a_stale_keyring_copy(v2_env, memory_keyring, with_key):
    """Store-first is the point: after migration every host must agree on the
    value, so a stale local keyring copy must never shadow the shared one."""
    ref = secrets.put_secret("current-value")
    keyring.set_password(secrets.SERVICE_NAME, ref, "stale-local-value")
    assert secrets.get_secret(ref) == "current-value"


def test_keyring_still_resolves_a_secret_not_yet_migrated(v2_env, memory_keyring, with_key):
    """The migration window: a pre-existing keyring secret keeps working on the
    machine that holds it, even once a key is configured."""
    ref = "crmbuilder:11111111-1111-1111-1111-111111111111"
    keyring.set_password(secrets.SERVICE_NAME, ref, "legacy-value")
    assert secrets.get_secret(ref) == "legacy-value"


def test_no_key_configured_behaves_exactly_as_before(v2_env, memory_keyring, without_key):
    """A developer machine with a keyring and no key: unchanged round trip."""
    ref = secrets.put_secret("hunter2")
    assert secrets.get_secret(ref) == "hunter2"
    assert not secrets.store_available()


def test_unknown_ref_is_a_miss_not_a_backend_error(v2_env, memory_keyring, with_key):
    with pytest.raises(KeyError):
        secrets.get_secret("crmbuilder:22222222-2222-2222-2222-222222222222")


def test_unknown_ref_on_a_headless_host_with_a_key_is_a_miss(v2_env, no_keyring, with_key):
    """A configured store that simply lacks the secret is a miss, not a fault —
    otherwise a never-stored credential would read as a misconfigured host."""
    with pytest.raises(KeyError):
        secrets.get_secret("crmbuilder:33333333-3333-3333-3333-333333333333")


# --- key handling ------------------------------------------------------------


def test_wrong_key_is_reported_not_silently_a_miss(v2_env, no_keyring, monkeypatch):
    """A row that will not decrypt means the host has the wrong key. Falling
    through to "not found" would mask a misconfiguration as a missing secret."""
    monkeypatch.setenv("CRMBUILDER_V2_SECRET_KEY", Fernet.generate_key().decode())
    reset_settings_cache()
    ref = secrets.put_secret("hunter2")

    monkeypatch.setenv("CRMBUILDER_V2_SECRET_KEY", Fernet.generate_key().decode())
    reset_settings_cache()
    with pytest.raises(secrets.SecretBackendError) as exc:
        secrets.get_secret(ref)
    assert "does not match" in str(exc.value)
    reset_settings_cache()


def test_malformed_key_raises_rather_than_falling_back(v2_env, memory_keyring, monkeypatch):
    """A host given a key is meant to use the store; quietly writing to the
    keyring instead would strand the secret exactly as before."""
    monkeypatch.setenv("CRMBUILDER_V2_SECRET_KEY", "not-a-fernet-key")
    reset_settings_cache()
    with pytest.raises(secrets.SecretBackendError) as exc:
        secrets.put_secret("hunter2")
    assert "not a valid Fernet key" in str(exc.value)
    reset_settings_cache()


# --- migration + deletion ----------------------------------------------------


def test_put_can_reuse_an_existing_ref_for_migration(v2_env, memory_keyring, with_key):
    """How the migration CLI moves a value without re-pointing the instance row:
    same reference, now resolvable from the shared store."""
    ref = "crmbuilder:44444444-4444-4444-4444-444444444444"
    keyring.set_password(secrets.SERVICE_NAME, ref, "legacy-value")
    assert secrets.put_secret("legacy-value", ref=ref) == ref
    from crmbuilder_v2.access.db import session_scope
    from crmbuilder_v2.access.models import SecretValue

    with session_scope() as s:
        assert s.get(SecretValue, ref) is not None
    assert secrets.get_secret(ref) == "legacy-value"


def test_delete_clears_both_backends(v2_env, memory_keyring, with_key):
    """A secret surviving in either backend would resurface as a live credential
    for a deleted instance."""
    ref = secrets.put_secret("hunter2")
    keyring.set_password(secrets.SERVICE_NAME, ref, "hunter2")
    secrets.delete_secret(ref)
    with pytest.raises(KeyError):
        secrets.get_secret(ref)


def test_delete_on_a_headless_host_does_not_raise(v2_env, no_keyring, with_key):
    """Deleting is tolerant by contract; a missing keyring must not turn it into
    an error once the store part has been removed."""
    ref = secrets.put_secret("hunter2")
    secrets.delete_secret(ref)
    with pytest.raises(KeyError):
        secrets.get_secret(ref)
