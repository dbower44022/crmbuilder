"""Tests for automation.core.create_client — client creation with rollback."""

import sqlite3

from automation.core.create_client import (
    CreateClientParams,
    create_client,
    validate_create_client,
)
from automation.db.migrations import run_master_migrations


def _setup_master(tmp_path):
    """Create and return a master database path."""
    db_path = str(tmp_path / "master.db")
    conn = run_master_migrations(db_path)
    conn.close()
    return db_path


def _make_params(tmp_path, **overrides):
    """Build CreateClientParams with sensible defaults."""
    project_folder = tmp_path / "project"
    project_folder.mkdir(exist_ok=True)
    defaults = {
        "name": "Test Corp",
        "code": "TST",
        "description": "A test client",
        "project_folder": str(project_folder),
    }
    defaults.update(overrides)
    return CreateClientParams(**defaults)


def _dummy_migrations(db_path: str):
    """Minimal migration that creates a schema_version table."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version "
        "(version INTEGER NOT NULL)"
    )
    conn.execute("INSERT INTO schema_version (version) VALUES (1)")
    conn.commit()
    return conn


# -----------------------------------------------------------------------
# Validation tests
# -----------------------------------------------------------------------

class TestValidateCreateClient:

    def test_valid_params(self, tmp_path):
        master = _setup_master(tmp_path)
        params = _make_params(tmp_path)
        errors = validate_create_client(params, master)
        assert errors == []

    def test_empty_name(self, tmp_path):
        master = _setup_master(tmp_path)
        params = _make_params(tmp_path, name="")
        errors = validate_create_client(params, master)
        assert any(e.field == "name" for e in errors)

    def test_whitespace_only_name(self, tmp_path):
        master = _setup_master(tmp_path)
        params = _make_params(tmp_path, name="   ")
        errors = validate_create_client(params, master)
        assert any(e.field == "name" for e in errors)

    def test_empty_code(self, tmp_path):
        master = _setup_master(tmp_path)
        params = _make_params(tmp_path, code="")
        errors = validate_create_client(params, master)
        assert any(e.field == "code" for e in errors)

    def test_invalid_code_lowercase(self, tmp_path):
        master = _setup_master(tmp_path)
        params = _make_params(tmp_path, code="abc")
        errors = validate_create_client(params, master)
        assert any(e.field == "code" for e in errors)

    def test_invalid_code_single_char(self, tmp_path):
        master = _setup_master(tmp_path)
        params = _make_params(tmp_path, code="A")
        errors = validate_create_client(params, master)
        assert any(e.field == "code" for e in errors)

    def test_invalid_code_too_long(self, tmp_path):
        master = _setup_master(tmp_path)
        params = _make_params(tmp_path, code="ABCDEFGHIJK")
        errors = validate_create_client(params, master)
        assert any(e.field == "code" for e in errors)

    def test_invalid_code_starts_with_digit(self, tmp_path):
        master = _setup_master(tmp_path)
        params = _make_params(tmp_path, code="1AB")
        errors = validate_create_client(params, master)
        assert any(e.field == "code" for e in errors)

    def test_duplicate_code(self, tmp_path):
        master = _setup_master(tmp_path)
        project1 = tmp_path / "p1"
        project1.mkdir()
        project2 = tmp_path / "p2"
        project2.mkdir()

        # Insert first client
        conn = sqlite3.connect(master)
        conn.execute(
            "INSERT INTO Client (name, code, project_folder) "
            "VALUES ('Existing', 'TST', ?)",
            (str(project1),),
        )
        conn.commit()
        conn.close()

        params = _make_params(tmp_path, code="TST", project_folder=str(project2))
        errors = validate_create_client(params, master)
        assert any(e.field == "code" and "already in use" in e.message for e in errors)

    def test_empty_project_folder(self, tmp_path):
        master = _setup_master(tmp_path)
        params = _make_params(tmp_path, project_folder="")
        errors = validate_create_client(params, master)
        assert any(e.field == "project_folder" for e in errors)

    def test_relative_project_folder(self, tmp_path):
        master = _setup_master(tmp_path)
        params = _make_params(tmp_path, project_folder="relative/path")
        errors = validate_create_client(params, master)
        assert any(e.field == "project_folder" for e in errors)

    def test_nonexistent_project_folder(self, tmp_path):
        master = _setup_master(tmp_path)
        params = _make_params(tmp_path, project_folder=str(tmp_path / "nope"))
        errors = validate_create_client(params, master)
        assert any(e.field == "project_folder" for e in errors)

    def test_duplicate_project_folder(self, tmp_path):
        master = _setup_master(tmp_path)
        project = tmp_path / "shared"
        project.mkdir()

        conn = sqlite3.connect(master)
        conn.execute(
            "INSERT INTO Client (name, code, project_folder) "
            "VALUES ('First', 'AA', ?)",
            (str(project),),
        )
        conn.commit()
        conn.close()

        params = _make_params(tmp_path, code="BB", project_folder=str(project))
        errors = validate_create_client(params, master)
        assert any(
            e.field == "project_folder" and "already in use" in e.message
            for e in errors
        )


# -----------------------------------------------------------------------
# Happy path
# -----------------------------------------------------------------------

class TestCreateClientHappyPath:

    def test_creates_client(self, tmp_path):
        master = _setup_master(tmp_path)
        params = _make_params(tmp_path)
        result = create_client(params, master, run_migrations=_dummy_migrations)

        assert result.success is True
        assert result.client is not None
        assert result.client.name == "Test Corp"
        assert result.client.code == "TST"
        assert result.client.project_folder == params.project_folder

    def test_creates_crmbuilder_dir(self, tmp_path):
        master = _setup_master(tmp_path)
        params = _make_params(tmp_path)
        create_client(params, master, run_migrations=_dummy_migrations)

        crmbuilder = tmp_path / "project" / ".crmbuilder"
        assert crmbuilder.is_dir()

    def test_creates_db_file(self, tmp_path):
        master = _setup_master(tmp_path)
        params = _make_params(tmp_path)
        create_client(params, master, run_migrations=_dummy_migrations)

        db_file = tmp_path / "project" / ".crmbuilder" / "TST.db"
        assert db_file.is_file()

    def test_creates_standard_subfolders(self, tmp_path):
        master = _setup_master(tmp_path)
        params = _make_params(tmp_path)
        create_client(params, master, run_migrations=_dummy_migrations)

        project = tmp_path / "project"
        for name in ("PRDs", "programs", "reports", "Implementation Docs"):
            assert (project / name).is_dir()

    def test_inserts_master_row(self, tmp_path):
        master = _setup_master(tmp_path)
        params = _make_params(tmp_path)
        create_client(params, master, run_migrations=_dummy_migrations)

        conn = sqlite3.connect(master)
        row = conn.execute("SELECT name, code FROM Client WHERE code = 'TST'").fetchone()
        conn.close()
        assert row == ("Test Corp", "TST")

    def test_preserves_preexisting_subfolders(self, tmp_path):
        """Pre-existing subfolders are not removed if creation succeeds."""
        master = _setup_master(tmp_path)
        project = tmp_path / "project"
        project.mkdir(exist_ok=True)
        (project / "PRDs").mkdir()
        (project / "PRDs" / "existing.md").write_text("keep me")

        params = _make_params(tmp_path, project_folder=str(project))
        result = create_client(params, master, run_migrations=_dummy_migrations)
        assert result.success is True
        assert (project / "PRDs" / "existing.md").read_text() == "keep me"

    def test_preexisting_crmbuilder_dir(self, tmp_path):
        """If .crmbuilder/ already exists, it is reused."""
        master = _setup_master(tmp_path)
        project = tmp_path / "project"
        project.mkdir(exist_ok=True)
        (project / ".crmbuilder").mkdir()

        params = _make_params(tmp_path, project_folder=str(project))
        result = create_client(params, master, run_migrations=_dummy_migrations)
        assert result.success is True


# -----------------------------------------------------------------------
# Rollback tests
# -----------------------------------------------------------------------

class TestCreateClientRollback:

    def test_rollback_on_migration_failure(self, tmp_path):
        """If migrations fail, .crmbuilder/ and DB file are cleaned up."""
        master = _setup_master(tmp_path)

        def failing_migrations(db_path: str):
            # Create the DB file then fail
            conn = sqlite3.connect(db_path)
            conn.close()
            raise RuntimeError("migration boom")

        params = _make_params(tmp_path)
        result = create_client(params, master, run_migrations=failing_migrations)

        assert result.success is False
        assert "migration boom" in result.error

        # Rollback should have cleaned up
        crmbuilder = tmp_path / "project" / ".crmbuilder"
        db_file = crmbuilder / "TST.db"
        assert not db_file.exists()
        # crmbuilder dir was created by this op, so should be removed
        assert not crmbuilder.exists()

    def test_rollback_on_master_insert_failure(self, tmp_path):
        """If master insert fails, subfolders created by this op are removed."""
        master = _setup_master(tmp_path)

        # Pre-insert a conflicting code to force master insert failure
        conn = sqlite3.connect(master)
        project_other = tmp_path / "other"
        project_other.mkdir()
        conn.execute(
            "INSERT INTO Client (name, code, project_folder) "
            "VALUES ('Existing', 'TST', ?)",
            (str(project_other),),
        )
        conn.commit()
        conn.close()

        params = _make_params(tmp_path)
        result = create_client(params, master, run_migrations=_dummy_migrations)

        assert result.success is False
        # Validation should catch the duplicate code
        assert len(result.validation_errors) > 0

    def test_rollback_preserves_preexisting_subfolders(self, tmp_path):
        """Rollback must not remove pre-existing subfolders."""
        master = _setup_master(tmp_path)
        project = tmp_path / "project"
        project.mkdir(exist_ok=True)
        # Pre-create PRDs/ with content
        (project / "PRDs").mkdir()
        (project / "PRDs" / "keep.md").write_text("important")

        def failing_migrations(db_path: str):
            conn = sqlite3.connect(db_path)
            conn.close()
            raise RuntimeError("fail")

        params = _make_params(tmp_path, project_folder=str(project))
        result = create_client(params, master, run_migrations=failing_migrations)

        assert result.success is False
        # PRDs/ was pre-existing — must survive rollback
        assert (project / "PRDs").is_dir()
        assert (project / "PRDs" / "keep.md").exists()

    def test_rollback_preserves_preexisting_crmbuilder_dir(self, tmp_path):
        """Rollback must not remove pre-existing .crmbuilder/."""
        master = _setup_master(tmp_path)
        project = tmp_path / "project"
        project.mkdir(exist_ok=True)
        (project / ".crmbuilder").mkdir()

        def failing_migrations(db_path: str):
            conn = sqlite3.connect(db_path)
            conn.close()
            raise RuntimeError("fail")

        params = _make_params(tmp_path, project_folder=str(project))
        result = create_client(params, master, run_migrations=failing_migrations)

        assert result.success is False
        # .crmbuilder/ was pre-existing — must survive rollback
        assert (project / ".crmbuilder").is_dir()

    def test_validation_errors_prevent_creation(self, tmp_path):
        """If validation fails, no files or DB rows are created."""
        master = _setup_master(tmp_path)
        params = _make_params(tmp_path, code="bad")

        result = create_client(params, master, run_migrations=_dummy_migrations)

        assert result.success is False
        assert len(result.validation_errors) > 0
        assert result.client is None

        # No .crmbuilder/ created
        assert not (tmp_path / "project" / ".crmbuilder").exists()

        # No master row
        conn = sqlite3.connect(master)
        count = conn.execute("SELECT COUNT(*) FROM Client").fetchone()[0]
        conn.close()
        assert count == 0
