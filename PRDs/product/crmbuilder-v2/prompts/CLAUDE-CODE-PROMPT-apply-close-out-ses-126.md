# Apply close-out — SES-126 / CNV-028 (implements + resolves PI-109)

## Purpose

Apply the SES-126 close-out: records the WT-049 investigation, the WT-049..054 cohort data fix, the filing of PI-109, and the PI-109 implementation. Resolves PI-109.

**Net effect**
- Creates session **SES-126**, conversation **CNV-028**.
- Records commits **2c9759d**, **1d6aedf**, **e4246e2** against the session.
- Creates decisions **DEC-334** (auto-consume side-effect placement) and **DEC-335** (pre-insert single-use guard).
- Creates references: `CNV-028 conversation_belongs_to_session SES-126`, `SES-126 session_belongs_to_workstream WS-011`, `DEC-334 decided_in CNV-028`, `DEC-335 decided_in CNV-028`.
- Flips **PI-109** `Open → Resolved`.
- No new work_tickets or planning items.

Note: this is the first apply that exercises the new opens-against auto-consume side-effect on its own apply chain. WT-049..054 were already retired by commit 2c9759d's PATCH pass, so the side-effect has no fresh cohort to flip in this apply — it's a behavior-change ahead of next-cohort use.

## Pre-flight

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git status --short
git pull --rebase origin main
curl -s http://127.0.0.1:8765/health
for e in sessions conversations decisions; do printf "%s -> " "$e"; curl -s "http://127.0.0.1:8765/$e/next-identifier"; echo; done
# Expect: sessions SES-126, conversations CNV-028, decisions DEC-334.
# Parallel sessions are active — re-key the payload + this prompt if any advanced.
curl -s http://127.0.0.1:8765/planning-items/PI-109 | python3 -c "import sys,json;print('PI-109 status:',json.load(sys.stdin)['data']['status'])"
# Expect: Open
ls PRDs/product/crmbuilder-v2/close-out-payloads/ses_126.json
```

## Apply

```bash
cd /home/doug/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_126.json
# Expected OK: 1 session, 1 conversation, 3 commits, 2 decisions, 4 references, PI-109 resolved.
```

## Post-apply verification

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
curl -s http://127.0.0.1:8765/planning-items/PI-109 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print(d['identifier'],'|',d['status'])"
# Expect: PI-109 | Resolved
curl -s http://127.0.0.1:8765/sessions/SES-126 | python3 -c "import sys,json;print(json.load(sys.stdin)['data'].get('session_status'))"
# Expect: complete
curl -s http://127.0.0.1:8765/decisions/DEC-334 | python3 -c "import sys,json;print(json.load(sys.stdin)['data'].get('status'))"
# Expect: Active
```

## Commit snapshot regeneration

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_126.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-126.md \
        PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "v2: SES-126 close-out — investigate WT-049 drift, retire WT-049..054, implement + resolve PI-109 (auto-consume work_tickets)"
```

Doug pushes after review (Claude Code push convention).
