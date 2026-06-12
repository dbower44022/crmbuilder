"""Phase 1.5 source adapters (WTK-110 design spec).

An adapter is anything that produces the serialized manifest pair the
landed deposit transform consumes — ``audit-report.json`` plus the
optional ``utilization-profile.json`` (the seam, WTK-110 §2).
Everything downstream of the pair — candidate mapping, scope rules,
evidence attachment, deposit-event provenance, idempotent re-runs —
is ``crmbuilder_v2.transform.audit_deposit`` and is shared, not
per-adapter. The seam keeps this package import-free of both
``espo_impl`` and the transform internals.
"""
