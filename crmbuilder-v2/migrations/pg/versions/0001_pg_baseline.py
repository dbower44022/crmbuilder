"""PI-alpha — Postgres baseline: the full strict schema from the ORM models.

The Postgres store starts from a single baseline materialised directly from
``Base.metadata`` (``create_all``), rather than replaying the SQLite batch-mode
chain (``crmbuilder-v2/migrations/`` 0001-0039), which encodes SQLite-shaped
intermediate states with no clean Postgres analogue. This mirrors the v0.1
posture where the baseline *is* ``create_all``. Postgres grows its own forward
chain from this revision; future PG schema changes are hand-written deltas here.

The models already render correctly on Postgres (JSONB via dialect variants,
``~`` regex / ``jsonb_*`` / boolean-domain CHECK constructs, composite keys, FKs,
partial-unique indexes) — see ``pi-alpha-postgres-foundation-architecture.md``.
"""

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.access.models import Base

revision: str = "0001_pg_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
