# PI-230 / WTK-171 — `requirement.review_state` Post-Approval Semantics: Design

**Design-phase deliverable** for **PI-230** ("Design requirement approval and
status-counts capabilities"), workstream **WSK-150** (phase: Design). Storage
area. Specifies the requirement-record semantics for **REQ-249** — *"Approving a
requirement clears its needs-review flag."*

Governing design: `requirements-provenance-and-review-anchor.md` (the
decision-outcome model — *deliver / change / decline*) and
`requirements-provenance-build-translation.md`. Provenance: REQ-249 ←
`CNV-130` ← `TOP-087` (the founding requirements-provenance topic),
approved by `DEC-539`.

This is a **specification only**. The implementing code + tests land in the
downstream Development workstream (`WSK-151`, `blocked_by` WSK-150). The design
is written to be implementable verbatim.

## 1. Problem

`requirement_review_state` is the living-drift flag (`current` |
`needs_review`, `vocab.REQUIREMENT_REVIEW_STATES`). It is raised to
`needs_review` whenever a requirement's basis changes:

- a **change-decision reopen** — `reopen_by_decision` sets
  `status → candidate`, `review_state → needs_review`, `approved_at → None`
  (`requirement.py`);
- **living drift** — `flag_descendants_needs_review` flags every descendant
  down the `requirement_refines_requirement` chain.

The **deliver** outcome, `activate_by_decision`, flips `candidate`/`deferred`
→ `confirmed` and stamps `requirement_approved_at`, but **never touches
`review_state`**. So the canonical cycle —

1. requirement is `confirmed`, `current`;
2. a change decision reopens it → `candidate`, `needs_review`;
3. the requirement is re-worked and re-approved through the approving-decision
   path → `confirmed`, but **still `needs_review`** —

leaves a freshly approved requirement sitting in the drift queue
(`review.drift_queue`, `GET /review/drift-queue`) and rendered with the
`needs_review` marker in the topic read-back. The approval *is* the review, so
this is wrong.

## 2. Semantics (the normative rule)

> **Approval through the approving-decision path normalizes the requirement's
> review state to `current`.** When `activate_by_decision` confirms a
> requirement it sets `requirement_review_state = "current"` together with
> `requirement_status = "confirmed"` and the `requirement_approved_at` stamp —
> one atomic post-approval state. This holds whether the requirement was a
> never-approved `candidate` or a `candidate` re-entered via a change-decision
> reopen. A just-approved requirement is never `needs_review`.

The clear is **unconditional on the prior `review_state`**: a `candidate`
that is already `current` stays `current` (no-op for that field); a
`candidate` that is `needs_review` becomes `current`. No new gate, no new
input — the clear rides the existing deliver outcome.

### 2.1 Idempotent (already-`confirmed`) branch

`activate_by_decision` early-returns when the requirement is already
`confirmed`. To honor the rule even when an approving edge lands on an
already-confirmed-but-flagged row (reachable because
`flag_descendants_needs_review` raises `needs_review` on a `human_defined`
descendant **without** regressing its status — only `ai_derived` confirmed
descendants regress to `candidate`), the idempotent branch must **also**
normalize: if the confirmed row is `needs_review`, set it `current`, flush,
and emit the `update` change-log event; otherwise return unchanged as today.
This keeps "approved ⇒ current" true on every entry to the function rather
than only the flip.

### 2.2 What does **not** change

- `reopen_by_decision` still sets `needs_review` on the **change** outcome —
  reopening is the inverse of approving and is unaffected.
- `flag_descendants_needs_review` (living drift) is unchanged: editing or
  reopening an ancestor still flags descendants `needs_review`. Drift flags
  the *derived* requirements; this rule only clears the flag on the
  *approved* one.
- The activation gates are unchanged: readability
  (`readability.validate_requirement_readability`), provenance
  (`requirement_defined_in_conversation` via ancestry), and topic
  (`requirement_belongs_to_topic` via ancestry) all still gate a non-confirmed
  approval. The `review_state` clear happens **after** the gates pass, so a
  gate-failing approval clears nothing.
- A `rejected` requirement still cannot be approved (terminal); the
  `review_state` clear is never reached on that path.

## 3. Boundary explicitly out of scope

Clearing the `needs_review` flag on a **`human_defined`, `confirmed`**
requirement that was flagged by drift is **not** covered by REQ-249 and is not
solved here. That row keeps `confirmed` status, so the reviewer-panel path
(`review.approve_requirements` → `_approve_one`) short-circuits it as
`already_confirmed` and records **no** approving decision — there is no
approval event to hang the clear on. Re-validating a confirmed-but-drifted
requirement (a re-affirm, distinct from a re-approval) is a separate concern
for the drift-queue workflow and a future requirement. §2.1 makes the
access-layer `activate_by_decision` itself idempotently correct if such an
edge is created directly, but the panel does not exercise that path.

## 4. Schema / migration / vocab

**None.** `requirement_review_state` and its CHECK
(`ck_requirement_review_state` over `REQUIREMENT_REVIEW_STATES`) already exist;
both target values (`current`, `needs_review`) are already admitted. No column,
migration, or vocab change.

## 5. API surface

**None.** The approval path is unchanged: a client creates a
`requirement_approved_by_decision` edge (`POST /references`, or the reviewer
panel's `POST /review/approve` → `review.approve_requirements`), which
atomically triggers `activate_by_decision`. The new postcondition is observed
through the existing reads — `GET /requirements/{id}`
(`requirement_review_state`), `GET /review/drift-queue`,
`GET /review/topics/{id}` / `.../document` — with no shape change.

## 6. Implementation pointer (for WSK-151)

Single module: `crmbuilder_v2/access/repositories/requirement.py`.

- In `activate_by_decision`, where the row flips to `confirmed` (beside
  `row.requirement_status = "confirmed"` / `row.requirement_approved_at =
  datetime.now(UTC)`), add `row.requirement_review_state = "current"`.
- In the same function's early-`confirmed` return, before returning,
  normalize a `needs_review` row to `current` with a flush + `emit(...,
  operation="update", before=..., after=...)` so the change is logged; an
  already-`current` confirmed row returns unchanged (preserve current
  behavior, no spurious event).

No other module is touched. Estimated change: a few lines.

## 7. Tests (for WSK-151, grounded in existing conventions)

Add to `tests/crmbuilder_v2/api/test_requirements_drift.py` (its `_make` /
`_ref` / `_refines` / `_get` helpers and the
`requirement_changed_by_decision` / `requirement_approved_by_decision`
edge-driven flow already model this exactly):

1. **reopen → re-approve clears the flag (REQ-249 core).** A requirement with
   provenance + topic, approved (`requirement_approved_by_decision`) →
   `confirmed`, `current`; reopened (`requirement_changed_by_decision`) →
   `candidate`, `needs_review`; re-approved → assert `confirmed` **and**
   `review_state == "current"` **and** `requirement_approved_at is not None`.
2. **first approval leaves `current`.** A `candidate` that is `current` and
   passes the gates approves to `confirmed`, `current` (no regression of the
   field).
3. **gate-failing approval clears nothing.** Approving a requirement missing
   provenance/topic is rejected (422) and the row stays `candidate` /
   `needs_review` (the clear is post-gate).
4. **idempotent normalize (§2.1).** A `human_defined` confirmed requirement
   flagged `needs_review` by an ancestor edit; creating a
   `requirement_approved_by_decision` edge on it leaves it `confirmed` and sets
   `review_state == "current"` (the early-return normalize path).

Run on SQLite and, where the suite is PG-gated (`CRMBUILDER_V2_TEST_PG_URL`),
on Postgres — no dialect-specific behavior is introduced.

## 8. Requirement traceability

| REQ | Acceptance | Where in this design |
|---|---|---|
| REQ-249 — approval returns review state to `current`, incl. after a reopen-for-change | "after a requirement is approved through the approving-decision path its review state is current, not needs-review, including when the approval immediately follows a reopen-for-change" | §2 (normative rule, flip path) + §2.1 (idempotent branch); test 1 covers the reopen→re-approve case, test 2 the first-approval case |
