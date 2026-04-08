"""Cross-reference query engine for Impact Analysis.

Implements L2 PRD Section 12.3 — traces downstream effects of changes
for each source record type. Each trace function returns a list of
AffectedRecord instances identifying downstream records that reference
the changed record.

Transitive tracing rule (Section 12.3 preamble):
- Delete operations trace transitively. If deleting an Entity surfaces its
  Fields as affected, the engine also traces each Field's downstream refs.
- Update operations trace one level only.
"""

from __future__ import annotations

import dataclasses
import sqlite3


@dataclasses.dataclass
class AffectedRecord:
    """A record downstream of a change, identified by cross-reference query."""

    table_name: str
    record_id: int
    impact_description: str
    requires_review: bool = True


# ---------------------------------------------------------------------------
# Name lookup helpers
# ---------------------------------------------------------------------------


def _field_label(conn: sqlite3.Connection, field_id: int) -> str:
    row = conn.execute(
        "SELECT name FROM Field WHERE id = ?", (field_id,)
    ).fetchone()
    return row[0] if row else f"[field:{field_id}]"


def _entity_label(conn: sqlite3.Connection, entity_id: int) -> str:
    row = conn.execute(
        "SELECT name, code FROM Entity WHERE id = ?", (entity_id,)
    ).fetchone()
    return f"{row[0]} ({row[1]})" if row else f"[entity:{entity_id}]"


def _process_label(conn: sqlite3.Connection, process_id: int) -> str:
    row = conn.execute(
        "SELECT name, code FROM Process WHERE id = ?", (process_id,)
    ).fetchone()
    return f"{row[0]} ({row[1]})" if row else f"[process:{process_id}]"


def _persona_label(conn: sqlite3.Connection, persona_id: int) -> str:
    row = conn.execute(
        "SELECT name, code FROM Persona WHERE id = ?", (persona_id,)
    ).fetchone()
    return f"{row[0]} ({row[1]})" if row else f"[persona:{persona_id}]"


def _domain_label(conn: sqlite3.Connection, domain_id: int) -> str:
    row = conn.execute(
        "SELECT name, code FROM Domain WHERE id = ?", (domain_id,)
    ).fetchone()
    return f"{row[0]} ({row[1]})" if row else f"[domain:{domain_id}]"


def _step_suffix(step_name: str | None) -> str:
    return f" step '{step_name}'" if step_name else ""


# ---------------------------------------------------------------------------
# Section 12.3.1 — Field Change
# ---------------------------------------------------------------------------


def trace_field_change(
    conn: sqlite3.Connection,
    field_id: int,
    change_type: str,
) -> list[AffectedRecord]:
    """Trace downstream effects of a Field change."""
    if change_type == "insert":
        return []

    results: list[AffectedRecord] = []
    fname = _field_label(conn, field_id)
    verb = "deletion" if change_type == "delete" else "modification"

    # ProcessField (Section 12.3.1)
    for r in conn.execute(
        "SELECT pf.id, p.name, p.code, pf.usage, ps.name "
        "FROM ProcessField pf "
        "JOIN Process p ON pf.process_id = p.id "
        "LEFT JOIN ProcessStep ps ON pf.process_step_id = ps.id "
        "WHERE pf.field_id = ?",
        (field_id,),
    ).fetchall():
        plabel = f"{r[1]} ({r[2]})"
        step = _step_suffix(r[4])
        cons = (
            "will orphan this process field reference"
            if change_type == "delete"
            else "may require process document review"
        )
        desc = (
            f"Process '{plabel}'{step} uses field '{fname}' "
            f"with usage '{r[3]}' — field {verb} {cons}."
        )
        results.append(AffectedRecord("ProcessField", r[0], desc))

    # LayoutRow (Section 12.3.1)
    for r in conn.execute(
        "SELECT lr.id, lp.label, lr.cell_1_field_id, lr.cell_2_field_id "
        "FROM LayoutRow lr "
        "JOIN LayoutPanel lp ON lr.panel_id = lp.id "
        "WHERE lr.cell_1_field_id = ? OR lr.cell_2_field_id = ?",
        (field_id, field_id),
    ).fetchall():
        cell_pos = "cell 1" if r[2] == field_id else "cell 2"
        cons = (
            "will orphan this layout cell"
            if change_type == "delete"
            else "may require layout adjustment"
        )
        desc = (
            f"Layout row on panel '{r[1]}' displays field '{fname}' "
            f"in {cell_pos} — field {verb} {cons}."
        )
        results.append(AffectedRecord("LayoutRow", r[0], desc))

    # ListColumn (Section 12.3.1)
    for r in conn.execute(
        "SELECT lc.id, e.name, e.code "
        "FROM ListColumn lc "
        "JOIN Entity e ON lc.entity_id = e.id "
        "WHERE lc.field_id = ?",
        (field_id,),
    ).fetchall():
        elabel = f"{r[1]} ({r[2]})"
        cons = (
            "will remove this list column"
            if change_type == "delete"
            else "may require list view review"
        )
        desc = (
            f"List column on entity '{elabel}' displays field '{fname}' "
            f"— field {verb} {cons}."
        )
        results.append(AffectedRecord("ListColumn", r[0], desc))

    # Persona (Section 12.3.1)
    for r in conn.execute(
        "SELECT id, name, code FROM Persona WHERE persona_field_id = ?",
        (field_id,),
    ).fetchall():
        plabel = f"{r[1]} ({r[2]})"
        cons = (
            "will invalidate persona mapping"
            if change_type == "delete"
            else "may affect persona mapping"
        )
        desc = (
            f"Persona '{plabel}' is discriminated by field '{fname}' "
            f"— field {verb} {cons}."
        )
        results.append(AffectedRecord("Persona", r[0], desc))

    # Decision — requires_review=False (Section 12.4.2)
    for r in conn.execute(
        "SELECT id, identifier FROM Decision WHERE field_id = ?",
        (field_id,),
    ).fetchall():
        desc = (
            f"Decision '{r[1]}' is scoped to field '{fname}' "
            f"— field {verb} noted for awareness."
        )
        results.append(AffectedRecord("Decision", r[0], desc, requires_review=False))

    # OpenIssue — requires_review=False (Section 12.4.2)
    for r in conn.execute(
        "SELECT id, identifier FROM OpenIssue WHERE field_id = ?",
        (field_id,),
    ).fetchall():
        desc = (
            f"Open issue '{r[1]}' is scoped to field '{fname}' "
            f"— field {verb} noted for awareness."
        )
        results.append(
            AffectedRecord("OpenIssue", r[0], desc, requires_review=False)
        )

    return results


