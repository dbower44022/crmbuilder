# CLAUDE-CODE-PROMPT-apply-close-out-ses-048

**Last Updated:** 05-20-26 23:55
**Operating mode:** DETAIL
**Series:** apply-close-out
**Status:** Ready to execute
**Companion payload:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_048.json`

---

## Purpose

Apply the SES-048 close-out payload to the CRMBUILDER engagement's database. Lands the SES-048 workstream-entity schema-design conversation's records (1 session, 6 decisions, 0 planning items, 7 references) so the next per-entity schema-design conversation can open against `PRDs/product/crmbuilder-v2/schema-design-kickoff-conversation.md` with the workstream specification's cross-spec precedents (references-edge for parent-child relationships, per-status lifecycle timestamps for workflow-shaped lifecycles, terminal-states-are-terminal discipline) recorded as decisions in the database.

Net effect on the v2 database after this prompt completes:

- **Session.** SES-048 created with the workstream-entity schema-design conversation's content (one substantive artifact: `governance-schema-specs/workstream.md`, 393 lines, committed at `b981c1f` during the conversation).
- **Decisions.** Six decisions created — DEC-123 (workstream identifier prefix), DEC-124 (workstream-to-conversation via references-table edge per DEC-120), DEC-125 (five-status lifecycle with truly terminal terminals and supersession-requires-edge rule), DEC-126 (field inventory with per-status lifecycle timestamps), DEC-127 (flat catalog, no nesting in this release), DEC-128 (master plan linkage, API and UI defaults, soft-delete posture, sixteen acceptance criteria).
- **Planning items.** None. PI-022 (retroactive backfill, authored by SES-046) covers this conversation's records implicitly; no new planning item.
- **References.** Seven added — six `decided_in` (DEC-123..128 → SES-048) plus one `is_about` (SES-048 → PI-022).

All 14 records (1 session + 6 decisions + 7 references) should report `OK` from the apply script. None should `SKIP` — this is a fresh apply, not a reconciliation.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root (typically `~/Dropbox/Projects/crmbuilder`). Stop and report if unexpected.

2. **Confirm `git status` is clean.** Stop and report if there are uncommitted changes. The conversation's deliverable (`governance-schema-specs/workstream.md`) was already committed at `b981c1f` during the conversation; this prompt's commit is snapshot-regeneration only and starts from a clean state.

3. **Confirm git identity is set:**

   ```bash
   git config user.name "Doug Bower"
   git config user.email "doug@dougbower.com"
   ```

4. **Pull latest from origin:**

   ```bash
   git pull --rebase origin main
   ```

   Stop and report if there are conflicts. HEAD should be at or past `b981c1f` (the workstream.md commit).

5. **Confirm payload file exists:**

   ```bash
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_048.json
   ```

   Stop if missing.

6. **Confirm the v2 API is running and routed at CRMBUILDER.** Two checks:

   **6a — API up:**

   ```bash
   curl -sf http://127.0.0.1:8765/sessions >/dev/null && echo "API up" || echo "API DOWN"
   ```

   If the API is down, start it:

   ```bash
   fuser -k 8765/tcp 2>/dev/null
   cd crmbuilder-v2
   uv run crmbuilder-v2-api --engagement CRMBUILDER &
   cd ..
   sleep 2
   curl -sf http://127.0.0.1:8765/sessions >/dev/null && echo "API now up" || echo "STILL DOWN"
   ```

   Stop and report if the API still does not come up.

   **6b — API routed at CRMBUILDER (not the empty v2.db or another engagement):**

   ```bash
   curl -s http://127.0.0.1:8765/sessions | python3 -c "
   import sys, json
   data = json.load(sys.stdin)['data']
   if not data:
       print('STOP — API is routed at an empty database. Restart per step 6a.')
   else:
       count = len(data)
       latest = sorted(r['identifier'] for r in data)[-1]
       print(f'API routed correctly: {count} sessions, latest {latest}')
   "
   ```

   Expected: at least 47 sessions returned, latest identifier SES-047 (the predecessor workstream-establishing conversation, which SES-048 follows). If the count is less than 47 or the latest is not SES-047, the API is misrouted or SES-047 has not yet been applied; stop and re-run step 6a or apply SES-047 first.

7. **Verify SES-048, DEC-123..128 are uncontested and prerequisites are in place** (TOCTOU mitigation per the SES-036 reconciliation precedent):

   ```bash
   # SES-048 must not yet exist
   curl -sf http://127.0.0.1:8765/sessions/SES-048 >/dev/null 2>&1 && echo "SES-048 ALREADY EXISTS — STOP" || echo "SES-048 available"

   # Each new decision identifier must not yet exist
   for id in DEC-123 DEC-124 DEC-125 DEC-126 DEC-127 DEC-128; do
     curl -sf http://127.0.0.1:8765/decisions/$id >/dev/null 2>&1 && echo "$id ALREADY EXISTS — STOP" || echo "$id available"
   done

   # PI-022 must exist (foreign-key target for the SES-048 is_about reference)
   curl -sf http://127.0.0.1:8765/planning-items/PI-022 >/dev/null 2>&1 && echo "PI-022 exists — reference target valid" || echo "PI-022 MISSING — STOP and apply SES-046 first"
   ```

   Expected: "SES-048 available", six lines of "DEC-12X available", and "PI-022 exists — reference target valid". Any other output: stop and report.

8. **Capture pre-state for verification.**

   ```bash
   curl -s http://127.0.0.1:8765/sessions       | python3 -c "import sys, json; print('Pre-state sessions:',       len(json.load(sys.stdin)['data']))"
   curl -s http://127.0.0.1:8765/decisions      | python3 -c "import sys, json; print('Pre-state decisions:',      len(json.load(sys.stdin)['data']))"
   curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys, json; print('Pre-state planning items:', len(json.load(sys.stdin)['data']))"
   curl -s http://127.0.0.1:8765/references     | python3 -c "import sys, json; print('Pre-state references:',     len(json.load(sys.stdin)['data']))"
   ```

   Note the four values. Post-state should be exactly +1 sessions / +6 decisions / +0 planning items / +7 references.

---

## Workflow

### Step 1 — Apply SES-048 payload

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_048.json
cd ..
```

