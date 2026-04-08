"""Tests for automation.ui.navigation — drill-down stack and breadcrumb logic."""

import pytest

from automation.ui.navigation import NavEntry, NavigationStack, build_breadcrumb_text


class TestNavigationStack:

    def test_initial_depth(self):
        root = NavEntry("Dashboard", "dashboard")
        stack = NavigationStack(root)
        assert stack.depth == 1

    def test_current_is_root(self):
        root = NavEntry("Dashboard", "dashboard")
        stack = NavigationStack(root)
        assert stack.current is root

    def test_push_increases_depth(self):
        root = NavEntry("Dashboard", "dashboard")
        stack = NavigationStack(root)
        stack.push(NavEntry("Work Item", "work_item", {"id": 1}))
        assert stack.depth == 2

    def test_push_changes_current(self):
        root = NavEntry("Dashboard", "dashboard")
        stack = NavigationStack(root)
        child = NavEntry("Work Item", "work_item", {"id": 1})
        stack.push(child)
        assert stack.current is child

    def test_pop_returns_to_root(self):
        root = NavEntry("Dashboard", "dashboard")
        stack = NavigationStack(root)
        child = NavEntry("Work Item", "work_item")
        stack.push(child)
        popped = stack.pop()
        assert popped is child
        assert stack.current is root

    def test_pop_at_root_returns_none(self):
        root = NavEntry("Dashboard", "dashboard")
        stack = NavigationStack(root)
        assert stack.pop() is None
        assert stack.depth == 1

    def test_pop_to_level_truncates(self):
        root = NavEntry("Dashboard", "dashboard")
        stack = NavigationStack(root)
        stack.push(NavEntry("Level 2", "l2"))
        stack.push(NavEntry("Level 3", "l3"))
        stack.push(NavEntry("Level 4", "l4"))
        assert stack.depth == 4

        stack.pop_to_level(2)
        assert stack.depth == 2
        assert stack.current.label == "Level 2"

    def test_pop_to_level_1_is_root(self):
        root = NavEntry("Dashboard", "dashboard")
        stack = NavigationStack(root)
        stack.push(NavEntry("Child", "child"))
        stack.pop_to_level(1)
        assert stack.depth == 1
        assert stack.current is root

    def test_pop_to_level_out_of_range_raises(self):
        root = NavEntry("Dashboard", "dashboard")
        stack = NavigationStack(root)
        with pytest.raises(ValueError):
            stack.pop_to_level(0)
        with pytest.raises(ValueError):
            stack.pop_to_level(5)

    def test_breadcrumbs_returns_all_entries(self):
        root = NavEntry("Dashboard", "dashboard")
        stack = NavigationStack(root)
        child = NavEntry("Work Item", "work_item")
        stack.push(child)
        crumbs = stack.breadcrumbs
        assert len(crumbs) == 2
        assert crumbs[0].label == "Dashboard"
        assert crumbs[1].label == "Work Item"

    def test_show_breadcrumbs_false_at_root(self):
        root = NavEntry("Dashboard", "dashboard")
        stack = NavigationStack(root)
        assert stack.show_breadcrumbs is False

    def test_show_breadcrumbs_true_with_children(self):
        root = NavEntry("Dashboard", "dashboard")
        stack = NavigationStack(root)
        stack.push(NavEntry("Child", "child"))
        assert stack.show_breadcrumbs is True

    def test_reset_clears_to_root(self):
        root = NavEntry("Dashboard", "dashboard")
        stack = NavigationStack(root)
        stack.push(NavEntry("A", "a"))
        stack.push(NavEntry("B", "b"))
        stack.reset()
        assert stack.depth == 1
        assert stack.current is root

    def test_view_data_preserved(self):
        root = NavEntry("Dashboard", "dashboard")
        stack = NavigationStack(root)
        data = {"id": 42, "name": "Test"}
        stack.push(NavEntry("Item", "work_item", data))
        assert stack.current.view_data == data

    def test_breadcrumbs_is_copy(self):
        root = NavEntry("Dashboard", "dashboard")
        stack = NavigationStack(root)
        crumbs = stack.breadcrumbs
        crumbs.append(NavEntry("Extra", "extra"))
        assert stack.depth == 1  # Original unaffected


class TestBuildBreadcrumbText:

    def test_single_entry(self):
        root = NavEntry("Dashboard", "dashboard")
        stack = NavigationStack(root)
        assert build_breadcrumb_text(stack) == "Dashboard"

    def test_multiple_entries(self):
        root = NavEntry("Dashboard", "dashboard")
        stack = NavigationStack(root)
        stack.push(NavEntry("Entity PRD: Contact", "work_item"))
        assert build_breadcrumb_text(stack) == "Dashboard > Entity PRD: Contact"

    def test_custom_separator(self):
        root = NavEntry("Dashboard", "dashboard")
        stack = NavigationStack(root)
        stack.push(NavEntry("Child", "child"))
        assert build_breadcrumb_text(stack, " / ") == "Dashboard / Child"

    def test_three_levels(self):
        root = NavEntry("Dashboard", "dashboard")
        stack = NavigationStack(root)
        stack.push(NavEntry("Work Item", "work_item"))
        stack.push(NavEntry("Dependency", "dep"))
        result = build_breadcrumb_text(stack)
        assert result == "Dashboard > Work Item > Dependency"