# ---------------------------------------------------------------------------
# Section 12.3.2 — Entity Change
# ---------------------------------------------------------------------------


def trace_entity_change(
    conn: sqlite3.Connection,
    entity_id: int,
    change_type: str,
) -> list[AffectedRecord]:
    """Trace downstream effects of an Entity change."""
    if change_type == "insert":
        return []

    results: list[AffectedRecord] = []
    elabel = _entity_label(conn, entity_id)
    verb = "deletion" if change_type == "delete" else "modification"

    # ProcessEntity
    for r in conn.execute(
        "SELECT pe.id, p.name, p.code, pe.role, ps.name "
        "FROM ProcessEntity pe "
        "JOIN Process p ON pe.process_id = p.id "
        "LEFT JOIN ProcessStep ps ON pe.process_step_id = ps.id "
        "WHERE pe.entity_id = ?",
        (entity_id,),
    ).fetchall():
        plabel = f"{r[1]} ({r[2]})"
        step = _step_suffix(r[4])
        cons = (
            "will orphan this process entity reference"
            if change_type == "delete"
            else "may require process document review"
        )
        desc = (
            f"Process '{plabel}'{step} involves entity '{elabel}' "
            f"with role '{r[3]}' — entity {verb} {cons}."
        )
        results.append(AffectedRecord("ProcessEntity", r[0], desc))

    # Field — transitive on delete
    for r in conn.execute(
        "SELECT id, name FROM Field WHERE entity_id = ?", (entity_id,)
    ).fetchall():
        cons = (
            "will orphan this field"
            if change_type == "delete"
            else "may affect field definitions"
        )
        desc = (
            f"Field '{r[1]}' belongs to entity '{elabel}' "
            f"— entity {verb} {cons}."
        )
        results.append(AffectedRecord("Field", r[0], desc))
        if change_type == "delete":
            results.extend(trace_field_change(conn, r[0], "delete"))

    # Relationship
    for r in conn.execute(
        "SELECT id, name FROM Relationship "
        "WHERE entity_id = ? OR entity_foreign_id = ?",
        (entity_id, entity_id),
    ).fetchall():
        cons = (
            "will orphan this relationship"
            if change_type == "delete"
            else "may affect relationship definition"
        )
        desc = (
            f"Relationship '{r[1]}' connects entity '{elabel}' "
            f"— entity {verb} {cons}."
        )
        results.append(AffectedRecord("Relationship", r[0], desc))

    # LayoutPanel — transitive on delete (rows, tabs)
    for r in conn.execute(
        "SELECT id, label FROM LayoutPanel WHERE entity_id = ?",
        (entity_id,),
    ).fetchall():
        cons = (
            "will orphan this layout panel"
            if change_type == "delete"
            else "may require layout review"
        )
        desc = (
            f"Layout panel '{r[1]}' belongs to entity '{elabel}' "
            f"— entity {verb} {cons}."
        )
        results.append(AffectedRecord("LayoutPanel", r[0], desc))
        if change_type == "delete":
            # Transitive: child rows and tabs
            for lr in conn.execute(
                "SELECT id FROM LayoutRow WHERE panel_id = ?", (r[0],)
            ).fetchall():
                desc_lr = (
                    f"Layout row on panel '{r[1]}' — entity deletion "
                    f"will orphan this layout row."
                )
                results.append(AffectedRecord("LayoutRow", lr[0], desc_lr))
            for lt in conn.execute(
                "SELECT id, label FROM LayoutTab WHERE panel_id = ?", (r[0],)
            ).fetchall():
                desc_lt = (
                    f"Layout tab '{lt[1]}' on panel '{r[1]}' — entity "
                    f"deletion will orphan this layout tab."
                )
                results.append(AffectedRecord("LayoutTab", lt[0], desc_lt))

    # ListColumn
    for r in conn.execute(
        "SELECT lc.id, f.name FROM ListColumn lc "
        "JOIN Field f ON lc.field_id = f.id "
        "WHERE lc.entity_id = ?",
        (entity_id,),
    ).fetchall():
        cons = (
            "will remove this list column"
            if change_type == "delete"
            else "may require list view review"
        )
        desc = (
            f"List column displaying field '{r[1]}' on entity '{elabel}' "
            f"— entity {verb} {cons}."
        )
        results.append(AffectedRecord("ListColumn", r[0], desc))

    # Persona
    for r in conn.execute(
        "SELECT id, name, code FROM Persona WHERE persona_entity_id = ?",
        (entity_id,),
    ).fetchall():
        plabel = f"{r[1]} ({r[2]})"
        cons = (
            "will invalidate persona entity mapping"
            if change_type == "delete"
            else "may affect persona mapping"
        )
        desc = (
            f"Persona '{plabel}' is mapped to entity '{elabel}' "
            f"— entity {verb} {cons}."
        )
        results.append(AffectedRecord("Persona", r[0], desc))

    # Decision — requires_review=False
    for r in conn.execute(
        "SELECT id, identifier FROM Decision WHERE entity_id = ?",
        (entity_id,),
    ).fetchall():
        desc = (
            f"Decision '{r[1]}' is scoped to entity '{elabel}' "
            f"— entity {verb} noted for awareness."
        )
        results.append(AffectedRecord("Decision", r[0], desc, requires_review=False))

    # OpenIssue — requires_review=False
    for r in conn.execute(
        "SELECT id, identifier FROM OpenIssue WHERE entity_id = ?",
        (entity_id,),
    ).fetchall():
        desc = (
            f"Open issue '{r[1]}' is scoped to entity '{elabel}' "
            f"— entity {verb} noted for awareness."
        )
        results.append(
            AffectedRecord("OpenIssue", r[0], desc, requires_review=False)
        )

    # WorkItem — entity_prd
    for r in conn.execute(
        "SELECT id, item_type FROM WorkItem "
        "WHERE entity_id = ? AND item_type = 'entity_prd'",
        (entity_id,),
    ).fetchall():
        desc = (
            f"Work item '{r[1]}' for entity '{elabel}' "
            f"— entity {verb} may require document revision."
        )
        results.append(AffectedRecord("WorkItem", r[0], desc))

    return results


