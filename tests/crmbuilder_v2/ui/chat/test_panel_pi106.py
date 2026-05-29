"""Qt-level wiring tests for the PI-106 chat-panel follow-ups.

These exercise the panel's signal handlers directly (the panel is never
shown, so assertions use the explicit ``isHidden()`` flag rather than
``isVisible()``, which also reflects ancestor visibility):

* the staleness badge appears only when a *read* entity changes elsewhere
  and no turn is in flight;
* a context-window overflow surfaces the interactive Trim affordance, and
  Trim degrades gracefully when nothing can be retried.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.ui.chat.widgets import ActionNoticeItem
from crmbuilder_v2.ui.panels.chat import ChatPanel
from crmbuilder_v2.ui.refresh import RefreshService

pytestmark = pytest.mark.v2


def _make_panel(qapp, tmp_path):
    # RefreshService is constructed but never started; the tests emit
    # ``data_changed`` manually to simulate a cross-tab write.
    refresh_service = RefreshService(tmp_path)
    panel = ChatPanel("http://test.invalid", refresh_service)
    return panel, refresh_service


def test_stale_badge_appears_for_read_entity(qapp, tmp_path):
    panel, refresh_service = _make_panel(qapp, tmp_path)
    panel._controller._read_entity_types.add("decision")
    refresh_service.data_changed.emit("decision")
    qapp.processEvents()
    assert not panel._stale_label.isHidden()
    assert "Decision" in panel._stale_label.text()


def test_stale_badge_silent_for_unread_entity(qapp, tmp_path):
    panel, refresh_service = _make_panel(qapp, tmp_path)
    refresh_service.data_changed.emit("risk")
    qapp.processEvents()
    assert panel._stale_label.isHidden()


def test_stale_badge_suppressed_during_turn(qapp, tmp_path):
    panel, refresh_service = _make_panel(qapp, tmp_path)
    panel._controller._read_entity_types.add("decision")
    panel._controller._in_turn = True
    refresh_service.data_changed.emit("decision")
    qapp.processEvents()
    assert panel._stale_label.isHidden()


def test_send_clears_stale_badge(qapp, tmp_path):
    panel, refresh_service = _make_panel(qapp, tmp_path)
    panel._controller._read_entity_types.add("decision")
    refresh_service.data_changed.emit("decision")
    qapp.processEvents()
    assert not panel._stale_label.isHidden()
    panel._clear_stale()
    assert panel._stale_label.isHidden()


def test_context_overflow_surfaces_trim_affordance(qapp, tmp_path):
    panel, _refresh_service = _make_panel(qapp, tmp_path)
    panel._controller.context_overflow.emit()
    qapp.processEvents()
    assert isinstance(panel._active_trim_notice, ActionNoticeItem)


def test_trim_without_worker_advises_new_chat(qapp, tmp_path):
    panel, _refresh_service = _make_panel(qapp, tmp_path)
    panel._controller.context_overflow.emit()
    qapp.processEvents()
    # No API key was set, so there is no worker; trim_and_retry returns
    # False and the panel must clear the affordance without raising.
    panel._on_trim_requested()
    qapp.processEvents()
    assert panel._active_trim_notice is None
