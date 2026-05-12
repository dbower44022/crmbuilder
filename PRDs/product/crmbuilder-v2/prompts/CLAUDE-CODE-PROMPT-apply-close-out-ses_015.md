# CLAUDE-CODE-PROMPT-apply-close-out-ses_015

**Last Updated:** 05-12-26 08:55
**Operating mode:** detail
**Series:** apply-close-out
**Status:** Ready to execute
**Companion conversation:** Claude.ai schema-design conversation on 05-12-26 that produced `PRDs/product/crmbuilder-v2/methodology-schema-specs/crm_candidate.md` v1.0 and `PRDs/product/crmbuilder-v2/ui-PRD-v0.4-build-planning-kickoff.md` v1.0 (both committed at `4d5863a`).

---

## Purpose

Apply the SES-015 close-out payload to the local v2 governance database. The payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_015.json` was authored during the crm_candidate schema-design conversation; this prompt runs `crmbuilder-v2/scripts/apply_close_out.py` against it.

Net effect on the v2 database after this prompt completes:

- **SES-015 records:** DEC-060..DEC-064 (crm_candidate schema decisions), PI-012 (crm_candidate metadata enums for v0.5+), SES-015 itself, plus 5 `decided_in` references linking the decisions to SES-015.

This is a one-shot apply prompt. The underlying script is idempotent (HTTP 409 conflict is treated as already-present and continues), so re-running is safe if interrupted, but post-apply this prompt should not be re-run as a matter of routine.

SES-015 is the final per-entity schema-design close-out in the methodology-entity-schema-design workstream. After this apply lands, the workstream's per-entity design portion is complete and the next workstream conversation is v0.4-build-planning per the kickoff at `PRDs/product/crmbuilder-v2/ui-PRD-v0.4-build-planning-kickoff.md`.

---

## Project context

Per DEC-004, the v2 database is the source of truth for all v2 artifacts; per DEC-008, the JSON snapshots under `PRDs/product/crmbuilder-v2/db-export/` are renders, not authored copies. Records are inserted via the v2 access layer (HTTP POST to `http://127.0.0.1:8765`), which transactionally regenerates the JSON snapshots.

The `apply_close_out.py` script reads a sectioned JSON payload and POSTs each section in fixed order: `session` → `decisions` → `planning_items` → `references`. This ordering matters because references in the payload target records created earlier in the same run (the `decided_in` references link decisions to the session, so the session must exist before the references are written).

Current expected pre-state (as of 05-12-26, post-`2accd8c`):

- `decisions.json` snapshot ends at **DEC-059** (last process conversation decision applied)
- `planning_items.json` snapshot ends at **PI-011**
- `sessions.json` snapshot ends at **SES-014** (process conversation)
- One payload pending in `close-out-payloads/`: `ses_015.json`, not yet applied

If the actual snapshot state is different (more advanced — e.g., SES-015 already applied), the script's 409-handling absorbs the difference. The pre-flight verification step calls this out either way.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root (the directory containing `CLAUDE.md`, `crmbuilder-v2/`, and `PRDs/`).

2. **Confirm `git status` is clean.** If there are uncommitted changes, stop and report to Doug before proceeding. The post-apply snapshot regeneration produces tracked-file changes; starting from a clean state ensures those changes are isolated and committable as one unit.

3. **Confirm git identity is set.** Run `git config user.name` and `git config user.email`. Expected values per the project convention: `Doug Bower` and `dbower44022@users.noreply.github.com`. If not set, configure them:

   ```bash
   git config user.name "Doug Bower"
   git config user.email "dbower44022@users.noreply.github.com"
   ```

4. **Pull latest from origin:** `git pull --rebase origin main`. Stop and report if there are conflicts. Expected HEAD is at or past `4d5863a` (the crm_candidate spec + build-planning kickoff commit).

5. **Confirm the payload file exists:**

   ```bash
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_015.json
   ```

   Stop if missing.

6. **Confirm the v2 API is running:**

   ```bash
   curl -sf http://127.0.0.1:8765/decisions >/dev/null && echo "API up" || echo "API DOWN"
   ```

   If the API is not running, ask Doug to start it (`cd crmbuilder-v2 && uv run crmbuilder-v2-api &`) before proceeding. Do not attempt to start it yourself — the API runs in the foreground in Doug's shell session.

7. **Capture pre-state for verification.** Record the current highest identifier in each entity type, so the post-apply check can confirm the expected new records landed:

   ```bash
   # Decisions
   curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys, json; d=json.load(sys.stdin); print('Latest DEC:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"

   # Planning items
   curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys, json; d=json.load(sys.stdin); print('Latest PI:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"

   # Sessions
   curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys, json; d=json.load(sys.stdin); print('Latest SES:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"
   ```

   Expected pre-state: `DEC-059`, `PI-011`, `SES-014`. Report the three values back so the post-apply step has a clear baseline.