# ---------------------------------------------------------------------------
# Section 12.3.3 — FieldOption Change
# ---------------------------------------------------------------------------


def trace_field_option_change(
    conn: sqlite3.Connection,
    field_option_id: int,
    change_type: str,
) -> list[AffectedRecord]:
    """Trace downstream effects of a FieldOption change."""
    if change_type == "insert":
        return []

    results: list[AffectedRecord] = []

    # Look up the option and its parent field
    row = conn.execute(
        "SELECT fo.value, fo.field_id, f.name "
        "FROM FieldOption fo JOIN Field f ON fo.field_id = f.id "
        "WHERE fo.id = ?",
        (field_option_id,),
    ).fetchone()
    if not row:
        return []

    opt_value, parent_field_id, field_name = row
    verb = "deletion" if change_type == "delete" else "modification"

    # Persona — discriminator match
    for r in conn.execute(
        "SELECT id, name, code FROM Persona "
        "WHERE persona_field_id = ? AND persona_field_value = ?",
        (parent_field_id, opt_value),
    ).fetchall():
        plabel = f"{r[1]} ({r[2]})"
        cons = (
            "will invalidate persona mapping"
            if change_type == "delete"
            else "may invalidate persona mapping"
        )
        desc = (
            f"Persona '{plabel}' is discriminated by field '{field_name}' "
            f"option '{opt_value}' — option {verb} {cons}."
        )
        results.append(AffectedRecord("Persona", r[0], desc))

    # LayoutPanel — dynamic logic match
    for r in conn.execute(
        "SELECT lp.id, lp.label, e.name, e.code "
        "FROM LayoutPanel lp "
        "JOIN Entity e ON lp.entity_id = e.id "
        "WHERE lp.dynamic_logic_attribute = ? AND lp.dynamic_logic_value = ?",
        (field_name, opt_value),
    ).fetchall():
        elabel = f"{r[2]} ({r[3]})"
        cons = (
            "will break visibility condition"
            if change_type == "delete"
            else "may break visibility condition"
        )
        desc = (
            f"Layout panel '{r[1]}' on entity '{elabel}' uses "
            f"field '{field_name}' option '{opt_value}' for visibility "
            f"— option {verb} {cons}."
        )
        results.append(AffectedRecord("LayoutPanel", r[0], desc))

    # Field — default value match (parent field)
    for r in conn.execute(
        "SELECT id, name FROM Field WHERE id = ? AND default_value = ?",
        (parent_field_id, opt_value),
    ).fetchall():
        cons = (
            "will invalidate default value"
            if change_type == "delete"
            else "may invalidate default value"
        )
        desc = (
            f"Field '{r[1]}' has default value '{opt_value}' from this option "
            f"— option {verb} {cons}."
        )
        results.append(AffectedRecord("Field", r[0], desc))

    return results


