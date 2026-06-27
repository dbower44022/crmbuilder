"""Tests for the activity-panel enablement pure transforms (PI-338 / REQ-379)."""

from espo_impl.core.activity_panel_manager import (
    ACTIVITY_PANELS,
    ActivityPanelManager,
    build_bottom_panels_detail_layout,
    entity_links_complete,
    entity_panels_present,
    merge_client_activity_panels,
    merge_entity_activity_links,
    merge_parent_entity_list,
    parent_list_contains,
    union_parent_list,
)


class FakeClient:
    """Minimal EspoAdminClient stand-in driven by canned metadata + capture."""

    def __init__(self, metadata=None, save_status=200):
        self._metadata = metadata or {}
        self._save_status = save_status
        self.saved_layouts = []

    def get_metadata(self, key):
        if key in self._metadata:
            return 200, self._metadata[key]
        return 200, None

    def save_layout(self, entity, layout_type, payload):
        self.saved_layouts.append((entity, layout_type, payload))
        return self._save_status, {}


class TestBuildBottomPanelsDetailLayout:
    def test_enables_all_activity_panels_disabled_false(self):
        layout = build_bottom_panels_detail_layout()
        assert set(layout) == set(ACTIVITY_PANELS)
        for spec in layout.values():
            assert spec["disabled"] is False

    def test_indexes_are_sequential_and_ordered(self):
        layout = build_bottom_panels_detail_layout(
            panels=("activities", "history", "tasks"), start_index=4
        )
        assert layout["activities"]["index"] == 4
        assert layout["history"]["index"] == 5
        assert layout["tasks"]["index"] == 6

    def test_custom_panel_subset(self):
        layout = build_bottom_panels_detail_layout(panels=("activities",))
        assert set(layout) == {"activities"}


class TestMergeParentEntityList:
    def test_adds_entity_to_empty_holder(self):
        result = merge_parent_entity_list({}, "CEngagement")
        assert result["fields"]["parent"]["entityList"] == ["CEngagement"]

    def test_appends_preserving_existing(self):
        holder = {"fields": {"parent": {"entityList": ["Account", "Contact"]}}}
        result = merge_parent_entity_list(holder, "CEngagement")
        assert result["fields"]["parent"]["entityList"] == [
            "Account",
            "Contact",
            "CEngagement",
        ]

    def test_idempotent_no_duplicate(self):
        holder = {"fields": {"parent": {"entityList": ["CEngagement"]}}}
        result = merge_parent_entity_list(holder, "CEngagement")
        assert result["fields"]["parent"]["entityList"] == ["CEngagement"]

    def test_keeps_entity_type_list_in_sync_when_present(self):
        holder = {
            "fields": {
                "parent": {
                    "entityList": ["Account"],
                    "entityTypeList": ["Account"],
                }
            }
        }
        result = merge_parent_entity_list(holder, "CEngagement")
        assert result["fields"]["parent"]["entityList"] == ["Account", "CEngagement"]
        assert result["fields"]["parent"]["entityTypeList"] == [
            "Account",
            "CEngagement",
        ]

    def test_does_not_mutate_input(self):
        holder = {"fields": {"parent": {"entityList": ["Account"]}}}
        merge_parent_entity_list(holder, "CEngagement")
        assert holder["fields"]["parent"]["entityList"] == ["Account"]

    def test_preserves_other_holder_keys(self):
        holder = {
            "fields": {
                "parent": {"entityList": ["Account"]},
                "name": {"type": "varchar"},
            },
            "links": {"parent": {"type": "belongsToParent"}},
        }
        result = merge_parent_entity_list(holder, "CEngagement")
        assert result["fields"]["name"] == {"type": "varchar"}
        assert result["links"] == {"parent": {"type": "belongsToParent"}}


class TestParentListContains:
    def test_true_when_in_entity_list(self):
        holder = {"fields": {"parent": {"entityList": ["CEngagement"]}}}
        assert parent_list_contains(holder, "CEngagement") is True

    def test_true_when_only_in_entity_type_list(self):
        holder = {"fields": {"parent": {"entityTypeList": ["CEngagement"]}}}
        assert parent_list_contains(holder, "CEngagement") is True

    def test_false_when_absent(self):
        holder = {"fields": {"parent": {"entityList": ["Account"]}}}
        assert parent_list_contains(holder, "CEngagement") is False

    def test_false_on_empty(self):
        assert parent_list_contains({}, "CEngagement") is False


class TestUnionParentList:
    def test_appends_new_deduped(self):
        assert union_parent_list(["Account", "Contact"], ["CEngagement"]) == [
            "Account",
            "Contact",
            "CEngagement",
        ]

    def test_skips_existing(self):
        assert union_parent_list(["CEngagement"], ["CEngagement"]) == ["CEngagement"]

    def test_handles_empty_current(self):
        assert union_parent_list([], ["A", "B"]) == ["A", "B"]

    def test_does_not_mutate_current(self):
        current = ["Account"]
        union_parent_list(current, ["CEngagement"])
        assert current == ["Account"]


