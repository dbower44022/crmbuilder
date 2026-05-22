# CLAUDE-CODE-PROMPT — v0.7 Execute All Slices End-to-End

**Last Updated:** 05-22-26 17:30
**Operating mode:** DETAIL with no per-slice confirmation gate
**Series:** v2-ui-v0.7
**Status:** Ready to execute

---

## Purpose

Execute all six v0.7 governance entity release slices (A through F) sequentially in one Claude Code session, without prompting Doug between slices. Doug reviews everything at the end.

The six slices are individually documented at:

- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-A-schema-and-access.md`
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-B-api-endpoints.md`
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-C-ui-panels.md`
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-D-apply-script-and-deposit-events.md`
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-E-pi022-backfill.md`
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-F-closeout.md`

This orchestration prompt drives them in order; each slice's prompt remains the authoritative source for its deliverables and acceptance criteria.

The integrating PRD is at `PRDs/product/crmbuilder-v2/governance-entity-PRD-v0.1.md`; the implementation plan at `PRDs/product/crmbuilder-v2/governance-entity-implementation-plan.md`.

---

## Operating discipline

### Do not stop and prompt unless a disaster condition is hit

Slice work that progresses normally — adding files, editing files, running tests that pass, committing intermediate work, encountering style choices the slice prompt leaves open, getting HTTP 409 SKIP responses from apply scripts, encountering linting warnings — proceeds **without stopping**. Use the judgement implied by the slice prompts and the spec documents they reference; pick the most consistent path with established precedents (v0.4 methodology entities, v0.5 engagement-management, v0.6 styling); document choices in code comments where they're consequential.

### Disaster conditions (stop and report)

Stop and write a disaster report to chat if **any** of these conditions hit and cannot be resolved by retrying or making a reasonable scope-bounded choice:

1. **Migration failure.** Alembic migration fails to apply forward, or fails to reverse cleanly when tested. Tests that exercise the migration boundary fail and the failure mode is not addressed by re-reading the spec.
2. **Persistent test failures.** Slice acceptance tests fail and the failure cannot be resolved within one retry. Or **regression**: an existing test that was green before the slice started is now failing.
3. **API persistently unavailable.** `curl -sf http://127.0.0.1:8765/health` returns non-200 across three retries spaced 5 seconds apart, and restarting the API (`uv run crmbuilder-v2-api &`) does not resolve it.
4. **Git conflict requiring human resolution.** `git pull --rebase origin main` produces a conflict that cannot be resolved by re-reading the changed files and applying obvious merge logic.
5. **Schema or vocabulary conflict.** A new entity type, relationship kind, identifier prefix, or field collides with an existing one not anticipated by the specs.
6. **Cross-spec contradiction.** During implementation, discover that two specs disagree on a substantive point not flagged in the SES-055 cross-spec consistency check; the contradiction blocks coherent implementation.
7. **Data corruption or inconsistent state.** Records appear in the database that contradict the schema (e.g., a deposit_event with `_updated_at` not null after an attempted PUT). Database-level integrity violation.
8. **PI-022 backfill produces inconsistent counts.** Slice E's verification queries return record counts substantially off from the expected ~50 records / ~70 references / ~14 versions and the discrepancy is not explained by HTTP 409 SKIPs.
9. **A step that should be idempotent isn't.** Re-running the same command produces different outcomes (other than expected 409 SKIPs).
10. **Any error you encounter that you cannot confidently resolve within one retry without changing the slice's scope or contract.**

### What is **not** a disaster

