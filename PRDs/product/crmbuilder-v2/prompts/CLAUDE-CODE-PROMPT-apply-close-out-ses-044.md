# CLAUDE-CODE-PROMPT-apply-close-out-ses-044

**Last Updated:** 05-19-26 01:30
**Operating mode:** detail
**Series:** apply-close-out
**Status:** Ready to execute
**Companion conversation:** Claude.ai paper-test conversation on 05-19-26 that produced `PRDs/product/crmbuilder-v2/methodology-schemas-cbm-paper-test-findings.md` (committed alongside this prompt as a single change set; commit by Doug).

---

## Purpose

Apply the SES-044 close-out payload to the local v2 governance database. Pure POST operations — no PATCH, no PI updates. Records inserted by the standard `apply_close_out.py` script in fixed order: session → decisions → planning items → references.

Net effect on the v2 database after this prompt completes:

- **Session.** SES-044 (methodology-schemas CBM-content paper-test record).
- **Decisions.** DEC-108 (paper-test single decision — amend `domain` with `domain_parent_identifier` self-FK before CBM redo Phase 1 opens), DEC-109 (Cross-Domain Services Option A — services not represented in v0.4 Phase 1), DEC-110 (Pass 2 v0.5+ workstream ordering signal).
- **Planning items.** PI-018 (`domain_parent_identifier` self-FK on `domain` for sub-domain hierarchy — the amendment workstream that opens as the next planning conversation).
- **References.** Three `decided_in` references (DEC-108 → SES-044, DEC-109 → SES-044, DEC-110 → SES-044).

One-shot apply prompt. The underlying script is idempotent (HTTP 409 conflict is treated as already-present and continues), so re-running is safe if interrupted. Post-apply this prompt should not be re-run as a matter of routine.

---

## Project context

Per DEC-004, the v2 database is the source of truth for all v2 artifacts; per DEC-008, the JSON snapshots under `PRDs/product/crmbuilder-v2/db-export/` are renders, not authored copies. Records are inserted via the v2 access layer (HTTP POST to `http://127.0.0.1:8765`), which transactionally regenerates the JSON snapshots.

The active engagement at apply time must be CBM — this paper-test's records belong to the CBM engagement's per-engagement DB, not the dogfood CRMBUILDER engagement. The pre-flight verifies engagement context before running the apply.

