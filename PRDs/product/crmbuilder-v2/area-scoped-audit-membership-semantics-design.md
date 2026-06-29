# Area-scoped Audit Membership Semantics (Design)

- **Status:** Design (REL-038 / PRJ-075, PI-353, WSK-196 / WTK-265)
- **Implements:** REQ-394 — *An audit pass must not erase another pass's recorded inventory*
- **Provenance:** TOP-091 (Multi-instance CRM audit & inventory); SES-293 / CNV-236
- **Area:** automation
- **Companion design:** `both-role-instance-audit-behavior-design.md` (REQ-393 / PI-352)
  specifies *which* reconcile path a both-role instance takes; this document
  specifies the **write boundaries and absent condition** that any audit pass —
  drift or candidate-gated — must obey, and is the precondition that lets the
  companion design trust its `absent` classification (its §3.3).

> This is the methodology/behavior specification for how an audit pass writes
> inventory membership. It defines *required behavior and acceptance*, not the
> code. The Development phase implements it; the Test phase verifies it against
> the acceptance below.

## 1. Purpose

A single audit of one instance runs as a **sequence of independent passes**, one
per audit area — entities, fields, associations, layouts, roles, teams,
filtered tabs (the seven `member_type` values in
`vocab.INSTANCE_MEMBERSHIP_MEMBER_TYPES`). Each pass reads its own slice of the
live instance and writes the corresponding slice of the instance's inventory
membership (the `instance_membership` rows). The passes share one instance and
one inventory, so the inventory after an audit is the **merge** of every pass's
per-area write.

This document fixes the **boundary** of each pass's write authority and the
**condition** under which an object may be marked `absent`, so that the passes
compose safely: no pass may damage the inventory another pass of the same audit
recorded, and no pass may assert absence it did not actually observe.

## 2. Background — the defect this design corrects

The membership write model is two operations per pass (`introspect/reconcile.py`):

1. **upsert** the `present` / `drifted` rows the pass resolved
   (`instance_membership.upsert_membership`), then
2. **sweep** every existing row of *this pass's* `member_type` not in the
   resolved set to `absent` (`instance_membership.mark_absent_missing`, which is
   already filtered `WHERE instance_identifier = ? AND member_type = ?`).

The sweep runs **unconditionally at the end of every pass** — including a pass
that resolved nothing. That is the failure:

- The **candidate-gated** reconcile path
  (`_reconcile_*_candidate_gated`) only records a live object as
  present/drifted when a **resolved `source_mapping`** points it at a canonical
  design object. On an instance with zero resolved mappings (the normal state
  for a deployed-to instance), the resolved set is empty, the sweep runs with an
  empty `present_member_identifiers`, and **every prior membership row for that
  area is flipped to `absent`** — erasing inventory that an earlier audit
  recorded. The 06-26 → 06-28 CBM Production debugging showed exactly this: the
  audit reported success while the inventory read 0 entities / 0 fields /
  0 relationships, and the prior good snapshot was clobbered.

- The same hazard exists for **any** pass whose live read returned an
  inconclusive empty result rather than an authoritative "the instance has
  none." The **drift** path partially guards this by *raising* `ReconcileError`
  when the live read is non-200 (e.g. `get_all_scopes returned status=…`), which
  aborts the pass *before* the sweep. But that guard is incidental to one read
  call, not a stated contract, and the candidate-gated path has no equivalent.

The root cause is that the sweep treats "I resolved nothing" as "the instance
contains nothing," when the two are only the same if the live read **succeeded
and was authoritative**.

## 3. Required behavior

### 3.1 A pass writes only the membership its own area resolved

Each audit pass has write authority over **exactly one `member_type`** — its
area. A pass:

- **may** upsert `present` / `drifted` / `absent` rows whose `member_type`
  equals its own area, and
- **must not** create, modify, or delete any membership row of a different
  `member_type`.

The existing `member_type` filter on both `upsert_membership` (keyed on
`(instance, member_type, member_identifier)`) and `mark_absent_missing`
(`WHERE member_type = ?`) is the mechanism; this rule makes that scoping a
**binding contract**, not an implementation accident. A fields pass never
touches entity, layout, or role membership; a roles pass never touches field
membership; and so on.

### 3.2 A pass that resolves nothing leaves its area's membership unchanged

A pass writes its `absent` sweep **only when its live read of the area succeeded
and was authoritative** — that is, the instance was actually read and the
resolved set is the genuine, complete set of objects the instance has in that
area. Concretely:

- If the live read **failed** (transport error, non-success status, or a body
  the pass cannot interpret), the pass makes **no membership writes at all** for
  its area — no upserts and **no absent sweep**. The area's existing membership
  (present, drifted, and absent rows from prior audits) is left **exactly as it
  was**. The pass reports the read failure; it does not silently report success.
