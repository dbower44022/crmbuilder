"""PI-512 (REQ-589, DEC-1077 / DEC-1092): the client record above the engagement.

Creates ``clients``, the system-wide table of client organisations, and
``engagement_clients``, the one link table between engagements and clients
(design note, shape A): an ordinary engagement has one row marked primary, a
chapter engagement one row per member client with one primary, an engagement
with no client no rows. A partial unique index keeps one primary per
engagement.

The data step assigns the six engagements the live store held when this was
written, guarded so it runs only where those engagements exist and the clients
do not: Cleveland Business Mentors (CLI-001) holds ENG-002 and ENG-004;
CRMBuilder (CLI-002) holds ENG-001 and ENG-005; ENG-003 and ENG-006 belong to
no client and get no row. A fresh database without those engagements gets the
tables and nothing else.

Downgrade drops both tables. Inspector-guarded both ways.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "client_management_0002_clients"
down_revision: str | None = "client_management_0001_branch"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ASSIGNMENT: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("CLI-001", "Cleveland Business Mentors", ("ENG-002", "ENG-004")),
    ("CLI-002", "CRMBuilder", ("ENG-001", "ENG-005")),
)


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _tables()
    if "clients" not in existing:
        op.create_table(
            "clients",
            sa.Column("client_identifier", sa.String(32), primary_key=True),
            sa.Column("client_name", sa.String(255), nullable=False),
            sa.Column("client_status", sa.String(16), nullable=False),
            sa.Column("client_notes", sa.Text(), nullable=True),
            sa.Column("client_created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("client_updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("client_deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint(
                "client_identifier ~ '^CLI-[0-9]{3,}$'",
                name="ck_client_identifier_format",
            ),
            sa.CheckConstraint(
                "client_status IN ('active', 'inactive')",
                name="ck_client_status",
            ),
        )
        op.create_index(
            "ux_clients_name_lower",
            "clients",
            [sa.text("LOWER(client_name)")],
            unique=True,
        )
        op.create_index("ix_clients_status", "clients", ["client_status"])
        op.create_index("ix_clients_deleted_at", "clients", ["client_deleted_at"])
    if "engagement_clients" not in existing:
        op.create_table(
            "engagement_clients",
            sa.Column(
                "engagement_id",
                sa.String(32),
                sa.ForeignKey("engagements.engagement_identifier", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "client_id",
                sa.String(32),
                sa.ForeignKey("clients.client_identifier", ondelete="RESTRICT"),
                primary_key=True,
            ),
            sa.Column(
                "is_primary",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "ux_engagement_clients_one_primary",
            "engagement_clients",
            ["engagement_id"],
            unique=True,
            postgresql_where=sa.text("is_primary"),
        )
        op.create_index(
            "ix_engagement_clients_client", "engagement_clients", ["client_id"]
        )
    _assign_known_engagements()


def _assign_known_engagements() -> None:
    """The guarded data step: only where the named engagements exist and the
    clients do not, so a fresh database and a re-run are both no-ops."""
    bind = op.get_bind()
    present = set(
        bind.execute(
            sa.text("SELECT engagement_identifier FROM engagements")
        ).scalars()
    )
    known_clients = set(
        bind.execute(sa.text("SELECT client_identifier FROM clients")).scalars()
    )
    for client_identifier, name, engagements in _ASSIGNMENT:
        held = [e for e in engagements if e in present]
        if not held or client_identifier in known_clients:
            continue
        bind.execute(
            sa.text(
                "INSERT INTO clients (client_identifier, client_name, client_status, "
                "client_notes, client_created_at, client_updated_at, client_deleted_at) "
                "VALUES (:id, :name, 'active', NULL, NOW(), NOW(), NULL)"
            ),
            {"id": client_identifier, "name": name},
        )
        for engagement_identifier in held:
            bind.execute(
                sa.text(
                    "INSERT INTO engagement_clients (engagement_id, client_id, "
                    "is_primary, created_at) VALUES (:e, :c, true, NOW())"
                ),
                {"e": engagement_identifier, "c": client_identifier},
            )


def downgrade() -> None:
    existing = _tables()
    if "engagement_clients" in existing:
        op.drop_table("engagement_clients")
    if "clients" in existing:
        op.drop_table("clients")
