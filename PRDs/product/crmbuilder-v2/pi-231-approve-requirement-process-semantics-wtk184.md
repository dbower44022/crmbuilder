# PI-231 / WTK-184 — `approve_requirement` Process Semantics and Gates: Design

**Status:** design, 2026-06-18. **Design-phase deliverable** for the
**methodology-process** facet (WTK-184) of design workstream **WSK-154**
("Design: Requirement approval in the Requirements Review panel"). Specifies the
**process contract** for the reviewer's *approve* action — its actor, single
selection-and-action, gate checks, governed approving-decision recording, the
recording of the approving reviewer, and the surfacing of failure reasons for
requirements that fail the gates (**REQ-251**, **REQ-249**).

This is the vN+1 wave of the approval design. Its three sibling facets carry the
rest of WSK-154 and are referenced, not duplicated, here:

- **storage** (WTK-183) — the `review_state` post-approval value `current`
  (REQ-249); see `pi-231-review-state-post-approval-semantics-wtk183.md`;
- **access** (WTK-182) — the reviewer persona's approve capability + the
  `approve` permission (REQ-251);
- **ui** (WTK-185) — the right-click Approve action and the upper-right Approve
  button (REQ-251).

Governing design: `requirements-provenance-and-review-anchor.md` (the
decision-outcome model — *deliver / change / decline* — and the
"readability is load-bearing" rule) and `requirements-provenance-build-
translation.md`. This document **supersedes the prior-wave process facet**
`approve-requirement-process-contract.md` (WSK-150 / PI-230 / WTK-172) where they
overlap: it carries the same normative actor/affordance/precondition/effect/
postcondition contract forward and adds the two things that wave predated — the
**RBAC authorization gate** (WTK-177, §3) and the **freeze-band re-lock**
postcondition (§6.1) — then pins the realized contract a verifier can hold the
shipped code against (§8).

A *process contract*, here, is the actor / affordance / precondition / effect /
postcondition specification a verifier can hold the built behavior against. It is
methodology, not code: it says what must be true, not how the savepoints are
written.

**Implementation status — already realized.** Like the storage facet, the
behavior this design specifies has already landed on `main`: the
`approve_requirements` access operation (`crmbuilder_v2/access/review.py`),
exposed at `POST /review/approvals`, driven from the Requirements Review panel
(`ui/panels/review.py`), authorized by the `approve` permission
(`access/vocab.py`, `access/rbac.py`). This document therefore pins the
**realized contract**; §8 cites the exact code that satisfies each clause.

---

## 1. Actor

The single actor is the **reviewer** — the human who defines what is to be built
(see the persona facet `reviewer-persona-approval-capability.md`). Only a
reviewer invokes `approve_requirement`. AI agents propose candidate requirements;
they do not approve them — confirming a requirement is a human review, not an
agent action. The contract requires that the invoking reviewer be **named on the
record** of every approval (§5, §6): an approval whose `reviewer` is missing or
empty is rejected before any decision is recorded.

The actor is constrained on two independent axes, both enforced:

1. **Identity present** — a non-empty `reviewer` string is supplied (§4.1).
2. **Authorized to approve** — the caller holds the `approve` permission (§3).

These are distinct: identity says *who is on the record*; authorization says
*who is allowed to act*. Both must hold.

---

## 2. Trigger, affordances, and selection

The reviewer triggers the action from the Requirements Review panel's approval
surface, by **either** of two equivalent affordances — both invoke the **same**
contract over the **same** selection:

- a **right-click Approve action** ("Approve selected…") on the selected
  requirement row(s), and
- an **Approve button in the upper-right** ("Approve selected…") of the approval
  surface.

Neither affordance is privileged: the contract, its preconditions, its effects,
and its outcomes are identical regardless of which one the reviewer uses (REQ-251
calls for both explicitly).

The action operates over a **selection of one or more candidate requirements**,
approved in a **single action**:

- The reviewer may select exactly one requirement or many; the action accepts
  both. The reviewer is never forced to approve one at a time.
- Each selected requirement is decided **independently** (§5). The selection is a
  batch of independent decisions, not one all-or-nothing transaction.
- Result order is preserved with the input selection order, so the reviewer can
  map each outcome back to the row they selected.

The action lives on the **Requirements Review panel** (Governance sidebar), on
the approval surface that already lists candidates awaiting activation and what
each still needs. This is the only surface from which a reviewer approves. The
contract is deliberately bound to this surface because the anchor's load-bearing
rule requires the human to approve *where the readable, traceable content is* —
approving by hand-assembled interface-layer calls outside the panel is the
rubber-stamp path the process exists to close.

