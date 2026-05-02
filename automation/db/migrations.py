"""Versioned schema migration runner for CRM Builder Automation databases.

Each database (master and client) has a schema_version table that tracks
which migrations have been applied. The migration runner applies versioned
migrations in order and is idempotent.

Migration sources:
  - _master_v1: Initial Client table (L2 PRD §3.1 original)
  - _master_v2: L2 PRD v1.16 §3.1 — add project_folder, deployment_model,
    last_opened_at to Client; backfill project_folder from database_path
  - _master_v3: Rebuild Client table — relax NOT NULL on database_path
  - _client_v1: Initial 25-table client schema (L2 PRD §4–§8)
  - _client_v2: Add action_required to ChangeImpact (ISS-012)
  - _client_v3: L2 PRD v1.16 §6.5 Instance table, §6.6 DeploymentRun table
"""

import logging
import re
import shutil
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from automation.db.client_schema import (
    CONFIGURATION_RUN_TABLE,
    DEPLOYMENT_RUN_TABLE,
    INSTANCE_DEFAULT_INDEX,
    INSTANCE_DEPLOY_CONFIG_TABLE,
    INSTANCE_TABLE,
    WORK_ITEM_TABLE,
    get_client_schema_sql,
)
from automation.db.client_schema import (
    SCHEMA_VERSION_TABLE as CLIENT_VERSION_TABLE,
)
from automation.db.connection import open_connection
from automation.db.master_schema import (
    CLIENT_TABLE,
    get_master_schema_sql,
)
from automation.db.master_schema import (
    SCHEMA_VERSION_TABLE as MASTER_VERSION_TABLE,
)

logger = logging.getLogger(__name__)

# Type alias for a migration function
Migration = Callable[[sqlite3.Connection], None]


def _get_current_version(conn: sqlite3.Connection) -> int:
    """Return the current schema version, or 0 if no migrations applied."""
    row = conn.execute(
        "SELECT MAX(version) FROM schema_version"
    ).fetchone()
    return row[0] if row[0] is not None else 0


