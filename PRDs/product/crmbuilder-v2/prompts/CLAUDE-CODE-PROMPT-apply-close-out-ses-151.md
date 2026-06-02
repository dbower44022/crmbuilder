# Apply close-out — SES-151 (PI-123 Architecture phase)

**Payload:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_151.json`
**Deliverable:** `PRDs/product/crmbuilder-v2/pi-123-unified-db-architecture.md` (committed `8082535`)
**Branch:** `main` (apply runs only on `main` per the Branch-work protocol)

## What this close-out records

The PI-123 Architecture/design pass for the unified multi-engagement-DB
migration (PRJ-019): the design doc (D1–D11) + the six-phase decomposition,
plus an end-to-end dogfood of the ADO substrate that models this work and
marks the Architecture phase Complete. SES-151 / CNV-053 / DEC-375; commit
`8082535`; `addresses` (does **not** resolve) PI-123.

## ADO substrate pre-steps (already executed against the live API before apply)

These are operational state transitions on the ADO entities (not close-out
sections — Workstreams/Work Tasks are created by the substrate, not the
payload). Run in order; each is idempotent-or-conflict on re-run.

```bash
# 1. PM dispatches the PI: Draft -> In Progress
curl -X POST http://127.0.0.1:8765/planning-items/PI-123/dispatch
# 2. Phase specialist decomposes: 6 phase Workstreams WSK-008..013 (serial blocked_by)
curl -X POST http://127.0.0.1:8765/planning-items/PI-123/decompose
# 3. Scope the Architecture Workstream with one storage-area Work Task (the design)
curl -X POST http://127.0.0.1:8765/workstreams/WSK-008/scope \
  -H 'Content-Type: application/json' \
  -d '{"work_tasks":[{"area":"storage","title":"Produce unified multi-engagement DB migration design + decomposition"}]}'
# 4. PI Lead opens the phase: Ready -> In Progress, readies WTK-025
curl -X POST http://127.0.0.1:8765/workstreams/WSK-008/start-execution
# 5. Area specialist claims + drives the Work Task to Complete (work is done — the design doc)
curl -X POST http://127.0.0.1:8765/work-tasks/WTK-025/claim -H 'Content-Type: application/json' -d '{"claimed_by":"claude-code (PI-123 Architecture pass)"}'
curl -X PATCH http://127.0.0.1:8765/work-tasks/WTK-025 -H 'Content-Type: application/json' -d '{"work_task_status":"Claimed"}'
curl -X PATCH http://127.0.0.1:8765/work-tasks/WTK-025 -H 'Content-Type: application/json' -d '{"work_task_status":"In Progress"}'
curl -X PATCH http://127.0.0.1:8765/work-tasks/WTK-025 -H 'Content-Type: application/json' -d '{"work_task_status":"Complete"}'
# 6. PI Lead completes the phase: verify all Work Tasks Complete -> WSK-008 Complete
curl -X POST http://127.0.0.1:8765/workstreams/WSK-008/complete-phase
```

Note: `claim` sets `claimed_by` only; the `Ready -> Claimed` status move is a
separate `PATCH work_task_status`. The PATCH body uses the **prefixed** field
name `work_task_status`, not `status`.

## Pre-flight

- Heads at authoring were next-free: SES-151, CNV-053, DEC-375. Re-verify via
  `GET /{sessions,conversations,decisions}/next-identifier` and re-key if a
  parallel session has claimed them.
- The pre-flight validator enforces `executive_summary` length 200–800 chars
  on the session block and each decision — keep both under 800 (this payload's
  first apply tripped on 1814/839, trimmed to 777/765).

## Apply

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_151.json
```

Atomically writes conversation → session → commit → DEC-375 → references →
`addresses` PI-123, and lazy-creates the `close_out_payload` + `deposit_event`
(DEP-146), teeing to `deposit-event-logs/dep_146.log`.

## Post-apply verification

```bash
curl -s http://127.0.0.1:8765/sessions/SES-151        # session_status: complete
curl -s http://127.0.0.1:8765/planning-items/PI-123   # status: In Progress (addressed, not resolved)
curl -s http://127.0.0.1:8765/workstreams/WSK-008     # workstream_status: Complete
```

Then commit the regenerated `db-export/*.json` + `deposit-event-logs/dep_146.log`
+ this payload + this prompt in one commit on `main`. (The design-doc commit
`8082535` landed separately and is ingested via the payload's `commits` section.)

## Next phase

Development (WSK-009), now unblocked. Slice 1: fold the meta DB into the unified
DB (migration `0037`) per the design doc §8 / Slice 1.
