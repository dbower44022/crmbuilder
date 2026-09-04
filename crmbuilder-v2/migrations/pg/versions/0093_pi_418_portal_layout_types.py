"""PI-418 (REQ-520 / DEC-1029): the layout type vocabulary grows by the five
portal variants.

The audit now fetches ``listPortal`` / ``detailPortal`` / ``listSmallPortal`` /
``detailSmallPortal`` / ``relationshipsPortal`` per entity so a layout the
platform cannot write can still be shown as a difference, non-actionable and
naming why. The ``ck_layout_type`` CHECK — rebuilt last by 0074 — is rebuilt
again from the live vocabulary.

Downgrade removes the portal rows (and their memberships) before narrowing the
CHECK back, as 0074 did.

Companion SQLite-chain delta: ``migrations/versions/0136_pi_418_portal_layout_types.py``.

Revision ID: 0093_pi_418_portal_layout_types
Revises: 0092_pi_413_workflow_membership
Create Date: 2026-09-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import LAYOUT_TYPES, PORTAL_LAYOUT_TYPES, _check_in

revision: str = "0093_pi_418_portal_layout_types"
down_revision: str | None = "0092_pi_413_workflow_membership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TYPES_NEW = LAYOUT_TYPES
_TYPES_OLD = LAYOUT_TYPES - PORTAL_LAYOUT_TYPES


def _rebuild_layout_type_check(types: frozenset[str]) -> None:
    if "layouts" not in set(sa.inspect(op.get_bind()).get_table_names()):
        return
    op.drop_constraint("ck_layout_type", "layouts", type_="check")
    op.create_check_constraint("ck_layout_type", "layouts", _check_in("layout_type", types))


def upgrade() -> None:
    _rebuild_layout_type_check(_TYPES_NEW)


def downgrade() -> None:
    quoted = ", ".join(f"'{t}'" for t in sorted(PORTAL_LAYOUT_TYPES))
    op.execute(
        "DELETE FROM instance_memberships WHERE member_type = 'layout' AND member_identifier IN "
        f"(SELECT layout_identifier FROM layouts WHERE layout_type IN ({quoted}))"
    )
    op.execute(f"DELETE FROM layouts WHERE layout_type IN ({quoted})")
    _rebuild_layout_type_check(_TYPES_OLD)
