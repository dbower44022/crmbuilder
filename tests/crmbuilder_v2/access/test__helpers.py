"""Tests for the shared access-layer helpers."""

from __future__ import annotations

from crmbuilder_v2.access._helpers import next_prefixed_identifier


def test_next_prefixed_identifier_width_three_default():
    assert next_prefixed_identifier([], "WT") == "WT-001"
    assert next_prefixed_identifier(["WT-005"], "WT") == "WT-006"


def test_next_prefixed_identifier_width_four_for_commits():
    assert next_prefixed_identifier([], "CM", width=4) == "CM-0001"
    assert next_prefixed_identifier(["CM-0042"], "CM", width=4) == "CM-0043"
