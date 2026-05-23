# PI-024 — Prior-workstreams backfill — Kickoff prompt

**Last Updated:** 05-23-26 05:30
**Operating mode:** ARCHITECTURE
**Repo:** `dbower44022/crmbuilder` (sparse clone — `CLAUDE.md`, `PRDs/`, `crmbuilder-v2/`)
**Anticipated SES at close:** SES-057 (next unassigned after SES-056)
**Discharges:** Phase 2 of PI-022, scoped narrowly per PI-024.
**Queued after this:** PI-025 (prior-conversations backfill) → PI-026 (historical-applies-as-deposit_events backfill) → PI-023 (workstream-state reconciliation utility).

---

## Purpose

Backfill the prior workstreams that pre-date PI-022 Phase 1 as `workstream` entity records in the V2 governance database. WS-001 (the governance entity schema-design workstream) was created in Phase 1 and covers the seven schema-design conversations plus the v0.7 build itself; everything before it remains unrepresented. This conversation lists those prior workstreams, settles their metadata (lifecycle dates, names, purposes, descriptions, status), and produces a Claude Code prompt that POSTs them via the V2 API.

This conversation does **not** create conversation records or workstream-to-conversation membership edges. Those are PI-025 (Phase 3). PI-024's deliverable is the workstream records themselves — clean, complete, ready for PI-025 to attach memberships against.

---

## Read this first

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. `PRDs/product/crmbuilder-v2/db-export/planning_items.json` — read PI-022 (the parent), PI-024 (this), PI-025 and PI-026 (the dependents). Confirms scope.
3. `PRDs/product/crmbuilder-v2/db-export/workstreams.json` — single record (WS-001). Confirms field shape, lifecycle timestamps, status vocabulary.
4. `PRDs/product/crmbuilder-v2/governance-schema-specs/workstream.md` — the schema spec, authoritative for field meanings and lifecycle states.
5. `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-E-pi022-backfill.md` — Phase 1 precedent. The backfill script pattern, idempotency contract, and verification approach to mirror.
6. `crmbuilder-v2/scripts/backfill_governance_phase_1.py` — the Phase 1 script itself. Read for the envelope-unwrap pattern and the POST sequencing.
7. `PRDs/product/crmbuilder-v2/db-export/sessions.json` — the 55 prior session records, used to reconstruct each workstream's date range and scope. Each session has a `session_date` plus `topics_covered` text describing what the conversation was about.

---

## The workstreams to backfill

PI-024's description names seven candidates. WS-001 already covers the last one (the v0.7 release = the schema-design + build workstream), so the actual list is **six**:

1. **Methodology entity schema-design workstream** — the user-interface version 0.4 arc that produced the four methodology entity types (domain, entity, process, crm_candidate). Spanned SES-011 through roughly SES-015 plus the v0.4 build conversation. First and largest of the prior workstreams.
2. **User-interface version 0.5 engagement management workstream** — multi-engagement architecture work. Material lives at `PRDs/product/crmbuilder-v2/v0.5-engagement-management-workstream-plan.md` and conversation kickoffs at `v0.5-conversation-1-kickoff.md`, `v0.5-conversation-2-kickoff.md`.
3. **User-interface version 0.6 styling workstream** — design pass. Material at `styling-workstream-plan.md`, `styling-design-pass.md`, `styling-conversation-1-kickoff.md`, screenshots directory.
4. **Multi-tenancy routing fix workstream** — investigation and remediation arc. Material at `multi-tenancy-routing-investigation-report.md`, `multi-tenancy-routing-fix-planning-kickoff.md`, `multi-tenancy-routing-fix-slice-plan.md`.
5. **Cleveland Business Mentors paper test workstream** — methodology-schema paper test. Material at `methodology-schemas-cbm-paper-test-kickoff.md` and `methodology-schemas-cbm-paper-test-findings.md`.
6. **Catalog ingestion workstream** — `catalog-ingestion-PRD-v0.1.md` and `catalog-ingestion-implementation-plan.md`.

Anticipated workstream identifiers after backfill: WS-002 through WS-007 in roughly chronological start order.

**Disambiguation note.** PI-024's text lists "the v0.7 release itself" as a seventh prior workstream, but WS-001's description in the database makes clear that WS-001 already covers the schema-design plus the v0.7 build (SES-047 through SES-056). The kickoff treats WS-001's scope as settled and excludes a separate v0.7 record. If the conversation surfaces a reason to split WS-001 into "schema design" and "v0.7 build" workstreams, that's a decision worth surfacing.

---

## Architectural questions likely to arise

These are the decisions this conversation is expected to make. Order is illustrative; let the conversation flow.

- **Definitive workstream inventory.** Six listed above. Are there omissions? Candidates that might or might not qualify: the YAML schema v1.1 eight-prompt series (already archived but predates the methodology schema work); the error-handling-prompt series A–E in the espo_impl code path; the layout-fix triplet of commits in May. The two-part test: did the work have a coherent purpose, multiple connected conversations or prompts, and a recognizable beginning/end? Some "workstreams" in the project's informal usage may be too small or too diffuse to record as workstream entities.

