# PI Cleanup Proposal — Phase A Review

**Last Updated:** 05-25-26 12:21
**Scope:** all Open planning items in the CRMBUILDER engagement
**Total reviewed:** 37
**Recommended RESOLVE:** 1
**Recommended KEEP:** 20
**NEEDS-INPUT:** 16

---

## Recommendations

| PI | Title | Recommendation | Reason |
|----|-------|----------------|--------|
| PI-001 | Full styling design pass per DEC-024 | KEEP | description: "...ing design pass per DEC-024. Originally deferred four times (DEC-024 → DEC-026 → DEC-037 → DEC-042) on the CBM-redo-friction trigger principle. **Reopened as a..." |
| PI-002 | Make `identifier` optional in POST bodies (SES-010 option C) | KEEP | description: "...sion — is the cleaner end state but was deferred from v0.4 because it changes existing endpoint contracts (gray-area under the kickoff's 'doesn't alter v0.3's s..." |
| PI-003 | Persona entity type for v0.5+ (deferred from v0.4 minimum-viable inventory) | KEEP | description: "...DEC-039 deferred persona from v0.4's minimum-viable inventory because evolved Phase 1's interview guide v0.2 explicitly excludes..." |
| PI-004 | Additional methodology entity types for v0.5+: field, requirement, manual_config, test_spec | KEEP | description: "...DEC-039 deferred fields, requirements, manual-config items, and test specs from v0.4's minimum-viable inventory. These are Phase..." |
| PI-005 | Process schema growth beyond Phase 1 thin shape (full process definition) | KEEP | description: "...but the migration scope is non-trivial. Target release: v0.5+ after persona and field land, conditional on CBM redo reaching Phase 3...." |
| PI-006 | Retrofit governance entities to parent-prefix field-naming convention | KEEP | description: "...ignificant additional work) or defer to v0.5+. The methodology workstream's specs ship with the new convention regardless of when this retrofit lands...." |
| PI-007 | domain.short_code field for mnemonic references and downstream identifier prefixes | NEEDS-INPUT | SES-015 topics_covered: "...gh DEC-064 from SES-015 pending apply), seven new planning items (PI-006 / PI-007 / PI-008 from SES-012; PI-009 / PI-010 from SES-013; PI-011 from SES-014; PI-012 from SES-015 pending apply), and the ..." |
| PI-008 | Inbox folder watcher in v0.3 desktop app for close-out JSON payloads | KEEP | description: "...am conversations) or defer to v0.5+. If deferred, the apply_close_out.py script remains the close-out pattern...." |
| PI-009 | Master-pane Domains column on the Entities panel (paired with PI-007 short codes) | KEEP | description: "...he master pane of the Entities panel to v0.5+, jointly enabled by PI-007 (domain.short_code field). The column renders affiliated domains as comma-separated sho..." |
| PI-010 | Entity-schema v0.5+ extensions — variants and base-type/kind classification | KEEP | description: "...ing new entity types. Variant mechanism TBD: candidates include self-referential FK (entity_parent_identifier), references-entity edge (entity_variant_of_entity..." |
| PI-011 | Future scalar implementation-priority field on process for ranking within classification buckets | KEEP | description: "...cation (mission_critical / supporting / deferred / unclassified) as the methodology priority classification per Principle 3. During the conversation the user ob..." |
| PI-012 | crm_candidate structured-metadata enums (vendor_url, hosting_type, license_type, price_tier) for v0.5+ | KEEP | description: "...-kickoff-crm_candidate.md document were deferred from v0.4 to v0.5+ under this planning item: - crm_candidate_vendor_url — optional free-text URL field pointin..." |
| PI-013 | Cross-Domain Service representation | KEEP | description: "...Target version: v0.5+. The original methodology named Cross-Domain Service (Notes, Email, Calendar, Surveys) as a methodology entity ty..." |
| PI-014 | Catalog FK integration for methodology entities | KEEP | description: "...Target version: v0.5+. The catalog ingestion PRD's section 3.3 sketched a hybrid integration pattern: methodology entities carry an opt..." |
| PI-015 | Methodology entity renderers | KEEP | description: "...Target version: v0.5+ or later. DEC-008 prescribes that v2 produces renders, not authored copies — Word documents, deployment YAML, and..." |
| PI-016 | Router-level per-pair vocabulary enforcement on `/references` | KEEP | description: "...Target version: v0.5+. The live `/references` router does not enforce per-pair `RELATIONSHIP_RULES` because doing so would break v0.3 r..." |
| PI-017 | Migrate API and MCP servers to multi-tenant model | KEEP | description: ".... Note: this PI is not the same as the deferred 'cross-engagement reporting' or 'engagement-level access control' workstreams. Those are separate v0.6+ candida..." |
| PI-018 | Add oneToOne relationship support to YAML schema | NEEDS-INPUT | commit `01fdc573 v2: apply SES-044 — multi-tenancy routing fix planning close-out` — no resolves edge |
| PI-019 | Cross-file category resolution in YAML layout validator | NEEDS-INPUT | commit `2d438f08 v2: SES-044 close-out — rebase PI-018 → PI-021 (TOCTOU collision)` — no resolves edge |
| PI-020 | Cross-file layout aggregation in deploy engine | NEEDS-INPUT | commit `2d438f08 v2: SES-044 close-out — rebase PI-018 → PI-021 (TOCTOU collision)` — no resolves edge |
| PI-023 | Workstream-state reconciliation utility at kickoff pre-flight to prevent git-vs-database state drift | KEEP | description: "...he kickoff-prompt-generator pattern for future workstreams) instructing pre-flight to invoke the utility against the workstream identifier before the first arch..." |
| PI-024 | PI-022 Phase 2 — backfill prior workstreams | NEEDS-INPUT | commit `3a7871f1 Apply SES-060 close-out — audit-v1.2 planning resolutions` — no resolves edge |
| PI-025 | PI-022 Phase 3 — backfill prior conversations | NEEDS-INPUT | commit `9b97211c Apply SES-062 close-out: PI-025 prior-conversations backfill planned` — no resolves edge |
| PI-026 | PI-022 Phase 4 — backfill historical applies as deposit_events | NEEDS-INPUT | commit `b34391ff PI-022 governance-backfill program closed — PI-022 status Open -> Resolved` — no resolves edge |
| PI-027 | Draft Code Change Lifecycle methodology document and settle deferred design decisions | KEEP | description: "...am queries walk the chain. Settle seven deferred design decisions plus the blocks direction question in passing. Deferred decisions are: commit identifier strat..." |
| PI-028 | Author commit entity schema spec in the governance schema spec format | RESOLVE | SES-063 topics_covered: "...dology specifies does not yet ship (PI-030 work), so this conversation cannot resolve its own planning item via the new mechanism. PI-033's back-fill resolves PI-028 retroactively. Honesty of "the met..." |
| PI-029 | Implement commit entity schema vocab access layer and REST API | NEEDS-INPUT | SES-067 topics_covered: "...isting files..." attached to the conversation's opening turn alongside the PI-029 slice B kickoff path (PRDs/product/crmbuilder-v2/pi-029-slice-b-commit-access-layer-and-rest-endpoints-kickoff.md). Pr..." |
| PI-031 | Implement commits panel and planning_item resolution display in V2 desktop UI | NEEDS-INPUT | commit `4fffbb73 Apply SES-074 close-out: PI-030 build closure — first nine-section v0.8 payload` — no resolves edge |
| PI-032 | Methodology rollout — close-out template and work_ticket authoring rule documented | NEEDS-INPUT | commit `4fffbb73 Apply SES-074 close-out: PI-030 build closure — first nine-section v0.8 payload` — no resolves edge |
| PI-033 | Back-fill historical planning_item resolutions work_tickets and commits | NEEDS-INPUT | commit `24c42cfb PI-030 build closure (SES-074) — first nine-section v0.8 close-out payload + apply prompt + methodology amendments` — no resolves edge |
| PI-045 | V2 remote-access deployment: expose MCP server publicly so claude.ai can read and write the v2 governance database | NEEDS-INPUT | SES-072 topics_covered: "...Seed prompts: each slice executed against its dedicated `CLAUDE-CODE-PROMPT-pi-045-{A,B,C}-*.md` prompt authored in SES-065. Slice A: 'PI-045 slice A — `--transport` flag and FastMCP HTTP binding' (op..." |
| PI-046 | Resolve vocab.py schema-vs-spec contradiction for reference targets in deposit_event_wrote_record edges | NEEDS-INPUT | commit `b34391ff PI-022 governance-backfill program closed — PI-022 status Open -> Resolved` — no resolves edge |
| PI-047 | Resolve ses_030 / ses_036 duplicate-session artifact and the 4 unresolvable references ses_030's payload claims | NEEDS-INPUT | commit `b34391ff PI-022 governance-backfill program closed — PI-022 status Open -> Resolved` — no resolves edge |
| PI-048 | Migrate stale 'blocks' relationship references in ses_056.json (and any other historical close-out payloads with the same pattern) to the v0.8-renamed 'blocked_by' relationship kind — or formally accept stale-vocab in historical payloads as an immutable archival convention | KEEP | description: "...argues for (i). PI-048's resolution is deferred to a future workstream alongside PI-046 (vocab schema-vs-spec contradiction) and PI-047 (ses_030/ses_036 duplic..." |
| PI-049 | v2 MCP server OAuth 2.1 + PKCE implementation: enable claude.ai custom connector registration by replacing the X-CRMBuilder-Secret shared-secret middleware with OAuth-token-based auth (with a timeboxed Path B feasibility check before committing to Path A) | NEEDS-INPUT | commit `24c42cfb PI-030 build closure (SES-074) — first nine-section v0.8 close-out payload + apply prompt + methodology amendments` — no resolves edge |
| PI-050 | Extend enumerate_commits.py with explicit-list mode for parallel-workstream closures | NEEDS-INPUT | commit `4fffbb73 Apply SES-074 close-out: PI-030 build closure — first nine-section v0.8 payload` — no resolves edge |
| PI-051 | audit-v1.4 — Section 12.5 role-aware visibility deploy implementation alongside Section 12.7 field-level permissions | KEEP | description: "...v1.2 because the schema sub-section was deferred from v1.1. v1.4 should consider §12.5 and §12.7 holistically since both are role-keyed permission surfaces with..." |

