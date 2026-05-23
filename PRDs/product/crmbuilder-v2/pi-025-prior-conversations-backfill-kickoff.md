# PI-025 prior-conversations backfill — kickoff

**Last Updated:** 05-23-26 22:30
**Status:** Kickoff — ready for a planning conversation to open against it once PI-024 has applied.
**Authored at:** the close of the PI-024 prior-workstreams backfill conversation (SES-059) per that kickoff's chain rule.
**Anticipated session at close:** SES-060 (subject to identifier rebasing if other conversations close between now and the open of PI-025; see "Identifier note" below).

---

## Purpose

PI-025 is Phase 3 of PI-022 (governance backfill). It backfills the **conversation entity records** for the sessions that pre-date PI-022 Phase 1 — and the edges that wire those conversation records to (a) the matching session records and (b) the parent workstreams settled in PI-024.

After PI-025 lands, every prior session in the CRMBUILDER engagement that belongs to a workstream has a conversation record. The audit-query "which sessions ran inside WS-NNN?" returns answers from data rather than from the workstream_description prose field.

---

## Read this first

- Read `crmbuilder/CLAUDE.md` for engagement context. Confirm with Doug at the open of the conversation.
- Read the PI-024 kickoff at `PRDs/product/crmbuilder-v2/pi-024-prior-workstreams-backfill-kickoff.md` for the surrounding backfill program shape and the discharge-Phase-2 framing.
- Read the conversation entity schema spec at `PRDs/product/crmbuilder-v2/governance-schema-specs/conversation.md` for required fields, lifecycle, and edge contracts. This is the canonical source for what a CONV record must carry.
- Read the Phase 1 precedent script at `crmbuilder-v2/scripts/backfill_governance_phase_1.py` for the conversation-creation pattern: lines 46–111 are the `_CONVERSATIONS` data shape and lines 380–420 are the create-and-transition flow.
- Skim the SES-059 close-out at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_059.json` for the three decisions PI-024 just settled (DEC-175 inventory, DEC-176 lifecycle-date strategy, DEC-177 master-plan bundling) — PI-025 inherits these and reuses the lifecycle-date strategy verbatim.

---

## Scope

### What this conversation backfills

- **Conversation records** for the prior sessions that belong to one of the seven backfilled workstreams (WS-001 through WS-007). Identifier range starts at CONV-009 (CONV-001 through CONV-008 were created by PI-022 Phase 1 for the governance entity schema-design workstream WS-001).
- **`conversation_records_session` edges** wiring each new CONV-NNN to its SES-NNN.
- **`conversation_belongs_to_workstream` edges** wiring each new CONV-NNN to its parent workstream (WS-001 through WS-007).
- **`conversation_succeeds_conversation` edges** as appropriate, forming the conversation-chain backbone within each workstream's arc.

### Inventory boundary

As of the time of this kickoff:

- Sessions present in CRMBUILDER: SES-001 through SES-057, with SES-028 absent (intentionally — earlier cleanup). 56 sessions.
- Sessions to be added by the queued close-outs: SES-058 (audit-v1.2 workstream — `close-out-payloads/ses_058.json` already pushed, pending apply) and SES-059 (PI-024 prior-workstreams backfill — `close-out-payloads/ses_059.json` already pushed, pending apply). After both apply, the total is 58 sessions ranging SES-001 through SES-059 with SES-028 absent.
- Sessions that already have CONV records via Phase 1: CONV-001 through CONV-008 are attached to SES-047, SES-048, SES-049, SES-050, SES-051, SES-052, SES-054, SES-055.
- Sessions needing CONV records in this phase: the remaining 50 sessions, comprising SES-001 through SES-046 (45 sessions, SES-028 absent), SES-053, SES-056, SES-057, SES-058, SES-059.

Of those 50, some did not occur inside any of the seven backfilled workstreams (WS-001 through WS-007). The audit-v1.2 workstream (which produced SES-053 and SES-058 and may have produced others) is excluded from PI-024's inventory per DEC-175 but may warrant its own workstream record before PI-025 runs — see the "Surface-and-settle" list below.

The exact session-to-workstream mapping is the conversation's first deliverable.

### Cross-engagement consideration (WS-006)

The CBM paper-test sessions (the ones that informed WS-006 Cleveland Business Mentors paper test) live in the **CBM engagement database**, not CRMBUILDER's. PI-025 must settle whether:

- **Option I:** Conversation records are authored in the CBM engagement (where the sessions live) with the `conversation_belongs_to_workstream` edge crossing engagement boundaries to WS-006 in CRMBUILDER. Requires the conversation entity schema to admit cross-engagement edges, which it may not.
- **Option II:** Conversation records are authored in CRMBUILDER engagement pointing to session records that live in CBM. Requires cross-engagement `conversation_records_session` edges.
- **Option III:** A pair of conversation records — one in each engagement — linked by a new relationship_kind (e.g., `conversation_mirrors_conversation_across_engagement`). Adds vocabulary but keeps every existing edge intra-engagement.
- **Option IV:** Defer the WS-006 conversation records entirely; mark WS-006 as the one workstream whose conversations are not backfilled, with a note pointing to the CBM engagement.

This decision is consequential (real downstream impact on query patterns; multiple options producing meaningfully different outcomes). It passes the two-part test and should be surfaced using the consequential-decision template.

### Other surface-and-settle questions for the conversation

These are flagged by the kickoff but **not** resolved here. The conversation should surface them as it works through the inventory:

1. **Audit-v1.2 workstream.** Should an eighth workstream record (WS-008 audit feature v1.2) be created before PI-025 wires conversations, so the audit-v1.2 sessions (at minimum SES-053 and SES-058) have a parent workstream to belong to? DEC-175 deferred this question — the audit-v1.2 effort is structurally a workstream by the kickoff's inclusion test (coherent purpose, multiple connected conversations, recognizable beginning/end with the v1.2 plan applied), but it was active and ongoing at the time PI-024 was scoped. Now that audit-v1.2 has closed (per the pushed ses_058.json), the answer may be different. If yes, a tight one-workstream-only backfill (WS-008 + applicable CONV records) should precede PI-025's main scope or fold in as a sub-step.
2. **Status of new conversation records.** Should every backfilled CONV record be born `complete` directly (Doug's status-as-`complete` POST path is supported per the workstream backfill precedent), or should the script use the Phase 1 two-step path (POST `in_flight` with `conversation_started_at`, then PATCH to `complete` with `conversation_completed_at` after wiring the session edge)? Two-step is more legible in the deposit-event log; one-step is faster. Phase 1 used two-step because it needed the session edge to land between POST and PATCH (per the work_ticket-consumed-requires-edge precedent); PI-025 may be able to use one-step if no analogous edge-required transition rule applies.
3. **Conversation-to-session cardinality.** Phase 1 wired 1 conversation per session. Are any prior sessions actually multiple conversations stacked into one session_record (e.g., a session that opened on one topic and pivoted to another)? Are any conversations spread across multiple sessions (e.g., a topic that ran across two days with two session records)? If either case appears in the inventory, PI-025 must extend the model — and possibly the conversation entity schema spec — before continuing. Default assumption: 1:1 unless the inventory surfaces a counterexample.
4. **`conversation_succeeds_conversation` chains.** Phase 1 chained CONV-001 through CONV-008 strictly sequentially (each succeeds the prior). PI-025 may need branched chains (two CONV records in WS-005 styling both succeed CONV-NNN in the v0.5 build-planning conversation; the slice A and slice B conversations within v0.4 may have run in parallel for some workstreams). Are succeeds-edges required between every conversation pair in a workstream, or are they optional and only authored where the chain is unambiguous?
5. **Source-document fields per CONV.** Phase 1's `_CONVERSATIONS` list carried `kickoff` path, `payload` path, and a `predecessor` string for the succeeds edge. PI-025's prior conversations don't all have a written kickoff document (the earliest sessions were ad-hoc continuations; many later ones used a prior session's `in_flight_at_end` field as the de facto kickoff). The conversation schema's required fields versus optional fields determines what PI-025 must source per CONV record. Confirm against the schema spec before drafting the inventory.

---

## Working pattern

Operating mode: **ARCHITECTURE** by project default. Switch to PROTOTYPE if and only if the conversation gets deep into vocabulary or schema-extension drafting that benefits from try-one-and-see; switch back to ARCHITECTURE before the close-out.

Same iteration shape as PI-024:
- One consequential decision at a time, presented using the consequential-decision template; terse approvals are sufficient.
- Routine choices decided and announced inline.
- Document approvals (the full inventory; the per-CONV name / purpose / description) presented as a block once before the apply prompt is drafted.

---

## Deliverable shape

Same triple-artifact close-out pattern as PI-024:

1. **`PRDs/product/crmbuilder-v2/close-out-payloads/ses_060.json`** — the close-out payload covering the planning conversation's session record plus any decisions it settles. Decisions to anticipate (subject to the conversation): the WS-006 cross-engagement read, the audit-v1.2 WS-008-or-not question, the conversation status-on-create decision, and the succeeds-chain policy.
2. **`PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-060.md`** — apply prompt for the close-out payload.
3. **`PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-025-prior-conversations-backfill.md`** — authors `crmbuilder-v2/scripts/backfill_pi_025_prior_conversations.py`, runs it, verifies counts, commits in two steps (script-file commit first, then regenerated db-export snapshots).

Mirror PI-024's script pattern: idempotent on re-run, HTTP 409 and 422-duplicate treated as already-present, stage list with reference_books-style structure for the data and per-stage logging.

---

## Identifier note

This kickoff anticipates SES-060 as the conversation's close. If other conversations close at SES-060 or beyond between the publishing of this kickoff and the opening of PI-025, the planning conversation will need to rebase to the next available session identifier and the next available DEC range. This pattern has happened twice now in the recent backfill program (SES-057 to SES-058 collision on the Code Change Lifecycle workstream conversation; SES-058 to SES-059 collision between audit-v1.2 and PI-024) — verify identifier heads at the start of the planning conversation.

---

## What's queued after this

- **PI-026** — Historical-applies-as-deposit_events backfill. Approximately 38 prior close-out payload JSON files (`close-out-payloads/ses_*.json` for ses_001 through ses_046, plus several follow-ups) become deposit_event records with `deposit_event_runner='backfill_script'` and `deposit_event_outcome='success'`. Each deposit_event reads its close_out_payload and authors `deposit_event_applies_close_out_payload` edges. PI-026 also surfaces the question of whether to retroactively author close_out_payload records for the close-outs that pre-date the close_out_payload entity (which was added in v0.7).
- **PI-023** — Workstream-state reconciliation utility at `crmbuilder/tools/workstream_reconcile.py`. Reads the populated workstream / conversation / session / close_out_payload / deposit_event graph after PI-024 / 025 / 026 land and verifies internal consistency. Reports orphan sessions (no CONV), orphan CONVs (no workstream), CONVs whose succeeds chain doesn't form a DAG, workstreams whose session_date range disagrees with conversation_completed_at extremes, and any other invariant violations.

PI-023 closes the PI-022 governance-backfill program.

---

## Out of scope (explicit)

- Conversation records for sessions that don't belong to any workstream (the orphan-session case). If the inventory surfaces orphan sessions, document them in the SES-060 close-out's `in_flight_at_end` and defer their CONV authoring to a follow-up phase or omit them permanently.
- The `conversation_mirrors_conversation_across_engagement` relationship_kind (if Option III of the WS-006 cross-engagement decision wins). PI-025 may decide to add this kind to the vocabulary, but the schema spec addition itself — including the inverse-kind question and the CHECK-constraint update — is a vocab.py edit that should be carried out as a separate Claude Code prompt against the codebase before PI-025's backfill script runs.
- Resolution of PI-024 itself. PI-024's resolution depends on the resolves mechanism that PI-029 / PI-030 (Code Change Lifecycle workstream) will ship. Until then PI-024 stays Open even after PI-025 lands.
