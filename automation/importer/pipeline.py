"""ImportProcessor — public API for the CRM Builder Import Processor.

Implements the seven-stage pipeline from L2 PRD Section 11.1:
Receive → Parse → Map → Detect → Review → Commit → Trigger

Like the PromptGenerator, accepts both client and optional master connections.
"""

from __future__ import annotations

import dataclasses
import json
import sqlite3

from automation.db.connection import transaction
from automation.importer.commit import CommitResult, commit_batch
from automation.importer.conflicts import detect_conflicts
from automation.importer.mappers import map_payload
from automation.importer.parser import parse_and_validate
from automation.importer.proposed import ProposedBatch
from automation.importer.triggers import TriggerResult, run_triggers
from automation.prompts.output_format import PROMPTABLE_ITEM_TYPES


@dataclasses.dataclass
class ImportResult:
    """Result of a full end-to-end import."""

    ai_session_id: int
    envelope: dict
    batch: ProposedBatch
    commit_result: CommitResult
    trigger_result: TriggerResult


class ImportProcessor:
    """Public API for the Import Processor.

    Supports both staged-interactive flow (individual stage calls) and
    run-all flow (run_full_import convenience method).
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        master_conn: sqlite3.Connection | None = None,
    ) -> None:
        """Initialize with database connections.

        :param conn: Open client database connection.
        :param master_conn: Optional master database connection, needed for
            work item types that update Client data (master_prd, crm_selection).
        """
        self._conn = conn
        self._master_conn = master_conn

    def receive(self, work_item_id: int, raw_text: str) -> int:
        """Stage 1: Store raw_output on the pending AISession.

        Finds the most recent pending AISession for this work item and
        updates it with the raw text.

        :param work_item_id: The WorkItem.id.
        :param raw_text: The raw pasted text from the AI session.
        :returns: The AISession.id.
        :raises ValueError: If no pending AISession exists for this work item.
        """
        if not raw_text or not raw_text.strip():
            raise ValueError("Raw text is empty")

        # Find the most recent pending session
        row = self._conn.execute(
            "SELECT id FROM AISession "
            "WHERE work_item_id = ? AND import_status = 'pending' "
            "ORDER BY id DESC LIMIT 1",
            (work_item_id,),
        ).fetchone()

        if row is None:
            raise ValueError(
                f"No pending AISession exists for work item {work_item_id}. "
                "Generate a prompt first (Step 11)."
            )

        ai_session_id = row[0]

        with transaction(self._conn):
            self._conn.execute(
                "UPDATE AISession SET raw_output = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (raw_text, ai_session_id),
            )

        return ai_session_id

    def parse(self, ai_session_id: int) -> dict:
        """Stage 2: Parse and validate envelope and payload structure.

        Reads raw_output from the AISession, parses it, validates against
        the work item's expected type and id.

        :param ai_session_id: The AISession.id (from receive()).
        :returns: The parsed and validated envelope dict.
        :raises ParserError: On any validation failure.
        :raises ValueError: If the AISession or work item is not found.
        """
        # Fetch AISession and work item info
        row = self._conn.execute(
            "SELECT a.raw_output, a.work_item_id, a.session_type, "
            "w.item_type "
            "FROM AISession a "
            "JOIN WorkItem w ON w.id = a.work_item_id "
            "WHERE a.id = ?",
            (ai_session_id,),
        ).fetchone()

        if row is None:
            raise ValueError(f"AISession {ai_session_id} not found")

        raw_output, work_item_id, session_type, item_type = row

        if not raw_output:
            raise ValueError(
                f"AISession {ai_session_id} has no raw_output. "
                "Call receive() first."
            )

        if item_type not in PROMPTABLE_ITEM_TYPES:
            raise ValueError(
                f"Work item type '{item_type}' is not importable"
            )

        # Parse and validate
        envelope = parse_and_validate(
            raw_output, item_type, work_item_id, session_type,
        )

        # Store structured_output
        with transaction(self._conn):
            self._conn.execute(
                "UPDATE AISession SET structured_output = ?, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(envelope), ai_session_id),
            )

        return envelope

    def map(self, ai_session_id: int) -> ProposedBatch:
        """Stage 3: Apply type-specific mapping rules.

        Reads the structured_output from the AISession and produces a
        ProposedBatch with all proposed records.

        :param ai_session_id: The AISession.id.
        :returns: A ProposedBatch with all proposed records.
        :raises ValueError: If structured_output is not available.
        """
        row = self._conn.execute(
            "SELECT a.structured_output, a.work_item_id, a.session_type, "
            "w.item_type, w.domain_id, w.entity_id, w.process_id "
            "FROM AISession a "
            "JOIN WorkItem w ON w.id = a.work_item_id "
            "WHERE a.id = ?",
            (ai_session_id,),
        ).fetchone()

        if row is None:
            raise ValueError(f"AISession {ai_session_id} not found")

        structured_output, work_item_id, session_type, item_type, \
            domain_id, entity_id, process_id = row

        if not structured_output:
            raise ValueError(
                f"AISession {ai_session_id} has no structured_output. "
                "Call parse() first."
            )

        envelope = json.loads(structured_output)
        payload = envelope["payload"]

        work_item = {
            "id": work_item_id,
            "item_type": item_type,
            "status": "in_progress",
            "domain_id": domain_id,
            "entity_id": entity_id,
            "process_id": process_id,
        }

        return map_payload(
            self._conn, work_item, payload, session_type, ai_session_id,
            master_conn=self._master_conn, envelope=envelope,
        )

    def detect_conflicts(self, batch: ProposedBatch) -> ProposedBatch:
        """Stage 4: Detect conflicts and attach them to ProposedRecords.

        Does not halt on conflicts — they are presented in Stage 5 (Review).

        :param batch: The ProposedBatch from map().
        :returns: The same batch with conflicts populated.
        """
        return detect_conflicts(self._conn, batch)

    def commit(
        self,
        ai_session_id: int,
        batch: ProposedBatch,
        accepted_record_ids: set[str] | None = None,
    ) -> CommitResult:
        """Stage 6: Commit accepted records in a single transaction.

        :param ai_session_id: The AISession.id.
        :param batch: The ProposedBatch (with conflicts from detect_conflicts).
        :param accepted_record_ids: Set of source_payload_path strings for
            accepted records. None means accept all.
        :returns: CommitResult with counts and new ids.
        """
        return commit_batch(
            self._conn, ai_session_id, batch,
            accepted_paths=accepted_record_ids,
            master_conn=self._master_conn,
        )

    def trigger(
        self,
        ai_session_id: int,
        commit_result: CommitResult,
    ) -> TriggerResult:
        """Stage 7: Run downstream triggers.

        Per Section 11.10.3, failures here do not roll back the commit.

        :param ai_session_id: The AISession.id.
        :param commit_result: The CommitResult from commit().
        :returns: TriggerResult describing what happened.
        """
        # Get work item info
        row = self._conn.execute(
            "SELECT a.work_item_id, a.session_type, w.item_type "
            "FROM AISession a "
            "JOIN WorkItem w ON w.id = a.work_item_id "
            "WHERE a.id = ?",
            (ai_session_id,),
        ).fetchone()

        if row is None:
            return TriggerResult(errors=[f"AISession {ai_session_id} not found"])

        work_item_id, session_type, item_type = row

        return run_triggers(
            self._conn, ai_session_id, commit_result,
            work_item_id, item_type, session_type,
        )

    def run_full_import(
        self,
        work_item_id: int,
        raw_text: str,
        accept_all: bool = True,
    ) -> ImportResult:
        """Convenience method that runs all 7 stages end-to-end.

        Used by tests and headless callers. The UI (Step 15) will call
        each stage individually for interactive review.

        :param work_item_id: The WorkItem.id.
        :param raw_text: The raw pasted text from the AI session.
        :param accept_all: If True, accept all records. If False, reject all.
        :returns: ImportResult with results from all stages.
        """
        # Stage 1: Receive
        ai_session_id = self.receive(work_item_id, raw_text)

        # Stage 2: Parse
        envelope = self.parse(ai_session_id)

        # Stage 3: Map
        batch = self.map(ai_session_id)

        # Stage 4: Detect conflicts
        batch = self.detect_conflicts(batch)

        # Stage 5: Review (auto-accept or auto-reject)
        accepted = None if accept_all else set()

        # Stage 6: Commit
        commit_result = self.commit(ai_session_id, batch, accepted)

        # Stage 7: Trigger
        trigger_result = self.trigger(ai_session_id, commit_result)

        return ImportResult(
            ai_session_id=ai_session_id,
            envelope=envelope,
            batch=batch,
            commit_result=commit_result,
            trigger_result=trigger_result,
        )
