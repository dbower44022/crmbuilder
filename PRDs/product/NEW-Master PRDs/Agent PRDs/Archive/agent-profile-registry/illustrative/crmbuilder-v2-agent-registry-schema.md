# CRM Builder V2 — Agent Registry Schema Specification

## Document Control

| Field | Value |
|---|---|
| Document | V2 Agent Registry Schema Specification |
| Status | DRAFT — resolved for implementation |
| Owner | D. Bower |
| Last Updated | 05-31-26 17:30 |
| Revision | 0.3 |
| Applies to | CRM Builder V2 database — SQLite (current), PostgreSQL (planned migration) |

---

## 1. Purpose & Scope

This document specifies the database schema for a centrally managed library of LLM agents in CRM Builder V2. The schema lets agent identity, capabilities ("skills"), and governance rules be stored, versioned, and managed in one place, so that dispersed agents derive their behavior from the database rather than from hardcoded local configuration.

In scope: table definitions, contract resolution, the runtime enforcement flow, the enforced-rule predicate format, and versioning/change control.

Out of scope (noted in §11): agent authentication, the code-asset registry internals, model selection policy, and the broker's deployment topology.

---

## 2. Design Principles

**Thin agents.** No agent hardcodes its own skills or rules. Each agent holds only a stable `agent_id`. At startup, and whenever its version stamp changes, it requests its *contract* from the registry and caches it locally. Changing an agent's behavior means editing rows and bumping a version — never redeploying the agent.

**Single source of truth.** The database is authoritative. A dispersed agent reports the contract revision it is running, so drift is detectable.

**Hybrid governance.** Governance rules carry an `enforcement` mode. Advisory rules are composed into the agent's system prompt and the LLM is trusted to follow them. Enforced rules are machine-evaluable predicates that a broker checks before any tool call (including code-asset invocations) executes. High-stakes rules — destructive operations, environment scoping, approval gates — are enforced; soft guidance stays advisory.

**Shared catalogs.** Skills and rules are defined once and bound to many agents, so an improvement propagates. Propagation is controlled per binding (see §9).

---

## 3. Data Model Overview

Four layers plus an audit trail:

1. **Identity / versioning** — `agent`, `agent_version`
2. **Capability** — `skill`, `agent_skill`
3. **Governance** — `governance_rule`, `agent_governance`
4. **Audit** — `audit_log` (design-time changes), `enforcement_event` (run-time broker decisions)

A read-only **resolver** composes `agent_id → contract`. It is the only call an agent makes to learn its behavior.

---

## 4. Table Definitions

DDL is engine-neutral. `JSON` columns assume native JSON support; on engines without it, store as `TEXT` and validate in the application layer (see §11).

### 4.1 `agent` — identity registry

```sql
CREATE TABLE agent (
    agent_id            TEXT PRIMARY KEY,        -- stable slug, e.g. 'deployment-agent'
    display_name        TEXT NOT NULL,
    description         TEXT NOT NULL,           -- base role; seeds the system prompt
    status              TEXT NOT NULL,           -- draft | active | deprecated
    current_version_id  TEXT,                    -- FK -> agent_version.version_id
    credential_ref      TEXT,                    -- placeholder for auth (out of scope)
    created_at          TIMESTAMP NOT NULL,
    updated_at          TIMESTAMP NOT NULL
);
```

### 4.2 `agent_version` — versioned definition + changelog

```sql
CREATE TABLE agent_version (
    version_id      TEXT PRIMARY KEY,
    agent_id        TEXT NOT NULL REFERENCES agent(agent_id),
    revision        TEXT NOT NULL,               -- semver, e.g. '1.2.0'
    effective_date  TIMESTAMP NOT NULL,
    author          TEXT NOT NULL,
    changelog       TEXT NOT NULL,
    model_hint      TEXT,                         -- optional preferred model/params
    is_current      BOOLEAN NOT NULL DEFAULT 0,
    created_at      TIMESTAMP NOT NULL,
    UNIQUE (agent_id, revision)
);
```

`is_current` is flipped atomically so exactly one version per agent is live at a time; `agent.current_version_id` mirrors it for fast lookup.

### 4.3 `skill` — shared capability catalog

