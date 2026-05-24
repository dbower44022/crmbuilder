# CLAUDE-CODE-PROMPT — Apply SES-072 close-out payload

**Last Updated:** 05-24-26 18:15
**Purpose:** Apply the SES-072 close-out payload — the retrospective combined close-out for the PI-045 code-changes implementation conversation, capturing slices A (transport flag + FastMCP HTTP binding), B (X-CRMBuilder-Secret middleware), and C (engagement-marker fail-loud guard per DEC-205) as a single session record per option 1 elected during the operational conversation. Lands SES-072 with no decisions, no planning items, and one `is_about` reference to PI-045. The slice code commits themselves live in Doug's local clone and reach origin on Doug's normal push cadence; this close-out is independent of where those commits are on the remote.

**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_072.json`
**Predecessors:** SES-071 must have landed (commit 350b044, applied per its apply prompt earlier today). PI-045 must exist as a planning item (it has since SES-064). The three slice prompts (`CLAUDE-CODE-PROMPT-pi-045-{A,B,C}-*.md`) exist in `PRDs/product/crmbuilder-v2/prompts/` and the slice work has completed at Doug's terminal — no dependency on those code commits being on origin for THIS close-out's apply.
**Successor:** PI-045 step-5 operational conversation. Slice C's prompt named the path under `PRDs/product/crmbuilder-v2/` where the step-5 kickoff 'should land' but slice C did not itself author it; that kickoff is a still-to-be-authored Claude.ai deliverable. Suggested filename: `pi-045-step-5-claude-ai-mcp-integration-registration-kickoff.md` or similar — final naming is the next conversation's call.

---

## Scope

Apply `close-out-payloads/ses_072.json` using the existing `crmbuilder-v2/scripts/apply_close_out.py` script. The payload contains:

- 1 session record (SES-072)
- 0 decisions
- 0 planning items
- 1 reference:
    * `session:SES-072 -[is_about]-> planning_item:PI-045`

This is the thinnest viable close-out — the code-changes conversation produced no new architectural decisions (all three slices implemented behavior settled in SES-065 and DEC-205), no new planning items, and just the standard session-to-planning-item edge. The session record itself carries the operational substance via `topics_covered` and `artifacts_produced`.

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
git config user.email
# Expect: doug@dougbower.com

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start the API:
#   uv run crmbuilder-v2-api &

# Verify the payload file exists
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_072.json

# Verify the API is routed to the CRMBUILDER engagement
curl -s http://127.0.0.1:8765/sessions \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), 'sessions - latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
# Expect at minimum SES-071 (PI-045 operational steps 1–4 landed at commit 350b044).

# Verify PI-045 is present (target of the is_about edge)
curl -sf http://127.0.0.1:8765/planning-items/PI-045 >/dev/null && echo "PI-045 OK (target of is_about edge)" || echo "PI-045 MISSING — apply SES-064 first"

# Capture pre-apply heads
echo "=== Pre-apply heads ==="
for endpoint in sessions decisions planning-items; do
  echo "$endpoint:"
  curl -s "http://127.0.0.1:8765/$endpoint" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
done
echo "Close-out payloads:"
curl -s http://127.0.0.1:8765/close-out-payloads | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['close_out_payload_identifier'] for r in d)[-1] if d else 'none')"
echo "Deposit events:"
curl -s http://127.0.0.1:8765/deposit-events | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['deposit_event_identifier'] for r in d)[-1] if d else 'none')"
echo "References (count):"
curl -s 'http://127.0.0.1:8765/references?limit=4000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', len(d))"
```

Expected pre-apply state (assuming SES-071 has landed and nothing else has applied since): sessions head SES-071, decisions head DEC-225, planning-items head PI-048, COP head COP-071, DEP head DEP-050, references ≈ 851. If a later parallel-sandbox commit has advanced heads further, that's fine — this apply produces SES-072 regardless.

---

