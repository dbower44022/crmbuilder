"""The scope picker groups engagements under client headings (PI-512 /
REQ-589, DEC-1092), and the top strip shows client then engagement. The two
widgets are shell furniture (the sanctioned shared edits); their client
behaviour is tested here beside the package that provides the clients."""

from __future__ import annotations

from datetime import UTC, datetime

from crmbuilder_v2.access.engagement_models import Engagement, EngagementStatus
from crmbuilder_v2.ui.active_engagement_context import ActiveEngagementContext
from crmbuilder_v2.ui.widgets.engagement_picker import (
    NO_CLIENT_HEADING,
    EngagementPicker,
    group_engagements_by_client,
)
from crmbuilder_v2.ui.widgets.engagement_top_strip import EngagementTopStrip
from PySide6.QtWidgets import QLabel


def _record(identifier: str, name: str, status: str = "active") -> dict:
    return {
        "engagement_identifier": identifier,
        "engagement_code": identifier.replace("-", ""),
        "engagement_name": name,
        "engagement_status": status,
        "engagement_last_opened_at": None,
        "engagement_deleted_at": None,
    }


def _client(identifier: str, name: str, engagements: list[str]) -> dict:
    return {
        "client_identifier": identifier,
        "client_name": name,
        "engagements": engagements,
        "client_deleted_at": None,
    }


_ENGAGEMENTS = [
    _record("ENG-001", "CRMBuilder v2"),
    _record("ENG-002", "Cleveland Business Mentoring"),
    _record("ENG-003", "ADO E2E Sandbox"),
    _record("ENG-004", "CBM Mentoring Custom App", status="paused"),
    _record("ENG-006", "Rochester NY Test Instance"),
]
_CLIENTS = [
    _client("CLI-002", "CRMBuilder", ["ENG-001"]),
    _client("CLI-001", "Cleveland Business Mentors", ["ENG-002", "ENG-004"]),
]


def test_grouping_puts_each_engagement_under_its_client_and_no_client_last():
    live = [r for r in _ENGAGEMENTS if r["engagement_status"] == "active"]
    non_live = [r for r in _ENGAGEMENTS if r["engagement_status"] != "active"]
    groups = group_engagements_by_client(live, non_live, _CLIENTS)
    headings = [h for h, _ in groups]
    assert headings == ["Cleveland Business Mentors", "CRMBuilder", NO_CLIENT_HEADING]
    members = {h: [(r["engagement_identifier"], muted) for r, muted in m] for h, m in groups}
    assert members["Cleveland Business Mentors"] == [("ENG-002", False), ("ENG-004", True)]
    assert members["CRMBuilder"] == [("ENG-001", False)]
    assert members[NO_CLIENT_HEADING] == [("ENG-003", False), ("ENG-006", False)]


def test_chapter_engagement_appears_once():
    clients = [
        _client("CLI-001", "Alpha", ["ENG-002"]),
        _client("CLI-002", "Beta", ["ENG-002"]),
    ]
    groups = group_engagements_by_client([_record("ENG-002", "Shared")], [], clients)
    assert [(h, [r["engagement_identifier"] for r, _ in m]) for h, m in groups] == [
        ("Alpha", ["ENG-002"])
    ]


def test_picker_renders_headings_and_rows_when_clients_given(qtbot, qapp):
    picker = EngagementPicker(_ENGAGEMENTS, "ENG-001", clients=_CLIENTS)
    qtbot.addWidget(picker)
    headings = [w.property("group_heading") for w in picker.findChildren(QLabel) if w.property("group_heading")]
    assert headings == ["Cleveland Business Mentors", "CRMBuilder", NO_CLIENT_HEADING]
    identifiers = [b.property("engagement_identifier") for b in picker._rows]
    assert identifiers == ["ENG-002", "ENG-004", "ENG-001", "ENG-003", "ENG-006"]


def test_picker_without_clients_is_the_flat_list(qtbot, qapp):
    picker = EngagementPicker(_ENGAGEMENTS, "ENG-001")
    qtbot.addWidget(picker)
    assert not [w for w in picker.findChildren(QLabel) if w.property("group_heading")]
    assert len(picker._rows) == 5


def _engagement(identifier="ENG-002", code="CBM", name="Cleveland Business Mentoring"):
    now = datetime.now(UTC)
    return Engagement(
        engagement_identifier=identifier,
        engagement_code=code,
        engagement_name=name,
        engagement_purpose="p",
        engagement_status=EngagementStatus.ACTIVE,
        engagement_last_opened_at=None,
        engagement_created_at=now,
        engagement_updated_at=now,
        engagement_deleted_at=None,
    )


def test_top_strip_names_the_application_and_its_defining_client(qtbot, qapp):
    context = ActiveEngagementContext()
    context.set_engagement(_engagement())
    strip = EngagementTopStrip(
        context,
        client_name_lookup=lambda ident: "Cleveland Business Mentors" if ident == "ENG-002" else None,
    )
    qtbot.addWidget(strip)
    text = strip._label.text()
    # PI-580: "Name (CODE) · defined by Client".
    assert "Cleveland Business Mentoring" in text and "(CBM)" in text
    assert "defined by" in text and "Cleveland Business Mentors" in text
    assert text.index("(CBM)") < text.index("defined by")


def test_top_strip_shows_the_application_alone_without_client_or_on_failure(qtbot, qapp):
    context = ActiveEngagementContext()
    context.set_engagement(_engagement())
    strip = EngagementTopStrip(context, client_name_lookup=lambda _ident: None)
    qtbot.addWidget(strip)
    assert "defined by" not in strip._label.text()

    def _boom(_ident):
        raise RuntimeError("store unreachable")

    strip = EngagementTopStrip(context, client_name_lookup=_boom)
    qtbot.addWidget(strip)
    assert "defined by" not in strip._label.text()
    assert "Cleveland Business Mentoring" in strip._label.text()
