"""Context assembly for CRM Builder Automation prompts.

Implements L2 PRD Section 10.3: one assembly function per promptable work
item type. Each function queries the database for the data the PRD specifies
and returns a dict that the structure module formats into the Context section.

Three item_types do not need context assembly: stakeholder_review,
crm_configuration, verification.
"""

import sqlite3


def _fetch_all_dicts(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    """Execute a query and return results as a list of dicts."""
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]


def _fetch_one_dict(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict | None:
    """Execute a query and return a single result as a dict, or None."""
    cur = conn.execute(sql, params)
    row = cur.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row, strict=False))


def _get_entity_full_data(conn: sqlite3.Connection, entity_id: int) -> dict:
    """Load full entity data including fields, options, and relationships."""
    entity = _fetch_one_dict(
        conn,
        "SELECT id, name, code, entity_type, is_native, primary_domain_id, "
        "description, singular_label, plural_label FROM Entity WHERE id = ?",
        (entity_id,),
    )
    if entity is None:
        return {}
    fields = _fetch_all_dicts(
        conn,
        "SELECT id, name, label, field_type, is_required, default_value, "
        "read_only, audited, category, max_length, description, is_native, "
        "sort_order FROM Field WHERE entity_id = ? ORDER BY sort_order",
        (entity_id,),
    )
    for field in fields:
        field["options"] = _fetch_all_dicts(
            conn,
            "SELECT value, label, description, style, sort_order, is_default "
            "FROM FieldOption WHERE field_id = ? ORDER BY sort_order",
            (field["id"],),
        )
    relationships = _fetch_all_dicts(
        conn,
        "SELECT name, description, entity_id, entity_foreign_id, link_type, "
        "link, link_foreign, label, label_foreign, relation_name "
        "FROM Relationship WHERE entity_id = ? OR entity_foreign_id = ?",
        (entity_id, entity_id),
    )
    entity["fields"] = fields
    entity["relationships"] = relationships
    return entity


def _get_entities_for_domain(conn: sqlite3.Connection, domain_id: int) -> list[dict]:
    """Load entities whose primary_domain_id matches, plus those linked via ProcessEntity."""
    entity_ids = set()
    # Primary domain entities
    rows = conn.execute(
        "SELECT id FROM Entity WHERE primary_domain_id = ?", (domain_id,)
    ).fetchall()
    for (eid,) in rows:
        entity_ids.add(eid)
    # Entities linked through ProcessEntity for processes in this domain
    rows = conn.execute(
        "SELECT DISTINCT pe.entity_id FROM ProcessEntity pe "
        "JOIN Process p ON p.id = pe.process_id "
        "WHERE p.domain_id = ?",
        (domain_id,),
    ).fetchall()
    for (eid,) in rows:
        entity_ids.add(eid)
    return [_get_entity_full_data(conn, eid) for eid in sorted(entity_ids)]


def _get_layout_data(conn: sqlite3.Connection, entity_id: int) -> dict:
    """Load layout panels, rows, tabs, and list columns for an entity."""
    panels = _fetch_all_dicts(
        conn,
        "SELECT id, label, description, tab_break, tab_label, style, "
        "hidden, sort_order, layout_mode FROM LayoutPanel "
        "WHERE entity_id = ? ORDER BY sort_order",
        (entity_id,),
    )
    for panel in panels:
        panel["rows"] = _fetch_all_dicts(
            conn,
            "SELECT sort_order, cell_1_field_id, cell_2_field_id, is_full_width "
            "FROM LayoutRow WHERE panel_id = ? ORDER BY sort_order",
            (panel["id"],),
        )
        panel["tabs"] = _fetch_all_dicts(
            conn,
            "SELECT label, category, sort_order FROM LayoutTab "
            "WHERE panel_id = ? ORDER BY sort_order",
            (panel["id"],),
        )
    list_columns = _fetch_all_dicts(
        conn,
        "SELECT field_id, width, sort_order FROM ListColumn "
        "WHERE entity_id = ? ORDER BY sort_order",
        (entity_id,),
    )
    return {"panels": panels, "list_columns": list_columns}


