# CLAUDE-CODE-PROMPT-apply-close-out-ses-047

**Last Updated:** 05-20-26 23:30
**Operating mode:** DETAIL
**Series:** apply-close-out
**Status:** Ready to execute
**Companion payload:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_047.json`

---

## Purpose

Apply the SES-047 close-out payload to the CRMBUILDER engagement's database. Lands the SES-047 workstream-establishing planning conversation's records (1 session, 0 decisions, 0 planning items, 1 reference) so the first per-entity schema-design conversation can open against `PRDs/product/crmbuilder-v2/schema-design-kickoff-workstream.md` with the workstream's foundation in place.

Net effect on the v2 database after this prompt completes:

- **Session.** SES-047 created with the workstream-establishing planning conversation's content (eight artifacts produced: master plan + methodology guide + six per-entity kickoff prompts; the six foundation decisions DEC-117..122 and the retroactive-backfill PI-022 referenced rather than re-recorded because SES-046 had already authored them).
- **Decisions.** None. The conversation produced no new decisions; the foundation decisions DEC-117..122 were recorded by SES-046.
- **Planning items.** None. PI-022 (retroactive backfill) was authored by SES-046; this conversation references it rather than re-authoring.
- **References.** 1 added — `SES-047 is_about PI-022` (the workstream-establishing conversation refines the planning context PI-022 frames).

All 2 records (1 session + 1 reference) should report `OK` from the apply script. None should `SKIP` — this is a fresh apply, not a reconciliation.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root (typically `~/Dropbox/Projects/crmbuilder`). Stop and report if unexpected.

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

   Stop and report if there are conflicts.

5. **Confirm payload file exists:**

   ```bash
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_047.json
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

   Expected: at least 46 sessions returned, latest identifier SES-046 (the predecessor scoping conversation, which SES-047 follows). If the count is less than 46 or the latest is not SES-046, the API is misrouted or SES-046 has not yet been applied; stop and re-run step 6a or apply SES-046 first.

7. **Verify SES-047 is uncontested and prerequisites are in place** (TOCTOU mitigation per the SES-036 reconciliation precedent):

   ```bash
   # SES-047 must not yet exist
   curl -sf http://127.0.0.1:8765/sessions/SES-047 >/dev/null 2>&1 && echo "SES-047 ALREADY EXISTS — STOP" || echo "SES-047 available"

   # PI-022 must exist (foreign-key target for the one reference)
   curl -sf http://127.0.0.1:8765/planning-items/PI-022 >/dev/null 2>&1 && echo "PI-022 exists — reference target valid" || echo "PI-022 MISSING — STOP and apply SES-046 first"
   ```

   Expected: "SES-047 available" and "PI-022 exists — reference target valid". Any other output: stop and report.

8. **Capture pre-state for verification.**

   ```bash
   curl -s http://127.0.0.1:8765/sessions       | python3 -c "import sys, json; print('Pre-state sessions:',       len(json.load(sys.stdin)['data']))"
   curl -s http://127.0.0.1:8765/decisions      | python3 -c "import sys, json; print('Pre-state decisions:',      len(json.load(sys.stdin)['data']))"
   curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys, json; print('Pre-state planning items:', len(json.load(sys.stdin)['data']))"
   curl -s http://127.0.0.1:8765/references     | python3 -c "import sys, json; print('Pre-state references:',     len(json.load(sys.stdin)['data']))"
   ```

   Note the four values. Post-state should be exactly +1 / +0 / +0 / +1.

---

## Workflow

### Step 1 — Apply SES-047 payload

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_047.json
cd ..
```

Expected output:
- SES-047 reports `OK` (created).
- 1 reference (`SES-047 is_about PI-022`) reports `OK` (created).
- Script exits 0.

Total: 2 `OK` lines. Zero `SKIP` lines. Zero non-`OK` lines.

Stop and report if any record returns `SKIP` or a status other than `OK`, or if the script exits non-zero.

### Step 2 — Verify created records

```bash
echo "--- Session ---"
curl -sf http://127.0.0.1:8765/sessions/SES-047 >/dev/null && echo "SES-047 OK" || echo "SES-047 MISSING"

