"""PI-262 (PG chain) — publish_runs table.

Companion to the SQLite-chain ``0079``. Creates the ``publish_runs`` table (a
lean engagement-scoped log of publishes to a target instance — pre-publish
backup + scope/status/outcome, REQ-292+293) on Postgres deployments
materialised from an earlier baseline. The PG baseline is ``create_all`` from
the live models, so a fresh PG DB already carries it — the create is
inspector-guarded. Never replay the SQLite chain on Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import PublishRun

revision: str = "0036_pi_262_publish_runs"
down_revision: str | None = "0035_pi_249_release_back_half"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if PublishRun.__tablename__ not in _tables():
        PublishRun.__table__.create(bind)


def downgrade() -> None:
    if PublishRun.__tablename__ in _tables():
        PublishRun.__table__.drop(op.get_bind())
