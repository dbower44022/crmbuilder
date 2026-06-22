"""PI-255 (PG chain) — source instance mapping model tables.

Companion to the SQLite-chain ``0081``. Creates the seven source mapping tables
on Postgres deployments materialised from an earlier baseline. The PG baseline
is ``create_all`` from the live models, so a fresh PG DB already carries these
tables (and their CHECKs, derived from current vocab) — the creates are
``checkfirst``-guarded no-ops there. Never replay the SQLite chain on Postgres.
"""

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.access.models import (
    FieldMapping,
    FieldMappingTranslation,
    MappingCandidate,
    SourceMapping,
    SourceMappingJoin,
    SourceMappingTarget,
    ValueMapping,
)

revision: str = "0038_pi_255_source_mapping_tables"
down_revision: str | None = "0037_pi_263_cost_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MODELS = (
    SourceMapping,
    SourceMappingTarget,
    SourceMappingJoin,
    FieldMapping,
    FieldMappingTranslation,
    ValueMapping,
    MappingCandidate,
)


def upgrade() -> None:
    bind = op.get_bind()
    for model in _MODELS:
        model.__table__.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    existing = set(inspect(bind).get_table_names())
    for model in reversed(_MODELS):
        if model.__tablename__ in existing:
            model.__table__.drop(bind)