Expected output:

- SES-048 reports `OK` (created).
- DEC-123 through DEC-128 each report `OK` (created). Six lines.
- Six `decided_in` references (DEC-123..128 → SES-048) each report `OK` (created). Six lines.
- One `is_about` reference (SES-048 → PI-022) reports `OK` (created).
- Script exits 0.

Total: 14 `OK` lines. Zero `SKIP` lines. Zero non-`OK` lines.

Stop and report if any record returns `SKIP` or a status other than `OK`, or if the script exits non-zero.

### Step 2 — Verify created records

```bash
echo "--- Session ---"
curl -sf http://127.0.0.1:8765/sessions/SES-048 >/dev/null && echo "SES-048 OK" || echo "SES-048 MISSING"

echo "--- Decisions ---"
for id in DEC-123 DEC-124 DEC-125 DEC-126 DEC-127 DEC-128; do
  curl -sf http://127.0.0.1:8765/decisions/$id >/dev/null && echo "$id OK" || echo "$id MISSING"
done

echo "--- References ---"
curl -s http://127.0.0.1:8765/references | python3 -c "
import sys, json
refs = json.load(sys.stdin)['data']
expected = [
    ('DEC-123', 'SES-048', 'decided_in'),
    ('DEC-124', 'SES-048', 'decided_in'),
    ('DEC-125', 'SES-048', 'decided_in'),
    ('DEC-126', 'SES-048', 'decided_in'),
    ('DEC-127', 'SES-048', 'decided_in'),
    ('DEC-128', 'SES-048', 'decided_in'),
    ('SES-048', 'PI-022',  'is_about'),
]
for src, tgt, kind in expected:
    found = any(r['source_id']==src and r['target_id']==tgt and r['relationship']==kind for r in refs)
    print(f'{src} -> {tgt} {kind}: {found}')
"
```

