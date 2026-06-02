"""PI-123 Slice 3 — empirical proof of the composite-identifier collision fix.

The headline crux of the unified multi-engagement DB: two engagements must be
able to hold a row with the *same* identifier (CBM's ``SES-001`` and
CRMBUILDER's ``SES-001``) in one database, while an identifier collision
*within* one engagement is still rejected.

This builds a small target-schema DB by raw DDL — representative of each
constraint class from ``pi-123-slice3-enforce-plan.md`` — and proves the
behaviour. It validates the *design* (composite ``(engagement_id, identifier)``
keying); the production strict-schema flip + consolidation that reach it are the
cutover unit (the live ORM models stay nullable until then, so the dormant suite
is unaffected).

Classes covered:
* **A — identifier-as-PK** (``sessions``): PK ``(engagement_id, session_identifier)``.
* **B — surrogate-PK + UNIQUE** (``decisions``): ``id`` PK + ``UNIQUE(engagement_id, identifier)``.
* **B-special — refs**: ``UNIQUE(engagement_id, reference_identifier)`` and the
  full-edge unique prefixed with ``engagement_id``.
"""

from __future__ import annotations

import sqlite3

import pytest

_TARGET_SCHEMA = """
CREATE TABLE engagements (
    engagement_identifier TEXT PRIMARY KEY
);

-- Class A: identifier is the PK -> composite (engagement_id, session_identifier)
CREATE TABLE sessions (
    session_identifier TEXT NOT NULL,
    engagement_id TEXT NOT NULL REFERENCES engagements(engagement_identifier),
    PRIMARY KEY (engagement_id, session_identifier)
);

-- Class B: surrogate id PK + UNIQUE(engagement_id, identifier)
CREATE TABLE decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier TEXT NOT NULL,
    engagement_id TEXT NOT NULL REFERENCES engagements(engagement_identifier),
    UNIQUE (engagement_id, identifier)
);

-- Class B-special: refs has two composite uniques
CREATE TABLE refs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_identifier TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship_kind TEXT NOT NULL,
    engagement_id TEXT NOT NULL REFERENCES engagements(engagement_identifier),
    UNIQUE (engagement_id, reference_identifier),
    UNIQUE (engagement_id, source_id, target_id, relationship_kind)
);
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys=ON")
    c.executescript(_TARGET_SCHEMA)
    c.execute("INSERT INTO engagements VALUES ('ENG-001')")
    c.execute("INSERT INTO engagements VALUES ('ENG-002')")
    c.commit()
    yield c
    c.close()


def test_same_session_identifier_coexists_across_engagements(conn):
    conn.execute("INSERT INTO sessions VALUES ('SES-001', 'ENG-001')")
    conn.execute("INSERT INTO sessions VALUES ('SES-001', 'ENG-002')")  # must coexist
    conn.commit()
    n = conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE session_identifier='SES-001'"
    ).fetchone()[0]
    assert n == 2


def test_duplicate_session_identifier_within_engagement_rejected(conn):
    conn.execute("INSERT INTO sessions VALUES ('SES-001', 'ENG-001')")
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO sessions VALUES ('SES-001', 'ENG-001')")


def test_same_decision_identifier_coexists_across_engagements(conn):
    conn.execute("INSERT INTO decisions (identifier, engagement_id) VALUES ('DEC-001', 'ENG-001')")
    conn.execute("INSERT INTO decisions (identifier, engagement_id) VALUES ('DEC-001', 'ENG-002')")
    conn.commit()
    assert (
        conn.execute("SELECT COUNT(*) FROM decisions WHERE identifier='DEC-001'").fetchone()[0]
        == 2
    )


def test_duplicate_decision_identifier_within_engagement_rejected(conn):
    conn.execute("INSERT INTO decisions (identifier, engagement_id) VALUES ('DEC-001', 'ENG-001')")
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO decisions (identifier, engagement_id) VALUES ('DEC-001', 'ENG-001')"
        )


def test_same_ref_edge_coexists_across_engagements(conn):
    row = ("REF-0001", "SES-001", "SES-002", "references")
    conn.execute(
        "INSERT INTO refs (reference_identifier, source_id, target_id, relationship_kind, engagement_id)"
        " VALUES (?,?,?,?, 'ENG-001')",
        row,
    )
    conn.execute(
        "INSERT INTO refs (reference_identifier, source_id, target_id, relationship_kind, engagement_id)"
        " VALUES (?,?,?,?, 'ENG-002')",
        row,
    )  # same edge + same REF id, different engagement -> coexists
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM refs").fetchone()[0] == 2


def test_duplicate_ref_edge_within_engagement_rejected(conn):
    conn.execute(
        "INSERT INTO refs (reference_identifier, source_id, target_id, relationship_kind, engagement_id)"
        " VALUES ('REF-0001','SES-001','SES-002','references','ENG-001')"
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO refs (reference_identifier, source_id, target_id, relationship_kind, engagement_id)"
            " VALUES ('REF-0002','SES-001','SES-002','references','ENG-001')"  # same edge, same engagement
        )


def test_null_engagement_id_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO sessions VALUES ('SES-001', NULL)")


def test_unknown_engagement_fk_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO sessions VALUES ('SES-001', 'ENG-999')")