---

## 3. Authorization gate (new in this wave — WTK-177)

The whole action is gated by the **`approve` permission**, a distinct RBAC verb
— not generic `create` — so authorization to approve can be granted and enforced
separately from authorization to author content
(`vocab.RBAC_PERMISSIONS`). The verb is checked **once, for the whole action**,
before any reviewer-identity check or per-requirement work (`rbac.check("approve",
…)`).

The grant matrix (`vocab.ROLE_PERMISSIONS`):

| Role | Holds `approve`? |
|---|---|
| `owner` | yes (total) |
| `editor` | **yes** — acts as the reviewer persona |
| `viewer` | no (read only) |
| `orchestrator`, `pi_lead`, `phase_specialist`, `area_specialist` (agent tiers) | **no** — an agent never approves |

Two boundaries this gate makes explicit:

- **The agent tiers are withheld `approve` by construction.** An ADO agent can
  read, write, and claim work, but confirming a requirement is a human review —
  so the permission an agent would need to self-confirm is one it can never hold.
  This is the authorization-layer expression of the anchor's "the human approves"
  rule.
- **The check is a no-op when `principal_auth_enabled` is off** — the
  default-owner localhost flow (the dogfood default). When auth is on, an
  unauthorized caller is refused with `PermissionDenied` (→ HTTP 403) **before**
  any decision is recorded; no partial work.

This gate did not exist in the prior-wave contract (WTK-172 predated WTK-177);
it is the substantive authorization addition this facet records.

---

## 4. Preconditions

Before any decision is recorded, in order:

1. **Authorized actor** (§3) — the caller holds `approve` (or auth is off).
2. **Actor identity present** — `reviewer` is non-empty after trimming;
   otherwise the action is rejected outright with a field error
   (`reviewer` / `missing_or_empty`) and no partial work is done (§4.1).
3. **Targets are requirements** — each target is decided per requirement; a
   missing requirement is a per-requirement `failed` outcome, not a precondition
   abort (§5).

### 4.1 No actor, no work

The reviewer-identity check is whole-action: an empty reviewer aborts the entire
call before the first requirement is touched. This is deliberate — the reviewer's
identity is a required part of every approval record, so an anonymous approval is
refused at the door, not recorded and patched later.

There is **no precondition that every target will pass its gates** — the gates
are checked per requirement during the effect, and a gate failure is an expected,
recoverable outcome, not a precondition violation.

---

## 5. Effects and the gate checks

For **each** selected requirement, independently and atomically (each within its
own savepoint), the action:

1. **Short-circuits an already-confirmed target** as `already_confirmed` — a
   no-op outcome, not an error, recording **no** decision (re-approving something
   already delivered is harmless and reported plainly).
2. Otherwise records a **governed approving decision** authored by the reviewer —
   a real decision record (status `Active`) titled *"Approve {REQ} for
   delivery"*, whose context, decision, rationale, and executive summary capture
   the reviewer's identity, the requirement under review, and the rationale that
   this is a human review recorded as a governed event, **not a status edit**.
   Any reviewer `note` is carried into the decision's context and summary.
3. Creates the **`requirement_approved_by_decision`** edge from the requirement
   to that decision, which triggers the existing **`activate_by_decision` gate
   chain atomically**:
   - **readability** — the statement is human-readable, with no embedded
     identifiers (`readability.validate_requirement_readability`);
   - **provenance** — the requirement traces to a defining conversation
     (`requirement_defined_in_conversation`), directly or through
     `requirement_refines_requirement` ancestry;
   - **topic** — the requirement belongs to a topic
     (`requirement_belongs_to_topic`), directly or through ancestry.

   If every gate passes, the requirement is **confirmed**,
   `requirement_approved_at` is stamped, and its `review_state` returns to
   `current` (§6, REQ-249) — one atomic post-approval state. Confirmation happens
   **only** through this governed path, never by editing the status field.

The contract adds a reviewer-facing **front door** onto the already-built
governed approving-decision path; it does **not** introduce a second, weaker
route to confirmation, and it does **not** define, relax, or bypass the gates it
invokes. The gates are the anchor's enforcement; this contract *invokes* them and
*surfaces their reasons*.

### 5.1 Per-requirement outcomes and failure-reason surfacing

A multi-requirement approval yields one outcome **per requirement**, and the
failures never roll back or block the successes:

| Outcome | Meaning | Decision recorded? | Requirement after |
|---|---|---|---|
| `confirmed` | Approved and all gates passed | yes | `confirmed`, `approved_at` stamped, `review_state = current` |
| `already_confirmed` | Re-approving an already-confirmed requirement | no | unchanged (no-op, not an error) |
| `failed` | A gate refused, or the requirement was not found | no (savepoint rolled back) | **remains a candidate**, unchanged |

