"""Unit tests for ``crmbuilder_v2.introspect.native_entity_types`` (PI-187)."""

from __future__ import annotations

import pytest
from crmbuilder_v2.introspect.native_entity_types import (
    NATIVE_ENTITY_BASE_TYPE,
    get_base_type,
)


@pytest.mark.parametrize(
    ("entity", "expected"),
    [
        ("Contact", "Person"),
        ("Lead", "Person"),
        ("User", "Person"),
        ("Account", "Company"),
        ("Opportunity", "Base"),
        ("Case", "Base"),
        ("Meeting", "Event"),
        ("Call", "Event"),
        ("Email", "Base"),
        ("Team", "Base"),
        ("Task", "Base"),
    ],
)
def test_get_base_type_known_entities(entity: str, expected: str) -> None:
    assert get_base_type(entity) == expected


def test_get_base_type_unknown_returns_none() -> None:
    assert get_base_type("CEngagement") is None
    assert get_base_type("Engagement") is None
    assert get_base_type("") is None


def test_base_type_values_are_canonical() -> None:
    # Every mapped base type must be one of the four EspoCRM base types.
    assert set(NATIVE_ENTITY_BASE_TYPE.values()) <= {
        "Person",
        "Company",
        "Event",
        "Base",
    }


def test_get_base_type_matches_mapping() -> None:
    for name, base in NATIVE_ENTITY_BASE_TYPE.items():
        assert get_base_type(name) == base
