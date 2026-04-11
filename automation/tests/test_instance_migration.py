"""Tests for legacy JSON instance migration (ISS-017).

Covers: empty directory, single file happy path, multiple files into one
client, multiple files across multiple clients, code collision handling,
environment inference, is_default assignment, idempotent re-run,
unresolvable-client skip with warning, already-migrated skip, and
``.migrated`` rename.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from automation.db.migrations import run_client_migrations, run_master_migrations
from automation.migrations.instance_json_migration import (
    _derive_code,
    _infer_environment,
    run_migration,
)


def _setup_master(tmp_path: Path) -> str:
    """Create a master database with one client.

    :returns: Path to the master database.
    """
    master_path = str(tmp_path / "master.db")
    conn = run_master_migrations(master_path)
    conn.execute(
        "INSERT INTO Client (name, code, database_path, project_folder) "
        "VALUES (?, ?, ?, ?)",
        (
            "Test Client",
            "TC",
            str(tmp_path / "client.db"),
            str(tmp_path / "project"),
        ),
    )
    conn.commit()
    conn.close()
    return master_path


def _setup_client_db(tmp_path: Path) -> str:
    """Create a client database with Instance table.

    :returns: Path to the client database.
    """
    db_path = str(tmp_path / "client.db")
    conn = run_client_migrations(db_path)
    conn.close()
    return db_path


def _write_json(instances_dir: Path, name: str, data: dict) -> Path:
    """Write a legacy JSON instance file.

    :returns: Path to the created file.
    """
    instances_dir.mkdir(parents=True, exist_ok=True)
    path = instances_dir / f"{name}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _get_instances(db_path: str) -> list[dict]:
    """Read all rows from the Instance table."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT name, code, environment, url, username, password, "
        "is_default FROM Instance ORDER BY id"
    ).fetchall()
    conn.close()
    return [
        {
            "name": r[0],
            "code": r[1],
            "environment": r[2],
            "url": r[3],
            "username": r[4],
            "password": r[5],
            "is_default": bool(r[6]),
        }
        for r in rows
    ]


class TestDeriveCode:
    """Tests for _derive_code helper."""

    def test_basic_name(self):
        assert _derive_code("TestApp", set()) == "TESTAPP"

    def test_strips_non_alnum(self):
        assert _derive_code("my_test-app", set()) == "MYTESTAPP"

    def test_truncates_to_10(self):
        code = _derive_code("VeryLongInstanceName", set())
        assert len(code) <= 10
        assert code == "VERYLONGIN"

    def test_collision_appends_suffix(self):
        existing = {"TESTAPP"}
        code = _derive_code("TestApp", existing)
        assert code == "TESTAPP2"
        assert code not in existing

    def test_multiple_collisions(self):
        existing = {"TESTAPP", "TESTAPP2", "TESTAPP3"}
        code = _derive_code("TestApp", existing)
        assert code == "TESTAPP4"

    def test_short_name_padded(self):
        code = _derive_code("A", set())
        assert len(code) >= 2
        assert code[0].isalpha()

    def test_numeric_start_gets_prefix(self):
        code = _derive_code("123", set())
        assert code[0].isalpha()


class TestInferEnvironment:
    """Tests for _infer_environment helper."""

    def test_defaults_to_production(self):
        assert _infer_environment("My CRM") == "production"

    def test_detects_test(self):
        assert _infer_environment("CBM Test Instance") == "test"

    def test_detects_staging(self):
        assert _infer_environment("App Staging") == "staging"

    def test_detects_dev(self):
        assert _infer_environment("Dev Server") == "test"

    def test_case_insensitive(self):
        assert _infer_environment("CBM_TEST") == "test"


