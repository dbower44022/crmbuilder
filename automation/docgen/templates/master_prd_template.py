"""Master PRD document template.

Generates a Word document matching the structure and formatting of the
prompt-generated Master PRD: metadata table, organization overview, persona
detail tables, tier definitions, process tier summary, domain detail tables
with process tables, cross-domain service tables, and system scope.
"""

from __future__ import annotations

from pathlib import Path

from automation.docgen.templates.doc_helpers import (
    add_data_row,
    add_header_row,
    add_heading,
    add_labeled_paragraph,
    add_meta_table,
    add_page_break,
    add_paragraph,
    create_document,
    set_draft_header,
    set_footer,
    set_header,
)
from automation.docgen.templates.formatting import (
    META_COL_WIDTHS_MASTER_PRD,
    SUBTITLE_SIZE,
    TITLE_COLOR_RGB,
    TITLE_SIZE,
    WD_ALIGN_PARAGRAPH,
)

# ── Tier definitions (static) ──────────────────────────────────────────���───

TIER_DEFINITIONS = [
    ("Core", "Required for launch. The organization cannot operate the "
     "related domain without these processes in place."),
    ("Important", "Required within 60 days of launch. Operations can begin "
     "without them, but they are needed to reach full capability."),
    ("Enhancement", "Valuable but can be deferred to a later phase without "
     "impacting launch or near-term operations."),
    ("Out of Scope", "Identified as a future need but not included in this "
     "implementation cycle."),
]


