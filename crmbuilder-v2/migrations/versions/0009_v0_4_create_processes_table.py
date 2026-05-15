"""v0.4 slice D — create the processes table

Revision ID: 0009_v0_4_create_processes_table
Revises: 0008_v0_4_create_entities_table
Create Date: 2026-05-14

UI v0.4 slice D. Adds the ``processes`` table — the third methodology
entity type — per ``methodology-schema-specs/process.md`` section 3.2.

The table follows the parent-prefix field-naming convention: every
column is prefixed ``process_``. The primary key is the prefixed-string
identifier ``process_identifier`` (format ``PROC-NNN``, enforced by a
SQLite GLOB CHECK) — there is no integer surrogate ``id`` column.

Two structural points distinguish this table from ``domains`` /
``entities``:

* **No ``process_status`` column** per DEC-056 — the four-value
  ``process_classification`` enum carries the lifecycle. A second GLOB
  CHECK enforces the enum at the database boundary.
* **A direct scalar FK column ``process_domain_identifier``** (format
  ``DOM-NNN``, enforced by GLOB CHECK). FK *existence* is validated at
  the access layer against live ``domain`` records, not via a SQL
  FOREIGN KEY constraint — matching v2's soft-FK convention.

Process-to-process handoffs live in the ``refs`` table as
``process_hands_off_to_process`` references; slice A added that vocab
kind and extended the ``refs`` CHECK constraints, and slice B's
migration already extended the ``change_log.entity_type`` CHECK to
admit all four methodology entity types, so this migration touches the
``processes`` table only.

Forward and backward reversible.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_v0_4_create_processes_table"
down_revision: Union[str, None] = "0008_v0_4_create_entities_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "processes",
        sa.Column("process_identifier", sa.String(length=32), nullable=False),
        sa.Column("process_name", sa.String(length=255), nullable=False),
        sa.Column(
            "process_domain_identifier", sa.String(length=32), nullable=False
        ),
        sa.Column("process_purpose", sa.Text(), nullable=False),
        sa.Column(
            "process_classification", sa.String(length=20), nullable=False
        ),
        sa.Column(
            "process_classification_rationale", sa.Text(), nullable=True
        ),
        sa.Column("process_notes", sa.Text(), nullable=True),
        sa.Column(
            "process_created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "process_updated_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "process_deleted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.CheckConstraint(
            "process_identifier GLOB 'PROC-[0-9][0-9][0-9]'",
            name="ck_process_identifier_format",
        ),
        sa.CheckConstraint(
            "process_domain_identifier GLOB 'DOM-[0-9][0-9][0-9]'",
            name="ck_process_domain_identifier_format",
        ),
        sa.CheckConstraint(
            "process_classification IN "
            "('unclassified', 'mission_critical', 'supporting', 'deferred')",
            name="ck_process_classification",
        ),
        sa.PrimaryKeyConstraint("process_identifier"),
    )
    with op.batch_alter_table("processes", schema=None) as batch_op:
        batch_op.create_index(
            "ix_processes_process_classification",
            ["process_classification"],
            unique=False,
        )
        batch_op.create_index(
            "ix_processes_process_domain_identifier",
            ["process_domain_identifier"],
            unique=False,
        )
        batch_op.create_index(
            "ix_processes_process_deleted_at",
            ["process_deleted_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("processes", schema=None) as batch_op:
        batch_op.drop_index("ix_processes_process_deleted_at")
        batch_op.drop_index("ix_processes_process_domain_identifier")
        batch_op.drop_index("ix_processes_process_classification")
    op.drop_table("processes")
