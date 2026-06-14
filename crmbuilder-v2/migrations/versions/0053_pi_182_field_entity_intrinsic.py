"""PI-182 — intrinsic engine-neutral design-intent columns + field_options.

PRJ-025 (engine-neutral CRM design model) Phase PI-B. Adds the intrinsic
neutral design-intent attributes from
``engine-neutral-design-model-and-adapters.md`` §6/§7 to the existing
methodology records, plus the ``field_options`` child collection (§8):

- ``entities`` gains ``entity_default_sort_field`` (TEXT NULL),
  ``entity_default_sort_direction`` (TEXT NULL), and
  ``entity_track_activity`` (BOOLEAN NOT NULL default 0) + its domain CHECK.
- ``fields`` gains ``field_tooltip``, ``field_usage_summary``,
  ``field_default_value``, ``field_format``, ``field_numeric_scale`` (all
  TEXT NULL), ``field_max_length`` (INTEGER NULL), ``field_min`` /
  ``field_max`` (TEXT NULL), and ``field_read_only`` / ``field_unique`` /
  ``field_externally_populated`` (BOOLEAN NOT NULL default 0) + their
  domain CHECKs.
- a new ``field_options`` table — a plain engagement-scoped child of
  ``fields`` (NOT a prefixed-identifier entity, NOT a ``change_log``
  entity type), with a composite FK to the parent's
  ``(engagement_id, field_identifier)`` PK and a unique
  ``(engagement_id, field_identifier, option_value)`` constraint.

PI-B adds **no** new ``entity_type`` and **no** new ``relationship_kind``,
so ``ck_changelog_entity_type`` and ``ck_ref_relationship`` are left
untouched (the field_options collection is captured inside the parent
field's change-log payload).

Migration shape mirrors 0049: column adds and new CHECKs go through
``batch_alter_table`` (so the NOT-NULL booleans pick up their
``server_default`` for existing rows, and the SQLite table recreate
preserves the existing CHECKs/indexes). The ``fields`` and ``entities``
tables carry only plain column indexes — **no expression indexes** — so
the SQLite batch recreate drops nothing that needs restoring (cf. the
0040 expression-index regression fixed in 08280ed1). Every table touch is
guarded by a ``get_table_names`` check so the migration is safe when the
chain is entered mid-stream (the stamp-0036 isolated path).

SQLite chain head 0052 -> 0053. There is no companion PG-chain delta: the
PG tree (``migrations/pg/``) is a single ``create_all`` baseline that
already materialises the current models, so it grows its own chain only
when a PG deployment is rehearsed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import _BooleanDomainCheck

revision: str = "0053_pi_182_field_entity_intrinsic"
down_revision: str | None = "0052_pi_161_service_entity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (column name, kwargs) tuples for the new methodology columns. The three
# NOT-NULL booleans carry ``server_default="0"`` so existing rows get a
# defined value under the new constraint; the model-side default is the
# Python-level ``default=False``.
_ENTITY_COLUMNS: tuple[tuple[str, dict], ...] = (
    ("entity_default_sort_field", {"type_": sa.Text(), "nullable": True}),
    ("entity_default_sort_direction", {"type_": sa.Text(), "nullable": True}),
    (
        "entity_track_activity",
        {"type_": sa.Boolean(), "nullable": False, "server_default": "0"},
    ),
)
_ENTITY_CHECKS: tuple[tuple[str, str], ...] = (
    ("ck_entity_track_activity_boolean", "entity_track_activity"),
)

_FIELD_COLUMNS: tuple[tuple[str, dict], ...] = (
    ("field_tooltip", {"type_": sa.Text(), "nullable": True}),
    ("field_usage_summary", {"type_": sa.Text(), "nullable": True}),
    ("field_default_value", {"type_": sa.Text(), "nullable": True}),
    ("field_format", {"type_": sa.Text(), "nullable": True}),
    ("field_numeric_scale", {"type_": sa.Text(), "nullable": True}),
    ("field_max_length", {"type_": sa.Integer(), "nullable": True}),
    ("field_min", {"type_": sa.Text(), "nullable": True}),
    ("field_max", {"type_": sa.Text(), "nullable": True}),
    (
        "field_read_only",
        {"type_": sa.Boolean(), "nullable": False, "server_default": "0"},
    ),
    (
        "field_unique",
        {"type_": sa.Boolean(), "nullable": False, "server_default": "0"},
    ),
    (
        "field_externally_populated",
        {"type_": sa.Boolean(), "nullable": False, "server_default": "0"},
    ),
)
_FIELD_CHECKS: tuple[tuple[str, str], ...] = (
    ("ck_field_read_only_boolean", "field_read_only"),
    ("ck_field_unique_boolean", "field_unique"),
    ("ck_field_externally_populated_boolean", "field_externally_populated"),
)


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _checks(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def _add_columns_and_checks(
    table: str,
    new_columns: tuple[tuple[str, dict], ...],
    new_checks: tuple[tuple[str, str], ...],
) -> None:
    """Add any missing columns + boolean-domain CHECKs to ``table``.

    Idempotent against the create_all-then-upgrade-head test path (the
    columns/CHECKs already exist there) and safe mid-chain (skips an
    absent table). The boolean ``server_default`` fills existing rows.
    """
    if table not in _tables():
        return
    have_cols = _columns(table)
    have_checks = _checks(table)
    missing_cols = [c for c in new_columns if c[0] not in have_cols]
    missing_checks = [c for c in new_checks if c[0] not in have_checks]
    if not missing_cols and not missing_checks:
        return
    with op.batch_alter_table(table) as batch:
        for name, kwargs in missing_cols:
            batch.add_column(sa.Column(name, **kwargs))
        for ck_name, column in missing_checks:
            batch.create_check_constraint(ck_name, _BooleanDomainCheck(column))


def _create_field_options() -> None:
    existing = _tables()
    # The parent must exist (mid-chain guard) and the child must not.
    if "fields" not in existing or "field_options" in existing:
        return
    op.create_table(
        "field_options",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "engagement_id",
            sa.String(length=32),
            sa.ForeignKey("engagements.engagement_identifier"),
            nullable=False,
        ),
        sa.Column("field_identifier", sa.String(length=32), nullable=False),
        sa.Column("option_value", sa.Text(), nullable=False),
        sa.Column("option_label", sa.Text(), nullable=True),
        sa.Column(
            "option_order", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.ForeignKeyConstraint(
            ["engagement_id", "field_identifier"],
            ["fields.engagement_id", "fields.field_identifier"],
            ondelete="CASCADE",
            name="fk_field_options_parent",
        ),
        sa.UniqueConstraint(
            "engagement_id",
            "field_identifier",
            "option_value",
            name="uq_field_option_value",
        ),
    )
    op.create_index(
        "ix_field_options_parent",
        "field_options",
        ["engagement_id", "field_identifier"],
    )


def upgrade() -> None:
    _add_columns_and_checks("entities", _ENTITY_COLUMNS, _ENTITY_CHECKS)
    _add_columns_and_checks("fields", _FIELD_COLUMNS, _FIELD_CHECKS)
    _create_field_options()


def _drop_columns_and_checks(
    table: str,
    new_columns: tuple[tuple[str, dict], ...],
    new_checks: tuple[tuple[str, str], ...],
) -> None:
    if table not in _tables():
        return
    with op.batch_alter_table(table) as batch:
        for ck_name, _column in new_checks:
            batch.drop_constraint(ck_name, type_="check")
        for name, _kwargs in reversed(new_columns):
            batch.drop_column(name)


def downgrade() -> None:
    # Drop the child collection first so the parent ``fields`` recreate has
    # no inbound FK to break.
    if "field_options" in _tables():
        op.drop_index("ix_field_options_parent", table_name="field_options")
        op.drop_table("field_options")
    _drop_columns_and_checks("fields", _FIELD_COLUMNS, _FIELD_CHECKS)
    _drop_columns_and_checks("entities", _ENTITY_COLUMNS, _ENTITY_CHECKS)
