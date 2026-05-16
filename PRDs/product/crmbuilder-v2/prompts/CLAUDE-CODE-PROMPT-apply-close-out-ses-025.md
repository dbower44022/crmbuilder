# CLAUDE-CODE-PROMPT-apply-close-out-ses-025

**Last Updated:** 05-16-26 14:00
**Operating mode:** detail
**Series:** apply-close-out
**Status:** Ready to execute
**Companion conversation:** Claude.ai v0.5-orientation conversation on 05-16-26 that produced `PRDs/product/crmbuilder-v2/v0.5-engagement-management-workstream-plan.md`, `PRDs/product/crmbuilder-v2/styling-workstream-plan.md`, and the Status: Deferred header on `PRDs/product/crmbuilder-v2/methodology-schemas-cbm-paper-test-kickoff.md` (all three committed at `ef365bc` on origin/main).

---

## Purpose

Apply the SES-025 close-out payload to the local v2 governance database. Three substantive operations: POST a new session and three decisions plus three references (handled by the standard `apply_close_out.py`), and PATCH the existing PI-001 record to reflect its reopening as a parallel workstream (handled by a single inline `curl` because `apply_close_out.py` is POST-only).

Net effect on the v2 database after this prompt completes:

- **Session.** SES-025 (v0.5-orientation conversation record, full topics_covered / summary / artifacts_produced / in_flight_at_end per the payload).
- **Decisions.** DEC-075 (v0.5 release scope; build engagement management in v2 not bridge to v1), DEC-076 (PI-001 reopens as parallel workstream), DEC-077 (paper-test deferred until v0.5 ships and CBM engagement is created).
- **Planning items.** PI-001 description updated via PATCH to reflect reopening; no new PIs.
- **References.** Three `decided_in` references (DEC-075 → SES-025, DEC-076 → SES-025, DEC-077 → SES-025).

This is a one-shot apply prompt. The underlying script is idempotent (HTTP 409 conflict is treated as already-present and continues) and the PATCH is idempotent by construction (the PATCH body matches the desired final state regardless of how many times it fires), so re-running is safe if interrupted. Post-apply this prompt should not be re-run as a matter of routine.

---

## Project context

Per DEC-004, the v2 database is the source of truth for all v2 artifacts; per DEC-008, the JSON snapshots under `PRDs/product/crmbuilder-v2/db-export/` are renders, not authored copies. Records are inserted via the v2 access layer (HTTP POST/PATCH to `http://127.0.0.1:8765`), which transactionally regenerates the JSON snapshots.

The `apply_close_out.py` script reads a sectioned JSON payload and POSTs each section in fixed order: `session` → `decisions` → `planning_items` → `references`. The PI-001 PATCH is performed separately because the script does not support update operations (per the SES-011 precedent at `apply_ses_011_planning_records.py`, which used a custom one-off script combining POST + PATCH). This prompt's payload sets `planning_items: []` in the JSON to skip the planning-items POST section entirely; PI-001 is handled by a single `curl` between the apply script and the verification step.

Current expected pre-state (immediately after `ef365bc` commit landed on origin):

