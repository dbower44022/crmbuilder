"""Tests for the Deployment-tab DeployEntry handlers.

Covers ``DeployEntry._on_regenerate_record`` — the Generate Deployment
Record button on the Deployment tab. When the active instance has no
``InstanceDeployConfig`` row yet, the handler must open the
``ConnectionConfigDialog`` backfill flow first (the same pattern used
by ``_on_upgrade`` and ``_on_recovery``) before proceeding to the
regeneration dialog.

Tests use a SimpleNamespace stub of ``DeployEntry`` rather than
constructing a full Qt widget — the handler reads only ``self._conn``,
``self._instance``, ``self._project_folder``, and ``self._db_path()``,
so a partial fake is sufficient and avoids booting Qt machinery.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from automation.core.deployment import deploy_config_repo
from automation.core.deployment.deploy_config_repo import InstanceDeployConfig
from automation.ui.deployment import (
    connection_config_dialog as connection_config_dialog_module,
)
from automation.ui.deployment import (
    deploy_entry,
    deployment_logic,
    regenerate_record_dialog,
)
from automation.ui.deployment.deployment_logic import InstanceDetail, InstanceRow


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
