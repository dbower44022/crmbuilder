"""PI-507 (REQ-592, DEC-1079 / DEC-1082): the ``operate`` migration branch.

One migration sequence per owner. This empty revision forks the ``operate``
branch from the last trunk revision, ``0097_pi_471_transitions``, and carries the
branch label every later ``operate`` revision inherits. Revisions on this
branch touch only the tables the approved record-type-to-segment map assigns
to Operate (instances, instance_deploy_configs, provider_credentials, deploy_runs) — see ``specifications/re-architecture/record-type-segment-map.md``.

Naming convention for revisions on this branch: ``operate_<nnnn>_<slug>``,
numbered per branch, so two lanes that each add a migration on different
branches never take the same identifier and merge without renumbering.
The database is at head when it carries every branch head
(``alembic upgrade heads``; ``crmbuilder-v2-bootstrap-db`` does the same).
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "operate_0001_branch"
down_revision: str | None = "0097_pi_471_transitions"
branch_labels: str | Sequence[str] | None = ("operate",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Fork point only; no schema change."""


def downgrade() -> None:
    """Fork point only; no schema change."""
