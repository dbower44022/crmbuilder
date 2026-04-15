"""Tests for formula parsing, validation, and rendering."""

import sys
from textwrap import dedent
from unittest.mock import MagicMock

import pytest

from espo_impl.core.config_loader import ConfigLoader
from espo_impl.core.formula_parser import (
    BinaryOp,
    FieldRef,
    NumberLiteral,
    extract_field_refs,
    parse_arithmetic,
    render_arithmetic,
)

# Stub PySide6 to allow importing FieldManager in environments without Qt
if "PySide6" not in sys.modules:
    _pyside6_mock = MagicMock()
    sys.modules["PySide6"] = _pyside6_mock
    sys.modules["PySide6.QtWidgets"] = _pyside6_mock
    sys.modules["PySide6.QtCore"] = _pyside6_mock
    sys.modules["PySide6.QtGui"] = _pyside6_mock

from espo_impl.core.field_manager import FieldManager  # noqa: E402


@pytest.fixture
def loader():
    return ConfigLoader()


# ======================================================================
# Arithmetic parser tests
# ======================================================================


class TestParseArithmetic:
    """Tests for the arithmetic expression parser."""

    def test_single_field(self):
        node = parse_arithmetic("fieldA")
        assert isinstance(node, FieldRef)
        assert node.name == "fieldA"

    def test_single_number_int(self):
        node = parse_arithmetic("42")
        assert isinstance(node, NumberLiteral)
        assert node.value == 42

    def test_single_number_float(self):
        node = parse_arithmetic("3.14")
        assert isinstance(node, NumberLiteral)
        assert node.value == 3.14

    def test_simple_addition(self):
        node = parse_arithmetic("a + b")
        assert isinstance(node, BinaryOp)
        assert node.op == "+"
        assert isinstance(node.left, FieldRef)
        assert node.left.name == "a"
        assert isinstance(node.right, FieldRef)
        assert node.right.name == "b"

    def test_simple_subtraction(self):
        node = parse_arithmetic("x - y")
        assert isinstance(node, BinaryOp)
        assert node.op == "-"

    def test_simple_multiplication(self):
        node = parse_arithmetic("x * y")
        assert isinstance(node, BinaryOp)
        assert node.op == "*"

    def test_simple_division(self):
        node = parse_arithmetic("x / y")
        assert isinstance(node, BinaryOp)
        assert node.op == "/"

    def test_precedence_mul_over_add(self):
        """a + b * c should parse as a + (b * c)."""
        node = parse_arithmetic("a + b * c")
        assert isinstance(node, BinaryOp)
        assert node.op == "+"
        assert isinstance(node.left, FieldRef)
        assert node.left.name == "a"
        assert isinstance(node.right, BinaryOp)
        assert node.right.op == "*"

    def test_precedence_div_over_sub(self):
        """a - b / c should parse as a - (b / c)."""
        node = parse_arithmetic("a - b / c")
        assert isinstance(node, BinaryOp)
        assert node.op == "-"
        assert isinstance(node.right, BinaryOp)
        assert node.right.op == "/"

    def test_parentheses_override_precedence(self):
        """(a + b) * c should parse as (a + b) * c."""
        node = parse_arithmetic("(a + b) * c")
        assert isinstance(node, BinaryOp)
        assert node.op == "*"
        assert isinstance(node.left, BinaryOp)
        assert node.left.op == "+"

    def test_nested_parentheses(self):
        node = parse_arithmetic("((a + b)) * c")
        assert isinstance(node, BinaryOp)
        assert node.op == "*"
        assert isinstance(node.left, BinaryOp)
        assert node.left.op == "+"

    def test_mixed_fields_and_numbers(self):
        node = parse_arithmetic("fieldA * 2 + 10")
        assert isinstance(node, BinaryOp)
        assert node.op == "+"
        assert isinstance(node.right, NumberLiteral)
        assert node.right.value == 10

    def test_complex_expression(self):
        node = parse_arithmetic("a + b * c - d / 2")
        # Should parse as: ((a + (b * c)) - (d / 2))
        assert isinstance(node, BinaryOp)
        assert node.op == "-"

    def test_error_empty_expression(self):
        with pytest.raises(ValueError, match="must not be empty"):
            parse_arithmetic("")

    def test_error_whitespace_only(self):
        with pytest.raises(ValueError, match="must not be empty"):
            parse_arithmetic("   ")

    def test_error_unbalanced_open_paren(self):
        with pytest.raises(ValueError):
            parse_arithmetic("(a + b")

    def test_error_unbalanced_close_paren(self):
        with pytest.raises(ValueError):
            parse_arithmetic("a + b)")

    def test_error_trailing_operator(self):
        with pytest.raises(ValueError):
            parse_arithmetic("a +")

    def test_error_leading_operator(self):
        with pytest.raises(ValueError):
            parse_arithmetic("+ a")

    def test_error_unknown_character(self):
        with pytest.raises(ValueError, match="Unexpected character"):
            parse_arithmetic("a & b")

    def test_error_double_operator(self):
        with pytest.raises(ValueError):
            parse_arithmetic("a + * b")


