"""
CRM Builder V2 — Agent Registry — Resolver & Enforcement Broker (SQLite)
=========================================================================
Spec:  V2 Agent Registry Schema Specification r0.3
Engine: SQLite (current). The code uses only stdlib and the portable column
        types from the SQLite migration; the contract returned is engine-agnostic.
Last Updated: 05-31-26 17:30

Two responsibilities:

  resolve_contract(conn, agent_id) -> Contract
      Turns an agent_id into its effective contract: composed system prompt,
      tool set, enforced ruleset, revision stamp, and any stale-pin warnings.

  Broker.check(call) -> Decision
      Evaluates a proposed tool call against the contract's enforced rules and
      returns allow / deny / override. log_event() persists the decision.

Pinning note (see spec §9): the catalog stores one row per skill/rule with its
current revision, so pinning is a *drift assertion*. A floating binding always
adopts the current row; a pinned binding adopts it too but is flagged stale if
the catalog revision has moved past the pinned value.
"""

from __future__ import annotations

import ast
import json
import importlib
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Skill:
    skill_id: str
    name: str
    description: str
    kind: str                       # 'instruction' | 'tool'
    revision: str
    io_contract: Optional[dict] = None
    code_asset_ref: Optional[str] = None

    @property
    def is_code_backed(self) -> bool:
        return self.kind == "tool" and bool(self.code_asset_ref)


@dataclass
class Rule:
    rule_id: str
    name: str
    rule_type: str
    enforcement: str                # 'advisory' | 'enforced' | 'enforced_with_override'
    severity: str                   # 'info' | 'warning' | 'critical'
    body: str
    revision: str
    predicate: Optional[dict] = None


@dataclass
class Contract:
    agent_id: str
    revision: str                   # the agent_version revision the contract was built from
    system_prompt: str
    tools: list[dict]               # tool definitions for the LLM
    enforced_rules: list[Rule]      # handed to the broker
    warnings: list[str] = field(default_factory=list)


@dataclass
class ProposedCall:
    """A tool call the LLM wants to make, mapped into rule-evaluable terms.

    The agent harness builds this from the raw tool call. `subjects` and
    `operations` are the *sets* of descriptors the call satisfies, so a single
    call can be matched by rules written at different granularities (e.g. a
    destructive apply to production is at once a 'deployment'/'apply',
    'schema_migration'/'destructive', and 'target'/'mutate').
    """
    tool: str
    subjects: set[str] = field(default_factory=set)
    operations: set[str] = field(default_factory=set)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class Decision:
    outcome: str                    # 'allow' | 'deny' | 'override'
    rules: list[Rule] = field(default_factory=list)

    def reason(self) -> str:
        if self.outcome == "allow":
            return "Allowed: no enforced rule blocked this call."
        verb = "Denied" if self.outcome == "deny" else "Blocked pending override"
        fired = "; ".join(f"{r.rule_id} ({r.severity})" for r in self.rules)
        return f"{verb} by: {fired}"


SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _json(value: Optional[str]) -> Optional[Any]:
    """Parse a JSON-as-TEXT column; tolerate NULL and already-decoded values."""
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

def resolve_contract(conn: sqlite3.Connection, agent_id: str) -> Contract:
    agent = conn.execute(
        "SELECT * FROM agent WHERE agent_id = ?", (agent_id,)
    ).fetchone()
    if agent is None:
        raise LookupError(f"Unknown agent: {agent_id!r}")
    if agent["status"] != "active":
        raise ValueError(f"Agent {agent_id!r} is not active (status={agent['status']}).")

    version = conn.execute(
        "SELECT * FROM agent_version WHERE agent_id = ? AND is_current = 1",
        (agent_id,),
    ).fetchone()
    if version is None:
        raise ValueError(f"Agent {agent_id!r} has no current version.")

    warnings: list[str] = []
    skills = _resolve_skills(conn, version["version_id"], warnings)
    rules = _resolve_rules(conn, version["version_id"], warnings)

    instruction_skills = [s for s in skills if s.kind == "instruction"]
    tool_skills = [s for s in skills if s.kind == "tool"]
    advisory = [r for r in rules if r.enforcement == "advisory"]
    enforced = [r for r in rules if r.enforcement != "advisory"]

    return Contract(
        agent_id=agent_id,
        revision=version["revision"],
        system_prompt=_compose_prompt(agent["description"], instruction_skills, advisory),
        tools=[_to_tool_def(s) for s in tool_skills],
        enforced_rules=enforced,
        warnings=warnings,
    )


