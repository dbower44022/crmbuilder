"""PI-442 (REQ-544 / DEC-971, PG chain) — server-management facts on the deploy records.

REQ-544 requires that a human admin or an AI agent can read, from a deployed
instance's records, which hosting provider runs the server, where its
management console is, and which SSH key grants access — plus the operational
facts (backup policy, verification time, cost, notes) that otherwise live in
nobody's head. DEC-971 put the facts on the two existing rows rather than a
new record: the instance deploy config is already the 1:1 management surface
for a server and the deploy run its history row; a second record describing
the same server is a second thing that can disagree.

``deploy_runs`` gains one column, ``deploy_run_provider`` — the hosting
provider the run provisioned against, stamped at creation so the history row
is self-describing. Free text (no CHECK): the service provisions on
DigitalOcean today, but the history must be able to name any provider a
future runner uses.

``instance_deploy_configs`` gains seventeen columns: provider identity and
consoles (``hosting_provider``, ``hosting_account``, ``hosting_console_url``,
``dns_console_url``), SSH-key identity (``ssh_key_public``,
``ssh_key_fingerprint``, ``ssh_key_name``, ``ssh_key_provider_id`` — the
private half stays a secret ref in ``ssh_credential_ref``), the server image
and lifecycle timestamps (``server_image``, ``provisioned_at``,
``last_verified_at``), and the operator-maintained facts
(``backup_schedule``, ``backup_retention``, ``backup_destination``,
``monthly_cost_usd``, ``billing_note``, ``notes``).

All columns nullable, NULL on every existing row and not backfilled: facts
nobody recorded are not invented (the DEC-924 principle DEC-971 follows).

PG chain head 0084 -> 0085. Companion SQLite-chain delta:
``migrations/versions/0128_pi_442_deploy_server_management_fields.py``.

NOTE (live application): the live store is create_all-managed and is NOT
walked through this chain. This migration is the canonical record of the
delta; the live application goes through ``crmbuilder-v2-bootstrap-db``,
verified on a copy first, and is performed by Doug (GVR-240) — never from
here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0085_pi_442_deploy_server_management_fields"
down_revision: str | None = "0084_pi_439_rule_enforcement_overrides"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONFIG_COLUMNS: tuple[sa.Column, ...] = (
    sa.Column("hosting_provider", sa.Text(), nullable=True),
    sa.Column("hosting_account", sa.Text(), nullable=True),
    sa.Column("hosting_console_url", sa.Text(), nullable=True),
    sa.Column("dns_console_url", sa.Text(), nullable=True),
    sa.Column("ssh_key_public", sa.Text(), nullable=True),
    sa.Column("ssh_key_fingerprint", sa.String(128), nullable=True),
    sa.Column("ssh_key_name", sa.Text(), nullable=True),
    sa.Column("ssh_key_provider_id", sa.String(64), nullable=True),
    sa.Column("server_image", sa.String(64), nullable=True),
    sa.Column("provisioned_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("backup_schedule", sa.Text(), nullable=True),
    sa.Column("backup_retention", sa.Text(), nullable=True),
    sa.Column("backup_destination", sa.Text(), nullable=True),
    sa.Column("monthly_cost_usd", sa.Float(), nullable=True),
    sa.Column("billing_note", sa.Text(), nullable=True),
    sa.Column("notes", sa.Text(), nullable=True),
)


def upgrade() -> None:
    op.add_column(
        "deploy_runs",
        sa.Column("deploy_run_provider", sa.String(24), nullable=True),
    )
    for column in _CONFIG_COLUMNS:
        op.add_column("instance_deploy_configs", column)


def downgrade() -> None:
    for column in reversed(_CONFIG_COLUMNS):
        op.drop_column("instance_deploy_configs", column.name)
    op.drop_column("deploy_runs", "deploy_run_provider")