---

## Reading the table

- **RESOLVE** rows: positive completion signal found — either a `resolves` reference edge from a session (rule 1) or a later session whose `topics_covered` contains the exact phrase `resolves PI-NNN`, `completes PI-NNN`, `closes PI-NNN`, or `ships PI-NNN` (rule 2). Status flip was missed.
- **KEEP** rows: self-deferral language in the PI's own description (rule 3) or parent of at least one other Open PI (rule 4). The conservative default also lands here when no positive completion signal is found (rule 7).
- **NEEDS-INPUT** rows: ambiguous. Either a later session mentioned the PI with partial-completion language (rule 5), or completion-verb commits exist with no `resolves` edge and no deferral language (rule 6). The cited commit *mentions* the PI but the subject doesn't necessarily prove the PI was completed — substrings like `close-out`, `rebase PI-X → PI-Y`, or another PI's `implement` can trigger this. Doug should adjudicate each one.

---

## Method

- **Inputs:** `db-export/{planning_items,sessions,decisions,references,conversations}.json` (current per the per-write `_refresh_snapshot` hook).
- **Evidence per PI:** description text scan, incoming reference edges (`resolves`, `is_about`, `addresses`, `blocked_by`), later-session `topics_covered` mentions, and `git log --all --grep` matches classified by completion / setup / other verbs.
- **Recommendation rules:** see `CLAUDE-CODE-PROMPT-pi-cleanup-A-review-open-items.md` §Recommendation rules. Conservative default: KEEP when no positive completion signal.
- **Reversibility:** any RESOLVE Doug spot-flags as wrong stays Open in Phase B; any KEEP that turns out to have been done can be re-resolved later with a one-off UPDATE-PROMPT.

---

## How to respond

Reply in chat with one of:

- "Approve all RESOLVE recommendations" — every row marked RESOLVE flips, every KEEP and NEEDS-INPUT stays Open.
- "Approve RESOLVE except PI-X, PI-Y" — listed exceptions stay Open.
- "Resolve PI-A, PI-B as well" — listed items override their KEEP / NEEDS-INPUT recommendation and flip.
- Any mix of the above.

Phase B (`CLAUDE-CODE-PROMPT-pi-cleanup-B-apply-resolutions.md`) is generated from your reply and runs against the V2 API as a standard close-out (resolutions bundled in a payload, applied via `apply_close_out.py`, snapshots regenerate, one deposit_event recorded).
