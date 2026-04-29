"""User Process Guide template.

Generates a Word document combining the business-language process narrative
captured in the client database with the CRM-specific operational detail
captured in the YAML program files. The result serves both end-users
(operational how-to) and process owners (high-level walkthrough).

Document structure:
  1. Process at a Glance
  2. For Process Owners
  3. Step-by-Step User Guide
  4. Field Reference
  5. Statuses and Transitions
  6. Related Records
  7. Open Issues
"""

from __future__ import annotations

from pathlib import Path

from automation.docgen.templates.doc_helpers import (
    add_field_table,
    add_heading,
    add_labeled_paragraph,
    add_meta_table,
    add_page_break,
    add_paragraph,
    add_two_col_table,
    create_document,
    set_draft_header,
    set_footer,
    set_header,
)
from automation.docgen.templates.formatting import (
    META_COL_WIDTHS_PROCESS,
    SUBTITLE_SIZE,
    TITLE_COLOR_RGB,
    TITLE_SIZE,
    TWO_COL_WIDTHS,
    WD_ALIGN_PARAGRAPH,
)

_TYPE_DISPLAY = {
    "varchar": "Text",
    "text": "Text (multi-line)",
    "wysiwyg": "Rich Text",
    "bool": "Yes/No",
    "int": "Whole number",
    "float": "Decimal",
    "date": "Date",
    "datetime": "Date and time",
    "enum": "Choice",
    "multiEnum": "Multiple choice",
    "url": "URL",
    "email": "Email",
    "phone": "Phone",
    "currency": "Currency",
    "address": "Address",
    "relationship": "Linked record",
}


