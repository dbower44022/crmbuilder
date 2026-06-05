# PI-134 findings-entity live-DB migration runbook (PREPARED — do not auto-apply)

Adding the `finding` entity to the live store (`crmbuilder-v2/data/v2-unified.db`)
is a **destructive schema operation** — it CREATEs the `findings` table and
**rebuilds three CHECK constraints** on the existing `change_log` and `refs`
tables (SQLite rebuilds the whole table to change a CHECK). Per the branch-work
protocol and the destructive-op discipline, this is **prepared and copy-tested
here but NOT applied** — a PM session authorizes and runs it after verifying
PI-134 and merging the branch.

## What the migration does

`migrations/versions/0045_pi_134_findings_entity.py` (SQLite) and its companion
`migrations/pg/versions/0007_pi_134_findings_entity.py` (Postgres):

1. **CREATE TABLE `findings`** from the ORM model (carries the `FND-` identifier
   CHECK, the type/severity/status/resolution-method CHECKs, and the composite
   `(engagement_id, finding_identifier)` PK).
2. **Rebuild `ck_changelog_entity_type`** to admit `finding`.
3. **Rebuild `ck_ref_source_type` + `ck_ref_target_type`** to admit `finding`.
4. **Rebuild `ck_ref_relationship`** to admit `finding_relates_to` +
   `finding_resolved_by`.

All four CHECKs are **supersets** of the current ones, so no existing row is
invalidated. Predicates are derived from the current vocab, so they cannot drift
from the model.

Why it is needed before any finding is written to the live DB: the live
`refs`/`change_log` CHECKs do not yet admit `finding`, so a finding insert or a
`finding_relates_to` edge would 500 on the live DB (the recurring
create_all-managed CHECK drift — see `project_v2_changelog_check_migration_gotcha`).

## The live store is create_all-managed (not on the alembic chain)

`data/v2-unified.db` has **no `alembic_version` table** — it was built by
`create_all`, not walked through the SQLite migration chain (which cannot run
from scratch without the decommissioned base-entity-catalog YAMLs). So the apply
is **stamp-then-single-step-upgrade**, exactly as copy-tested below; the
migration file is the canonical record of the delta either way.

## Copy-test performed (this session, passed)

Run against a **copy** of the live DB; the live DB was never touched.

```bash
cp crmbuilder-v2/data/v2-unified.db /tmp/v2-unified-pi134-copytest.db
cd crmbuilder-v2
CRMBUILDER_V2_DB_PATH=/tmp/v2-unified-pi134-copytest.db uv run alembic stamp 0044_pi_122_registry_binding_edges
CRMBUILDER_V2_DB_PATH=/tmp/v2-unified-pi134-copytest.db uv run alembic upgrade 0045_pi_134_findings_entity
```

Verified on the copy:
- `findings` table created;
- `refs` CHECK admits `'finding'` source/target + `finding_relates_to` +
  `finding_resolved_by`; `change_log` CHECK admits `'finding'` (DDL inspected);
- a real finding INSERT succeeds; finding ref edges of both kinds insert without
  CHECK failure;
- the live `data/v2-unified.db` still has **no** findings table (untouched).

## PM apply procedure (when authorized)

1. **Stop the API** (so there is no concurrent writer — this is exactly the
   PI-133 exclusive-migration drill, by hand):
   `pkill -f crmbuilder-v2-api` (or the runtime's exclusive-migration step).
2. **Back up** the live DB:
   `cp crmbuilder-v2/data/v2-unified.db crmbuilder-v2/data/v2-unified.db.pi134-backup`
3. **Apply** the delta (stamp-then-upgrade, the copy-tested path):
   ```bash
   cd crmbuilder-v2
   CRMBUILDER_V2_DB_PATH=data/v2-unified.db uv run alembic stamp 0044_pi_122_registry_binding_edges
   CRMBUILDER_V2_DB_PATH=data/v2-unified.db uv run alembic upgrade 0045_pi_134_findings_entity
   ```
   (Stamping writes the `alembic_version` marker the live DB never had; only
   0045 then runs.)
4. **Verify**: `GET /findings` returns `{data: [], ...}`; a `POST /findings`
   with a `finding_relates_to` edge succeeds (no 500).
5. **Restart the API**.

Rollback if needed: restore the `.pi134-backup` copy, or
`alembic downgrade 0044_pi_122_registry_binding_edges` (drops the table and
narrows the CHECKs after clearing any finding rows/edges).

## After apply — the rest of PI-134's live governance

Only after the live DB carries the `findings` table can the live runtime record
findings (the pool's `_record_finding` and the reconciliation gate's reads).
Until then, the gate is fully functional on create_all/test DBs (proven by the
demo + tests); on the live DB a merge-conflict/verify-failure still surfaces via
the `needs_attention` flag (the pool's existing fallback).