```sql
CREATE TABLE skill (
    skill_id        TEXT PRIMARY KEY,            -- slug, e.g. 'validate-deployment-yaml'
    name            TEXT NOT NULL,
    description     TEXT NOT NULL,
    kind            TEXT NOT NULL,               -- instruction | tool
    io_contract     JSON,                         -- JSON Schema of inputs/outputs (tool only)
    code_asset_ref  TEXT,                         -- optional: pointer to callable (code-backed tools)
    category        TEXT,
    revision        TEXT NOT NULL,               -- catalog item is independently versioned
    created_at      TIMESTAMP NOT NULL,
    updated_at      TIMESTAMP NOT NULL
);
```

- `instruction` — pure prompt guidance; contributes text to the system prompt, no tool exposed.
- `tool` — exposed to the LLM as a tool definition built from `io_contract`. A tool is **code-backed** when it carries a `code_asset_ref` (the runtime imports and calls that callable on invocation); a tool with no `code_asset_ref` is handled by the agent harness or produces structured output by reasoning alone. Presence of the ref — not a separate kind — answers "is this backed by code?"

### 4.4 `agent_skill` — binding (agent_version ↔ skill)

```sql
CREATE TABLE agent_skill (
    agent_version_id  TEXT NOT NULL REFERENCES agent_version(version_id),
    skill_id          TEXT NOT NULL REFERENCES skill(skill_id),
    pinned_revision   TEXT,                       -- NULL = float to latest; set = pinned
    scope             JSON,                        -- per-binding params/limits
    PRIMARY KEY (agent_version_id, skill_id)
);
```

### 4.5 `governance_rule` — shared policy catalog

```sql
CREATE TABLE governance_rule (
    rule_id      TEXT PRIMARY KEY,                -- slug, e.g. 'no-destructive-migration-without-approval'
    name         TEXT NOT NULL,
    rule_type    TEXT NOT NULL,                   -- permission | prohibition | constraint | escalation
    enforcement  TEXT NOT NULL,                   -- advisory | enforced | enforced_with_override
    severity     TEXT NOT NULL,                   -- info | warning | critical
    body         TEXT NOT NULL,                   -- advisory: instruction text; enforced: human description
    predicate    JSON,                            -- enforced rules only (see §8)
    revision     TEXT NOT NULL,
    created_at   TIMESTAMP NOT NULL,
    updated_at   TIMESTAMP NOT NULL
);
```

`enforcement` is an enum (not a boolean) so `enforced_with_override` — block but allow a logged human override — is available without a schema change.

### 4.6 `agent_governance` — binding (agent_version ↔ rule)

```sql
CREATE TABLE agent_governance (
    agent_version_id  TEXT NOT NULL REFERENCES agent_version(version_id),
    rule_id           TEXT NOT NULL REFERENCES governance_rule(rule_id),
    pinned_revision   TEXT,                       -- NULL = float; set = pinned
    override          JSON,                        -- per-binding override (e.g. raise/lower severity)
    PRIMARY KEY (agent_version_id, rule_id)
);
```

### 4.7 `audit_log` — design-time change control

```sql
CREATE TABLE audit_log (
    audit_id      TEXT PRIMARY KEY,
    entity_type   TEXT NOT NULL,                  -- agent | agent_version | skill | rule | binding
    entity_id     TEXT NOT NULL,
    action        TEXT NOT NULL,                  -- create | update | deprecate | bind | unbind
    actor         TEXT NOT NULL,
    diff          JSON,
    occurred_at   TIMESTAMP NOT NULL
);
```

### 4.8 `enforcement_event` — run-time broker decisions

```sql
CREATE TABLE enforcement_event (
    event_id          TEXT PRIMARY KEY,
    agent_id          TEXT NOT NULL,
    agent_version_id  TEXT NOT NULL,
    rule_id           TEXT,                        -- rule that fired, if any
    tool_call         JSON NOT NULL,               -- the proposed action
    decision          TEXT NOT NULL,               -- allow | deny | override
    actor             TEXT,                         -- approver, for overrides
    occurred_at       TIMESTAMP NOT NULL
);
```

---

## 5. Contract Resolution

Given an `agent_id`, the resolver gathers the current version, its bound skills, and its bound rules, then composes a contract.

Representative gather queries:

