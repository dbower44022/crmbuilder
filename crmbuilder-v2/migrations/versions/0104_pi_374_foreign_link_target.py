"""PI-374 (REQ-435/436) — foreign-field link/target columns on ``fields``.

A ``foreign`` field mirrors a scalar from a linked record; to round-trip it
(deploy it back) and to resolve its mirrored value-type, the canonical record
must carry **what** it mirrors. Adds two nullable columns to ``fields``:

- ``field_foreign_link`` (TEXT NULL) — the link the foreign field mirrors through.
- ``field_foreign_target`` (TEXT NULL) — the field on the linked entity it surfaces.

Both nullable, so no ``server_default`` and no CHECK — the required-when-foreign
rule lives at the access layer (mirrors the ``field_derived_result_type`` /
``field_formula`` columns added in 0062). No ``entity_type`` /
``relationship_kind`` change.

Migration shape mirrors 0062/0055: the column adds go through
``batch_alter_table`` (the SQLite table recreate preserves CHECKs/indexes),
guarded by table/column existence so it is safe mid-chain and idempotent against
create_all-then-upgrade-head.

SQLite chain head 0103 -> 0104. Companion PG-chain delta:
``migrations/pg/versions/0061_pi_374_foreign_link_target.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0104_pi_374_foreign_link_target"
down_revision: str | None = "0103_pi_374_foreign_field_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FIELD_COLUMNS: tuple[tuple[str, dict], ...] = (
    ("field_foreign_link", {"type_": sa.Text(), "nullable": True}),
    ("field_foreign_target", {"type_": sa.Text(), "nullable": True}),
)


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "fields" not in _tables():
        return
    have = _columns("fields")
    missing = [c for c in _FIELD_COLUMNS if c[0] not in have]
    if not missing:
        return
    with op.batch_alter_table("fields") as batch:
        for name, kwargs in missing:
            batch.add_column(sa.Column(name, **kwargs))


def downgrade() -> None:
    if "fields" not in _tables():
        return
    have = _columns("fields")
    with op.batch_alter_table("fields") as batch:
        for name, _ in _FIELD_COLUMNS:
            if name in have:
                batch.drop_column(name)
