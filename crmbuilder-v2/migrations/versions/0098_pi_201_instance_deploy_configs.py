"""PI-201 (REQ-172 / PRJ-027) — instance_deploy_configs table.

Adds the per-instance deploy/provisioning config child table (1:1 with
``instance``, engagement-scoped, non-governed — no change_log / refs
participation), ported from the V1 ``InstanceDeployConfig``. Created from the ORM
``__table__`` with ``checkfirst`` (idempotent on the create_all-then-upgrade-head
test path). No entity-type / refs CHECK rebuilds — it is not a governance entity.

SQLite chain head 0097 -> 0098; companion PG delta
``migrations/pg/versions/0055_pi_201_instance_deploy_configs.py``.
"""

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.access.models import InstanceDeployConfig
from sqlalchemy import inspect

revision: str = "0098_pi_201_instance_deploy_configs"
down_revision: str | None = "0097_pi_046_reference_entity_type"
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
