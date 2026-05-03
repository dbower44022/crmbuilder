"""Deployment tab data access and view-model logic — pure Python, no Qt.

Provides dataclasses and query functions for all five deployment sidebar
entries: Instances, Deploy, Configure, Verify, Output.  Also provides
phase-status-banner and active-instance-picker logic.

All functions take an open sqlite3.Connection to the per-client database
(except ``load_yaml_files`` which reads the filesystem).
"""

from __future__ import annotations

import dataclasses
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class InstanceRow:
    """One row in the Instances list."""

    id: int
    name: str
    code: str
    environment: str
    url: str | None
    is_default: bool


@dataclasses.dataclass
class InstanceDetail:
    """Full instance record for the detail pane."""

    id: int
    name: str
    code: str
    environment: str
    url: str | None
    username: str | None
    password: str | None
    description: str | None
    is_default: bool
    created_at: str | None
    updated_at: str | None


@dataclasses.dataclass
class DeploymentRunRow:
    """One row in the Deploy history table."""

    id: int
    instance_id: int
    instance_name: str
    scenario: str
    started_at: str
    completed_at: str | None
    outcome: str | None
    log_path: str | None


@dataclasses.dataclass
class YamlFileInfo:
    """One YAML program file for the Configure entry."""

    name: str
    path: str
    last_modified: str
    last_run_outcome: str | None
    version: str | None = None


@dataclasses.dataclass
class PhaseWorkItem:
    """Minimal work item info for the phase status banner."""

    id: int
    item_type: str
    status: str


# ---------------------------------------------------------------------------
# Instances
# ---------------------------------------------------------------------------

def load_instances(conn: sqlite3.Connection) -> list[InstanceRow]:
    """Load all instances for the active client, ordered by name.

    :param conn: Per-client database connection.
    :returns: List of InstanceRow.
    """
    rows = conn.execute(
        "SELECT id, name, code, environment, url, is_default "
        "FROM Instance ORDER BY name"
    ).fetchall()
    return [
        InstanceRow(
            id=r[0], name=r[1], code=r[2], environment=r[3],
            url=r[4], is_default=bool(r[5]),
        )
        for r in rows
    ]


def load_instance_detail(
    conn: sqlite3.Connection, instance_id: int
) -> InstanceDetail | None:
    """Load full detail for a single instance.

    :param conn: Per-client database connection.
    :param instance_id: The instance ID.
    :returns: InstanceDetail or None if not found.
    """
    row = conn.execute(
        "SELECT id, name, code, environment, url, username, password, "
        "description, is_default, created_at, updated_at "
        "FROM Instance WHERE id = ?",
        (instance_id,),
    ).fetchone()
    if row is None:
        return None
    return InstanceDetail(
        id=row[0], name=row[1], code=row[2], environment=row[3],
        url=row[4], username=row[5], password=row[6],
        description=row[7], is_default=bool(row[8]),
        created_at=row[9], updated_at=row[10],
    )


def create_instance(
    conn: sqlite3.Connection,
    *,
    name: str,
    code: str,
    environment: str,
    url: str | None = None,
    username: str | None = None,
    password: str | None = None,
    description: str | None = None,
    is_default: bool = False,
) -> int:
    """Insert a new instance row.

    If ``is_default`` is True, clears the flag from all other rows first.

    :param conn: Per-client database connection.
    :returns: The new row ID.
    """
    now = datetime.now(UTC).isoformat()
    if is_default:
        conn.execute("UPDATE Instance SET is_default = 0 WHERE is_default = 1")
    cursor = conn.execute(
        "INSERT INTO Instance "
        "(name, code, environment, url, username, password, description, "
        "is_default, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (name, code, environment, url, username, password, description,
         1 if is_default else 0, now, now),
    )
    conn.commit()
    return cursor.lastrowid


def update_instance(
    conn: sqlite3.Connection,
    instance_id: int,
    *,
    name: str | None = None,
    url: str | None = ...,
    username: str | None = ...,
    password: str | None = ...,
    description: str | None = ...,
) -> None:
    """Update editable fields on an existing instance.

    Pass the sentinel ``...`` (Ellipsis) to leave a field unchanged.
    Pass ``None`` to set it to NULL.

    :param conn: Per-client database connection.
    :param instance_id: The instance ID.
    """
    updates: list[str] = []
    params: list = []

    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if url is not ...:
        updates.append("url = ?")
        params.append(url)
    if username is not ...:
        updates.append("username = ?")
        params.append(username)
    if password is not ...:
        updates.append("password = ?")
        params.append(password)
    if description is not ...:
        updates.append("description = ?")
        params.append(description)

    if not updates:
        return

    updates.append("updated_at = ?")
    params.append(datetime.now(UTC).isoformat())
    params.append(instance_id)

    conn.execute(
        f"UPDATE Instance SET {', '.join(updates)} WHERE id = ?",
        params,
    )
    conn.commit()


