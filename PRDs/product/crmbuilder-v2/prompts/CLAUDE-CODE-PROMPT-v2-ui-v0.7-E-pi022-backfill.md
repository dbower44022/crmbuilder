# Claude Code Prompt — v0.7 Slice E: PI-022 Phase 1 retroactive backfill

**Last Updated:** 05-22-26 17:30
**Release:** v0.7 (governance entity release)
**Slice:** E — execute PI-022 Phase 1: backfill the governance entity schema-design workstream's eight conversations, one workstream, eight close_out_payloads, eight deposit_events, eight work_tickets, nine reference_books, and their reference edges
**Predecessor slice:** Slice D (apply script modifications) — must have shipped
**Successor slice:** Slice F (documentation and version bump)
**PRD:** `PRDs/product/crmbuilder-v2/governance-entity-PRD-v0.1.md`
**Implementation plan section:** §2.5

---

## Task

Author and run a one-off backfill script that creates ~50 governance entity records and ~70 reference edges representing the governance entity schema-design workstream itself. This is the proof-of-end-to-end test that the new entity types work against real content. Future backfill phases (prior workstreams, prior conversations, prior payloads) are deferred to follow-on planning items authored in Slice F.

## Read this first

1. `crmbuilder/CLAUDE.md`.
2. `PRDs/product/crmbuilder-v2/governance-entity-PRD-v0.1.md` §3.6 (PI-022 refinement; Phase 1 record-by-record plan).
3. `PRDs/product/crmbuilder-v2/governance-entity-implementation-plan.md` §2.5 (this slice's deliverables, target record counts, verification queries).
4. PI-022's database record (from `db-export/planning_items.json`) — the planning item this slice partially discharges.
5. The eight close-out payload files at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_047.json` through `ses_055.json` — source data for backfilled close_out_payload records and reconstructable deposit_event back-references.
6. The eight kickoff prompts: `governance-entity-schema-workstream-establishing-kickoff.md`, `schema-design-kickoff-workstream.md`, `schema-design-kickoff-conversation.md`, `schema-design-kickoff-reference-book.md`, `schema-design-kickoff-work-ticket.md`, `schema-design-kickoff-close-out-payload.md`, `schema-design-kickoff-deposit-event.md`, `governance-schema-build-planning-kickoff.md` — source files for the eight work_ticket records.
7. The seven schema-spec reference documents at `governance-schema-specs/` plus the workstream master plan, the spec guide, this PRD, and the implementation plan — source files for the ten reference_book records.

## Deliverables

Per implementation plan §2.5:

1. **One-off backfill script** at `crmbuilder-v2/scripts/backfill_governance_phase_1.py`:
   - Reads from db-export snapshots and close-out payload files.
   - Creates records in this fixed order (to satisfy edge-required-at-terminal rules):
     1. WS-001 workstream record (`_status = 'in_flight'` for now; Slice F transitions to `complete` after closeout session lands).
     2. RB-001 through RB-010 reference_book records (with per-version rows for RB-005 and RB-007 which have two versions each).
     3. WT-001 through WT-008 work_ticket records at `_status = 'drafted'` initially (transition to `consumed` after the conversation edge is in place — see step 6).
     4. CONV-001 through CONV-008 conversation records at `_status = 'in_flight'` initially (transition to `complete` after edges in place — see step 7). Each carries `conversation_belongs_to_workstream` to WS-001 and `conversation_succeeds_conversation` to its predecessor (skip for CONV-001).
     5. SES record edges: for each conversation, create `conversation_records_session` edge to the matching SES record.
     6. WT consumption edges: for each conversation, create `conversation_opens_against_work_ticket` edge from CONV-NNN to WT-NNN. Then transition each WT to `consumed`.
     7. CONV completion: transition each CONV to `complete`.
     8. COP-001 through COP-008 close_out_payload records at `_status = 'ready'` initially. Each carries `close_out_payload_produced_by_conversation` edge to its CONV.
     9. DEP-001 through DEP-008 deposit_event records. POSTing each will atomically transition the matching COP to `applied` via the access-layer logic (Slice A). For DEP-001 through DEP-007, `_outcome = 'success'`, `_log_file_path = 'PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN-historical.log'` (with one-line placeholder note in the file), `_apply_context.runner = "backfill_script"`, `_records_summary` reconstructed from the payload's section counts, `wrote_record` back-references created for each record the payload created (per the SES, decisions, planning_items, references arrays in the payload file).
     10. DEP-008 special-case: this is the apply of SES-055 itself, which already ran via the modified apply script. The backfill skips creating DEP-008 if it already exists in the database (HTTP 409); otherwise creates with `_outcome = 'success'`, the real `_log_file_path`, `runner = "claude_code"`.
     11. RB-001 master-plan edge: `workstream_planned_in_reference_book` from WS-001 to RB-001.
   - Idempotent on re-run (HTTP 409 SKIPs).
   - Writes its stdout to `deposit-event-logs/backfill-phase-1.log`.

2. **Backfill verification step** at script's end:
   - GET each entity-type list endpoint; verify counts.
   - GET references with various `?relationship_kind=` filters; verify edge counts.
   - Print summary table.

## Working style

- The script is single-purpose and one-off; not part of the application's runtime path.
- Use the same envelope-unwrapping pattern as `apply_close_out.py`.
- Title and description fields auto-generated where possible from session record content; manual review acceptable before commit.
- Run the script; verify counts; commit. The backfill files (the script itself, the historical log placeholders) are committed.

## Pre-flight

```
curl -sf http://127.0.0.1:8765/health
uv run pytest tests/crmbuilder_v2/ -v
git pull --rebase origin main
```

## Acceptance gate

Per implementation plan §2.5:

- ~50 records created: 1 workstream, 8 conversations, 8 work_tickets, 8 close_out_payloads, 8 deposit_events, 10 reference_books, ~14 reference_book_versions, ~70 reference edges.
- All eight conversations chained correctly via `conversation_succeeds_conversation`.
- Each conversation carries its membership and session edges.
- Each work_ticket consumed; each close_out_payload applied; each deposit_event recorded.
- RB-005 and RB-007 each carry two version rows.
- WS-001's master-plan edge inbound from RB-001 exists.
- Re-running the script is idempotent.
- Desktop UI shows the new records correctly across all six panels.
- `uv run pytest tests/crmbuilder_v2/` green.

## Out of scope

- Phases 2 and beyond (prior workstreams, prior conversations, prior payloads). Deferred to follow-on planning items authored in Slice F.
- WS-001 transition to `complete` — done in Slice F after closeout session lands.
- Documentation updates — Slice F.
