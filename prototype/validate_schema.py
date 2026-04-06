"""
Task 3 -- Validation queries proving the schema supports every major application path.

Run after create_schema.py and populate_cbm.py.
"""

import sqlite3
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_DB = os.path.join(SCRIPT_DIR, "cbm_client.db")
MASTER_DB = os.path.join(SCRIPT_DIR, "crmbuilder_master.db")

PASS = 0
WARN = 0


def run_query(conn, title, sql, params=None):
    """Run a query, print results, return rows."""
    global PASS, WARN
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print('=' * 70)
    print(f"SQL:\n{sql.strip()}\n")

    rows = conn.execute(sql, params or ()).fetchall()
    desc = [d[0] for d in conn.execute(sql, params or ()).description] if rows else []

    if not rows:
        print("  ** NO RESULTS — potential schema issue **")
        WARN += 1
        return rows

    # Print header
    print(f"  {' | '.join(desc)}")
    print(f"  {'-' * (sum(max(len(str(d)), 8) for d in desc) + 3 * (len(desc) - 1))}")
    for row in rows:
        print(f"  {' | '.join(str(v) if v is not None else 'NULL' for v in row)}")
    print(f"\n  ({len(rows)} row{'s' if len(rows) != 1 else ''})")
    PASS += 1
    return rows


# =============================================================================
# Query 1 — Dashboard: Available Work
# =============================================================================

def query_1_dashboard(conn):
    sql = """
        SELECT
            wi.id,
            wi.item_type,
            wi.phase,
            wi.status,
            COALESCE(d.code, '') AS domain,
            COALESCE(e.code, '') AS entity,
            COALESCE(p.code, '') AS process
        FROM WorkItem wi
        LEFT JOIN Domain d ON wi.domain_id = d.id
        LEFT JOIN Entity e ON wi.entity_id = e.id
        LEFT JOIN Process p ON wi.process_id = p.id
        WHERE wi.status IN ('in_progress', 'ready')
        ORDER BY
            CAST(REPLACE(wi.phase, 'Phase ', '') AS INTEGER),
            COALESCE(d.sort_order, 999)
    """
    return run_query(conn, "Query 1 — Dashboard: Available Work (in_progress + ready)", sql)


# =============================================================================
# Query 2 — Dependency Graph
# =============================================================================

def query_2_dependency_graph(conn):
    # Find the MN-INTAKE process_definition work item
    wi_row = conn.execute("""
        SELECT wi.id FROM WorkItem wi
        JOIN Process p ON wi.process_id = p.id
        WHERE wi.item_type = 'process_definition' AND p.code = 'MN-INTAKE'
    """).fetchone()

    if not wi_row:
        print("\n  ** Could not find MN-INTAKE work item **")
        return

    wi_id = wi_row[0]

    # Upstream dependencies
    sql_up = """
        SELECT
            'UPSTREAM' AS direction,
            dep_wi.item_type,
            dep_wi.phase,
            dep_wi.status,
            COALESCE(d.code, '') AS domain,
            COALESCE(e.code, '') AS entity,
            COALESCE(p.code, '') AS process
        FROM Dependency dep
        JOIN WorkItem dep_wi ON dep.depends_on_id = dep_wi.id
        LEFT JOIN Domain d ON dep_wi.domain_id = d.id
        LEFT JOIN Entity e ON dep_wi.entity_id = e.id
        LEFT JOIN Process p ON dep_wi.process_id = p.id
        WHERE dep.work_item_id = ?
    """
    run_query(conn,
              "Query 2a — Dependency Graph: MN-INTAKE Upstream Dependencies",
              sql_up, (wi_id,))

    # Downstream dependents
    sql_down = """
        SELECT
            'DOWNSTREAM' AS direction,
            wait_wi.item_type,
            wait_wi.phase,
            wait_wi.status,
            COALESCE(d.code, '') AS domain,
            COALESCE(e.code, '') AS entity,
            COALESCE(p.code, '') AS process
        FROM Dependency dep
        JOIN WorkItem wait_wi ON dep.work_item_id = wait_wi.id
        LEFT JOIN Domain d ON wait_wi.domain_id = d.id
        LEFT JOIN Entity e ON wait_wi.entity_id = e.id
        LEFT JOIN Process p ON wait_wi.process_id = p.id
        WHERE dep.depends_on_id = ?
    """
    run_query(conn,
              "Query 2b — Dependency Graph: MN-INTAKE Downstream Dependents",
              sql_down, (wi_id,))


