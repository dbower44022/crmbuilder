"""Client database schema for CRM Builder Automation.

Each client implementation has its own SQLite database with tables organized
into five layers: Requirements, Cross-Reference, Management, Audit, and Layout.
Schema defined in L2 PRD Sections 4-8, with additional columns from Sections
9.9, 10.10, and 13.13.
"""

CLIENT_SCHEMA_VERSION = 1

SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# Requirements Layer (Section 4)
# ---------------------------------------------------------------------------

DOMAIN_TABLE = """
CREATE TABLE Domain (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    description TEXT,
    sort_order INTEGER,
    parent_domain_id INTEGER,
    is_service BOOLEAN NOT NULL DEFAULT FALSE,
    domain_overview_text TEXT,
    domain_reconciliation_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_session_id INTEGER,
    FOREIGN KEY (parent_domain_id) REFERENCES Domain(id),
    FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
);
"""

ENTITY_TABLE = """
CREATE TABLE Entity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('Base', 'Person', 'Company', 'Event')),
    is_native BOOLEAN NOT NULL,
    singular_label TEXT,
    plural_label TEXT,
    description TEXT,
    primary_domain_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_session_id INTEGER,
    FOREIGN KEY (primary_domain_id) REFERENCES Domain(id),
    FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
);
"""

FIELD_TABLE = """
CREATE TABLE Field (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT NOT NULL CHECK (field_type IN (
        'varchar', 'text', 'wysiwyg', 'bool', 'int', 'float',
        'date', 'datetime', 'currency', 'url', 'email', 'phone',
        'enum', 'multiEnum'
    )),
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    default_value TEXT,
    read_only BOOLEAN NOT NULL DEFAULT FALSE,
    audited BOOLEAN NOT NULL DEFAULT FALSE,
    category TEXT,
    max_length INTEGER,
    min_value REAL,
    max_value REAL,
    is_sorted BOOLEAN NOT NULL DEFAULT FALSE,
    display_as_label BOOLEAN NOT NULL DEFAULT FALSE,
    tooltip TEXT,
    description TEXT,
    sort_order INTEGER,
    is_native BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_session_id INTEGER,
    FOREIGN KEY (entity_id) REFERENCES Entity(id),
    FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
);
"""

FIELD_OPTION_TABLE = """
CREATE TABLE FieldOption (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id INTEGER NOT NULL,
    value TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    style TEXT CHECK (style IS NULL OR style IN ('default', 'primary', 'success', 'danger', 'warning', 'info')),
    sort_order INTEGER,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_session_id INTEGER,
    FOREIGN KEY (field_id) REFERENCES Field(id),
    FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
);
"""

RELATIONSHIP_TABLE = """
CREATE TABLE Relationship (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    entity_foreign_id INTEGER NOT NULL,
    link_type TEXT NOT NULL CHECK (link_type IN ('oneToMany', 'manyToOne', 'manyToMany')),
    link TEXT NOT NULL,
    link_foreign TEXT NOT NULL,
    label TEXT NOT NULL,
    label_foreign TEXT NOT NULL,
    relation_name TEXT,
    audited BOOLEAN NOT NULL DEFAULT FALSE,
    audited_foreign BOOLEAN NOT NULL DEFAULT FALSE,
    action TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_session_id INTEGER,
    FOREIGN KEY (entity_id) REFERENCES Entity(id),
    FOREIGN KEY (entity_foreign_id) REFERENCES Entity(id),
    FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
);
"""

PERSONA_TABLE = """
CREATE TABLE Persona (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    description TEXT,
    persona_entity_id INTEGER,
    persona_field_id INTEGER,
    persona_field_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_session_id INTEGER,
    FOREIGN KEY (persona_entity_id) REFERENCES Entity(id),
    FOREIGN KEY (persona_field_id) REFERENCES Field(id),
    FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
);
"""

BUSINESS_OBJECT_TABLE = """
CREATE TABLE BusinessObject (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL CHECK (status IN ('unclassified', 'classified', 'excluded')),
    resolution TEXT CHECK (resolution IS NULL OR resolution IN (
        'entity', 'process', 'persona', 'field_value',
        'lifecycle_state', 'relationship'
    )),
    resolved_to_entity_id INTEGER,
    resolved_to_process_id INTEGER,
    resolved_to_persona_id INTEGER,
    resolution_detail TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_session_id INTEGER,
    FOREIGN KEY (resolved_to_entity_id) REFERENCES Entity(id),
    FOREIGN KEY (resolved_to_process_id) REFERENCES Process(id),
    FOREIGN KEY (resolved_to_persona_id) REFERENCES Persona(id),
    FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
);
"""

