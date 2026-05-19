# CLAUDE-CODE-PROMPT-apply-close-out-ses-044

**Last Updated:** 05-19-26 16:00
**Operating mode:** DETAIL
**Series:** apply-close-out
**Status:** Ready to execute
**Companion payload:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_044.json`

---

## Purpose

Apply the SES-044 close-out payload to the CRMBUILDER engagement's database. Lands the SES-044 planning conversation's records (1 session, 7 decisions DEC-108..114, 1 planning item PI-018, 8 references) so subsequent slice A and slice B build commits can reference them.

Net effect on the v2 database after this prompt completes:

- **Session.** SES-044 created with the planning conversation content (seven decisions surfaced via the eight-element template, two-slice build plan authored, slice prompts authored).
- **Decisions.** DEC-108 through DEC-114 created — fresh-install behavior, missing engagement_export_dir behavior, plumbing model, --engagement CLI flag scope, /admin/runtime-info deferral, centralized gate scope, fail-loud-on-missing-disk-path policy.
- **Planning item.** PI-018 created — "Complete v0.5 multi-tenancy routing: API startup engagement resolution + per-engagement export_dir". Open status; discharges after slice B lands.
- **References.** 8 added — seven `decided_in` references (DEC-108..114 → SES-044), one `is_about` reference (SES-044 → PI-018).

All 17 records (1 session + 7 decisions + 1 PI + 8 references) should report `OK` from the apply script. None should `SKIP` — this is a fresh apply, not a reconciliation.

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
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_044.json
   ```

   Stop if missing.

6. **Confirm the v2 API is running and routed at CRMBUILDER.** Two checks:

   **6a — API up:**

   ```bash
   curl -sf http://127.0.0.1:8765/sessions >/dev/null && echo "API up" || echo "API DOWN"
   ```

   If the API is down, the multi-tenancy routing fix this very payload tracks has not yet shipped — the API has to be started with an explicit environment variable pointing at CRMBUILDER.db. Stop and ask Doug to start it via:

   ```bash
   fuser -k 8765/tcp 2>/dev/null
   cd crmbuilder-v2
   CRMBUILDER_V2_DB_PATH=$(pwd)/data/engagements/CRMBUILDER.db uv run crmbuilder-v2-api &
   cd ..
   sleep 2
   curl -sf http://127.0.0.1:8765/sessions >/dev/null && echo "API now up" || echo "STILL DOWN"
   ```

   Do not start it yourself — Doug runs the recovery sequence so the process is attached to his shell.

   **6b — API routed at CRMBUILDER (not the empty v2.db):**

   ```bash
   curl -s http://127.0.0.1:8765/sessions | python3 -c "
   import sys, json
   data = json.load(sys.stdin)['data']
   if not data:
       print('STOP — API is routed at an empty database (likely the post-migration v2.db). Restart per step 6a.')
   else:
       count = len(data)
       latest = sorted(r['identifier'] for r in data)[-1]
       print(f'API routed correctly: {count} sessions, latest {latest}')
   "
   ```

   Expected: at least ~43 sessions returned, latest identifier SES-043 (the v0.6 release closeout). If the API returns an empty list or sub-43 count, the API is misrouted; stop and re-run step 6a.

7. **Verify identifiers are still uncontested.** This payload claims SES-044, DEC-108..DEC-114, and PI-018; verify none of these have been claimed by a parallel process since this payload was authored (same TOCTOU pattern as the SES-036 reconciliation precedent — parallel workstreams calculating next-available concurrently can collide).

   ```bash
   curl -sf http://127.0.0.1:8765/sessions/SES-044 >/dev/null 2>&1 && echo "SES-044 ALREADY EXISTS — STOP" || echo "SES-044 available"
   for dec in DEC-108 DEC-109 DEC-110 DEC-111 DEC-112 DEC-113 DEC-114; do
     curl -sf http://127.0.0.1:8765/decisions/$dec >/dev/null 2>&1 && echo "$dec ALREADY EXISTS — STOP" || echo "$dec available"
   done
   curl -sf http://127.0.0.1:8765/planning-items/PI-018 >/dev/null 2>&1 && echo "PI-018 ALREADY EXISTS — STOP" || echo "PI-018 available"
   ```

   Every line should end in "available". If any "ALREADY EXISTS", stop and report — Doug will need to rebase the payload to next-available identifiers (the SES-036 reconciliation pattern shows how).