- If the live read **succeeded** and authoritatively returned **zero** objects
  for the area, the absent sweep runs and the area's prior rows are correctly
  flipped to `absent` — this is a real, observed emptying, not an inconclusive
  one.

"Resolves nothing" therefore splits into two distinct cases that must **not** be
conflated: *read failed / inconclusive* → leave membership intact; *read
succeeded, instance genuinely empty* → sweep to absent. The defect was treating
the first as the second.

A pass that is **not applicable** to the instance's role or that the audit did
not run at all is the strongest form of "resolves nothing": it performs no read
and therefore writes nothing, leaving its area's membership intact for whatever
prior audit last recorded it.

### 3.3 An object is marked `absent` only on a successful read that no longer contains it

An `instance_membership` row transitions to `absent` if and only if **both**
hold:

1. the pass's live read of that area **succeeded** (§3.2), and
2. the object's `member_identifier` is **not in** the resolved present set from
   that successful read (i.e. the live instance, read correctly, no longer
   contains the object).

Absence is thus always a **positive observation** — "I read the instance and the
object is gone" — never an inference from an empty or failed read. This is the
precondition the companion design (REQ-393, §3.3) relies on when it classifies a
design object with no live counterpart as `absent`.

### 3.4 Partial and per-area writes merge into one inventory

Because each pass owns a disjoint `member_type` slice (§3.1), the inventory after
an audit is the **union** of the slices, and the passes compose without a merge
conflict:

- A **partial audit** that runs only some areas (e.g. an entity-only re-audit, or
  an audit whose later passes failed their reads) updates only the slices whose
  passes successfully read, and leaves every other area's slice untouched and
  authoritative from its last successful audit. The inventory is never left in a
  half-erased state where one pass's failure blanks another pass's good data.
- The order of passes within an audit is irrelevant to correctness: each pass
  reads its own area and writes its own slice, so two passes of the same audit
  can never race on the same membership row, and re-running one area's pass is
  idempotent over that slice (`upsert_membership` is keyed and idempotent;
  `mark_absent_missing` only re-confirms already-`absent` rows).

There is no global "clear then rewrite" step for an instance's inventory; the
inventory is only ever mutated one area-slice at a time, by the one pass that
authoritatively read that area.

### 3.5 A failed pass does not make the audit report success

A pass whose live read failed (§3.2) must surface that failure in the audit
result for its area rather than recording a clean pass. The audit's
completion-truthfulness — that a run reporting success actually wrote the
inventory it claims — is specified in full under REQ-395 / PI-354; this design
only fixes the **write side** (an unreadable area writes nothing), and names the
reporting obligation here so the two slices meet without a gap.

## 4. What stays unchanged

- The `present` / `drifted` / `absent` membership model and the
  `upsert_membership` + `mark_absent_missing` two-step are unchanged; this design
  constrains **when** the sweep fires and **what slice** a pass may touch, not
  the row model.
- The drift path's existing read-failure raise is unchanged — it already
  satisfies §3.2 for its read; this design generalizes the same guard to every
  pass and every area (notably the candidate-gated path).
- The candidate-gated reconcile and the mapping-candidate workflow remain in
  place for `source`-only instances (per the companion design); this rule only
  stops their empty-resolve sweep from erasing prior inventory.
- Neutral-name matching, the sparse per-attribute drift override, and
  per-`member_type` membership scoping are unchanged.

## 5. Acceptance

This slice is satisfied when, for any instance whose inventory was populated by a
prior audit:

1. A later audit pass whose area resolves **nothing because its live read failed
   or was inconclusive** leaves that area's `present`, `drifted`, and `absent`
   membership **exactly as the prior audit left it** — no rows are flipped to
   `absent`.
2. A later audit pass whose live read **succeeded and authoritatively returned
   zero objects** flips that area's prior rows to `absent` — proving absence is
   recorded only on a successful, observed emptying.
3. An object is marked `absent` **only** when its area's read succeeded and the
   object is no longer in the resolved set; never on a failed or empty-by-default
   read.
4. A pass writes membership rows of **only its own `member_type`**; running one
   area's pass never alters another area's membership slice.
5. A **partial audit** (some areas read, others failed) updates only the
   successfully-read areas and preserves every other area's prior membership,
   yielding an inventory that is the union of the last authoritative per-area
   reads.

Acceptance items 1–3 mirror REQ-394's acceptance summary; items 4–5 fix the
per-area write boundary and merge behavior the requirement names. The Test phase
exercises them, with the CBM Production instance — whose inventory was the one
clobbered — as the worked regression case.
