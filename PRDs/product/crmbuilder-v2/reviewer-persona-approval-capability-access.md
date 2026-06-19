# Reviewer Persona — Approval Capability (access facet)

**Status:** design, 2026-06-18. Specifies the **access-layer** design of the
reviewer persona's capability to approve candidate requirements from the
Requirements Review panel (REQ-251): how the access layer *authorizes* the
reviewer, *names* the capability as a distinct permission, and *executes* the
approval as a per-requirement governed operation. This is the **access** facet
of design workstream WSK-154 (PI-231), the sibling of the product, process, and
storage facets below. Read those and `requirements-provenance-and-review-anchor.md`
first — they establish *who* the reviewer is, *why* approval must be a governed
event, and the *product/process contract* the reviewer sees. This document does
not restate the persona or the "why"; it pins down the access model that makes
the reviewer capability **enforceable** and the approval **atomic per
requirement**.

Three sibling facets carry the rest of the same workstream and are referenced,
not duplicated, here:

- **methodology-product** (`reviewer-persona-approval-capability.md`, WTK-170 of
  the prior round) — the persona and the product-level capability.
- **methodology-process** (`approve-requirement-process-contract.md`, WTK-184) —
  the `approve_requirement` actor/affordance/effect/postcondition contract.
- **storage** (`pi-230-review-state-post-approval-semantics-wtk171.md`,
  WTK-183) — `requirement.review_state` returns to `current` on approval
  (REQ-249).

A *capability*, at the access layer, is the pairing of **a named permission**
(the authorization to do the thing) with **the operation it gates** (the thing
itself). This document specifies both halves for reviewer approval.

---

## The reviewer persona as an access-layer subject

The product facet defines the **reviewer** as the human who defines what is to
be built and whose judgment the provenance-and-review process exists to capture.
At the access layer, that persona is not a row or an entity — it is a **set of
roles that hold a permission**. A principal *is* a reviewer, for approval
purposes, iff it holds the `approve` permission on the active engagement.

The reviewer persona maps to the existing RBAC roles (`vocab.ROLE_PERMISSIONS`):

| Role | Reviewer persona? | Holds `approve`? |
|---|---|---|
| `owner` | yes (total, engagement-spanning) | yes |
| `editor` | yes (the working reviewer) | yes |
| `viewer` | no | no |
| `orchestrator`, `pi_lead`, `phase_specialist`, `area_specialist` | no — agent tiers | no |

The load-bearing access decision: **confirming a requirement is a human review,
not an agent action.** Every ADO agent tier can read, write, and claim work, but
none of them holds `approve`. Approval authority is the one capability the
agents that *propose* candidate requirements are deliberately denied, so the
human-in-the-loop is enforced by the permission model, not merely by convention.

---

## The capability as a named permission (`approve`)

Reviewer approval is its **own coarse permission verb** — `approve` —
distinct from `create`, `update`, and `admin` (`vocab.RBAC_PERMISSIONS`). The
design choice and its reason:

- **A distinct verb, not generic `create`.** A reviewer records an approving
  *decision*, which is a `create` under the hood. But authorization to *approve
  a requirement for delivery* must be grantable and revocable **independently**
  of authorization to author content. Folding approval into `create` would make
  any content author a reviewer; the whole point of the persona is that
  approval is a narrower, human-judgment authority. So `approve` is its own verb
  in the permission set and its own column in the role → permission map.
- **Withheld from agents by construction.** Because `approve` is separate, the
  agent-tier roles can be given full read/write/claim (`create`, `update`,
  `delete`, `claim`) without ever acquiring approval authority. The agent tiers'
  permission sets simply omit `approve`. There is no path by which an agent's
  ordinary write authority leaks into approval authority.
- **Engagement-scoped like every permission.** `approve` is held *per
  engagement*: a principal that is an `editor` on ENG-002 is a reviewer there
  and **not** on ENG-001. Reviewer rights do not travel across engagements.

This permission already exists in the vocabulary and role map; this facet
*names it as the reviewer capability* and binds the design rationale to it.

---

## The authorization gate

The capability is enforced by a single `rbac.check` at the **top** of the
access operation, before any requirement is touched:

```python
rbac.check("approve", engagement_id=get_active_engagement())
```

Its guarantees:

- **The gate sits above the per-requirement loop.** Authorization is decided
  once for the whole action. An unauthorized principal approves **none** of a
  multi-requirement batch — there is no partial approval and no per-requirement
  authorization. This is what makes "a denied reviewer confirms nothing" a
  structural property, not a coincidence of ordering.
