# CLAUDE-CODE-PROMPT-apply-close-out-ses-029

**Last Updated:** 05-16-26 21:30
**Operating mode:** detail
**Series:** apply-close-out
**Status:** Ready to execute
**Companion conversation:** Claude.ai v0.5 Conversation 2 (build planning) on 05-16-26 that produced `PRDs/product/crmbuilder-v2/ui-PRD-v0.5.md`, `PRDs/product/crmbuilder-v2/ui-v0.5-implementation-plan.md`, and the five slice build prompts at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.5-{A..E}-*.md`.

**Note on numbering.** This payload reflects the three-way numbering collision that resolved at closeout. The parallel PI-001 styling workstream's Conversation 1 (SES-027) close-out applied first claiming DEC-087 through DEC-094 (its `close-out-payloads/ses_027.json` apply landed at commit `5b7a504`). The styling Conversation 2 ran in parallel with this v0.5 Conversation 2 and committed `ui-PRD-v0.6.md` plus `ui-v0.6-implementation-plan.md` mid-way through this conversation (at commits `9f57c6a` and `ec5c806`); the styling Conversation 2 claims SES-028 plus DEC-095 through DEC-097 for its v0.6 PRD authoring (its close-out payload presumably forthcoming under `close-out-payloads/ses_028.json`). This v0.5 Conversation 2 payload therefore claims SES-029 plus DEC-098 through DEC-104 — the next available range past both styling payloads' claims. If the styling Conversation 2's `ses_028.json` close-out payload has not yet been applied when this prompt runs, that's fine: `apply_close_out.py` is idempotent on the 409 path, and the SES-029 records claim numbers past where the styling Conversation 2 will land. Mechanical bookkeeping per the v0.4 SES-016 → SES-017 precedent.

---

## Purpose

Apply the SES-029 close-out payload to the local v2 governance database. One substantive operation: POST a new session, seven decisions, and seven references via the standard `apply_close_out.py` script. No planning-item patches — the v0.5 Conversation 2 produced no new PIs (PI-017 was authored at SES-026; no new tracked work surfaced in Conversation 2).

Net effect on the v2 database after this prompt completes:

- **Session.** SES-029 (v0.5 Conversation 2 build-planning record — full topics_covered prose covering pre-flight, the seven decisions in narrative order, the PRD and implementation plan and five slice prompts authoring, the compaction event partway through, and the mid-conversation discovery of the v0.6 PRD landing on origin/main which triggered the §9 coordination rewrite and the numbering collision resolution).
- **Decisions.** DEC-098 (v0.5 five-slice breakdown with foundation+migration combined in slice A), DEC-099 (engagement UI affordance placement — top-strip switching + Engagements sidebar group + dual paths to management), DEC-100 (single-gesture engagement creation+activation with graceful inline failure recovery), DEC-101 (forbid soft-delete on active engagement with inline redirect to switch), DEC-102 (null default for engagement_export_dir on new engagement records), DEC-103 (meta DB JSON exports at db-export/meta/engagements.json), DEC-104 (v0.5 UI PRD approval — release scope and slice plan accepted; §9 coordination rewritten at closeout).
- **Planning items.** No changes.
- **References.** Seven `decided_in` references (DEC-098..DEC-104 → SES-029).

This is a one-shot apply prompt. The underlying script is idempotent (HTTP 409 conflict is treated as already-present and continues), so re-running is safe if interrupted.

---

## Project context

Per DEC-004, the v2 database is the source of truth for all v2 artifacts; per DEC-008, the JSON snapshots under `PRDs/product/crmbuilder-v2/db-export/` are renders, not authored copies. Records are inserted via the v2 access layer (HTTP POST to `http://127.0.0.1:8765`), which transactionally regenerates the JSON snapshots.

The `apply_close_out.py` script reads a sectioned JSON payload and POSTs each section in fixed order: `session` → `decisions` → `planning_items` → `references`. The `planning_items` section in `ses_029.json` is an empty array, so the script skips that POST loop entirely.

Current expected pre-state:

