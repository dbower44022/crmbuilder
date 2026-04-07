"""Proposed record dataclasses for the Import Processor.

Defines the in-memory representation of records after mapping (Stage 3)
but before commit (Stage 6). Per L2 PRD Section 11.3.
"""

from __future__ import annotations

import dataclasses
from typing import Any


@dataclasses.dataclass
class Conflict:
    """A conflict detected on a proposed record."""

    severity: str  # 'error', 'warning', 'info'
    conflict_type: str  # 'identifier_uniqueness', 'type_mismatch', etc.
    message: str
    field_name: str | None = None

    def __post_init__(self) -> None:
        if self.severity not in ("error", "warning", "info"):
            raise ValueError(f"Invalid conflict severity: {self.severity}")


@dataclasses.dataclass
class ProposedRecord:
    """A single proposed database record.

    :param table_name: Target table (e.g., 'Domain', 'Entity').
    :param action: 'create' or 'update'.
    :param target_id: For updates, the existing record's id. None for creates.
    :param values: Dict of column_name -> value to write.
    :param source_payload_path: JSON path for error messages
        (e.g., 'payload.domains[0]').
    :param conflicts: List of detected conflicts (populated in Stage 4).
    :param intra_batch_refs: Dict of column_name -> source_payload_path for
        references to other records within this same batch. These are resolved
        to real ids during commit.
    :param batch_id: Unique identifier within the batch for intra-batch
        reference tracking.
    """

    table_name: str
    action: str  # 'create' or 'update'
    target_id: int | None
    values: dict[str, Any]
    source_payload_path: str
    conflicts: list[Conflict] = dataclasses.field(default_factory=list)
    intra_batch_refs: dict[str, str] = dataclasses.field(default_factory=dict)
    batch_id: str | None = None

    def __post_init__(self) -> None:
        if self.action not in ("create", "update"):
            raise ValueError(f"Invalid action: {self.action}")
        if self.action == "update" and self.target_id is None:
            raise ValueError("Update records must have a target_id")

    @property
    def has_errors(self) -> bool:
        """Return True if any conflict is severity='error'."""
        return any(c.severity == "error" for c in self.conflicts)

    @property
    def identifier_value(self) -> str | None:
        """Return the identifier/code value if present."""
        for key in ("code", "identifier"):
            if key in self.values:
                return self.values[key]
        return None


@dataclasses.dataclass
class ProposedBatch:
    """A batch of proposed records from a single import.

    :param records: All proposed records in this batch.
    :param ai_session_id: The AISession.id this batch belongs to.
    :param work_item_id: The WorkItem.id this batch is for.
    :param session_type: 'initial', 'revision', or 'clarification'.
    """

    records: list[ProposedRecord]
    ai_session_id: int
    work_item_id: int
    session_type: str

    @property
    def has_errors(self) -> bool:
        """Return True if any record has error-severity conflicts."""
        return any(r.has_errors for r in self.records)

    @property
    def error_count(self) -> int:
        """Count of records with error-severity conflicts."""
        return sum(1 for r in self.records if r.has_errors)

    def records_by_table(self) -> dict[str, list[ProposedRecord]]:
        """Group records by table name."""
        result: dict[str, list[ProposedRecord]] = {}
        for rec in self.records:
            result.setdefault(rec.table_name, []).append(rec)
        return result

    def find_by_batch_id(self, batch_id: str) -> ProposedRecord | None:
        """Find a record by its batch_id."""
        for rec in self.records:
            if rec.batch_id == batch_id:
                return rec
        return None
