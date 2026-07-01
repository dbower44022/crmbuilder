"""Tests for the shared access-layer helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from crmbuilder_v2.access._helpers import (
    check_lost_update,
    next_prefixed_identifier,
    validate_optional_value_list,
)
from crmbuilder_v2.access.exceptions import ConflictError, ValidationError


def test_next_prefixed_identifier_width_three_default():
    assert next_prefixed_identifier([], "WT") == "WT-001"
    assert next_prefixed_identifier(["WT-005"], "WT") == "WT-006"


def test_next_prefixed_identifier_width_four_for_commits():
    assert next_prefixed_identifier([], "CM", width=4) == "CM-0001"
    assert next_prefixed_identifier(["CM-0042"], "CM", width=4) == "CM-0043"


_ALLOWED = frozenset({"a", "b", "c"})


def test_validate_optional_value_list_none_passes_through():
    assert validate_optional_value_list(None, field="area", allowed=_ALLOWED) is None


def test_validate_optional_value_list_preserves_order():
    assert validate_optional_value_list(
        ["b", "a"], field="area", allowed=_ALLOWED
    ) == ["b", "a"]


def test_validate_optional_value_list_accepts_tuple():
    assert validate_optional_value_list(
        ("a",), field="area", allowed=_ALLOWED
    ) == ["a"]


@pytest.mark.parametrize(
    "bad",
    [
        "a",          # bare string, not a list
        [],           # empty
        ["a", "a"],   # duplicate
        ["a", 1],     # non-string element
        ["a", "z"],   # unknown value
    ],
)
def test_validate_optional_value_list_rejects(bad):
    with pytest.raises(ValidationError):
        validate_optional_value_list(bad, field="area", allowed=_ALLOWED)


# -- check_lost_update (REQ-396 / PI-103) ------------------------------------

_NOW = datetime(2026, 6, 30, 14, 2, 11, 123456, tzinfo=UTC)


def test_check_lost_update_none_precondition_is_noop():
    # No expected token → guard skipped (backward compatible).
    check_lost_update(_NOW, None, entity_type="decision", identifier="DEC-1")


def test_check_lost_update_matching_datetime_passes():
    check_lost_update(_NOW, _NOW.isoformat(), entity_type="decision", identifier="DEC-1")


def test_check_lost_update_matching_z_suffix_passes():
    # A client that formats the token with a trailing Z must still match.
    z = _NOW.isoformat().replace("+00:00", "Z")
    check_lost_update(_NOW, z, entity_type="decision", identifier="DEC-1")


def test_check_lost_update_stale_raises_conflict():
    stale = datetime(2026, 6, 30, 14, 0, 0, tzinfo=UTC).isoformat()
    with pytest.raises(ConflictError) as exc:
        check_lost_update(_NOW, stale, entity_type="decision", identifier="DEC-1")
    assert "stale_write" in str(exc.value)


def test_check_lost_update_malformed_precondition_raises_validation():
    with pytest.raises(ValidationError):
        check_lost_update(_NOW, "not-a-timestamp", entity_type="decision", identifier="DEC-1")


def test_check_lost_update_naive_current_treated_as_utc():
    naive = _NOW.replace(tzinfo=None)
    check_lost_update(naive, _NOW.isoformat(), entity_type="decision", identifier="DEC-1")