def generate(
    data_dict: dict, output_path: str | Path, is_draft: bool = False
) -> None:
    """Generate a User Process Guide Word document.

    :param data_dict: Data dict from queries.user_process_guide.query().
    :param output_path: Path where the .docx file will be written.
    :param is_draft: If True, add draft indicators.
    """
    doc = create_document(is_draft)
    section = doc.sections[0]

    client_name = data_dict.get("client_name") or "Organization"
    process = data_dict.get("process") or {}
    domain = data_dict.get("domain") or {}
    process_name = process.get("name", "Unknown")
    process_code = process.get("code", "")
    domain_name = domain.get("name", "")
    domain_code = domain.get("code", "")
    process_label = (
        f"{process_name} ({process_code})" if process_code else process_name
    )

    set_header(section, client_name, process_label)
    set_footer(section, f"User Process Guide \u2014 {domain_name} Domain")

    if is_draft:
        set_draft_header(section)

    # Title page
    add_paragraph(
        doc, client_name, bold=True, size=TITLE_SIZE,
        color=TITLE_COLOR_RGB, alignment=WD_ALIGN_PARAGRAPH.CENTER,
        space_after=60,
    )
    add_paragraph(
        doc, process_label, bold=True, size=SUBTITLE_SIZE,
        color=TITLE_COLOR_RGB, alignment=WD_ALIGN_PARAGRAPH.CENTER,
        space_after=200,
    )
    add_paragraph(
        doc, "User Process Guide",
        alignment=WD_ALIGN_PARAGRAPH.CENTER, space_after=400,
    )

    primary_persona = _pick_primary_persona(data_dict.get("personas") or [])
    add_meta_table(doc, [
        ("Domain", f"{domain_name} ({domain_code})" if domain_code else domain_name),
        ("Process Code", process_code),
        ("Primary Persona", primary_persona or "\u2014"),
        ("Trigger Summary", _shorten(process.get("triggers"), 200) or "\u2014"),
    ], META_COL_WIDTHS_PROCESS)

    add_page_break(doc)

    # 1. Process at a Glance
    add_heading(doc, "1. Process at a Glance", level=1)
    desc = process.get("description", "")
    if desc:
        add_paragraph(doc, desc)
    triggers = process.get("triggers", "")
    if triggers:
        add_labeled_paragraph(doc, "When this process runs: ", triggers)
    completion = process.get("completion_criteria", "")
    if completion:
        add_labeled_paragraph(doc, "Defined end state: ", completion)

    # 2. For Process Owners
    add_heading(doc, "2. For Process Owners", level=1)
    add_paragraph(
        doc,
        "This section is a high-level walk-through of who does what and "
        "when, suitable for managers overseeing the process.",
        italic=True,
    )

    personas = data_dict.get("personas") or []
    if personas:
        add_paragraph(doc, "Personas involved:", bold=True)
        for persona in personas:
            name = persona.get("name", "")
            role = persona.get("role", "") or "participant"
            desc_text = persona.get("description") or ""
            add_labeled_paragraph(
                doc, f"{name}",
                f" \u2014 [{role}] {desc_text}" if desc_text else f" \u2014 [{role}]",
            )
    else:
        add_paragraph(doc, "No personas defined.", italic=True)

    steps = data_dict.get("steps") or []
    if steps:
        add_paragraph(doc, "Process flow:", bold=True, space_before=120)
        for i, step in enumerate(steps, 1):
            performer = step.get("performer_name") or "(unassigned)"
            step_name = step.get("name") or f"Step {i}"
            add_paragraph(doc, f"{i}. [{performer}] {step_name}")
    else:
        add_paragraph(doc, "No workflow steps defined.", italic=True)

    decisions = data_dict.get("decisions") or []
    if decisions:
        add_paragraph(doc, "Key decisions made during the process:",
                      bold=True, space_before=120)
        add_two_col_table(
            doc, "ID", "Decision",
            [
                (d.get("identifier", ""),
                 d.get("description") or d.get("title") or "")
                for d in decisions
            ],
            TWO_COL_WIDTHS,
        )

    # 3. Step-by-Step User Guide
    add_heading(doc, "3. Step-by-Step User Guide", level=1)
    add_paragraph(
        doc,
        "Each step below is what an end-user does in the CRM to advance "
        "the process. Field names match the labels visible on the screen.",
        italic=True,
    )

    yaml_by_entity = data_dict.get("yaml_by_entity") or {}
    data_reference = data_dict.get("data_reference") or []
    primary_entities = [r.get("entity_name") for r in data_reference if r.get("entity_name")]

    if not steps:
        add_paragraph(doc, "No workflow steps defined.", italic=True)
    else:
        for i, step in enumerate(steps, 1):
            step_name = step.get("name") or f"Step {i}"
            add_heading(doc, f"Step {i}: {step_name}", level=2)

            performer = step.get("performer_name")
            if performer:
                add_labeled_paragraph(doc, "Performed by: ", performer)

            step_desc = step.get("description") or ""
            if step_desc:
                add_paragraph(doc, step_desc)

            entity_for_step = _guess_entity_for_step(
                step_desc, primary_entities,
            )
            if entity_for_step and entity_for_step in yaml_by_entity:
                yaml_entity = yaml_by_entity[entity_for_step]
                add_labeled_paragraph(
                    doc, "In the CRM: ",
                    f"open the {yaml_entity['label_singular']} record "
                    f"(menu \u2192 {yaml_entity['label_plural']}).",
                )

                step_fields = _fields_touched_by_step(
                    step_desc, data_reference, entity_for_step,
                )
                if step_fields:
                    add_paragraph(doc, "Fields to update at this step:",
                                  bold=True, space_before=60)
                    for f in step_fields:
                        line = _render_field_line(f, yaml_entity)
                        add_paragraph(doc, f"  \u2022 {line}")

    # 4. Field Reference
    add_heading(doc, "4. Field Reference", level=1)
    add_paragraph(
        doc,
        "Every CRM field this process reads or writes, grouped by record type. "
        "Use this as a cheat-sheet while running the process.",
        italic=True,
    )

    if not data_reference:
        add_paragraph(doc, "No fields are referenced by this process.",
                      italic=True)
    else:
        for entity_ref in data_reference:
            entity_name = entity_ref.get("entity_name", "")
            yaml_entity = yaml_by_entity.get(entity_name) or {}
            label = yaml_entity.get("label_singular") or entity_name

            add_heading(doc, f"Record: {label}", level=2)
            entity_desc = yaml_entity.get("description")
            if entity_desc:
                add_paragraph(doc, entity_desc, italic=True)

            fields = entity_ref.get("fields") or []
            if not fields:
                add_paragraph(doc, "No fields recorded for this record type.",
                              italic=True)
                continue

            yaml_fields_by_name = {
                yf["name"]: yf for yf in (yaml_entity.get("fields") or [])
            }

            table_fields: list[dict] = []
            for f in fields:
                yaml_field = yaml_fields_by_name.get(f.get("name") or "") or {}
                values_display = _render_options(yaml_field)
                table_fields.append({
                    "label": yaml_field.get("label") or f.get("label") or f.get("name", ""),
                    "field_type": _TYPE_DISPLAY.get(
                        yaml_field.get("type") or f.get("field_type") or "",
                        yaml_field.get("type") or f.get("field_type") or "",
                    ),
                    "is_required": yaml_field.get("required", False),
                    "values": values_display,
                    "default_value": yaml_field.get("default"),
                    "identifier": f.get("name") or "",
                    "description": (
                        yaml_field.get("description")
                        or f.get("description")
                        or f.get("usage")
                        or ""
                    ),
                })
            add_field_table(doc, table_fields)
            add_paragraph(doc, "")

    # 5. Statuses and Transitions
    status_fields = _collect_status_fields(yaml_by_entity, primary_entities)
    if status_fields:
        add_heading(doc, "5. Statuses and Transitions", level=1)
        add_paragraph(
            doc,
            "Status fields drive what an end-user sees and can do next. "
            "Every allowed value is listed below.",
            italic=True,
        )
        for entity_name, sf in status_fields:
            ent_label = (
                yaml_by_entity.get(entity_name, {}).get("label_singular")
                or entity_name
            )
            add_heading(doc, f"{ent_label} \u2014 {sf['label']}", level=2)
            translated = sf.get("translated_options") or {}
            options = sf.get("options") or []
            if options:
                rows = []
                for opt in options:
                    rows.append((str(opt), translated.get(opt) or ""))
                add_two_col_table(
                    doc, "Value", "Meaning", rows, TWO_COL_WIDTHS,
                )
            else:
                add_paragraph(doc, "No values defined.", italic=True)

    # 6. Related Records
    rel_lines = _collect_relationships(yaml_by_entity, primary_entities)
    if rel_lines:
        add_heading(doc, "6. Related Records", level=1)
        add_paragraph(
            doc,
            "These links determine which records are visible from each other "
            "and how counts and roll-ups work.",
            italic=True,
        )
        for line in rel_lines:
            add_paragraph(doc, f"  \u2022 {line}")

    # 7. Open Issues
    open_issues = data_dict.get("open_issues") or []
    if open_issues:
        add_heading(doc, "7. Open Issues", level=1)
        add_paragraph(
            doc,
            "Outstanding questions or TBDs identified during process "
            "definition that may affect this guide.",
            italic=True,
        )
        add_two_col_table(
            doc, "ID", "Issue",
            [
                (i.get("identifier", ""),
                 i.get("description") or i.get("title") or "")
                for i in open_issues
            ],
            TWO_COL_WIDTHS,
        )

    # YAML load warnings (non-fatal; surface so the reader knows what's missing)
    errors = data_dict.get("yaml_load_errors") or []
    if errors:
        add_heading(doc, "Appendix: YAML Coverage Notes", level=1)
        add_paragraph(
            doc,
            "Some operational detail could not be merged from the YAML "
            "program files. The guide still describes the process in "
            "business terms; the items below indicate where CRM-specific "
            "labels were unavailable.",
            italic=True,
        )
        for err in errors:
            add_paragraph(doc, f"  \u2022 {err}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))


def _pick_primary_persona(personas: list[dict]) -> str:
    """Return the most likely primary persona name for the meta table."""
    for p in personas:
        if (p.get("role") or "").lower() in ("initiator", "performer", "owner"):
            return p.get("name") or ""
    if personas:
        return personas[0].get("name") or ""
    return ""


def _shorten(value, limit: int) -> str:
    """Trim a string to ``limit`` chars with ellipsis."""
    if not value:
        return ""
    s = str(value).strip()
    return s if len(s) <= limit else s[: limit - 1] + "\u2026"


def _guess_entity_for_step(
    step_desc: str, candidate_entities: list[str]
) -> str | None:
    """Best-effort guess of which entity a step touches.

    Looks for a candidate entity name as a whole-word substring of the
    step description. Returns the longest match (so 'PartnerActivity'
    wins over 'Partner').
    """
    if not step_desc or not candidate_entities:
        return None
    desc_lower = step_desc.lower()
    matches = [
        name for name in candidate_entities
        if name and name.lower() in desc_lower
    ]
    if not matches:
        return None
    matches.sort(key=len, reverse=True)
    return matches[0]


def _fields_touched_by_step(
    step_desc: str,
    data_reference: list[dict],
    entity_name: str,
) -> list[dict]:
    """Return fields whose name or label appears in the step description."""
    if not step_desc:
        return []
    desc_lower = step_desc.lower()
    out: list[dict] = []
    for ref in data_reference:
        if ref.get("entity_name") != entity_name:
            continue
        for f in ref.get("fields") or []:
            label = (f.get("label") or "").lower()
            name = (f.get("name") or "").lower()
            if label and label in desc_lower:
                out.append(f)
            elif name and name in desc_lower:
                out.append(f)
    return out


def _render_field_line(field: dict, yaml_entity: dict) -> str:
    """Render a single bullet about a field touched by a step."""
    yaml_fields = {f["name"]: f for f in yaml_entity.get("fields") or []}
    yf = yaml_fields.get(field.get("name") or "") or {}
    label = yf.get("label") or field.get("label") or field.get("name") or ""
    type_display = _TYPE_DISPLAY.get(
        yf.get("type") or field.get("field_type") or "",
        yf.get("type") or field.get("field_type") or "",
    )
    options = _render_options(yf)
    if options and options != "\u2014":
        return f"{label} ({type_display}) — choose one of: {options}"
    return f"{label} ({type_display})"


def _render_options(yaml_field: dict) -> str:
    """Format the allowed values for an enum/multiEnum field."""
    options = yaml_field.get("options") or []
    if not options:
        return "\u2014"
    translated = yaml_field.get("translated_options") or {}
    parts: list[str] = []
    for opt in options:
        label = translated.get(opt)
        parts.append(f"{label} ({opt})" if label and label != opt else str(opt))
    return ", ".join(parts)


def _collect_status_fields(
    yaml_by_entity: dict, entity_names: list[str]
) -> list[tuple[str, dict]]:
    """Return (entity_name, field_dict) pairs for status enum fields."""
    out: list[tuple[str, dict]] = []
    for name in entity_names:
        entity = yaml_by_entity.get(name)
        if not entity:
            continue
        for sf in entity.get("status_fields") or []:
            out.append((name, sf))
    return out


def _collect_relationships(
    yaml_by_entity: dict, entity_names: list[str]
) -> list[str]:
    """Render relationship lines in business language."""
    seen: set[str] = set()
    lines: list[str] = []
    for name in entity_names:
        entity = yaml_by_entity.get(name)
        if not entity:
            continue
        ent_label = entity.get("label_singular") or name
        for rel in entity.get("relationships") or []:
            if not isinstance(rel, dict):
                continue
            rel_name = rel.get("name") or rel.get("link") or ""
            target = rel.get("targetEntity") or rel.get("foreign") or ""
            kind = rel.get("type") or rel.get("kind") or ""
            key = f"{name}:{rel_name}:{target}"
            if key in seen:
                continue
            seen.add(key)
            target_label = (
                yaml_by_entity.get(target, {}).get("label_singular") or target
            )
            if rel_name:
                lines.append(
                    f"{ent_label} \u2192 {target_label}"
                    f"{' (' + kind + ')' if kind else ''} via '{rel_name}'"
                )
            else:
                lines.append(
                    f"{ent_label} \u2192 {target_label}"
                    f"{' (' + kind + ')' if kind else ''}"
                )
    return lines
