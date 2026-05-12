# CLAUDE-CODE-PROMPT-apply-close-out-ses_014

**Last Updated:** 05-12-26 05:00
**Operating mode:** detail
**Series:** apply-close-out
**Status:** Ready to execute
**Companion conversation:** Claude.ai schema-design conversation on 05-12-26 that produced `PRDs/product/crmbuilder-v2/methodology-schema-specs/process.md` v1.0 (commit `4f06a0e`).

---

## Purpose

Apply the SES-014 close-out payload to the local v2 governance database. The payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_014.json` was authored during the process schema-design conversation and committed to `main` already; this prompt runs `crmbuilder-v2/scripts/apply_close_out.py` against it, after first ensuring SES-013's payload (a precondition) has been applied.

Net effect on the v2 database after this prompt completes:

- **SES-013 records (if not already present):** DEC-050..DEC-054 (entity schema decisions), PI-009 and PI-010, SES-013 itself, plus 5 `decided_in` references linking the decisions to SES-013.
- **SES-014 records:** DEC-055..DEC-059 (process schema decisions), PI-011, SES-014 itself, plus 5 `decided_in` references linking the decisions to SES-014.

This is a one-shot apply prompt. The underlying script is idempotent (HTTP 409 conflict is treated as already-present and continues), so re-running is safe if interrupted, but post-apply this prompt should not be re-run as a matter of routine.

---

## Project context

Per DEC-004, the v2 database is the source of truth for all v2 artifacts; per DEC-008, the JSON snapshots under `PRDs/product/crmbuilder-v2/db-export/` are renders, not authored copies. Records are inserted via the v2 access layer (HTTP POST to `http://127.0.0.1:8765`), which transactionally regenerates the JSON snapshots.

The `apply_close_out.py` script reads a sectioned JSON payload and POSTs each section in fixed order: `session` → `decisions` → `planning_items` → `references`. This ordering matters because references in the payload target records created earlier in the same run (the `decided_in` references link decisions to the session, so the session must exist before the references are written).

Current expected pre-state (as of 05-12-26):

- `decisions.json` snapshot ends at **DEC-049** (last domain conversation decision applied)
- `planning_items.json` snapshot ends at **PI-008**
- `sessions.json` snapshot ends at **SES-012** (domain conversation)
- Two payloads pending in `close-out-payloads/`: `ses_013.json` and `ses_014.json`, neither yet applied

If the actual snapshot state is different (more advanced — e.g., SES-013 already applied), the script's 409-handling absorbs the difference. The pre-flight verification step calls this out either way.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root (the directory containing `CLAUDE.md`, `crmbuilder-v2/`, and `PRDs/`).

2. **Confirm `git status` is clean.** If there are uncommitted changes, stop and report to Doug before proceeding. The post-apply snapshot regeneration produces tracked-file changes; starting from a clean state ensures those changes are isolated and committable as one unit.

3. **Confirm git identity is set.** Run `git config user.name` and `git config user.email`. Expected values per the project convention: `Doug Bower` and `dbower44022@users.noreply.github.com`. If not set, configure them:

   ```bash
   git config user.name "Doug Bower"
   git config user.email "dbower44022@users.noreply.github.com"
   ```

4. **Pull latest from origin:** `git pull --rebase origin main`. Stop and report if there are conflicts.

5. **Confirm both payload files exist:**

   ```bash
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_013.json
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_014.json
   ```

   Stop if either file is missing.

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

   Report the three values back so the post-apply step has a clear baseline.

---

## Workflow

### Step 1 — Apply SES-013 close-out payload (precondition)

SES-014's decisions reference and build on SES-013's. Apply SES-013's payload first. The script is idempotent, so if SES-013 has already been applied, this step is a no-op (409 conflicts are treated as already-present and the script continues).

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_013.json
cd ..
```

Expected output: each record reports `OK` (created) or `SKIP` (409, already present). The script exits 0 on full success. Stop and report if it exits non-zero.

After this step:

- Decisions snapshot should contain DEC-050 through DEC-054.
- Planning items snapshot should contain PI-009 and PI-010.
- Sessions snapshot should contain SES-013.
- 5 new `decided_in` references should exist linking DEC-050..054 to SES-013.

### Step 2 — Apply SES-014 close-out payload

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_014.json
cd ..
```

