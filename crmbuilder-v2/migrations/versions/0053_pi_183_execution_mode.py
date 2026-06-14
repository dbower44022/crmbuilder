"""PI-183 — ADO execution_mode gate on projects + planning_items.

Implements the storage slice of PRJ-026 / PI-183 (DEC-423..425): the structural
risk gate that replaces the fragile "don't point the ADO there" convention with
an enforced field.

- adds ``project_execution_mode`` to ``projects`` (NOT NULL, server-default
  ``ado``) plus its ``ck_project_execution_mode`` CHECK;
- adds ``execution_mode`` (NOT NULL, server-default ``ado``) and
  ``dispatch_approved`` (NOT NULL boolean, server-default ``0``) to
  ``planning_items`` plus their ``ck_planning_execution_mode`` /
  ``ck_planning_dispatch_approved`` CHECKs.

No new entity types or refs kinds, so ``ck_changelog_entity_type`` and the
``refs`` CHECKs are untouched. CHECK predicates derive from the current vocab so
they cannot drift from the models. The column / CHECK adds are guarded against
the create_all-then-upgrade-head test path (the columns already exist there),
mirroring 0049, and the ``_tables()`` guard keeps the migration safe when the
chain is entered mid-stream (the stamp-0036 isolated path).

SQLite chain head 0052 -> 0053. Companion PG-chain delta:
``migrations/pg/versions/0015_pi_183_execution_mode.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import EXECUTION_MODES, _check_in

revision: str = "0053_pi_183_execution_mode"
down_revision: str | None = "0052_pi_161_service_entity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (column name, kwargs) for the new columns, keyed by table.
_PROJECT_COLUMNS: tuple[tuple[str, dict], ...] = (
    (
        "project_execution_mode",
        {
            "type_": sa.String(20),
            "nullable": False,
            "server_default": sa.text("'ado'"),
        },
    ),
)
_PLANNING_COLUMNS: tuple[tuple[str, dict], ...] = (
    (
        "execution_mode",
        {
            "type_": sa.String(20),
            "nullable": False,
            "server_default": sa.text("'ado'"),
        },
    ),
    (
        "dispatch_approved",
        {
            "type_": sa.Boolean(),
            "nullable": False,
            "server_default": sa.text("0"),
        },
    ),
)
# (check name, raw SQL predicate) per table.
_PROJECT_CHECKS: tuple[tuple[str, str], ...] = (
    ("ck_project_execution_mode", _check_in("project_execution_mode", EXECUTION_MODES)),
)
_PLANNING_CHECKS: tuple[tuple[str, str], ...] = (
    ("ck_planning_execution_mode", _check_in("execution_mode", EXECUTION_MODES)),
    ("ck_planning_dispatch_approved", "dispatch_approved IN (0, 1)"),
)


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _checks(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def _add(table: str, columns, checks) -> None:
    if table not in _tables():
        return
    have_cols = _columns(table)
    have_checks = _checks(table)
    missing_cols = [c for c in columns if c[0] not in have_cols]
    missing_checks = [c for c in checks if c[0] not in have_checks]
    if not (missing_cols or missing_checks):
        return
    with op.batch_alter_table(table) as batch:
        for name, kwargs in missing_cols:
            batch.add_column(sa.Column(name, **kwargs))
        for ck_name, predicate in missing_checks:
            batch.create_check_constraint(ck_name, predicate)


def _drop(table: str, columns, checks) -> None:
    if table not in _tables():
        return
    have_checks = _checks(table)
    have_cols = _columns(table)
    with op.batch_alter_table(table) as batch:
        for ck_name, _predicate in checks:
            if ck_name in have_checks:
                batch.drop_constraint(ck_name, type_="check")
        for name, _kwargs in reversed(columns):
            if name in have_cols:
                batch.drop_column(name)


def upgrade() -> None:
    _add("projects", _PROJECT_COLUMNS, _PROJECT_CHECKS)
    _add("planning_items", _PLANNING_COLUMNS, _PLANNING_CHECKS)


def downgrade() -> None:
    _drop("planning_items", _PLANNING_COLUMNS, _PLANNING_CHECKS)
    _drop("projects", _PROJECT_COLUMNS, _PROJECT_CHECKS)
