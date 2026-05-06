# CLAUDE-CODE-PROMPT-v2-A-bootstrap

## Purpose

Bootstrap **CRMBuilder v2** by creating the v2 home directory, populating it with the four initial governance artifacts (charter, decisions, sessions, status) produced during the initial planning conversation, updating the top-level `CLAUDE.md` to route new sessions to v2 when v2 work is engaged, and committing all of it under the `v2:` commit prefix.

## Project context

CRMBuilder v2 is the next major iteration of CRMBuilder. It rebuilds the methodology's foundation by making a structured database the source of truth for all CRM implementation artifacts (personas, entities, fields, processes, requirements, decisions, manual-config items, test specifications, cross-references), with Word documents, deployment YAML, and test cases generated as renders of that source rather than authored separately. CBM is the test case validating progress.

The initial planning conversation resolved planning dimensions 1, 2.1, 2.3, 2.4, 3, and 4. Dimensions 5–8 (pacing, division of labor, risk register, exit criteria) remain. Step 0 (schema design) has not yet started.

This prompt is the first concrete execution step — it lands the planning work as durable artifacts in the repo.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. If there are uncommitted changes, stop and report to Doug before proceeding.
3. Confirm git identity is set: `git config user.email` and `git config user.name`. If not set, configure with `dbower44022@users.noreply.github.com` and `Doug Bower`.
4. Pull latest from origin: `git pull --rebase origin main`.

## Tasks

### Task 1 — Create directory structure

```bash
mkdir -p PRDs/product/crmbuilder-v2/prompts
```

### Task 2 — Create `PRDs/product/crmbuilder-v2/charter.md`

Replace `HH:MM` with the current time in 24-hour format (e.g., `14:30`).

