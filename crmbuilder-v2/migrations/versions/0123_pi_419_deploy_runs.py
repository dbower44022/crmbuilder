"""PI-419 (REQ-522 / DEC-945, SQLite chain) — deploy runs and provider credentials.

Companion to the PG-chain ``0080``. Adds the two tables behind admin-driven
CRM deployment and widens ``instance_deploy_configs`` with the facts a deploy
run writes when it provisions the server itself:

* ``deploy_runs`` — one recorded execution of a provisioning job (``DEP-NNN``),
  with a non-terminal lifecycle (queued → running → terminal), a worker claim
  + heartbeat, a resume checkpoint, and a capped log.
* ``provider_credentials`` — an engagement's DigitalOcean / Cloudflare token
  as an opaque secret ref, one row per provider.
* ``instance_deploy_configs`` gains ``db_password_ref``, ``admin_username``,
  ``admin_password_ref``, ``droplet_ip``, ``droplet_region``, ``droplet_size``,
  ``dns_record_id`` and ``last_deploy_run_identifier`` — all nullable, so no
  existing row changes meaning.

Both tables are non-governed operational records (DEC-447 precedent): no
change_log / refs CHECK rebuild. Bootstrap-safe — table creates use
``checkfirst`` and column adds are inspector-guarded, because the create_all
+ stamp-behind path runs this migration against a database that already has
the head schema.

SQLite chain head 0122 -> 0123. Companion PG-chain delta:
``migrations/pg/versions/0080_pi_419_deploy_runs.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import DeployRun, ProviderCredential

revision: str = "0123_pi_419_deploy_runs"
down_revision: str | None = "0122_pi_425_field_built_in"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEPLOY_CONFIG_COLUMNS: tuple[sa.Column, ...] = (
    sa.Column("db_password_ref", sa.Text(), nullable=True),
    sa.Column("admin_username", sa.Text(), nullable=True),
    sa.Column("admin_password_ref", sa.Text(), nullable=True),
    sa.Column("droplet_ip", sa.String(64), nullable=True),
    sa.Column("droplet_region", sa.String(32), nullable=True),
    sa.Column("droplet_size", sa.String(64), nullable=True),
    sa.Column("dns_record_id", sa.String(64), nullable=True),
    sa.Column("last_deploy_run_identifier", sa.String(32), nullable=True),
)


def _existing_columns(table: str) -> set[str]:
    if op.get_context().as_sql:
        return set()
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    DeployRun.__table__.create(bind, checkfirst=True)
    ProviderCredential.__table__.create(bind, checkfirst=True)
    present = _existing_columns("instance_deploy_configs")
    for column in _DEPLOY_CONFIG_COLUMNS:
        if column.name not in present:
            op.add_column("instance_deploy_configs", column.copy())


def downgrade() -> None:
    bind = op.get_bind()
    present = _existing_columns("instance_deploy_configs")
    with op.batch_alter_table("instance_deploy_configs") as batch:
        for column in _DEPLOY_CONFIG_COLUMNS:
            if column.name in present:
                batch.drop_column(column.name)
    tables = set(sa.inspect(bind).get_table_names())
    if ProviderCredential.__tablename__ in tables:
        ProviderCredential.__table__.drop(bind)
    if DeployRun.__tablename__ in tables:
        DeployRun.__table__.drop(bind)
