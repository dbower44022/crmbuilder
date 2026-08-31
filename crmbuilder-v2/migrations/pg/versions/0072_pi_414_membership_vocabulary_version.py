"""PI-414 (REQ-504 / DEC-930, PG chain) — a stored verdict names the vocabulary that produced it.

The design's field vocabulary now carries a version, and a stored comparison
result has to say which version computed it. Without that, re-reading an old
membership row silently claims agreement with a vocabulary the row never saw —
and PI-414 changed the vocabulary four times, so rows written across that work
disagree with each other for reasons no reader can see.

One nullable column on ``instance_memberships``: ``vocabulary_version``. NULL is
meaningful and is the correct value for every existing row — it reads as
"produced before the vocabulary was versioned", which is exactly true and is
what keeps results from before a change distinguishable from those after
(REQ-504's second acceptance clause). Backfilling a number onto those rows would
assert a provenance nobody observed.

Nullable and additive, so no existing row can be invalidated. No CHECK: the
value is an integer the access layer stamps from a single constant, not a
vocabulary an operator picks.

The stamp is applied in ``upsert_membership`` rather than at each call site, so
a verdict cannot be written without one — a row that forgot its version is
indistinguishable from a pre-versioning row, which would quietly undo the
distinction this column exists to make.

PG chain head 0071 -> 0072. Companion SQLite-chain delta:
``migrations/versions/0115_pi_414_membership_vocabulary_version.py``.

NOTE (live application): the live store is create_all-managed and is NOT walked
through this PG chain. This migration is the canonical record of the delta;
the live application goes through ``crmbuilder-v2-bootstrap-db``, verified on a
copy first, and is performed by Doug (GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0072_pi_414_membership_vocabulary_version"
down_revision: str | None = "0071_pi_414_many_to_one_cardinality"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table not in set(inspector.get_table_names()):
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    # A schema materialised from the current ORM models already carries this
    # column, so the add is guarded — a clean no-op there, a real delta on a
    # database that predates it.
    if not _has_column("instance_memberships", "vocabulary_version"):
        op.add_column(
            "instance_memberships",
            sa.Column("vocabulary_version", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    if _has_column("instance_memberships", "vocabulary_version"):
        op.drop_column("instance_memberships", "vocabulary_version")
