"""Verification Spec builder — External Integration Dependencies section."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from espo_impl.core.models import ProgramFile


def build_external_dependencies_section(
    programs: list[ProgramFile],
) -> str:
    """Build the External Integration Dependencies section content.

    Scans all entities across all program files for fields with
    ``externally_populated`` set to ``True`` and groups them by entity.

    :param programs: List of loaded ProgramFile objects.
    :returns: Markdown content for the section.
    """
    # Collect fields grouped by entity name
    by_entity: dict[str, list[dict[str, str]]] = {}

    for program in programs:
        for entity in program.entities:
            for field in entity.fields:
                if not field.externally_populated:
                    continue
                entry = {
                    "name": field.name,
                    "label": field.label,
                    "type": field.type,
                    "description": field.description or "",
                }
                by_entity.setdefault(entity.name, []).append(entry)

    if not by_entity:
        return (
            "## External Integration Dependencies\n\n"
            "No fields are marked as externally populated.\n"
        )

    lines: list[str] = ["## External Integration Dependencies\n"]
    lines.append(
        "The following fields are populated by external integrations and "
        "are not directly editable by CRM users. Verification should "
        "confirm that integration pipelines are writing to these fields.\n"
    )

    for entity_name in sorted(by_entity):
        lines.append(f"### {entity_name}\n")
        lines.append("| Field | Label | Type | Description |")
        lines.append("|-------|-------|------|-------------|")
        for entry in by_entity[entity_name]:
            desc = entry["description"] or "\u2014"
            lines.append(
                f"| `{entry['name']}` "
                f"| {entry['label']} "
                f"| {entry['type']} "
                f"| {desc} |"
            )
        lines.append("")

    return "\n".join(lines)
