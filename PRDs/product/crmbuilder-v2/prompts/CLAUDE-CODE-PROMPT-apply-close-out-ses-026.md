# CLAUDE-CODE-PROMPT-apply-close-out-ses-026

**Last Updated:** 05-16-26 19:00
**Operating mode:** detail
**Series:** apply-close-out
**Status:** Ready to execute
**Companion conversation:** Claude.ai v0.5 Conversation 1 on 05-16-26 that produced `PRDs/product/crmbuilder-v2/multi-engagement-architecture.md` and `PRDs/product/crmbuilder-v2/methodology-schema-specs/engagement.md` (both committed alongside this prompt and the payload file by Claude at session close per the in-sandbox close-out convention).

---

## Purpose

Apply the SES-026 close-out payload to the local v2 governance database. All operations are pure POSTs handled by the standard `apply_close_out.py` script — no PATCH step is needed because PI-017 is a brand-new planning item rather than a modification of an existing one. This is simpler than the SES-025 apply prompt (which patched PI-001 in addition to running the standard payload).

Net effect on the v2 database after this prompt completes:

- **Session.** SES-026 (v0.5 Conversation 1 record — settled the ten architectural questions from the workstream plan §6, produced multi-engagement-architecture.md and engagement.md, queued v0.5 Conversation 2 (build planning) as the next conversation).
- **Decisions.** Nine new decisions DEC-078 through DEC-086:
  - DEC-078: engagement discovery model (bootstrap meta DB)
  - DEC-079: per-engagement DB file location (engine repo, conventional paths)
  - DEC-080: active-engagement state persistence (JSON file + last_opened_at column + in-memory context)
  - DEC-081: v0.5 API+MCP server model (one process per engagement) + committed multi-tenant migration
  - DEC-082: identifier scope (per-engagement governance/methodology; engagement scoped to meta DB)
  - DEC-083: migrations across engagements (lazy at engagement-open)
  - DEC-084: dogfood migration (one-shot explicit)
  - DEC-085: per-engagement exports (split via engagement_export_dir field)
  - DEC-086: engagement entity schema, lifecycle, and API surface
- **Planning items.** PI-017 (multi-tenant API + MCP migration; trigger = prototype-to-production transition; anchored by DEC-081).
- **References.** Nine `decided_in` references (DEC-078 → SES-026, DEC-079 → SES-026, ..., DEC-086 → SES-026).

This is a one-shot apply prompt. The underlying script is idempotent (HTTP 409 conflict is treated as already-present and continues), so re-running is safe if interrupted. Post-apply this prompt should not be re-run as a matter of routine.

---

## Project context

Per DEC-004, the v2 database is the source of truth for all v2 artifacts; per DEC-008, the JSON snapshots under `PRDs/product/crmbuilder-v2/db-export/` are renders, not authored copies. Records are inserted via the v2 access layer (HTTP POST to `http://127.0.0.1:8765`), which transactionally regenerates the JSON snapshots.

The `apply_close_out.py` script reads a sectioned JSON payload and POSTs each section in fixed order: `session` → `decisions` → `planning_items` → `references`. SES-026's payload uses all four sections.

