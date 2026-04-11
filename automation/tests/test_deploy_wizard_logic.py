"""Tests for Deploy Wizard core logic (Qt-free).

Covers: pre-selection, instance matching, DeploymentRun lifecycle,
instance creation/update, connectivity result model.

Note: ssh_deploy tests are skipped when dnspython/paramiko are not
installed (test environment may lack these dependencies).
"""

from __future__ import annotations

import sqlite3

import pytest

from automation.core.deployment.wizard_logic import (
    SCENARIOS,
    SUPPORTED_PLATFORMS,
    create_wizard_instance,
    finalize_deployment_run,
    find_matching_instances,
    get_pre_selection,
    insert_deployment_run,
    update_instance_from_wizard,
)
from automation.db.migrations import run_client_migrations, run_master_migrations

try:
    from automation.core.deployment.connectivity import (
        SUPPORTED_VERSIONS,
        ConnectivityResult,
    )
    _HAS_CONNECTIVITY = True
except ImportError:
    _HAS_CONNECTIVITY = False

try:
    from automation.core.deployment.ssh_deploy import SelfHostedConfig
    _HAS_SSH = True
except ImportError:
    _HAS_SSH = False


@pytest.fixture()
def master_db(tmp_path) -> str:
    """Create a master database with one client."""
    path = str(tmp_path / "master.db")
    conn = run_master_migrations(path)
    conn.execute(
        "INSERT INTO Client (name, code, project_folder, crm_platform, deployment_model) "
        "VALUES (?, ?, ?, ?, ?)",
        ("Test", "TC", str(tmp_path / "proj"), "EspoCRM", "self_hosted"),
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture()
def master_db_null_platform(tmp_path) -> str:
    """Create a master database with a client that has no platform set."""
    path = str(tmp_path / "master_null.db")
    conn = run_master_migrations(path)
    conn.execute(
        "INSERT INTO Client (name, code, project_folder) VALUES (?, ?, ?)",
        ("Unset", "UN", str(tmp_path / "proj")),
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture()
def client_db(tmp_path) -> sqlite3.Connection:
    """Fresh per-client database."""
    return run_client_migrations(str(tmp_path / "client.db"))


class TestPreSelection:

    def test_both_set(self, master_db):
        pre = get_pre_selection(master_db, 1)
        assert pre.platform == "EspoCRM"
        assert pre.scenario == "self_hosted"

    def test_both_null(self, master_db_null_platform):
        pre = get_pre_selection(master_db_null_platform, 1)
        assert pre.platform is None
        assert pre.scenario is None

    def test_nonexistent_client(self, master_db):
        pre = get_pre_selection(master_db, 9999)
        assert pre.platform is None
        assert pre.scenario is None


class TestInstanceMatching:

    def test_empty_database(self, client_db):
        matches = find_matching_instances(client_db)
        assert matches == []

    def test_finds_instances(self, client_db):
        client_db.execute(
            "INSERT INTO Instance (name, code, environment, url, is_default) "
            "VALUES (?, ?, ?, ?, ?)",
            ("Alpha", "AL", "production", "https://alpha.example.com", 0),
        )
        client_db.commit()
        matches = find_matching_instances(client_db)
        assert len(matches) == 1
        assert matches[0].name == "Alpha"
        assert matches[0].code == "AL"

    def test_multiple_matches(self, client_db):
        for name, code in [("Alpha", "AL"), ("Beta", "BE")]:
            client_db.execute(
                "INSERT INTO Instance (name, code, environment, is_default) "
                "VALUES (?, ?, ?, ?)",
                (name, code, "production", 0),
            )
        client_db.commit()
        matches = find_matching_instances(client_db)
        assert len(matches) == 2


class TestDeploymentRunLifecycle:

    def test_insert_and_finalize_success(self, client_db):
        inst_id = create_wizard_instance(
            client_db, name="Test", code="TS", environment="production",
        )
        run_id = insert_deployment_run(
            client_db, instance_id=inst_id,
            scenario="self_hosted", crm_platform="EspoCRM",
        )
        assert run_id > 0

        # Check the row exists
        row = client_db.execute(
            "SELECT scenario, crm_platform, outcome FROM DeploymentRun WHERE id = ?",
            (run_id,),
        ).fetchone()
        assert row[0] == "self_hosted"
        assert row[1] == "EspoCRM"
        assert row[2] is None  # Not yet finalized

        finalize_deployment_run(client_db, run_id, outcome="success")
        row = client_db.execute(
            "SELECT outcome, completed_at FROM DeploymentRun WHERE id = ?",
            (run_id,),
        ).fetchone()
        assert row[0] == "success"
        assert row[1] is not None

    def test_finalize_failure(self, client_db):
        inst_id = create_wizard_instance(
            client_db, name="Fail", code="FL", environment="test",
        )
        run_id = insert_deployment_run(
            client_db, instance_id=inst_id,
            scenario="cloud_hosted", crm_platform="EspoCRM",
        )
        finalize_deployment_run(
            client_db, run_id, outcome="failure",
            failure_reason="SSH connection refused",
        )
        row = client_db.execute(
            "SELECT outcome, failure_reason FROM DeploymentRun WHERE id = ?",
            (run_id,),
        ).fetchone()
        assert row[0] == "failure"
        assert row[1] == "SSH connection refused"

    def test_finalize_cancelled(self, client_db):
        inst_id = create_wizard_instance(
            client_db, name="Cancel", code="CN", environment="staging",
        )
        run_id = insert_deployment_run(
            client_db, instance_id=inst_id,
            scenario="bring_your_own", crm_platform="EspoCRM",
        )
        finalize_deployment_run(client_db, run_id, outcome="cancelled")
        row = client_db.execute(
            "SELECT outcome FROM DeploymentRun WHERE id = ?",
            (run_id,),
        ).fetchone()
        assert row[0] == "cancelled"


class TestWizardInstanceOps:

    def test_create_wizard_instance(self, client_db):
        inst_id = create_wizard_instance(
            client_db, name="New", code="NW", environment="production",
            url="https://new.example.com",
        )
        row = client_db.execute(
            "SELECT name, code, environment, url FROM Instance WHERE id = ?",
            (inst_id,),
        ).fetchone()
        assert row[0] == "New"
        assert row[1] == "NW"
        assert row[3] == "https://new.example.com"

    def test_update_instance_from_wizard(self, client_db):
        inst_id = create_wizard_instance(
            client_db, name="Old", code="OD", environment="production",
        )
        update_instance_from_wizard(
            client_db, inst_id,
            url="https://updated.example.com",
            username="admin",
            password="secret",
        )
        row = client_db.execute(
            "SELECT url, username, password FROM Instance WHERE id = ?",
            (inst_id,),
        ).fetchone()
        assert row[0] == "https://updated.example.com"
        assert row[1] == "admin"
        assert row[2] == "secret"


class TestConstants:

    def test_supported_platforms(self):
        assert "EspoCRM" in SUPPORTED_PLATFORMS

    def test_scenarios(self):
        assert set(SCENARIOS) == {"self_hosted", "cloud_hosted", "bring_your_own"}

    @pytest.mark.skipif(not _HAS_CONNECTIVITY, reason="dnspython/requests not available")
    def test_supported_versions_has_espocrm(self):
        assert "EspoCRM" in SUPPORTED_VERSIONS
        assert len(SUPPORTED_VERSIONS["EspoCRM"]) > 0


@pytest.mark.skipif(not _HAS_CONNECTIVITY, reason="connectivity module not available")
class TestConnectivityResultModel:

    def test_success_result(self):
        r = ConnectivityResult(
            reachable=True, authenticated=True, platform_match=True,
            version="8.4.1", version_supported=True, error=None,
        )
        assert r.reachable
        assert r.authenticated
        assert r.error is None

    def test_failure_result(self):
        r = ConnectivityResult(
            reachable=False, authenticated=False, platform_match=False,
            version=None, version_supported=False,
            error="Connection refused",
        )
        assert not r.reachable
        assert r.error == "Connection refused"


@pytest.mark.skipif(not _HAS_SSH, reason="paramiko/dnspython not available")
class TestSelfHostedConfig:

    def test_config_creation(self):
        cfg = SelfHostedConfig(
            ssh_host="1.2.3.4", ssh_port=22, ssh_username="root",
            ssh_credential="/home/user/.ssh/id_ed25519", ssh_auth_type="key",
            domain="crm.example.com", letsencrypt_email="admin@example.com",
            db_password="dbpw", db_root_password="rootpw",
            admin_username="admin", admin_password="adminpw",
            admin_email="admin@example.com",
        )
        assert cfg.ssh_host == "1.2.3.4"
        assert cfg.domain == "crm.example.com"
