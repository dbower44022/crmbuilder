# Apply close-out — SES-155 (PI-β build-closure: de-file + kill snapshots)

## Purpose

Land the PI-β build-closure governance on `main`: record the session/conversation,
the build decision, ingest the four PI-β commits, and **resolve PI-126**.

**Net effect** (CRMBUILDER / ENG-001):
- `SES-155` (build-closure session, complete) + `CNV-057` (its conversation).
- `DEC-378` — PI-β de-file + kill-snapshots build decisions and findings.
- 4 commits ingested: `7d6eac5` (arch), `a9d2694` (slices 1-3), `4185bd8d` (slice 4), `eac4b01` (slices 5-6).
- References: session/conversation `*_belongs_to_project` → PRJ-019, `session_follows_from` SES-154, `decided_in` CNV-057.
- **PI-126 → Resolved** (`resolves_planning_items`).
- Lazy-creates the `close_out_payload` + `deposit_event`; tees to `deposit-event-logs/dep_NNN.log`.

## Pre-flight

1. On `main`, clean working tree (or only the payload/prompt/script-fix staged), `git pull --rebase`.
2. Payload exists: `PRDs/product/crmbuilder-v2/close-out-payloads/ses_155.json`.
3. **The API must be running POST-PI-β code.** A pre-PI-β API still runs the old
   export hook (which would regenerate the deleted `db-export/` tree) and the
   meta-DB/marker path. Check: `GET /admin/version` must return a single `schema`
   block (NOT `engagement_schema`/`meta_schema`), and `POST /admin/active-engagement`
   must 404/405 (the endpoint was removed). If the live API on 8765 is stale,
   either restart it on current `main`, or run a fresh API on an alternate port
   and pass `--base`.
4. Capture heads (expect next SES-155 / CNV-057 / DEC-378; PI-126 Draft):
   `curl -s -H X-Engagement:CRMBUILDER http://127.0.0.1:8765/sessions/next-identifier` (etc.).

## Apply

PI-β now requires the engagement be named per request — pass `--engagement`:

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_155.json \
  --engagement CRMBUILDER            # add --base http://127.0.0.1:8766 if using an alt-port API
```

Expected: SES-155, CNV-057, DEC-378 created; 4 commits; 5 references (4 top-level +
1 conversation membership); PI-126 flipped Open→Resolved; `close_out_payload` +
`deposit_event` lazy-created.

## Post-apply verification

- `GET /planning-items/PI-126` → `status: Resolved` with a resolution reference.
- `GET /decisions/DEC-378` → exists, `status: Active`.
- `GET /sessions/SES-155`, `/conversations/CNV-057` → exist, `complete`.
- Heads advanced to SES-155 / CNV-057 / DEC-378.
- A new `deposit-event-logs/dep_NNN.log` was written.

## Commit

Commit on `main` (no `db-export/` to regenerate — PI-β removed it):

```
git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_155.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-155.md \
        PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log \
        crmbuilder-v2/scripts/apply_close_out.py
```

(The `apply_close_out.py` change adds the `--engagement` flag + `X-Engagement`
header that PI-β made necessary.)

## Done block

Heads before/after, record counts, PI-126 status, deposit-event log path.
