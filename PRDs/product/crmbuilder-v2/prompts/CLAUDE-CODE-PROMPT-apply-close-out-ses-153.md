# Apply close-out SES-153 — PI-123 build-closure (unified-DB cutover) + resolve PI-123

**Run on `main`, after `pi-123` is merged** (apply_close_out refuses off `main`).
Payload: `PRDs/product/crmbuilder-v2/close-out-payloads/ses_153.json`.

This is the DEC-232 / SES-074 build-closure for PI-123: it ingests the 9 slice +
cutover commits (`commits` section → CM records), records the build-discovered
refinements as **DEC-376**, and **resolves PI-123** (`resolves_planning_items`),
which unblocks PI-122. Workstream/Work-Task completion is **not** a payload
section — do it via the ADO endpoints after the apply (step 3 below).

## 1. Pre-flight — re-key to main's heads
The payload was drafted off `pi-123` where the heads were SES-151 / CNV-053 /
DEC-375 (+ the PI-124 draft `ses_152.json` claims SES-152 / CNV-054). On `main`,
check the live heads and **re-key if anything advanced** (the SES-077 pattern):

```
curl -s .../sessions/next-identifier ; curl -s .../conversations/next-identifier
curl -s .../decisions/next-identifier ; curl -s .../planning-items/PI-123
```

- If applying **after** `ses_152.json` (PI-124), this is SES-153 / CNV-055 /
  DEC-376 as drafted; otherwise bump to the actual next free values and update
  the matching `source_id`/`target_id`/`decided_in` references.
- The 9 `commit_sha`s are git-stable — **do not change them**; `commit_identifier`
  (CM-NNNN) is server-assigned at apply.
- Confirm `PRJ-019` and `PI-123` exist on `main`.

## 2. Apply
```
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_153.json
```
Atomically writes the session, conversation, 9 commits, DEC-376, the edges, and
flips PI-123 → Resolved; lazy-creates the close_out_payload + deposit_event.

## 3. Complete the ADO workstreams + work tasks (via the API)
PI-123's phases (state at authoring): WSK-008 Architecture **Complete**; WSK-009
Development **In Progress** (WTK-026 In Progress, WTK-027/028/029/030 Ready);
WSK-010 Testing, WSK-011 Documentation, WSK-012 Data Migration, WSK-013
Deployment all **Planned**. The build delivered all of these (slices + cutover +
leak/consolidation tests + the runbook/arch-doc + the live cutover). Drive them
terminal — verify live state first, it may differ on `main`:

- Mark WTK-026..030 **Complete** (work-task lifecycle endpoints).
- `POST /workstreams/WSK-009/complete-phase` (Development) once its tasks are Complete.
- Complete WSK-010 (Testing), WSK-012 (Data Migration), WSK-013 (Deployment),
  WSK-011 (Documentation) — scope/`complete-phase` each, or mark **Not Applicable**
  if a phase had no discrete tasks. (The de-file/activation-worker remainder is
  successor-program work per DEC-376, not a PI-123 phase task.)

## 4. Verify
- `curl .../planning-items/PI-123` → status **Resolved**.
- PI-122's `blocked_by PI-123` is now satisfied → `GET /projects/PRJ-019/eligible-planning-items` (or PI-122's home) shows PI-122 eligible.
- `curl .../decisions/DEC-376` present; the 9 commits present (`GET /commits`).

## 5. Commit
Commit the regenerated `db-export/*.json` + the new `deposit-event-logs/dep_NNN.log`
+ this payload + prompt in one commit (the standard close-out commit on `main`).

## Note
DEC-376 records the build-discovered refinements (string-identifier discriminator,
consolidation-coupled enforce, **Session-class scope registration** — the
un-stamped-write fix, CBM re-created fresh, the deferred activation-worker
de-file). Fold those annotations into `pi-123-unified-db-architecture.md`
(D1/D3/D5/D8/D9). With PI-123 Resolved, the successor **Production Multi-Tenant
API** program (`production-multitenant-api-architecture.md`, PI-α/β/γ) can start.
