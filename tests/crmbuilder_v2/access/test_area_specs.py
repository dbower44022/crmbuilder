"""Per-(release, area) implementation + testable spec — PI-244 (PRJ-041 / REQ-295).

The matrix back half's design artifact: append-only / versioned, current = latest
version per (release, area), each revision recording a change_reason + trigger; a
content fingerprint per version for the Design-Review freshness gate. Covers the
repository (author/current/history, versioning, fingerprint), validation, and the
not-found path.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import NotFoundError, UnprocessableError
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import area_specs, releases


def _set_status(s, rel, status):
    row = get_by_identifier(s, Release, Release.release_identifier, rel)
    row.release_status = status
    s.flush()


def _rel(s):
    return releases.create_release(s, title="R", description="d")["release_identifier"]


# --- author / current / versioning ------------------------------------------


def test_author_then_current(v2_env):
    with session_scope() as s:
        rel = _rel(s)
        out = area_specs.author_spec(
            s, rel, "storage", implementation="build it thus",
            testable="row persists; survives re-run", change_reason="initial",
            trigger_kind="initial")
        assert out["spec_version"] == 1
        assert out["spec_fingerprint"]
        cur = area_specs.current_spec(s, rel, "storage")
        assert cur["spec_version"] == 1
        assert cur["spec_implementation"] == "build it thus"
        assert cur["spec_testable"] == "row persists; survives re-run"


def test_revision_appends_and_current_is_latest(v2_env):
    with session_scope() as s:
        rel = _rel(s)
        area_specs.author_spec(s, rel, "access", implementation="v1 impl",
                               testable="v1 checks", trigger_kind="initial")
        v2 = area_specs.author_spec(
            s, rel, "access", implementation="v2 impl", testable="v2 checks",
            change_reason="Design Review rejected the cardinality criterion",
            trigger_kind="design_review")
        assert v2["spec_version"] == 2
        cur = area_specs.current_spec(s, rel, "access")
        assert cur["spec_version"] == 2 and cur["spec_implementation"] == "v2 impl"
        # history keeps both, oldest -> newest, with the reason/trigger chain
        hist = area_specs.spec_history(s, rel, "access")
        assert [h["spec_version"] for h in hist] == [1, 2]
        assert hist[1]["spec_change_reason"].startswith("Design Review")
        assert hist[1]["spec_trigger_kind"] == "design_review"
        # the prior version is never erased
        assert hist[0]["spec_implementation"] == "v1 impl"


def test_fingerprint_changes_with_content(v2_env):
    with session_scope() as s:
        rel = _rel(s)
        a = area_specs.author_spec(s, rel, "api", implementation="x", testable="y")
        b = area_specs.author_spec(s, rel, "api", implementation="x2", testable="y",
                                   trigger_kind="revision")
        assert a["spec_fingerprint"] != b["spec_fingerprint"]
        # identical content → identical fingerprint (the freshness-gate key)
        assert area_specs.fingerprint("x", "y") == a["spec_fingerprint"]


def test_versions_are_per_area(v2_env):
    with session_scope() as s:
        rel = _rel(s)
        area_specs.author_spec(s, rel, "storage", implementation="s", testable="s")
        area_specs.author_spec(s, rel, "ui", implementation="u", testable="u")
        area_specs.author_spec(s, rel, "storage", implementation="s2", testable="s2",
                               trigger_kind="revision")
        # storage is at v2, ui still v1 — versions are scoped per (release, area)
        assert area_specs.current_spec(s, rel, "storage")["spec_version"] == 2
        assert area_specs.current_spec(s, rel, "ui")["spec_version"] == 1


def test_current_specs_returns_latest_per_area(v2_env):
    with session_scope() as s:
        rel = _rel(s)
        area_specs.author_spec(s, rel, "storage", implementation="s1", testable="t")
        area_specs.author_spec(s, rel, "storage", implementation="s2", testable="t",
                               trigger_kind="revision")
        area_specs.author_spec(s, rel, "access", implementation="a", testable="t")
        specs = area_specs.current_specs(s, rel)
        by_area = {d["area"]: d for d in specs}
        assert set(by_area) == {"storage", "access"}
        assert by_area["storage"]["spec_version"] == 2
        assert by_area["storage"]["spec_implementation"] == "s2"


# --- validation / not-found -------------------------------------------------


def test_no_current_spec_returns_none(v2_env):
    with session_scope() as s:
        rel = _rel(s)
        assert area_specs.current_spec(s, rel, "storage") is None
        assert area_specs.current_specs(s, rel) == []


def test_invalid_trigger_kind_rejected(v2_env):
    with session_scope() as s:
        rel = _rel(s)
        with pytest.raises(UnprocessableError):
            area_specs.author_spec(s, rel, "storage", implementation="i",
                                   testable="t", trigger_kind="bogus")


def test_unknown_release_rejected(v2_env):
    with session_scope() as s:
        with pytest.raises(NotFoundError):
            area_specs.author_spec(s, "REL-999", "storage", implementation="i",
                                   testable="t")
        with pytest.raises(NotFoundError):
            area_specs.current_spec(s, "REL-999", "storage")
