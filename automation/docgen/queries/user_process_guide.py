"""Data query for User Process Guide generation.

Mirrors the DB-side queries used by ``process_document.query`` and adds a
YAML loading step. The User Process Guide combines the business-language
process narrative captured during Phase 4 (Process, ProcessStep,
ProcessPersona, Requirement, ProcessEntity, ProcessField, OpenIssue) with
the operational detail captured in the YAML program files (entity labels,
field labels, layouts, enum values, relationships, workflows). The result
is one document per process aimed at both end-users (operational how-to)
and process owners (high-level walkthrough).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from automation.docgen.queries import get_client_row


def query(
    conn: sqlite3.Connection,
    work_item_id: int,
    master_conn: sqlite3.Connection | None = None,
    project_folder: str | Path | None = None,
) -> dict:
    """Assemble the data dictionary for a User Process Guide.

    Note: ``project_folder`` is required to populate ``yaml_by_entity``.
    When omitted, the data dict still contains all DB-derived sections
    but the template will fall back to business-language references
    rather than the actual CRM entity/field labels.

    :param conn: Client database connection.
    :param work_item_id: The ``user_process_guide`` WorkItem.id.
    :param master_conn: Master database connection (for Client record).
    :param project_folder: Root of the client's project repository,
        used to load YAML program files from ``{project_folder}/programs/``.
    :returns: Data dictionary for the User Process Guide template.
    """
    data: dict = {
        "work_item_id": work_item_id,
        "client_name": None,
        "client_short_name": None,
        "process": None,
        "domain": None,
        "personas": [],
        "steps": [],
        "requirements": [],
        "data_reference": [],
        "decisions": [],
        "open_issues": [],
        "yaml_by_entity": {},
        "yaml_load_errors": [],
    }

    if master_conn:
        row = get_client_row(master_conn, conn, columns="name, code")
        if row:
            data["client_name"] = row[0]
            data["client_short_name"] = row[1]

    wi = conn.execute(
        "SELECT process_id FROM WorkItem WHERE id = ?", (work_item_id,)
    ).fetchone()
    if not wi or not wi[0]:
        return data
    process_id = wi[0]

    # Process record
    row = conn.execute(
        "SELECT id, name, code, description, triggers, completion_criteria, "
        "domain_id, sort_order "
        "FROM Process WHERE id = ?",
        (process_id,),
    ).fetchone()
    if not row:
        return data

    data["process"] = {
        "id": row[0], "name": row[1], "code": row[2], "description": row[3],
        "triggers": row[4], "completion_criteria": row[5],
        "domain_id": row[6], "sort_order": row[7],
    }

    # Domain
    domain_row = conn.execute(
        "SELECT id, name, code FROM Domain WHERE id = ?", (row[6],)
    ).fetchone()
    if domain_row:
        data["domain"] = {
            "id": domain_row[0], "name": domain_row[1], "code": domain_row[2],
        }

    # Personas with roles
    persona_rows = conn.execute(
        "SELECT per.id, per.name, per.code, per.description, pp.role "
        "FROM ProcessPersona pp "
        "JOIN Persona per ON pp.persona_id = per.id "
        "WHERE pp.process_id = ? ORDER BY per.code",
        (process_id,),
    ).fetchall()
    data["personas"] = [
        {"id": r[0], "name": r[1], "code": r[2], "description": r[3], "role": r[4]}
        for r in persona_rows
    ]

    # Workflow steps
    step_rows = conn.execute(
        "SELECT ps.id, ps.name, ps.description, ps.step_type, "
        "ps.sort_order, per.name AS performer_name, per.code AS performer_code "
        "FROM ProcessStep ps "
        "LEFT JOIN Persona per ON ps.performer_persona_id = per.id "
        "WHERE ps.process_id = ? ORDER BY ps.sort_order",
        (process_id,),
    ).fetchall()
    data["steps"] = [
        {
            "id": r[0], "name": r[1], "description": r[2],
            "step_type": r[3], "sort_order": r[4],
            "performer_name": r[5], "performer_code": r[6],
        }
        for r in step_rows
    ]

    # Requirements
    req_rows = conn.execute(
        "SELECT identifier, description, priority, status "
        "FROM Requirement WHERE process_id = ? ORDER BY identifier",
        (process_id,),
    ).fetchall()
    data["requirements"] = [
        {"identifier": r[0], "description": r[1], "priority": r[2], "status": r[3]}
        for r in req_rows
    ]

    # Data references grouped by entity
    entity_rows = conn.execute(
        "SELECT DISTINCT e.id, e.name, e.code "
        "FROM ProcessEntity pe "
        "JOIN Entity e ON pe.entity_id = e.id "
        "WHERE pe.process_id = ? ORDER BY e.name",
        (process_id,),
    ).fetchall()

    referenced_entity_names: list[str] = []
    for er in entity_rows:
        entity_id, entity_name, entity_code = er
        referenced_entity_names.append(entity_name)
        field_rows = conn.execute(
            "SELECT f.name, f.label, f.field_type, pf.usage, pf.description "
            "FROM ProcessField pf "
            "JOIN Field f ON pf.field_id = f.id "
            "WHERE pf.process_id = ? AND f.entity_id = ? "
            "ORDER BY f.name",
            (process_id, entity_id),
        ).fetchall()
        data["data_reference"].append({
            "entity_name": entity_name,
            "entity_code": entity_code,
            "fields": [
                {"name": fr[0], "label": fr[1], "field_type": fr[2],
                 "usage": fr[3], "description": fr[4]}
                for fr in field_rows
            ],
        })

    # Decisions
    decisions = conn.execute(
        "SELECT identifier, title, description, status "
        "FROM Decision WHERE process_id = ? ORDER BY identifier",
        (process_id,),
    ).fetchall()
    data["decisions"] = [
        {"identifier": r[0], "title": r[1], "description": r[2], "status": r[3]}
        for r in decisions
    ]

    # Open issues
    issues = conn.execute(
        "SELECT identifier, title, description, status, priority "
        "FROM OpenIssue WHERE process_id = ? ORDER BY identifier",
        (process_id,),
    ).fetchall()
    data["open_issues"] = [
        {"identifier": r[0], "title": r[1], "description": r[2],
         "status": r[3], "priority": r[4]}
        for r in issues
    ]

    # YAML program file enrichment
    if project_folder is not None:
        yaml_by_entity, errors = _load_yaml_for_entities(
            project_folder, referenced_entity_names,
        )
        data["yaml_by_entity"] = yaml_by_entity
        data["yaml_load_errors"] = errors

    return data


def _load_yaml_for_entities(
    project_folder: str | Path,
    entity_names: list[str],
) -> tuple[dict, list[str]]:
    """Load YAML program files and project them onto the requested entities.

    Reuses ``tools.docgen.yaml_loader.load_programs`` so the parsing rules
    (file discovery, multi-file merge, full_rebuild skip) stay aligned with
    the existing Verification Spec generator. Only entities present in
    ``entity_names`` are returned, keeping the dict size proportional to
    the process being documented.

    :param project_folder: Project repo root.
    :param entity_names: Entity names referenced by this process.
    :returns: Tuple of (yaml_by_entity, errors). ``yaml_by_entity`` maps
        entity name to a dict containing the relevant YAML projections.
        ``errors`` is a list of human-readable warnings (non-fatal).
    """
    errors: list[str] = []
    programs_dir = Path(project_folder) / "programs"
    if not programs_dir.is_dir():
        errors.append(f"programs/ directory not found at {programs_dir}")
        return {}, errors

    try:
        from tools.docgen.yaml_loader import load_programs
    except ImportError as exc:
        errors.append(f"YAML loader unavailable: {exc}")
        return {}, errors

    try:
        all_entities = load_programs(programs_dir)
    except Exception as exc:
        errors.append(f"Failed to load YAML files: {exc}")
        return {}, errors

    requested = set(entity_names)
    by_entity: dict = {}
    for name, raw in all_entities.items():
        if name not in requested:
            continue
        by_entity[name] = _project_entity_yaml(name, raw)

    missing = requested - set(by_entity.keys())
    for name in sorted(missing):
        errors.append(
            f"Entity '{name}' referenced by process but not found in any YAML file"
        )

    return by_entity, errors


def _project_entity_yaml(entity_name: str, raw: dict) -> dict:
    """Reduce raw YAML entity data to the fields a User Process Guide needs.

    :param entity_name: Entity name (YAML key).
    :param raw: Raw entity dict from ``load_programs``.
    :returns: Projected dict with labels, fields, status enums, layout
        panels, relationships, and workflows.
    """
    labels = raw.get("labels") or {}
    label_singular = labels.get("singular") or entity_name
    label_plural = labels.get("plural") or f"{entity_name}s"

    fields_raw = raw.get("fields") or []
    fields: list[dict] = []
    status_fields: list[dict] = []
    for f in fields_raw:
        if not isinstance(f, dict):
            continue
        name = f.get("name") or ""
        label = f.get("label") or _humanize(name)
        ftype = f.get("type") or ""
        is_required = bool(f.get("required"))
        description = f.get("description") or ""
        options = f.get("options") or []
        translated = f.get("translatedOptions") or {}
        default = f.get("default")

        field_dict = {
            "name": name,
            "label": label,
            "type": ftype,
            "required": is_required,
            "description": description,
            "options": options,
            "translated_options": translated,
            "default": default,
        }
        fields.append(field_dict)
        if ftype in ("enum", "multiEnum") and (
            "status" in name.lower() or name.lower().endswith("state")
        ):
            status_fields.append(field_dict)

    layout = raw.get("layout") or {}
    panels = layout.get("detail") or []
    panel_summaries: list[dict] = []
    for p in panels:
        if not isinstance(p, dict):
            continue
        panel_summaries.append({
            "label": p.get("label") or "",
            "tab": p.get("tabLabel") or "",
            "rows": p.get("rows") or [],
            "visible_when": p.get("visibleWhen") or None,
        })

    relationships = raw.get("relationships") or []

    workflows_raw = raw.get("workflows") or []
    workflow_summaries: list[dict] = []
    for w in workflows_raw:
        if not isinstance(w, dict):
            continue
        workflow_summaries.append({
            "name": w.get("name") or "",
            "trigger": w.get("trigger") or w.get("when") or "",
            "actions": w.get("actions") or [],
        })

    return {
        "label_singular": label_singular,
        "label_plural": label_plural,
        "description": raw.get("description") or "",
        "fields": fields,
        "status_fields": status_fields,
        "panels": panel_summaries,
        "relationships": relationships,
        "workflows": workflow_summaries,
    }


def _humanize(name: str) -> str:
    """Convert a camelCase or c-prefixed YAML field name to a human label.

    :param name: Raw YAML field name (e.g. 'cMentorStatus').
    :returns: Best-effort label (e.g. 'Mentor Status').
    """
    if not name:
        return ""
    if name.startswith("c") and len(name) > 1 and name[1].isupper():
        name = name[1:]
    out: list[str] = []
    for i, ch in enumerate(name):
        if i and ch.isupper() and not name[i - 1].isupper():
            out.append(" ")
        out.append(ch)
    return "".join(out).strip().title()
