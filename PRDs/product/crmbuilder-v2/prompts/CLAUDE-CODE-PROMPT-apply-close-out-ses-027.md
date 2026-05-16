# CLAUDE-CODE-PROMPT-apply-close-out-ses-027

**Last Updated:** 05-16-26 16:00
**Operating mode:** detail
**Series:** apply-close-out
**Status:** Ready to execute
**Companion conversation:** Claude.ai styling Conversation 1 on 05-16-26 that produced `PRDs/product/crmbuilder-v2/styling-design-pass.md` (~709 lines, design tokens + visual decisions for major component classes + application priorities + acceptance criteria for v0.5/v0.6 styling work).


**Note on numbering.** This conversation initially proposed SES-026 / DEC-078..DEC-085 but those were consumed in flight by the parallel v0.5 Conversation 1 (commit `5c7e7a6`), which authored its own SES-026 close-out with DEC-078..DEC-086 and PI-017. Per the parallel-workstream coupling discipline in DEC-076, the styling workstream rebased its numbering to SES-027 / DEC-087..DEC-094 to avoid collision. No content change; numbering only.

---

## Purpose

Apply the SES-027 close-out payload to the local v2 governance database. One substantive operation: POST a new session, eight decisions, and eight references via the standard `apply_close_out.py` script. No PI patches this time — all deferred design-pass work folds into existing PI-001 (which already reflects the parallel-workstream reopening from DEC-076) or is documented as explicitly out of scope in `styling-design-pass.md` §4.6.

Net effect on the v2 database after this prompt completes:

- **Session.** SES-027 (styling Conversation 1 record — full topics_covered prose covering pre-flight, decision-by-decision walk-through across the foundation token layer and the component visual decisions, document creation arc, and close-out planning).
- **Decisions.** DEC-087 (density: Default — workstation context rules out compact and comfortable), DEC-088 (brand accent `#1F5FBF` plus 9-step cool-gray neutral family and harmonized status colors), DEC-089 (theme-keyed token-naming structure, dark-mode-ready without retrofit), DEC-090 (Inter Variable + JetBrains Mono Variable, bundled at app startup), DEC-091 (modal elevation only via `QGraphicsDropShadowEffect`; rest of app flat), DEC-092 (Lucide icon library, bundled additively as components need icons), DEC-093 (selected-state visual vocabulary: 3px left accent bar + tinted background; consistent across sidebar and master pane), DEC-094 (About dialog modest-showcase treatment).
- **Planning items.** No changes. PI-001 already reflects the parallel-workstream reopening (from DEC-076).
- **References.** Eight `decided_in` references (DEC-087..DEC-094 → SES-027).

This is a one-shot apply prompt. The underlying script is idempotent (HTTP 409 conflict is treated as already-present and continues), so re-running is safe if interrupted. Post-apply this prompt should not be re-run as a matter of routine.

---

## Project context

Per DEC-004, the v2 database is the source of truth for all v2 artifacts; per DEC-008, the JSON snapshots under `PRDs/product/crmbuilder-v2/db-export/` are renders, not authored copies. Records are inserted via the v2 access layer (HTTP POST to `http://127.0.0.1:8765`), which transactionally regenerates the JSON snapshots.

The `apply_close_out.py` script reads a sectioned JSON payload and POSTs each section in fixed order: `session` → `decisions` → `planning_items` → `references`. The `planning_items` section in `ses_027.json` is an empty array, so the script skips that POST loop entirely.

Current expected pre-state (immediately after the styling-design-pass commit lands on origin):

- `decisions.json` snapshot ends at **DEC-086** (last v0.5 SES-026 closeout decision), assuming SES-026 has already been applied locally; if not, ends at DEC-077
- `planning_items.json` snapshot ends at **PI-017** (added by v0.5 SES-026 apply), assuming SES-026 has been applied locally; if not, ends at PI-016
- `sessions.json` snapshot ends at **SES-026** (the v0.5 Conversation 1 architecture+schema closeout), assuming it has been applied locally; if not, ends at SES-025
- One payload in `close-out-payloads/` not yet applied: `ses_027.json` (this one — the styling Conversation 1 closeout). The v0.5 Conversation 1's `ses_026.json` may or may not have been applied locally yet — if not, apply it first via its own apply prompt before this one. If `ses_027.json` has already been partially applied (interrupted prior run), the script's 409-handling absorbs the difference; the pre-flight verification step calls this out either way.
- HEAD on `main` is at or past the styling-design-pass commit.

If the actual snapshot state is different (more advanced — e.g., SES-027 already applied), the apply script's 409-handling absorbs the difference. The pre-flight verification step calls this out either way.

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
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_027.json
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

   Expected pre-state: `DEC-086` (post-SES-026 apply) or `DEC-077` (if SES-026 has not yet been applied locally); `SES-026` or `SES-025`; reference count of 89 (post-SES-026 apply) or 80 (pre). Report the values back so the post-apply step has a clear baseline.

---

## Workflow