- HTTP 409 SKIPs from apply or backfill scripts (expected idempotency behavior).
- Test additions needing to be authored (write them; that's part of the slice work).
- Choices about variable names, function organization, file structure within a module, comment style — make them per existing precedents and continue.
- Minor linting warnings.
- Decisions about UI icon choices, status badge colors, or other cosmetic details — match v0.4 / v0.5 / v0.6 patterns.
- Acceptable scope expansions clearly implied by spec content but not explicitly enumerated in a slice prompt (e.g., a missing import the access-layer code obviously needs).

### Per-slice cadence

For each slice in order (A, B, C, D, E, F):

1. **Read the slice prompt fully** (path listed above).
2. **Read the slice's referenced documents** (per its "Read this first" section).
3. **Verify pre-flight passes:** API healthy, `uv run pytest tests/crmbuilder_v2/` green (modulo the new tests this slice will add — those don't exist yet at slice start).
4. **Execute the slice's deliverables.** Use multiple commits per slice if the slice naturally decomposes (e.g., Slice A: migration commit, then vocab.py commit, then per-repository commits, then test commit). Smaller commits are better for Doug's review.
5. **Run the slice's acceptance gate.** `uv run pytest tests/crmbuilder_v2/` green; spec-specific behavioral verifications per the slice prompt's "Acceptance gate" section pass.
6. **Commit any remaining work** (anything not already committed during step 4).
7. **Do NOT push.** Doug pushes after reviewing all slices.
8. **Move to the next slice** without stopping unless a disaster condition has fired.

### Commit message convention

Each commit follows the existing repo convention. Slice-internal commits use prefixes like:

```
v0.7 Slice A: <short description>

<body explaining the change, referencing the spec section it implements>
```

The final commit of each slice should be tagged in its message with `Slice A complete.` (or B, C, etc.) for easy navigation in `git log`.

### Push convention

Do **not** push during execution. Doug pushes manually after reviewing the local commit history. The commits build up on `main` locally; the orchestration prompt does not affect the remote.

If you encounter a state where you genuinely cannot proceed without pushing first (very unusual; would only happen if some external tool requires a remote artifact), stop and report.

---

## Pre-flight (run once at the start)

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder || cd ~/crmbuilder
git pull --rebase origin main
cd crmbuilder-v2

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start it: uv run crmbuilder-v2-api &

# Test suite baseline
uv run pytest tests/crmbuilder_v2/ -v

# Verify both predecessor close-outs have been applied
curl -sf http://127.0.0.1:8765/sessions/SES-054 >/dev/null && echo "SES-054 present"
curl -sf http://127.0.0.1:8765/sessions/SES-055 >/dev/null && echo "SES-055 present"
# If either returns 404, STOP and apply them first via their respective apply prompts:
#   CLAUDE-CODE-PROMPT-apply-close-out-ses-054.md
#   CLAUDE-CODE-PROMPT-apply-close-out-ses-055.md
# Both must be applied before Slice E references them in the Phase 1 backfill.

# Confirm we're at the v0.6 baseline
grep '__version__' src/crmbuilder_v2/__init__.py
# Expected: __version__ = "0.6.0"
```

If pre-flight fails on any of the above, **stop and report** — this is a disaster condition (#3 API unavailable, or missing predecessor data).

---

## Execution sequence

### Slice A — Schema, migrations, vocab.py, access layer

**Prompt:** `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-A-schema-and-access.md`

Execute the slice per its prompt. Acceptance gate per the prompt's "Acceptance gate" section. Reference: PRD §3.1, §3.2, §4.1, §4.2, §4.3; implementation plan §2.1.

Expected commits at slice end (suggested decomposition; adjust as natural):

1. `v0.7 Slice A: migration 0011 — extend CHECK constraints and add reference_identifier column`
2. `v0.7 Slice A: migration 0011 — create seven new entity tables`
3. `v0.7 Slice A: vocab.py — 8 new relationship kinds, 6 new entity types, _kinds_for_pair clauses`
4. `v0.7 Slice A: ORM models for the seven new tables and Reference.reference_identifier`
5. `v0.7 Slice A: workstreams repository + tests`
6. `v0.7 Slice A: conversations repository + tests`
7. `v0.7 Slice A: reference_books repository (parent + child versions) + tests`
8. `v0.7 Slice A: work_tickets repository + tests`
9. `v0.7 Slice A: close_out_payloads repository (first-success-transitions semantics) + tests`
10. `v0.7 Slice A: deposit_events repository (atomic POST, lazy close_out_payload creation) + tests`
11. `v0.7 Slice A: cross-entity integration tests. Slice A complete.`

Move to Slice B without prompting.

### Slice B — REST API endpoints

**Prompt:** `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-B-api-endpoints.md`

Reference: PRD §3.3; implementation plan §2.2. Note the `/references` filter API gap fix (per commit `dcb7377`) is part of this slice.

Expected commits at slice end:

1. `v0.7 Slice B: workstreams router + tests`
2. `v0.7 Slice B: conversations router + tests`
3. `v0.7 Slice B: reference_books router with versions sub-endpoints + tests`
4. `v0.7 Slice B: work_tickets router + tests`
5. `v0.7 Slice B: close_out_payloads router + tests`
6. `v0.7 Slice B: deposit_events router (POST + GET only, HTTP 405 for write methods) + tests`
7. `v0.7 Slice B: /references filter parameter fix + tests`
8. `v0.7 Slice B: router registration in api app. Slice B complete.`

Move to Slice C without prompting.

### Slice C — Desktop UI panels

**Prompt:** `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-C-ui-panels.md`

Reference: PRD §3.4; implementation plan §2.3. Note the sidebar append-no-sub-grouping policy from DEC-163, and the deposit_event panel's read-only audit-log shape.

Expected commits at slice end:

1. `v0.7 Slice C: workstreams panel + dialog + tests`
2. `v0.7 Slice C: conversations panel + dialog + tests`
3. `v0.7 Slice C: reference_books panel with version-history section + dialog + tests`
4. `v0.7 Slice C: work_tickets panel + dialog + tests`
5. `v0.7 Slice C: close_out_payloads panel + dialog + tests`
6. `v0.7 Slice C: deposit_events panel (read-only audit log, no dialogs) + tests`
7. `v0.7 Slice C: sidebar integration — six new entries appended to Governance group. Slice C complete.`

Move to Slice D without prompting.

### Slice D — apply_close_out.py modifications + deposit-event-logs/

**Prompt:** `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-D-apply-script-and-deposit-events.md`

Reference: PRD §3.5; implementation plan §2.4. Note: the modified apply script lazy-creates the close_out_payload record when its target identifier doesn't yet exist (per PRD §3.5).

Expected commits at slice end:

1. `v0.7 Slice D: deposit-event-logs/ directory with README and .gitkeep`
2. `v0.7 Slice D: apply_close_out.py — log file tee writer + records_summary capture`
3. `v0.7 Slice D: apply_close_out.py — atomic deposit_event POST as last step`
4. `v0.7 Slice D: tests for happy-path and failure-path apply runs. Slice D complete.`

Move to Slice E without prompting.

### Slice E — PI-022 Phase 1 retroactive backfill

**Prompt:** `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-E-pi022-backfill.md`

Reference: PRD §3.6; implementation plan §2.5. Note the eight-conversation, ten-reference-book Phase 1 scope and the idempotency requirement.

Expected commits at slice end:

1. `v0.7 Slice E: backfill_governance_phase_1.py — one-off script for the governance workstream's records`
2. `v0.7 Slice E: backfill executed — 1 workstream, 8 conversations, 8 work_tickets, 8 close_out_payloads, 8 deposit_events, 10 reference_books, ~14 version rows, ~70 references created`
3. `v0.7 Slice E: deposit-event-logs/dep_NNN-historical.log placeholders for backfilled records`
4. `v0.7 Slice E: backfill verification report. Slice E complete.`

Move to Slice F without prompting.

### Slice F — Docs, version bump, build closeout

**Prompt:** `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-F-closeout.md`

Reference: PRD §4.4, §4.5; implementation plan §2.6. Note: this is the final slice; it bumps the version to 0.7.0, updates documentation, transitions WS-001 to `complete`, authors the closeout session, and authors three follow-on planning items (PI-023, 024, 025).

Expected commits at slice end:

1. `v0.7 Slice F: __version__ bump to 0.7.0`
2. `v0.7 Slice F: README.md — v0.7 governance entity release bullet`
3. `v0.7 Slice F: CLAUDE.md — v0.7 subsection and deposit-event-logs/ note`
4. `v0.7 Slice F: WS-001 transitioned to complete`
5. `v0.7 Slice F: closeout payload at close-out-payloads/ses_NNN.json + apply prompt`
6. `v0.7 Slice F: follow-on planning items PI-023 (Phase 2), PI-024 (Phase 3), PI-025 (Phase 4) authored`
7. `v0.7 Slice F: build closeout applied via apply_close_out.py — deposit_event captured. Slice F complete. v0.7 ready to ship.`

(Note: the closeout session's identifier is the next available SES-NNN at Slice F execution time, fetched via `GET /sessions/next-identifier`. Slice F authors the payload with that identifier baked in.)

---

## On disaster

If a disaster condition fires:

1. **Commit any partial work** that's in a consistent state (don't leave the working tree dirty if it can be cleanly committed).
2. **Write a disaster report** in chat with:
   - Which slice was executing.
   - Which step within the slice.
   - The disaster condition number (from the list above).
   - The exact error message or test failure output.
   - The set of commits authored in this session (last `git log` since pre-flight).
   - What you tried (retries, alternate approaches).
   - Recommended recovery: rollback target, diagnostic commands Doug should run, files Doug should review.
3. **Do not push.** Doug reviews and decides.
4. **Stop.** Do not attempt to continue past the disaster.

---

## On completion (all six slices green)

When Slice F's final acceptance gate passes:

1. **Final test run:** `uv run pytest tests/crmbuilder_v2/ -v` — should be green.
2. **Final git log review:** `git log --oneline main..HEAD` or equivalent — should show ~40-50 commits, organized by slice.
3. **Write a completion report** in chat with:
   - Total commits authored.
   - Slice-by-slice summary (one bullet per slice naming the file count and major deliverables).
   - PI-022 Phase 1 backfill verification counts (record counts by entity type, edge counts by relationship kind).
   - The next-available session identifier (the closeout session's identifier).
   - Confirmation that `__version__` is `"0.7.0"`.
   - Reminder to Doug: review commits, then `git push origin main` to ship.
4. **Stop.** Do not push. Do not tag. Doug pushes and tags after review.

---

## Reference: Slice acceptance criteria are aggregated in the implementation plan

See `PRDs/product/crmbuilder-v2/governance-entity-implementation-plan.md` §4 ("Acceptance criteria summary") for the full release-level acceptance list. Each slice's prompt has its own per-slice acceptance gate; the release-level summary aggregates them.

---

*End of orchestration prompt.*
