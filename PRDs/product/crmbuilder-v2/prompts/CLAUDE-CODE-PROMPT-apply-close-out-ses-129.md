# Apply close-out — SES-129 / CNV-031 (implements + resolves PI-105)

## Purpose

Apply the SES-129 close-out: records the PI-105 implementation (executive_summary write-surface gaps) and resolves PI-105.

**Net effect**
- Creates session **SES-129**, conversation **CNV-031**.
- Records commit **8293a06** (branch `pi-105-exec-summary-claude`).
- Creates references: `CNV-031 conversation_belongs_to_session SES-129`, `SES-129 session_belongs_to_workstream WS-011`.
- Flips **PI-105** `Open → Resolved`.

## Branch / snapshot note (parallel-orchestrator cleanup)

- PI-105 code + this close-out live on branch **`pi-105-exec-summary-claude`** (`8293a06` code, plus this close-out commit). The branch was cut defensively because a parallel orchestrator hijacked `pi-105-exec-summary`.
- This close-out commit deliberately **omits `db-export/*.json`**: at apply time those snapshots were dirty with another orchestrator's uncommitted `ses_128` deltas, so committing them here would entangle the two. Regenerate and commit `db-export/` once during branch reconciliation (the snapshots are a DB mirror; the live DB is the source of truth).
- Deferred PI-105 acceptance #7: the live CNV-016 executive-summary refresh via MCP requires the running API restarted with this code; the capability is already proven by the MCP end-to-end tests.

## Pre-flight

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git status --short
curl -s http://127.0.0.1:8765/health
for e in sessions conversations; do printf "%s -> " "$e"; curl -s "http://127.0.0.1:8765/$e/next-identifier"; echo; done
# Expect SES-129 / CNV-031 (re-key if a parallel session advanced them).
curl -s http://127.0.0.1:8765/planning-items/PI-105 | python3 -c "import sys,json;print('PI-105:',json.load(sys.stdin)['data']['status'])"
```

## Apply

```bash
cd /home/doug/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_129.json
# Expected OK: 1 session, 1 conversation, 1 commit, 2 references, PI-105 resolved.
```

## Post-apply verification

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
curl -s http://127.0.0.1:8765/planning-items/PI-105 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print(d['identifier'],'|',d['status'])"
```

## Commit

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_129.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-129.md \
        PRDs/product/crmbuilder-v2/deposit-event-logs/dep_121.log
git commit -m "v2: SES-129 close-out — implement + resolve PI-105 (exec_summary write surfaces)"
# db-export/ intentionally NOT committed here — regenerate during branch reconciliation.
```
Doug reviews/merges `pi-105-exec-summary-claude` and pushes.
