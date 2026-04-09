"""Light import-and-construct tests for Data Browser widgets."""

import pytest

PySide6 = pytest.importorskip("PySide6")


def test_browser_view_imports():
    """Verify BrowserView can be imported."""
    from automation.ui.browser.browser_view import BrowserView
    assert BrowserView is not None


def test_browser_logic_imports():
    """Verify browser_logic can be imported (no Qt)."""
    from automation.ui.browser.browser_logic import (
        BROWSABLE_TABLES,
        ColumnInfo,
    )
    assert ColumnInfo is not None
    assert "Entity" in BROWSABLE_TABLES


def test_tree_model_imports():
    """Verify tree_model can be imported (no Qt)."""
    from automation.ui.browser.tree_model import (
        TreeNode,
    )
    assert TreeNode is not None


def test_navigation_tree_imports():
    """Verify navigation_tree widget can be imported."""
    from automation.ui.browser.navigation_tree import NavigationTree
    assert NavigationTree is not None


def test_record_detail_imports():
    """Verify record_detail widget can be imported."""
    from automation.ui.browser.record_detail import RecordDetailView
    assert RecordDetailView is not None


def test_record_editor_imports():
    """Verify record_editor widget can be imported."""
    from automation.ui.browser.record_editor import RecordEditor
    assert RecordEditor is not None


def test_record_creator_imports():
    """Verify record_creator widget can be imported."""
    from automation.ui.browser.record_creator import RecordCreator
    assert RecordCreator is not None


def test_fk_selector_imports():
    """Verify fk_selector widget can be imported."""
    from automation.ui.browser.fk_selector import FKSelector
    assert FKSelector is not None


def test_audit_trail_imports():
    """Verify audit_trail widget can be imported."""
    from automation.ui.browser.audit_trail import AuditTrail
    assert AuditTrail is not None