- `decisions.json` snapshot ends at **DEC-094** (last styling Conversation 1 decision; from the SES-027 apply at commit `5b7a504`), OR at **DEC-097** if the styling Conversation 2's `ses_028.json` apply has also already run.
- `planning_items.json` snapshot ends at **PI-017** (added by v0.5 SES-026 apply).
- `sessions.json` snapshot ends at **SES-027** OR **SES-028** depending on whether the styling Conversation 2's close-out has applied.
- One payload in `close-out-payloads/` not yet applied: `ses_029.json` (this one). The styling Conversation 2's `ses_028.json` payload may or may not be present yet; if present and not applied, run its apply prompt first; if applied already, the pre-state values shift accordingly.
- HEAD on `main` is at or past the v0.5 Conversation 2 closeout commit (the commit that introduced this payload, the PRD, the implementation plan, and the five slice build prompts).

If the actual snapshot state is different, the apply script's 409-handling absorbs the difference. The pre-flight verification step calls this out either way.

**The v0.5 multi-engagement routing is not yet live.** This apply prompt runs against the current CRMBUILDER engagement's database — the same single `v2.db` that has been the source of truth since v0.3. v0.5 slice A is the next executable Claude Code prompt; until it runs, the v2 database is at v0.4 state. This apply prompt's records land in `v2.db`; when slice A runs, the dogfood migration copies `v2.db` to `engagements/CRMBUILDER.db` (preserving all the records including the seven new decisions and SES-029).

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
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_029.json
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

   Expected pre-state: `DEC-094` and `SES-027` (if styling Conversation 2's `ses_028.json` apply has NOT yet run); OR `DEC-097` and `SES-028` (if it has). Reference count varies accordingly. If pre-state shows `DEC-086` / `SES-026` (styling SES-027 apply not yet run), stop and run `CLAUDE-CODE-PROMPT-apply-close-out-ses-027.md` first; do not proceed with this one out of order. If pre-state is at or past DEC-104 / SES-029, this apply has already partially or fully run; the 409-handling absorbs the re-run safely. Report the values back so the post-apply step has a clear baseline.

---

## Workflow

### Step 1 — Apply SES-029 standard close-out payload (session + decisions + references)

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_029.json
cd ..
```

Expected output: each record reports `OK` (created) or `SKIP` (409, already present). The script exits 0 on full success. Stop and report if it exits non-zero.

The payload's `planning_items` section is an empty array — the script's planning-items loop is a no-op. After this step:

- Sessions snapshot should contain SES-029.
- Decisions snapshot should contain DEC-098 through DEC-104 (seven new decisions).
- Seven new `decided_in` references should exist (DEC-098..DEC-104 → SES-029).
- Planning items snapshot should be unchanged (still ends at PI-017).

### Step 2 — Verify post-state

Confirm the expected records exist via direct API queries:

```bash
# All 7 new decisions
for id in DEC-098 DEC-099 DEC-100 DEC-101 DEC-102 DEC-103 DEC-104; do
  curl -sf http://127.0.0.1:8765/decisions/$id >/dev/null && echo "$id OK" || echo "$id MISSING"
done

# The new session
curl -sf http://127.0.0.1:8765/sessions/SES-029 >/dev/null && echo "SES-029 OK" || echo "SES-029 MISSING"

# Reference existence checks (all 7 decided_in)
curl -s http://127.0.0.1:8765/references | python3 -c "
import sys, json
refs = json.load(sys.stdin)['data']
for dec in ['DEC-098','DEC-099','DEC-100','DEC-101','DEC-102','DEC-103','DEC-104']:
    found = any(r['source_id']==dec and r['target_id']=='SES-029' and r['relationship_kind']=='decided_in' for r in refs)
    print(f'{dec}->SES-029 decided_in:', found)
print('Refs total:', len(refs))
"
```

All decision and session checks should report `OK`. All seven reference-existence checks should report `True`. Refs total should be the pre-state count + 7. Report any anomaly.

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
git commit -m "v2: apply SES-029 close-out payload

Inserts:
- SES-029 (v0.5 Conversation 2 build-planning record — release PRD
  authoring, implementation plan authoring, five slice build prompts
  authoring; ten kickoff questions settled; three-way numbering
  collision resolved at closeout (styling SES-027 applied first;
  styling Conversation 2 ran in parallel claiming SES-028/DEC-095-
  097); this payload claims SES-029/DEC-098-104)
- DEC-098 (v0.5 five-slice breakdown: A foundation+migration combined,
  B engagement schema+access+REST, C panel UI, D switching+single-
  gesture creation+activation, E closeout; A1/A2 split fallback
  documented for slice-A-bloat risk)
- DEC-099 (engagement UI affordance placement: always-visible top-
  strip switching widget + Engagements sidebar group above Governance
  with one entry + dual paths to the management panel via sidebar
  entry and picker footer 'Manage engagements...' item; picker
  ordering rules and empty-state handling)
- DEC-100 (single-gesture engagement creation+activation: New
  Engagement dialog runs POST + DB file creation + activation in one
  click with three-label progress indicator; graceful inline failure
  recovery with 'Try switching now' / 'Stay in <previous>' affordances
  if activation fails after both creates succeed)
- DEC-101 (forbid soft-delete on currently-active engagement: delete
  dialog refuses with inline redirect to switch first; last-engagement
  edge case wording redirects to create another; drift-recovery path
  retained as safety net for cross-restart desync)
- DEC-102 (null default for engagement_export_dir on new engagement
  records: dialog field empty by default with 'Optional - leave blank
  to disable auto-export' placeholder; dogfood migration explicitly
  sets a non-null value for CRMBUILDER, divergent from dialog default
  because dogfood has a known export location)
- DEC-103 (meta DB JSON exports at PRDs/product/crmbuilder-v2/db-
  export/meta/engagements.json: subdirectory parallel to dogfood's
  engagement-content exports; file-watch refresh per the standard
  v0.3+ pattern; access-layer hook regenerates on write within the
  same transaction)
- DEC-104 (v0.5 UI PRD approval: 10 in-scope items, 16 out-of-scope
  items, five-slice plan, E1-E8 closeout acceptance criteria; PRD
  Section 9 coordination rewritten at closeout after styling
  Conversation 2's v0.6 PRD landed on origin/main mid-conversation;
  v0.5 ships first with Qt-default styling per DEC-095's separate-
  release sequencing; v0.6 retrofits engagement panel as the 13th
  panel covered by v0.6 slice C; PRD transitions from Draft to
  Approved)
- 7 decided_in references (DEC-098..DEC-104 -> SES-029)

No planning item changes. PI-017 (multi-tenant API+MCP migration for
prototype-to-production transition) was authored at SES-026; no new
tracked work surfaced in this conversation.

Snapshot regeneration only - payload file is unchanged. The standard
apply script is idempotent on the 409 path; re-running is safe if
interrupted. This commit captures the resulting db-export state for
git tracking.

After this apply lands, slice A is the next executable Claude Code
prompt: foundation infrastructure plus dogfood migration. Doug runs
it at his local terminal; slice A produces the meta DB plus two-
database API plus ActiveEngagementContext plus the dogfood migration
that copies v2.db to engagements/CRMBUILDER.db with backup-verify-
delete discipline. After slice A completes and Doug pushes, slice B
is queued; the linear A->B->C->D->E chain runs through slice E
closeout (version 0.5.0, README release note, end-to-end integration
smoke). Status remains 'v0.4 complete' until slice E lands and the
status entity is operator-updated. v0.6 styling work runs in
parallel; v0.6 slice C retrofits v0.5's engagement panel.
"
```

### Step 4 — Push

```bash
git push origin main
```

Stop and report if push fails for any reason (rejection, auth, etc.).

---

## Done

After Step 4 completes, the v0.5 Conversation 2 close-out is fully landed in the v2 governance database and committed to origin. No further action required against this prompt.

Next executable Claude Code prompt: `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.5-A-foundation-and-dogfood-migration.md` (slice A). Doug opens Claude Code in the crmbuilder repo and instructs it to execute the slice A prompt. After slice A completes and Doug pushes, slice B is queued; and so on through slice E.

The parallel PI-001 styling workstream's v0.6 release runs against its own conversation thread and execution stream. Per DEC-095's separate-release sequencing, v0.5 ships first with Qt-default styling on its new engagement-management surfaces; v0.6 retrofits the styling design pass across all panels including v0.5's engagement panel as the 13th panel covered by v0.6 slice C.