def assemble_master_prd(
    conn: sqlite3.Connection,
    work_item_id: int,
    master_conn: sqlite3.Connection | None = None,
) -> dict:
    """Section 10.3.1: Master PRD context.

    Contains client name and description from the master database Client
    record. The session instructions carry the primary weight.
    """
    context: dict = {"subsections": []}
    if master_conn is not None:
        client = _fetch_one_dict(
            master_conn,
            "SELECT name, description, organization_overview FROM Client LIMIT 1",
        )
        if client:
            context["subsections"].append({
                "label": "Client Information",
                "content": client,
            })
    return context


def assemble_business_object_discovery(
    conn: sqlite3.Connection,
    work_item_id: int,
    master_conn: sqlite3.Connection | None = None,
) -> dict:
    """Section 10.3.2: Business Object Discovery context.

    Contains organization_overview, domains (hierarchical), processes grouped
    by domain, and personas.
    """
    context: dict = {"subsections": []}

    # Organization overview from master
    if master_conn is not None:
        client = _fetch_one_dict(
            master_conn,
            "SELECT organization_overview FROM Client LIMIT 1",
        )
        if client and client["organization_overview"]:
            context["subsections"].append({
                "label": "Organization Overview",
                "content": client["organization_overview"],
            })

    # Domains — hierarchical with sub-domains nested
    domains = _fetch_all_dicts(
        conn,
        "SELECT id, name, code, description, sort_order, parent_domain_id, is_service "
        "FROM Domain ORDER BY sort_order",
    )
    top_domains = [d for d in domains if not d["parent_domain_id"] and not d["is_service"]]
    service_domains = [d for d in domains if d["is_service"]]
    for d in top_domains:
        d["sub_domains"] = [s for s in domains if s["parent_domain_id"] == d["id"]]
    context["subsections"].append({
        "label": "Domains",
        "content": top_domains,
    })
    if service_domains:
        context["subsections"].append({
            "label": "Cross-Domain Services",
            "content": service_domains,
        })

    # Processes grouped by domain
    processes = _fetch_all_dicts(
        conn,
        "SELECT id, domain_id, name, code, description, sort_order "
        "FROM Process ORDER BY domain_id, sort_order",
    )
    context["subsections"].append({
        "label": "Processes",
        "content": processes,
    })

    # Personas
    personas = _fetch_all_dicts(
        conn, "SELECT name, code, description FROM Persona",
    )
    context["subsections"].append({
        "label": "Personas",
        "content": personas,
    })

    return context


