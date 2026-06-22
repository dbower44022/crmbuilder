"""PI-051 (PG chain) — field_visibility_rule entity table.

Companion to the SQLite-chain ``0082``. Creates ``field_visibility_rules``
(``FVR-``) on Postgres deployments materialised from an earlier baseline. The PG
baseline is ``create_all`` from the live models, so a fresh PG DB already carries
this table (and its CHECKs, derived from current vocab) — the create is
``checkfirst``-guarded a no-op there. Never replay the SQLite chain on Postgres.
"""

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.access.models import FieldVisibilityRule

revision: str = "0039_pi_051_field_visibility_rule"
down_revision: str | None = "0038_pi_255_source_mapping_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    FieldVisibilityRule.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    if FieldVisibilityRule.__tablename__ in set(
        inspect(bind).get_table_names()
    ):
        FieldVisibilityRule.__table__.drop(bind)
