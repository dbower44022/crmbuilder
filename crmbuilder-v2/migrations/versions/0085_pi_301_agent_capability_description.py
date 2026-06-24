"""PI-301 (PRJ-039 / DEC-677) — agent_profiles.capability_description.

Adds a nullable JSON capability description so agents are located by a searchable
capability object (``{summary, specialties, builds, constraints}``) rather than only
by their ``(area, tier)`` key. SEPARATE from ``description`` (the system prompt). A
plain nullable add-column — no refs/change_log CHECK rebuild is needed (not a new
entity type or relationship kind). The add is inspector-guarded so the migration is
a no-op on a create_all-materialised DB (the test path) and safe mid-chain. SQLite
head 0084 -> 0085; companion PG delta
``migrations/pg/versions/0042_pi_301_agent_capability_description.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0085_pi_301_agent_capability_description"
down_revision: str | None = "0084_pi_297_entity_tracks_activities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMN = "capability_description"


def _cols(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if "agent_profiles" not in sa.inspect(op.get_bind()).get_table_names():
        return
    if _COLUMN not in _cols("agent_profiles"):
        with op.batch_alter_table("agent_profiles") as batch:
            batch.add_column(sa.Column(_COLUMN, sa.JSON(), nullable=True))


def downgrade() -> None:
    if _COLUMN in _cols("agent_profiles"):
        with op.batch_alter_table("agent_profiles") as batch:
            batch.drop_column(_COLUMN)
