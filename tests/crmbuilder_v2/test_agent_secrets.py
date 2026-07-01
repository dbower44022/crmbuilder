"""Unit tests for agent runtime secret storage + resolution (PI-321 / REQ-253).

Covers the keyring-first-then-env resolution order, the ``resolved_agent_env``
overlay used when spawning agents (including the guarantee that it never removes
a value the environment already carries — the headless/CI fallback), and the
migration CLI that moves ``ANTHROPIC_API_KEY`` out of the plaintext ``.env`` into
the keyring.

Uses keyring's pluggable backend so tests never touch the OS keychain.
"""

from __future__ import annotations

import keyring
import pytest
from crmbuilder_v2 import agent_secrets
from keyring.backend import KeyringBackend


class _MemoryBackend(KeyringBackend):
    """An in-process ``KeyringBackend`` for tests."""

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


@pytest.fixture
def memory_keyring(monkeypatch: pytest.MonkeyPatch):
    """Replace the active keyring with a fresh in-memory backend."""
    backend = _MemoryBackend()
    original = keyring.get_keyring()
    keyring.set_keyring(backend)
    try:
        yield backend
    finally:
        keyring.set_keyring(original)


@pytest.fixture
def no_anthropic_env(monkeypatch: pytest.MonkeyPatch):
    """Ensure ANTHROPIC_API_KEY is not inherited from the real environment."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


# -- store / resolve round trip ---------------------------------------------


def test_store_and_resolve_from_keyring(memory_keyring, no_anthropic_env):
    agent_secrets.store_secret("ANTHROPIC_API_KEY", "sk-ant-keyring")
    assert agent_secrets.resolve_secret("ANTHROPIC_API_KEY") == "sk-ant-keyring"


def test_resolve_keyring_first_over_env(memory_keyring, monkeypatch):
    """Keyring wins over the environment — the property that lets the plaintext
    be removed from the .env once the value is in the keyring."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env")
    agent_secrets.store_secret("ANTHROPIC_API_KEY", "sk-ant-keyring")
    assert agent_secrets.resolve_secret("ANTHROPIC_API_KEY") == "sk-ant-keyring"


def test_resolve_falls_back_to_env(memory_keyring, monkeypatch):
    """No keyring entry → the environment fallback carries the value (headless/CI)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env")
    assert agent_secrets.resolve_secret("ANTHROPIC_API_KEY") == "sk-ant-env"


def test_resolve_none_when_absent_everywhere(memory_keyring, no_anthropic_env):
    assert agent_secrets.resolve_secret("ANTHROPIC_API_KEY") is None


def test_delete_secret_removes_keyring_entry(memory_keyring, no_anthropic_env):
    agent_secrets.store_secret("ANTHROPIC_API_KEY", "sk-ant-x")
    agent_secrets.delete_secret("ANTHROPIC_API_KEY")
    assert agent_secrets.resolve_secret("ANTHROPIC_API_KEY") is None


def test_delete_missing_is_noop(memory_keyring):
    agent_secrets.delete_secret("ANTHROPIC_API_KEY")  # should not raise


def test_store_uses_agent_service_name(memory_keyring, no_anthropic_env):
    agent_secrets.store_secret("ANTHROPIC_API_KEY", "v")
    services = {service for service, _ in memory_keyring._store}
    assert services == {agent_secrets.KEYRING_SERVICE}


# -- resolved_agent_env overlay ---------------------------------------------


def test_resolved_env_overlays_keyring_value(memory_keyring, no_anthropic_env):
    agent_secrets.store_secret("ANTHROPIC_API_KEY", "sk-ant-keyring")
    env = agent_secrets.resolved_agent_env(base={"PATH": "/usr/bin"})
    assert env["ANTHROPIC_API_KEY"] == "sk-ant-keyring"
    assert env["PATH"] == "/usr/bin"  # base preserved


def test_resolved_env_preserves_env_only_value(memory_keyring):
    """A key present only in the base env is passed through unchanged — the fleet
    never loses a key it already had (backward compat + headless)."""
    env = agent_secrets.resolved_agent_env(
        base={"ANTHROPIC_API_KEY": "sk-ant-env", "PATH": "/bin"}
    )
    assert env["ANTHROPIC_API_KEY"] == "sk-ant-env"


def test_resolved_env_no_key_leaves_absent(memory_keyring, no_anthropic_env):
    env = agent_secrets.resolved_agent_env(base={"PATH": "/bin"})
    assert "ANTHROPIC_API_KEY" not in env


def test_resolved_env_defaults_to_os_environ(memory_keyring, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-os")
    env = agent_secrets.resolved_agent_env()
    assert env["ANTHROPIC_API_KEY"] == "sk-ant-os"


# -- migration CLI ----------------------------------------------------------


def test_migrate_from_env_file(tmp_path, memory_keyring, monkeypatch, no_anthropic_env):
    env_file = tmp_path / "crmbuilder.env"
    env_file.write_text(
        "CRMBUILDER_V2_DATABASE_URL=postgresql://x\n"
        "ANTHROPIC_API_KEY=sk-ant-fromfile\n"
    )
    monkeypatch.setattr(agent_secrets, "_env_file_path", lambda: str(env_file))
    monkeypatch.setattr(agent_secrets, "keyring_available", lambda: True)

    rc = agent_secrets.main([])
    assert rc == 0
    assert agent_secrets._keyring_get("ANTHROPIC_API_KEY") == "sk-ant-fromfile"
    # Without --purge-env-file the plaintext stays put.
    assert "ANTHROPIC_API_KEY=sk-ant-fromfile" in env_file.read_text()


def test_migrate_purges_env_file(tmp_path, memory_keyring, monkeypatch, no_anthropic_env):
    env_file = tmp_path / "crmbuilder.env"
    env_file.write_text(
        "CRMBUILDER_V2_DATABASE_URL=postgresql://x\n"
        "ANTHROPIC_API_KEY=sk-ant-fromfile\n"
    )
    monkeypatch.setattr(agent_secrets, "_env_file_path", lambda: str(env_file))
    monkeypatch.setattr(agent_secrets, "keyring_available", lambda: True)

    rc = agent_secrets.main(["--purge-env-file"])
    assert rc == 0
    text = env_file.read_text()
    assert "ANTHROPIC_API_KEY" not in text
    # An unrelated line is left intact.
    assert "CRMBUILDER_V2_DATABASE_URL=postgresql://x" in text
    # And the value is resolvable from the keyring after purge.
    assert agent_secrets.resolve_secret("ANTHROPIC_API_KEY") == "sk-ant-fromfile"


def test_migrate_no_keyring_backend_returns_2(monkeypatch):
    monkeypatch.setattr(agent_secrets, "keyring_available", lambda: False)
    assert agent_secrets.main([]) == 2


def test_migrate_nothing_to_migrate(tmp_path, memory_keyring, monkeypatch, no_anthropic_env):
    env_file = tmp_path / "crmbuilder.env"
    env_file.write_text("CRMBUILDER_V2_DATABASE_URL=postgresql://x\n")
    monkeypatch.setattr(agent_secrets, "_env_file_path", lambda: str(env_file))
    monkeypatch.setattr(agent_secrets, "keyring_available", lambda: True)
    assert agent_secrets.main([]) == 0
