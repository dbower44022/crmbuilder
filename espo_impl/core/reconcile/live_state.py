"""Capture live EspoCRM config in the shapes the diff engine consumes.

The field path produces ``{yaml_entity: {yaml_field: current_dict}}`` — the
``live`` input to :func:`...diff_engine.diff_fields` — reusing the same
enumeration and name-reversal helpers the Audit feature uses
(``get_entity_field_list``, ``classify_field``, ``strip_field_c_prefix``) so
reconciliation sees fields by their YAML names and the comparison stays identical
to the forward CHECK. The i18n label lookup is injected as ``label_resolver``
(entityDefs carries no ``label`` — labels live in the translation system),
verified against the live CBM instance.

The relationship, layout, and role/team paths (``capture_relationships`` /
``capture_layouts`` / ``capture_roles_teams``) feed
:func:`...diff_engine.diff_relationships` / :func:`...diff_engine.diff_layouts` /
:func:`...security_diff.diff_roles` + :func:`...security_diff.diff_teams`. Rather
than re-implement discovery, these **reuse the Audit machinery's tested
discovery + reverse-mappers** (``AuditManager._discover_relationships`` /
``_discover_roles`` / ``_discover_teams``) driven by a throwaway ``AuditReport``,
and the raw ``client.get_layout`` for the layout live side (``diff_layouts``
compares raw EspoCRM payloads directly). All capture methods stay read-only.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from espo_impl.core.audit_utils import (
    EntityClass,
    FieldClass,
    classify_field,
    strip_field_c_prefix,
)
from espo_impl.core.layout_types import DEPLOYABLE_LAYOUT_TYPES

#: ``(espo_entity, api_field, fallback) -> label``.
LabelResolver = Callable[[str, str, str], str]


def build_label_resolver(client) -> LabelResolver:
    """Build an i18n label resolver from a connected client.

    Fetches the full ``/I18n`` tree once and returns a closure that looks up
    ``i18n[scope].fields[name]`` then ``i18n.Global.fields[name]`` then the
    fallback — the same resolution the Audit feature uses. Verified against the
    live CBM instance (recovers e.g. ``Contact.title`` label drift).
    """
    status, i18n = client.get_i18n()
    i18n = i18n if status == 200 and isinstance(i18n, dict) else {}

    def resolver(scope: str, api_name: str, fallback: str) -> str:
        scoped = (i18n.get(scope) or {}).get("fields") or {}
        val = scoped.get(api_name)
        if isinstance(val, str):
            return val
        glob = (i18n.get("Global") or {}).get("fields") or {}
        gval = glob.get(api_name)
        return gval if isinstance(gval, str) else fallback

    return resolver


def map_entity_specs(
    desired_entities: Iterable[str], scopes: dict[str, Any]
) -> tuple[list[EntitySpec], list[str]]:
    """Map desired (YAML) entity names to live :class:`EntitySpec`\\ s via scopes.

    A native entity maps to itself; a custom entity ``Session`` maps to ``CSession``.
    Returns ``(specs, unmapped)`` where ``unmapped`` lists YAML entities not present
    on the live instance (e.g. a domain not deployed to this instance) — reported,
    not an error.
    """
    specs: list[EntitySpec] = []
    unmapped: list[str] = []
    for name in sorted(set(desired_entities)):
        if name in scopes:
            specs.append(EntitySpec(name, name, scopes[name].get("type")))
        elif f"C{name}" in scopes:
            specs.append(EntitySpec(name, f"C{name}", scopes[f"C{name}"].get("type")))
        else:
            unmapped.append(name)
    return specs, unmapped


@dataclass(frozen=True)
class EntitySpec:
    """An entity to capture, with the names/type needed to reach and classify it.

    :param yaml_name: logical name as used in the program files and diff engine.
    :param espo_name: API/internal name (custom entities are ``C``-prefixed).
    :param entity_type: ``Person`` | ``Company`` | ``Base`` | ``Event`` — used to
        recognise native fields.
    """

    yaml_name: str
    espo_name: str
    entity_type: str | None = None


class LiveStateCapture:
    """Reads live field state for a set of entities."""

    def __init__(
        self,
        client,
        *,
        label_resolver: LabelResolver | None = None,
        include_native: bool = True,
    ) -> None:
        """:param client: an ``EspoAdminClient``.
        :param label_resolver: resolves the i18n label for a field; defaults to
            the field's fallback name when not supplied.
        :param include_native: include native (non-custom) fields, so label/extra
            drift on native fields is visible. System fields are always skipped.
        """
        self._client = client
        self._label_resolver = label_resolver or (lambda espo, api, fallback: fallback)
        self._include_native = include_native

    def capture_fields(
        self, entities: Iterable[EntitySpec]
    ) -> tuple[dict[str, dict[str, dict[str, Any]]], list[str]]:
        """Capture fields for ``entities``.

        :returns: ``(live, warnings)`` where ``live`` is
            ``{yaml_entity: {yaml_field: current_dict}}`` and ``warnings`` lists
            entities whose fields could not be fetched (the entity is omitted
            from ``live`` rather than reported as all-deleted).
        """
        live: dict[str, dict[str, dict[str, Any]]] = {}
        warnings: list[str] = []

        for spec in entities:
            status, fields_meta = self._client.get_entity_field_list(spec.espo_name)
            if status != 200 or not isinstance(fields_meta, dict):
                warnings.append(
                    f"{spec.yaml_name}: failed to fetch fields (HTTP {status})"
                )
                continue

            ent: dict[str, dict[str, Any]] = {}
            for api_name, meta in fields_meta.items():
                if not isinstance(meta, dict):
                    continue
                fclass = classify_field(api_name, meta, spec.entity_type)
                if fclass is FieldClass.SYSTEM:
                    continue
                if fclass is FieldClass.NATIVE and not self._include_native:
                    continue

                if fclass is FieldClass.CUSTOM:
                    yaml_name = strip_field_c_prefix(api_name)
                else:
                    yaml_name = api_name

                current = dict(meta)
                # entityDefs has no label; the i18n resolver is authoritative.
                current["label"] = self._label_resolver(
                    spec.espo_name, api_name, yaml_name
                )
                ent[yaml_name] = current

            live[spec.yaml_name] = ent

        return live, warnings

    def capture_relationships(
        self, entities: Iterable[EntitySpec]
    ) -> tuple[dict[str, dict[str, dict[str, Any]]], list[str]]:
        """Capture relationships for ``entities`` in ``diff_relationships`` shape.

        Reuses ``AuditManager._discover_relationships`` (link enumeration,
        link-type resolution, i18n labels, dedup) then projects each
        ``RelationshipAuditResult`` to the comparator's per-property dict, keyed
        by the **primary link name** — the stable identity shared by both sides
        (the YAML ``RelationshipDefinition.link``). The audit's synthetic
        relationship ``name`` is not used for matching.

        :returns: ``({yaml_entity: {link_name: rel_dict}}, warnings)``.

        .. note:: Link names on a native entity pointing at a custom entity are
            c-prefixed in EspoCRM and are not reversed here (they are not custom
            *fields*), matching the Audit feature's own behaviour; such a pair
            can surface as CRM_ONLY + YAML_ONLY rather than CHANGED. A v1 limit,
            reported not hidden.
        """
        # Imported here to avoid a heavy module-level import for the field path.
        from espo_impl.core.audit_manager import (
            AuditManager,
            AuditReport,
            EntityAuditResult,
        )

        audit = AuditManager(self._client)
        report = AuditReport(
            source_url="", source_name="", timestamp="", output_dir=""
        )
        stubs = [
            EntityAuditResult(
                yaml_name=spec.yaml_name,
                espo_name=spec.espo_name,
                entity_class=(
                    EntityClass.NATIVE
                    if spec.espo_name == spec.yaml_name
                    else EntityClass.CUSTOM
                ),
                entity_type=spec.entity_type,
            )
            for spec in entities
        ]

        live: dict[str, dict[str, dict[str, Any]]] = {}
        for rel in audit._discover_relationships(stubs, report):
            live.setdefault(rel.entity, {})[rel.link] = {
                "link_type": rel.link_type,
                "entity_foreign": rel.entity_foreign,
                "link": rel.link,
                "link_foreign": rel.link_foreign,
                "label": rel.label,
                "label_foreign": rel.label_foreign,
                "relation_name": rel.relation_name,
                "audited": rel.audited,
                "audited_foreign": rel.audited_foreign,
            }
        return live, report.warnings

    def capture_layouts(
        self,
        entities: Iterable[EntitySpec],
        *,
        layout_types: Iterable[str] | None = None,
    ) -> tuple[dict[str, dict[str, Any]], list[str]]:
        """Capture live layout payloads for ``entities`` (``diff_layouts`` shape).

        For each entity and layout type, fetch the raw EspoCRM payload via
        ``client.get_layout`` — exactly what ``diff_layouts`` compares against the
        YAML-built ``desired`` payloads. A falsy response (``false`` / ``[]`` /
        ``{}``) means the layout is not separately defined (e.g. ``edit`` derives
        from ``detail``) and is skipped.

        :param layout_types: which types to read; defaults to every deployable
            layout type.
        :returns: ``({yaml_entity: {layout_type: payload}}, warnings)``.
        """
        types = sorted(layout_types) if layout_types else sorted(
            DEPLOYABLE_LAYOUT_TYPES
        )
        live: dict[str, dict[str, Any]] = {}
        warnings: list[str] = []

        for spec in entities:
            ent: dict[str, Any] = {}
            for ltype in types:
                status, payload = self._client.get_layout(spec.espo_name, ltype)
                if status != 200:
                    warnings.append(
                        f"{spec.yaml_name}: failed to fetch {ltype} layout "
                        f"(HTTP {status})"
                    )
                    continue
                if not payload:  # false/empty: derived or undefined layout
                    continue
                ent[ltype] = payload
            if ent:
                live[spec.yaml_name] = ent

        return live, warnings

    def capture_roles_teams(
        self,
    ) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
        """Capture all live roles and teams (``diff_roles`` / ``diff_teams`` shape).

        Reuses ``AuditManager._discover_roles`` / ``_discover_teams`` (and their
        ``_reverse_scope_access`` / ``_reverse_system_permissions``), returning
        ``RoleAuditResult`` / ``TeamAuditResult`` objects keyed by name — exactly
        the ``.description`` / ``.scope_access`` / ``.system_permissions`` surface
        the security comparators read.

        :returns: ``(roles_by_name, teams_by_name, warnings)``.
        """
        from espo_impl.core.audit_manager import AuditManager, AuditReport

        audit = AuditManager(self._client)
        report = AuditReport(
            source_url="", source_name="", timestamp="", output_dir=""
        )
        roles = {r.name: r for r in audit._discover_roles(report)}
        teams = {t.name: t for t in audit._discover_teams(report)}
        return roles, teams, report.warnings + report.errors
