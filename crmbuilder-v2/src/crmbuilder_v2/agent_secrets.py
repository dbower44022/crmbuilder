"""Keyring-backed storage + runtime resolution for agent secrets (PI-321).

REQ-253 ("Security Key/Token Storage"): the system must provide a secure method
to store the keys and tokens agents need to reach the remote systems they work
against — chiefly ``ANTHROPIC_API_KEY`` for the ADO fleet, which spawns real
``claude -p`` agents. Historically that key lived in **plaintext** in the
gitignored ``crmbuilder-v2/data/crmbuilder.env`` and reached a spawned agent only
because the launching shell happened to export it. This module moves the value
into the OS keyring and resolves it at spawn time, keeping the plaintext ``.env``
as a fallback **only** for headless/CI environments that have no keyring backend.

Resolution order (deliberately **keyring-first**, unlike the interactive chat
tab's env-first :func:`crmbuilder_v2.ui.chat.auth.resolve_api_key`):

1. A named OS keyring entry (service ``crmbuilder-v2-agent``, user = the env-var
   name, e.g. ``ANTHROPIC_API_KEY``).
2. The process environment (``os.environ``) — how a CI secret or a still-exported
   ``.env`` value arrives.

Keyring-first is what lets the plaintext be *removed* from the ``.env``: once the
value is in the keyring, resolution stops consulting the environment first, so
the fleet keeps working with no plaintext copy. Where no keyring backend exists
(headless CI, Docker without dbus), the keyring lookup fails soft to ``None`` and
the environment fallback carries the fleet exactly as before — so migrating never
risks the running fleet losing its key.

``keyring`` is imported lazily so a missing/broken backend never breaks import on
a headless box; every keyring call is guarded and degrades to the env fallback.
"""

from __future__ import annotations

import logging
import os
from typing import Final

logger = logging.getLogger(__name__)

#: Keyring service namespace for agent runtime secrets. Distinct from the
#: opaque-ref ``crmbuilder`` service used for entity-attached secrets
#: (:mod:`crmbuilder_v2.secrets`) and the ``crmbuilder-v2-chat`` service used by
#: the interactive chat tab — each is a separate, purpose-named slot.
KEYRING_SERVICE: Final[str] = "crmbuilder-v2-agent"

#: The env-var names an agent may need at runtime. The keyring "user" for each
#: entry is the env-var name itself, so a stored ``ANTHROPIC_API_KEY`` shadows the
#: plaintext ``.env`` value of the same name. Extend this as agents grow to reach
#: more remote systems (e.g. per-instance API tokens).
AGENT_SECRET_NAMES: Final[tuple[str, ...]] = ("ANTHROPIC_API_KEY",)


def _keyring_get(name: str) -> str | None:
    """Read one named agent secret from the keyring, or ``None`` on any failure."""
    try:
        import keyring

        return keyring.get_password(KEYRING_SERVICE, name)
    except Exception:  # noqa: BLE001 — backend may be missing/locked/headless
        logger.debug("keyring.get_password unavailable for %s", name, exc_info=True)
        return None


def keyring_available() -> bool:
    """Whether a usable (non-fail) keyring backend is present on this host."""
    try:
        import keyring
        from keyring.backends.fail import Keyring as FailKeyring

        return not isinstance(keyring.get_keyring(), FailKeyring)
    except Exception:  # noqa: BLE001
        return False


def store_secret(name: str, value: str) -> None:
    """Store one named agent secret in the OS keyring.

    :param name: The env-var name (e.g. ``ANTHROPIC_API_KEY``) used as the keyring
        entry's user, so runtime resolution shadows the same-named env value.
    :param value: The secret value.
    :raises RuntimeError: If no usable keyring backend accepts the write. The
        caller should surface this rather than silently leaving the secret in
        plaintext.
    """
    try:
        import keyring

        keyring.set_password(KEYRING_SERVICE, name, value)
    except Exception as exc:  # noqa: BLE001 — no/locked backend
        raise RuntimeError(
            f"Could not write agent secret {name!r} to the OS keyring. On a "
            "headless system without a keyring backend, keep the value in the "
            "environment/.env fallback instead."
        ) from exc


def delete_secret(name: str) -> None:
    """Remove one named agent secret from the keyring. No-op if absent/unavailable."""
    try:
        import keyring
        import keyring.errors

        try:
            keyring.delete_password(KEYRING_SERVICE, name)
        except keyring.errors.PasswordDeleteError:
            pass
    except Exception:  # noqa: BLE001 — backend missing/locked
        logger.debug("keyring.delete_password unavailable for %s", name, exc_info=True)


