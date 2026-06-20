"""Smoke test for agent_runtime against the real V2 SQLite migration + seed."""
import json
import sqlite3
import sys

sys.path.insert(0, "/home/claude")
from agent_runtime import (
    connect, resolve_contract, Broker, ProposedCall, log_event, invoke_code_asset, Skill
)

DDL_PATH = "/mnt/user-data/outputs/migration_v2_0_sqlite.sql"
SEED_PATH = "/mnt/user-data/outputs/seed_v2_0_agent_registry.yaml"

NOW = "2026-05-31T17:30:00Z"


def build_db() -> sqlite3.Connection:
    conn = connect(":memory:")
    with open(DDL_PATH) as f:
        conn.executescript(f.read())
    return conn


def seed_from_yaml(conn, seed):
    # skills
    for s in seed["skills"]:
        conn.execute(
            "INSERT INTO skill (skill_id,name,description,kind,io_contract,"
            "code_asset_ref,category,revision,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (s["skill_id"], s["name"], s["description"], s["kind"],
             json.dumps(s["io_contract"]) if s.get("io_contract") else None,
             s.get("code_asset_ref"), s.get("category"), s["revision"], NOW, NOW),
        )
    # rules
    for r in seed["governance_rules"]:
        conn.execute(
            "INSERT INTO governance_rule (rule_id,name,rule_type,enforcement,"
            "severity,body,predicate,revision,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (r["rule_id"], r["name"], r["rule_type"], r["enforcement"],
             r["severity"], r["body"],
             json.dumps(r["predicate"]) if r.get("predicate") else None,
             r["revision"], NOW, NOW),
        )
    # agents + versions + bindings
    for a in seed["agents"]:
        conn.execute(
            "INSERT INTO agent (agent_id,display_name,description,status,"
            "current_version_id,credential_ref,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (a["agent_id"], a["display_name"], a["description"], a["status"],
             None, None, NOW, NOW),
        )
        v = a["version"]
        version_id = f"{a['agent_id']}@{v['revision']}"
        conn.execute(
            "INSERT INTO agent_version (version_id,agent_id,revision,effective_date,"
            "author,changelog,model_hint,is_current,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (version_id, a["agent_id"], v["revision"], v["effective_date"],
             v["author"], v["changelog"], v.get("model_hint"), 1, NOW),
        )
        conn.execute("UPDATE agent SET current_version_id=? WHERE agent_id=?",
                     (version_id, a["agent_id"]))
        for b in a.get("skills", []):
            conn.execute(
                "INSERT INTO agent_skill (agent_version_id,skill_id,pinned_revision,scope) "
                "VALUES (?,?,?,?)",
                (version_id, b["skill_id"], b.get("pinned_revision"), None),
            )
        for b in a.get("governance", []):
            conn.execute(
                "INSERT INTO agent_governance (agent_version_id,rule_id,pinned_revision,override) "
                "VALUES (?,?,?,?)",
                (version_id, b["rule_id"], b.get("pinned_revision"), None),
            )
    conn.commit()


def main():
    import yaml
    with open(SEED_PATH) as f:
        seed = yaml.safe_load(f)

    conn = build_db()
    seed_from_yaml(conn, seed)

    contract = resolve_contract(conn, "deployment-agent")
    print("=== CONTRACT: deployment-agent ===")
    print("revision:", contract.revision)
    print("tools:", [t["name"] for t in contract.tools])
    print("code-backed tools:", [t["name"] for t in contract.tools if t["code_backed"]])
    print("enforced rules:", [r.rule_id for r in contract.enforced_rules])
    print("warnings:", contract.warnings)
    print("\n--- system prompt ---")
    print(contract.system_prompt)
    print()

    broker = Broker(contract)

    scenarios = {
        "1. clean validated apply (staging)": ProposedCall(
            tool="apply-yaml-config",
            subjects={"deployment"}, operations={"apply"},
            context={"validated": True, "approval_flag": True,
                     "backup_verified": True, "environment": "staging"},
        ),
        "2. destructive apply, no approval/backup (staging)": ProposedCall(
            tool="apply-yaml-config",
            subjects={"deployment", "schema_migration", "target"},
            operations={"apply", "destructive", "mutate"},
            context={"validated": True, "approval_flag": False,
                     "backup_verified": False, "environment": "staging"},
        ),
        "3. mutate production (approved + backed up)": ProposedCall(
            tool="apply-yaml-config",
            subjects={"deployment", "target"}, operations={"apply", "mutate"},
            context={"validated": True, "approval_flag": True,
                     "backup_verified": True, "environment": "production"},
        ),
        "4. apply without validation (staging)": ProposedCall(
            tool="apply-yaml-config",
            subjects={"deployment"}, operations={"apply"},
            context={"validated": False, "approval_flag": True,
                     "backup_verified": True, "environment": "staging"},
        ),
    }

    print("=== BROKER DECISIONS ===")
    for label, call in scenarios.items():
        decision = broker.check(call)
        log_event(conn, contract, call, decision)
        print(f"{label}\n    -> {decision.outcome.upper()} :: {decision.reason()}")

    n_events = conn.execute("SELECT COUNT(*) FROM enforcement_event").fetchone()[0]
    print(f"\nenforcement_event rows logged: {n_events}")

    # demonstrate the code_asset_ref bridge with a stubbed loader
    apply_skill = Skill(skill_id="apply-yaml-config", name="x", description="x",
                        kind="tool", revision="1.0.0",
                        code_asset_ref="crmbuilder.deploy.apply_config:apply")

    class _Stub:
        def apply(self, **kw):
            return {"applied": True, "summary": f"stub applied to {kw.get('target')}"}

    result = invoke_code_asset(apply_skill, {"target": "cbm-staging"},
                               loader=lambda mp: _Stub())
    print("\ncode_asset_ref bridge (stub):", result)


if __name__ == "__main__":
    main()