def assemble_entity_prd(
    conn: sqlite3.Connection,
    work_item_id: int,
    master_conn: sqlite3.Connection | None = None,
) -> dict:
    """Section 10.3.3: Entity PRD context.

    Contains all domains, all processes, the target entity's business object,
    the full entity inventory, and completed entity data.
    """
    # Get the target entity from the work item
    wi = _fetch_one_dict(
        conn,
        "SELECT entity_id, domain_id FROM WorkItem WHERE id = ?",
        (work_item_id,),
    )
    target_entity_id = wi["entity_id"] if wi else None

    context: dict = {"subsections": []}

    # All domains
    domains = _fetch_all_dicts(
        conn, "SELECT name, code, description FROM Domain ORDER BY sort_order",
    )
    context["subsections"].append({"label": "Domains", "content": domains})

    # All processes
    processes = _fetch_all_dicts(
        conn,
        "SELECT name, code, description, domain_id FROM Process ORDER BY domain_id, sort_order",
    )
    context["subsections"].append({"label": "Processes", "content": processes})

    # Target entity's BusinessObject
    if target_entity_id:
        bos = _fetch_all_dicts(
            conn,
            "SELECT name, status, resolution, resolution_detail, description "
            "FROM BusinessObject WHERE resolved_to_entity_id = ?",
            (target_entity_id,),
        )
        if bos:
            context["subsections"].append({
                "label": "Target Entity Business Object",
                "content": bos,
            })

    # Entity Inventory (all entities)
    entities = _fetch_all_dicts(
        conn,
        "SELECT id, name, code, entity_type, is_native, primary_domain_id, description "
        "FROM Entity ORDER BY name",
    )
    context["subsections"].append({"label": "Entity Inventory", "content": entities})

    # Completed entity PRD data — entities with completed work items
    completed_entity_ids = [
        r[0] for r in conn.execute(
            "SELECT DISTINCT entity_id FROM WorkItem "
            "WHERE item_type = 'entity_prd' AND status = 'complete' AND entity_id IS NOT NULL"
        ).fetchall()
    ]
    completed_entities = []
    for eid in completed_entity_ids:
        if eid != target_entity_id:
            completed_entities.append(_get_entity_full_data(conn, eid))
    if completed_entities:
        context["subsections"].append({
            "label": "Completed Entity PRDs",
            "content": completed_entities,
        })

    # Target entity participation data
    if target_entity_id:
        target = _fetch_one_dict(
            conn,
            "SELECT name, primary_domain_id FROM Entity WHERE id = ?",
            (target_entity_id,),
        )
        if target:
            # Additional domains via ProcessEntity
            add_domains = _fetch_all_dicts(
                conn,
                "SELECT DISTINCT d.name, d.code FROM Domain d "
                "JOIN Process p ON p.domain_id = d.id "
                "JOIN ProcessEntity pe ON pe.process_id = p.id "
                "WHERE pe.entity_id = ? AND d.id != ?",
                (target_entity_id, target.get("primary_domain_id") or -1),
            )
            context["subsections"].append({
                "label": "Target Entity Participation",
                "content": {
                    "entity_name": target["name"],
                    "primary_domain_id": target["primary_domain_id"],
                    "additional_domains": add_domains,
                },
            })

    return context


def assemble_domain_overview(
    conn: sqlite3.Connection,
    work_item_id: int,
    master_conn: sqlite3.Connection | None = None,
) -> dict:
    """Section 10.3.4: Domain Overview context."""
    wi = _fetch_one_dict(
        conn, "SELECT domain_id FROM WorkItem WHERE id = ?", (work_item_id,),
    )
    domain_id = wi["domain_id"] if wi else None

    context: dict = {"subsections": []}

    # Organization overview
    if master_conn is not None:
        client = _fetch_one_dict(
            master_conn, "SELECT organization_overview FROM Client LIMIT 1",
        )
        if client and client["organization_overview"]:
            context["subsections"].append({
                "label": "Organization Overview",
                "content": client["organization_overview"],
            })

    if domain_id is None:
        return context

    # Target domain
    domain = _fetch_one_dict(
        conn,
        "SELECT id, name, code, description, parent_domain_id, is_service "
        "FROM Domain WHERE id = ?",
        (domain_id,),
    )
    if domain:
        context["subsections"].append({"label": "Target Domain", "content": domain})

    # Parent domain if sub-domain
    if domain and domain["parent_domain_id"]:
        parent = _fetch_one_dict(
            conn,
            "SELECT name, code, description, domain_overview_text "
            "FROM Domain WHERE id = ?",
            (domain["parent_domain_id"],),
        )
        if parent:
            context["subsections"].append({"label": "Parent Domain", "content": parent})

    # Sub-domains if parent domain
    sub_domains = _fetch_all_dicts(
        conn,
        "SELECT id, name, code, description FROM Domain WHERE parent_domain_id = ?",
        (domain_id,),
    )
    if sub_domains:
        for sd in sub_domains:
            sd["processes"] = _fetch_all_dicts(
                conn,
                "SELECT name, code, description, sort_order FROM Process "
                "WHERE domain_id = ? ORDER BY sort_order",
                (sd["id"],),
            )
        context["subsections"].append({"label": "Sub-Domains", "content": sub_domains})

    # Processes for this domain
    processes = _fetch_all_dicts(
        conn,
        "SELECT name, code, description, sort_order FROM Process "
        "WHERE domain_id = ? ORDER BY sort_order",
        (domain_id,),
    )
    context["subsections"].append({"label": "Domain Processes", "content": processes})

    # Personas (all — domain-scoped filtering would need ProcessPersona)
    personas = _fetch_all_dicts(
        conn, "SELECT name, code, description FROM Persona",
    )
    context["subsections"].append({"label": "Personas", "content": personas})

    # Entities relevant to this domain
    entities = _get_entities_for_domain(conn, domain_id)
    context["subsections"].append({"label": "Domain Entities", "content": entities})

    # Cross-Domain Services
    services = _fetch_all_dicts(
        conn,
        "SELECT name, code, description FROM Domain WHERE is_service = 1",
    )
    if services:
        context["subsections"].append({
            "label": "Cross-Domain Services",
            "content": services,
        })

    return context


