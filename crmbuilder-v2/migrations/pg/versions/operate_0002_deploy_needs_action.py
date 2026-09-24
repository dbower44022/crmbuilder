"""PI-571 (REQ-650, REQ-651): a deploy run can end needing action, and an
instance keeps its open items.

Three changes on the ``operate`` branch:

* ``deploy_runs.deploy_run_status`` accepts ``needs_action`` — a run that went
  as far as it could, registered the instance, and left something a person
  must do (typically the DNS record).
* ``deploy_runs.deploy_run_phase`` accepts the two new steps ``check_dns`` and
  ``certificate``. ``wait_dns`` stays accepted, because runs queued before
  this change name it in their rows.
* ``instance_deploy_configs.open_items`` (JSON, nullable) holds what is still
  outstanding on the instance. Never backfilled.

Downgrade restores the old CHECKs and drops the column, and refuses when a row
would violate the narrower CHECKs.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "operate_0002_deploy_needs_action"
down_revision: str | None = "operate_0001_branch"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_STATUSES = ("cancelled", "failed", "queued", "running", "succeeded", "succeeded_with_issues")
_NEW_STATUSES = tuple(sorted(_OLD_STATUSES + ("needs_action",)))
_OLD_PHASES = (
    "create_dns", "create_droplet", "create_instance", "install_espocrm", "post_install",
    "server_prep", "validate", "verify", "wait_dns", "wait_droplet",
)
_NEW_PHASES = tuple(sorted(_OLD_PHASES + ("check_dns", "certificate")))


def _in(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in sorted(values))
    return f"{column} IN ({quoted})"


def _columns(table: str) -> set[str]:
    if op.get_context().as_sql:
        return set()
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _replace_check(name: str, expression: str) -> None:
    op.drop_constraint(name, "deploy_runs", type_="check")
    op.create_check_constraint(name, "deploy_runs", sa.text(expression))


def upgrade() -> None:
    _replace_check("ck_deploy_run_status", _in("deploy_run_status", _NEW_STATUSES))
    _replace_check(
        "ck_deploy_run_phase",
        _in("deploy_run_phase", _NEW_PHASES),
    )
    if "open_items" not in _columns("instance_deploy_configs"):
        op.add_column("instance_deploy_configs", sa.Column("open_items", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    blocked = bind.execute(
        sa.text(
            "SELECT count(*) FROM deploy_runs WHERE deploy_run_status = 'needs_action' "
            "OR deploy_run_phase IN ('check_dns', 'certificate')"
        )
    ).scalar_one()
    if blocked:
        raise RuntimeError(
            f"{blocked} deploy run(s) use the needs_action status or a new step; "
            "narrowing the CHECKs would leave the table violating them."
        )
    _replace_check("ck_deploy_run_status", _in("deploy_run_status", _OLD_STATUSES))
    _replace_check(
        "ck_deploy_run_phase",
        _in("deploy_run_phase", _OLD_PHASES),
    )
    if "open_items" in _columns("instance_deploy_configs"):
        op.drop_column("instance_deploy_configs", "open_items")