# ---------------------------------------------------------------------------
# Section 12.3.4 — Process Change
# ---------------------------------------------------------------------------


def trace_process_change(
    conn: sqlite3.Connection,
    process_id: int,
    change_type: str,
) -> list[AffectedRecord]:
    """Trace downstream effects of a Process change."""
    if change_type == "insert":
        return []

    results: list[AffectedRecord] = []
    plabel = _process_label(conn, process_id)
    verb = "deletion" if change_type == "delete" else "modification"

    # ProcessStep — transitive on delete
    for r in conn.execute(
        "SELECT id, name FROM ProcessStep WHERE process_id = ?",
        (process_id,),
    ).fetchall():
        cons = (
            "will orphan this process step"
            if change_type == "delete"
            else "may affect process step"
        )
        desc = (
            f"Process step '{r[1]}' belongs to process '{plabel}' "
            f"— process {verb} {cons}."
        )
        results.append(AffectedRecord("ProcessStep", r[0], desc))
        if change_type == "delete":
            results.extend(trace_process_step_change(conn, r[0], "delete"))

    # ProcessEntity
    for r in conn.execute(
        "SELECT pe.id, e.name, e.code, pe.role, ps.name "
        "FROM ProcessEntity pe "
        "JOIN Entity e ON pe.entity_id = e.id "
        "LEFT JOIN ProcessStep ps ON pe.process_step_id = ps.id "
        "WHERE pe.process_id = ?",
        (process_id,),
    ).fetchall():
        elabel = f"{r[1]} ({r[2]})"
        step = _step_suffix(r[4])
        desc = (
            f"Process entity reference{step} links entity '{elabel}' "
            f"to process '{plabel}' with role '{r[3]}' "
            f"— process {verb} will orphan this reference."
        )
        results.append(AffectedRecord("ProcessEntity", r[0], desc))

    # ProcessField
    for r in conn.execute(
        "SELECT pf.id, f.name, pf.usage, ps.name "
        "FROM ProcessField pf "
        "JOIN Field f ON pf.field_id = f.id "
        "LEFT JOIN ProcessStep ps ON pf.process_step_id = ps.id "
        "WHERE pf.process_id = ?",
        (process_id,),
    ).fetchall():
        step = _step_suffix(r[3])
        desc = (
            f"Process field reference{step} links field '{r[1]}' "
            f"to process '{plabel}' with usage '{r[2]}' "
            f"— process {verb} will orphan this reference."
        )
        results.append(AffectedRecord("ProcessField", r[0], desc))

    # ProcessPersona
    for r in conn.execute(
        "SELECT pp.id, p.name, p.code, pp.role "
        "FROM ProcessPersona pp "
        "JOIN Persona p ON pp.persona_id = p.id "
        "WHERE pp.process_id = ?",
        (process_id,),
    ).fetchall():
        prlabel = f"{r[1]} ({r[2]})"
        desc = (
            f"Process persona reference links persona '{prlabel}' "
            f"to process '{plabel}' with role '{r[3]}' "
            f"— process {verb} will orphan this reference."
        )
        results.append(AffectedRecord("ProcessPersona", r[0], desc))

    # Requirement — transitive on delete
    for r in conn.execute(
        "SELECT id, identifier FROM Requirement WHERE process_id = ?",
        (process_id,),
    ).fetchall():
        cons = (
            "will orphan this requirement"
            if change_type == "delete"
            else "may affect requirement"
        )
        desc = (
            f"Requirement '{r[1]}' belongs to process '{plabel}' "
            f"— process {verb} {cons}."
        )
        results.append(AffectedRecord("Requirement", r[0], desc))
        if change_type == "delete":
            results.extend(trace_requirement_change(conn, r[0], "delete"))

    # Decision — requires_review=False
    for r in conn.execute(
        "SELECT id, identifier FROM Decision WHERE process_id = ?",
        (process_id,),
    ).fetchall():
        desc = (
            f"Decision '{r[1]}' is scoped to process '{plabel}' "
            f"— process {verb} noted for awareness."
        )
        results.append(AffectedRecord("Decision", r[0], desc, requires_review=False))

    # OpenIssue — requires_review=False
    for r in conn.execute(
        "SELECT id, identifier FROM OpenIssue WHERE process_id = ?",
        (process_id,),
    ).fetchall():
        desc = (
            f"Open issue '{r[1]}' is scoped to process '{plabel}' "
            f"— process {verb} noted for awareness."
        )
        results.append(
            AffectedRecord("OpenIssue", r[0], desc, requires_review=False)
        )

    # WorkItem — process_definition
    for r in conn.execute(
        "SELECT id, item_type FROM WorkItem "
        "WHERE process_id = ? AND item_type = 'process_definition'",
        (process_id,),
    ).fetchall():
        desc = (
            f"Work item '{r[1]}' for process '{plabel}' "
            f"— process {verb} may require document revision."
        )
        results.append(AffectedRecord("WorkItem", r[0], desc))

    return results


