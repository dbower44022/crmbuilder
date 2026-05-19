# CLAUDE-CODE-PROMPT-apply-close-out-ses-001

**Last Updated:** 05-19-26 03:00
**Operating mode:** detail
**Series:** apply-close-out
**Status:** Ready to execute
**Companion conversation:** Claude.ai paper-test conversation on 05-19-26 that produced `PRDs/product/crmbuilder-v2/methodology-schemas-cbm-paper-test-findings.md`. Supersedes `CLAUDE-CODE-PROMPT-apply-close-out-ses-044.md` (committed at d365ebc, since deleted), which incorrectly continued the CRMBUILDER engagement's global identifier sequence into a fresh CBM engagement. CBM uses a per-engagement counter starting at 001.

---

## Purpose

Apply the SES-001 close-out payload to the **CBM** engagement's per-engagement DB. Pure POST operations — no PATCH, no PI updates. Records inserted by the standard `apply_close_out.py` script in fixed order: session → decisions → planning items → references.

Net effect on CBM's per-engagement DB after this prompt completes:

- **Session.** SES-001 (methodology-schemas CBM-content paper-test record).
- **Decisions.** DEC-001 (paper-test single decision — amend `domain` with `domain_parent_identifier` self-FK before CBM redo Phase 1 opens), DEC-002 (Cross-Domain Services Option A — services not represented in v0.4 Phase 1), DEC-003 (Pass 2 v0.5+ workstream ordering signal).
- **Planning items.** PI-001 (`domain_parent_identifier` self-FK on `domain` for sub-domain hierarchy — the amendment workstream that opens as the next planning conversation).
- **References.** Three `decided_in` references (DEC-001 → SES-001, DEC-002 → SES-001, DEC-003 → SES-001).

These are CBM's first records of any kind. CBM's per-engagement DB at `crmbuilder-v2/data/engagements/CBM.db` is expected to have empty sessions / decisions / planning_items / references tables at pre-flight time (or near-empty if any test writes have happened).

One-shot apply prompt. The underlying script is idempotent (HTTP 409 conflict is treated as already-present and continues), so re-running is safe if interrupted. Post-apply this prompt should not be re-run as a matter of routine.

---

## Project context

Per DEC-004, the v2 database is the source of truth for all v2 artifacts; per DEC-008, the JSON snapshots are renders, not authored copies. Under multi-tenancy (slice D), each engagement has its own per-engagement DB at `crmbuilder-v2/data/engagements/{engagement_code}.db` and its own snapshot export directory configured via `engagement_export_dir`.

