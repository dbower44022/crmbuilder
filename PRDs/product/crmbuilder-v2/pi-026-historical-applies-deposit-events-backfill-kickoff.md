# PI-026 historical-applies-deposit-events backfill — kickoff

**Last Updated:** 05-23-26 23:30
**Status:** Kickoff — ready for a planning conversation to open against it once PI-025 has applied and SES-063 / SES-064 have applied through the normal real-time path.
**Authored at:** the close of the PI-025 prior-conversations backfill conversation (SES-062) per that kickoff's chain rule.
**Anticipated session at close:** SES-065 (subject to identifier rebasing if other conversations close between now and the open of PI-026; see "Identifier note" below).

---

## Purpose

PI-026 is Phase 4 of PI-022 (governance backfill). It backfills the **close_out_payload** and **deposit_event** entity records for the close-out applies that landed before the deposit_event entity wiring was complete — and the edges that wire each new deposit_event to its parent close_out_payload and to the records the historical apply actually created.

After PI-026 lands, every close-out apply in the engagement's history is queryable as a first-class event: which payload was applied, when, with what outcome, and which session / decisions / planning items / references the apply produced. The audit-query "which apply created record X?" returns answers from data via `deposit_event_wrote_record` edges, rather than from inference against the apply script's stdout logs.

---

## Read this first

