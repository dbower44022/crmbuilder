"""Applying declared screen layouts to a live CRM system (REQ-611 / PI-525).

A layout is written whole — the platform has no way to change one panel — so
the only question worth asking first is whether the instance already holds
what the design declares. Asking it properly is most of this module, because
the platform does not hand back what it was given:

* It titles a panel under one key when the layout was customised and another
  when it is a factory default, and uses an empty string and a null
  interchangeably for "no title".
* It omits the keys that mark a tab break rather than storing them false.
* It adds its own built-in panels to the side- and bottom-panel maps, so what
  comes back is always a superset of what was sent.

A comparison that ignored those would rewrite every layout on every run. One
that took them literally would report a difference that is not there. The
rules here are version 1's, which were established against a live instance.

Two kinds of layout are refused rather than written, each for its own reason,
and both are reported by name so the operator knows what did not happen.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

from crmbuilder_v2.adapters.espocrm.layout_types import (
    is_deploy_deferred,
    is_known,
)
from crmbuilder_v2.introspect.espo_client import format_error_detail
from crmbuilder_v2.publish.entities import AuthenticationRejected
from crmbuilder_v2.publish.espo_write_client import EspoWriteClient

#: What happened to a layout.
UPDATED = "updated"
SKIPPED = "skipped"
REFUSED = "refused"
FAILED = "failed"
PREVIEWED = "previewed"

_PORTAL_REASON = (
    "a portal layout is not written: no instance this system has read defines "
    "one, so there is nothing to be faithful to. Set it by hand in the portal "
    "if it is needed."
)
_PER_ROLE_REASON = (
    "a layout that varies by role is not written: the platform expresses that "
    "as a separate layout set, which this system does not model. Create the "
    "layout set by hand and apply this layout inside it."
)
_UNKNOWN_REASON = "the platform has no layout by this name"


@dataclass(frozen=True)
class LayoutIntent:
    """One layout as the design declares it.

    :ivar layout_type: The platform's name for the layout, e.g. ``detail``.
    :ivar body: The layout as it would be sent — a list of panels, a list of
        columns, a list of names, or a name-to-configuration map, depending
        on the layout's shape.
    :ivar for_roles: The roles this layout is meant to vary for, when the
        design says so. Any value here means the layout is refused.
    """

    layout_type: str
    body: Any
    for_roles: Sequence[str] = ()


@dataclass
class LayoutOutcome:
    """What happened to one layout.

    :ivar entity: The platform's name for the object type.
    :ivar layout_type: The platform's name for the layout.
    :ivar status: One of :data:`UPDATED`, :data:`SKIPPED`, :data:`REFUSED`,
        :data:`FAILED`, :data:`PREVIEWED`.
    :ivar detail: What a person needs to read about it.
    :ivar manual_config: What somebody must now do by hand, when the layout
        was refused.
    """

    entity: str
    layout_type: str
    status: str
    detail: str = ""
    manual_config: list[str] = dataclass_field(default_factory=list)

    @property
    def failed(self) -> bool:
        return self.status == FAILED


def _panel_title(panel: Mapping[str, Any]) -> str:
    """A panel's title, however the platform chose to store it."""
    return panel.get("customLabel") or panel.get("label") or ""


def _cell_name(cell: Any) -> Any:
    """A cell's field name, whether the cell is a name or a whole cell."""
    return cell.get("name") if isinstance(cell, Mapping) else cell


def _rows_match(declared: Any, live: Any) -> bool:
    if len(declared) != len(live):
        return False
    for declared_row, live_row in zip(declared, live, strict=True):
        if not isinstance(declared_row, list) or not isinstance(live_row, list):
            if declared_row != live_row:
                return False
            continue
        if len(declared_row) != len(live_row):
            return False
        for declared_cell, live_cell in zip(declared_row, live_row, strict=True):
            if _cell_name(declared_cell) != _cell_name(live_cell):
                return False
    return True


