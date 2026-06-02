# Apply close-out SES-154 — PI-α build-closure (Postgres foundation) + create PI-α/β/γ + resolve PI-α

**Run on `main`, after `pi-alpha-postgres` is merged** (apply_close_out refuses
off `main`). Payload:
`PRDs/product/crmbuilder-v2/close-out-payloads/ses_154.json`.

This is the DEC-232 / SES-074 build-closure for **PI-α** (Postgres foundation,
PRJ-019). Unlike PI-123, **PI-α never existed as a governance planning item** — so
this close-out **creates all three PRJ-019 planning items** (PI-α Postgres
foundation, PI-β de-file + kill snapshots, PI-γ identity/RBAC) in the
`planning_items` section, ingests the 7 branch commits as CM records, records the
build as **DEC-377**, and **resolves PI-α**. There is **no ADO workstream/work-task
completion step** (PI-α was built directly, not decomposed into phase Workstreams).

## 1. Pre-flight — re-key to main's heads
The payload was drafted off `pi-alpha-postgres` assuming main's heads are
SES-153 / CNV-055 / DEC-376 / PI-124 (i.e. after `ses_152` + `ses_153` applied).
Check the live heads and **re-key if anything advanced in parallel** (the SES-077
pattern):

```
curl -s .../sessions/next-identifier        # expect SES-154
curl -s .../conversations/next-identifier    # expect CNV-056
curl -s .../decisions/next-identifier         # expect DEC-377
curl -s .../planning-items/next-identifier    # expect PI-125 (then 126, 127)
curl -s .../projects/PRJ-019                   # must exist
```

- If a value advanced, bump it and **every matching `source_id`/`target_id`** in
  the payload: the session/conversation ids, DEC-377, the three planning-item ids
  (PI-125/126/127), the `planning_item_belongs_to_project` edges, the
  `blocked_by` edge (PI-127→PI-125), `decided_in`, `session_follows_from`
  (→ the actual prior session), and `resolves_planning_items` (→ the re-keyed
  PI-α id).
- The 7 `commit_sha`s are git-stable on a **fast-forward** merge — do **not**
  change them. If the merge was a rebase/squash, re-capture the SHAs + parent SHAs
  from `main` (`git log`). `commit_identifier` (CM-NNNN) is server-assigned.

## 2. Apply
```
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_154.json
```
Atomically writes the session, conversation, the 3 planning items, the 7 commits,
DEC-377, the edges, and flips PI-α (PI-125) → **Resolved**; lazy-creates the
close_out_payload + deposit_event.

## 3. Verify
- `curl .../planning-items/PI-125` → status **Resolved**; PI-126 / PI-127 present
  (status **Draft**), both with `planning_item_belongs_to_project → PRJ-019`.
- `curl .../decisions/DEC-377` present; the 7 commits present (`GET /commits`).
- `GET /references?target_id=PI-125&relationship=blocked_by` → PI-127 depends on
  PI-α (now satisfied, since PI-α is Resolved).
- `GET /projects/PRJ-019/backlog` shows PI-126 / PI-127 as the program's open
  successors.

## 4. Commit
Commit the regenerated `db-export/*.json` + the new
`deposit-event-logs/dep_NNN.log` + this payload + prompt in one commit (the
standard close-out commit on `main`).

## Notes
- **DEC-377** records PI-α's build + the port-discovered findings (the four
  byte-identical-on-SQLite dialect-aware CHECK constructs; dual-head Alembic via a
  separate `migrations/pg/` tree; the straight-copy + sequence-reset migration;
  the DELETE-based PG test reset + the scope-listener reinstall; the six
  VARCHAR-overflow widenings). The architecture doc already carries the §8.5 build
  notes; no further doc edit is required by this apply.
- **Successors:** with PI-α Resolved, **PI-γ** (RBAC) and **PI-β** (de-file + kill
  snapshots, parallel) are the open PRJ-019 items. PI-122 (Agent Profile Registry)
  additionally consumes PI-γ's principal model.
- **Carried-over PI-123 hygiene (separate, optional):** PI-123's phase workstreams
  WSK-009..013 / work-tasks WTK-026..030 were never marked terminal via the ADO
  endpoints. Cosmetic; does not affect PI-123's Resolved state. Clear it whenever
  convenient, independently of this apply.
