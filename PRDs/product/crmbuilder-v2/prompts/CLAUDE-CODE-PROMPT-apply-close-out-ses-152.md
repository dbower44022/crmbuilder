# Apply close-out SES-152 — create PI-124 (UI messages must be selectable + copyable)

**Run on `main` only** (apply_close_out refuses off `main`; governance lands on
the single advancing line). Payload:
`PRDs/product/crmbuilder-v2/close-out-payloads/ses_152.json`.

This payload creates one planning item — **PI-124** ("All UI message/error
dialogs must support select-all and copy") under **PRJ-015** (UI usability
improvements) — plus the session/conversation that surfaced it. No commits, no
decisions, no resolves.

## Pre-flight (re-key to main's heads)
The payload was drafted off the `pi-123` branch where the heads were SES-151 /
CNV-053 / PI-123. Before applying on `main`, verify main's current heads and
**re-key if anything has advanced** (the SES-077 re-keying pattern):

```
curl -s http://127.0.0.1:8765/sessions/next-identifier        # vs SES-152
curl -s http://127.0.0.1:8765/conversations/next-identifier   # vs CNV-054
curl -s http://127.0.0.1:8765/planning-items/next-identifier  # vs PI-124
```

If main is ahead, bump SES-152 / CNV-054 / PI-124 (and the matching `source_id`
/ `target_id` / `planning_item_identifier` references) to the next free values.
Confirm **PRJ-015** exists on main (`curl .../projects/PRJ-015`); it is the
target of the `session_belongs_to_project`, `conversation_belongs_to_project`,
and `planning_item_belongs_to_project` edges.

## Apply
```
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_152.json
```

## Post-apply verification
- `curl .../planning-items/PI-124` → status `Draft`, item_type `pending_work`,
  belongs to PRJ-015.
- `GET /references?source_id=PI-124&relationship=planning_item_belongs_to_project`
  → one edge to PRJ-015.
- Commit the regenerated `db-export/*.json` + the new `deposit-event-logs/dep_NNN.log`
  + this payload + prompt in one commit (the standard close-out commit).

## Note
The error that surfaced this PI — "Switching failed at step 3" when switching to
CBM — is a *separate* concern: the desktop engagement-switch activation worker
(`ui/activation_worker.py`, Step 3 pre-flight Alembic + Step 8 launch) still
targets the per-engagement DB rather than the unified `v2-unified.db`. That is
PI-123 cutover-completion work (the "desktop switch → write-marker-only" item in
`pi-123-stage4-cutover-runbook.md`), not part of PI-124.
