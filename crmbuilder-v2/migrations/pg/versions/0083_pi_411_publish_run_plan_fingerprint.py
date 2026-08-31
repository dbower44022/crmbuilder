"""PI-411 (REQ-496 / DEC-924, PG chain) — a publish run records the plan it applied.

REQ-496 requires the identity of the plan actually applied to be recorded so it
can be answered for afterwards, and the stamp written to the instance carries
the same identity — which is what lets "what is this instance running" be
checked against "what did we apply" rather than taken on trust.

One nullable column, ``publish_run_plan_fingerprint``. DEC-924 put it on this
row rather than in a new record: publish_runs already carries the run's
pre-publish backup and outcome summary, and a second record describing the same
run is a second thing that can disagree about what that run did.

NULL on every existing row and not backfilled. A run that predates plan identity
did not have one, and inventing a fingerprint for it would assert that some
specific plan was applied when nobody recorded which — the same failure the
column exists to prevent.

Additive and nullable, so no existing row is invalidated. No CHECK: the value is
a hex digest the access layer computes, not a vocabulary an operator picks.

PG chain head 0082 -> 0083. Companion SQLite-chain delta:
``migrations/versions/0126_pi_411_publish_run_plan_fingerprint.py``.

NOTE (live application): the live store is create_all-managed and is NOT walked
through this PG chain. This migration is the canonical record of the delta;
the live application goes through ``crmbuilder-v2-bootstrap-db``, verified on a
copy first, and is performed by Doug (GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0083_pi_411_publish_run_plan_fingerprint"
down_revision: str | None = "0082_pi_438_rule_audience_moment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "publish_runs",
        sa.Column("publish_run_plan_fingerprint", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("publish_runs", "publish_run_plan_fingerprint")
