"""Database record insertion for CRM audit results.

Inserts Entity, Field, FieldOption, Relationship, LayoutPanel, LayoutRow,
and ListColumn records into the client SQLite database from audit results.
"""

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

from espo_impl.core.audit_manager import (
    AuditReport,
    EntityAuditResult,
    FieldAuditResult,
    RelationshipAuditResult,
)
from espo_impl.core.audit_utils import EntityClass

logger = logging.getLogger(__name__)


def insert_audit_records(
    conn: sqlite3.Connection,
    report: AuditReport,
    instance_id: int | None = None,
) -> int:
    """Insert audit results into the client database.

    :param conn: Open connection to the client SQLite database.
    :param report: Completed audit report.
    :param instance_id: Instance table ID for ConfigurationRun, or None to skip.
    :returns: Total number of records inserted.
    """
    total = 0

    # Maps for FK resolution: yaml_name -> entity row ID
    entity_ids: dict[str, int] = {}
    # Maps for FK resolution: (yaml_entity, yaml_field) -> field row ID
    field_ids: dict[tuple[str, str], int] = {}

    # Insert entities and fields
    for entity in report.entities:
        entity_id = _insert_entity(conn, entity, entity_ids)
        if entity_id is None:
            continue
        total += 1

        for field_result in entity.fields:
            field_id = _insert_field(conn, entity.yaml_name, entity_id, field_result, field_ids)
            if field_id is not None:
                total += 1
                # Insert field options for enum/multiEnum
                if field_result.field_type in ("enum", "multiEnum"):
                    total += _insert_field_options(conn, field_id, field_result)

        # Insert layouts
        for layout_result in entity.layouts:
            if layout_result.layout_type in ("detail", "edit"):
                total += _insert_detail_layout(
                    conn, entity.yaml_name, entity_id, layout_result.data, field_ids
                )
            elif layout_result.layout_type == "list":
                total += _insert_list_layout(
                    conn, entity.yaml_name, entity_id, layout_result.data, field_ids
                )

    # Insert relationships
    for rel in report.relationships:
        inserted = _insert_relationship(conn, rel, entity_ids)
        if inserted:
            total += 1

    # Insert ConfigurationRun record
    if instance_id is not None:
        _insert_configuration_run(conn, report, instance_id)
        total += 1

    conn.commit()
    return total


def _insert_entity(
    conn: sqlite3.Connection,
    entity: EntityAuditResult,
    entity_ids: dict[str, int],
) -> int | None:
    """Insert an Entity row, skipping if it already exists.

    :param conn: Database connection.
    :param entity: Audited entity result.
    :param entity_ids: Map to populate with yaml_name -> row ID.
    :returns: The entity row ID, or None if skipped.
    """
    # Check for existing entity by code
    code = entity.yaml_name.upper()[:10]
    existing = conn.execute(
        "SELECT id FROM Entity WHERE code = ?", (code,)
    ).fetchone()
    if existing:
        entity_ids[entity.yaml_name] = existing[0]
        return existing[0]

    entity_type = entity.entity_type or "Base"
    is_native = entity.entity_class == EntityClass.NATIVE

    try:
        cursor = conn.execute(
            "INSERT INTO Entity (name, code, entity_type, is_native, "
            "singular_label, plural_label) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                entity.yaml_name,
                code,
                entity_type,
                is_native,
                entity.label_singular,
                entity.label_plural,
            ),
        )
        entity_ids[entity.yaml_name] = cursor.lastrowid
        return cursor.lastrowid
    except sqlite3.IntegrityError as exc:
        logger.warning("Failed to insert entity %s: %s", entity.yaml_name, exc)
        return None


def _insert_field(
    conn: sqlite3.Connection,
    entity_name: str,
    entity_id: int,
    field_result: FieldAuditResult,
    field_ids: dict[tuple[str, str], int],
) -> int | None:
    """Insert a Field row, skipping if it already exists.

    :param conn: Database connection.
    :param entity_name: YAML entity name (for FK map key).
    :param entity_id: Entity row ID.
    :param field_result: Audited field result.
    :param field_ids: Map to populate with (entity_name, field_name) -> row ID.
    :returns: The field row ID, or None if skipped.
    """
    # Check for existing
    existing = conn.execute(
        "SELECT id FROM Field WHERE entity_id = ? AND name = ?",
        (entity_id, field_result.yaml_name),
    ).fetchone()
    if existing:
        field_ids[(entity_name, field_result.yaml_name)] = existing[0]
        return existing[0]

    props = field_result.properties

    try:
        cursor = conn.execute(
            "INSERT INTO Field (entity_id, name, label, field_type, "
            "is_required, default_value, read_only, audited, "
            "max_length, min_value, max_value, is_sorted, display_as_label, "
            "is_native) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entity_id,
                field_result.yaml_name,
                field_result.label,
                field_result.field_type,
                props.get("required", False),
                props.get("default"),
                props.get("readOnly", False),
                props.get("audited", False),
                props.get("maxLength"),
                props.get("min"),
                props.get("max"),
                props.get("isSorted", False),
                props.get("displayAsLabel", False),
                False,  # Audit only captures custom fields
            ),
        )
        field_ids[(entity_name, field_result.yaml_name)] = cursor.lastrowid
        return cursor.lastrowid
    except sqlite3.IntegrityError as exc:
        logger.warning(
            "Failed to insert field %s.%s: %s",
            entity_name, field_result.yaml_name, exc,
        )
        return None