def set_default_instance(
    conn: sqlite3.Connection, instance_id: int
) -> None:
    """Set an instance as the default, clearing others in the same transaction.

    :param conn: Per-client database connection.
    :param instance_id: The instance to make default.
    """
    conn.execute("UPDATE Instance SET is_default = 0 WHERE is_default = 1")
    conn.execute(
        "UPDATE Instance SET is_default = 1, updated_at = ? WHERE id = ?",
        (datetime.now(UTC).isoformat(), instance_id),
    )
    conn.commit()


def delete_instance(
    conn: sqlite3.Connection, instance_id: int
) -> str | None:
    """Delete an instance, checking for referencing deployment runs first.

    :param conn: Per-client database connection.
    :param instance_id: The instance to delete.
    :returns: Error message if deletion is blocked, or None on success.
    """
    run_count = conn.execute(
        "SELECT COUNT(*) FROM DeploymentRun WHERE instance_id = ?",
        (instance_id,),
    ).fetchone()[0]
    if run_count > 0:
        conn.execute(
            "DELETE FROM DeploymentRun WHERE instance_id = ?",
            (instance_id,),
        )

    conn.execute("DELETE FROM Instance WHERE id = ?", (instance_id,))
    conn.commit()
    return None


def get_default_instance_id(conn: sqlite3.Connection) -> int | None:
    """Return the ID of the default instance, or None.

    :param conn: Per-client database connection.
    """
    row = conn.execute(
        "SELECT id FROM Instance WHERE is_default = 1"
    ).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Connection testing
# ---------------------------------------------------------------------------

def test_instance_connection(
    conn: sqlite3.Connection, instance_id: int
) -> tuple[bool, str]:
    """Test connectivity to an EspoCRM instance.

    Builds an InstanceProfile from the DB row and calls
    EspoAdminClient.test_connection().

    :param conn: Per-client database connection.
    :param instance_id: The instance to test.
    :returns: (success, message) tuple.
    """
    detail = load_instance_detail(conn, instance_id)
    if detail is None:
        return False, "Instance not found"
    if not detail.url:
        return False, "No URL configured"
    if not detail.username or not detail.password:
        return False, "Username and password are required"

    from espo_impl.core.api_client import EspoAdminClient
    from espo_impl.core.models import InstanceProfile

    profile = InstanceProfile(
        name=detail.name,
        url=detail.url,
        api_key=detail.username,
        auth_method="basic",
        secret_key=detail.password,
    )
    client = EspoAdminClient(profile, timeout=15)
    return client.test_connection()


# ---------------------------------------------------------------------------
# Deploy history
# ---------------------------------------------------------------------------

