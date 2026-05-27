"""PI-073 Phase F — data migration of legacy session/conversation records.

Reads from ``legacy_conversations`` and ``legacy_sessions`` (preserved by
the Phase A schema migration at revision 0020) and populates the new
``sessions`` and ``conversations`` tables per the mapping in
``session-v2.md`` §6 and ``conversation-v2.md`` §6.

Field mapping:

* Old ``conversations`` (v0.7 lifecycle wrapper) → new ``sessions``.
  CONV-NNN identifier retained as session identifier (accepted
  asymmetry per the migration spec). Default medium=chat, default
  medium_metadata={"chat_platform": "claude_ai_sandbox"}.

* Old ``sessions`` (DEC-013 append-only record) → new ``conversations``.
  SES-NNN identifier retained as conversation identifier (accepted
  asymmetry). Lifecycle inferred from old status:
  Complete → complete, In Progress → in_flight.

Reference-edge retargeting:

* Edges with source/target type='conversation' AND id matching CONV-NNN
  flip to type='session' (those rows are now sessions).
* Edges with source/target type='session' AND id matching SES-NNN flip
  to type='conversation' (those rows are now conversations).
* Relationship-kind renames:
    conversation_belongs_to_workstream    → session_belongs_to_workstream
    conversation_opens_against_work_ticket → session_opens_against_work_ticket
    conversation_succeeds_conversation    → session_follows_from
    conversation_records_session          → conversation_belongs_to_session
                                            (direction REVERSED — the old
                                            CONV row records its session;
                                            new SES row belongs to its session)
* ``close_out_payload_produced_by_conversation`` keeps its kind but its
  conversation target was the v0.7 CONV row (now a session); the
  kind name is misleading post-migration. v0.7 left it because Phase F
  was deferred; we leave it for now and address in Phase G doc updates.

Idempotency: the script verifies new tables are empty before inserting;
re-running on a partially-migrated DB is a no-op with a warning.

Usage:
    CRMBUILDER_V2_DB_PATH=path/to/db.db python scripts/migrate_pi_073_data.py [--dry-run]

The script writes a migration audit report to
``PRDs/product/crmbuilder-v2/pi-073-migration-audit.md`` listing the
old → new mapping for every row and edge.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


# Status mapping for old conversations (v0.7) → new sessions
_CONV_STATUS_MAP = {
    "planned": "planned",
    "kickoff_drafted": "planned",  # collapses into planned per session-v2.md §6
    "ready": "planned",            # ditto
    "in_flight": "in_flight",
    "complete": "complete",
    "cancelled": "cancelled",
    "superseded": "superseded",
}

# Status mapping for old sessions (DEC-013) → new conversations
_SESS_STATUS_MAP = {
    "Complete": "complete",
    "In Progress": "in_flight",
}

# Relationship-kind rename mapping (post-migration)
_KIND_RENAMES = {
    "conversation_belongs_to_workstream": "session_belongs_to_workstream",
    "conversation_opens_against_work_ticket": "session_opens_against_work_ticket",
    "conversation_succeeds_conversation": "session_follows_from",
    # conversation_records_session handled separately because the direction
    # is reversed (old: conv→sess; new: sess→conv as conversation_belongs_to_session)
}


def _row_to_dict(cursor: sqlite3.Cursor, row: tuple) -> dict:
    return {col[0]: val for col, val in zip(cursor.description, row)}


def verify_state(conn: sqlite3.Connection) -> tuple[int, int]:
    """Confirm DB is at the right alembic head and legacy tables present."""
    head = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    if head != "0020_pi_073_session_conversation_redesign":
        raise SystemExit(
            f"Expected alembic head 0020_pi_073_*, got {head}. "
            f"Run 'alembic upgrade head' first."
        )
    tables = {
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if "legacy_conversations" not in tables or "legacy_sessions" not in tables:
        raise SystemExit(
            "legacy_conversations / legacy_sessions tables not present. "
            "Phase A migration did not run, or Phase F already dropped them."
        )
    sess_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    conv_count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    if sess_count or conv_count:
        raise SystemExit(
            f"New tables non-empty (sessions={sess_count}, "
            f"conversations={conv_count}). Run drop-and-rerun manually if you "
            f"want to redo the migration."
        )
    legacy_conv_count = conn.execute(
        "SELECT COUNT(*) FROM legacy_conversations"
    ).fetchone()[0]
    legacy_sess_count = conn.execute(
        "SELECT COUNT(*) FROM legacy_sessions"
    ).fetchone()[0]
    return legacy_conv_count, legacy_sess_count


def migrate_conversations_to_sessions(conn: sqlite3.Connection) -> list[dict]:
    """Read legacy_conversations, write to new sessions table.

    Returns the list of row mappings for the audit report.
    """
    cur = conn.execute("SELECT * FROM legacy_conversations ORDER BY conversation_identifier")
    audit: list[dict] = []
    for row in cur.fetchall():
        r = _row_to_dict(cur, row)
        # Build session_description as purpose + description (purpose first,
        # then a blank line, then description).
        parts = []
        if r.get("conversation_purpose"):
            parts.append(r["conversation_purpose"])
        if r.get("conversation_description"):
            parts.append(r["conversation_description"])
        description = "\n\n".join(parts) if parts else "(no description carried over from legacy schema)"

        new_status = _CONV_STATUS_MAP.get(
            r["conversation_status"], "complete"
        )

        body = {
            "session_identifier": r["conversation_identifier"],
            "session_title": r["conversation_title"],
            "session_description": description,
            "session_notes": r.get("conversation_notes"),
            "session_status": new_status,
            "session_medium": "chat",
            "session_medium_metadata": json.dumps(
                {"chat_platform": "claude_ai_sandbox"}
            ),
            "session_participants": json.dumps([]),
            "session_created_at": r["conversation_created_at"],
            "session_updated_at": r["conversation_updated_at"],
            "session_deleted_at": r.get("conversation_deleted_at"),
            # Lifecycle timestamps — collapse old states into the new shape.
            # session_in_flight_at gets the started_at (or any of the
            # earlier planning timestamps as best-fit).
            "session_in_flight_at": r.get("conversation_started_at")
                or r.get("conversation_ready_at")
                or r.get("conversation_kickoff_drafted_at"),
            "session_completed_at": r.get("conversation_completed_at"),
            "session_cancelled_at": r.get("conversation_cancelled_at"),
            "session_superseded_at": r.get("conversation_superseded_at"),
            # session_started_at, session_ended_at, session_scheduled_for,
            # session_not_started_at have no direct legacy parallel; leave null.
        }
        cols = ", ".join(body.keys())
        placeholders = ", ".join(["?"] * len(body))
        conn.execute(
            f"INSERT INTO sessions ({cols}) VALUES ({placeholders})",
            list(body.values()),
        )
        audit.append({
            "legacy_kind": "conversation",
            "legacy_id": r["conversation_identifier"],
            "new_kind": "session",
            "new_id": r["conversation_identifier"],
            "legacy_status": r["conversation_status"],
            "new_status": new_status,
        })
    return audit


def migrate_sessions_to_conversations(conn: sqlite3.Connection) -> list[dict]:
    """Read legacy_sessions, write to new conversations table."""
    cur = conn.execute("SELECT * FROM legacy_sessions ORDER BY identifier")
    audit: list[dict] = []
    for row in cur.fetchall():
        r = _row_to_dict(cur, row)
        # Map old legacy session fields:
        #   identifier → conversation_identifier (SES-NNN retained)
        #   title → conversation_title
        #   conversation_reference → conversation_purpose
        #     (was the "descriptive text identifying the conversation by its
        #      outputs" per the v0.3 schema docs — closest to "purpose")
        #   topics_covered → conversation_description
        #   summary → conversation_summary
        #   artifacts_produced + in_flight_at_end + session_date → conversation_notes
        notes_parts = []
        if r.get("session_date"):
            notes_parts.append(f"Session date (legacy): {r['session_date']}")
        if r.get("artifacts_produced"):
            notes_parts.append(f"Artifacts produced (legacy):\n{r['artifacts_produced']}")
        if r.get("in_flight_at_end"):
            notes_parts.append(f"In-flight at end (legacy):\n{r['in_flight_at_end']}")
        notes = "\n\n".join(notes_parts) if notes_parts else None

        new_status = _SESS_STATUS_MAP.get(r["status"], "complete")
        completed_at = r["created_at"] if new_status == "complete" else None

        body = {
            "conversation_identifier": r["identifier"],
            "conversation_title": r["title"],
            "conversation_purpose": r.get("conversation_reference")
                or "(no purpose recorded under legacy schema)",
            "conversation_description": r.get("topics_covered")
                or "(no description recorded under legacy schema)",
            "conversation_summary": r.get("summary"),
            "conversation_notes": notes,
            "conversation_status": new_status,
            "conversation_created_at": r["created_at"],
            "conversation_updated_at": r["created_at"],
            "conversation_completed_at": completed_at,
            "conversation_in_flight_at": r["created_at"] if new_status == "in_flight" else None,
            # cancelled_at, not_started_at, superseded_at all null — old DEC-013
            # sessions only had Complete or In Progress
        }
        cols = ", ".join(body.keys())
        placeholders = ", ".join(["?"] * len(body))
        conn.execute(
            f"INSERT INTO conversations ({cols}) VALUES ({placeholders})",
            list(body.values()),
        )
        audit.append({
            "legacy_kind": "session",
            "legacy_id": r["identifier"],
            "new_kind": "conversation",
            "new_id": r["identifier"],
            "legacy_status": r["status"],
            "new_status": new_status,
        })
    return audit


def retarget_reference_edges(conn: sqlite3.Connection) -> dict:
    """Retype source_type / target_type on refs, and rename kinds.

    The CONV-NNN-prefixed rows are now sessions; the SES-NNN-prefixed rows
    are now conversations. We flip source/target type accordingly. Kind
    renames follow the table at module top.

    For ``conversation_records_session`` (66 rows) the direction reverses:
    old (conversation CONV-NNN → session SES-NNN), new (conversation
    SES-NNN → session CONV-NNN) with relationship_kind
    ``conversation_belongs_to_session``. We swap source/target columns
    for those rows and update the kind.
    """
    stats = {
        "source_type_flipped_conv_to_sess": 0,
        "source_type_flipped_sess_to_conv": 0,
        "target_type_flipped_conv_to_sess": 0,
        "target_type_flipped_sess_to_conv": 0,
        "kind_renames_session_belongs_to_workstream": 0,
        "kind_renames_session_opens_against_work_ticket": 0,
        "kind_renames_session_follows_from": 0,
        "records_session_reversed": 0,
    }

    # The conversation_records_session reversal must happen FIRST because
    # we need both source/target to still be the old types ('conversation'
    # source CONV-NNN, 'session' target SES-NNN) to identify the rows.
    # After reversal: source='conversation' SES-NNN, target='session'
    # CONV-NNN, relationship='conversation_belongs_to_session'.
    crs_rows = conn.execute("""
        SELECT id, source_id, target_id FROM refs
        WHERE relationship_kind = 'conversation_records_session'
    """).fetchall()
    for row_id, src_id, tgt_id in crs_rows:
        # Swap source/target. source becomes the SES-NNN (now conversation),
        # target becomes the CONV-NNN (now session).
        conn.execute("""
            UPDATE refs
            SET source_type='conversation',
                source_id=?,
                target_type='session',
                target_id=?,
                relationship_kind='conversation_belongs_to_session'
            WHERE id=?
        """, (tgt_id, src_id, row_id))
        stats["records_session_reversed"] += 1

    # Now flip source_type='conversation' AND source_id LIKE 'CONV-%'
    # → source_type='session'. These are the legacy CONV rows that are
    # now sessions.
    r = conn.execute("""
        UPDATE refs SET source_type='session'
        WHERE source_type='conversation' AND source_id LIKE 'CONV-%'
    """)
    stats["source_type_flipped_conv_to_sess"] = r.rowcount

    # Flip source_type='session' AND source_id LIKE 'SES-%' → 'conversation'.
    r = conn.execute("""
        UPDATE refs SET source_type='conversation'
        WHERE source_type='session' AND source_id LIKE 'SES-%'
    """)
    stats["source_type_flipped_sess_to_conv"] = r.rowcount

    # Symmetric for targets.
    r = conn.execute("""
        UPDATE refs SET target_type='session'
        WHERE target_type='conversation' AND target_id LIKE 'CONV-%'
    """)
    stats["target_type_flipped_conv_to_sess"] = r.rowcount

    r = conn.execute("""
        UPDATE refs SET target_type='conversation'
        WHERE target_type='session' AND target_id LIKE 'SES-%'
    """)
    stats["target_type_flipped_sess_to_conv"] = r.rowcount

    # Kind renames (source_type already flipped above).
    for old_kind, new_kind in _KIND_RENAMES.items():
        r = conn.execute(
            "UPDATE refs SET relationship_kind=? WHERE relationship_kind=?",
            (new_kind, old_kind),
        )
        key = f"kind_renames_{new_kind}"
        stats[key] = r.rowcount

    return stats


def write_audit_report(
    audit_sessions: list[dict],
    audit_conversations: list[dict],
    refs_stats: dict,
    repo_root: Path,
) -> Path:
    """Write the migration audit report to PRDs/product/crmbuilder-v2/."""
    report_path = (
        repo_root
        / "PRDs"
        / "product"
        / "crmbuilder-v2"
        / "pi-073-migration-audit.md"
    )
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = []
    lines.append("# PI-073 Phase F — Data Migration Audit Report")
    lines.append("")
    lines.append(f"**Generated:** {now}")
    lines.append(f"**Phase:** F (data migration)")
    lines.append(f"**Source DB:** branch isolation copy at `crmbuilder-v2/data/branch-pi-073/CRMBUILDER.db`")
    lines.append("")
    lines.append("## Row counts")
    lines.append("")
    lines.append(f"- legacy_conversations → new sessions: **{len(audit_sessions)}** rows migrated")
    lines.append(f"- legacy_sessions → new conversations: **{len(audit_conversations)}** rows migrated")
    lines.append("")
    lines.append("## Reference-edge retargeting")
    lines.append("")
    for k, v in refs_stats.items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append("## legacy_conversations → sessions (CONV-NNN identifiers retained)")
    lines.append("")
    lines.append("| Legacy identifier | New identifier | Legacy status | New status |")
    lines.append("|---|---|---|---|")
    for a in audit_sessions:
        lines.append(
            f"| {a['legacy_id']} | {a['new_id']} | "
            f"{a['legacy_status']} | {a['new_status']} |"
        )
    lines.append("")
    lines.append("## legacy_sessions → conversations (SES-NNN identifiers retained)")
    lines.append("")
    lines.append("| Legacy identifier | New identifier | Legacy status | New status |")
    lines.append("|---|---|---|---|")
    for a in audit_conversations:
        lines.append(
            f"| {a['legacy_id']} | {a['new_id']} | "
            f"{a['legacy_status']} | {a['new_status']} |"
        )
    report_path.write_text("\n".join(lines) + "\n")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="PI-073 Phase F data migration")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run inside a transaction but rollback at the end (no commit)."
    )
    args = parser.parse_args()

    db_path = os.environ.get("CRMBUILDER_V2_DB_PATH")
    if not db_path:
        print("Set CRMBUILDER_V2_DB_PATH to the target DB.", file=sys.stderr)
        return 1
    db_path = Path(db_path).resolve()
    if not db_path.exists():
        print(f"DB not found: {db_path}", file=sys.stderr)
        return 1

    repo_root = Path(__file__).resolve().parents[2]

    print(f"=== PI-073 Phase F data migration ===")
    print(f"DB: {db_path}")
    print(f"Dry run: {args.dry_run}")
    print()

    conn = sqlite3.connect(db_path)
    conn.execute("BEGIN IMMEDIATE")
    try:
        legacy_conv_count, legacy_sess_count = verify_state(conn)
        print(f"To migrate: {legacy_conv_count} legacy conversations + "
              f"{legacy_sess_count} legacy sessions")
        print()

        print("Step 1: legacy_conversations → new sessions...")
        audit_sessions = migrate_conversations_to_sessions(conn)
        print(f"  inserted {len(audit_sessions)} sessions")

        print("Step 2: legacy_sessions → new conversations...")
        audit_conversations = migrate_sessions_to_conversations(conn)
        print(f"  inserted {len(audit_conversations)} conversations")

        print("Step 3: retargeting reference edges...")
        refs_stats = retarget_reference_edges(conn)
        for k, v in refs_stats.items():
            print(f"  {k}: {v}")

        print()
        print("Step 4: writing audit report...")
        report_path = write_audit_report(
            audit_sessions, audit_conversations, refs_stats, repo_root
        )
        print(f"  wrote {report_path.relative_to(repo_root)}")

        if args.dry_run:
            conn.execute("ROLLBACK")
            print()
            print("Dry run — rolled back. Re-run without --dry-run to commit.")
        else:
            conn.execute("COMMIT")
            print()
            print("✓ Phase F migration complete.")
    except Exception as exc:
        conn.execute("ROLLBACK")
        print(f"\n✗ Migration failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
