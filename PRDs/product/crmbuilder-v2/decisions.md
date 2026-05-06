# CRMBuilder v2 — Decisions Log

**Last Updated:** 05-06-26 19:28
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