# ---------------------------------------------------------------------------
# Section 12.3.5 — Persona Change
# ---------------------------------------------------------------------------


def trace_persona_change(
    conn: sqlite3.Connection,
    persona_id: int,
    change_type: str,
) -> list[AffectedRecord]:
    """Trace downstream effects of a Persona change."""
    if change_type == "insert":
        return []

    results: list[AffectedRecord] = []
    plabel = _persona_label(conn, persona_id)
    verb = "deletion" if change_type == "delete" else "modification"

    # ProcessPersona
    for r in conn.execute(
        "SELECT pp.id, p.name, p.code, pp.role "
        "FROM ProcessPersona pp "
        "JOIN Process p ON pp.process_id = p.id "
        "WHERE pp.persona_id = ?",
        (persona_id,),
    ).fetchall():
        prlabel = f"{r[1]} ({r[2]})"
        cons = (
            "will orphan this process persona reference"
            if change_type == "delete"
            else "may require process document review"
        )
        desc = (
            f"Process persona reference links persona '{plabel}' "
            f"to process '{prlabel}' with role '{r[3]}' "
            f"— persona {verb} {cons}."
        )
        results.append(AffectedRecord("ProcessPersona", r[0], desc))

    # ProcessStep — performer_persona_id
    for r in conn.execute(
        "SELECT ps.id, ps.name, p.name, p.code "
        "FROM ProcessStep ps "
        "JOIN Process p ON ps.process_id = p.id "
        "WHERE ps.performer_persona_id = ?",
        (persona_id,),
    ).fetchall():
        prlabel = f"{r[2]} ({r[3]})"
        cons = (
            "will orphan step performer assignment"
            if change_type == "delete"
            else "may affect step performer assignment"
        )
        desc = (
            f"Process step '{r[1]}' in process '{prlabel}' has performer "
            f"persona '{plabel}' — persona {verb} {cons}."
        )
        results.append(AffectedRecord("ProcessStep", r[0], desc))

    return results


# ---------------------------------------------------------------------------
# Section 12.3.6 — Relationship Change
# ---------------------------------------------------------------------------


def trace_relationship_change(
    conn: sqlite3.Connection,
    relationship_id: int,
    change_type: str,
) -> list[AffectedRecord]:
    """Trace downstream effects of a Relationship change.

    Relationships are near-leaf nodes. The PRD specifies LayoutPanel for
    both connected entities and informational Entity impacts.
    """
    if change_type == "insert":
        return []

    results: list[AffectedRecord] = []

    row = conn.execute(
        "SELECT name, entity_id, entity_foreign_id FROM Relationship WHERE id = ?",
        (relationship_id,),
    ).fetchone()
    if not row:
        return []

    rname, eid, efid = row
    verb = "deletion" if change_type == "delete" else "modification"

    # LayoutPanel for both entities
    for r in conn.execute(
        "SELECT lp.id, lp.label, e.name, e.code "
        "FROM LayoutPanel lp JOIN Entity e ON lp.entity_id = e.id "
        "WHERE lp.entity_id IN (?, ?)",
        (eid, efid),
    ).fetchall():
        elabel = f"{r[2]} ({r[3]})"
        desc = (
            f"Layout panel '{r[1]}' on entity '{elabel}' may display "
            f"relationship '{rname}' data — relationship {verb} "
            f"may require layout review."
        )
        results.append(AffectedRecord("LayoutPanel", r[0], desc))

    # Entity — informational (requires_review=False per Section 12.4.2)
    for target_eid in (eid, efid):
        elabel = _entity_label(conn, target_eid)
        desc = (
            f"Entity '{elabel}' is connected by relationship '{rname}' "
            f"— relationship {verb} noted for awareness."
        )
        results.append(
            AffectedRecord("Entity", target_eid, desc, requires_review=False)
        )

    return results


# ---------------------------------------------------------------------------
# Section 12.3.7 — Domain Change
# ---------------------------------------------------------------------------


