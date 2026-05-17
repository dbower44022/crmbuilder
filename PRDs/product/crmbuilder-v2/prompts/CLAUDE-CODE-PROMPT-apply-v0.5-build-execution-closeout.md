# CLAUDE-CODE-PROMPT-apply-v0.5-build-execution-closeout

**Last Updated:** 05-17-26 15:00
**Operating mode:** detail
**Series:** apply-close-out
**Status:** Ready to execute
**Predecessor:** SES-029 apply (commit `0e23ce6` per the earlier apply); v0.5 build slices A-E plus launcher-wiring follow-up committed by Doug

## Purpose

Author session records for each Claude Code build-execution conversation that contributed to v0.5, and update the status entity from "v0.4 complete" to "v0.5 complete". Per DEC-014, every v2 conversation produces a session record; the build-execution conversations have not yet been recorded. Per slice E "After commit", the status update is queued.

Originally slice E specified the status update as operator-authored through the desktop versioned-replace dialog. This prompt batches it with the session records as a single Claude Code closeout pass for efficiency.

Conversations to record (one session record each):

1. **Slice A** — foundation infrastructure plus dogfood migration. Commit hash TBD (Claude Code identifies from git log).
2. **Slice B** — engagement schema, access layer, REST API.
3. **Slice C** — engagement management panel UI.
4. **Slice D** — engagement switching, top-strip, picker, single-gesture creation+activation.
5. **Slice E** — closeout (version bump, README, end-to-end integration smoke).
6. **Slice A follow-up** — launcher-wiring fix (`bootstrap_meta_db` at API startup, migration trigger at desktop startup, plus three regression tests). Includes the SQLite race fix discovered during execution.

That's six Claude Code sessions. SES numbering assigned dynamically at runtime (likely SES-030 through SES-035, adjusted for whatever current max identifier is). No decisions are produced by build-execution conversations (they implement decisions already settled in SES-029); each session records `is_about` references to DEC-098 (v0.5 slice plan) and DEC-104 (PRD approval) plus slice-specific decisions where applicable.

The status update is a single new row in the `status` table with phase="v0.5 complete" and version incremented per the existing v0.4 record's pattern.

**Operator review gate.** This prompt is guided: Claude Code generates the six session-record payloads plus the status update, presents summaries for review, and only applies after Doug confirms. Doug may edit individual payloads before approving.

---

## Project context

The v2 governance database is the source of truth (DEC-004); JSON snapshots under `db-export/` are renders (DEC-008). Records are inserted via the v2 access layer (HTTP POST to `http://127.0.0.1:8765`), which transactionally regenerates the JSON snapshots.

Each build-execution session is a Claude Code conversation that opened against one of the slice prompts at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.5-{A..E}-*.md` plus the follow-up prompt at `CLAUDE-CODE-PROMPT-v2-ui-v0.5-A-followup-launcher-wiring.md`. The slice prompts plus commit messages plus this prompt's section below are the source material for synthesizing `topics_covered`.

The `apply_close_out.py` script expects one session per payload file. Six session payloads will be created, one per session, each at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json`.

The status update is a separate operation not handled by `apply_close_out.py` — direct POST to `/status` per the v2 status-entity API surface.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root.

2. **Confirm `git status` is clean.** If uncommitted changes, stop and report.

3. **Confirm git identity:** `user.name "Doug Bower"`, `user.email "doug@dougbower.com"`.

4. **Pull latest:** `git pull --rebase origin main`.

5. **Confirm the v2 API is running:**
   ```bash
   curl -sf http://127.0.0.1:8765/sessions >/dev/null && echo "API up" || echo "API DOWN"
   ```
   If down, stop and ask Doug to start it.

6. **Capture pre-state.** Record the current max SES identifier, max DEC identifier, max PI identifier, and the current `/status` records:
   ```bash
   curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('Latest SES:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"
   curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('Latest DEC:', sorted([r['identifier'] for r in d])[-1] if d else 'none')"
   curl -s http://127.0.0.1:8765/status | python3 -m json.tool
   ```
   Expected after SES-029 apply: latest SES is SES-029 (or SES-028 if styling closeout never applied, in which case SES-029 might be the latest after a gap; or SES-030+ if other applies have intervened). Latest DEC: DEC-104. Status: most recent row should show phase "v0.4 complete" or similar. Note the exact values for use in Step 5.

---

## Step 1 — Identify the six build-execution commits

Read git log to identify the v0.5 build commits between SES-029 closeout and present:

```bash
git log --oneline 071d266..HEAD
```

(`071d266` was the SES-029 closeout commit per the apply prompt; substitute the actual hash if different.)

Expected output: six v0.5 build commits plus possibly intervening v0.6 work, the SES-029 apply commit, and operator commits. For each v0.5 build commit (slice A, B, C, D, E, plus follow-up), capture:
- commit hash
- commit date
- commit message subject

