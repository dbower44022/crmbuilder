"""PI-297 (REQ-337) — entities.entity_tracks_activities.

Adds the neutral activity-tracking flag (meetings/calls/tasks/emails as linked
activities + history) + its boolean-domain CHECK. The EspoCRM adapter maps it to
the ``BasePlus`` base type; it is DISTINCT from ``entity_track_activity`` (the
stream/feed flag). NOT NULL with a ``0`` server default so existing rows land at
False. Column/CHECK adds go through ``batch_alter_table`` and are inspector-guarded
so the migration is idempotent on a create_all-materialised DB (the test path) and
safe mid-chain. SQLite head 0083 -> 0084; companion PG delta
``migrations/pg/versions/0041_pi_297_entity_tracks_activities.py``. Mirrors 0055.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import _BooleanDomainCheck

revision: str = "0084_pi_297_entity_tracks_activities"
down_revision: str | None = "0083_pi_271_agent_technology"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMN = "entity_tracks_activities"
_CHECK = "ck_entity_tracks_activities_boolean"


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _cols(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _checks(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def upgrade() -> None:
    if "entities" not in _tables():
        return
    have_cols = _cols("entities")
    have_checks = _checks("entities")
    if _COLUMN in have_cols and _CHECK in have_checks:
        return
    with op.batch_alter_table("entities") as batch:
        if _COLUMN not in have_cols:
            batch.add_column(
                sa.Column(
                    _COLUMN, sa.Boolean(), nullable=False, server_default="0"
                )
            )
        if _CHECK not in have_checks:
            batch.create_check_constraint(_CHECK, _BooleanDomainCheck(_COLUMN))


def downgrade() -> None:
    if "entities" not in _tables() or _COLUMN not in _cols("entities"):
        return
    with op.batch_alter_table("entities") as batch:
        if _CHECK in _checks("entities"):
            batch.drop_constraint(_CHECK, type_="check")
        batch.drop_column(_COLUMN)