PROCESS_TABLE = """
CREATE TABLE Process (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    description TEXT,
    triggers TEXT,
    completion_criteria TEXT,
    sort_order INTEGER NOT NULL,
    tier TEXT CHECK (tier IS NULL OR tier IN ('core', 'important', 'enhancement')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_session_id INTEGER,
    FOREIGN KEY (domain_id) REFERENCES Domain(id),
    FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
);
"""

PROCESS_STEP_TABLE = """
CREATE TABLE ProcessStep (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    process_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    step_type TEXT NOT NULL CHECK (step_type IN ('action', 'decision', 'system', 'notification')),
    performer_persona_id INTEGER,
    sort_order INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_session_id INTEGER,
    FOREIGN KEY (process_id) REFERENCES Process(id),
    FOREIGN KEY (performer_persona_id) REFERENCES Persona(id),
    FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
);
"""

REQUIREMENT_TABLE = """
CREATE TABLE Requirement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier TEXT NOT NULL UNIQUE,
    process_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    priority TEXT CHECK (priority IS NULL OR priority IN ('must', 'should', 'may')),
    status TEXT NOT NULL CHECK (status IN ('proposed', 'approved', 'deferred', 'removed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_session_id INTEGER,
    FOREIGN KEY (process_id) REFERENCES Process(id),
    FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
);
"""

# ---------------------------------------------------------------------------
# Cross-Reference Layer (Section 5)
# ---------------------------------------------------------------------------

PROCESS_ENTITY_TABLE = """
CREATE TABLE ProcessEntity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    process_id INTEGER NOT NULL,
    entity_id INTEGER NOT NULL,
    process_step_id INTEGER,
    role TEXT NOT NULL CHECK (role IN ('primary', 'referenced', 'created', 'updated')),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (process_id) REFERENCES Process(id),
    FOREIGN KEY (entity_id) REFERENCES Entity(id),
    FOREIGN KEY (process_step_id) REFERENCES ProcessStep(id)
);
"""

PROCESS_FIELD_TABLE = """
CREATE TABLE ProcessField (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    process_id INTEGER NOT NULL,
    field_id INTEGER NOT NULL,
    process_step_id INTEGER,
    usage TEXT NOT NULL CHECK (usage IN (
        'collected', 'displayed', 'updated', 'evaluated', 'filtered', 'calculated'
    )),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (process_id) REFERENCES Process(id),
    FOREIGN KEY (field_id) REFERENCES Field(id),
    FOREIGN KEY (process_step_id) REFERENCES ProcessStep(id)
);
"""

PROCESS_PERSONA_TABLE = """
CREATE TABLE ProcessPersona (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    process_id INTEGER NOT NULL,
    persona_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('initiator', 'performer', 'approver', 'recipient', 'observer')),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (process_id) REFERENCES Process(id),
    FOREIGN KEY (persona_id) REFERENCES Persona(id)
);
"""

# ---------------------------------------------------------------------------
# Management Layer (Section 6)
# ---------------------------------------------------------------------------

DECISION_TABLE = """
CREATE TABLE Decision (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('proposed', 'locked', 'superseded')),
    domain_id INTEGER,
    entity_id INTEGER,
    process_id INTEGER,
    field_id INTEGER,
    requirement_id INTEGER,
    business_object_id INTEGER,
    superseded_by_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_session_id INTEGER,
    locked_at TIMESTAMP,
    locked_by_session_id INTEGER,
    FOREIGN KEY (domain_id) REFERENCES Domain(id),
    FOREIGN KEY (entity_id) REFERENCES Entity(id),
    FOREIGN KEY (process_id) REFERENCES Process(id),
    FOREIGN KEY (field_id) REFERENCES Field(id),
    FOREIGN KEY (requirement_id) REFERENCES Requirement(id),
    FOREIGN KEY (business_object_id) REFERENCES BusinessObject(id),
    FOREIGN KEY (superseded_by_id) REFERENCES Decision(id),
    FOREIGN KEY (created_by_session_id) REFERENCES AISession(id),
    FOREIGN KEY (locked_by_session_id) REFERENCES AISession(id)
);
"""

