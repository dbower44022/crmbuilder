# PI Cleanup Proposal — Phase A Review (revised method)

**Last Updated:** 05-25-26 13:00
**Scope:** all Open planning items in the CRMBUILDER engagement
**Total reviewed:** 37
**Recommended RESOLVE:** 4
**Recommended KEEP:** 27
**NEEDS-INPUT:** 6

**Method correction.** The first version of this proposal scanned PI description text for deferral keywords. That was wrong — PI descriptions are immutable scope statements written at PI-creation time, never updated when work lands. This revision verifies each PI against actual codebase / artifact state: file existence, ORM models, alembic migrations, vocab entries, methodology document sections, status-payload narrative, database snapshot record counts.

---

## Recommendations

| PI | Title | Recommendation | Evidence (artifact-based) |
|----|-------|----------------|---------------------------|
| PI-001 | Full styling design pass per DEC-024 | RESOLVE | `styling-design-pass.md` exists (50K, 05-18-26); six v0.6 slice prompts A-F + slice-A follow-up shipped; status v16 payload narrates "PI-001 is discharged at slice F" verbatim; SES-037..SES-043 closed-out. Status field never flipped — oversight. |
| PI-002 | Make `identifier` optional in POST bodies (SES-010 option C) | KEEP | `schemas.py` L29/59/74/96/116 — DecisionCreateIn / SessionCreateIn / RiskCreateIn / PlanningItemCreateIn / TopicCreateIn still require `identifier: str`. Only methodology entities (Domain/Entity/Process/Engagement) shipped the optional+server-assigned pattern. |
| PI-003 | Persona entity type for v0.5+ | KEEP | No `Persona` ORM class in `access/models.py`. `'persona'` not in `ENTITY_TYPES` (vocab.py L250-289). No `persona.md` in `methodology-schema-specs/`. |
| PI-004 | Additional methodology entity types: field, requirement, manual_config, test_spec | KEEP | None of these in ORM, vocab `ENTITY_TYPES`, or `methodology-schema-specs/`. Multiple specs explicitly defer them. |
| PI-005 | Process schema growth beyond Phase 1 thin shape | KEEP | `Process` model (models.py L355-423) still has only identifier/name/domain/purpose/classification/notes — no steps, actors, triggers, outcomes. `process.md` L97 explicitly defers `process_kind` and L105 defers entity-touches to PI-005. |
| PI-006 | Retrofit governance entities to parent-prefix field-naming convention | KEEP | Governance tables in models.py L114-251 still use bare names (`identifier`, `title`, `status`, etc.). No alembic rename across 12 migrations. Contrast methodology entities at L266+ which use parent-prefix. |
| PI-007 | `domain.short_code` field for mnemonic references | KEEP | `grep -rn short_code` returns zero hits. Domain table (models.py L266-283) has no short_code column. |
| PI-008 | Inbox folder watcher in v0.3 desktop app | KEEP | No inbox/watcher code under `ui/`. The `QFileSystemWatcher` at `ui/refresh.py:93` watches the db-export snapshot, not an inbox of close-out payloads. `apply_close_out.py` remains the pattern. |
| PI-009 | Master-pane Domains column on the Entities panel | KEEP | `ui/panels/entities.py:141-151` — `list_columns()` returns Identifier, Name, Status, Updated only. The file's own L18 docstring acknowledges: "Domains column ships in v0.4 (`entity.md` §3.6.2, PI-009)." |
| PI-010 | Entity-schema v0.5+ extensions — variants and base-type/kind | KEEP | Entity table (models.py L304-352) has no `entity_kind`, no `entity_parent_identifier`, no self-FK. No `entity_variant_of_entity` kind in `_kinds_for_pair`. No alembic migration extending entity. |
| PI-011 | Implementation-priority scalar field on process | KEEP | Process model (L376-400) has only `process_classification` (4-value enum) plus `process_classification_rationale`. No scalar priority field. |
| PI-012 | crm_candidate structured-metadata enums (vendor_url, hosting_type, license_type, price_tier) | KEEP | CrmCandidate (models.py L426-484) has only identifier/name/status/fit_reason/notes. None of the four enums. |
| PI-013 | Cross-Domain Service representation | KEEP | No `'cross_domain_service'` in `ENTITY_TYPES`. No ORM class. No `cross_domain_service.md` in methodology-schema-specs. |
| PI-014 | Catalog FK integration for methodology entities | KEEP | No `primary_catalog_entity_id` / `catalog_entity_id` / `catalog_id` on Domain, Entity, Process, or CrmCandidate. Zero references between methodology entities and catalog entities. Blocked by PI-004 (field entity) anyway. |
| PI-015 | Methodology entity renderers | KEEP | No `renderers/` subpackage. No `render_*.py` modules. No docx generator. No YAML generation driven from v2 DB. |
| PI-016 | Router-level per-pair vocabulary enforcement on `/references` | KEEP | `api/routers/references.py:58-61` POST handler does no per-pair check. `repositories/references.py:193-195` only validates entity-type and relationship-kind set membership, not RELATIONSHIP_RULES pairs. |
| PI-017 | Migrate API and MCP servers to multi-tenant model | KEEP | `api/deps.py:21-44` routes to a single env-var-pointed DB; no per-request engagement resolution. No `X-Engagement` header parsing. No `/v1/engagements/{id}/...` path-prefixed routes. `activation_worker.py` still uses the kill-relaunch dance. |
| PI-018 | Add `oneToOne` to YAML schema | KEEP | `config_loader.py:84` — `VALID_LINK_TYPES = {"oneToMany", "manyToOne", "manyToMany"}`. No oneToOne. `relationship_manager.py:25-29` LINK_TYPE_TO_METADATA has only the three original entries. |
| PI-019 | Cross-file category resolution in YAML layout validator | KEEP | `config_loader.py:783-785` — `field_categories` still scoped to current YAML's `entity.fields` only. ProgramContext exposes `fields_by_entity` but no `field_categories_by_entity`. |
| PI-020 | Cross-file layout aggregation in deploy engine | KEEP | `run_worker.py:558-571` `_layouts_body` processes per-entity per-file; no batch aggregation. No `LayoutAggregator`. Clobber semantics still in effect. |
| PI-023 | Workstream-state reconciliation utility at kickoff pre-flight | NEEDS-INPUT | `crmbuilder-v2/scripts/reconcile.py` exists (snapshot-driven allowlist design per SES-069 redesign), but original PI spec was at `crmbuilder/tools/workstream_reconcile.py` with API+git cross-reference design. Original acceptance conditions 5 (CLAUDE.md update) and 6 (kickoff-template invocation) unmet. May have been superseded by SES-069 — Doug confirm. |
| PI-024 | PI-022 Phase 2 — backfill prior workstreams | RESOLVE | `workstreams.json` has 9 workstream records covering all 7 prior workstreams listed in PI-024's description (WS-002..008). Apply commit `7eec15d2` landed them. Status field never flipped — missed. Note: PI-022 umbrella close commit `b34391ff` *incorrectly* claimed "Phase 2 deferred." |
| PI-025 | PI-022 Phase 3 — backfill prior conversations | RESOLVE | `conversations.json` has 46 CONV records all `complete`. Per DEC-197, 16 orphan sessions were formally descoped; the remaining 37 CONV records match the orchestrator's target. Apply commit `af11e649` landed them. Status field never flipped. |
| PI-026 | PI-022 Phase 4 — backfill historical applies as deposit_events | RESOLVE | `deposit_events.json` has 32 historical-tagged records (DEP-001..008 from Phase 1 + DEP-020..043 from Phase 4). Per DEC-210, scope tightened to 24 close-outs — matches DEP-020..043 exactly. 32 `dep_NNN-historical.log` files exist. Apply commit `944495e1` landed them. Status field never flipped. |
| PI-027 | Code Change Lifecycle methodology document + settle deferred decisions | NEEDS-INPUT | `methodology-code-change-lifecycle.md` exists (569 lines); DEC-183..190 settle the seven (plus blocks-direction bonus) deferred decisions; §10 build-closure pattern added in SES-074. **However:** §9 "PI-027 Resolution Posture" L487-494 explicitly says "PI-027 stays Open at the end of this conversation's close-out. PI-033's back-fill resolves it once the resolves_planning_items payload section ships in PI-030." This is a deliberate stay-Open contract, not an oversight — Doug confirm whether to honor it. |
| PI-028 | Author commit entity schema spec | NEEDS-INPUT | `governance-schema-specs/commit.md` exists (78KB, 05-23-26). Substantive work is done. Same governance posture as PI-027 per SES-063 topics: "PI-033's back-fill resolves PI-028 retroactively." Doug confirm. |
| PI-029 | Implement commit entity vocab + access + REST API | NEEDS-INPUT | ~95% complete: alembic migration 0012, vocab.py edits, ORM Commit class, `repositories/commits.py`, `api/routers/commits.py` with full standard endpoints, tests at `test_commit_api.py` + `test_commit.py` + `test_commit_model.py`. **Gap:** `ui/client.py` (StorageClient) has zero commit methods — the description explicitly named "StorageClient methods exposing the new endpoints" as a deliverable. Doug confirm whether to RESOLVE despite the gap or KEEP until StorageClient lands. |
| PI-031 | Commits panel + planning_item resolution display in V2 desktop UI | KEEP | No `commits_panel.py` exists. Sidebar at `ui/sidebar.py:56-76` has 14 Governance entries; no Commits entry. Planning_items panel detail view (panels/planning_items.py:172-176) shows raw `resolution_reference` string with no clickable chain. Commit `a5ec830` was kickoff (markdown only), no code shipped. |
| PI-032 | Methodology rollout — close-out template + work_ticket authoring rule documented | NEEDS-INPUT | Methodology guide updated (§4 payload sections, §5.1 work_ticket rule, §10 build-closure); ses_074.json demonstrates the full new shape. **Gap:** root `CLAUDE.md` has zero references to `methodology-code-change-lifecycle`, `resolves_planning_items`, or `work_ticket auth`. PI-032 acceptance bullet 3 requires CLAUDE.md cross-reference. Doug confirm whether methodology-internal documentation suffices. |
| PI-033 | Back-fill historical PI resolutions + work_tickets + commits | KEEP | `work_tickets.json` has 46 records; PI-033 expects ~220. Only 12 `resolves` edges in `references.json` (CONV-046→PI-030, SES-075→PI-034..044) — PI-021, PI-027, PI-028 etc. lack back-fill edges. No `commits.json` snapshot (table exists, zero rows ingested). |
| PI-045 | V2 remote-access deployment | KEEP | Part (a) Code: `cli.py:166-171` --transport flag, FastMCP HTTP binding, marker-drift guard all shipped. Part (b) Steps 1-4: SES-071 close-out applied. **Blocked:** Step 5 (claude.ai connector registration) failed → DEC-226 reroutes to OAuth → PI-049 created. `PI-045 --blocked_by--> PI-049` edge exists in references.json. Part (d) Docs: README has no remote-deployment section. KEEP until PI-049 lands, step 5 completes, docs ship. |
| PI-046 | Resolve vocab.py schema-vs-spec contradiction for `deposit_event_wrote_record` | KEEP | `vocab.py` L353-366 `_kinds_for_pair` still admits `target_type="reference"` for `deposit_event_wrote_record` while `ENTITY_TYPES` (L250-289) does NOT include `"reference"`. Contradiction intact. |
| PI-047 | Resolve ses_030 / ses_036 duplicate-session artifact | NEEDS-INPUT | DB record half is de-facto resolved (SES-030 retitled to "v0.5 slice A follow-up"; SES-036 holds "Styling Conversation 2" title; decided_in edges point DEC-105/106/107 → SES-036). File half still stale: `close-out-payloads/ses_030.json` still claims the old title and references DEC-105/106/107. Doug confirm whether file is treated as immutable archival per PI-048's option (ii). |
| PI-048 | Migrate stale `blocks` references in ses_056.json to `blocked_by` | KEEP | `close-out-payloads/ses_056.json` still contains two entries with `"relationship": "blocks"` (PI-025→PI-024 and PI-026→PI-025). Vocabulary itself renamed in migration 0012; the payload file was not rewritten. |
| PI-049 | v2 MCP server OAuth 2.1 + PKCE implementation | KEEP | Working tree has uncommitted Phase 3 cleanup in progress: middleware.py deleted, config.py strips mcp_shared_secret, server.py adds DEC-227/PI-049 docstring choosing Path B (Cloudflare-managed OAuth). No own-OAuth-server code (no /.well-known endpoints, no /authorize, no /token, no oauth_clients table). Phase 4 (claude.ai registration + 44-tool smoke test) not done. |
| PI-050 | Extend `enumerate_commits.py` with explicit-list mode | KEEP | `scripts/enumerate_commits.py:194-263` `_parse_args` defines only --repos, --engagement-db-export, --repo-root, --branch, --skip-pull, --output, --repo-root-override. No --commits / --shas flag. Still since..HEAD range mode only. |
| PI-051 | audit-v1.4 — §12.5 role-aware visibility deploy + §12.7 field-level permissions | KEEP | Current audit is v1.2 (per `feat-audit.md` and CLAUDE.md). No `audit-v1.4-*.md` or `audit-v1.3-*.md` files in `crmbuilder-automation-PRD/`. No §12.5 Dynamic Handler / Teams-as-proxies deploy in `role_manager.py`. |

