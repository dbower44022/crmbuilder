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

```bash
curl -s -X PUT http://127.0.0.1:8765/status \
  -H 'Content-Type: application/json' \
  -d @PRDs/product/crmbuilder-v2/close-out-payloads/_ses_128_status.json \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('status version now', d.get('version'))"
```

The new status payload body (`{"payload": {...}}`) is `_ses_128_status.json` alongside the close-out payload. Expect version `16 → 17`.

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