OPEN_ISSUE_TABLE = """
CREATE TABLE OpenIssue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'resolved', 'deferred')),
    priority TEXT CHECK (priority IS NULL OR priority IN ('high', 'medium', 'low')),
    domain_id INTEGER,
    entity_id INTEGER,
    process_id INTEGER,
    field_id INTEGER,
    requirement_id INTEGER,
    business_object_id INTEGER,
    resolution TEXT,
    resolved_by_decision_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_session_id INTEGER,
    resolved_at TIMESTAMP,
    resolved_by_session_id INTEGER,
    FOREIGN KEY (domain_id) REFERENCES Domain(id),
    FOREIGN KEY (entity_id) REFERENCES Entity(id),
    FOREIGN KEY (process_id) REFERENCES Process(id),
    FOREIGN KEY (field_id) REFERENCES Field(id),
    FOREIGN KEY (requirement_id) REFERENCES Requirement(id),
    FOREIGN KEY (business_object_id) REFERENCES BusinessObject(id),
    FOREIGN KEY (resolved_by_decision_id) REFERENCES Decision(id),
    FOREIGN KEY (created_by_session_id) REFERENCES AISession(id),
    FOREIGN KEY (resolved_by_session_id) REFERENCES AISession(id)
);
"""

WORK_ITEM_TABLE = """
CREATE TABLE WorkItem (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type TEXT NOT NULL CHECK (item_type IN (
        'master_prd', 'business_object_discovery', 'entity_prd',
        'domain_overview', 'process_definition', 'domain_reconciliation',
        'stakeholder_review', 'yaml_generation', 'crm_selection',
        'crm_deployment', 'crm_configuration', 'verification'
    )),
    domain_id INTEGER,
    entity_id INTEGER,
    process_id INTEGER,
    status TEXT NOT NULL CHECK (status IN (
        'not_started', 'ready', 'in_progress', 'complete', 'blocked'
    )),
    blocked_reason TEXT,
    status_before_blocked TEXT CHECK (status_before_blocked IS NULL OR status_before_blocked IN (
        'not_started', 'ready', 'in_progress', 'complete'
    )),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (domain_id) REFERENCES Domain(id),
    FOREIGN KEY (entity_id) REFERENCES Entity(id),
    FOREIGN KEY (process_id) REFERENCES Process(id)
);
"""

DEPENDENCY_TABLE = """
CREATE TABLE Dependency (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_item_id INTEGER NOT NULL,
    depends_on_id INTEGER NOT NULL,
    UNIQUE (work_item_id, depends_on_id),
    FOREIGN KEY (work_item_id) REFERENCES WorkItem(id),
    FOREIGN KEY (depends_on_id) REFERENCES WorkItem(id)
);
"""

# ---------------------------------------------------------------------------
# Audit Layer (Section 7)
# ---------------------------------------------------------------------------

AI_SESSION_TABLE = """
CREATE TABLE AISession (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_item_id INTEGER NOT NULL,
    session_type TEXT NOT NULL CHECK (session_type IN ('initial', 'revision', 'clarification')),
    generated_prompt TEXT NOT NULL,
    raw_output TEXT,
    structured_output TEXT,
    import_status TEXT NOT NULL CHECK (import_status IN (
        'pending', 'imported', 'partial', 'rejected'
    )),
    notes TEXT,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (work_item_id) REFERENCES WorkItem(id)
);
"""

CHANGE_LOG_TABLE = """
CREATE TABLE ChangeLog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    table_name TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    change_type TEXT NOT NULL CHECK (change_type IN ('insert', 'update', 'delete')),
    field_name TEXT,
    old_value TEXT,
    new_value TEXT,
    rationale TEXT,
    changed_at TIMESTAMP NOT NULL
);
"""

CHANGE_IMPACT_TABLE = """
CREATE TABLE ChangeImpact (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_log_id INTEGER NOT NULL,
    affected_table TEXT NOT NULL,
    affected_record_id INTEGER NOT NULL,
    impact_description TEXT,
    requires_review BOOLEAN NOT NULL DEFAULT TRUE,
    reviewed BOOLEAN NOT NULL DEFAULT FALSE,
    reviewed_at TIMESTAMP,
    FOREIGN KEY (change_log_id) REFERENCES ChangeLog(id)
);
"""