Each result carries `{identifier, outcome, decision_identifier, reason}`.

Key guarantees the contract makes about outcomes:

- **Partial success is normal and safe.** In a mixed selection, each requirement
  is decided on its own savepoint; one requirement's failure neither blocks nor
  undoes the others.
- **A failure teaches — failure reasons are surfaced (REQ-251).** A `failed`
  outcome **carries the failing gate's own message** ("what to fix") —
  readability, provenance, or topic — not a generic refusal. The gate's
  `UnprocessableError` / `ValidationError` message is captured into the result's
  `reason`, the decision + edge for that requirement are rolled back so no
  half-approval is left behind, and the panel renders these reasons to the
  reviewer so the human review can be completed in the panel.
- **A gate-failing requirement remains a candidate.** It is never silently
  dropped and never partially confirmed; it stays in the candidate set so the
  reviewer can fix the named problem and re-approve.
- **Already-confirmed is reported plainly**, not as an error.

---

## 6. Postconditions

After the action returns:

1. Every `confirmed` requirement has a `requirement_approved_by_decision` edge to
   a governed `Active` decision naming the approving reviewer, status `confirmed`,
   and `requirement_approved_at` stamped.
2. Every `failed` requirement is exactly as it was before the action (a
   candidate), with no orphan decision or edge, and the reviewer has been given
   the gate's reason.
3. **`review_state` postcondition (REQ-249).** An approved requirement's review
   state is **`current`**, not `needs_review` — including when the approval
   immediately follows a reopen-for-change. The approval *is* the review, so a
   freshly approved requirement must not linger in the review-needed queue. This
   postcondition is owned and implemented by the **storage** facet (WTK-183,
   REQ-249); this contract *requires* it of any conforming implementation and
   names it as the binding postcondition of a successful approval.

### 6.1 Freeze-band re-lock (new in this wave)

The `review_state = current` postcondition composes with the release freeze gate
(`freeze.assert_requirement_amendable`), which permits a substantive edit in the
`amend_window` band **only** while the requirement is `needs_review`. Therefore
once a reopened requirement in a frozen release is **re-approved**, this
contract's `review_state → current` postcondition **re-locks the amend window**:
the requirement is settled again, so further substantive edits require a fresh
governing decision (a new `requirement_changed_by_decision` reopen, which
re-raises `needs_review` and reopens the gate). This is intended — approval is
precisely the event that should close the amend window. The mechanism lives in
the storage facet (§3.1 of WTK-183); this facet records it as a process
consequence of a successful approval so a verifier sees the full settled-state
picture.

---

## 7. Contract boundaries (what it is not)

- **Decline and change** are the other two reviewer decision outcomes from the
  anchor's *deliver / change / decline* model. This contract covers **approve**
  (deliver) only; declining or sending a requirement back for change is a
  separate action.
- **Authoring or editing requirement statements** is not part of this action. The
  reviewer approves what is presented; an unreadable statement is refused by the
  readability gate, and the reviewer's recourse is to send it back, not to
  rewrite it inside the approve action.
- **The gates themselves** (readability, provenance, topic resolution) are the
  anchor's already-built enforcement. This contract *invokes* them and *surfaces
  their reasons*; it does not define, relax, or extend them.
- **Clearing drift on an already-confirmed requirement** (a *re-affirm*, distinct
  from a *re-approval*) is out of scope: such a row short-circuits as
  `already_confirmed` with no approval event to hang a clear on (see WTK-183 §3).

---

## 8. Realized-contract pointer (verification map)