def _insert_field_options(
    conn: sqlite3.Connection,
    field_id: int,
    field_result: FieldAuditResult,
) -> int:
    """Insert FieldOption rows for an enum/multiEnum field.

    :param conn: Database connection.
    :param field_id: Field row ID.
    :param field_result: Audited field result.
    :returns: Number of options inserted.
    """
    options = field_result.properties.get("options", [])
    if not options:
        return 0

    styles = field_result.properties.get("style", {})
    translated = field_result.properties.get("translatedOptions", {})
    default_value = field_result.properties.get("default")

    count = 0
    for i, value in enumerate(options):
        # Check for existing
        existing = conn.execute(
            "SELECT id FROM FieldOption WHERE field_id = ? AND value = ?",
            (field_id, value),
        ).fetchone()
        if existing:
            continue

        label = translated.get(value, value)
        style = styles.get(value)
        is_default = (value == default_value) if default_value else False

        try:
            conn.execute(
                "INSERT INTO FieldOption (field_id, value, label, style, "
                "sort_order, is_default) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (field_id, value, label, style, i, is_default),
            )
            count += 1
        except sqlite3.IntegrityError as exc:
            logger.warning(
                "Failed to insert option %s for field %d: %s",
                value, field_id, exc,
            )

    return count


def _insert_relationship(
    conn: sqlite3.Connection,
    rel: RelationshipAuditResult,
    entity_ids: dict[str, int],
) -> bool:
    """Insert a Relationship row, skipping if entities not in scope.

    :param conn: Database connection.
    :param rel: Audited relationship result.
    :param entity_ids: Map of yaml_name -> entity row ID.
    :returns: True if inserted, False if skipped.
    """
    entity_id = entity_ids.get(rel.entity)
    entity_foreign_id = entity_ids.get(rel.entity_foreign)

    if entity_id is None or entity_foreign_id is None:
        logger.debug(
            "Skipping relationship %s: entity not in scope",
            rel.name,
        )
        return False

    # Check for existing
    existing = conn.execute(
        "SELECT id FROM Relationship WHERE entity_id = ? AND entity_foreign_id = ? "
        "AND link = ? AND link_foreign = ?",
        (entity_id, entity_foreign_id, rel.link, rel.link_foreign),
    ).fetchone()
    if existing:
        return False

    try:
        conn.execute(
            "INSERT INTO Relationship (name, description, entity_id, entity_foreign_id, "
            "link_type, link, link_foreign, label, label_foreign, "
            "relation_name, audited, audited_foreign) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                rel.name,
                f"Discovered by audit: {rel.entity} → {rel.entity_foreign}",
                entity_id,
                entity_foreign_id,
                rel.link_type,
                rel.link,
                rel.link_foreign,
                rel.label,
                rel.label_foreign,
                rel.relation_name,
                rel.audited,
                rel.audited_foreign,
            ),
        )
        return True
    except sqlite3.IntegrityError as exc:
        logger.warning("Failed to insert relationship %s: %s", rel.name, exc)
        return False


