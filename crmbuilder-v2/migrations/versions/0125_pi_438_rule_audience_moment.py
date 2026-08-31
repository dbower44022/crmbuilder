"""PI-438 (REQ-541 / DEC-963) — governance_rules.applies_to + applies_when, backfilled.

Every governance rule now says WHO it is for (``applies_to``, TERM-042 Audience:
all / claude_code / sandbox / ui / ado_agent) and WHEN it applies
(``applies_when``, TERM-043 Moment: always / commit / deploy / governance_record /
release). Both are NOT NULL with server defaults (``all`` / ``always``) so
existing rows are valid the moment the columns exist; a CHECK per column freezes
the vocabulary as it stood at this revision (LSN-062 — never derive a CHECK from
the live vocab module).

Backfill (REQ-541): a rule bound to an agent profile through an
``agent_profile_governed_by_rule`` reference is an agent rule (``ado_agent``);
every other rule is a session rule (``claude_code``). The moment is ``always``
except for the operating rules whose text names a point of action: the
commit-trailer, commit-with-pathspec and commit-under-parallel-orchestrators
rules apply at ``commit``, human-only production deploy at ``deploy``,
real-time recording at ``governance_record``, and the demonstrable-increment
checkpoint at ``release``. Identifier-keyed, so the mapping is a no-op on a
store that does not hold those rows.

SQLite chain head 0124 -> 0125. Companion PG-chain delta:
``migrations/pg/versions/0082_pi_438_rule_audience_moment.py``.

Inspector-guarded: the PI-308 bootstrap path materialises the head schema with
create_all and stamps one revision behind (LSN-050), so the columns may already
exist when this runs; the backfill still runs in that case.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0125_pi_438_rule_audience_moment"
down_revision: str | None = "0124_pi_406_system_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "governance_rules"
# Frozen at this revision (LSN-062).
_AUDIENCES = frozenset({"all", "claude_code", "sandbox", "ui", "ado_agent"})
_MOMENTS = frozenset({"always", "commit", "deploy", "governance_record", "release"})
_MOMENT_BY_IDENTIFIER: dict[str, str] = {
    "GVR-229": "commit",  # Governed-By trailer
    "GVR-235": "commit",  # commit with an explicit pathspec
    "GVR-236": "commit",  # commit immediately under parallel orchestrators
    "GVR-240": "deploy",  # production deploy is human-only
    "GVR-231": "governance_record",  # record governance in real time
    "GVR-239": "release",  # demonstrable increment before the next PI
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
    try:
        return {c["name"] for c in insp.get_check_constraints(table) if c.get("name")}
    except NotImplementedError:
        return set()


def _backfill() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            f"UPDATE {_TABLE} SET applies_to = 'ado_agent' WHERE identifier IN ("
            "SELECT target_id FROM refs WHERE source_type = 'agent_profile' "
            "AND target_type = 'governance_rule' "
            "AND relationship_kind = 'agent_profile_governed_by_rule')"
        )
    )
    bind.execute(
        sa.text(
            f"UPDATE {_TABLE} SET applies_to = 'claude_code' "
            "WHERE applies_to = 'all' AND identifier NOT IN ("
            "SELECT target_id FROM refs WHERE source_type = 'agent_profile' "
            "AND target_type = 'governance_rule' "
            "AND relationship_kind = 'agent_profile_governed_by_rule')"
        )
    )
    for identifier, moment in _MOMENT_BY_IDENTIFIER.items():
        bind.execute(
            sa.text(
                f"UPDATE {_TABLE} SET applies_when = :moment WHERE identifier = :id"
            ),
            {"moment": moment, "id": identifier},
        )


def upgrade() -> None:
    have = _cols(_TABLE)
    if not have:
        return
    checks = _check_names(_TABLE)
    with op.batch_alter_table(_TABLE) as batch:
        if "applies_to" not in have:
            batch.add_column(
                sa.Column(
                    "applies_to", sa.String(32), nullable=False, server_default="all"
                )
            )
        if "applies_when" not in have:
            batch.add_column(
                sa.Column(
                    "applies_when",
                    sa.String(32),
                    nullable=False,
                    server_default="always",
                )
            )
        if "ck_governance_rule_applies_to" not in checks:
            batch.create_check_constraint(
                "ck_governance_rule_applies_to", _check_in("applies_to", _AUDIENCES)
            )
        if "ck_governance_rule_applies_when" not in checks:
            batch.create_check_constraint(
                "ck_governance_rule_applies_when", _check_in("applies_when", _MOMENTS)
            )
    _backfill()


def downgrade() -> None:
    have = _cols(_TABLE)
    if not have:
        return
    checks = _check_names(_TABLE)
    with op.batch_alter_table(_TABLE) as batch:
        if "ck_governance_rule_applies_when" in checks:
            batch.drop_constraint("ck_governance_rule_applies_when", type_="check")
        if "ck_governance_rule_applies_to" in checks:
            batch.drop_constraint("ck_governance_rule_applies_to", type_="check")
        if "applies_when" in have:
            batch.drop_column("applies_when")
        if "applies_to" in have:
            batch.drop_column("applies_to")
