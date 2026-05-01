"""Tests for the keyring-backed secrets store.

Uses keyring's in-memory testing helpers so tests run without touching
the OS keychain.
"""

import keyring
import pytest
from keyring.backend import KeyringBackend

from automation.core import secrets


class _MemoryBackend(KeyringBackend):
    """An in-process KeyringBackend for tests."""

    priority = 1

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self._store:
            from keyring.errors import PasswordDeleteError
            raise PasswordDeleteError(username)
        del self._store[(service, username)]


@pytest.fixture(autouse=True)
def _memory_keyring(monkeypatch: pytest.MonkeyPatch):
    """Replace the active keyring with a fresh in-memory backend."""
    monkeypatch.delenv(secrets.DISABLE_ENV_VAR, raising=False)
    backend = _MemoryBackend()
    original = keyring.get_keyring()
    keyring.set_keyring(backend)
    try:
        yield backend
    finally:
        keyring.set_keyring(original)


# ── Round-trip ────────────────────────────────────────────────────────


def test_put_returns_prefixed_ref():
    ref = secrets.put_secret("hunter2")
    assert ref.startswith(secrets.REF_PREFIX)


def test_put_get_round_trip():
    ref = secrets.put_secret("hunter2")
    assert secrets.get_secret(ref) == "hunter2"


def test_put_returns_unique_refs_per_call():
    ref1 = secrets.put_secret("a")
    ref2 = secrets.put_secret("b")
    assert ref1 != ref2
    assert secrets.get_secret(ref1) == "a"
    assert secrets.get_secret(ref2) == "b"


def test_get_unknown_ref_raises_key_error():
    with pytest.raises(KeyError):
        secrets.get_secret("crmbuilder:nonexistent")


def test_get_invalid_ref_format_raises_value_error():
    with pytest.raises(ValueError):
        secrets.get_secret("not-a-ref")
    with pytest.raises(ValueError):
        secrets.get_secret("")


def test_delete_removes_secret():
    ref = secrets.put_secret("gone")
    secrets.delete_secret(ref)
    with pytest.raises(KeyError):
        secrets.get_secret(ref)


def test_delete_unknown_ref_is_noop():
    secrets.delete_secret("crmbuilder:nonexistent")  # should not raise


def test_delete_invalid_ref_is_noop():
    secrets.delete_secret("garbage")  # should not raise


# ── Service name and ref format ──────────────────────────────────────


def test_uses_crmbuilder_service_name(_memory_keyring: _MemoryBackend):
    secrets.put_secret("hello")
    services = {service for service, _ in _memory_keyring._store}
    assert services == {secrets.SERVICE_NAME}


def test_ref_uses_uuid_form():
    ref = secrets.put_secret("x")
    suffix = ref.removeprefix(secrets.REF_PREFIX)
    # uuid4 hex form is 36 chars including hyphens
    assert len(suffix) == 36
    assert suffix.count("-") == 4


# ── Disabled mode ────────────────────────────────────────────────────


def test_disabled_mode_uses_in_memory_store(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()

    ref = secrets.put_secret("disabled-secret")
    assert secrets.get_secret(ref) == "disabled-secret"
    secrets.delete_secret(ref)
    with pytest.raises(KeyError):
        secrets.get_secret(ref)


def test_disabled_mode_keyring_untouched(
    monkeypatch: pytest.MonkeyPatch,
    _memory_keyring: _MemoryBackend,
):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    secrets.put_secret("v")
    assert _memory_keyring._store == {}