---

## Patterns the corrected audit surfaced

### 1. PI-022 backfill phases finished; status fields never flipped (3 RESOLVEs)

PI-024 / PI-025 / PI-026 are the most consequential miss. All three were *executed* — workstream records exist, conversation records exist, deposit_events exist with placeholder logs — but the umbrella PI-022 close commit `b34391ff` incorrectly characterized Phase 2 as "deferred" and no `resolves` edges were ever authored to flip the children. The work shipped; the governance bookkeeping stopped at the umbrella.

### 2. PI-001 status flip never happened despite explicit "discharged" claim (1 RESOLVE)

Status v16 narrates "PI-001 is discharged" but never wrote a `resolves` edge or flipped the status field. Same shape as the PI-022 family — substantive completion landed, machinery missed.

### 3. "Stay Open until PI-033 back-fill" PIs (2 NEEDS-INPUT)

PI-027 and PI-028 have substantively complete deliverables (the CCL methodology doc, the commit.md schema spec) but both have a documented stay-Open contract pointing at PI-033's retroactive resolves-edge back-fill. Honoring that contract → KEEP. Resolving now → 2 more RESOLVEs.

### 4. Almost-done items with one missing deliverable (3 NEEDS-INPUT)

- PI-029: full access layer + REST API + tests, but no StorageClient methods
- PI-032: methodology document and worked example shipped, but no root CLAUDE.md cross-reference
- PI-023: utility shipped but at a different path / design (snapshot-driven per SES-069 redesign instead of API+git original spec); CLAUDE.md and kickoff invocations unmet

