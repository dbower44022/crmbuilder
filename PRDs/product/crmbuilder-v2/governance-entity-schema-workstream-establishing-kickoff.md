# Governance Entity Schema Design — Workstream-Establishing Planning Conversation — Kickoff Prompt

**Last Updated:** 05-20-26 14:30
**Purpose:** Seed prompt for a new Claude.ai conversation that establishes the governance entity schema-design workstream and produces its scaffolding artifacts. Analog of Session 011 for the methodology entity schema-design workstream. This conversation does not design schemas itself — it produces the workstream master plan, the schema-spec methodology guide, and a kickoff prompt for each of the six per-entity schema-design conversations that follow.
**Position in workstream:** Workstream-establishing planning conversation. First conversation of the governance entity schema-design workstream.
**Predecessor:** A strategic scoping conversation in May 2026 that identified the governance gap and resolved six principle-level questions. None of those resolutions were recorded as formal decisions in the governance database at the time. The workstream-establishing conversation opening against this kickoff prompt re-records them as its first order of business.
**Successor conversations:** Six per-entity schema-design conversations, then a build-planning conversation that consumes the six schema specifications and produces the integrating Product Requirements Document, implementation plan, and per-slice execution prompts. Target version for the build is open — to be set by the build-planning conversation in coordination with the active version sequence at that time.

---

## The Task

Establish the governance entity schema-design workstream and produce its scaffolding artifacts. Four categories of deliverable:

1. Six new decision records formalizing the six incoming principles below (numbers in the Decision 117 range; actual values resolved at conversation close).

2. `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md` — workstream master plan. Names the workstream, states its purpose, lists the six per-entity schema-design conversations in order, names their predecessor and successor relationships, identifies the build-planning conversation that closes the workstream, and links to the methodology guide and each kickoff prompt.

3. `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md` — methodology guide. Sets the template each per-entity schema-design conversation follows to produce one schema specification file. Parallels `methodology-entity-schema-spec-guide.md` in form, adapted for governance entities. Inherits conventions from the methodology workstream where compatible: parent-prefix field naming (Decision 046), source-first relationship-kind naming (Decision 048), three-status lifecycle posture.

4. Six kickoff prompts under `PRDs/product/crmbuilder-v2/`, one per per-entity schema-design conversation:
   - `schema-design-kickoff-workstream.md`
   - `schema-design-kickoff-conversation.md`
   - `schema-design-kickoff-reference-book.md`
   - `schema-design-kickoff-work-ticket.md`
   - `schema-design-kickoff-close-out-payload.md`
   - `schema-design-kickoff-deposit-event.md`

---

## The Six Incoming Principles

Captured in the predecessor scoping conversation and re-stated here for formal recording during this conversation's close. Each becomes one decision record.

**Principle 1 — Three purpose-built entity-type families for workflow files.** Track workflow files as three families (reference book — long-lived versioned documents; work ticket — single-use seed documents; deposit bucket — close-out payload paired with its application event) rather than one generalized governed-artifact type. The families have meaningfully different lifecycles and benefit from per-family schemas.

**Principle 2 — Two entities within the deposit bucket, not one.** Separate the close-out payload (the slip) from the deposit event (the record of when it was applied). Their lifecycles are meaningfully different: a payload is produced once at conversation close and applied once; a deposit event is created at apply-time and links the payload to its outcome and the records it wrote.

**Principle 3 — Conversation as a first-class entity.** A conversation entity represents the unit of conversational work through its full lifecycle: planned, kickoff-drafted, ready, in-flight, complete, cancelled, superseded. The session record (already in the database) captures what happened after a conversation completes; the conversation record captures the work unit through all states including before it has happened.

**Principle 4 — Workstream as a first-class entity.** A workstream entity represents a coherent line of related conversations. Workstreams have their own lifecycle (planned, in flight, complete) and let the database answer queries like "show me every conversation in this workstream and the state of each."

**Principle 5 — Single source of truth.** These additions close the gap between the governance database's stated single-source-of-truth role and its actual coverage. After this workstream lands, queries like "what is queued up next," "did this payload's apply succeed and produce the records it should have," and "what version of the Product Requirements Document was in force at the time of session NNN" become answerable from the database without filesystem scanning.