def assemble_process_definition(
    conn: sqlite3.Connection,
    work_item_id: int,
    master_conn: sqlite3.Connection | None = None,
) -> dict:
    """Section 10.3.5: Process Definition context."""
    wi = _fetch_one_dict(
        conn,
        "SELECT domain_id, process_id FROM WorkItem WHERE id = ?",
        (work_item_id,),
    )
    domain_id = wi["domain_id"] if wi else None

    context: dict = {"subsections": []}

    if domain_id is None:
        return context

    # Domain overview text
    domain = _fetch_one_dict(
        conn,
        "SELECT name, code, domain_overview_text, parent_domain_id FROM Domain WHERE id = ?",
        (domain_id,),
    )
    if domain and domain["domain_overview_text"]:
        context["subsections"].append({
            "label": "Domain Overview",
            "content": domain["domain_overview_text"],
        })

    # Parent domain context for sub-domains
    if domain and domain["parent_domain_id"]:
        parent = _fetch_one_dict(
            conn,
            "SELECT name, domain_overview_text FROM Domain WHERE id = ?",
            (domain["parent_domain_id"],),
        )
        if parent and parent["domain_overview_text"]:
            context["subsections"].append({
                "label": "Parent Domain Context",
                "content": parent["domain_overview_text"],
            })

    # Personas
    personas = _fetch_all_dicts(
        conn, "SELECT name, code, description FROM Persona",
    )
    context["subsections"].append({"label": "Personas", "content": personas})

    # Entities relevant to this domain
    entities = _get_entities_for_domain(conn, domain_id)
    context["subsections"].append({"label": "Domain Entities", "content": entities})

    # Previously completed processes in this domain
    completed_procs = _fetch_all_dicts(
        conn,
        "SELECT p.id, p.name, p.code, p.description, p.sort_order "
        "FROM Process p "
        "JOIN WorkItem wi ON wi.process_id = p.id AND wi.item_type = 'process_definition' "
        "WHERE p.domain_id = ? AND wi.status = 'complete' "
        "ORDER BY p.sort_order",
        (domain_id,),
    )
    for proc in completed_procs:
        proc["steps"] = _fetch_all_dicts(
            conn,
            "SELECT name, description, step_type, sort_order "
            "FROM ProcessStep WHERE process_id = ? ORDER BY sort_order",
            (proc["id"],),
        )
        proc["requirements"] = _fetch_all_dicts(
            conn,
            "SELECT identifier, description, priority, status "
            "FROM Requirement WHERE process_id = ?",
            (proc["id"],),
        )
        proc["entity_refs"] = _fetch_all_dicts(
            conn,
            "SELECT entity_id, role, description FROM ProcessEntity "
            "WHERE process_id = ?",
            (proc["id"],),
        )
        proc["field_refs"] = _fetch_all_dicts(
            conn,
            "SELECT field_id, usage, description FROM ProcessField "
            "WHERE process_id = ?",
            (proc["id"],),
        )
        proc["persona_refs"] = _fetch_all_dicts(
            conn,
            "SELECT persona_id, role, description FROM ProcessPersona "
            "WHERE process_id = ?",
            (proc["id"],),
        )
    if completed_procs:
        context["subsections"].append({
            "label": "Completed Processes",
            "content": completed_procs,
        })

    return context


