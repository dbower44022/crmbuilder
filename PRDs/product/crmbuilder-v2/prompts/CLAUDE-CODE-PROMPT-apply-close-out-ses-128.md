# Apply close-out — SES-128 / CNV-030

**Created:** 05-30-26
**Engagement:** CRMBUILDER dogfood
**Payload:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_128.json`

---

## Purpose

Land the SES-128 close-out: a Claude Code maintenance session that ran the superseded PI-052 "Slice C early" prompt, retired the dead Slice A chat spike (commit `74d4195`), confirmed the governance DB already reflected the shipped chat tab (PI-052/PI-106 Resolved, WT-055 consumed), and refreshed the long-stale v0.6 status singleton to v0.7.0 current reality.

**Net effect on apply:**

- `session` SES-128 (medium `chat`, status `complete`, parent WS-010)
- `conversation` CNV-030 (status `complete`)
- `commits` — 1 record (`74d4195`, the spike retirement)
- `references` — 3 total: `conversation_belongs_to_session` (CNV-030 → SES-128, also inlined into the conversation block), `session_belongs_to_workstream` (SES-128 → WS-010, inlined into the session block), `is_about` (CNV-030 → PI-052)
- `decisions`, `planning_items`, `work_tickets`, `resolves_planning_items`, `addresses_planning_items` — all empty
- A `close_out_payload` + `deposit_event` lazy-created by the apply, with `dep_NNN.log` teed to `deposit-event-logs/`

**Separate, non-payload step (status singleton refresh).** `apply_close_out.py` has no status-singleton section. The status refresh is a standalone `PUT /status` run **before** the apply, so the apply's snapshot regeneration captures the new `status.json` in one pass. See Step 1.

---

## Pre-flight

1. `cd` to repo root; confirm clean-ish tree (the payload + apply prompt are the only new untracked files).
2. `git pull --rebase origin main` (Doug's local clone — fast-forward expected).
3. Confirm payload exists: `PRDs/product/crmbuilder-v2/close-out-payloads/ses_128.json`.
4. API health: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/health` → `200`.
5. Pre-apply head capture: SES head `SES-127`, CNV head `CNV-029`, status version `16`. (Re-verify; re-key SES-128/CNV-030 if a parallel session advanced them.)

## Step 1 — refresh the status singleton (before apply)

The status body is inlined here (the `{"payload": {...}}` shape `PUT /status` expects). Expect version `16 → 17`:

```bash
curl -s -X PUT http://127.0.0.1:8765/status \
  -H 'Content-Type: application/json' \
  -d @- <<'JSON' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('status version now', d.get('version'))"
{
  "payload": {
    "title": "CRMBuilder v2 status",
    "phase": "v0.7 governance entities shipped; chat UI + session/conversation redesign + API-lifecycle hardening landed",
    "version_label": "0.7.0",
    "metadata": {
      "Last Updated": "05-30-26",
      "Status": "v0.7.0. Master CRMBuilder PRD consolidation is the active direction; CRMBuilder dogfood is the current validation case."
    },
    "active_work": "Active direction per CLAUDE.md: consolidate into a single canonical Master CRMBuilder PRD at specifications/master-crmbuilder-PRD.md, authored by running its own process against CRMBuilder itself (dogfood). CBM is the next-phase validation case. Approach is iterative: draft enough PRD to make the next phase runnable, execute it against CRMBuilder, refine.\n\nShipped since the v0.6 styling rollout (this status was last refreshed at v0.6 / 05-18-26 and had drifted ~12 sessions; refreshed at SES-128 / 05-30-26):\n\n- PI-052 — Chat UI on the Anthropic API with native tool definitions. Resolved. The chat tab is fully built at ui/chat/ (controller, persistence, session, worker, widgets, auth, tools) consuming the shared mcp_server.tools.tool_definitions(http) registry (ToolDefinition dataclass; 51 tools; read/write partition by name-prefix). PI-106 (Slice D follow-ups — sidebar staleness indicator + interactive context-window Trim) Resolved. The throwaway Slice A terminal spike (chat_spike.py) was retired at SES-128 (commit 74d4195) once the production tab made it dead scaffolding.\n\n- PI-073 / DEC-314 — Session/Conversation redesign. Session is now the medium-agnostic communication container (one chat / email / call / meeting = one session) with a six-status lifecycle and schedulability; Conversation is a topical sub-unit nested 1:N within a session. New conversations use the CNV-NNN prefix.\n\n- v0.7 governance-entity release — six new entity types (workstream, conversation, reference_book, work_ticket, close_out_payload, deposit_event) with tables, REST endpoints, desktop panels under the Governance group, and access-layer edge-rule enforcement. deposit_event POST is atomic and lazy-creates its close_out_payload.\n\n- PI-075 — executive_summary is NOT NULL (200-800 chars) on decisions, planning_items, and sessions.\n\n- PI-090 / PI-101 — close-out pre-flight + apply-pipeline validator hardening against governance-recording-rules.md.\n\n- PI-108 — universal created/last-edited timestamp visibility across the V2 desktop UI.\n\n- PI-109 — references.create auto-consumes ready work_tickets on inbound opens-against edges of either kind (replacing the fragile explicit-PATCH discipline).\n\n- PI-110 / DEC-333 — API rotating log file (data/logs/api.log) + desktop UI auto-restart of the API on connection loss / subprocess crash.\n\nNotable open work: PI-084 (author the canonical governance-recording-rules.md to released status), PI-104 (re-test/enable the claude.ai-web custom connector once Anthropic ships the post-OAuth bearer-attachment fix — DEC-244/DEC-245 record the upstream block and the chat-UI-on-API pivot that succeeded it), PI-111 (optional periodic /health heartbeat to proactively detect an external API's death).\n\n__version__ is 0.7.0 (crmbuilder-v2/src/crmbuilder_v2/__init__.py)."
  }
}
JSON
```

## Step 2 — apply

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_128.json
```

Expected: conversation ✓, session ✓, 1 commit ✓, 3 references ✓ (no decisions/PIs/WTs), deposit_event recorded, `dep_NNN.log` written.

## Step 3 — post-apply verification

- `GET /sessions/SES-128` → status `complete`, parent edge to WS-010 present.
- `GET /conversations/CNV-030` → status `complete`, belongs_to_session SES-128.
- `GET /references/touching/planning_item/PI-052` → includes the new `is_about` from CNV-030.
- `GET /status` → version `17`, version_label `0.7.0`.

## Step 4 — commit snapshot regeneration

The apply transactionally regenerates `db-export/*.json` (incl. `status.json`) + `change_log.json` and writes `deposit-event-logs/dep_NNN.log`. Commit those together with the payload, apply prompt, and status body:

```
v2: SES-128 close-out — retire PI-052 Slice A spike, refresh status singleton to v0.7.0
```

Do not push — Doug pushes after review.