**Principle 6 — Governance schema-design workstream order.** This workstream opens immediately. It does not pause to gate on Planning Item 001 in the Cleveland Business Mentors engagement (the paper test's sub-domain hierarchy amendment) or on the multi-tenancy routing fix slices in flight. Those are parallel concerns. The Cleveland Business Mentors redo Phase 1 conversation waits on its Planning Item 001 regardless; the governance workstream operates against the CRMBuilder dogfood engagement and does not touch other engagements' content.

---

## Workstream Composition

Six per-entity schema-design conversations, in this order:

| Order | Entity | Why this position |
|---|---|---|
| 1 | workstream | Most independent — references nothing else in the new set. |
| 2 | conversation | References workstream. |
| 3 | reference book | Independent record, but conversations link to it; designed after conversation so references can be specified. |
| 4 | work ticket | References conversation as its consumer. |
| 5 | close-out payload | Produced by a specific conversation; references conversation. |
| 6 | deposit event | References close-out payload and the records the deposit wrote. |

Each conversation produces one schema specification at `PRDs/product/crmbuilder-v2/governance-schema-specs/{entity_name}.md`, following the template in `governance-entity-schema-spec-guide.md`.

After all six schema specifications are complete, a build-planning conversation consumes them and produces the integrating Product Requirements Document, implementation plan, and per-slice execution prompts. That build-planning conversation's kickoff prompt is drafted at the close of the sixth per-entity schema-design conversation, not by this workstream-establishing conversation.

---

## Read This First

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. The session record from the predecessor scoping conversation — the most recent session at the time of this conversation's open, expected to be Session 046 if the predecessor closed out at that number.
3. The six decision records formalized at the predecessor's close (Decisions 117 through 122, expected numbering).
4. `PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md` — workstream master plan from the methodology entity schema-design workstream. Closest model for the master plan this conversation produces.
5. `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — methodology guide for the methodology workstream. Closest model for the governance methodology guide this conversation produces.
6. `PRDs/product/crmbuilder-v2/schema-design-kickoff-domain.md` — first of the four completed kickoff prompts from the methodology workstream, as the canonical model for per-entity kickoff prompts.
7. The session record for Session 011 — the workstream-establishing planning conversation for the methodology workstream. Closest model for this conversation's shape, pace, and deliverable cadence.
8. `PRDs/product/crmbuilder-v2/methodology-schemas-cbm-paper-test-findings.md` — recent context. The paper test's blocking finding (sub-domain hierarchy on domain) is a separate parallel workstream; the governance workstream is independent.
9. `PRDs/product/crmbuilder-v2/multi-engagement-architecture.md` — engagement-isolation architecture. Governance entities are per-engagement; this workstream's first records land in the CRMBuilder dogfood engagement.

---

## Architectural Disciplines to Apply

These have evolved since the methodology workstream completed; each per-entity schema-design conversation must apply them in its outputs.

- **Reference relationship vocabulary discipline.** New relationship kinds must be added to `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` (`REFERENCE_RELATIONSHIPS` set and `_kinds_for_pair` source-target constraint mapping), and require an Alembic migration on the `refs.relationship_kind` CHECK constraint. Per-entity schema specs name the vocabulary additions they require; the build-planning conversation aggregates them.
- **API envelope discipline.** Any new apply script or API-touching code must unwrap the `{data, meta, errors}` envelope before reading payload. Canonical pattern at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-025.md`.
- **Client-side identifier computation.** Prefixed-identifier entity types (Workstream NNN, Conversation NNN, Reference Book NNN, Work Ticket NNN, Close-Out Payload NNN, Deposit Event NNN) compute their identifier client-side from a `compute_next_identifier(client.list_<entity>())` style helper. Schema specs must declare the prefix and identifier format explicitly.
- **Per-engagement isolation.** New entity types live in the per-engagement SQLite file. The dogfood (`CRMBUILDER`) database is where this workstream's first records land. Other engagements receive the new entity types as part of their initialization once the schema is built.

---

## Pre-Flight Checks

Before the first architectural question:

1. `curl -sf http://127.0.0.1:8765/health` — V2 storage API up.
2. `uv run pytest tests/crmbuilder_v2/ -v` — V2 test suite green.
3. `git pull --rebase origin main` — clone current.
4. Read items 1 through 9 in "Read This First" above.

---

## Governance at Conversation Close

Per Decision 013 (sessions append-only), one Claude.ai conversation produces one session record. This conversation's session record is written at the actual close, by Doug, through the V2 desktop New Session dialog or via the standard close-out apply script.

Record contents follow the Session 011 pattern:

- `identifier`: next available session identifier at conversation close.
- `conversation_reference`: descriptive text identifying the conversation by its deliverables. Example: `"Claude.ai workstream-establishing planning conversation for the governance entity schema-design workstream. Produced the workstream master plan, the schema-spec methodology guide, and six per-entity schema-design kickoff prompts; formalized the six incoming principles from the predecessor scoping conversation as Decisions 117 through 122. No transcript preserved per Decision 025."`
- `topics_covered`: opens with the verbatim seed prompt from this kickoff file, followed by the structured summary of decisions reached.
- `artifacts_produced`: the workstream master plan, the methodology guide, the six kickoff prompt paths, the six new decisions, and any planning items authored.
- `in_flight_at_end`: `"Next workstream conversation: workstream schema design. Kickoff at schema-design-kickoff-workstream.md."`

---

## What This Conversation Does NOT Do

- Build any code.
- Design any schema. The six per-entity schema-design conversations do that work, one entity each.
- Modify V2's storage architecture. Schema modification happens in the per-entity schema-design conversations.
- Plan or schedule anything beyond this workstream.
- Resolve the nested-workstream question (whether a workstream can contain a sub-workstream). Deferred to the workstream entity's own schema-design conversation.
- Resolve the retroactive-migration question (whether to backfill governance entity records for sessions, decisions, and prior workstreams already in the database). Deferred to a planning item authored by this conversation.
- Touch the methodology entities (domain, entity, process, candidate Customer Relationship Management product, engagement) shipped in user-interface versions 0.4 and 0.5. Those remain unchanged.
- Touch the in-flight multi-tenancy routing fix work (Sessions 044 and 045 plus remaining slices). Parallel work; no overlap with the governance entity scope.
- Open the Cleveland Business Mentors redo Phase 1 conversation. That waits on the paper-test-flagged sub-domain hierarchy amendment (Planning Item 001 in the Cleveland Business Mentors engagement).

---

End of kickoff prompt.