def trace_domain_change(
    conn: sqlite3.Connection,
    domain_id: int,
    change_type: str,
) -> list[AffectedRecord]:
    """Trace downstream effects of a Domain change."""
    if change_type == "insert":
        return []

    results: list[AffectedRecord] = []
    dlabel = _domain_label(conn, domain_id)
    verb = "deletion" if change_type == "delete" else "modification"

    # Process — transitive on delete
    for r in conn.execute(
        "SELECT id, name, code FROM Process WHERE domain_id = ?",
        (domain_id,),
    ).fetchall():
        plabel = f"{r[1]} ({r[2]})"
        cons = (
            "will orphan this process"
            if change_type == "delete"
            else "may affect process"
        )
        desc = (
            f"Process '{plabel}' belongs to domain '{dlabel}' "
            f"— domain {verb} {cons}."
        )
        results.append(AffectedRecord("Process", r[0], desc))
        if change_type == "delete":
            results.extend(trace_process_change(conn, r[0], "delete"))

    # Domain — sub-domains
    for r in conn.execute(
        "SELECT id, name, code FROM Domain WHERE parent_domain_id = ?",
        (domain_id,),
    ).fetchall():
        sublabel = f"{r[1]} ({r[2]})"
        cons = (
            "will orphan this sub-domain"
            if change_type == "delete"
            else "may affect sub-domain"
        )
        desc = (
            f"Sub-domain '{sublabel}' has parent domain '{dlabel}' "
            f"— domain {verb} {cons}."
        )
        results.append(AffectedRecord("Domain", r[0], desc))

    # Entity
    for r in conn.execute(
        "SELECT id, name, code FROM Entity WHERE primary_domain_id = ?",
        (domain_id,),
    ).fetchall():
        elabel = f"{r[1]} ({r[2]})"
        cons = (
            "will orphan entity domain assignment"
            if change_type == "delete"
            else "may affect entity domain assignment"
        )
        desc = (
            f"Entity '{elabel}' has primary domain '{dlabel}' "
            f"— domain {verb} {cons}."
        )
        results.append(AffectedRecord("Entity", r[0], desc))

    # WorkItem — domain-scoped types
    for r in conn.execute(
        "SELECT id, item_type FROM WorkItem "
        "WHERE domain_id = ? AND item_type IN "
        "('domain_overview', 'domain_reconciliation', 'yaml_generation')",
        (domain_id,),
    ).fetchall():
        desc = (
            f"Work item '{r[1]}' for domain '{dlabel}' "
            f"— domain {verb} may require document revision."
        )
        results.append(AffectedRecord("WorkItem", r[0], desc))

    # Decision — requires_review=False
    for r in conn.execute(
        "SELECT id, identifier FROM Decision WHERE domain_id = ?",
        (domain_id,),
    ).fetchall():
        desc = (
            f"Decision '{r[1]}' is scoped to domain '{dlabel}' "
            f"— domain {verb} noted for awareness."
        )
        results.append(AffectedRecord("Decision", r[0], desc, requires_review=False))

    # OpenIssue — requires_review=False
    for r in conn.execute(
        "SELECT id, identifier FROM OpenIssue WHERE domain_id = ?",
        (domain_id,),
    ).fetchall():
        desc = (
            f"Open issue '{r[1]}' is scoped to domain '{dlabel}' "
            f"— domain {verb} noted for awareness."
        )
        results.append(
            AffectedRecord("OpenIssue", r[0], desc, requires_review=False)
        )

    return results


# ---------------------------------------------------------------------------
# Section 12.3.8 — Requirement Change
# ---------------------------------------------------------------------------


def trace_requirement_change(
    conn: sqlite3.Connection,
    requirement_id: int,
    change_type: str,
) -> list[AffectedRecord]:
    """Trace downstream effects of a Requirement change."""
    if change_type == "insert":
        return []

    results: list[AffectedRecord] = []
    row = conn.execute(
        "SELECT identifier FROM Requirement WHERE id = ?",
        (requirement_id,),
    ).fetchone()
    rlabel = row[0] if row else f"[requirement:{requirement_id}]"
    verb = "deletion" if change_type == "delete" else "modification"

    # Decision — requires_review=False
    for r in conn.execute(
        "SELECT id, identifier FROM Decision WHERE requirement_id = ?",
        (requirement_id,),
    ).fetchall():
        desc = (
            f"Decision '{r[1]}' is scoped to requirement '{rlabel}' "
            f"— requirement {verb} noted for awareness."
        )
        results.append(AffectedRecord("Decision", r[0], desc, requires_review=False))

    # OpenIssue — requires_review=False
    for r in conn.execute(
        "SELECT id, identifier FROM OpenIssue WHERE requirement_id = ?",
        (requirement_id,),
    ).fetchall():
        desc = (
            f"Open issue '{r[1]}' is scoped to requirement '{rlabel}' "
            f"— requirement {verb} noted for awareness."
        )
        results.append(
            AffectedRecord("OpenIssue", r[0], desc, requires_review=False)
        )

    return results


# ---------------------------------------------------------------------------
# Section 12.3.9 — ProcessStep Change
# ---------------------------------------------------------------------------


