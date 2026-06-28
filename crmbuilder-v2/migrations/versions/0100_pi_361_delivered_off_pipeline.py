"""PI-361 (REQ-420) — add ``delivered_off_pipeline`` to RELEASE_STATUSES; rebuild ck_release_status.

An honest terminal release status for work delivered outside the release pipeline
(REQ-420): a retroactive container wrapping work merged via normal pull requests
never ran the pipeline stages, so ``shipped`` would claim reviews that did not
happen and ``cancelled`` would claim the delivered work was abandoned. The value
widens the ``ck_release_status`` CHECK on ``releases``, which derives from
``RELEASE_STATUSES``. A superset rebuild — no existing row is invalidated.

SQLite cannot alter a CHECK in place, so this batch-recreates ``releases``. The
partial unique lane index ``uq_releases_one_in_lane`` carries a ``WHERE`` predicate
that Alembic batch reflection can silently drop (turning it into a full unique on
``engagement_id`` — which would wrongly forbid a second release per engagement), so
it is dropped before the batch and recreated explicitly after, with its predicate.

SQLite chain head 0099 -> 0100. Companion PG delta:
``migrations/pg/versions/0057_pi_361_delivered_off_pipeline.py``.

NOTE (live application): the live store (``data/v2-unified.db``) is stamped, so
``crmbuilder-v2-bootstrap-db`` applies this via ``alembic upgrade head`` (idempotent
at head). Verify on a copy of the live DB first per the standard runbook.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import (
    RELEASE_BACK_HALF_MODES,
    RELEASE_EXECUTION_MODES,
    RELEASE_STATUSES,
    _check_in,
)

revision: str = "0100_pi_361_delivered_off_pipeline"
down_revision: str | None = "0099_pi_283_budget_approvals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW = "delivered_off_pipeline"
_STATUSES_NEW = RELEASE_STATUSES
_STATUSES_OLD = RELEASE_STATUSES - {_NEW}

_LANE_INDEX = "uq_releases_one_in_lane"
_LANE_WHERE = (
    "release_status IN ('development','qa','testing','deployment') "
    "AND release_deleted_at IS NULL"
)


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_release_status_check(statuses: frozenset[str]) -> None:
    if "releases" not in _tables():  # absent when the chain is entered mid-stream
        return
    # Drop the partial unique lane index up front: batch recreate reflects indexes,
    # but the ``WHERE`` predicate is not reliably preserved. Recreate it explicitly
    # afterwards so its partiality is guaranteed regardless of reflection.
    op.drop_index(_LANE_INDEX, table_name="releases")
    with op.batch_alter_table("releases") as batch:
        batch.drop_constraint("ck_release_status", type_="check")
        batch.create_check_constraint(
            "ck_release_status", _check_in("release_status", statuses)
        )
        # Alembic batch reflection drops these two later-added IN-based CHECKs
        # (``ck_release_identifier_format`` GLOB and the reflected
        # ``ck_release_status`` survive, but these do not — verified on a copy of
        # the live DB). Re-add them so the rebuilt table keeps every constraint.
        batch.create_check_constraint(
            "ck_release_back_half",
            _check_in("release_back_half", RELEASE_BACK_HALF_MODES),
        )
        batch.create_check_constraint(
            "ck_release_execution_mode",
            _check_in("release_execution_mode", RELEASE_EXECUTION_MODES),
        )
    op.create_index(
        _LANE_INDEX,
        "releases",
        ["engagement_id"],
        unique=True,
        sqlite_where=sa.text(_LANE_WHERE),
    )


def upgrade() -> None:
    _rebuild_release_status_check(_STATUSES_NEW)


def downgrade() -> None:
    # Drop any rows the widened CHECK newly admitted, then restore the old CHECK.
    if "releases" in _tables():
        op.execute(
            "DELETE FROM releases WHERE release_status = 'delivered_off_pipeline'"
        )
    _rebuild_release_status_check(_STATUSES_OLD)