def assemble_domain_reconciliation(
    conn: sqlite3.Connection,
    work_item_id: int,
    master_conn: sqlite3.Connection | None = None,
) -> dict:
    """Section 10.3.6: Domain Reconciliation context."""
    wi = _fetch_one_dict(
        conn, "SELECT domain_id FROM WorkItem WHERE id = ?", (work_item_id,),
    )
    domain_id = wi["domain_id"] if wi else None

    context: dict = {"subsections": []}
    if domain_id is None:
        return context

    # Domain overview text
    domain = _fetch_one_dict(
        conn,
        "SELECT name, code, domain_overview_text, parent_domain_id "
        "FROM Domain WHERE id = ?",
        (domain_id,),
    )
    if domain and domain["domain_overview_text"]:
        context["subsections"].append({
            "label": "Domain Overview",
            "content": domain["domain_overview_text"],
        })

    # For parent domain: include sub-domain reconciliation texts
    sub_domains = _fetch_all_dicts(
        conn,
        "SELECT name, code, domain_overview_text, domain_reconciliation_text "
        "FROM Domain WHERE parent_domain_id = ?",
        (domain_id,),
    )
    if sub_domains:
        context["subsections"].append({
            "label": "Sub-Domain Reconciliation Data",
            "content": sub_domains,
        })

    # All processes in this domain with full data
    processes = _fetch_all_dicts(
        conn,
        "SELECT id, name, code, description, sort_order "
        "FROM Process WHERE domain_id = ? ORDER BY sort_order",
        (domain_id,),
    )
    for proc in processes:
        proc["steps"] = _fetch_all_dicts(
            conn,
            "SELECT name, description, step_type, sort_order "
            "FROM ProcessStep WHERE process_id = ? ORDER BY sort_order",
            (proc["id"],),
        )
        proc["requirements"] = _fetch_all_dicts(
            conn,
            "SELECT identifier, description, priority, status "
            "FROM Requirement WHERE process_id = ?",
            (proc["id"],),
        )
        proc["entity_refs"] = _fetch_all_dicts(
            conn,
            "SELECT entity_id, role, description FROM ProcessEntity WHERE process_id = ?",
            (proc["id"],),
        )
        proc["field_refs"] = _fetch_all_dicts(
            conn,
            "SELECT field_id, usage, description FROM ProcessField WHERE process_id = ?",
            (proc["id"],),
        )
        proc["persona_refs"] = _fetch_all_dicts(
            conn,
            "SELECT persona_id, role, description FROM ProcessPersona WHERE process_id = ?",
            (proc["id"],),
        )
    context["subsections"].append({"label": "Domain Processes", "content": processes})

    # Entities
    entities = _get_entities_for_domain(conn, domain_id)
    context["subsections"].append({"label": "Domain Entities", "content": entities})

    return context