class TestActivityPanelManager:
    def _mgr(self, metadata=None, save_status=200):
        return ActivityPanelManager(FakeClient(metadata, save_status))

    def test_read_parent_list_returns_list(self):
        mgr = self._mgr(
            {"entityDefs.Meeting.fields.parent.entityList": ["Account", "CEngagement"]}
        )
        assert mgr.read_parent_list("Meeting") == ["Account", "CEngagement"]

    def test_read_parent_list_absent_key_empty(self):
        assert self._mgr().read_parent_list("Meeting") == []

    def test_is_registered_true_when_in_all_holders(self):
        md = {
            f"entityDefs.{h}.fields.parent.entityList": ["CEngagement"]
            for h in ("Meeting", "Call", "Task")
        }
        assert self._mgr(md).is_registered("CEngagement") is True

    def test_is_registered_false_when_missing_one_holder(self):
        md = {
            "entityDefs.Meeting.fields.parent.entityList": ["CEngagement"],
            "entityDefs.Call.fields.parent.entityList": ["CEngagement"],
            # Task missing CEngagement
            "entityDefs.Task.fields.parent.entityList": ["Account"],
        }
        assert self._mgr(md).is_registered("CEngagement") is False

    def test_enable_panels_layout_saves_enabled_layout(self):
        mgr = self._mgr()
        assert mgr.enable_panels_layout("CEngagement") is True
        assert len(mgr.client.saved_layouts) == 1
        entity, ltype, payload = mgr.client.saved_layouts[0]
        assert entity == "CEngagement"
        assert ltype == "bottomPanelsDetail"
        assert set(payload) == set(ACTIVITY_PANELS)
        assert all(spec["disabled"] is False for spec in payload.values())

    def test_enable_panels_layout_reports_failure(self):
        mgr = self._mgr(save_status=500)
        assert mgr.enable_panels_layout("CEngagement") is False

    def test_wait_until_registered_returns_true_immediately(self):
        md = {
            f"entityDefs.{h}.fields.parent.entityList": ["CEngagement"]
            for h in ("Meeting", "Call", "Task")
        }
        mgr = self._mgr(md)
        slept = []
        assert mgr.wait_until_registered(
            "CEngagement", sleep=slept.append
        ) is True
        assert slept == []  # already registered, no polling

    def test_wait_until_registered_polls_until_present(self):
        # Client that reports "not registered" for the first two checks,
        # then registered (simulates cache propagation lag after rebuild).
        class LaggyClient:
            def __init__(self):
                self.calls = 0

            def get_metadata(self, key):
                # is_registered short-circuits on the first missing holder, so a
                # failing attempt is one call. First two attempts miss (calls
                # 1,2 return Account); the third attempt onward registers.
                self.calls += 1
                registered = self.calls >= 3
                return 200, (["CEngagement"] if registered else ["Account"])

        mgr = ActivityPanelManager(LaggyClient())
        slept = []
        assert mgr.wait_until_registered(
            "CEngagement", timeout=10, interval=1, sleep=slept.append
        ) is True
        assert len(slept) == 2  # polled twice before success

    def test_wait_until_registered_times_out(self):
        md = {
            "entityDefs.Meeting.fields.parent.entityList": ["Account"],
            "entityDefs.Call.fields.parent.entityList": ["Account"],
            "entityDefs.Task.fields.parent.entityList": ["Account"],
        }
        mgr = self._mgr(md)
        slept = []
        assert mgr.wait_until_registered(
            "CEngagement", timeout=3, interval=1, sleep=slept.append
        ) is False


_PARENT_LINKS = {
    ln: {"foreign": "parent"} for ln in ("meetings", "calls", "tasks", "emails")
}


class TestMergeEntityActivityLinks:
    def test_adds_all_four_links_to_empty_def(self):
        result = merge_entity_activity_links({})
        links = result["links"]
        assert set(links) == {"meetings", "calls", "tasks", "emails"}
        for ln in ("meetings", "calls", "tasks", "emails"):
            assert links[ln]["foreign"] == "parent"
        # probe-verified shape: meetings/calls hasMany, tasks/emails hasChildren
        assert links["meetings"]["type"] == "hasMany"
        assert links["tasks"]["type"] == "hasChildren"
        assert links["emails"]["layoutRelationshipsDisabled"] is True

    def test_overwrites_miswired_link(self):
        # CInformationRequest's broken cParent link is corrected to parent.
        broken = {"links": {"meetings": {"type": "hasMany", "foreign": "cParent"}}}
        result = merge_entity_activity_links(broken)
        assert result["links"]["meetings"]["foreign"] == "parent"

    def test_drop_links_removes_before_adding(self):
        broken = {"links": {"meetings": {"foreign": "cParent"}, "keepMe": {"x": 1}}}
        result = merge_entity_activity_links(broken, drop_links=("meetings",))
        assert result["links"]["meetings"]["foreign"] == "parent"  # re-added clean
        assert result["links"]["keepMe"] == {"x": 1}  # unrelated link preserved

    def test_does_not_mutate_input(self):
        src = {"links": {}}
        merge_entity_activity_links(src)
        assert src == {"links": {}}


