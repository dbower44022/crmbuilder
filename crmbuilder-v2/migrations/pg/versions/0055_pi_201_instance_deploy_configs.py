"""PI-201 (PG chain) — instance_deploy_configs table.

Companion to the SQLite-chain ``0098`` (REQ-172). Creates the per-instance
deploy-config table on a Postgres deployment materialised from an earlier
baseline. The PG baseline is ``create_all`` from the live models, so a fresh PG
DB already carries it — the create is a ``checkfirst``-guarded no-op there. Never
replay the SQLite chain on Postgres.
"""

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.access.models import InstanceDeployConfig
from sqlalchemy import inspect

revision: str = "0055_pi_201_instance_deploy_configs"
down_revision: str | None = "0054_pi_046_reference_entity_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    InstanceDeployConfig.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    if InstanceDeployConfig.__tablename__ in set(
        inspect(bind).get_table_names()
    ):
        InstanceDeployConfig.__table__.drop(bind)
