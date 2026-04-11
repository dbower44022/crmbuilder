"""Dependency graph construction for CRM Builder Automation.

Implements L2 PRD Section 9.4: builds the WorkItem and Dependency graph
progressively as the project advances through four scenarios:

- 9.4.1 Project Creation — master_prd with no dependencies
- 9.4.2 After Master PRD Import — business_object_discovery
- 9.4.3 After Business Object Discovery Import — all remaining phases
- 9.4.4 Mid-Project Additions — new entities, processes, domains
"""

import sqlite3

from automation.db.connection import transaction
from automation.workflow.status import calculate_status


def _insert_work_item(
    conn: sqlite3.Connection,
    item_type: str,
    status: str = "not_started",
    *,
    domain_id: int | None = None,
    entity_id: int | None = None,
    process_id: int | None = None,
) -> int:
    """Insert a WorkItem and return its id."""
    cur = conn.execute(
        "INSERT INTO WorkItem (item_type, status, domain_id, entity_id, process_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (item_type, status, domain_id, entity_id, process_id),
    )
    return cur.lastrowid


def _insert_dependency(
    conn: sqlite3.Connection,
    work_item_id: int,
    depends_on_id: int,
) -> None:
    """Insert a Dependency row."""
    conn.execute(
        "INSERT INTO Dependency (work_item_id, depends_on_id) VALUES (?, ?)",
        (work_item_id, depends_on_id),
    )


def _find_work_item(
    conn: sqlite3.Connection,
    item_type: str,
    *,
    domain_id: int | None = None,
    entity_id: int | None = None,
    process_id: int | None = None,
) -> int | None:
    """Find a work item by type and optional FK. Returns id or None."""
    sql = "SELECT id FROM WorkItem WHERE item_type = ?"
    params: list = [item_type]
    if domain_id is not None:
        sql += " AND domain_id = ?"
        params.append(domain_id)
    else:
        sql += " AND domain_id IS NULL"
    if entity_id is not None:
        sql += " AND entity_id = ?"
        params.append(entity_id)
    else:
        sql += " AND entity_id IS NULL"
    if process_id is not None:
        sql += " AND process_id = ?"
        params.append(process_id)
    else:
        sql += " AND process_id IS NULL"
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def _recalculate_all(conn: sqlite3.Connection) -> None:
    """Recalculate status for all not_started work items."""
    rows = conn.execute(
        "SELECT id FROM WorkItem WHERE status = 'not_started'"
    ).fetchall()
    for (wid,) in rows:
        new_status = calculate_status(conn, wid)
        if new_status == "ready":
            conn.execute(
                "UPDATE WorkItem SET status = 'ready', updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (wid,),
            )


def create_project(conn: sqlite3.Connection) -> int:
    """Create the initial project graph — a single master_prd work item.

    Section 9.4.1: The master_prd has zero dependencies and is immediately
    ready for work.

    :param conn: An open sqlite3.Connection.
    :returns: The master_prd work item id.
    """
    with transaction(conn):
        wid = _insert_work_item(conn, "master_prd", status="ready")
    return wid


def after_master_prd_import(conn: sqlite3.Connection) -> None:
    """Expand the graph after Master PRD import.

    Section 9.4.2: Creates business_object_discovery depending on master_prd.
    Recalculates — if master_prd is complete, business_object_discovery
    transitions to ready.

    :param conn: An open sqlite3.Connection.
    """
    master_prd_id = _find_work_item(conn, "master_prd")
    if master_prd_id is None:
        raise ValueError("master_prd work item not found")

    with transaction(conn):
        bod_id = _insert_work_item(conn, "business_object_discovery")
        _insert_dependency(conn, bod_id, master_prd_id)
        # Recalculate — if master_prd is complete, bod becomes ready
        new_status = calculate_status(conn, bod_id)
        if new_status == "ready":
            conn.execute(
                "UPDATE WorkItem SET status = 'ready', updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (bod_id,),
            )