def trace_process_step_change(
    conn: sqlite3.Connection,
    process_step_id: int,
    change_type: str,
) -> list[AffectedRecord]:
    """Trace downstream effects of a ProcessStep change.

    Note: ProcessPersona does not have process_step_id in the current schema
    (Section 12.3.9 mentions it conditionally). Only ProcessEntity and
    ProcessField are queried here.
    """
    if change_type == "insert":
        return []

    results: list[AffectedRecord] = []
    row = conn.execute(
        "SELECT ps.name, p.name, p.code "
        "FROM ProcessStep ps JOIN Process p ON ps.process_id = p.id "
        "WHERE ps.id = ?",
        (process_step_id,),
    ).fetchone()
    if not row:
        return []
    step_name, proc_name, proc_code = row
    plabel = f"{proc_name} ({proc_code})"
    verb = "deletion" if change_type == "delete" else "modification"

    # ProcessEntity at step level
    for r in conn.execute(
        "SELECT pe.id, e.name, e.code, pe.role "
        "FROM ProcessEntity pe "
        "JOIN Entity e ON pe.entity_id = e.id "
        "WHERE pe.process_step_id = ?",
        (process_step_id,),
    ).fetchall():
        elabel = f"{r[1]} ({r[2]})"
        desc = (
            f"Process entity reference at step '{step_name}' in "
            f"process '{plabel}' links entity '{elabel}' with role "
            f"'{r[3]}' — step {verb} will orphan this reference."
        )
        results.append(AffectedRecord("ProcessEntity", r[0], desc))

    # ProcessField at step level
    for r in conn.execute(
        "SELECT pf.id, f.name, pf.usage "
        "FROM ProcessField pf "
        "JOIN Field f ON pf.field_id = f.id "
        "WHERE pf.process_step_id = ?",
        (process_step_id,),
    ).fetchall():
        desc = (
            f"Process field reference at step '{step_name}' in "
            f"process '{plabel}' links field '{r[1]}' with usage "
            f"'{r[2]}' — step {verb} will orphan this reference."
        )
        results.append(AffectedRecord("ProcessField", r[0], desc))

    return results


# ---------------------------------------------------------------------------
# Section 12.3.10 — Decision and OpenIssue Changes
# ---------------------------------------------------------------------------


def trace_decision_change(
    conn: sqlite3.Connection,
    decision_id: int,
    change_type: str,
) -> list[AffectedRecord]:
    """Decision changes produce no downstream impacts (leaf node)."""
    return []


def trace_open_issue_change(
    conn: sqlite3.Connection,
    open_issue_id: int,
    change_type: str,
) -> list[AffectedRecord]:
    """OpenIssue changes produce no downstream impacts (leaf node)."""
    return []


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_TRACE_DISPATCH: dict[str, object] = {
    "Field": trace_field_change,
    "Entity": trace_entity_change,
    "FieldOption": trace_field_option_change,
    "Process": trace_process_change,
    "Persona": trace_persona_change,
    "Relationship": trace_relationship_change,
    "Domain": trace_domain_change,
    "Requirement": trace_requirement_change,
    "ProcessStep": trace_process_step_change,
    "Decision": trace_decision_change,
    "OpenIssue": trace_open_issue_change,
}


def trace_change(
    conn: sqlite3.Connection,
    table_name: str,
    record_id: int,
    change_type: str,
) -> list[AffectedRecord]:
    """Dispatch to the correct trace function based on table_name."""
    fn = _TRACE_DISPATCH.get(table_name)
    if fn is None:
        return []
    return fn(conn, record_id, change_type)


# ---------------------------------------------------------------------------
# Batch query consolidation (Section 12.9.3)
# ---------------------------------------------------------------------------


def batch_trace_changes(
    conn: sqlite3.Connection,
    changes: list[tuple[str, int, str]],
) -> dict[tuple[str, int], list[AffectedRecord]]:
    """Process multiple changes with query consolidation.

    Groups changes by (table_name, change_type) and runs consolidated
    queries where possible. Falls back to individual queries for tables
    without batch implementation.

    :param changes: List of (table_name, record_id, change_type) tuples.
    :returns: Dict mapping (table_name, record_id) to affected records.
    """
    results: dict[tuple[str, int], list[AffectedRecord]] = {}

    # Group by (table_name, change_type)
    groups: dict[tuple[str, str], list[int]] = {}
    for table, rid, ct in changes:
        groups.setdefault((table, ct), []).append(rid)

    for (table, ct), rids in groups.items():
        unique_ids = list(set(rids))

        if table == "Field" and len(unique_ids) > 1:
            batch = _batch_field_trace(conn, unique_ids, ct)
            for rid, affected in batch.items():
                results[(table, rid)] = affected
        else:
            for rid in unique_ids:
                results[(table, rid)] = trace_change(conn, table, rid, ct)

    return results


