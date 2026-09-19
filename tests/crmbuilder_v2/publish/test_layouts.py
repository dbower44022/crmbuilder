"""Tests for applying declared screen layouts (REQ-611 / PI-525).

Most of these are about the platform not handing back what it was given: the
two places it stores a panel's title, the keys it omits rather than storing
false, and the panels it adds to a map of its own accord. A comparison that
got those wrong would either rewrite every layout on every run or report a
difference that is not there.
"""

from __future__ import annotations

from typing import Any

import pytest
from crmbuilder_v2.publish import layouts as lay
from crmbuilder_v2.publish.entities import AuthenticationRejected
from crmbuilder_v2.publish.layouts import (
    LayoutIntent,
    apply_layout,
    apply_layouts,
    layouts_match,
)


class FakeClient:
    def __init__(self, live: Any = None, get_status: int = 200) -> None:
        self.live = live
        self.get_status = get_status
        self.calls: list[tuple[str, str, Any]] = []
        self.save_answers: list[tuple[int, Any]] = [(200, {})]

    def get_layout(self, entity: str, layout_type: str) -> tuple[int, Any]:
        self.calls.append(("get", layout_type, None))
        return self.get_status, self.live

    def save_layout(self, entity: str, layout_type: str, body: Any):
        self.calls.append(("save", layout_type, body))
        return (
            self.save_answers.pop(0)
            if len(self.save_answers) > 1
            else self.save_answers[0]
        )

    @property
    def kinds(self) -> list[str]:
        return [kind for kind, _, _ in self.calls]


def _panel(label: str = "Overview", fields: list[str] | None = None, **extra: Any):
    panel: dict[str, Any] = {
        "label": label,
        "rows": [[{"name": name} for name in (fields or ["name"])]],
    }
    panel.update(extra)
    return panel


# --- the platform's own habits ----------------------------------------------


def test_a_title_stored_under_either_key_is_the_same_title() -> None:
    """The platform uses one key for a customised layout and another for a
    factory default."""
    assert layouts_match(
        [{"customLabel": "Overview", "rows": []}],
        [{"label": "Overview", "rows": []}],
    )


def test_no_title_is_no_title_however_it_is_spelled() -> None:
    assert layouts_match(
        [{"customLabel": "", "rows": []}], [{"label": None, "rows": []}]
    )


def test_an_absent_tab_mark_equals_a_false_one() -> None:
    assert layouts_match(
        [{"label": "A", "rows": [], "tabBreak": False}], [{"label": "A", "rows": []}]
    )


def test_a_tab_break_that_differs_is_a_difference() -> None:
    assert not layouts_match(
        [{"label": "A", "rows": [], "tabBreak": True}], [{"label": "A", "rows": []}]
    )


def test_a_panel_map_matches_when_what_is_declared_is_present() -> None:
    """The platform adds its own built-in panels, so the answer is a superset."""
    assert layouts_match(
        {"cDues": {"index": 1}},
        {"cDues": {"index": 1}, "activities": {"index": 0}},
    )


def test_a_panel_map_that_differs_on_a_declared_key_does_not_match() -> None:
    assert not layouts_match({"cDues": {"index": 1}}, {"cDues": {"index": 5}})


# --- panels, rows and columns -----------------------------------------------


def test_the_same_panels_match() -> None:
    assert layouts_match([_panel()], [_panel()])


def test_a_different_field_in_a_row_is_a_difference() -> None:
    assert not layouts_match(
        [_panel(fields=["name"])], [_panel(fields=["description"])]
    )


def test_a_cell_written_as_a_bare_name_matches_the_same_cell_as_an_object() -> None:
    assert layouts_match(
        [{"label": "A", "rows": [["name"]]}],
        [{"label": "A", "rows": [[{"name": "name"}]]}],
    )


def test_a_different_number_of_panels_is_a_difference() -> None:
    assert not layouts_match([_panel(), _panel("Second")], [_panel()])


def test_list_columns_compare_on_name_and_width() -> None:
    assert layouts_match(
        [{"name": "amount", "width": 20}], [{"name": "amount", "width": 20}]
    )
    assert not layouts_match(
        [{"name": "amount", "width": 20}], [{"name": "amount", "width": 30}]
    )


