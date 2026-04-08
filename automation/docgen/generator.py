"""DocumentGenerator — public API for the Document Generator.

Implements L2 PRD Section 13 — the main entry point for document generation.
This class wraps the rendering pipeline and provides convenience methods for
batch generation, staleness detection, and git push.

The generator never modifies work items. It only reads work items to validate
state, and writes only to GenerationLog and the file system.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from automation.docgen import git_ops
from automation.docgen.pipeline import GenerationResult, run_pipeline
from automation.docgen.staleness import StaleDocument, get_stale_documents

logger = logging.getLogger(__name__)


class DocumentGenerator:
    """Public API for the Document Generator.

    Accepts database connections and a project folder at construction time.
    All methods operate on these connections.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        master_conn: sqlite3.Connection | None = None,
        project_folder: str | Path | None = None,
    ) -> None:
        """Initialize the Document Generator.

        :param conn: Client database connection.
        :param master_conn: Master database connection (for Client record).
        :param project_folder: Root of the client's project repository.
        """
        self._conn = conn
        self._master_conn = master_conn
        self._project_folder = str(project_folder) if project_folder else None

    def generate(
        self,
        work_item_id: int,
        mode: str = "final",
    ) -> GenerationResult:
        """Run the full pipeline for a work item.

        :param work_item_id: The WorkItem.id to generate.
        :param mode: 'final' or 'draft'.
        :returns: GenerationResult with file_path, warnings, git_commit_hash,
            and any errors.
        :raises ValueError: If mode is invalid or the work item is not in
            a generatable state.
        """
        return run_pipeline(
            self._conn,
            work_item_id,
            mode=mode,
            project_folder=self._project_folder,
            master_conn=self._master_conn,
        )

    def generate_batch(
        self,
        work_item_ids: list[int],
        mode: str = "final",
    ) -> list[GenerationResult]:
        """Generate multiple documents.

        Per Section 13.7.4, each document is committed individually.
        A failure on one document does not block the others.

        :param work_item_ids: List of WorkItem.id values to generate.
        :param mode: 'final' or 'draft'.
        :returns: List of GenerationResult, one per work item.
        """
        results: list[GenerationResult] = []
        for wi_id in work_item_ids:
            try:
                result = self.generate(wi_id, mode=mode)
                results.append(result)
            except Exception as e:
                logger.warning(
                    "Batch generation failed for work item %d: %s",
                    wi_id, e,
                )
                from automation.docgen import WORK_ITEM_TYPE_TO_DOCUMENT_TYPE
                from automation.docgen.pipeline import GenerationResult as GR
                # Try to get the document type
                wi = self._conn.execute(
                    "SELECT item_type FROM WorkItem WHERE id = ?", (wi_id,)
                ).fetchone()
                doc_type = WORK_ITEM_TYPE_TO_DOCUMENT_TYPE.get(wi[0]) if wi else None
                results.append(GR(
                    work_item_id=wi_id,
                    document_type=doc_type,
                    mode=mode,
                    error=str(e),
                ))
        return results

    def get_stale_documents(self) -> list[StaleDocument]:
        """Return all documents that are stale.

        Convenience wrapper around staleness.get_stale_documents().
        """
        return get_stale_documents(self._conn)

    def push(self) -> bool:
        """Push committed changes to the remote.

        Optional follow-up after one or more generate() calls.

        :returns: True on success, False on failure.
        """
        if not self._project_folder:
            logger.warning("No project folder configured; cannot push.")
            return False
        return git_ops.push(self._project_folder)
