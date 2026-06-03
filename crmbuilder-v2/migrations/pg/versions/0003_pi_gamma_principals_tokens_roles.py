"""PI-gamma (PG chain) — identity/RBAC tables: principals, api_tokens, role_assignments.

Companion to the SQLite-chain ``0041_pi_gamma_principals_tokens_roles``. Creates
the three system/shared tables from the live ORM metadata on Postgres
deployments materialised from an earlier baseline.

The PG baseline (``0001_pg_baseline``) is ``Base.metadata.create_all`` from the
live models, which now include these tables — so a freshly-built PG DB already
has them. The creation is therefore guarded by an inspector check, making this
revision a clean no-op on a fresh baseline and a real create on a pre-existing
PG store (matching the dual-head posture of the ``0002`` drop revision).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import (
    ApiTokenRow,
    PrincipalRow,
    RoleAssignmentRow,
)

revision: str = "0003_pi_gamma_principals_tokens_roles"
down_revision: str | None = "0002_drop_engagement_export_dir"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (PrincipalRow, ApiTokenRow, RoleAssignmentRow)


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    have = _existing_tables()
    for model in _TABLES:
        if model.__tablename__ not in have:
            model.__table__.create(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    have = _existing_tables()
    for model in reversed(_TABLES):
        if model.__tablename__ in have:
            model.__table__.drop(bind=bind)
