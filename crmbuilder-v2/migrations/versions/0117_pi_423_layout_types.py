"""PI-423 (REQ-357 / REQ-158) — the audit reads every editable layout type.

V2 audited six layout types where the V1 audit reads eighteen; the ``edit``
layout was the consequential omission because operators customise it
separately from ``detail``. The ``layouts.layout_type`` vocabulary grows by
twelve neutral names (edit, detail_convert, filters, relationships and the
eight side/bottom panel maps), so the ``ck_layout_type`` CHECK — created
inline from the ORM in 0060 — is rebuilt from the current vocab. The rebuild
is a superset; no existing row is invalidated. Downgrade deletes rows of the
new types (and their membership rows) before narrowing the CHECK.

SQLite chain head 0115 -> 0117 (0116 is claimed by PI-419 on its branch).
Companion PG-chain delta: ``migrations/pg/versions/0074_pi_423_layout_types.py``.

NOTE (live application): the live store is create_all-managed and is NOT walked
through this SQLite chain. This migration is the canonical record of the delta;
the live application goes through ``crmbuilder-v2-bootstrap-db``, verified on a
copy first, and is performed by Doug (GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import LAYOUT_TYPES, _check_in

revision: str = "0117_pi_423_layout_types"
down_revision: str | None = "0115_pi_414_membership_vocabulary_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPES = frozenset(
    {
        "edit",
        "detail_convert",
        "filters",
        "relationships",
        "side_panels_detail",
        "side_panels_edit",
        "side_panels_detail_small",
        "side_panels_edit_small",
        "bottom_panels_detail",
        "bottom_panels_edit",
        "bottom_panels_detail_small",
        "bottom_panels_edit_small",
    }
)
_TYPES_NEW = LAYOUT_TYPES
_TYPES_OLD = LAYOUT_TYPES - _NEW_TYPES


def _rebuild_layout_type_check(types: frozenset[str]) -> None:
    if "layouts" not in set(sa.inspect(op.get_bind()).get_table_names()):
        return
    with op.batch_alter_table("layouts") as batch:
        batch.drop_constraint("ck_layout_type", type_="check")
        batch.create_check_constraint("ck_layout_type", _check_in("layout_type", types))


def upgrade() -> None:
    _rebuild_layout_type_check(_TYPES_NEW)


def downgrade() -> None:
    quoted = ", ".join(f"'{t}'" for t in sorted(_NEW_TYPES))
    op.execute(
        "DELETE FROM instance_memberships WHERE member_type = 'layout' AND member_identifier IN "
        f"(SELECT layout_identifier FROM layouts WHERE layout_type IN ({quoted}))"
    )
    op.execute(f"DELETE FROM layouts WHERE layout_type IN ({quoted})")
    _rebuild_layout_type_check(_TYPES_OLD)
