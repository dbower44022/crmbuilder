"""Light import-and-construct tests for Documents view widgets."""

import pytest

PySide6 = pytest.importorskip("PySide6")


def test_documents_view_imports():
    """Verify DocumentsView can be imported."""
    from automation.ui.documents.documents_view import DocumentsView
    assert DocumentsView is not None


def test_documents_logic_imports():
    """Verify documents_logic can be imported (no Qt)."""
    from automation.ui.documents.documents_logic import (
        DocumentEntry,
        DocumentStatus,
    )
    assert DocumentEntry is not None
    assert DocumentStatus.STALE == "stale"


def test_generation_logic_imports():
    """Verify generation_logic can be imported (no Qt)."""
    from automation.ui.documents.generation_logic import (
        GenerationProgress,
        GenerationState,
    )
    assert GenerationProgress is not None
    assert GenerationState.IDLE.value == "idle"


def test_document_inventory_imports():
    """Verify document_inventory widget can be imported."""
    from automation.ui.documents.document_inventory import DocumentInventory
    assert DocumentInventory is not None


def test_batch_controls_imports():
    """Verify batch_controls widget can be imported."""
    from automation.ui.documents.batch_controls import BatchControls
    assert BatchControls is not None


def test_generation_flow_imports():
    """Verify generation_flow widget can be imported."""
    from automation.ui.documents.generation_flow import GenerationFlow
    assert GenerationFlow is not None
