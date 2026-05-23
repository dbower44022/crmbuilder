# CLAUDE-CODE-PROMPT — Apply SES-056 closeout

**Last Updated:** 05-22-26 17:30 (after the v0.7 governance entity release shipped)
**Payload:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_056.json`
**Predecessor close-out:** SES-055 (`PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-055.md`)

---

## What this applies

SES-056 closes the v0.7 governance entity release. The payload writes:

- **1 session** — `SES-056`, the v0.7 release ship session.
- **1 decision** — `DEC-167`, the SQLite transaction-control fix landed during the Slice B regression run (explicit `BEGIN IMMEDIATE` + `busy_timeout` so an outer `session.rollback()` actually undoes the autoassign `SAVEPOINT` write).
- **3 planning items** — `PI-024` / `PI-025` / `PI-026`, the three follow-on phases of PI-022 (prior workstreams; prior conversations; historical applies as deposit_events).
- **6 references** — `DEC-167 decided_in SES-056`; `PI-024/025/026 is_about PI-022`; `PI-025 blocks PI-024`; `PI-026 blocks PI-025`.

The v0.7 apply script (Slice D) automatically POSTs the closing deposit_event at the apply's last step. The deposit_event lazy-creates `COP-056` (status `ready`), then atomically transitions it to `applied` per first-success semantics (DEC-149 / DEC-158).

## Pre-flight

```bash
curl -sf http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/sessions/next-identifier   # → SES-056
curl -s http://127.0.0.1:8765/decisions/next-identifier  # → DEC-167
curl -s http://127.0.0.1:8765/planning-items/next-identifier  # → PI-024
```

The API must be running with v0.7 code (the running process should report `"version":"0.7.0"` at `GET /`).

## Apply

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_056.json
```

The script:

1. Fetches the next `DEP-NNN` identifier and opens `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log`; tees stdout to it.
2. POSTs the 11 records (1 session, 1 decision, 3 planning items, 6 references) in fixed section order.
3. POSTs the deposit_event as the apply's last step with `target_file_path` = `PRDs/product/crmbuilder-v2/close-out-payloads/ses_056.json`. The access layer lazy-creates `COP-056` and transitions it to `applied`.

Exit code 0 on full success.

## Post-apply

Transition the WS-001 workstream to `complete` (the v0.7 workstream is finished):

```bash
curl -s -X PATCH http://127.0.0.1:8765/workstreams/WS-001 \
  -H "Content-Type: application/json" \
  -d '{"workstream_status":"complete"}'
```

The CLAUDE.md `Working conventions` section requires the operator to push commits manually after review; do not push from this script.

## Verify

```bash
curl -s http://127.0.0.1:8765/sessions/SES-056 | jq '.data.identifier'
curl -s http://127.0.0.1:8765/decisions/DEC-167 | jq '.data.identifier'
curl -s "http://127.0.0.1:8765/planning-items" | jq -r '.data[].identifier' | grep -E "PI-02[456]"
curl -s "http://127.0.0.1:8765/close-out-payloads/COP-056" | jq '.data.close_out_payload_status'
curl -s "http://127.0.0.1:8765/workstreams/WS-001" | jq '.data.workstream_status'
curl -s "http://127.0.0.1:8765/deposit-events" | jq -r '.data[0].deposit_event_identifier'
```

Expected: `SES-056`, `DEC-167`, three new PIs, COP `applied`, WS-001 `complete`, latest deposit_event `DEP-009` (or higher if subsequent applies have run).
