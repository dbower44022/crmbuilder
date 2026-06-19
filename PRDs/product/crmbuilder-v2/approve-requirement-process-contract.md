# Process Contract — `approve_requirement`

**Status:** design, 2026-06-18. Specifies the **process contract** for the
reviewer's *approve* action in the Requirements Review panel: its actor,
affordances, selection, surface, effects, per-requirement outcomes, and
postconditions. This is the **methodology-process** facet of design workstream
WSK-150 (PI-230), the sibling of the **methodology-product** facet
(`reviewer-persona-approval-capability.md`, WTK-170). Read that facet and
`requirements-provenance-and-review-anchor.md` first — they establish *who* the
reviewer is and *why* approval must be a governed event. This document does not
restate the persona or the "why"; it pins down the precise contract the
implemented `approve_requirements` operation must honor (REQ-251) and names the
`review_state` postcondition it depends on (REQ-249).

A *process contract*, here, is the actor/affordance/precondition/effect/
postcondition specification a verifier can hold the built behavior against. It
is methodology, not code: it says what must be true, not how the savepoints are
written.

---

## Actor

The single actor is the **reviewer** — the human who defines what is to be
built (see the persona facet). Only a reviewer invokes `approve_requirement`.
AI agents propose candidate requirements; they do not approve them. The contract
requires that the invoking reviewer be **named on the record** of every approval
(see *Effects*); an approval whose reviewer is missing or empty is rejected
before any decision is recorded.

---

## Trigger and affordances

The reviewer triggers the action from the Requirements Review panel's approval
surface, by **either** of two equivalent affordances — both invoke the **same**
contract over the **same** selection:

- a **right-click Approve action** on the selected requirement row(s), and
- an **Approve button in the upper-right** of the approval surface.

Neither affordance is privileged: the contract, its preconditions, its effects,
and its outcomes are identical regardless of which one the reviewer uses.

---

## Selection (input)

The action operates over a **selection of one or more candidate requirements**,
approved in a **single action**:

- The reviewer may select exactly one requirement or many; the action accepts
  both. The reviewer is never forced to approve one at a time.
- Each selected requirement is decided **independently** (see *Per-requirement
  outcomes*). The selection is a batch of independent decisions, not one
  all-or-nothing transaction.
- The order of results is preserved with the order of the input selection, so
  the reviewer can map each outcome back to the row they selected.

---

## Surface

The action lives on the **Requirements Review panel** (Governance sidebar), on
the **approval surface** that already lists candidates awaiting activation and
what each still needs. This is the only surface from which a reviewer approves.
The contract is deliberately bound to this surface because the anchor's
load-bearing rule requires the human to approve *where the readable, traceable
content is* — approving by hand-assembled interface-layer calls outside the
panel is the rubber-stamp path the process exists to close.

---

## Preconditions

Before any decision is recorded:

1. **Actor present.** A non-empty reviewer identity is supplied; otherwise the
   action is rejected outright (no partial work).
2. **Targets are candidates.** Each target is an existing requirement. A
   requirement that is already `confirmed` is handled as a no-op outcome, not an
   error (see below); a `rejected` requirement cannot be approved.

There is **no precondition that every target will pass its gates** — the gates
are checked per requirement during the effect, and failure is an expected,
recoverable outcome, not a precondition violation.

---

## Effects

For **each** selected requirement, independently and atomically (each within its
own savepoint), the action:

1. Records a **governed approving decision** authored by the reviewer — a real
   decision record (status `Active`) that captures the reviewer's identity, the
   requirement under review, and the rationale that this is a human review
   recorded as a governed event, not a status edit. Any reviewer note is carried
   into the decision's context and summary.
2. Creates the **`requirement_approved_by_decision`** edge from the requirement
   to that decision, which triggers the existing `activate_by_decision` gate
   chain (readability → provenance → topic) **atomically**. If every gate
   passes, the requirement is **confirmed** and `requirement_approved_at` is
   stamped — confirmation happens **only** through this governed path, never by
   editing the status field.

The contract adds a reviewer-facing *front door* onto the already-built governed
approving-decision path; it does **not** introduce a second, weaker route to
confirmation, and it does not define, relax, or bypass the gates it invokes.

---

## Per-requirement outcomes

A multi-requirement approval yields one outcome **per requirement**, and the
failures never roll back or block the successes. The defined outcomes are:

