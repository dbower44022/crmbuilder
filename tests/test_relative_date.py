"""Tests for the relative-date vocabulary module."""

import datetime

import pytest

from espo_impl.core.relative_date import (
    is_relative_date,
    resolve_relative_date,
)

# ---------------------------------------------------------------------------
# is_relative_date
# ---------------------------------------------------------------------------


class TestIsRelativeDate:
    """Tests for is_relative_date detection."""

    @pytest.mark.parametrize("token", ["today", "yesterday", "thisMonth", "lastMonth"])
    def test_bare_tokens(self, token):
        assert is_relative_date(token) is True

    @pytest.mark.parametrize("value", [
        "lastNDays:0",
        "lastNDays:1",
        "lastNDays:30",
        "lastNDays:365",
        "nextNDays:0",
        "nextNDays:1",
        "nextNDays:7",
        "nextNDays:365",
    ])
    def test_n_days_patterns(self, value):
        assert is_relative_date(value) is True

    @pytest.mark.parametrize("value", [
        "2026-04-14",
        "tomorrow",
        "nextMonth",
        "lastNDays:",
        "lastNDays:abc",
        "nextNDays:",
        "gibberish",
        "",
        "lastNDays:-1",
    ])
    def test_invalid_forms(self, value):
        assert is_relative_date(value) is False


# ---------------------------------------------------------------------------
# resolve_relative_date — bare tokens
# ---------------------------------------------------------------------------


class TestResolveBareTokens:
    """Resolution of the four bare tokens."""

    TODAY = datetime.date(2026, 4, 14)

    def test_today(self):
        assert resolve_relative_date("today", self.TODAY) == datetime.date(2026, 4, 14)

    def test_yesterday(self):
        assert resolve_relative_date("yesterday", self.TODAY) == datetime.date(2026, 4, 13)

    def test_this_month(self):
        assert resolve_relative_date("thisMonth", self.TODAY) == datetime.date(2026, 4, 1)

    def test_last_month(self):
        assert resolve_relative_date("lastMonth", self.TODAY) == datetime.date(2026, 3, 1)

    def test_last_month_january(self):
        """lastMonth when current month is January crosses year boundary."""
        jan = datetime.date(2026, 1, 15)
        assert resolve_relative_date("lastMonth", jan) == datetime.date(2025, 12, 1)


# ---------------------------------------------------------------------------
# resolve_relative_date — lastNDays / nextNDays
# ---------------------------------------------------------------------------


class TestResolveNDays:
    """Resolution of lastNDays:N and nextNDays:N."""

    TODAY = datetime.date(2026, 4, 14)

    def test_last_n_days_0(self):
        assert resolve_relative_date("lastNDays:0", self.TODAY) == self.TODAY

    def test_last_n_days_1(self):
        assert resolve_relative_date("lastNDays:1", self.TODAY) == datetime.date(2026, 4, 13)

    def test_last_n_days_30(self):
        assert resolve_relative_date("lastNDays:30", self.TODAY) == datetime.date(2026, 3, 15)

    def test_last_n_days_365(self):
        assert resolve_relative_date("lastNDays:365", self.TODAY) == datetime.date(2025, 4, 14)

    def test_next_n_days_0(self):
        assert resolve_relative_date("nextNDays:0", self.TODAY) == self.TODAY

    def test_next_n_days_1(self):
        assert resolve_relative_date("nextNDays:1", self.TODAY) == datetime.date(2026, 4, 15)

    def test_next_n_days_7(self):
        assert resolve_relative_date("nextNDays:7", self.TODAY) == datetime.date(2026, 4, 21)

    def test_next_n_days_365(self):
        assert resolve_relative_date("nextNDays:365", self.TODAY) == datetime.date(2027, 4, 14)


# ---------------------------------------------------------------------------
# resolve_relative_date — defaults and errors
# ---------------------------------------------------------------------------


class TestResolveEdgeCases:
    """Default today and error handling."""

    def test_defaults_to_real_today(self):
        result = resolve_relative_date("today")
        assert result == datetime.date.today()

    def test_invalid_token_raises(self):
        with pytest.raises(ValueError, match="Invalid relative-date string"):
            resolve_relative_date("bogus")

    def test_iso_date_not_accepted(self):
        with pytest.raises(ValueError, match="Invalid relative-date string"):
            resolve_relative_date("2026-04-14")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Invalid relative-date string"):
            resolve_relative_date("")