def _apply_migration(
    conn: sqlite3.Connection,
    version: int,
    migrate_fn: Migration,
) -> None:
    """Apply a single migration and record it in schema_version."""
    migrate_fn(conn)
    conn.execute(
        "INSERT INTO schema_version (version) VALUES (?)", (version,)
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Master database migrations
# ---------------------------------------------------------------------------

def _master_v1(conn: sqlite3.Connection) -> None:
    """Initial master database schema — Client table."""
    for stmt in get_master_schema_sql():
        conn.execute(stmt)


def _master_v2(conn: sqlite3.Connection) -> None:
    """L2 PRD v1.16 §3.1 — add project_folder, deployment_model, last_opened_at.

    Idempotent: checks column existence via PRAGMA table_info before each
    ALTER TABLE ADD COLUMN.

    The project_folder column is NOT NULL in the fresh-table definition
    (master_schema.py). For existing databases, SQLite's ALTER TABLE ADD
    COLUMN with NOT NULL requires a default, so we add it as nullable here
    and backfill from database_path. Existing databases will not have the
    NOT NULL constraint on project_folder; fresh databases get it from the
    rewritten CLIENT_TABLE definition. This tradeoff is acceptable because
    the application enforces the constraint in code.
    """
    cols = conn.execute("PRAGMA table_info(Client)").fetchall()
    col_names = {row[1] for row in cols}

    if "project_folder" not in col_names:
        conn.execute("ALTER TABLE Client ADD COLUMN project_folder TEXT")

    if "deployment_model" not in col_names:
        conn.execute("ALTER TABLE Client ADD COLUMN deployment_model TEXT")

    if "last_opened_at" not in col_names:
        conn.execute("ALTER TABLE Client ADD COLUMN last_opened_at TIMESTAMP")

    # Backfill project_folder from database_path for existing rows.
    # Expected pattern: {project_folder}/.crmbuilder/{code}.db
    # We strip the trailing /.crmbuilder/{code}.db segment.
    rows = conn.execute(
        "SELECT id, code, database_path FROM Client "
        "WHERE project_folder IS NULL AND database_path IS NOT NULL"
    ).fetchall()
    pattern = re.compile(r"^(.+)/\.crmbuilder/[A-Z][A-Z0-9]{1,9}\.db$")
    for row_id, code, db_path in rows:
        match = pattern.match(db_path)
        if match:
            conn.execute(
                "UPDATE Client SET project_folder = ? WHERE id = ?",
                (match.group(1), row_id),
            )
        else:
            logger.warning(
                "Client id=%d code=%s: database_path '%s' does not match "
                "expected pattern; leaving project_folder NULL",
                row_id,
                code,
                db_path,
            )


def _master_v3(conn: sqlite3.Connection) -> None:
    """Rebuild Client table to match current master_schema.py definition.

    Relaxes the NOT NULL constraint on database_path that exists in pre-v1.16
    databases. Uses the SQLite 12-step table redefinition pattern because
    ALTER COLUMN is not supported.

    Pre-check: aborts if any Client rows have NULL project_folder, since the
    new table enforces NOT NULL on that column.
    """
    # Pre-check: ensure no rows have NULL project_folder
    bad_rows = conn.execute(
        "SELECT id, code FROM Client WHERE project_folder IS NULL"
    ).fetchall()
    if bad_rows:
        lines = [
            f"  - Client id={row[0]} code={row[1]}" for row in bad_rows
        ]
        raise RuntimeError(
            "Cannot apply master migration v3: the following Client rows have "
            "NULL project_folder and cannot be migrated to the new schema. "
            "Resolve manually before running the migration.\n"
            + "\n".join(lines)
        )

    # Build CREATE TABLE Client_new from the canonical CLIENT_TABLE constant
    create_new = CLIENT_TABLE.replace(
        "CREATE TABLE Client", "CREATE TABLE Client_new", 1
    )

    # Save and disable Python's automatic transaction handling so we can
    # control BEGIN/COMMIT/ROLLBACK explicitly (required because the rebuild
    # mixes DDL and DML, and Python's implicit commit-before-DDL would break
    # atomicity).
    fk_setting = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    orig_isolation = conn.isolation_level
    conn.isolation_level = None

    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN")
        conn.execute(create_new)
        conn.execute(
            "INSERT INTO Client_new "
            "(id, name, code, description, database_path, "
            "organization_overview, project_folder, crm_platform, "
            "deployment_model, last_opened_at, created_at, updated_at) "
            "SELECT id, name, code, description, database_path, "
            "organization_overview, project_folder, crm_platform, "
            "deployment_model, last_opened_at, created_at, updated_at "
            "FROM Client"
        )
        conn.execute("DROP TABLE Client")
        conn.execute("ALTER TABLE Client_new RENAME TO Client")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        conn.execute("DROP TABLE IF EXISTS Client_new")
        raise
    finally:
        conn.execute(f"PRAGMA foreign_keys = {'ON' if fk_setting else 'OFF'}")
        conn.isolation_level = orig_isolation


MASTER_MIGRATIONS: list[tuple[int, Migration]] = [
    (1, _master_v1),
    (2, _master_v2),
    (3, _master_v3),
]


def _heal_null_project_folders(
    conn: sqlite3.Connection,
    overrides: dict[str, str] | None,
) -> int:
    """Repair Client rows that have NULL project_folder before v3 runs.

    Applies overrides from the caller (keyed by Client.code), then
    returns the number of rows healed. Rows that cannot be repaired are
    left alone — v3's own pre-check will abort with a clear error.

    :param conn: Open connection to the master database.
    :param overrides: Mapping of client code → project_folder path.
    :returns: Number of rows updated.
    """
    if not overrides:
        return 0

    rows = conn.execute(
        "SELECT id, code FROM Client WHERE project_folder IS NULL"
    ).fetchall()

    healed = 0
    for row_id, code in rows:
        folder = overrides.get(code)
        if folder:
            conn.execute(
                "UPDATE Client SET project_folder = ? WHERE id = ?",
                (folder, row_id),
            )
            healed += 1
            logger.info(
                "Healed Client id=%d code=%s: set project_folder=%s",
                row_id,
                code,
                folder,
            )
        else:
            logger.warning(
                "Client id=%d code=%s has NULL project_folder and no "
                "override supplied; leaving unhealed",
                row_id,
                code,
            )

    # Warn about override keys that don't match any NULL-project_folder row
    null_codes = {code for _, code in rows}
    for code in overrides:
        if code not in null_codes:
            logger.warning(
                "Override for code=%s does not match any Client row with "
                "NULL project_folder; ignoring",
                code,
            )

    if healed:
        conn.commit()
    return healed


def _backup_master_db(db_path: str) -> str | None:
    """Create a timestamped backup of the master database.

    :param db_path: Path to the master database.
    :returns: Path to the backup file, or None if backup failed.
    """
    src = Path(db_path)
    if not src.exists():
        return None
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = src.parent / f"{src.stem}.db.pre-v3-heal-{ts}"
    try:
        shutil.copy2(str(src), str(backup_path))
        logger.info("Master database backed up to %s", backup_path)
        return str(backup_path)
    except OSError as exc:
        logger.error("Failed to back up master database: %s", exc)
        raise


def run_master_migrations(
    db_path: str,
    *,
    project_folder_overrides: dict[str, str] | None = None,
) -> sqlite3.Connection:
    """Open the master database and apply any pending migrations.

    Creates the schema_version table if it does not exist. Returns the
    open connection so callers can use it immediately.

    Before applying migrations, runs a heal step that repairs Client rows
    with NULL project_folder using the provided overrides. A backup of
    the database is created before any heal modifications.

    :param db_path: Path to the master database file.
    :param project_folder_overrides: Optional mapping of client code to
        project folder path for healing NULL project_folder values.
    :returns: An open sqlite3.Connection with all migrations applied.
    """
    conn = open_connection(db_path)
    conn.execute(MASTER_VERSION_TABLE)
    conn.commit()
    current = _get_current_version(conn)

    # Heal step: fix NULL project_folder rows before v3 runs
    if current < 3 and project_folder_overrides:
        # Check if there are rows that need healing
        bad_rows = conn.execute(
            "SELECT 1 FROM Client WHERE project_folder IS NULL"
        ).fetchone()
        if bad_rows:
            _backup_master_db(db_path)
            _heal_null_project_folders(conn, project_folder_overrides)

    for version, migrate_fn in MASTER_MIGRATIONS:
        if version > current:
            _apply_migration(conn, version, migrate_fn)
    return conn


# ---------------------------------------------------------------------------
# Client database migrations
# ---------------------------------------------------------------------------

def _client_v1(conn: sqlite3.Connection) -> None:
    """Initial client database schema — all 25 tables."""
    for stmt in get_client_schema_sql():
        conn.execute(stmt)


def _client_v2(conn: sqlite3.Connection) -> None:
    """Add action_required column to ChangeImpact (ISS-012).

    Deferred from Step 13 because Step 9 schema was locked.
    Step 15 needs this column for implementor review actions
    per L2 PRD Section 14.6.2.

    Idempotent: skips ALTER if the column already exists.
    """
    cols = conn.execute("PRAGMA table_info(ChangeImpact)").fetchall()
    col_names = {row[1] for row in cols}
    if "action_required" not in col_names:
        conn.execute(
            "ALTER TABLE ChangeImpact "
            "ADD COLUMN action_required INTEGER NOT NULL DEFAULT 0"
        )


def _client_v3(conn: sqlite3.Connection) -> None:
    """L2 PRD v1.16 §6.5 Instance table, §6.6 DeploymentRun table.

    Uses CREATE TABLE IF NOT EXISTS / CREATE UNIQUE INDEX IF NOT EXISTS
    for idempotency.
    """
    conn.execute(INSTANCE_TABLE.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS "))
    conn.execute(INSTANCE_DEFAULT_INDEX)
    conn.execute(
        DEPLOYMENT_RUN_TABLE.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ")
    )


def _client_v4(conn: sqlite3.Connection) -> None:
    """Add identifier column to Domain for MST-DOM-NNN style identifiers.

    Idempotent: skips ALTER if the column already exists.
    Guard: skips if Domain table does not exist (pre-v1 databases).
    """
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if "Domain" not in tables:
        return
    cols = conn.execute("PRAGMA table_info(Domain)").fetchall()
    col_names = {row[1] for row in cols}
    if "identifier" not in col_names:
        conn.execute("ALTER TABLE Domain ADD COLUMN identifier TEXT")


def _client_v5(conn: sqlite3.Connection) -> None:
    """ConfigurationRun table — audit trail for YAML configuration runs.

    Tracks each time a YAML file is run/checked against an instance,
    including the file version and content hash for change detection.
    """
    conn.execute(
        CONFIGURATION_RUN_TABLE.replace(
            "CREATE TABLE ", "CREATE TABLE IF NOT EXISTS "
        )
    )


def _client_v6(conn: sqlite3.Connection) -> None:
    """Add log_output column to ConfigurationRun for stored run output."""
    cols = conn.execute("PRAGMA table_info(ConfigurationRun)").fetchall()
    col_names = {row[1] for row in cols}
    if "log_output" not in col_names:
        conn.execute(
            "ALTER TABLE ConfigurationRun ADD COLUMN log_output TEXT"
        )


def _client_v7(conn: sqlite3.Connection) -> None:
    """Rebuild ConfigurationRun to allow 'audit' in operation CHECK constraint.

    SQLite cannot ALTER CHECK constraints, so the table is rebuilt using
    the 12-step redefinition pattern.
    """
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if "ConfigurationRun" not in tables:
        # Table doesn't exist yet; v5 will create it with the updated CHECK
        return

    create_new = CONFIGURATION_RUN_TABLE.replace(
        "CREATE TABLE ConfigurationRun",
        "CREATE TABLE ConfigurationRun_new",
        1,
    )

    fk_setting = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    orig_isolation = conn.isolation_level
    conn.isolation_level = None

    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN")
        conn.execute(create_new)
        conn.execute(
            "INSERT INTO ConfigurationRun_new "
            "(id, instance_id, file_name, file_version, file_hash, "
            "operation, outcome, error_message, log_output, "
            "started_at, completed_at, created_at) "
            "SELECT id, instance_id, file_name, file_version, file_hash, "
            "operation, outcome, error_message, log_output, "
            "started_at, completed_at, created_at "
            "FROM ConfigurationRun"
        )
        conn.execute("DROP TABLE ConfigurationRun")
        conn.execute(
            "ALTER TABLE ConfigurationRun_new RENAME TO ConfigurationRun"
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        conn.execute("DROP TABLE IF EXISTS ConfigurationRun_new")
        raise
    finally:
        conn.execute(f"PRAGMA foreign_keys = {'ON' if fk_setting else 'OFF'}")
        conn.isolation_level = orig_isolation


def _client_v8(conn: sqlite3.Connection) -> None:
    """Rebuild WorkItem to allow 'user_process_guide' in item_type CHECK
    constraint, then backfill user_process_guide work items for every
    existing Process row.

    SQLite cannot ALTER CHECK constraints, so the table is rebuilt using
    the 12-step redefinition pattern. Skips entirely if the WorkItem
    table does not yet exist (a fresh database created via _client_v1
    already has the new constraint).
    """
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if "WorkItem" not in tables:
        return

    # If the existing WorkItem table already permits user_process_guide
    # (e.g. a database created from the new schema after this migration's
    # introduction), skip the rebuild — only backfill missing rows.
    schema_row = conn.execute(
        "SELECT sql FROM sqlite_master "
        "WHERE type = 'table' AND name = 'WorkItem'"
    ).fetchone()
    needs_rebuild = bool(schema_row) and "user_process_guide" not in (schema_row[0] or "")

    if needs_rebuild:
        create_new = WORK_ITEM_TABLE.replace(
            "CREATE TABLE WorkItem",
            "CREATE TABLE WorkItem_new",
            1,
        )

        fk_setting = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        orig_isolation = conn.isolation_level
        conn.isolation_level = None

        try:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("BEGIN")
            conn.execute(create_new)
            conn.execute(
                "INSERT INTO WorkItem_new "
                "(id, item_type, domain_id, entity_id, process_id, status, "
                "blocked_reason, status_before_blocked, started_at, "
                "completed_at, created_at, updated_at) "
                "SELECT id, item_type, domain_id, entity_id, process_id, "
                "status, blocked_reason, status_before_blocked, started_at, "
                "completed_at, created_at, updated_at FROM WorkItem"
            )
            conn.execute("DROP TABLE WorkItem")
            conn.execute("ALTER TABLE WorkItem_new RENAME TO WorkItem")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            conn.execute("DROP TABLE IF EXISTS WorkItem_new")
            raise
        finally:
            conn.execute(
                f"PRAGMA foreign_keys = {'ON' if fk_setting else 'OFF'}"
            )
            conn.isolation_level = orig_isolation

    # Backfill user_process_guide work items for every process_definition
    # that does not yet have a sibling guide. Lazy import to avoid circular
    # imports at module load time.
    from automation.workflow.graph import backfill_user_process_guides
    backfill_user_process_guides(conn)


def _client_v9(conn: sqlite3.Connection) -> None:
    """Add InstanceDeployConfig table for post-deploy server operations.

    Stores SSH connection details and the server-side credentials
    needed for Upgrade EspoCRM, Recovery & Reset, and future
    maintenance features. One-to-one with Instance via UNIQUE
    instance_id; ON DELETE CASCADE.

    Idempotent via CREATE TABLE IF NOT EXISTS. Skips silently if the
    Instance table does not yet exist (a fresh database created via
    _client_v1 already includes both tables).

    See PRDs/product/features/feat-server-management.md.
    """
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if "Instance" not in tables:
        return
    conn.execute(
        INSTANCE_DEPLOY_CONFIG_TABLE.replace(
            "CREATE TABLE ", "CREATE TABLE IF NOT EXISTS "
        )
    )


def _client_v10(conn: sqlite3.Connection) -> None:
    """Add Deployment Record administrator-input columns to InstanceDeployConfig.

    Four columns capture values supplied via the wizard's Documentation
    Inputs page (Prompt B of the deployment-record series). Idempotent
    via PRAGMA table_info checks. Skips silently if the
    InstanceDeployConfig table does not yet exist (a fresh database
    created via _client_v1 already includes the new columns).

    See PRDs/_archive/CLAUDE-CODE-PROMPT-deployment-record-B-wizard-integration.md.
    """
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if "InstanceDeployConfig" not in tables:
        return
    cols = conn.execute(
        "PRAGMA table_info(InstanceDeployConfig)"
    ).fetchall()
    col_names = {row[1] for row in cols}
    new_columns = [
        ("domain_registrar", "TEXT"),
        ("dns_provider", "TEXT"),
        ("droplet_id", "TEXT"),
        ("backups_enabled", "INTEGER"),
    ]
    for name, decl in new_columns:
        if name not in col_names:
            conn.execute(
                f"ALTER TABLE InstanceDeployConfig ADD COLUMN {name} {decl}"
            )


def _client_v11(conn: sqlite3.Connection) -> None:
    """Persist Proton Pass entry names on InstanceDeployConfig.

    Three nullable TEXT columns hold the Documentation Inputs that the
    regeneration dialog (Prompt C) and wizard Documentation Inputs page
    (Prompt B) collect today but discard after rendering. Persisting
    them lets the next regeneration of the same instance pre-fill the
    operator's actual entry names instead of templated guesses.

    Idempotent via PRAGMA table_info checks. Skips silently if the
    InstanceDeployConfig table does not yet exist (a fresh database
    created via _client_v1 already includes the new columns).

    See PRDs/product/crmbuilder-automation-PRD/CLAUDE-CODE-PROMPT-deployment-record-I-persistence-papercuts.md.
    """
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if "InstanceDeployConfig" not in tables:
        return
    cols = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(InstanceDeployConfig)"
        ).fetchall()
    }
    for col in (
        "proton_pass_admin_entry",
        "proton_pass_db_root_entry",
        "proton_pass_hosting_entry",
    ):
        if col not in cols:
            conn.execute(
                f"ALTER TABLE InstanceDeployConfig ADD COLUMN {col} TEXT"
            )


def _client_v12(conn: sqlite3.Connection) -> None:
    """Add ``last_record_version`` to InstanceDeployConfig.

    Holds the document_version most recently rendered to the canonical
    Deployment Record .docx for this instance. The regeneration flow
    reads it to compute the next document_version (minor-bump) and
    writes it back after a successful overwrite. Nullable; defaults to
    NULL for existing rows so the first regeneration falls back to
    "1.0".

    Idempotent via PRAGMA table_info checks. Skips silently if the
    InstanceDeployConfig table does not yet exist.
    """
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if "InstanceDeployConfig" not in tables:
        return
    cols = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(InstanceDeployConfig)"
        ).fetchall()
    }
    if "last_record_version" not in cols:
        conn.execute(
            "ALTER TABLE InstanceDeployConfig "
            "ADD COLUMN last_record_version TEXT"
        )


CLIENT_MIGRATIONS: list[tuple[int, Migration]] = [
    (1, _client_v1),
    (2, _client_v2),
    (3, _client_v3),
    (4, _client_v4),
    (5, _client_v5),
    (6, _client_v6),
    (7, _client_v7),
    (8, _client_v8),
    (9, _client_v9),
    (10, _client_v10),
    (11, _client_v11),
    (12, _client_v12),
]


def run_client_migrations(db_path: str) -> sqlite3.Connection:
    """Open a client database and apply any pending migrations.

    Creates the schema_version table if it does not exist. Returns the
    open connection so callers can use it immediately.

    :param db_path: Path to the client database file.
    :returns: An open sqlite3.Connection with all migrations applied.
    """
    conn = open_connection(db_path)
    conn.execute(CLIENT_VERSION_TABLE)
    conn.commit()
    current = _get_current_version(conn)
    for version, migrate_fn in CLIENT_MIGRATIONS:
        if version > current:
            _apply_migration(conn, version, migrate_fn)
    return conn
