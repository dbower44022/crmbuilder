"""Unit tests for the shared timestamp display helper (PI-107)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone

import pytest
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp

_SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")


@pytest.mark.parametrize("value", [None, "", "not-a-date", "2026-13-99", 12345])
def test_missing_or_unparseable_renders_em_dash(value):
    assert format_timestamp(value) == "—"


def test_iso_string_naive_renders_shape():
    # Naive input is assumed UTC then converted to local; we assert the
    # rendered shape rather than an exact value to stay tz-independent.
    assert _SHAPE.match(format_timestamp("2026-05-29T23:35:53.169304"))


def test_iso_string_with_offset_renders_shape():
    assert _SHAPE.match(format_timestamp("2026-05-29T23:35:53+00:00"))


def test_datetime_instance_renders_shape():
    assert _SHAPE.match(format_timestamp(datetime(2026, 5, 29, 23, 35, tzinfo=UTC)))


def test_local_conversion_applied():
    # A fixed +05:00 instant must render as the equivalent local wall clock.
    aware = datetime(2026, 5, 29, 12, 0, tzinfo=timezone(timedelta(hours=5)))
    expected = aware.astimezone().strftime("%Y-%m-%d %H:%M")
    assert format_timestamp(aware) == expected
    # And the same instant expressed as an ISO string parses identically.
    assert format_timestamp("2026-05-29T12:00:00+05:00") == expected
