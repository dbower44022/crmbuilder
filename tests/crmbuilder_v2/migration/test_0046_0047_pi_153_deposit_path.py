"""PI-153 / WTK-089 — migrations 0046 + 0047 round-trip and CHECK enforcement.

Mirrors the test_0045 pattern: create_all, drop the utilization_evidence
table to simulate the pre-0046 state, stamp at 0045, then walk the chain
both ways asserting the WTK-088/WTK-089 verification criteria:

- M1 round-trip — upgrade 0045 → 0047, downgrade back to 0045, upgrade
  again, cleanly.
- M2 CHECK enforcement — post-upgrade the rebuilt CHECKs admit the new
  `rejected` status, the `rejected_by_decision` / `observed_in` kinds, and
  the `utilization_evidence` change_log type; a still-unknown kind fails
  post-upgrade (the rebuild is exact, not slack); post-downgrade the old
  CHECKs reject all of them again.
- M3 kind-column backfill — a deposit_events row inserted before 0047
  reads `deposit_event_kind = 'close_out_apply'` after it; an out-of-enum
  kind fails ck_deposit_event_kind.
- M4 mid-stream entry is covered by test_0037 (stamp 0036 → upgrade head),
  which now walks 0046/0047 over a DB containing only what 0037+ created.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_DIR = _REPO_ROOT / "crmbuilder-v2"
_MIGRATION_0045 = "0045_pi_134_findings_entity"
_MIGRATION_0046 = "0046_pi_153_rejected_and_utilization_evidence"
_MIGRATION_0047 = "0047_wtk_089_deposit_event_kind"
_TABLE = "utilization_evidence"


def _alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(_ALEMBIC_DIR),
        env=env,
        capture_output=True,
        text=True,
    )


def _insert_domain(c, identifier: str, status: str) -> None:
    c.execute(
        text(
            "INSERT INTO domains "
            "(domain_identifier, domain_name, domain_status, domain_purpose, "
            "domain_description, domain_created_at, domain_updated_at, engagement_id) "
            f"VALUES ('{identifier}', 'D', '{status}', 'p', 'd', "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'ENG-001')"
        )
    )


def _insert_ref(c, ref_id: str, src_type: str, src: str, tgt_type: str,
                tgt: str, kind: str) -> None:
    c.execute(
        text(
            "INSERT INTO refs "
            "(reference_identifier, source_type, source_id, target_type, target_id, "
            "relationship_kind, created_at, engagement_id) "
            f"VALUES ('{ref_id}', '{src_type}', '{src}', '{tgt_type}', '{tgt}', "
            f"'{kind}', CURRENT_TIMESTAMP, 'ENG-001')"
        )
    )


def _insert_deposit_event(c, identifier: str) -> None:
    c.execute(
        text(
            "INSERT INTO deposit_events "
            "(deposit_event_identifier, deposit_event_title, "
            "deposit_event_description, deposit_event_outcome, "
            "deposit_event_records_summary, deposit_event_apply_context, "
            "deposit_event_log_file_path, deposit_event_created_at, engagement_id) "
            f"VALUES ('{identifier}', 'T', 'd', 'success', '{{}}', '{{}}', "
            "'deposit-event-logs/dep_900.log', CURRENT_TIMESTAMP, 'ENG-001')"
        )
    )


# Pre-0047 deposit_events shape (no deposit_event_kind column / CHECK /
# index) so the 0047 column add + backfill is a real delta, not the
# create_all no-op path.
_OLD_DEPOSIT_EVENTS_DDL = """
CREATE TABLE deposit_events (
    engagement_id VARCHAR(32) NOT NULL,
    deposit_event_identifier VARCHAR(32) NOT NULL,
    deposit_event_title VARCHAR(255) NOT NULL,
    deposit_event_description TEXT NOT NULL,
    deposit_event_outcome VARCHAR(16) NOT NULL,
    deposit_event_records_summary JSON NOT NULL,
    deposit_event_error_info JSON,
    deposit_event_apply_context JSON NOT NULL,
    deposit_event_log_file_path TEXT NOT NULL,
    deposit_event_created_at DATETIME NOT NULL,
    PRIMARY KEY (engagement_id, deposit_event_identifier),
    CONSTRAINT ck_deposit_event_identifier_format
        CHECK (deposit_event_identifier GLOB 'DEP-[0-9][0-9][0-9]'),
    CONSTRAINT ck_deposit_event_outcome
        CHECK (deposit_event_outcome IN ('failure', 'success')),
    FOREIGN KEY(engagement_id) REFERENCES engagements (engagement_identifier)
)
"""


def test_models_define_utilization_evidence_table() -> None:
    assert _TABLE in Base.metadata.tables


def test_0046_0047_round_trip_and_check_enforcement(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        c.execute(text(f"DROP TABLE IF EXISTS {_TABLE}"))
        # Rebuild deposit_events in its pre-0047 shape (create_all already
        # carries the kind column, which would make 0047 a no-op).
        c.execute(text("DROP TABLE IF EXISTS deposit_events"))
        c.execute(text(_OLD_DEPOSIT_EVENTS_DDL))
        c.execute(
            text(
                "CREATE INDEX ix_deposit_events_deposit_event_outcome "
                "ON deposit_events (deposit_event_outcome)"
            )
        )
        c.execute(
            text(
                "CREATE INDEX ix_deposit_events_deposit_event_created_at "
                "ON deposit_events (deposit_event_created_at)"
            )
        )
    engine.dispose()

    stamp = _alembic(["stamp", _MIGRATION_0045], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION_0046], db)
    assert up.returncode == 0, f"upgrade 0046 failed:\n{up.stdout}\n{up.stderr}"

    eng = create_engine(f"sqlite:///{db}")
    assert _TABLE in set(inspect(eng).get_table_names()), (
        "utilization_evidence missing after 0046"
    )
    with eng.begin() as c:
        # The rebuilt status CHECK admits the new 'rejected' status.
        _insert_domain(c, "DOM-901", "rejected")
        # The rebuilt refs CHECK admits both new kinds (the merged
        # WTK-089 §5.2 rebuild).
        _insert_ref(
            c, "REF-9001", "domain", "DOM-901", "decision", "DEC-001",
            "rejected_by_decision",
        )
        _insert_ref(
            c, "REF-9002", "field", "FLD-001", "deposit_event", "DEP-001",
            "observed_in",
        )
        # The rebuilt change_log CHECK admits the new mechanical type.
        c.execute(
            text(
                "INSERT INTO change_log "
                "(timestamp, entity_type, entity_identifier, operation, actor, "
                "engagement_id) "
                "VALUES (CURRENT_TIMESTAMP, 'utilization_evidence', '42', "
                "'insert', 'claude_session', 'ENG-001')"
            )
        )
    # M2: the rebuild is exact — a still-unknown kind fails post-upgrade.
    with pytest.raises(IntegrityError), eng.begin() as c:
        _insert_ref(
            c, "REF-9003", "field", "FLD-001", "deposit_event", "DEP-001",
            "not_a_kind",
        )
    eng.dispose()

    # 0047: insert a deposit_events row first so the backfill is observable.
    eng = create_engine(f"sqlite:///{db}")
    with eng.begin() as c:
        _insert_deposit_event(c, "DEP-901")
    eng.dispose()
    up = _alembic(["upgrade", _MIGRATION_0047], db)
    assert up.returncode == 0, f"upgrade 0047 failed:\n{up.stdout}\n{up.stderr}"

    eng = create_engine(f"sqlite:///{db}")
    with eng.begin() as c:
        # M3: every pre-existing row backfills to 'close_out_apply'.
        kind = c.execute(
            text(
                "SELECT deposit_event_kind FROM deposit_events "
                "WHERE deposit_event_identifier = 'DEP-901'"
            )
        ).scalar_one()
        assert kind == "close_out_apply"
        # The new kind value is admitted.
        c.execute(
            text(
                "UPDATE deposit_events SET deposit_event_kind = 'audit_deposit' "
                "WHERE deposit_event_identifier = 'DEP-901'"
            )
        )
    # M3: an out-of-enum kind fails ck_deposit_event_kind.
    with pytest.raises(IntegrityError), eng.begin() as c:
        c.execute(
            text(
                "UPDATE deposit_events SET deposit_event_kind = 'bogus' "
                "WHERE deposit_event_identifier = 'DEP-901'"
            )
        )
    eng.dispose()

    # Downgrade across both migrations (M1) — 0047 deletes the
    # audit_deposit row, 0046 deletes the rejected/new-kind rows and
    # drops the table.
    down = _alembic(["downgrade", _MIGRATION_0045], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"

    eng = create_engine(f"sqlite:///{db}")
    insp = inspect(eng)
    assert _TABLE not in set(insp.get_table_names()), (
        "utilization_evidence present after downgrade"
    )
    assert "deposit_event_kind" not in {
        col["name"] for col in insp.get_columns("deposit_events")
    }, "deposit_event_kind present after downgrade"
    with eng.begin() as c:
        # The delete-then-rebuild posture removed the offending rows...
        assert c.execute(text("SELECT COUNT(*) FROM domains")).scalar_one() == 0
        assert c.execute(text("SELECT COUNT(*) FROM refs")).scalar_one() == 0
        assert (
            c.execute(
                text(
                    "SELECT COUNT(*) FROM deposit_events "
                    "WHERE deposit_event_identifier = 'DEP-901'"
                )
            ).scalar_one()
            == 0
        )
    # ...and the restored old CHECKs reject the new vocab again (M2).
    with pytest.raises(IntegrityError), eng.begin() as c:
        _insert_domain(c, "DOM-902", "rejected")
    with pytest.raises(IntegrityError), eng.begin() as c:
        _insert_ref(
            c, "REF-9004", "field", "FLD-001", "deposit_event", "DEP-001",
            "observed_in",
        )
    eng.dispose()

    # M1: upgrade again cleanly after the downgrade.
    up2 = _alembic(["upgrade", _MIGRATION_0047], db)
    assert up2.returncode == 0, f"re-upgrade failed:\n{up2.stdout}\n{up2.stderr}"