def _items_match(declared: Mapping[str, Any], live: Mapping[str, Any]) -> bool:
    """Whether one panel or column is what the design declares.

    A list column is a flat item carrying a name and a width; a panel carries
    a title, rows and its tab marks. Neither shape has the other's keys, so
    both are checked and the absent ones compare equal on both sides.
    """
    if declared.get("name") != live.get("name"):
        return False
    if declared.get("width") != live.get("width"):
        return False
    if _panel_title(declared) != _panel_title(live):
        return False
    if not _rows_match(declared.get("rows", []), live.get("rows", [])):
        return False
    # A factory layout omits these keys rather than storing them false.
    if bool(declared.get("tabBreak")) != bool(live.get("tabBreak")):
        return False
    return (declared.get("tabLabel") or "") == (live.get("tabLabel") or "")


def layouts_match(declared: Any, live: Any) -> bool:
    """Whether the instance already holds the declared layout.

    :param declared: The layout as it would be sent.
    :param live: The layout as the instance reports it.
    :returns: True when nothing needs writing.
    """
    if isinstance(declared, Mapping):
        # The platform adds its own built-in panels to these maps, so what
        # comes back is a superset. Everything declared must be present and
        # equal; what the platform added is its own business.
        if not isinstance(live, Mapping):
            return False
        return all(live.get(key) == value for key, value in declared.items())

    if not isinstance(live, list) or not isinstance(declared, list):
        return False
    if len(declared) != len(live):
        return False

    for declared_item, live_item in zip(declared, live, strict=True):
        if isinstance(declared_item, Mapping) and isinstance(live_item, Mapping):
            if not _items_match(declared_item, live_item):
                return False
        elif declared_item != live_item:
            return False
    return True


def _refusal(intent: LayoutIntent) -> str | None:
    """Why this layout will not be written, if it will not be."""
    if intent.for_roles:
        return _PER_ROLE_REASON
    if not is_known(intent.layout_type):
        return _UNKNOWN_REASON
    if is_deploy_deferred(intent.layout_type):
        return _PORTAL_REASON
    return None


def apply_layout(
    client: EspoWriteClient,
    entity: str,
    intent: LayoutIntent,
    *,
    preview: bool = False,
) -> LayoutOutcome:
    """Apply one declared layout to an object type on the instance.

    :param client: A write-capable client for the target instance.
    :param entity: The platform's name for the object type.
    :param intent: The layout as declared.
    :param preview: When true, report what would happen and write nothing.
    :returns: What happened.
    :raises AuthenticationRejected: If the instance rejects the credential.
    """
    refusal = _refusal(intent)
    if refusal:
        return LayoutOutcome(
            entity,
            intent.layout_type,
            REFUSED,
            refusal,
            manual_config=[f"{entity} {intent.layout_type}: {refusal}"],
        )

    status, live = client.get_layout(entity, intent.layout_type)
    if status == 401:
        raise AuthenticationRejected(
            "the instance rejected the credential (401); nothing further "
            "can be applied"
        )
    if status == 200 and live is not None and layouts_match(intent.body, live):
        return LayoutOutcome(
            entity, intent.layout_type, SKIPPED, "already as declared"
        )

    if preview:
        return LayoutOutcome(
            entity,
            intent.layout_type,
            PREVIEWED,
            "would be written"
            if status == 200
            else "would be written; the instance did not report a current "
            "layout to compare against",
        )

    put_status, put_body = client.save_layout(
        entity, intent.layout_type, intent.body
    )
    if put_status == 401:
        raise AuthenticationRejected(
            "the instance rejected the credential (401); nothing further "
            "can be applied"
        )
    if put_status == 200:
        return LayoutOutcome(entity, intent.layout_type, UPDATED)
    return LayoutOutcome(
        entity,
        intent.layout_type,
        FAILED,
        f"the instance refused the layout ({put_status}): "
        f"{format_error_detail(put_body)}",
    )


def apply_layouts(
    client: EspoWriteClient,
    entity: str,
    intents: Iterable[LayoutIntent],
    *,
    preview: bool = False,
) -> list[LayoutOutcome]:
    """Apply every declared layout on one object type, in the order given."""
    return [
        apply_layout(client, entity, intent, preview=preview)
        for intent in intents
    ]
