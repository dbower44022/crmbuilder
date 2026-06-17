"""The reconciliation-merge engine — pure core (PI-215, §5.4/§16.5).

PRJ-031, DEC-483…487 (RC-2/RC-3). :func:`reconcile_artifact` is a pure,
deterministic, order-independent N-way three-way merge of a set of demanded
deltas against one artifact's live base, classifying every same-facet overlap by
the facet taxonomy: NONE / IDENTICAL / COMPOSE / ADDITIVE-UNION auto-merge; only a
same-facet contradiction (facet_value) or a remove-vs-modify is a CONFLICT. No
database, no judgment — the orchestration (``repositories.reconciliation``)
persists conflicts and the resolver settles them.

Artifact shape (a generic convention so the engine is artifact-agnostic)::

    {"fields": {name: {facet: value}}, "attributes": {facet: value}}

A delta::

    {requirement_identifier, field, facet, op, value}

``field=""`` targets an attribute; ``op`` is ``set`` (scalar) / ``add``
(set-valued, e.g. enum options) / ``remove`` (drop the field).
"""

from __future__ import annotations

import copy
from typing import Any

_FIELD_FACET = "__field__"  # the locus for a field add/remove (vs a facet edit)


def _as_list(value: Any) -> list:
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _competing(deltas: list[dict]) -> list[dict]:
    return [
        {
            "requirement": d.get("requirement_identifier"),
            "op": d.get("op"),
            "value": d.get("value"),
        }
        for d in deltas
    ]


def _reqs(deltas: list[dict]) -> list[str]:
    return sorted({d["requirement_identifier"] for d in deltas})


def reconcile_artifact(base: dict | None, deltas: list[dict]) -> dict:
    """Merge ``deltas`` onto ``base``; return ``{merged, conflicts, provenance}``.

    Pure and deterministic — the result is independent of delta order. Conflicts
    carry ``{field, facet, conflict_type, competing}``; provenance carries
    ``{field, facet, requirements}`` for each auto-merged change.
    """
    merged = copy.deepcopy(base) if base else {}
    merged.setdefault("fields", {})
    merged.setdefault("attributes", {})

    conflicts: list[dict] = []
    provenance: list[dict] = []

    by_field: dict[str, list[dict]] = {}
    for d in deltas:
        by_field.setdefault(d.get("field", ""), []).append(d)

    for field in sorted(by_field):
        ds = by_field[field]
        removes = [d for d in ds if d.get("op") == "remove"]
        mods = [d for d in ds if d.get("op") in ("set", "add")]
        is_attr = field == ""

        def _target(_field=field, _is_attr=is_attr) -> dict:
            # Created lazily so a fully-contended field leaves no empty entry.
            if _is_attr:
                return merged["attributes"]
            return merged["fields"].setdefault(_field, {})

        def _base_facet(facet, _field=field, _is_attr=is_attr):
            bag = merged["attributes"] if _is_attr else merged["fields"].get(
                _field, {}
            )
            return bag.get(facet)

        if removes and mods:
            conflicts.append({
                "field": field, "facet": _FIELD_FACET,
                "conflict_type": "remove_vs_modify", "competing": _competing(ds),
            })
            continue
        if removes:
            if not is_attr:
                merged["fields"].pop(field, None)
                provenance.append({
                    "field": field, "facet": _FIELD_FACET,
                    "requirements": _reqs(removes),
                })
            continue

        by_facet: dict[str, list[dict]] = {}
        for d in mods:
            by_facet.setdefault(d.get("facet"), []).append(d)
        for facet in sorted(by_facet, key=lambda x: (x is None, x)):
            fds = by_facet[facet]
            sets = [d for d in fds if d.get("op") == "set"]
            adds = [d for d in fds if d.get("op") == "add"]
            if sets and adds:
                conflicts.append({
                    "field": field, "facet": facet,
                    "conflict_type": "facet_value", "competing": _competing(fds),
                })
                continue
            if adds:
                vals = _as_list(_base_facet(facet))
                for d in adds:
                    vals.extend(_as_list(d.get("value")))
                # dedupe + sort for an order-independent, deterministic union.
                frozen = sorted({_freeze(v) for v in vals}, key=_sortkey)
                _target()[facet] = _restore_list(frozen)
                provenance.append({
                    "field": field, "facet": facet, "requirements": _reqs(adds),
                })
                continue
            distinct = []
            for d in sets:
                if d.get("value") not in distinct:
                    distinct.append(d.get("value"))
            if len(distinct) > 1:
                conflicts.append({
                    "field": field, "facet": facet,
                    "conflict_type": "facet_value", "competing": _competing(sets),
                })
            else:
                _target()[facet] = distinct[0]
                provenance.append({
                    "field": field, "facet": facet, "requirements": _reqs(sets),
                })

    return {"merged": merged, "conflicts": conflicts, "provenance": provenance}


# Union values may be unhashable (dicts); freeze for set-dedupe, then restore.
def _freeze(v: Any) -> Any:
    if isinstance(v, dict):
        return ("__d__", tuple(sorted((k, _freeze(x)) for k, x in v.items())))
    if isinstance(v, list):
        return ("__l__", tuple(_freeze(x) for x in v))
    return v


def _restore(v: Any) -> Any:
    if isinstance(v, tuple) and len(v) == 2 and v[0] == "__d__":
        return {k: _restore(x) for k, x in v[1]}
    if isinstance(v, tuple) and len(v) == 2 and v[0] == "__l__":
        return [_restore(x) for x in v[1]]
    return v


def _restore_list(frozen: list) -> list:
    return [_restore(v) for v in frozen]


def _sortkey(v: Any):
    # Deterministic ordering across heterogeneous frozen values.
    return (type(v).__name__, repr(v))
