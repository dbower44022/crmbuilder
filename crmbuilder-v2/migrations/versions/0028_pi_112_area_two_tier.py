"""PI-112 Phase 2 — two-tier area model (System / Engagement), drop prefix

Revision ID: 0028_pi_112_area_two_tier
Revises: 0027_pi_112_workstream_to_project
Create Date: 2026-05-30

DEC-340 (drop the area version prefix), DEC-342 (System / Engagement tiers),
DEC-348 (Engagement areas user-defined, no Domain link). The ``area`` column
stays on ``planning_items`` at this phase; relocation onto the Work Task is
Phase 4.

Operations:
  1. Create the ``engagement_areas`` table (the Engagement tier — per
     engagement, user-defined). Empty unless step 2 seeds it.
  2. Rewrite every ``planning_items.area`` JSON-array element to its
     prefix-dropped form via a fixed map of the 18 legacy labels. The five
     engagement-tier labels (``cbm-*`` -> ``mn``/``mr``/``cr``/``fu``/
     ``services``) are additionally seeded into ``engagement_areas`` when
     present, so each engagement database keeps exactly the engagement areas
     its own data uses.

Reversible: ``downgrade`` re-applies the version prefixes and drops the
``engagement_areas`` table (engagement-area rows added later via the repo and
not referenced by any planning_item are lost on downgrade — documented, like
prior data-bearing reversals).
"""

import json
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028_pi_112_area_two_tier"
down_revision: Union[str, None] = "0027_pi_112_workstream_to_project"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# old label -> new label (prefix dropped). Covers all 18 legacy areas.
_FWD = {
    "v2-storage": "storage", "v2-access": "access", "v2-api": "api",
    "v2-mcp": "mcp", "v2-ui": "ui",
    "v1-automation": "automation", "v1-espo": "espo", "v1-programs": "programs",
    "methodology-interviews": "methodology-interviews",
    "methodology-process": "methodology-process",
    "methodology-templates": "methodology-templates",
    "methodology-product": "methodology-product",
    "infrastructure": "infrastructure",
    "cbm-mn": "mn", "cbm-mr": "mr", "cbm-cr": "cr", "cbm-fu": "fu",
    "cbm-services": "services",
}
_REV = {v: k for k, v in _FWD.items()}
# The five engagement-tier new labels (seeded into engagement_areas).
_ENGAGEMENT_NEW = {"mn", "mr", "cr", "fu", "services"}


def upgrade() -> None:
    op.create_table(
        "engagement_areas",
        sa.Column("engagement_area_name", sa.String(64), primary_key=True),
        sa.Column("engagement_area_description", sa.Text(), nullable=True),
        sa.Column("engagement_area_created_at", sa.DateTime(), nullable=False),
    )
    _rewrite_areas_seed(op.get_bind())


def _rewrite_areas_seed(bind) -> None:
    rows = bind.execute(
        sa.text("SELECT identifier, area FROM planning_items WHERE area IS NOT NULL")
    ).fetchall()
    seed: set[str] = set()
    for ident, area_json in rows:
        arr = json.loads(area_json)
        new = [_FWD.get(a, a) for a in arr]
        if new != arr:
            bind.execute(
                sa.text("UPDATE planning_items SET area = :a WHERE identifier = :i"),
                {"a": json.dumps(new), "i": ident},
            )
        seed |= {a for a in new if a in _ENGAGEMENT_NEW}
    for name in sorted(seed):
        bind.execute(
            sa.text(
                "INSERT OR IGNORE INTO engagement_areas "
                "(engagement_area_name, engagement_area_created_at) "
                "VALUES (:n, datetime('now'))"
            ),
            {"n": name},
        )


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT identifier, area FROM planning_items WHERE area IS NOT NULL")
    ).fetchall()
    for ident, area_json in rows:
        arr = json.loads(area_json)
        new = [_REV.get(a, a) for a in arr]
        if new != arr:
            bind.execute(
                sa.text("UPDATE planning_items SET area = :a WHERE identifier = :i"),
                {"a": json.dumps(new), "i": ident},
            )
    op.drop_table("engagement_areas")
