"""Tests for field comparison logic."""

from espo_impl.core.comparator import FieldComparator, FieldDifference
from espo_impl.core.models import FieldDefinition


def make_spec(**kwargs) -> FieldDefinition:
    defaults = {"name": "testField", "type": "varchar", "label": "Test"}
    defaults.update(kwargs)
    return FieldDefinition(**defaults)


def test_exact_match():
    spec = make_spec(type="varchar", label="Test", required=False)
    current = {"type": "varchar", "label": "Test", "required": False}
    result = FieldComparator().compare(spec, current)
    assert result.matches is True
    assert result.differences == []
    assert result.type_conflict is False


def test_label_differs():
    spec = make_spec(label="New Label")
    current = {"type": "varchar", "label": "Old Label"}
    result = FieldComparator().compare(spec, current)
    assert result.matches is False
    assert "label" in result.differences


def test_multiple_differences():
    spec = make_spec(label="New", required=True, audited=True)
    current = {"type": "varchar", "label": "Old", "required": False, "audited": False}
    result = FieldComparator().compare(spec, current)
    assert result.matches is False
    assert "label" in result.differences
    assert "required" in result.differences
    assert "audited" in result.differences


def test_type_conflict():
    spec = make_spec(type="varchar")
    current = {"type": "text", "label": "Test"}
    result = FieldComparator().compare(spec, current)
    assert result.matches is False
    assert result.type_conflict is True
    assert "type" in result.differences


def test_enum_options_differ():
    spec = make_spec(
        type="enum",
        options=["A", "B", "C"],
        translatedOptions={"A": "Alpha", "B": "Beta", "C": "Charlie"},
    )
    current = {
        "type": "enum",
        "label": "Test",
        "options": ["A", "B"],
        "translatedOptions": {"A": "Alpha", "B": "Beta"},
    }
    result = FieldComparator().compare(spec, current)
    assert result.matches is False
    assert "options" in result.differences
    assert "translatedOptions" in result.differences


def test_enum_options_order_matters():
    spec = make_spec(type="enum", options=["A", "B", "C"])
    current = {"type": "enum", "label": "Test", "options": ["C", "B", "A"]}
    result = FieldComparator().compare(spec, current)
    assert result.matches is False
    assert "options" in result.differences


def test_detailed_type_conflict_names_both_types():
    spec = make_spec(type="int")
    current = {"type": "float", "label": "Test"}
    result = FieldComparator().compare(spec, current)
    assert result.type_conflict is True
    assert len(result.detailed) == 1
    diff = result.detailed[0]
    assert isinstance(diff, FieldDifference)
    assert diff.property == "type"
    assert diff.expected == "int"
    assert diff.actual == "float"
    assert "'int'" in diff.message
    assert "'float'" in diff.message
    assert "'int'" in result.detail_text


def test_detailed_scalar_diff_names_both_values():
    spec = make_spec(label="New Label")
    current = {"type": "varchar", "label": "Old Label"}
    result = FieldComparator().compare(spec, current)
    diff = next(d for d in result.detailed if d.property == "label")
    assert diff.expected == "New Label"
    assert diff.actual == "Old Label"
    assert "New Label" in diff.message
    assert "Old Label" in diff.message


def test_detailed_options_reports_missing_and_extra():
    spec = make_spec(type="enum", options=["A", "B", "C"])
    current = {"type": "enum", "label": "Test", "options": ["A", "B", "D"]}
    result = FieldComparator().compare(spec, current)
    diff = next(d for d in result.detailed if d.property == "options")
    # C is in YAML but not deployed; D is deployed but not in YAML.
    assert "missing from deployed: [C]" in diff.message
    assert "extra in deployed: [D]" in diff.message


def test_detailed_options_reports_order_only_difference():
    spec = make_spec(type="enum", options=["A", "B", "C"])
    current = {"type": "enum", "label": "Test", "options": ["C", "B", "A"]}
    result = FieldComparator().compare(spec, current)
    diff = next(d for d in result.detailed if d.property == "options")
    assert "different order" in diff.message


def test_unspecified_optional_fields_do_not_trigger_diff():
    spec = make_spec(type="varchar", label="Test")
    current = {
        "type": "varchar",
        "label": "Test",
        "required": True,
        "audited": True,
        "readOnly": True,
    }
    result = FieldComparator().compare(spec, current)
    assert result.matches is True
    assert result.differences == []


