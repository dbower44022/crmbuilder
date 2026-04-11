"""TOMBSTONED — migrated to automation/importer/parsers/process_doc_docx.py on 04-10-26."""
from __future__ import annotations


def parse(*args, **kwargs):
    raise NotImplementedError(
        "Path A process document parser has been migrated to "
        "automation/importer/parsers/process_doc_docx.py. Use Path B "
        "ImportProcessor with the new adapter."
    )
