# CLAUDE-CODE-PROMPT — Apply SES-067 close-out payload

**Last Updated:** 05-24-26 10:45
**Purpose:** Apply the SES-067 close-out payload — the ARCHITECTURE-mode planning conversation that settled four PI-029 slice B build-planning decisions (DEC-211 derived endpoint scope ships only `/conversations/{id}/commits` and defers the two-hop workstream variant; DEC-212 PATCH updatability — every commit field except the identity pair is updatable for administrative correction; DEC-213 by-sha endpoint specifics — minimum prefix length 4, uppercase input lowercased before query, ambiguous-prefix 409 response uses 'candidates' field with full 40-char SHAs; DEC-214 list endpoint default sort `commit_committed_at` descending matching the UI, sortable column set locked to a known-safe subset, `?sort` and `?order` per V2 list convention) and authored the slice B Claude Code prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-029-B-commit-access-layer-and-rest.md`.

**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_067.json`

**Predecessor session:** SES-066 (PI-026 historical-applies-as-deposit-events backfill planning, applied via `CLAUDE-CODE-PROMPT-apply-close-out-ses-066.md`). Its close-out must be applied before this prompt runs — DEC-210 must be present from that apply. If `curl -sf http://127.0.0.1:8765/decisions/DEC-210` returns 404, apply the SES-066 close-out first and return here. Note: between SES-066's apply and this prompt, the PI-026 backfill prompt may or may not have run; either order works for this prompt's correctness (the apply script auto-creates one deposit_event per apply against the current DEP head regardless).

**Successor prompt:** After this apply lands, Doug runs the slice B Claude Code prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-029-B-commit-access-layer-and-rest.md` from his terminal via Claude Code. The slice B prompt builds the commit access-layer repository, REST endpoints, Pydantic schemas, router registration, derived endpoint on the conversations router, and full test coverage. After slice B completes, PI-030 (apply_close_out.py integration for the commits close-out payload section) is the natural next kickoff conversation.

---

## Scope

Apply `close-out-payloads/ses_067.json` using the existing `crmbuilder-v2/scripts/apply_close_out.py` script. The payload contains:

- 1 session record (SES-067)
- 4 decisions (DEC-211 through DEC-214)
- 0 planning items
- 5 references (4 `decided_in` linking each decision to SES-067, plus 1 `is_about` from SES-067 to PI-029)

The payload is idempotent on re-run; HTTP 409 SKIPs are treated as already-present.

This payload does NOT author any commit records, close_out_payload records, deposit_event records, or commits-related reference edges — none of those entity types yet have functioning REST endpoints (slice B builds the commits endpoints; the deposit_event lazy-created at apply close is from the existing v0.7 governance entity machinery, not new code). The session record's `artifacts_produced` and `in_flight_at_end` fields note this explicitly.

---

## Pre-flight

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

# Confirm clean working tree
git status

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start the API:
#   uv run crmbuilder-v2-api &

# Pull latest commits from origin/main (SES-067 payload, this apply
# prompt, and the slice B Claude Code prompt were pushed from the
# planning sandbox)
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# Verify the payload file exists
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_067.json

# Verify the slice B Claude Code prompt also exists (same sandbox push)
ls -la ../PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-029-B-commit-access-layer-and-rest.md

# Verify the API is routed to the CRMBUILDER engagement (the dogfood DB, not CBM)
curl -s http://127.0.0.1:8765/sessions \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), 'sessions - latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
# Expect: at least 66 sessions, latest SES-066. After this apply, expect 67 sessions, latest SES-067.

# Verify SES-066 has been applied (the immediate predecessor)
curl -sf http://127.0.0.1:8765/sessions/SES-066 | head -5
# If this returns 404, the SES-066 close-out has not been applied.
# Apply it first via
#   PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-066.md
# then return to this prompt.

# Verify DEC-210 has been applied (the latest decision from SES-066)
curl -sf http://127.0.0.1:8765/decisions/DEC-210 | head -5
# If 404, SES-066's apply has not landed cleanly.

# Capture pre-apply identifier heads for post-apply verification
echo "=== Pre-apply heads ==="
echo "Sessions:"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Decisions:"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Planning items:"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Close-out payloads (expect COP-066 from SES-066's lazy-create, or COP-032 if PI-026 backfill landed without further real-time applies — the highest matters, not the count):"
curl -s http://127.0.0.1:8765/close-out-payloads | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['close_out_payload_identifier'] for r in d)[-1] if d else 'none')"
echo "Deposit events (expect DEP-019 from SES-066's lazy-create, or DEP-043 if PI-026 backfill landed, or higher if other applies intervened):"
curl -s http://127.0.0.1:8765/deposit-events | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['deposit_event_identifier'] for r in d)[-1] if d else 'none')"
echo "References (count):"
curl -s 'http://127.0.0.1:8765/references?limit=4000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
```

