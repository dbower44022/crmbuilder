"""v0.5 slice B — engagement repository tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from crmbuilder_v2.access.engagement import (
    create_engagement,
    delete_engagement,
    get_engagement,
    list_engagements,
    next_engagement_identifier,
    patch_engagement,
    restore_engagement,
    update_engagement,
)
from crmbuilder_v2.access.engagement_models import EngagementStatus
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.meta_db import (
    bootstrap_meta_db,
    meta_session_scope,
    reset_meta_engine_cache,
)
from crmbuilder_v2.access.meta_exporter import meta_export_dir


@pytest.fixture
def meta_db(v2_env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Materialise the meta DB schema for the test."""
    # Redirect meta_export_dir() to the temp path so tests don't write
    # to the real PRDs/db-export/meta/ dir.
    from crmbuilder_v2.access import meta_exporter

    test_export = tmp_path / "test-meta-export"
    monkeypatch.setattr(meta_exporter, "meta_export_dir", lambda: test_export)

    reset_meta_engine_cache()
    bootstrap_meta_db()
    yield test_export


def test_create_happy_path(meta_db):
    with meta_session_scope() as s:
        eng = create_engagement(
            s,
            engagement_code="ALPHA",
            engagement_name="Alpha Engagement",
            engagement_purpose="testing",
        )
    assert eng.engagement_identifier == "ENG-001"
    assert eng.engagement_code == "ALPHA"
    assert eng.engagement_status == EngagementStatus.ACTIVE
    assert eng.engagement_export_dir is None


def test_create_assigns_identifier_when_omitted(meta_db):
    with meta_session_scope() as s:
        a = create_engagement(
            s, engagement_code="ALPHA", engagement_name="A", engagement_purpose="p"
        )
        b = create_engagement(
            s, engagement_code="BETA", engagement_name="B", engagement_purpose="p"
        )
    assert a.engagement_identifier == "ENG-001"
    assert b.engagement_identifier == "ENG-002"


def test_create_rejects_invalid_code(meta_db):
    with meta_session_scope() as s, pytest.raises(UnprocessableError) as exc:
        create_engagement(
            s,
            engagement_code="too_long_lowercase",
            engagement_name="X",
            engagement_purpose="p",
        )
    assert any(e.field == "engagement_code" for e in exc.value.errors)


def test_create_rejects_short_code(meta_db):
    with meta_session_scope() as s, pytest.raises(UnprocessableError):
        create_engagement(
            s,
            engagement_code="A",  # too short (1 char; min is 2)
            engagement_name="A",
            engagement_purpose="p",
        )


def test_create_rejects_leading_digit_code(meta_db):
    with meta_session_scope() as s, pytest.raises(UnprocessableError):
        create_engagement(
            s,
            engagement_code="1ABC",
            engagement_name="X",
            engagement_purpose="p",
        )


def test_create_rejects_lowercase_code(meta_db):
    with meta_session_scope() as s, pytest.raises(UnprocessableError):
        create_engagement(
            s, engagement_code="cbm", engagement_name="x", engagement_purpose="p"
        )


def test_create_rejects_duplicate_code_case_insensitive(meta_db):
    with meta_session_scope() as s:
        create_engagement(
            s, engagement_code="CBM", engagement_name="A", engagement_purpose="p"
        )
    with meta_session_scope() as s, pytest.raises(UnprocessableError) as exc:
        create_engagement(
            s, engagement_code="CBM", engagement_name="B", engagement_purpose="p"
        )
    assert any(
        e.field == "engagement_code" and e.code == "not_unique"
        for e in exc.value.errors
    )


def test_create_rejects_duplicate_name_case_insensitive(meta_db):
    with meta_session_scope() as s:
        create_engagement(
            s,
            engagement_code="ALPHA",
            engagement_name="Same Name",
            engagement_purpose="p",
        )
    with meta_session_scope() as s, pytest.raises(UnprocessableError):
        create_engagement(
            s,
            engagement_code="BETA",
            engagement_name="SAME NAME",
            engagement_purpose="p",
        )


def test_create_rejects_invalid_status(meta_db):
    with meta_session_scope() as s, pytest.raises(UnprocessableError):
        create_engagement(
            s,
            engagement_code="XY",
            engagement_name="X",
            engagement_purpose="p",
            engagement_status="bogus",
        )


def test_create_rejects_missing_purpose(meta_db):
    with meta_session_scope() as s, pytest.raises(UnprocessableError):
        create_engagement(
            s,
            engagement_code="XY",
            engagement_name="X",
            engagement_purpose="",
        )


def test_create_accepts_nonexistent_export_dir(meta_db):
    # Relaxed in multi-tenancy-routing-fix slice B: existence is no longer
    # required at create time. The write-time gate (DEC-114) fails loud
    # with EngagementExportDirMissing if the dir is absent when an export
    # runs. An absolute path that does not yet exist is accepted here.
    with meta_session_scope() as s:
        eng = create_engagement(
            s,
            engagement_code="XY",
            engagement_name="X",
            engagement_purpose="p",
            engagement_export_dir="/nonexistent/path/zzz",
        )
    assert eng.engagement_export_dir == "/nonexistent/path/zzz"


