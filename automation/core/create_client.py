"""Client creation logic with rollback (pure Python, no Qt).

Implements the five-step creation sequence from L2 PRD v1.16 §14.11.3
with tracked rollback so only artifacts created by *this* operation are
removed on failure.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from automation.core.active_client_state import Client

logger = logging.getLogger(__name__)

CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")

STANDARD_SUBFOLDERS = ("PRDs", "programs", "reports", "Implementation Docs")


@dataclass
class CreateClientParams:
    """Input parameters for client creation.

    :param name: Client display name (required).
    :param code: Short code matching ``^[A-Z][A-Z0-9]{1,9}$`` (required).
    :param description: Optional description.
    :param project_folder: Absolute path to the project folder (required).
    """

    name: str
    code: str
    description: str | None
    project_folder: str


@dataclass
class ValidationError:
    """A single field-level validation error.

    :param field: Field name (``"name"``, ``"code"``, ``"project_folder"``).
    :param message: Human-readable error message.
    """

    field: str
    message: str


@dataclass
class CreateClientResult:
    """Result of a client creation attempt.

    :param success: True if the client was created.
    :param client: The created :class:`Client`, or None on failure.
    :param error: Error message on failure.
    :param validation_errors: Field-level validation errors.
    """

    success: bool
    client: Client | None = None
    error: str | None = None
    validation_errors: list[ValidationError] = field(default_factory=list)


def validate_create_client(
    params: CreateClientParams,
    master_db_path: str,
) -> list[ValidationError]:
    """Validate Create Client form fields.

    :param params: The form field values.
    :param master_db_path: Path to the master database.
    :returns: List of validation errors (empty if valid).
    """
    errors: list[ValidationError] = []

    if not params.name or not params.name.strip():
        errors.append(ValidationError("name", "Name is required."))

    if not params.code:
        errors.append(ValidationError("code", "Code is required."))
    elif not CODE_PATTERN.match(params.code):
        errors.append(ValidationError(
            "code",
            "Code must be 2-10 characters: uppercase letter followed by "
            "uppercase letters or digits.",
        ))
    else:
        try:
            conn = sqlite3.connect(master_db_path)
            try:
                row = conn.execute(
                    "SELECT 1 FROM Client WHERE code = ?", (params.code,)
                ).fetchone()
                if row:
                    errors.append(ValidationError(
                        "code", f"Code '{params.code}' is already in use."
                    ))
            finally:
                conn.close()
        except sqlite3.Error:
            pass  # If DB is inaccessible, skip uniqueness check

    if not params.project_folder:
        errors.append(ValidationError(
            "project_folder", "Project Folder is required."
        ))
    elif not Path(params.project_folder).is_absolute():
        errors.append(ValidationError(
            "project_folder", "Project Folder must be an absolute path."
        ))
    elif not Path(params.project_folder).is_dir():
        errors.append(ValidationError(
            "project_folder", "Project Folder does not exist on disk."
        ))
    else:
        try:
            conn = sqlite3.connect(master_db_path)
            try:
                row = conn.execute(
                    "SELECT 1 FROM Client WHERE project_folder = ?",
                    (params.project_folder,),
                ).fetchone()
                if row:
                    errors.append(ValidationError(
                        "project_folder",
                        "This project folder is already in use by another client.",
                    ))
            finally:
                conn.close()
        except sqlite3.Error:
            pass

    return errors


def create_client(
    params: CreateClientParams,
    master_db_path: str,
    run_migrations: Callable[[str], sqlite3.Connection] | None = None,
) -> CreateClientResult:
    """Execute the five-step client creation sequence with rollback.

    Steps (§14.11.3):

    1. Create ``{project_folder}/.crmbuilder/`` if it does not exist.
    2. Create the SQLite database file.
    3. Run schema migrations.
    4. Create standard subfolders.
    5. Insert the master database row.

    On failure, only artifacts created by *this* operation are removed.

    :param params: Creation parameters.
    :param master_db_path: Path to the master database.
    :param run_migrations: Callable that takes a db path string and returns
        an open connection.  Defaults to
        ``automation.db.migrations.run_client_migrations``.
    :returns: A :class:`CreateClientResult`.
    """
    if run_migrations is None:
        from automation.db.migrations import run_client_migrations
        run_migrations = run_client_migrations

    # Validate first
    errors = validate_create_client(params, master_db_path)
    if errors:
        return CreateClientResult(
            success=False,
            validation_errors=errors,
        )

    # Rollback tracking
    created_crmbuilder_dir = False
    created_db_file = False
    created_subfolders: list[Path] = []
    client_conn: sqlite3.Connection | None = None

    folder = Path(params.project_folder)
    crmbuilder_dir = folder / ".crmbuilder"
    db_path = crmbuilder_dir / f"{params.code}.db"

    try:
        # Step 1: Create .crmbuilder/ directory
        if not crmbuilder_dir.exists():
            crmbuilder_dir.mkdir(parents=True)
            created_crmbuilder_dir = True

        # Step 2 & 3: Create and initialize database
        # Track whether DB existed before so rollback knows what to clean up.
        # Must be set before run_migrations in case it raises.
        if not db_path.exists():
            created_db_file = True
        client_conn = run_migrations(str(db_path))
        client_conn.close()
        client_conn = None

        # Step 4: Create standard subfolders
        for subfolder_name in STANDARD_SUBFOLDERS:
            subfolder = folder / subfolder_name
            if not subfolder.exists():
                subfolder.mkdir(parents=True)
                created_subfolders.append(subfolder)

        # Step 5: Insert master database row
        master_conn = sqlite3.connect(master_db_path)
        try:
            master_conn.execute(
                "INSERT INTO Client (name, code, description, project_folder) "
                "VALUES (?, ?, ?, ?)",
                (params.name.strip(), params.code, params.description, params.project_folder),
            )
            master_conn.commit()
            row = master_conn.execute(
                "SELECT id, name, code, description, project_folder, "
                "crm_platform, deployment_model, last_opened_at, "
                "created_at, updated_at "
                "FROM Client WHERE code = ?",
                (params.code,),
            ).fetchone()
        finally:
            master_conn.close()

        if not row:
            raise RuntimeError("Master row insert succeeded but row not found")

        client = Client(
            id=row[0],
            name=row[1],
            code=row[2],
            description=row[3],
            project_folder=row[4],
            crm_platform=row[5],
            deployment_model=row[6],
            last_opened_at=row[7],
            created_at=row[8],
            updated_at=row[9],
        )

        return CreateClientResult(success=True, client=client)

    except Exception as exc:
        # Rollback: undo only what this operation created
        if client_conn:
            try:
                client_conn.close()
            except Exception:
                pass

        for subfolder in reversed(created_subfolders):
            try:
                subfolder.rmdir()
            except OSError:
                pass  # Directory not empty or already gone

        if created_db_file and db_path.exists():
            try:
                db_path.unlink()
            except OSError:
                pass

        if created_crmbuilder_dir and crmbuilder_dir.exists():
            try:
                crmbuilder_dir.rmdir()
            except OSError:
                pass  # Directory not empty

        return CreateClientResult(
            success=False,
            error=f"Client creation failed: {exc}",
        )
