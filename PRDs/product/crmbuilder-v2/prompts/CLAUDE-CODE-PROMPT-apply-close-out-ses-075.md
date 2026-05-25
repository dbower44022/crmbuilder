# CLAUDE-CODE-PROMPT — Apply SES-075 close-out payload

**Last Updated:** 05-25-26 02:30
**Purpose:** Apply the SES-075 close-out payload for the audit-v1.2 prompt-series authoring conversation. Lands SES-075 plus six decisions (DEC-238 through DEC-243), one planning item (PI-051), and eight references (six `decided_in` plus two `is_about`). The payload uses the four-section format (label, session, decisions, planning_items, references) rather than the nine-section v0.8 format introduced in SES-074 — this conversation produced no commits in the V2 codebase, no work tickets, no charter changes, and no other entity-table additions, so the four-section shape is sufficient.

**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_075.json`

**Predecessors:**
- SES-074 close-out payload should land before this one (currently in flight per `prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-074.md`). SES-075 claims SES-075 / DEC-238 / PI-051 — identifiers chosen to leave a buffer at DEC-227..231 for any other in-flight sandboxes that may have claimed identifiers in that range via parallel-sandbox workflows. If SES-074 has not yet been applied at the time of this prompt's execution, applying SES-075 first is safe (the two payloads do not share identifiers), but the conventional order is sequential.
- The audit-v1.2 implementation commits (Prompt A through Prompt K) all land in the crmbuilder-v1 codebase paths; none of them are V2 code commits, so no `commits` payload section is needed. The eleven CLAUDE-CODE-PROMPT prompt files in `PRDs/product/crmbuilder-automation-PRD/` are sandbox-authored artifacts already on origin via sandbox commits and do not require V2 governance records.

**Successor:** PI-051 enters the backlog at status Open with no committed timeline. Whoever picks up the v1.4 workstream investigates the four candidate paths documented in PI-051's description (Dynamic Handler JS, Teams-as-Roles proxy, upstream EspoCRM feature request, Layout Sets + Teams for forRoles).

---

## Scope

Apply `close-out-payloads/ses_075.json` using `crmbuilder-v2/scripts/apply_close_out.py`. The payload contains:

- **1 session** (SES-075, status Complete)
- **6 decisions** (DEC-238 natural-form scope_access keys; DEC-239 audit_log removed from §12.4; DEC-240 three EspoCRM-only PATCH permissions preserved; DEC-241 role_manager pre-flight server-state validation; DEC-242 deploy ordering security-LAST + schema §12.6 corrected; DEC-243 §12.5 NOT_SUPPORTED on EspoCRM 9.x + schema §12.5 documentation updated, deferred to v1.4)
- **1 planning_item** (PI-051 audit-v1.4 deferred work, item_type `pending_work`, status Open)
- **8 references**:
    - `decision:DEC-238 -[decided_in]-> session:SES-075`
    - `decision:DEC-239 -[decided_in]-> session:SES-075`
    - `decision:DEC-240 -[decided_in]-> session:SES-075`
    - `decision:DEC-241 -[decided_in]-> session:SES-075`
    - `decision:DEC-242 -[decided_in]-> session:SES-075`
    - `decision:DEC-243 -[decided_in]-> session:SES-075`
    - `session:SES-075 -[is_about]-> planning_item:PI-051`
    - `decision:DEC-243 -[is_about]-> planning_item:PI-051`

The payload is idempotent on re-run; HTTP 409 SKIPs are treated as already-present.

---

## Pre-flight

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

# Clean working tree (acknowledge that there will be unrelated unstaged work in Doug's tree — proceed regardless)
git status

# Pull latest commits
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# Git identity
git config user.email | grep -q "doug@dougbower.com" || git config user.email "doug@dougbower.com"
git config user.name | grep -q "Doug" || git config user.name "Doug Bower"

# Payload exists
test -f ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_075.json && echo "Payload present" || echo "Payload missing — abort"

# API health
curl -sf http://127.0.0.1:8765/health > /dev/null && echo "API healthy" || echo "API not running — start it before proceeding"

# Pre-apply identifier-head capture (record current heads for the post-apply verification step)
python3 -c "
import json
sessions = json.load(open('../PRDs/product/crmbuilder-v2/db-export/sessions.json'))
decisions = json.load(open('../PRDs/product/crmbuilder-v2/db-export/decisions.json'))
planning_items = json.load(open('../PRDs/product/crmbuilder-v2/db-export/planning_items.json'))
references = json.load(open('../PRDs/product/crmbuilder-v2/db-export/references.json'))
print(f'Pre-apply heads:')
print(f'  Sessions:    max={sorted(s[\"identifier\"] for s in sessions)[-1]}, count={len(sessions)}')
print(f'  Decisions:   max={sorted(d[\"identifier\"] for d in decisions)[-1]}, count={len(decisions)}')
print(f'  PIs:         max={sorted(p[\"identifier\"] for p in planning_items)[-1]}, count={len(planning_items)}')
print(f'  References:  count={len(references)}')
"
```

---

## Apply

```bash
# Single apply invocation against the CRMBUILDER engagement.
# The apply script POSTs records in the standard fixed order:
# session -> decisions -> planning_items -> references.
python3 scripts/apply_close_out.py \
    --engagement CRMBUILDER \
    --payload ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_075.json

# Expected OK counts (the apply script reports these in summary form):
# - 1 session OK (SES-075)
# - 6 decisions OK (DEC-238..DEC-243)
# - 1 planning_item OK (PI-051)
# - 8 references OK (6 decided_in + 2 is_about)
```

