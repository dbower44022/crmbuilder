"""Live-capture tests for the relationship / layout / role-team paths.

Offline, fake-client. These verify that ``LiveStateCapture`` projects the Audit
machinery's discovery into exactly the shapes ``diff_relationships`` /
``diff_layouts`` / ``diff_roles`` + ``diff_teams`` consume. End-to-end against the
live CBM instance is verified separately (as the field path was).
"""
from __future__ import annotations

from espo_impl.core.reconcile.live_state import EntitySpec, LiveStateCapture


class _FakeClient:
    """A read-only fake exposing only the endpoints the capture paths call."""

    def __init__(self, *, links=None, i18n=None, layouts=None, roles=None, teams=None):
        self._links = links or {}
        self._i18n = i18n or {}
        self._layouts = layouts or {}
        self._roles = roles
        self._teams = teams

    def get_all_links(self, espo_name):
        return (200, self._links.get(espo_name, {}))

    def get_i18n(self):
        return (200, self._i18n)

    def get_layout(self, espo_name, layout_type):
        return self._layouts.get((espo_name, layout_type), (200, False))

    def get_roles(self):
        return (200, {"list": self._roles}) if self._roles is not None else (500, None)

    def get_teams(self):
        return (200, {"list": self._teams}) if self._teams is not None else (500, None)


# --------------------------------------------------------------------------- #
# relationships
# --------------------------------------------------------------------------- #
def test_capture_relationships_keyed_by_link_with_props():
    client = _FakeClient(
        links={
            "CEngagement": {
                "mentor": {"entity": "Contact", "foreign": "engagementsAsMentor",
                           "type": "belongsTo", "audited": True},
            },
            "Contact": {
                "engagementsAsMentor": {"entity": "CEngagement", "foreign": "mentor",
                                        "type": "hasMany"},
            },
        },
        i18n={
            "CEngagement": {"links": {"mentor": "Mentor"}},
            "Contact": {"links": {"engagementsAsMentor": "Engagements (Mentor)"}},
        },
    )
    cap = LiveStateCapture(client)

    # Engagement first so the manyToOne (belongsTo) side wins dedup.
    live, warnings = cap.capture_relationships([
        EntitySpec("Engagement", "CEngagement", "Base"),
        EntitySpec("Contact", "Contact", "Person"),
    ])

    assert warnings == []
    rel = live["Engagement"]["mentor"]
    assert rel["link_type"] == "manyToOne"
    assert rel["entity_foreign"] == "Contact"
    assert rel["link_foreign"] == "engagementsAsMentor"
    assert rel["label"] == "Mentor"
    assert rel["label_foreign"] == "Engagements (Mentor)"
    assert rel["audited"] is True


# --------------------------------------------------------------------------- #
# layouts
# --------------------------------------------------------------------------- #
def test_capture_layouts_skips_falsy_and_keys_by_type():
    client = _FakeClient(layouts={
        ("Contact", "list"): (200, [{"name": "name"}]),
        ("Contact", "detail"): (200, False),          # derived -> skipped
        ("Contact", "filters"): (200, ["lastName"]),
    })
    cap = LiveStateCapture(client)

    live, warnings = cap.capture_layouts(
        [EntitySpec("Contact", "Contact", "Person")],
        layout_types=["list", "detail", "filters"],
    )

    assert warnings == []
    assert live["Contact"] == {"list": [{"name": "name"}], "filters": ["lastName"]}


def test_capture_layouts_warns_on_http_error():
    client = _FakeClient(layouts={("Contact", "list"): (500, None)})
    cap = LiveStateCapture(client)

    live, warnings = cap.capture_layouts(
        [EntitySpec("Contact", "Contact", "Person")], layout_types=["list"]
    )

    assert "Contact" not in live  # nothing captured
    assert len(warnings) == 1 and "500" in warnings[0]


# --------------------------------------------------------------------------- #
# roles / teams
# --------------------------------------------------------------------------- #
def test_capture_roles_teams_reverse_maps_scope_and_perms():
    client = _FakeClient(
        roles=[{
            "name": "Mentor",
            "description": "Mentor role",
            "data": {"Contact": {"create": "yes", "read": "all",
                                 "edit": "own", "delete": "no", "stream": "no"}},
            "assignmentPermission": "all",
            "userPermission": "no",
            "exportPermission": "yes",
            "massUpdatePermission": "no",
            "portalPermission": "no",
        }],
        teams=[{"name": "Mentors", "description": "The mentors team"}],
    )
    cap = LiveStateCapture(client)

    roles, teams, warnings = cap.capture_roles_teams()

    assert roles["Mentor"].description == "Mentor role"
    assert roles["Mentor"].scope_access["Contact"].create is True
    assert roles["Mentor"].scope_access["Contact"].read == "all"
    assert roles["Mentor"].system_permissions.export is True
    assert teams["Mentors"].description == "The mentors team"
    assert warnings == []