```sql
-- current version
SELECT v.* FROM agent_version v
JOIN agent a ON a.current_version_id = v.version_id
WHERE a.agent_id = :agent_id;

-- bound skills (revision resolved per binding: pinned or latest)
SELECT s.*, b.scope, b.pinned_revision
FROM agent_skill b
JOIN skill s ON s.skill_id = b.skill_id
WHERE b.agent_version_id = :version_id;

-- bound rules
SELECT r.*, g.override, g.pinned_revision
FROM agent_governance g
JOIN governance_rule r ON r.rule_id = g.rule_id
WHERE g.agent_version_id = :version_id;
```

Composition (Python-flavored, matching the PySide6 stack):

```python
def resolve_contract(agent_id):
    ver    = current_version(agent_id)
    skills = bound_skills(ver.version_id)   # revision resolved per binding
    rules  = bound_rules(ver.version_id)

    instruction_skills = [s for s in skills if s.kind == "instruction"]
    tool_skills        = [s for s in skills if s.kind == "tool"]
    advisory           = [r for r in rules if r.enforcement == "advisory"]
    enforced           = [r for r in rules if r.enforcement != "advisory"]

    system_prompt = compose_prompt(ver.description, instruction_skills, advisory)
    tools         = [to_tool_def(s) for s in tool_skills]   # code-backed tools wired via code_asset_ref
    return Contract(
        system_prompt = system_prompt,
        tools         = tools,
        enforced      = enforced,
        revision      = ver.revision,
    )
```

The contract returned to a dispersed agent is therefore: a composed **system prompt**, a **tool set**, an **enforced ruleset** (handed to the broker), and a **revision stamp**.

---

## 6. Runtime Flow & Enforcement Broker

1. Agent boots holding only `agent_id` (and a credential, once auth is designed).
2. Agent calls the resolver, receives the contract, caches it locally keyed by revision.
3. On each turn the LLM may propose a tool call, including a code-asset invocation.
4. The **broker** intercepts the proposed call and evaluates it against the enforced ruleset before execution.
5. Decision is logged to `enforcement_event`.
6. The agent periodically re-checks the current revision; on change it re-resolves and refreshes its cache.

Broker logic:

```python
def check(proposed_call, enforced_rules):
    for rule in sorted(enforced_rules, key=lambda r: SEVERITY_ORDER[r.severity]):
        if predicate_matches(rule.predicate, proposed_call):
            if rule.enforcement == "enforced":
                return Deny(rule)            # returned to LLM with reason
            return PendingOverride(rule)     # enforced_with_override: block, await approval
    return Allow()
```

A `Deny` is returned to the LLM as a tool result explaining which rule fired and why, so the model can adapt (e.g. request an approval flag) rather than fail blindly.

---

## 7. (reserved)

---

## 8. Enforced-Rule Predicate Format

Per the prior decision, enforced rules start with a small structured predicate rather than a full expression language. Escalate to an expression engine only if this proves too rigid.

```json
{
  "subject": "schema_migration",
  "operation": "destructive",
  "condition": "approval_flag != true OR backup_verified != true",
  "effect": "deny"
}
```

- `subject` — the domain object the proposed call touches.
- `operation` — the action class.
- `condition` — the circumstance under which the effect applies.
- `effect` — `deny` or `override`.

`predicate_matches` evaluates the predicate against the proposed tool call's resolved arguments.

---

## 9. Versioning & Change Control

- Every mutation to an agent, version, skill, rule, or binding writes an `audit_log` row.
- Agent behavior is anchored by `agent_version.revision` (semver); `is_current` flips atomically.
- Skills and rules are **independently versioned** catalog items. Each binding either **floats** (tracks the latest catalog revision) or **pins** (locks to a specific revision) via `pinned_revision`.

**RESOLVED — default propagation behavior (r0.2).** Bindings split by risk class:

- **Float** (`pinned_revision = NULL`, tracks latest catalog revision): `instruction` skills and `advisory` rules. These are pure guidance; propagating improvements immediately is the centralization win.
- **Pin** (`pinned_revision` set, requires explicit version bump to adopt a change): all `tool` skills (code-backed or not) and `enforced` / `enforced_with_override` rules. These change what the agent actually executes or hard-constrain it, so a catalog edit must not silently alter behavior across every bound agent. Pinning gives controlled rollout where the stakes are highest.

