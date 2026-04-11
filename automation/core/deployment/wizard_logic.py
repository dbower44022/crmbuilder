"""Deploy Wizard business logic — Qt-free, unit-testable.

Handles scenario pre-selection from Client columns, existing-instance
matching, and DeploymentRun lifecycle (insert on start, update on finish).

L2 PRD v1.16 §14.12.5, §6.5, §6.6.
"""

from __future__ import annotations

import dataclasses
import sqlite3
from datetime import UTC, datetime

# Supported CRM platforms (v1: EspoCRM only; structured for future expansion)
SUPPORTED_PLATFORMS: list[str] = ["EspoCRM"]

# Valid deployment scenarios (must match Client.deployment_model CHECK constraint)
SCENARIOS: list[str] = ["self_hosted", "cloud_hosted", "bring_your_own"]

SCENARIO_LABELS: dict[str, str] = {
    "self_hosted": "Self-Hosted",
    "cloud_hosted": "Cloud-Hosted",
    "bring_your_own": "Bring Your Own",
}


@dataclasses.dataclass
class PreSelection:
    """Pre-selection state derived from Client columns.

    :param platform: Pre-selected platform or None.
    :param scenario: Pre-selected scenario or None.
    """

    platform: str | None
    scenario: str | None


@dataclasses.dataclass
class MatchingInstance:
    """An existing Instance row matching the wizard's target."""

    id: int
    name: str
    code: str
    environment: str
    url: str | None


def get_pre_selection(master_db_path: str, client_id: int) -> PreSelection:
    """Read Client.crm_platform and Client.deployment_model for pre-selection.

    :param master_db_path: Path to the master database.
    :param client_id: The active client's ID.
    :returns: PreSelection (both fields may be None).
    """
    try:
        conn = sqlite3.connect(master_db_path)
        try:
            row = conn.execute(
                "SELECT crm_platform, deployment_model FROM Client WHERE id = ?",
                (client_id,),
            ).fetchone()
        finally:
            conn.close()
        if row:
            return PreSelection(platform=row[0], scenario=row[1])
    except Exception:
        pass
    return PreSelection(platform=None, scenario=None)


def find_matching_instances(
    conn: sqlite3.Connection,
) -> list[MatchingInstance]:
    """Find existing instances that could be updated by the wizard.

    Returns all instances for the active client (the wizard's
    existing-instance matching per §14.12.5).

    :param conn: Per-client database connection.
    :returns: List of matching instances.
    """
    rows = conn.execute(
        "SELECT id, name, code, environment, url FROM Instance ORDER BY name"
    ).fetchall()
    return [
        MatchingInstance(id=r[0], name=r[1], code=r[2], environment=r[3], url=r[4])
        for r in rows
    ]


def insert_deployment_run(
    conn: sqlite3.Connection,
    *,
    instance_id: int | None,
    scenario: str,
    crm_platform: str,
) -> int:
    """Insert a DeploymentRun row at wizard start.

    :param conn: Per-client database connection.
    :param instance_id: Instance being updated (or None if creating new).
    :param scenario: The deployment scenario.
    :param crm_platform: The CRM platform.
    :returns: The new DeploymentRun row ID.
    """
    now = datetime.now(UTC).isoformat()
    # instance_id is NOT NULL in the schema, so we need a valid ID.
    # If creating a new instance, the caller must create the Instance row first.
    cursor = conn.execute(
        "INSERT INTO DeploymentRun "
        "(instance_id, scenario, crm_platform, started_at, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (instance_id, scenario, crm_platform, now, now, now),
    )
    conn.commit()
    return cursor.lastrowid


def finalize_deployment_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    outcome: str,
    failure_reason: str | None = None,
    log_path: str | None = None,
) -> None:
    """Update a DeploymentRun row when the wizard terminates.

    :param conn: Per-client database connection.
    :param run_id: The DeploymentRun row ID.
    :param outcome: One of 'success', 'failure', 'cancelled'.
    :param failure_reason: Error description (on failure).
    :param log_path: Path to the log file (optional).
    """
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "UPDATE DeploymentRun SET completed_at = ?, outcome = ?, "
        "failure_reason = ?, log_path = ?, updated_at = ? WHERE id = ?",
        (now, outcome, failure_reason, log_path, now, run_id),
    )
    conn.commit()


def create_wizard_instance(
    conn: sqlite3.Connection,
    *,
    name: str,
    code: str,
    environment: str,
    url: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> int:
    """Create a new Instance row from the wizard.

    :param conn: Per-client database connection.
    :returns: The new Instance row ID.
    """
    now = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        "INSERT INTO Instance "
        "(name, code, environment, url, username, password, is_default, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)",
        (name, code, environment, url, username, password, now, now),
    )
    conn.commit()
    return cursor.lastrowid


def update_instance_from_wizard(
    conn: sqlite3.Connection,
    instance_id: int,
    *,
    url: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> None:
    """Update an Instance row with wizard results.

    :param conn: Per-client database connection.
    :param instance_id: The Instance row ID.
    """
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "UPDATE Instance SET url = ?, username = ?, password = ?, "
        "updated_at = ? WHERE id = ?",
        (url, username, password, now, instance_id),
    )
    conn.commit()
