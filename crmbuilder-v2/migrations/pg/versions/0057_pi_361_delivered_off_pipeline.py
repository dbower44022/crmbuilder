"""PI-361 (PG chain) — add ``delivered_off_pipeline`` to RELEASE_STATUSES; rebuild ck_release_status.

Companion to the SQLite-chain ``0100``. An honest terminal release status for work
delivered outside the release pipeline (REQ-420): a retroactive container wrapping
work merged via normal pull requests never ran the pipeline stages, so ``shipped``
would claim reviews that did not happen and ``cancelled`` would claim the delivered
work was abandoned. Only the ``ck_release_status`` CHECK moves — it derives from
``RELEASE_STATUSES``. A superset rebuild, so no existing row is invalidated. PG
alters the CHECK directly (no table recreate, no partial-index handling needed).

PG chain head 0056 -> 0057.
"""

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.access.vocab import RELEASE_STATUSES, _check_in

revision: str = "0057_pi_361_delivered_off_pipeline"
down_revision: str | None = "0056_pi_283_budget_approvals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW = "delivered_off_pipeline"
_STATUSES_NEW = RELEASE_STATUSES
_STATUSES_OLD = RELEASE_STATUSES - {_NEW}


def _rebuild_release_status_check(statuses: frozenset[str]) -> None:
    op.drop_constraint("ck_release_status", "releases", type_="check")
    op.create_check_constraint(
        "ck_release_status", "releases", _check_in("release_status", statuses)
    )


def upgrade() -> None:
    _rebuild_release_status_check(_STATUSES_NEW)


def downgrade() -> None:
    op.execute(
        "DELETE FROM releases WHERE release_status = 'delivered_off_pipeline'"
    )
    _rebuild_release_status_check(_STATUSES_OLD)
