"""Deploy History panel tests — PI-419 (REQ-522)."""

from __future__ import annotations

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import deploy_runs
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.panels.deploy_history import DeployHistoryPanel, _kept_line
from crmbuilder_v2.ui.sidebar import SIDEBAR_GROUPS
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QLabel


@pytest.fixture(autouse=True)
def _secrets_in_memory(monkeypatch):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    yield
    secrets._reset_in_memory_store_for_tests()


@pytest.fixture
def ui_client(v2_env) -> StorageClient:
    sc = StorageClient(base_url="http://testserver", client=TestClient(create_app()))
    sc.set_active_engagement("ENG-001")
    return sc


def _seed_failed_run():
    with session_scope() as s:
        deploy_runs.create_deploy_run(s, spec={"domain": "crm.example.org", "size": "s-2vcpu-4gb", "region": "nyc3", "image": "ubuntu"})
        deploy_runs.claim_next_run(s, worker_id="w")
        deploy_runs.set_phase(s, "DEP-001", "create_droplet", state={"droplet_id": "4242", "droplet_ip": "203.0.113.7"}, phase_status="done")
        deploy_runs.set_phase(s, "DEP-001", "create_dns", phase_status="failed", error="403")
        deploy_runs.append_log(s, "DEP-001", [("error", "Authentication error")])
        deploy_runs.finish(s, "DEP-001", status="failed", error="create_dns: 403")


def test_sidebar_and_build_panel():
    # REQ-526 / PI-432: the sidebar is phase-scoped (DEC-953); the legacy
    # fixed groups are retired. These panels stay registered and reachable
    # through the All-panels index of every phase tab.
    all_panels = dict(SIDEBAR_GROUPS)["All panels"]
    assert "Deploy History" in all_panels
    assert "Publish History" in all_panels


def test_records_and_detail_show_kept_server(qtbot, ui_client):
    _seed_failed_run()
    panel = DeployHistoryPanel(ui_client)
    qtbot.addWidget(panel)
    records = panel._post_process_records(panel.fetch_records())
    assert records[0]["status_display"] == "✗ failed"
    assert records[0]["phase_display"] == "Setting DNS"
    assert records[0]["domain_display"] == "crm.example.org"
    extras = panel.fetch_detail_extras(records[0])
    assert extras["full"]["deploy_run_log"][0][2] == "Authentication error"
    detail = panel.render_detail(records[0], extras)
    qtbot.addWidget(detail)
    kept = detail.findChild(QLabel, "deploy_kept_label")
    assert kept is not None and "server 4242 at 203.0.113.7" in kept.text()
    assert detail.findChild(type(kept).__mro__[0], "deploy_kept_label") is not None
    from PySide6.QtWidgets import QPushButton
    assert detail.findChild(QPushButton, "deploy_retry_button") is not None
    assert detail.findChild(QPushButton, "deploy_copy_droplet_button") is not None
    assert detail.findChild(QPushButton, "deploy_open_progress_button") is None


def test_kept_line_only_for_failed_or_cancelled():
    assert _kept_line({"deploy_run_status": "succeeded", "deploy_run_state": {"droplet_id": "1"}}) is None
    assert _kept_line({"deploy_run_status": "failed", "deploy_run_state": {}}) is None
    assert "server 9" in _kept_line({"deploy_run_status": "cancelled", "deploy_run_state": {"droplet_id": "9"}})
