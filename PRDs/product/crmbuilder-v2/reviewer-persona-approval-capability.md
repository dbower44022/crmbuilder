# Reviewer Persona — Approval Capability

**Status:** design, 2026-06-18. Defines the *reviewer persona* and the
*approval capability* it is given in the Requirements Review panel (REQ-251).
This is the **methodology-product** facet of the design workstream WSK-150
(PI-230). Read `requirements-provenance-and-review-anchor.md` first — this
document does not restate the "why" of provenance and review; it names the
persona that does the reviewing and the capability that lets them finish a
review without leaving the panel.

Three sibling facets carry the rest of the same workstream and are referenced,
not duplicated, here:

- **storage** (WTK-171) — `requirement.review_state` post-approval semantics
  (REQ-249): approval returns an approved requirement to `current`.
- **methodology-process** (WTK-172) — the `approve_requirement` *process
  contract*: actor, affordances, selection, surface, effects, postcondition.
- **api** (WTK-173) — the release planning-item status-counts read API
  (REQ-242); related only by being co-scoped, not by the approval capability.

---

## The persona

The **reviewer** is the human who defines what is to be built — the project
manager of the anchor's principle ("The human project manager defines what is
to be built"). The reviewer is the one person whose judgment the whole
provenance-and-review process exists to capture: every requirement must trace
to something this persona defined, or to an AI interpretation this persona
approved.

The reviewer is **not** an AI agent and **not** a developer. AI agents propose
candidate requirements; the reviewer is the human who reads a candidate against
its source conversation and decides whether it matches intent. Approval is the
reviewer's judgment recorded as a governed event — never a status edit, never a
rubber stamp.

The reviewer's job-to-be-done, in the reviewer's own words:

> *"I am looking at a topic's candidate requirements. The ones that match what
> I meant, I want to approve — right here, in the same place I read them — and
> have the system record that I approved them and confirm the ones that are
> ready. The ones that aren't ready, I want to be told why, so I know what to
> fix, and I want them to stay candidates until they are."*

---

## The capability

**From the Requirements Review panel, the reviewer can select one or more
candidate requirements and approve them in a single action.** The action is
offered two ways so it meets the reviewer wherever their hands already are:

- a **right-click Approve action** on the selected rows, and
- an **Approve button in the upper-right** of the panel's approval surface.

Approving records, for each selected requirement, a **governed approving
decision** authored by the reviewer, and confirms each requirement that passes
its gates. The capability is a thin, reviewer-facing front door onto the
existing governed approving-decision path — it adds a way to *invoke* that path
from the panel; it does not add a second, weaker path to confirmation.

What the capability guarantees, at the product level:

- **One action, many requirements.** A selection of one or many candidates is
  approved together. The reviewer is not forced to approve one at a time.
- **The approving reviewer is recorded.** Each approval names the human who made
  it, on the record, as part of the governed decision.
- **Confirmation only through the gates.** A requirement is confirmed only if
  its readability, provenance, and topic gates pass. Approval is the reviewer's
  *intent*; the gates are the system's *check*. Both must hold.
- **Partial success is normal and safe.** In a multi-requirement approval, each
  requirement is decided independently. One requirement failing its gates
  neither blocks nor undoes the others. The reviewer gets a per-requirement
  outcome.
- **A failure teaches, it does not just refuse.** A requirement that fails its
  gates **surfaces the gate's own reason** ("what to fix") and **remains a
  candidate**. It is not silently dropped and not partially confirmed.
- **Already-confirmed is a no-op, not an error.** Re-approving a requirement
  that is already confirmed reports that state plainly rather than failing.

This is the capability that lets the human **complete the review inside the
panel** — the surface where the requirement is readable and traceable to its
conversation — rather than only by hand-assembling interface-layer calls
outside it. That matters for the anchor's load-bearing rule: *readability is
only worth enforcing if the human actually approves where the readable content
is.* Pushing approval out to a raw API call is exactly the path that reintroduces
the rubber stamp this process exists to kill.

---

## Where it lives in the product

The capability lives on the **Requirements Review panel** (Governance sidebar),
on the **approval surface** that already lists the candidates awaiting
activation and what each still needs. The reviewer arrives there by the normal
topic-first review flow (anchor §"How a review works"): pick a topic, read its
requirement tree, trace anything in question to its conversation — and then,
without leaving the panel, select the candidates that match intent and approve
them.

The approval surface is the natural home because it already answers the
question the reviewer asks immediately before approving — *"what does each of
these still need?"* — so the decision to approve and the act of approving sit in
one place.

---

## Capability boundaries (what it is not)

To keep this facet scoped to the persona and its capability, the following are
explicitly **out** of this document and owned elsewhere:

- **The mechanical process contract** — the precise actor/affordance/effect/
  postcondition specification of `approve_requirement` — is WTK-172
  (methodology-process).
- **The `review_state` transition on approval** (back to `current`, clearing a
  reopened-for-change flag) is WTK-171 (storage) and REQ-249.
- **The gates themselves** (readability, provenance, topic resolution) are the
  already-built enforcement of the anchor; this capability *invokes* them and
  *surfaces their reasons*, it does not define or relax them.
- **Decline and change** are the other two decision outcomes from the anchor.
  This capability covers **approve** only. Declining or sending a requirement
  back for change is a separate reviewer action, not part of this capability.
- **Authoring or editing requirement statements** is not a reviewer capability
  here. The reviewer approves what is presented; if a statement is unreadable
  the readability gate refuses it and the reviewer's recourse is to send it
  back, not to rewrite it in the approve action.

---

## Acceptance shape (product level)

The capability is satisfied when, from the Requirements Review panel:

1. The reviewer can select one **or more** candidate requirements.
2. Both affordances — the **right-click Approve action** and the **upper-right
   Approve button** — invoke the same approval.
3. Each selected requirement gets a **governed approving decision** that names
   the **approving reviewer**.
4. Each requirement that **passes its gates is confirmed**; each that **fails**
   **surfaces its reason** and **remains a candidate**.
5. A mixed selection yields a **per-requirement outcome** — confirmed,
   already-confirmed, or failed-with-reason — and the failures do not roll back
   the successes.
6. No path in this capability confirms a requirement by editing its status
   field; confirmation is only ever through the governed approving-decision
   path.

These map directly to REQ-251's acceptance summary; the underlying behavior is
the `approve_requirements` access operation that records a per-requirement
decision and `requirement_approved_by_decision` edge inside an independent
savepoint per requirement.

---

## Provenance

- **Requirement:** REQ-251 — *"Reviewers can approve requirements from the
  Requirements Review panel."* (human_defined, confirmed.)
- **Sibling requirement:** REQ-249 — review_state returns to `current` on
  approval (storage facet).
- **Planning item / workstream:** PI-230, Design workstream WSK-150.
- **Work task:** WTK-170 (methodology-product).
- **Anchor:** `requirements-provenance-and-review-anchor.md` — the principle,
  the gates, and the "readability is load-bearing" rule this capability serves.
