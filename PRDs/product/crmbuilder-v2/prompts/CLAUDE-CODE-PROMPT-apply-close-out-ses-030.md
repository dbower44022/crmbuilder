# CLAUDE-CODE-PROMPT-apply-close-out-ses-030

**Last Updated:** 05-16-26 19:30
**Operating mode:** detail
**Series:** apply-close-out
**Status:** Ready to execute
**Companion conversation:** Claude.ai styling Conversation 2 on 05-16-26 that produced `PRDs/product/crmbuilder-v2/ui-PRD-v0.6.md` (430 lines), `PRDs/product/crmbuilder-v2/ui-v0.6-implementation-plan.md` (456 lines), and six slice prompts under `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.6-{A..F}-*.md` (456 / 369 / 398 / 495 / 369 / 304 lines).


**Note on numbering.** This conversation initially anticipated SES-028 / DEC-095..DEC-097 at PRD-authoring time but those were consumed in flight by parallel v0.5 work (latest applied session at close-out time was SES-029; latest applied decision was DEC-104). Per the parallel-workstream coupling discipline in DEC-076, the styling Conversation 2 rebased its numbering to SES-030 / DEC-105..DEC-107 to avoid collision. Rebase applied across the PRD, implementation plan, and all six slice prompts via commit `7255667`. No content change; numbering only. Same pattern as the SES-027 rebase from SES-026 during styling Conversation 1's close-out.

---

## Purpose

Apply the SES-030 close-out payload to the local v2 governance database. One substantive operation: POST a new session, three decisions, and four references via the standard `apply_close_out.py` script. No PI patches — all v0.6 build work folds into existing PI-001 (the parent for the whole styling pass, already reopened as parallel workstream by DEC-076).

Net effect on the v2 database after this prompt completes:

- **Session.** SES-030 (styling Conversation 2 record — build-planning walk-through covering the three architectural decisions, PRD authoring, implementation plan authoring, six slice prompt authoring, pre-flight corrections from the actual v0.5 codebase, and the identifier rebase).
- **Decisions.** DEC-105 (version bundling for the styling work: separate v0.6 release rather than bundled into v0.5), DEC-106 (six-slice structure A–F reconciling the workstream-plan strawman), DEC-107 (slice acceptance pattern: per-slice screenshots + closeout WCAG check).
- **Planning items.** No changes. PI-001 already reflects the parallel-workstream reopening (from DEC-076); slice work folds into it.
- **References.** Four references: three `decided_in` (DEC-105/106/107 → SES-030) plus one `is_about` (SES-030 → PI-001).

This is a one-shot apply prompt. The underlying script is idempotent (HTTP 409 conflict is treated as already-present and continues), so re-running is safe if interrupted. Post-apply this prompt should not be re-run as a matter of routine.

---

## Project context

Per DEC-004, the v2 database is the source of truth for all v2 artifacts; per DEC-008, the JSON snapshots under `PRDs/product/crmbuilder-v2/db-export/` are renders, not authored copies. Records are inserted via the v2 access layer (HTTP POST to `http://127.0.0.1:8765`), which transactionally regenerates the JSON snapshots.

The `apply_close_out.py` script reads a sectioned JSON payload and POSTs each section in fixed order: `session` → `decisions` → `planning_items` → `references`. The `planning_items` section in `ses_030.json` is an empty array, so the script skips that POST loop entirely.

Current expected pre-state (immediately before this apply runs):