GENERATION_LOG_TABLE = """
CREATE TABLE GenerationLog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_item_id INTEGER NOT NULL,
    document_type TEXT NOT NULL CHECK (document_type IN (
        'master_prd', 'entity_inventory', 'entity_prd', 'domain_overview',
        'process_document', 'domain_prd', 'yaml_program_files',
        'crm_evaluation_report'
    )),
    file_path TEXT NOT NULL,
    generated_at DATETIME NOT NULL,
    generation_mode TEXT NOT NULL CHECK (generation_mode IN ('final', 'draft')),
    git_commit_hash TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (work_item_id) REFERENCES WorkItem(id)
);
"""

# ---------------------------------------------------------------------------
# Layout Layer (Section 8)
# ---------------------------------------------------------------------------

LAYOUT_PANEL_TABLE = """
CREATE TABLE LayoutPanel (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    tab_break BOOLEAN NOT NULL DEFAULT FALSE,
    tab_label TEXT,
    style TEXT CHECK (style IS NULL OR style IN (
        'default', 'primary', 'success', 'danger', 'warning', 'info'
    )),
    hidden BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL,
    layout_mode TEXT NOT NULL CHECK (layout_mode IN ('rows', 'tabs')),
    dynamic_logic_attribute TEXT,
    dynamic_logic_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_session_id INTEGER,
    FOREIGN KEY (entity_id) REFERENCES Entity(id),
    FOREIGN KEY (created_by_session_id) REFERENCES AISession(id)
);
"""

LAYOUT_ROW_TABLE = """
CREATE TABLE LayoutRow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    panel_id INTEGER NOT NULL,
    sort_order INTEGER NOT NULL,
    cell_1_field_id INTEGER,
    cell_2_field_id INTEGER,
    is_full_width BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (cell_1_field_id IS NOT NULL OR cell_2_field_id IS NOT NULL),
    FOREIGN KEY (panel_id) REFERENCES LayoutPanel(id),
    FOREIGN KEY (cell_1_field_id) REFERENCES Field(id),
    FOREIGN KEY (cell_2_field_id) REFERENCES Field(id)
);
"""

LAYOUT_TAB_TABLE = """
CREATE TABLE LayoutTab (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    panel_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    category TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    FOREIGN KEY (panel_id) REFERENCES LayoutPanel(id)
);
"""

LIST_COLUMN_TABLE = """
CREATE TABLE ListColumn (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL,
    field_id INTEGER NOT NULL,
    width INTEGER,
    sort_order INTEGER NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES Entity(id),
    FOREIGN KEY (field_id) REFERENCES Field(id)
);
"""

# ---------------------------------------------------------------------------
# Table ordering — AISession must be created before tables that reference it
# ---------------------------------------------------------------------------

# Tables must be created in dependency order. AISession references WorkItem,
# and many Requirements-layer tables reference AISession. We create:
# 1. WorkItem and Dependency (no AISession FK)
# 2. AISession (references WorkItem)
# 3. Requirements-layer tables (reference AISession)
# 4. Everything else

ALL_CLIENT_TABLES = [
    # Management layer first — WorkItem has no AISession FK
    WORK_ITEM_TABLE,
    DEPENDENCY_TABLE,
    # Audit layer — AISession references WorkItem
    AI_SESSION_TABLE,
    CHANGE_LOG_TABLE,
    CHANGE_IMPACT_TABLE,
    GENERATION_LOG_TABLE,
    # Requirements layer — many reference AISession
    DOMAIN_TABLE,
    ENTITY_TABLE,
    FIELD_TABLE,
    FIELD_OPTION_TABLE,
    RELATIONSHIP_TABLE,
    PERSONA_TABLE,
    BUSINESS_OBJECT_TABLE,
    PROCESS_TABLE,
    PROCESS_STEP_TABLE,
    REQUIREMENT_TABLE,
    # Cross-reference layer
    PROCESS_ENTITY_TABLE,
    PROCESS_FIELD_TABLE,
    PROCESS_PERSONA_TABLE,
    # Management layer (Decision and OpenIssue reference many tables)
    DECISION_TABLE,
    OPEN_ISSUE_TABLE,
    # Layout layer
    LAYOUT_PANEL_TABLE,
    LAYOUT_ROW_TABLE,
    LAYOUT_TAB_TABLE,
    LIST_COLUMN_TABLE,
]


def get_client_schema_sql() -> list[str]:
    """Return the list of CREATE TABLE statements for a client database."""
    return list(ALL_CLIENT_TABLES)
