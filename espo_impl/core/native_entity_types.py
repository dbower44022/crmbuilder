"""Canonical mapping from EspoCRM native entity names to their
base types, used to resolve native field sets during validation
and in any other context that needs to know what built-in fields
ship with a native entity.

This complements ``espo_impl.ui.confirm_delete_dialog.NATIVE_ENTITIES``
(which lists *which* entities are native) by recording *which
base type* each native entity uses, so the field catalog in
``espo_impl.core.audit_utils`` can be looked up.
"""

from __future__ import annotations

# Native entity name -> base type string used by
# audit_utils._TYPE_NATIVE_FIELDS.
NATIVE_ENTITY_BASE_TYPE: dict[str, str] = {
    "Contact": "Person",
    "Lead": "Person",
    "User": "Person",
    "Account": "Company",
    "Opportunity": "Base",
    "Case": "Base",
    "Document": "Base",
    "Campaign": "Base",
    "TargetList": "Base",
    "Team": "Base",
    "Task": "Base",
    "Meeting": "Event",
    "Call": "Event",
    "Email": "Base",
}


def get_base_type(entity_name: str) -> str | None:
    """Return the EspoCRM base type for the named native entity.

    :param entity_name: Entity natural name (e.g. ``Contact``).
    :returns: Base type string (``Person | Company | Event | Base``)
        if `entity_name` is a known native entity, otherwise None.
        Custom entities resolve to None — callers should use the
        entity's declared ``type`` field for those.
    """
    return NATIVE_ENTITY_BASE_TYPE.get(entity_name)
