"""Import review state machine — pure Python, no Qt.

Tracks the current stage, per-record acceptance state, and computes
the accepted_record_ids set for ImportProcessor.commit().
"""

from __future__ import annotations

import dataclasses
import enum
from typing import Any


class ImportStage(enum.Enum):
    """The seven stages of the import pipeline plus Done."""

    RECEIVE = "Receive"
    PARSE = "Parse"
    MAP = "Map"
    DETECT = "Detect"
    REVIEW = "Review"
    COMMIT = "Commit"
    TRIGGER = "Trigger"
    DONE = "Done"


# Display order for stages (excluding Done)
STAGE_ORDER = [
    ImportStage.RECEIVE,
    ImportStage.PARSE,
    ImportStage.MAP,
    ImportStage.DETECT,
    ImportStage.REVIEW,
    ImportStage.COMMIT,
    ImportStage.TRIGGER,
]

# Category ordering for the review stage (Section 14.5.5 / 11.4.1)
CATEGORY_ORDER = [
    "Domain",
    "Entity",
    "Persona",
    "Field",
    "FieldOption",
    "Relationship",
    "ProcessStep",
    "Requirement",
    "ProcessEntity",
    "ProcessField",
    "ProcessPersona",
    "LayoutPanel",
    "LayoutRow",
    "LayoutTab",
    "ListColumn",
    "Decision",
    "OpenIssue",
]

# Human-readable category labels
CATEGORY_LABELS: dict[str, str] = {
    "Domain": "Domains",
    "Entity": "Entities",
    "Persona": "Personas",
    "Field": "Fields",
    "FieldOption": "Field Options",
    "Relationship": "Relationships",
    "ProcessStep": "Process Steps",
    "Requirement": "Requirements",
    "ProcessEntity": "Cross-References (ProcessEntity)",
    "ProcessField": "Cross-References (ProcessField)",
    "ProcessPersona": "Cross-References (ProcessPersona)",
    "LayoutPanel": "Layout Panels",
    "LayoutRow": "Layout Rows",
    "LayoutTab": "Layout Tabs",
    "ListColumn": "List Columns",
    "Decision": "Decisions",
    "OpenIssue": "Open Issues",
}


class RecordAction(enum.Enum):
    """Per-record acceptance state."""

    ACCEPTED = "accepted"
    MODIFIED = "modified"
    REJECTED = "rejected"


@dataclasses.dataclass
class RecordState:
    """Tracks the acceptance state and optional modified values for a record."""

    source_payload_path: str
    table_name: str
    action: str  # 'create' or 'update'
    record_action: RecordAction = RecordAction.ACCEPTED
    modified_values: dict[str, Any] | None = None
    has_errors: bool = False
    dependency_count: int = 0
    batch_id: str | None = None


@dataclasses.dataclass
class ImportState:
    """The complete import state machine."""

    current_stage: ImportStage = ImportStage.RECEIVE
    completed_stages: set[ImportStage] = dataclasses.field(default_factory=set)
    records: dict[str, RecordState] = dataclasses.field(default_factory=dict)
    ai_session_id: int | None = None
    error_message: str | None = None


# ---------------------------------------------------------------------------
# State machine transitions
# ---------------------------------------------------------------------------

def advance_stage(state: ImportState, to_stage: ImportStage) -> ImportState:
    """Advance to the next stage, marking the current as completed.

    :param state: The current import state.
    :param to_stage: The target stage.
    :returns: Updated state.
    """
    state.completed_stages.add(state.current_stage)
    state.current_stage = to_stage
    state.error_message = None
    return state


def set_error(state: ImportState, message: str) -> ImportState:
    """Set an error on the current stage without advancing.

    :param state: The current import state.
    :param message: Error description.
    :returns: Updated state.
    """
    state.error_message = message
    return state


# ---------------------------------------------------------------------------
# Record state management
# ---------------------------------------------------------------------------

def init_records_from_batch(state: ImportState, batch) -> ImportState:
    """Initialize record states from a ProposedBatch.

    :param state: The current import state.
    :param batch: A ProposedBatch from ImportProcessor.map().
    :returns: Updated state with records populated.
    """
    state.records.clear()

    # Build dependency counts
    dep_counts: dict[str, int] = {}
    for rec in batch.records:
        for ref_path in rec.intra_batch_refs.values():
            dep_counts[ref_path] = dep_counts.get(ref_path, 0) + 1

    for rec in batch.records:
        state.records[rec.source_payload_path] = RecordState(
            source_payload_path=rec.source_payload_path,
            table_name=rec.table_name,
            action=rec.action,
            has_errors=rec.has_errors,
            dependency_count=dep_counts.get(rec.source_payload_path, 0),
            batch_id=rec.batch_id,
        )

    return state


