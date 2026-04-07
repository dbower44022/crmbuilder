"""Downstream triggers for the Import Processor.

Implements L2 PRD Section 11.10 — post-commit trigger sequence:
1. Graph construction (conditional)
2. Work item completion (conditional)
3. Downstream status recalculation (via engine.complete())
4. Revision unblocking (via engine.complete())
5. Impact analysis — DEFERRED to Step 13

Per Section 11.10.3, trigger failures do not roll back the commit.
"""

from __future__ import annotations

import dataclasses
import logging
import sqlite3

from automation.importer.commit import CommitResult
from automation.workflow.engine import WorkflowEngine

logger = logging.getLogger(__name__)

# Impact analysis flag column or marker.
# Step 13 will implement actual impact analysis. Step 12 records the intent.
_IMPACT_ANALYSIS_MARKER = "IMPACT_ANALYSIS_NEEDED"


@dataclasses.dataclass
class TriggerResult:
    """Result of the trigger stage."""

    graph_constructed: bool = False
    work_item_completed: bool = False
    downstream_affected: list[int] = dataclasses.field(default_factory=list)
    impact_analysis_queued: bool = False
    errors: list[str] = dataclasses.field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


def run_triggers(
    conn: sqlite3.Connection,
    ai_session_id: int,
    commit_result: CommitResult,
    work_item_id: int,
    item_type: str,
    session_type: str,
) -> TriggerResult:
    """Run the post-commit trigger sequence.

    Per Section 11.10.2, graph construction must complete before work item
    completion. The sequence is strictly ordered.

    Per Section 11.10.3, failures here do not roll back the commit.
    All errors are captured in the TriggerResult.

    :param conn: Open client database connection.
    :param ai_session_id: The AISession.id.
    :param commit_result: The result from the commit stage.
    :param work_item_id: The WorkItem.id.
    :param item_type: The work item's item_type.
    :param session_type: 'initial', 'revision', or 'clarification'.
    :returns: TriggerResult describing what happened.
    """
    result = TriggerResult()
    engine = WorkflowEngine(conn)

    # Step 1: Graph construction (conditional)
    try:
        if item_type == "master_prd" and commit_result.import_status == "imported":
            engine.after_master_prd_import()
            result.graph_constructed = True
            logger.info("Graph expanded after master_prd import")

        elif item_type == "business_object_discovery" and commit_result.import_status == "imported":
            engine.after_business_object_discovery_import()
            result.graph_constructed = True
            logger.info("Graph expanded after business_object_discovery import")
    except Exception as exc:
        result.errors.append(f"Graph construction failed: {exc}")
        logger.error("Graph construction failed: %s", exc)
        # Per 11.10.3, continue despite failure

    # Step 2 + 3: Work item completion and downstream recalculation
    # Only for full imports (import_status == 'imported')
    # Clarification sessions don't transition status per Section 11.7.3
    if commit_result.import_status == "imported" and session_type != "clarification":
        try:
            # Ensure work item is in_progress before completing
            status = engine.get_status(work_item_id)
            if status == "in_progress":
                affected = engine.complete(work_item_id)
                result.work_item_completed = True
                result.downstream_affected = affected
                logger.info(
                    "Work item %d completed, %d downstream affected",
                    work_item_id, len(affected),
                )
            elif status == "complete":
                # Already complete (clarification case shouldn't reach here,
                # but revision re-complete is handled by engine.complete)
                pass
        except Exception as exc:
            result.errors.append(f"Work item completion failed: {exc}")
            logger.error("Work item completion failed: %s", exc)

    # Step 4: Revision unblocking is handled inside engine.complete()
    # per Section 9.8.2 — no additional action needed here.

    # Step 5: Impact analysis — DEFERRED to Step 13
    # Record that impact analysis is needed if there were updates.
    if commit_result.has_updates:
        result.impact_analysis_queued = True
        # Write a marker note on the AISession for Step 13 to pick up.
        # Step 13 will look for AISession records where impact analysis
        # has not yet been run.
        try:
            conn.execute(
                "UPDATE AISession SET notes = COALESCE(notes || ' | ', '') || ? "
                "WHERE id = ?",
                (_IMPACT_ANALYSIS_MARKER, ai_session_id),
            )
            conn.commit()
            logger.info(
                "Impact analysis queued for AISession %d (deferred to Step 13)",
                ai_session_id,
            )
        except Exception as exc:
            result.errors.append(f"Impact analysis marker failed: {exc}")
            logger.error("Failed to write impact analysis marker: %s", exc)

    return result
