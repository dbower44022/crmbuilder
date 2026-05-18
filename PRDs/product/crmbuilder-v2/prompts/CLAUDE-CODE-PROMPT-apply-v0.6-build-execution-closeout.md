# CLAUDE-CODE-PROMPT-apply-v0.6-build-execution-closeout

**Last Updated:** 05-18-26 10:00
**Operating mode:** detail
**Series:** apply-close-out
**Status:** Ready to execute
**Predecessor:** v0.5 build-execution closeout (commit `8932b03` per Doug's apply) — SES-029, SES-031..035 plus status "v0.5 complete" (version 14, is_current) landed
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.6.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.6-implementation-plan.md` §9 (Closeout Discipline)

## Purpose

Author session records for each Claude Code build-execution conversation that contributed to v0.6, and update the status entity from "v0.5 complete" to "v0.6 complete". Per DEC-014, every v2 conversation produces a session record; the v0.6 build-execution conversations have not yet been recorded. Per v0.6 implementation plan §9, the status update is queued as operator follow-up; this prompt batches it with the session records as a single Claude Code closeout pass.

Conversations to record (one session record each):

1. **v0.6 slice A** — foundation infrastructure + About dialog. Token system, font loading, icon loader, elevation, modal backdrop, About dialog re-skin.
2. **v0.6 slice B** — sidebar + master-pane delegate. Sentence-cased group headers, SidebarItemDelegate selected-state, MasterPaneDelegate + MasterPaneTreeDelegate covering all 13 panels through ListDetailPanel inheritance.
3. **v0.6 slice C** — panel retrofits. ReferencesSection sub-section rewrite, WrapAllRows, required_label helper applied across 13 panels + crud_dialog base, status hint captions, CollapsibleSection for Notes.
4. **v0.6 slice D** — dialogs and form controls. Button category helpers (primary/destructive/text-link/icon), 5 button-category QSS blocks, edit-dialog context strip, delete-confirm retoken, references_section.Add reference as text_link_button, 13 panels' New + Delete CTAs migrated.
5. **v0.6 slice E** — status, error, warning, crash banner. WarningCallout widget, Processes warning retoken'd, error dialog Lucide circle-x + heading-3, crash banner retoken'd onto color.danger.default.
6. **v0.6 slice F** — closeout. `__version__` bumped to 0.6.0, README v0.6 release note, WCAG contrast check test (9 cases) — caught a design-pass transcription error in `color.neutral.500` (#7A8694 → #6A7480) and validated the prompt's recommended `color.warning.default` adjustment (#B0731A → #9D6517). Design pass §4.4 updated with corrected ratios and traceability notes.
7. **v0.6 slice A follow-up** — force-light-palette fix. Surgical defect fix discovered after slice B: `build_application()` didn't force a Qt style or palette, so on Linux Mint with a GTK/Cinnamon theme, QLabel widgets without explicit QSS rules rendered against GTK-derived dark backgrounds (the dark-on-dark readability failure). Fix: `setStyle("Fusion")` + explicit palette construction from `TOKENS["light"]`. Plus QStyleSheetStyle proxy finding documented in commit message body.

That's seven Claude Code sessions. SES numbering assigned dynamically at runtime (likely SES-036 through SES-042, adjusted for whatever current max identifier is at apply time). No decisions are produced by these build-execution conversations — they implement decisions already settled in SES-027 (styling design pass) and SES-030 (styling Conv 2 / v0.6 PRD authoring). Each session records `is_about` references to DEC-094 (design pass approval), DEC-096 (six-slice structure), and slice-specific decisions where applicable; plus an `is_about` reference to PI-001 (the styling pass parent planning item).

The status update is a single new row in the `status` table with `status_phase="v0.6 complete"` and version incremented from the v0.5-complete record's version 14.

**Operator review gate.** This prompt is guided: Claude Code generates the seven session-record payloads plus the status update, presents summaries for review, and only applies after Doug confirms. Doug may edit individual payloads before approving.

---

## Project context

The v2 governance database is the source of truth (DEC-004); JSON snapshots under `db-export/` are renders (DEC-008). Records are inserted via the v2 access layer (HTTP POST to `http://127.0.0.1:8765`), which transactionally regenerates the JSON snapshots.

Each build-execution session is a Claude Code conversation that opened against one of the slice prompts at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.6-{A..F}-*.md` plus the follow-up prompt at `CLAUDE-CODE-PROMPT-v2-ui-v0.6-A-followup-force-light-palette.md`. The slice prompts plus commit messages plus Doug's per-slice summary reports are the source material for synthesizing `topics_covered`.

The `apply_close_out.py` script expects one session per payload file. Seven session payloads will be created, one per session, each at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json`.

The status update is a separate operation not handled by `apply_close_out.py` — direct POST to `/status`. The v0.5-complete status record (version 14, is_current=true) is the template for shape; the new v0.6-complete record uses the same fields with incremented version, new phase, and the versioned-replace pattern (the previous is_current=true flag gets cleared automatically per the API's behavior — Doug's v0.5 status update confirmed this works).

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root.

2. **Confirm `git status` is clean.** If uncommitted changes, stop and report.

3. **Confirm git identity:** `user.name "Doug Bower"`, `user.email "doug@dougbower.com"`.

4. **Pull latest:** `git pull --rebase origin main`.

5. **Confirm v0.6 slice F has pushed.** `git log --oneline origin/main..HEAD` should show no v0.6 slice commits ahead of origin (they should all be on origin/main by the time this closeout runs). If slice E or F are still local-only, push them first.

6. **Confirm the v2 API is running:**
   ```bash
   curl -sf http://127.0.0.1:8765/sessions >/dev/null && echo "API up" || echo "API DOWN"
   ```
   If down, stop and ask Doug to start it.

7. **Capture pre-state:**
   ```bash
   curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('Latest SES:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"
   curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('Latest DEC:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"
   curl -s http://127.0.0.1:8765/status | python3 -m json.tool | head -30
   ```
   Expected: latest SES is SES-035 (or higher if other applies have intervened). Latest DEC: DEC-107. Status: most recent is_current row should show `status_phase: "v0.5 complete"`, `status_version: 14`. Note the exact values for use in Step 5.

---

## Step 1 — Identify the seven v0.6 build-execution commits

Read git log to identify the v0.6 build commits between the v0.5 build-execution closeout (commit `8932b03` per Doug's apply) and present:

```bash
git log --oneline 8932b03..HEAD
```

Expected output: seven v0.6 build commits plus intervening apply/operator/screenshot commits. For each substantive v0.6 build commit, capture:
- commit hash
- commit date
- commit message subject

Expected hashes (per Doug's per-slice summary reports):
- v0.6 slice A — `7e5c010` "v2: ui v0.6 slice A — foundation infrastructure + About dialog"
- v0.6 slice B — `86d9072` "v2: ui v0.6 slice B — sidebar + master-pane delegate"
- v0.6 slice A follow-up — palette fix commit (hash TBD; landed after slice B but ordering depends on push timing)
- v0.6 slice C — `0114324` "v2: ui v0.6 slice C — panel retrofits"
- v0.6 slice D — `a54adc5` "v2: ui v0.6 slice D — dialogs and form controls"
- v0.6 slice E — `296aa2a` "v2: ui v0.6 slice E — status/error/warning + crash banner"
- v0.6 slice F — `583f511` "v2: ui v0.6 slice F — closeout (release v0.6.0)"

Confirm the seven commits with Doug if there's any ambiguity. The chronological ordering between slice B and the palette-fix follow-up may surface depending on which was pushed first.

---

## Step 2 — Generate the seven session record payloads

For each build-execution commit, construct a session record at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json` using the close-out-payload schema:

```json
{
  "label": "SES-NNN slice X build-execution closeout: 1 session, 0 decisions, 0 planning items, K references",
  "session": {
    "identifier": "SES-NNN",
    "title": "v0.6 slice X — <slice topic>",
    "session_date": "<MM-DD-YY of commit>",
    "status": "Complete",
    "conversation_reference": "<descriptive text per DEC-025>",
    "topics_covered": "<synthesized from slice prompt + commit message + Doug's summary report>",
    "artifacts_produced": "<list of files created or modified per commit>",
    "in_flight_at_end": "<what comes next; for slice A this is slice B; for slice F this is the v0.6 build-execution closeout (this conversation); for palette fix it's the resumption of slice C work>"
  },
  "decisions": [],
  "planning_items": [],
  "references": [
    {
      "source_type": "session",
      "source_id": "SES-NNN",
      "target_type": "decision",
      "target_id": "DEC-094",
      "relationship": "is_about"
    },
    {
      "source_type": "session",
      "source_id": "SES-NNN",
      "target_type": "decision",
      "target_id": "DEC-096",
      "relationship": "is_about"
    },
    {
      "source_type": "session",
      "source_id": "SES-NNN",
      "target_type": "planning_item",
      "target_id": "PI-001",
      "relationship": "is_about"
    }
  ]
}
```

### Synthesis sources per session

For each session, read the following before authoring `topics_covered`:

- **The slice prompt** at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.6-{LETTER}-*.md` — defines the work the session executed.
- **The commit message** of the corresponding commit — captures what landed, what tests pass, any deviations.
- **The commit diff** (`git show <hash>`) for material findings — only consult if a finding is referenced in the commit message body but the detail isn't in the message itself.

The `topics_covered` should describe what the conversation did, in narrative form, opening with the seed prompt reference (the slice prompt path) per DEC-025's convention. Length: 2-4 paragraphs per session. For sessions with notable findings (slice A's Inter Variable family-name substitution; slice B's Engagements/Engagements label collision and VersionedPanel inheritance positive surprise; slice F's design-pass transcription error; the palette-fix follow-up's OS-theme-bleed-through diagnosis), include the finding in the narrative.

### Slice-specific `is_about` references

Beyond DEC-094 (design pass approval), DEC-096 (six-slice structure), and PI-001 (styling pass parent), add slice-specific references where the session directly implements a particular decision:

- **Slice A** — `is_about` DEC-087 (density), DEC-088 (color palette), DEC-089 (theme keying), DEC-090 (typography), DEC-091 (modal elevation), DEC-092 (icon library), DEC-095 (separate-release sequencing — slice A is the first slice of v0.6 separate from v0.5).
- **Slice B** — `is_about` DEC-093 (selected-state vocabulary — left accent bar + tinted background, applied identically across sidebar entries and master-pane rows).
- **Slice C** — `is_about` DEC-087 (density applied to forms), DEC-088 (color tokens applied to form chrome), DEC-090 (typography applied to form labels). Spans the design pass §2.4 form-control treatment broadly.
- **Slice D** — `is_about` DEC-091 (modal elevation applied to dialog backdrop + shadow), DEC-097 (per-slice screenshot pattern — slice D's button-state screenshots are the most numerous individual surfaces).
- **Slice E** — `is_about` DEC-088 (status colors — danger/warning/success applied to error/warning/crash banner surfaces).
- **Slice F** — `is_about` DEC-095 (separate-release sequencing — slice F bumps `__version__` to 0.6.0 per the separate-release decision), DEC-097 (closeout WCAG check acceptance pattern — slice F's contrast test discharges the gate).
- **Slice A follow-up (palette fix)** — `is_about` DEC-089 (theme keying — fix preserves light-theme-only intent against OS theme bleed-through).

### SES numbering

Assign SES identifiers sequentially starting from `max(existing) + 1`. Seven sessions, seven identifiers. If the max identifier from pre-flight Step 7 is SES-035, the new range is SES-036 through SES-042. If higher due to other intervening applies, adjust accordingly.

The chronological order for SES assignment is the commit-date order per git log, NOT necessarily the slice-letter order. Slice A follow-up landed AFTER slice B per Doug's narrative, so its SES number is between slice B's and slice C's:

| SES (likely) | Slice | Commit date (approx) |
|---|---|---|
| SES-036 | v0.6 slice A | first |
| SES-037 | v0.6 slice B | second |
| SES-038 | v0.6 slice A follow-up | third (after B, before C) |
| SES-039 | v0.6 slice C | fourth |
| SES-040 | v0.6 slice D | fifth |
| SES-041 | v0.6 slice E | sixth |
| SES-042 | v0.6 slice F | seventh |

Adjust if the actual commit ordering differs.

### Save the seven payload files

Save each generated payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json` (lowercase `ses_` prefix matching the existing convention). Do NOT commit them yet.

---

## Step 3 — Generate the status update payload

Read the existing `/status` records to understand the schema:

```bash
curl -s http://127.0.0.1:8765/status | python3 -m json.tool > /tmp/status_existing.json
```

The status entity uses a versioned-replace pattern. The v0.5-complete record (version 14, is_current=true) is the most recent. Construct the new row mirroring its shape:

```bash
curl -s http://127.0.0.1:8765/status | python3 -c "
import sys, json
records = json.load(sys.stdin)['data']
# Find the v0.5-complete row
v5 = [r for r in records if r.get('status_phase') == 'v0.5 complete' and r.get('is_current')][0]
print(json.dumps(v5, indent=2))
"
```

Use the v0.5-complete record as the template. Construct the new POST body with:
- `status_phase`: `"v0.6 complete"`
- `status_version`: 15 (increment from 14)
- `is_current`: true (the API's versioned-replace logic will clear the previous is_current=true row)
- Narrative summary field: synthesize from v0.6's release-note content in `crmbuilder-v2/README.md` (slice F added the v0.6 section)
- Any other required fields per the v0.5-complete record's shape

Save the constructed POST body as `/tmp/status_update.json`. Do NOT POST yet.

---

## Step 4 — Present for review

Before applying anything, present a summary to Doug:

```
Seven session record payloads generated:
  SES-036 → v0.6 slice A (foundation + About dialog)              <hash> <date>
  SES-037 → v0.6 slice B (sidebar + master-pane delegate)         <hash> <date>
  SES-038 → v0.6 slice A follow-up (palette fix)                  <hash> <date>
  SES-039 → v0.6 slice C (panel retrofits)                        <hash> <date>
  SES-040 → v0.6 slice D (dialogs and form controls)              <hash> <date>
  SES-041 → v0.6 slice E (status/error/warning/crash banner)      <hash> <date>
  SES-042 → v0.6 slice F (closeout + WCAG contrast check)         <hash> <date>

Status update generated:
  status_phase: "v0.6 complete"
  status_version: 15  (incremented from v0.5-complete version 14)
  is_current: true

Payload files: PRDs/product/crmbuilder-v2/close-out-payloads/ses_036.json
               ... through ses_042.json
Status update: /tmp/status_update.json

Review the files, then confirm to proceed. Type 'apply' to apply all seven
session records plus the status update. Type 'review SES-NNN' to print a
specific payload's topics_covered for inspection. Type 'abort' to stop
without applying.
```

Wait for Doug's confirmation. Honor `review SES-NNN` requests by printing the relevant `topics_covered` field. Only proceed past this gate on explicit `apply`.

---

## Step 5 — Apply the session records

For each session payload, in order from lowest SES to highest:

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json
cd ..  # return to repo root after each run
```

Expected per file: 1 session + 0 decisions + 0 planning items + K references created (or skipped if already present). Script exits 0 on success.

If any apply fails non-zero, stop and report. Do NOT proceed to subsequent sessions or the status update until the failure is understood.

---

## Step 6 — Apply the status update

```bash
curl -X POST http://127.0.0.1:8765/status \
  -H "Content-Type: application/json" \
  -d @/tmp/status_update.json \
  --fail-with-body
```

Expected: 201 Created with the new status record in the envelope's `data` field. The previous "v0.5 complete" record's `is_current` flag is automatically cleared per the API's versioned-replace pattern (v0.5 closeout precedent confirmed this behavior).

If the POST fails with 422 (validation error), the constructed body likely missed a required field — inspect the error envelope and adapt. If it fails with another status, stop and report.

---

## Step 7 — Verify post-state

```bash
# Seven new sessions
for n in 36 37 38 39 40 41 42; do
  id="SES-0${n}"
  curl -sf http://127.0.0.1:8765/sessions/$id >/dev/null && echo "$id OK" || echo "$id MISSING"
done

# Status reflects v0.6 complete
curl -s http://127.0.0.1:8765/status | python3 -c "
import sys, json
records = json.load(sys.stdin)['data']
current = [r for r in records if r.get('is_current')][0]
print('Current status phase:', current.get('status_phase'))
print('Current status version:', current.get('status_version'))
print('v0.5 complete is_current cleared:', not any(r.get('status_phase') == 'v0.5 complete' and r.get('is_current') for r in records))
"

# References were created (3-9 new is_about refs per session × 7 sessions = ~21-63 new)
curl -s http://127.0.0.1:8765/references | python3 -c "
import sys, json
refs = json.load(sys.stdin)['data']
new_refs = [r for r in refs if r.get('source_id', '').startswith('SES-03') or r.get('source_id', '').startswith('SES-04')]
v6_new_refs = [r for r in new_refs if r.get('source_id') in ['SES-036','SES-037','SES-038','SES-039','SES-040','SES-041','SES-042']]
print(f'SES-036..042 is_about references: {len(v6_new_refs)}')
"
```

Adjust the SES identifier range if pre-flight showed a different starting number.

Confirm the JSON snapshots regenerated:
```bash
git status PRDs/product/crmbuilder-v2/db-export/
```
Expected modifications: `sessions.json`, `references.json`, `status.json`, `change_log.json`. (`decisions.json` and `planning_items.json` unchanged.)

---

## Step 8 — Commit

Single commit covering all snapshot regenerations plus the seven payload files:

```bash
git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_036.json \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_037.json \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_038.json \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_039.json \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_040.json \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_041.json \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_042.json \
        PRDs/product/crmbuilder-v2/db-export/

git commit -m "v2: apply v0.6 build-execution closeout — 7 session records + status update to v0.6 complete

Inserts seven session records for the Claude Code build-execution
conversations that produced v0.6:
- SES-036 slice A (foundation + About dialog)
- SES-037 slice B (sidebar + master-pane delegate)
- SES-038 slice A follow-up (force-light-palette fix; Linux Mint
  GTK theme bleed-through diagnosis + Fusion style + explicit light
  palette from TOKENS['light'])
- SES-039 slice C (panel retrofits + ReferencesSection sub-section
  rewrite)
- SES-040 slice D (dialogs + form controls + button category helpers)
- SES-041 slice E (status/error/warning + crash banner retoken'd
  off legacy hex values)
- SES-042 slice F (closeout: __version__ 0.6.0, README v0.6 release
  note, WCAG contrast check test, design pass §4.4 transcription-error
  correction for color.neutral.500)

Each session records is_about references to DEC-094 (design pass
approval), DEC-096 (six-slice structure), PI-001 (styling pass
parent), plus slice-specific decisions where the session directly
implements them.

Inserts new status entity row: status_phase 'v0.6 complete',
status_version 15, is_current true. Previous 'v0.5 complete'
row's is_current flag cleared per versioned-replace pattern.

No new decisions. No new planning items. Snapshot regeneration
captures the resulting db-export state for git tracking. Adjust
SES identifier range in commit message if pre-flight showed
different starting number."
```

Adjust SES identifier range in the commit message if the actual range differs from SES-036..042.

---

## Step 9 — Push

```bash
git push origin main
```

Stop and report if push fails.

---

## Done

After Step 9 completes, v0.6 is governance-complete:
- v0.6 PRD authoring captured (SES-030, DEC-095..097 — already applied)
- Seven build-execution conversations captured (SES-036..042)
- Status reflects v0.6 complete
- All snapshot files in `db-export/` reflect the post-apply state

After this closeout pass plus the deferred screenshot captures land, v0.6 is shippable and the paper-test workstream (DEC-077) is the next conversation. The paper-test runs against a freshly-created CBM engagement (single-gesture flow from v0.5 slice D).

## What NOT to do

- Do NOT generate session records for non-Claude-Code commits. The v0.5 build-execution closeout apply (commit `8932b03`), the screenshot operator commits, the v0.6 slice apply/closeout/operator commits — none of these are v2 conversations per DEC-014 and do not warrant session records here.
- Do NOT add new decisions. The v0.6 build-execution sessions implement decisions already settled in SES-027 (design pass) and SES-030 (v0.6 PRD authoring); no new decisions are produced.
- Do NOT bypass the review gate in Step 4. If Doug doesn't explicitly approve, stop without applying.
- Do NOT modify the status entity schema or the apply_close_out.py script — both are out of scope for this closeout.
- Do NOT push without all verifications in Step 7 reporting clean. If any verification fails, stop and report.
- Do NOT skip session records for slices that landed in rapid succession — each Claude Code conversation gets its own SES per DEC-014, regardless of how close in time they were.
- Do NOT skip the palette-fix follow-up session (SES-038). It's a substantive Claude Code conversation that diagnosed a real defect, shipped a surgical fix, and added a regression test. It deserves its own session record on the same footing as the slice-letter sessions.

---

*End of prompt.*