The general principle: **float pure guidance, pin anything that changes execution or imposes a hard constraint.** A binding may override its class default explicitly (e.g. pin an advisory rule, or float a low-risk tool) by setting or clearing `pinned_revision`.

**Pinning semantics under the current single-row catalog.** The `skill` and `governance_rule` tables hold one row per item carrying its current `revision`; historical revisions are not stored. Pinning therefore behaves as a **drift assertion**: a floating binding always adopts the current row; a pinned binding also reads the current row but, if `current.revision` no longer equals `pinned_revision`, the resolver flags the binding as *stale* (surfaced in the contract's warnings) so an operator can review and bump the binding to adopt. True point-in-time retrieval of a superseded revision would require versioned catalog tables (`skill_version`, `rule_version`) — recorded as a future enhancement in §11.

---

## 10. Worked Example — CBM Deployment Agent

`deployment-agent` v1.2.0, bound as follows:

- Skills: `validate-deployment-yaml` (tool), `diff-config` (tool), `apply-yaml-config` (tool, code-backed via `code_asset_ref`).
- Rules: `no-destructive-migration-without-approval` (enforced, critical, pinned), `escalate-on-prod-target` (enforced_with_override, critical, pinned), `prefer-idempotent-operations` (advisory, warning, floating).

Flow: the agent resolves its contract; the system prompt carries the idempotency guidance, the tool set exposes the three skills, and the broker holds the two enforced rules. The LLM proposes `apply-yaml-config` against the live CBM instance with a config that drops an entity field. The broker matches `no-destructive-migration-without-approval` (no approval flag, no verified backup) and returns `Deny`. The LLM receives the denial reason and responds by requesting an approval flag and a backup verification before retrying. The decision is recorded in `enforcement_event`.

---

## 11. Open Decisions & Dependencies

1. **Database engine (resolved).** Current engine is **SQLite**; **PostgreSQL** is the planned migration target. The schema is authored portably from one design; both engine migrations are maintained in parallel (`migration_v2_0_sqlite.sql`, `migration_v2_0_postgres.sql`) so the switch is a swap, not a rewrite. Type mappings: `TEXT`/`TEXT`, JSON-as-`TEXT` / `JSONB`, `INTEGER 0|1` / `BOOLEAN`, ISO-8601 `TEXT` / `TIMESTAMPTZ`.
2. **Propagation default (resolved §9, r0.2).** Float pure guidance, pin execution/constraint bindings.
3. **Agent authentication** — how a dispersed agent proves it may pull a given contract; `credential_ref` is a placeholder pending a separate design.
4. **Code-asset registry internals** — `code_asset_ref` assumes an external registry/locator for callables; its schema is out of scope here.
5. **Broker topology** — whether the broker is in-process with each agent or a shared service; affects latency and audit centralization.
6. **SQLite → Postgres data migration** — once V2 carries live catalog data, the engine switch needs a one-time data transfer (and JSON-text → JSONB cast) step; to be specified when the switch is scheduled.
7. **Versioned catalog tables (future enhancement).** True point-in-time pinning to a superseded skill/rule revision requires `skill_version` and `rule_version` tables. Until then, pinning is a drift assertion (§9). Adopt this if/when controlled rollback to prior catalog revisions becomes a requirement.

---

## Change Log

| Revision | Date (MM-DD-YY HH:MM) | Author | Summary |
|---|---|---|---|
| 0.1 | 05-31-26 16:00 | D. Bower / Claude | Initial draft: four-layer registry, hybrid governance, contract resolution, broker flow, predicate format, versioning, worked example. |
| 0.2 | 05-31-26 16:45 | D. Bower / Claude | Resolved engine (SQLite current, Postgres planned) and propagation policy (float guidance, pin execution/constraint bindings). Added SQLite→Postgres data-migration dependency. Companion artifacts: SQLite + Postgres DDL migrations, YAML seed. |
| 0.3 | 05-31-26 17:30 | D. Bower / Claude | Taxonomy simplified to two skill kinds (instruction, tool); `code_asset_ref` is now an optional attribute of any tool. Documented drift-assertion pinning semantics and added versioned-catalog future enhancement. Resolver + broker implemented. |
