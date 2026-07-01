"""Tests for cross-file layout aggregation (PI-020 / REQ-403)."""

from __future__ import annotations

from espo_impl.core.layout_aggregator import aggregate_layouts
from espo_impl.core.models import (
    EntityAction,
    EntityDefinition,
    FieldDefinition,
    LayoutSpec,
    PanelSpec,
)


def _espo(name: str) -> str:
    # Native entities keep their name; custom get a C prefix (mirrors the real
    # mapping closely enough for grouping).
    return name if name in {"Account", "Contact"} else f"C{name}"


def _field(name: str) -> FieldDefinition:
    return FieldDefinition(name=name, label=name, type="varchar")


def _entity(name, panels, *, fields=(), layout_type="detail", action=EntityAction.NONE):
    return EntityDefinition(
        name=name,
        fields=[_field(f) for f in fields],
        action=action,
        layouts={layout_type: LayoutSpec(layout_type=layout_type, panels=list(panels))},
    )


def _panel(label, rows=None):
    return PanelSpec(label=label, rows=rows or [])


# -- the core merge ----------------------------------------------------------


def test_two_files_same_entity_merge_all_panels():
    mn = _entity("Account", [_panel("Client Profile")], fields=["clientType"])
    cr = _entity("Account", [_panel("Partner Profile")], fields=["partnerType"])
    result = aggregate_layouts(
        [("MN-Account.yaml", [mn]), ("CR-Account.yaml", [cr])], _espo
    )
    assert result.ok
    # Canonical = first alphabetically (CR-Account.yaml).
    cr_out = result.programs["CR-Account.yaml"][0]
    labels = [p.label for p in cr_out.layouts["detail"].panels]
    assert labels == ["Partner Profile", "Client Profile"]  # CR before MN
    # The other file's layout is stripped so it doesn't clobber.
    mn_out = result.programs["MN-Account.yaml"][0]
    assert "detail" not in mn_out.layouts


def test_merge_carries_field_union_for_cprefix():
    mn = _entity("Account", [_panel("Client")], fields=["clientType"])
    cr = _entity("Account", [_panel("Partner")], fields=["partnerType"])
    result = aggregate_layouts(
        [("MN-Account.yaml", [mn]), ("CR-Account.yaml", [cr])], _espo
    )
    canonical = result.programs["CR-Account.yaml"][0]
    assert canonical.layout_field_names == {"clientType", "partnerType"}


def test_ordering_is_file_alphabetical_then_declaration():
    a = _entity("Account", [_panel("A1"), _panel("A2")])
    b = _entity("Account", [_panel("B1")])
    result = aggregate_layouts(
        [("B-file.yaml", [b]), ("A-file.yaml", [a])], _espo
    )
    canonical = result.programs["A-file.yaml"][0]
    assert [p.label for p in canonical.layouts["detail"].panels] == ["A1", "A2", "B1"]


# -- conflict ----------------------------------------------------------------


def test_duplicate_panel_label_is_a_conflict():
    mn = _entity("Account", [_panel("Profile")])
    cr = _entity("Account", [_panel("Profile")])
    result = aggregate_layouts(
        [("MN-Account.yaml", [mn]), ("CR-Account.yaml", [cr])], _espo
    )
    assert not result.ok
    assert len(result.conflicts) == 1
    c = result.conflicts[0]
    assert c.entity == "Account" and c.label == "Profile"
    assert "Profile" in c.message()
    # On conflict the originals are handed back untouched (nothing merged/stripped).
    assert "detail" in result.programs["MN-Account.yaml"][0].layouts


# -- single-contributor + non-panel layouts are untouched --------------------


def test_single_file_layout_untouched():
    a = _entity("Account", [_panel("Only")])
    result = aggregate_layouts([("A.yaml", [a])], _espo)
    assert result.ok
    out = result.programs["A.yaml"][0]
    assert [p.label for p in out.layouts["detail"].panels] == ["Only"]
    assert out.layout_field_names is None  # no aggregation hint for a lone file


def test_different_entities_do_not_merge():
    acct = _entity("Account", [_panel("A")])
    contact = _entity("Contact", [_panel("C")])
    result = aggregate_layouts(
        [("F1.yaml", [acct]), ("F2.yaml", [contact])], _espo
    )
    assert result.ok
    assert [p.label for p in result.programs["F1.yaml"][0].layouts["detail"].panels] == ["A"]
    assert [p.label for p in result.programs["F2.yaml"][0].layouts["detail"].panels] == ["C"]


def test_delete_action_entities_ignored():
    live = _entity("Account", [_panel("Live")])
    gone = _entity("Account", [_panel("Gone")], action=EntityAction.DELETE)
    result = aggregate_layouts(
        [("A.yaml", [live]), ("B.yaml", [gone])], _espo
    )
    assert result.ok
    # Only the live contributor exists -> single contributor -> untouched.
    assert [p.label for p in result.programs["A.yaml"][0].layouts["detail"].panels] == ["Live"]


def test_list_layout_without_panels_not_merged():
    # A 'list' layout has columns, not panels — leave both as-is (no crash).
    a = EntityDefinition(
        name="Account", fields=[],
        layouts={"list": LayoutSpec(layout_type="list", panels=None)},
    )
    b = EntityDefinition(
        name="Account", fields=[],
        layouts={"list": LayoutSpec(layout_type="list", panels=None)},
    )
    result = aggregate_layouts([("A.yaml", [a]), ("B.yaml", [b])], _espo)
    assert result.ok
    assert "list" in result.programs["A.yaml"][0].layouts
    assert "list" in result.programs["B.yaml"][0].layouts
