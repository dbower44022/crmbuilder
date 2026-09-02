"""Live target reads for the publish path — PI-449 (REQ-549).

The two server-state reads publish needs, V2-native: mapping the design's
natural entity names onto a live instance's scopes, and discovering the field
names already present there so the validator can resolve a reference to a
field created by an earlier deploy. Both were previously imported from the V1
reconcile module ``espo_impl/core/reconcile/live_state.py``, whose imports
pull in the whole V1 audit; this module re-homes exactly what publish uses,
on V2's own audit-utils port, so removing the V1 audit cannot break publish.
V1's reconcile feature keeps its own copy untouched.

Read-only and side-effect-free throughout: every failure is reported through
a returned warnings list, never raised — the caller falls back to validating
against the deploy batch alone.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from crmbuilder_v2.introspect.audit_utils import (
    FieldClass,
    classify_field,
    strip_field_c_prefix,
)


@dataclass(frozen=True)
class EntitySpec:
    """An entity to read, with the names/type needed to reach and classify it.

    :param yaml_name: logical name as used in the program files and validator.
    :param espo_name: API/internal name (custom entities are ``C``-prefixed).
    :param entity_type: ``Person`` | ``Company`` | ``Base`` | ``Event`` — used
        to recognise native fields.
    """

    yaml_name: str
    espo_name: str
    entity_type: str | None = None


def map_entity_specs(
    desired_entities: Iterable[str], scopes: dict[str, Any]
) -> tuple[list[EntitySpec], list[str]]:
    """Map desired (design) entity names to live :class:`EntitySpec`\\ s.

    A native entity maps to itself; a custom entity ``Session`` maps to
    ``CSession``. Returns ``(specs, unmapped)`` where ``unmapped`` lists
    entities not present on the live instance (e.g. a domain not deployed to
    this instance) — reported, not an error.
    """
    specs: list[EntitySpec] = []
    unmapped: list[str] = []
    for name in sorted(set(desired_entities)):
        if name in scopes:
            specs.append(EntitySpec(name, name, scopes[name].get("type")))
        elif f"C{name}" in scopes:
            specs.append(
                EntitySpec(name, f"C{name}", scopes[f"C{name}"].get("type"))
            )
        else:
            unmapped.append(name)
    return specs, unmapped


def _capture_field_names(
    client, specs: Iterable[EntitySpec]
) -> tuple[dict[str, frozenset[str]], list[str]]:
    """Each entity's live field names in natural form, plus fetch warnings.

    Custom fields have the platform ``c`` prefix stripped when the parent
    entity is native (on a custom entity, custom fields keep their natural
    names); native fields keep their names; system fields are skipped. An
    entity whose fields cannot be fetched is omitted with a warning rather
    than reported as empty.
    """
    out: dict[str, frozenset[str]] = {}
    warnings: list[str] = []
    for spec in specs:
        status, fields_meta = client.get_entity_field_list(spec.espo_name)
        if status != 200 or not isinstance(fields_meta, dict):
            warnings.append(
                f"{spec.yaml_name}: failed to fetch fields (HTTP {status})"
            )
            continue
        names: set[str] = set()
        for api_name, meta in fields_meta.items():
            if not isinstance(meta, dict):
                continue
            fclass = classify_field(api_name, meta, spec.entity_type)
            if fclass is FieldClass.SYSTEM:
                continue
            if fclass is FieldClass.CUSTOM:
                names.add(
                    strip_field_c_prefix(
                        api_name,
                        entity_is_native=(spec.espo_name == spec.yaml_name),
                    )
                )
            else:
                names.add(api_name)
        out[spec.yaml_name] = frozenset(names)
    return out, warnings


def gather_server_fields(
    client, entity_names: Iterable[str]
) -> tuple[dict[str, frozenset[str]], list[str]]:
    """Discover the field names already present on a live instance.

    Best-effort read of the target so the validator can resolve a reference
    to a field created by an earlier deploy (or by a YAML outside the current
    batch) instead of rejecting it. Field names come back in the natural form
    the validator compares against.

    :param client: a connected admin client (exposes ``get_all_scopes`` and
        ``get_entity_field_list``).
    :param entity_names: natural names of the entities in the deploy batch.
    :returns: ``(server_fields_by_entity, warnings)``.
    """
    names = sorted(set(entity_names))
    if not names:
        return {}, []

    status, scopes = client.get_all_scopes()
    if status != 200 or not isinstance(scopes, dict):
        return {}, [
            f"Could not read live instance scopes (HTTP {status}); "
            "validating against the deploy batch only."
        ]

    specs, unmapped = map_entity_specs(names, scopes)
    warnings: list[str] = [
        f"{name}: not present on the live instance — "
        "validated against the deploy batch only."
        for name in unmapped
    ]
    if not specs:
        return {}, warnings

    server_fields, capture_warnings = _capture_field_names(client, specs)
    warnings.extend(capture_warnings)
    return server_fields, warnings