Confirm the six commits with Doug if there's any ambiguity. If Doug ran slices in unusual groupings (e.g., C+D in one Claude Code session), adjust the session-record count accordingly.

---

## Step 2 — Generate the six session record payloads

For each build-execution commit, construct a session record at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json` using the close-out-payload schema:

```json
{
  "label": "SES-NNN slice X build-execution closeout: 1 session, 0 decisions, 0 planning items, K references",
  "session": {
    "identifier": "SES-NNN",
    "title": "v0.5 slice X — <slice topic>",
    "session_date": "<MM-DD-YY of commit>",
    "status": "Complete",
    "conversation_reference": "<descriptive text per DEC-025>",
    "topics_covered": "<synthesized from slice prompt + commit message + any findings noted in Doug's status reports>",
    "artifacts_produced": "<list of files created or modified per commit>",
    "in_flight_at_end": "<what comes next; for slice A this is slice B; for follow-up this is the manual smoke pass>"
  },
  "decisions": [],
  "planning_items": [],
  "references": [
    {
      "source_type": "session",
      "source_id": "SES-NNN",
      "target_type": "decision",
      "target_id": "DEC-098",
      "relationship": "is_about"
    },
    {
      "source_type": "session",
      "source_id": "SES-NNN",
      "target_type": "decision",
      "target_id": "DEC-104",
      "relationship": "is_about"
    }
  ]
}
```

### Synthesis sources per session

For each session, read the following before authoring `topics_covered`:

- **The slice prompt** at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.5-{LETTER}-*.md` — defines the work the session executed.
- **The commit message** of the corresponding commit — captures what landed, what tests pass, any deviations.
- **The commit diff** (`git show <hash>`) for material findings — only consult if a finding is referenced in the commit message but the detail isn't in the message itself.

The `topics_covered` should describe what the conversation did, in narrative form, opening with the seed prompt reference (the slice prompt path) per DEC-025's convention. Length: 2-4 paragraphs per session.

### Slice-specific `is_about` references

Beyond DEC-098 (slice plan) and DEC-104 (PRD approval), add slice-specific references where the session directly implements a particular decision:

- **Slice A** — `is_about` DEC-078 (meta DB discovery model), DEC-079 (per-engagement DB convention), DEC-080 (active state persistence), DEC-082 (per-engagement identifier scope), DEC-083 (lazy migrations), DEC-084 (one-shot dogfood migration).
- **Slice B** — `is_about` DEC-086 (engagement entity schema and lifecycle); DEC-019 (API-only access principle applied to engagement endpoints).
- **Slice C** — `is_about` DEC-099 (UI affordance placement), DEC-101 (forbid-active-delete), DEC-102 (null export-dir default).
- **Slice D** — `is_about` DEC-099 (UI placement; picker is half of it), DEC-100 (single-gesture creation+activation), DEC-081 (one-process-per-engagement API+MCP at v0.5 with PI-017 deferred); PI reference: `is_about` PI-017.
- **Slice E** — `is_about` DEC-098 and DEC-104 are sufficient (closeout is generic).
- **Launcher-wiring follow-up** — `is_about` DEC-084 (dogfood migration spec — the fix wires the trigger that DEC-084 specified). Note the SQLite race fix in the `topics_covered` even though it didn't produce a DEC (it's defensive against a TOCTOU pattern surfaced by the concurrent-POST test).

### SES numbering

Assign SES identifiers sequentially starting from `max(existing) + 1`. Six sessions, six identifiers. If the max identifier from pre-flight Step 6 is SES-029, the new range is SES-030 through SES-035. If higher due to other intervening applies, adjust accordingly.

### Save the six payload files

Save each generated payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json` (lowercase `ses_` prefix matching the existing convention). Do NOT commit them yet.

---

## Step 3 — Generate the status update payload

Read the existing `/status` records to understand the schema:

```bash
curl -s http://127.0.0.1:8765/status | python3 -m json.tool > /tmp/status_existing.json
cat /tmp/status_existing.json
```

The status entity uses a versioned-replace pattern — each row is a snapshot at a point in time. Construct the new row mirroring the existing v0.4 record's shape:

```bash
# Inspect the most recent record's fields (status_phase, status_version, etc.)
curl -s http://127.0.0.1:8765/status | python3 -c "
import sys, json
records = json.load(sys.stdin)['data']
# Sort by created_at descending, get most recent
records.sort(key=lambda r: r.get('status_created_at', ''), reverse=True)
print(json.dumps(records[0], indent=2))
"
```

Use the most recent record as the template. Construct the new row with:
- `status_phase`: `"v0.5 complete"`
- `status_version`: increment per the existing record's pattern (likely a semver-like string; e.g., if v0.4 was `"0.4.0"` then v0.5 is `"0.5.0"`)
- Whatever other fields the schema requires (date, narrative summary, etc.)

Save the constructed POST body as `/tmp/status_update.json`. Do NOT POST yet.

---

## Step 4 — Present for review

Before applying anything, present a summary to Doug:

```
Six session record payloads generated:
  SES-030 → slice A (foundation + dogfood migration)         <hash> <date>
  SES-031 → slice B (engagement schema + API)                <hash> <date>
  SES-032 → slice C (engagement management panel)            <hash> <date>
  SES-033 → slice D (engagement switching + single-gesture)  <hash> <date>
  SES-034 → slice E (closeout + integration smoke)           <hash> <date>
  SES-035 → slice A follow-up (launcher wiring fix)          <hash> <date>

