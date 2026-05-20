# CLAUDE-CODE-PROMPT-apply-close-out-ses-046

**Last Updated:** 05-20-26 14:30
**Operating mode:** DETAIL
**Series:** apply-close-out
**Status:** Ready to execute
**Companion payload:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_046.json`

---

## Purpose

Apply the SES-046 close-out payload to the CRMBUILDER engagement's database. Lands the SES-046 strategic-scoping conversation's records (1 session, 6 decisions DEC-117..122, 1 planning item PI-022, 7 references) so the new governance entity schema-design workstream can open against `governance-entity-schema-workstream-establishing-kickoff.md` with the predecessor decisions in place.

Net effect on the v2 database after this prompt completes:

- **Session.** SES-046 created with the scoping conversation content (governance-gap identification, six principle-level decisions reached, workstream-establishing kickoff prompt authored and committed at `e1a0be4`).
- **Decisions.** DEC-117 through DEC-122 created — three purpose-built file-tracking families, deposit-bucket two-entity split, conversation as first-class, workstream as first-class, single-source-of-truth coverage extension, governance-workstream-opens-immediately.
- **Planning item.** PI-022 created — "Retroactive migration: whether to backfill governance entity records for sessions, decisions, planning items, references, and prior workstreams already in the database". Open status; discharges when a backfill decision is reached and (if backfill is chosen) executed.
- **References.** 7 added — six `decided_in` references (DEC-117..122 → SES-046), one `is_about` reference (SES-046 → PI-022).

All 15 records (1 session + 6 decisions + 1 PI + 7 references) should report `OK` from the apply script. None should `SKIP` — this is a fresh apply, not a reconciliation.

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
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_046.json
   ```

   Stop if missing.

6. **Confirm the v2 API is running and routed at CRMBUILDER.** Two checks:

   **6a — API up:**

   ```bash
   curl -sf http://127.0.0.1:8765/sessions >/dev/null && echo "API up" || echo "API DOWN"
   ```

   If the API is down, start it via the standard launch path (slice A of the multi-tenancy routing fix has landed, so `--engagement CRMBUILDER` is supported):

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

   Expected: at least 45 sessions returned, latest identifier SES-045 (the multi-tenancy routing fix slice A build closeout). If the count is less than 45 or the latest is not SES-045, the API is misrouted; stop and re-run step 6a.

7. **Verify identifiers are still uncontested.** This payload claims SES-046, DEC-117..DEC-122, and PI-022; verify none have been claimed by a parallel process since this payload was authored (TOCTOU mitigation per the SES-036 reconciliation precedent).

   ```bash
   curl -sf http://127.0.0.1:8765/sessions/SES-046 >/dev/null 2>&1 && echo "SES-046 ALREADY EXISTS — STOP" || echo "SES-046 available"
   for dec in DEC-117 DEC-118 DEC-119 DEC-120 DEC-121 DEC-122; do
     curl -sf http://127.0.0.1:8765/decisions/$dec >/dev/null 2>&1 && echo "$dec ALREADY EXISTS — STOP" || echo "$dec available"
   done
   curl -sf http://127.0.0.1:8765/planning-items/PI-022 >/dev/null 2>&1 && echo "PI-022 ALREADY EXISTS — STOP" || echo "PI-022 available"
   ```

   Every line should end in "available". If any "ALREADY EXISTS", stop and report — Doug will rebase the payload to next-available identifiers.

8. **Capture pre-state for verification.**

   ```bash
   curl -s http://127.0.0.1:8765/sessions       | python3 -c "import sys, json; print('Pre-state sessions:',       len(json.load(sys.stdin)['data']))"
   curl -s http://127.0.0.1:8765/decisions      | python3 -c "import sys, json; print('Pre-state decisions:',      len(json.load(sys.stdin)['data']))"
   curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys, json; print('Pre-state planning items:', len(json.load(sys.stdin)['data']))"
   curl -s http://127.0.0.1:8765/references     | python3 -c "import sys, json; print('Pre-state references:',     len(json.load(sys.stdin)['data']))"
   ```

   Note the four values. Post-state should be exactly +1 / +6 / +1 / +7.

---

## Workflow

### Step 1 — Apply SES-046 payload

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_046.json
cd ..
```

Expected output:
- SES-046 reports `OK` (created).
- DEC-117, DEC-118, DEC-119, DEC-120, DEC-121, DEC-122 each report `OK` (created).
- PI-022 reports `OK` (created).
- 7 references each report `OK` (created).
- Script exits 0.

Total: 15 `OK` lines. Zero `SKIP` lines. Zero non-`OK` lines.

Stop and report if any record returns `SKIP` or a status other than `OK`, or if the script exits non-zero.

### Step 2 — Verify created records

```bash
echo "--- Session ---"
curl -sf http://127.0.0.1:8765/sessions/SES-046 >/dev/null && echo "SES-046 OK" || echo "SES-046 MISSING"

echo "--- Decisions ---"
for dec in DEC-117 DEC-118 DEC-119 DEC-120 DEC-121 DEC-122; do
  curl -sf http://127.0.0.1:8765/decisions/$dec >/dev/null && echo "$dec OK" || echo "$dec MISSING"
done

echo "--- Planning Item ---"
curl -sf http://127.0.0.1:8765/planning-items/PI-022 >/dev/null && echo "PI-022 OK" || echo "PI-022 MISSING"

