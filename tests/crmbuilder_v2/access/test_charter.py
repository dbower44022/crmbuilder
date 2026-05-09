"""Charter repository tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import NotFoundError, ValidationError
from crmbuilder_v2.access.repositories import charter


def test_no_current_charter_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        charter.get_current(s)


def test_replace_creates_v1(v2_env):
    with session_scope() as s:
        row = charter.replace(s, payload={"scope": "first draft"})
    assert row["version"] == 1
    assert row["is_current"] is True
    assert row["payload"] == {"scope": "first draft"}


def test_replace_increments_version_and_demotes_previous(v2_env):
    with session_scope() as s:
        charter.replace(s, payload={"scope": "v1"})
    with session_scope() as s:
        v2 = charter.replace(s, payload={"scope": "v2"})
    assert v2["version"] == 2
    with session_scope() as s:
        all_versions = charter.list_versions(s)
        cur = charter.get_current(s)
    assert [v["version"] for v in all_versions] == [2, 1]
    assert cur["version"] == 2
    # Historical version must be flagged not-current.
    assert all_versions[1]["is_current"] is False


def test_replace_rejects_non_dict_payload(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        charter.replace(s, payload="oh hi")  # type: ignore[arg-type]


def test_make_version_current_flips_flag_back(v2_env):
    with session_scope() as s:
        charter.replace(s, payload={"scope": "v1"})
        charter.replace(s, payload={"scope": "v2"})
    with session_scope() as s:
        charter.make_version_current(s, version=1)
    with session_scope() as s:
        cur = charter.get_current(s)
        all_versions = charter.list_versions(s)
    assert cur["version"] == 1
    by_version = {v["version"]: v for v in all_versions}
    assert by_version[1]["is_current"] is True
    assert by_version[2]["is_current"] is False


def test_make_version_current_idempotent(v2_env):
    with session_scope() as s:
        charter.replace(s, payload={"scope": "v1"})
    with session_scope() as s:
        charter.make_version_current(s, version=1)
    with session_scope() as s:
        cur = charter.get_current(s)
    assert cur["version"] == 1
    assert cur["is_current"] is True


def test_make_version_current_unknown_version_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        charter.make_version_current(s, version=99)


def test_export_reflects_charter_state(v2_env, export_dir: Path):
    with session_scope() as s:
        charter.replace(s, payload={"scope": "demo"})
    rows = json.loads((export_dir / "charter.json").read_text())
    assert len(rows) == 1
    assert rows[0]["payload"] == {"scope": "demo"}
    assert rows[0]["is_current"] is True
