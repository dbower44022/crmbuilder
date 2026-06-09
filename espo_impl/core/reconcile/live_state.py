"""Capture live EspoCRM field state in the shape the diff engine consumes.

Produces ``{yaml_entity: {yaml_field: current_dict}}`` — the ``live`` input to
:func:`espo_impl.core.reconcile.diff_engine.diff_fields`, where ``current_dict``
is the API field-definition meta (``type``, ``required``, ``options``, ...)
enriched with the i18n ``label``. This reuses the same enumeration and
name-reversal helpers the Audit feature uses (``get_entity_field_list``,
``classify_field``, ``strip_field_c_prefix``) so reconciliation sees fields by
their YAML names and the comparison stays identical to the forward CHECK.

The i18n label lookup is injected as ``label_resolver`` (entityDefs carries no
``label`` — labels live in the translation system). In production this is wired
to the Audit machinery's i18n resolver; the seam keeps the transform testable
without a live server. End-to-end verification against a live instance (real API
shapes + i18n) is the remaining step for this module.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from espo_impl.core.audit_utils import (
    FieldClass,
    classify_field,
    strip_field_c_prefix,
)

#: ``(espo_entity, api_field, fallback) -> label``.
LabelResolver = Callable[[str, str, str], str]


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