class TestMergeClientActivityPanels:
    def test_adds_side_and_bottom_panels(self):
        result = merge_client_activity_panels({})
        side = [p["name"] for p in result["sidePanels"]["detail"]]
        bottom = [p["name"] for p in result["bottomPanels"]["detail"]]
        # side panels are what render — all three
        assert side == ["activities", "history", "tasks"]
        # bottom counterparts shipped disabled (mirror a native BasePlus entity)
        assert bottom == ["activities", "history"]
        assert all(p["disabled"] is True for p in result["bottomPanels"]["detail"])

    def test_preserves_existing_custom_panel(self):
        existing = {"bottomPanels": {"detail": [{"name": "reportPanelX"}]}}
        result = merge_client_activity_panels(existing)
        bottom = [p["name"] for p in result["bottomPanels"]["detail"]]
        assert bottom == ["reportPanelX", "activities", "history"]
        assert [p["name"] for p in result["sidePanels"]["detail"]] == [
            "activities", "history", "tasks",
        ]

    def test_idempotent_no_duplicate(self):
        once = merge_client_activity_panels({})
        twice = merge_client_activity_panels(once)
        assert [p["name"] for p in twice["sidePanels"]["detail"]] == [
            "activities", "history", "tasks",
        ]


class TestEntityPanelsPresent:
    def test_true_when_side_panels_present(self):
        cd = {"sidePanels": {"detail": [
            {"name": "activities"}, {"name": "history"}, {"name": "tasks"},
        ]}}
        assert entity_panels_present(cd) is True

    def test_false_when_panel_missing(self):
        cd = {"sidePanels": {"detail": [{"name": "activities"}, {"name": "history"}]}}
        assert entity_panels_present(cd) is False

    def test_false_when_only_bottom_panels(self):
        # panels in bottomPanels (not sidePanels) do not render -> not present
        cd = {"bottomPanels": {"detail": [
            {"name": "activities"}, {"name": "history"}, {"name": "tasks"},
        ]}}
        assert entity_panels_present(cd) is False

    def test_false_for_empty(self):
        assert entity_panels_present({}) is False


class TestEntityLinksComplete:
    def test_true_when_all_parent_wired(self):
        assert entity_links_complete(_PARENT_LINKS) is True

    def test_false_when_link_missing(self):
        partial = dict(_PARENT_LINKS)
        del partial["tasks"]
        assert entity_links_complete(partial) is False

    def test_false_when_link_cparent_wired(self):
        bad = dict(_PARENT_LINKS)
        bad["meetings"] = {"foreign": "cParent"}
        assert entity_links_complete(bad) is False

    def test_false_for_non_dict(self):
        assert entity_links_complete(None) is False


class TestHasActivityLinks:
    def _mgr(self, md):
        return ActivityPanelManager(FakeClient(md))

    def test_true_when_links_parent_wired(self):
        mgr = self._mgr({"entityDefs.CEngagement.links": _PARENT_LINKS})
        assert mgr.has_activity_links("CEngagement") is True

    def test_false_when_links_absent(self):
        mgr = self._mgr({})  # get_metadata returns (200, None)
        assert mgr.has_activity_links("CEngagement") is False

    def test_false_when_cparent_wired(self):
        bad = dict(_PARENT_LINKS)
        bad["calls"] = {"foreign": "cParent"}
        mgr = self._mgr({"entityDefs.CInformationRequest.links": bad})
        assert mgr.has_activity_links("CInformationRequest") is False


class TestHasActivityPanels:
    def _mgr(self, md):
        return ActivityPanelManager(FakeClient(md))

    def test_true_when_side_panels_present(self):
        cd = {"sidePanels": {"detail": [
            {"name": "activities"}, {"name": "history"}, {"name": "tasks"},
        ]}}
        mgr = self._mgr({"clientDefs.CEngagement": cd})
        assert mgr.has_activity_panels("CEngagement") is True

    def test_false_when_clientdefs_absent(self):
        mgr = self._mgr({})  # get_metadata returns (200, None)
        assert mgr.has_activity_panels("CEngagement") is False

    def test_false_when_only_bottom_panels(self):
        cd = {"bottomPanels": {"detail": [
            {"name": "activities"}, {"name": "history"}, {"name": "tasks"},
        ]}}
        mgr = self._mgr({"clientDefs.CEngagement": cd})
        assert mgr.has_activity_panels("CEngagement") is False
