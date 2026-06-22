"""PI-262 (PRJ-042 / REQ-292+REQ-293) — publish_runs table.

Creates the ``publish_runs`` table from the ORM ``__table__`` with
``checkfirst`` (idempotent on the create_all-then-upgrade-head test path). A
lean engagement-scoped operational log of publishes to a target instance: each
row carries a pre-publish JSON backup of the target (REQ-292) plus the run's
scope / status / timing / outcome summary (REQ-293). Outside the refs /
change_log discipline, so no CHECK rebuilds. SQLite head 0078 -> 0079; companion
PG delta ``migrations/pg/versions/0036_pi_262_publish_runs.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import PublishRun

revision: str = "0079_pi_262_publish_runs"
down_revision: str | None = "0078_pi_249_release_back_half"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    PublishRun.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    if PublishRun.__tablename__ in _tables():
        PublishRun.__table__.drop(op.get_bind())
