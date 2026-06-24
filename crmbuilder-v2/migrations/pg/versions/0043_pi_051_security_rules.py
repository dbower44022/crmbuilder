"""PI-051 (PG chain) — security-rule entity tables.

Companion to the SQLite-chain ``0086``. Creates ``field_permission_rules``
(``FPR-``) and ``field_visibility_rules`` (``FVR-``) on Postgres deployments
materialised from an earlier baseline. The PG baseline is ``create_all`` from
the live models, so a fresh PG DB already carries these tables (and their
CHECKs, derived from current vocab) — the create is ``checkfirst``-guarded a
no-op there. Never replay the SQLite chain on Postgres.
"""

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.access.models import (
    FieldPermissionRule,
    FieldVisibilityRule,
)

revision: str = "0043_pi_051_security_rules"
down_revision: str | None = "0042_pi_301_agent_capability_description"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    FieldPermissionRule.__table__.create(bind, checkfirst=True)
    FieldVisibilityRule.__table__.create(bind, checkfirst=True)


def downgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if FieldVisibilityRule.__tablename__ in tables:
        FieldVisibilityRule.__table__.drop(bind)
    if FieldPermissionRule.__tablename__ in tables:
        FieldPermissionRule.__table__.drop(bind)
