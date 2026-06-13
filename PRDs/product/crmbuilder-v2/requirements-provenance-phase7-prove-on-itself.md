# Requirements Provenance — Phase 7: Prove It On Itself

**Status:** draft, 2026-06-13. The capstone of the requirements-provenance
rebuild (anchor: `requirements-provenance-and-review-anchor.md`; engine merged to
`main` in PR #4). The anchor's own rule: *the founding requirement becomes the
first record created under the new process — a top-level, human-defined
requirement, rooted in the conversation that produced the anchor.* If the engine
cannot cleanly hold its own founding requirement, it is not done.

This is the dogfood: run CRMBuilder's requirements-provenance capability through
the very model it implements, against the **CRMBUILDER** engagement (ENG-001).

---

## Prerequisite (operational, one step at a time at the terminal)

The engine is merged to `main`, but the **running** API was started from older
code, and the live DB predates migrations 0049–0051. Before any record below
will take:

1. Stop the running API (the desktop UI owns it — or stop the standalone
   `crmbuilder-v2-api` on 8765).
2. Apply the new migrations to the live engagement DB (`alembic upgrade head`, or
   apply the deltas directly per the create_all-managed live-DB practice):
   `0049` (requirement columns + 6 edge kinds), `0050`
   (`planning_item_implements_requirement`), `0051` (`review_signoffs`).
3. Restart the API from current `main` and confirm `GET /review/...` and
   `GET /coverage/capabilities` respond.

All records below are entered **in real time via direct API POST** (DEC-383),
each request carrying `X-Engagement: CRMBUILDER`.

---

## The records — the spine, rooted in this conversation

Created bottom-rooted so each gate is genuinely exercised, not bypassed.

1. **Topic** — the home for this capability's review. Name e.g.
   *"Requirements Capture, Documentation & Organization."* Reuse an existing
   topic if one fits; else `POST /topics`.

2. **Session** — this design dialogue. `POST /sessions`, `session_medium = chat`,
   dated 2026-06-13, with the membership edge `session_belongs_to_project` to the
   relevant project. This is the medium in which the model was defined.

3. **Conversation** — the topical sub-unit within the session where the founding
   requirement was defined with the human. `POST /conversations` +
   `conversation_belongs_to_session` (its session) +
   `conversation_belongs_to_topic` (the topic — exactly one). **This is the
   provenance root.**

4. **Decision** — *"Adopt the requirements-provenance-and-review model."*
   `POST /decisions`, summarizing the anchor as the settled model, with
   `decided_in` → the session. This is the approving decision for the founding
   requirement.

5. **Founding requirement** (top-level, `origin = human_defined`). A readable
   statement — no embedded identifiers, one idea:
   > *Requirements are captured, organized, and verified so that every
   > requirement traces to the human conversation that defined it and is
   > reviewable by the project manager.*
   - acceptance: *A project manager can find any requirement under its topic,
     read it in plain language, and trace it to the conversation that defined it;
     and nothing is built without a requirement.*
   - Edges: `requirement_defined_in_conversation` → the conversation;
     `requirement_belongs_to_topic` → the topic.
   - **Approve** it: `requirement_approved_by_decision` → the decision. This
     activates it — and only succeeds because it resolves to provenance **and** a
     topic **and** its statement is readable. (That single POST exercises three
     gates at once.)

6. **Child requirements** — decompose the founding one into the model's
   load-bearing rules. Each `requirement_refines_requirement` → the founding
   requirement (so it inherits provenance + topic), then approved via a decision
   edge. Draft statements (each readable, one idea):
   - *Every requirement traces to a conversation, directly or through its
     ancestors.*
   - *No work is built without a requirement above it, and nothing a human states
     is silently dropped — it becomes a requirement or is explicitly declined.*
   - *A requirement becomes active only when a human approves it, and only if it
     resolves to a conversation and a topic.*
   - *When a requirement's meaning changes, its descendants are flagged for
     re-review.*
   - *A requirement statement must be readable enough to review before it can be
     approved.*
   - *The project manager reviews by topic and records a sign-off attesting the
     set matches intent.*

7. **Plan links** — connect the built work to the requirements so the loop
   closes. For each phase of this rebuild, a planning item with
   `planning_item_implements_requirement` → the child requirement it realizes
   (reuse existing planning items where they exist, else create them). After
   this, `GET /coverage/capabilities` should show these planning items **not**
   in `orphan_planning_items`.

8. **Sign-off** — the human attestation. `POST /review/signoffs`
   (`signoff_reviewer` = Doug, `signoff_attestation` = "matches intent") for the
   topic. Turns "reviewable" into "reviewed, on the record."

---

## What each step proves (gate by gate)

| Gate (engine) | Proven by |
|---|---|
| Provenance root + topic reachability | the founding requirement activates only because it resolves to both |
| Readability at approval | the statements pass; an unreadable one would block the approve |
| Decision resolves (deliver) | the approve edge flips candidate → confirmed |
| Hierarchy + inheritance | children inherit the parent's provenance + topic and still activate |
| No orphan capability | the plan links make the work traceable; coverage shows them non-orphan |
| Living drift | editing the founding requirement flags the children `needs_review` |
| Review surface + sign-off | the topic tree, the read-back document, and the recorded sign-off |

## Verification (read-backs)

- `GET /review/topics/{topic}` → the founding requirement with its children.
- `GET /review/topics/{topic}/document` → reads cleanly top to bottom.
- `GET /coverage/capabilities` → the linked planning items are not orphans.
- `GET /review/drift-queue` after a parent edit → the children appear.
- `GET /review/signoffs?topic={topic}` → the sign-off.

When all five read true, the engine has held its own founding requirement — and
Phase 7 is complete.

---

## Open choices for the run (decide at execution)

- Which existing **project** the session belongs to (CRMBuilder's v2 program), or
  a dedicated one.
- Whether the topic is new or an existing governance/methodology topic.
- How many child requirements to record now vs. grow over time (the six above are
  a sufficient first set; the tree can deepen later).
- Which planning items to link (the PR #4 phase commits map naturally to plan
  items; create or reuse).
