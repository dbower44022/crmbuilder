"""Risks repository tests."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from crmbuilder_v2.access.repositories import risks


def _make(s, identifier="RISK-001", **kw):
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
        assert risks.get(s, "RISK-001")["status"] == "Open"


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
        risks.update(s, "RISK-001", status="Mitigated")
    with session_scope() as s:
        assert risks.get(s, "RISK-001")["status"] == "Mitigated"


def test_duplicate_id(v2_env):
    with session_scope() as s:
        _make(s)
    with session_scope() as s, pytest.raises(ConflictError):
        _make(s)


def test_delete(v2_env):
    with session_scope() as s:
        _make(s)
    with session_scope() as s:
        risks.delete(s, "RISK-001")
    with session_scope() as s, pytest.raises(NotFoundError):
        risks.get(s, "RISK-001")
