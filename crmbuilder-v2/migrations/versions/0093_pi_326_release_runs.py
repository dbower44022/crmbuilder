"""PI-326 — release_runs table + entity-type / relationship-kind CHECK rebuilds.

Creates the ``release_runs`` table (the born-terminal run-outcome satellite,
``release_run`` entity, DEC-742 / REQ-262) and rebuilds the ``change_log`` +
``refs`` entity-type CHECKs to admit the new ``release_run`` entity type, and the
``refs`` relationship-kind CHECK to admit the new edge kind
``release_run_relates_to_finding``. All three CHECKs are supersets, so no existing
row is invalidated (the documented gotcha that adding an ENTITY_TYPE must rebuild
change_log + refs CHECKs, not just refs; tests build via create_all and miss it —
see 0034 / 0043 / 0045 / 0088).

The table is created from the ORM ``__table__`` (carries the dialect-aware
identifier-format CHECK + composite FK to ``releases``) with ``checkfirst`` so this
is idempotent on the create_all-then-upgrade-head test path. The CHECK predicates
are derived from the current vocab so they cannot drift from the models.

SQLite chain head 0092 -> 0093. Companion PG-chain delta:
``migrations/pg/versions/0050_pi_326_release_runs.py``.

NOTE (live application): the live store (``data/v2-unified.db``) is
create_all-managed and is NOT walked through this SQLite chain. This migration is
the canonical record of the delta; the live application is performed (and verified
on a copy first) per the standard runbook and authorized by a PM session.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import ReleaseRunRow
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    REFERENCE_RELATIONSHIPS,
    _check_in,
)

revision: str = "0093_pi_326_release_runs"
down_revision: str | None = "0092_rel_025_field_label"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPE = "release_run"
_NEW_KINDS = frozenset({"release_run_relates_to_finding"})

_CHANGELOG_TYPES_NEW = CHANGE_LOG_ENTITY_TYPES
_CHANGELOG_TYPES_OLD = CHANGE_LOG_ENTITY_TYPES - {_NEW_TYPE}
_REF_TYPES_NEW = ENTITY_TYPES
_REF_TYPES_OLD = ENTITY_TYPES - {_NEW_TYPE}
_KINDS_NEW = REFERENCE_RELATIONSHIPS
_KINDS_OLD = REFERENCE_RELATIONSHIPS - _NEW_KINDS


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_entity_type_checks(
    changelog_types: frozenset[str], ref_types: frozenset[str]
) -> None:
    existing = _tables()  # change_log/refs absent when the chain is entered mid-stream
    if "change_log" in existing:
        with op.batch_alter_table("change_log") as batch:
            batch.drop_constraint("ck_changelog_entity_type", type_="check")
            batch.create_check_constraint(
                "ck_changelog_entity_type", _check_in("entity_type", changelog_types)
            )
    if "refs" in existing:
        with op.batch_alter_table("refs") as batch:
            batch.drop_constraint("ck_ref_source_type", type_="check")
            batch.create_check_constraint(
                "ck_ref_source_type", _check_in("source_type", ref_types)
            )
            batch.drop_constraint("ck_ref_target_type", type_="check")
            batch.create_check_constraint(
                "ck_ref_target_type", _check_in("target_type", ref_types)
            )


def _rebuild_relationship_check(kinds: frozenset[str]) -> None:
    if "refs" not in _tables():
        return
    with op.batch_alter_table("refs") as batch:
        batch.drop_constraint("ck_ref_relationship", type_="check")
        batch.create_check_constraint(
            "ck_ref_relationship", _check_in("relationship_kind", kinds)
        )


def upgrade() -> None:
    bind = op.get_bind()
    ReleaseRunRow.__table__.create(bind, checkfirst=True)
    _rebuild_entity_type_checks(_CHANGELOG_TYPES_NEW, _REF_TYPES_NEW)
    _rebuild_relationship_check(_KINDS_NEW)


def downgrade() -> None:
    bind = op.get_bind()
    existing = _tables()
    if "refs" in existing:
        op.execute(
            "DELETE FROM refs WHERE source_type = 'release_run' "
            "OR target_type = 'release_run' "
            "OR relationship_kind = 'release_run_relates_to_finding'"
        )
    if "change_log" in existing:
        op.execute("DELETE FROM change_log WHERE entity_type = 'release_run'")
    _rebuild_entity_type_checks(_CHANGELOG_TYPES_OLD, _REF_TYPES_OLD)
    _rebuild_relationship_check(_KINDS_OLD)
    if ReleaseRunRow.__tablename__ in _tables():
        ReleaseRunRow.__table__.drop(bind)