def generate(data_dict: dict, output_path: str | Path, is_draft: bool = False) -> None:
    """Generate a Master PRD Word document.

    :param data_dict: Data dictionary from queries.master_prd.query().
    :param output_path: Path where the .docx file will be written.
    :param is_draft: If True, add draft indicators.
    """
    doc = create_document(is_draft)
    section = doc.sections[0]

    client_name = data_dict.get("client_name") or "Organization"
    client_code = data_dict.get("client_short_name") or ""
    set_header(section, client_name, "Master PRD")
    set_footer(section, f"Master PRD \u2014 {client_name}")

    if is_draft:
        set_draft_header(section)

    # ── Title page ──────────────────────────────────────────────────────

    add_paragraph(doc, "Master PRD", bold=True, size=TITLE_SIZE,
                  color=TITLE_COLOR_RGB, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  space_after=60)
    add_paragraph(doc, client_name, bold=False, size=SUBTITLE_SIZE,
                  color=TITLE_COLOR_RGB, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  space_after=400)

    add_page_break(doc)

    # ── Metadata table ──────────────────────────────────────────────────

    last_updated = data_dict.get("last_updated") or ""
    add_meta_table(doc, [
        ("Client", client_name),
        ("Client Code", client_code),
        ("Last Updated", last_updated),
        ("Status", "Draft \u2014 Pending Stakeholder Review"),
    ])
    add_paragraph(doc)  # spacer

    # ── Section 1: Organization Overview ─────────────────────────────────

    add_heading(doc, "1. Organization Overview", level=1)
    overview = data_dict.get("organization_overview") or ""
    if overview:
        for para_text in overview.split("\n\n"):
            stripped = para_text.strip()
            if stripped:
                add_paragraph(doc, stripped)
    else:
        add_paragraph(doc, "Organization overview not yet defined.", italic=True)

    # ── Section 2: Personas ──────────────────────────────────────────────

    add_heading(doc, "2. Personas", level=1)
    personas = data_dict.get("personas", [])

    if personas:
        add_paragraph(
            doc,
            "The following personas represent the distinct roles that interact "
            "with or are tracked by the CRM. Each persona is assigned a permanent "
            "identifier and described in terms of role responsibilities and the "
            "capabilities the CRM delivers to support that role.",
        )

        domains = data_dict.get("domains", [])

        for persona in personas:
            name = persona.get("name", "")
            code = persona.get("code", "")

            add_heading(doc, f"{code}: {name}", level=2)

            responsibilities = persona.get("responsibilities", [])
            crm_capabilities = persona.get("crm_capabilities", [])
            primary_domains = persona.get("primary_domains", [])

            # Build primary domains list from persona data or infer from
            # domain process-persona links
            if not primary_domains:
                primary_domains = _infer_primary_domains(persona, domains)

            rows = [
                ("Identifier", [code]),
                ("Responsibilities", responsibilities
                 if responsibilities else [persona.get("description", "") or "\u2014"]),
                ("What the CRM Provides", crm_capabilities
                 if crm_capabilities else ["\u2014"]),
                ("Primary Domains", primary_domains if primary_domains else ["\u2014"]),
            ]
            add_meta_table(doc, rows, widths=META_COL_WIDTHS_MASTER_PRD)
            add_paragraph(doc)  # spacer
    else:
        add_paragraph(doc, "No personas defined.", italic=True)

    # ── Section 3: Key Business Domains ──────────────────────────────────

    add_page_break(doc)
    add_heading(doc, "3. Key Business Domains", level=1)

    domains = data_dict.get("domains", [])
    services = data_dict.get("services", [])

    # 3a: Implementation Tier Definitions
    add_heading(doc, "Implementation Tier Definitions", level=2)
    tier_widths = [2000, 7360]
    tier_table = doc.add_table(rows=1, cols=2)
    tier_table.autofit = False
    add_header_row(tier_table, ["Tier", "Definition"], tier_widths)
    for idx, (tier_name, tier_def) in enumerate(TIER_DEFINITIONS):
        add_data_row(tier_table, [tier_name, tier_def], tier_widths,
                     shaded=idx % 2 == 1, bold_indices={0})
    add_paragraph(doc)

    # 3b: Process Tier Summary
    _render_process_tier_summary(doc, domains)

    # 3c: Domain Processing Order
    _render_domain_processing_order(doc, domains)

    # 3d: Individual domain sections with process tables
    if domains:
        for domain in domains:
            _render_domain_section(doc, domain, personas)
    else:
        add_paragraph(doc, "No domains defined.", italic=True)

    # ── Section 4: Cross-Domain Services ─────────────────────────────────

    if services:
        add_heading(doc, "4. Cross-Domain Services", level=1)
        add_paragraph(
            doc,
            "Cross-Domain Services are shared platform capabilities consumed "
            "by multiple domains. They are not owned by any single domain but "
            "provide consistent, centrally managed functions that all consuming "
            "domains can rely on.",
        )

        for svc in services:
            _render_service_section(doc, svc, domains)

    # ── Section 5: System Scope ──────────────────────────────────────────

    scope = data_dict.get("system_scope", {})
    section_num = 5 if services else 4
    _render_system_scope(doc, scope, section_num)

    # ── Section 6: Decisions and Open Issues ─────────────────────────────

    dec_num = section_num + 1
    decisions = data_dict.get("decisions", [])
    open_issues = data_dict.get("open_issues", [])
    if decisions or open_issues:
        add_heading(doc, f"{dec_num}. Decisions and Open Issues", level=1)
        if decisions:
            add_heading(doc, "Decisions", level=2)
            for dec in decisions:
                ident = dec.get("identifier", "")
                title = dec.get("title", "")
                desc = dec.get("description", "")
                add_labeled_paragraph(doc, f"{ident}: {title}", "")
                if desc:
                    add_paragraph(doc, desc)

        if open_issues:
            add_heading(doc, "Open Issues", level=2)
            for oi in open_issues:
                ident = oi.get("identifier", "")
                title = oi.get("title", "")
                desc = oi.get("description", "")
                priority = oi.get("priority", "")
                label = f"{ident}: {title}"
                if priority:
                    label += f" [{priority.upper()}]"
                add_labeled_paragraph(doc, label, "")
                if desc:
                    add_paragraph(doc, desc)

    # ── Write ────────────────────────────────────────────────────────────

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))


# ═════════════════════════════════════════════════════════════════════════════
# Private helpers
# ═════════════════════════════════════════════════════════════════════════════