def set_record_action(
    state: ImportState,
    path: str,
    action: RecordAction,
    modified_values: dict[str, Any] | None = None,
) -> ImportState:
    """Set the acceptance state for a single record.

    :param state: The current import state.
    :param path: The source_payload_path.
    :param action: The new RecordAction.
    :param modified_values: For MODIFIED, the changed field values.
    :returns: Updated state.
    """
    if path in state.records:
        state.records[path].record_action = action
        state.records[path].modified_values = modified_values
    return state


def set_category_action(
    state: ImportState,
    table_name: str,
    action: RecordAction,
) -> ImportState:
    """Set the acceptance state for all records in a category.

    :param state: The current import state.
    :param table_name: The table/category name.
    :param action: The new RecordAction.
    :returns: Updated state.
    """
    for rec in state.records.values():
        if rec.table_name == table_name:
            rec.record_action = action
            if action != RecordAction.MODIFIED:
                rec.modified_values = None
    return state


# ---------------------------------------------------------------------------
# Computed properties
# ---------------------------------------------------------------------------

def compute_accepted_record_ids(state: ImportState) -> set[str]:
    """Compute the set of source_payload_path strings for accepted/modified records.

    :param state: The current import state.
    :returns: Set of accepted paths for ImportProcessor.commit().
    """
    return {
        path
        for path, rec in state.records.items()
        if rec.record_action in (RecordAction.ACCEPTED, RecordAction.MODIFIED)
    }


def count_by_action(state: ImportState) -> dict[str, int]:
    """Count records by their action state.

    :param state: The current import state.
    :returns: Dict with keys "accepted", "modified", "rejected".
    """
    counts = {"accepted": 0, "modified": 0, "rejected": 0}
    for rec in state.records.values():
        counts[rec.record_action.value] += 1
    return counts


def get_unresolved_errors(state: ImportState) -> list[str]:
    """Get paths of accepted/modified records with error-severity conflicts.

    Per Section 11.11.1, error-severity conflicts must be resolved
    (rejected or modified) before commit.

    :param state: The current import state.
    :returns: List of source_payload_path strings with unresolved errors.
    """
    return [
        path
        for path, rec in state.records.items()
        if rec.has_errors and rec.record_action in (RecordAction.ACCEPTED, RecordAction.MODIFIED)
    ]


def get_cascade_reject_set(state: ImportState, path: str) -> list[str]:
    """Find records that depend on the given record.

    When a record is rejected, its dependents may also need to be rejected.

    :param state: The current import state.
    :param path: The source_payload_path being rejected.
    :returns: List of dependent source_payload_path strings.
    """
    # Find batch_id for the record being rejected
    rec = state.records.get(path)
    if not rec or not rec.batch_id:
        return []

    # A record depends on `path` if its intra_batch_refs point to `path`
    # Since we don't store the full ref graph in RecordState, we check
    # if any record references this one via batch_id matching
    # This is a simplified version — full implementation would need the
    # original ProposedBatch for intra_batch_refs
    return []


def get_cascade_reject_set_from_batch(batch, path: str) -> list[str]:
    """Find records that depend on the given record using the full batch.

    :param batch: The ProposedBatch with intra_batch_refs.
    :param path: The source_payload_path being rejected.
    :returns: List of dependent source_payload_path strings.
    """
    dependents = []
    for rec in batch.records:
        for ref_path in rec.intra_batch_refs.values():
            if ref_path == path:
                dependents.append(rec.source_payload_path)
                break
    return dependents


def get_records_by_category(state: ImportState) -> list[tuple[str, list[RecordState]]]:
    """Group records by table name in category order.

    Categories with no records are omitted.

    :param state: The current import state.
    :returns: List of (table_name, records) tuples in category order.
    """
    groups: dict[str, list[RecordState]] = {}
    for rec in state.records.values():
        groups.setdefault(rec.table_name, []).append(rec)

    result = []
    # First add known categories in order
    for table in CATEGORY_ORDER:
        if table in groups:
            result.append((table, groups.pop(table)))

    # Then any remaining unknown categories
    for table, recs in sorted(groups.items()):
        result.append((table, recs))

    return result
