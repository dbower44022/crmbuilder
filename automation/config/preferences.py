"""Per-machine application preferences (Qt-free).

Stores user preferences in a JSON file at
``~/.config/crmbuilder/preferences.json``.  Safe to import before any
Qt code runs.  All read operations return ``None`` on missing keys,
corrupt files, or missing files — never raises.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_prefs_dir() -> Path:
    """Return the directory for the preferences file."""
    return Path.home() / ".config" / "crmbuilder"


def _read_prefs() -> dict:
    """Read the preferences file, returning an empty dict on any error."""
    try:
        prefs_file = _get_prefs_dir() / "preferences.json"
        if prefs_file.exists():
            return json.loads(prefs_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, TypeError):
        pass
    return {}


def _write_prefs(prefs: dict) -> None:
    """Write the preferences dict to disk, creating the directory if needed."""
    try:
        prefs_dir = _get_prefs_dir()
        prefs_dir.mkdir(parents=True, exist_ok=True)
        prefs_file = prefs_dir / "preferences.json"
        prefs_file.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
    except OSError:
        logger.warning("Could not write preferences to %s", _get_prefs_dir())


def get_last_active_tab() -> str | None:
    """Return the last active tab name, or None.

    :returns: One of ``"clients"``, ``"requirements"``, ``"deployment"``,
        or ``None``.
    """
    value = _read_prefs().get("last_active_tab")
    if value in ("clients", "requirements", "deployment", "crm_compare"):
        return value
    return None


def set_last_active_tab(tab: str) -> None:
    """Persist the last active tab name.

    :param tab: Tab name (``"clients"``, ``"requirements"``, or
        ``"deployment"``).
    """
    prefs = _read_prefs()
    prefs["last_active_tab"] = tab
    _write_prefs(prefs)


def get_last_selected_client_id() -> int | None:
    """Return the last selected client ID, or None."""
    value = _read_prefs().get("last_selected_client_id")
    if isinstance(value, int):
        return value
    return None


def get_anthropic_api_key() -> str | None:
    """Return the stored Anthropic API key, or None."""
    return _read_prefs().get("anthropic_api_key")


def set_anthropic_api_key(key: str) -> None:
    """Persist the Anthropic API key.

    :param key: API key string.
    """
    prefs = _read_prefs()
    prefs["anthropic_api_key"] = key
    _write_prefs(prefs)


def set_last_selected_client_id(client_id: int | None) -> None:
    """Persist the last selected client ID.

    :param client_id: Client ID integer, or None to clear.
    """
    prefs = _read_prefs()
    prefs["last_selected_client_id"] = client_id
    _write_prefs(prefs)