def _resolve_skills(conn, version_id: str, warnings: list[str]) -> list[Skill]:
    rows = conn.execute(
        """
        SELECT s.*, b.pinned_revision
        FROM agent_skill b
        JOIN skill s ON s.skill_id = b.skill_id
        WHERE b.agent_version_id = ?
        """,
        (version_id,),
    ).fetchall()
    skills = []
    for r in rows:
        pinned = r["pinned_revision"]
        if pinned is not None and pinned != r["revision"]:
            warnings.append(
                f"skill '{r['skill_id']}' pinned to {pinned} but catalog is at "
                f"{r['revision']}; binding is stale and will not auto-adopt."
            )
        skills.append(Skill(
            skill_id=r["skill_id"],
            name=r["name"],
            description=r["description"],
            kind=r["kind"],
            revision=r["revision"],
            io_contract=_json(r["io_contract"]),
            code_asset_ref=r["code_asset_ref"],
        ))
    return skills


def _resolve_rules(conn, version_id: str, warnings: list[str]) -> list[Rule]:
    rows = conn.execute(
        """
        SELECT g.*, b.pinned_revision
        FROM agent_governance b
        JOIN governance_rule g ON g.rule_id = b.rule_id
        WHERE b.agent_version_id = ?
        """,
        (version_id,),
    ).fetchall()
    rules = []
    for r in rows:
        pinned = r["pinned_revision"]
        if pinned is not None and pinned != r["revision"]:
            warnings.append(
                f"rule '{r['rule_id']}' pinned to {pinned} but catalog is at "
                f"{r['revision']}; binding is stale and will not auto-adopt."
            )
        rules.append(Rule(
            rule_id=r["rule_id"],
            name=r["name"],
            rule_type=r["rule_type"],
            enforcement=r["enforcement"],
            severity=r["severity"],
            body=r["body"],
            revision=r["revision"],
            predicate=_json(r["predicate"]),
        ))
    return rules


def _compose_prompt(base: str, instruction_skills: list[Skill], advisory: list[Rule]) -> str:
    parts = [base.strip()]
    if instruction_skills:
        parts.append("## Operating guidance\n" + "\n".join(
            f"- {s.description}" for s in instruction_skills
        ))
    if advisory:
        ordered = sorted(advisory, key=lambda r: SEVERITY_ORDER.get(r.severity, 9))
        parts.append("## Advisory rules\n" + "\n".join(
            f"- [{r.severity}] {r.body}" for r in ordered
        ))
    return "\n\n".join(parts)


def _to_tool_def(skill: Skill) -> dict:
    return {
        "name": skill.skill_id,
        "description": skill.description,
        "input_schema": (skill.io_contract or {}).get("input"),
        "code_backed": skill.is_code_backed,
        "code_asset_ref": skill.code_asset_ref,
    }


# ---------------------------------------------------------------------------
# Predicate evaluation (safe; no eval)
# ---------------------------------------------------------------------------

_WORD_SUBS = (("OR", "or"), ("AND", "and"), ("NOT", "not"),
              ("true", "True"), ("false", "False"), ("null", "None"))

_ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
    ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.Name, ast.Load, ast.Constant,
)


def _normalize(condition: str) -> str:
    import re
    out = condition
    for src, dst in _WORD_SUBS:
        out = re.sub(rf"\b{src}\b", dst, out)
    return out