| Outcome | Meaning | Decision recorded? | Requirement after |
|---|---|---|---|
| `confirmed` | Approved and all gates passed | yes | `confirmed`, `approved_at` stamped |
| `already_confirmed` | Re-approving an already-confirmed requirement | no | unchanged (no-op, not an error) |
| `failed` | A gate refused, the requirement is missing, or another validation error | no (rolled back) | **remains a candidate**, unchanged |

Key guarantees the contract makes about outcomes:

- **Partial success is normal and safe.** In a mixed selection, each requirement
  is decided on its own; one requirement's failure neither blocks nor undoes the
  others.
- **A failure teaches.** A `failed` outcome **surfaces the failing gate's own
  reason** ("what to fix") — readability, provenance, or topic — rather than a
  generic refusal. The decision and edge for that requirement are rolled back so
  no half-approval is left behind.
- **A gate-failing requirement remains a candidate.** It is never silently
  dropped and never partially confirmed; it stays in the candidate set so the
  reviewer can fix the named problem and re-approve.
- **Already-confirmed is reported plainly.** Re-approving a confirmed
  requirement is a no-op outcome, not an error.

---

## Postconditions

After the action returns:

1. Every `confirmed` requirement has a `requirement_approved_by_decision` edge
   to a governed decision naming the approving reviewer, status `confirmed`, and
   `requirement_approved_at` stamped.
2. Every `failed` requirement is exactly as it was before the action (a
   candidate), with no orphan decision or edge, and the reviewer has been given
   the gate's reason.
3. **`review_state` postcondition (REQ-249).** An approved requirement's review
   state is **`current`**, not `needs_review` — including when the approval
   immediately follows a reopen-for-change. The approval *is* the review, so a
   freshly approved requirement must not linger in the review-needed queue. This
   postcondition is owned and implemented by the **storage** facet (WTK-171,
   REQ-249); this contract *requires* it of any conforming implementation and
   names it as the binding postcondition of a successful approval.

---

## Contract boundaries (what it is not)

- **Decline and change** are the other two reviewer decision outcomes from the
  anchor. This contract covers **approve** only; declining or sending a
  requirement back for change is a separate action.
- **Authoring or editing requirement statements** is not part of this action.
  The reviewer approves what is presented; an unreadable statement is refused by
  the readability gate, and the reviewer's recourse is to send it back, not to
  rewrite it inside the approve action.
- **The gates themselves** (readability, provenance, topic resolution) are the
  anchor's already-built enforcement. This contract *invokes* them and *surfaces
  their reasons*; it does not define or relax them.
- **The release planning-item status-counts read API** (REQ-242, WTK-173) is
  co-scoped in WSK-150 but is unrelated to this contract.

---

## Acceptance shape (process level)

The contract is satisfied when, from the Requirements Review panel:

1. A reviewer — and only a reviewer, named on the record — can invoke approve
   over a selection of **one or more** candidate requirements in a single action.
2. The **right-click Approve action** and the **upper-right Approve button**
   invoke the same contract over the same selection.
3. Each selected requirement gets a **governed approving decision** authored by
   the reviewer and a `requirement_approved_by_decision` edge.
4. Each requirement that **passes its gates is confirmed** (and stamped); each
   that **fails surfaces its gate reason** and **remains a candidate**.
5. A mixed selection yields a **per-requirement outcome** (`confirmed`,
   `already_confirmed`, or `failed` with a reason); failures do not roll back
   successes.
6. No path confirms a requirement by editing its status field — confirmation is
   only ever through the governed approving-decision path.
7. After approval, each confirmed requirement's `review_state` is `current`
   (REQ-249).

These map directly to REQ-251's acceptance summary. The implemented behavior is
the `approve_requirements` access operation
(`crmbuilder_v2/access/review.py`), exposed at `POST /review/approvals` and
driven from the panel, which records a per-requirement governed decision and
edge inside an independent savepoint per requirement.

---

## Provenance

- **Requirement:** REQ-251 — *"Reviewers can approve requirements from the
  Requirements Review panel."* (human_defined, confirmed.)
- **Postcondition requirement:** REQ-249 — review_state returns to `current` on
  approval (storage facet, WTK-171).
- **Planning item / workstream:** PI-230, Design workstream WSK-150.
- **Work task:** WTK-172 (methodology-process).
- **Sibling facets:** WTK-170 (methodology-product, the persona + capability),
  WTK-171 (storage, review_state), WTK-173 (api, status-counts read — co-scoped
  only).
- **Anchor:** `requirements-provenance-and-review-anchor.md` — the principle,
  the gates, and the "readability is load-bearing" rule this contract serves.