def load_deployment_runs(conn: sqlite3.Connection) -> list[DeploymentRunRow]:
    """Load all deployment runs for the active client.

    :param conn: Per-client database connection.
    :returns: List of DeploymentRunRow, most recent first.
    """
    rows = conn.execute(
        "SELECT dr.id, dr.instance_id, i.name, dr.scenario, "
        "dr.started_at, dr.completed_at, dr.outcome, dr.log_path "
        "FROM DeploymentRun dr "
        "JOIN Instance i ON i.id = dr.instance_id "
        "ORDER BY dr.started_at DESC"
    ).fetchall()
    return [
        DeploymentRunRow(
            id=r[0], instance_id=r[1], instance_name=r[2],
            scenario=r[3], started_at=r[4], completed_at=r[5],
            outcome=r[6], log_path=r[7],
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Configure — YAML files
# ---------------------------------------------------------------------------

def load_yaml_files(project_folder: str | None) -> list[YamlFileInfo]:
    """List YAML program files in ``{project_folder}/programs/`` and subdirectories.

    Searches recursively so that domain-organized subdirectories (e.g.
    ``programs/mentor-recruitment/``) are included.  The display name
    shows the path relative to ``programs/``.

    :param project_folder: Client's project folder path.
    :returns: List of YamlFileInfo, sorted by relative path.
    """
    if not project_folder:
        return []
    programs_dir = Path(project_folder) / "programs"
    if not programs_dir.is_dir():
        return []

    results: list[YamlFileInfo] = []
    for pattern in ("*.yaml", "*.yml"):
        for p in programs_dir.rglob(pattern):
            rel = p.relative_to(programs_dir)
            if "archive" in str(rel).lower():
                continue
            stat = p.stat()

            # Read content_version from the YAML front-matter
            version = None
            try:
                import yaml

                raw = yaml.safe_load(p.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    version = str(raw.get("content_version", "")) or None
            except Exception:
                pass

            results.append(YamlFileInfo(
                name=str(rel),
                path=str(p),
                last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(
                    timespec="seconds"
                ),
                last_run_outcome=None,
                version=version,
            ))
    results.sort(key=lambda f: f.name)
    return results


# ---------------------------------------------------------------------------
# Configuration run history
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class ConfigurationRunRecord:
    """Most recent configuration run for a file + instance pair."""

    id: int
    file_name: str
    file_version: str | None
    file_hash: str | None
    operation: str
    outcome: str
    completed_at: str | None


def record_configuration_run(
    conn: sqlite3.Connection,
    *,
    instance_id: int,
    file_name: str,
    file_version: str | None,
    file_hash: str | None,
    operation: str,
    outcome: str,
    error_message: str | None,
    log_output: str | None,
    started_at: str,
    completed_at: str,
) -> int:
    """Insert a ConfigurationRun row.

    :param conn: Per-client database connection.
    :returns: The new row ID.
    """
    cursor = conn.execute(
        "INSERT INTO ConfigurationRun "
        "(instance_id, file_name, file_version, file_hash, operation, "
        "outcome, error_message, log_output, started_at, completed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (instance_id, file_name, file_version, file_hash, operation,
         outcome, error_message, log_output, started_at, completed_at),
    )
    conn.commit()
    return cursor.lastrowid


def load_last_runs(
    conn: sqlite3.Connection, instance_id: int
) -> dict[str, ConfigurationRunRecord]:
    """Load the most recent configuration run per file for an instance.

    :param conn: Per-client database connection.
    :param instance_id: The instance to query.
    :returns: Dict mapping file_name → most recent ConfigurationRunRecord.
    """
    # Check if table exists (handles databases before v5 migration)
    table_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name='ConfigurationRun'"
    ).fetchone()
    if not table_exists:
        return {}

    rows = conn.execute(
        "SELECT cr.id, cr.file_name, cr.file_version, cr.file_hash, "
        "cr.operation, cr.outcome, cr.completed_at "
        "FROM ConfigurationRun cr "
        "INNER JOIN ("
        "  SELECT file_name, MAX(id) AS max_id "
        "  FROM ConfigurationRun "
        "  WHERE instance_id = ? "
        "  GROUP BY file_name"
        ") latest ON cr.id = latest.max_id "
        "ORDER BY cr.file_name",
        (instance_id,),
    ).fetchall()
    result: dict[str, ConfigurationRunRecord] = {}
    for r in rows:
        rec = ConfigurationRunRecord(
            id=r[0], file_name=r[1], file_version=r[2], file_hash=r[3],
            operation=r[4], outcome=r[5], completed_at=r[6],
        )
        result[rec.file_name] = rec
    return result


def load_run_log(
    conn: sqlite3.Connection, run_id: int
) -> tuple[str | None, str | None, str | None]:
    """Load the log output for a specific configuration run.

    :param conn: Per-client database connection.
    :param run_id: The ConfigurationRun.id.
    :returns: (file_name, completed_at, log_output) or (None, None, None).
    """
    row = conn.execute(
        "SELECT file_name, completed_at, log_output "
        "FROM ConfigurationRun WHERE id = ?",
        (run_id,),
    ).fetchone()
    if row is None:
        return None, None, None
    return row[0], row[1], row[2]


# ---------------------------------------------------------------------------
# Phase status banner
# ---------------------------------------------------------------------------

# Map sidebar entry → work item type for the phase status banner.
# Instances and Output do not show the banner.
ENTRY_TO_WORK_ITEM_TYPE: dict[str, str] = {
    "Deploy": "crm_deployment",
    "Configure": "crm_configuration",
    "Run History": "verification",
}


def get_phase_work_item(
    conn: sqlite3.Connection, item_type: str
) -> PhaseWorkItem | None:
    """Load the singleton work item for a deployment phase.

    :param conn: Per-client database connection.
    :param item_type: One of crm_deployment, crm_configuration, verification.
    :returns: PhaseWorkItem or None if not yet created.
    """
    row = conn.execute(
        "SELECT id, item_type, status FROM WorkItem WHERE item_type = ?",
        (item_type,),
    ).fetchone()
    if row is None:
        return None
    return PhaseWorkItem(id=row[0], item_type=row[1], status=row[2])


# ---------------------------------------------------------------------------
# Active-instance picker helpers
# ---------------------------------------------------------------------------

def picker_display_text(instance: InstanceRow) -> str:
    """Format an instance for the picker dropdown.

    :param instance: The instance row.
    :returns: Display string in ``"name (environment)"`` format.
    """
    return f"{instance.name} ({instance.environment})"