def assemble_yaml_generation(
    conn: sqlite3.Connection,
    work_item_id: int,
    master_conn: sqlite3.Connection | None = None,
) -> dict:
    """Section 10.3.7: YAML Generation context."""
    wi = _fetch_one_dict(
        conn, "SELECT domain_id FROM WorkItem WHERE id = ?", (work_item_id,),
    )
    domain_id = wi["domain_id"] if wi else None

    context: dict = {"subsections": []}
    if domain_id is None:
        return context

    # Domain reconciliation text
    domain = _fetch_one_dict(
        conn,
        "SELECT name, code, domain_reconciliation_text FROM Domain WHERE id = ?",
        (domain_id,),
    )
    if domain and domain["domain_reconciliation_text"]:
        context["subsections"].append({
            "label": "Domain Reconciliation",
            "content": domain["domain_reconciliation_text"],
        })

    # Entities with full data + layout
    entity_ids = set()
    rows = conn.execute(
        "SELECT id FROM Entity WHERE primary_domain_id = ?", (domain_id,)
    ).fetchall()
    for (eid,) in rows:
        entity_ids.add(eid)
    rows = conn.execute(
        "SELECT DISTINCT pe.entity_id FROM ProcessEntity pe "
        "JOIN Process p ON p.id = pe.process_id WHERE p.domain_id = ?",
        (domain_id,),
    ).fetchall()
    for (eid,) in rows:
        entity_ids.add(eid)

    entities_with_layout = []
    for eid in sorted(entity_ids):
        edata = _get_entity_full_data(conn, eid)
        edata["layout"] = _get_layout_data(conn, eid)
        entities_with_layout.append(edata)
    context["subsections"].append({
        "label": "Domain Entities with Layout",
        "content": entities_with_layout,
    })

    # Requirements for this domain's processes
    requirements = _fetch_all_dicts(
        conn,
        "SELECT r.identifier, r.description, r.priority, r.status, p.name AS process_name "
        "FROM Requirement r JOIN Process p ON p.id = r.process_id "
        "WHERE p.domain_id = ?",
        (domain_id,),
    )
    context["subsections"].append({"label": "Requirements", "content": requirements})

    # Previously completed domains' entity/field/relationship data
    completed_domain_ids = [
        r[0] for r in conn.execute(
            "SELECT DISTINCT domain_id FROM WorkItem "
            "WHERE item_type = 'yaml_generation' AND status = 'complete' "
            "AND domain_id IS NOT NULL AND domain_id != ?",
            (domain_id,),
        ).fetchall()
    ]
    if completed_domain_ids:
        prior_domains_data = []
        for did in completed_domain_ids:
            d = _fetch_one_dict(
                conn, "SELECT name, code FROM Domain WHERE id = ?", (did,),
            )
            if d:
                d["entities"] = _get_entities_for_domain(conn, did)
                prior_domains_data.append(d)
        if prior_domains_data:
            context["subsections"].append({
                "label": "Prior Domain Data",
                "content": prior_domains_data,
            })

    return context


def assemble_crm_selection(
    conn: sqlite3.Connection,
    work_item_id: int,
    master_conn: sqlite3.Connection | None = None,
) -> dict:
    """Section 10.3.8: CRM Selection context — broadest scope."""
    context: dict = {"subsections": []}

    # Organization overview
    if master_conn is not None:
        client = _fetch_one_dict(
            master_conn, "SELECT organization_overview FROM Client LIMIT 1",
        )
        if client and client["organization_overview"]:
            context["subsections"].append({
                "label": "Organization Overview",
                "content": client["organization_overview"],
            })

    # All domains with reconciliation text
    domains = _fetch_all_dicts(
        conn,
        "SELECT name, code, description, domain_reconciliation_text "
        "FROM Domain ORDER BY sort_order",
    )
    context["subsections"].append({"label": "Domains", "content": domains})

    # All entities with full data
    all_entities = _fetch_all_dicts(
        conn, "SELECT id FROM Entity ORDER BY name",
    )
    entities_full = [_get_entity_full_data(conn, e["id"]) for e in all_entities]
    context["subsections"].append({"label": "All Entities", "content": entities_full})

    # All requirements
    requirements = _fetch_all_dicts(
        conn,
        "SELECT r.identifier, r.description, r.priority, r.status, p.name AS process_name "
        "FROM Requirement r JOIN Process p ON p.id = r.process_id",
    )
    context["subsections"].append({"label": "All Requirements", "content": requirements})

    # All layout data
    layout_entities = _fetch_all_dicts(
        conn, "SELECT DISTINCT entity_id FROM LayoutPanel",
    )
    all_layouts = []
    for le in layout_entities:
        ld = _get_layout_data(conn, le["entity_id"])
        ld["entity_id"] = le["entity_id"]
        all_layouts.append(ld)
    if all_layouts:
        context["subsections"].append({"label": "Layout Data", "content": all_layouts})

    return context