- **Auth off ⇒ open (the localhost default).** When
  `Settings.principal_auth_enabled` is off — the default-owner localhost flow
  the desktop app and dogfood run in — the check is a no-op and the operation
  runs as the implicit owner. Reviewer enforcement is a production-RBAC concern,
  not a local-dev obstacle.
- **Auth on ⇒ `PermissionDenied` (→ HTTP 403).** When auth is on, a principal
  lacking `approve` on the active engagement — including an **anonymous**
  request (auth on, no active principal) — is denied with
  `rbac.PermissionDenied`, surfaced by the API as 403. Denial *prevents*
  confirmation: it raises before the loop, so the candidates are left exactly as
  they were, no governed decision is recorded, and nothing is half-approved.
- **Reviewer identity is validated independently of authorization.** Being
  *authorized* to approve (the `approve` permission) and *naming the reviewer on
  the record* (the `reviewer` argument) are two separate requirements. Even an
  authorized principal must supply a non-empty `reviewer`; an empty reviewer is
  rejected with an `UnprocessableError` before any decision is recorded. The
  permission says *may this principal approve*; the `reviewer` field records
  *who, on the record, did*.

---

## The access operation (`approve_requirements`)

The capability is delivered by `crmbuilder_v2.access.review.approve_requirements`,
a **thin front door** onto the already-built governed approving-decision path.
It adds a way to *invoke* that path over a selection from the panel; it does
**not** add a second, weaker route to confirmation.

**Signature and shape.**

```python
def approve_requirements(
    session,
    *,
    requirement_identifiers: list[str],
    reviewer: str,
    decision_date: str,
    note: str | None = None,
) -> list[dict]:
```

It returns one result dict **per input identifier, order-preserving**, so a
caller can map each outcome back to the row the reviewer selected.

**Per-requirement isolation.** Each identifier is decided **independently,
inside its own `session.begin_nested()` savepoint** (`_approve_one`). For each
requirement the operation:

1. Records a **governed approving decision** (status `Active`) authored by the
   reviewer — reusing `repositories.decisions.create` — capturing the reviewer's
   identity, the requirement under review, the rationale that this is a human
   review recorded as a governed event (not a status edit), and any reviewer
   `note`.
2. Creates the **`requirement_approved_by_decision`** edge from the requirement
   to that decision — reusing `repositories.references.create` — which triggers
   the existing `requirement.activate_by_decision` gate chain **atomically**.

**The gate chain it invokes (defined elsewhere, invoked here).** The edge
triggers `activate_by_decision`, which confirms the requirement only if, in
order:

1. **readability** — `access/readability.py` rejects an embedded-identifier or
   otherwise unreadable statement;
2. **provenance** — the requirement (or an ancestor, via
   `requirement_refines_requirement`) has a `requirement_defined_in_conversation`
   edge (the no-orphan-capability rule);
3. **topic** — the requirement (or an ancestor) resolves to a topic, so it is
   reviewable under the topic-first review.

If every gate passes the requirement is flipped to `confirmed`,
`requirement_approved_at` is stamped, and `review_state` is returned to
`current` (the storage facet / REQ-249). This facet **invokes** the gates and
**surfaces their reasons**; it does not define or relax them.

**Per-requirement outcomes.** Each result is one of:

| `outcome` | Meaning | Decision recorded? | Requirement after |
|---|---|---|---|
| `confirmed` | Approved, all gates passed | yes | `confirmed`, `approved_at` stamped |
| `already_confirmed` | Re-approving an already-confirmed requirement | no | unchanged (no-op, not an error) |
| `failed` | A gate refused, the requirement is missing, or another validation error | no (savepoint rolled back) | **remains a candidate**, unchanged |

The access guarantees behind those outcomes:

- **Partial success is normal and safe.** Because each requirement is decided in
  its **own savepoint**, one requirement's gate failure neither rolls back nor
  blocks the others. A mixed selection yields a mix of outcomes, never an
  all-or-nothing transaction.
- **A failure teaches.** On a caught `UnprocessableError`/`ValidationError`, the
  savepoint rolls back the decision and edge (no orphan half-approval) and the
  result carries the **gate's own reason string** — "what to fix", not a generic
  refusal.
- **Already-confirmed is a no-op, reported plainly.** A requirement already
  `confirmed` returns `already_confirmed` with no new decision, rather than
  erroring. (A `rejected` requirement cannot be approved — the gate chain
  refuses it as a `failed` outcome.)

---

## Composition with the rest of the access layer

