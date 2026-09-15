"""Frozen definitions of tables the store no longer has a model for.

PI-509 (REQ-601, DEC-1089) removed the three record types no code creates:
``services`` (Service), ``source_mapping_joins`` (SourceMappingJoin) and
``field_mapping_translations`` (FieldMappingTranslation). Their ORM classes are
gone from ``crmbuilder_v2.access.models``, but the migration chain still has
to be able to create them: the trunk revisions that introduced them
(``0014_pi_161_service_entity``, ``0038_pi_255_source_mapping_tables``) run
on a store materialised from an older baseline, and the branch revisions that
drop them need a ``downgrade``. Each function below returns the table as it
stood on the day it was retired, bound to a throwaway :class:`MetaData`, so
``Table.create`` works without the model.

Each table's ``engagement_id`` foreign key points at ``engagements``, which
the throwaway metadata also has to know about for the constraint to compile;
:func:`_metadata` supplies a stub of that one referenced column. Only the
retired table is ever created from it.

Nothing outside the migration tree imports this module.
"""

from __future__ import annotations

import sqlalchemy as sa

from crmbuilder_v2.access.base import _IdentifierFormatCheck
from crmbuilder_v2.access.vocab import _check_in

#: The statuses the retired ``services`` table admitted (its ``vocab`` set).
SERVICE_STATUSES: frozenset[str] = frozenset(
    {"candidate", "confirmed", "deferred", "rejected"}
)
#: The translation types the retired ``field_mapping_translations`` admitted.
FIELD_MAPPING_TRANSLATION_TYPES: frozenset[str] = frozenset(
    {"value_map", "expression"}
)
#: The reference entity type and kinds retired with the ``services`` table.
SERVICE_ENTITY_TYPE = "service"
SERVICE_REFERENCE_KINDS: frozenset[str] = frozenset(
    {"process_consumes_service", "service_owns_entity"}
)


def _metadata(metadata: sa.MetaData | None) -> sa.MetaData:
    """``metadata`` (or a fresh one) carrying the ``engagements`` FK target."""
    md = metadata if metadata is not None else sa.MetaData()
    if "engagements" not in md.tables:
        sa.Table(
            "engagements",
            md,
            sa.Column("engagement_identifier", sa.String(32), primary_key=True),
        )
    return md


def services_table(metadata: sa.MetaData | None = None) -> sa.Table:
    """``services`` as retired: identifier-as-PK, engagement-scoped (Class A)."""
    md = _metadata(metadata)
    return sa.Table(
        "services",
        md,
        sa.Column(
            "engagement_id",
            sa.String(32),
            sa.ForeignKey("engagements.engagement_identifier"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("service_identifier", sa.String(32), primary_key=True),
        sa.Column("service_name", sa.String(255), nullable=False),
        sa.Column("service_purpose", sa.Text, nullable=False),
        sa.Column("service_capabilities", sa.Text, nullable=True),
        sa.Column("service_notes", sa.Text, nullable=True),
        sa.Column("service_status", sa.String(16), nullable=False),
        sa.Column("service_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("service_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("service_deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            _IdentifierFormatCheck("service_identifier", ["SVC"]),
            name="ck_service_identifier_format",
        ),
        sa.CheckConstraint(
            _check_in("service_status", SERVICE_STATUSES), name="ck_service_status"
        ),
        sa.Index("ix_services_service_status", "service_status"),
    )


def source_mapping_joins_table(metadata: sa.MetaData | None = None) -> sa.Table:
    """``source_mapping_joins`` as retired: surrogate id, engagement-scoped."""
    md = _metadata(metadata)
    return sa.Table(
        "source_mapping_joins",
        md,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "engagement_id",
            sa.String(32),
            sa.ForeignKey("engagements.engagement_identifier"),
            nullable=False,
        ),
        sa.Column("source_mapping_identifier", sa.String(32), nullable=False),
        sa.Column("source_field_name", sa.Text, nullable=False),
        sa.Column("design_entity_identifier", sa.String(32), nullable=False),
        sa.Column("design_field_identifier", sa.String(32), nullable=False),
        sa.UniqueConstraint(
            "engagement_id", "source_mapping_identifier", name="uq_source_mapping_join"
        ),
    )


def field_mapping_translations_table(
    metadata: sa.MetaData | None = None,
) -> sa.Table:
    """``field_mapping_translations`` as retired: surrogate id, engagement-scoped."""
    md = _metadata(metadata)
    return sa.Table(
        "field_mapping_translations",
        md,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "engagement_id",
            sa.String(32),
            sa.ForeignKey("engagements.engagement_identifier"),
            nullable=False,
        ),
        sa.Column("field_mapping_identifier", sa.String(32), nullable=False),
        sa.Column("translation_type", sa.String(32), nullable=False),
        sa.Column("expression", sa.Text, nullable=True),
        sa.UniqueConstraint(
            "engagement_id", "field_mapping_identifier", name="uq_field_mapping_translation"
        ),
        sa.CheckConstraint(
            _check_in("translation_type", FIELD_MAPPING_TRANSLATION_TYPES),
            name="ck_field_mapping_translation_type",
        ),
    )