def _infer_primary_domains(persona: dict, domains: list[dict]) -> list[str]:
    """Infer primary domain names from persona description keywords."""
    desc = (persona.get("description") or "").lower()
    name = (persona.get("name") or "").lower()
    matched: list[str] = []
    for d in domains:
        d_name = d.get("name", "")
        d_code = d.get("code", "")
        d_name_lower = d_name.lower()
        if d_name_lower in desc or d_name_lower in name:
            matched.append(f"{d_name} ({d_code})")
    return matched


def _render_process_tier_summary(doc, domains: list[dict]) -> None:
    """Render the Process Tier Summary as a heading + 4-column table."""
    add_heading(doc, "Process Tier Summary", level=2)

    # Collect all processes across domains
    proc_rows: list[list[str]] = []
    for domain in domains:
        d_name = domain.get("name", "")
        d_code = domain.get("code", "")
        for proc in domain.get("processes", []):
            p_code = proc.get("code", "")
            p_name = proc.get("name", "")
            tier = (proc.get("tier") or "").capitalize()
            proc_rows.append([f"{d_name} ({d_code})", p_code, p_name, tier])

    if proc_rows:
        # 4-column widths summing to TABLE_WIDTH_DXA (9360)
        col_widths = [3000, 1200, 3160, 2000]
        table = doc.add_table(rows=1, cols=4)
        table.autofit = False
        add_header_row(table, ["Domain", "Code", "Process Name", "Tier"], col_widths)
        for idx, row_data in enumerate(proc_rows):
            add_data_row(table, row_data, col_widths, shaded=idx % 2 == 1)
    else:
        add_paragraph(doc, "No processes defined.", italic=True)
    add_paragraph(doc)


def _render_domain_processing_order(doc, domains: list[dict]) -> None:
    """Render the Domain Processing Order section."""
    add_heading(doc, "Domain Processing Order", level=2)
    add_paragraph(
        doc,
        "Domains should be processed in the following order. The principle is "
        "to begin with the domain that establishes the most foundational data, "
        "since later domains will depend on the entities it creates.",
    )

    # Sort by sort_order
    sorted_domains = sorted(domains, key=lambda d: d.get("sort_order", 99))
    for d in sorted_domains:
        identifier = d.get("identifier") or ""
        name = d.get("name", "")
        code = d.get("code", "")
        desc = d.get("description", "")
        # Truncate description for the ordered list
        short_desc = desc[:120] + "..." if len(desc) > 120 else desc
        label = f"{identifier}: {name} ({code})" if identifier else f"{name} ({code})"
        add_labeled_paragraph(doc, label, f" \u2014 {short_desc}" if short_desc else "")

    add_paragraph(doc)


def _render_domain_section(doc, domain: dict, personas: list[dict]) -> None:
    """Render a single domain with its detail table and process tables."""
    d_name = domain.get("name", "")
    d_code = domain.get("code", "")
    d_identifier = domain.get("identifier") or ""
    d_desc = domain.get("description", "")
    processes = domain.get("processes", [])

    label = f"{d_identifier}: {d_name} ({d_code})" if d_identifier else f"{d_name} ({d_code})"
    add_heading(doc, label, level=2)

    # Domain detail table
    key_data_list = _domain_key_data_categories_list(domain)
    personas_list = _domain_personas_list(domain, personas)
    rows = [
        ("Identifier", [d_identifier or "\u2014"]),
        ("Domain Code", [d_code]),
        ("Purpose", [d_desc or "\u2014"]),
        ("Personas Involved", personas_list if personas_list else ["\u2014"]),
        ("Key Data Categories", key_data_list if key_data_list else ["\u2014"]),
    ]
    add_meta_table(doc, rows, widths=META_COL_WIDTHS_MASTER_PRD)
    add_paragraph(doc)

    # Processes
    if processes:
        add_heading(doc, "Business Processes", level=3)
        for proc in processes:
            _render_process_table(doc, proc)

    # Sub-domains
    for sub in domain.get("sub_domains", []):
        _render_domain_section(doc, sub, personas)


def _domain_key_data_categories_list(domain: dict) -> list[str]:
    """Derive key data categories from domain processes as a list."""
    processes = domain.get("processes", [])
    categories: list[str] = []
    for proc in processes:
        name = proc.get("name", "")
        if name:
            categories.append(name)
    return categories


