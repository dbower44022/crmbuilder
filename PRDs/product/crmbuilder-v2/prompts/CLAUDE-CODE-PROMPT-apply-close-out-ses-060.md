# CLAUDE-CODE-PROMPT — Apply SES-060 close-out payload

**Last Updated:** 05-23-26 04:00
**Purpose:** Apply the SES-060 close-out payload — the audit-v1.2 planning resolution conversation that formalized the four §9 open questions from audit-v1.2-planning.md v1.0 plus the security.yaml file-placement question, capturing five design decisions (DEC-178 through DEC-182) and bumping the planning document to v1.3 (commits 315801b, c9ebcda, and pending v1.3 on origin/main).
**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_060.json`
**Predecessor sessions:** SES-058 (audit-v1.2 workstream established) AND SES-059 (PI-024 prior-workstreams backfill planned). Both must already be applied — SES-058 per its apply prompt at `prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-058.md`, SES-059 per its apply prompt at `prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-059.md`. If `curl -sf http://127.0.0.1:8765/sessions/SES-059` returns 404, apply SES-059's close-out (and SES-058's if also pending) first and then return here.

**Identifier-rebase context.** This conversation originally allocated SES-059 and DEC-175 through DEC-179 against the engagement's db-export snapshot, which showed SES-057 as head and SES-058's payload as pending apply. The PI-024 prior-workstreams backfill conversation ran concurrently and pushed its own SES-059 close-out (commit 44182d1) first, taking SES-059 / DEC-175..177. This conversation's records were rebased to SES-060 / DEC-178..182. The lost ses_059.json content was re-authored verbatim at ses_060.json with identifier shifts only — no design content change.

---

## Scope

Apply `close-out-payloads/ses_060.json` using the existing `crmbuilder-v2/scripts/apply_close_out.py` script. The payload contains:

- 1 session record (SES-060)
- 5 decisions (DEC-178 through DEC-182)
- 0 planning items (existing PI-034 through PI-044 from SES-058 remain valid; this session's resolutions refine the design that those PIs implement)
- 5 references (5 `decided_in` linking each decision to SES-060)

Net effect on the CRMBUILDER engagement database after apply:

- Sessions head advances from SES-059 to SES-060
- Decisions head advances from DEC-177 to DEC-182
- Planning items head unchanged at PI-044 (no new PIs)
- Total reference count increases by 5
- One deposit_event written at apply close per the v0.7 governance convention

The payload is idempotent on re-run; HTTP 409 SKIPs are treated as already-present. On first run, every record should return OK; if any record returns 409 SKIP on first run, halt and investigate.

This payload does NOT author the planning document revisions (v1.1 commit 315801b, v1.2 commit c9ebcda, v1.3 pending) as reference_book records or commit records — the close-out payload format does not yet support those sections (extension is part of PI-030 in the Code Change Lifecycle workstream from SES-057). The planning document lives at `PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md` and will be back-filled when PI-030 ships.

---

## Pre-flight

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

# Working tree clean
git status --porcelain
# Expected: empty output

# Git identity
git config user.name
git config user.email
# Expected: Doug / doug@dougbower.com

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start the API:
#   uv run crmbuilder-v2-api &

# Pull latest commits from origin/main (SES-060 payload and planning doc v1.1/v1.2/v1.3 were pushed from the sandbox)
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# Verify the payload file exists
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_060.json

# Verify the planning document is at v1.3 (the head 'Version:' line should read 1.3)
head -10 ../PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md | grep '^**Version:**'
# Expected: **Version:** 1.3 (identifier rebase — SES-060 / DEC-178..182)

# Verify the API is routed to the CRMBUILDER engagement (the dogfood DB, not CBM)
curl -s http://127.0.0.1:8765/sessions \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), 'sessions - latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
# Expect 59 sessions, latest SES-059. After this apply, expect 60 sessions, latest SES-060.

# Verify both predecessors have been applied (SES-058 audit-v1.2 workstream, SES-059 PI-024 backfill)
curl -sf http://127.0.0.1:8765/sessions/SES-058 | head -5
curl -sf http://127.0.0.1:8765/sessions/SES-059 | head -5
# If either returns 404, apply its close-out first:
#   SES-058 → PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-058.md
#   SES-059 → PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-059.md
# Return to this prompt after both land.

# Capture pre-apply identifier heads for post-apply verification
echo "=== Pre-apply heads ==="
echo "Sessions:"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Decisions:"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Planning items:"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "References (count, since these are auto-identified):"
curl -s 'http://127.0.0.1:8765/references?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
```

Expected pre-apply heads: SES-059, DEC-177, PI-044. Reference count will vary; capture for delta verification (should increase by exactly 5 after apply).

---

## Apply

Run the apply script against the payload:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_060.json
```

Expected output structure:

- 1 session OK (SES-060)
- 5 decisions OK (DEC-178, DEC-179, DEC-180, DEC-181, DEC-182)
- 0 planning items (empty array)
- 5 references OK (5 decided_in)
- 1 deposit_event written at apply close

If any record returns 409 SKIP on first run, halt and investigate — first run should have zero SKIPs. On re-run, every record should SKIP idempotently.

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Sessions (expect SES-060):"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Decisions (expect DEC-182):"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Planning items (expect PI-044 unchanged):"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"

# Reference count delta (expect exactly +5 vs the pre-apply count)
echo "References (post-apply count):"
curl -s 'http://127.0.0.1:8765/references?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"

# Spot check SES-060
curl -s http://127.0.0.1:8765/sessions/SES-060 | python3 -m json.tool | head -20

# Spot check DEC-180 (the default-True revision of v1.0's provisional default-False — the most behaviorally consequential decision in this set)
curl -s http://127.0.0.1:8765/decisions/DEC-180 | python3 -m json.tool | head -20

# Spot check DEC-182 (the security.yaml placement decision — affects Prompt A loader scan)
curl -s http://127.0.0.1:8765/decisions/DEC-182 | python3 -m json.tool | head -20

# Spot check a decided_in reference: find DEC-180 references and confirm one resolves to SES-060 with relationship decided_in
curl -s 'http://127.0.0.1:8765/references?source_type=decision&source_id=DEC-180' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(r['source_id'], '->', r['target_id'], '[', r['relationship'], ']') for r in d]"
# Expect at minimum: DEC-180 -> SES-060 [ decided_in ]