```markdown
# CRMBuilder v2 Charter

**Version:** 0.1 (draft)
**Last Updated:** 05-06-26 HH:MM
**Status:** In planning — pre-build

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-06-26 | Initial draft from planning conversation. Captures scope, name, architectural foundations, session orientation protocol, and remaining planning dimensions. |

## Scope

CRMBuilder v2 is the next major iteration of CRMBuilder. It rebuilds the methodology's foundation by making a structured database the source of truth for all CRM implementation artifacts — personas, entities, fields, processes, process steps, requirements, decisions, manual-config items, test specifications, and cross-references — with Word documents, deployment YAML, and test cases all generated as renders of that source rather than authored separately. It evolves the authoring loop, the storage layer, and the parts of the application that read or write methodology data, on the basis of lessons learned during the CBM pilot.

CBM is the test case that validates progress at each step, not a parallel client commitment that constrains the work. The new system's correctness is demonstrated by its ability to absorb CBM's existing PRD content and produce equivalent or improved deployment, authoring, and verification outcomes.

## In Scope

The following are in scope for CRMBuilder v2:

- **Schema design.** Designing the structured data model for both project management artifacts (decisions, sessions, statuses, topics, references) and methodology artifacts (personas, entities, fields, processes, requirements, etc.).
- **Storage and rendering implementation.** Building the SQLite + Python access layer + REST API + MCP server stack, plus the renderers that produce Word documents, deployment YAML, and test cases from the database.
- **Authoring evolution.** Moving from Word-document authoring sessions to structured database authoring through Claude.ai and MCP tool calls. Includes evolving the methodology's interview guides and prompt templates accordingly.
- **Application changes to support the new model.** Modifying the existing crmbuilder PySide6 desktop application to read and write the v2 database directly, rather than importing Word documents into a per-client store.
- **Migration of CBM into the new model.** Porting CBM's existing PRD content into the v2 database one domain at a time, in priority order: MN first as the proving ground, then MR, then CR, then FU.
- **Test infrastructure.** Building the layered functional testing system (CRUD → integration → process/persona → UI) that exercises deployed CRMs against database-stored requirements, with structured feedback to Claude Code for iterative remediation.

## Out of Scope

The following are explicitly out of scope, and continue or proceed as separate workstreams:

- **Incremental fixes to the existing v1 deployment engine.** Continue under the existing crmbuilder roadmap. v2 does not replace the engine itself; it replaces the storage and authoring foundation that feeds it.
- **Engine pluggability work for additional CRM backends.** The Attio and HubSpot deployment series proceed independently. v2 makes engine pluggability cleaner over time (renders for different engines come from the same source), but the pluggability work itself is a separate stream.
- **New client onboardings before the migration is sufficiently complete.** No new clients onboarded through CRMBuilder until v2 can support them. CBM completes its migration before any second client is considered.

## Architectural Foundations

These are the design principles that underpin the v2 system. Each is captured in detail with rationale, alternatives considered, and consequences in the companion decisions document (see `decisions.md`).

**Database as source of truth.** All v2 artifacts — both project management artifacts (decisions, sessions, statuses) and methodology artifacts (personas, entities, fields, processes, requirements) — live in a single structured database. Word documents, deployment YAML, and test cases are renders of that database, not independently authored. This eliminates the drift cost paid today, where the same field is referenced from multiple Word documents and any change requires manual reconciliation.

**Storage stack.** The data layer is SQLite (file-based, no server required, ACID transactions). Above it sits a Python access layer that handles validation, transactions, and JSON exports for git diffability. Above that sits a REST API (FastAPI) that exposes the database over HTTP, providing a stable interface for any client. An MCP server adapts the REST API for Claude.ai tool calls, allowing AI sessions to read and write the database in real time. The same architecture migrates to PostgreSQL when productization needs multi-user remote access; the protocol stays the same.

**Universal references pattern.** Cross-references between any two records — a decision about a topic, a session covering a requirement, a process step touching a field — are stored in a single `references` table with `source_type`, `source_id`, `target_type`, `target_id`, and a controlled-vocabulary `relationship` field. This scales linearly with the number of entity types instead of quadratically, makes "give me everything related to X" a uniform query regardless of what X is, and provides the foundation for change-impact analysis.

**Topics as a generic concern type.** A `topics` table stores free-floating subjects that aren't typed entities (architectural concepts, design discussions, planning topics). Methodology entities are first-class typed records and don't live in topics; both can be referenced through the same `references` table.

**Renders, not authored copies.** Word documents for stakeholder review, YAML programs for deployment, test cases for verification — all are generated from the database on demand. Authoring flows update the database; rendered artifacts are derivative and disposable.

**CBM as test case.** Cleveland Business Mentoring is the first client whose existing PRD content migrates into v2. Migration validates that the schema can absorb real implementation content. Migration order is priority-driven: MN first, then MR, then CR, then FU.

**v1/v2 boundary tracking.** Directory separation (v2 artifacts under `PRDs/product/crmbuilder-v2/`), file naming conventions, commit message scope tag (`v2:`), and a living status document maintain a clear distinction between v2 work and the existing v1 codebase and methodology.

**Session orientation protocol.** Every Claude.ai session that engages v2 follows a tiered orientation: Tier 1 reads `CLAUDE.md`, Tier 2 queries CHARTER, STATUS, recent sessions, and relevant decisions via MCP, Tier 3 issues on-demand queries during conversation. Bounded context cost, predictable session start.

## Current State

**Phase:** Planning (pre-build).

Planning dimensions completed:

- #1 (project identity) — resolved
- #2.1 (session orientation protocol) — resolved
- #2.2 (CLAUDE.md update) — design resolved; mechanical implementation pending
- #2.3 (handoff conventions) — substantially resolved by sessions table + references; full design happens in schema work
- #2.4 (capture of working ideas) — substantially resolved by topics + references
- #3 (decision management) — substantially resolved by decisions table + references
- #4 (CBM coexistence) — collapsed (CBM is the test case, not a parallel commitment)

Planning dimensions remaining:

- #5 (pacing, cadence, milestones)
- #6 (division of labor)
- #7 (risk register)
- #8 (exit criteria)

**Active work:** Drafting this charter and the companion decisions document as the first durable artifacts of the project. Architectural decisions are being numbered retroactively as DEC-001 through DEC-N.

**Not yet started:** Step 0 (schema design), implementation of any v2 code, creation of the v2 home directory in the repo, CLAUDE.md update, MCP server build.

## Open Planning Items

The following planning dimensions remain to be resolved before Step 0 (schema design) begins:

**#5 — Pacing, cadence, and milestones.** What does a working session on this project look like? Cadence weekly, ad-hoc, or time-blocked against ongoing CBM work? What does "done" mean for each phase and sub-step? What are the gates that determine whether to proceed forward, iterate within the current step, or stop and reassess?

**#6 — Division of labor.** Where are the boundaries between Claude.ai work (design, drafting, schema iteration), Claude Code work (implementation, file edits, repo changes), and Doug-only work (methodology decisions, stakeholder coordination, final approval, validation review)? What's the handoff protocol between modes?

**#7 — Risk register.** What can fail and what's the response? Schema design taking longer than budgeted, the schema being wrong only after a domain is migrated, application UI work being substantially larger than scoped, the existing methodology continuing to accrue Word-doc artifacts faster than the new system can absorb them.

**#8 — Exit criteria.** Success criterion that lets us commit from Step 0 (schema design) to Step 1 (storage layer build). Abort criterion that says "this isn't viable, fall back to the existing model." Per-phase gates at each subsequent boundary.

Once these are resolved, the next major workstream is **Step 0 — Schema Design**, itself a multi-session design effort covering the project management schema, the methodology schema (entities, fields, personas, processes, requirements, decisions, manual-config items, test specifications), the references vocabulary, and validation rules.
```