# =============================================================================
# Query 3 — Prompt Context Assembly (process_definition)
# =============================================================================

def query_3_prompt_context(conn):
    # Assemble context for MN-MATCH process_definition
    proc_row = conn.execute(
        "SELECT id, domain_id FROM Process WHERE code = 'MN-MATCH'"
    ).fetchone()
    if not proc_row:
        print("  ** MN-MATCH not found **")
        return
    proc_id, domain_id = proc_row

    # Domain overview text
    sql_overview = """
        SELECT d.code, d.name, SUBSTR(d.domain_overview_text, 1, 120) || '...' AS overview_excerpt
        FROM Domain d WHERE d.id = ?
    """
    run_query(conn, "Query 3a — Context: Domain Overview for MN-MATCH", sql_overview, (domain_id,))

    # Personas participating in this domain
    sql_personas = """
        SELECT DISTINCT per.code, per.name, pp.role
        FROM ProcessPersona pp
        JOIN Persona per ON pp.persona_id = per.id
        JOIN Process p ON pp.process_id = p.id
        WHERE p.domain_id = ?
        ORDER BY per.code
    """
    run_query(conn, "Query 3b — Context: Personas in MN Domain", sql_personas, (domain_id,))

    # Entities relevant to this domain via ProcessEntity
    sql_entities = """
        SELECT DISTINCT e.code, e.name, e.entity_type,
            (SELECT COUNT(*) FROM Field f WHERE f.entity_id = e.id) AS field_count
        FROM ProcessEntity pe
        JOIN Entity e ON pe.entity_id = e.id
        JOIN Process p ON pe.process_id = p.id
        WHERE p.domain_id = ?
        ORDER BY e.code
    """
    run_query(conn, "Query 3c — Context: Entities in MN Domain with Field Counts",
              sql_entities, (domain_id,))

    # Prior completed processes in this domain (for sequential context)
    sql_prior = """
        SELECT p.code, p.name, p.sort_order,
            (SELECT COUNT(*) FROM ProcessStep ps WHERE ps.process_id = p.id) AS step_count,
            (SELECT COUNT(*) FROM Requirement r WHERE r.process_id = p.id) AS req_count
        FROM Process p
        JOIN WorkItem wi ON wi.process_id = p.id AND wi.item_type = 'process_definition'
        WHERE p.domain_id = ? AND wi.status = 'complete' AND p.sort_order < (
            SELECT sort_order FROM Process WHERE id = ?
        )
        ORDER BY p.sort_order
    """
    run_query(conn, "Query 3d — Context: Prior Completed Processes in MN Domain",
              sql_prior, (domain_id, proc_id))


# =============================================================================
# Query 4 — Impact Analysis Trace (Field Change)
# =============================================================================

def query_4_impact_trace(conn):
    # Trace mentorStatus field on Contact
    field_row = conn.execute(
        "SELECT id, entity_id FROM Field WHERE entity_id = (SELECT id FROM Entity WHERE code = 'CON') "
        "AND name = 'mentorStatus'"
    ).fetchone()
    if not field_row:
        print("  ** mentorStatus field not found **")
        return
    field_id = field_row[0]

    # ProcessField references
    sql_pf = """
        SELECT p.code AS process, pf.usage, pf.description
        FROM ProcessField pf
        JOIN Process p ON pf.process_id = p.id
        WHERE pf.field_id = ?
    """
    run_query(conn, "Query 4a — Impact: Processes Using mentorStatus", sql_pf, (field_id,))

    # LayoutRow references
    sql_lr = """
        SELECT lp.label AS panel, lr.sort_order AS row_num,
               CASE WHEN lr.cell_1_field_id = ? THEN 'cell_1' ELSE 'cell_2' END AS cell
        FROM LayoutRow lr
        JOIN LayoutPanel lp ON lr.panel_id = lp.id
        WHERE lr.cell_1_field_id = ? OR lr.cell_2_field_id = ?
    """
    run_query(conn, "Query 4b — Impact: Layout Rows Displaying mentorStatus",
              sql_lr, (field_id, field_id, field_id))

    # ListColumn references
    sql_lc = """
        SELECT e.code AS entity, lc.sort_order, lc.width
        FROM ListColumn lc
        JOIN Entity e ON lc.entity_id = e.id
        WHERE lc.field_id = ?
    """
    run_query(conn, "Query 4c — Impact: List Columns Displaying mentorStatus",
              sql_lc, (field_id,))

    # Persona discriminator references
    sql_per = """
        SELECT per.code, per.name, per.persona_field_value
        FROM Persona per
        WHERE per.persona_field_id = (
            SELECT id FROM Field WHERE entity_id = ? AND name = 'contactType'
        )
    """
    run_query(conn, "Query 4d — Impact: Personas Using contactType Discriminator",
              sql_per, (field_row[1],))


