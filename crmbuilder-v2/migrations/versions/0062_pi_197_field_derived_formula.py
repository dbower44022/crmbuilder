"""PI-197 — derived/formula columns on ``fields`` (PRJ-025, DEC-438).

PRJ-025 (engine-neutral CRM design model) Phase PI-197. Adds the two
neutral derived-field attributes from
``engine-neutral-design-model-and-adapters.md`` §7/§9 so a ``derived``
field carries the value-type its formula yields and the formula itself:

- ``fields`` gains ``field_derived_result_type`` (TEXT NULL) — the
  value-shape the formula produces, validated against
  ``DERIVED_RESULT_TYPES`` at the access layer (required when
  ``field_type`` is ``derived``, NULL otherwise).
- ``fields`` gains ``field_formula`` (JSON NULL) — the neutral structured
  formula AST (``access.formulas`` shape), validated at the access layer
  when present.

Both columns are nullable, so neither carries a ``server_default`` and
there is no boolean-domain CHECK. PI-197 adds **no** new ``entity_type``
and **no** new ``relationship_kind``, so ``ck_changelog_entity_type`` and
``ck_ref_relationship`` are left untouched.

Migration shape mirrors 0055: the column adds go through
``batch_alter_table`` (the SQLite table recreate preserves the existing
CHECKs/indexes). The ``fields`` table carries only plain column indexes —
no expression indexes — so the SQLite batch recreate drops nothing that
needs restoring. The table touch is guarded by a ``get_table_names`` check
so the migration is safe mid-chain (the stamp-0036 isolated path) and
idempotent against the create_all-then-upgrade-head test path.

SQLite chain head 0061 -> 0062. There is no companion PG-chain delta: the
PG tree (``migrations/pg/``) is a single ``create_all`` baseline that
already materialises the current models, so it grows its own chain only
when a PG deployment is rehearsed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import JSONColumn

revision: str = "0062_pi_197_field_derived_formula"
down_revision: str | None = "0061_pi_195_filtered_tab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (column name, kwargs) tuples for the two new ``derived`` columns. Both
# nullable, so no ``server_default`` and no CHECK — the cross-field /
# AST-shape validation lives at the access layer.
_FIELD_COLUMNS: tuple[tuple[str, dict], ...] = (
    ("field_derived_result_type", {"type_": sa.Text(), "nullable": True}),
    ("field_formula", {"type_": JSONColumn, "nullable": True}),
)


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _add_columns(
    table: str, new_columns: tuple[tuple[str, dict], ...]
) -> None:
    """Add any missing columns to ``table``.

    Idempotent against the create_all-then-upgrade-head test path (the
    columns already exist there) and safe mid-chain (skips an absent
    table).
    """
    if table not in _tables():
        return
    have_cols = _columns(table)
    missing_cols = [c for c in new_columns if c[0] not in have_cols]
    if not missing_cols:
        return
    with op.batch_alter_table(table) as batch:
        for name, kwargs in missing_cols:
            batch.add_column(sa.Column(name, **kwargs))


def upgrade() -> None:
    _add_columns("fields", _FIELD_COLUMNS)


def downgrade() -> None:
    if "fields" not in _tables():
        return
    with op.batch_alter_table("fields") as batch:
        for name, _kwargs in reversed(_FIELD_COLUMNS):
            batch.drop_column(name)
