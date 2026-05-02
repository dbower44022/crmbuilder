"""Tests for the Deployment-tab DeployEntry handlers.

Covers ``DeployEntry._on_regenerate_record`` — the Generate Deployment
Record button on the Deployment tab. When the active instance has no
``InstanceDeployConfig`` row yet, the handler must open the
``ConnectionConfigDialog`` backfill flow first (the same pattern used
by ``_on_upgrade`` and ``_on_recovery``) before proceeding to the
regeneration dialog.

Also covers ``DeployEntry._instance_is_self_hosted`` and the
button-visibility logic in ``refresh()``. An instance with no
``DeploymentRun`` and no ``InstanceDeployConfig`` row must be treated
as self-hosted so the backfill dialog is reachable; cloud-hosted and
bring-your-own scenarios are recognized only with positive evidence.

Tests for the handlers use a SimpleNamespace stub of ``DeployEntry``
rather than constructing a full Qt widget — the handler reads only
``self._conn``, ``self._instance``, ``self._project_folder``, and
``self._db_path()``, so a partial fake is sufficient and avoids booting
Qt machinery. Visibility tests do build a real ``DeployEntry`` widget
under an offscreen ``QApplication`` so ``QPushButton.isVisible`` can be
asserted.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from automation.core.deployment import deploy_config_repo
from automation.core.deployment.deploy_config_repo import InstanceDeployConfig
from automation.db.migrations import run_client_migrations
from automation.ui.deployment import (
    connection_config_dialog as connection_config_dialog_module,
)
from automation.ui.deployment import (
    deploy_entry,
    deployment_logic,
    regenerate_record_dialog,
)
from automation.ui.deployment.deployment_logic import InstanceDetail, InstanceRow


@pytest.fixture(scope="module", autouse=True)
def _qapplication():
    """Boot an offscreen QApplication for the visibility tests.

    The handler-only tests do not need this, but importing it once at
    module scope is cheap and avoids ordering surprises.
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def _make_instance() -> InstanceRow:
    return InstanceRow(
        id=42,
        name="CBM Test",
        code="CBMTEST",
        environment="test",
        url="https://crm-test.example.com",
        is_default=False,
    )


def _make_instance_detail() -> InstanceDetail:
    return InstanceDetail(
        id=42,
        name="CBM Test",
        code="CBMTEST",
        environment="test",
        url="https://crm-test.example.com",
        username="admin",
        password="adminpw",
        description=None,
        is_default=False,
        created_at=None,
        updated_at=None,
    )


def _make_deploy_config() -> InstanceDeployConfig:
    return InstanceDeployConfig(
        instance_id=42,
        scenario="self_hosted",
        ssh_host="1.2.3.4",
        ssh_port=22,
        ssh_username="root",
        ssh_auth_type="key",
        ssh_credential="/home/user/.ssh/id_ed25519",
        domain="crm-test.example.com",
        letsencrypt_email="ops@example.com",
        db_root_password="db-root-secret",
        admin_email="admin@example.com",
        domain_registrar="Porkbun",
    )


def _stub_entry(instance: InstanceRow | None) -> SimpleNamespace:
    """Build a partial DeployEntry stub the handler can run against."""
    stub = SimpleNamespace(
        _conn=object(),  # opaque; load_deploy_config is patched
        _instance=instance,
        _project_folder="/tmp/project",
    )
    stub._db_path = lambda: "/tmp/client.db"
    stub._read_client_name = lambda: "Cleveland Business Mentors"
    return stub


def _invoke_handler(stub: SimpleNamespace) -> None:
    """Invoke the unbound method with the stub as ``self``."""
    deploy_entry.DeployEntry._on_regenerate_record(stub)


# ── Backfill: opens ConnectionConfigDialog when config missing ──────


