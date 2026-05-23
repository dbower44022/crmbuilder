# CLAUDE-CODE-PROMPT — Apply SES-061 close-out payload

**Last Updated:** 05-23-26 21:00
**Purpose:** Apply the SES-061 close-out payload — the Code Change Lifecycle methodology drafting conversation that settles eight deferred design decisions (DEC-183 through DEC-190), authors `methodology-code-change-lifecycle.md` v1.0, and produces the PI-028 commit entity schema kickoff.
**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_061.json`
**Predecessor session in apply order:** SES-060 (audit-v1.2 §9 resolutions — five decisions DEC-178..182, authored in a parallel sandbox; unrelated to this conversation's workstream but landed last in the apply queue before this one). The SES-060 payload should already be applied per its own apply prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-060.md`. Three sessions must already be applied before this one in this order: SES-058 (audit feature v1.2 planning) → SES-059 (PI-024 prior-workstreams backfill planning) → SES-060 (audit-v1.2 §9 resolutions). If `curl -sf http://127.0.0.1:8765/sessions/SES-060` returns 404, apply the predecessor chain first (each has its own apply prompt in the prompts/ directory) and then return here.

---

## Net Effect

After this apply lands, the CRMBUILDER engagement database will hold the eight design decisions that drive PI-028 through PI-033 of the Code Change Lifecycle workstream. The methodology document at `PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md` v1.0 is the design authority for those downstream planning items; this apply lands the governance records that cite it. No new entity types, no new relationship_kinds, no new planning items — PI-028 through PI-033 already exist from SES-057's apply.