Status update generated:
  status_phase: "v0.5 complete"
  status_version: "0.5.0"  (or whatever increment fits)

Payload files: PRDs/product/crmbuilder-v2/close-out-payloads/ses_030.json
               ... through ses_035.json
Status update: /tmp/status_update.json

Review the files, then confirm to proceed. Type 'apply' to apply all six
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

Expected: 201 Created with the new status record in the envelope's `data` field. The previous "v0.4 complete" record is preserved (versioned-replace pattern); the new "v0.5 complete" record is the current state.

If the POST fails with 422 (validation error), the constructed body likely missed a required field — inspect the error envelope and adapt. If it fails with another status, stop and report.

---

## Step 7 — Verify post-state

```bash
# Six new sessions
for n in 30 31 32 33 34 35; do
  id="SES-0${n}"
  curl -sf http://127.0.0.1:8765/sessions/$id >/dev/null && echo "$id OK" || echo "$id MISSING"
done

# Status reflects v0.5 complete
curl -s http://127.0.0.1:8765/status | python3 -c "
import sys, json
records = json.load(sys.stdin)['data']
records.sort(key=lambda r: r.get('status_created_at', ''), reverse=True)
latest = records[0]
print('Latest status phase:', latest.get('status_phase'))
print('Latest status version:', latest.get('status_version'))
"

# References were created (~12-20 new is_about refs across the six sessions)
curl -s http://127.0.0.1:8765/references | python3 -c "
import sys, json
refs = json.load(sys.stdin)['data']
new_refs = [r for r in refs if r.get('source_id', '').startswith('SES-03')]
print('SES-030..035 is_about references:', len(new_refs))
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

Single commit covering all snapshot regenerations plus the six payload files plus the status update file:

```bash
git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_030.json \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_031.json \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_032.json \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_033.json \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_034.json \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_035.json \
        PRDs/product/crmbuilder-v2/db-export/

git commit -m "v2: apply v0.5 build-execution closeout — 6 session records + status update to v0.5 complete

Inserts six session records for the Claude Code build-execution
conversations that produced v0.5:
- SES-030 slice A (foundation + dogfood migration)
- SES-031 slice B (engagement schema + access + REST API)
- SES-032 slice C (engagement management panel UI)
- SES-033 slice D (switching + top-strip + picker + single-gesture)
- SES-034 slice E (closeout + integration smoke)
- SES-035 slice A follow-up (launcher wiring fix + SQLite race fix)

Each session records is_about references to DEC-098 (slice plan)
and DEC-104 (PRD approval) plus slice-specific decisions where the
session directly implements them.

Inserts new status entity row: phase v0.5 complete, version 0.5.0.
Previous v0.4 complete row preserved per versioned-replace pattern.

No new decisions. No new planning items. Snapshot regeneration
captures the resulting db-export state for git tracking. Adjust SES
identifier range in commit message if pre-flight showed different
starting number."
```

Adjust SES identifier range in the commit message if the actual range differs from SES-030..035.

---

## Step 9 — Push

```bash
git push origin main
```

Stop and report if push fails.

---

## Done

After Step 9 completes, v0.5 is governance-complete:
- PRD authoring captured (SES-029, DEC-098..104)
- Six build-execution conversations captured (SES-030..035)
- Status reflects v0.5 complete
- All snapshot files in `db-export/` reflect the post-apply state

The paper-test workstream (DEC-077) is now fully unblocked. The next Claude.ai conversation can be the paper-test kickoff against a freshly-created CBM engagement (single-gesture flow per slice D's UX).

## What NOT to do

- Do NOT generate session records for non-Claude-Code commits. The SES-029 apply, the reconcile-divergence script run, and any styling Conversation 2 commits are not v2 conversations per DEC-014 and do not warrant session records here.
- Do NOT add new decisions. The build-execution sessions implement decisions already settled in SES-026 and SES-029; no new decisions are produced.
- Do NOT bypass the review gate in Step 4. If Doug doesn't explicitly approve, stop without applying.
- Do NOT modify the status entity schema or the apply_close_out.py script — both are out of scope for this closeout.
- Do NOT push without all eight verifications in Step 7 reporting clean. If any verification fails, stop and report.
- Do NOT skip session records for slices that landed in the same calendar day or in rapid succession — each Claude Code conversation gets its own SES per DEC-014, regardless of how close in time they were.

---

*End of prompt.*