echo "--- References ---"
curl -s http://127.0.0.1:8765/references | python3 -c "
import sys, json
refs = json.load(sys.stdin)['data']
for dec in ['DEC-117','DEC-118','DEC-119','DEC-120','DEC-121','DEC-122']:
    found = any(r['source_id']==dec and r['target_id']=='SES-046' and r['relationship']=='decided_in' for r in refs)
    print(f'{dec}->SES-046 decided_in:', found)
is_about_found = any(r['source_id']=='SES-046' and r['target_id']=='PI-022' and r['relationship']=='is_about' for r in refs)
print(f'SES-046->PI-022 is_about:', is_about_found)
"
```

All 14 checks should report `OK` / `True`. Stop and report if any reports `MISSING` or `False`.

### Step 3 — Verify post-state counts

```bash
curl -s http://127.0.0.1:8765/sessions       | python3 -c "import sys, json; print('Post-state sessions:',       len(json.load(sys.stdin)['data']))"
curl -s http://127.0.0.1:8765/decisions      | python3 -c "import sys, json; print('Post-state decisions:',      len(json.load(sys.stdin)['data']))"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys, json; print('Post-state planning items:', len(json.load(sys.stdin)['data']))"
curl -s http://127.0.0.1:8765/references     | python3 -c "import sys, json; print('Post-state references:',     len(json.load(sys.stdin)['data']))"
```

Each should be exactly +1 / +6 / +1 / +7 over the pre-state captured in pre-flight step 8. Stop and report any other delta.

### Step 4 — Verify snapshot regeneration

```bash
git status PRDs/product/crmbuilder-v2/db-export/
```

Expected modifications:

- `sessions.json` — SES-046 added
- `decisions.json` — DEC-117..122 added (6 entries)
- `planning_items.json` — PI-022 added
- `references.json` — 7 entries added
- `change_log.json` — corresponding append entries

If `git status` shows no changes in `db-export/`, the snapshot may have written to a wrong location (multi-tenancy routing bug regression). Run:

```bash
find . -name "sessions.json" -newer PRDs/product/crmbuilder-v2/close-out-payloads/ses_046.json 2>/dev/null
```

Report whatever path turned up; Doug will copy the snapshots to the correct location before commit.

### Step 5 — Commit

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git status   # confirm only db-export changes are staged
git commit -m "v2: apply SES-046 — governance entity schema scoping close-out

Lands the SES-046 strategic-scoping conversation's records to the
CRMBUILDER engagement database:

- 1 session: SES-046 (governance entity schema gap identified, six
  principle-level decisions reached, workstream-establishing kickoff
  prompt authored and committed at e1a0be4)
- 6 decisions: DEC-117..122
  * DEC-117: Three purpose-built entity-type families for workflow
    files (reference book, work ticket, deposit bucket)
  * DEC-118: Two entities within the deposit bucket (close-out payload
    and deposit event separate)
  * DEC-119: Conversation as a first-class entity, distinct from the
    session record
  * DEC-120: Workstream as a first-class entity
  * DEC-121: Single source of truth coverage extension — umbrella
    principle covering all governance-meaningful artifacts
  * DEC-122: Governance entity schema-design workstream opens
    immediately, in parallel to other in-flight work
- 1 planning item: PI-022 (retroactive migration question: whether to
  backfill governance entity records for pre-existing sessions,
  decisions, references, and workstreams)
- 7 references: 6 decided_in (DEC-117..122 -> SES-046) + 1 is_about
  (SES-046 -> PI-022)

Snapshot regeneration only — payload file is unchanged.

Next step after this apply lands: open a fresh Claude.ai conversation
against PRDs/product/crmbuilder-v2/governance-entity-schema-workstream-establishing-kickoff.md
(committed at e1a0be4). That conversation produces the workstream
master plan, the schema-spec methodology guide, six per-entity
schema-design kickoff prompts, and its own session record. After it
closes, six per-entity schema-design conversations run in the order
specified by the workstream plan (workstream, conversation, reference
book, work ticket, close-out payload, deposit event), then a
build-planning conversation consumes the six specs and produces the
integrating PRD, implementation plan, and per-slice execution prompts.

Governance workstream operates against the CRMBUILDER dogfood
engagement only; runs in parallel to multi-tenancy routing fix slice B
and the paper-test-flagged sub-domain hierarchy amendment in the CBM
engagement (Planning Item 001 in the CBM engagement)."
```

### Step 6 — Push

```bash
git push origin main
```

Stop and report if push fails.

---

## Done

After Step 6 completes, the SES-046 close-out has fully landed:

- 15 records (1 session + 6 decisions + 1 PI + 7 references) live in the CRMBUILDER engagement database.
- Snapshot files regenerated and committed.
- The governance entity schema-design workstream's predecessor state is in place.

**Next step:** open a fresh Claude.ai conversation against `PRDs/product/crmbuilder-v2/governance-entity-schema-workstream-establishing-kickoff.md`. That conversation runs the workstream-establishing planning conversation per the kickoff prompt's instructions and produces the workstream master plan, methodology guide, six per-entity schema-design kickoff prompts, and its own close-out.

**Next governance step inside this workstream:** none — the workstream-establishing conversation handles its own close-out and authors the kickoff prompt for the first per-entity schema-design conversation (workstream entity).

**PI-022 discharge condition:** when a backfill decision is reached at the workstream-establishing conversation or any of the per-entity schema-design conversations, and (if backfill is chosen) the backfill is executed.
