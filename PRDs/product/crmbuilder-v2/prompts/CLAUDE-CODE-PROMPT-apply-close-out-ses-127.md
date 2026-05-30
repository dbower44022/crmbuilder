# Apply close-out — SES-127 / CNV-029 (implements + resolves PI-108)

## Purpose

Apply the SES-127 close-out: records the PI-108 implementation (universal timestamp visibility) and resolves PI-108.

**Net effect**
- Creates session **SES-127**, conversation **CNV-029**.
- Records commits **550e10e** (slice A) and **2915393** (slices B/C).
- Creates references: `CNV-029 conversation_belongs_to_session SES-127`, `SES-127 session_belongs_to_workstream WS-013`.
- Flips **PI-108** `Open → Resolved`.

## Branch note

The implementation lives on branch **`pi-108-finish`** (one commit ahead of `main`: `2915393`). Slice A (`550e10e`) is already in `main`'s ancestry. The parallel orchestrator's ~14 panel commits also landed on `main` (in `e8d0c19`). Merge `pi-108-finish` → `main` to land the full PI-108.

## Pre-flight

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git status --short
curl -s http://127.0.0.1:8765/health
for e in sessions conversations; do printf "%s -> " "$e"; curl -s "http://127.0.0.1:8765/$e/next-identifier"; echo; done
# Expect SES-127 / CNV-029 (re-key if a parallel session advanced them).
curl -s http://127.0.0.1:8765/planning-items/PI-108 | python3 -c "import sys,json;print('PI-108:',json.load(sys.stdin)['data']['status'])"
```

## Apply

```bash
cd /home/doug/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_127.json
# Expected OK: 1 session, 1 conversation, 2 commits, 2 references, PI-108 resolved.
```

## Post-apply verification

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
curl -s http://127.0.0.1:8765/planning-items/PI-108 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print(d['identifier'],'|',d['status'])"
```

## Commit snapshot regeneration

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_127.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-127.md \
        PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "v2: SES-127 close-out — implement + resolve PI-108 (universal timestamp visibility)"
```
Doug reviews/merges `pi-108-finish` → `main` and pushes (Claude Code convention).