### Step 1 — Apply SES-027 standard close-out payload (session + decisions + references)

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_027.json
cd ..
```

Expected output: each record reports `OK` (created) or `SKIP` (409, already present). The script exits 0 on full success. Stop and report if it exits non-zero.

The payload's `planning_items` section is an empty array — the script's planning-items loop is a no-op. After this step:

- Sessions snapshot should contain SES-027.
- Decisions snapshot should contain DEC-087 through DEC-094 (eight new decisions).
- Eight new `decided_in` references should exist (DEC-087..DEC-094 → SES-027).
- Planning items snapshot should be unchanged (still ends at PI-016).

### Step 2 — Verify post-state

Confirm the expected records exist via direct API queries:

```bash
# All 8 new decisions
for id in DEC-087 DEC-088 DEC-089 DEC-090 DEC-091 DEC-092 DEC-093 DEC-094; do
  curl -sf http://127.0.0.1:8765/decisions/$id >/dev/null && echo "$id OK" || echo "$id MISSING"
done

# The new session
curl -sf http://127.0.0.1:8765/sessions/SES-027 >/dev/null && echo "SES-027 OK" || echo "SES-027 MISSING"

# Reference existence checks (all 8 decided_in)
curl -s http://127.0.0.1:8765/references | python3 -c "
import sys, json
refs = json.load(sys.stdin)['data']
for dec in ['DEC-087','DEC-088','DEC-089','DEC-090','DEC-091','DEC-092','DEC-093','DEC-094']:
    found = any(r['source_id']==dec and r['target_id']=='SES-027' and r['relationship_kind']=='decided_in' for r in refs)
    print(f'{dec}->SES-027 decided_in:', found)
print('Refs total:', len(refs))
"
```

All decision and session checks should report `OK`. All eight reference-existence checks should report `True`. Refs total should be the pre-state count + 8 (88 if SES-026 was not yet applied at pre-flight; 97 if SES-026 was already applied) (or higher if intervening writes have landed; report any anomaly).

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
git commit -m "v2: apply SES-027 close-out payload

Inserts:
- SES-027 (styling Conversation 1 record — design pass through the
  foundation token layer and component visual decisions for the v2
  desktop application)
- DEC-087 (density target: Default — workstation context (3x 4K
  monitors) rules out compact and comfortable; 4px spacing scale,
  28px list rows, 14px body)
- DEC-088 (brand accent #1F5FBF (steely blue) retires legacy navy
  #1F3864 stub; 9-step cool-gray neutral family retires the four
  ad-hoc grays; status colors harmonized with the accent)
- DEC-089 (theme-keyed token-naming structure; single light theme
  today; dark-mode-ready without consumer-code retrofit)
- DEC-090 (Inter Variable as sans-serif throughout + JetBrains Mono
  Variable as monospace; both OFL-licensed, bundled at app startup
  via QFontDatabase.addApplicationFont)
- DEC-091 (modal elevation only via QGraphicsDropShadowEffect; rest
  of app flat; single shadow.dialog token plus modal-backdrop
  overlay; popup/row/button elevation tiers explicitly rejected)
- DEC-092 (Lucide icon library, ISC-licensed, bundled additively as
  components need icons; runtime color-tinting via token system)
- DEC-093 (selected-state visual vocabulary: 3px left accent bar
  plus color.accent.subtle tinted background plus medium-weight
  text; applied consistently to both sidebar entries and master-
  pane rows via shared QStyledItemDelegate)
- DEC-094 (About dialog modest-showcase treatment: wordmark plus
  tagline header replaces default QFormLayout; metadata table
  restructured to two-line-per-row vertical list; brand-mark logo
  explicitly out of scope)
- 8 decided_in references (DEC-087..DEC-094 -> SES-027)

No planning item changes. All deferred design-pass work either folds
into existing PI-001 (the parent for the whole styling pass, already
reopened as parallel workstream by DEC-076) or is documented as
explicitly out of scope in styling-design-pass.md \xc2\xa74.6 (dark mode
values, animation, icon SVG authoring beyond initial set, Windows-
specific cross-platform testing, full accessibility audit beyond
WCAG AA contrast floor).

Snapshot regeneration only - payload file is unchanged. The standard
apply script is idempotent on the 409 path; re-running is safe if
interrupted. This commit captures the resulting db-export state for
git tracking.

After this apply lands, styling Conversation 2 (build planning) opens
in a fresh Claude.ai chat against styling-design-pass.md as input -
produces a styling release PRD, an implementation plan with slice
breakdown, and Claude Code slice build prompts. Also settles the
version-bundling question (ship as v0.5 bundled with engagement
management, or as v0.6 separately). v0.5 Conversation 1 may also
still be running in parallel; the two workstreams are coupled only
at v0.5's engagement panel coupling point per DEC-076's boundary
discipline.
"
```

### Step 4 — Push

```bash
git push origin main
```

Stop and report if push fails for any reason (rejection, auth, etc.).

---

## Done

After Step 4 completes, the styling Conversation 1 close-out is fully landed in the v2 governance database and committed to origin. Doug pulls locally; no further action required against this prompt.

The styling design pass artifact (`PRDs/product/crmbuilder-v2/styling-design-pass.md`) was committed alongside the close-out payload and apply prompt as a separate commit; that commit has already landed by the time this prompt runs (its commit precedes the payload commit which precedes this apply).

Next conversations to open in fresh Claude.ai chats:

- **Styling Conversation 2** — build planning. Takes `styling-design-pass.md` as input. Produces a styling release PRD, an implementation plan, and slice build prompts. Settles the version-bundling question.
- **v0.5 Conversation 1** (if not already running) — engagement management architecture + schema design per `v0.5-conversation-1-kickoff.md`.

These two conversations can run in any order; coupled only at v0.5's engagement panel per DEC-076's boundary discipline.
