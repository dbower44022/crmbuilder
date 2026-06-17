"""PI-206 (PG chain) — release-level QA/test gate stamps.

Companion to the SQLite-chain ``0065``. Adds ``release_qa_passed_at`` and
``release_test_passed_at`` to ``releases`` on Postgres deployments materialised
from an earlier baseline. Column-adds are guarded (no-op when create_all already
made them). Never replay the SQLite chain on Postgres; siblings, not a sequence.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_pi_206_release_qa_test_stamps"
down_revision: str | None = "0021_pi_208_artifact_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("release_qa_passed_at", "release_test_passed_at")


def _existing_columns() -> set[str]:
    insp = sa.inspect(op.get_bind())
    if "releases" not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns("releases")}


def upgrade() -> None:
    have = _existing_columns()
    for col in (c for c in _COLUMNS if c not in have):
        op.add_column(
            "releases", sa.Column(col, sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    have = _existing_columns()
    for col in (c for c in _COLUMNS if c in have):
        op.drop_column("releases", col)
