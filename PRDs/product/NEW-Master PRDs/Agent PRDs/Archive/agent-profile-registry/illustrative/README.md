# Illustrative artifacts — read for the pattern, not the taxonomy

These files are the artifacts produced in the Claude.ai design conversation that
preceded reconciliation with the Agent Delivery Organization (ADO) design and the
PI-112 governance model. They are **reference material for the parent PRD**
(`../agent-profile-registry-PRD-v0.1.md`), not implementation-ready code.

**What is sound and carried into the PRD:** the registry *pattern* — a versioned,
shared catalog of skills and governance rules; float/pin propagation; the hybrid
advisory/enforced governance split; resolution of an agent identity into an
actionable contract; and the `code_asset_ref` bridge from a tool to a backing
callable. The reference broker's decision logic passes its smoke test.

**What is NOT carried forward (and why):**

- **The agent roster is wrong-layer.** `deployment-agent`, `validation-agent`,
  etc., with skills about applying YAML to an EspoCRM instance, describe the *v1
  product's* deploy operations. The real agents are the ADO tiers (Project
  Manager, PI Lead, Phase Specialists, Area Specialists). The PRD re-points the
  pattern at those.
- **Raw relational tables.** The PRD models `agent_profile` / `skill` /
  `governance_rule` as governance entities with reference-edge bindings, per
  `governance-entity-schema-spec-guide.md`, not the join tables shown here.
- **Dual-engine hand-written DDL.** V2 runs SQLite under Alembic behind the
  access layer; real implementation is a single Alembic migration, not the
  illustrative SQLite + Postgres scripts here.
- **Standalone runtime.** `agent_runtime.py` is not integrated with the access
  layer, the `{data, meta, errors}` envelope, or the MCP surface; much of its
  broker is likely subsumed by existing access-layer enforcement.

## Files

| File | What it illustrates |
|------|---------------------|
| `crmbuilder-v2-agent-registry-schema.md` | Full schema spec: four-layer registry, contract resolution, broker flow, predicate format, drift-assertion pinning, worked example. |
| `migration_v2_0_sqlite.sql` | Illustrative SQLite DDL (CHECK-enum, JSON-as-TEXT). |
| `migration_v2_0_postgres.sql` | Illustrative Postgres DDL (JSONB, TIMESTAMPTZ) — the conversation's now-superseded dual-engine plan. |
| `seed_v2_0_agent_registry.yaml` | Illustrative seed: the wrong-layer generic roster, kept as a pattern example. |
| `agent_runtime.py` | Reference resolver + enforcement broker (stdlib only; safe AST predicate eval; code-asset bridge). |
| `smoke_test.py` | Loads the SQLite DDL + seed in memory and exercises the broker across four scenarios; passes. |
