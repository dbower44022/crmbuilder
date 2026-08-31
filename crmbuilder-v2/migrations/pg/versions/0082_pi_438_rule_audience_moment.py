"""PI-438 (PG chain) — governance_rules.applies_to + applies_when, backfilled.

Companion to the SQLite-chain ``0125_pi_438_rule_audience_moment``; see its
docstring for the rule. Adds the two NOT NULL audience/moment columns with
server defaults and one CHECK each (vocabulary frozen at this revision,
LSN-062), then backfills: profile-bound rules become ``ado_agent``, the rest
``claude_code``, and the operating rules that name a point of action get their
moment. The PG baseline is ``create_all`` from the live models, so a fresh PG DB
already carries the columns — the DDL is inspector-guarded and the backfill
still runs. Chains after ``0081_pi_406_system_settings``. Never replay the
SQLite chain on Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0082_pi_438_rule_audience_moment"
down_revision: str | None = "0081_pi_406_system_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "governance_rules"
_AUDIENCES = frozenset({"all", "claude_code", "sandbox", "ui", "ado_agent"})
_MOMENTS = frozenset({"always", "commit", "deploy", "governance_record", "release"})
_MOMENT_BY_IDENTIFIER: dict[str, str] = {
    "GVR-229": "commit",
    "GVR-235": "commit",
    "GVR-236": "commit",
    "GVR-240": "deploy",
    "GVR-231": "governance_record",
    "GVR-239": "release",
}


def _check_in(name: str, allowed: frozenset[str]) -> str:
    quoted = ", ".join(f"'{v}'" for v in sorted(allowed))
    return f"{name} IN ({quoted})"


def _cols(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _check_names(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    return {c["name"] for c in insp.get_check_constraints(table) if c.get("name")}


def _backfill() -> None:
    bind = op.get_bind()
    if "refs" not in sa.inspect(bind).get_table_names():
        return  # chain entered mid-stream: nothing to backfill yet
    bound = (
        "SELECT target_id FROM refs WHERE source_type = 'agent_profile' "
        "AND target_type = 'governance_rule' "
        "AND relationship_kind = 'agent_profile_governed_by_rule'"
    )
    bind.execute(
        sa.text(f"UPDATE {_TABLE} SET applies_to = 'ado_agent' WHERE identifier IN ({bound})")
    )
    bind.execute(
        sa.text(
            f"UPDATE {_TABLE} SET applies_to = 'claude_code' "
            f"WHERE applies_to = 'all' AND identifier NOT IN ({bound})"
        )
    )
    for identifier, moment in _MOMENT_BY_IDENTIFIER.items():
        bind.execute(
            sa.text(f"UPDATE {_TABLE} SET applies_when = :moment WHERE identifier = :id"),
            {"moment": moment, "id": identifier},
        )


def upgrade() -> None:
    have = _cols(_TABLE)
    if not have:
        return
    if "applies_to" not in have:
        op.add_column(
            _TABLE,
            sa.Column("applies_to", sa.String(32), nullable=False, server_default="all"),
        )
    if "applies_when" not in have:
        op.add_column(
            _TABLE,
            sa.Column(
                "applies_when", sa.String(32), nullable=False, server_default="always"
            ),
        )
    checks = _check_names(_TABLE)
    if "ck_governance_rule_applies_to" not in checks:
        op.create_check_constraint(
            "ck_governance_rule_applies_to", _TABLE, _check_in("applies_to", _AUDIENCES)
        )
    if "ck_governance_rule_applies_when" not in checks:
        op.create_check_constraint(
            "ck_governance_rule_applies_when", _TABLE, _check_in("applies_when", _MOMENTS)
        )
    _backfill()


def downgrade() -> None:
    have = _cols(_TABLE)
    if not have:
        return
    checks = _check_names(_TABLE)
    if "ck_governance_rule_applies_when" in checks:
        op.drop_constraint("ck_governance_rule_applies_when", _TABLE, type_="check")
    if "ck_governance_rule_applies_to" in checks:
        op.drop_constraint("ck_governance_rule_applies_to", _TABLE, type_="check")
    if "applies_when" in have:
        op.drop_column(_TABLE, "applies_when")
    if "applies_to" in have:
        op.drop_column(_TABLE, "applies_to")
