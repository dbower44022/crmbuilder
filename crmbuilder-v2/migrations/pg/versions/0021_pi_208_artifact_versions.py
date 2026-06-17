"""PI-208 (PG chain) — artifact_versions table.

Companion to the SQLite-chain ``0064``. Creates the generic ``artifact_versions``
table (DEC-503) on Postgres deployments materialised from an earlier baseline.
The PG baseline is ``create_all`` from the live models, so a fresh PG DB already
carries it — the create is inspector-guarded. Never replay the SQLite chain on
Postgres; siblings, not a sequence.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import ArtifactVersion

revision: str = "0021_pi_208_artifact_versions"
down_revision: str | None = "0020_pi_205_release_entity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if ArtifactVersion.__tablename__ not in _tables():
        ArtifactVersion.__table__.create(bind)


def downgrade() -> None:
    if ArtifactVersion.__tablename__ in _tables():
        ArtifactVersion.__table__.drop(op.get_bind())
