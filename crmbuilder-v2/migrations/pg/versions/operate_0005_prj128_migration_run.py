"""PI-579 (REQ-653, DEC-1175, DEC-1176..DEC-1182): the PRJ-128 migration run.

A data-only revision. It applies the approved engagement migration mapping
once, through :mod:`crmbuilder_v2.segments.operate.prj128_migration`: the
Rochester copy is compared with Cleveland's design and archived on a pass,
the clients Rochester and Boston are created, every existing instance
becomes a deployment under the application it installs, the Rochester and
Boston instances, configurations, credentials and run history move under
the Cleveland application, and the four engagements that stop being
applications are archived. A comparison that fails raises before any row
moves; the revision then records itself as run without applying, leaves
the store as it was, and the run is applied later with the module's
command line once the ruling on the comparison is recorded.

Runs only where the store the mapping describes is present and not yet
migrated; a fresh database or one already migrated passes through. There
is no downgrade: the moves are recorded in the change log and the rehearsal
log, and reversing them is a decision, not a script.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.segments.operate import prj128_migration

revision: str = "operate_0005_prj128_migration_run"
down_revision: str | None = "operate_0004_deployment_purpose"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_context().as_sql:
        return
    try:
        prj128_migration.run(op.get_bind(), log=print)
    except prj128_migration.MigrationStop as exc:
        # The schema revisions before this one must not be held back by a
        # comparison that awaits a ruling: the store is left exactly as it
        # was, the reason is in the migrate log, and the run is applied later
        # with ``python -m crmbuilder_v2.segments.operate.prj128_migration
        # --url ... --apply`` once the ruling is recorded.
        print(f"PRJ-128 migration run NOT applied: {exc}")


def downgrade() -> None:
    bind = op.get_bind()
    applied = bind.exec_driver_sql(
        "SELECT COUNT(*) FROM deployments WHERE deployment_application = 'ENG-002'"
    ).scalar()
    if applied:
        raise RuntimeError(
            "operate_0005_prj128_migration_run cannot be reversed by script: the "
            "PRJ-128 moves are recorded in the change log; restore the pre-run "
            "backup instead"
        )
