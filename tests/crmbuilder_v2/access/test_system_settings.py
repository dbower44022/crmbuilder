"""Governed system settings with per-instance values — PI-406 (REQ-485/488)."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import instances as inst_repo
from crmbuilder_v2.access.repositories import system_settings as ss
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    SYSTEM_SETTING_STATUSES,
)
from sqlalchemy import inspect

_EXPECTED_COLUMNS = {
    "system_setting_identifier": "VARCHAR",
    "system_setting_key": "VARCHAR",
    "system_setting_name": "VARCHAR",
    "system_setting_value_type": "VARCHAR",
    "system_setting_description": "TEXT",
    "system_setting_notes": "TEXT",
    "system_setting_status": "VARCHAR",
    # PI-407 / REQ-486 — names the enum field whose active subset this is.
    "system_setting_active_subset_field": "VARCHAR",
    "system_setting_created_at": "DATETIME",
    "system_setting_updated_at": "DATETIME",
    "system_setting_deleted_at": "DATETIME",
    "engagement_id": "VARCHAR",
}


def _instance(s, name="src"):
    return inst_repo.create_instance(
        s, name=name, url=f"https://{name}.example.org", role="both"
    )["instance_identifier"]


def _setting(s, key="outboundEmailFromAddress"):
    return ss.create_system_setting(
        s, key=key, name="Outbound email address", value_type="text"
    )["system_setting_identifier"]


def test_table_shape(v2_env):
    insp = inspect(get_engine())
    cols = {c["name"]: c for c in insp.get_columns("system_settings")}
    assert set(cols) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(cols[name]["type"]).upper().startswith(affinity), name
    pk = insp.get_pk_constraint("system_settings")
    assert pk["constrained_columns"] == ["system_setting_identifier", "engagement_id"]


def test_registered_in_both_entity_type_vocabularies():
    """The standing lesson: a new entity type needs both CHECKs. CHANGE_LOG
    derives from ENTITY_TYPES, so registering once must reach both."""
    assert "system_setting" in ENTITY_TYPES
    assert "system_setting" in CHANGE_LOG_ENTITY_TYPES
    assert SYSTEM_SETTING_STATUSES == {
        "candidate", "confirmed", "deferred", "rejected"
    }


def test_a_governed_setting_declares_its_shape(v2_env):
    with session_scope() as s:
        out = ss.create_system_setting(
            s, key="siteUrl", name="Site URL", value_type="text"
        )
        assert out["system_setting_identifier"].startswith("SET-")
        assert out["system_setting_status"] == "candidate"
        assert out["system_setting_value_type"] == "text"


def test_the_value_shape_comes_from_the_field_vocabulary(v2_env):
    """REQ-485 asks for the setting's shape. PI-414 already built a vocabulary
    that describes any value a CRM can hold, so a second one would be a second
    thing to keep correct — a shape outside it is refused."""
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            ss.create_system_setting(
                s, key="x", name="X", value_type="not_a_field_kind"
            )


def test_two_settings_cannot_govern_the_same_key(v2_env):
    """One key, one governing record. Two would let the design hold two answers
    for what an instance should carry, which is the duplication the whole
    reconcile story depends on not existing."""
    with session_scope() as s:
        ss.create_system_setting(s, key="siteUrl", name="A", value_type="text")
        with pytest.raises(ConflictError):
            ss.create_system_setting(s, key="siteUrl", name="B", value_type="text")


# --- per-instance values ----------------------------------------------------

def test_a_value_is_declared_per_instance(v2_env):
    """REQ-485: the design governs which settings exist; each instance carries
    its own value. Two instances holding different values is not drift."""
    with session_scope() as s:
        sid = _setting(s)
        a, b = _instance(s, "alpha"), _instance(s, "beta")
        ss.set_value(s, system_setting_identifier=sid, instance_identifier=a,
                     value="info@alpha.org")
        ss.set_value(s, system_setting_identifier=sid, instance_identifier=b,
                     value="info@beta.org")
        assert ss.get_value(s, system_setting_identifier=sid,
                            instance_identifier=a)["value"] == "info@alpha.org"
        assert ss.get_value(s, system_setting_identifier=sid,
                            instance_identifier=b)["value"] == "info@beta.org"


def test_an_undeclared_value_is_absent_not_empty(v2_env):
    """REQ-485's third outcome turns on this distinction: nobody having said
    what an instance should hold is not the same as declaring it holds nothing,
    and only the first may never be reported conformant."""
    with session_scope() as s:
        sid = _setting(s)
        iid = _instance(s)
        assert ss.get_value(
            s, system_setting_identifier=sid, instance_identifier=iid
        ) is None
        ss.set_value(s, system_setting_identifier=sid, instance_identifier=iid,
                     value=None)
        declared = ss.get_value(
            s, system_setting_identifier=sid, instance_identifier=iid
        )
        assert declared is not None and declared["value"] is None


def test_withdrawing_a_declaration_returns_it_to_undeclared(v2_env):
    """Clearing deletes the row rather than nulling it, for the same reason."""
    with session_scope() as s:
        sid = _setting(s)
        iid = _instance(s)
        ss.set_value(s, system_setting_identifier=sid, instance_identifier=iid,
                     value="x")
        assert ss.clear_value(
            s, system_setting_identifier=sid, instance_identifier=iid
        ) is True
        assert ss.get_value(
            s, system_setting_identifier=sid, instance_identifier=iid
        ) is None


def test_redeclaring_updates_in_place(v2_env):
    with session_scope() as s:
        sid = _setting(s)
        iid = _instance(s)
        first = ss.set_value(s, system_setting_identifier=sid,
                             instance_identifier=iid, value="a")
        again = ss.set_value(s, system_setting_identifier=sid,
                             instance_identifier=iid, value="b")
        assert again["id"] == first["id"]
        assert again["value"] == "b"
        assert len(ss.list_values(s, system_setting_identifier=sid)) == 1


def test_a_value_cannot_be_declared_for_an_unknown_setting(v2_env):
    with session_scope() as s:
        iid = _instance(s)
        with pytest.raises(NotFoundError):
            ss.set_value(s, system_setting_identifier="SET-999",
                         instance_identifier=iid, value="x")
