"""
Task 1 -- Create both databases for the CRM Builder Automation schema.

Master database: crmbuilder_master.db  (1 table)
Client database: cbm_client.db         (25 tables across 5 layers)

Schema source: L2 PRD Sections 2-8, with changes from 9.9, 10.10, 12.11, 13.13.
"""

import sqlite3
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_DB = os.path.join(SCRIPT_DIR, "crmbuilder_master.db")
CLIENT_DB = os.path.join(SCRIPT_DIR, "cbm_client.db")


def create_master_database():
    """Create the master database with the Client table (Section 3.1 + 10.10)."""
    if os.path.exists(MASTER_DB):
        os.remove(MASTER_DB)

    conn = sqlite3.connect(MASTER_DB)
    conn.execute("PRAGMA foreign_keys = ON")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE Client (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            name                  TEXT NOT NULL,
            code                  TEXT NOT NULL UNIQUE,
            description           TEXT,
            database_path         TEXT NOT NULL,
            organization_overview TEXT,          -- Section 10.10
            crm_platform          TEXT,          -- Section 10.10
            created_at            TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at            TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()
    print(f"Created {MASTER_DB}")


def create_client_database():
    """Create the client database with 25 tables across 5 layers."""
    if os.path.exists(CLIENT_DB):
        os.remove(CLIENT_DB)

    conn = sqlite3.connect(CLIENT_DB)
    conn.execute("PRAGMA foreign_keys = ON")
    c = conn.cursor()

    # =========================================================================
    # REQUIREMENTS LAYER  (Sections 4.1 - 4.10)
    # =========================================================================

    # 4.1 Domain  (+Section 10.10: parent_domain_id, is_service,
    #              domain_overview_text, domain_reconciliation_text)
    c.execute("""
        CREATE TABLE Domain (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            name                      TEXT NOT NULL,
            code                      TEXT NOT NULL UNIQUE,
            description               TEXT,
            sort_order                INTEGER,
            parent_domain_id          INTEGER,          -- Section 10.10
            is_service                BOOLEAN NOT NULL DEFAULT 0,  -- Section 10.10
            domain_overview_text      TEXT,              -- Section 10.10
            domain_reconciliation_text TEXT,             -- Section 10.10
            created_at                TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at                TEXT NOT NULL DEFAULT (datetime('now')),
            created_by_session_id     INTEGER,
            FOREIGN KEY (parent_domain_id) REFERENCES Domain(id),
            FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
        )
    """)

    # 4.2 Entity  (+Section 10.10: primary_domain_id)
    c.execute("""
        CREATE TABLE Entity (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            name                  TEXT NOT NULL,
            code                  TEXT NOT NULL UNIQUE,
            entity_type           TEXT NOT NULL,
            is_native             BOOLEAN NOT NULL,
            singular_label        TEXT,
            plural_label          TEXT,
            description           TEXT,
            primary_domain_id     INTEGER,              -- Section 10.10
            created_at            TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at            TEXT NOT NULL DEFAULT (datetime('now')),
            created_by_session_id INTEGER,
            FOREIGN KEY (primary_domain_id) REFERENCES Domain(id),
            FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
        )
    """)

    # 4.3 Field  (+Section 10.10: is_native)
    c.execute("""
        CREATE TABLE Field (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id             INTEGER NOT NULL,
            name                  TEXT NOT NULL,
            label                 TEXT NOT NULL,
            field_type            TEXT NOT NULL,
            is_required           BOOLEAN NOT NULL DEFAULT 0,
            default_value         TEXT,
            read_only             BOOLEAN NOT NULL DEFAULT 0,
            audited               BOOLEAN NOT NULL DEFAULT 0,
            category              TEXT,
            max_length            INTEGER,
            min_value             REAL,
            max_value             REAL,
            is_sorted             BOOLEAN NOT NULL DEFAULT 0,
            display_as_label      BOOLEAN NOT NULL DEFAULT 0,
            tooltip               TEXT,
            description           TEXT,
            sort_order            INTEGER,
            is_native             BOOLEAN NOT NULL DEFAULT 0,  -- Section 10.10
            created_at            TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at            TEXT NOT NULL DEFAULT (datetime('now')),
            created_by_session_id INTEGER,
            FOREIGN KEY (entity_id) REFERENCES Entity(id),
            FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
        )
    """)

    # 4.4 FieldOption
    c.execute("""
        CREATE TABLE FieldOption (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            field_id              INTEGER NOT NULL,
            value                 TEXT NOT NULL,
            label                 TEXT NOT NULL,
            description           TEXT,
            style                 TEXT,
            sort_order            INTEGER,
            is_default            BOOLEAN NOT NULL DEFAULT 0,
            created_at            TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at            TEXT NOT NULL DEFAULT (datetime('now')),
            created_by_session_id INTEGER,
            FOREIGN KEY (field_id) REFERENCES Field(id),
            FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
        )
    """)

    # 4.5 Relationship
    c.execute("""
        CREATE TABLE Relationship (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            name                  TEXT NOT NULL,
            description           TEXT NOT NULL,
            entity_id             INTEGER NOT NULL,
            entity_foreign_id     INTEGER NOT NULL,
            link_type             TEXT NOT NULL,
            link                  TEXT NOT NULL,
            link_foreign          TEXT NOT NULL,
            label                 TEXT NOT NULL,
            label_foreign         TEXT NOT NULL,
            relation_name         TEXT,
            audited               BOOLEAN NOT NULL DEFAULT 0,
            audited_foreign       BOOLEAN NOT NULL DEFAULT 0,
            action                TEXT,
            created_at            TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at            TEXT NOT NULL DEFAULT (datetime('now')),
            created_by_session_id INTEGER,
            FOREIGN KEY (entity_id) REFERENCES Entity(id),
            FOREIGN KEY (entity_foreign_id) REFERENCES Entity(id),
            FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
        )
    """)

    # 4.6 Persona
    c.execute("""
        CREATE TABLE Persona (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            name                  TEXT NOT NULL,
            code                  TEXT NOT NULL UNIQUE,
            description           TEXT,
            persona_entity_id     INTEGER,
            persona_field_id      INTEGER,
            persona_field_value   TEXT,
            created_at            TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at            TEXT NOT NULL DEFAULT (datetime('now')),
            created_by_session_id INTEGER,
            FOREIGN KEY (persona_entity_id) REFERENCES Entity(id),
            FOREIGN KEY (persona_field_id) REFERENCES Field(id),
            FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
        )
    """)

    # 4.7 BusinessObject
    c.execute("""
        CREATE TABLE BusinessObject (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            name                  TEXT NOT NULL,
            description           TEXT,
            status                TEXT NOT NULL,
            resolution            TEXT,
            resolved_to_entity_id  INTEGER,
            resolved_to_process_id INTEGER,
            resolved_to_persona_id INTEGER,
            resolution_detail     TEXT,
            created_at            TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at            TEXT NOT NULL DEFAULT (datetime('now')),
            created_by_session_id INTEGER,
            FOREIGN KEY (resolved_to_entity_id) REFERENCES Entity(id),
            FOREIGN KEY (resolved_to_process_id) REFERENCES Process(id),
            FOREIGN KEY (resolved_to_persona_id) REFERENCES Persona(id),
            FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
        )
    """)

    # 4.8 Process
    c.execute("""
        CREATE TABLE Process (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            domain_id             INTEGER NOT NULL,
            name                  TEXT NOT NULL,
            code                  TEXT NOT NULL UNIQUE,
            description           TEXT,
            triggers              TEXT,
            completion_criteria   TEXT,
            sort_order            INTEGER NOT NULL,
            tier                  TEXT,
            created_at            TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at            TEXT NOT NULL DEFAULT (datetime('now')),
            created_by_session_id INTEGER,
            FOREIGN KEY (domain_id) REFERENCES Domain(id),
            FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
        )
    """)

    # 4.9 ProcessStep
    c.execute("""
        CREATE TABLE ProcessStep (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            process_id            INTEGER NOT NULL,
            name                  TEXT NOT NULL,
            description           TEXT,
            step_type             TEXT NOT NULL,
            performer_persona_id  INTEGER,
            sort_order            INTEGER NOT NULL,
            created_at            TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at            TEXT NOT NULL DEFAULT (datetime('now')),
            created_by_session_id INTEGER,
            FOREIGN KEY (process_id) REFERENCES Process(id),
            FOREIGN KEY (performer_persona_id) REFERENCES Persona(id),
            FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
        )
    """)

    # 4.10 Requirement
    c.execute("""
        CREATE TABLE Requirement (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier            TEXT NOT NULL UNIQUE,
            process_id            INTEGER NOT NULL,
            description           TEXT NOT NULL,
            priority              TEXT,
            status                TEXT NOT NULL,
            created_at            TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at            TEXT NOT NULL DEFAULT (datetime('now')),
            created_by_session_id INTEGER,
            FOREIGN KEY (process_id) REFERENCES Process(id),
            FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
        )
    """)

    # =========================================================================
    # CROSS-REFERENCE LAYER  (Sections 5.1 - 5.3)
    # =========================================================================

    # 5.1 ProcessEntity
    c.execute("""
        CREATE TABLE ProcessEntity (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            process_id      INTEGER NOT NULL,
            entity_id       INTEGER NOT NULL,
            process_step_id INTEGER,
            role            TEXT NOT NULL,
            description     TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (process_id) REFERENCES Process(id),
            FOREIGN KEY (entity_id) REFERENCES Entity(id),
            FOREIGN KEY (process_step_id) REFERENCES ProcessStep(id)
        )
    """)

    # 5.2 ProcessField
    c.execute("""
        CREATE TABLE ProcessField (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            process_id      INTEGER NOT NULL,
            field_id        INTEGER NOT NULL,
            process_step_id INTEGER,
            usage           TEXT NOT NULL,
            description     TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (process_id) REFERENCES Process(id),
            FOREIGN KEY (field_id) REFERENCES Field(id),
            FOREIGN KEY (process_step_id) REFERENCES ProcessStep(id)
        )
    """)

    # 5.3 ProcessPersona
    c.execute("""
        CREATE TABLE ProcessPersona (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            process_id  INTEGER NOT NULL,
            persona_id  INTEGER NOT NULL,
            role        TEXT NOT NULL,
            description TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (process_id) REFERENCES Process(id),
            FOREIGN KEY (persona_id) REFERENCES Persona(id)
        )
    """)

    # =========================================================================
    # MANAGEMENT LAYER  (Sections 6.1 - 6.4)
    # =========================================================================

    # 6.1 Decision
    c.execute("""
        CREATE TABLE Decision (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier            TEXT NOT NULL UNIQUE,
            title                 TEXT NOT NULL,
            description           TEXT NOT NULL,
            status                TEXT NOT NULL,
            domain_id             INTEGER,
            entity_id             INTEGER,
            process_id            INTEGER,
            field_id              INTEGER,
            requirement_id        INTEGER,
            business_object_id    INTEGER,
            superseded_by_id      INTEGER,
            created_at            TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at            TEXT NOT NULL DEFAULT (datetime('now')),
            created_by_session_id INTEGER,
            locked_at             TEXT,
            locked_by_session_id  INTEGER,
            FOREIGN KEY (domain_id) REFERENCES Domain(id),
            FOREIGN KEY (entity_id) REFERENCES Entity(id),
            FOREIGN KEY (process_id) REFERENCES Process(id),
            FOREIGN KEY (field_id) REFERENCES Field(id),
            FOREIGN KEY (requirement_id) REFERENCES Requirement(id),
            FOREIGN KEY (business_object_id) REFERENCES BusinessObject(id),
            FOREIGN KEY (superseded_by_id) REFERENCES Decision(id),
            FOREIGN KEY (created_by_session_id) REFERENCES AISession(id),
            FOREIGN KEY (locked_by_session_id) REFERENCES AISession(id)
        )
    """)

    # 6.2 OpenIssue
    c.execute("""
        CREATE TABLE OpenIssue (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier              TEXT NOT NULL UNIQUE,
            title                   TEXT NOT NULL,
            description             TEXT NOT NULL,
            status                  TEXT NOT NULL,
            priority                TEXT,
            domain_id               INTEGER,
            entity_id               INTEGER,
            process_id              INTEGER,
            field_id                INTEGER,
            requirement_id          INTEGER,
            business_object_id      INTEGER,
            resolution              TEXT,
            resolved_by_decision_id INTEGER,
            created_at              TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at              TEXT NOT NULL DEFAULT (datetime('now')),
            created_by_session_id   INTEGER,
            resolved_at             TEXT,
            resolved_by_session_id  INTEGER,
            FOREIGN KEY (domain_id) REFERENCES Domain(id),
            FOREIGN KEY (entity_id) REFERENCES Entity(id),
            FOREIGN KEY (process_id) REFERENCES Process(id),
            FOREIGN KEY (field_id) REFERENCES Field(id),
            FOREIGN KEY (requirement_id) REFERENCES Requirement(id),
            FOREIGN KEY (business_object_id) REFERENCES BusinessObject(id),
            FOREIGN KEY (resolved_by_decision_id) REFERENCES Decision(id),
            FOREIGN KEY (created_by_session_id) REFERENCES AISession(id),
            FOREIGN KEY (resolved_by_session_id) REFERENCES AISession(id)
        )
    """)

    # 6.3 WorkItem  (+Section 9.9: status_before_blocked)
    c.execute("""
        CREATE TABLE WorkItem (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type             TEXT NOT NULL,
            domain_id             INTEGER,
            entity_id             INTEGER,
            process_id            INTEGER,
            phase                 TEXT NOT NULL
                                  CHECK (phase IN (
                                      'Phase 1', 'Phase 2', 'Phase 3', 'Phase 4',
                                      'Phase 5', 'Phase 6', 'Phase 7', 'Phase 8',
                                      'Phase 9', 'Phase 10', 'Phase 11'
                                  )),
            status                TEXT NOT NULL,
            blocked_reason        TEXT,
            status_before_blocked TEXT,          -- Section 9.9
            started_at            TEXT,
            completed_at          TEXT,
            created_at            TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at            TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (domain_id) REFERENCES Domain(id),
            FOREIGN KEY (entity_id) REFERENCES Entity(id),
            FOREIGN KEY (process_id) REFERENCES Process(id),
            CHECK (item_type IN (
                'master_prd', 'business_object_discovery', 'entity_prd',
                'domain_overview', 'process_definition', 'domain_reconciliation',
                'stakeholder_review', 'yaml_generation', 'crm_selection',
                'crm_deployment', 'crm_configuration', 'verification'
            )),
            CHECK (status IN (
                'not_started', 'ready', 'in_progress', 'complete', 'blocked'
            ))
        )
    """)

    # 6.4 Dependency
    c.execute("""
        CREATE TABLE Dependency (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            work_item_id  INTEGER NOT NULL,
            depends_on_id INTEGER NOT NULL,
            FOREIGN KEY (work_item_id) REFERENCES WorkItem(id),
            FOREIGN KEY (depends_on_id) REFERENCES WorkItem(id),
            UNIQUE (work_item_id, depends_on_id)
        )
    """)

    # =========================================================================
    # AUDIT LAYER  (Sections 7.1 - 7.3 + 13.13)
    # =========================================================================

    # 7.1 AISession
    c.execute("""
        CREATE TABLE AISession (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            work_item_id      INTEGER NOT NULL,
            session_type      TEXT NOT NULL,
            generated_prompt  TEXT NOT NULL,
            raw_output        TEXT,
            structured_output TEXT,
            import_status     TEXT NOT NULL,
            notes             TEXT,
            started_at        TEXT NOT NULL,
            completed_at      TEXT,
            created_at        TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (work_item_id) REFERENCES WorkItem(id),
            CHECK (session_type IN ('initial', 'revision', 'clarification')),
            CHECK (import_status IN ('pending', 'imported', 'partial', 'rejected'))
        )
    """)

    # 7.2 ChangeLog
    c.execute("""
        CREATE TABLE ChangeLog (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  INTEGER,
            table_name  TEXT NOT NULL,
            record_id   INTEGER NOT NULL,
            change_type TEXT NOT NULL,
            field_name  TEXT,
            old_value   TEXT,
            new_value   TEXT,
            rationale   TEXT,
            changed_at  TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES AISession(id),
            CHECK (change_type IN ('insert', 'update', 'delete'))
        )
    """)

    # 7.3 ChangeImpact  (+Section 12.11: action_required)
    c.execute("""
        CREATE TABLE ChangeImpact (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            change_log_id       INTEGER NOT NULL,
            affected_table      TEXT NOT NULL,
            affected_record_id  INTEGER NOT NULL,
            impact_description  TEXT,
            requires_review     BOOLEAN NOT NULL DEFAULT 1,
            reviewed            BOOLEAN NOT NULL DEFAULT 0,
            reviewed_at         TEXT,
            action_required     BOOLEAN NOT NULL DEFAULT 0,  -- Section 12.11
            FOREIGN KEY (change_log_id) REFERENCES ChangeLog(id)
        )
    """)

    # 13.13 GenerationLog
    c.execute("""
        CREATE TABLE GenerationLog (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            work_item_id    INTEGER NOT NULL,
            document_type   TEXT NOT NULL,
            file_path       TEXT NOT NULL,
            generated_at    TEXT NOT NULL,
            generation_mode TEXT NOT NULL,
            git_commit_hash TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (work_item_id) REFERENCES WorkItem(id),
            CHECK (generation_mode IN ('final', 'draft')),
            CHECK (document_type IN (
                'master_prd', 'entity_inventory', 'entity_prd',
                'domain_overview', 'process_document', 'domain_prd',
                'yaml_program_files', 'crm_evaluation_report'
            ))
        )
    """)

    # =========================================================================
    # LAYOUT LAYER  (Sections 8.1 - 8.4)
    # =========================================================================

    # 8.1 LayoutPanel
    c.execute("""
        CREATE TABLE LayoutPanel (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id               INTEGER NOT NULL,
            label                   TEXT NOT NULL,
            description             TEXT,
            tab_break               BOOLEAN NOT NULL DEFAULT 0,
            tab_label               TEXT,
            style                   TEXT,
            hidden                  BOOLEAN NOT NULL DEFAULT 0,
            sort_order              INTEGER NOT NULL,
            layout_mode             TEXT NOT NULL,
            dynamic_logic_attribute TEXT,
            dynamic_logic_value     TEXT,
            created_at              TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at              TEXT NOT NULL DEFAULT (datetime('now')),
            created_by_session_id   INTEGER,
            FOREIGN KEY (entity_id) REFERENCES Entity(id),
            FOREIGN KEY (created_by_session_id) REFERENCES AISession(id),
            CHECK (layout_mode IN ('rows', 'tabs'))
        )
    """)

    # 8.2 LayoutRow
    c.execute("""
        CREATE TABLE LayoutRow (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            panel_id        INTEGER NOT NULL,
            sort_order      INTEGER NOT NULL,
            cell_1_field_id INTEGER,
            cell_2_field_id INTEGER,
            is_full_width   BOOLEAN NOT NULL DEFAULT 0,
            FOREIGN KEY (panel_id) REFERENCES LayoutPanel(id),
            FOREIGN KEY (cell_1_field_id) REFERENCES Field(id),
            FOREIGN KEY (cell_2_field_id) REFERENCES Field(id),
            CHECK (cell_1_field_id IS NOT NULL OR cell_2_field_id IS NOT NULL)
        )
    """)

    # 8.3 LayoutTab
    c.execute("""
        CREATE TABLE LayoutTab (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            panel_id   INTEGER NOT NULL,
            label      TEXT NOT NULL,
            category   TEXT NOT NULL,
            sort_order INTEGER NOT NULL,
            FOREIGN KEY (panel_id) REFERENCES LayoutPanel(id)
        )
    """)

    # 8.4 ListColumn
    c.execute("""
        CREATE TABLE ListColumn (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id  INTEGER NOT NULL,
            field_id   INTEGER NOT NULL,
            width      INTEGER,
            sort_order INTEGER NOT NULL,
            FOREIGN KEY (entity_id) REFERENCES Entity(id),
            FOREIGN KEY (field_id) REFERENCES Field(id)
        )
    """)

    conn.commit()
    conn.close()
    print(f"Created {CLIENT_DB}")


def verify_databases():
    """Verify both databases were created correctly."""
    print("\n--- Verification ---")

    # Master DB
    conn = sqlite3.connect(MASTER_DB)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print(f"\nMaster DB tables ({len(tables)}):")
    for t in tables:
        print(f"  {t[0]}")
    conn.close()

    # Client DB
    conn = sqlite3.connect(CLIENT_DB)
    conn.execute("PRAGMA foreign_keys = ON")
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print(f"\nClient DB tables ({len(tables)}):")
    for t in tables:
        print(f"  {t[0]}")

    # Test insert/select with FK references
    print("\n--- Test Insert/Select with FK ---")
    c = conn.cursor()

    # Insert a Domain
    c.execute("""
        INSERT INTO Domain (name, code, description, sort_order)
        VALUES ('Test Domain', 'TEST', 'Test description', 1)
    """)
    domain_id = c.lastrowid

    # Insert an Entity referencing the Domain
    c.execute("""
        INSERT INTO Entity (name, code, entity_type, is_native, primary_domain_id)
        VALUES ('Test Entity', 'TST', 'Base', 0, ?)
    """, (domain_id,))
    entity_id = c.lastrowid

    # Insert a Field referencing the Entity
    c.execute("""
        INSERT INTO Field (entity_id, name, label, field_type, is_native)
        VALUES (?, 'testField', 'Test Field', 'varchar', 0)
    """, (entity_id,))
    field_id = c.lastrowid

    # Insert a FieldOption referencing the Field
    c.execute("""
        INSERT INTO FieldOption (field_id, value, label)
        VALUES (?, 'option1', 'Option 1')
    """, (field_id,))

    # Select with JOINs to verify FK chain
    row = c.execute("""
        SELECT d.name, e.name, f.name, fo.value
        FROM FieldOption fo
        JOIN Field f ON fo.field_id = f.id
        JOIN Entity e ON f.entity_id = e.id
        JOIN Domain d ON e.primary_domain_id = d.id
        WHERE d.code = 'TEST'
    """).fetchone()

    print(f"  Domain: {row[0]}, Entity: {row[1]}, Field: {row[2]}, Option: {row[3]}")
    print("  FK chain verified successfully!")

    # Clean up test data
    conn.execute("DELETE FROM FieldOption")
    conn.execute("DELETE FROM Field")
    conn.execute("DELETE FROM Entity")
    conn.execute("DELETE FROM Domain")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    print("Creating CRM Builder Automation schema prototype...\n")
    create_master_database()
    create_client_database()
    verify_databases()
    print("\nDone.")
