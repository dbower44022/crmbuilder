"""Decision and OpenIssue inclusion rules for CRM Builder Automation prompts.

Implements L2 PRD Section 10.4: per-type inclusion rules determining which
Decision and OpenIssue records appear in a generated prompt.

Inclusion is based on scoping foreign keys on Decision/OpenIssue:
domain_id, entity_id, process_id, field_id, requirement_id, business_object_id.

Global records (all scoping FKs NULL) are included in all prompts except
master_prd.
"""

import sqlite3

_SCOPE_COLS = (
    "domain_id", "entity_id", "process_id",
    "field_id", "requirement_id", "business_object_id",
)

_GLOBAL_FILTER = " AND ".join(f"{c} IS NULL" for c in _SCOPE_COLS)


def _fetch_records(conn: sqlite3.Connection, table: str, where: str,
                   params: tuple = ()) -> list[dict]:
    """Fetch records from Decision or OpenIssue with the given WHERE clause."""
    status_filter = ""
    if table == "Decision":
        status_filter = " AND status = 'locked'"
    elif table == "OpenIssue":
        status_filter = " AND status = 'open'"

    sql = f"SELECT * FROM {table} WHERE ({where}){status_filter}"
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]


def _get_global(conn: sqlite3.Connection, table: str) -> list[dict]:
    """Get global records (all scope FKs are NULL)."""
    return _fetch_records(conn, table, _GLOBAL_FILTER)


def _get_domain_scoped(conn: sqlite3.Connection, table: str,
                       domain_id: int) -> list[dict]:
    """Get records scoped to a specific domain."""
    return _fetch_records(conn, table, "domain_id = ?", (domain_id,))


def _get_entity_scoped(conn: sqlite3.Connection, table: str,
                       entity_id: int) -> list[dict]:
    """Get records scoped to a specific entity."""
    return _fetch_records(conn, table, "entity_id = ?", (entity_id,))


def _get_process_scoped(conn: sqlite3.Connection, table: str,
                        process_id: int) -> list[dict]:
    """Get records scoped to a specific process."""
    return _fetch_records(conn, table, "process_id = ?", (process_id,))


def _dedupe(records: list[dict]) -> list[dict]:
    """Remove duplicate records by id."""
    seen = set()
    result = []
    for r in records:
        if r["id"] not in seen:
            seen.add(r["id"])
            result.append(r)
    return result


def _include_master_prd(conn: sqlite3.Connection, _wi: dict,
                        table: str) -> list[dict]:
    """master_prd: no decisions or issues exist at project start."""
    return []


def _include_bod(conn: sqlite3.Connection, _wi: dict,
                 table: str) -> list[dict]:
    """business_object_discovery: global only."""
    return _get_global(conn, table)


def _include_entity_prd(conn: sqlite3.Connection, wi: dict,
                        table: str) -> list[dict]:
    """entity_prd: global + entity-scoped + entity's primary domain-scoped."""
    records = _get_global(conn, table)
    if wi.get("entity_id"):
        records += _get_entity_scoped(conn, table, wi["entity_id"])
        # Entity's primary domain
        row = conn.execute(
            "SELECT primary_domain_id FROM Entity WHERE id = ?",
            (wi["entity_id"],),
        ).fetchone()
        if row and row[0]:
            records += _get_domain_scoped(conn, table, row[0])
    return _dedupe(records)


def _include_domain_overview(conn: sqlite3.Connection, wi: dict,
                             table: str) -> list[dict]:
    """domain_overview: global + domain-scoped."""
    records = _get_global(conn, table)
    if wi.get("domain_id"):
        records += _get_domain_scoped(conn, table, wi["domain_id"])
    return _dedupe(records)


def _include_process_definition(conn: sqlite3.Connection, wi: dict,
                                table: str) -> list[dict]:
    """process_definition: global + domain + process + entities in process."""
    records = _get_global(conn, table)
    if wi.get("domain_id"):
        records += _get_domain_scoped(conn, table, wi["domain_id"])
    if wi.get("process_id"):
        records += _get_process_scoped(conn, table, wi["process_id"])
        # Entities involved in this process
        entity_rows = conn.execute(
            "SELECT DISTINCT entity_id FROM ProcessEntity WHERE process_id = ?",
            (wi["process_id"],),
        ).fetchall()
        for (eid,) in entity_rows:
            records += _get_entity_scoped(conn, table, eid)
    return _dedupe(records)


def _include_domain_reconciliation(conn: sqlite3.Connection, wi: dict,
                                   table: str) -> list[dict]:
    """domain_reconciliation: global + all domain/process/entity-scoped within domain."""
    records = _get_global(conn, table)
    if wi.get("domain_id"):
        records += _get_domain_scoped(conn, table, wi["domain_id"])
        # All processes in this domain
        proc_rows = conn.execute(
            "SELECT id FROM Process WHERE domain_id = ?",
            (wi["domain_id"],),
        ).fetchall()
        for (pid,) in proc_rows:
            records += _get_process_scoped(conn, table, pid)
        # All entities in this domain
        entity_rows = conn.execute(
            "SELECT id FROM Entity WHERE primary_domain_id = ?",
            (wi["domain_id"],),
        ).fetchall()
        for (eid,) in entity_rows:
            records += _get_entity_scoped(conn, table, eid)
    return _dedupe(records)


def _include_crm_selection(conn: sqlite3.Connection, _wi: dict,
                           table: str) -> list[dict]:
    """crm_selection: all records across the entire project."""
    return _fetch_records(conn, table, "1=1")


def _include_crm_deployment(conn: sqlite3.Connection, _wi: dict,
                            table: str) -> list[dict]:
    """crm_deployment: global + deployment/infrastructure-scoped.

    Since there's no explicit 'infrastructure' scope flag, we include global
    records only. Infrastructure-scoped records would need to be identified
    by the administrator via tagging — for now, global is the safe baseline.
    """
    return _get_global(conn, table)


# Dispatcher
_INCLUSION_RULES = {
    "master_prd": _include_master_prd,
    "business_object_discovery": _include_bod,
    "entity_prd": _include_entity_prd,
    "domain_overview": _include_domain_overview,
    "process_definition": _include_process_definition,
    "domain_reconciliation": _include_domain_reconciliation,
    "yaml_generation": _include_domain_reconciliation,  # same rules per spec
    "crm_selection": _include_crm_selection,
    "crm_deployment": _include_crm_deployment,
}


def get_decisions(
    conn: sqlite3.Connection,
    item_type: str,
    work_item: dict,
) -> list[dict]:
    """Return locked Decision records for inclusion in the prompt.

    :param conn: Open client database connection.
    :param item_type: The work item's item_type.
    :param work_item: Dict with domain_id, entity_id, process_id from WorkItem.
    :returns: List of Decision record dicts.
    """
    rule_fn = _INCLUSION_RULES.get(item_type)
    if rule_fn is None:
        return []
    return rule_fn(conn, work_item, "Decision")


def get_open_issues(
    conn: sqlite3.Connection,
    item_type: str,
    work_item: dict,
) -> list[dict]:
    """Return open OpenIssue records for inclusion in the prompt.

    :param conn: Open client database connection.
    :param item_type: The work item's item_type.
    :param work_item: Dict with domain_id, entity_id, process_id from WorkItem.
    :returns: List of OpenIssue record dicts.
    """
    rule_fn = _INCLUSION_RULES.get(item_type)
    if rule_fn is None:
        return []
    return rule_fn(conn, work_item, "OpenIssue")
