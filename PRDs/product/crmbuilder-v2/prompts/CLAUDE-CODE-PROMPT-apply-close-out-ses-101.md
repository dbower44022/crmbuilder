# Apply close-out: SES-101 (PI-091/092/093 — executive_summary UI surface)

This applies `PRDs/product/crmbuilder-v2/close-out-payloads/ses_101.json`,
which resolves PI-091, PI-092, and PI-093 in a single transaction. The
implementation commit is already on `main` (3adb959e6bf8d4f7867a81709fef1065445fcf9d).

## Pre-flight

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
# API health check
curl -fsS http://127.0.0.1:8765/health || { echo "API down — start crmbuilder-v2-api &"; exit 1; }

# Confirm the implementation commit is at HEAD (or in the current branch's ancestry)
git log --oneline -1 3adb959 && \
  echo "OK: implementation commit reachable"

# Confirm the three target PIs are still Open (and have NOT been resolved by another session)
for pi in PI-091 PI-092 PI-093 ; do
  status=$(curl -fsS "http://127.0.0.1:8765/planning-items/$pi" | \
    uv run python -c "import json,sys; print(json.load(sys.stdin)['data']['status'])")
  echo "$pi: $status"
done
# All three must be "Open". If any is "Resolved", abort and investigate — a parallel session got there first.

# Confirm next-identifier heads match the payload's reserved identifiers
echo "session next:" $(curl -fsS http://127.0.0.1:8765/sessions/next-identifier | uv run python -c "import json,sys; print(json.load(sys.stdin)['data']['next'])")
echo "conversation next:" $(curl -fsS http://127.0.0.1:8765/conversations/next-identifier | uv run python -c "import json,sys; print(json.load(sys.stdin)['data']['next'])")
# Expected: SES-101, CNV-003. If different, re-key the payload before applying.
```

## Apply

```bash
cd /home/doug/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_101.json
```

The script tees stdout to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log`
(next free dep id at apply time — currently DEP-088). It writes:

- `session` SES-101 with `session_belongs_to_workstream` → WS-012
- `conversation` CNV-003 with `conversation_belongs_to_session` → SES-101
- `commits` row for 3adb959 with `recorded_in` back-edges to CNV-003 / SES-101
- `resolves_planning_items` atomic edges flipping PI-091, PI-092, PI-093 from Open → Resolved
- a `close_out_payload` row (lazy-created from the file path)
- a `deposit_event` (DEP-NNN) with `wrote_record` edges to every record above

## Post-apply verification

```bash
# All three PIs must now be Resolved
for pi in PI-091 PI-092 PI-093 ; do
  status=$(curl -fsS "http://127.0.0.1:8765/planning-items/$pi" | \
    uv run python -c "import json,sys; print(json.load(sys.stdin)['data']['status'])")
  echo "$pi: $status"
done
# All three must read "Resolved".

# Confirm SES-101, CNV-003 exist
curl -fsS http://127.0.0.1:8765/sessions/SES-101 | \
  uv run python -c "import json,sys; d=json.load(sys.stdin); print('SES-101:', d['data']['session_status'])"
curl -fsS http://127.0.0.1:8765/conversations/CNV-003 | \
  uv run python -c "import json,sys; d=json.load(sys.stdin); print('CNV-003:', d['data']['conversation_status'])"

# Confirm the new deposit_event recorded the apply
curl -fsS 'http://127.0.0.1:8765/deposit-events?limit=1' | \
  uv run python -c "import json,sys; d=json.load(sys.stdin); r=d['data'][0]; print(r['deposit_event_identifier'], '-', r.get('deposit_event_outcome') or r.get('outcome'))"
```

## Commit close-out artifacts

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git add \
  PRDs/product/crmbuilder-v2/close-out-payloads/ses_101.json \
  PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-101.md \
  PRDs/product/crmbuilder-v2/deposit-event-logs/dep_*.log \
  PRDs/product/crmbuilder-v2/db-export/

git commit -m "v2: SES-101 close-out applied — PI-091/092/093 resolved (executive_summary UI surface)"
```

Note: the `db-export/` snapshot diff includes pre-existing changes from the
SES-100 apply (PI-094 / PI-095 creation) that were never separately committed.
Applying SES-101 regenerates the snapshots from the current live DB state,
producing one coherent snapshot diff that absorbs both deltas. That is by
design — snapshots represent DB state at regen time, not per-session deltas.

## Rollback

`apply_close_out.py` is idempotent on re-run (a session/conversation already
present produces 409 Conflict and the run continues). If the apply fails
mid-flight, re-running the same command is safe. If the apply succeeds but
the post-apply verification reveals a logic error in the payload, author a
correcting session — do not edit the applied records directly.
