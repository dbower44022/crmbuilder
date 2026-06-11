"""PI-alpha — widen columns whose data exceeds their declared VARCHAR length.

Porting the schema to Postgres surfaced six columns whose real data overruns the
declared ``VARCHAR(n)``: SQLite never enforces the cap, Postgres does. Five hold
free text or derived/audit identifiers that legitimately run long; one
(``refs.relationship_kind``) was simply under-sized for its own vocabulary (the
longest kind, ``close_out_payload_produced_by_conversation``, is 42 chars).

* ``decisions.title``                    VARCHAR(255) -> TEXT
* ``planning_items.title``               VARCHAR(255) -> TEXT
* ``risks.title``                        VARCHAR(255) -> TEXT
* ``conversations.conversation_title``   VARCHAR(255) -> TEXT
* ``change_log.entity_identifier``       VARCHAR(64)  -> TEXT
* ``refs.relationship_kind``             VARCHAR(32)  -> VARCHAR(64)

On SQLite this is a no-op in practice (column affinity is TEXT either way and the
length was never enforced); the migration exists so ``alembic upgrade head``
matches the ORM models. On Postgres these are real, enforced widenings — though
the PG baseline is materialised fresh from the models, not by replaying this
SQLite chain, so this revision is effectively SQLite-chain hygiene.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0039_pi_alpha_widen_text_columns"
down_revision: str | None = "0038_pi_123_engagement_id_discriminator_nullable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, column, new_type, old_type)
_WIDENINGS: tuple[tuple[str, str, sa.types.TypeEngine, sa.types.TypeEngine], ...] = (
    ("decisions", "title", sa.Text(), sa.String(255)),
    ("planning_items", "title", sa.Text(), sa.String(255)),
    ("risks", "title", sa.Text(), sa.String(255)),
    ("conversations", "conversation_title", sa.Text(), sa.String(255)),
    ("change_log", "entity_identifier", sa.Text(), sa.String(64)),
    ("refs", "relationship_kind", sa.String(64), sa.String(32)),
)


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _existing_tables()
    for table, column, new_type, _old in _WIDENINGS:
        if table not in existing:
            continue  # absent when the chain is entered mid-stream (isolated-migration tests)
        with op.batch_alter_table(table) as batch:
            batch.alter_column(column, type_=new_type)


def downgrade() -> None:
    existing = _existing_tables()
    for table, column, _new, old_type in _WIDENINGS:
        if table not in existing:
            continue
        with op.batch_alter_table(table) as batch:
            batch.alter_column(column, type_=old_type)
