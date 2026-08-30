"""PI-406 (REQ-485 / DEC-918, PG chain) — governed system settings with per-instance values.

Every other design record describes something every instance must hold
identically. A system setting is the one construct whose value is per instance:
an outbound email address differing between Cleveland and another chapter is not
drift, it is Cleveland's. The design governs *which* settings exist and what
shape their values take; each instance carries its own value.

**Two tables.**

``system_settings`` is the governed declaration — ``SET-NNN``, the key the CRM
itself uses, the value's shape, and the standard propose-verify status. A
setting the design does not name is not reported at all (REQ-485), so this table
is also the definition of what reconcile looks at. ``system_setting_value_type``
is CHECKed against ``FIELD_TYPES`` rather than a parallel vocabulary: PI-414
made that vocabulary able to describe any value a CRM can hold, and a setting's
value is such a value.

``system_setting_values`` holds the value each instance is declared to hold —
intent, not observation. Keeping declared apart from observed is what lets
reconcile tell "holds the wrong value" from "nobody has said what this instance
should hold"; the second is REQ-485's third outcome and must never read as
conformant. **Absence of a row is meaningful** and is the normal starting state,
so no row is created empty to stand in for a decision not yet taken.

**Both CHECKs move**, per the standing lesson that a new entity type needs them
together: ``ENTITY_TYPES`` gains ``system_setting``, so the ``refs``
source/target CHECKs and the ``change_log`` entity-type CHECK are rebuilt from
the current vocabulary. All are supersets — no existing row is invalidated. Each
rebuild is inspector-guarded so the chain is safe to enter mid-stream.

The instance-membership member type is deliberately NOT added here. Nothing
audits a setting yet; adding the member type before the reconcile that populates
it would admit a state no writer can produce.

PG chain head 0080 -> 0081. Companion SQLite-chain delta:
``migrations/versions/0124_pi_406_system_settings.py``.

NOTE (live application): the live store is create_all-managed and is NOT walked
through this PG chain. This migration is the canonical record of the delta;
the live application goes through ``crmbuilder-v2-bootstrap-db``, verified on a
copy first, and is performed by Doug (GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    FIELD_TYPES,
    SYSTEM_SETTING_STATUSES,
    _check_in,
)

revision: str = "0081_pi_406_system_settings"
down_revision: str | None = "0080_pi_419_deploy_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPE = "system_setting"
_ENTITY_TYPES_OLD = ENTITY_TYPES - {_NEW_TYPE}
_CHANGELOG_OLD = CHANGE_LOG_ENTITY_TYPES - {_NEW_TYPE}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_ref_checks(entity_types: frozenset[str]) -> None:
    if "refs" not in _tables():  # absent when the chain is entered mid-stream
        return
    with op.batch_alter_table("refs") as batch:
        batch.drop_constraint("ck_ref_source_type", type_="check")
        batch.create_check_constraint(
            "ck_ref_source_type", _check_in("source_type", entity_types)
        )
        batch.drop_constraint("ck_ref_target_type", type_="check")
        batch.create_check_constraint(
            "ck_ref_target_type", _check_in("target_type", entity_types)
        )


def _rebuild_changelog_check(entity_types: frozenset[str]) -> None:
    if "change_log" not in _tables():
        return
    with op.batch_alter_table("change_log") as batch:
        batch.drop_constraint("ck_changelog_entity_type", type_="check")
        batch.create_check_constraint(
            "ck_changelog_entity_type", _check_in("entity_type", entity_types)
        )


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("system_setting_identifier", sa.String(32), nullable=False),
        sa.Column("engagement_id", sa.String(32), nullable=False),
        sa.Column("system_setting_key", sa.String(255), nullable=False),
        sa.Column("system_setting_name", sa.String(255), nullable=False),
        sa.Column("system_setting_value_type", sa.String(32), nullable=False),
        sa.Column("system_setting_description", sa.Text(), nullable=True),
        sa.Column("system_setting_notes", sa.Text(), nullable=True),
        sa.Column("system_setting_status", sa.String(16), nullable=False),
        sa.Column(
            "system_setting_created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "system_setting_updated_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "system_setting_deleted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.PrimaryKeyConstraint("system_setting_identifier", "engagement_id"),
        sa.CheckConstraint(
            _check_in("system_setting_value_type", FIELD_TYPES),
            name="ck_system_setting_value_type",
        ),
        sa.CheckConstraint(
            _check_in("system_setting_status", SYSTEM_SETTING_STATUSES),
            name="ck_system_setting_status",
        ),
        sa.UniqueConstraint(
            "engagement_id", "system_setting_key", name="uq_system_setting_key"
        ),
    )
    op.create_index(
        "ix_system_settings_system_setting_status",
        "system_settings",
        ["system_setting_status"],
    )
    op.create_index(
        "ix_system_settings_system_setting_deleted_at",
        "system_settings",
        ["system_setting_deleted_at"],
    )

    op.create_table(
        "system_setting_values",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("engagement_id", sa.String(32), nullable=False),
        sa.Column("system_setting_identifier", sa.String(32), nullable=False),
        sa.Column("instance_identifier", sa.String(32), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["engagement_id", "instance_identifier"],
            ["instances.engagement_id", "instances.instance_identifier"],
            ondelete="CASCADE",
            name="fk_system_setting_values_instance",
        ),
        sa.UniqueConstraint(
            "engagement_id",
            "system_setting_identifier",
            "instance_identifier",
            name="uq_system_setting_value",
        ),
    )
    op.create_index(
        "ix_system_setting_values_setting",
        "system_setting_values",
        ["system_setting_identifier"],
    )

    _rebuild_ref_checks(ENTITY_TYPES)
    _rebuild_changelog_check(CHANGE_LOG_ENTITY_TYPES)


def downgrade() -> None:
    _rebuild_changelog_check(_CHANGELOG_OLD)
    _rebuild_ref_checks(_ENTITY_TYPES_OLD)
    op.drop_index(
        "ix_system_setting_values_setting", table_name="system_setting_values"
    )
    op.drop_table("system_setting_values")
    op.drop_index(
        "ix_system_settings_system_setting_deleted_at", table_name="system_settings"
    )
    op.drop_index(
        "ix_system_settings_system_setting_status", table_name="system_settings"
    )
    op.drop_table("system_settings")
