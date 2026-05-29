"""Tests for the shared access-layer helpers."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access._helpers import (
    next_prefixed_identifier,
    validate_optional_value_list,
)
from crmbuilder_v2.access.exceptions import ValidationError


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
