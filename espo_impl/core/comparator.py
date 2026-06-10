"""Field state comparison logic."""

from dataclasses import dataclass, field
from typing import Any

from espo_impl.core.models import FieldDefinition

ENUM_TYPES: set[str] = {"enum", "multiEnum"}

FOREIGN_TYPES: set[str] = {"foreign"}

# Properties compared for all field types.
COMMON_PROPERTIES: list[str] = [
    "label",
    "required",
    "default",
    "readOnly",
    "audited",
    "min",
    "max",
    "maxLength",
]

# Additional properties compared for enum/multiEnum types.
ENUM_PROPERTIES: list[str] = [
    "options",
    "translatedOptions",
    "style",
]

# Properties whose values are option lists and merit a missing/extra breakdown.
_OPTION_LIST_PROPERTIES: set[str] = {"options"}

# Spec-to-API property mapping for foreign-field comparison.
# Python attribute names on FieldDefinition do not match the API payload
# names because ``field`` is shadowed by the dataclasses import; the
# comparator bridges the two.
FOREIGN_PROPERTY_MAP: dict[str, str] = {
    "link": "link",
    "foreign_field": "field",
}


def _format_value(value: Any) -> str:
    """Render a property value for a human-readable difference message.

    :param value: Spec or API value.
    :returns: Compact string form.
    """
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(str(v) for v in value) + "]"
    return repr(value)


def _describe_options(prop: str, expected: Any, actual: Any) -> str:
    """Describe how two option lists differ (missing / extra values).

    :param prop: Property name (e.g. ``options``).
    :param expected: Option list from the YAML spec.
    :param actual: Option list from the deployed field.
    :returns: Human-readable difference message.
    """
    exp_list = list(expected) if isinstance(expected, (list, tuple)) else []
    act_list = list(actual) if isinstance(actual, (list, tuple)) else []
    exp_set = set(exp_list)
    act_set = set(act_list)

    missing = [v for v in exp_list if v not in act_set]
    extra = [v for v in act_list if v not in exp_set]

    parts: list[str] = []
    if missing:
        parts.append(
            "missing from deployed: [" + ", ".join(str(v) for v in missing) + "]"
        )
    if extra:
        parts.append(
            "extra in deployed: [" + ", ".join(str(v) for v in extra) + "]"
        )
    if not parts:
        # Same values, only the ordering differs.
        parts.append("same values, different order")
    return f"{prop} differ — " + "; ".join(parts)


def _describe_generic(prop: str, expected: Any, actual: Any) -> str:
    """Describe a scalar property difference.

    :param prop: Property name.
    :param expected: Value from the YAML spec.
    :param actual: Value from the deployed field.
    :returns: Human-readable difference message.
    """
    return (
        f"{prop} differs — YAML expects {_format_value(expected)} "
        f"but deployed has {_format_value(actual)}"
    )


@dataclass
class FieldDifference:
    """A single property-level difference between spec and deployed state.

    :param property: Name of the differing property.
    :param expected: Value declared in the YAML spec.
    :param actual: Value currently deployed on the instance.
    :param message: Human-readable explanation of the difference.
    """

    property: str
    expected: Any
    actual: Any
    message: str


@dataclass
class ComparisonResult:
    """Result of comparing a field spec to current API state.

    :param matches: True if the field matches the spec.
    :param differences: List of property names that differ.
    :param type_conflict: True if field types differ.
    :param detailed: Structured per-property difference records carrying the
        expected vs deployed values and a human-readable message.
    """

    matches: bool
    differences: list[str] = field(default_factory=list)
    type_conflict: bool = False
    detailed: list[FieldDifference] = field(default_factory=list)

    @property
    def detail_text(self) -> str:
        """Join every difference message into one human-readable string."""
        return "; ".join(d.message for d in self.detailed)


class FieldComparator:
    """Compares a FieldDefinition spec against current API state."""

    def compare(
        self, spec: FieldDefinition, current: dict[str, Any]
    ) -> ComparisonResult:
        """Compare a field spec to the current state from the API.

        :param spec: Desired field definition from the YAML program.
        :param current: Current field state returned by the API.
        :returns: ComparisonResult indicating match status.
        """
        if spec.type != current.get("type"):
            current_type = current.get("type")
            return ComparisonResult(
                matches=False,
                type_conflict=True,
                differences=["type"],
                detailed=[
                    FieldDifference(
                        property="type",
                        expected=spec.type,
                        actual=current_type,
                        message=(
                            f"type differs — YAML expects "
                            f"{_format_value(spec.type)} but deployed is "
                            f"{_format_value(current_type)}"
                        ),
                    )
                ],
            )

        differences: list[str] = []
        detailed: list[FieldDifference] = []

        def record(prop: str, expected: Any, actual: Any) -> None:
            """Append a difference, choosing the option-aware describer."""
            if prop in _OPTION_LIST_PROPERTIES:
                message = _describe_options(prop, expected, actual)
            else:
                message = _describe_generic(prop, expected, actual)
            differences.append(prop)
            detailed.append(
                FieldDifference(
                    property=prop,
                    expected=expected,
                    actual=actual,
                    message=message,
                )
            )

        for prop in COMMON_PROPERTIES:
            spec_value = getattr(spec, prop)
            if spec_value is None:
                continue
            current_value = current.get(prop)
            # Skip if the API didn't return this property — the Metadata
            # API omits label, translatedOptions, and some defaults from
            # the field definition (they're in the translation system).
            if current_value is None and prop not in current:
                continue
            if spec_value != current_value:
                record(prop, spec_value, current_value)

        if spec.type in ENUM_TYPES:
            for prop in ENUM_PROPERTIES:
                spec_value = getattr(spec, prop)
                if spec_value is None:
                    continue
                current_value = current.get(prop)
                if current_value is None and prop not in current:
                    continue
                if spec_value != current_value:
                    record(prop, spec_value, current_value)

        if spec.type in FOREIGN_TYPES:
            for spec_attr, api_key in FOREIGN_PROPERTY_MAP.items():
                spec_value = getattr(spec, spec_attr)
                if spec_value is None:
                    continue
                current_value = current.get(api_key)
                if current_value is None and api_key not in current:
                    continue
                if spec_value != current_value:
                    record(api_key, spec_value, current_value)

        return ComparisonResult(
            matches=len(differences) == 0,
            differences=differences,
            detailed=detailed,
        )
