"""Field state comparison logic."""

from dataclasses import dataclass, field
from typing import Any

from espo_impl.core.models import FieldDefinition

ENUM_TYPES: set[str] = {"enum", "multiEnum"}

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


@dataclass
class ComparisonResult:
    """Result of comparing a field spec to current API state.

    :param matches: True if the field matches the spec.
    :param differences: List of property names that differ.
    :param type_conflict: True if field types differ.
    """

    matches: bool
    differences: list[str] = field(default_factory=list)
    type_conflict: bool = False


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
            return ComparisonResult(
                matches=False, type_conflict=True, differences=["type"]
            )

        differences: list[str] = []

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
                differences.append(prop)

        if spec.type in ENUM_TYPES:
            for prop in ENUM_PROPERTIES:
                spec_value = getattr(spec, prop)
                if spec_value is None:
                    continue
                current_value = current.get(prop)
                if current_value is None and prop not in current:
                    continue
                if spec_value != current_value:
                    differences.append(prop)

        return ComparisonResult(
            matches=len(differences) == 0,
            differences=differences,
        )