### Task 3 — Create `PRDs/product/crmbuilder-v2/decisions.md`

Replace `HH:MM` with the current time.

```markdown
# CRMBuilder v2 — Decisions Log

**Last Updated:** 05-06-26 HH:MM
**Status:** Active

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-06-26 | Initial decisions log capturing architectural decisions DEC-001 through DEC-011 from the planning conversation. |

## Index

- DEC-001: CRMBuilder v2 framed as next iteration, not separate initiative
- DEC-002: Project identity — name, home, character
- DEC-003: v1/v2 boundary tracking mechanisms
- DEC-004: Database as source of truth for all v2 artifacts
- DEC-005: Storage stack — SQLite + access layer + REST API + MCP server
- DEC-006: Universal references pattern with controlled relationship vocabulary
- DEC-007: Topics table for free-floating concepts
- DEC-008: Renders, not authored copies
- DEC-009: CBM as test case, not parallel commitment
- DEC-010: CBM migration order — MN, then MR, then CR, then FU
- DEC-011: Session orientation protocol — tiered

---

### DEC-001: CRMBuilder v2 framed as next iteration, not separate initiative

**Date:** 05-06-26
**Status:** Active

**Context:** The methodology rearchitecture project had open framing — separate strategic initiative parallel to CRMBuilder, or evolution of CRMBuilder itself.

**Decision:** Frame the project as the next major iteration of CRMBuilder, building on the existing roadmap and lessons learned from the CBM pilot, not as a separate initiative.

**Rationale:** CRMBuilder's original design was already pointing at a database-as-source-of-truth model (per-client SQLite, Path B import pipeline, Requirements tab fed from the database). The work being undertaken closes that loop rather than introducing a new direction. Framing it as evolution preserves continuity, avoids duplicate stakeholder/management overhead, and sets the right expectation that CBM is downstream of the new system rather than parallel to it.

**Alternatives considered:**
- Separate strategic initiative running parallel to CRMBuilder. Rejected — would create a CBM coexistence problem and fragment the product roadmap.

**Consequences:** v2 work governed under the existing crmbuilder repo and CLAUDE.md. CBM does not constrain v2's pace; v2 drives CBM's eventual full re-run.

---

### DEC-002: Project identity — name, home, character

**Date:** 05-06-26
**Status:** Active

**Context:** Project needs operational identity (name, file location, scope tag) so that artifacts, commits, and references are unambiguous across many sessions and many months.

**Decision:** Name is "CRMBuilder v2" with short tag `v2`. Home is `PRDs/product/crmbuilder-v2/` in the crmbuilder repo. Character is product initiative (lives under PRDs/product/, not PRDs/process/).

**Rationale:** "v2" cleanly signals the next major iteration without implying parallel v1/v2 maintenance. Home under PRDs/product/ matches existing CRMBuilder product specs (CRMBuilder-PRD.md, app-*.md, crmbuilder-automation-PRD/). Methodology guide changes are downstream consequences of v2 and happen in PRDs/process/ as separate work referenced from v2.

**Alternatives considered:**
- Names: "CRMBuilder Foundation" (rejected — slightly grand-sounding), "CRMBuilder Core" (rejected — less distinctive than alternatives).
- Character: process initiative under PRDs/process/. Rejected — v2 rebuilds product foundations; methodology evolution is the downstream effect, not the project itself.

**Consequences:** All v2 artifacts under `PRDs/product/crmbuilder-v2/`. Commit messages prefix with `v2:`. CLAUDE.md updated to point to v2's home and orientation protocol.

---

### DEC-003: v1/v2 boundary tracking mechanisms

**Date:** 05-06-26
**Status:** Active

**Context:** v2 will run alongside v1 for an extended period. Without clear boundary tracking, the two will become entangled in the filesystem, git history, conversations, and code, making it hard to identify which artifacts belong to which generation.

**Decision:** Hybrid tracking with directory separation as the primary mechanism, anchored by a status / inventory document and reinforced by file naming, commit message scope tags (`v2:`), CLAUDE.md updates, and (later) code module separation.

**Rationale:** Single-mechanism approaches are insufficient because confusion can creep in through any layer. The status document provides a navigation anchor that scales as the project advances through phases; directory and naming conventions stay stable while content evolves; CLAUDE.md is the entry point that routes new sessions correctly.

**Alternatives considered:**
- Branch separation (v2 development on a separate git branch). Rejected — adds friction for single-developer workflow and doesn't help track artifacts within a single tree.
- Naming convention only, no directory separation. Rejected — boundary not visible at the tree level.

**Consequences:** v2 home directory required before any v2 work commits. Status document is one of the first artifacts authored. CLAUDE.md gets a v2 routing section.

---

### DEC-004: Database as source of truth for all v2 artifacts

**Date:** 05-06-26
**Status:** Active

**Context:** The methodology currently treats Word documents as authoritative source for personas, entities, fields, processes, requirements, and so on, with the per-client SQLite database as a derivative populated by import. The result is multi-document drift, manual reconciliation cost (e.g., the recent four-session MN reconciliation workpacket), and absence of a query layer that could detect cross-document conflicts before deployment.

**Decision:** Invert the relationship. A structured database is the source of truth for all v2 artifacts — both methodology artifacts (personas, entities, fields, processes, requirements, decisions, manual-config items, test specifications, cross-references) and project management artifacts (charter, decisions, sessions, status, topics). Word documents, deployment YAML, and test cases become renders generated from the database, not authored separately.

**Rationale:** Eliminates drift by construction. Queries become possible. Identifier governance becomes automatic. The Word-to-database import problem disappears. Project management artifacts go into the database too — dogfooding the philosophy from day one rather than asking the methodology to do something v2 itself doesn't do.

**Alternatives considered:**
- Word as source, structured shadow database. Rejected — preserves drift cost; never converges to clean inversion in single-person efforts.
- Markdown with structured frontmatter, no database. Rejected — diff-friendly but lacks the query and validation guarantees of a real database.

**Consequences:** Schema design (Step 0) becomes the foundational design effort. The application's existing Word-to-database import pipeline (Path B) becomes obsolete. Stakeholder reviewers see Word renders, never edit Word directly.

---

### DEC-005: Storage stack — SQLite + access layer + REST API + MCP server

**Date:** 05-06-26
**Status:** Active

**Context:** With database as source of truth (DEC-004), the storage stack needs to support concurrent access from AI sessions (Claude.ai), the existing crmbuilder PySide6 application, scripts, and eventually remote multi-user clients in productized form.

**Decision:** Layered architecture. SQLite at the bottom (file-based, ACID transactions, no server). Python access layer with validation, transactions, and JSON exports for git diffability. REST API (FastAPI) over the access layer for stable client interface. MCP server as a thin adapter that translates Claude.ai tool calls into REST API calls. JSON exports written transactionally on every database write.

**Rationale:** REST API is the durable productization-path interface — when productized, it becomes the hosted endpoint with authentication added. MCP is the Claude.ai bridge, swappable without affecting the rest of the stack. SQLite is already used by crmbuilder for per-client data, so no new technology stack. Migration to PostgreSQL is straightforward when multi-user remote becomes a requirement.

**Alternatives considered:**
- YAML files in git, no database. Rejected — files-with-extra-steps; doesn't support concurrent access, queries, or multi-actor consistency.
- MCP-direct (MCP server talks to SQLite, no REST API). Rejected — skips the durable interface layer; would need to be added later for productization or other clients.
- SQLite hosted on a server with cloud database from day one. Rejected — over-engineered for current single-user state; introduces hosting dependency before it's needed.
- Sync script applying end-of-session delta blocks to a passive database. Rejected — operationally worse than markdown, makes the database a glorified file format requiring batch synchronization.

**Consequences:** Initial build effort is roughly four pieces (schema, access layer, REST API, MCP wrapper, plus JSON export hook). REST API testable independently via curl. MCP wrapper small (~100 lines). All pieces required before v2 storage is operational.

---

### DEC-006: Universal references pattern with controlled relationship vocabulary

**Date:** 05-06-26
**Status:** Active

**Context:** The schema needs to support cross-references between any two records (decision about a topic, session covering a requirement, process step touching a field). Modeling these as separate junction tables per type pair scales O(n²) and produces fragmented queries.

**Decision:** Single `references` table with columns `source_type`, `source_id`, `target_type`, `target_id`, `relationship`, `created_at`. The `relationship` field uses a controlled vocabulary (enumerated values like `is_about`, `supersedes`, `blocks`, `decided_in`, `affects`, `covers`) that grows deliberately as new entity types are added.

**Rationale:** Schema scales linearly with entity types instead of quadratically. Cross-cutting query "give me everything related to X" is uniform regardless of what X is. Bidirectional traversal is a single query. Relationship semantics preserved through the controlled vocabulary. Same mechanism handles the project-management graph and the methodology graph.

**Alternatives considered:**
- Explicit junction tables per type pair (`decisions_to_topics`, `sessions_to_requirements`, etc.). Rejected — quadratic table proliferation, fragmented queries, every new entity type adds N junctions.
- Free-text relationship strings. Rejected — synonyms ("is_about" vs "concerns" vs "regards") fragment query results; controlled vocabulary required regardless.

**Consequences:** The `references` table is foundational and built into the project-management schema from day one. The relationship vocabulary becomes its own design artifact, growing deliberately. Polymorphic indexes on (source_type, source_id) and (target_type, target_id) required for query performance.

---

### DEC-007: Topics table for free-floating concepts

**Date:** 05-06-26
**Status:** Active

**Context:** Some things being referenced are not typed entities but free-floating concepts (architectural ideas, design discussions, planning topics) that don't fit any existing entity type and need a home in the schema.

**Decision:** Lightweight `topics` table with columns `id`, `name`, `description`, `parent_topic_id` (for hierarchy), `created_at`. Topics are referenced through the same `references` table (DEC-006) that all other entities use. Methodology entities (requirements, fields, personas) do NOT live in the topics table — they remain first-class typed records.

**Rationale:** Free-floating concepts need a home. A separate topics table keeps them distinct from typed methodology entities, which have their own schemas. Hierarchy support handles natural nested topics ("schema design > references table > relationship vocabulary"). Polymorphic references mean "everything related to topic X" and "everything related to requirement Y" use the same query shape.

**Alternatives considered:**
- No topics table; force everything into typed entities. Rejected — free-floating concepts have no natural home in entity schemas.
- Topics as a generic record that everything (including methodology entities) inherits from. Rejected — adds inheritance complexity without clear benefit.

**Consequences:** Topics expected to be heavily used during the design phase before methodology entities exist. Topic governance (preventing duplicate names, enforcing hierarchy) is part of the access layer.

---

### DEC-008: Renders, not authored copies

**Date:** 05-06-26
**Status:** Active

**Context:** Stakeholder review requires Word documents. Deployment requires YAML. Verification requires test cases. Each is currently authored as a separate artifact, which creates drift between artifacts that should agree.

**Decision:** Word documents, deployment YAML, and test cases are all renders generated from the v2 database on demand. None of them is independently authored. Authoring flows update the database; rendered artifacts are derivative and disposable.

**Rationale:** Eliminates drift between PRDs and YAML. Stakeholder reviews always see content matching what will be deployed. Deployment YAML always matches the requirements it implements. Test cases always exercise current requirements. One source, multiple renders.

**Alternatives considered:**
- Authored Word documents with structured shadow database for queries. Rejected — preserves drift cost; requires manual reconciliation discipline.
- Authored YAML and Word, with database as derivative. Rejected — same drift problem, just shifted to a different pair of artifacts.

**Consequences:** Renderers needed for each output format (Word, YAML, test cases). Stakeholder feedback on rendered Word docs feeds back into database changes via the authoring loop, never by editing Word directly.

---

### DEC-009: CBM as test case, not parallel commitment

**Date:** 05-06-26
**Status:** Active

**Context:** CBM is the active client implementation with substantial existing PRD content and ongoing work. Open question: does v2 work run in parallel to CBM (with CBM constraining the pace), or is CBM downstream of v2?

**Decision:** CBM is the test case that validates v2 progress at each step, not a parallel client commitment that constrains v2's work. CBM proceeds at the pace v2 is ready to absorb it.

**Rationale:** CBM is Doug's pilot, not an external client commitment with deadlines. The methodology rearchitecture is the higher-leverage effort, and CBM's eventual full re-run becomes the natural moment when the new system absorbs CBM. Forcing v2 to run parallel to ongoing CBM work would split focus and slow both.

**Alternatives considered:**
- CBM continues in old model in parallel; v2 builds independently. Rejected — splits focus, accumulates more legacy in v1, no forcing function for v2 to actually be used.
- v2 work paused until CBM is fully complete in v1 model. Rejected — never gets to v2 because CBM is iterative and "complete" recedes.

**Consequences:** No new CBM forward work in the v1 Word-doc model after the v2 transition begins. CR and FU domains (incomplete in CBM) wait for v2 to be ready. The recently-completed MN reconciliation and ongoing CR work are likely the last v1-model CBM artifacts.

---

### DEC-010: CBM migration order — MN, then MR, then CR, then FU

**Date:** 05-06-26
**Status:** Active

**Context:** When CBM migrates into v2, the question is which domain goes first.

**Decision:** Priority-driven order: MN first as the proving ground, then MR (high-priority business functionality also already complete in Word), then CR, then FU. Not queue-driven — the next domain to migrate is determined by priority, not by which was next in the original CBM work queue.

**Rationale:** MN was just reconciled to v1.1 (05-05-26) and has fresh content for validation. MR is high-priority business functionality already complete in Word, providing a second clean validation target. CR and FU come after because they're either incomplete (CR partial, FU not started) or lower priority for delivery.

**Alternatives considered:**
- Queue-driven order (work on whatever was next in the CBM v1 queue). Rejected — would prioritize CR-OUTREACH or FU work over higher-priority MR migration.
- All domains in parallel. Rejected — too much surface area to validate at once; better to prove with one domain at a time.

**Consequences:** No CBM CR or FU work happens in v1 model after v2 migration starts. CR's OUTREACH process doc and CR Reconciliation are deferred. FU work is deferred entirely.

---

### DEC-011: Session orientation protocol — tiered

**Date:** 05-06-26
**Status:** Active

**Context:** Every Claude.ai session that engages v2 work needs to establish context efficiently. Insufficient orientation produces stale assumptions; excessive orientation eats context budget that could go to actual work.

**Decision:** Three-tier protocol. Tier 1 (universal, every session): read `crmbuilder/CLAUDE.md`. Tier 2 (when v2 is engaged): query CHARTER, STATUS, recent 3 sessions, and decisions referenced by recent sessions, via MCP. Tier 3 (on-demand during conversation): targeted queries as topics arise.

**Rationale:** Tiered structure bounds the context cost of session start (1-2K tokens for Tier 2 when MCP is online) while keeping orientation predictable and reliable. CLAUDE.md is the universal entry; MCP queries are the v2-specific orientation layer; on-demand queries handle deeper investigation as needed.

**Alternatives considered:**
- Read-everything at session start. Rejected — too expensive in context budget.
- Lazy / on-demand only (read CLAUDE.md, query DB only when explicitly needed). Rejected — risks proceeding without enough context, produces stale assumptions.

**Consequences:** CLAUDE.md update required to document the protocol. Sessions table schema must support "what was in flight at end of session" so the next session resumes cleanly. Bootstrap window before MCP exists requires fallback to reading the v2 directory listing and most recent session transcript.
```