All seven checks should report `OK` / `True`. Stop and report any `MISSING` or `False`.

### Step 3 — Verify post-state counts

```bash
curl -s http://127.0.0.1:8765/sessions       | python3 -c "import sys, json; print('Post-state sessions:',       len(json.load(sys.stdin)['data']))"
curl -s http://127.0.0.1:8765/decisions      | python3 -c "import sys, json; print('Post-state decisions:',      len(json.load(sys.stdin)['data']))"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys, json; print('Post-state planning items:', len(json.load(sys.stdin)['data']))"
curl -s http://127.0.0.1:8765/references     | python3 -c "import sys, json; print('Post-state references:',     len(json.load(sys.stdin)['data']))"
```

Deltas from pre-state should be exactly **+1 sessions / +6 decisions / +0 planning items / +7 references**. Stop and report any other delta.

### Step 4 — Verify snapshot regeneration

```bash
git status PRDs/product/crmbuilder-v2/db-export/
```

Expected modifications:

- `sessions.json` — SES-048 added
- `decisions.json` — DEC-123, DEC-124, DEC-125, DEC-126, DEC-127, DEC-128 added
- `references.json` — 7 entries added (6 decided_in plus 1 is_about)
- `change_log.json` — corresponding append entries

`planning_items.json` should NOT be modified (no new planning items in this payload).

If `git status` shows no changes in `db-export/`, the snapshot may have written to a wrong location. Run:

```bash
find . -name "sessions.json" -newer PRDs/product/crmbuilder-v2/close-out-payloads/ses_048.json 2>/dev/null
```

Report whatever path turned up; Doug will copy the snapshots to the correct location before commit.

### Step 5 — Commit

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git status   # confirm only db-export changes are staged
git commit -m "v2: apply SES-048 — workstream entity schema designed

Lands the SES-048 workstream-entity schema-design conversation's records
to the CRMBUILDER engagement database:

- 1 session: SES-048 (workstream entity schema designed; first
  per-entity governance schema specification produced)
- 6 decisions:
  - DEC-123 (WS identifier prefix and format)
  - DEC-124 (workstream-to-conversation via references-table edge per
    DEC-120; new kind conversation_belongs_to_workstream; cross-spec
    precedent of references-edge over foreign-key)
  - DEC-125 (five-status lifecycle with truly terminal terminals and
    supersession-requires-edge rule; cross-spec precedent of
    terminal-states-are-terminal for workflow-shaped lifecycles)
  - DEC-126 (field inventory with per-status lifecycle timestamps;
    cross-spec precedent of per-status timestamps for workflow-shaped
    lifecycles)
  - DEC-127 (flat catalog, no nesting in this release; retrofit path
    is references-edge addition not self-FK column)
  - DEC-128 (master plan linkage via references-edge with new kind
    workstream_planned_in_reference_book; standard API and UI defaults;
    soft-delete posture; sixteen acceptance criteria)
- 0 planning items: PI-022 (retroactive backfill, authored by SES-046)
  covers this conversation's records implicitly
- 7 references: 6 decided_in (DEC-123..128 -> SES-048) plus 1 is_about
  (SES-048 -> PI-022)

Snapshot regeneration only — payload file is unchanged. The schema
specification deliverable (governance-schema-specs/workstream.md, 393
lines) was committed separately during the conversation at b981c1f.