def test_create_rejects_relative_export_dir(meta_db, tmp_path):
    with meta_session_scope() as s, pytest.raises(UnprocessableError) as exc:
        create_engagement(
            s,
            engagement_code="XY",
            engagement_name="X",
            engagement_purpose="p",
            engagement_export_dir="relative/path",
        )
    assert any(e.code == "not_absolute_path" for e in exc.value.errors)


def test_create_accepts_valid_export_dir(meta_db, tmp_path):
    with meta_session_scope() as s:
        eng = create_engagement(
            s,
            engagement_code="XY",
            engagement_name="X",
            engagement_purpose="p",
            engagement_export_dir=str(tmp_path),
        )
    assert eng.engagement_export_dir == str(tmp_path)


def test_create_explicit_identifier_collision(meta_db):
    with meta_session_scope() as s:
        create_engagement(
            s,
            engagement_identifier="ENG-001",
            engagement_code="AA",
            engagement_name="A",
            engagement_purpose="p",
        )
    with meta_session_scope() as s, pytest.raises(ConflictError):
        create_engagement(
            s,
            engagement_identifier="ENG-001",
            engagement_code="BB",
            engagement_name="B",
            engagement_purpose="p",
        )


def test_list_excludes_soft_deleted_by_default(meta_db):
    with meta_session_scope() as s:
        create_engagement(
            s, engagement_code="AA", engagement_name="A1", engagement_purpose="p"
        )
        eng2 = create_engagement(
            s, engagement_code="BB", engagement_name="B1", engagement_purpose="p"
        )
        delete_engagement(s, eng2.engagement_identifier)

    with meta_session_scope() as s:
        live = list_engagements(s)
        all_ = list_engagements(s, include_deleted=True)
    assert len(live) == 1
    assert len(all_) == 2


def test_get_returns_soft_deleted(meta_db):
    with meta_session_scope() as s:
        eng = create_engagement(
            s, engagement_code="AA", engagement_name="A", engagement_purpose="p"
        )
        delete_engagement(s, eng.engagement_identifier)

    with meta_session_scope() as s:
        fetched = get_engagement(s, eng.engagement_identifier)
    assert fetched is not None
    assert fetched.engagement_deleted_at is not None


def test_get_missing_returns_none(meta_db):
    with meta_session_scope() as s:
        assert get_engagement(s, "ENG-099") is None


def test_patch_status_transitions_all_six(meta_db):
    """All six transitions between the three statuses are valid."""
    with meta_session_scope() as s:
        eng = create_engagement(
            s, engagement_code="AA", engagement_name="A", engagement_purpose="p"
        )
        idn = eng.engagement_identifier

    for target in ("paused", "archived", "active", "archived", "paused", "active"):
        with meta_session_scope() as s:
            updated = patch_engagement(s, idn, engagement_status=target)
        assert updated.engagement_status.value == target


def test_patch_rejects_invalid_status(meta_db):
    with meta_session_scope() as s:
        eng = create_engagement(
            s, engagement_code="AA", engagement_name="A", engagement_purpose="p"
        )
    with meta_session_scope() as s, pytest.raises(UnprocessableError):
        patch_engagement(
            s, eng.engagement_identifier, engagement_status="bogus"
        )


def test_patch_rejects_code_change(meta_db):
    with meta_session_scope() as s:
        eng = create_engagement(
            s, engagement_code="AA", engagement_name="A", engagement_purpose="p"
        )
    with meta_session_scope() as s, pytest.raises(UnprocessableError) as exc:
        patch_engagement(
            s, eng.engagement_identifier, engagement_code="DIFFERENT"
        )
    assert any(
        e.field == "engagement_code" and e.code == "immutable_field"
        for e in exc.value.errors
    )


def test_patch_allows_noop_code_match(meta_db):
    with meta_session_scope() as s:
        eng = create_engagement(
            s, engagement_code="ALPHA", engagement_name="A", engagement_purpose="p"
        )
    with meta_session_scope() as s:
        # Same code is a no-op, no error.
        updated = patch_engagement(
            s,
            eng.engagement_identifier,
            engagement_code="ALPHA",
            engagement_name="Renamed",
        )
    assert updated.engagement_name == "Renamed"


def test_update_full_replace(meta_db):
    with meta_session_scope() as s:
        eng = create_engagement(
            s, engagement_code="AA", engagement_name="A", engagement_purpose="p"
        )
    with meta_session_scope() as s:
        updated = update_engagement(
            s,
            eng.engagement_identifier,
            engagement_name="Replaced Name",
            engagement_purpose="Replaced purpose",
            engagement_status="paused",
        )
    assert updated.engagement_name == "Replaced Name"
    assert updated.engagement_status.value == "paused"


