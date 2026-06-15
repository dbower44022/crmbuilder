"""Message-template repository tests — PRJ-025 PI-189 slice 3.

Covers schema shape, vocab/CHECK registration, CRUD, soft-delete/restore,
non-empty body, channel vocab, merge-field validation, and the optional
subject-entity existence/liveness surfaces (validated only when present).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import entity, message_template
from crmbuilder_v2.access.vocab import CHANGE_LOG_ENTITY_TYPES, ENTITY_TYPES
from sqlalchemy import inspect

_EXPECTED_COLUMNS = {
    "message_template_identifier": "VARCHAR",
    "message_template_name": "VARCHAR",
    "message_template_entity": "VARCHAR",
    "message_template_channel": "VARCHAR",
    "message_template_subject": "VARCHAR",
    "message_template_body": "TEXT",
    "message_template_merge_fields": "JSON",
    "message_template_audience": "TEXT",
    "message_template_description": "TEXT",
    "message_template_notes": "TEXT",
    "message_template_status": "VARCHAR",
    # DateTime(timezone=True) reflects as DATETIME on SQLite, TIMESTAMP on
    # Postgres; this suite runs on both (CRMBUILDER_V2_TEST_PG_URL). str
    # .startswith accepts a tuple of acceptable prefixes.
    "message_template_created_at": ("DATETIME", "TIMESTAMP"),
    "message_template_updated_at": ("DATETIME", "TIMESTAMP"),
    "message_template_deleted_at": ("DATETIME", "TIMESTAMP"),
    "engagement_id": "VARCHAR",
}


def _seed_entity(s, name: str) -> str:
    return entity.create_entity(s, name=name, description="seed")[
        "entity_identifier"
    ]


def test_message_templates_table_has_expected_columns(v2_env):
    insp = inspect(get_engine())
    assert "message_templates" in insp.get_table_names()
    columns = {c["name"]: c for c in insp.get_columns("message_templates")}
    assert set(columns) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    pk = insp.get_pk_constraint("message_templates")
    assert pk["constrained_columns"] == [
        "message_template_identifier",
        "engagement_id",
    ]


def test_message_template_registered_in_vocab():
    assert "message_template" in ENTITY_TYPES
    assert "message_template" in CHANGE_LOG_ENTITY_TYPES


def test_create_and_get_message_template(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "Contact")
        row = message_template.create_message_template(
            s,
            name="Welcome",
            body="Hello {{name}}",
            entity=e,
            channel="email",
            subject="Welcome {{name}}",
            merge_fields=["name", "email"],
            audience="new contacts",
        )
    assert row["message_template_identifier"] == "MSG-001"
    assert row["message_template_status"] == "candidate"
    assert row["message_template_channel"] == "email"
    assert row["message_template_merge_fields"] == ["name", "email"]
    assert row["message_template_entity"] == e
    with session_scope() as s:
        got = message_template.get_message_template(s, "MSG-001")
        assert got["message_template_body"] == "Hello {{name}}"


def test_create_minimal_without_optionals(v2_env):
    with session_scope() as s:
        row = message_template.create_message_template(
            s, name="t", body="body content"
        )
        assert row["message_template_entity"] is None
        assert row["message_template_channel"] is None
        assert row["message_template_merge_fields"] is None


def test_create_rejects_empty_body(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        message_template.create_message_template(s, name="t", body="   ")
    assert "message_template_body" in str(exc.value)


def test_create_rejects_bad_channel(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        message_template.create_message_template(
            s, name="t", body="b", channel="carrier_pigeon"
        )
    assert "message_template_channel" in str(exc.value)


def test_create_rejects_non_string_merge_field(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        message_template.create_message_template(
            s, name="t", body="b", merge_fields=["name", 9]
        )
    assert "message_template_merge_fields" in str(exc.value)


def test_create_rejects_dead_entity_when_present(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        entity.delete_entity(s, e)
        with pytest.raises(UnprocessableError) as exc:
            message_template.create_message_template(
                s, name="t", body="b", entity=e
            )
        assert "soft-deleted" in str(exc.value)


def test_create_rejects_unknown_entity_when_present(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        message_template.create_message_template(
            s, name="t", body="b", entity="ENT-999"
        )


def test_entity_not_validated_when_absent(v2_env):
    # No entity supplied: body-only template is accepted with no entity check.
    with session_scope() as s:
        row = message_template.create_message_template(
            s, name="t", body="b"
        )
        assert row["message_template_entity"] is None


def test_create_with_explicit_identifier_and_collision(v2_env):
    with session_scope() as s:
        message_template.create_message_template(
            s, name="t", body="b", identifier="MSG-050"
        )
    with session_scope() as s, pytest.raises(ConflictError):
        message_template.create_message_template(
            s, name="dup", body="b", identifier="MSG-050"
        )


def test_update_and_status_transition(v2_env):
    with session_scope() as s:
        message_template.create_message_template(
            s, name="t", body="b", identifier="MSG-001"
        )
    with session_scope() as s:
        row = message_template.patch_message_template(
            s, "MSG-001", status="confirmed"
        )
        assert row["message_template_status"] == "confirmed"
    with session_scope() as s, pytest.raises(StatusTransitionError):
        message_template.patch_message_template(
            s, "MSG-001", status="candidate"
        )


def test_patch_clears_channel(v2_env):
    with session_scope() as s:
        message_template.create_message_template(
            s, name="t", body="b", channel="sms", identifier="MSG-001"
        )
    with session_scope() as s:
        row = message_template.patch_message_template(
            s, "MSG-001", channel=None
        )
        assert row["message_template_channel"] is None


def test_soft_delete_and_restore(v2_env):
    with session_scope() as s:
        message_template.create_message_template(
            s, name="t", body="b", identifier="MSG-001"
        )
    with session_scope() as s:
        message_template.delete_message_template(s, "MSG-001")
        assert message_template.get_message_template(s, "MSG-001") is None
        assert (
            message_template.get_message_template(
                s, "MSG-001", include_deleted=True
            )
            is not None
        )
    with session_scope() as s:
        message_template.restore_message_template(s, "MSG-001")
        assert (
            message_template.get_message_template(s, "MSG-001") is not None
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        message_template.restore_message_template(s, "MSG-001")


def test_get_missing_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        message_template.delete_message_template(s, "MSG-404")


def test_list_filters_by_entity_and_channel(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        message_template.create_message_template(
            s, name="ta", body="b", entity=a, channel="email"
        )
        message_template.create_message_template(
            s, name="tb", body="b", channel="sms"
        )
    with session_scope() as s:
        assert len(message_template.list_message_templates(s)) == 2
        assert len(message_template.list_message_templates(s, entity=a)) == 1
        assert (
            len(message_template.list_message_templates(s, channel="sms"))
            == 1
        )