- `decisions.json` snapshot ends at **DEC-104** (latest v0.5 SES-029 decision, assuming SES-029 has already been applied locally; if not, ends at whatever the most recent applied decision is).
- `planning_items.json` snapshot ends at **PI-017** (latest applied PI; no change from v0.5 work since v0.5 didn't add a PI in its SES-029 closeout).
- `sessions.json` snapshot ends at **SES-029** (the most recent v0.5 closeout).
- One payload in `close-out-payloads/` not yet applied: `ses_030.json` (this one — the styling Conversation 2 closeout). The v0.5 close-out payloads (`ses_028.json`, `ses_029.json`) may or may not have been applied locally yet — if not, apply them first via their own apply prompts before this one. If `ses_030.json` has already been partially applied (interrupted prior run), the script's 409-handling absorbs the difference.
- HEAD on `main` is at or past the v0.6 PRD / implementation plan / slice prompt commits and the identifier rebase commit (`7255667`).

If the actual snapshot state is different (more advanced — e.g., SES-030 already applied), the apply script's 409-handling absorbs the difference. The pre-flight verification step calls this out either way.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root (the directory containing `CLAUDE.md`, `crmbuilder-v2/`, and `PRDs/`).

2. **Confirm `git status` is clean.** If there are uncommitted changes, stop and report to Doug before proceeding. The post-apply snapshot regeneration produces tracked-file changes; starting from a clean state ensures those changes are isolated and committable as one unit.

3. **Confirm git identity is set.**

   ```bash
   git config user.name "Doug Bower"
   git config user.email "doug@dougbower.com"
   ```

4. **Pull latest from origin:**

   ```bash
   git pull --rebase origin main
   ```

   Stop and report if there are conflicts.

5. **Confirm the payload file exists:**

   ```bash
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_030.json
   ```

   Stop if missing.

6. **Confirm the v2 API is running:**

   ```bash
   curl -sf http://127.0.0.1:8765/decisions >/dev/null && echo "API up" || echo "API DOWN"
   ```

   If the API is not running, ask Doug to start it (`cd crmbuilder-v2 && uv run crmbuilder-v2-api &`) before proceeding. Do not attempt to start it yourself — the API runs in the foreground in Doug's shell session.

7. **Capture pre-state for verification.** Record the current highest identifier in each entity type so the post-apply step has a clear baseline:

   ```bash
   # Decisions
   curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys, json; d=json.load(sys.stdin)['data']; print('Latest DEC:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"

   # Sessions
   curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys, json; d=json.load(sys.stdin)['data']; print('Latest SES:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"

   # References count
   curl -s http://127.0.0.1:8765/references | python3 -c "import sys, json; refs=json.load(sys.stdin)['data']; print('Refs total:', len(refs))"
   ```

   Expected pre-state: `DEC-104` (post-SES-029 apply), `SES-029`, reference count whatever v0.5's work brought it to. Report the values back so the post-apply step has a clear baseline.

---

## Workflow

### Step 1 — Apply SES-030 standard close-out payload (session + decisions + references)

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_030.json
cd ..
```

Expected output: each record reports `OK` (created) or `SKIP` (409, already present). The script exits 0 on full success. Stop and report if it exits non-zero.

The payload's `planning_items` section is an empty array — the script's planning-items loop is a no-op. After this step:

- Sessions snapshot should contain SES-030.
- Decisions snapshot should contain DEC-105, DEC-106, DEC-107 (three new decisions).
- Four new references should exist: three `decided_in` (DEC-105/106/107 → SES-030) plus one `is_about` (SES-030 → PI-001).
- Planning items snapshot should be unchanged (still ends at PI-017).

### Step 2 — Verify post-state

Confirm the expected records exist via direct API queries:

```bash
# All 3 new decisions
for id in DEC-105 DEC-106 DEC-107; do
  curl -sf http://127.0.0.1:8765/decisions/$id >/dev/null && echo "$id OK" || echo "$id MISSING"
done

# The new session
curl -sf http://127.0.0.1:8765/sessions/SES-030 >/dev/null && echo "SES-030 OK" || echo "SES-030 MISSING"

# Reference existence checks (3 decided_in + 1 is_about)
curl -s http://127.0.0.1:8765/references | python3 -c "
import sys, json
refs = json.load(sys.stdin)['data']
for dec in ['DEC-105','DEC-106','DEC-107']:
    found = any(r['source_id']==dec and r['target_id']=='SES-030' and r['relationship']=='decided_in' for r in refs)
    print(f'{dec}->SES-030 decided_in:', found)
is_about_found = any(r['source_id']=='SES-030' and r['target_id']=='PI-001' and r['relationship']=='is_about' for r in refs)
print(f'SES-030->PI-001 is_about:', is_about_found)
print('Refs total:', len(refs))
"
```

All decision and session checks should report `OK`. All three `decided_in` reference-existence checks should report `True`, and the `is_about` check should report `True`. Refs total should be the pre-state count + 4 (or higher if intervening writes have landed; report any anomaly).

Then confirm the JSON snapshots were regenerated:

```bash
git status PRDs/product/crmbuilder-v2/db-export/
```

Expected modifications: `decisions.json`, `sessions.json`, `references.json`, and `change_log.json`. (`planning_items.json` is unchanged because no PI records were touched.) If any expected file is unchanged or unexpectedly absent from the diff, the export hook may have failed — stop and report before committing.

### Step 3 — Commit

Single commit covering all snapshot regenerations:

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git status   # confirm only db-export changes are staged
git commit -m "v2: apply SES-030 close-out payload

Inserts:
- SES-030 (styling Conversation 2 record — build planning for v0.6:
  produced ui-PRD-v0.6.md, ui-v0.6-implementation-plan.md, and six
  slice prompts. Pre-flight corrections from actual v0.5 codebase
  shape: styling.py rewritten in place not new tokens.py; about_-
  dialog.py at ui/ top level not in dialogs/; EntityCrudDeleteDialog
  shares crud_dialog.py with EntityCrudDialog; third dialog base
  versioned_replace_dialog.py covers Charter/Status. Identifier
  rebase at close-out: SES-028 -> SES-030; DEC-095/096/097 ->
  DEC-105/106/107 (parallel-workstream consumption per DEC-076.)
- DEC-105 (version bundling for the styling work: ship as separate
  v0.6 release rather than bundled into v0.5. Functional independence
  of the two workstreams is load-bearing; bundling permanently blurs
  v2's release-version navigation index. Cost: one additional
  closeout cycle.)
- DEC-106 (six-slice structure A-F: Foundation + About, Sidebar +
  master-pane delegate, Panel retrofits + ReferencesSection, Dialogs
  + form controls, Status + crash banner, Closeout. Reconciles three
  differences from workstream plan §5.3 strawman: pull master-pane
  delegate to its own slice; collapse governance + methodology
  retrofits into omnibus slice; promote status + crash banner to
  their own slice.)
- DEC-107 (slice acceptance pattern: per-slice after-state screen-
  shots committed to styling-screenshots/slice-{X}/ plus eyeball
  verification against the design pass; automated WCAG AA contrast
  check at slice F closeout. The WCAG check is a build gate.)
- 4 references: 3 decided_in (DEC-105/106/107 -> SES-030) + 1 is_-
  about (SES-030 -> PI-001 — this conversation is about discharging
  PI-001)

No planning item changes. All v0.6 build work folds into existing
PI-001 (parent for the whole styling pass, already reopened as
parallel workstream by DEC-076).

Snapshot regeneration only - payload file is unchanged. The standard
apply script is idempotent on the 409 path; re-running is safe if
interrupted. This commit captures the resulting db-export state for
git tracking.

After this apply lands, v0.6 build executes via the six slice
prompts in sequence (A->B->C->D->E->F, strict ordering, no
parallelism within v0.6). v0.5 ships first per DEC-105. When v0.6
slices complete, slice F bumps __version__ to 0.6.0, adds README
v0.6 release note, and runs the WCAG contrast check. Post-slice-F
operator steps: status entity versioned-replace from 'v0.5 complete'
to 'v0.6 complete' via the desktop versioned-replace dialog; no
further session record application (SES-030 is THIS payload).
"
```

### Step 4 — Push

```bash
git push origin main
```

Stop and report if push fails for any reason (rejection, auth, etc.).

---

## Done

After Step 4 completes, the styling Conversation 2 close-out is fully landed in the v2 governance database and committed to origin. Doug pulls locally; no further action required against this prompt.

The PRD, implementation plan, and six slice prompts were committed alongside the close-out payload and apply prompt across multiple commits; all are on `main` by the time this prompt runs.

Next steps (post-apply, operator-authored and Claude-Code-authored):

- **v0.6 build execution.** Six slice prompts at `prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.6-{A..F}-*.md` execute in sequence via Claude Code. v0.5 ships first per DEC-105; v0.6 begins after v0.5's release. After slice F lands, Doug runs the status entity versioned-replace through the desktop UI to update from "v0.5 complete" to "v0.6 complete".
- **Per-slice screenshot capture.** Per DEC-107, Doug captures after-state screenshots for each visual slice (A through E) and commits them to `PRDs/product/crmbuilder-v2/styling-screenshots/slice-{X}/` as separate operator commits.
- **PI-001 close.** When v0.6 ships, PI-001 (the styling pass parent planning item) transitions to its terminal status via the desktop UI. The PI was reopened as a parallel workstream by DEC-076; v0.6 discharges its full scope.
