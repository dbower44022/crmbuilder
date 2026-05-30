# Apply close-out — SES-131 / CNV-033 (PI-081 orchestrator _execute, addresses)

**Engagement:** CRMBUILDER. **Payload:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_131.json`.

## Net effect

Lands the builder-session governance for PI-081 (orchestrator `_execute`
implementation). PI-081 is **addressed, not resolved** — the WS-012 §7.2
acceptance run is deferred (no open PI carries an `area`, so the depth-0
wave yields 0 clusters). Records:

- 1 session (SES-131, complete), 1 conversation (CNV-033, complete)
- 4 decisions (DEC-336 per-child worktree isolation, DEC-337
  `--dangerously-skip-permissions` child autonomy, DEC-338
  completion-detection + halt-on-failure, DEC-339 bounded human-watched
  first run)
- 2 commits (800e329 `_execute` + tests, 3ba1875 `--dry-run` flag)
- references: conversation→session + conversation→workstream membership,
  4× `decided_in` (DEC→CNV-033), and **`PI-081 blocked_by PI-062`**
- `addresses_planning_items: [PI-081]` (no status flip — PI-081 stays Open)
- 1 deposit_event + lazy-created COP-131 + dep log

## Pre-flight

```bash
cd ~/Dropbox/Projects/crmbuilder
git status --porcelain          # expect clean (payload+prompt staged separately)
curl -s http://127.0.0.1:8765/health
# Re-verify heads haven't advanced in parallel; re-key if claimed.
for ep in sessions conversations decisions commits; do \
  curl -s "http://127.0.0.1:8765/$ep/next-identifier"; echo; done
# Expect: SES-131, CNV-033, DEC-336, CM-0067 (or later — re-key on collision).
```

If any head has advanced past the payload's reserved identifiers, re-key
SES/CNV/DEC in `ses_131.json` to the next free slots (update every
internal reference) before applying — SES-077 re-keying precedent.

## Apply

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_131.json
```

Expected: conversation ✓, session ✓, 4 decisions ✓, 2 commits ✓,
7 references ✓ (membership ×2, decided_in ×4, blocked_by ×1),
addresses_planning_items ✓ (1 edge), deposit_event DEP-NNN ✓. The
membership edges hoist into the singular blocks automatically.

## Post-apply verification

```bash
curl -s http://127.0.0.1:8765/sessions/SES-131 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print(d['session_status'])"   # complete
curl -s http://127.0.0.1:8765/planning-items/PI-081 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print(d['status'])"      # Open (addressed, not resolved)
curl -s "http://127.0.0.1:8765/references/from/planning_item/PI-081" | python3 -c "import sys,json;[print(r['relationship'],r['target_id']) for r in json.load(sys.stdin)['data']]"  # blocked_by PI-062
curl -s "http://127.0.0.1:8765/references/from/decision/DEC-336" | python3 -c "import sys,json;[print(r['relationship'],r['target_type'],r['target_id']) for r in json.load(sys.stdin)['data']]"  # decided_in conversation CNV-033
```

## Commit snapshot

The apply regenerates `db-export/*.json` + `change_log.json` and writes a
new `deposit-event-logs/dep_NNN.log`. Commit those together with the
payload + this apply prompt:

```bash
git add PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/ \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_131.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-131.md
git commit -m "v2: SES-131 close-out — address PI-081 (orchestrator _execute); defer §7.2 acceptance pending PI-062 area backfill"
```

**Doug pushes.**