### Task 4 — Create `PRDs/product/crmbuilder-v2/sessions.md`

Replace `HH:MM` with the current time.

```markdown
# CRMBuilder v2 — Session Records

**Last Updated:** 05-06-26 HH:MM
**Status:** Active

**Revision Control:** This document is an append-only log. Each new SES-NNN entry constitutes a revision; the "Last Updated" field above reflects the most recent addition.

---

## SES-001: Initial Planning — Project Identity, Architecture, and Initial Artifacts

**Date:** 05-06-26
**Status:** Complete
**Conversation reference:** Claude.ai session (transcript preserved separately if needed)

**Topics covered:** v2 project identity, methodology rearchitecture rationale, storage architecture (SQLite + REST API + MCP server), universal references pattern, topics table, session orientation protocol, charter structure, decisions log structure, CBM as test case

**Summary:**

Started as a request to create a functional testing routine for CRM Builder YAML processing. Through iterative reframing during the conversation, the scope evolved into a substantially larger architectural redesign — a structured database as source of truth for all CRM implementation artifacts (methodology and project management both), with Word documents, deployment YAML, and test cases as renders.

Key reframes during the conversation, in order:

- Testing system → behavior-driven testing → cross-cutting persona/process testing → end-to-end PRD-to-deployed-CRM verification with feedback loop to Claude Code
- Word documents as source → structured database as source
- Project artifacts as markdown documents → project artifacts as database records (dogfooding)
- YAML files in git → SQLite + REST API + MCP server (real database)
- MCP-direct → layered (REST API as durable interface, MCP as Claude.ai bridge)
- Topics as one of many junction tables → universal references pattern with controlled relationship vocabulary

Working through the eight planning dimensions:

- Resolved #1 (project identity) including all sub-questions A–F
- Resolved #2.1 (session orientation protocol)
- Substantially resolved #2.3, #2.4, #3 by virtue of the database architecture
- Collapsed #4 (CBM coexistence) — CBM is the test case, not parallel commitment
- Did not address #5–#8 (deferred to future conversations)

**Decisions made:** DEC-001 through DEC-011 (see `decisions.md`)

**Artifacts produced:**

- `charter.md` (draft v0.1)
- `decisions.md` (draft v0.1, capturing DEC-001 through DEC-011)
- `sessions.md` (this record)
- `status.md` (draft v0.1)

**In-flight at session end:**

- All four governance artifacts drafted and committed via the v2-A bootstrap prompt
- v2 home directory `PRDs/product/crmbuilder-v2/` created
- CLAUDE.md updated with v2 routing section
- Planning dimensions #5–#8 unresolved
- Step 0 (schema design) not started

**Next step:**

In a new conversation, continue with planning dimension #5 (pacing, cadence, milestones). Subsequent conversations cover #6, #7, #8. After all eight planning dimensions are resolved, Step 0 (schema design) begins.
```

