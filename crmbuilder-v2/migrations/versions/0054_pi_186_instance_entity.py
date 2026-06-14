"""PI-186 (PRJ-027) — instances table + entity-type CHECK rebuilds.

Creates the ``instances`` table (the CRM-connection record type, ``INST-NNN``)
from the ORM ``__table__`` with ``checkfirst`` (idempotent on the
create_all-then-upgrade-head test path) — it carries the identifier-format,
vendor/role/auth/status CHECKs and the two indexes — and rebuilds
``ck_changelog_entity_type`` and the ``refs`` ``ck_ref_source_type`` /
``ck_ref_target_type`` CHECKs to admit the new ``instance`` entity type (the
known gotcha: tests build via create_all and miss it; the live DB 500s without
it — see 0034 / 0043 / 0045 / 0048 / 0052).

No new relationship kinds: the instance's membership edges land in PI-185, so
``ck_ref_relationship`` is untouched here. All CHECK predicates derive from the
current vocab so they cannot drift from the models; the rebuilds are supersets,
so no existing row is invalidated. The rebuild helper inspects the live tables
first and skips absent ones so the chain is safe to enter mid-stream (the
stamp-0036 isolated-migration path). Downgrade deletes refs/change_log rows
naming the new type, restores the narrower CHECKs, then drops the table.

SQLite chain head 0053 -> 0054. Companion PG-chain delta:
``migrations/pg/versions/0016_pi_186_instance_entity.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import Instance
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    _check_in,
)

revision: str = "0054_pi_186_instance_entity"
down_revision: str | None = "0053_pi_183_execution_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPE = "instance"

_TYPES_NEW = ENTITY_TYPES
_TYPES_OLD = ENTITY_TYPES - {_NEW_TYPE}
_LOG_TYPES_NEW = CHANGE_LOG_ENTITY_TYPES
_LOG_TYPES_OLD = CHANGE_LOG_ENTITY_TYPES - {_NEW_TYPE}


def _tables() -> set[str]:
    # Touched tables are absent when the chain is entered mid-stream
    # (the stamp-0036 isolated-migration test path).
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_entity_type_checks(
    types: frozenset[str], log_types: frozenset[str]
) -> None:
    existing = _tables()
    if "change_log" in existing:
        with op.batch_alter_table("change_log") as batch:
            batch.drop_constraint("ck_changelog_entity_type", type_="check")
            batch.create_check_constraint(
                "ck_changelog_entity_type", _check_in("entity_type", log_types)
            )
    if "refs" in existing:
        with op.batch_alter_table("refs") as batch:
            batch.drop_constraint("ck_ref_source_type", type_="check")
            batch.create_check_constraint(
                "ck_ref_source_type", _check_in("source_type", types)
            )
            batch.drop_constraint("ck_ref_target_type", type_="check")
            batch.create_check_constraint(
                "ck_ref_target_type", _check_in("target_type", types)
            )


def upgrade() -> None:
    bind = op.get_bind()
    Instance.__table__.create(bind, checkfirst=True)
    _rebuild_entity_type_checks(_TYPES_NEW, _LOG_TYPES_NEW)


def downgrade() -> None:
    bind = op.get_bind()
    existing = _tables()
    if "refs" in existing:
        op.execute(
            "DELETE FROM refs WHERE source_type = 'instance' "
            "OR target_type = 'instance'"
        )
    if "change_log" in existing:
        op.execute("DELETE FROM change_log WHERE entity_type = 'instance'")
    _rebuild_entity_type_checks(_TYPES_OLD, _LOG_TYPES_OLD)
    if Instance.__tablename__ in _tables():
        Instance.__table__.drop(bind)
