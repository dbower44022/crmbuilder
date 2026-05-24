# CLAUDE-CODE-PROMPT — Apply SES-071 close-out payload

**Last Updated:** 05-24-26 12:50
**Purpose:** Apply the SES-071 close-out payload — the PI-045 operational deployment conversation (part (b)) that executed operational steps 1 through 4 of PI-045's five-step operational scope (nameserver migration crmbuilder.ai GoDaddy → Cloudflare with all Google Workspace email records preserved; cloudflared installed and tunnel crmbuilder-mcp running as systemd user service routing mcp.crmbuilder.ai → 127.0.0.1:8810; Cloudflare Access two-policy split protecting the hostname with Service Auth for the claude-ai-mcp Service Token and Allow + One-time PIN for the admin browser path). Lands DEC-225 (Cloudflare Access auth model revisions: Service Token added for programmatic clients since claude.ai's MCP integration cannot follow OAuth redirects; One-time PIN replaces Google login since Cloudflare retired the built-in Google OAuth shortcut) and three supporting references (DEC-225 decided_in SES-071, SES-071 is_about PI-045, DEC-225 references DEC-204).

**Identifier rebase note:** This work was initially anticipated as SES-069 / DEC-216 per the PI-045 kickoff's identifier expectations and the operational-conversation framing in SES-065's in_flight_at_end. Three parallel-sandbox commits landed during the conversation: 1435f0a applied SES-069 with DEC-216..220 and PI-048 (PI-023 reconciliation utility planning); 232e967 committed but did not apply SES-070 with DEC-221..224 (PI-030 architecture planning); b34391f closed PI-022 governance-backfill program. Rebased to SES-071 / DEC-225 to avoid collision with both the applied SES-069 and the file-claimed-but-unapplied SES-070. This is the fifth occurrence of the parallel-sandbox identifier-rebase pattern in the recent program (prior four: SES-057→058 on Code Change Lifecycle workstream; SES-058→059 between audit-v1.2 and PI-024; SES-062→063→064 during the SES-064 conversation; SES-067→068 during PI-026's Option-I supersession). The reserve-at-apply-time identifier model (a PI-032 future) would eliminate this class of collisions; this conversation's experience is one more data point for promoting it.

**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_071.json`
**Predecessors:** SES-069 must have landed (commit 1435f0a). SES-070's apply prompt may or may not have run yet — apply order between SES-070 and SES-071 is unconstrained; both can apply in either order without collision since their identifier spaces are disjoint (SES-070 claims DEC-221..224; SES-071 claims DEC-225). DEC-204 must exist (target of the references edge) — it was landed by SES-064's apply long before this conversation. PI-045 must exist (target of the is_about edge) — it was landed by SES-064's apply alongside DEC-204.
**Successor:** The PI-045 code-changes implementation conversation runs slices A (CLAUDE-CODE-PROMPT-pi-045-A-transport-flag-and-http-binding.md), B (CLAUDE-CODE-PROMPT-pi-045-B-shared-secret-middleware.md), and C (CLAUDE-CODE-PROMPT-pi-045-C-marker-handling.md) in sequence. After all three slices land and the MCP HTTP transport is running on 127.0.0.1:8810, PI-045 step 5 (claude.ai MCP integration registration) becomes executable in a short follow-up operational conversation or as part of the smoke-test conversation.

---

## Scope

Apply `close-out-payloads/ses_071.json` using the existing `crmbuilder-v2/scripts/apply_close_out.py` script. The payload contains:

- 1 session record (SES-071)
- 1 decision (DEC-225)
- 0 planning items
- 3 references:
    * `decision:DEC-225 -[decided_in]-> session:SES-071`
    * `session:SES-071 -[is_about]-> planning_item:PI-045`
    * `decision:DEC-225 -[references]-> decision:DEC-204`

The references edge from DEC-225 to DEC-204 captures that DEC-225 revises DEC-204's auth-model framing (Service Token added, OTP replaces Google login) without superseding DEC-204's substantive decision (Cloudflare Tunnel + Cloudflare Access identity gating remains intact). DEC-204 stays at status=Active. `references` is the appropriate kind here per the vocab's same-type decision→decision usage (precedent: DEC-205 references DEC-203 in ses_065.json).

The payload is idempotent on re-run; HTTP 409 SKIPs are treated as already-present.

---

## Pre-flight

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

# Clean working tree
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
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_071.json

# Verify the API is routed to the CRMBUILDER engagement
curl -s http://127.0.0.1:8765/sessions \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), 'sessions - latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
# Expect at minimum SES-069 (PI-023 reconciliation utility planning landed at commit 1435f0a).
# If SES-070's apply (PI-030 architecture planning) has also run, expect SES-070 as the head.
# Either is fine; this apply produces SES-071 regardless.

# Verify DEC-204 is present (target of the references edge)
curl -sf http://127.0.0.1:8765/decisions/DEC-204 >/dev/null && echo "DEC-204 OK (target of references edge)" || echo "DEC-204 MISSING — apply SES-064 first"

# Verify PI-045 is present (target of the is_about edge)
curl -sf http://127.0.0.1:8765/planning-items/PI-045 >/dev/null && echo "PI-045 OK (target of is_about edge)" || echo "PI-045 MISSING — apply SES-064 first"

# Confirm there are no existing outbound references from DEC-225 (first run should have none)
curl -s 'http://127.0.0.1:8765/references?source_id=DEC-225' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(f'  Existing DEC-225 outbound refs: {len(d)} (expect 0 on first run)')"

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

Expected pre-apply state depends on whether SES-070's apply has been run:

| State | Sessions head | Decisions head | PI head | COP head | DEP head |
|---|---|---|---|---|---|
| SES-070 NOT yet applied | SES-069 | DEC-220 | PI-048 | COP-069 | DEP-048 |
| SES-070 applied | SES-070 | DEC-224 | PI-048 | COP-070 | DEP-049+ |

Either is acceptable; this apply produces SES-071 / DEC-225 either way.

---

## Apply

Run the apply script against the payload:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_071.json
```

Expected output structure:

- 1 session OK (SES-071)
- 1 decision OK (DEC-225)
- 0 planning items
- 3 references OK (decided_in, is_about, references)
- 1 close_out_payload lazy-created (COP-071 — derived from filename `ses_071.json`)
- 1 deposit_event written at apply close (lazy-created — DEP identifier depends on current head; expect DEP-049 if SES-070 unapplied, DEP-050+ if applied)

If any record returns 409 SKIP on first run, halt and investigate — first run should have zero SKIPs. On re-run, every record should SKIP idempotently.

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Sessions (expect SES-071):"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Decisions (expect DEC-225):"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Planning items (expect PI-048 unchanged):"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Close-out payloads (expect COP-071 lazy-created):"
curl -s http://127.0.0.1:8765/close-out-payloads | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['close_out_payload_identifier'] for r in d)[-1])"
echo "Deposit events (expect DEP-049 or DEP-050+ lazy-created):"
curl -s http://127.0.0.1:8765/deposit-events | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['deposit_event_identifier'] for r in d)[-1])"

# Spot-check DEC-225
curl -s http://127.0.0.1:8765/decisions/DEC-225 | python3 -m json.tool | head -10

# Spot-check SES-071
curl -s http://127.0.0.1:8765/sessions/SES-071 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:100]); print('  status:', d['status'])"

# Confirm the references edges landed
curl -s 'http://127.0.0.1:8765/references?source_type=decision&source_id=DEC-225' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(' ', r['source_id'], '->', r['target_id'], '[', r['relationship_kind'], ']') for r in d]"
# Expect at minimum:
#   DEC-225 -> SES-071 [ decided_in ]
#   DEC-225 -> DEC-204 [ references ]