def _safe_eval(condition: str, context: dict[str, Any]) -> bool:
    """Evaluate a predicate condition against a context dict.

    Only boolean ops, comparisons, names, and literals are permitted. Unknown
    names resolve to None, which makes absence fail-safe for guard conditions
    (e.g. 'approval_flag != true' is True when approval_flag is missing).
    """
    tree = ast.parse(_normalize(condition), mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"Disallowed expression element: {type(node).__name__}")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.BoolOp):
            vals = [ev(v) for v in node.values]
            return all(vals) if isinstance(node.op, ast.And) else any(vals)
        if isinstance(node, ast.UnaryOp):      # only Not is allowed
            return not ev(node.operand)
        if isinstance(node, ast.Compare):
            left = ev(node.left)
            for op, comp in zip(node.ops, node.comparators):
                right = ev(comp)
                if not _compare(op, left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.Name):
            return context.get(node.id)
        if isinstance(node, ast.Constant):
            return node.value
        raise ValueError(f"Unhandled node: {type(node).__name__}")

    return bool(ev(tree))


def _compare(op, left, right) -> bool:
    if isinstance(op, ast.Eq):    return left == right
    if isinstance(op, ast.NotEq): return left != right
    # ordering comparisons: None is treated as "unknown" -> non-matching
    if left is None or right is None:
        return False
    if isinstance(op, ast.Lt):  return left < right
    if isinstance(op, ast.LtE): return left <= right
    if isinstance(op, ast.Gt):  return left > right
    if isinstance(op, ast.GtE): return left >= right
    raise ValueError("Unsupported comparison operator")


def predicate_matches(predicate: dict, call: ProposedCall) -> bool:
    subj = predicate.get("subject")
    op = predicate.get("operation")
    if subj not in (None, "*") and subj not in call.subjects:
        return False
    if op not in (None, "*") and op not in call.operations:
        return False
    condition = predicate.get("condition")
    if not condition:
        return True
    return _safe_eval(condition, call.context)


# ---------------------------------------------------------------------------
# Broker
# ---------------------------------------------------------------------------

class Broker:
    def __init__(self, contract: Contract):
        self.contract = contract

    def check(self, call: ProposedCall) -> Decision:
        denies, overrides = [], []
        for rule in self.contract.enforced_rules:
            if rule.predicate and predicate_matches(rule.predicate, call):
                if rule.enforcement == "enforced":
                    denies.append(rule)
                else:  # enforced_with_override
                    overrides.append(rule)
        key = lambda r: SEVERITY_ORDER.get(r.severity, 9)
        if denies:
            return Decision("deny", sorted(denies, key=key))
        if overrides:
            return Decision("override", sorted(overrides, key=key))
        return Decision("allow", [])


def log_event(conn: sqlite3.Connection, contract: Contract,
              call: ProposedCall, decision: Decision) -> None:
    conn.execute(
        """
        INSERT INTO enforcement_event
            (event_id, agent_id, agent_version_id, rule_id, tool_call,
             decision, actor, occurred_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            contract.agent_id,
            contract.revision,
            decision.rules[0].rule_id if decision.rules else None,
            json.dumps({"tool": call.tool, "subjects": sorted(call.subjects),
                        "operations": sorted(call.operations), "context": call.context}),
            decision.outcome,
            None,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Code-asset invocation (the code_asset_ref bridge)
# ---------------------------------------------------------------------------

def invoke_code_asset(skill: Skill, arguments: dict, *,
                      loader: Callable[[str], Any] = importlib.import_module) -> Any:
    """Resolve a code-backed tool's `module.path:callable` ref and call it."""
    if not skill.is_code_backed:
        raise ValueError(f"Skill {skill.skill_id!r} is not code-backed.")
    module_path, _, attr = skill.code_asset_ref.partition(":")
    if not attr:
        raise ValueError(f"Malformed code_asset_ref: {skill.code_asset_ref!r}")
    fn = getattr(loader(module_path), attr)
    return fn(**arguments)
