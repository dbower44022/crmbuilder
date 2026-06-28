"""PI-283 (PG chain) — budget_approvals table.

Companion to the SQLite-chain ``0099`` (REQ-318). Creates the pre-launch
budget-decision control satellite on a Postgres deployment. The PG baseline is
``create_all`` from the live models, so a fresh PG DB already carries it — the
create is a ``checkfirst``-guarded no-op there. Never replay the SQLite chain on
Postgres.
"""

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.access.models import BudgetApproval
from sqlalchemy import inspect

revision: str = "0056_pi_283_budget_approvals"
down_revision: str | None = "0055_pi_201_instance_deploy_configs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    BudgetApproval.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    if BudgetApproval.__tablename__ in set(inspect(bind).get_table_names()):
        BudgetApproval.__table__.drop(bind)
