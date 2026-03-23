"""Section 2 — Entity reference builder."""

from typing import Any

from tools.docgen.models import DocParagraph, DocSection, DocTable
from tools.docgen.yaml_loader import get_display_name

NATIVE_ENTITIES: set[str] = {"Contact", "Account"}


def build_entity_sections(
    entities: list[tuple[str, dict[str, Any]]],
) -> DocSection:
    """Build Section 2 — Entities.

    :param entities: Ordered list of (entity_name, entity_data).
    :returns: DocSection for entities.
    """
    section = DocSection(title="Entities", level=1)

    for name, data in entities:
        display = get_display_name(name)
        title = f"{display}" if display == name else f"{display} ({name})"
        subsection = DocSection(title=title, level=2)

        # Entity header table
        is_native = name in NATIVE_ENTITIES
        action = data.get("action", "")
        entity_type = data.get("type", "Native" if is_native else "Base")
        singular = data.get("labelSingular", display)
        plural = data.get("labelPlural", f"{display}s")
        stream = "Yes" if data.get("stream", False) else "No"

        if is_native:
            espo_name = name
            type_display = f"Native ({name})"
            deploy = "Field configuration only"
        else:
            espo_name = f"C{name}"
            type_display = f"Custom ({entity_type})"
            deploy = action if action else "Field configuration only"

        header_table = DocTable(
            headers=["Property", "Value"],
            rows=[
                ["EspoCRM Entity Name", espo_name],
                ["Display Name (Singular)", singular],
                ["Display Name (Plural)", plural],
                ["Entity Type", type_display],
                ["Stream Enabled", stream],
                ["Deployment Method", deploy],
            ],
        )
        subsection.content.append(header_table)

        # Description
        desc = data.get("description")
        if desc:
            subsection.content.append(
                DocParagraph(text=desc.strip())
            )
        else:
            subsection.content.append(
                DocParagraph(text="No description provided.")
            )

        section.content.append(subsection)

    return section
