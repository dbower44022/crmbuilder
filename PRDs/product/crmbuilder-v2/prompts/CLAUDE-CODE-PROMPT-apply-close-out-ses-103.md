# Apply close-out: SES-103 (PI-019/050/053/068/080 — second autonomous orchestrator run)

This applies `PRDs/product/crmbuilder-v2/close-out-payloads/ses_103.json`,
which resolves PI-019, PI-050, PI-053, PI-068, and PI-080 in a single
transaction. All five implementation commits are already on `main`:

| PI    | SHA       | First line |
|-------|-----------|-----------|
| PI-068 | cac3909  | author specifications/README.md manifest |
| PI-053 | bd55db0  | add Commit model to exporter._EXPORT_TABLES |
| PI-019 | 07fa7b2  | cross-file category resolution in YAML layout validator |
| PI-050 | 2903f77  | extend enumerate_commits.py with --commits mode |
| PI-080 | 5333f46  | register conversation_orchestrates_conversation kind |

## Pre-flight

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
curl -fsS http://127.0.0.1:8765/health || { echo "API down"; exit 1; }

# All five PIs must be Open at apply time
for pi in PI-019 PI-050 PI-053 PI-068 PI-080 ; do
  status=$(curl -fsS "http://127.0.0.1:8765/planning-items/$pi" | \
    uv run python -c "import json,sys; print(json.load(sys.stdin)['data']['status'])")
  echo "$pi: $status"
done
# If any is Resolved, abort — a parallel session got there first.

# Confirm reserved identifiers still align
echo "session next:" $(curl -fsS http://127.0.0.1:8765/sessions/next-identifier | uv run python -c "import json,sys; print(json.load(sys.stdin)['data']['next'])")
echo "conversation next:" $(curl -fsS http://127.0.0.1:8765/conversations/next-identifier | uv run python -c "import json,sys; print(json.load(sys.stdin)['data']['next'])")
# Expected: SES-103, CNV-005. If different, re-key the payload before applying.
```

## Apply

```bash
cd /home/doug/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_103.json
```

Note: the running `crmbuilder-v2-api` daemon was started before migration
0022 (PI-080) landed, so its in-Python REFERENCE_RELATIONSHIPS set does
not include `conversation_orchestrates_conversation`. This payload does
NOT write that kind, so the gap is benign for THIS apply. Restart the
daemon (`pkill crmbuilder-v2-api && crmbuilder-v2-api &`) after this
close-out before any future session writes a
`conversation_orchestrates_conversation` reference.

## Post-apply verification

```bash
# All five PIs must now read Resolved
for pi in PI-019 PI-050 PI-053 PI-068 PI-080 ; do
  curl -fsS "http://127.0.0.1:8765/planning-items/$pi" | \
    uv run python -c "import json,sys; d=json.load(sys.stdin); print(d['data']['identifier'], d['data']['status'])"
done

curl -fsS http://127.0.0.1:8765/sessions/SES-103 | \
  uv run python -c "import json,sys; d=json.load(sys.stdin)['data']; print('SES-103:', d['session_status'])"
curl -fsS http://127.0.0.1:8765/conversations/CNV-005 | \
  uv run python -c "import json,sys; d=json.load(sys.stdin)['data']; print('CNV-005:', d['conversation_status'])"
```

## Commit close-out artifacts

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git add \
  PRDs/product/crmbuilder-v2/close-out-payloads/ses_103.json \
  PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-103.md \
  PRDs/product/crmbuilder-v2/deposit-event-logs/dep_*.log \
  PRDs/product/crmbuilder-v2/db-export/

git commit -m "v2: SES-103 close-out applied — PI-019/050/053/068/080 resolved (second autonomous orchestrator run)"
```

The `db-export/` snapshot diff also absorbs the new `commits.json` file
that PI-053's wiring now produces alongside the rest of the engagement
snapshot (a meta-validation of PI-053's own fix).

## Rollback

`apply_close_out.py` is idempotent on re-run (already-present records
produce 409 Conflict and the run continues). If the apply fails
mid-flight, re-running is safe.
