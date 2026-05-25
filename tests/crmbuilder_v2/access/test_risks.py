"""Risks repository tests."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
    ValidationError,
)
from crmbuilder_v2.access.repositories import risks


def _make(s, identifier="RSK-001", **kw):
    payload = dict(
        identifier=identifier,
        title="t",
        probability="Medium",
        impact="High",
        status="Open",
    )
    payload.update(kw)
    return risks.create(s, **payload)


def test_create_and_get(v2_env):
    with session_scope() as s:
        _make(s)
    with session_scope() as s:
        assert risks.get(s, "RSK-001")["status"] == "Open"


def test_invalid_probability(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        _make(s, probability="Sometimes")


def test_invalid_impact(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        _make(s, impact="Catastrophic")


def test_invalid_status(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        _make(s, status="Stuck")


def test_update(v2_env):
    with session_scope() as s:
        _make(s)
    with session_scope() as s:
        risks.update(s, "RSK-001", status="Mitigated")
    with session_scope() as s:
        assert risks.get(s, "RSK-001")["status"] == "Mitigated"


def test_duplicate_id(v2_env):
    with session_scope() as s:
        _make(s)
    with session_scope() as s, pytest.raises(ConflictError):
        _make(s)


def test_delete(v2_env):
    with session_scope() as s:
        _make(s)
    with session_scope() as s:
        risks.delete(s, "RSK-001")
    with session_scope() as s, pytest.raises(NotFoundError):
        risks.get(s, "RSK-001")


# ---------------------------------------------------------------------------
# PI-002 — identifier is server-assigned when omitted (option C of SES-010)
# ---------------------------------------------------------------------------


def test_create_with_omitted_identifier_assigns_next(v2_env):
    with session_scope() as s:
        row = risks.create(
            s, title="Auto", probability="Medium", impact="High", status="Open"
        )
    assert row["identifier"] == "RSK-001"
    with session_scope() as s:
        row2 = risks.create(
            s, title="Auto2", probability="Medium", impact="High", status="Open"
        )
    assert row2["identifier"] == "RSK-002"


def test_create_with_supplied_identifier_uses_it(v2_env):
    with session_scope() as s:
        row = risks.create(
            s, identifier="RSK-042", title="Explicit",
            probability="Medium", impact="High", status="Open",
        )
    assert row["identifier"] == "RSK-042"


def test_create_with_invalid_identifier_format_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        risks.create(
            s, identifier="RSK-1", title="Bad",
            probability="Medium", impact="High", status="Open",
        )


def test_create_with_empty_string_identifier_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        risks.create(
            s, identifier="", title="Bad",
            probability="Medium", impact="High", status="Open",
        )


def test_create_explicit_duplicate_identifier_raises_conflict(v2_env):
    with session_scope() as s:
        _make(s, identifier="RSK-001")
    with session_scope() as s, pytest.raises(ConflictError):
        risks.create(
            s, identifier="RSK-001", title="Second",
            probability="Medium", impact="High", status="Open",
        )


def test_autoassign_retries_on_identifier_collision(v2_env, monkeypatch):
    with session_scope() as s:
        _make(s, identifier="RSK-001")
    monkeypatch.setattr(risks, "compute_next_identifier", lambda _s: "RSK-001")
    with session_scope() as s:
        row = risks.create(
            s, title="Second", probability="Medium", impact="High", status="Open"
        )
    assert row["identifier"] == "RSK-002"
