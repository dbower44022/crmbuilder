# CLAUDE-CODE-PROMPT-apply-PI-023

**Last Updated:** 05-21-26 16:10
**Operating mode:** DETAIL
**Series:** apply-PI (standalone planning-item write, one-shot)
**Status:** Ready to execute
**Companion conversation:** SES-050 (governance-schema reference_book audit-and-finalize). Authored at SES-050's close on Doug's instruction to capture the workstream reconciliation prevention measure as a planning item.

---

## Purpose

Apply **PI-023** to the CRMBUILDER engagement's V2 governance database: a planning item committing the project to building a workstream-state reconciliation utility (`crmbuilder/tools/workstream_reconcile.py`) invoked from every kickoff prompt's pre-flight, to prevent the class of state-drift that produced SES-050's audit-and-finalize posture.

This is a one-shot apply prompt — a standalone planning-item write without an associated session record, decisions, or references. The originating context for the planning item is recorded in its own description text (citing SES-050) rather than via an `is_about` reference; if cross-linking proves useful later, the reference can be added then.

Per the SES-050 close-out apply prompt's "Done" section, the reconciliation utility was flagged for Doug's planning-item decision. Doug authorized capturing it after SES-050 landed.

Net effect on the V2 database after this prompt completes: one new planning item (PI-023) appended to the planning_items table; matching change_log entry; `planning_items.json` snapshot regenerated.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root.

2. **Confirm `git status` is clean.** Stop and report if there are uncommitted changes.

3. **Confirm git identity is set:**

   ```bash
   git config user.name "Doug Bower"
   git config user.email "doug@dougbower.com"
   ```

4. **Pull latest from origin:**

   ```bash
   git pull --rebase origin main
   ```

5. **Confirm the V2 API is running and routed at CRMBUILDER:**

   ```bash
   curl -sf http://127.0.0.1:8765/planning-items >/dev/null && echo "API up" || echo "API DOWN"
   curl -s http://127.0.0.1:8765/planning-items | python3 -c "
   import sys, json
   data = json.load(sys.stdin)['data']
   ids = sorted(p['identifier'] for p in data)
   print(f'Planning items: {len(data)}, latest {ids[-1] if ids else \"(none)\"}')
   "
   ```

   Expected: "API up" and "Planning items: 22, latest PI-022". If the count is less than 22 or the latest is not PI-022, the API is misrouted or earlier work has not been applied; stop and report.

6. **Confirm PI-023 does not already exist** (TOCTOU mitigation):

   ```bash
   curl -sf http://127.0.0.1:8765/planning-items/PI-023 >/dev/null 2>&1 && echo "PI-023 ALREADY EXISTS — STOP" || echo "PI-023 available"
   ```

7. **Capture pre-state:**

   ```bash
   curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys, json; print('Pre-state planning items:', len(json.load(sys.stdin)['data']))"
   ```

   Expected: `Pre-state planning items: 22`. Post-state should be exactly +1.

---

## Workflow

### Step 1 — POST PI-023

