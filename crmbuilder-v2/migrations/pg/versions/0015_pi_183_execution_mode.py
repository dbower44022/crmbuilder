"""PI-183 (PG chain) — ADO execution_mode gate on projects + planning_items.

Companion to the SQLite-chain ``0053``. Adds ``project_execution_mode`` to
``projects`` and ``execution_mode`` + ``dispatch_approved`` to
``planning_items``, with their CHECKs, on Postgres deployments materialised from
an earlier baseline.

The PG baseline (``0001_pg_baseline``) is ``Base.metadata.create_all`` from the
live ORM models, so a freshly-built PG DB already carries the new columns and
the vocab-derived CHECK predicates — the adds are inspector-guarded and no-op
there; on a pre-existing PG store they are real changes. Never replay the SQLite
chain on a Postgres DB; the two files are siblings, not a sequence.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import EXECUTION_MODES, _check_in

revision: str = "0015_pi_183_execution_mode"
down_revision: str | None = "0014_pi_161_service_entity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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
            "server_default": sa.text("false"),
        },
    ),
)
_PROJECT_CHECKS: tuple[tuple[str, str], ...] = (
    ("ck_project_execution_mode", _check_in("project_execution_mode", EXECUTION_MODES)),
)
_PLANNING_CHECKS: tuple[tuple[str, str], ...] = (
    ("ck_planning_execution_mode", _check_in("execution_mode", EXECUTION_MODES)),
    ("ck_planning_dispatch_approved", "dispatch_approved IN (true, false)"),
)


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _checks(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def _add(table: str, columns, checks) -> None:
    have_cols = _columns(table)
    have_checks = _checks(table)
    for name, kwargs in columns:
        if name not in have_cols:
            op.add_column(table, sa.Column(name, **kwargs))
    for ck_name, predicate in checks:
        if ck_name not in have_checks:
            op.create_check_constraint(ck_name, table, predicate)


def _drop(table: str, columns, checks) -> None:
    have_cols = _columns(table)
    have_checks = _checks(table)
    for ck_name, _predicate in checks:
        if ck_name in have_checks:
            op.drop_constraint(ck_name, table, type_="check")
    for name, _kwargs in reversed(columns):
        if name in have_cols:
            op.drop_column(table, name)


def upgrade() -> None:
    _add("projects", _PROJECT_COLUMNS, _PROJECT_CHECKS)
    _add("planning_items", _PLANNING_COLUMNS, _PLANNING_CHECKS)


def downgrade() -> None:
    _drop("planning_items", _PLANNING_COLUMNS, _PLANNING_CHECKS)
    _drop("projects", _PROJECT_COLUMNS, _PROJECT_CHECKS)