class TestRunMigration:
    """Tests for the full run_migration flow."""

    def test_empty_directory(self, tmp_path):
        """Empty instances_dir → nothing_to_migrate."""
        master = _setup_master(tmp_path)
        _setup_client_db(tmp_path)
        instances_dir = tmp_path / "instances"
        instances_dir.mkdir()

        report = run_migration(master, instances_dir)
        assert report.nothing_to_migrate is True
        assert report.files_scanned == 0

    def test_nonexistent_directory(self, tmp_path):
        """Missing instances_dir → nothing_to_migrate."""
        master = _setup_master(tmp_path)
        report = run_migration(master, tmp_path / "nope")
        assert report.nothing_to_migrate is True

    def test_single_file_happy_path(self, tmp_path):
        """Single JSON file migrated successfully."""
        master = _setup_master(tmp_path)
        _setup_client_db(tmp_path)
        instances_dir = tmp_path / "instances"

        _write_json(instances_dir, "my_app", {
            "name": "My App",
            "url": "https://example.com",
            "api_key": "admin",
            "auth_method": "basic",
            "secret_key": "s3cret",
            "project_folder": str(tmp_path / "project"),
        })

        report = run_migration(master, instances_dir)
        assert report.files_scanned == 1
        assert report.rows_inserted == 1
        assert report.skipped == 0
        assert len(report.warnings) == 0

        # Verify the instance was created
        rows = _get_instances(str(tmp_path / "client.db"))
        assert len(rows) == 1
        assert rows[0]["name"] == "My App"
        assert rows[0]["url"] == "https://example.com"
        assert rows[0]["username"] == "admin"
        assert rows[0]["password"] == "s3cret"
        assert rows[0]["is_default"] is True

        # Verify file was renamed
        assert not (instances_dir / "my_app.json").exists()
        assert (instances_dir / "my_app.json.migrated").exists()

    def test_multiple_files_one_client(self, tmp_path):
        """Multiple JSON files for the same client."""
        master = _setup_master(tmp_path)
        _setup_client_db(tmp_path)
        instances_dir = tmp_path / "instances"

        _write_json(instances_dir, "app_test", {
            "name": "App Test",
            "url": "https://test.example.com",
            "api_key": "admin",
            "auth_method": "basic",
            "secret_key": "pw1",
            "project_folder": str(tmp_path / "project"),
        })
        _write_json(instances_dir, "app_prod", {
            "name": "App Prod",
            "url": "https://prod.example.com",
            "api_key": "admin",
            "auth_method": "basic",
            "secret_key": "pw2",
            "project_folder": str(tmp_path / "project"),
        })

        report = run_migration(master, instances_dir)
        assert report.files_scanned == 2
        assert report.rows_inserted == 2

        rows = _get_instances(str(tmp_path / "client.db"))
        assert len(rows) == 2
        # Only the first should be default
        defaults = [r for r in rows if r["is_default"]]
        assert len(defaults) == 1

    def test_deploy_files_skipped(self, tmp_path):
        """Files ending in _deploy.json are ignored."""
        master = _setup_master(tmp_path)
        _setup_client_db(tmp_path)
        instances_dir = tmp_path / "instances"

        _write_json(instances_dir, "app", {
            "name": "App",
            "url": "https://example.com",
            "api_key": "admin",
            "auth_method": "basic",
            "secret_key": "pw",
            "project_folder": str(tmp_path / "project"),
        })
        _write_json(instances_dir, "app_deploy", {
            "droplet_ip": "1.2.3.4",
        })

        report = run_migration(master, instances_dir)
        assert report.files_scanned == 1
        assert report.rows_inserted == 1

    def test_environment_inference(self, tmp_path):
        """Environment inferred from instance name."""
        master = _setup_master(tmp_path)
        _setup_client_db(tmp_path)
        instances_dir = tmp_path / "instances"

        _write_json(instances_dir, "cbm_test", {
            "name": "CBM Test Instance",
            "url": "https://test.example.com",
            "api_key": "admin",
            "auth_method": "basic",
            "secret_key": "pw",
            "project_folder": str(tmp_path / "project"),
        })

        run_migration(master, instances_dir)
        rows = _get_instances(str(tmp_path / "client.db"))
        assert rows[0]["environment"] == "test"

    def test_idempotent_rerun(self, tmp_path):
        """Re-running migration does not duplicate rows."""
        master = _setup_master(tmp_path)
        _setup_client_db(tmp_path)
        instances_dir = tmp_path / "instances"

        _write_json(instances_dir, "app", {
            "name": "App",
            "url": "https://example.com",
            "api_key": "admin",
            "auth_method": "basic",
            "secret_key": "pw",
            "project_folder": str(tmp_path / "project"),
        })

        # First run
        report1 = run_migration(master, instances_dir)
        assert report1.rows_inserted == 1

        # Second run — file already renamed, should report nothing_to_migrate
        report2 = run_migration(master, instances_dir)
        assert report2.nothing_to_migrate is True or report2.rows_inserted == 0

        rows = _get_instances(str(tmp_path / "client.db"))
        assert len(rows) == 1

    def test_unresolvable_client_skipped(self, tmp_path):
        """JSON with non-matching project_folder is skipped with warning."""
        master = _setup_master(tmp_path)
        _setup_client_db(tmp_path)
        instances_dir = tmp_path / "instances"

        _write_json(instances_dir, "orphan", {
            "name": "Orphan",
            "url": "https://example.com",
            "api_key": "admin",
            "auth_method": "basic",
            "secret_key": "pw",
            "project_folder": "/nonexistent/path",
        })

        report = run_migration(master, instances_dir)
        assert report.skipped == 1
        assert len(report.warnings) == 1
        assert "no matching client" in report.warnings[0].reason

        # File should not be renamed
        assert (instances_dir / "orphan.json").exists()

    def test_no_project_folder_skipped(self, tmp_path):
        """JSON without project_folder is skipped with warning."""
        master = _setup_master(tmp_path)
        _setup_client_db(tmp_path)
        instances_dir = tmp_path / "instances"

        _write_json(instances_dir, "no_pf", {
            "name": "No PF",
            "url": "https://example.com",
            "api_key": "admin",
            "auth_method": "basic",
            "secret_key": "pw",
        })

        report = run_migration(master, instances_dir)
        assert report.skipped == 1
        assert "no project_folder" in report.skip_reasons[0][1]

    def test_already_migrated_file_skipped(self, tmp_path):
        """If JSON is already renamed to .migrated, it's not scanned."""
        master = _setup_master(tmp_path)
        _setup_client_db(tmp_path)
        instances_dir = tmp_path / "instances"
        instances_dir.mkdir()

        # Only .migrated file exists — no .json to scan
        (instances_dir / "app.json.migrated").write_text("{}")

        report = run_migration(master, instances_dir)
        assert report.nothing_to_migrate is True

    def test_multiple_clients(self, tmp_path):
        """Instances routed to different clients by project_folder."""
        master_path = str(tmp_path / "master.db")
        conn = run_master_migrations(master_path)

        proj1 = tmp_path / "project1"
        proj2 = tmp_path / "project2"

        db1 = str(tmp_path / "client1.db")
        db2 = str(tmp_path / "client2.db")

        conn.execute(
            "INSERT INTO Client (name, code, database_path, project_folder) "
            "VALUES (?, ?, ?, ?)",
            ("Client 1", "C1", db1, str(proj1)),
        )
        conn.execute(
            "INSERT INTO Client (name, code, database_path, project_folder) "
            "VALUES (?, ?, ?, ?)",
            ("Client 2", "C2", db2, str(proj2)),
        )
        conn.commit()
        conn.close()

        run_client_migrations(db1).close()
        run_client_migrations(db2).close()

        instances_dir = tmp_path / "instances"
        _write_json(instances_dir, "app1", {
            "name": "App 1",
            "url": "https://c1.example.com",
            "api_key": "admin",
            "auth_method": "basic",
            "secret_key": "pw",
            "project_folder": str(proj1),
        })
        _write_json(instances_dir, "app2", {
            "name": "App 2",
            "url": "https://c2.example.com",
            "api_key": "admin",
            "auth_method": "basic",
            "secret_key": "pw",
            "project_folder": str(proj2),
        })

        report = run_migration(master_path, instances_dir)
        assert report.rows_inserted == 2

        rows1 = _get_instances(db1)
        rows2 = _get_instances(db2)
        assert len(rows1) == 1
        assert rows1[0]["name"] == "App 1"
        assert len(rows2) == 1
        assert rows2[0]["name"] == "App 2"

    def test_code_collision_within_client(self, tmp_path):
        """Two instances with same derived code get suffixed."""
        master = _setup_master(tmp_path)
        db_path = _setup_client_db(tmp_path)

        # Pre-insert an instance with the code that will be derived
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO Instance (name, code, environment, is_default) "
            "VALUES (?, ?, ?, ?)",
            ("Existing", "APP", "production", 0),
        )
        conn.commit()
        conn.close()

        instances_dir = tmp_path / "instances"
        _write_json(instances_dir, "app", {
            "name": "App",
            "url": "https://example.com",
            "api_key": "admin",
            "auth_method": "basic",
            "secret_key": "pw",
            "project_folder": str(tmp_path / "project"),
        })

        report = run_migration(master, instances_dir)
        assert report.rows_inserted == 1

        rows = _get_instances(db_path)
        assert len(rows) == 2
        codes = {r["code"] for r in rows}
        assert "APP" in codes
        # Second one should have a suffix
        assert any(c.startswith("APP") and c != "APP" for c in codes)

    def test_api_key_auth_method(self, tmp_path):
        """Non-basic auth maps api_key to password, no username."""
        master = _setup_master(tmp_path)
        _setup_client_db(tmp_path)
        instances_dir = tmp_path / "instances"

        _write_json(instances_dir, "app", {
            "name": "App",
            "url": "https://example.com",
            "api_key": "myapikey123",
            "auth_method": "api_key",
            "project_folder": str(tmp_path / "project"),
        })

        run_migration(master, instances_dir)
        rows = _get_instances(str(tmp_path / "client.db"))
        assert rows[0]["username"] is None
        assert rows[0]["password"] == "myapikey123"

    def test_malformed_json_skipped(self, tmp_path):
        """Malformed JSON file is skipped with reason."""
        master = _setup_master(tmp_path)
        _setup_client_db(tmp_path)
        instances_dir = tmp_path / "instances"
        instances_dir.mkdir()
        (instances_dir / "bad.json").write_text("not valid json")

        report = run_migration(master, instances_dir)
        assert report.skipped == 1
        assert "parse error" in report.skip_reasons[0][1]

    def test_no_clients_in_master(self, tmp_path):
        """Empty master database → nothing_to_migrate."""
        master_path = str(tmp_path / "master.db")
        conn = run_master_migrations(master_path)
        conn.close()

        instances_dir = tmp_path / "instances"
        _write_json(instances_dir, "app", {
            "name": "App",
            "url": "https://example.com",
            "api_key": "admin",
            "auth_method": "basic",
            "secret_key": "pw",
            "project_folder": str(tmp_path / "project"),
        })

        report = run_migration(master_path, instances_dir)
        assert report.nothing_to_migrate is True