def test_on_regenerate_record_opens_backfill_when_config_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``load_deploy_config`` returns None, the handler opens the
    backfill dialog and then proceeds to the regeneration dialog using
    the saved config.
    """
    saved = _make_deploy_config()
    detail = _make_instance_detail()

    dialog_instance = MagicMock()
    dialog_instance.saved_config = saved
    dialog_class = MagicMock(return_value=dialog_instance)
    launch_mock = MagicMock()

    monkeypatch.setattr(
        deploy_config_repo, "load_deploy_config", lambda *_a, **_kw: None,
    )
    monkeypatch.setattr(
        connection_config_dialog_module, "ConnectionConfigDialog",
        dialog_class,
    )
    monkeypatch.setattr(
        deployment_logic, "load_instance_detail",
        lambda *_a, **_kw: detail,
    )
    monkeypatch.setattr(
        regenerate_record_dialog, "launch_regeneration_dialog", launch_mock,
    )

    instance = _make_instance()
    stub = _stub_entry(instance)
    _invoke_handler(stub)

    dialog_class.assert_called_once()
    args, kwargs = dialog_class.call_args
    # Constructor positional args: conn, instance_id, instance_name
    assert args[0] is stub._conn
    assert args[1] == instance.id
    assert args[2] == instance.name
    assert kwargs.get("parent") is stub
    dialog_instance.exec.assert_called_once()

    launch_mock.assert_called_once_with(
        stub, detail, saved, stub._project_folder, "/tmp/client.db",
        "Cleveland Business Mentors",
    )


# ── Cancel: regeneration dialog is NOT launched ─────────────────────


def test_on_regenerate_record_skips_when_user_cancels_backfill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the operator cancels the backfill dialog, the handler must
    bail without invoking ``launch_regeneration_dialog``.
    """
    dialog_instance = MagicMock()
    dialog_instance.saved_config = None  # User cancelled.
    dialog_class = MagicMock(return_value=dialog_instance)
    launch_mock = MagicMock()
    detail_mock = MagicMock()

    monkeypatch.setattr(
        deploy_config_repo, "load_deploy_config", lambda *_a, **_kw: None,
    )
    monkeypatch.setattr(
        connection_config_dialog_module, "ConnectionConfigDialog",
        dialog_class,
    )
    monkeypatch.setattr(
        deployment_logic, "load_instance_detail", detail_mock,
    )
    monkeypatch.setattr(
        regenerate_record_dialog, "launch_regeneration_dialog", launch_mock,
    )

    stub = _stub_entry(_make_instance())
    _invoke_handler(stub)

    dialog_class.assert_called_once()
    dialog_instance.exec.assert_called_once()
    detail_mock.assert_not_called()
    launch_mock.assert_not_called()


# ── _instance_is_self_hosted: defaults and positive evidence ────────


def _self_hosted_stub(
    conn: sqlite3.Connection, instance: InstanceRow | None,
) -> SimpleNamespace:
    """Stub usable as ``self`` when calling ``_instance_is_self_hosted``."""
    return SimpleNamespace(_conn=conn, _instance=instance)


def _migrated_db(tmp_path: Path) -> sqlite3.Connection:
    """Return a per-client SQLite connection with all migrations applied."""
    return run_client_migrations(str(tmp_path / "client.db"))


def _insert_instance(conn: sqlite3.Connection) -> int:
    """Insert one Instance row and return its id."""
    cur = conn.execute(
        "INSERT INTO Instance (name, code, environment, url) "
        "VALUES (?, ?, ?, ?)",
        ("CBM Test", "CBMTEST", "test", "https://crm-test.example.com"),
    )
    conn.commit()
    return int(cur.lastrowid)


def test_instance_is_self_hosted_when_no_run_and_no_config(
    tmp_path: Path,
) -> None:
    """No DeploymentRun and no InstanceDeployConfig → default to True.

    This is the regression case that gates the CBM Test backfill
    procedure: the user has just created the Instance row but has not
    yet recorded a deploy or backfilled a config, so the buttons must
    still appear so the backfill dialog is reachable.
    """
    conn = _migrated_db(tmp_path)
    try:
        instance_id = _insert_instance(conn)
        instance = InstanceRow(
            id=instance_id, name="CBM Test", code="CBMTEST",
            environment="test", url="https://crm-test.example.com",
            is_default=False,
        )
        stub = _self_hosted_stub(conn, instance)
        assert deploy_entry.DeployEntry._instance_is_self_hosted(stub) is True
    finally:
        conn.close()