# =============================================================================
# Query 5 — Document Generator Data (Process Document)
# =============================================================================

def query_5_document_generator(conn):
    proc_row = conn.execute(
        "SELECT id, domain_id FROM Process WHERE code = 'MN-INTAKE'"
    ).fetchone()
    if not proc_row:
        return
    proc_id, domain_id = proc_row

    # Process metadata
    sql_proc = """
        SELECT p.code, p.name, p.triggers, p.completion_criteria
        FROM Process p WHERE p.id = ?
    """
    run_query(conn, "Query 5a — DocGen: MN-INTAKE Process Metadata", sql_proc, (proc_id,))

    # ProcessSteps sorted
    sql_steps = """
        SELECT ps.sort_order, ps.name, ps.step_type,
               COALESCE(per.code, 'SYSTEM') AS performer
        FROM ProcessStep ps
        LEFT JOIN Persona per ON ps.performer_persona_id = per.id
        WHERE ps.process_id = ?
        ORDER BY ps.sort_order
    """
    run_query(conn, "Query 5b — DocGen: MN-INTAKE Steps", sql_steps, (proc_id,))

    # Requirements
    sql_reqs = """
        SELECT r.identifier, r.description, r.priority
        FROM Requirement r
        WHERE r.process_id = ?
        ORDER BY r.identifier
    """
    run_query(conn, "Query 5c — DocGen: MN-INTAKE Requirements", sql_reqs, (proc_id,))

    # ProcessPersona with names and roles
    sql_pp = """
        SELECT per.code, per.name, pp.role, pp.description
        FROM ProcessPersona pp
        JOIN Persona per ON pp.persona_id = per.id
        WHERE pp.process_id = ?
    """
    run_query(conn, "Query 5d — DocGen: MN-INTAKE Personas and Roles", sql_pp, (proc_id,))

    # ProcessEntity and ProcessField with entity/field names
    sql_pe = """
        SELECT e.code, e.name, pe.role, pe.description
        FROM ProcessEntity pe
        JOIN Entity e ON pe.entity_id = e.id
        WHERE pe.process_id = ?
    """
    run_query(conn, "Query 5e — DocGen: MN-INTAKE Entity Usage", sql_pe, (proc_id,))

    sql_fields = """
        SELECT e.code AS entity, f.name AS field, pf.usage, pf.description
        FROM ProcessField pf
        JOIN Field f ON pf.field_id = f.id
        JOIN Entity e ON f.entity_id = e.id
        WHERE pf.process_id = ?
        ORDER BY e.code, f.sort_order
    """
    run_query(conn, "Query 5f — DocGen: MN-INTAKE Field Usage", sql_fields, (proc_id,))


# =============================================================================
# Query 6 — Staleness Detection
# =============================================================================

