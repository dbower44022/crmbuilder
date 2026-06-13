# Requirements Provenance — Build Translation

**Status:** draft, 2026-06-13. Turns the process anchor
(`requirements-provenance-and-review-anchor.md`) into a concrete build against
the current v2 schema. Read the anchor first; this document does not restate the
"why."

This is the architecture pass. It names what to change and in what order. It
does **not** write migrations or code yet — the blocking decisions in Phase 0
come first.

---

## What already exists (reuse, don't rebuild)

The schema map turned up substrate we keep:

- **Topic hierarchy** — `topics.parent_topic_id` self-FK already gives the topic
  tree. No change needed for topic nesting.
- **Conversation → session, mandatory 1:1** — the `conversation_belongs_to_session`
  edge is enforced today. Because a conversation belongs to exactly one session,
  a requirement that links to its conversation **transitively carries the
  session** — so we do not need a separate requirement→session edge. The save
  threshold ("conversation + session") is met by one conversation link.
- **The decline outcome, end to end** — `rejected_by_decision` (requirement →
  decision) plus the `rejected` terminal status already implement "a decision
  declines a requirement, on the record" (shipped as PI-153). This is the
  pattern the approve and change outcomes copy.
- **The verified stage** — `requirement_verified_by_test_spec` already links a
  requirement to the test that proves it. The sixth spine stage is representable
  now.
- **Requirement status** — `{candidate, confirmed, deferred, rejected}` maps
  almost directly onto the anchor's lifecycle: `candidate` = saved/proposed,
  `confirmed` = active, `rejected` = declined. We add gates around the
  transitions, not a new status vocabulary.

So three of the harder pieces — the decline path, the verified link, and the
active/declined states — are largely in place.

---

## What's missing (the build)

Grouped by the anchor rule each one serves.

### Hierarchy
- **Requirement parent link** — ABSENT. New same-type edge
  `requirement_refines_requirement` (child → parent). Chosen as an edge, not a
  column, so the orphan check, provenance inheritance, and drift propagation all
  traverse the one `refs` graph the rule engine already walks. *(Phase 0
  decision: edge vs. self-FK column.)*

### Provenance
- **Requirement → conversation** — ABSENT. New edge
  `requirement_defined_in_conversation`. Carries the session transitively.
- **Requirement → topic** — ABSENT (today only the generic `is_about`). New
  dedicated edge `requirement_belongs_to_topic`, explicit and queryable. The link
  is **inherited down** the requirement tree: required on a root, optional on a
  child, which inherits its nearest ancestor's topic until the user re-links it
  to a subtopic.
- **Requirement origin** — ABSENT. New column `requirement_origin`
  ∈ `{human_defined, ai_derived}`.

### The decision outcomes
- **Decline** — EXISTS (`rejected_by_decision`). Reuse.
- **Deliver / approve** — ABSENT. New edge `requirement_approved_by_decision`
  (requirement → decision); drives `candidate → confirmed`.
- **Change** — ABSENT. New edge `requirement_changed_by_decision`; supersedes
  the current requirement text and returns it to `candidate` for re-approval.

### Save vs. active
- The states exist; the **gates** do not. To be enforced in the access layer
  (Phase 2), not new schema.

### One topic per conversation
- **Conversation → topic** — ABSENT as a constrained link. New edge
  `conversation_belongs_to_topic`, with access-layer cardinality of exactly one
  (mirrors how `conversation_belongs_to_session` is enforced).

### Living drift
- **Review state** — ABSENT. New column `requirement_review_state`
  ∈ `{current, needs_review}`, plus a propagation routine (Phase 4).

### Readability
- No content gate exists. New validator (Phase 5).

### Review surface
- No panel, no read-back document (Phase 6).

---

## Phased build

Each phase is independently shippable and independently verifiable.

**Phase 0 — Decisions (blocking).** Settle the open design decisions below. Small
but gating; everything downstream depends on them.

