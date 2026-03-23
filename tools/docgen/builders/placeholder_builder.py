"""Sections 6, 7, 8 — Placeholder sections for future capabilities."""

from tools.docgen.models import DocParagraph, DocSection, DocTable

FILTERS_TEXT = (
    "This section will define the named search presets (saved views) configured "
    "in EspoCRM for each entity. Search presets allow administrators and mentors "
    "to quickly access commonly-used filtered views of CRM data.\n\n"
    "Search preset definitions will be added to the YAML program files in a "
    "future release of the implementation tool."
)

RELATIONSHIPS_TEXT = (
    "This section will define the relationships between entities \u2014 the links "
    "that allow EspoCRM to connect related records across entity types.\n\n"
    "Planned relationships include:\n"
    "  \u2022 Account (Company) \u2192 Contact (one-to-many)\n"
    "  \u2022 Account (Company) \u2192 Engagement (one-to-many)\n"
    "  \u2022 Engagement \u2192 Contact / Assigned Mentor (many-to-one)\n"
    "  \u2022 Engagement \u2192 Session (one-to-many)\n"
    "  \u2022 Engagement \u2192 NPS Survey Response (one-to-many)\n"
    "  \u2022 Workshop \u2192 Workshop Attendance (one-to-many)\n"
    "  \u2022 Contact \u2192 Workshop Attendance (one-to-many)\n"
    "  \u2022 Contact \u2192 Dues (one-to-many)"
)

PROCESSES_TEXT = (
    "This section defines conditional field behavior (Dynamic Logic) and "
    "automated field-setting rules (Entity Formula Scripts) configured in EspoCRM."
)

PROCESSES_TABLE = DocTable(
    headers=["Entity", "Trigger", "Condition", "Action"],
    rows=[
        ["Contact", "Display", "Contact Type = Mentor", "Show Mentor panels"],
        ["Contact", "Display", "Contact Type = Client", "Show Client Details panel"],
        ["Contact", "Display", "Mentor Status = Departed", "Show Departure Reason, Departure Date"],
        ["Session", "Display", "Session Type = In-Person", "Show Meeting Location Type"],
        ["Session", "Display", "Meeting Location Type = Other", "Show Location Details"],
        ["Account", "Display", "Registered with State = Yes", "Show registration fields"],
        ["Engagement", "On Save", "Status changed to Assigned AND Mentor Assigned Date is empty", "Set Mentor Assigned Date = today"],
    ],
)


def build_placeholder_sections() -> list[DocSection]:
    """Build Sections 6, 7, 8 — placeholders.

    :returns: List of placeholder DocSections.
    """
    filters = DocSection(title="Filters (Search Presets)", level=1)
    filters.content.append(
        DocParagraph(
            text="Planned \u2014 Not Yet Implemented", style="status"
        )
    )
    filters.content.append(DocParagraph(text=FILTERS_TEXT))

    relationships = DocSection(title="Relationships", level=1)
    relationships.content.append(
        DocParagraph(
            text="Planned \u2014 Not Yet Implemented", style="status"
        )
    )
    relationships.content.append(DocParagraph(text=RELATIONSHIPS_TEXT))

    processes = DocSection(
        title="Processes (Dynamic Logic & Automation)", level=1
    )
    processes.content.append(
        DocParagraph(
            text="Partially Defined \u2014 Not Yet Implemented by Tool",
            style="status",
        )
    )
    processes.content.append(DocParagraph(text=PROCESSES_TEXT))
    processes.content.append(PROCESSES_TABLE)

    return [filters, relationships, processes]