Current expected pre-state (immediately after SES-025's apply landed and the v0.5 Conversation 1 deliverable commit landed):

- `decisions.json` snapshot ends at **DEC-077** (last from SES-025 close-out)
- `planning_items.json` snapshot ends at **PI-016** (last v0.4 closeout PI; PI-001 description was PATCHed at SES-025 but no new PIs were authored at SES-025)
- `sessions.json` snapshot ends at **SES-025** (v0.5 orientation closeout)
- One payload pending in `close-out-payloads/`: `ses_026.json`, not yet applied
- HEAD on `main` is at the v0.5 Conversation 1 deliverable commit authored by Claude at session close (the four-file commit that includes this apply prompt and the payload it applies)

If the actual snapshot state is different (more advanced — e.g., SES-026 already applied), the apply script's 409-handling absorbs the difference. The pre-flight verification step calls this out either way.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root (the directory containing `CLAUDE.md`, `crmbuilder-v2/`, and `PRDs/`).

2. **Confirm `git status` is clean.** If there are uncommitted changes, stop and report to Doug before proceeding. The post-apply snapshot regeneration produces tracked-file changes; starting from a clean state ensures those changes are isolated and committable as one unit.

3. **Confirm git identity is set.**

   ```bash
   git config user.name "Doug Bower"
   git config user.email "dbower44022@users.noreply.github.com"
   ```

4. **Pull latest from origin:**

   ```bash
   git pull --rebase origin main
   ```

   Stop and report if there are conflicts. Expected HEAD includes the v0.5 Conversation 1 deliverable commit (the one that introduced this apply prompt and the payload file alongside the two deliverable documents).

5. **Confirm the payload file exists:**

   ```bash
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_026.json
   ```

   Stop if missing.

6. **Confirm the v2 API is running:**

   ```bash
   curl -sf http://127.0.0.1:8765/decisions >/dev/null && echo "API up" || echo "API DOWN"
   ```

   If the API is not running, ask Doug to start it (`cd crmbuilder-v2 && uv run crmbuilder-v2-api &`) before proceeding. Do not attempt to start it yourself — the API runs in the foreground in Doug's shell session.

7. **Capture pre-state for verification.** Record the current highest identifier in each entity type:

   ```bash
   curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys, json; d=json.load(sys.stdin)['data']; print('Latest DEC:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"
   curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys, json; d=json.load(sys.stdin)['data']; print('Latest PI:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"
   curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys, json; d=json.load(sys.stdin)['data']; print('Latest SES:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"
   curl -s http://127.0.0.1:8765/references | python3 -c "import sys, json; refs=json.load(sys.stdin)['data']; print('Refs total:', len(refs))"
   ```

   Expected pre-state: `DEC-077`, `PI-016`, `SES-025`, and refs total = 80 (the 77 prior + 3 from SES-025 close-out). Report the four values back so the post-apply step has a clear baseline.

---

## Workflow

### Step 1 — Apply SES-026 close-out payload

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_026.json
cd ..
```

Expected output: each record reports created (HTTP 201) or skipped (HTTP 409 already present). The script exits 0 on full success. Stop and report if it exits non-zero.

After this step:

- Sessions snapshot should contain SES-026 (latest SES becomes `SES-026`).
- Decisions snapshot should contain DEC-078 through DEC-086 (latest DEC becomes `DEC-086`; 9 new decisions).
- Planning items snapshot should contain PI-017 (latest PI becomes `PI-017`; 1 new PI).
- Nine new `decided_in` references should exist (DEC-078 → SES-026, DEC-079 → SES-026, ..., DEC-086 → SES-026). Refs total grows by 9.

### Step 2 — Verify post-state

Confirm the expected records exist via direct API queries:

```bash
# All 9 new decisions
for id in DEC-078 DEC-079 DEC-080 DEC-081 DEC-082 DEC-083 DEC-084 DEC-085 DEC-086; do
  curl -sf http://127.0.0.1:8765/decisions/$id >/dev/null && echo "$id OK" || echo "$id MISSING"
done

# The new session
curl -sf http://127.0.0.1:8765/sessions/SES-026 >/dev/null && echo "SES-026 OK" || echo "SES-026 MISSING"

# The new planning item
curl -sf http://127.0.0.1:8765/planning-items/PI-017 >/dev/null && echo "PI-017 OK" || echo "PI-017 MISSING"

# References — confirm all 9 decided_in references exist and count delta is correct
curl -s http://127.0.0.1:8765/references | python3 -c "
import sys, json
refs = json.load(sys.stdin)['data']
print('Refs total:', len(refs))
expected = [('DEC-078','SES-026'), ('DEC-079','SES-026'), ('DEC-080','SES-026'),
            ('DEC-081','SES-026'), ('DEC-082','SES-026'), ('DEC-083','SES-026'),
            ('DEC-084','SES-026'), ('DEC-085','SES-026'), ('DEC-086','SES-026')]
for src, tgt in expected:
    found = any(r['source_id']==src and r['target_id']==tgt for r in refs)
    print(f'{src} -> {tgt}: {found}')
"
```

All decision, session, and PI checks should report `OK`. All nine reference-existence checks should report `True`. Refs total should be 80 + 9 = 89 (or higher if intervening writes have landed; report any anomaly).

Then confirm the JSON snapshots were regenerated:

```bash
git status PRDs/product/crmbuilder-v2/db-export/
```

Expected modifications: `decisions.json`, `planning_items.json`, `sessions.json`, `references.json`, and `change_log.json`. If any of these are unexpectedly unchanged or unexpectedly absent from the diff, the export hook may have failed — stop and report before committing.

### Step 3 — Commit

Single commit covering all snapshot regenerations:

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git status   # confirm only db-export changes are staged
git commit -m "v2: apply SES-026 close-out payload

Inserts:
- SES-026 (v0.5 Conversation 1 — settled the ten architectural
  questions from the workstream plan; produced
  multi-engagement-architecture.md and engagement.md; queued
  v0.5 Conversation 2 build planning as the next conversation)
- DEC-078 (engagement discovery: bootstrap meta DB at
  crmbuilder-v2/data/engagements.db)
- DEC-079 (per-engagement DB file location: engine repo,
  conventional paths derived from engagement_code)
- DEC-080 (active-engagement state: JSON file for live state +
  engagements.last_opened_at column for ordering + in-memory
  ActiveEngagementContext mirroring v1's pattern)
- DEC-081 (v0.5 API and MCP server model: one process per
  engagement, kill-relaunch on switch; committed migration
  to multi-tenant single-process server at v2's prototype-
  to-production transition)
- DEC-082 (identifier scope: per-engagement for governance/
  methodology identifiers; engagement identifiers scoped to
  the meta DB)
- DEC-083 (migrations across engagements: lazy at engagement-
  open via run_engagement_migrations helper mirroring v1's
  pattern)
- DEC-084 (dogfood migration: one-shot explicit migration
  moves v2.db to engagements/CRMBUILDER.db at v0.5 first
  launch; idempotent on rerun)
- DEC-085 (per-engagement exports: split via nullable
  engagement_export_dir field on the meta DB engagement
  record)
- DEC-086 (engagement entity schema, lifecycle, and API
  surface: ENG-NNN identifier; ten fields including
  engagement_code mirroring v1's Client.code constraint;
  active/paused/archived lifecycle with free transitions;
  standard endpoint set served from the meta DB; no activate
  endpoint; UI shape deferred to Conversation 2)
- PI-017 (multi-tenant API and MCP migration; trigger =
  prototype-to-production transition; anchored by DEC-081)
- 9 decided_in references (DEC-078..086 → SES-026)

Snapshot regeneration only — payload file is unchanged.
The standard apply script is idempotent on the 409 path.
This commit captures the resulting db-export state for git
tracking.

After this apply lands, v0.5 Conversation 2 (build planning)
opens in a fresh Claude.ai chat against a kickoff document
Doug authors. Status remains 'v0.4 complete' until v0.5
actually ships."
```

Do **not** push. Doug pushes per the project convention. (This apply prompt runs in Doug's local terminal via Claude Code; the in-sandbox push convention from session close does not apply here.)

### Step 4 — Report

Print a short summary of what was applied:

- Number of decisions created vs skipped (409) — expected 9 created
- Number of sessions created vs skipped — expected 1 created
- Number of planning items created vs skipped — expected 1 created
- Number of references created vs skipped — expected 9 created
- The commit SHA
- A reminder that the commit needs to be pushed by Doug
- An explicit note that this apply closes the v0.5 Conversation 1 work and the next conversation to open is v0.5 Conversation 2 (build planning), opened in a fresh Claude.ai chat against a kickoff document Doug authors.

---

## Error handling

- **Standard apply script exits non-zero on a non-409 error.** Stop, do not commit, report the full script output to Doug. The most likely causes are API not running, payload file malformed, or a validation error at the API layer.

- **Snapshot not regenerated.** The export hook in the access layer may have failed silently. Stop, do not commit. Doug investigates by checking the API server logs.

- **Pre-state already past SES-026.** If `Latest SES` from the pre-flight is already `SES-026` or later, the work has already been applied. Report this finding; do not run the apply again (still safe given idempotency, but unnecessary).

- **Pre-state earlier than SES-025.** If `Latest SES` from the pre-flight is `SES-024` or earlier, the SES-025 closeout records may not have all landed. Stop and report to Doug — the prerequisite work is missing, and this prompt should not run until SES-025 is fully applied.

- **`git status` not clean at start.** Stop and report. Do not stash. Doug decides how to handle the uncommitted changes before re-running.

- **A specific decision verification fails (e.g., DEC-083 returns 404 but the others succeed).** Stop, do not commit. The apply script may have aborted partway through. Doug investigates the partial-state and may need to manually complete or rerun.

---

## What this prompt does NOT do

- Does not push the commit. Doug pushes (this prompt runs in Doug's local terminal).
- Does not modify the payload file. It is a read-only input.
- Does not modify the apply script. The script is generic; per-payload variation is in the payload file itself.
- Does not author additional decisions, planning items, or sessions beyond what the payload file contains.
- Does not write a status update. Release status remains `"v0.4 complete"` until v0.5 actually ships; v0.5 Conversation 1 is an architecture+schema conversation that does not change shipped state.
- Does not open v0.5 Conversation 2. That is a separate Claude.ai chat Doug opens against a build-planning kickoff document.

---

*End of prompt.*