- `decisions.json` snapshot ends at **DEC-074** (last v0.4 closeout decision)
- `planning_items.json` snapshot ends at **PI-016** (last v0.4 closeout PI)
- `sessions.json` snapshot ends at **SES-024** (v0.4 slice F closeout)
- One payload pending in `close-out-payloads/`: `ses_025.json`, not yet applied
- `PI-001` description currently reflects the four-times-deferred state (per the PATCH at `apply_ses_011_planning_records.py` from SES-011)
- HEAD on `main` is at or past `ef365bc` (the v0.5-orientation conversation's three-document commit)

If the actual snapshot state is different (more advanced — e.g., SES-025 already applied), the apply script's 409-handling absorbs the difference. The pre-flight verification step calls this out either way.

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

   Stop and report if there are conflicts. Expected HEAD is at or past `ef365bc` (the v0.5-orientation conversation's three-document commit).

5. **Confirm the payload file exists:**

   ```bash
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_025.json
   ```

   Stop if missing.

6. **Confirm the v2 API is running:**

   ```bash
   curl -sf http://127.0.0.1:8765/decisions >/dev/null && echo "API up" || echo "API DOWN"
   ```

   If the API is not running, ask Doug to start it (`cd crmbuilder-v2 && uv run crmbuilder-v2-api &`) before proceeding. Do not attempt to start it yourself — the API runs in the foreground in Doug's shell session.

7. **Capture pre-state for verification.** Record the current highest identifier in each entity type, plus the current PI-001 description hash so the PATCH effect can be verified:

   ```bash
   # Decisions
   curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys, json; d=json.load(sys.stdin); print('Latest DEC:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"

   # Planning items
   curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys, json; d=json.load(sys.stdin); print('Latest PI:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"

   # Sessions
   curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys, json; d=json.load(sys.stdin); print('Latest SES:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"

   # PI-001 description SHA256 (pre-patch fingerprint)
   curl -s http://127.0.0.1:8765/planning-items/PI-001 | python3 -c "import sys, json, hashlib; d=json.load(sys.stdin); print('PI-001 desc SHA pre:', hashlib.sha256(d['description'].encode()).hexdigest()[:12])"
   ```

   Expected pre-state: `DEC-074`, `PI-016`, `SES-024`, and a PI-001 description hash that does NOT match the post-patch hash captured at Step 3. Report the four values back so the post-apply step has a clear baseline.

---

## Workflow

### Step 1 — Apply SES-025 standard close-out payload (session + decisions + references)

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_025.json
cd ..
```

Expected output: each record reports `OK` (created) or `SKIP` (409, already present). The script exits 0 on full success. Stop and report if it exits non-zero.

The payload's `planning_items` section is intentionally empty — PI-001 is handled in Step 2 below. After this step:

- Sessions snapshot should contain SES-025.
- Decisions snapshot should contain DEC-075, DEC-076, DEC-077.
- Three new `decided_in` references should exist (DEC-075 → SES-025, DEC-076 → SES-025, DEC-077 → SES-025).
- Planning items snapshot should be unchanged (still ends at PI-016).

### Step 2 — Patch PI-001 to reflect reopening as a parallel workstream

PI-001's description is amended via a single PATCH. The desired final-state description is below; copy it verbatim into the `curl` body (preserving newlines and the embedded paths):

```bash
curl -sf -X PATCH http://127.0.0.1:8765/planning-items/PI-001 \
  -H "Content-Type: application/json" \
  -d '{"description": "Full styling design pass per DEC-024. Originally deferred four times (DEC-024 → DEC-026 → DEC-037 → DEC-042) on the CBM-redo-friction trigger principle. **Reopened as a parallel workstream by DEC-076 (05-16-26)** because the trigger condition (CBM-redo Phase 1 surfacing visual friction on the four v0.4 methodology panels) cannot fire in v0.5'\''s timeframe — CBM redo waits on v0.5 (DEC-075) plus the paper-test (DEC-077) plus Phase 1 itself, and the four-deferral pattern with progressively-elaborate trigger conditions that never fire has become an anti-pattern. The pass establishes a coherent visual language for the v2 desktop application: design tokens (palette with semantic naming, typography scale, spacing scale, radius/border/elevation tokens, density target), visual decisions for major component classes (panels, sidebar, buttons, form controls, dialogs, tables), and implementation across all governance and methodology panels. **Workstream structure (per `PRDs/product/crmbuilder-v2/styling-workstream-plan.md`):** two conversations — Conversation 1 produces the design pass document at `PRDs/product/crmbuilder-v2/styling-design-pass.md`; Conversation 2 produces the styling PRD, implementation plan, and slice build prompts. Strawman five build slices follow (foundation; governance panel retrofit; methodology panel retrofit; dialog and form-control polish; closeout). **Boundary discipline with v0.5 (per DEC-076):** styling owns the visual layer (QSS, design tokens, panel chrome, sidebar visuals, About dialog, hover/focus/disabled states); v0.5 owns the data/routing layer (config, ActiveEngagementContext, alembic, API routing, engagement entity). One coupling point: v0.5'\''s engagement panel inherits whatever tokens are current at slice land time; either order ships fine. **Version-bundling question** (v0.5 vs. v0.6) deferred to the styling workstream'\''s Conversation 2."}'
echo
```

Expected output: a JSON response with the updated PI-001 record, HTTP 200. The `description` field in the response should match the body sent. Stop and report if status is not 200 or if `description` does not match.

### Step 3 — Verify post-state

Confirm the expected records exist via direct API queries:

```bash
# All 3 new decisions
for id in DEC-075 DEC-076 DEC-077; do
  curl -sf http://127.0.0.1:8765/decisions/$id >/dev/null && echo "$id OK" || echo "$id MISSING"
done

# The new session
curl -sf http://127.0.0.1:8765/sessions/SES-025 >/dev/null && echo "SES-025 OK" || echo "SES-025 MISSING"

# PI-001 post-patch fingerprint
curl -s http://127.0.0.1:8765/planning-items/PI-001 | python3 -c "import sys, json, hashlib; d=json.load(sys.stdin); print('PI-001 desc SHA post:', hashlib.sha256(d['description'].encode()).hexdigest()[:12])"

# References count delta
curl -s http://127.0.0.1:8765/references | python3 -c "import sys, json; refs=json.load(sys.stdin); print('Refs total:', len(refs)); print('DEC-075→SES-025:', any(r['source_id']=='DEC-075' and r['target_id']=='SES-025' for r in refs)); print('DEC-076→SES-025:', any(r['source_id']=='DEC-076' and r['target_id']=='SES-025' for r in refs)); print('DEC-077→SES-025:', any(r['source_id']=='DEC-077' and r['target_id']=='SES-025' for r in refs))"
```

All decision and session checks should report `OK`. The PI-001 post-patch SHA should DIFFER from the pre-patch SHA captured at pre-flight Step 7. All three reference-existence checks should report `True`. Refs total should be 77 + 3 = 80 (or higher if intervening writes have landed; report any anomaly).

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
git commit -m "v2: apply SES-025 close-out payload

Inserts:
- SES-025 (v0.5-orientation conversation record — surfaced v1/v2
  client-management overlap, committed v2 to building engagement
  management as v0.5, reopened PI-001 as parallel workstream,
  deferred paper-test)
- DEC-075 (v0.5 release scope: engagement management + multi-instance
  routing as v2-native capability, not a bridge to v1's Client master)
- DEC-076 (PI-001 reopens as parallel workstream alongside v0.5,
  replacing fifth deferral)
- DEC-077 (paper-test deferred until v0.5 ships and CBM engagement
  is created)
- 3 decided_in references (DEC-075/076/077 → SES-025)

Updates:
- PI-001 description amended via PATCH to reflect reopening as a
  parallel workstream; references DEC-076 and styling-workstream-plan.md.
  Status remains Open; meaning changes from 'deferred work waiting for
  a trigger that never fires' to 'active parallel workstream with its
  own plan.'

Snapshot regeneration only — payload file is unchanged. The standard
apply script is idempotent on the 409 path; the PI-001 PATCH is
idempotent by construction. This commit captures the resulting
db-export state for git tracking.

After this apply lands, two Conversation 1's queue in fresh Claude.ai
chats: v0.5 architecture-plus-schema (against v0.5-conversation-1-
kickoff.md) and styling design pass (against styling-conversation-1-
kickoff.md). Either can open first."
```

Do **not** push. Doug pushes per the project convention.

### Step 5 — Report

Print a short summary of what was applied:

- Number of decisions created vs skipped (409) — expected 3 created
- Number of references created vs skipped — expected 3 created
- Number of sessions created vs skipped — expected 1 created
- PI-001 PATCH result (200 OK and description hash changed)
- The commit SHA
- A reminder that the commit needs to be pushed by Doug
- An explicit note that this apply closes the v0.5-orientation conversation and the next two conversations to open are v0.5 Conversation 1 (kickoff at `PRDs/product/crmbuilder-v2/v0.5-conversation-1-kickoff.md`) and styling Conversation 1 (kickoff at `PRDs/product/crmbuilder-v2/styling-conversation-1-kickoff.md`). They can open in any order, in fresh Claude.ai chats.

---

## Error handling

- **Standard apply script exits non-zero on a non-409 error.** Stop, do not commit, do not run the PATCH yet, report the full script output to Doug. The most likely causes are API not running, payload file malformed, or a validation error at the API layer.

- **PATCH returns non-200 (e.g., 404 PI-001 not found, or 400 validation error).** Stop, do not commit. If 404, PI-001 has been deleted or renamed — flag the discrepancy. If 400, the PATCH body has a field name the schema doesn't accept — print the error response and stop.

- **PATCH succeeds but PI-001 description SHA doesn't change.** This means the PATCH body matched the existing description exactly — the PATCH ran but had no effect. Most likely cause: this apply has already been run once and the PATCH already landed. Skip the commit step and report.

- **Snapshot not regenerated.** The export hook in the access layer may have failed silently. Stop, do not commit. Doug investigates by checking the API server logs.

- **Pre-state already past SES-025.** If `Latest SES` from the pre-flight is already `SES-025` or later, the work has already been applied. Report this finding; do not run the apply again (still safe given idempotency, but unnecessary). Still run the PATCH idempotency check — if PI-001's description SHA matches the post-patch fingerprint already, the work is fully complete. No commit needed.

- **Pre-state earlier than SES-024.** If `Latest SES` from the pre-flight is `SES-023` or earlier, the v0.4 closeout records may not have all landed. Stop and report to Doug — the prerequisite work is missing, and this prompt should not run until the v0.4 closeout records are complete.

- **`git status` not clean at start.** Stop and report. Do not stash. Doug decides how to handle the uncommitted changes before re-running.

---

## What this prompt does NOT do

- Does not push the commit. Doug pushes.
- Does not modify the payload file. It is a read-only input.
- Does not modify the apply script. The script is generic; per-payload variation is in the payload file itself and the PATCH step in this prompt.
- Does not author additional decisions, planning items, or sessions beyond what the payload file and the PATCH step contain. If something is missing from the payload, fix the payload first and re-author it; do not work around in this prompt.
- Does not write a status update. Release status remains `"v0.4 complete"` until v0.5 actually ships; the v0.5-orientation conversation is a planning conversation that does not change shipped state.
- Does not open the v0.5 Conversation 1 or styling Conversation 1. Those are separate Claude.ai chats Doug opens against the two kickoff documents (`v0.5-conversation-1-kickoff.md`, `styling-conversation-1-kickoff.md`) — outside this prompt's scope.

---

*End of prompt.*
