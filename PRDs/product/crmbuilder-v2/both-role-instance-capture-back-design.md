# Both-role Instance — Live-to-Design Capture Availability (Design)

- **Status:** Design (REL-038 / PRJ-075, PI-352, WSK-193 / WTK-252)
- **Implements:** REQ-393 — *Pushing a live change back into the design must remain available for a both-role instance*
- **Provenance:** TOP-091 (Multi-instance CRM audit & inventory); SES-293 / CNV-236
- **Area:** methodology-process
- **Companion design slices (WSK-193):** WTK-250 (the `both` value on the Instance entity), WTK-251 (full-inventory audit behavior — see `both-role-instance-audit-behavior-design.md`), WTK-253 (scoping the mapping-candidate workflow to external migrations). This document specifies only the **live-to-design capture availability** that WTK-251 §3.6 defers to here.

> This is the methodology/behavior specification for the rule that
> live-to-design capture-back stays available for a both-role instance.
> It defines *required behavior and acceptance*, not the code. The
> Development phase (WSK-194) implements it; the Test phase (WSK-195)
> verifies it against the acceptance below.

## 1. Purpose

An Instance in the V2 model may carry one of three roles: `source`, `target`,
or `both` (see WTK-250). A `both` instance is at once a **deployment target**
(the design has been, or will be, pushed to it) and a **design source** (live
changes made on it may be captured back into the design). The Cleveland
Business Mentors Production instance (INST-002) is the canonical example: the
canonical design was deployed to it, and operators also adjust it live.

The companion audit slice (WTK-251) re-routes a both-role instance's audit
through the full drift reconcile and corrects the routing predicate that had
conflated `source` and `both`. This document specifies a separate, narrower
guarantee that travels alongside that change: **changing how a both-role
instance is audited must not remove its ability to push a live change back into
the design.** Capture-back stays available for a both-role instance, before and
after the WTK-251 routing fix.

## 2. Background — why this needs stating

"Live-to-design capture-back" is the operator action of taking a value that was
changed directly on a live instance and writing it onto the canonical design,
so the design reflects the as-built reality. In the current system it is the
reconcile surface's **capture** and **publish** family:

- `POST /reconcile/capture` → `reconcile_apply.capture_field_attribute` —
  capture a live **field**-attribute value into the canonical field (REQ-356);
- `POST /reconcile/capture-setting` → `reconcile_apply.capture_entity_setting` —
  capture a live **entity-collection-setting** value (sort field/direction,
  full-text search, text-filter fields) onto the canonical entity (REQ-375);
- `POST /reconcile/publish` → `reconcile_apply.record_publish` — the design→instance
  direction of the same reconcile surface, retained as the symmetric partner.

These operations are **not role-gated today.** `capture_field_attribute` and
`capture_entity_setting` key entirely off the instance's recorded drift
membership/override for the named attribute — they read the instance's deviation
and write it onto the design; they never inspect `instance_role`. An instance
can be captured from whenever it has recorded drift, regardless of role.

The risk this slice closes is a **regression-by-association**: the WTK-251 fix
sharpens the `source` / `both` distinction across the audit-routing predicates
(`_is_source_audit`, `_SOURCE_ROLES`, `_SOURCE_AUDIT_AREAS`). A natural but wrong
reading of "a both-role instance is audited as a target, not a source" would be
to conclude that capture-back — a *source*-flavored, instance-to-design
operation — should now be withheld from a both-role instance. That conclusion is
incorrect: capture-back is exactly the capability that makes the `both` role
*both*. This document records the rule explicitly so the audit-routing change
cannot be over-applied into the capture path.

## 3. Required behavior

### 3.1 Capture-back is available for a both-role instance

For an instance with `instance_role = both`, the live-to-design capture
operations succeed on the same terms as for any other instance:

- capturing a live **field**-attribute value into the design;
- capturing a live **entity-collection-setting** value into the design;
- the symmetric design→instance **publish** of an object.

A both-role instance may be the `source_ref` of a `capture` transaction and the
`instance` of a `publish`. Carrying the `both` role neither blocks these
operations nor adds a precondition to them.

### 3.2 Capture-back stays role-agnostic — no new role gate

The capture and capture-setting paths must remain **role-agnostic**: eligibility
to capture an attribute is determined by whether the instance records a
deviation for that attribute (the existing `ConflictError` when there is nothing
to capture), **not** by the instance's role. The WTK-251 audit-routing fix must
not introduce a role check into `reconcile_apply.capture_field_attribute`,
`reconcile_apply.capture_entity_setting`, `record_publish`, or the
`/reconcile/capture`, `/reconcile/capture-setting`, and `/reconcile/publish`
endpoints. (`source` and `target` instances capture-back today as well; this
slice's specific charge is that `both` is not singled out for a new restriction.)

### 3.3 Audit and capture-back are independent

The full-inventory audit (WTK-251) and capture-back are **independent surfaces**
that operate on the same instance without interfering:

- Running a both-role audit does not consume, disable, or pre-empt the
  instance's capture-back availability.
- The audit *populates* the drift membership that capture-back later *reads* —
  an audit classifies a live field as `drifted` with a per-attribute override;
  capture-back then promotes a chosen override value into the design. This is a
  feed-forward relationship, not a conflict: the audit makes capture-back more
  useful (it surfaces what drifted), and never removes it.
- Capture-back's post-write membership recompute (drop the captured attribute
  from the override; state → `present` when no override remains, else `drifted`)
  is unchanged for a both-role instance.

### 3.4 No pre-resolved mappings are a precondition

Capturing a live change back into the design for a both-role instance must
succeed with **zero `source_mapping` rows present.** Capture-back reads the
instance's own drift membership, not a foreign-migration mapping; mapping
resolution is a `source`-only external-migration concern (WTK-253) and is not on
the both-role capture path at all. This matches the both-role audit's same
no-mappings-required precondition (WTK-251 §3.5).

## 4. What stays unchanged

- The reconcile surface's **capture / capture-setting / publish** semantics,
  transaction logging, drift-membership recompute, and data-loss / rollback
  guards are unchanged; this design only asserts that the `both` role does not
  gate them.
- `source` and `target` instances continue to capture-back exactly as today.
- The companion audit-routing change (WTK-251) is unchanged by this slice; this
  slice constrains that change so it is not over-applied into the capture path.

## 5. Acceptance

This slice is satisfied when, for an instance with `instance_role = both`:

1. Capturing a live **field**-attribute value into the design succeeds (the
   captured value lands on the canonical field, a `capture` transaction is
   logged, and the attribute's drift clears on the instance).
2. Capturing a live **entity-collection-setting** value into the design succeeds
   on the same terms.
3. Both succeed with **no** `source_mapping` rows present.
4. Neither the capture access functions nor the capture endpoints reject or add
   a precondition because the instance's role is `both` — eligibility is decided
   solely by whether a deviation exists to capture.
5. Running a full-inventory both-role audit (WTK-251) before or after a capture
   does not disable capture-back; the two surfaces operate independently on the
   same instance.

Acceptance item 5 corresponds to WTK-251 §3.6 acceptance item 5
("Capturing a live setting back into the design still succeeds for that
instance"); this document carries the full statement that the audit slice
defers here. The Test phase (WSK-195) exercises items 1–5, with the CBM
Production both-role instance as the worked validation case.