# Spot check the decided_in references for SES-060: all 5 should appear
curl -s 'http://127.0.0.1:8765/references?target_type=session&target_id=SES-060&relationship=decided_in' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(f'Found {len(d)} decided_in references targeting SES-060'); [print(' ', r['source_id'], '->', r['target_id']) for r in d]"
# Expect 5 references, one per DEC-178 through DEC-182
```

---

## Commit snapshot regeneration

The apply script transactionally regenerates the engagement's `db-export/` JSON snapshots after the apply succeeds (per the `_refresh_snapshot` hook in `crmbuilder-v2/src/crmbuilder_v2/access/engagement.py`). A row is also appended to `db-export/change_log.json` capturing before/after payloads for this apply event. Do NOT invoke any standalone exporter — none exists.

Verify the snapshots reflect the new records:

```bash
cd ~/Dropbox/Projects/crmbuilder
git status --porcelain PRDs/product/crmbuilder-v2/db-export/
# Expected: changes to sessions.json, decisions.json, references.json, change_log.json, plus the deposit_events.json and close_out_payloads.json snapshots if the v0.7 governance entity tables are wired in.
# planning_items.json should NOT change (no new PIs).

# Quick smoke test on the regenerated sessions snapshot
python3 -c "
import json
with open('PRDs/product/crmbuilder-v2/db-export/sessions.json') as f:
    data = json.load(f)
sessions = data if isinstance(data, list) else data.get('data', data.get('sessions', []))
ids = sorted([s.get('identifier','') for s in sessions if s.get('identifier','').startswith('SES-')])
print(f'Sessions in snapshot: {len(ids)}, highest: {ids[-1]}')
"
# Expect highest SES-060

# And on decisions snapshot
python3 -c "
import json
with open('PRDs/product/crmbuilder-v2/db-export/decisions.json') as f:
    data = json.load(f)
decs = data if isinstance(data, list) else data.get('data', data.get('decisions', []))
ids = sorted([x.get('identifier','') for x in decs if x.get('identifier','').startswith('DEC-')])
print(f'Decisions in snapshot: {len(ids)}, highest: {ids[-1]}')
"
# Expect highest DEC-182
```

Commit the regenerated snapshots and change_log as a single commit:

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git commit -m "Apply SES-060 close-out — audit-v1.2 planning resolutions

Lands the audit-v1.2 resolution conversation's governance records into
the CRMBUILDER engagement database: SES-060 session record, five
decisions (DEC-178 persona is documentation metadata only, DEC-179
empty scope_access produces informational audit-log warning, DEC-180
include_security and include_filtered_tabs default True revising v1.0's
provisional default False, DEC-181 overwrite existing audit output with
pre-run confirmation guard, DEC-182 security.yaml lives in a security/
subdirectory of the program directory), and five references
(decided_in linking each decision to SES-060).

Rebased from SES-059 to SES-060 to clear collision with the PI-024
prior-workstreams backfill conversation's SES-059 close-out (commit
44182d1). No design content change in the rebase — only identifier
shifts.

No new planning items — existing PI-034 through PI-044 from SES-058
remain valid, refined by these decisions.

Snapshot regeneration committed alongside the apply per the
_refresh_snapshot hook convention; change_log.json captures the
apply event payload."

git push origin main
```

---

## Done

Report back to Doug with:

- Pre-apply heads (SES, DEC, PI) and post-apply heads (expect SES-060, DEC-182, PI-044 unchanged)
- Record counts from the apply (expect 1 session OK + 5 decisions OK + 0 planning items + 5 references OK + 1 deposit_event)
- Snapshot regeneration commit SHA
- Next-conversation kickoff: a fresh Claude.ai conversation against the planning document at `PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md` (now v1.3) to author `CLAUDE-CODE-PROMPT-audit-v1.2-A-roles-teams-recognition.md` as the PI-034 deliverable