echo "--- Reference ---"
curl -s http://127.0.0.1:8765/references | python3 -c "
import sys, json
refs = json.load(sys.stdin)['data']
found = any(
    r['source_id']=='SES-047' and
    r['target_id']=='PI-022' and
    r['relationship']=='is_about'
    for r in refs
)
print(f'SES-047->PI-022 is_about:', found)
"
```

Both checks should report `OK` / `True`. Stop and report if either reports `MISSING` or `False`.

### Step 3 — Verify post-state counts

```bash
curl -s http://127.0.0.1:8765/sessions       | python3 -c "import sys, json; print('Post-state sessions:',       len(json.load(sys.stdin)['data']))"
curl -s http://127.0.0.1:8765/decisions      | python3 -c "import sys, json; print('Post-state decisions:',      len(json.load(sys.stdin)['data']))"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys, json; print('Post-state planning items:', len(json.load(sys.stdin)['data']))"
curl -s http://127.0.0.1:8765/references     | python3 -c "import sys, json; print('Post-state references:',     len(json.load(sys.stdin)['data']))"
```

Deltas from pre-state should be exactly +1 sessions / +0 decisions / +0 planning items / +1 references. Stop and report any other delta.

### Step 4 — Verify snapshot regeneration

```bash
git status PRDs/product/crmbuilder-v2/db-export/
```

Expected modifications:

- `sessions.json` — SES-047 added
- `references.json` — 1 entry added (SES-047 → PI-022 is_about)
- `change_log.json` — corresponding append entries

`decisions.json` and `planning_items.json` should NOT be modified (no new records of those kinds).

If `git status` shows no changes in `db-export/`, the snapshot may have written to a wrong location. Run:

```bash
find . -name "sessions.json" -newer PRDs/product/crmbuilder-v2/close-out-payloads/ses_047.json 2>/dev/null
```

Report whatever path turned up; Doug will copy the snapshots to the correct location before commit.

### Step 5 — Commit

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git status   # confirm only db-export changes are staged
git commit -m "v2: apply SES-047 — governance schema-design workstream established

Lands the SES-047 workstream-establishing planning conversation's records
to the CRMBUILDER engagement database:

- 1 session: SES-047 (governance entity schema-design workstream
  established; workstream master plan, schema-spec methodology guide,
  and six per-entity schema-design kickoff prompts produced)
- 0 decisions: DEC-117..122 were recorded by the predecessor scoping
  conversation SES-046 and are referenced as foundation rather than
  re-recorded
- 0 planning items: PI-022 (retroactive backfill) was authored by
  SES-046 and is referenced rather than re-authored
- 1 reference: SES-047 is_about PI-022

Snapshot regeneration only — payload file is unchanged. The eight
workstream-scaffolding artifacts produced by SES-047 (master plan,
methodology guide, six per-entity kickoff prompts) were committed
separately during the conversation at 95b7939, 802bdc4, 369f32e,
0dfcc25, and 0aeb5c0.

Next step after this apply lands: open a fresh Claude.ai conversation
against PRDs/product/crmbuilder-v2/schema-design-kickoff-workstream.md.
That conversation designs the workstream entity schema, settles the
nested-workstream question DEC-120 deferred, locks the WS identifier
prefix, and establishes cross-spec consistency precedents for the
remaining five per-entity schema-design conversations."
```

### Step 6 — Push

```bash
git push origin main
```

Stop and report if push fails.

---

## Done

After Step 6 completes, the SES-047 close-out has fully landed:

- 2 records (1 session + 1 reference) live in the CRMBUILDER engagement database.
- Snapshot files regenerated and committed.
- The governance entity schema-design workstream's foundation is in place; the first per-entity schema-design conversation can open.

**Next step:** open a fresh Claude.ai conversation against `PRDs/product/crmbuilder-v2/schema-design-kickoff-workstream.md`. That conversation designs the workstream entity schema as the first of six per-entity conversations in the workstream.

**Next governance step inside this workstream:** the workstream schema-design conversation produces `governance-schema-specs/workstream.md` (creating the `governance-schema-specs/` directory) and its own close-out (session, decisions, any planning items).

**PI-022 discharge condition:** when a backfill resolution path is reached (go-forward only, selective backfill, or full backfill with reconstructed outcomes — see PI-022's description) at the build-planning conversation, and (if backfill is chosen) the backfill is executed.