class TestExtractFieldRefs:
    """Tests for field reference extraction."""

    def test_single_field(self):
        node = parse_arithmetic("x")
        assert extract_field_refs(node) == {"x"}

    def test_multiple_fields(self):
        node = parse_arithmetic("a + b * c")
        assert extract_field_refs(node) == {"a", "b", "c"}

    def test_no_fields(self):
        node = parse_arithmetic("1 + 2")
        assert extract_field_refs(node) == set()

    def test_duplicate_field(self):
        node = parse_arithmetic("a + a")
        assert extract_field_refs(node) == {"a"}

    def test_mixed(self):
        node = parse_arithmetic("a * 2 + b / 3")
        assert extract_field_refs(node) == {"a", "b"}


class TestRenderArithmetic:
    """Tests for arithmetic AST rendering."""

    def test_render_simple(self):
        node = parse_arithmetic("a + b")
        assert render_arithmetic(node) == "a + b"

    def test_render_precedence(self):
        node = parse_arithmetic("a + b * c")
        assert render_arithmetic(node) == "a + b * c"

    def test_render_parens(self):
        node = parse_arithmetic("(a + b) * c")
        result = render_arithmetic(node)
        assert result == "(a + b) * c"

    def test_render_number(self):
        node = parse_arithmetic("42")
        assert render_arithmetic(node) == "42"

    def test_render_float(self):
        node = parse_arithmetic("3.14")
        assert render_arithmetic(node) == "3.14"

    def test_roundtrip_complex(self):
        expr = "a * 2 + b"
        node = parse_arithmetic(expr)
        rendered = render_arithmetic(node)
        re_node = parse_arithmetic(rendered)
        assert extract_field_refs(re_node) == extract_field_refs(node)

    def test_render_subtraction_associativity(self):
        """a - (b - c) needs parens on the right."""
        # Build: a - (b - c)
        inner = BinaryOp(left=FieldRef("b"), op="-", right=FieldRef("c"))
        outer = BinaryOp(left=FieldRef("a"), op="-", right=inner)
        result = render_arithmetic(outer)
        assert result == "a - (b - c)"

    def test_render_division_associativity(self):
        """a / (b / c) needs parens on the right."""
        inner = BinaryOp(left=FieldRef("b"), op="/", right=FieldRef("c"))
        outer = BinaryOp(left=FieldRef("a"), op="/", right=inner)
        result = render_arithmetic(outer)
        assert result == "a / (b / c)"


# ======================================================================
# Config loader formula parsing tests
# ======================================================================