### Task 5 — Create `PRDs/product/crmbuilder-v2/status.md`

Replace `HH:MM` with the current time.

```markdown
# CRMBuilder v2 — Status

**Last Updated:** 05-06-26 HH:MM
**Status:** Active

**Revision Control:** This document is a living status snapshot updated as project state changes. The "Last Updated" field above reflects the most recent revision; prior states are recoverable through git history.

---

## Current Phase

**Phase:** Planning (pre-build)

**Sub-step:** Initial planning conversation complete and bootstrap committed. Planning dimensions 1, 2.1, 2.3, 2.4, 3, and 4 resolved (some explicitly, some by virtue of the database architecture). Dimensions 5–8 remain. Step 0 (schema design) has not yet started.

---

## v1 / v2 / Transition Inventory

### What's in v2

- `charter.md` v0.1 — scope, name, architectural foundations, current state, open planning items
- `decisions.md` v0.1 — DEC-001 through DEC-011, architectural decisions from initial planning
- `sessions.md` v0.1 — SES-001, the initial planning conversation record
- `status.md` v0.1 — this document
- `prompts/CLAUDE-CODE-PROMPT-v2-A-bootstrap.md` — the prompt that produced this initial state

### What's in v1 (unchanged)

The following remain in v1 form and are explicitly NOT part of v2 work:

- The crmbuilder PySide6 desktop application code (`espo_impl/`, `automation/`)
- The existing methodology guides (`PRDs/process/interviews/`, `PRDs/process/CRM-Builder-Document-Production-Process.docx`)
- The existing app-level product specs (`PRDs/product/CRMBuilder-PRD.md`, `PRDs/product/app-*.md`)
- The engine pluggability planning (`PRDs/product/crmbuilder-automation-PRD/engine-pluggability-planning.md`)
- The CBM client repo and all its content (`ClevelandBusinessMentoring/PRDs/`, `ClevelandBusinessMentoring/programs/`)

### What's in transition

None at this stage. v2 has not yet begun migrating any v1 artifacts.

---

## Active Work

None currently active. The bootstrap commit lands the planning work as durable artifacts; the next active work begins in the next conversation when planning dimension #5 (pacing) is taken up.

---

## Pending — Immediate

None. The bootstrap is complete after this prompt executes.

## Pending — Planning

- Planning dimension #5 — pacing, cadence, milestones
- Planning dimension #6 — division of labor
- Planning dimension #7 — risk register
- Planning dimension #8 — exit criteria

## Pending — Build (gated by planning completion)

- Step 0 — schema design (project management schema first, methodology schema second; references vocabulary; validation rules)
- Step 1 — storage layer build (SQLite, Python access layer, REST API, MCP server, JSON export hook)
- Step 2 — MN domain migration as proving ground
- Step 3 — test infrastructure first deliverable (CRUD layer)
- Subsequent: MR, CR, FU migration; integration / process / UI test layers; methodology guide evolution; application UI changes

---

## Blockers

None at this stage. The architecture is defined sufficiently for the next planning conversation to proceed; no external dependencies block forward motion.

---

## Reading Order for New Sessions

Per DEC-011 (session orientation protocol):

**Tier 1:** `crmbuilder/CLAUDE.md`

**Tier 2 (when v2 work is engaged, before the MCP server exists):**

1. `status.md` — current state (this file)
2. `charter.md` — project scope and architectural foundations
3. `sessions.md` — most recent session(s), starting from the latest
4. `decisions.md` — referenced on demand when sessions reference DEC-NNN

**Tier 2 (once the MCP server exists):** Replace the file reads above with MCP queries (`get_status`, `get_charter`, `get_recent_sessions`, `get_decisions`).
```

