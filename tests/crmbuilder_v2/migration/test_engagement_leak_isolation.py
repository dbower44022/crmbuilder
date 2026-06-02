"""PI-123 Stage 3 — the cross-engagement isolation (leak) test.

The acceptance backbone of the unified multi-engagement DB (architecture §7):
seed a single database with **two** engagements that *intentionally share
identifiers* (both hold ``DEC-001``, ``PRJ-001``), then assert that under
engagement A's active context every read/list/identifier-assignment path
returns only A's rows — never B's. This is the regression net for the D5
central read-filter / write-stamp mechanism.

Unlike ``test_engagement_id_collision_coexistence`` (raw DDL, proves the schema
admits coexistence) this exercises the **real access layer** — the repositories,
``session_scope``, and the ContextVar scope mechanism end-to-end. It covers both
constraint classes: ``decisions`` (Class B — surrogate ``id`` PK + composite
``UNIQUE(engagement_id, identifier)``) and ``projects`` (Class A — composite PK
``(engagement_id, project_identifier)``). Both create without mandatory edges.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from crmbuilder_v2.access import engagement_scope as es
from crmbuilder_v2.access.db import (
    bootstrap_database,
    get_session_factory,
    reset_engine_cache,
    session_scope,
)
from crmbuilder_v2.access.models import EngagementRow
from crmbuilder_v2.access.repositories import decisions as dec_repo
from crmbuilder_v2.access.repositories import projects as prj_repo
from crmbuilder_v2.config import reset_settings_cache

_EXEC = "x" * 200  # satisfies the 200..800 executive-summary CHECK


def _seed_engagement(ident: str, code: str) -> None:
    factory = get_session_factory()
    s = factory()
    now = datetime.now(UTC)
    s.add(
        EngagementRow(
            engagement_identifier=ident,
            engagement_code=code,
            engagement_name=code,
            engagement_purpose="leak-test",
            engagement_status="active",
            engagement_created_at=now,
            engagement_updated_at=now,
        )
    )
    s.commit()
    s.close()


@pytest.fixture
def two_engagements(tmp_path, monkeypatch) -> Iterator[None]:
    """A unified DB with ENG-001 and ENG-002, scoping enabled + enforced."""
    monkeypatch.setenv("CRMBUILDER_V2_DB_PATH", str(tmp_path / "v2.db"))
    export = tmp_path / "db-export"
    export.mkdir()
    monkeypatch.setenv("CRMBUILDER_V2_EXPORT_DIR", str(export))
    monkeypatch.setenv("CRMBUILDER_V2_ENGAGEMENT_SCOPING_ENABLED", "true")
    reset_settings_cache()
    reset_engine_cache()
    bootstrap_database()
    _seed_engagement("ENG-001", "ALPHA")
    _seed_engagement("ENG-002", "BETA")
    prev = es.set_enforcement(True)
    try:
        yield
    finally:
        es.set_enforcement(prev)
        reset_engine_cache()
        reset_settings_cache()


def _create_decision(eng: str, title: str, ident: str | None) -> str:
    with es.active_engagement(eng), session_scope() as s:
        return dec_repo.create(
            s, title=title, decision_date="2026-06-02", status="Active",
            executive_summary=_EXEC, identifier=ident,
        )["identifier"]


def _create_project(eng: str, name: str, ident: str | None) -> str:
    with es.active_engagement(eng), session_scope() as s:
        return prj_repo.create_project(
            s, name=name, purpose="p", description="d", identifier=ident,
        )["project_identifier"]


def test_same_identifier_coexists_across_engagements(two_engagements):
    """Both engagements can hold DEC-001 / PRJ-001 — no collision."""
    assert _create_decision("ENG-001", "alpha decision", "DEC-001") == "DEC-001"
    assert _create_decision("ENG-002", "beta decision", "DEC-001") == "DEC-001"
    assert _create_project("ENG-001", "alpha project", "PRJ-001") == "PRJ-001"
    assert _create_project("ENG-002", "beta project", "PRJ-001") == "PRJ-001"


def test_reads_scoped_to_active_engagement(two_engagements):
    """A list under ENG-001 returns only ENG-001's rows."""
    _create_decision("ENG-001", "alpha-1", "DEC-001")
    _create_decision("ENG-001", "alpha-2", "DEC-002")
    _create_decision("ENG-002", "beta-1", "DEC-001")

    with es.active_engagement("ENG-001"), session_scope(export=False) as s:
        a_titles = {r["title"] for r in dec_repo.list_all(s)}
    with es.active_engagement("ENG-002"), session_scope(export=False) as s:
        b_titles = {r["title"] for r in dec_repo.list_all(s)}

    assert a_titles == {"alpha-1", "alpha-2"}
    assert b_titles == {"beta-1"}


def test_get_by_identifier_scoped(two_engagements):
    """Fetching DEC-001 returns the active engagement's row, not the other's."""
    _create_decision("ENG-001", "alpha decision", "DEC-001")
    _create_decision("ENG-002", "beta decision", "DEC-001")

    with es.active_engagement("ENG-001"), session_scope(export=False) as s:
        a = dec_repo.get(s, "DEC-001")
    with es.active_engagement("ENG-002"), session_scope(export=False) as s:
        b = dec_repo.get(s, "DEC-001")
    assert a["title"] == "alpha decision"
    assert b["title"] == "beta decision"


def test_next_identifier_scoped_per_engagement(two_engagements):
    """Identifier assignment advances each engagement's own sequence."""
    _create_decision("ENG-001", "a1", "DEC-001")
    _create_decision("ENG-001", "a2", "DEC-002")
    # Auto-assign in ENG-001 → DEC-003 (sees only ENG-001's rows).
    assert _create_decision("ENG-001", "a3", None) == "DEC-003"
    # Auto-assign in ENG-002 → DEC-001 (its sequence is independent).
    assert _create_decision("ENG-002", "b1", None) == "DEC-001"
