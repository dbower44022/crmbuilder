"""Tests for the activity-panel enablement pure transforms (PI-338 / REQ-379)."""

from espo_impl.core.activity_panel_manager import (
    ACTIVITY_PANELS,
    build_bottom_panels_detail_layout,
    merge_parent_entity_list,
    parent_list_contains,
)


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