def test_a_layout_of_the_wrong_shape_does_not_match() -> None:
    assert not layouts_match([_panel()], {"cDues": {}})
    assert not layouts_match({"cDues": {}}, [_panel()])


# --- applying ---------------------------------------------------------------


def test_a_layout_already_as_declared_is_not_rewritten() -> None:
    client = FakeClient(live=[_panel()])
    outcome = apply_layout(client, "CEngagement", LayoutIntent("detail", [_panel()]))
    assert outcome.status == lay.SKIPPED
    assert "save" not in client.kinds


def test_a_layout_that_differs_is_written_whole() -> None:
    client = FakeClient(live=[_panel("Old")])
    body = [_panel("New")]
    outcome = apply_layout(client, "CEngagement", LayoutIntent("detail", body))
    assert outcome.status == lay.UPDATED
    assert ("save", "detail", body) in client.calls


def test_a_layout_the_instance_cannot_report_is_still_written() -> None:
    """A missing current layout is not a reason to leave the design unapplied."""
    client = FakeClient(live=None, get_status=404)
    outcome = apply_layout(client, "CEngagement", LayoutIntent("detail", [_panel()]))
    assert outcome.status == lay.UPDATED


def test_a_refused_write_is_reported_with_what_the_instance_said() -> None:
    client = FakeClient(live=[_panel("Old")])
    client.save_answers = [(400, {"message": "bad layout"})]
    outcome = apply_layout(client, "CEngagement", LayoutIntent("detail", [_panel()]))
    assert outcome.failed
    assert "400" in outcome.detail


def test_a_rejected_credential_stops_the_run() -> None:
    client = FakeClient(get_status=401)
    with pytest.raises(AuthenticationRejected):
        apply_layout(client, "CEngagement", LayoutIntent("detail", [_panel()]))


# --- what is refused, and why -----------------------------------------------


def test_a_portal_layout_is_refused_by_name() -> None:
    client = FakeClient()
    outcome = apply_layout(
        client, "CEngagement", LayoutIntent("detailPortal", [_panel()])
    )
    assert outcome.status == lay.REFUSED
    assert "portal" in outcome.detail
    assert outcome.manual_config
    assert client.calls == []


def test_a_layout_that_varies_by_role_is_refused_with_the_reason() -> None:
    client = FakeClient()
    outcome = apply_layout(
        client,
        "CEngagement",
        LayoutIntent("detail", [_panel()], for_roles=["Mentor"]),
    )
    assert outcome.status == lay.REFUSED
    assert "layout set" in outcome.detail
    assert client.calls == []


def test_a_layout_the_platform_does_not_have_is_refused() -> None:
    client = FakeClient()
    outcome = apply_layout(
        client, "CEngagement", LayoutIntent("dashboard", [_panel()])
    )
    assert outcome.status == lay.REFUSED
    assert "no layout by this name" in outcome.detail


# --- preview and batches ----------------------------------------------------


def test_preview_writes_nothing() -> None:
    client = FakeClient(live=[_panel("Old")])
    outcome = apply_layout(
        client, "CEngagement", LayoutIntent("detail", [_panel()]), preview=True
    )
    assert outcome.status == lay.PREVIEWED
    assert "save" not in client.kinds


def test_preview_still_reports_a_layout_already_as_declared() -> None:
    client = FakeClient(live=[_panel()])
    outcome = apply_layout(
        client, "CEngagement", LayoutIntent("detail", [_panel()]), preview=True
    )
    assert outcome.status == lay.SKIPPED


def test_every_declared_layout_is_attempted() -> None:
    client = FakeClient(live=[_panel("Old")])
    outcomes = apply_layouts(
        client,
        "CEngagement",
        [
            LayoutIntent("detail", [_panel()]),
            LayoutIntent("detailPortal", [_panel()]),
            LayoutIntent("list", [{"name": "name"}]),
        ],
    )
    assert [o.status for o in outcomes] == [lay.UPDATED, lay.REFUSED, lay.UPDATED]