def resolve_secret(name: str) -> str | None:
    """Resolve one agent secret, **keyring-first** then the environment.

    Returns ``None`` only when neither source has a value — so a spawned agent
    that genuinely has no key configured is a distinguishable, loud condition.
    """
    from_keyring = _keyring_get(name)
    if from_keyring:
        return from_keyring
    env_value = os.environ.get(name)
    if env_value:
        return env_value
    return None


def resolved_agent_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Return an environment mapping for a spawned agent with secrets resolved.

    Starts from ``base`` (default: a copy of ``os.environ``) and, for every known
    agent secret, overlays the **resolved** value (keyring-first, env-fallback).
    A name absent from both sources is left untouched — so this never *removes* a
    value the environment already carries, preserving the headless/CI fallback and
    guaranteeing a running fleet never loses a key it already had.

    Pass the result as ``subprocess.run(..., env=...)`` when spawning an agent.
    """
    env = dict(os.environ if base is None else base)
    for name in AGENT_SECRET_NAMES:
        value = resolve_secret(name)
        if value:
            env[name] = value
    return env


# --------------------------------------------------------------------------
# Migration CLI — move agent secrets out of the plaintext .env into the keyring
# --------------------------------------------------------------------------


def _env_file_path() -> str:
    """Path to the gitignored ``crmbuilder-v2/data/crmbuilder.env`` file."""
    from crmbuilder_v2.config import _repo_root

    return str(_repo_root() / "crmbuilder-v2" / "data" / "crmbuilder.env")


def _read_env_file(path: str) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines from an env file. Missing file → empty dict."""
    values: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip()
    except FileNotFoundError:
        pass
    return values


def _purge_env_file_lines(path: str, names: set[str]) -> list[str]:
    """Remove ``NAME=...`` lines for ``names`` from the env file in place.

    :returns: The list of names actually removed.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        return []
    removed: list[str] = []
    kept: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        key = stripped.partition("=")[0].strip() if "=" in stripped else ""
        if key in names and not stripped.startswith("#"):
            removed.append(key)
            continue
        kept.append(raw)
    if removed:
        with open(path, "w", encoding="utf-8") as fh:
            fh.writelines(kept)
    return removed


def main(argv: list[str] | None = None) -> int:
    """CLI: migrate agent secrets from the plaintext ``.env`` into the OS keyring.

    For each known agent secret found in ``crmbuilder.env`` (or, with
    ``--from-env``, the current process environment), store it in the keyring so
    runtime resolution serves it keyring-first. With ``--purge-env-file`` the
    plaintext lines are then removed from ``crmbuilder.env`` — the point of the
    migration. Without it, the plaintext is left in place (a safe dry-run that
    still populates the keyring) and the operator is told to remove it.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-migrate-agent-secrets",
        description="Move agent secrets (e.g. ANTHROPIC_API_KEY) from the plaintext "
        "crmbuilder.env into the OS keyring.",
    )
    parser.add_argument(
        "--from-env",
        action="store_true",
        help="Read values from the current process environment instead of the "
        "crmbuilder.env file.",
    )
    parser.add_argument(
        "--purge-env-file",
        action="store_true",
        help="After a successful keyring write, remove the migrated NAME=... lines "
        "from crmbuilder.env (the point of the migration).",
    )
    args = parser.parse_args(argv)

    if not keyring_available():
        print(
            "No usable OS keyring backend is available on this host. Agent secrets "
            "cannot be migrated here; the environment/.env fallback remains in use.",
        )
        return 2

    env_path = _env_file_path()
    source = dict(os.environ) if args.from_env else _read_env_file(env_path)
    source_label = "the environment" if args.from_env else env_path

    migrated: list[str] = []
    for name in AGENT_SECRET_NAMES:
        value = source.get(name)
        if not value:
            print(f"  {name}: not found in {source_label} — skipped")
            continue
        store_secret(name, value)
        # Verify the round-trip before we consider it migrated.
        if _keyring_get(name) != value:
            print(f"  {name}: keyring write did not round-trip — NOT migrated")
            return 1
        migrated.append(name)
        print(f"  {name}: stored in keyring (service {KEYRING_SERVICE!r})")

    if not migrated:
        print("Nothing to migrate.")
        return 0

    if args.purge_env_file and not args.from_env:
        removed = _purge_env_file_lines(env_path, set(migrated))
        if removed:
            print(f"Removed plaintext lines from {env_path}: {', '.join(removed)}")
    elif not args.from_env:
        print(
            "\nPlaintext values are still present in "
            f"{env_path}.\nRe-run with --purge-env-file to remove them, or delete "
            f"the {', '.join(migrated)} line(s) by hand."
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
