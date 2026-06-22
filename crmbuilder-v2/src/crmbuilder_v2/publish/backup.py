"""Pre-publish target backup capture (PRJ-042, PI-262 — REQ-292).

Before a publish writes to a live target, capture a point-in-time snapshot of
the target's current configuration so the publish is reviewable and reversible.
The capture is **read-only** and reuses the same introspection primitives the
audit path uses (``get_all_scopes`` → :func:`map_entity_specs` →
``get_entity_field_list`` / ``get_all_links``), scoped to the entities the
publish is about to touch.

A total failure to read the target's scopes raises :class:`BackupCaptureError`
— the publish service turns that into the REQ-292 gate (no backup → no publish,
unless explicitly overridden). Per-entity read failures are non-fatal: they are
recorded as ``warnings`` on the snapshot so a partial backup still proceeds.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from espo_impl.core.reconcile.live_state import map_entity_specs


class BackupCaptureError(RuntimeError):
    """The target's current configuration could not be captured at all."""


def capture_target_backup(
    client, entity_names: Iterable[str]
) -> dict[str, Any]:
    """Capture a read-only snapshot of the target's current configuration.

    :param client: a connected ``EspoAdminClient`` (exposes ``get_all_scopes``,
        ``get_entity_field_list``, ``get_all_links``).
    :param entity_names: natural names of the entities the publish will touch.
    :returns: a JSON-serializable snapshot
        ``{captured_for, scopes, entities: {name: {espo_name, fields, links}},
        warnings}``.
    :raises BackupCaptureError: when the target's scopes cannot be read (the
        snapshot would be empty / meaningless).
    """
    names = sorted(set(entity_names))
    status, scopes = client.get_all_scopes()
    if status != 200 or not isinstance(scopes, dict):
        raise BackupCaptureError(
            f"could not read the target's scopes (HTTP {status})"
        )

    specs, unmapped = map_entity_specs(names, scopes)
    warnings: list[str] = [
        f"{name}: not present on the target — nothing to back up" for name in unmapped
    ]

    entities: dict[str, Any] = {}
    captured_scopes: dict[str, Any] = {}
    for spec in specs:
        captured_scopes[spec.espo_name] = scopes.get(spec.espo_name)
        fstatus, fields = client.get_entity_field_list(spec.espo_name)
        if fstatus != 200 or not isinstance(fields, dict):
            warnings.append(
                f"{spec.yaml_name}: could not read fields (HTTP {fstatus})"
            )
            fields = None
        lstatus, links = client.get_all_links(spec.espo_name)
        if lstatus != 200 or not isinstance(links, dict):
            links = None
        entities[spec.yaml_name] = {
            "espo_name": spec.espo_name,
            "fields": fields,
            "links": links,
        }

    return {
        "captured_for": names,
        "scopes": captured_scopes,
        "entities": entities,
        "warnings": warnings,
    }
