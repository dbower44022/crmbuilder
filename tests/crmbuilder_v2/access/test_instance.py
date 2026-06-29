"""Instance repository tests — PI-186 (PRJ-027).

Covers the schema shape, identifier format + auto-assignment, the
vendor/role/auth/status enums, the eight repository methods, the
secret-reference pass-through (the data layer stores only opaque refs, never
plaintext), and the soft-delete / restore round-trip.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import instances
from sqlalchemy import inspect

_EXPECTED_COLUMNS = {
    "instance_identifier",
    "instance_name",
    "instance_vendor",
    "instance_url",
    "instance_role",
    "instance_auth_method",
    "instance_secret_ref",
    "instance_secret_key_ref",
    "instance_status",
    "instance_notes",
    "instance_created_at",
    "instance_updated_at",
    "instance_deleted_at",
    "engagement_id",
}


def _make(s, *, name="CBM sandbox", url="https://sandbox.example.org", **kw):
    return instances.create_instance(s, name=name, url=url, **kw)


def test_table_shape(v2_env):
    inspector = inspect(get_engine())
    assert "instances" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("instances")}
    assert cols == _EXPECTED_COLUMNS


def test_create_defaults(v2_env):
    with session_scope() as s:
        row = _make(s)
        assert row["instance_identifier"] == "INST-001"
        assert row["instance_vendor"] == "espocrm"
        assert row["instance_role"] == "both"
        assert row["instance_auth_method"] == "api_key"
        assert row["instance_status"] == "active"
        assert row["instance_secret_ref"] is None
        assert row["instance_deleted_at"] is None


def test_identifier_autoassigns_sequentially(v2_env):
    with session_scope() as s:
        a = _make(s)
        b = _make(s, name="CBM prod", url="https://prod.example.org")
        assert a["instance_identifier"] == "INST-001"
        assert b["instance_identifier"] == "INST-002"


def test_explicit_identifier_collision_rejected(v2_env):
    with session_scope() as s:
        _make(s, identifier="INST-005")
        with pytest.raises(ConflictError):
            _make(s, identifier="INST-005", name="dup")


def test_bad_identifier_format_rejected(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            _make(s, identifier="INST-5")


@pytest.mark.parametrize(
    "field,value",
    [("vendor", "hubspot"), ("role", "reader"), ("auth_method", "oauth"),
     ("status", "paused")],
)
def test_enum_validation(v2_env, field, value):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            _make(s, **{field: value})


def test_empty_name_and_url_rejected(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            instances.create_instance(s, name="  ", url="https://x")
        with pytest.raises(UnprocessableError):
            instances.create_instance(s, name="ok", url="")


def test_secret_refs_pass_through_only(v2_env):
    """The data layer stores exactly the opaque refs it is handed (REQ-157)."""
    with session_scope() as s:
        row = _make(
            s,
            auth_method="hmac",
            secret_ref="crmbuilder:abc",
            secret_key_ref="crmbuilder:def",
        )
        assert row["instance_secret_ref"] == "crmbuilder:abc"
        assert row["instance_secret_key_ref"] == "crmbuilder:def"


def test_patch_unknown_field_rejected(v2_env):
    with session_scope() as s:
        row = _make(s)
        with pytest.raises(UnprocessableError):
            instances.patch_instance(
                s, row["instance_identifier"], wibble="x"
            )


def test_patch_updates_fields(v2_env):
    with session_scope() as s:
        row = _make(s)
        ident = row["instance_identifier"]
        out = instances.patch_instance(
            s, ident, role="source", status="disabled", notes="read-only"
        )
        assert out["instance_role"] == "source"
        assert out["instance_status"] == "disabled"
        assert out["instance_notes"] == "read-only"


def test_update_full_replace(v2_env):
    with session_scope() as s:
        ident = _make(s)["instance_identifier"]
        out = instances.update_instance(
            s,
            ident,
            name="renamed",
            url="https://new.example.org",
            vendor="espocrm",
            role="target",
            auth_method="api_key",
            status="active",
        )
        assert out["instance_name"] == "renamed"
        assert out["instance_role"] == "target"


def test_soft_delete_and_restore(v2_env):
    with session_scope() as s:
        ident = _make(s)["instance_identifier"]
        deleted = instances.delete_instance(s, ident)
        assert deleted["instance_deleted_at"] is not None
        assert instances.get_instance(s, ident) is None
        assert instances.get_instance(s, ident, include_deleted=True) is not None
        restored = instances.restore_instance(s, ident)
        assert restored["instance_deleted_at"] is None


def test_restore_not_deleted_rejected(v2_env):
    with session_scope() as s:
        ident = _make(s)["instance_identifier"]
        with pytest.raises(UnprocessableError):
            instances.restore_instance(s, ident)


def test_get_missing_returns_none_repo(v2_env):
    with session_scope() as s:
        assert instances.get_instance(s, "INST-999") is None
        with pytest.raises(NotFoundError):
            instances.delete_instance(s, "INST-999")


def test_list_filters(v2_env):
    with session_scope() as s:
        _make(s, role="source", status="active")
        _make(s, name="b", url="https://b", role="target", status="disabled")
        assert len(instances.list_instances(s)) == 2
        assert len(instances.list_instances(s, role="source")) == 1
        assert len(instances.list_instances(s, status="disabled")) == 1


def test_basic_auth_method_accepted(v2_env):
    """PI-196: basic is a valid instance auth method (EspoCRM/CBM use it)."""
    with session_scope() as s:
        row = _make(s, auth_method="basic")
        assert row["instance_auth_method"] == "basic"


# --- both role (PI-352 / REQ-393) -------------------------------------------
# The ``both`` role (a single instance read from *and* written to) was a valid
# INSTANCE_ROLES member and the create default from the start, but the storage
# layer had no test that exercised the value explicitly — only the default.
# These prove it can be stored, validated, read back durably, and that an
# already-stored instance migrates to ``both`` cleanly. The API counterpart is
# tests/crmbuilder_v2/api/test_instance_api.py (WTK-255).


def test_create_explicit_both_role(v2_env):
    """``both`` is settable explicitly (not just the create default)."""
    with session_scope() as s:
        row = _make(s, role="both")
        assert row["instance_role"] == "both"
    # And it reads back identically from a fresh session (committed to the DB,
    # so the ck_instance_role CHECK admitted it — not merely repo validation).
    with session_scope() as s:
        assert instances.get_instance(s, "INST-001")["instance_role"] == "both"


def test_patch_existing_instance_to_both(v2_env):
    """An existing source instance re-roles to ``both`` via patch and persists."""
    with session_scope() as s:
        ident = _make(s, role="source")["instance_identifier"]
    with session_scope() as s:
        out = instances.patch_instance(s, ident, role="both")
        assert out["instance_role"] == "both"
    with session_scope() as s:
        assert instances.get_instance(s, ident)["instance_role"] == "both"


def test_update_existing_instance_to_both(v2_env):
    """Full-replace update of a target instance to ``both`` persists."""
    with session_scope() as s:
        ident = _make(s, role="target")["instance_identifier"]
    with session_scope() as s:
        out = instances.update_instance(
            s,
            ident,
            name="CBM sandbox",
            url="https://sandbox.example.org",
            role="both",
        )
        assert out["instance_role"] == "both"
    with session_scope() as s:
        assert instances.get_instance(s, ident)["instance_role"] == "both"


def test_list_filter_by_both_role(v2_env):
    """The role filter resolves ``both`` distinctly from source/target."""
    with session_scope() as s:
        _make(s, role="both")
        _make(s, name="b", url="https://b", role="source")
        both = instances.list_instances(s, role="both")
        assert len(both) == 1
        assert both[0]["instance_role"] == "both"


def test_role_check_constraint_admits_both(v2_env):
    """The migrated schema carries a role CHECK whose predicate admits ``both``.

    Guards against a future migration narrowing INSTANCE_ROLES and silently
    orphaning stored both-role instances.
    """
    checks = inspect(get_engine()).get_check_constraints("instances")
    role_check = next(c for c in checks if c["name"] == "ck_instance_role")
    assert "both" in role_check["sqltext"]


def test_bad_role_still_rejected_alongside_both(v2_env):
    """``both`` being valid does not loosen rejection of unknown roles."""
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            _make(s, role="mirror")
