"""Storage-layer tests for the ``services`` table (PI-161).

Exercises the schema-boundary CHECK constraints the WTK-132 design spec
puts on the table itself (service.md §3.2 + §5.2 items 1–3) via raw SQL
against a ``create_all`` SQLite store — repository-layer validation
(transition checking, case-insensitive name uniqueness, the atomic
``rejected_by_decision`` edge) is a sibling Work Task and is deliberately
not covered here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from crmbuilder_v2.access.models import Base, Service
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

_INSERT = text(
    "INSERT INTO services "
    "(engagement_id, service_identifier, service_name, service_purpose, "
    "service_capabilities, service_notes, service_status, "
    "service_created_at, service_updated_at) "
    "VALUES (:eng, :ident, :name, :purpose, :capabilities, :notes, :status, "
    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
)

_ROW = {
    "eng": "ENG-001",
    "ident": "SVC-001",
    "name": "Document Storage",
    "purpose": "Store, version, and attach documents across all domains.",
    "capabilities": "- Store and version uploaded documents\n- Full-text search",
    "notes": None,
    "status": "confirmed",
}


@pytest.fixture
def engine(tmp_path: Path):
    eng = create_engine(f"sqlite:///{tmp_path / 'v2.db'}")
    Base.metadata.create_all(eng)
    with eng.begin() as c:
        c.execute(
            text(
                "INSERT INTO engagements "
                "(engagement_identifier, engagement_code, engagement_name, "
                "engagement_purpose, engagement_status, engagement_created_at, "
                "engagement_updated_at) "
                "VALUES ('ENG-001', 'TEST', 'Test', 'p', 'active', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
    yield eng
    eng.dispose()


def _insert(engine, **overrides) -> None:
    with engine.begin() as c:
        c.execute(_INSERT, {**_ROW, **overrides})


def test_models_define_services_table():
    assert "services" in Base.metadata.tables
    assert Service.__tablename__ == "services"


def test_minimal_row_round_trips(engine):
    # Only the required content fields; optional columns NULL.
    _insert(engine, ident="SVC-002", capabilities=None, notes=None)
    with engine.begin() as c:
        name = c.execute(
            text(
                "SELECT service_name FROM services "
                "WHERE service_identifier = 'SVC-002'"
            )
        ).scalar_one()
    assert name == "Document Storage"


def test_default_status_is_candidate():
    # The model carries the Python-side ``candidate`` default (applied by the
    # ORM on insert; the standard four-status starter per §3.2.3).
    assert Service.service_status.default.arg == "candidate"


def test_identifier_format_check(engine):
    with pytest.raises(IntegrityError):
        _insert(engine, ident="SVC-1")
    with pytest.raises(IntegrityError):
        _insert(engine, ident="SRV-001")
    with pytest.raises(IntegrityError):
        _insert(engine, ident="SVC-0001")


def test_status_check(engine):
    with pytest.raises(IntegrityError):
        _insert(engine, status="Open")
    with pytest.raises(IntegrityError):
        _insert(engine, status="archived")


def test_duplicate_identifier_rejected_within_engagement(engine):
    _insert(engine)
    with pytest.raises(IntegrityError):
        _insert(engine)


def test_four_dogfood_services_coexist(engine):
    # The SES-166 backfill set (§6) all fit the schema with distinct ids.
    _insert(engine, ident="SVC-001", name="Document Storage")
    _insert(engine, ident="SVC-002", name="Notifications")
    _insert(engine, ident="SVC-003", name="User Accounts")
    _insert(engine, ident="SVC-004", name="AI Agent Orchestration")
    with engine.begin() as c:
        n = c.execute(text("SELECT COUNT(*) FROM services")).scalar_one()
    assert n == 4