8. **Capture pre-state for verification.**

   ```bash
   curl -s http://127.0.0.1:8765/sessions       | python3 -c "import sys, json; print('Pre-state sessions:',       len(json.load(sys.stdin)['data']))"
   curl -s http://127.0.0.1:8765/decisions      | python3 -c "import sys, json; print('Pre-state decisions:',      len(json.load(sys.stdin)['data']))"
   curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys, json; print('Pre-state planning items:', len(json.load(sys.stdin)['data']))"
   curl -s http://127.0.0.1:8765/references     | python3 -c "import sys, json; print('Pre-state references:',     len(json.load(sys.stdin)['data']))"
   ```

   Note the four values. Post-state should be exactly +1 / +7 / +1 / +8.

---

## Workflow

### Step 1 — Apply SES-044 payload

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_044.json
cd ..
```

Expected output:
- SES-044 reports `OK` (created).
- DEC-108, DEC-109, DEC-110, DEC-111, DEC-112, DEC-113, DEC-114 each report `OK` (created).
- PI-018 reports `OK` (created).
- 8 references each report `OK` (created).
- Script exits 0.

Total: 17 `OK` lines. Zero `SKIP` lines. Zero non-`OK` lines.

Stop and report if any record returns `SKIP` or a status other than `OK`, or if the script exits non-zero.

### Step 2 — Verify created records

```bash
echo "--- Session ---"
curl -sf http://127.0.0.1:8765/sessions/SES-044 >/dev/null && echo "SES-044 OK" || echo "SES-044 MISSING"

echo "--- Decisions ---"
for dec in DEC-108 DEC-109 DEC-110 DEC-111 DEC-112 DEC-113 DEC-114; do
  curl -sf http://127.0.0.1:8765/decisions/$dec >/dev/null && echo "$dec OK" || echo "$dec MISSING"
done

echo "--- Planning Item ---"
curl -sf http://127.0.0.1:8765/planning-items/PI-018 >/dev/null && echo "PI-018 OK" || echo "PI-018 MISSING"

echo "--- References ---"
curl -s http://127.0.0.1:8765/references | python3 -c "
import sys, json
refs = json.load(sys.stdin)['data']
for dec in ['DEC-108','DEC-109','DEC-110','DEC-111','DEC-112','DEC-113','DEC-114']:
    found = any(r['source_id']==dec and r['target_id']=='SES-044' and r['relationship']=='decided_in' for r in refs)
    print(f'{dec}->SES-044 decided_in:', found)
