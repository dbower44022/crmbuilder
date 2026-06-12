"""Inline evidence object assembly (WTK-097 design spec §3).

The single normalized JSON shape every surface presents for one
``utilization_evidence`` row — the transform's ``--dry-run`` plan, the
``include_evidence`` candidate-API projection, the evidence endpoints,
the Baseline Report, and Phase 3 triage all derive it from the stored
row through :func:`project_evidence_object`, deterministically (§3.4):
drop the ``evidence_`` prefix, partition the typed columns into the
envelope and ``metrics`` (absent metrics are **omitted, not null** —
"no evidence" and "evidence of zero" must not be confusable), lift the
five advisory flag keys from ``evidence_detail`` into ``flags`` (§3.3 —
stored once, surfaced at top level), and pass ``detail`` through
verbatim per the §4 key schema.

Pure functions only — no ORM, no session. The repository layer
(:mod:`crmbuilder_v2.access.repositories.utilization_evidence`) owns
the row reads and the §7.1 latest-snapshot selection; the transform
imports this module to render plan-time objects without touching the
database (acceptance criterion A8 — plan/read parity).
"""

from __future__ import annotations

# The §3.3 advisory flag keys, lifted from ``detail`` into the object's
# top-level ``flags`` block: the WTK-096 §5 entity flags (``dormant``,
# ``empty``) and field flags (``low_population``, ``stale``,
# ``ghost_options``). Flags are a rendering of the typed metrics at the
# recorded ``detail.thresholds``; the metrics win on disagreement.
EVIDENCE_FLAG_KEYS = ("dormant", "empty", "low_population", "stale", "ghost_options")

# Envelope columns (§3.1) — always present on the object, value may be
# null (``deposit_event`` is null for standalone re-profiles). Maps the
# object key to the row-column stem it projects.
_ENVELOPE_KEYS = (
    ("subject_type", "evidence_subject_type"),
    ("subject_identifier", "evidence_subject_identifier"),
    ("profiled_at", "evidence_profiled_at"),
    ("source_label", "evidence_source_label"),
    ("deposit_event", "evidence_deposit_event_identifier"),
    ("catalog_class", "evidence_catalog_class"),
)

# Typed metric columns (WTK-088 §4.3) — omitted from ``metrics`` when
# NULL on the row.
_METRIC_KEYS = (
    "record_count",
    "last_record_created_at",
    "populated_count",
    "population_rate",
    "last_populated_at",
    "distinct_value_count",
    "declared_option_count",
    "used_option_count",
)


def project_evidence_object(row: dict) -> dict:
    """Assemble the §3 inline evidence object from one row dict.

    ``row`` is the serialized form the repository returns (column names
    as keys, datetimes already ISO strings). Pure: two surfaces
    rendering the same row produce identical objects (§3.4). A row with
    no ``evidence_detail`` projects ``detail: {}`` and ``flags: {}`` —
    present-and-empty, which is itself signal (§8 A3).
    """
    obj: dict = {key: row.get(column) for key, column in _ENVELOPE_KEYS}
    obj["metrics"] = {
        key: row[f"evidence_{key}"]
        for key in _METRIC_KEYS
        if row.get(f"evidence_{key}") is not None
    }
    detail = row.get("evidence_detail") or {}
    obj["flags"] = {key: detail[key] for key in EVIDENCE_FLAG_KEYS if key in detail}
    obj["detail"] = detail
    return obj
