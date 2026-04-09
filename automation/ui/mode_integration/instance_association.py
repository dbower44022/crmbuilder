"""Instance ↔ Client association logic (Section 14.9.3).

Pure Python — no PySide6 imports.

Provides lookup functions to match:
  - A Client record's crm_platform to an InstanceProfile
  - An InstanceProfile's project_folder to a Client record
"""

from __future__ import annotations

from pathlib import Path


def find_instance_for_client(
    crm_platform: str | None,
    instance_profiles: list,
) -> int | None:
    """Find the index of the instance profile matching a client's crm_platform.

    The match strategy: compare crm_platform (lowered) against instance name (lowered).

    :param crm_platform: The Client.crm_platform value.
    :param instance_profiles: List of InstanceProfile objects (from espo_impl).
    :returns: Index into instance_profiles, or None if no match.
    """
    if not crm_platform or not instance_profiles:
        return None

    platform_lower = crm_platform.lower().strip()
    for i, profile in enumerate(instance_profiles):
        if profile.name.lower().strip() == platform_lower:
            return i
    return None


def find_client_for_instance(
    project_folder: str | None,
    clients: list,
) -> int | None:
    """Find the index of the client whose database is in the instance's project folder.

    The match strategy: check if the client's database_path starts with the
    instance's project_folder path.

    :param project_folder: The InstanceProfile.project_folder value.
    :param clients: List of ClientInfo objects (from automation.ui.client_context).
    :returns: Index into clients, or None if no match.
    """
    if not project_folder or not clients:
        return None

    folder = Path(project_folder).resolve()
    for i, client in enumerate(clients):
        if client.database_path:
            db_path = Path(client.database_path).resolve()
            try:
                db_path.relative_to(folder)
                return i
            except ValueError:
                continue
    return None


def get_client_crm_platform(
    master_db_path: str, client_id: int
) -> str | None:
    """Look up the crm_platform value for a client from the master database.

    :param master_db_path: Path to the master database.
    :param client_id: Client ID.
    :returns: crm_platform value, or None.
    """
    try:
        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(master_db_path)
        row = conn.execute(
            "SELECT crm_platform FROM Client WHERE id = ?", (client_id,)
        ).fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None
