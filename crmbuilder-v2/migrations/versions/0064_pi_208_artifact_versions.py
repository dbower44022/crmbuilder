"""PI-208 (PRJ-031) — artifact_versions table (the versioned change spine).

Creates the generic ``artifact_versions`` table (DEC-503) from the ORM
``__table__`` with ``checkfirst`` (idempotent on the create_all-then-upgrade-head
test path). The table is outside the refs / change_log discipline (the version
rows are themselves the audit trail), so there are no CHECK rebuilds. Its
composite FK references ``releases`` (created in 0063). SQLite head 0063 -> 0064;
companion PG delta ``migrations/pg/versions/0021_pi_208_artifact_versions.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import ArtifactVersion

revision: str = "0064_pi_208_artifact_versions"
down_revision: str | None = "0063_pi_205_release_entity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    ArtifactVersion.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    if ArtifactVersion.__tablename__ in _tables():
        ArtifactVersion.__table__.drop(op.get_bind())
