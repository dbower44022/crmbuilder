"""PI-301 (PG chain) — agent_profiles.capability_description.

Companion to the SQLite-chain ``0085``. Adds the nullable JSON capability
description (``{summary, specialties, builds, constraints}``) on Postgres
deployments materialised from an earlier baseline; rendered as ``JSONB`` to match
the model's ``JSONColumnNoneAsNull`` variant. The PG baseline is ``create_all`` from
the live models, so a fresh PG DB already carries the column — the add is
inspector-guarded. Chains after ``0041_pi_297_entity_tracks_activities``. Never
replay the SQLite chain on Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0042_pi_301_agent_capability_description"
down_revision: str | None = "0041_pi_297_entity_tracks_activities"
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
        op.add_column(
            "agent_profiles",
            sa.Column(_COLUMN, JSONB(none_as_null=True), nullable=True),
        )


def downgrade() -> None:
    if _COLUMN in _cols("agent_profiles"):
        op.drop_column("agent_profiles", _COLUMN)