def assemble_crm_deployment(
    conn: sqlite3.Connection,
    work_item_id: int,
    master_conn: sqlite3.Connection | None = None,
) -> dict:
    """Section 10.3.9: CRM Deployment context."""
    context: dict = {"subsections": []}

    # Organization overview and CRM platform
    if master_conn is not None:
        client = _fetch_one_dict(
            master_conn,
            "SELECT organization_overview, crm_platform FROM Client LIMIT 1",
        )
        if client:
            if client["organization_overview"]:
                context["subsections"].append({
                    "label": "Organization Overview",
                    "content": client["organization_overview"],
                })
            if client["crm_platform"]:
                context["subsections"].append({
                    "label": "CRM Platform",
                    "content": client["crm_platform"],
                })

    # Scale summary
    entity_count = conn.execute("SELECT COUNT(*) FROM Entity").fetchone()[0]
    custom_count = conn.execute(
        "SELECT COUNT(*) FROM Entity WHERE is_native = 0"
    ).fetchone()[0]
    field_count = conn.execute("SELECT COUNT(*) FROM Field").fetchone()[0]
    rel_count = conn.execute("SELECT COUNT(*) FROM Relationship").fetchone()[0]
    context["subsections"].append({
        "label": "Scale Summary",
        "content": {
            "entity_count": entity_count,
            "custom_entity_count": custom_count,
            "field_count": field_count,
            "relationship_count": rel_count,
        },
    })

    # CRM selection session results (structured_output from crm_selection)
    crm_sel_output = _fetch_one_dict(
        conn,
        "SELECT a.structured_output FROM AISession a "
        "JOIN WorkItem wi ON wi.id = a.work_item_id "
        "WHERE wi.item_type = 'crm_selection' AND a.structured_output IS NOT NULL "
        "ORDER BY a.id DESC LIMIT 1",
    )
    if crm_sel_output and crm_sel_output["structured_output"]:
        context["subsections"].append({
            "label": "CRM Selection Results",
            "content": crm_sel_output["structured_output"],
        })

    return context


# Dispatcher mapping item_type → assembly function.
CONTEXT_ASSEMBLERS = {
    "master_prd": assemble_master_prd,
    "business_object_discovery": assemble_business_object_discovery,
    "entity_prd": assemble_entity_prd,
    "domain_overview": assemble_domain_overview,
    "process_definition": assemble_process_definition,
    "domain_reconciliation": assemble_domain_reconciliation,
    "yaml_generation": assemble_yaml_generation,
    "crm_selection": assemble_crm_selection,
    "crm_deployment": assemble_crm_deployment,
}


def assemble_context(
    conn: sqlite3.Connection,
    work_item_id: int,
    item_type: str,
    master_conn: sqlite3.Connection | None = None,
) -> dict:
    """Dispatch to the appropriate context assembly function.

    :param conn: Open client database connection.
    :param work_item_id: The WorkItem.id.
    :param item_type: The work item's item_type.
    :param master_conn: Optional master database connection.
    :returns: A context dict with a "subsections" list.
    :raises ValueError: If item_type is not promptable.
    """
    if item_type not in CONTEXT_ASSEMBLERS:
        raise ValueError(f"Item type '{item_type}' does not produce prompts")
    return CONTEXT_ASSEMBLERS[item_type](conn, work_item_id, master_conn)