Current expected pre-state (per the snapshots at this prompt's commit):

- `decisions.json` snapshot ends at **DEC-107** (last v0.6-closeout decision)
- `planning_items.json` snapshot ends at **PI-017** (last applied PI, from styling Conversation 1)
- `sessions.json` snapshot ends at **SES-043** (v0.6 slice F closeout)
- One payload pending in `close-out-payloads/`: `ses_044.json`, not yet applied
- HEAD on `main` is at or past the commit containing `ses_044.json` and `methodology-schemas-cbm-paper-test-findings.md`

If the actual snapshot state is different (more advanced — e.g., SES-044 already applied), the apply script's 409-handling absorbs the difference. The pre-flight verification step calls this out either way.

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

   Stop and report if there are conflicts. Expected HEAD is at or past the commit containing `ses_044.json` and `methodology-schemas-cbm-paper-test-findings.md`.

5. **Confirm the payload and findings files exist:**

   ```bash
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_044.json
   ls -la PRDs/product/crmbuilder-v2/methodology-schemas-cbm-paper-test-findings.md
   ```

   Stop if either is missing.

6. **Confirm the v2 API is running:**

   ```bash
   curl -sf http://127.0.0.1:8765/decisions >/dev/null && echo "API up" || echo "API DOWN"
   ```

   If the API is not running, ask Doug to start it (`cd crmbuilder-v2 && uv run crmbuilder-v2-api &`) before proceeding. Do not attempt to start it yourself — the API runs in the foreground in Doug's shell session.

7. **Confirm the active engagement is CBM.**

   ```bash
   curl -s http://127.0.0.1:8765/active-engagement | python3 -c "import sys, json; d=json.load(sys.stdin).get('data') or {}; print('Active engagement:', d.get('engagement_code'), '-', d.get('engagement_name'))"
   ```

   Expected: active engagement is `CBM`. If the active engagement is `CRMBUILDER` or anything else, **stop and report to Doug** — the paper-test's records belong to the CBM engagement and must not be written into the dogfood. If the `/active-engagement` endpoint shape differs from the assumed `{data: {engagement_code, engagement_name}}`, fall back to whichever endpoint exposes the active engagement and report the actual response shape so the check can be corrected.

8. **Capture pre-state for verification.** Record the current highest identifier in each entity type:

   ```bash
   # Decisions
   curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys, json; d=json.load(sys.stdin)['data']; print('Latest DEC:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"

   # Planning items
   curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys, json; d=json.load(sys.stdin)['data']; print('Latest PI:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"

   # Sessions
   curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys, json; d=json.load(sys.stdin)['data']; print('Latest SES:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"

   # Total references before
   curl -s http://127.0.0.1:8765/references | python3 -c "import sys, json; refs=json.load(sys.stdin)['data']; print('Refs total before:', len(refs))"
   ```

   Expected pre-state in the CBM engagement: this paper-test produces the first content records, so all three lists are likely empty or near-empty if the CBM engagement was created fresh per the v0.5 slice D activation flow. Report the four values back so the post-apply step has a clear baseline.

---

## Workflow

### Step 1 — Apply SES-044 close-out payload (session + decisions + planning items + references)

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_044.json
cd ..
```

Expected output: each record reports `OK` (created) or `SKIP` (409, already present). The script exits 0 on full success. Stop and report if it exits non-zero.

After this step:

- Sessions snapshot should contain SES-044.
- Decisions snapshot should contain DEC-108, DEC-109, DEC-110.
- Planning items snapshot should contain PI-018.
- Three new `decided_in` references should exist (DEC-108 → SES-044, DEC-109 → SES-044, DEC-110 → SES-044).

### Step 2 — Verify post-state

Confirm the expected records exist via direct API queries:

```bash
# All 3 new decisions
for id in DEC-108 DEC-109 DEC-110; do
  curl -sf http://127.0.0.1:8765/decisions/$id >/dev/null && echo "$id OK" || echo "$id MISSING"
done

# The new session
curl -sf http://127.0.0.1:8765/sessions/SES-044 >/dev/null && echo "SES-044 OK" || echo "SES-044 MISSING"

# The new planning item
curl -sf http://127.0.0.1:8765/planning-items/PI-018 >/dev/null && echo "PI-018 OK" || echo "PI-018 MISSING"

# References existence check
curl -s http://127.0.0.1:8765/references | python3 -c "import sys, json; refs=json.load(sys.stdin)['data']; print('Refs total after:', len(refs)); print('DEC-108 to SES-044:', any(r['source_id']=='DEC-108' and r['target_id']=='SES-044' for r in refs)); print('DEC-109 to SES-044:', any(r['source_id']=='DEC-109' and r['target_id']=='SES-044' for r in refs)); print('DEC-110 to SES-044:', any(r['source_id']=='DEC-110' and r['target_id']=='SES-044' for r in refs))"
```

All decision / session / planning-item checks should report `OK`. All three reference-existence checks should report `True`. Refs total after should be the pre-state count + 3 (or higher if intervening writes have landed; report any anomaly).

Then confirm the JSON snapshots were regenerated:

```bash
git status PRDs/product/crmbuilder-v2/db-export/
```

Expected modifications (for the CBM engagement's export directory): `decisions.json`, `planning_items.json`, `sessions.json`, `references.json`, and `change_log.json`. The exact directory path depends on the CBM engagement's `engagement_export_dir`; the meta engagement's `db-export/` should NOT be modified by this apply since CBM is the active engagement. If the CBM export directory doesn't have any modifications, the export hook may have failed — stop and report before committing. If the dogfood `db-export/` has modifications, the active engagement was wrong and Doug needs to investigate before committing.

### Step 3 — Commit

Single commit covering all snapshot regenerations:

```bash
git add -A PRDs/product/crmbuilder-v2/
git status   # confirm only the CBM engagement's db-export changes are staged (plus possibly meta change_log if writes are also tracked there)
git commit -m "v2: apply SES-044 close-out payload (paper-test)

Inserts in the CBM engagement:
- SES-044 (methodology-schemas CBM-content paper-test record;
  pass-by-pass topics_covered; full conversation_reference per DEC-025;
  artifacts_produced points to the findings file)
- DEC-108 (paper-test single decision: amend domain with
  domain_parent_identifier self-FK before CBM redo Phase 1 opens;
  opens PI-018 as the first v0.5+ planning conversation)
- DEC-109 (Cross-Domain Services Option A: services not represented
  in v0.4 Phase 1; CDS-owned entities handled by entity_scopes_to_domain
  many-to-many; PI-013 retains the v0.5+ design question)
- DEC-110 (Pass 2 v0.5+ workstream ordering signal: PI-018 first,
  then PI-004+014+010 joint workstream, PI-005, PI-003, PI-013,
  PI-015, then lower-priority follow-ons)
- PI-018 (domain_parent_identifier self-FK for sub-domain hierarchy;
  opens as the next planning conversation; CBM redo Phase 1 waits
  on the amendment shipping)
- 3 decided_in references (DEC-108/109/110 to SES-044)

Snapshot regeneration only — payload file is unchanged. The apply
script is idempotent on the 409 path; this commit captures the
resulting db-export state for git tracking.

After this apply lands, the next conversation is the PI-018 planning
conversation. CBM redo Phase 1 waits on the amendment shipping and
the domain.md schema spec being updated to reflect that sub-domain
hierarchy is in scope."
```

Do **not** push. Doug pushes per the project convention.

### Step 4 — Report

Print a short summary of what was applied:

- Number of decisions created vs skipped (409) — expected 3 created
- Number of references created vs skipped — expected 3 created
- Number of sessions created vs skipped — expected 1 created
- Number of planning items created vs skipped — expected 1 created
- The active engagement at apply time (confirmation that CBM was active, not CRMBUILDER)
- The commit SHA
- A reminder that the commit needs to be pushed by Doug
- An explicit note that this apply closes the paper-test conversation and the next conversation to open is the PI-018 planning conversation (no kickoff document exists yet for it; the planning conversation drafts its own kickoff against the `domain.md` schema spec and the findings file's Finding 2)

---

## Error handling

- **Standard apply script exits non-zero on a non-409 error.** Stop, do not commit, report the full script output to Doug. The most likely causes are API not running, payload file malformed, or a validation error at the API layer (e.g., a field type mismatch).

- **Active engagement is not CBM.** Stop immediately. Do not run the apply. Records belong to the CBM engagement; writing them into CRMBUILDER (or any other engagement) creates a cross-engagement contamination that's difficult to clean up. Report the actual active engagement to Doug and ask him to switch via the v2 desktop UI's Engagements panel before re-running.

- **Snapshot not regenerated, or regenerated in the wrong engagement's export directory.** The export hook in the access layer may have failed silently or the active-engagement context may have been wrong at write time. Stop, do not commit. Doug investigates by checking the API server logs and the meta DB's engagement state.

- **Pre-state already past SES-044.** If `Latest SES` from the pre-flight is already `SES-044` or later, the work has already been applied. Report this finding; do not run the apply again (still safe given idempotency, but unnecessary). No commit needed unless the prior apply was on a different machine and the snapshots haven't been committed yet — in that case `git status` will show the pending snapshot changes and Step 3's commit is still appropriate.

- **Pre-state earlier than SES-043.** If `Latest SES` from the pre-flight is `SES-042` or earlier in the CBM engagement, that's fine — CBM is a fresh engagement and its sessions start independently from CRMBUILDER's sequence. The expected pre-state for the CBM engagement specifically is that this is its first content (likely empty or near-empty lists). Report the actual values.

- **`git status` not clean at start.** Stop and report. Do not stash. Doug decides how to handle the uncommitted changes before re-running.

---

## What this prompt does NOT do

- Does not push the commit. Doug pushes.
- Does not modify the payload file. It is a read-only input.
- Does not modify the apply script. The script is generic; per-payload variation is in the payload file itself.
- Does not author additional decisions, planning items, or sessions beyond what the payload file contains. If something is missing from the payload, fix the payload first and re-author it; do not work around in this prompt.
- Does not write a status update. Release status remains `"v0.6 complete"`; the paper-test is a planning artifact that does not change shipped state.
- Does not open the PI-018 planning conversation. That is a separate Claude.ai chat Doug opens against `domain.md` schema spec + this paper-test's Finding 2 — outside this prompt's scope.
- Does not switch the active engagement. If the active engagement is wrong, Doug switches it via the v2 desktop UI before re-running this prompt.

---

*End of prompt.*
