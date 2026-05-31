-- =====================================================================
-- CRM Builder V2 — Agent Registry — DDL Migration (SQLite)
-- Spec: V2 Agent Registry Schema Specification r0.3
-- Migration: v2.0  |  Engine: SQLite (current)
-- Last Updated: 05-31-26 17:30
-- ---------------------------------------------------------------------
-- Notes:
--   * Foreign keys are NOT enforced by SQLite unless enabled per-connection.
--     The application MUST run:  PRAGMA foreign_keys = ON;
--   * JSON is stored as TEXT (validated in the application layer). On the
--     planned Postgres migration these columns become JSONB.
--   * BOOLEAN is stored as INTEGER 0|1 with a CHECK constraint.
--   * TIMESTAMP is stored as ISO-8601 TEXT (e.g. '2026-05-31T16:45:00Z').
--   * Enumerated values are enforced via CHECK constraints (no native ENUM).
--   * Run inside a single transaction.
-- =====================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- ---- bookkeeping ----------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_migration (
    migration_id  TEXT PRIMARY KEY,
    applied_at    TEXT NOT NULL,
    description   TEXT NOT NULL
);

-- ---- 1. agent -------------------------------------------------------
CREATE TABLE agent (
    agent_id            TEXT PRIMARY KEY,
    display_name        TEXT NOT NULL,
    description         TEXT NOT NULL,
    status              TEXT NOT NULL
                          CHECK (status IN ('draft','active','deprecated')),
    current_version_id  TEXT,
    credential_ref      TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

-- ---- 2. agent_version ----------------------------------------------
CREATE TABLE agent_version (
    version_id      TEXT PRIMARY KEY,
    agent_id        TEXT NOT NULL REFERENCES agent(agent_id),
    revision        TEXT NOT NULL,
    effective_date  TEXT NOT NULL,
    author          TEXT NOT NULL,
    changelog       TEXT NOT NULL,
    model_hint      TEXT,
    is_current      INTEGER NOT NULL DEFAULT 0
                      CHECK (is_current IN (0,1)),
    created_at      TEXT NOT NULL,
    UNIQUE (agent_id, revision)
);

-- exactly one current version per agent
CREATE UNIQUE INDEX ux_agent_version_current
    ON agent_version (agent_id)
    WHERE is_current = 1;

CREATE INDEX ix_agent_version_agent ON agent_version (agent_id);

-- deferred FK from agent.current_version_id is implicit via app logic
-- (SQLite cannot ALTER TABLE ADD CONSTRAINT; enforced in application layer).

-- ---- 3. skill -------------------------------------------------------
CREATE TABLE skill (
    skill_id        TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL,
    kind            TEXT NOT NULL
                      CHECK (kind IN ('instruction','tool')),
    io_contract     TEXT,            -- JSON Schema (JSONB in Postgres); tool only
    code_asset_ref  TEXT,            -- optional; set for code-backed tools
    category        TEXT,
    revision        TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- ---- 4. agent_skill -------------------------------------------------
CREATE TABLE agent_skill (
    agent_version_id  TEXT NOT NULL REFERENCES agent_version(version_id),
    skill_id          TEXT NOT NULL REFERENCES skill(skill_id),
    pinned_revision   TEXT,          -- NULL = float to latest
    scope             TEXT,          -- JSON (JSONB in Postgres)
    PRIMARY KEY (agent_version_id, skill_id)
);

CREATE INDEX ix_agent_skill_skill ON agent_skill (skill_id);

-- ---- 5. governance_rule --------------------------------------------
CREATE TABLE governance_rule (
    rule_id      TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    rule_type    TEXT NOT NULL
                   CHECK (rule_type IN ('permission','prohibition','constraint','escalation')),
    enforcement  TEXT NOT NULL
                   CHECK (enforcement IN ('advisory','enforced','enforced_with_override')),
    severity     TEXT NOT NULL
                   CHECK (severity IN ('info','warning','critical')),
    body         TEXT NOT NULL,
    predicate    TEXT,              -- JSON (JSONB in Postgres); required for enforced rules
    revision     TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

-- ---- 6. agent_governance -------------------------------------------
CREATE TABLE agent_governance (
    agent_version_id  TEXT NOT NULL REFERENCES agent_version(version_id),
    rule_id           TEXT NOT NULL REFERENCES governance_rule(rule_id),
    pinned_revision   TEXT,          -- NULL = float to latest
    override          TEXT,          -- JSON (JSONB in Postgres)
    PRIMARY KEY (agent_version_id, rule_id)
);

CREATE INDEX ix_agent_governance_rule ON agent_governance (rule_id);

-- ---- 7. audit_log ---------------------------------------------------
CREATE TABLE audit_log (
    audit_id      TEXT PRIMARY KEY,
    entity_type   TEXT NOT NULL
                    CHECK (entity_type IN ('agent','agent_version','skill','rule','binding')),
    entity_id     TEXT NOT NULL,
    action        TEXT NOT NULL
                    CHECK (action IN ('create','update','deprecate','bind','unbind')),
    actor         TEXT NOT NULL,
    diff          TEXT,              -- JSON (JSONB in Postgres)
    occurred_at   TEXT NOT NULL
);

CREATE INDEX ix_audit_entity ON audit_log (entity_type, entity_id);
CREATE INDEX ix_audit_time   ON audit_log (occurred_at);

-- ---- 8. enforcement_event ------------------------------------------
CREATE TABLE enforcement_event (
    event_id          TEXT PRIMARY KEY,
    agent_id          TEXT NOT NULL,
    agent_version_id  TEXT NOT NULL,
    rule_id           TEXT,
    tool_call         TEXT NOT NULL,  -- JSON (JSONB in Postgres)
    decision          TEXT NOT NULL
                        CHECK (decision IN ('allow','deny','override')),
    actor             TEXT,
    occurred_at       TEXT NOT NULL
);

CREATE INDEX ix_enforcement_agent_time ON enforcement_event (agent_id, occurred_at);

-- ---- record this migration -----------------------------------------
INSERT INTO schema_migration (migration_id, applied_at, description)
VALUES ('v2.0', '2026-05-31T16:45:00Z',
        'Initial agent registry: identity, capability, governance, audit.');

COMMIT;