Inline `curl` POST with the planning item JSON. The identifier `PI-023` is supplied in the body per the direct-API client-computed-identifier convention (per `crmbuilder/CLAUDE.md`'s note: "Direct-API writes for prefixed-identifier entity types compute the identifier client-side, not server-side").

```bash
curl -sf -X POST http://127.0.0.1:8765/planning-items \
  -H 'Content-Type: application/json' \
  -d @- <<'JSON_EOF'
{
  "identifier": "PI-023",
  "title": "Workstream-state reconciliation utility at kickoff pre-flight to prevent git-vs-database state drift",
  "item_type": "pending_work",
  "status": "Open",
  "description": "Build and integrate `crmbuilder/tools/workstream_reconcile.py` to prevent state-drift between git-committed workstream deliverables and the V2 governance database at session-startup time.\n\n**Why this exists.** SES-050 (the reference_book entity schema-design conversation) opened against `PRDs/product/crmbuilder-v2/schema-design-kickoff-reference-book.md` as a fresh schema-design conversation, but the first pre-flight check found that the deliverable (`governance-schema-specs/reference_book.md`, 467 lines at v1.0) had already been drafted and committed at `c1d007e` on 05-21-26 14:55 by a prior Claude.ai sandbox session whose close-out was never run. The V2 database had no SES-050 or DEC-135..140 yet recorded; git was one commit ahead of origin/main with the spec on it, but the governance database was silently out of sync. Without the manual `git log` check during SES-050's pre-flight, the schema-design conversation would have either overwritten 467 lines of completed work or duplicated effort to produce a parallel spec. The root cause is a two-system-of-record gap: git holds committed deliverables; the V2 database holds governance state; the bridge — manual close-out apply — is a separate step that can be skipped silently.\n\n**Discharge conditions** (all must be met to mark PI-023 Resolved):\n\n1. `crmbuilder/tools/workstream_reconcile.py` exists, runs from any working directory, and accepts a workstream identifier as input. (Once the V2 workstream entity ships per the governance-schema workstream's build phase, the tool may accept a workstream record directly; until then, the workstream identifier is supplied as a string with the deliverable directory implied by convention.)\n\n2. The utility queries the V2 API for the workstream's conversations (via the sessions table for pre-workstream-entity workstreams, via the workstream entity once it ships) and collects each session's `artifacts_produced` field.\n\n3. The utility queries git for commits touching the workstream's deliverable directory since the workstream began (deliverable directory is configurable per workstream; for the governance workstream it is `PRDs/product/crmbuilder-v2/governance-schema-specs/` plus `PRDs/product/crmbuilder-v2/close-out-payloads/` plus `PRDs/product/crmbuilder-v2/prompts/` plus `PRDs/product/crmbuilder-v2/schema-design-kickoff-*.md`).\n\n4. The utility cross-references the two: any commit whose deliverable path is not referenced in any session record's `artifacts_produced` text is reported as a stale-state signal, with the commit hash, date, and path.\n\n5. A one-line addition to `crmbuilder/CLAUDE.md` under \"Session orientation protocol\" instructing V2-engaged sessions to run the reconciliation check at session start.\n\n6. A one-line addition to the kickoff-prompt template (and to each remaining per-entity schema-design kickoff prompt's Pre-flight section — work_ticket, close_out_payload, deposit_event — and to the kickoff-prompt-generator pattern for future workstreams) instructing pre-flight to invoke the utility against the workstream identifier before the first architectural question.\n\n7. The utility is run once against the current governance-entity-schema-design workstream and reports clean (after SES-050's apply lands; the c1d007e commit's deliverable is now referenced in SES-050's `artifacts_produced`, so no stale-state signal should surface).\n\n**Why this is preventative not a fix to current state.** SES-050 already landed and the SES-050 session record's `artifacts_produced` text includes `governance-schema-specs/reference_book.md` and the v1.1 patch. The current state is consistent; the utility prevents the recurrence of the class of issue, not a current data inconsistency.\n\n**Alternatives considered.** (a) Automatic close-out from the sandbox to Doug's local API — infeasible because the sandbox cannot reach `http://127.0.0.1:8765` on Doug's local machine. (b) V2 desktop app showing \"git ahead\" warnings — would require changing the V2 app and storing a `last_processed_commit_hash` somewhere; heavier than needed and only surfaces the gap when Doug happens to open the app. (c) Co-commit enforcement (a hook that rejects spec commits without paired apply scripts) — fragile and easy to circumvent, and does not catch the \"applied locally in sandbox but never pushed\" variant. The reconciliation utility addresses every variant — committed-not-pushed, pushed-not-applied, applied-locally-not-mirrored — because it always derives state from origin and the V2 API together.\n\n**Priority.** Routine — the utility is preventative; no current data drift is blocking work. Discharge timing is build-planning conversation's call within the governance-entity-schema-design workstream, or earlier if Doug authorizes a tooling slice between schema-design conversations."
}
JSON_EOF
```

Expected response: HTTP 201 with JSON body `{"data": {"identifier": "PI-023", ...}, "meta": ..., "errors": null}`. Stop and report if anything else.

### Step 2 — Verify PI-023 created

```bash
curl -sf http://127.0.0.1:8765/planning-items/PI-023 | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
print(f'PI-023 OK')
print(f'  title: {data[\"title\"]}')
print(f'  status: {data[\"status\"]}')
print(f'  item_type: {data[\"item_type\"]}')
print(f'  description length: {len(data[\"description\"])} chars')
"
```

Expected: `PI-023 OK` plus four metadata lines confirming the planning item landed with the expected values. Stop and report any other output.

### Step 3 — Verify post-state count

```bash
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys, json; print('Post-state planning items:', len(json.load(sys.stdin)['data']))"
```

Expected: `Post-state planning items: 23` (pre-state was 22; delta +1). Stop and report any other delta.

### Step 4 — Verify snapshot regeneration

```bash
git status PRDs/product/crmbuilder-v2/db-export/
```

Expected modifications:

- `planning_items.json` — PI-023 added.
- `change_log.json` — corresponding append entry for the planning_item insert.

Other snapshot files (`sessions.json`, `decisions.json`, `references.json`) should NOT be modified — this is a standalone planning-item write with no session, decision, or reference side-effects.

### Step 5 — Commit

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git status   # confirm only db-export changes are staged
git commit -m "v2: apply PI-023 — workstream-state reconciliation utility at kickoff pre-flight

Lands one standalone planning item to the CRMBUILDER engagement
governance database:

- PI-023 (Workstream-state reconciliation utility at kickoff pre-flight
  to prevent git-vs-database state drift)

Authored at the close of SES-050 on Doug's instruction following the
audit-and-finalize posture that surfaced the class of state-drift the
utility would prevent. Description text in PI-023 cites SES-050 as the
originating context; no is_about reference from SES-050 to PI-023 added
at this time (can be added later if cross-linking proves useful).

Discharge conditions in PI-023's description:

- crmbuilder/tools/workstream_reconcile.py exists and runs.
- Utility queries V2 API for workstream conversations and their
  artifacts_produced fields.
- Utility queries git for commits touching the workstream's deliverable
  directory since the workstream began.
- Utility cross-references the two and reports stale-state signals.
- One-line addition to crmbuilder/CLAUDE.md under Session orientation
  protocol.
- One-line addition to the kickoff-prompt template plus each remaining
  per-entity schema-design kickoff prompt's Pre-flight section.
- Utility run once against the current governance workstream reports
  clean (post-SES-050).

Priority: routine. Discharge timing is the build-planning conversation's
call within the governance-entity-schema-design workstream, or earlier
if Doug authorizes a tooling slice between schema-design conversations.

Snapshot regeneration only — no source code modified by this commit."
```