def _batch_field_trace(
    conn: sqlite3.Connection,
    field_ids: list[int],
    change_type: str,
) -> dict[int, list[AffectedRecord]]:
    """Consolidated field trace — one query per cross-ref table.

    Runs 6 queries total instead of N * 6 for N fields.
    """
    results: dict[int, list[AffectedRecord]] = {fid: [] for fid in field_ids}
    verb = "deletion" if change_type == "delete" else "modification"

    # Batch name lookups
    ph = ",".join("?" * len(field_ids))
    names: dict[int, str] = {}
    for r in conn.execute(
        f"SELECT id, name FROM Field WHERE id IN ({ph})", field_ids  # noqa: S608
    ).fetchall():
        names[r[0]] = r[1]

    def fname(fid: int) -> str:
        return names.get(fid, f"[field:{fid}]")

    # 1. ProcessField
    for r in conn.execute(
        f"SELECT pf.id, pf.field_id, p.name, p.code, pf.usage, ps.name "  # noqa: S608
        f"FROM ProcessField pf "
        f"JOIN Process p ON pf.process_id = p.id "
        f"LEFT JOIN ProcessStep ps ON pf.process_step_id = ps.id "
        f"WHERE pf.field_id IN ({ph})",
        field_ids,
    ).fetchall():
        fid = r[1]
        plabel = f"{r[2]} ({r[3]})"
        step = _step_suffix(r[5])
        cons = (
            "will orphan this process field reference"
            if change_type == "delete"
            else "may require process document review"
        )
        desc = (
            f"Process '{plabel}'{step} uses field '{fname(fid)}' "
            f"with usage '{r[4]}' — field {verb} {cons}."
        )
        results[fid].append(AffectedRecord("ProcessField", r[0], desc))

    # 2. LayoutRow — uses OR on two columns
    for r in conn.execute(
        f"SELECT lr.id, lr.cell_1_field_id, lr.cell_2_field_id, lp.label "  # noqa: S608
        f"FROM LayoutRow lr "
        f"JOIN LayoutPanel lp ON lr.panel_id = lp.id "
        f"WHERE lr.cell_1_field_id IN ({ph}) OR lr.cell_2_field_id IN ({ph})",
        field_ids + field_ids,
    ).fetchall():
        field_id_set = set(field_ids)
        cons = (
            "will orphan this layout cell"
            if change_type == "delete"
            else "may require layout adjustment"
        )
        if r[1] in field_id_set:
            desc = (
                f"Layout row on panel '{r[3]}' displays field "
                f"'{fname(r[1])}' in cell 1 — field {verb} {cons}."
            )
            results[r[1]].append(AffectedRecord("LayoutRow", r[0], desc))
        if r[2] in field_id_set and r[2] != r[1]:
            desc = (
                f"Layout row on panel '{r[3]}' displays field "
                f"'{fname(r[2])}' in cell 2 — field {verb} {cons}."
            )
            results[r[2]].append(AffectedRecord("LayoutRow", r[0], desc))

    # 3. ListColumn
    for r in conn.execute(
        f"SELECT lc.id, lc.field_id, e.name, e.code "  # noqa: S608
        f"FROM ListColumn lc "
        f"JOIN Entity e ON lc.entity_id = e.id "
        f"WHERE lc.field_id IN ({ph})",
        field_ids,
    ).fetchall():
        fid = r[1]
        elabel = f"{r[2]} ({r[3]})"
        cons = (
            "will remove this list column"
            if change_type == "delete"
            else "may require list view review"
        )
        desc = (
            f"List column on entity '{elabel}' displays field '{fname(fid)}' "
            f"— field {verb} {cons}."
        )
        results[fid].append(AffectedRecord("ListColumn", r[0], desc))

    # 4. Persona
    for r in conn.execute(
        f"SELECT id, persona_field_id, name, code FROM Persona "  # noqa: S608
        f"WHERE persona_field_id IN ({ph})",
        field_ids,
    ).fetchall():
        fid = r[1]
        plabel = f"{r[2]} ({r[3]})"
        cons = (
            "will invalidate persona mapping"
            if change_type == "delete"
            else "may affect persona mapping"
        )
        desc = (
            f"Persona '{plabel}' is discriminated by field '{fname(fid)}' "
            f"— field {verb} {cons}."
        )
        results[fid].append(AffectedRecord("Persona", r[0], desc))

    # 5. Decision — requires_review=False
    for r in conn.execute(
        f"SELECT id, field_id, identifier FROM Decision "  # noqa: S608
        f"WHERE field_id IN ({ph})",
        field_ids,
    ).fetchall():
        fid = r[1]
        desc = (
            f"Decision '{r[2]}' is scoped to field '{fname(fid)}' "
            f"— field {verb} noted for awareness."
        )
        results[fid].append(
            AffectedRecord("Decision", r[0], desc, requires_review=False)
        )

    # 6. OpenIssue — requires_review=False
    for r in conn.execute(
        f"SELECT id, field_id, identifier FROM OpenIssue "  # noqa: S608
        f"WHERE field_id IN ({ph})",
        field_ids,
    ).fetchall():
        fid = r[1]
        desc = (
            f"Open issue '{r[2]}' is scoped to field '{fname(fid)}' "
            f"— field {verb} noted for awareness."
        )
        results[fid].append(
            AffectedRecord("OpenIssue", r[0], desc, requires_review=False)
        )

    return results
