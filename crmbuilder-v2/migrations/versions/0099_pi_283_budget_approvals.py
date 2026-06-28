"""PI-283 (REQ-318 / PRJ-043) — budget_approvals table.

Adds the pre-launch budget-decision control satellite (engagement-scoped,
non-governed — no change_log / refs participation), recording an operator's
approve/decline of a run's projected cost against a budget. Created from the ORM
``__table__`` with ``checkfirst`` (idempotent on the create_all-then-upgrade-head
test path). No entity-type / refs CHECK rebuilds — it is not a governance entity.

SQLite chain head 0098 -> 0099; companion PG delta
``migrations/pg/versions/0056_pi_283_budget_approvals.py``.
"""

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.access.models import BudgetApproval
from sqlalchemy import inspect

revision: str = "0099_pi_283_budget_approvals"
down_revision: str | None = "0098_pi_201_instance_deploy_configs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    BudgetApproval.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    if BudgetApproval.__tablename__ in set(inspect(bind).get_table_names()):
        BudgetApproval.__table__.drop(bind)