def after_business_object_discovery_import(conn: sqlite3.Connection) -> None:
    """Expand the graph after Business Object Discovery import.

    Section 9.4.3: Creates work items for all remaining phases based on the
    Domain, Entity, and Process records now in the database. Wires all
    dependencies per the spec.

    :param conn: An open sqlite3.Connection.
    """
    bod_id = _find_work_item(conn, "business_object_discovery")
    if bod_id is None:
        raise ValueError("business_object_discovery work item not found")

    with transaction(conn):
        # Load entities, domains, processes
        entities = conn.execute(
            "SELECT id, primary_domain_id FROM Entity"
        ).fetchall()
        domains = conn.execute(
            "SELECT id FROM Domain"
        ).fetchall()
        processes = conn.execute(
            "SELECT id, domain_id, sort_order FROM Process ORDER BY domain_id, sort_order"
        ).fetchall()

        # -- Entity PRDs (Phase 2) --
        # One per entity, depends on business_object_discovery
        entity_prd_ids: dict[int, int] = {}  # entity_id -> work_item_id
        for entity_id, primary_domain_id in entities:
            wid = _insert_work_item(
                conn, "entity_prd",
                domain_id=primary_domain_id,
                entity_id=entity_id,
            )
            _insert_dependency(conn, wid, bod_id)
            entity_prd_ids[entity_id] = wid

        # -- Domain Overview (Phase 3) --
        # One per domain, depends on: (1) bod, and (2) entity_prd for every
        # entity whose primary_domain_id matches this domain
        domain_overview_ids: dict[int, int] = {}  # domain_id -> work_item_id
        for (domain_id,) in domains:
            wid = _insert_work_item(
                conn, "domain_overview", domain_id=domain_id,
            )
            _insert_dependency(conn, wid, bod_id)
            # Add dependencies on entity PRDs for entities in this domain
            for entity_id, primary_domain_id in entities:
                if primary_domain_id == domain_id:
                    _insert_dependency(conn, wid, entity_prd_ids[entity_id])
            domain_overview_ids[domain_id] = wid

        # -- Process Definitions (Phase 5) --
        # One per process, depends on: (1) domain_overview for its domain,
        # (2) prior process_definition in the same domain by sort_order
        process_def_ids: dict[int, int] = {}  # process_id -> work_item_id
        prev_process_in_domain: dict[int, int] = {}  # domain_id -> last process work_item_id
        for process_id, domain_id, _sort_order in processes:
            wid = _insert_work_item(
                conn, "process_definition",
                domain_id=domain_id,
                process_id=process_id,
            )
            _insert_dependency(conn, wid, domain_overview_ids[domain_id])
            # Chain to prior process in same domain
            if domain_id in prev_process_in_domain:
                _insert_dependency(conn, wid, prev_process_in_domain[domain_id])
            prev_process_in_domain[domain_id] = wid
            process_def_ids[process_id] = wid

        # -- Domain Reconciliation (Phase 6) --
        # One per domain, depends on all process_definitions in that domain
        domain_recon_ids: dict[int, int] = {}  # domain_id -> work_item_id
        for (domain_id,) in domains:
            wid = _insert_work_item(
                conn, "domain_reconciliation", domain_id=domain_id,
            )
            for process_id, proc_domain_id, _ in processes:
                if proc_domain_id == domain_id:
                    _insert_dependency(conn, wid, process_def_ids[process_id])
            domain_recon_ids[domain_id] = wid

        # -- Stakeholder Review (Phase 7) --
        # One per domain, depends on domain_reconciliation
        stakeholder_ids: dict[int, int] = {}  # domain_id -> work_item_id
        for (domain_id,) in domains:
            wid = _insert_work_item(
                conn, "stakeholder_review", domain_id=domain_id,
            )
            _insert_dependency(conn, wid, domain_recon_ids[domain_id])
            stakeholder_ids[domain_id] = wid

        # -- YAML Generation (Phase 8) --
        # One per domain, depends on stakeholder_review
        yaml_gen_ids: dict[int, int] = {}  # domain_id -> work_item_id
        for (domain_id,) in domains:
            wid = _insert_work_item(
                conn, "yaml_generation", domain_id=domain_id,
            )
            _insert_dependency(conn, wid, stakeholder_ids[domain_id])
            yaml_gen_ids[domain_id] = wid

        # -- CRM Selection (Phase 9) --
        # Singleton, depends on all yaml_generation items
        crm_selection_id = _insert_work_item(conn, "crm_selection")
        for yg_id in yaml_gen_ids.values():
            _insert_dependency(conn, crm_selection_id, yg_id)

        # -- CRM Deployment (Phase 10) --
        crm_deployment_id = _insert_work_item(conn, "crm_deployment")
        _insert_dependency(conn, crm_deployment_id, crm_selection_id)

        # -- CRM Configuration (Phase 11) --
        crm_config_id = _insert_work_item(conn, "crm_configuration")
        _insert_dependency(conn, crm_config_id, crm_deployment_id)

        # -- Verification (Phase 12) --
        verification_id = _insert_work_item(conn, "verification")
        _insert_dependency(conn, verification_id, crm_config_id)

        # Full recalculation pass
        _recalculate_all(conn)