def query_6_staleness(conn):
    sql = """
        SELECT
            wi.id AS work_item_id,
            wi.item_type,
            COALESCE(p.code, e.code, d.code) AS scope,
            gl.file_path,
            gl.generated_at,
            cl.changed_at,
            cl.table_name || '.' || COALESCE(cl.field_name, cl.change_type) AS change_detail
        FROM GenerationLog gl
        JOIN WorkItem wi ON gl.work_item_id = wi.id
        LEFT JOIN Domain d ON wi.domain_id = d.id
        LEFT JOIN Entity e ON wi.entity_id = e.id
        LEFT JOIN Process p ON wi.process_id = p.id
        -- Find ChangeLog entries affecting records in scope
        -- For entity_prd: changes to fields on that entity
        -- For process_definition: changes to process steps/requirements
        JOIN ChangeLog cl ON (
            -- Entity PRD: field changes on the entity
            (wi.item_type = 'entity_prd' AND cl.table_name = 'Field'
             AND cl.record_id IN (SELECT f.id FROM Field f WHERE f.entity_id = wi.entity_id))
            OR
            -- Process definition: step/requirement changes
            (wi.item_type = 'process_definition' AND cl.table_name IN ('ProcessStep', 'Requirement')
             AND cl.record_id IN (
                 SELECT ps.id FROM ProcessStep ps WHERE ps.process_id = wi.process_id
                 UNION
                 SELECT r.id FROM Requirement r WHERE r.process_id = wi.process_id
             ))
            OR
            -- Entity PRD: entity-level changes
            (wi.item_type = 'entity_prd' AND cl.table_name = 'Entity'
             AND cl.record_id = wi.entity_id)
        )
        WHERE gl.generation_mode = 'final'
          AND cl.changed_at > gl.generated_at
        ORDER BY cl.changed_at DESC
    """
    return run_query(conn, "Query 6 — Staleness Detection: Documents with Post-Generation Changes", sql)


# =============================================================================
# Query 7 — Unresolved Changes
# =============================================================================

def query_7_unresolved_changes(conn):
    sql = """
        SELECT
            cl.session_id,
            cl.changed_at,
            cl.table_name,
            cl.change_type,
            cl.field_name,
            COUNT(ci.id) AS total_impacts,
            SUM(CASE WHEN ci.reviewed = 0 THEN 1 ELSE 0 END) AS unreviewed,
            SUM(CASE WHEN ci.reviewed = 1 AND ci.action_required = 1 THEN 1 ELSE 0 END) AS action_required
        FROM ChangeLog cl
        JOIN ChangeImpact ci ON ci.change_log_id = cl.id
        GROUP BY cl.id
        HAVING SUM(CASE WHEN ci.reviewed = 0 THEN 1 ELSE 0 END) > 0
        ORDER BY cl.changed_at DESC
    """
    return run_query(conn, "Query 7 — Unresolved Changes: Change Sets with Unreviewed Impacts", sql)


# =============================================================================
# Query 8 — Work Item Impact Mapping
# =============================================================================

def query_8_work_item_impact(conn):
    sql = """
        SELECT
            ci.id AS impact_id,
            ci.affected_table,
            ci.affected_record_id,
            ci.impact_description,
            ci.action_required,
            -- Map affected record to work item
            CASE
                WHEN ci.affected_table = 'ProcessField' THEN (
                    SELECT wi.item_type || ':' || COALESCE(p.code, '')
                    FROM ProcessField pf
                    JOIN Process p ON pf.process_id = p.id
                    JOIN WorkItem wi ON wi.process_id = p.id AND wi.item_type = 'process_definition'
                    WHERE pf.id = ci.affected_record_id
                    LIMIT 1
                )
                WHEN ci.affected_table = 'LayoutRow' THEN (
                    SELECT wi.item_type || ':' || COALESCE(e.code, '')
                    FROM LayoutRow lr
                    JOIN LayoutPanel lp ON lr.panel_id = lp.id
                    JOIN Entity e ON lp.entity_id = e.id
                    JOIN WorkItem wi ON wi.entity_id = e.id AND wi.item_type = 'entity_prd'
                    WHERE lr.id = ci.affected_record_id
                    LIMIT 1
                )
                ELSE 'unmapped'
            END AS affected_work_item
        FROM ChangeImpact ci
        WHERE ci.action_required = 1
        ORDER BY ci.id
    """
    return run_query(conn,
                     "Query 8 — Work Item Impact Mapping: action_required=1 Grouped by Work Item",
                     sql)


# =============================================================================
# Query 9 — Decision and Issue Inclusion
# =============================================================================