### Task 6 — Save this prompt to `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-A-bootstrap.md`

Use `create_file` to write the complete contents of this prompt to `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-A-bootstrap.md`. The contents to write are everything from the H1 line `# CLAUDE-CODE-PROMPT-v2-A-bootstrap` through the end of this document, verbatim. Do not modify, abbreviate, or commentate the contents — they should match this prompt exactly so future sessions have an authoritative record of what produced the bootstrap state.

### Task 7 — Update `crmbuilder/CLAUDE.md` with v2 routing section

Use `str_replace` on `crmbuilder/CLAUDE.md` with the following exact anchors. Copy `old_str` and `new_str` verbatim, preserving blank lines exactly as shown.

**`old_str`** (these three lines, with one blank line between them):

```
the short-named clone now exists locally.

## Commands
```

**`new_str`** (the original line, the new v2 section, then the `## Commands` header):

```
the short-named clone now exists locally.

## CRMBuilder v2 — Methodology Rearchitecture

CRMBuilder v2 is the next major iteration of CRMBuilder, currently in planning phase. It rebuilds the methodology's foundation by making a structured database the source of truth for all CRM implementation artifacts (personas, entities, fields, processes, requirements, decisions, manual-config items, test specifications, cross-references). Word documents, deployment YAML, and test cases become renders generated from the database, not authored separately. CBM is the test case validating progress at each step.

**v2 home:** `PRDs/product/crmbuilder-v2/`

**Tracking:** Commits touching v2 work prefix the subject with `v2:`. Status, decisions, sessions, and charter live in the v2 home directory. v1 work (the existing application code, methodology guides, app-level product specs, engine pluggability planning, and the CBM client repo) continues unchanged under existing locations.

**Session orientation protocol** (per DEC-011 in `crmbuilder-v2/decisions.md`):

When a session engages v2 work — by the conversation referencing v2, or the user explicitly engaging it — Claude follows this tiered orientation:

- **Tier 1 (universal, every session):** Read this CLAUDE.md (already done by reading this section).
- **Tier 2 (v2 engagement, before MCP server exists):** Read `PRDs/product/crmbuilder-v2/status.md` (current state), `charter.md` (scope and foundations), most recent entries in `sessions.md` (recent context), then `decisions.md` records as referenced.
- **Tier 3 (on-demand):** Targeted queries during conversation as topics arise.

Once the MCP server exists (Step 1 deliverable, not yet built), Tier 2 file reads become MCP tool calls (`get_status`, `get_charter`, `get_recent_sessions`, `get_decisions`).

v1 work continues normally — the deployment engine, methodology guides, and existing app code are not part of v2 and are maintained under their existing locations.

## Commands
```

