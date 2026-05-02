"""Tests for the Deploy Wizard's per-field hint text.

Verifies that placeholder text and tooltips are set on the
self-hosted-scenario pages added in the deployment-record series.
Tests assert presence (non-empty), not exact wording — strings live
alongside the production code and would otherwise create brittle
duplication that drifts on every copy edit.

Password fields intentionally omit placeholder text (per the
deployment-record-D spec) so the hint table never echoes a
credential silhouette into a screen recording. They are excluded
from placeholder assertions but still required to carry tooltips.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QLabel, QLineEdit

from automation.core.deployment.wizard_logic import PreSelection
from automation.db.migrations import run_client_migrations
from automation.ui.deployment.deploy_wizard.wizard_dialog import DeployWizard


@pytest.fixture(scope="module", autouse=True)
def _qapplication():
    """Boot an offscreen QApplication for widget instantiation."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def wizard(tmp_path: Path) -> DeployWizard:
    """Build a wizard against a fresh per-client DB."""
    client_db = tmp_path / "client.db"
    conn = run_client_migrations(str(client_db))
    master_db = str(tmp_path / "master.db")
    dlg = DeployWizard(
        conn=conn,
        pre_selection=PreSelection(platform=None, scenario=None),
        master_db_path=master_db,
        client_id=0,
    )
    yield dlg
    dlg.deleteLater()
    conn.close()


def _assert_placeholders(page) -> None:
    """Every non-password QLineEdit on the page carries a placeholder."""
    line_edits = page.findChildren(QLineEdit)
    assert line_edits, "expected at least one QLineEdit on the page"
    for line_edit in line_edits:
        if line_edit.echoMode() == QLineEdit.EchoMode.Password:
            continue
        assert line_edit.placeholderText(), (
            f"missing placeholder on QLineEdit (text={line_edit.text()!r})"
        )


def _assert_tooltips(page) -> None:
    """Every QLineEdit on the page carries a tooltip."""
    line_edits = page.findChildren(QLineEdit)
    assert line_edits, "expected at least one QLineEdit on the page"
    for line_edit in line_edits:
        assert line_edit.toolTip(), (
            f"missing tooltip on QLineEdit (text={line_edit.text()!r})"
        )


# ── Server (SSH) Connection page ───────────────────────────────────────


def test_server_page_fields_have_placeholders(wizard: DeployWizard) -> None:
    page = wizard._stack.widget(wizard._PAGE_SH_SERVER)
    _assert_placeholders(page)


def test_server_page_fields_have_tooltips(wizard: DeployWizard) -> None:
    page = wizard._stack.widget(wizard._PAGE_SH_SERVER)
    _assert_tooltips(page)


def test_ssh_host_helper_label_present(wizard: DeployWizard) -> None:
    """Spot-check that a helper QLabel sits below SSH Host."""
    host_field = wizard._ssh_host
    container = host_field.parentWidget()
    assert container is not None
    helper_labels = [
        child for child in container.findChildren(QLabel)
        if child.text().strip()
    ]
    assert helper_labels, "expected at least one helper label under SSH Host"


# ── Domain and Database page ───────────────────────────────────────────


def test_domain_page_fields_have_placeholders(wizard: DeployWizard) -> None:
    page = wizard._stack.widget(wizard._PAGE_SH_DOMAIN)
    _assert_placeholders(page)


def test_domain_page_fields_have_tooltips(wizard: DeployWizard) -> None:
    page = wizard._stack.widget(wizard._PAGE_SH_DOMAIN)
    _assert_tooltips(page)


# ── Admin page ─────────────────────────────────────────────────────────


def test_admin_page_fields_have_placeholders(wizard: DeployWizard) -> None:
    page = wizard._stack.widget(wizard._PAGE_SH_ADMIN)
    _assert_placeholders(page)


def test_admin_page_fields_have_tooltips(wizard: DeployWizard) -> None:
    page = wizard._stack.widget(wizard._PAGE_SH_ADMIN)
    _assert_tooltips(page)


# ── Documentation Inputs page ──────────────────────────────────────────


def test_documentation_page_fields_have_placeholders(
    wizard: DeployWizard,
) -> None:
    page = wizard._stack.widget(wizard._PAGE_SH_DOCUMENTATION)
    _assert_placeholders(page)


def test_documentation_page_fields_have_tooltips(
    wizard: DeployWizard,
) -> None:
    page = wizard._stack.widget(wizard._PAGE_SH_DOCUMENTATION)
    _assert_tooltips(page)