- **Engagement scope.** The operation runs under the ORM execute hook's
  row-level engagement filter (`get_active_engagement()`); it reads and writes
  only the active engagement's rows, and the same engagement is the one the
  `approve` permission is checked against — authorization and data scope name
  the same engagement.
- **Single governed path to confirmation.** Confirmation is reachable **only**
  through `activate_by_decision`, triggered **only** by the
  `requirement_approved_by_decision` edge. There is no status-edit path (the
  bypass closed by the prior round). This operation is one caller of that path;
  the API endpoint `POST /review/approvals` (and the Qt panel above it) is the
  other surface, and both go through this same access operation.
- **Reuse, not reimplementation.** The operation composes
  `repositories.decisions.create`, `repositories.references.create`,
  `repositories.requirement.get_requirement`, `rbac.check`, and the existing
  gate chain. It introduces no new persistence, no new edge kind, and no new
  permission — only the reviewer-facing batch entry point with per-requirement
  savepoint isolation.

---

## Capability boundaries (what this facet is not)

- **The gates themselves** (readability, provenance, topic) are the anchor's
  already-built enforcement in `activate_by_decision`. This facet invokes them
  and surfaces their reasons; it does not define or relax them.
- **The `review_state` transition** back to `current` on approval is the
  **storage** facet (WTK-183 / REQ-249). This facet depends on it as a
  postcondition but does not own it.
- **The process contract** (actor/affordance/effect/postcondition the verifier
  holds behavior against) is the **methodology-process** facet (WTK-184).
- **The panel affordances** — the right-click action and upper-right button —
  are the **ui** facet (WTK-185). This facet exposes the operation those
  affordances call; it does not specify the surface.
- **Decline and change** are the other two reviewer decision outcomes from the
  anchor. This capability covers **approve** only; declining or sending a
  requirement back for change is a separate access operation.

---

## Acceptance shape (access level)

The access facet is satisfied when:

1. `approve` is a **distinct permission verb** in `RBAC_PERMISSIONS`, held by
   exactly the reviewer-persona roles (`owner`, `editor`) and withheld from
   `viewer` and **every** agent tier, per engagement.
2. `approve_requirements` is **gated by `rbac.check("approve", ...)` above the
   per-requirement loop**: a no-op when auth is off; `PermissionDenied` (→ 403)
   when auth is on and the principal — or an anonymous request — lacks the
   permission; and a denial confirms **nothing** in the batch.
3. An **authorized** reviewer with an **empty** `reviewer` argument is rejected
   before any decision is recorded.
4. For each input identifier the operation records a **governed approving
   decision** naming the reviewer and a `requirement_approved_by_decision` edge,
   **each in its own savepoint**, and returns an **order-preserving**
   per-requirement result.
5. Each requirement that **passes its gates is confirmed** (and stamped); each
   that **fails surfaces the gate's own reason** and **remains a candidate**,
   with its decision and edge rolled back; an already-confirmed requirement is a
   plain `already_confirmed` no-op.
6. No path in the operation confirms a requirement by editing its status field —
   confirmation is only ever through `activate_by_decision` via the approving
   edge.

These map directly to REQ-251's acceptance summary. The implemented behavior is
`crmbuilder_v2/access/review.py::approve_requirements` (+ `_approve_one`),
exposed at `POST /review/approvals` and driven from the Requirements Review
panel; its authorization is covered by
`tests/crmbuilder_v2/access/test_review_approve_authz.py`.

---

## Provenance

- **Requirement:** REQ-251 — *"Reviewers can approve requirements from the
  Requirements Review panel."* (human_defined, confirmed.)
- **Postcondition requirement:** REQ-249 — review_state returns to `current` on
  approval (storage facet).
- **Planning item / workstream:** PI-231, Design workstream WSK-154.
- **Work task:** WTK-182 (access).
- **Sibling facets (WSK-154):** WTK-183 (storage, review_state), WTK-184
  (methodology-process, the process contract), WTK-185 (ui, the panel
  affordances). Prior-round product facet: `reviewer-persona-approval-capability.md`.
- **Implementation anchored:** `crmbuilder_v2/access/review.py`
  (`approve_requirements`/`_approve_one`), `crmbuilder_v2/access/rbac.py`,
  `crmbuilder_v2/access/vocab.py` (`RBAC_PERMISSIONS` / `ROLE_PERMISSIONS`),
  `crmbuilder_v2/access/repositories/requirement.py` (`activate_by_decision`).
- **Anchor:** `requirements-provenance-and-review-anchor.md` — the principle,
  the gates, and the "readability is load-bearing" rule this capability serves.