Expected output: each record reports `OK`. The script exits 0 on full success. Stop and report if it exits non-zero.

After this step:

- Decisions snapshot should contain DEC-055 through DEC-059.
- Planning items snapshot should contain PI-011.
- Sessions snapshot should contain SES-014.
- 5 new `decided_in` references should exist linking DEC-055..059 to SES-014.

### Step 3 — Verify post-state

Confirm the expected records exist via direct API queries:

```bash
# All 10 new decisions
for id in DEC-050 DEC-051 DEC-052 DEC-053 DEC-054 DEC-055 DEC-056 DEC-057 DEC-058 DEC-059; do
  curl -sf http://127.0.0.1:8765/decisions/$id >/dev/null && echo "$id OK" || echo "$id MISSING"
done

# Both new planning items
for id in PI-009 PI-010 PI-011; do
  curl -sf http://127.0.0.1:8765/planning-items/$id >/dev/null && echo "$id OK" || echo "$id MISSING"
done

# Both new sessions
for id in SES-013 SES-014; do
  curl -sf http://127.0.0.1:8765/sessions/$id >/dev/null && echo "$id OK" || echo "$id MISSING"
done
```

All checks should report `OK`. Any `MISSING` is a failure; stop and report.

Then confirm the JSON snapshots were regenerated:

```bash
git status PRDs/product/crmbuilder-v2/db-export/
```

Expected modifications: `decisions.json`, `planning_items.json`, `sessions.json`, `references.json`, and `change_log.json`. If any of these are unexpectedly unchanged or unexpectedly absent from the diff, the export hook may have failed — stop and report before committing.

### Step 4 — Commit

Single commit covering all snapshot regenerations:

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git status   # confirm only db-export changes are staged
git commit -m "v2: apply SES-013 and SES-014 close-out payloads

Inserts:
- DEC-050..DEC-054 + PI-009/PI-010 + SES-013 (entity schema conversation)
- DEC-055..DEC-059 + PI-011 + SES-014 (process schema conversation)
- 10 decided_in references linking decisions to their sessions

Snapshot regeneration only — payload files and apply script are
unchanged. The script is idempotent on the 409 path; this commit
captures the resulting db-export state for git tracking."
```

Do **not** push. Doug pushes per the project convention.

### Step 5 — Report

Print a short summary of what was applied:

- Number of decisions created vs skipped (409)
- Number of planning items created vs skipped
- Number of sessions created vs skipped
- Number of references created vs skipped
- The commit SHA
- A reminder that the commit needs to be pushed by Doug

---

## Error handling

- **Script exits non-zero on a non-409 error:** stop, do not commit, report the full script output to Doug. The most likely causes are API not running, payload file malformed, or a validation error at the API layer (unexpected field, FK violation, etc.). Doug investigates from the script output.

- **Snapshot not regenerated:** the export hook in the access layer may have failed silently. Stop, do not commit. Doug investigates by checking the API server logs.

- **Pre-state already past SES-014:** if `Latest SES` from the pre-flight is already `SES-014` or later, the work has already been applied. Report this finding; do not run the script again (still safe given idempotency, but unnecessary). No commit needed.

- **`git status` not clean at start:** stop and report. Do not stash. Doug decides how to handle the uncommitted changes before re-running.

---

## What this prompt does NOT do

- Does not push the commit. Doug pushes.
- Does not modify the payload files. They are read-only inputs.
- Does not modify the apply script. The script is generic; per-payload variation is in the payload files themselves.
- Does not author additional decisions, planning items, or sessions beyond what the two payload files contain. If something is missing from a payload, fix the payload first and re-author it; do not work around in this prompt.
- Does not advance the workstream. The next workstream conversation is the `crm_candidate` schema-design conversation, kicked off separately at `PRDs/product/crmbuilder-v2/schema-design-kickoff-crm_candidate.md` — outside this prompt's scope.

---

*End of prompt.*