PI-027 stays `Open` after this apply. The methodology specifies a `resolves_planning_items` payload section that does not yet ship (PI-030's scope). PI-027 is resolved retroactively by PI-033 once the section is supported. This is intentional per methodology section 9 and DEC-184 / DEC-185's design.

---

## Scope

Apply `close-out-payloads/ses_061.json` using `crmbuilder-v2/scripts/apply_close_out.py`. The payload contains:

- 1 session record (SES-061)
- 8 decisions (DEC-183 through DEC-190)
- 0 planning items
- 11 references (8 `decided_in` linking each decision to SES-061; 2 `is_about` linking SES-061 to PI-028 and PI-027 respectively; 1 `references` linking DEC-190 to DEC-170 as the antecedent that flagged the blocks-direction question)

The payload is idempotent on re-run; HTTP 409 SKIPs are treated as already-present.

**This payload does NOT** author commit records, work_ticket records, or `resolves_planning_items` edges for the methodology document, the PI-028 kickoff, or this conversation's own commits. The close-out payload format does not yet support those sections — extending it is part of the workstream this conversation's methodology defines (PI-030's scope). All three artifacts (methodology document, PI-028 kickoff, this payload file plus its apply prompt) are committed as markdown/JSON in the same sandbox push that contains this payload, and will be back-filled as work_ticket / commit / resolves records via PI-033 after PI-030 ships.

---

## Pre-flight

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

# Clean status check
cd .. && git status --porcelain
# Expect clean. If anything is staged or modified, halt and resolve before continuing.
cd crmbuilder-v2

# Git identity
git config user.email
git config user.name
# Expect doug@dougbower.com and Doug Bower

# Pull latest commits from origin/main (SES-061 payload was pushed from the methodology drafting sandbox)
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start the API:
#   uv run crmbuilder-v2-api &

# Verify the payload file exists
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_061.json

# Verify the methodology document and the PI-028 kickoff exist (both pushed in the same sandbox commit)
ls -la ../PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md
ls -la ../PRDs/product/crmbuilder-v2/schema-design-kickoff-commit.md

# Verify the API is routed to the CRMBUILDER engagement (the dogfood DB, not CBM)
# Look for the latest session to be SES-060 (the audit-v1.2 §9 resolutions payload, already applied)
curl -s http://127.0.0.1:8765/sessions \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), 'sessions - latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"

# Verify SES-060 has been applied (the predecessor in apply order — audit-v1.2 §9 resolutions)
curl -sf http://127.0.0.1:8765/sessions/SES-060 | head -5
# If this returns 404, the predecessor chain has not been fully applied. Apply in order via:
#   PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-058.md (audit feature v1.2)
#   PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-059.md (PI-024 backfill)
#   PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-060.md (audit-v1.2 resolutions)
# Return to this prompt after SES-060 lands.

# Capture pre-apply identifier heads for post-apply verification
echo "=== Pre-apply heads ==="
echo "Sessions:"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Decisions:"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Planning items:"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "References (count):"
curl -s 'http://127.0.0.1:8765/references?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
```

Expected pre-apply heads: SES-060, DEC-182, PI-044. Reference count will vary; capture for delta verification.

---

## Apply

Run the apply script against the payload:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_061.json
```

Expected output structure:

- 1 session OK (SES-061)
- 8 decisions OK (DEC-183 through DEC-190)
- 0 planning items (none in this payload)
- 11 references OK
- 1 deposit_event written at apply close

If any record returns 409 SKIP on first run, halt and investigate — first run should have zero SKIPs. On re-run, every record should SKIP idempotently.

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Sessions (expect SES-061):"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Decisions (expect DEC-190):"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Planning items (expect PI-044, unchanged from pre-apply):"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"

# Reference count delta — expect +11
echo "References after apply:"
curl -s 'http://127.0.0.1:8765/references?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"

# Spot check SES-061
curl -s http://127.0.0.1:8765/sessions/SES-061 | python3 -m json.tool | head -25

# Spot check DEC-183 (the first new decision — commit identifier strategy)
curl -s http://127.0.0.1:8765/decisions/DEC-183 | python3 -m json.tool | head -20

# Spot check DEC-190 (the last new decision — blocks → blocked_by rename)
curl -s http://127.0.0.1:8765/decisions/DEC-190 | python3 -m json.tool | head -20

# Spot check the cross-decision reference (DEC-190 references DEC-170)
curl -s 'http://127.0.0.1:8765/references?source_type=decision&source_id=DEC-190' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(r['source_id'], '->', r['target_id'], '[', r['relationship'], ']') for r in d]"
# Expect at minimum two rows:
#   DEC-190 -> SES-061 [ decided_in ]
#   DEC-190 -> DEC-170 [ references ]

# Spot check PI-027 status (expect Open — methodology adopts deferred-resolution posture)
curl -s http://127.0.0.1:8765/planning-items/PI-027 \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('PI-027 status:', d['status'])"
# Expect: Open
# (PI-027 stays Open intentionally; the resolves_planning_items payload section that would
#  resolve it does not yet ship. PI-033 retroactive resolve handles it.)

# Confirm decision count
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('total decisions:', len(d))"
# Expect 190 (was 182 before this apply; was 177 before SES-060; was 174 before SES-059; was 170 before SES-058).
```

---

## Commit snapshot regeneration

The apply script transactionally regenerates the engagement's db-export JSON snapshots on every API write via the `_refresh_snapshot` hook in `crmbuilder-v2/src/crmbuilder_v2/access/engagement.py`. The `change_log.json` file also gets one audit row per write with before/after payloads. After a successful apply, commit the regenerated snapshots together with the deposit-event log:

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect what changed (should be sessions, decisions, references, deposit_events, change_log, plus deposit-event log)
git status PRDs/product/crmbuilder-v2/db-export/
git status PRDs/product/crmbuilder-v2/deposit-event-logs/

# Commit the snapshot regeneration in a single commit
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "Apply SES-061 close-out: Code Change Lifecycle methodology drafted

Records landed via apply_close_out.py against CRMBUILDER engagement:
- 1 session (SES-061)
- 8 decisions (DEC-183 commit identifier CM-NNNN with /by-sha lookup;
  DEC-184 per-conversation resolves edge; DEC-185 payload-declared
  helper-enumerated commit ingestion; DEC-186 v0.8 commit fields with
  parent_shas JSON array; DEC-187 conversation-scoped commits;
  DEC-188 typed addresses kind for (work_ticket, planning_item) and
  (conversation, planning_item); DEC-189 broad work_ticket authoring
  rule; DEC-190 rename blocks to blocked_by)
- 0 planning items
- 11 references (8 decided_in, 2 is_about to PI-028 and PI-027,
  1 references from DEC-190 to DEC-170)
- 1 deposit_event

PI-027 stays Open per methodology section 9 — the resolves_planning_items
payload section the methodology specifies does not yet ship. PI-033
retroactive resolve handles it once PI-030 lands."

git pull --rebase origin main
git push
```

---

## Done

Reply with:

- **Pre-apply heads:** SES-060, DEC-182, PI-044, references = N (captured)
- **Post-apply heads:** SES-061, DEC-190, PI-044 (unchanged — no new PIs), references = N + 11
- **Record counts:** expect 1 session OK, 8 decisions OK, 0 planning items, 11 references OK, 0 SKIPs on first run
- **Snapshot commit SHA** from the commit-snapshot-regeneration step
- **PI-027 status:** confirm `Open` (intentional per methodology section 9)
- **Next-conversation kickoff path:** `PRDs/product/crmbuilder-v2/schema-design-kickoff-commit.md` — open a new Claude.ai conversation against that kickoff to begin PI-028 (the commit entity schema-design conversation)
