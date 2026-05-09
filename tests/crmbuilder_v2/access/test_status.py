"""Status repository tests."""

from __future__ import annotations

import json

import pytest

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import status


def test_no_current_status(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        status.get_current(s)


def test_status_versioning(v2_env, export_dir):
    with session_scope() as s:
        status.replace(s, payload={"phase": "Planning"})
    with session_scope() as s:
        status.replace(s, payload={"phase": "Build"})
    with session_scope() as s:
        cur = status.get_current(s)
        versions = status.list_versions(s)
    assert cur["payload"]["phase"] == "Build"
    assert [v["version"] for v in versions] == [2, 1]

    rows = json.loads((export_dir / "status.json").read_text())
    assert len(rows) == 2


def test_make_status_version_current_flips_flag_back(v2_env):
    with session_scope() as s:
        status.replace(s, payload={"phase": "Planning"})
        status.replace(s, payload={"phase": "Build"})
    with session_scope() as s:
        status.make_version_current(s, version=1)
    with session_scope() as s:
        cur = status.get_current(s)
    assert cur["version"] == 1


def test_make_status_version_current_unknown_version_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        status.make_version_current(s, version=99)