If the apply script reports any non-OK record beyond an acceptable SKIP (HTTP 409, record already present from an earlier run), pause and investigate. Common causes: identifier collision with a parallel-sandbox claim (re-key the offending record after coordination), or API-side schema mismatch (the v0.8 payload format introduced in SES-074 added fields the v0.7 API may not yet support — but SES-075 uses the four-section v0.7 shape, so this should not apply).

---

## Post-apply verification

```bash
# 1. Identifier-head advancement
python3 -c "
import json
sessions = json.load(open('../PRDs/product/crmbuilder-v2/db-export/sessions.json'))
decisions = json.load(open('../PRDs/product/crmbuilder-v2/db-export/decisions.json'))
planning_items = json.load(open('../PRDs/product/crmbuilder-v2/db-export/planning_items.json'))
references = json.load(open('../PRDs/product/crmbuilder-v2/db-export/references.json'))
print(f'Post-apply heads:')
print(f'  Sessions:    max={sorted(s[\"identifier\"] for s in sessions)[-1]} (expect SES-075)')
print(f'  Decisions:   max={sorted(d[\"identifier\"] for d in decisions)[-1]} (expect DEC-243 or higher)')
print(f'  PIs:         max={sorted(p[\"identifier\"] for p in planning_items)[-1]} (expect PI-051 or higher)')
print(f'  References:  count={len(references)} (expect +8 from pre-apply)')
"

# 2. Spot-check the session record
python3 -c "
import json
sessions = json.load(open('../PRDs/product/crmbuilder-v2/db-export/sessions.json'))
ses = next((s for s in sessions if s['identifier'] == 'SES-075'), None)
if ses:
    print(f'SES-075 present. Title (first 100 chars): {ses[\"title\"][:100]}')
    print(f'Status: {ses[\"status\"]}')
else:
    print('SES-075 MISSING — apply failed')
"

# 3. Spot-check one decision record
python3 -c "
import json
decisions = json.load(open('../PRDs/product/crmbuilder-v2/db-export/decisions.json'))
dec = next((d for d in decisions if d['identifier'] == 'DEC-243'), None)
if dec:
    print(f'DEC-243 present. Title (first 100 chars): {dec[\"title\"][:100]}')
    print(f'Status: {dec[\"status\"]}')
else:
    print('DEC-243 MISSING — apply failed')
"

# 4. Spot-check decided_in reference resolution
python3 -c "
import json
references = json.load(open('../PRDs/product/crmbuilder-v2/db-export/references.json'))
matching = [
    r for r in references
    if r.get('source_id') == 'DEC-243'
    and r.get('target_id') == 'SES-075'
    and r.get('relationship') == 'decided_in'
]
print(f'DEC-243 decided_in SES-075: {len(matching)} reference(s) (expect 1)')
"

# 5. Spot-check is_about reference resolution
python3 -c "
import json
references = json.load(open('../PRDs/product/crmbuilder-v2/db-export/references.json'))
matching = [
    r for r in references
    if r.get('source_id') == 'SES-075'
    and r.get('target_id') == 'PI-051'
    and r.get('relationship') == 'is_about'
]
print(f'SES-075 is_about PI-051: {len(matching)} reference(s) (expect 1)')
"
```

---

## Commit snapshot regeneration

The `apply_close_out.py` script transactionally regenerates `PRDs/product/crmbuilder-v2/db-export/` JSON snapshots after every API write via the `_refresh_snapshot` hook in `crmbuilder-v2/src/crmbuilder_v2/access/engagement.py`. The `change_log.json` audit row captures the before/after payloads. Commit both the table snapshots and `change_log.json` in a single commit:

```bash
cd ..  # back to repo root
git add PRDs/product/crmbuilder-v2/db-export/
git commit -m "v2: SES-075 close-out applied — audit-v1.2 prompt-series authoring (6 decisions, 1 planning item)

Applies close-out-payloads/ses_075.json:
- 1 session (SES-075)
- 6 decisions (DEC-238..DEC-243)
- 1 planning_item (PI-051)
- 8 references (6 decided_in + 2 is_about)

Decisions span the audit-v1.2 series kickoff resolutions:
- DEC-238 natural-form scope_access keys (Prompt B)
- DEC-239 audit_log removed from \u00a712.4 (Prompt D)
- DEC-240 three EspoCRM-only PATCH permissions preserved (Prompt D)
- DEC-241 role_manager pre-flight server-state validation (Prompt E)
- DEC-242 deploy ordering security-LAST, schema \u00a712.6 corrected (Prompt G)
- DEC-243 \u00a712.5 NOT_SUPPORTED on EspoCRM 9.x, deferred to v1.4 (Prompt G; merges originally-separate DEC-6 and DEC-7 per Doug's call at close-out)

PI-051 tracks the v1.4 deferred work scope (\u00a712.5 role-aware visibility deploy
implementation alongside \u00a712.7 field-level permissions)."

# Per repo CLAUDE.md: apply prompts' snapshot git commit in Claude Code does NOT push.
# Doug pushes on normal cadence.
```

---

## Done

When the apply, verification, and snapshot commit are complete, reply with:

- Heads before and after (sessions, decisions, PIs, references counts)
- Apply script OK / SKIP / FAIL counts (expect 1/0/0 for sessions, 6/0/0 for decisions, 1/0/0 for PIs, 8/0/0 for references)
- Snapshot commit SHA
- Path to next-conversation kickoff (if any). For SES-075 there is no successor conversation queued — PI-051 enters backlog and the audit-v1.2 series is complete.

After this apply lands, the audit-v1.2 workstream is fully closed:
- All eleven prompts authored (sandbox commits on origin) and implemented (Doug's Claude Code commits on origin or pending push)
- Governance captured in V2 engagement (this apply)
- v1.4 deferred work tracked as PI-051 for future workstream pickup
