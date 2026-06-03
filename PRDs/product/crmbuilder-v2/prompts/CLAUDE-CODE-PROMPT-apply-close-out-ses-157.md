# Apply close-out SES-157 — PI-122 build-closure (Agent Profile Registry)

Applies `close-out-payloads/ses_157.json` on `main`: records the PI-122 (Agent
Profile Registry, ADO §10 follow-on, PRJ-018) build, ingests the seven commits
(Architecture pass + six Development slices), records **DEC-380**, and
**resolves PI-122**.

## Pre-flight

1. **On `main`** (branch-work protocol). `pi-122-registry` is merged FF.
2. **Run against a post-PI-122 API.** Start a fresh one on an alt port from
   current `main`:
   ```bash
   CRMBUILDER_V2_API_PORT=8766 crmbuilder-v2-api &
   curl -s http://127.0.0.1:8766/admin/version   # single `schema` block, head 0044
   ```
3. **Live-DB registry tables (create_all-managed DB).** The close-out itself
   writes only standard governance records, so it needs **no** registry schema
   change. To keep the live API's registry *reads* from 500-ing, the four
   registry tables were added to `data/v2-unified.db` directly via
   `Base.metadata.create_all` (idempotent, additive) after backing up to
   `data/v2-unified.db.pre-pi-122-backup-*`. **Registry WRITES on the live DB**
   additionally need the `change_log`/`refs` entity-type + relationship_kind
   CHECK rebuild (SQLite 0043/0044) — deferred until the registry is first
   exercised live (the runtime scheduler); nothing writes registry records on
   the live DB before then.
4. **Re-key if heads moved.** Authoring heads: next `SES-157` / `CNV-059` /
   `DEC-380`, `PI-122` In Progress under `PRJ-018`.

## Apply

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py \
    ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_157.json \
    --base http://127.0.0.1:8766 \
    --engagement CRMBUILDER
```

`session_belongs_to_project` (→ PRJ-018) is hoisted onto the session POST and
won't appear in the references-loop output — that's correct.

## Post-apply verification

```bash
curl -s -H X-Engagement:CRMBUILDER http://127.0.0.1:8766/planning-items/PI-122 \
  | python -c "import sys,json; d=json.load(sys.stdin)['data']; print(d['identifier'], d['status'])"
# expect: PI-122 Resolved
```

Then commit the new `deposit-event-logs/dep_NNN.log` + this payload + this apply
prompt in one commit.

## Deferred follow-ons (recorded in DEC-380)
- Read-only Qt monitoring panels for the four registry entities.
- The resolver's engagement override/disable of a system rule.
- The runtime scheduler (the separate ADO §10 follow-on that resolves a contract
  + `mint_agent_principal`s the ephemeral agent).
