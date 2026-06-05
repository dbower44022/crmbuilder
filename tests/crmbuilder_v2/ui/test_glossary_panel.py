"""Glossary panel / dialog tests — PI-061.

Covers the "Glossary" sidebar entry under the Methodology group, the
``term`` ENTITY_TYPE_TO_SIDEBAR_LABEL registration, the master-pane columns,
and the create/edit dialogs end to end against a real per-test DB.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.term_crud import TermCreateDialog, TermEditDialog
from crmbuilder_v2.ui.main_window import ENTITY_TYPE_TO_SIDEBAR_LABEL
from crmbuilder_v2.ui.panels.glossary import GlossaryPanel
from crmbuilder_v2.ui.sidebar import SIDEBAR_GROUPS, Sidebar
from fastapi.testclient import TestClient


@pytest.fixture
def glossary_client(v2_env) -> StorageClient:
    sc = StorageClient(base_url="http://testserver", client=TestClient(create_app()))
    sc.set_active_engagement("ENG-001")
    return sc


def _wait_rows(qtbot, panel: GlossaryPanel, count: int) -> None:
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == count, timeout=3000)


def test_glossary_is_present_in_methodology_group():
    methodology = dict(SIDEBAR_GROUPS)["Methodology"]
    assert "Glossary" in methodology
    assert ENTITY_TYPE_TO_SIDEBAR_LABEL["term"] == "Glossary"


def test_sidebar_renders_glossary_under_methodology(qtbot):
    from crmbuilder_v2.ui.sidebar import _HEADER_ROLE  # noqa: PLC0415

    sidebar = Sidebar()
    qtbot.addWidget(sidebar)
    items = [sidebar.item(r) for r in range(sidebar.count())]
    rendered = [item.text() for item in items]
    headers = {item.text(): i for i, item in enumerate(items) if item.data(_HEADER_ROLE)}
    assert "Glossary" in rendered
    assert rendered.index("Glossary") > headers["Methodology"]


def test_glossary_panel_columns(qtbot, glossary_client):
    panel = GlossaryPanel(glossary_client)
    qtbot.addWidget(panel)
    titles = [c.title for c in panel.list_columns()]
    assert titles == ["Identifier", "Term", "Scope", "Status"]
    assert panel.entity_title() == "Glossary"


def test_create_term_via_dialog(qtbot, glossary_client):
    dialog = TermCreateDialog(glossary_client)
    qtbot.addWidget(dialog)
    assert "identifier" not in dialog._widgets  # server-assigned
    dialog._widgets["name"].setText("Engagement")
    dialog._widgets["definition"].setPlainText("A defined unit of work for one client.")
    dialog._widgets["usage_scope"].setPlainText("Used throughout the PRD.")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    assert dialog.created_identifier() == "TERM-001"

    # The new term shows in the panel.
    panel = GlossaryPanel(glossary_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 1)
    row0 = panel._model.record_at(0)
    assert row0["identifier"] == "TERM-001"
    assert row0["name"] == "Engagement"
    assert row0["scope"] == "system"


def test_edit_term_status_via_dialog(qtbot, glossary_client):
    created = glossary_client.create_term(
        {"name": "Skill", "definition": "A reusable knowledge file."}
    )
    fresh = glossary_client.get_term(created["identifier"])
    dialog = TermEditDialog(glossary_client, fresh)
    qtbot.addWidget(dialog)
    assert dialog._widgets["identifier"].isReadOnly()
    status = dialog._widgets["status"]
    status.setCurrentText("retired")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    assert glossary_client.get_term(created["identifier"])["status"] == "retired"
