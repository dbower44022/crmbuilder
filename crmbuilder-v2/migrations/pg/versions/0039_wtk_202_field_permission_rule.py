"""WTK-202 (PG chain) — field_permission_rule entity table.

Companion to the SQLite-chain ``0082``. Creates the ``field_permission_rules``
table (``FPR-NNN``) on Postgres deployments materialised from an earlier
baseline. The PG baseline is ``create_all`` from the live models, so a fresh PG
DB already carries this table (and its CHECKs, derived from current vocab) — the
create is ``checkfirst``-guarded a no-op there. Never replay the SQLite chain on
Postgres.
"""

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.access.models import FieldPermissionRule

revision: str = "0039_wtk_202_field_permission_rule"
down_revision: str | None = "0038_pi_255_source_mapping_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    FieldPermissionRule.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    if FieldPermissionRule.__tablename__ in set(
        inspect(bind).get_table_names()
    ):
        FieldPermissionRule.__table__.drop(bind)
