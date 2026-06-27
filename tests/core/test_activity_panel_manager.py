"""Tests for the activity-panel enablement pure transforms (PI-338 / REQ-379)."""

from espo_impl.core.activity_panel_manager import (
    ACTIVITY_PANELS,
    ActivityPanelManager,
    build_bottom_panels_detail_layout,
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
