"""PI-297 (REQ-337, PG chain) — entities.entity_tracks_activities.

Companion to the SQLite-chain ``0084``. Adds the neutral activity-tracking flag
(EspoCRM ``BasePlus``) + its boolean-domain CHECK on Postgres deployments
materialised from an earlier baseline. The PG baseline is ``create_all`` from the
live models, so a fresh PG DB already carries both — the adds are inspector-guarded.
NOT NULL with a ``false`` server default. The CHECK uses the same
``_BooleanDomainCheck`` construct as the model so it renders identically to
create_all. Chains after ``0040_pi_271_agent_technology``. Never replay the SQLite
chain on Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import _BooleanDomainCheck

revision: str = "0041_pi_297_entity_tracks_activities"
down_revision: str | None = "0040_pi_271_agent_technology"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMN = "entity_tracks_activities"
_CHECK = "ck_entity_tracks_activities_boolean"


def _cols(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _checks(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def upgrade() -> None:
    if _COLUMN not in _cols("entities"):
        op.add_column(
            "entities",
            sa.Column(
                _COLUMN, sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
        )
    if _CHECK not in _checks("entities"):
        op.create_check_constraint(_CHECK, "entities", _BooleanDomainCheck(_COLUMN))


def downgrade() -> None:
    if _CHECK in _checks("entities"):
        op.drop_constraint(_CHECK, "entities", type_="check")
    if _COLUMN in _cols("entities"):
        op.drop_column("entities", _COLUMN)
