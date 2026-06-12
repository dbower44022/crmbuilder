"""Transforms that carry external artifacts into the V2 requirements graph.

First member: the AuditReport-to-candidate deposit transform
(:mod:`crmbuilder_v2.transform.audit_deposit`, WTK-090 design spec) —
the Phase 1.5 path that turns a V1 audit's ``audit-report.json``
manifest into candidate methodology records with deposit-event
provenance and utilization evidence.
"""
