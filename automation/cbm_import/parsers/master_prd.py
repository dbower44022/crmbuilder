"""Master PRD .docx parser — MIGRATED to Path B.

The Master PRD parser has moved to:
    automation.importer.parsers.master_prd_docx

This module is retained as a tombstone. Calling parse() raises immediately.
"""

from __future__ import annotations

from pathlib import Path


def parse(path: str | Path):
    raise NotImplementedError(
        "Master PRD parsing has migrated to "
        "automation.importer.parsers.master_prd_docx.parse(). "
        "Use ImportProcessor.run_full_import() with the envelope JSON "
        "produced by the new adapter. "
        "See PRDs/product/crmbuilder-automation-PRD/"
        "CLAUDE-CODE-PROMPT-master-prd-docx-adapter.md for context."
    )