is_about_found = any(r['source_id']=='SES-044' and r['target_id']=='PI-018' and r['relationship']=='is_about' for r in refs)
print(f'SES-044->PI-018 is_about:', is_about_found)
"
```

All 16 checks should report `OK` / `True`. Stop and report if any reports `MISSING` or `False`.

### Step 3 — Verify post-state counts

```bash
curl -s http://127.0.0.1:8765/sessions       | python3 -c "import sys, json; print('Post-state sessions:',       len(json.load(sys.stdin)['data']))"
curl -s http://127.0.0.1:8765/decisions      | python3 -c "import sys, json; print('Post-state decisions:',      len(json.load(sys.stdin)['data']))"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys, json; print('Post-state planning items:', len(json.load(sys.stdin)['data']))"
curl -s http://127.0.0.1:8765/references     | python3 -c "import sys, json; print('Post-state references:',     len(json.load(sys.stdin)['data']))"
```

Each should be exactly +1 / +7 / +1 / +8 over the pre-state captured in pre-flight step 8. Stop and report any other delta.

### Step 4 — Verify snapshot regeneration

```bash
git status PRDs/product/crmbuilder-v2/db-export/
```

Expected modifications (assuming the multi-tenancy routing fix from this very workstream has shipped, so the snapshot lands in CRMBUILDER's export_dir at `PRDs/product/crmbuilder-v2/db-export/`):

- `sessions.json` — SES-044 added
- `decisions.json` — DEC-108..114 added (7 entries)
- `planning_items.json` — PI-018 added
- `references.json` — 8 entries added
- `change_log.json` — corresponding append entries

If the fix has not yet shipped (slice A not yet landed), the snapshot may have written to the wrong location. If `git status` shows no changes in db-export/, run:

```bash
find . -name "sessions.json" -newer PRDs/product/crmbuilder-v2/close-out-payloads/ses_044.json 2>/dev/null
```

Report whatever path turned up; Doug will manually copy the snapshots to the correct location before commit. (This is the very bug PI-018 tracks; documenting in case it surfaces during the apply itself.)

### Step 5 — Commit

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git status   # confirm only db-export changes are staged
git commit -m "v2: apply SES-044 — multi-tenancy routing fix planning close-out

Lands the SES-044 planning conversation's records to the CRMBUILDER
engagement database:

- 1 session: SES-044 (multi-tenancy routing fix planning)
- 7 decisions: DEC-108..114
  * DEC-108: fresh-install behavior — fail loud always
  * DEC-109: missing engagement_export_dir — refuse the write
  * DEC-110: plumbing model — env var + cache reset
  * DEC-111: --engagement <code> CLI flag — land in slice A
  * DEC-112: /admin/runtime-info endpoint — defer entirely
  * DEC-113: centralized gate at all active export-write paths
  * DEC-114: fail loud if export_dir doesn't exist on disk
- 1 planning item: PI-018 (complete v0.5 multi-tenancy routing)
- 8 references: 7 decided_in (DEC-108..114 -> SES-044) + 1 is_about
  (SES-044 -> PI-018)

Snapshot regeneration only — payload file is unchanged.

Build sequence after this apply lands:
1. Slice A build conversation opens against
   prompts/CLAUDE-CODE-PROMPT-multi-tenancy-routing-fix-A-helpers-cli-gate.md
   — backend helpers, gate, CLI flag, fail-loud, tests
2. Slice B build conversation opens against
   prompts/CLAUDE-CODE-PROMPT-multi-tenancy-routing-fix-B-ui-refactor-affordances.md
   — UI refactor + warning bands + dialog emphasis + integration tests
3. PI-018 discharges after slice B lands

The two bugs PI-018 tracks were surfaced during the 05-19-26 SES-001
paper-test apply attempt:
- Bug 1: API startup ignores current_engagement.json, lands on empty
  post-migration v2.db
- Bug 2: export hook writes snapshots against engine-repo default
  Settings.export_dir regardless of active engagement; under CBM,
  snapshots clobbered CRMBUILDER's db-export/

Diagnostic context at PRDs/product/crmbuilder-v2/multi-tenancy-routing-investigation-report.md.
Slice plan at PRDs/product/crmbuilder-v2/multi-tenancy-routing-fix-slice-plan.md."
```

### Step 6 — Push

```bash
git push origin main
```

Stop and report if push fails.

---

## Done

After Step 6 completes, the SES-044 close-out has fully landed:

- 17 records (1 session + 7 decisions + 1 PI + 8 references) live in the CRMBUILDER engagement database.
- Snapshot files regenerated and committed.
- Slice A and slice B build conversations can now open against their respective Claude Code prompts, referencing SES-044 / DEC-108..114 / PI-018 in their commit messages.

**Next build step:** open a fresh Claude Code session against `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-multi-tenancy-routing-fix-A-helpers-cli-gate.md` to execute slice A.

**Next governance step:** none until slice B lands, at which point discharge PI-018 (`Open` → `Closed (resolved)`) via the desktop UI's planning-items panel or direct API.