def test_instance_is_self_hosted_false_for_cloud_hosted_run(
    tmp_path: Path,
) -> None:
    """Positive evidence of cloud-hosted → False."""
    conn = _migrated_db(tmp_path)
    try:
        instance_id = _insert_instance(conn)
        conn.execute(
            "INSERT INTO DeploymentRun "
            "(instance_id, scenario, crm_platform, started_at, "
            "completed_at, outcome) "
            "VALUES (?, 'cloud_hosted', 'EspoCRM', "
            "'2026-01-01T00:00:00', '2026-01-01T00:05:00', 'success')",
            (instance_id,),
        )
        conn.commit()
        instance = InstanceRow(
            id=instance_id, name="CBM Test", code="CBMTEST",
            environment="test", url="https://crm-test.example.com",
            is_default=False,
        )
        stub = _self_hosted_stub(conn, instance)
        assert deploy_entry.DeployEntry._instance_is_self_hosted(stub) is False
    finally:
        conn.close()


def test_instance_is_self_hosted_true_for_self_hosted_run(
    tmp_path: Path,
) -> None:
    """Positive evidence of self-hosted → True."""
    conn = _migrated_db(tmp_path)
    try:
        instance_id = _insert_instance(conn)
        conn.execute(
            "INSERT INTO DeploymentRun "
            "(instance_id, scenario, crm_platform, started_at, "
            "completed_at, outcome) "
            "VALUES (?, 'self_hosted', 'EspoCRM', "
            "'2026-01-01T00:00:00', '2026-01-01T00:05:00', 'success')",
            (instance_id,),
        )
        conn.commit()
        instance = InstanceRow(
            id=instance_id, name="CBM Test", code="CBMTEST",
            environment="test", url="https://crm-test.example.com",
            is_default=False,
        )
        stub = _self_hosted_stub(conn, instance)
        assert deploy_entry.DeployEntry._instance_is_self_hosted(stub) is True
    finally:
        conn.close()


# ── refresh() visibility for the Generate Deployment Record button ──


def test_regenerate_record_button_visible_for_self_hosted_without_config(
    tmp_path: Path,
) -> None:
    """Regression: button must be visible when scenario is unrecorded.

    Reproduces the live CBM Test situation that motivated Prompt G —
    an Instance row exists but neither DeploymentRun nor
    InstanceDeployConfig has any rows for it. The button must still
    show so the backfill dialog can be opened.
    """
    conn = _migrated_db(tmp_path)
    try:
        instance_id = _insert_instance(conn)
        instance = InstanceRow(
            id=instance_id, name="CBM Test", code="CBMTEST",
            environment="test", url="https://crm-test.example.com",
            is_default=False,
        )
        widget = deploy_entry.DeployEntry()
        try:
            widget.show()
            widget.refresh(conn, instance, has_instances=True)
            assert widget._regenerate_record_btn.isVisible() is True
            assert widget._upgrade_btn.isVisible() is True
            assert widget._recovery_btn.isVisible() is True
        finally:
            widget.close()
            widget.deleteLater()
    finally:
        conn.close()


def test_regenerate_record_button_hidden_for_cloud_hosted(
    tmp_path: Path,
) -> None:
    """A cloud-hosted DeploymentRun must hide all three action buttons."""
    conn = _migrated_db(tmp_path)
    try:
        instance_id = _insert_instance(conn)
        conn.execute(
            "INSERT INTO DeploymentRun "
            "(instance_id, scenario, crm_platform, started_at, "
            "completed_at, outcome) "
            "VALUES (?, 'cloud_hosted', 'EspoCRM', "
            "'2026-01-01T00:00:00', '2026-01-01T00:05:00', 'success')",
            (instance_id,),
        )
        conn.commit()
        instance = InstanceRow(
            id=instance_id, name="CBM Test", code="CBMTEST",
            environment="test", url="https://crm-test.example.com",
            is_default=False,
        )
        widget = deploy_entry.DeployEntry()
        try:
            widget.show()
            widget.refresh(conn, instance, has_instances=True)
            assert widget._regenerate_record_btn.isVisible() is False
            assert widget._upgrade_btn.isVisible() is False
            assert widget._recovery_btn.isVisible() is False
        finally:
            widget.close()
            widget.deleteLater()
    finally:
        conn.close()
