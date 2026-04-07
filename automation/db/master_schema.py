"""Master database schema for CRM Builder Automation.

The master database contains a single Client table that tracks each client
implementation managed by CRM Builder. Schema defined in L2 PRD Section 3,
with additional columns from Section 10.10.
"""

MASTER_SCHEMA_VERSION = 1

SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

CLIENT_TABLE = """
CREATE TABLE Client (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    description TEXT,
    database_path TEXT NOT NULL,
    organization_overview TEXT,
    crm_platform TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

ALL_MASTER_TABLES = [CLIENT_TABLE]


def get_master_schema_sql() -> list[str]:
    """Return the list of CREATE TABLE statements for the master database."""
    return list(ALL_MASTER_TABLES)