- Read `crmbuilder/CLAUDE.md` for engagement context. Confirm with Doug at the open of the conversation.
- Read the PI-025 kickoff at `PRDs/product/crmbuilder-v2/pi-025-prior-conversations-backfill-kickoff.md` for the immediate predecessor's framing and the discharge-Phase-3 pattern.
- Read the deposit_event entity schema spec at `PRDs/product/crmbuilder-v2/governance-schema-specs/deposit_event.md` for required fields (sections 3.2.6 covers the three required JSON fields: `records_summary`, `error_info`, `apply_context`), the born-terminal lifecycle, and the applies-edge contract. Pay particular attention to section 3.4.3 — the access-layer atomicity around the applies-close-out-payload edge and the COP status transition.
- Read the close_out_payload entity schema spec at `PRDs/product/crmbuilder-v2/governance-schema-specs/close_out_payload.md` for the COP record shape and its `ready` → `applied` lifecycle.
- Read the Phase 1 precedent script at `crmbuilder-v2/scripts/backfill_governance_phase_1.py` for the deposit_event-and-close_out_payload creation pattern: Phase 1 authored COP-001..008 and DEP-001..008 inline as part of the governance entity workstream backfill. PI-026 extends the same pattern to the remaining historical close-outs.
- Skim the SES-062 close-out at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_062.json` for the seven decisions PI-025 just settled (DEC-191..197) — PI-026 inherits the routine choices (born-complete via single-POST with references array; idempotency contract; commit-and-snapshot two-step pattern).

---

## Scope

### What this conversation backfills

- **`close_out_payload` records** for the historical close-out JSON files that landed before the COP entity existed (i.e., before the v0.7 release). Identifier range starts at COP-009 (COP-001..008 are Phase 1's backfilled records; COP-056..062 are real-time records for SES-056..062; PI-026 fills the gap between COP-008 and COP-056).
- **`deposit_event` records** for the historical close-out applies. Identifier range starts at DEP-016 (DEP-001..008 are Phase 1's backfilled records; DEP-009..015 are real-time records for COP-056..062; PI-026 fills the gap from DEP-016 onward).
- **`deposit_event_applies_close_out_payload` edges** — one per new DEP, pointing to its parent COP.
- **`deposit_event_wrote_record` edges** — one per record the historical apply created, reconstructed by parsing each close-out JSON's session / decisions / planning_items / references arrays.

### Inventory boundary

As of the time of this kickoff (post PI-025 apply):

- **Close-out payload JSONs on disk:** 43 files in `PRDs/product/crmbuilder-v2/close-out-payloads/` covering ses_001 through ses_064 with 21 gaps (no JSON for sessions where the close-out was never authored or was merged into another payload).
- **COP records currently present:** 15 (COP-001..008 from Phase 1 backfill covering ses_047/048/049/050/051/052/054/055; COP-056..062 real-time covering ses_056..062).
- **DEP records currently present:** 15 (DEP-001..008 from Phase 1 backfill; DEP-009..015 real-time).
- **Close-out JSONs needing COP+DEP records via PI-026 (28 candidates pre-filter):** ses_001, ses_012..015, ses_025..027, ses_029..044, ses_046, ses_053, ses_063, ses_064.
- **Excluded by pre-flight:** ses_063 and ses_064 are recent close-outs that will land COP+DEP records via the normal real-time apply path. PI-026 verifies in pre-flight that both have been applied (their COPs are present in the snapshot); if either is still pending, the kickoff says "apply them first via their normal apply prompts, then return to this conversation."
- **Final PI-026 inventory: 26 close-out JSONs** — ses_001, ses_012..015, ses_025..027, ses_029..044, ses_046, ses_053.

The exact COP-to-records mapping for each historical close-out is the conversation's first deliverable: for each of the 26 JSONs, enumerate the session record + decisions + planning_items + references it carries, so the DEP's `records_summary` JSON field and the matching count of `deposit_event_wrote_record` edges can be authored deterministically.

### Identifier-allocation question (COP and DEP numbering)

The existing identifier landscape has a structural inconsistency: COP-001..008 use sequential numbering inherited from Phase 1's backfill; COP-056..062 use match-to-SES numbering adopted by the v0.7 real-time apply script. PI-026 inherits this inconsistency. Two options:

- **Option A — continue sequential.** PI-026 authors COP-009 through COP-034 (26 records) and DEP-016 through DEP-041, allocating in inventory order. Convention then reads: "backfilled COPs/DEPs are sequential; real-time records match SES." Inconsistent but factually accurate to the project history.
- **Option B — match-to-SES for backfilled records too.** PI-026 authors COP-001-h (or COP-201, or some collision-free naming) per close-out. Requires either a schema-level identifier-format change to admit a backfill suffix, or skipping the under-008 range (impossible — COP-001 already covers ses_047) and using a high range like COP-101..126. Adds complexity.

Default: Option A. Surface and confirm; settle as a routine decision unless the conversation discovers a reason to prefer B.

### Other surface-and-settle questions for the conversation

These are flagged by the kickoff but **not** resolved here. The conversation should surface them as it works through the inventory:

1. **Log file backfill convention.** Phase 1 created `dep_NNN-historical.log` placeholder log files at `PRDs/product/crmbuilder-v2/deposit-event-logs/` for its 8 backfilled DEPs. PI-026 should follow the same convention: author 26 placeholder log files with synthetic content describing what each historical apply did (e.g., "Backfilled apply of ses_001.json against CRMBUILDER engagement on <date>. Outcome: success. Records created: 1 session SES-001, N decisions, ..."). Confirm the convention against Phase 1's actual log content before drafting.
2. **`apply_context.apply_script_version` for backfilled DEPs.** Historical applies pre-date the current apply_close_out.py version tracking. Use a placeholder like `"backfill"` or `"unknown-historical"`? Or attempt to identify the actual version that was running by git-log at the close-out file's commit timestamp? Default: `"backfill"` — the runner field carries the provenance, version doesn't add information.
3. **`apply_context.invocation`.** Historical applies' actual command-line invocations are unrecorded. Synthesize a representative string like `"backfill_pi_026: ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json"`? Default: yes, with the actual JSON file path substituted.
4. **`records_summary` counting for re-confirmations.** All 26 historical applies are presumed first-applies (no re-confirmation history). Counts equal the payload's record counts. Confirm no counterexample exists by spot-checking a sample.
5. **Idempotency of `deposit_event_wrote_record` edges.** Each historical record (session, decision, planning_item, reference) gets exactly one inbound wrote_record edge per the spec's at-most-one-inbound cardinality. If any historical record currently has a stale wrote_record edge (e.g., from an aborted earlier backfill attempt), the script must detect and skip rather than fail. Use 409 / 422-duplicate handling per the inherited pattern.

---

## Working pattern

Operating mode: **ARCHITECTURE** by project default. PROTOTYPE if and only if the conversation gets deep into JSON-shape drafting for the diagnostic fields; switch back to ARCHITECTURE before the close-out.

Same iteration shape as PI-024 and PI-025:
- One consequential decision at a time, presented using the consequential-decision template; terse approvals are sufficient.
- Routine choices decided and announced inline.
- Document approvals (the per-COP record-count inventory) presented as a block once before the apply prompt is drafted.

---

## Deliverable shape

Same triple-artifact close-out pattern as PI-024 and PI-025:

1. **`PRDs/product/crmbuilder-v2/close-out-payloads/ses_065.json`** — close-out payload for the planning conversation, covering its session record plus the decisions it settles. Decisions to anticipate (subject to the conversation): the identifier-allocation read (A vs B), the log file convention, the apply_context.invocation convention, and the `records_summary` counting convention.
2. **`PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-065.md`** — apply prompt for the close-out payload.
3. **`PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-026-historical-applies-deposit-events-backfill.md`** — authors `crmbuilder-v2/scripts/backfill_pi_026_historical_applies_deposit_events.py`, runs it, verifies counts, commits in two steps (script-file commit first, then regenerated db-export snapshots).

Mirror PI-024 and PI-025's script pattern: idempotent on re-run, HTTP 409 and 422-duplicate treated as already-present. Inventory data is a single list of 26 entries each carrying the close-out JSON path, allocated COP identifier, allocated DEP identifier, log file placeholder content, and the parsed record counts for `records_summary`.

**Lessons inherited from PI-025's backfill experience** (memory references during the planning conversation):

- Every field listed as required at the access layer must be populated in the POST body even when the value is a placeholder or empty string — never omit the key.
- `session_date` values in the CRMBUILDER snapshot are heterogeneous (older sessions store MM-DD-YY, newer sessions store YYYY-MM-DD). Any field-substitution into ISO-8601 datetime strings must normalize on read regardless of stored format. Same applies to any other date-bearing field consumed during this backfill.

---

## Identifier note

This kickoff anticipates SES-065 as the conversation's close. If other conversations close at SES-065 or beyond between this kickoff's publishing and PI-026's open, the planning conversation will need to rebase to the next available session identifier and the next available DEC range. Verify identifier heads at the start of the planning conversation as the first sanity check.

---

## What's queued after this

- **PI-023** — Workstream-state reconciliation utility at `crmbuilder/tools/workstream_reconcile.py`. Reads the populated workstream / conversation / session / close_out_payload / deposit_event graph after PI-024 / 025 / 026 land and verifies internal consistency. Reports orphan sessions (no CONV record), orphan CONVs (no workstream), CONVs whose succeeds chain doesn't form a DAG, workstreams whose session_date range disagrees with conversation_completed_at extremes, COPs without applies-edges, applies-edges pointing at nonexistent COPs, and any other invariant violations. Closes the PI-022 governance-backfill program.

PI-023 closes the PI-022 program once it lands.

---

## Out of scope (explicit)

- **Master-plan `reference_book` records for WS-002 (catalog ingestion), WS-006 (CBM paper test), WS-007 (multi-tenancy fix), and WS-008 (audit-v1.2).** PI-024's DEC-177 deferred the first three on the grounds that their planning material spans multiple documents without a single master-plan-style doc; PI-025 created WS-008 with the same property and inherited the deferral. PI-026 is deposit_events, not reference_books — this gap is unrelated to its scope. It is the only remaining open thread from the PI-022 governance-backfill program outside Phase 4's scope. The thread is either addressed by a future tight one-PI conversation (proposed as PI-045 or whatever the next-available planning item number is at the time) or accepted as permanently deferred. No decision required here.
- **Close-out payload JSONs that exist on disk but cover sessions that don't exist in the database.** If the inventory surfaces such files (currently none anticipated, but verify), document them in the SES-065 close-out's `in_flight_at_end` and skip them — a COP record requires the apply target's session record to exist.
- **The SES-063 and SES-064 close-out applies themselves.** Both close-out payloads landed on disk via real-time work outside the PI-022 governance-backfill program; both will produce COP+DEP records when applied through their normal apply prompts. PI-026's pre-flight verifies both have been applied before proceeding. Apply them first via their respective apply prompts at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-063.md` and `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-064.md` if they are still pending.
- **Resolution of PI-024 / PI-025 / PI-026 themselves.** Resolution depends on the resolves mechanism that PI-029 / PI-030 (Code Change Lifecycle workstream) will ship. Until then, all three stay Open even after PI-026 lands.
