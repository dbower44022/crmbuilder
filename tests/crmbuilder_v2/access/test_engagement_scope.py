"""PI-123 Slice 2b — the central engagement-scope mechanism.

Unit tests for ``access/engagement_scope.py``: the read filter, the write
stamp, dormancy (no active engagement → no effect), A/B isolation, the
column-select path (identifier helpers), and the optional unset guard.

Uses ``refs`` (the :class:`Reference` model) as a representative scoped table —
it is engagement-scoped (carries ``engagement_id``) and cheap to construct.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from crmbuilder_v2.access import engagement_scope as es
from crmbuilder_v2.access.models import Base, EngagementRow, Reference
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def factory():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sm = sessionmaker(bind=engine)
    es.install_engagement_scope(sm)
    yield sm
    es.uninstall_engagement_scope(sm)
    engine.dispose()
    # Make sure no enforcement / active engagement leaks to other tests.
    es.set_enforcement(False)


def _ref(source_id: str, target_id: str, engagement_id: str | None = None) -> Reference:
    r = Reference(
        source_type="session",
        source_id=source_id,
        target_type="session",
        target_id=target_id,
        relationship_kind="references",
    )
    if engagement_id is not None:
        r.engagement_id = engagement_id
    return r


def _seed(factory, engagement_id: str, pairs: list[tuple[str, str]]) -> None:
    with es.active_engagement(engagement_id):
        s = factory()
        s.add_all([_ref(a, b) for a, b in pairs])
        s.commit()
        s.close()


def _count(factory, engagement_id: str | None) -> int:
    with es.active_engagement(engagement_id):
        s = factory()
        n = len(s.execute(select(Reference)).scalars().all())
        s.close()
        return n


def test_write_stamp_sets_engagement_id_from_context(factory):
    with es.active_engagement("ENG-001"):
        s = factory()
        r = _ref("SES-001", "SES-002")
        s.add(r)
        s.commit()
        assert r.engagement_id == "ENG-001"
        s.close()


def test_read_filter_scopes_to_active_engagement(factory):
    _seed(factory, "ENG-001", [("SES-001", "SES-002"), ("SES-003", "SES-004")])
    _seed(factory, "ENG-002", [("SES-010", "SES-011")])
    assert _count(factory, "ENG-001") == 2
    assert _count(factory, "ENG-002") == 1


def test_ab_isolation_no_caching_bleed(factory):
    _seed(factory, "ENG-001", [("SES-001", "SES-002")])
    _seed(factory, "ENG-002", [("SES-010", "SES-011"), ("SES-012", "SES-013")])
    # Alternate engagements on the same session to catch any cached-filter bleed.
    s = factory()
    with es.active_engagement("ENG-001"):
        assert len(s.execute(select(Reference)).scalars().all()) == 1
    with es.active_engagement("ENG-002"):
        assert len(s.execute(select(Reference)).scalars().all()) == 2
    with es.active_engagement("ENG-001"):
        assert len(s.execute(select(Reference)).scalars().all()) == 1
    s.close()


def test_column_select_is_filtered(factory):
    """The identifier-assignment path (select(Model.column)) must be scoped."""
    _seed(factory, "ENG-001", [("SES-001", "SES-002")])
    _seed(factory, "ENG-002", [("SES-010", "SES-011"), ("SES-012", "SES-013")])
    with es.active_engagement("ENG-001"):
        s = factory()
        rows = s.execute(select(Reference.source_id)).all()
        s.close()
    assert len(rows) == 1


def test_dormant_without_active_engagement_returns_all(factory):
    _seed(factory, "ENG-001", [("SES-001", "SES-002")])
    _seed(factory, "ENG-002", [("SES-010", "SES-011")])
    # No active engagement, enforcement off → no filtering (legacy behaviour).
    assert _count(factory, None) == 2


def test_unscoped_write_rejected_by_strict_schema(factory):
    """PI-123 Stage 2: ``engagement_id`` is now NOT NULL.

    With no active engagement the write-stamp leaves ``engagement_id`` unset,
    and the strict (cutover) schema rejects the row — superseding the Slice-2b
    dormant behaviour where the column was nullable and a no-active-engagement
    write simply left it ``NULL``.
    """
    from sqlalchemy.exc import IntegrityError

    s = factory()
    r = _ref("SES-001", "SES-002")  # no active engagement
    s.add(r)
    with pytest.raises(IntegrityError):
        s.commit()
    s.rollback()
    s.close()


def test_explicit_engagement_id_is_not_overwritten(factory):
    with es.active_engagement("ENG-001"):
        s = factory()
        r = _ref("SES-001", "SES-002", engagement_id="ENG-099")
        s.add(r)
        s.commit()
        assert r.engagement_id == "ENG-099"  # stamp skips a set value
        s.close()


def test_enforcement_raises_on_unscoped_read(factory):
    _seed(factory, "ENG-001", [("SES-001", "SES-002")])
    with es.enforcement(True):
        s = factory()
        with pytest.raises(es.EngagementScopeNotSet):
            s.execute(select(Reference)).scalars().all()
        s.close()


def test_enforcement_raises_on_unscoped_write(factory):
    with es.enforcement(True):
        s = factory()
        s.add(_ref("SES-001", "SES-002"))
        with pytest.raises(es.EngagementScopeNotSet):
            s.commit()
        s.rollback()
        s.close()


def test_enforcement_allows_non_scoped_entity(factory):
    """The engagements tenant table is not scoped — querying it never raises."""
    s = factory()
    now = datetime.now(UTC)
    s.add(
        EngagementRow(
            engagement_identifier="ENG-001",
            engagement_code="ALPHA",
            engagement_name="Alpha",
            engagement_purpose="p",
            engagement_status="active",
            engagement_created_at=now,
            engagement_updated_at=now,
        )
    )
    s.commit()
    s.close()
    with es.enforcement(True):
        s2 = factory()
        rows = s2.execute(select(EngagementRow)).scalars().all()  # must not raise
        s2.close()
    assert len(rows) == 1


def test_install_is_idempotent(factory):
    # Re-installing must not double-register (else the filter/stamp run twice).
    es.install_engagement_scope(factory)
    es.install_engagement_scope(factory)
    _seed(factory, "ENG-001", [("SES-001", "SES-002")])
    assert _count(factory, "ENG-001") == 1


def test_active_engagement_context_restores_on_exit(factory):
    assert es.get_active_engagement() is None
    with es.active_engagement("ENG-001"):
        assert es.get_active_engagement() == "ENG-001"
        with es.active_engagement("ENG-002"):
            assert es.get_active_engagement() == "ENG-002"
        assert es.get_active_engagement() == "ENG-001"
    assert es.get_active_engagement() is None