| Contract clause | Where realized |
|---|---|
| Actor = reviewer, named on record; missing reviewer rejected whole-action (§1, §4.1) | `access/review.py:approve_requirements` — `reviewer.strip()` → `UnprocessableError([FieldError("reviewer", "missing_or_empty", …)])` |
| Authorization gate, checked once (§3) | `access/review.py` — `rbac.check("approve", engagement_id=…)`; verb + grants in `access/vocab.py` (`RBAC_PERMISSIONS`, `ROLE_PERMISSIONS`) |
| One-or-more selection, single action, per-requirement independence, order preserved (§2, §5) | `approve_requirements` — list comprehension over `requirement_identifiers`, one `_approve_one` per id |
| Two affordances over the same selection (§2) | `ui/panels/review.py` — `_approve_button` ("Approve selected…", upper-right) and `_build_approval_context_menu` (right-click), both → `_on_approve_selected` |
| Governed approving decision + edge, in a per-requirement savepoint (§5) | `_approve_one` — `with session.begin_nested(): _decisions.create(... status="Active" ...)` then `_references.create(... relationship="requirement_approved_by_decision")` |
| Gate chain triggered atomically; confirm only via the governed path (§5) | `references.create` → `requirement.activate_by_decision` (readability / provenance / topic) |
| `already_confirmed` short-circuit, no decision (§5, §5.1) | `_approve_one` — early return when `requirement_status == "confirmed"` |
| `failed` surfaces the gate's own reason; savepoint rolls back; stays candidate (§5.1) | `_approve_one` — `except (UnprocessableError, ValidationError)` captures `exc.errors[0]` / `str(exc)` into `reason` |
| `review_state = current` postcondition (§6) | storage facet `requirement.activate_by_decision` — `row.requirement_review_state = "current"` (commit `e2c2868a`; WTK-183) |
| Freeze re-lock (§6.1) | `freeze.assert_requirement_amendable` (unchanged) keying on `needs_review`; cleared by the approval |
| Surface = `POST /review/approvals`, panel-driven (§2) | `api/routers/review.py` `create_approvals` (201); `ui/client.py:approve_requirements`; panel `_submit_approvals` rendering confirmed / already / failed-with-reason |

---

## 9. Tests (the existing suite that proves the contract)

The realized behavior is exercised by the review/approval API tests
(`tests/crmbuilder_v2/api/`, alongside `test_requirements_drift.py` which models
the reopen→re-approve cycle for the `review_state` postcondition). The contract's
process clauses are proven by:

1. **Single and multi selection** — approving one and approving many in one call
   each yield an order-preserving per-requirement result list.
2. **Mixed outcome, no cross-contamination** — a selection mixing a
   gate-passing, an already-confirmed, and a gate-failing requirement yields
   `confirmed` / `already_confirmed` / `failed` respectively; the failure neither
   rolls back nor blocks the successes.
3. **Failure reason surfaced** — a requirement missing provenance/topic returns
   `failed` with the gate's own reason, and the row remains a `candidate` with no
   orphan decision or edge.
4. **Missing reviewer rejected whole-action** — an empty `reviewer` aborts the
   call (field error) before any decision is recorded.
5. **Authorization** — with `principal_auth_enabled` on, a caller lacking
   `approve` (a `viewer` or an agent-tier principal) is refused 403; with auth
   off the check is a no-op.
6. **`review_state` postcondition** — confirmed via the reopen→re-approve cycle
   in the storage facet's suite (WTK-183 §7).

These run on SQLite and, where PG-gated (`CRMBUILDER_V2_TEST_PG_URL`), on
Postgres — the contract introduces no dialect-specific behavior.

---

## 10. Requirement traceability

| REQ | Acceptance | Where in this design |
|---|---|---|
| REQ-251 — reviewers can approve requirements from the Requirements Review panel | "selecting one or more candidate requirements … and choosing Approve, by right-click or the upper-right button, records an approving decision for each and confirms those that pass the gates; any that fail surface their reason and remain candidates; the approving reviewer is recorded" | §1 (actor recorded), §2 (two affordances, one-or-more selection, single action), §3 (authorization), §5 (decision + edge + gates), §5.1 (per-requirement outcomes + failure-reason surfacing), §8 (verification map) |
| REQ-249 — approval returns review state to `current` | "after a requirement is approved through the approving-decision path its review state is current, not needs-review, including when the approval immediately follows a reopen-for-change" | §5 (post-gate state), §6 postcondition 3, §6.1 (freeze re-lock); owned by storage facet WTK-183 |

---

## 11. Provenance

- **Requirement:** REQ-251 — *"Reviewers can approve requirements from the
  Requirements Review panel."* (human_defined, confirmed.)
- **Postcondition requirement:** REQ-249 — review_state returns to `current` on
  approval (storage facet, WTK-183).
- **Planning item / workstream:** PI-231, Design workstream WSK-154.
- **Work task:** WTK-184 (methodology-process).
- **Sibling facets:** WTK-182 (access, approve capability + `approve` permission),
  WTK-183 (storage, review_state), WTK-185 (ui, the two affordances).
- **Superseded prior-wave facet:** `approve-requirement-process-contract.md`
  (WSK-150 / PI-230 / WTK-172) — carried forward here, plus the authorization
  gate (§3) and the freeze re-lock postcondition (§6.1).
- **Anchor:** `requirements-provenance-and-review-anchor.md` — the principle, the
  gates, and the "readability is load-bearing" rule this contract serves.