Next step after this apply lands: open a fresh Claude.ai conversation
against PRDs/product/crmbuilder-v2/schema-design-kickoff-conversation.md.
That conversation designs the conversation entity schema as the second
of six per-entity conversations in the workstream, inheriting three
cross-spec precedents locked by this conversation."
```

### Step 6 — Push

```bash
git push origin main
```

Stop and report if push fails.

---

## Done

After Step 6 completes, the SES-048 close-out has fully landed:

- 14 records (1 session + 6 decisions + 7 references) live in the CRMBUILDER engagement database.
- Snapshot files regenerated and committed.
- The workstream entity schema is recorded with its decisions; the conversation entity schema-design conversation can open.

**Next step:** open a fresh Claude.ai conversation against `PRDs/product/crmbuilder-v2/schema-design-kickoff-conversation.md`. That conversation designs the conversation entity schema as the second of six per-entity conversations in the workstream.

**Cross-spec precedents this conversation locked, inherited by the remaining five schema-design conversations:**

- References-edge over foreign-key for parent-child governance relationships (DEC-124).
- Per-status lifecycle timestamps for workflow-shaped governance lifecycles (DEC-126).
- Terminal-states-are-terminal discipline for governance entities with workflow lifecycles (DEC-125).

**Vocabulary additions named by this spec, aggregated by the build-planning conversation:**

- `REFERENCE_RELATIONSHIPS` += `conversation_belongs_to_workstream`, `workstream_planned_in_reference_book`
- `ENTITY_TYPES` += `workstream`, `conversation`, `reference_book`
- `_kinds_for_pair` gains two clauses tying the new kinds to their valid pairs
- Matching Alembic migration on `refs.relationship_kind` CHECK constraint

The existing generic `supersedes` kind is reused for the `(workstream, workstream)` supersession edge — no new typed kind required for that relationship.

**PI-022 discharge condition unchanged:** still open; the build-planning conversation decides the resolution path (go-forward only, selective backfill, or full backfill with reconstructed outcomes) and executes (if backfill is chosen).

---

## Error handling

- **Standard apply script exits non-zero on a non-409 error.** Stop, do not commit, report the full script output to Doug. Most likely causes: API not running, API misrouted, payload file malformed, or a validation error at the API layer (for example, foreign-key target PI-022 missing).

- **One or more `OK`-expected records returns `SKIP` (409 conflict).** This means a record with the same identifier already exists. Stop and report which identifiers conflicted. The pre-flight TOCTOU check should have caught this; a `SKIP` here indicates either a race (unlikely on a single-operator machine) or an inconsistent pre-flight state.

- **Snapshot not regenerated.** The export hook in the access layer may have failed silently. Stop, do not commit. Check the API server logs for errors during snapshot regeneration.

- **Pre-state already past SES-048.** If `Latest SES` from the pre-flight is already `SES-048` or later, the work has already been applied. Report this finding; do not run the apply again (still safe given idempotency, but unnecessary). No commit needed if pre-state already past.

- **Pre-state earlier than SES-047.** If `Latest SES` from the pre-flight is `SES-046` or earlier, the prerequisite workstream-establishing conversation's records have not landed. Stop and report — SES-047 must apply first.

- **`git status` not clean at start.** Stop and report. Do not stash. Doug decides how to handle the uncommitted changes before re-running.

- **`git pull --rebase` reports conflicts.** Stop and report. The schema specification commit (`b981c1f`) should be on origin/main by the time this prompt runs; if rebase conflicts surface, something diverged between the conversation's commit and the apply.

---

## What this prompt does NOT do

- Does not modify the payload file. It is a read-only input.
- Does not modify the apply script. The script is generic; per-payload variation is in the payload file.
- Does not author additional decisions, planning items, or sessions beyond what the payload file contains. If something is missing from the payload, fix the payload first and re-author it; do not work around in this prompt.
- Does not register the vocabulary additions (`conversation_belongs_to_workstream`, `workstream_planned_in_reference_book`, the three new `ENTITY_TYPES`, the two new `_kinds_for_pair` clauses, the Alembic migration on `refs.relationship_kind`). Those are aggregated by the build-planning conversation after all six governance entity schemas exist and applied as one consolidated migration during the build.
- Does not create the `workstreams` table or any access-layer methods. Those are built from the schema specification during the build phase, which is a separate workstream conversation later (the build-planning conversation, conversation 7 of the governance workstream).
- Does not modify any spec, plan, or methodology document. The only files touched are under `PRDs/product/crmbuilder-v2/db-export/` (snapshot regeneration).
- Does not open the next schema-design conversation (conversation entity). That is a separate fresh Claude.ai chat Doug opens against `schema-design-kickoff-conversation.md` after this apply lands.

---

*End of prompt.*