def query_9_decision_issue_cascade(conn):
    proc_row = conn.execute(
        "SELECT id, domain_id FROM Process WHERE code = 'MN-MATCH'"
    ).fetchone()
    if not proc_row:
        return
    proc_id, domain_id = proc_row

    # Decisions: global, domain-scoped, process-scoped, entity-scoped
    sql_dec = """
        SELECT dec.identifier, dec.title, dec.status,
            CASE
                WHEN dec.process_id IS NOT NULL THEN 'process-scoped'
                WHEN dec.entity_id IS NOT NULL THEN 'entity-scoped'
                WHEN dec.domain_id IS NOT NULL THEN 'domain-scoped'
                ELSE 'global'
            END AS scope_level
        FROM Decision dec
        WHERE
            -- Global (no scope)
            (dec.domain_id IS NULL AND dec.entity_id IS NULL
             AND dec.process_id IS NULL AND dec.field_id IS NULL)
            -- Domain-scoped to MN
            OR dec.domain_id = ?
            -- Process-scoped to MN-MATCH
            OR dec.process_id = ?
            -- Entity-scoped to entities used by MN-MATCH
            OR dec.entity_id IN (
                SELECT pe.entity_id FROM ProcessEntity pe WHERE pe.process_id = ?
            )
        ORDER BY
            CASE
                WHEN dec.process_id IS NOT NULL THEN 3
                WHEN dec.entity_id IS NOT NULL THEN 2
                WHEN dec.domain_id IS NOT NULL THEN 1
                ELSE 0
            END,
            dec.identifier
    """
    run_query(conn,
              "Query 9a — Decision Cascade for MN-MATCH (global → domain → entity → process)",
              sql_dec, (domain_id, proc_id, proc_id))

    # Same cascade for OpenIssues
    sql_iss = """
        SELECT iss.identifier, iss.title, iss.status, iss.priority,
            CASE
                WHEN iss.process_id IS NOT NULL THEN 'process-scoped'
                WHEN iss.entity_id IS NOT NULL THEN 'entity-scoped'
                WHEN iss.domain_id IS NOT NULL THEN 'domain-scoped'
                ELSE 'global'
            END AS scope_level
        FROM OpenIssue iss
        WHERE
            (iss.domain_id IS NULL AND iss.entity_id IS NULL
             AND iss.process_id IS NULL AND iss.field_id IS NULL)
            OR iss.domain_id = ?
            OR iss.process_id = ?
            OR iss.entity_id IN (
                SELECT pe.entity_id FROM ProcessEntity pe WHERE pe.process_id = ?
            )
        ORDER BY
            CASE iss.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
            iss.identifier
    """
    run_query(conn,
              "Query 9b — Open Issue Cascade for MN-MATCH",
              sql_iss, (domain_id, proc_id, proc_id))


# =============================================================================
# Query 10 — Audit Trail
# =============================================================================

def query_10_audit_trail(conn):
    sql = """
        SELECT
            f.name AS field_name,
            e.code AS entity,
            cl.change_type,
            cl.field_name AS changed_column,
            cl.old_value,
            cl.new_value,
            cl.rationale,
            cl.changed_at,
            ais.session_type,
            ais.started_at AS session_started,
            wi.item_type AS session_work_item_type,
            COALESCE(d.code, '') AS session_domain
        FROM ChangeLog cl
        JOIN Field f ON cl.record_id = f.id AND cl.table_name = 'Field'
        JOIN Entity e ON f.entity_id = e.id
        LEFT JOIN AISession ais ON cl.session_id = ais.id
        LEFT JOIN WorkItem wi ON ais.work_item_id = wi.id
        LEFT JOIN Domain d ON wi.domain_id = d.id
        WHERE e.code = 'CON' AND f.name = 'mentorStatus'
        ORDER BY cl.changed_at
    """
    return run_query(conn,
                     "Query 10 — Audit Trail: mentorStatus Field Changes with Session Context",
                     sql)


# =============================================================================
# Main
# =============================================================================

def main():
    conn = sqlite3.connect(CLIENT_DB)
    conn.execute("PRAGMA foreign_keys = ON")

    print("CRM Builder Automation — Schema Validation Queries")
    print("=" * 70)

    query_1_dashboard(conn)
    query_2_dependency_graph(conn)
    query_3_prompt_context(conn)
    query_4_impact_trace(conn)
    query_5_document_generator(conn)
    query_6_staleness(conn)
    query_7_unresolved_changes(conn)
    query_8_work_item_impact(conn)
    query_9_decision_issue_cascade(conn)
    query_10_audit_trail(conn)

    conn.close()

    print("\n" + "=" * 70)
    print(f"  VALIDATION SUMMARY: {PASS} queries returned results, {WARN} returned empty")
    print("=" * 70)


if __name__ == "__main__":
    main()