If `str_replace` fails (the anchor text is not found, or matches more than once), stop and report — do not attempt a fallback insertion or guess at the intended location.

### Task 8 — Commit

```bash
git add PRDs/product/crmbuilder-v2/ CLAUDE.md
git commit -m "v2: bootstrap — create governance artifacts (charter, decisions, sessions, status) and add CLAUDE.md routing section"
```

Do **not** push automatically. Doug will review and push manually after inspection.

## Validation

After completion, confirm:

- `PRDs/product/crmbuilder-v2/` exists with five files: `charter.md`, `decisions.md`, `sessions.md`, `status.md`, and `prompts/CLAUDE-CODE-PROMPT-v2-A-bootstrap.md`
- `crmbuilder/CLAUDE.md` has a new "CRMBuilder v2 — Methodology Rearchitecture" section between Project and Commands
- The commit message starts with `v2:` and is the most recent commit
- `git status` is clean (no untracked files or unstaged changes)
- `git log -1 --stat` shows exactly the expected files added/modified (4 governance files, 1 prompt file, 1 CLAUDE.md update)

## Reporting

Report back to Doug with:

- The full text of the commit message
- Output of `git log -1 --stat`
- Any anomalies encountered

## Notes

- This is the first commit of the v2 series. All future v2 commits use the `v2:` subject prefix.
- The four governance artifacts are at v0.1 draft. They will be updated as the project advances; the change logs in each file are append-only.
- The `HH:MM` placeholder in each artifact's "Last Updated" field must be replaced with the actual commit time.
- Future v2 Claude Code prompts will follow the naming pattern `CLAUDE-CODE-PROMPT-v2-{LETTER}-{DESCRIPTOR}.md` and live in `PRDs/product/crmbuilder-v2/prompts/`.
