"""Diff-engine data model.

A :class:`Difference` is one comparison result between the live CRM and the
source YAML. The diff engine emits a list of these; the UI renders them for
selection; the worker hands the ticked subset to the patcher, which applies each
via its :attr:`Difference.locator`.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class DiffCategory(Enum):
    """Which side(s) a difference exists on."""

    #: Present in both YAML and CRM, but a property value differs -> surgical set.
    CHANGED = "changed"
    #: Present in the CRM only (added via the admin UI) -> insert (ask target file).
    CRM_ONLY = "crm_only"
    #: Present in the YAML only (deleted in UI, or never deployed) -> report only.
    YAML_ONLY = "yaml_only"


class ConfigType(Enum):
    """The kind of configuration a difference concerns."""

    FIELD = "field"
    RELATIONSHIP = "relationship"
    LAYOUT = "layout"
    ROLE = "role"
    TEAM = "team"
    FILTERED_TAB = "filtered_tab"
    SAVED_VIEW = "saved_view"
    DUP_CHECK = "dup_check"
    WORKFLOW = "workflow"


@dataclass(frozen=True)
class Difference:
    """One difference between the live CRM and the source YAML.

    :param config_type: the kind of config (field, relationship, ...).
    :param category: CHANGED / CRM_ONLY / YAML_ONLY.
    :param entity: entity name the difference is on.
    :param locator: typed address used by the patcher to apply the change.
    :param property: the property key for a CHANGED difference; ``None`` for a
        whole-item add/remove.
    :param yaml_value: the value on the YAML side (``None`` for CRM_ONLY).
    :param crm_value: the value on the CRM side (``None`` for YAML_ONLY).
    :param source_file: the YAML file that owns the item; ``None`` for a
        CRM_ONLY addition until the user chooses a target file.
    :param full_crm_block: for a CRM_ONLY addition, the reconstructed field
        definition to insert; ``None`` otherwise.
    """

    config_type: ConfigType
    category: DiffCategory
    entity: str
    locator: Any
    property: str | None = None
    yaml_value: Any = None
    crm_value: Any = None
    source_file: Path | None = None
    full_crm_block: dict[str, Any] | None = None
