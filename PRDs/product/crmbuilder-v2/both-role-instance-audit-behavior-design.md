# Both-role Instance — Full-inventory Audit Behavior (Design)

- **Status:** Design (REL-038 / PRJ-075, PI-352, WSK-193 / WTK-251)
- **Implements:** REQ-393 — *Full-fidelity audit for an instance that is both source and target*
- **Provenance:** TOP-091 (Multi-instance CRM audit & inventory); SES-293 / CNV-236
- **Area:** methodology-process
- **Companion design slices (WSK-193):** WTK-250 (the `both` value on the Instance entity), WTK-252 (capture-back availability for a both-role instance), WTK-253 (scoping the mapping-candidate workflow to external migrations). This document specifies only the **audit behavior**.

> This is the methodology/behavior specification for what an audit of a
> both-role instance must do. It defines *required behavior and acceptance*,
> not the code. The Development phase (WSK-194) implements it; the Test phase
> (WSK-195) verifies it against the acceptance below.

## 1. Purpose

An Instance in the V2 model may carry one of three roles: `source`, `target`,
or `both` (see WTK-250). A `both` instance is at once a **deployment target**
(the design has been, or will be, pushed to it) and a **design source** (live
changes made on it may be captured back into the design). The Cleveland
Business Mentors Production instance (INST-002) is the canonical example: the
canonical design was deployed to it, and operators also adjust it live.

This document specifies how such a both-role instance is **audited** — that is,
how its live structure is read and reconciled into the inventory. The governing
rule is simple: **a both-role instance is audited as a complete inventory of
the live system, classified against the design, with no pre-resolved mappings
required.** It is never routed through the foreign-migration candidate path.

## 2. Background — the defect this design corrects

The current audit routing (in `introspect/reconcile.py` and
`api/routers/instances.py`) treats `source` **and** `both` identically via a
single predicate (`_SOURCE_ROLES = {"source", "both"}`, `_is_source_audit`).
This has two consequences for a both-role instance, both wrong:

1. **Wrong reconcile path.** Its entities, fields, and relationships are routed
   through the *candidate-gated* reconcile, which only records a live object as
   present/drifted when a **resolved `source_mapping`** points the live object
   at a canonical design object; unmapped live objects become deferred
   *candidates* awaiting human review. With zero resolved mappings — the normal
   state for a deployed-to instance — nothing is recognized, and the
   absent-sweep flips the prior inventory to `absent`.
2. **Truncated area coverage.** A source/both audit only runs the three
   "design-input" areas (`_SOURCE_AUDIT_AREAS = {entities, fields,
   associations}`); layouts, roles, field-permissions, teams, and filtered tabs
   are skipped as "deploy-fidelity" concerns. A both-role instance *is* a deploy
   target, so those areas are exactly what its inventory must include.

The empirical outcome (06-26 → 06-28 CBM Production debugging): the audit
reported success while showing 0 entities / 0 fields / 0 relationships, and the
prior good inventory snapshot was clobbered. The candidate path is correct only
for a **purely external** source being migrated *in* from a separate system,
where no design object yet corresponds to the live object. It is the wrong tool
for an instance the design was deployed to.

## 3. Required behavior

### 3.1 A both-role audit runs the full drift reconcile

When the audited instance's `instance_role` is `both`, **every** audit area is
reconciled through the **drift** path (`_reconcile_*_drift`), the same path a
`target` audit uses today. The drift path:

- reads the live object set for the area from the instance;
- matches each live object to its canonical design object by **neutral name**
  (entity name; `(entity, field)`; relationship endpoints; etc.) — **no
  `source_mapping` lookup, and none required**;
- classifies each matched object as **`present`** (live state equals design) or
  **`drifted`** (live state differs, with a sparse per-attribute override
  recording what differs);
- classifies a design object with no live counterpart as **`absent`**;
- writes the result as the instance's inventory membership for that area.

A both-role audit therefore **never creates candidates** and **never consults
or requires `source_mapping` rows.**

### 3.2 Every audit area is covered

A both-role audit reconciles the complete area set, not the truncated
source set. The required areas, and the requirement's named coverage, are:

| Audit area (reconcile fn)      | REQ-393 coverage term |
|--------------------------------|-----------------------|
| `entities`                     | entities              |
| `fields`                       | fields                |
| `associations`                 | relationships         |
| `layouts`                      | layouts               |
| `roles`                        | roles                 |
| `teams`                        | teams                 |
| `field_permissions`            | (within roles/teams)  |
| `filtered_tabs`                | (deploy-fidelity)     |

The first six satisfy the requirement's acceptance verbatim
("entities, fields, relationships, layouts, roles, and teams"); the last two
are reconciled as well because they are part of a target's deploy-fidelity
inventory and a both-role instance is a target.

### 3.3 Every live object is classified — no silent omission

For each area, the audit produces a complete classification: every live object
resolves to `present`, `drifted`, or `absent` relative to the design. A live
object the audit reads but cannot place is a **drift finding to surface**, never
a silently dropped row. (The complementary safety rule — that an audit pass must
not erase another pass's inventory, and `absent` is asserted only when the
instance was read successfully and the object is genuinely gone — is specified
separately under REQ-394 / PI-353 and is a precondition for trusting the
`absent` classification here.)

### 3.4 The instance must be auditable in this role

A both-role instance must pass the auditability gate and run the full audit.
Concretely, the role-routing predicate must distinguish `source` from `both`:
the candidate-gated path is selected **only** for `source`; `both` selects the
drift path and the full area set. (The current `target`-is-`not_auditable`
gate, `_is_source_audit` returning true for `both`, and the
`_SOURCE_AUDIT_AREAS` truncation are the three code seams the Development phase
must correct — named here so the implementation is unambiguous, not prescribed
in detail.)

### 3.5 No pre-resolved mappings are a precondition

Auditing a both-role instance must succeed against a fresh inventory with **zero
`source_mapping` rows present**. Mapping resolution is a foreign-migration
concern (WTK-253) and is not on the both-role audit path at all.

### 3.6 Capture-back remains available

Auditing a both-role instance as a full inventory does **not** remove its
ability to push a live change back into the design. Instance-to-design
capture-back (`reconcile_apply.capture_*`) is not role-gated and continues to
work for a both-role instance; the audit and the capture-back are independent
and both available. (Specified in full under WTK-252.)

## 4. What stays unchanged

- The **candidate-gated** reconcile and the mapping-candidate workflow are
  retained unchanged, reserved for `source`-only instances migrating in from a
  separate external system (WTK-253).
- A **`target`** audit is unchanged — it already runs the full drift reconcile;
  a both-role audit simply runs the same path.
- The drift reconcile's neutral-name matching, sparse per-attribute drift
  override, and `present/drifted/absent` membership model are unchanged; this
  design only routes `both` into them.

## 5. Acceptance

This slice is satisfied when, for an instance with `instance_role = both`:

1. An audit run, with **no** `source_mapping` rows present, populates
   `present` / `drifted` / `absent` inventory membership for **entities,
   fields, relationships, layouts, roles, and teams** (and the additional
   field-permission / filtered-tab areas).
2. The audit **creates no candidates** and does not require, read, or resolve
   any `source_mapping`.
3. Every live object read in each area is classified `present`, `drifted`, or
   `absent` — none is silently omitted.
4. The both-role instance is accepted by the auditability gate (it is not
   reported `not_auditable`).
5. Capturing a live setting back into the design still succeeds for that
   instance.

Acceptance items 1–5 mirror REQ-393's acceptance summary; the Test phase
(WSK-195) exercises them, with the CBM Production both-role instance as the
worked validation case.
