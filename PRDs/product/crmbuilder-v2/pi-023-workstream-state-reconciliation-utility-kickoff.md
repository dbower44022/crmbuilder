# PI-023 workstream-state reconciliation utility — kickoff

**Last Updated:** 05-24-26 00:35
**Status:** Kickoff — ready for a planning conversation to open against it once SES-068 (the PI-026 supersession close-out at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-068.md`) has applied. PI-029 slice B's SES-067 apply has already landed (commit `ffd7ea2`); the SES-068 apply is the only outstanding gate.
**Authored at:** the close of the PI-026 supersession conversation (SES-068, commit `814a05c`) per the PI-022 program's chain rule.
**Anticipated session at close:** SES-069 (subject to identifier rebasing if other conversations close between now and the open of PI-023; see "Identifier note" below).

---

## Purpose

PI-023 is the **closing phase** of PI-022 (governance backfill). It builds the **workstream-state reconciliation utility** — a Python script that runs at the pre-flight of any future close-out conversation and detects **git-vs-database state drift** before the conversation does any work against potentially-drifted state.

PI-024, PI-025, and PI-026 produced the backfilled governance graph. PI-023 builds the tool that confirms the graph matches the close-out JSON files on disk and surfaces any drift up front rather than as a mid-conversation apply-time discovery (the kind that forced the SES-066 → SES-068 rebase chain and the four parallel-sandbox identifier collisions in the recent backfill program).

After PI-023 lands, the standard pre-flight stanza for any future close-out conversation includes a `reconcile` invocation. Drift detected at pre-flight stops the conversation at the door; drift detected during the conversation forces rebase. The cost shift is one-way.

PI-023's close-out is the **terminal close-out of the PI-022 program**. No successor kickoff is authored at PI-023's close; the next conversation is at Doug's discretion.

---

## Read this first

- Read `crmbuilder/CLAUDE.md` for engagement context. Confirm with Doug at the open of the conversation.
- Read the SES-068 close-out at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_068.json` for the DEC-215 supersession context and the two surfaced planning items (PI-046 vocab contradiction, PI-047 ses_030 duplicate). These are the canonical examples of known data-quality artifacts that PI-023's allowlist must cover.
- Read the three predecessor kickoffs to understand the full backfilled-graph state:
    * `PRDs/product/crmbuilder-v2/pi-024-prior-workstreams-backfill-kickoff.md` (workstream + reference_book + work_ticket records, Phase 2)
    * `PRDs/product/crmbuilder-v2/pi-025-prior-conversations-backfill-kickoff.md` (conversation records, Phase 3)
    * `PRDs/product/crmbuilder-v2/pi-026-historical-applies-deposit-events-backfill-kickoff.md` (close_out_payload + deposit_event records, Phase 4)
- Skim DEC-197 in the SES-062 close-out — names the 16 sessions deliberately left orphan (no CONV parent). Those orphans are KNOWN data-quality artifacts that PI-023's reconciliation logic must classify as "expected" rather than "drift."
- Skim DEC-215 in SES-068 — the supersedes edge that overrides DEC-206. PI-023's reconciliation logic must traverse supersedes edges when computing "active decisions honored by records," otherwise it false-positives on the 24 PI-026 DEPs whose `records_summary.references=0` directly contradicts (now-superseded) DEC-206.
- Read the close_out_payload entity schema spec at `PRDs/product/crmbuilder-v2/governance-schema-specs/close_out_payload.md` and the deposit_event spec at `PRDs/product/crmbuilder-v2/governance-schema-specs/deposit_event.md` for the cross-check invariants the access layer already enforces at write time (so PI-023 doesn't redundantly check them).
- Read the relationship vocab at `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` (lines 211-380) for the canonical relationship kinds and the schema-vs-spec contradiction PI-046 names.
- Skim the four prior backfill scripts at `crmbuilder-v2/scripts/backfill_governance_phase_1.py`, `backfill_pi_024_prior_workstreams.py`, `backfill_pi_025_prior_conversations.py`, `backfill_pi_026_historical_applies_deposit_events.py` for the read-and-validate patterns; PI-023's utility is the symmetric counterpart (read-and-report rather than read-and-write).

---

## Scope

### What this conversation produces

The deliverable is a **read-only Python utility** — call it `reconcile.py` for the kickoff, the conversation can rename — that:

1. Reads the current state of the v2 governance database (mechanism TBD per surface-and-settle Q3 below).
2. Reads the close-out payload JSON files on disk in `PRDs/product/crmbuilder-v2/close-out-payloads/`.
3. Cross-references the two against a defined set of invariants (scope TBD per surface-and-settle Q2 below).
4. Reports drift findings in a defined output format (TBD per surface-and-settle Q1 below).
5. Respects a known-issue allowlist that classifies acknowledged data-quality artifacts as "expected" rather than "drift" (TBD per surface-and-settle Q4 below).

The utility is invoked at the pre-flight of any future close-out conversation. Its output is informational — it does NOT mutate the database or any files. Findings that warrant action are addressed by the conversation that ran the pre-flight (typically by surfacing a consequential decision or by halting before any other work begins).

### What this conversation does NOT produce

- **A general invariant-checking framework.** Schema-level invariants (records_summary equals edge count; status enum values valid; required edges present at write time) are already enforced at the access layer; PI-023 does not re-check them.
- **Database writes.** The utility is strictly read-only. Findings that should be recorded as governance records (e.g., a newly-discovered duplicate session that deserves a planning item) are surfaced by the operator of the pre-flight, not authored by the utility itself.
- **Automated remediation.** No "fix" mode. PI-023 detects drift; the operator decides what to do.
- **Workstream-level analytics beyond drift detection.** The planning item title says "workstream-state reconciliation"; the scope is reconciliation of git state vs database state, not reporting on workstream progress / velocity / etc.

### Out of scope (deferred)

- PI-046's vocab.py contradiction itself. PI-023 detects the schema-vs-spec asymmetry as drift and reports it; resolving it is PI-046's planning item.
- PI-047's ses_030 / ses_036 duplicate-session canonicality determination. PI-023 reports the duplicate as a known-acknowledged artifact (per its allowlist); resolving it is PI-047's planning item.
- A CI integration that runs reconcile.py on every push. Possible future work; not part of PI-023 v1.

---

## Surface-and-settle questions

The planning conversation should surface and settle these as consequential decisions (eight-element template). Defaults are proposed; the conversation may override.

### Q1 — Output format

What does `reconcile.py` produce on stdout when drift is detected?

- **Option A — structured plain text.** Human-readable summary with categorized findings, one per line, severity-prefixed (DRIFT / EXPECTED / INFO). Easy to skim; easy to copy-paste into a chat conversation; no programmatic parsing.
- **Option B — JSON.** Machine-readable structured output; can be consumed by tooling; harder for a human to read directly.
- **Option C — Markdown.** Sectioned report with headers per finding category; easy to file as a governance record (if PI-046 or PI-047 work surfaces the need); harder to skim quickly.
- **Option D — both A and B via a `--format` flag.** Default A for interactive use; B available for downstream tooling.

**Proposed default: A.** The utility is invoked at conversation pre-flight by humans (Doug at his terminal, or Claude.ai's tool invocations); structured plain text is the right primary format. If a downstream consumer needs JSON, add `--format json` later.

### Q2 — Invariant scope for v1

Which classes of git-vs-database drift does v1 detect?

- **Class 1 — file vs record presence.** Every `.json` file in `close-out-payloads/` has a corresponding COP record; every COP record's `file_path` points to an extant file. (Both directions.)
- **Class 2 — record-claims-vs-record-presence.** Every record a payload JSON claims it created (session, decisions, planning_items, references) exists in the database with the claimed identifier. Every record in the database has an `is_about` / `decided_in` / `wrote_record` edge back to the session that created it. (Detects: Phase 1's references-orphan; Option I's references-orphan after DEC-215; ses_030's 4 unresolvable references.)
- **Class 3 — decision-vs-records consistency.** Every Active decision's prescriptions match the records in the database (respecting supersedes-edge traversal). (Detects: DEC-206 vs DEC-215 — would correctly identify DEC-206 as superseded; would correctly identify DEC-215 as honored.)
- **Class 4 — workstream chain coherence.** Every workstream has a connected chain of conversations + work_tickets; no orphan conversations; no orphan sessions outside DEC-197's named list.
- **Class 5 — identifier-head continuity.** Identifier ranges (SES, DEC, PI, COP, DEP, REF, CONV, WT, WS, RB) have no unexplained gaps; gaps that exist are documented.

**Proposed default: Classes 1, 2, and 3.** These directly address the drift patterns that hit SES-066 → SES-068 (record-claims-vs-record-presence) and DEC-206 → DEC-215 (decision-vs-records consistency). Class 4 is workstream-analytics-adjacent and could be deferred. Class 5 is structural and largely caught by the schema CHECK constraints; less drift-detection value.

### Q3 — Database read mechanism

Does the utility read via the V2 REST API or directly from the `PRDs/product/crmbuilder-v2/db-export/` JSON snapshots?

- **Option A — REST API.** Canonical; always reflects current database state; slower (~12 endpoints to query for a full reconciliation); requires the API to be running.
- **Option B — db-export snapshots.** Faster (just file reads); doesn't require the API; but the snapshot's freshness depends on when the last write occurred. Stale snapshots produce stale findings.
- **Option C — both, with the API as fall-back.** Read from snapshots first; if a particular endpoint isn't in the snapshot or appears stale, query the API.

**Proposed default: A (REST API).** The freshness guarantee matters more than the speed cost. Reading via the API also ensures the utility's behavior matches what any other read consumer sees. The cost is ~1 second per reconciliation invocation, which is acceptable for a pre-flight check.

### Q4 — Known-issue allowlist

How does v1 distinguish "known data-quality artifact that's been deliberately accepted" from "new drift that needs investigation"?

- **Option A — hard-coded allowlist in the script.** Each known artifact is a constant: "Phase 1 references orphan: DEP-001..008 records_summary.references=0", "Option I references orphan: DEP-020..043 records_summary.references=0 per DEC-215", "ses_030/ses_036 duplicate: 4 unresolvable references in ses_030 per PI-047", etc. New artifacts require a code edit + commit.
- **Option B — config file allowlist.** A YAML or JSON file in the repo at `PRDs/product/crmbuilder-v2/reconciliation-allowlist.yaml` that the script reads. Each entry references a decision identifier or planning item that documents the acknowledgment. New artifacts require an allowlist commit + a governing decision/planning item.
- **Option C — database-driven allowlist.** Specific decisions or planning items tagged with a "this acknowledges a data-quality artifact" relationship; the script queries the database for them. New artifacts require a governance close-out — the same path that creates the acknowledging decision/PI.

**Proposed default: B (config file allowlist) with entries that reference the acknowledging decision / planning item.** Option A makes the script harder to audit (the allowlist is buried in code); Option C requires schema additions (a new relationship kind). Option B's config file at `reconciliation-allowlist.yaml` gives Doug and Claude.ai a single place to grep for "what's the current set of known-acknowledged artifacts," and each entry can carry a `decided_in: DEC-NNN` or `planning_item: PI-NNN` field pointing at the canonical record.

---

## Decide-and-announce items

These are below the two-part consequential threshold; settle inline during the planning conversation.

1. **Language and runtime.** Python 3.12+, matching the rest of the v2 toolchain. No additional dependencies beyond what `crmbuilder-v2/pyproject.toml` already declares (probably just `httpx` or `urllib` for REST calls and `PyYAML` for the allowlist).
2. **Script distribution.** Under `crmbuilder-v2/scripts/` alongside the four backfill scripts, named `reconcile.py` (subject to renaming during planning). Wired up as a console-script entry point in `pyproject.toml` if the conversation finds the script substantial enough — otherwise invoked directly via `uv run python scripts/reconcile.py`.
3. **Invocation shape.** `uv run python scripts/reconcile.py` with optional `--allowlist PATH`, `--format text|json`, `--base URL`. Exit code 0 if no drift (or all drift is allowlisted); 1 if unallowlisted drift detected.
4. **Allowlist file location and shape.** `PRDs/product/crmbuilder-v2/reconciliation-allowlist.yaml`. Each entry: `{ name, description, decided_in OR planning_item, drift_pattern: { class, identifier_range, expected_value } }`.
5. **Pre-flight integration.** The pre-flight section of all future close-out apply prompts (and Claude.ai planning conversations' opening orientation routine) gains a "run reconcile.py and confirm zero unallowlisted drift" step. Existing prompts are not retroactively edited; new prompts pick it up.
6. **CRMBuilder engagement only for v1.** The utility targets the CRMBUILDER engagement's database; CBM-engagement reconciliation is out of scope (CBM has its own close-out payloads but a different inventory pattern; a future PI could extend the utility to take an `--engagement` flag).
7. **No coverage of MN/MR/CR/FU domain payloads** (CBM PRDs) — those aren't v2 governance records and aren't in the reconciliation scope.

---

## Working pattern

Operating mode: **ARCHITECTURE** by project default. The conversation surfaces Q1-Q4 as consequential decisions using the eight-element template; settles decide-and-announce items inline; produces the close-out at the end with DEC records for each settled consequential question.

Same iteration shape as the backfill kickoffs:
- One consequential decision at a time; terse approvals sufficient.
- Routine choices decided and announced.
- The conversation's deliverables are the close-out payload (`ses_NNN.json`), the apply prompt, and a follow-on **Claude Code prompt** that authors `reconcile.py` and `reconciliation-allowlist.yaml` and runs the first reconciliation against the current database. The Claude Code prompt's structure mirrors the PI-026 backfill prompt's pattern (embed the full script source; author + run + commit + verify in two commits per the sandbox convention).

The first reconciliation invocation is itself the **acceptance test** — running `reconcile.py` against the current database after PI-024/025/026 land should produce an "expected" or "no drift" report once the allowlist is populated. If it surfaces an unexplained finding, the conversation surfaces a follow-on decision before declaring PI-023 complete.

---

## Identifier note

The PI-022 program's identifier-collision pattern has hit four times in recent backfills (PI-024 / PI-025 / PI-026 / SES-066-to-SES-068). PI-023's planning conversation should expect to rebase against any parallel-sandbox commits that land during its authoring window. The eventual structural fix is PI-032's Code Change Lifecycle reserve-at-apply-time identifier model; until then, every planning conversation runs `git fetch origin && git log HEAD..origin/main --oneline` before its first identifier claim, and re-runs the check before the close-out commit.

**Anticipated session identifier at PI-023's close: SES-069**, assuming no parallel-sandbox conversations close before PI-023's planning conversation opens. Anticipated decision range: DEC-216 onward (4 surface-and-settle questions → 4 DECs; plus any extras the conversation surfaces). Anticipated planning-item identifier: PI-048 onward (in case PI-023 surfaces additional planning items at its close). COP and DEP allocations are lazy at apply time.

If PI-029 slice B's SES-067 has been applied (commit `ffd7ea2`) and SES-068 has been applied, but other parallel-sandbox sessions have landed between now and PI-023's open, the identifier rebase chain applies.

---

## Out-of-scope for the planning conversation

- **Resolving PI-046 or PI-047.** PI-023's utility *detects* these as known-acknowledged artifacts via the allowlist; *resolving* them is each PI's own planning work.
- **Authoring the next kickoff after PI-023.** PI-023's close is the **terminal close-out of the PI-022 program**. The conversation's `in_flight_at_end` notes that PI-022's planning item moves from Open to Resolved (or some equivalent closing status); the next conversation after PI-023 closes is at Doug's discretion, not chain-prescribed by a successor kickoff.
- **CI integration.** Running `reconcile.py` on every git push is potentially valuable but out of scope; v1 is operator-invoked.
- **Cross-engagement reconciliation.** Doug's CBM engagement also has close-out payloads and a parallel governance graph; PI-023 v1 targets only CRMBUILDER. A future PI can extend if needed.

---

## Acceptance criteria

PI-023 is complete when:

1. `crmbuilder-v2/scripts/reconcile.py` exists, runs against the live database, and produces output matching the format settled in Q1.
2. `PRDs/product/crmbuilder-v2/reconciliation-allowlist.yaml` exists with entries covering at minimum: Phase 1 references orphan, Option I references orphan (per DEC-215), ses_030 / ses_036 duplicate (per PI-047), the 16 DEC-197 orphan sessions, and any other known artifacts the conversation surfaces.
3. The first invocation against the current database produces an "all drift is allowlisted" report (exit 0).
4. The script and allowlist are documented in the PI-023 close-out payload.
5. PI-022's planning item moves from Open to Resolved (or equivalent closing status) per the conversation's settlement on how to mark the program closed.
6. SES-069 (PI-023's session) is in the database; the close-out apply has landed.