Expected pre-apply heads (after SES-066 has been applied):
- Sessions: SES-066
- Decisions: DEC-210
- Planning items: PI-045 (unchanged from PI-029 slice B's authoring)
- Close-out payloads: COP-066 (or higher if PI-026 backfill landed COP-009..COP-032 — those gap-fill, so the head by lexicographic sort stays at COP-066)
- Deposit events: DEP-019 (if PI-026 backfill has not yet run) OR DEP-043 (if PI-026 backfill has run) OR higher if other applies intervened — the apply script auto-creates the next-after-head DEP regardless

Reference count varies; capture for delta verification.

---

## Apply

Run the apply script against the payload:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_067.json
```

Expected output structure:

- 1 session OK (SES-067)
- 4 decisions OK (DEC-211 through DEC-214)
- 0 planning items
- 5 references OK (4 decided_in + 1 is_about)
- 1 deposit_event written at apply close (auto-allocated next-after-head identifier, against a lazy-created COP-067)

If any record returns 409 SKIP on first run, halt and investigate — first run should have zero SKIPs. On re-run, every record should SKIP idempotently.

Note: the apply script lazy-creates COP-067 (the close_out_payload for SES-067 itself) and writes a deposit_event. The DEP head advances by one; the COP head advances from its current value to COP-067 (which becomes the new head since COP-067 > COP-066 lexicographically).

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Sessions (expect SES-067):"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Decisions (expect DEC-214):"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Planning items (expect PI-045 — unchanged):"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Close-out payloads (expect COP-067 lazy-created):"
curl -s http://127.0.0.1:8765/close-out-payloads | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['close_out_payload_identifier'] for r in d)[-1])"
echo "Deposit events (expect next-after-pre-apply lazy-created):"
curl -s http://127.0.0.1:8765/deposit-events | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['deposit_event_identifier'] for r in d)[-1])"

# Spot check SES-067
curl -s http://127.0.0.1:8765/sessions/SES-067 | python3 -m json.tool | head -20

# Spot check DEC-211 (the stop-the-flow derived-endpoint-scope decision)
curl -s http://127.0.0.1:8765/decisions/DEC-211 | python3 -m json.tool | head -20

# Spot check DEC-214 (the latest decision)
curl -s http://127.0.0.1:8765/decisions/DEC-214 | python3 -m json.tool | head -20

# Spot check a decided_in reference: find DEC-211 → SES-067 reference and confirm it resolves
# Note: response body uses field key 'relationship' (renamed from DB column 'relationship_kind'
# by the to_dict helper at access/repositories/references.py:68).
curl -s 'http://127.0.0.1:8765/references?source_type=decision&source_id=DEC-211' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(r['source_id'], '->', r['target_id'], '[', r['relationship'], ']') for r in d]"
# Expect at minimum: DEC-211 -> SES-067 [ decided_in ]

# Spot check the is_about reference from SES-067 to PI-029
curl -s 'http://127.0.0.1:8765/references?source_type=session&source_id=SES-067' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(r['source_id'], '->', r['target_id'], '[', r['relationship'], ']') for r in d]"
# Expect at minimum: SES-067 -> PI-029 [ is_about ]

# Confirm reference total delta from pre-apply
# (5 payload refs: 4 decided_in + 1 is_about) + (wrote_record edges from the deposit_event POST:
# 1 session + 4 decisions + 0 planning items + 5 references = 10) + 1 applies_close_out_payload
# edge + possibly 1 close_out_payload_produced_by_conversation edge if the apply auto-authors it
# for the lazy-created COP-067 = +16 or +17 total
echo "Reference total after apply:"
curl -s 'http://127.0.0.1:8765/references?limit=4000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
```

Expected: sessions head SES-067, decisions head DEC-214, planning_items head PI-045 (unchanged), close_out_payloads head COP-067 (lazy-created), deposit_events head advanced by 1 from pre-apply (lazy-created), reference total +16 or +17 from pre-apply.

---

## Commit snapshot regeneration

The apply script transactionally regenerates the engagement's `db-export/` JSON snapshots on every API write via the `_refresh_snapshot` hook in `crmbuilder-v2/src/crmbuilder_v2/access/engagement.py`. The `change_log.json` file also gets one audit row per write with before/after payloads. After a successful apply, commit the regenerated snapshots together:

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect what changed (should be sessions.json, decisions.json, references.json,
# close_out_payloads.json, deposit_events.json, change_log.json, plus the deposit-event log)
git status PRDs/product/crmbuilder-v2/db-export/
git status PRDs/product/crmbuilder-v2/deposit-event-logs/

# Commit the snapshot regeneration in a single commit
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "Apply SES-067 close-out: PI-029 slice B build planning complete

Records landed via apply_close_out.py against CRMBUILDER engagement:
- 1 session (SES-067)
- 4 decisions:
  - DEC-211 derived endpoint scope — ship only GET /conversations/
    {conversation_identifier}/commits, defer the two-hop
    /workstreams/{workstream_identifier}/commits variant pending
    operational evidence
  - DEC-212 PATCH updatability — every commit field except the
    identity pair (commit_identifier, commit_sha) is updatable for
    the administrative-correction path
  - DEC-213 by-sha endpoint specifics — minimum prefix length 4,
    uppercase input lowercased before query, ambiguous-prefix 409
    response uses 'candidates' field with full 40-char SHAs
  - DEC-214 list endpoint sort and order parameters — default sort
    commit_committed_at descending matching UI master pane, sortable
    column set locked to known-safe subset, ?sort and ?order per V2
    list convention
- 0 planning items
- 5 references (4 decided_in + 1 is_about session→PI-029)
- 1 close_out_payload lazy-created (COP-067)
- 1 deposit_event lazy-created (next-after-pre-apply identifier)

Slice B Claude Code prompt authored and queued for execution at
PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-029-B-
commit-access-layer-and-rest.md. The prompt installs the commit
access-layer repository (access/repositories/commits.py), REST
router (api/routers/commits.py), Pydantic schemas (additions to
api/schemas.py), router registration (main.py), the new derived
endpoint on the conversations router (DEC-211), and full test
coverage for commit.md §3.7 acceptance criteria 4-11 plus the four
DEC-211..214 specifics."

git pull --rebase origin main
git push
```

---

## Done

Reply with:

- Pre-apply heads: SES-066, DEC-210, PI-045, COP head (captured), DEP head (captured), references = N (captured)
- Post-apply heads: SES-067, DEC-214, PI-045 (unchanged), COP-067 (lazy-created), DEP head + 1 (lazy-created), references = N + 16 or +17
- Record counts (expect 1 session OK, 4 decisions OK, 0 planning items, 5 references OK, 0 SKIPs on first run, 1 lazy-created COP, 1 lazy-created DEP)
- Snapshot commit SHA from the commit-snapshot-regeneration step
- Next prompt to run: `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-029-B-commit-access-layer-and-rest.md` — the slice B Claude Code prompt that lands the commit access layer, REST endpoints, Pydantic schemas, router registration, derived endpoint on the conversations router, and full test coverage. After slice B completes, the natural next kickoff conversation is PI-030 (apply_close_out.py integration for the commits close-out payload section).