def add_entity(conn: sqlite3.Connection, entity_id: int) -> int:
    """Add a new entity mid-project (Section 9.4.4).

    Creates an entity_prd work item depending on business_object_discovery.
    Since business_object_discovery is already complete at this point, the
    new work item is set to ready.

    The implementor is responsible for adding this entity_prd as a
    dependency to relevant domain_overview work items.

    :param conn: An open sqlite3.Connection.
    :param entity_id: The Entity.id for the new entity.
    :returns: The new entity_prd work item id.
    """
    bod_id = _find_work_item(conn, "business_object_discovery")
    if bod_id is None:
        raise ValueError("business_object_discovery work item not found")

    # Get entity's primary_domain_id
    row = conn.execute(
        "SELECT primary_domain_id FROM Entity WHERE id = ?", (entity_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Entity {entity_id} not found")
    primary_domain_id = row[0]

    with transaction(conn):
        wid = _insert_work_item(
            conn, "entity_prd",
            domain_id=primary_domain_id,
            entity_id=entity_id,
        )
        _insert_dependency(conn, wid, bod_id)
        # BOD is complete, so this should be ready
        new_status = calculate_status(conn, wid)
        if new_status == "ready":
            conn.execute(
                "UPDATE WorkItem SET status = 'ready', updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (wid,),
            )
    return wid


def add_process(conn: sqlite3.Connection, process_id: int) -> int:
    """Add a new process mid-project (Section 9.4.4).

    Creates a process_definition work item depending on that domain's
    domain_overview. Inserts into the domain's sort_order sequence by
    adding the prior process_definition as a dependency if one exists.

    The domain_reconciliation work item for that domain automatically
    gets a new dependency on this process_definition.

    :param conn: An open sqlite3.Connection.
    :param process_id: The Process.id for the new process.
    :returns: The new process_definition work item id.
    """
    # Get process domain and sort_order
    row = conn.execute(
        "SELECT domain_id, sort_order FROM Process WHERE id = ?", (process_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Process {process_id} not found")
    domain_id, sort_order = row

    # Find domain_overview for this domain
    do_id = _find_work_item(conn, "domain_overview", domain_id=domain_id)
    if do_id is None:
        raise ValueError(
            f"domain_overview work item not found for domain {domain_id}"
        )

    with transaction(conn):
        wid = _insert_work_item(
            conn, "process_definition",
            domain_id=domain_id,
            process_id=process_id,
        )
        _insert_dependency(conn, wid, do_id)

        # Find the prior process_definition in this domain by sort_order
        # (the one with the highest sort_order that is less than ours)
        prior_row = conn.execute(
            """
            SELECT wi.id FROM WorkItem wi
            JOIN Process p ON p.id = wi.process_id
            WHERE wi.item_type = 'process_definition'
              AND wi.domain_id = ?
              AND wi.id != ?
              AND p.sort_order < ?
            ORDER BY p.sort_order DESC
            LIMIT 1
            """,
            (domain_id, wid, sort_order),
        ).fetchone()
        if prior_row is not None:
            _insert_dependency(conn, wid, prior_row[0])

        # Add this as a dependency of domain_reconciliation for this domain
        recon_id = _find_work_item(
            conn, "domain_reconciliation", domain_id=domain_id,
        )
        if recon_id is not None:
            _insert_dependency(conn, recon_id, wid)

        # Recalculate the new item's status
        new_status = calculate_status(conn, wid)
        if new_status == "ready":
            conn.execute(
                "UPDATE WorkItem SET status = 'ready', updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (wid,),
            )

    return wid


def add_domain(conn: sqlite3.Connection, domain_id: int) -> list[int]:
    """Add a new domain mid-project (Section 9.4.4).

    Creates domain_overview, domain_reconciliation, stakeholder_review,
    and yaml_generation work items for the new domain. Wires dependencies.
    Also adds the yaml_generation as a dependency of crm_selection.

    :param conn: An open sqlite3.Connection.
    :param domain_id: The Domain.id for the new domain.
    :returns: List of created work item ids.
    """
    bod_id = _find_work_item(conn, "business_object_discovery")
    if bod_id is None:
        raise ValueError("business_object_discovery work item not found")

    with transaction(conn):
        created_ids = []

        # Domain Overview
        do_id = _insert_work_item(
            conn, "domain_overview", domain_id=domain_id,
        )
        _insert_dependency(conn, do_id, bod_id)
        # Add entity_prd dependencies for entities in this domain
        entity_rows = conn.execute(
            "SELECT id FROM Entity WHERE primary_domain_id = ?", (domain_id,)
        ).fetchall()
        for (entity_id,) in entity_rows:
            entity_prd_id = _find_work_item(
                conn, "entity_prd", entity_id=entity_id, domain_id=domain_id,
            )
            if entity_prd_id is not None:
                _insert_dependency(conn, do_id, entity_prd_id)
        created_ids.append(do_id)

        # Process Definitions for any processes already in this domain
        processes = conn.execute(
            "SELECT id, sort_order FROM Process WHERE domain_id = ? ORDER BY sort_order",
            (domain_id,),
        ).fetchall()
        prev_pd_id = None
        pd_ids = []
        for proc_id, _ in processes:
            pd_id = _insert_work_item(
                conn, "process_definition",
                domain_id=domain_id,
                process_id=proc_id,
            )
            _insert_dependency(conn, pd_id, do_id)
            if prev_pd_id is not None:
                _insert_dependency(conn, pd_id, prev_pd_id)
            prev_pd_id = pd_id
            pd_ids.append(pd_id)
            created_ids.append(pd_id)

        # Domain Reconciliation
        recon_id = _insert_work_item(
            conn, "domain_reconciliation", domain_id=domain_id,
        )
        for pd_id in pd_ids:
            _insert_dependency(conn, recon_id, pd_id)
        created_ids.append(recon_id)

        # Stakeholder Review
        sr_id = _insert_work_item(
            conn, "stakeholder_review", domain_id=domain_id,
        )
        _insert_dependency(conn, sr_id, recon_id)
        created_ids.append(sr_id)

        # YAML Generation
        yg_id = _insert_work_item(
            conn, "yaml_generation", domain_id=domain_id,
        )
        _insert_dependency(conn, yg_id, sr_id)
        created_ids.append(yg_id)

        # Add yaml_generation as dependency of crm_selection
        crm_sel_id = _find_work_item(conn, "crm_selection")
        if crm_sel_id is not None:
            _insert_dependency(conn, crm_sel_id, yg_id)

        # Recalculate all
        _recalculate_all(conn)

    return created_ids