### 5. File-vs-DB divergence (1 NEEDS-INPUT)

PI-047: the SES-030/SES-036 duplicate is fixed in the database (titles corrected, edges point to right session) but the on-disk `ses_030.json` close-out payload still misrepresents the conversation's identity.

### 6. In-progress work (1 KEEP)

PI-049 — your working-tree changes (middleware.py deletion, config.py + server.py edits) are exactly this PI's Phase 3 implementation, not committed yet.

---

## Method

For each PI, the revised audit extracts the concrete artifacts the description specifies — file paths, ORM columns, alembic migrations, vocab entries, sidebar entries, methodology document sections, database snapshot record counts — and checks whether they exist in the current codebase / snapshots / payload files. RESOLVE only when *all* artifacts are present. KEEP when none exist. NEEDS-INPUT when partial or when a stay-Open contract is in effect.

PI description text is treated as a specification of expected end-state, not as a status field. The original keyword-scan against descriptions was discarded.

---

## How to respond

Reply in chat with one of:

- "Approve all RESOLVE recommendations" — PI-001, PI-024, PI-025, PI-026 flip to Resolved; everything else stays Open.
- "Approve RESOLVE except PI-X" — listed exceptions stay Open.
- "Also resolve PI-A, PI-B" — listed NEEDS-INPUT or KEEP items override and flip.
- Any mix.

For each NEEDS-INPUT item, an explicit RESOLVE or KEEP decision is most useful — the corrected audit can't adjudicate them without a call:

- **PI-023** — does the SES-069-redesign-shipped utility discharge the original conditions?
- **PI-027** — honor the §9 stay-Open contract (KEEP) or flip now since methodology is done (RESOLVE)?
- **PI-028** — same posture as PI-027.
- **PI-029** — RESOLVE despite missing StorageClient methods, or KEEP until they land?
- **PI-032** — does the methodology-internal documentation discharge acceptance bullet 3, or is the missing root CLAUDE.md cross-reference still blocking?
- **PI-047** — treat the stale ses_030.json as immutable archival (RESOLVE) or migrate the file (KEEP)?

Phase B (`CLAUDE-CODE-PROMPT-pi-cleanup-B-apply-resolutions.md`) is generated from your reply and runs against the V2 API as a standard close-out (resolutions bundled in a payload, applied via `apply_close_out.py`, snapshots regenerate, one deposit_event recorded).