---

## Workflow

### Step 1 — Apply SES-015 close-out payload

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_015.json
cd ..
```

Expected output: each record reports `OK` (created) or `SKIP` (409, already present). The script exits 0 on full success. Stop and report if it exits non-zero.

After this step:

- Decisions snapshot should contain DEC-060 through DEC-064.
- Planning items snapshot should contain PI-012.
- Sessions snapshot should contain SES-015.
- 5 new `decided_in` references should exist linking DEC-060..064 to SES-015.

### Step 2 — Verify post-state

Confirm the expected records exist via direct API queries:

```bash
# All 5 new decisions
for id in DEC-060 DEC-061 DEC-062 DEC-063 DEC-064; do
  curl -sf http://127.0.0.1:8765/decisions/$id >/dev/null && echo "$id OK" || echo "$id MISSING"
done

# The new planning item
curl -sf http://127.0.0.1:8765/planning-items/PI-012 >/dev/null && echo "PI-012 OK" || echo "PI-012 MISSING"

# The new session
curl -sf http://127.0.0.1:8765/sessions/SES-015 >/dev/null && echo "SES-015 OK" || echo "SES-015 MISSING"
```

All checks should report `OK`. Any `MISSING` is a failure; stop and report.

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
git commit -m "v2: apply SES-015 close-out payload

Inserts:
- DEC-060..DEC-064 (crm_candidate schema decisions)
- PI-012 (crm_candidate structured-metadata enums for v0.5+)
- SES-015 (crm_candidate schema-design conversation, workstream
  conversation #4 of 4 — final per-entity schema-design conversation)
- 5 decided_in references linking DEC-060..064 to SES-015

Snapshot regeneration only — payload file and apply script are
unchanged. The script is idempotent on the 409 path; this commit
captures the resulting db-export state for git tracking.

Closes the per-entity schema-design portion of the methodology-
entity-schema-design workstream. The successor v0.4-build-planning
conversation opens against the kickoff at PRDs/product/crmbuilder-v2/
ui-PRD-v0.4-build-planning-kickoff.md."
```

Do **not** push. Doug pushes per the project convention.

### Step 4 — Report

Print a short summary of what was applied:

- Number of decisions created vs skipped (409)
- Number of planning items created vs skipped
- Number of sessions created vs skipped
- Number of references created vs skipped
- The commit SHA
- A reminder that the commit needs to be pushed by Doug
- An explicit note that this apply closes the per-entity portion of the workstream and the next conversation is v0.4-build-planning per the kickoff already on disk

---

## Error handling

- **Script exits non-zero on a non-409 error:** stop, do not commit, report the full script output to Doug. The most likely causes are API not running, payload file malformed, or a validation error at the API layer (unexpected field, FK violation, etc.). Doug investigates from the script output.

- **Snapshot not regenerated:** the export hook in the access layer may have failed silently. Stop, do not commit. Doug investigates by checking the API server logs.

- **Pre-state already past SES-015:** if `Latest SES` from the pre-flight is already `SES-015` or later, the work has already been applied. Report this finding; do not run the script again (still safe given idempotency, but unnecessary). No commit needed.

- **Pre-state earlier than SES-014:** if `Latest SES` from the pre-flight is `SES-013` or earlier, the SES-014 close-out has not yet been applied. Stop and report to Doug — the prerequisite is missing, and this prompt does not apply it (the SES-014 apply prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses_014.md` is the correct path for that work).

- **`git status` not clean at start:** stop and report. Do not stash. Doug decides how to handle the uncommitted changes before re-running.

---

## What this prompt does NOT do

- Does not push the commit. Doug pushes.
- Does not modify the payload file. It is a read-only input.
- Does not modify the apply script. The script is generic; per-payload variation is in the payload file itself.
- Does not author additional decisions, planning items, or sessions beyond what the payload file contains. If something is missing from the payload, fix the payload first and re-author it; do not work around in this prompt.
- Does not advance the workstream. The next workstream conversation is the v0.4-build-planning conversation, kicked off separately at `PRDs/product/crmbuilder-v2/ui-PRD-v0.4-build-planning-kickoff.md` — outside this prompt's scope.
- Does not apply earlier workstream close-out payloads (SES-013 / SES-014). Those were applied at `2accd8c`; this prompt only applies SES-015.

---

*End of prompt.*