- **Lifecycle date reconstruction strategy.** Each workstream needs `workstream_started_at` and `workstream_completed_at`. Candidate sources: (a) first/last commit touching that workstream's material in git; (b) first/last session_date in the relevant sessions.json range; (c) date of the kickoff file's `Last Updated` and the closeout payload's `session_date`. The conversation chooses one and applies it consistently, or admits a per-workstream judgment with reasoning recorded in each `workstream_notes`.

- **Status for each workstream.** Working assumption: all six are `complete`. Is anything actually `cancelled` or `superseded`? The CBM paper test, for example — was it run to completion, or was it cut short when findings made the rest unnecessary?

- **Workstream-supersedes-workstream edges.** Does any workstream supersede another? Plausible candidates: the methodology entity schema-design workstream succeeded by the governance entity schema-design workstream (related, but not the same scope — probably not supersession). The user-interface version 0.4 → 0.5 → 0.6 → 0.7 sequence is a natural-order chain but probably not a supersession relationship in the entity-vocabulary sense.

- **What edges, if any, to create in this phase.** Phase 2's scope is intentionally narrow: workstream records only. Conversation-membership edges are PI-025. But there are workstream-level edges that don't require conversations to exist — for example, a workstream-supersedes-workstream edge between two workstream records (if any apply) could be created in PI-024 without waiting for PI-025. The conversation decides whether to attempt these or punt them entirely.

- **Master-plan reference_book edges.** Some prior workstreams have a master plan document at a known path (e.g., `v0.5-engagement-management-workstream-plan.md` for the v0.5 workstream). These could become reference_book records with a `workstream_planned_in_reference_book` edge, mirroring how WS-001 has RB-001 (the governance workstream plan). This is technically reference_book backfill, not workstream backfill — outside PI-024 strictly. The conversation decides whether to bundle one master-plan reference_book per workstream into PI-024's prompt, or defer all reference_book work to a future phase.

---

## Working pattern

- ARCHITECTURE mode. Surface design questions one at a time; decide each before moving on. Routine framing choices (e.g., field formatting) get decided and announced briefly per the two-part test.
- Code changes go through Claude Code prompts under `PRDs/product/crmbuilder-v2/prompts/`, named `CLAUDE-CODE-PROMPT-pi-024-{descriptor}.md` (no multi-letter series unless the work splits naturally; PI-024 is expected to fit in one prompt).
- The backfill script itself goes at `crmbuilder-v2/scripts/backfill_pi_024_prior_workstreams.py`, mirroring the Phase 1 script's location and pattern. Idempotent on re-run via HTTP 409 SKIP.
- Sandbox commits push at session close per CLAUDE.md's working-conventions rule.

---

## Deliverable shape

By end of conversation:

1. **A list of ~6 workstream records** with each field settled: identifier (WS-002..WS-007 or as decided), name, purpose, description, started_at, completed_at, status, notes (if any), plus any inbound master-plan reference_book or supersession edges decided in scope.
2. **A Claude Code prompt** at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-024-prior-workstreams-backfill.md` that authors a backfill script, runs it, verifies counts, commits the script and any log placeholders. Doug runs this prompt locally via Claude Code.
3. **The close-out artifacts:** payload at `close-out-payloads/ses_057.json` and apply prompt at `prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-057.md`, both committed and pushed from the sandbox.

The close-out applies the session record (SES-057), any DECs the conversation produces (likely one or two — at minimum a decision on the lifecycle-date reconstruction strategy if it's non-obvious), and any references. The workstream records themselves arrive via the Claude Code backfill prompt, not via the close-out payload — the close-out payload's `records_summary` will note that workstream records are populated out-of-band by the backfill script.

---

## Identifier notes

Verified against the database snapshot at this kickoff's authoring time (05-23-26):

- **Session:** SES-057. SES-056 was the v0.7 build closeout; no session has landed since.
- **Decision:** DEC-168. DEC-167 was authored at SES-056 closeout. (This was the identifier the cancelled SQLite-transaction-semantics decision-capture kickoff had reserved; with that kickoff cancelled, DEC-168 is free for the first real decision PI-024 produces.)
- **Workstream:** WS-002 starts the new range; WS-007 is the expected ceiling for six prior workstreams. Adjust if the conversation revises the inventory.

If a conversation closes between this kickoff's authoring and the SES-057 apply, the session re-verifies via `GET /sessions/next-identifier` and `GET /decisions/next-identifier` at apply time.

---

## What's queued after this

PI-024 → **PI-025** (prior-conversations backfill — ~52 prior session records plus SES-053 become conversation records, each with workstream membership and session-record edges; this is where the workstream-to-conversation edges actually land) → **PI-026** (~38 prior close-out payload files become deposit_event records with `runner = 'backfill_script'` and `_outcome = 'success'`; transitions each prior close_out_payload to `applied`) → **PI-023** (workstream-state reconciliation utility — `crmbuilder/tools/workstream_reconcile.py` to prevent state drift between git deliverables and the V2 governance database).

Each of those gets its own kickoff prompt authored at the close of the prior conversation.

---

## Out of scope

- Conversation records (PI-025).
- Deposit_event records for historical applies (PI-026).
- The workstream-state reconciliation utility (PI-023).
- Reference_book records beyond optional master-plan books, if the conversation decides to include those.
- Reopening the question of WS-001's scope (treated as settled unless the conversation surfaces a strong reason to revisit).
- Any code change unrelated to the backfill script.

---

*End of kickoff.*
