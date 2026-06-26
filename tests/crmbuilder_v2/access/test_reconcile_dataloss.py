"""Data-loss analysis tests — PI-318 (REL-024 / REQ-361)."""

from __future__ import annotations

from crmbuilder_v2.access.reconcile_dataloss import (
    assess_field_change,
    assess_revert,
)


def test_safe_change_needs_no_confirmation():
    v = assess_field_change("field_required", False, True)
    assert v["severity"] == "safe"
    assert v["requires_confirmation"] is False
    assert v["reasons"] == []


def test_narrowing_max_length_is_data_loss():
    v = assess_field_change("field_max_length", 255, 100)
    assert v["severity"] == "data_loss"
    assert v["requires_confirmation"] is True
    assert any("truncat" in r for r in v["reasons"])


def test_widening_max_length_is_safe():
    v = assess_field_change("field_max_length", 100, 255)
    assert v["requires_confirmation"] is False


def test_type_change_warns():
    v = assess_field_change("field_type", "text", "number")
    assert v["requires_confirmation"] is True
    assert any("convert" in r for r in v["reasons"])


def test_member_removal_is_data_loss():
    v = assess_field_change(None, None, None, removes_member=True)
    assert v["requires_confirmation"] is True
    assert any("stored data would be lost" in r for r in v["reasons"])


def test_assess_revert_of_narrowing_capture():
    # original published max_length 255 -> 100; reverting restores 255 (safe widen)
    txn = {
        "id": 5, "attribute": "field_max_length",
        "before_value": 255, "after_value": 100, "target_ref": "INST-001",
    }
    v = assess_revert(txn)
    assert v["transaction_id"] == 5
    assert v["requires_confirmation"] is False  # 100 -> 255 widens


def test_assess_revert_that_removes_member():
    txn = {
        "id": 6, "attribute": None,
        "before_value": "absent", "after_value": "present", "target_ref": "INST-001",
    }
    v = assess_revert(txn)
    assert v["requires_confirmation"] is True