curl -s 'http://127.0.0.1:8765/references?source_type=session&source_id=SES-071' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(' ', r['source_id'], '->', r['target_id'], '[', r['relationship_kind'], ']') for r in d]"
# Expect at minimum:
#   SES-071 -> PI-045 [ is_about ]

# Reference total delta
echo ""
echo "Reference total after apply:"
curl -s 'http://127.0.0.1:8765/references?limit=4000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
# Expected delta: +6 or +7 from pre-apply
#   3 from payload (decided_in, is_about, references)
#   2 wrote_record edges from the apply script's lazy-created DEP (1 session + 1 decision)
#   1 deposit_event_applies_close_out_payload from the lazy DEP to the lazy COP-071
#   (possibly 1 close_out_payload_produced_by_conversation edge for the lazy COP-071)
```

Expected post-apply heads: SES-071, DEC-225, PI-048 unchanged, COP-071 (lazy), DEP-049 or DEP-050+ (lazy). Reference total +6 or +7.

---

## Commit snapshot regeneration

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect changed snapshot files
git status PRDs/product/crmbuilder-v2/db-export/
git status PRDs/product/crmbuilder-v2/deposit-event-logs/

# Commit
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "Apply SES-071 close-out: PI-045 V2 remote-access deployment operational steps 1-4

Records landed via apply_close_out.py against the CRMBUILDER engagement:
- 1 session (SES-071 — PI-045 operational steps 1 through 4 executed:
  nameserver migration crmbuilder.ai GoDaddy → Cloudflare with all
  Google Workspace email records preserved; cloudflared installed and
  tunnel crmbuilder-mcp running as systemd user service routing
  mcp.crmbuilder.ai → 127.0.0.1:8810; Cloudflare Access two-policy
  split — Service Auth for the claude-ai-mcp Service Token and
  Allow + One-time PIN for the admin browser path; three auth paths
  verified end-to-end)
- 1 decision (DEC-225 — Cloudflare Access auth model revisions:
  Service Token added for programmatic clients that cannot follow
  OAuth redirects; One-time PIN replaces Google login since Cloudflare
  retired the built-in Google OAuth shortcut and bring-your-own Google
  Cloud OAuth setup is meaningful overhead for a low-frequency single-
  user admin path)
- 3 payload references:
  * decision:DEC-225 -[decided_in]-> session:SES-071
  * session:SES-071 -[is_about]-> planning_item:PI-045
  * decision:DEC-225 -[references]-> decision:DEC-204
- 1 close_out_payload lazy-created (COP-071)
- 1 deposit_event lazy-created (DEP head + 1)

Identifier rebase note: this work was initially anticipated as
SES-069 / DEC-216 per the PI-045 kickoff. Three parallel-sandbox
commits during the conversation advanced the identifier space —
SES-069 / DEC-216..220 / PI-048 (PI-023 reconciliation utility
planning) applied at commit 1435f0a; SES-070 / DEC-221..224 (PI-030
architecture planning) committed but unapplied at 232e967; PI-022
governance-backfill program closed at b34391f. Rebased to
SES-071 / DEC-225 to avoid collision. Fifth occurrence of the
parallel-sandbox identifier-rebase pattern in the recent program;
PI-032's reserve-at-apply-time identifier model would eliminate
this class.

Step 5 of PI-045 (register the MCP URL https://mcp.crmbuilder.ai in
claude.ai's MCP integration with the X-CRMBuilder-Secret custom
header and the CF-Access-Client-Id / CF-Access-Client-Secret
service-token headers) is gated on the PI-045 code-changes
implementation conversation completing first. That conversation
runs slices A, B, C in sequence at Doug's terminal via Claude Code.

Hygiene followup before step 5 goes live: rotate the claude-ai-mcp
Service Token's Client Secret — the value appeared in this
conversation's transcript during a doubled-header diagnostic. Blast
radius is currently zero (no MCP backend listening, no shared-secret
middleware to gate); rotation closes the window before claude.ai
integration goes live."

git pull --rebase origin main
git push
```

---

## Done

Reply with:

- Pre-apply heads: actual (depends on SES-070 apply state), references = N
- Post-apply heads: SES-071, DEC-225, PI-048 unchanged, COP-071 (lazy), DEP head + 1 (lazy), references = N + 6 or 7
- Record counts: 1 session OK, 1 decision OK, 0 planning items, 3 references OK, 0 SKIPs, 1 lazy COP-071, 1 lazy DEP
- The references edges confirmed via `curl -s 'http://127.0.0.1:8765/references?source_type=decision&source_id=DEC-225'` and `curl -s 'http://127.0.0.1:8765/references?source_type=session&source_id=SES-071'`
- Snapshot commit SHA
- Next: PI-045 code-changes implementation conversation — run the three slice prompts in sequence at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-045-A-transport-flag-and-http-binding.md`, then `…-pi-045-B-shared-secret-middleware.md`, then `…-pi-045-C-marker-handling.md`. After slice C lands, step 5 of PI-045 (claude.ai MCP integration registration) becomes executable.
