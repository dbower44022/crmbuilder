"""PI-576 (REQ-653, DEC-1155, DEC-1175, DEC-1185): the deployment record.

Creates ``deployments``, the system-wide table naming, for one installation,
its application (the engagement row), its client, its hosting provider and
the instance it holds; adds ``deployment_identifier`` to ``deploy_runs`` (the
run history points at the deployment it built) and to
``provider_credentials`` (a credential may belong to one deployment, the
application-level row being the fallback), and replaces the credential
table's ``UNIQUE (engagement_id, provider)`` with a unique expression index
over ``(engagement_id, provider, COALESCE(deployment_identifier, ''))`` so
an application keeps one fallback row per provider and each deployment may
hold its own.

No row moves here: the existing instances, configurations and credentials
are re-homed under deployments by the migration run (PI-579) from the
approved mapping (DEC-1176 to DEC-1182).

Bootstrap-safe (LSN-050): every step is inspector-guarded, so a database
built by ``create_all`` and stamped behind this revision passes through
unchanged. Downgrade drops the column and table only when no credential row
is scoped to a deployment, because collapsing those rows back into the
application scope could violate the old uniqueness rule.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "operate_0003_deployments"
down_revision: str | None = "operate_0002_deploy_needs_action"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_HOSTING_PROVIDERS = ("digitalocean", "other")
_STATUSES = ("active", "retired")


def _inspector():
    return sa.inspect(op.get_bind())


def _tables() -> set[str]:
    return set(_inspector().get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in _inspector().get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {i["name"] for i in _inspector().get_indexes(table)}


def _uniques(table: str) -> set[str]:
    return {u["name"] for u in _inspector().get_unique_constraints(table)}


def _foreign_keys_to_deployments(table: str) -> list[str]:
    """Names of ``table``'s foreign keys that reference ``deployments``: the
    migration names its own, but a database built by ``create_all`` carries
    SQLAlchemy's generated names, so the downgrade looks them up."""
    return [
        fk["name"]
        for fk in _inspector().get_foreign_keys(table)
        if fk.get("referred_table") == "deployments" and fk.get("name")
    ]


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    if "deployments" not in _tables():
        op.create_table(
            "deployments",
            sa.Column("deployment_identifier", sa.String(32), primary_key=True),
            sa.Column(
                "deployment_application",
                sa.String(32),
                sa.ForeignKey("engagements.engagement_identifier", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "deployment_client",
                sa.String(32),
                sa.ForeignKey("clients.client_identifier", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "deployment_hosting_provider",
                sa.String(24),
                nullable=False,
                server_default=sa.text("'digitalocean'"),
            ),
            sa.Column("deployment_name", sa.String(255), nullable=False),
            sa.Column(
                "deployment_status",
                sa.String(16),
                nullable=False,
                server_default=sa.text("'active'"),
            ),
            sa.Column("deployment_instance_identifier", sa.String(32), nullable=True),
            sa.Column("deployment_notes", sa.Text(), nullable=True),
            sa.Column(
                "deployment_created_at", sa.DateTime(timezone=True), nullable=False
            ),
            sa.Column(
                "deployment_updated_at", sa.DateTime(timezone=True), nullable=False
            ),
            sa.Column(
                "deployment_deleted_at", sa.DateTime(timezone=True), nullable=True
            ),
            sa.CheckConstraint(
                "deployment_identifier ~ '^DPL-[0-9]{3,}$'",
                name="ck_deployment_identifier_format",
            ),
            sa.CheckConstraint(
                _in("deployment_hosting_provider", _HOSTING_PROVIDERS),
                name="ck_deployment_hosting_provider",
            ),
            sa.CheckConstraint(
                _in("deployment_status", _STATUSES), name="ck_deployment_status"
            ),
        )
    existing = _indexes("deployments")
    if "ux_deployments_instance" not in existing:
        op.create_index(
            "ux_deployments_instance",
            "deployments",
            ["deployment_application", "deployment_instance_identifier"],
            unique=True,
        )
    for name, column in (
        ("ix_deployments_application", "deployment_application"),
        ("ix_deployments_client", "deployment_client"),
        ("ix_deployments_deleted_at", "deployment_deleted_at"),
    ):
        if name not in existing:
            op.create_index(name, "deployments", [column])

    if "deployment_identifier" not in _columns("deploy_runs"):
        op.add_column(
            "deploy_runs",
            sa.Column(
                "deployment_identifier",
                sa.String(32),
                sa.ForeignKey(
                    "deployments.deployment_identifier",
                    ondelete="SET NULL",
                    name="fk_deploy_runs_deployment",
                ),
                nullable=True,
            ),
        )
    if "ix_deploy_runs_deployment" not in _indexes("deploy_runs"):
        op.create_index(
            "ix_deploy_runs_deployment", "deploy_runs", ["deployment_identifier"]
        )

    if "deployment_identifier" not in _columns("provider_credentials"):
        op.add_column(
            "provider_credentials",
            sa.Column(
                "deployment_identifier",
                sa.String(32),
                sa.ForeignKey(
                    "deployments.deployment_identifier",
                    ondelete="CASCADE",
                    name="fk_provider_credentials_deployment",
                ),
                nullable=True,
            ),
        )
    if "uq_provider_credential_provider" in _uniques("provider_credentials"):
        op.drop_constraint(
            "uq_provider_credential_provider", "provider_credentials", type_="unique"
        )
    if "ux_provider_credential_scope" not in _indexes("provider_credentials"):
        op.create_index(
            "ux_provider_credential_scope",
            "provider_credentials",
            [
                "engagement_id",
                "provider",
                sa.text("COALESCE(deployment_identifier, '')"),
            ],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if "deployment_identifier" in _columns("provider_credentials"):
        scoped = bind.execute(
            sa.text(
                "SELECT COUNT(*) FROM provider_credentials "
                "WHERE deployment_identifier IS NOT NULL"
            )
        ).scalar()
        if scoped:
            raise RuntimeError(
                f"refusing to downgrade: {scoped} provider credential row(s) are "
                "scoped to a deployment and would collide in the application "
                "scope; remove or re-home them first"
            )
        if "ux_provider_credential_scope" in _indexes("provider_credentials"):
            op.drop_index("ux_provider_credential_scope", "provider_credentials")
        if "uq_provider_credential_provider" not in _uniques("provider_credentials"):
            op.create_unique_constraint(
                "uq_provider_credential_provider",
                "provider_credentials",
                ["engagement_id", "provider"],
            )
        for name in _foreign_keys_to_deployments("provider_credentials"):
            op.drop_constraint(name, "provider_credentials", type_="foreignkey")
        op.drop_column("provider_credentials", "deployment_identifier")
    if "deployment_identifier" in _columns("deploy_runs"):
        if "ix_deploy_runs_deployment" in _indexes("deploy_runs"):
            op.drop_index("ix_deploy_runs_deployment", "deploy_runs")
        for name in _foreign_keys_to_deployments("deploy_runs"):
            op.drop_constraint(name, "deploy_runs", type_="foreignkey")
        op.drop_column("deploy_runs", "deployment_identifier")
    if "deployments" in _tables():
        op.drop_table("deployments")
