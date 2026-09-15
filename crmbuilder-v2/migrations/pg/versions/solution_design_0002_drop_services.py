"""PI-509 (REQ-601, DEC-1089): drop the ``services`` table.

No operation anywhere in the code creates a service record: the table had a
model (PI-161) but never a repository, a router, a connector tool or a screen,
and the live store held zero rows when the record-type-to-segment map marked
it a removal candidate. Solution Design owns the table, so the drop lands on
this branch. The reference type ``service`` and its two kinds are retired on
the ``shared_core`` branch (``refs`` is a plumbing table), independently.

Downgrade recreates the table from its frozen definition in
``crmbuilder_v2.migration.retired_tables``. Inspector-guarded both ways.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.migration.retired_tables import services_table

revision: str = "solution_design_0002_drop_services"
down_revision: str | None = "solution_design_0001_branch"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "services"


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if _TABLE in _tables():
        op.drop_table(_TABLE)


def downgrade() -> None:
    if _TABLE not in _tables():
        services_table().create(op.get_bind())