**Phase 1 — The requirement graph (schema).**
- New edge kinds in `vocab.py` (`REFERENCE_RELATIONSHIPS` + `_kinds_for_pair`),
  with the matching `refs.relationship_kind` CHECK migration (SQLite batch chain
  + the Postgres tree). Kinds: `requirement_refines_requirement`,
  `requirement_defined_in_conversation`, `requirement_belongs_to_topic`,
  `conversation_belongs_to_topic`, `requirement_approved_by_decision`,
  `requirement_changed_by_decision`.
- New requirement columns: `requirement_origin`, `requirement_review_state`,
  `requirement_approved_at`. Migration on both dialects.
- No new entity types, so no `change_log` CHECK rebuild needed — but verify
  against the live DB, not just `create_all` (known gotcha).

**Phase 2 — The gates (access layer).** Enforced in `access`, so no client can
bypass — desktop, agent, and raw API alike.
- **No orphan requirement:** a saved requirement must have a parent edge **or** a
  `requirement_defined_in_conversation` edge.
- **Provenance inheritance:** a child with no direct conversation link inherits
  through its parent chain; the chain must root in a conversation.
- **Save vs. active:** `candidate → confirmed` requires an
  `requirement_approved_by_decision` edge. An `ai_derived` requirement cannot go
  active without it (approval before active).
- **Decision resolves three ways:** approve → confirmed; decline → rejected
  (exists); change → back to candidate + `needs_review`.
- **One topic per conversation:** cardinality 1 on `conversation_belongs_to_topic`.
- **Requirement topic:** a root requirement must carry a
  `requirement_belongs_to_topic` edge; a child may omit it and inherit the
  nearest ancestor's topic.

**Phase 3 — No orphan capability (the bidirectional gate).** The rule the
original failure broke.
- Require every planning item to trace up to a requirement (a
  `planning_item → requirement` link, directly or via its workstream); enforce it.
- A coverage report: built things (planning items, commits) with no requirement
  above them, and conversation intents that never became a requirement or a
  decline. This is the "nothing built unasked, nothing said dropped" check.

**Phase 4 — Living drift.** On a requirement or decision change, propagate
`needs_review` to descendants and to downstream spine stages; an `ai_derived`
child re-opens for approval. Requires the Phase 1 `review_state` column.

**Phase 5 — Readability gate.** A validator at create/approve time: one
declarative idea, an acceptance criterion present, no embedded build history or
jargon. AI-assisted, but blocking — a statement that fails is not presented for
human approval. This is what keeps approval from degrading into rubber-stamping.

**Phase 6 — Review surface.**
- Desktop panel: navigate the requirement tree by topic, open any requirement,
  trace it to its conversation, see the six spine stages side by side.
- Read-back document generator: a plain-language render of a topic's requirement
  set for review away from the app.
- Recorded validation event ("reviewed, not reviewable"): the PM's dated
  attestation that a topic's set matches intent.

**Phase 7 — Prove it on itself.** Capture the founding requirement —
"requirements must be captured, organized, and verified this way" — as the first
record created under the finished process, rooted in this conversation.

---

## Phase 0 decisions — resolved (2026-06-13)

1. **Parent link** — graph **edge** `requirement_refines_requirement` (child →
   parent), so one graph carries hierarchy, provenance, and drift. ✓
2. **Decision outcomes** — **three distinct edges** (approve / change / reuse the
   existing reject), so the outcome is explicit in the graph. ✓
3. **"Change"** — **return-to-candidate + the decision trail + `updated_at`**; no
   separate version chain. ✓
4. **Readability validator** — **blocking**, inside the approval flow. A
   statement that fails is never presented for human approval. ✓
5. **Topic granularity** — requirement levels and topic levels are
   **independent, connected by the human**. A requirement's topic is **inherited
   down** the requirement tree from the nearest ancestor that carries a topic
   link; the user may **re-link** any requirement to a subtopic, and that topic
   then governs it and its descendants until re-linked again. So a **root**
   requirement must carry a topic link; a **child** may omit it and inherit.
   Example: three requirement levels under the top-level topic, then a
   fourth-level requirement re-linked to a subtopic. ✓

Still deferred from the anchor and not in this plan: cross-cutting requirements,
and final decomposition-depth governance.
