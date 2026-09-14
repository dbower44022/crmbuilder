"""PI-507 (REQ-592, DEC-1079 / DEC-1082): the ``solution_design`` migration branch.

One migration sequence per owner. This empty revision forks the ``solution_design``
branch from the last trunk revision, ``0097_pi_471_transitions``, and carries the
branch label every later ``solution_design`` revision inherits. Revisions on this
branch touch only the tables the approved record-type-to-segment map assigns
to Solution Design (entities, fields, field_options, associations, rules, field_permission_rules, field_visibility_rules, views, automations, dedup_rules, message_templates, layouts, roles, teams, filtered_tabs, engine_overrides, system_settings, test_specs, crm_candidates, migration_mappings and the catalog_* tables) — see ``specifications/re-architecture/record-type-segment-map.md``.

Naming convention for revisions on this branch: ``solution_design_<nnnn>_<slug>``,
numbered per branch, so two lanes that each add a migration on different
branches never take the same identifier and merge without renumbering.
The database is at head when it carries every branch head
(``alembic upgrade heads``; ``crmbuilder-v2-bootstrap-db`` does the same).
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "solution_design_0001_branch"
down_revision: str | None = "0097_pi_471_transitions"
branch_labels: str | Sequence[str] | None = ("solution_design",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Fork point only; no schema change."""


def downgrade() -> None:
    """Fork point only; no schema change."""