For CBM, `engagement_export_dir` points into the ClevelandBusinessMentoring repo (Option 1 per the paper-test conversation's Issue A resolution). This means the apply's snapshot regeneration writes into a different git repo than the one the apply runs from. The Step 3 commit happens in the CBM repo, not the crmbuilder repo.

Per-engagement identifiers start at 001. CBM has no prior records; this paper-test's records are CBM's first. The CRMBUILDER engagement's identifier history (SES-043 / DEC-107 / PI-017 highest at v0.6 closeout) is irrelevant to CBM's sequence.

Current expected pre-state:

- Active engagement is **CBM** (engagement_code `CBM`, engagement_identifier `ENG-002`).
- CBM's `engagement_export_dir` is non-null and points into the ClevelandBusinessMentoring repo clone (operator-set per Issue A resolution).
- CBM's per-engagement DB has empty sessions / decisions / planning_items tables (or near-empty).
- The CBM export directory exists, is inside a git repo, has a clean working tree.
- The crmbuilder repo has a clean working tree; HEAD is on or past the commit containing `ses_001.json` and the apply prompt.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root (the directory containing `CLAUDE.md`, `crmbuilder-v2/`, and `PRDs/`).

2. **Confirm `git status` is clean in the crmbuilder repo.** If there are uncommitted changes, stop and report to Doug before proceeding.

3. **Confirm git identity is set.**

   ```bash
   git config user.name "Doug Bower"
   git config user.email "doug@dougbower.com"
   ```

4. **Pull latest from origin (crmbuilder repo):**

   ```bash
   git pull --rebase origin main
   ```

   Stop and report if there are conflicts. Expected HEAD is at or past the commit containing `ses_001.json` and the apply prompt.

5. **Confirm the payload and findings files exist:**

   ```bash
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_001.json
   ls -la PRDs/product/crmbuilder-v2/methodology-schemas-cbm-paper-test-findings.md
   ```

   Stop if either is missing. The findings file is the durable artifact the SES-001 record's `artifacts_produced` field cites.

6. **Confirm the v2 API is running:**

   ```bash
   curl -sf http://127.0.0.1:8765/decisions >/dev/null && echo "API: up" || echo "API: DOWN"
   ```

   If the API is not running, ask Doug to start it (`cd crmbuilder-v2 && uv run crmbuilder-v2-api &`) before proceeding.

7. **Confirm active engagement is CBM and discover its export_dir.**

   ```bash
   curl -s http://127.0.0.1:8765/active-engagement | python3 -m json.tool
   ```

   Capture both:
   - The `engagement_code` — must be `CBM`. If it is `CRMBUILDER` or anything else, **STOP**. Records belong to CBM; writing them into the wrong engagement is hard to undo. Ask Doug to switch via the v2 desktop UI's Engagements panel before re-running.
   - The `engagement_export_dir` — must be non-null and must be an existing directory inside a git repo. If null, STOP and ask Doug to set it via the desktop UI. If the response shape doesn't match (no `engagement_code` or `engagement_export_dir` key), report the actual shape so this prompt can be corrected.

   Resolve the export directory's git repo root for use in Step 3:

   ```bash
   export CBM_EXPORT_DIR=$(curl -s http://127.0.0.1:8765/active-engagement | python3 -c "import sys, json; d=json.load(sys.stdin); print((d.get('data') or d).get('engagement_export_dir', ''))")
   export CBM_REPO_ROOT=$(git -C "$CBM_EXPORT_DIR" rev-parse --show-toplevel 2>/dev/null)
   echo "CBM export dir: $CBM_EXPORT_DIR"
   echo "CBM repo root:  $CBM_REPO_ROOT"
   ```

   If `$CBM_REPO_ROOT` is empty (export_dir is not inside a git repo), STOP and report. The cross-repo commit pattern requires the export_dir to be inside a git working tree.

8. **Confirm CBM repo working tree is clean.**

   ```bash
   git -C "$CBM_REPO_ROOT" status
   ```

   If uncommitted changes exist in the CBM repo, stop and report. The post-apply snapshot regeneration should be the only modification.

9. **Capture pre-state for verification.** CBM is fresh, so expect empty or near-empty lists:

   ```bash
   curl -s http://127.0.0.1:8765/decisions       | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('CBM decisions before:',       len(d), '— latest:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"
   curl -s http://127.0.0.1:8765/planning-items  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('CBM planning items before:', len(d), '— latest:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"
   curl -s http://127.0.0.1:8765/sessions        | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('CBM sessions before:',        len(d), '— latest:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"
   curl -s http://127.0.0.1:8765/references      | python3 -c "import sys,json; refs=json.load(sys.stdin)['data']; print('CBM references before:', len(refs))"
   ```

   Expected: all four near zero. Report the actual values back so the post-apply step has a clear baseline.

---

## Workflow

### Step 1 — Apply the SES-001 payload

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_001.json
cd ..
```

Expected output: each record reports `OK` (created) or `SKIP` (409, already present). The script exits 0 on full success. Stop and report if it exits non-zero.

After this step:

- CBM sessions: contains SES-001.
- CBM decisions: contains DEC-001, DEC-002, DEC-003.
- CBM planning items: contains PI-001.
- CBM references: three new `decided_in` edges (DEC-001/002/003 → SES-001).

### Step 2 — Verify post-state

```bash
# Sessions, decisions, planning item all present
curl -sf http://127.0.0.1:8765/sessions/SES-001         >/dev/null && echo "SES-001 OK" || echo "SES-001 MISSING"
for id in DEC-001 DEC-002 DEC-003; do
  curl -sf http://127.0.0.1:8765/decisions/$id          >/dev/null && echo "$id OK"     || echo "$id MISSING"
done
curl -sf http://127.0.0.1:8765/planning-items/PI-001    >/dev/null && echo "PI-001 OK"  || echo "PI-001 MISSING"

# References existence + count
curl -s http://127.0.0.1:8765/references | python3 -c "
import sys, json
refs = json.load(sys.stdin)['data']
print('CBM references after:', len(refs))
for src in ['DEC-001', 'DEC-002', 'DEC-003']:
  hit = any(r['source_id'] == src and r['target_id'] == 'SES-001' for r in refs)
  print(f'  {src} -> SES-001:', hit)
"
```

All existence checks should return `OK`. All three reference existence checks should return `True`. References after = references before + 3.

Then confirm the CBM repo's working tree shows the expected snapshot modifications:

```bash
git -C "$CBM_REPO_ROOT" status
```

Expected modifications inside `$CBM_EXPORT_DIR`: `decisions.json`, `planning_items.json`, `sessions.json`, `references.json`, `change_log.json`. If the export_dir has no modifications, the export hook may have failed silently — STOP and report; do not commit. If files outside `$CBM_EXPORT_DIR` are modified inside the CBM repo, that's also unexpected — report before committing.

### Step 3 — Commit (in the CBM repo)

The commit happens in the CBM repo, not the crmbuilder repo. Use the same git identity:

```bash
git -C "$CBM_REPO_ROOT" config user.name "Doug Bower"
git -C "$CBM_REPO_ROOT" config user.email "doug@dougbower.com"

# Stage only the export_dir's contents (relative to repo root)
EXPORT_REL=$(realpath --relative-to="$CBM_REPO_ROOT" "$CBM_EXPORT_DIR")
git -C "$CBM_REPO_ROOT" add "$EXPORT_REL"
git -C "$CBM_REPO_ROOT" status

git -C "$CBM_REPO_ROOT" commit -m "Apply SES-001 close-out payload (CBM engagement's first records)

CBM engagement methodology-record snapshot regeneration following the
SES-001 close-out apply against the CBM per-engagement DB.

Inserts in CBM's per-engagement DB:
- SES-001 (methodology-schemas CBM-content paper-test record)
- DEC-001 (paper-test single decision: amend domain with
  domain_parent_identifier self-FK before CBM redo Phase 1 opens;
  opens PI-001 as the first v0.5+ planning conversation)
- DEC-002 (Cross-Domain Services Option A: services not represented
  in v0.4 Phase 1; CDS-owned entities handled by entity_scopes_to_domain
  many-to-many; PI-013 retains the v0.5+ design question — note that
  PI-013 lives in the CRMBUILDER engagement's methodology planning,
  not in CBM's)
- DEC-003 (Pass 2 v0.5+ workstream ordering signal)
- PI-001 (domain_parent_identifier self-FK for sub-domain hierarchy;
  opens as the next planning conversation in the CRMBUILDER engagement;
  CBM redo Phase 1 waits on the amendment shipping)
- 3 decided_in references (DEC-001/002/003 to SES-001)

These are CBM's first records of any kind. The paper-test source
artifact (methodology-schemas-cbm-paper-test-findings.md) and the
payload itself (ses_001.json) live in the crmbuilder repo and are
referenced in CBM's SES-001 record via artifacts_produced.

Snapshot regeneration only — payload file is unchanged. After this
commit the next conversation to open is the PI-001 planning
conversation (in the CRMBUILDER engagement; PI-001 is methodology work
not CBM-engagement-specific work, even though the planning item
identifier lives in CBM's DB as the close-out record of where the
need was surfaced)."
```

Do **not** push. Doug pushes both repos at his convenience per the project convention. If `git -C "$CBM_REPO_ROOT" log -1` returns a commit SHA, report it back.

### Step 4 — Report

Print a structured summary:

- Identity of the active engagement at apply time (must be CBM)
- CBM export directory path (from `$CBM_EXPORT_DIR`)
- CBM repo root (from `$CBM_REPO_ROOT`)
- Number of decisions / sessions / planning items / references created vs skipped (409)
- The commit SHA in the CBM repo
- Reminder that the commit needs to be pushed by Doug (CBM repo: `git push origin main`)
- Note that the next conversation to open is the PI-001 planning conversation, in a fresh Claude.ai chat against `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` (crmbuilder repo) + Finding 2 of the paper-test findings file. No kickoff document exists for it yet; the planning conversation drafts its own.

---

## Error handling

- **Active engagement is not CBM.** Stop immediately. Records belong to CBM; writing them elsewhere is contamination. Ask Doug to switch via the desktop UI.

- **CBM `engagement_export_dir` is null.** Stop. The cross-repo commit pattern requires a real path. Ask Doug to set it via the desktop UI (Option 1 per the paper-test resolution: a path inside the ClevelandBusinessMentoring repo clone).

- **CBM export_dir is not inside a git working tree.** Stop. The commit step can't operate. Report the path and ask Doug to either move the export_dir into a tracked location or initialize git there.

- **Standard apply script exits non-zero on a non-409 error.** Stop, do not commit, report the full script output. Most likely causes: API not running, payload malformed, validation error at the access layer.

- **Snapshot not regenerated, or regenerated outside `$CBM_EXPORT_DIR`.** The export hook may have failed silently or the active-engagement context may have been wrong at write time. Stop, do not commit.

- **Pre-state already past SES-001.** If CBM's sessions list already contains SES-001 (or higher), the work has already been applied. Report this finding; do not re-run. Idempotency makes re-running safe but unnecessary.

- **`git status` not clean in either repo at start.** Stop and report. Do not stash. Doug decides how to handle uncommitted changes before re-running.

- **`/active-engagement` endpoint shape unexpected.** If the endpoint doesn't expose `engagement_code` and `engagement_export_dir` in the documented shape, fall back to querying the meta DB engagements endpoint (`curl http://127.0.0.1:8765/engagements`) and find the record where `engagement_status='active'` (or whatever flag identifies the active engagement). Report the actual response shape so this prompt can be corrected.

---

## What this prompt does NOT do

- Does not push the commit. Doug pushes (in the CBM repo, not the crmbuilder repo, for the snapshot regeneration commit).
- Does not modify the payload file. It is a read-only input.
- Does not modify the apply script.
- Does not author additional records beyond the payload contents.
- Does not write a status update. Release status remains "v0.6 complete"; the paper-test is a planning artifact that does not change shipped state.
- Does not open the PI-001 planning conversation. That is a separate Claude.ai chat Doug opens later — outside this prompt's scope.
- Does not switch the active engagement.
- Does not write to the crmbuilder repo. All commits in this prompt's Step 3 happen in the CBM repo via the `$CBM_REPO_ROOT` variable.

---

*End of prompt.*
