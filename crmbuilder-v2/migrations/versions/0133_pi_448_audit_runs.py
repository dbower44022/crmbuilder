"""PI-448 (REQ-551 / DEC-994) — audit runs: the audit's background-job record.

Adds ``audit_runs``: one background execution of an audit area (``ARN-NNN``),
with the deploy-run lifecycle (queued -> running -> terminal), a worker claim
+ heartbeat, live progress counters, a capped log, and the reconciler's final
summary. Today only the opt-in utilization area runs this way.

A non-governed operational record (DEC-447 precedent): no change_log / refs
CHECK rebuild. Bootstrap-safe — the table create uses ``checkfirst`` because
the create_all + stamp-behind path runs this migration against a database
that already has the head schema.

SQLite chain head 0132 -> 0133. Companion PG-chain delta:
``migrations/pg/versions/0090_pi_448_audit_runs.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import AuditRun

revision: str = "0133_pi_448_audit_runs"
down_revision: str | None = "0132_pi_410_conformance_overrides"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    AuditRun.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    if AuditRun.__tablename__ in set(sa.inspect(bind).get_table_names()):
        AuditRun.__table__.drop(bind)