class TestFormulaLoading:
    """Tests for loading formula blocks from YAML."""

    def test_aggregate_count(self, loader, tmp_path):
        content = dedent("""\
            version: "1.1"
            description: "Test aggregate count"
            entities:
              Contact:
                fields:
                  - name: engagementCount
                    type: int
                    label: "Engagement Count"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: count
                      relatedEntity: Engagement
                      via: engagements
        """)
        path = tmp_path / "test.yaml"
        path.write_text(content)
        program = loader.load_program(path)
        field_def = program.entities[0].fields[0]
        assert field_def.formula is not None
        assert field_def.formula.type == "aggregate"
        assert field_def.formula.aggregate.function == "count"
        assert field_def.formula.aggregate.related_entity == "Engagement"
        assert field_def.formula.aggregate.via == "engagements"

    def test_aggregate_sum(self, loader, tmp_path):
        content = dedent("""\
            version: "1.1"
            description: "Test aggregate sum"
            entities:
              Contact:
                fields:
                  - name: totalHours
                    type: float
                    label: "Total Hours"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: sum
                      relatedEntity: Engagement
                      via: engagements
                      field: duration
        """)
        path = tmp_path / "test.yaml"
        path.write_text(content)
        program = loader.load_program(path)
        field_def = program.entities[0].fields[0]
        assert field_def.formula.aggregate.function == "sum"
        assert field_def.formula.aggregate.field == "duration"

    def test_aggregate_first_with_orderby(self, loader, tmp_path):
        content = dedent("""\
            version: "1.1"
            description: "Test aggregate first"
            entities:
              Contact:
                fields:
                  - name: latestNote
                    type: varchar
                    label: "Latest Note"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: first
                      relatedEntity: Engagement
                      via: engagements
                      pickField: note
                      orderBy:
                        field: createdAt
                        direction: desc
        """)
        path = tmp_path / "test.yaml"
        path.write_text(content)
        program = loader.load_program(path)
        field_def = program.entities[0].fields[0]
        assert field_def.formula.aggregate.function == "first"
        assert field_def.formula.aggregate.pick_field == "note"
        assert field_def.formula.aggregate.order_by.field == "createdAt"
        assert field_def.formula.aggregate.order_by.direction == "desc"

    def test_aggregate_with_where(self, loader, tmp_path):
        content = dedent("""\
            version: "1.1"
            description: "Test aggregate with where"
            entities:
              Contact:
                fields:
                  - name: activeCount
                    type: int
                    label: "Active Count"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: count
                      relatedEntity: Engagement
                      via: engagements
                      where:
                        - field: status
                          op: equals
                          value: Active
        """)
        path = tmp_path / "test.yaml"
        path.write_text(content)
        program = loader.load_program(path)
        field_def = program.entities[0].fields[0]
        assert field_def.formula.aggregate.where is not None

    def test_aggregate_with_join(self, loader, tmp_path):
        content = dedent("""\
            version: "1.1"
            description: "Test aggregate with join"
            entities:
              Contact:
                fields:
                  - name: totalHours
                    type: float
                    label: "Total Hours"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: sum
                      relatedEntity: Session
                      via: engagements
                      field: duration
                      join:
                        - via: sessions
                          entity: Session
        """)
        path = tmp_path / "test.yaml"
        path.write_text(content)
        program = loader.load_program(path)
        field_def = program.entities[0].fields[0]
        assert field_def.formula.aggregate.join is not None
        assert len(field_def.formula.aggregate.join) == 1

    def test_arithmetic_formula(self, loader, tmp_path):
        content = dedent("""\
            version: "1.1"
            description: "Test arithmetic"
            entities:
              Contact:
                fields:
                  - name: fieldA
                    type: int
                    label: "Field A"
                  - name: fieldB
                    type: int
                    label: "Field B"
                  - name: total
                    type: int
                    label: "Total"
                    readOnly: true
                    formula:
                      type: arithmetic
                      expression: "fieldA + fieldB"
        """)
        path = tmp_path / "test.yaml"
        path.write_text(content)
        program = loader.load_program(path)
        field_def = program.entities[0].fields[2]
        assert field_def.formula is not None
        assert field_def.formula.type == "arithmetic"
        assert field_def.formula.arithmetic.expression == "fieldA + fieldB"
        assert field_def.formula.arithmetic.parsed is not None

    def test_concat_formula(self, loader, tmp_path):
        content = dedent("""\
            version: "1.1"
            description: "Test concat"
            entities:
              Contact:
                fields:
                  - name: firstName
                    type: varchar
                    label: "First Name"
                  - name: fullDisplay
                    type: varchar
                    label: "Full Display"
                    readOnly: true
                    formula:
                      type: concat
                      parts:
                        - literal: "Name: "
                        - field: firstName
                        - lookup:
                            via: account
                            field: name
        """)
        path = tmp_path / "test.yaml"
        path.write_text(content)
        program = loader.load_program(path)
        field_def = program.entities[0].fields[1]
        assert field_def.formula is not None
        assert field_def.formula.type == "concat"
        assert len(field_def.formula.concat.parts) == 3


# ======================================================================
# Validation tests
# ======================================================================