def _insert_detail_layout(
    conn: sqlite3.Connection,
    entity_name: str,
    entity_id: int,
    layout_data: dict[str, Any],
    field_ids: dict[tuple[str, str], int],
) -> int:
    """Insert LayoutPanel and LayoutRow records for a detail layout.

    :param conn: Database connection.
    :param entity_name: YAML entity name.
    :param entity_id: Entity row ID.
    :param layout_data: Layout data dict with 'panels' key.
    :param field_ids: Map of (entity_name, field_name) -> field row ID.
    :returns: Number of records inserted.
    """
    panels = layout_data.get("panels", [])
    if not panels:
        return 0

    count = 0
    for i, panel_data in enumerate(panels):
        if not isinstance(panel_data, dict):
            continue

        label = panel_data.get("label", f"Panel {i + 1}")

        # Check for existing panel
        existing = conn.execute(
            "SELECT id FROM LayoutPanel WHERE entity_id = ? AND label = ?",
            (entity_id, label),
        ).fetchone()
        if existing:
            continue

        # Dynamic logic
        dlv = panel_data.get("dynamicLogicVisible")
        dl_attr = None
        dl_value = None
        if isinstance(dlv, dict) and "attribute" in dlv:
            dl_attr = dlv["attribute"]
            dl_value = str(dlv.get("value", ""))

        layout_mode = "tabs" if panel_data.get("tabs") else "rows"

        try:
            cursor = conn.execute(
                "INSERT INTO LayoutPanel (entity_id, label, tab_break, tab_label, "
                "style, hidden, sort_order, layout_mode, "
                "dynamic_logic_attribute, dynamic_logic_value) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entity_id,
                    label,
                    panel_data.get("tabBreak", False),
                    panel_data.get("tabLabel"),
                    panel_data.get("style", "default"),
                    panel_data.get("hidden", False),
                    i,
                    layout_mode,
                    dl_attr,
                    dl_value,
                ),
            )
            panel_id = cursor.lastrowid
            count += 1
        except sqlite3.IntegrityError as exc:
            logger.warning("Failed to insert panel %s: %s", label, exc)
            continue

        # Insert rows
        rows = panel_data.get("rows", [])
        if isinstance(rows, list):
            for j, row in enumerate(rows):
                if not isinstance(row, list):
                    continue

                cell_1_id = None
                cell_2_id = None

                if len(row) >= 1 and row[0] is not None:
                    cell_1_id = field_ids.get((entity_name, row[0]))
                if len(row) >= 2 and row[1] is not None:
                    cell_2_id = field_ids.get((entity_name, row[1]))

                is_full_width = len(row) == 1 or (len(row) == 2 and row[1] is None)

                # Skip rows where we can't resolve any field
                if cell_1_id is None and cell_2_id is None:
                    continue

                try:
                    conn.execute(
                        "INSERT INTO LayoutRow (panel_id, sort_order, "
                        "cell_1_field_id, cell_2_field_id, is_full_width) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (panel_id, j, cell_1_id, cell_2_id, is_full_width),
                    )
                    count += 1
                except sqlite3.IntegrityError as exc:
                    logger.warning(
                        "Failed to insert layout row %d in panel %s: %s",
                        j, label, exc,
                    )

    return count


def _insert_list_layout(
    conn: sqlite3.Connection,
    entity_name: str,
    entity_id: int,
    layout_data: dict[str, Any],
    field_ids: dict[tuple[str, str], int],
) -> int:
    """Insert ListColumn records for a list layout.

    :param conn: Database connection.
    :param entity_name: YAML entity name.
    :param entity_id: Entity row ID.
    :param layout_data: Layout data dict with 'columns' key.
    :param field_ids: Map of (entity_name, field_name) -> field row ID.
    :returns: Number of records inserted.
    """
    columns = layout_data.get("columns", [])
    if not columns:
        return 0

    count = 0
    for i, col_data in enumerate(columns):
        if not isinstance(col_data, dict):
            continue

        field_name = col_data.get("field", "")
        field_id = field_ids.get((entity_name, field_name))
        if field_id is None:
            continue

        # Check for existing
        existing = conn.execute(
            "SELECT id FROM ListColumn WHERE entity_id = ? AND field_id = ?",
            (entity_id, field_id),
        ).fetchone()
        if existing:
            continue

        try:
            conn.execute(
                "INSERT INTO ListColumn (entity_id, field_id, width, sort_order) "
                "VALUES (?, ?, ?, ?)",
                (entity_id, field_id, col_data.get("width"), i),
            )
            count += 1
        except sqlite3.IntegrityError as exc:
            logger.warning(
                "Failed to insert list column %s: %s", field_name, exc,
            )

    return count


def _insert_configuration_run(
    conn: sqlite3.Connection,
    report: AuditReport,
    instance_id: int,
) -> None:
    """Insert a ConfigurationRun record for the audit.

    :param conn: Database connection.
    :param report: Completed audit report.
    :param instance_id: Instance table row ID.
    """
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    outcome = "success" if not report.errors else "error"
    error_msg = "; ".join(report.errors) if report.errors else None

    conn.execute(
        "INSERT INTO ConfigurationRun (instance_id, file_name, operation, "
        "outcome, error_message, started_at, completed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            instance_id,
            f"audit-{report.timestamp}",
            "audit",
            outcome,
            error_msg,
            report.timestamp,
            now,
        ),
    )
