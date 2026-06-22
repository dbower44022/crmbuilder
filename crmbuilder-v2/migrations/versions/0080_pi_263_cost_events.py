"""PI-263 (PRJ-041 / REQ-307) — cost_events table (AI spend telemetry).

Creates the ``cost_events`` table from the ORM ``__table__`` with ``checkfirst``
(idempotent on the create_all-then-upgrade-head test path). One row per AI spend event
(an SDK call or a ``claude -p`` agent invocation): token counts + a computed cost_usd +
nullable attribution tags. A telemetry satellite — outside the refs / change_log
discipline, so no CHECK rebuilds. SQLite head 0079 -> 0080 (chains after the
``0079_pi_262_publish_runs`` head that landed on main in parallel); companion PG delta
``migrations/pg/versions/0037_pi_263_cost_events.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import CostEvent

revision: str = "0080_pi_263_cost_events"
down_revision: str | None = "0079_pi_262_publish_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    CostEvent.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    if CostEvent.__tablename__ in _tables():
        CostEvent.__table__.drop(op.get_bind())
