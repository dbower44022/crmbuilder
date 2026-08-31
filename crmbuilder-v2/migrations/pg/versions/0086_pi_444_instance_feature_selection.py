"""PI-444 (REQ-546 / DEC-977, PG chain) — per-instance stored feature selection.

REQ-546: each CRM instance record carries a persistent selection of which
entities from the engagement's canonical design are active for that instance
(the chapter's feature selection, DEC-976/977). Publish resolves the stored
selection to its generated program filenames automatically when no per-run
scope is supplied; an instance with no selection keeps today's full-design
behaviour.

``instances`` gains one column, ``instance_feature_selection`` — a JSON list
of design-entity identifiers (``ENT-NNN``), NULL meaning "no selection".
Entity identifiers rather than program filenames so a design-entity rename
cannot silently detach the selection.

Nullable, NULL on every existing row and not backfilled: an instance that
never chose a selection publishes the full design (the DEC-924 principle —
facts nobody recorded are not invented).

Bootstrap-safe (LSN-050): the create_all + stamp-behind path already holds
this column, so the add and drop are existence-guarded.

PG chain head 0085 -> 0086. Companion SQLite-chain delta:
``migrations/versions/0129_pi_444_instance_feature_selection.py``.

NOTE (live application): the live store is create_all-managed and is NOT
walked through this chain. This migration is the canonical record of the
delta; the live application goes through ``crmbuilder-v2-bootstrap-db``,
verified on a copy first, and is performed by Doug (GVR-240) — never from
here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0086_pi_444_instance_feature_selection"
down_revision: str | None = "0085_pi_442_deploy_server_management_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMN = "instance_feature_selection"


def _cols(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if _COLUMN not in _cols("instances"):
        op.add_column(
            "instances", sa.Column(_COLUMN, sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    if _COLUMN in _cols("instances"):
        op.drop_column("instances", _COLUMN)
