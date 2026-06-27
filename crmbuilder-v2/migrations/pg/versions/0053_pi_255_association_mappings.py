"""PI-255 (PG chain) — association_mappings table.

Companion to the SQLite-chain ``0096`` (DEC-654). Creates the
``association_mappings`` table on a Postgres deployment materialised from an
earlier baseline. The PG baseline is ``create_all`` from the live models, so a
fresh PG DB already carries the table (and its CHECKs, derived from current
vocab) — the create is a ``checkfirst``-guarded no-op there. Never replay the
SQLite chain on Postgres.
"""

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.access.models import AssociationMapping
from sqlalchemy import inspect

revision: str = "0053_pi_255_association_mappings"
down_revision: str | None = "0052_pi_255_drop_membership_candidate_states"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    AssociationMapping.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    if AssociationMapping.__tablename__ in set(
        inspect(bind).get_table_names()
    ):
        AssociationMapping.__table__.drop(bind)