class TestFormulaValidation:
    """Tests for formula validation in config_loader."""

    def _make_yaml(self, fields_yaml, tmp_path):
        """Build a full YAML program with given fields block.

        The ``fields_yaml`` is dedented text; this helper re-indents it
        to 10 spaces so it sits correctly under ``fields:``.
        """
        base = dedent("""\
            version: "1.1"
            description: "Test"
            entities:
              Contact:
                fields:
        """)
        # Re-indent each line of the fields block
        indented = "\n".join(
            ("          " + line if line.strip() else line)
            for line in fields_yaml.splitlines()
        )
        content = base + indented + "\n"
        path = tmp_path / "test.yaml"
        path.write_text(content)
        return path

    def test_formula_requires_readonly(self, loader, tmp_path):
        fields = dedent("""\
                  - name: total
                    type: int
                    label: "Total"
                    formula:
                      type: aggregate
                      function: count
                      relatedEntity: Engagement
                      via: engagements
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("readOnly: true" in e for e in errors)

    def test_aggregate_missing_function(self, loader, tmp_path):
        fields = dedent("""\
                  - name: total
                    type: int
                    label: "Total"
                    readOnly: true
                    formula:
                      type: aggregate
                      relatedEntity: Engagement
                      via: engagements
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("function" in e for e in errors)

    def test_aggregate_invalid_function(self, loader, tmp_path):
        fields = dedent("""\
                  - name: total
                    type: int
                    label: "Total"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: median
                      relatedEntity: Engagement
                      via: engagements
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("median" in e for e in errors)

    def test_aggregate_count_with_field_error(self, loader, tmp_path):
        fields = dedent("""\
                  - name: total
                    type: int
                    label: "Total"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: count
                      relatedEntity: Engagement
                      via: engagements
                      field: duration
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("must not be set" in e and "count" in e for e in errors)

    def test_aggregate_sum_requires_field(self, loader, tmp_path):
        fields = dedent("""\
                  - name: total
                    type: float
                    label: "Total"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: sum
                      relatedEntity: Engagement
                      via: engagements
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("field" in e and "required" in e for e in errors)

    def test_aggregate_first_requires_pickfield_and_orderby(
        self, loader, tmp_path
    ):
        fields = dedent("""\
                  - name: latest
                    type: varchar
                    label: "Latest"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: first
                      relatedEntity: Engagement
                      via: engagements
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("pickField" in e for e in errors)
        assert any("orderBy" in e for e in errors)

    def test_aggregate_missing_related_entity(self, loader, tmp_path):
        fields = dedent("""\
                  - name: total
                    type: int
                    label: "Total"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: count
                      via: engagements
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("relatedEntity" in e for e in errors)

    def test_aggregate_missing_via(self, loader, tmp_path):
        fields = dedent("""\
                  - name: total
                    type: int
                    label: "Total"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: count
                      relatedEntity: Engagement
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("via" in e for e in errors)

    def test_aggregate_avg_requires_field(self, loader, tmp_path):
        fields = dedent("""\
                  - name: avgHours
                    type: float
                    label: "Avg Hours"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: avg
                      relatedEntity: Engagement
                      via: engagements
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("field" in e and "required" in e for e in errors)

    def test_aggregate_min_requires_field(self, loader, tmp_path):
        fields = dedent("""\
                  - name: minHours
                    type: float
                    label: "Min Hours"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: min
                      relatedEntity: Engagement
                      via: engagements
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("field" in e and "required" in e for e in errors)

    def test_aggregate_max_requires_field(self, loader, tmp_path):
        fields = dedent("""\
                  - name: maxHours
                    type: float
                    label: "Max Hours"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: max
                      relatedEntity: Engagement
                      via: engagements
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("field" in e and "required" in e for e in errors)

    def test_aggregate_last_requires_pickfield_and_orderby(
        self, loader, tmp_path
    ):
        fields = dedent("""\
                  - name: earliest
                    type: varchar
                    label: "Earliest"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: last
                      relatedEntity: Engagement
                      via: engagements
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("pickField" in e for e in errors)
        assert any("orderBy" in e for e in errors)

    def test_arithmetic_unknown_field(self, loader, tmp_path):
        fields = dedent("""\
                  - name: total
                    type: int
                    label: "Total"
                    readOnly: true
                    formula:
                      type: arithmetic
                      expression: "unknownField + 1"
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("unknownField" in e and "not found" in e for e in errors)

    def test_arithmetic_valid_fields(self, loader, tmp_path):
        content = dedent("""\
            version: "1.1"
            description: "Test"
            entities:
              Contact:
                fields:
                  - name: a
                    type: int
                    label: "A"
                  - name: b
                    type: int
                    label: "B"
                  - name: total
                    type: int
                    label: "Total"
                    readOnly: true
                    formula:
                      type: arithmetic
                      expression: "a + b"
        """)
        path = tmp_path / "test.yaml"
        path.write_text(content)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert errors == []

    def test_arithmetic_bad_expression(self, loader, tmp_path):
        fields = dedent("""\
                  - name: total
                    type: int
                    label: "Total"
                    readOnly: true
                    formula:
                      type: arithmetic
                      expression: "a + + b"
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("expression" in e for e in errors)

    def test_arithmetic_empty_expression(self, loader, tmp_path):
        fields = dedent("""\
                  - name: total
                    type: int
                    label: "Total"
                    readOnly: true
                    formula:
                      type: arithmetic
                      expression: ""
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("expression" in e for e in errors)

    def test_concat_empty_parts(self, loader, tmp_path):
        fields = dedent("""\
                  - name: display
                    type: varchar
                    label: "Display"
                    readOnly: true
                    formula:
                      type: concat
                      parts: []
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("non-empty" in e for e in errors)

    def test_concat_field_not_found(self, loader, tmp_path):
        fields = dedent("""\
                  - name: display
                    type: varchar
                    label: "Display"
                    readOnly: true
                    formula:
                      type: concat
                      parts:
                        - field: nonExistent
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("nonExistent" in e and "not found" in e for e in errors)

    def test_concat_invalid_part_key(self, loader, tmp_path):
        fields = dedent("""\
                  - name: display
                    type: varchar
                    label: "Display"
                    readOnly: true
                    formula:
                      type: concat
                      parts:
                        - unknown: value
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("literal" in e and "field" in e and "lookup" in e for e in errors)

    def test_concat_lookup_missing_via(self, loader, tmp_path):
        fields = dedent("""\
                  - name: display
                    type: varchar
                    label: "Display"
                    readOnly: true
                    formula:
                      type: concat
                      parts:
                        - lookup:
                            field: name
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("via" in e for e in errors)

    def test_concat_lookup_missing_field(self, loader, tmp_path):
        fields = dedent("""\
                  - name: display
                    type: varchar
                    label: "Display"
                    readOnly: true
                    formula:
                      type: concat
                      parts:
                        - lookup:
                            via: account
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("field" in e for e in errors)

    def test_invalid_formula_type(self, loader, tmp_path):
        fields = dedent("""\
                  - name: total
                    type: int
                    label: "Total"
                    readOnly: true
                    formula:
                      type: custom
        """)
        path = self._make_yaml(fields, tmp_path)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("custom" in e for e in errors)

    def test_valid_aggregate_count_no_errors(self, loader, tmp_path):
        content = dedent("""\
            version: "1.1"
            description: "Test"
            entities:
              Contact:
                fields:
                  - name: engagementCount
                    type: int
                    label: "Engagement Count"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: count
                      relatedEntity: Engagement
                      via: engagements
        """)
        path = tmp_path / "test.yaml"
        path.write_text(content)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert errors == []

    def test_valid_concat_with_all_part_types(self, loader, tmp_path):
        content = dedent("""\
            version: "1.1"
            description: "Test"
            entities:
              Contact:
                fields:
                  - name: firstName
                    type: varchar
                    label: "First Name"
                  - name: display
                    type: varchar
                    label: "Display"
                    readOnly: true
                    formula:
                      type: concat
                      parts:
                        - literal: "Hello "
                        - field: firstName
                        - lookup:
                            via: account
                            field: name
        """)
        path = tmp_path / "test.yaml"
        path.write_text(content)
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert errors == []


# ======================================================================
# Deploy / rendering tests
# ======================================================================


class TestFormulaRendering:
    """Tests for formula rendering to API payload format."""

    def test_aggregate_count_rendering(self, loader, tmp_path):
        """Aggregate count formula renders expected API payload."""
        content = dedent("""\
            version: "1.1"
            description: "Test"
            entities:
              Contact:
                fields:
                  - name: engagementCount
                    type: int
                    label: "Engagement Count"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: count
                      relatedEntity: Engagement
                      via: engagements
        """)
        path = tmp_path / "test.yaml"
        path.write_text(content)
        program = loader.load_program(path)
        field_def = program.entities[0].fields[0]

        result = FieldManager._render_formula(field_def.formula)
        assert result["type"] == "aggregate"
        assert result["function"] == "count"
        assert result["relatedEntity"] == "Engagement"
        assert result["via"] == "engagements"
        assert "field" not in result

    def test_aggregate_sum_rendering(self, loader, tmp_path):
        content = dedent("""\
            version: "1.1"
            description: "Test"
            entities:
              Contact:
                fields:
                  - name: totalHours
                    type: float
                    label: "Total Hours"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: sum
                      relatedEntity: Engagement
                      via: engagements
                      field: duration
        """)
        path = tmp_path / "test.yaml"
        path.write_text(content)
        program = loader.load_program(path)
        field_def = program.entities[0].fields[0]

        result = FieldManager._render_formula(field_def.formula)
        assert result["field"] == "duration"

    def test_aggregate_first_rendering(self, loader, tmp_path):
        content = dedent("""\
            version: "1.1"
            description: "Test"
            entities:
              Contact:
                fields:
                  - name: latestNote
                    type: varchar
                    label: "Latest Note"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: first
                      relatedEntity: Engagement
                      via: engagements
                      pickField: note
                      orderBy:
                        field: createdAt
                        direction: desc
        """)
        path = tmp_path / "test.yaml"
        path.write_text(content)
        program = loader.load_program(path)
        field_def = program.entities[0].fields[0]

        result = FieldManager._render_formula(field_def.formula)
        assert result["pickField"] == "note"
        assert result["orderBy"]["field"] == "createdAt"
        assert result["orderBy"]["direction"] == "desc"

    def test_aggregate_with_where_rendering(self, loader, tmp_path):
        content = dedent("""\
            version: "1.1"
            description: "Test"
            entities:
              Contact:
                fields:
                  - name: activeCount
                    type: int
                    label: "Active Count"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: count
                      relatedEntity: Engagement
                      via: engagements
                      where:
                        - field: status
                          op: equals
                          value: Active
        """)
        path = tmp_path / "test.yaml"
        path.write_text(content)
        program = loader.load_program(path)
        field_def = program.entities[0].fields[0]

        result = FieldManager._render_formula(field_def.formula)
        assert "where" in result
        # Rendered as condition expression dict
        where = result["where"]
        assert "all" in where

    def test_arithmetic_rendering(self, loader, tmp_path):
        content = dedent("""\
            version: "1.1"
            description: "Test"
            entities:
              Contact:
                fields:
                  - name: a
                    type: int
                    label: "A"
                  - name: b
                    type: int
                    label: "B"
                  - name: total
                    type: int
                    label: "Total"
                    readOnly: true
                    formula:
                      type: arithmetic
                      expression: "a + b"
        """)
        path = tmp_path / "test.yaml"
        path.write_text(content)
        program = loader.load_program(path)
        field_def = program.entities[0].fields[2]

        result = FieldManager._render_formula(field_def.formula)
        assert result["type"] == "arithmetic"
        assert result["expression"] == "a + b"
        assert result["expressionRendered"] == "a + b"

    def test_concat_rendering(self, loader, tmp_path):
        content = dedent("""\
            version: "1.1"
            description: "Test"
            entities:
              Contact:
                fields:
                  - name: firstName
                    type: varchar
                    label: "First Name"
                  - name: display
                    type: varchar
                    label: "Display"
                    readOnly: true
                    formula:
                      type: concat
                      parts:
                        - literal: "Name: "
                        - field: firstName
        """)
        path = tmp_path / "test.yaml"
        path.write_text(content)
        program = loader.load_program(path)
        field_def = program.entities[0].fields[1]

        result = FieldManager._render_formula(field_def.formula)
        assert result["type"] == "concat"
        assert result["parts"] == [
            {"literal": "Name: "},
            {"field": "firstName"},
        ]

    def test_aggregate_join_rendering(self, loader, tmp_path):
        content = dedent("""\
            version: "1.1"
            description: "Test"
            entities:
              Contact:
                fields:
                  - name: totalHours
                    type: float
                    label: "Total Hours"
                    readOnly: true
                    formula:
                      type: aggregate
                      function: sum
                      relatedEntity: Session
                      via: engagements
                      field: duration
                      join:
                        - via: sessions
                          entity: Session
        """)
        path = tmp_path / "test.yaml"
        path.write_text(content)
        program = loader.load_program(path)
        field_def = program.entities[0].fields[0]

        result = FieldManager._render_formula(field_def.formula)
        assert result["join"] == [{"via": "sessions", "entity": "Session"}]
