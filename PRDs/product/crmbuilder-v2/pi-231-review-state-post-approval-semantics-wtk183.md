# PI-231 / WTK-183 — `requirement.review_state` Post-Approval Value: Design

**Status:** design, 2026-06-18. **Design-phase deliverable** for the **storage**
facet (WTK-183) of design workstream **WSK-154** ("Design: Requirement approval
in the Requirements Review panel"). Specifies the requirement-record semantics
for **REQ-249** — *"Approving a requirement clears its needs-review flag."*

This is the vN+1 wave of the approval design. Its three sibling facets carry the
rest of WSK-154 and are referenced, not duplicated, here:

- **access** (WTK-182) — the reviewer persona's approve capability (REQ-251);
- **methodology-process** (WTK-184) — the `approve_requirement` process
  contract: actor, gates, governed approving-decision recording, approving
  reviewer, failure-reason surfacing (REQ-251, REQ-249);
- **ui** (WTK-185) — the right-click Approve action and upper-right Approve
  button (REQ-251).

Governing design: `requirements-provenance-and-review-anchor.md` (the
decision-outcome model — *deliver / change / decline*) and
`requirements-provenance-build-translation.md`. This document supersedes the
prior-wave storage facet `pi-230-review-state-post-approval-semantics-wtk171.md`
(WSK-150) where they overlap; it carries the same normative rule forward and
adds the freeze-band interaction (§3.1) that the prior wave predated.

**Implementation status — already realized.** Unlike the prior wave (which
handed off to a downstream Development workstream), the behavior this design
specifies has already landed on `main` (commit `e2c2868a` — *"WTK-174 — set
requirement review_state=current on approval (REQ-249)"*). This document
therefore pins the **realized contract** and is written so a verifier can hold
the shipped code against it; §6 cites the exact code that satisfies each clause.

## 1. Problem

`requirement_review_state` is the living-drift flag (`current` |
`needs_review`, `vocab.REQUIREMENT_REVIEW_STATES`,
`crmbuilder-v2/src/crmbuilder_v2/access/vocab.py:343`). It is raised to
`needs_review` whenever a requirement's basis changes:

- a **change-decision reopen** — `reopen_by_decision` sets
  `status → candidate`, `review_state → needs_review`, `approved_at → None`
  (`access/repositories/requirement.py`);
- **living drift** — `flag_descendants_needs_review` flags every descendant
  down the `requirement_refines_requirement` chain.

Historically the **deliver** outcome, `activate_by_decision`, flipped
`candidate`/`deferred` → `confirmed` and stamped `requirement_approved_at`, but
left `review_state` untouched. So the canonical cycle —

1. requirement is `confirmed`, `current`;
2. a change decision reopens it → `candidate`, `needs_review`;
3. the requirement is re-worked and re-approved through the approving-decision
   path → `confirmed`, but **still `needs_review`** —

left a freshly approved requirement sitting in the drift queue
(`review.drift_queue`, `GET /review/drift-queue`) and rendered with the
`needs_review` marker in the topic read-back. The approval *is* the review, so
this is wrong (REQ-249).

## 2. Semantics — the post-approval value (the normative rule)

> **The value `requirement_review_state` takes after approval through the
> approving-decision path is `current`.** When `activate_by_decision` confirms a
> requirement it sets `requirement_review_state = "current"` together with
> `requirement_status = "confirmed"` and the `requirement_approved_at` stamp —
> one atomic post-approval state. This holds whether the requirement was a
> never-approved `candidate` or a `candidate` re-entered via a change-decision
> reopen. **A just-approved requirement is never `needs_review`** — the
> needs-review flag is cleared even immediately after a reopen-for-change.

The post-approval value is **unconditional on the prior `review_state`**: a
`candidate` that is already `current` stays `current` (a no-op for that field);
a `candidate` that is `needs_review` becomes `current`. There is no new gate,
no new input, and no new column — the clear rides the existing deliver outcome.
"`post_approval_value` of `review_state` is `current`" is a semantic
postcondition of `activate_by_decision`, not a stored attribute.

### 2.1 Idempotent (already-`confirmed`) branch

`activate_by_decision` early-returns when the requirement is already
`confirmed`. To honor the rule even when an approving edge lands on an
already-confirmed-but-flagged row — reachable because
`flag_descendants_needs_review` raises `needs_review` on a `human_defined`
confirmed descendant **without** regressing its status (only `ai_derived`
confirmed descendants regress to `candidate`) — the idempotent branch **also**
normalizes: if the confirmed row is `needs_review`, set it `current`, flush, and
emit the `update` change-log event; an already-`current` confirmed row returns
unchanged (no spurious event). This keeps "approved ⇒ current" true on **every**
entry to the function, not only on the status flip.

### 2.2 What does **not** change

- `reopen_by_decision` still sets `needs_review` on the **change** outcome —
  reopening is the inverse of approving and is unaffected. The reopen→re-approve
  cycle is exactly where the rule earns its keep.
- `flag_descendants_needs_review` (living drift) is unchanged: editing or
  reopening an ancestor still flags descendants `needs_review`. Drift flags the
  *derived* requirements; this rule only clears the flag on the *approved* one.
- The activation gates are unchanged and still run **before** the clear:
  readability (`readability.validate_requirement_readability`), provenance
  (`requirement_defined_in_conversation` via ancestry), and topic
  (`requirement_belongs_to_topic` via ancestry). The `review_state` clear
  happens **after** the gates pass, so a gate-failing approval clears nothing.
- A `rejected` requirement still cannot be approved (terminal); the
  `review_state` clear is never reached on that path.

## 3. Boundary explicitly out of scope

Clearing the `needs_review` flag on a **`human_defined`, `confirmed`**
requirement that was flagged by drift is **not** covered by REQ-249 and is not
solved here. That row keeps `confirmed` status, so the reviewer-panel path
(`review.approve_requirements` → `_approve_one`) short-circuits it as
`already_confirmed` and records **no** approving decision — there is no approval
event to hang the clear on. Re-validating a confirmed-but-drifted requirement (a
*re-affirm*, distinct from a *re-approval*) is a separate concern for the
drift-queue workflow and a future requirement. §2.1 makes the access-layer
`activate_by_decision` itself idempotently correct if such an edge is created
directly, but the panel does not exercise that path.

### 3.1 Freeze-band interaction (new in this wave)

`access/freeze.py:assert_requirement_amendable` gates a substantive requirement
edit against the requirement's release freeze band. In the `amend_window` band
it permits the edit **only** when the requirement's `review_state` is
`needs_review` (i.e. a `requirement_changed_by_decision` decision opened the
amend gate); otherwise it raises `ConflictError`.

The post-approval clear therefore has a deliberate, correct consequence: once a
reopened requirement in a frozen release is **re-approved**, its `review_state`
returns to `current`, which **re-locks the amend window**. This is intended — an
approved requirement is settled, so further substantive edits again require a
fresh governing decision (a new `requirement_changed_by_decision` reopen, which
re-raises `needs_review` and reopens the gate). The clear and the freeze gate
compose without conflict: `needs_review` is the single signal that the amend
gate keys on, and approval is precisely the event that should close it.

## 4. Schema / migration / vocab

**None.** `requirement_review_state` and its CHECK
(`ck_requirement_review_state` over `REQUIREMENT_REVIEW_STATES`) already exist;
both target values (`current`, `needs_review`) are already admitted
(`vocab.py:343`). No column, migration, or vocab change. The rule is expressed
entirely through the transition logic in `activate_by_decision`.

## 5. API surface

**None.** The approval path is unchanged: a client creates a
`requirement_approved_by_decision` edge (`POST /references`, or the reviewer
panel's `POST /review/approve` → `review.approve_requirements`), which
atomically triggers `activate_by_decision` (`references.create` →
`requirement.activate_by_decision`). The post-approval value is observed through
the existing reads — `GET /requirements/{id}` (`requirement_review_state`),
`GET /review/drift-queue`, `GET /review/topics/{id}` / `.../document` — with no
shape change.

## 6. Realized-contract pointer (verification map)

Single module: `crmbuilder_v2/access/repositories/requirement.py`. The shipped
code (commit `e2c2868a`) satisfies the rule at two points:

- **flip path** — in `activate_by_decision`, alongside
  `row.requirement_status = "confirmed"` and `row.requirement_approved_at =
  datetime.now(UTC)`, the line `row.requirement_review_state = "current"` sets
  the post-approval value (§2). Gates run above it, so the clear is post-gate.
- **idempotent branch** — the early-`confirmed` return first checks
  `row.requirement_review_state == "needs_review"`; if so it sets `current`,
  flushes, and emits an `update` event; otherwise it returns unchanged (§2.1).

`reopen_by_decision` (the change outcome) and `flag_descendants_needs_review`
(living drift) are unchanged and supply the `needs_review` states this rule
clears (§2.2). `freeze.assert_requirement_amendable` is unchanged and composes
as described in §3.1.

## 7. Tests (the existing suite that proves the contract)

`tests/crmbuilder_v2/api/test_requirements_drift.py` is the home of these checks
(its `_make` / `_ref` / `_refines` / `_get` helpers and the
`requirement_changed_by_decision` / `requirement_approved_by_decision`
edge-driven flow model the cycle exactly). The contract is proven by:

1. **reopen → re-approve clears the flag (REQ-249 core).** A requirement with
   provenance + topic, approved → `confirmed`, `current`; reopened →
   `candidate`, `needs_review`; re-approved → `confirmed` **and**
   `review_state == "current"` **and** `requirement_approved_at is not None`.
2. **first approval leaves `current`.** A `candidate` that is `current` and
   passes the gates approves to `confirmed`, `current` (no regression).
3. **gate-failing approval clears nothing.** Approving a requirement missing
   provenance/topic is rejected (422) and the row stays `candidate` /
   `needs_review` (the clear is post-gate).
4. **idempotent normalize (§2.1).** A `human_defined` confirmed requirement
   flagged `needs_review` by an ancestor edit; creating a
   `requirement_approved_by_decision` edge on it leaves it `confirmed` and sets
   `review_state == "current"` (the early-return normalize path).

These run on SQLite and, where PG-gated (`CRMBUILDER_V2_TEST_PG_URL`), on
Postgres — the rule introduces no dialect-specific behavior.

## 8. Requirement traceability

| REQ | Acceptance | Where in this design |
|---|---|---|
| REQ-249 — approval returns review state to `current`, incl. immediately after a reopen-for-change | "after a requirement is approved through the approving-decision path its review state is current, not needs-review, including when the approval immediately follows a reopen-for-change" | §2 (normative post-approval value, flip path) + §2.1 (idempotent branch); §3.1 (freeze-band interaction); §6 (realized-contract pointer); tests 1 (reopen→re-approve) and 2 (first approval) in §7 |