def test_enum_style_differs():
    spec = make_spec(
        type="enum",
        options=["Active", "Inactive"],
        style={"Active": "success", "Inactive": "danger"},
    )
    current = {
        "type": "enum",
        "label": "Test",
        "options": ["Active", "Inactive"],
        "style": {"Active": "success", "Inactive": None},
    }
    result = FieldComparator().compare(spec, current)
    assert result.matches is False
    assert "style" in result.differences


def test_default_value_differs():
    spec = make_spec(default="hello")
    current = {"type": "varchar", "label": "Test", "default": "world"}
    result = FieldComparator().compare(spec, current)
    assert result.matches is False
    assert "default" in result.differences


def test_min_value_differs():
    spec = make_spec(type="int", min=0, max=10)
    current = {"type": "int", "label": "Test", "min": 1, "max": 10}
    result = FieldComparator().compare(spec, current)
    assert result.matches is False
    assert "min" in result.differences
    assert "max" not in result.differences


def test_max_length_differs():
    spec = make_spec(type="varchar", maxLength=100)
    current = {"type": "varchar", "label": "Test", "maxLength": 255}
    result = FieldComparator().compare(spec, current)
    assert result.matches is False
    assert "maxLength" in result.differences


def test_min_max_match():
    spec = make_spec(type="int", min=0, max=10)
    current = {"type": "int", "label": "Test", "min": 0, "max": 10}
    result = FieldComparator().compare(spec, current)
    assert result.matches is True


def test_foreign_field_matches():
    spec = make_spec(
        type="foreign",
        label="Partner",
        link="partner",
        foreign_field="name",
    )
    current = {
        "type": "foreign",
        "label": "Partner",
        "link": "partner",
        "field": "name",
    }
    result = FieldComparator().compare(spec, current)
    assert result.matches is True
    assert result.differences == []


def test_foreign_field_drift_on_link():
    spec = make_spec(
        type="foreign",
        label="Partner",
        link="partner",
        foreign_field="name",
    )
    current = {
        "type": "foreign",
        "label": "Partner",
        "link": "primaryPartner",
        "field": "name",
    }
    result = FieldComparator().compare(spec, current)
    assert result.matches is False
    assert "link" in result.differences


def test_foreign_field_drift_on_source_field():
    spec = make_spec(
        type="foreign",
        label="Partner",
        link="partner",
        foreign_field="name",
    )
    current = {
        "type": "foreign",
        "label": "Partner",
        "link": "partner",
        "field": "displayName",
    }
    result = FieldComparator().compare(spec, current)
    assert result.matches is False
    assert "field" in result.differences


# --- attribute-level unknown (PI-409 / REQ-491) ------------------------------


def _spec(**over):
    from espo_impl.core.models import FieldDefinition

    base = {"name": "phone", "type": "varchar", "label": "Phone"}
    base.update(over)
    return FieldDefinition(**base)


def test_an_unset_spec_property_is_recorded_not_skipped():
    """The first retired skip rule: a property the YAML leaves unset is an
    unknown naming why — never omitted, never a difference."""
    from espo_impl.core.comparator import FieldComparator

    result = FieldComparator().compare(
        _spec(maxLength=None), {"type": "varchar", "maxLength": 100}
    )
    unknown = next(u for u in result.unknowns if u.property == "maxLength")
    assert "declares no value" in unknown.message
    assert "maxLength" not in result.differences
    assert result.conclusive is False


def test_an_api_unreturned_property_is_recorded_not_skipped():
    """The second retired skip rule: a compared property the API did not
    return is unknown naming why — never treated as matching."""
    from espo_impl.core.comparator import FieldComparator

    result = FieldComparator().compare(
        _spec(label="Phone"), {"type": "varchar"}
    )
    unknown = next(u for u in result.unknowns if u.property == "label")
    assert "did not return" in unknown.message
    assert result.conclusive is False


def test_matches_keeps_its_deploy_meaning_while_conclusive_says_the_truth():
    """``matches`` still means "nothing declared differs" (the deploy CHECK);
    ``conclusive`` is what a conformance consumer must consult (REQ-491)."""
    from espo_impl.core.comparator import FieldComparator

    result = FieldComparator().compare(
        _spec(), {"type": "varchar"}
    )
    assert result.matches is True
    assert result.conclusive is False


def test_a_fully_answered_comparison_is_conclusive():
    from espo_impl.core.comparator import FieldComparator
    from espo_impl.core.comparator import COMMON_PROPERTIES

    spec = _spec(
        **{p: "x" for p in COMMON_PROPERTIES if p not in ("type",)}
    )
    current = {"type": "varchar", **{p: "x" for p in COMMON_PROPERTIES}}
    result = FieldComparator().compare(spec, current)
    assert result.conclusive is True
    assert result.matches is True