def _domain_personas_list(domain: dict, personas: list[dict]) -> list[str]:
    """Build a list of persona strings for a domain."""
    d_name = (domain.get("name") or "").lower()
    d_code = (domain.get("code") or "").lower()
    matched: list[str] = []

    for p in personas:
        p_domains = p.get("primary_domains", [])
        if p_domains:
            for pd in p_domains:
                if d_code in pd.lower() or d_name in pd.lower():
                    matched.append(f"{p['code']} ({p['name']})")
                    break
        else:
            desc = (p.get("description") or "").lower()
            name_lower = (p.get("name") or "").lower()
            if d_name in desc or d_name in name_lower:
                matched.append(f"{p['code']} ({p['name']})")

    return matched


def _render_process_table(doc, proc: dict) -> None:
    """Render a process as a heading + detail table."""
    p_code = proc.get("code", "")
    p_name = proc.get("name", "")
    p_desc = proc.get("description", "")
    tier = (proc.get("tier") or "").capitalize()
    bv = proc.get("business_value", "")
    caps = proc.get("key_capabilities", [])

    add_heading(doc, f"{p_code}: {p_name}", level=3)

    rows = [
        ("Description", [p_desc or "\u2014"]),
        ("Implementation Tier", [tier or "\u2014"]),
        ("Business Value", [bv or "\u2014"]),
        ("Key Capabilities", caps if caps else ["\u2014"]),
    ]
    add_meta_table(doc, rows, widths=META_COL_WIDTHS_MASTER_PRD)
    add_paragraph(doc)


def _render_service_section(doc, svc: dict, domains: list[dict]) -> None:
    """Render a cross-domain service with its detail table."""
    name = svc.get("name", "")
    desc = svc.get("description", "")
    capabilities = svc.get("capabilities", [])
    consuming = svc.get("consuming_domains", [])
    owned = svc.get("owned_entities", [])

    add_heading(doc, name, level=2)

    # Resolve consuming domain codes to names
    domain_name_map = {d.get("code", ""): d.get("name", "") for d in domains}
    consuming_strs: list[str] = []
    for c in consuming:
        d_name = domain_name_map.get(c, c)
        consuming_strs.append(f"{d_name} ({c})" if d_name != c else c)

    rows = [
        ("Purpose", [desc or "\u2014"]),
        ("Capabilities", capabilities if capabilities else ["\u2014"]),
        ("Consuming Domains", consuming_strs if consuming_strs else ["\u2014"]),
        ("Entities Owned", owned if owned
         else ["None \u2014 consumes data owned by other domains"]),
    ]
    add_meta_table(doc, rows, widths=META_COL_WIDTHS_MASTER_PRD)
    add_paragraph(doc)


def _render_system_scope(doc, scope: dict, section_num: int) -> None:
    """Render the System Scope section."""
    add_heading(doc, f"{section_num}. System Scope", level=1)

    # In Scope
    in_scope = scope.get("in_scope", [])
    add_heading(doc, "In Scope", level=2)
    if in_scope:
        for item in in_scope:
            add_labeled_paragraph(doc, "\u2022 ", item)
    else:
        add_paragraph(doc, "System scope not yet defined.", italic=True)

    # Out of Scope
    add_heading(doc, "Out of Scope", level=2)
    out_scope = scope.get("out_of_scope", [])
    if out_scope:
        for item in out_scope:
            add_labeled_paragraph(doc, "\u2022 ", item)
    else:
        add_paragraph(
            doc,
            "No functional areas have been explicitly designated as out of scope "
            "for this implementation.",
        )

    # Key Integrations
    integrations = scope.get("integrations", [])
    if integrations:
        add_heading(doc, "Key Integrations", level=2)
        for item in integrations:
            add_labeled_paragraph(doc, "\u2022 ", item)

    # Implementation Timeline
    add_heading(doc, "Implementation Timeline", level=2)
    timeline = scope.get("timeline", "")
    if timeline:
        add_paragraph(doc, timeline)
    else:
        add_paragraph(
            doc,
            "Implementation timeline not yet defined.",
            italic=True,
        )
