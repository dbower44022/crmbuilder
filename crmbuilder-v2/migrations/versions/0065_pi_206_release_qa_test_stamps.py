"""PI-206 (PRJ-031) — release-level QA/test gate stamps.

Adds ``release_qa_passed_at`` and ``release_test_passed_at`` to ``releases`` (§8
release-level gates). Both nullable; no CHECK changes. Column-adds are guarded so
the migration is a no-op on a create_all-materialised DB (the test path) where the
columns already exist. SQLite head 0064 -> 0065; companion PG delta
``migrations/pg/versions/0022_pi_206_release_qa_test_stamps.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0065_pi_206_release_qa_test_stamps"
down_revision: str | None = "0064_pi_208_artifact_versions"
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
    to_add = [c for c in _COLUMNS if c not in have]
    if not to_add:
        return
    with op.batch_alter_table("releases") as batch:
        for col in to_add:
            batch.add_column(sa.Column(col, sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    have = _existing_columns()
    to_drop = [c for c in _COLUMNS if c in have]
    if not to_drop:
        return
    with op.batch_alter_table("releases") as batch:
        for col in to_drop:
            batch.drop_column(col)
