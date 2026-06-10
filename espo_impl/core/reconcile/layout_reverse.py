"""Convert a live layout API payload to its YAML body shape, for write-back.

``diff_layouts`` compares raw EspoCRM layout payloads (bare panel/column lists
with c-prefixed API field names). To write an accepted layout drift back into the
program file we need the *YAML* shape instead: natural field names and the
``panels:`` / ``columns:`` structure the loader and deploy builder expect.

This reuses the Audit feature's tested reverse-mappers (the single source of truth
for payload→YAML, kept lossless by the layout work) via an ``AuditManager``
constructed with ``client=None`` — its ``__init__`` only stores args, and the
``_reverse_*`` methods are pure functions of ``(payload, custom_names)``. Same
client=None pattern ``provenance.build_layout_desired`` uses with ``LayoutManager``.

Authoring-style note: the reverse-map always yields *explicit* panels/rows. So a
layout the source YAML authored with the tabs+category abstraction is rewritten in
explicit form when its drift is reconciled — an accepted, documented consequence
of capturing live layout state back into source.
"""
from __future__ import annotations

from typing import Any

from espo_impl.core.audit_manager import AuditManager
from espo_impl.core.layout_types import LayoutClass, structure_class

# One reusable mapper instance; the reverse methods hold no per-call state.
_MAPPER = AuditManager(client=None)


def reverse_layout_payload(
    layout_type: str, payload: Any, custom_names: set[str]
) -> Any:
    """Return the YAML body for ``payload`` under a ``<layout_type>:`` key.

    :param layout_type: e.g. ``detail`` / ``list`` / ``filters`` / ``sidePanelsDetail``.
    :param payload: the raw live API layout payload (from ``client.get_layout``).
    :param custom_names: the entity's *custom* field API names (c-prefixed on
        native entities) so they get reversed to natural names; native field
        names pass through.
    :returns: ``{"panels": [...]}`` (PANELS), ``{"columns": [...]}`` (COLUMNS),
        a bare list (FIELD_LIST), or a bare dict (PANEL_MAP) — ready for
        :meth:`YamlDocument.replace_block_body`.
    """
    cls = structure_class(layout_type)
    if cls is LayoutClass.PANELS:
        return {"panels": _MAPPER._reverse_detail_layout(payload, custom_names)}
    if cls is LayoutClass.COLUMNS:
        return {"columns": _MAPPER._reverse_list_layout(payload, custom_names)}
    if cls is LayoutClass.FIELD_LIST:
        return _MAPPER._reverse_field_list_layout(payload, custom_names)
    if cls is LayoutClass.PANEL_MAP:
        return _MAPPER._reverse_panel_map_layout(payload)
    return payload  # unknown type: passthrough (should not occur for deployables)
