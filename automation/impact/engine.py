"""Impact Analysis Engine — public API.

Implements L2 PRD Section 12 — the ImpactAnalysisEngine class bundles
cross-reference queries, ChangeImpact creation, deduplication, batch
processing, work item mapping, and staleness detection.

The engine has two modes:
- Post-commit analysis: runs after AI session imports (Section 12.1).
- Pre-commit analysis: runs before direct implementor edits (Section 12.5).

The engine never modifies work items. Per Section 12.1, it surfaces
information and the implementor decides how to act.
"""

from __future__ import annotations

import dataclasses
import logging
import sqlite3

from automation.impact.batch import process_batch
from automation.impact.precommit import ProposedImpact, analyze_proposed_change
from automation.impact.staleness import StaleWorkItem, get_stale_work_items
from automation.impact.work_item_mapping import (
    AffectedWorkItem,
    get_affected_work_items,
)

logger = logging.getLogger(__name__)

# Marker written by Step 12 Import Processor (automation/importer/triggers.py)
_IMPACT_ANALYSIS_MARKER = "IMPACT_ANALYSIS_NEEDED"


@dataclasses.dataclass
class AnalysisResult:
    """Summary of impact analysis for a single AISession."""

    ai_session_id: int
    change_log_count: int
    impact_count: int
    requires_review_count: int
    informational_count: int


class ImpactAnalysisEngine:
    """Public API for Impact Analysis.

    Bundles cross-reference queries, ChangeImpact creation, deduplication,
    batch processing, work item mapping, and staleness detection.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # Post-commit analysis
    # ------------------------------------------------------------------

    def analyze_session(self, ai_session_id: int) -> AnalysisResult:
        """Analyze ChangeLog entries from a single AISession.

        Reads all ChangeLog rows for this session, traces downstream
        effects, deduplicates, and writes ChangeImpact rows.

        :param ai_session_id: The AISession.id to analyze.
        :returns: Summary of what was created.
        """
        # Get ChangeLog entries for this session (updates and deletes only)
        cl_rows = self._conn.execute(
            "SELECT id FROM ChangeLog "
            "WHERE session_id = ? AND change_type IN ('update', 'delete')",
            (ai_session_id,),
        ).fetchall()

        cl_ids = [r[0] for r in cl_rows]

        if not cl_ids:
            logger.info(
                "No update/delete ChangeLog entries for session %d",
                ai_session_id,
            )
            return AnalysisResult(
                ai_session_id=ai_session_id,
                change_log_count=0,
                impact_count=0,
                requires_review_count=0,
                informational_count=0,
            )

        deduped = process_batch(self._conn, cl_ids)

        review_count = sum(1 for c in deduped if c.requires_review)
        info_count = sum(1 for c in deduped if not c.requires_review)

        logger.info(
            "Session %d: %d ChangeLog entries → %d impacts "
            "(%d review, %d informational)",
            ai_session_id,
            len(cl_ids),
            len(deduped),
            review_count,
            info_count,
        )

        return AnalysisResult(
            ai_session_id=ai_session_id,
            change_log_count=len(cl_ids),
            impact_count=len(deduped),
            requires_review_count=review_count,
            informational_count=info_count,
        )

    def analyze_pending_sessions(self) -> list[AnalysisResult]:
        """Find all AISessions with the IMPACT_ANALYSIS_NEEDED marker,
        run analysis on each, and clear the marker after success.

        The marker is appended to AISession.notes with ' | ' separator.
        Removal preserves any other notes content.

        :returns: List of AnalysisResult, one per processed session.
        """
        # Find sessions with the marker
        rows = self._conn.execute(
            "SELECT id, notes FROM AISession WHERE notes LIKE ?",
            (f"%{_IMPACT_ANALYSIS_MARKER}%",),
        ).fetchall()

        if not rows:
            logger.info("No pending impact analysis sessions found")
            return []

        results: list[AnalysisResult] = []

        for session_id, notes in rows:
            logger.info("Processing pending session %d", session_id)

            result = self.analyze_session(session_id)
            results.append(result)

            # Clear the marker from notes, preserving other content
            cleaned = _remove_marker(notes)
            self._conn.execute(
                "UPDATE AISession SET notes = ? WHERE id = ?",
                (cleaned, session_id),
            )
            self._conn.commit()

            logger.info(
                "Cleared marker for session %d, notes now: %r",
                session_id,
                cleaned,
            )

        return results

    # ------------------------------------------------------------------
    # Pre-commit analysis
    # ------------------------------------------------------------------

    def analyze_proposed_change(
        self,
        table_name: str,
        record_id: int,
        change_type: str,
        new_values: dict | None = None,
        rationale: str | None = None,
    ) -> list[ProposedImpact]:
        """Analyze a proposed direct edit before commit.

        Returns in-memory impact objects without writing them. The caller
        (future UI) presents them to the implementor for confirmation.

        :param table_name: Table of the record being modified.
        :param record_id: ID of the record being modified.
        :param change_type: 'update' or 'delete'.
        :param new_values: For updates, dict of field_name -> new_value.
        :param rationale: Implementor's rationale (accepted, not enforced).
        :returns: List of ProposedImpact objects (not persisted).
        """
        return analyze_proposed_change(
            self._conn,
            table_name,
            record_id,
            change_type,
            new_values=new_values,
            rationale=rationale,
        )

    # ------------------------------------------------------------------
    # Work item mapping
    # ------------------------------------------------------------------

    def get_affected_work_items(
        self,
        change_impact_ids: list[int],
    ) -> list[AffectedWorkItem]:
        """Group ChangeImpact records by their owning work item.

        :param change_impact_ids: ChangeImpact.id values to map.
        :returns: List of AffectedWorkItem, one per unique work item.
        """
        return get_affected_work_items(self._conn, change_impact_ids)

    # ------------------------------------------------------------------
    # Staleness detection
    # ------------------------------------------------------------------

    def get_stale_work_items(self) -> list[StaleWorkItem]:
        """Return all work items whose documents are stale.

        A document is stale when a ChangeLog entry affects a record owned
        by that work item and changed_at > completed_at.

        :returns: List of StaleWorkItem records.
        """
        return get_stale_work_items(self._conn)


def _remove_marker(notes: str | None) -> str | None:
    """Remove the IMPACT_ANALYSIS_NEEDED marker from notes text.

    The marker is appended with ' | ' separator. Handles:
    - Marker alone: returns None
    - Marker at end: "other notes | IMPACT_ANALYSIS_NEEDED" → "other notes"
    - Marker at start: "IMPACT_ANALYSIS_NEEDED | other notes" → "other notes"
    - Marker in middle: "a | IMPACT_ANALYSIS_NEEDED | b" → "a | b"
    """
    if notes is None:
        return None

    if notes == _IMPACT_ANALYSIS_MARKER:
        return None

    # Split on ' | ', remove marker segments, rejoin
    parts = [p.strip() for p in notes.split(" | ")]
    remaining = [p for p in parts if p != _IMPACT_ANALYSIS_MARKER]

    if not remaining:
        return None

    return " | ".join(remaining)
