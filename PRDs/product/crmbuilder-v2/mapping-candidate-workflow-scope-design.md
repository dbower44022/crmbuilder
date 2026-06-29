# Mapping-candidate Workflow — Scope: External Migrations Only (Design)

- **Status:** Design (REL-038 / PRJ-075, PI-352, WSK-193 / WTK-253)
- **Implements:** REQ-393 — *Full-fidelity audit for an instance that is both source and target* (the requirement's scoping clause: *"The mapping-candidate workflow that defers objects pending human review must apply only to instances being migrated in from a separate external system."*)
- **Provenance:** TOP-091 (Multi-instance CRM audit & inventory); SES-293 / CNV-236
- **Area:** methodology-process
- **Companion design slices (WSK-193):** WTK-250 (the `both` value on the Instance entity), WTK-251 (full-inventory audit behavior for a both-role instance), WTK-252 (capture-back availability for a both-role instance). This document specifies only the **scope of the mapping-candidate workflow** — *which instances it applies to, and which it must never be applied to*. The companion WTK-251 specifies what a both-role audit does instead.

> This is the methodology/behavior specification for the boundary of the
> mapping-candidate workflow. It defines *required behavior and acceptance* — the
> rule that governs when the candidate path is selected and when it is forbidden —
> not the code. The Development phase (WSK-194) implements it (slice WTK-258); the
> Test phase (WSK-195) verifies it (slice WTK-263) against the acceptance below.

## 1. Purpose

The **mapping-candidate workflow** is the part of the audit pipeline that, instead
of reconciling a live object directly into the inventory, defers it as a
**`mapping_candidate`** pending human review: a live object is recorded as
`present`/`drifted` only when a human-resolved **`source_mapping`** points it at a
canonical design object, and an unmapped live object surfaces as a candidate the
operator must adjudicate. It exists for one situation: pulling structure **in from
a separate external system** whose objects have no pre-existing correspondence to
the canonical design, so a human must decide how each foreign object maps before
it is admitted.

This document fixes the **scope** of that workflow: it applies **only** to an
instance being migrated in from a separate external system — i.e. an instance whose
role is **`source`** — and it must **never** be applied to a **`both`**-role
instance (an instance the canonical design was deployed to and is also captured back
from). Scoping is the single rule; the behavior a both-role instance gets *instead*
is specified by WTK-251.

## 2. Background — why the scope must be stated explicitly

The current routing collapses `source` and `both` into one predicate. In
`introspect/reconcile.py`:

```
_SOURCE_ROLES: frozenset[str] = frozenset({"source", "both"})   # line 254
def _is_source_audit(...) -> bool: ... rec.get("instance_role") in _SOURCE_ROLES
```

and identically in `api/routers/instances.py` (`_is_source_audit`, line 311,
`rec.get("instance_role") in ("source", "both")`). Because `both` falls inside the
predicate, a both-role audit is routed through `_reconcile_*_candidate_gated`, which
recognizes a live object only against a resolved `source_mapping` and otherwise
defers it as a `mapping_candidate`. A deployed-to instance normally has **zero**
resolved mappings, so the candidate-gated pass recognizes nothing, writes no
membership, and the absent-sweep then clobbers the prior good inventory. This is the
06-26 → 06-28 CBM Production defect (audit reported success at 0 entities / 0 fields
/ 0 relationships).

The candidate workflow is not wrong — it is correctly built for a **purely external**
source whose objects have no canonical counterpart. It is being *applied to the wrong
instances*. Stating the scope as a binding rule — `source` only, `both` never — is what
closes the misapplication. WTK-251 specifies the full-inventory drift path a both-role
instance must take instead; this slice specifies the matching boundary on the candidate
workflow so the two are exhaustive and disjoint.

## 3. Required behavior

### 3.1 The candidate workflow applies only to `source`-role instances

The mapping-candidate workflow — candidate creation, `source_mapping` resolution,
and the candidate-gated reconcile (`_reconcile_*_candidate_gated`) — is selected
**only** when the audited instance's `instance_role` is **`source`**: an instance
being migrated in from a separate external system. For a `source` instance the
workflow is unchanged: unmapped live objects surface as `mapping_candidate` rows, a
human-resolved `source_mapping` admits a live object into the inventory, and no
canonical object is auto-created from an unmapped live one.

### 3.2 The candidate workflow is never applied to a `both`-role instance

A `both`-role instance is **excluded** from the mapping-candidate workflow in its
entirety. Auditing a `both` instance must:

- **never create a `mapping_candidate`** for any area;
- **never read, require, or resolve a `source_mapping`**;
- **never route any area through `_reconcile_*_candidate_gated`.**

Instead it runs the full drift reconcile over every area, as specified by WTK-251.
A both-role audit run against a fresh inventory with **zero `source_mapping` rows
present** must still fully populate `present`/`drifted`/`absent` membership — which
is only possible because the candidate workflow is not on its path.

### 3.3 The scope is enforced by splitting the routing predicate

The implementation seam is the role predicate, which currently admits `both`. The
rule is: the candidate path is selected by an `instance_role == "source"` test, **not**
by membership in a `{source, both}` set. Concretely, the three places that treat
`both` as candidate-gated must be narrowed to `source`:

| Seam | File | Today | Required |
|------|------|-------|----------|
| Reconcile role set | `introspect/reconcile.py:254` (`_SOURCE_ROLES`) | `{source, both}` | candidate-gating selected for `source` only |
| Audit-route predicate | `api/routers/instances.py:311` (`_is_source_audit`) | `role in (source, both)` | candidate-gating selected for `source` only |
| Area truncation | `api/routers/instances.py` (`_SOURCE_AUDIT_AREAS`) | applied to `source`+`both` | applied to `source` only |

`both` must route to the full drift path and the full area set (WTK-251 §3.1–3.2).
The Development phase chooses how to express this (a dedicated `source`-only test, a
distinct `both` branch, or both); this design fixes only the *required outcome* — `both`
takes no candidate path — not the code shape.

### 3.4 A `target`-role instance is unaffected

A `target`-role instance never entered the candidate workflow and does not now: it
runs the full drift reconcile already. This slice changes nothing for `target`; it
only removes `both` from the candidate workflow and leaves `source` as the workflow's
sole remaining role.

### 3.5 Migration mapping stays whole for external sources

Narrowing the workflow's scope does **not** weaken it for the case it exists for. For
a `source` instance every capability is retained unchanged: candidate creation, the
`source_mapping` / transform-rule model, name-match suggestion, and human resolution.
The external-migration path is fully preserved; only its over-application to deployed-to
instances is removed.

## 4. What stays unchanged

- The **candidate-gated** reconcile, the `mapping_candidate` entity, and the
  `source_mapping` resolution model are retained unchanged — reserved for `source`-only
  instances migrating in from a separate external system.
- A **`target`** audit is unchanged (full drift reconcile, all areas).
- The drift reconcile's neutral-name matching and `present/drifted/absent` membership
  model are unchanged; this slice only ensures `both` reaches them by keeping the
  candidate workflow off the `both` path.
- The neutral-design model and capture-back (WTK-252) are unaffected by this scoping.

## 5. Acceptance

This slice is satisfied when:

1. The mapping-candidate workflow is selected **only** for an instance with
   `instance_role = source`; auditing such an instance still produces candidates and
   resolves them via `source_mapping` exactly as before.
2. Auditing an instance with `instance_role = both` **creates no `mapping_candidate`**,
   reads or resolves **no `source_mapping`**, and routes **no area** through the
   candidate-gated reconcile.
3. A `both`-role audit run with **zero `source_mapping` rows present** still populates
   `present`/`drifted`/`absent` membership across all areas (the WTK-251 outcome),
   demonstrating the candidate workflow is off its path.
4. A `target`-role audit is unchanged by this slice.
5. The external-source migration capability (candidate creation, `source_mapping`,
   transform rules, suggestions, resolution) is fully retained for a `source` instance.

Acceptance items 1–5 implement REQ-393's scoping clause; the Test phase (WSK-195,
slice WTK-263) exercises them, with the CBM Production both-role instance (INST-002,
no resolved mappings) as the worked validation case for items 2–3 and a `source`-role
external instance for items 1 and 5.
