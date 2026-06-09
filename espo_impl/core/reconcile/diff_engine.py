"""Compute differences between live CRM config and the source YAML.

Phase 1 covers fields. The engine reuses the existing :class:`FieldComparator`
to decide *which* properties differ (its forward-CHECK asymmetry — only flag a
property the YAML actually sets — matches the changed-in-both write-back case),
then attaches the old/new values and a target-file so each :class:`Difference`
is directly actionable.

Inputs are kept plain so the engine is testable without a live CRM:

* ``desired`` — ``{entity: {field_name: (FieldDefinition, source_file)}}``,
  assembled from the program files (with provenance) by the caller.
* ``live`` — ``{entity: {field_name: current_dict}}``, where ``current_dict`` is
  the API/audit field-definition shape (keys ``type``, ``label``, ``required``,
  ``options``, ...).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from espo_impl.core.comparator import FOREIGN_PROPERTY_MAP, FieldComparator
from espo_impl.core.models import FieldDefinition
from espo_impl.core.reconcile.locators import FieldLocator
from espo_impl.core.reconcile.models import ConfigType, DiffCategory, Difference

# A difference's property name is the YAML key (e.g. "field"/"link" for foreign
# fields). To read the YAML-side value we map that key back to the dataclass
# attribute ("field" -> "foreign_field"); for everything else key == attribute.
_KEY_TO_ATTR: dict[str, str] = {v: k for k, v in FOREIGN_PROPERTY_MAP.items()}


def _yaml_value(spec: FieldDefinition, prop: str) -> Any:
    return getattr(spec, _KEY_TO_ATTR.get(prop, prop), None)


def diff_fields(
    desired: dict[str, dict[str, tuple[FieldDefinition, Path]]],
    live: dict[str, dict[str, dict[str, Any]]],
    *,
    comparator: FieldComparator | None = None,
) -> list[Difference]:
    """Compute field-level differences across all entities.

    Returns CHANGED differences (per differing property, with old/new values),
    CRM_ONLY differences (a whole field present only in the CRM), and YAML_ONLY
    differences (a whole field present only in the YAML). Ordering is stable:
    entities then fields then properties, as encountered.
    """
    comparator = comparator or FieldComparator()
    diffs: list[Difference] = []

    for entity in sorted(set(desired) | set(live)):
        yaml_fields = desired.get(entity, {})
        crm_fields = live.get(entity, {})

        for name in sorted(set(yaml_fields) | set(crm_fields)):
            in_yaml = name in yaml_fields
            in_crm = name in crm_fields

            if in_yaml and in_crm:
                spec, source_file = yaml_fields[name]
                result = comparator.compare(spec, crm_fields[name])
                for prop in result.differences:
                    diffs.append(
                        Difference(
                            config_type=ConfigType.FIELD,
                            category=DiffCategory.CHANGED,
                            entity=entity,
                            locator=FieldLocator(entity, name, prop),
                            property=prop,
                            yaml_value=_yaml_value(spec, prop),
                            crm_value=crm_fields[name].get(prop),
                            source_file=source_file,
                        )
                    )
            elif in_crm:
                diffs.append(
                    Difference(
                        config_type=ConfigType.FIELD,
                        category=DiffCategory.CRM_ONLY,
                        entity=entity,
                        locator=FieldLocator(entity, name, None),
                        property=None,
                        crm_value=crm_fields[name],
                        full_crm_block=crm_fields[name],
                        # source_file deliberately None: the user picks it
                        # (ask-per-addition) since entities span multiple files.
                    )
                )
            else:
                spec, source_file = yaml_fields[name]
                diffs.append(
                    Difference(
                        config_type=ConfigType.FIELD,
                        category=DiffCategory.YAML_ONLY,
                        entity=entity,
                        locator=FieldLocator(entity, name, None),
                        property=None,
                        yaml_value=spec,
                        source_file=source_file,
                    )
                )

    return diffs