### Step 6 — Push

```bash
git push origin main
```

Stop and report if push fails.

---

## Done

After Step 6 completes, PI-023 has fully landed:

- One record (PI-023) lives in the CRMBUILDER engagement governance database.
- `planning_items.json` and `change_log.json` snapshots regenerated and committed.
- The discharge conditions are documented in PI-023's description and committable artifacts (the utility script + CLAUDE.md edit + kickoff-prompt template edit) await authoring at the build-planning conversation or earlier per Doug's tooling-slice call.

**Next step** (unchanged from SES-050's "Done" section): open a fresh Claude.ai conversation against `PRDs/product/crmbuilder-v2/schema-design-kickoff-work-ticket.md` to design the work_ticket entity schema (fourth of six per-entity conversations).

The PI-023 planning item is now visible in the V2 desktop Planning Items panel and queryable via the API at `GET /planning-items/PI-023`. It does not block the work_ticket conversation; the work_ticket conversation may reference PI-023 in passing if relevant but is not required to discharge it.

---

## Error handling

- **`curl` POST returns 422 with a validation error.** The API rejected the JSON body. Most likely causes: an unexpected character in the description text breaking the JSON quoting, a missing required field, or an enum value that doesn't match. Inspect the response body, fix the JSON, and re-run Step 1.

- **`curl` POST returns 409.** PI-023 already exists. The pre-flight TOCTOU check should have caught this; a 409 here indicates either a race or an inconsistent pre-flight state. Stop and report; do not commit.

- **`curl` POST returns 500.** Server-side error. Stop and check the API server logs. Do not commit.

- **Snapshot not regenerated.** The export hook may have failed silently. Stop, do not commit. Check the API server logs.

- **`git status` not clean at start.** Stop and report. Do not stash. Doug decides how to handle the uncommitted changes before re-running.

---

## What this prompt does NOT do

- Does not author the utility (`crmbuilder/tools/workstream_reconcile.py`) — that's the discharge action, not the planning-item creation. The utility lands at the build-planning conversation or an earlier tooling-slice conversation per Doug's call.
- Does not modify `crmbuilder/CLAUDE.md` or any kickoff prompt — those are also discharge actions, gated on the utility existing first.
- Does not modify the SES-050 record retroactively — SES-050's `artifacts_produced` and reference list are immutable per DEC-013. No new `is_about` reference from SES-050 to PI-023 is added; the originating context is captured in PI-023's description text instead.
- Does not author a session record. This is a standalone planning-item write per the SES-050 close-out's "Open-and-flagged for Doug's planning-item decision (NOT in this payload)" note.

---

*End of prompt.*