def test_update_rejects_identifier_mismatch(meta_db):
    with meta_session_scope() as s:
        eng = create_engagement(
            s, engagement_code="AA", engagement_name="A", engagement_purpose="p"
        )
    with meta_session_scope() as s, pytest.raises(UnprocessableError) as exc:
        update_engagement(
            s,
            eng.engagement_identifier,
            engagement_identifier="ENG-099",
            engagement_name="X",
            engagement_purpose="X",
            engagement_status="active",
        )
    assert any(e.code == "identifier_mismatch" for e in exc.value.errors)


def test_update_rejects_code_change(meta_db):
    with meta_session_scope() as s:
        eng = create_engagement(
            s, engagement_code="AA", engagement_name="A", engagement_purpose="p"
        )
    with meta_session_scope() as s, pytest.raises(UnprocessableError) as exc:
        update_engagement(
            s,
            eng.engagement_identifier,
            engagement_code="DIFFERENT",
            engagement_name="X",
            engagement_purpose="X",
            engagement_status="active",
        )
    assert any(e.code == "immutable_field" for e in exc.value.errors)


def test_delete_idempotent(meta_db):
    with meta_session_scope() as s:
        eng = create_engagement(
            s, engagement_code="AA", engagement_name="A", engagement_purpose="p"
        )
        first = delete_engagement(s, eng.engagement_identifier)
        first_deleted_at = first.engagement_deleted_at
    with meta_session_scope() as s:
        second = delete_engagement(s, eng.engagement_identifier)
    assert first_deleted_at is not None
    assert second.engagement_deleted_at is not None
    # SQLite strips tzinfo on re-read; compare via timestamp() for robustness.
    assert (
        second.engagement_deleted_at.replace(tzinfo=None)
        == first_deleted_at.replace(tzinfo=None)
    )


def test_restore_round_trip(meta_db):
    with meta_session_scope() as s:
        eng = create_engagement(
            s, engagement_code="AA", engagement_name="A", engagement_purpose="p"
        )
        delete_engagement(s, eng.engagement_identifier)
        restored = restore_engagement(s, eng.engagement_identifier)
    assert restored.engagement_deleted_at is None


def test_restore_on_live_record_raises(meta_db):
    with meta_session_scope() as s:
        eng = create_engagement(
            s, engagement_code="AA", engagement_name="A", engagement_purpose="p"
        )
    with meta_session_scope() as s, pytest.raises(UnprocessableError) as exc:
        restore_engagement(s, eng.engagement_identifier)
    assert any(e.code == "not_soft_deleted" for e in exc.value.errors)


def test_next_identifier_empty_db(meta_db):
    with meta_session_scope() as s:
        assert next_engagement_identifier(s) == "ENG-001"


def test_next_identifier_increments(meta_db):
    with meta_session_scope() as s:
        create_engagement(
            s, engagement_code="AA", engagement_name="A", engagement_purpose="p"
        )
    with meta_session_scope() as s:
        assert next_engagement_identifier(s) == "ENG-002"


def test_list_orders_by_last_opened_desc_nulls_last(meta_db):
    """Engagements with last_opened_at sort first (desc); nulls last."""
    with meta_session_scope() as s:
        a = create_engagement(
            s, engagement_code="AA", engagement_name="A", engagement_purpose="p"
        )
        b = create_engagement(
            s, engagement_code="BB", engagement_name="B", engagement_purpose="p"
        )
        c = create_engagement(
            s, engagement_code="CC", engagement_name="C", engagement_purpose="p"
        )
        # B opened most recently; A opened earlier; C never opened.
        patch_engagement(
            s,
            a.engagement_identifier,
            engagement_last_opened_at=datetime(2026, 5, 1, tzinfo=UTC),
        )
        patch_engagement(
            s,
            b.engagement_identifier,
            engagement_last_opened_at=datetime(2026, 5, 10, tzinfo=UTC),
        )

    with meta_session_scope() as s:
        engagements = list_engagements(s)
    codes = [e.engagement_code for e in engagements]
    assert codes == ["BB", "AA", "CC"]


def test_snapshot_regenerated_on_write(meta_db):
    with meta_session_scope() as s:
        create_engagement(
            s, engagement_code="AA", engagement_name="A", engagement_purpose="p"
        )

    snapshot = meta_db / "engagements.json"
    # meta_db fixture redirected meta_export_dir() to the temp path.
    from crmbuilder_v2.access.meta_exporter import meta_export_dir

    snapshot_path = meta_export_dir() / "engagements.json"
    assert snapshot_path.exists()

    import json

    payload = json.loads(snapshot_path.read_text())
    assert len(payload) == 1
    assert payload[0]["engagement_code"] == "AA"
    assert payload[0]["engagement_status"] == "active"
