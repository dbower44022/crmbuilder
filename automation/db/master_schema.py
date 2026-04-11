"""Master database schema for CRM Builder Automation.

The master database contains a single Client table that tracks each client
implementation managed by CRM Builder. Schema defined in L2 PRD v1.16
Section 3.1.
"""

MASTER_SCHEMA_VERSION = 3

SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

# L2 PRD v1.16 §3.1 — Client table.
#
# The database_path column is retained for backward compatibility with
# existing rows created before v1.16 but is deprecated and unused by new
# code. The client database path is now derived at runtime as:
#   {project_folder}/.crmbuilder/{code}.db
#
# The crm_platform CHECK constraint enumerates the platforms listed in
# §14.12.6. For existing databases, this CHECK cannot be retrofitted via
# ALTER TABLE (SQLite limitation); the application enforces the constraint
# in code until a future full-table rebuild.
CLIENT_TABLE = """
CREATE TABLE Client (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE
        CHECK (
            length(code) >= 2 AND length(code) <= 10
            AND substr(code, 1, 1) GLOB '[A-Z]'
            AND code NOT GLOB '*[^A-Z0-9]*'
        ),
    description TEXT,
    database_path TEXT,
    organization_overview TEXT,
    project_folder TEXT NOT NULL UNIQUE,
    crm_platform TEXT CHECK (crm_platform IS NULL OR crm_platform IN ('EspoCRM')),
    deployment_model TEXT CHECK (
        deployment_model IS NULL
        OR deployment_model IN ('self_hosted', 'cloud_hosted', 'bring_your_own')
    ),
    last_opened_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

ALL_MASTER_TABLES = [CLIENT_TABLE]


def get_master_schema_sql() -> list[str]:
    """Return the list of CREATE TABLE statements for the master database."""
    return list(ALL_MASTER_TABLES)