## Apply

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_072.json
```

Expected output structure:

- 1 session OK (SES-072)
- 0 decisions
- 0 planning items
- 1 reference OK (`session:SES-072 -[is_about]-> planning_item:PI-045`)
- 1 close_out_payload lazy-created (COP-072 — derived from filename `ses_072.json`)
- 1 deposit_event written at apply close (lazy-created — DEP identifier depends on current head; expect DEP-051 if no parallel applies have intervened)

If any record returns 409 SKIP on first run, halt and investigate — first run should have zero SKIPs. On re-run, every record should SKIP idempotently.

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Sessions (expect SES-072):"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Decisions (expect DEC-225 unchanged):"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Planning items (expect PI-048 unchanged):"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Close-out payloads (expect COP-072 lazy-created):"
curl -s http://127.0.0.1:8765/close-out-payloads | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['close_out_payload_identifier'] for r in d)[-1])"
echo "Deposit events (expect DEP head + 1 lazy-created):"
curl -s http://127.0.0.1:8765/deposit-events | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['deposit_event_identifier'] for r in d)[-1])"

# Spot-check SES-072
curl -s http://127.0.0.1:8765/sessions/SES-072 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:100]); print('  status:', d['status'])"

# Confirm the is_about edge landed (NB: API field is 'relationship', not 'relationship_kind')
curl -s 'http://127.0.0.1:8765/references?source_type=session&source_id=SES-072' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(' ', r['source_id'], '->', r['target_id'], '[', r['relationship'], ']') for r in d]"
# Expect:
#   SES-072 -> PI-045 [ is_about ]

# Reference total delta
echo ""
echo "Reference total after apply:"
curl -s 'http://127.0.0.1:8765/references?limit=4000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
# Expected delta: +3 or +4 from pre-apply
#   1 from payload (is_about)
#   1 wrote_record edge from the apply script's lazy-created DEP (1 session record)
#   1 deposit_event_applies_close_out_payload from the lazy DEP to the lazy COP-072
#   (possibly 1 close_out_payload_produced_by_conversation edge for the lazy COP-072)
```

Expected post-apply heads: SES-072, DEC-225 unchanged, PI-048 unchanged, COP-072 (lazy), DEP head + 1 (lazy). Reference total +3 or +4.

---

## Commit snapshot regeneration

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect changed snapshot files
git status PRDs/product/crmbuilder-v2/db-export/
git status PRDs/product/crmbuilder-v2/deposit-event-logs/

# Commit
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "Apply SES-072 close-out: PI-045 code-changes implementation (slices A, B, C combined)

Records landed via apply_close_out.py against the CRMBUILDER engagement:
- 1 session (SES-072 — PI-045 code-changes implementation conversation
  combined close-out covering slices A, B, C: --transport flag + FastMCP
  HTTP binding to 127.0.0.1:8810; X-CRMBuilder-Secret header middleware
  with hmac.compare_digest validation and startup hard-fail on
  missing-secret; engagement-marker fail-loud guard on REST API per
  DEC-205 with HTTP 409 + structured body + WARNING log on drift,
  exempt paths /health /openapi.json /docs /redoc; all three slices
  verified end-to-end against the live tunnel and API)
- 0 decisions (everything in the three slices implemented behavior
  settled in SES-065 and DEC-205; no new architectural decisions)
- 0 planning items
- 1 payload reference:
  * session:SES-072 -[is_about]-> planning_item:PI-045
- 1 close_out_payload lazy-created (COP-072)
- 1 deposit_event lazy-created (DEP head + 1)

Slice code commits in Doug's local clone (pushed to origin on normal
cadence): slice A at 95b801a2, slice B at 209a3dc9, slice C at
ea04e1a6 with follow-ups c578503b (_UNINITIALIZED sentinel) and
a9cfe138 (api/main.py adjustments). Test count at HEAD ae7a77ea:
1489 v2 tests collect.

Per option 1 elected during the SES-071 operational conversation —
single combined close-out at the end of slice C captures all three
slices at session granularity, symmetric with SES-071 capturing
PI-045 operational steps 1–4 as a single record.

PI-045 code-changes scope is structurally complete. Step 5 of
PI-045 (claude.ai MCP integration registration with the three
custom headers X-CRMBuilder-Secret, CF-Access-Client-Id,
CF-Access-Client-Secret) is now unblocked; the step-5 kickoff
prompt is still to-be-authored under PRDs/product/crmbuilder-v2/.

Pre-step-5 hygiene: rotate the claude-ai-mcp Service Token's
Client Secret per SES-071's in_flight_at_end — the value appeared
in transcript during a doubled-header diagnostic; blast radius is
now becoming non-zero because slice B's middleware is in place and
the MCP HTTP transport is buildable."

git pull --rebase origin main
git push
```

---

## Done

Reply with:

- Pre-apply heads: actual (sessions / decisions / planning_items / COP / DEP heads + references count)
- Post-apply heads: SES-072, DEC-225 unchanged, PI-048 unchanged, COP-072 (lazy), DEP head + 1 (lazy), references = pre + 3 or 4
- Record counts: 1 session OK, 0 decisions, 0 planning items, 1 reference OK, 0 SKIPs, 1 lazy COP-072, 1 lazy DEP
- The is_about edge confirmed via `curl -s 'http://127.0.0.1:8765/references?source_type=session&source_id=SES-072'` (using `r['relationship']` field key, not `r['relationship_kind']`)
- Snapshot commit SHA
- Next: author the PI-045 step-5 kickoff under `PRDs/product/crmbuilder-v2/` (Claude.ai deliverable, fresh conversation), then open the step-5 operational conversation against it. After step 5 lands, the smoke-test conversation runs the 44-MCP-tool surface end-to-end against both engagements and ships the part-(d) documentation deliverables to advance PI-045 status from In Progress to Complete.
