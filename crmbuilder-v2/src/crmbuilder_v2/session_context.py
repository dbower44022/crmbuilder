"""Session-start context: the cross-cutting rules, the opening question and
the preferences.

Implements REQ-540 (PI-437, DEC-962) and, since PI-488 (REQ-575, DEC-1062),
the first half of the two-hook session opening. A Claude Code ``SessionStart``
hook runs this module before the first prompt. It asks the store for the
session opening (``GET /sessions/opening``): the cross-cutting rules — the one
named set that loads whatever the phase — the opening question *What do you
want to do today?* with its examples, and the catalogue of kinds of work. It
prints those, plus the active preferences, as compact instruction text, and
writes a per-session marker file so the prompt-submission hook
(``session_open.py``) knows the session is not yet opened and the pre-command
check (``rule_check.py``) can read the enforced rules before the first prompt.
On a resumed session whose marker already names a session record, the stored
contract is printed again instead of the question.

A store whose API predates the opening endpoint (or is unreachable) falls back
to the flat audience query this module ran before PI-488: every active rule
addressed to a Claude Code session, so the transition is safe in both
directions.

Fallback (REQ-540): when the store cannot be reached, the last rendered snapshot
is printed instead under a visible banner that says it is a snapshot. The hook
never blocks a session — any failure degrades to the snapshot, or to a pointer at
the irreducible core in ``CLAUDE.md`` when no snapshot exists yet.

The module is **stdlib-only** on purpose so the hook runs with the system
``python3`` and no virtualenv activation. Audience selection is client-side until
the ``applies_to`` field lands (PI-438): a rule is a *session* rule when it is
bound to no agent profile. Once a rule record carries ``applies_to`` the field
wins, so the hook needs no change when PI-438 ships.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

#: Audience values that reach a Claude Code session (TERM-042 Audience).
SESSION_AUDIENCES: frozenset[str] = frozenset({"all", "claude_code"})
DEFAULT_ENGAGEMENT = "ENG-001"
ENV_FILE = Path("crmbuilder-v2/data/crmbuilder.env")
SNAPSHOT_FILE = Path("crmbuilder-v2/data/session-context.snapshot.md")
HTTP_TIMEOUT_SECONDS = 10

Fetcher = Callable[[str], list[dict]]
#: ``call(method, path, body) -> data`` against the V2 API envelope, any shape.
Caller = Callable[[str, str, dict | None], object]
#: Per-session markers written by the two opening hooks (gitignored).
MARKER_DIR = Path("crmbuilder-v2/data/session-open")
OPENING_PATH = "/sessions/opening"


# --- configuration ---------------------------------------------------------------


def load_env_file(path: Path) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines (comments and blanks skipped) from an env file."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def resolve_config(project_dir: Path) -> tuple[str, str, str]:
    """``(base_url, token, engagement)`` — env vars first, then the env file."""
    file_values = load_env_file(project_dir / ENV_FILE)
    base = os.environ.get("CRMBUILDER_V2_API_BASE_URL") or file_values.get(
        "CRMBUILDER_V2_API_BASE_URL", ""
    )
    token = os.environ.get("CRMBUILDER_V2_API_TOKEN") or file_values.get(
        "CRMBUILDER_V2_API_TOKEN", ""
    )
    engagement = (
        os.environ.get("CRMBUILDER_V2_SESSION_ENGAGEMENT")
        or file_values.get("CRMBUILDER_V2_SESSION_ENGAGEMENT")
        or DEFAULT_ENGAGEMENT
    )
    return base.rstrip("/"), token, engagement


def make_caller(base_url: str, token: str, engagement: str) -> Caller:
    """Return ``call(method, path, body) -> data`` against the V2 API envelope."""
    if not base_url:
        raise RuntimeError("no API base URL configured (CRMBUILDER_V2_API_BASE_URL)")

    def call(method: str, path: str, body: dict | None = None) -> object:
        req = urllib.request.Request(
            base_url + path,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Authorization": f"Bearer {token}",
                "X-Engagement": engagement,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            envelope = json.loads(resp.read())
        if envelope.get("errors"):
            raise RuntimeError(f"{path}: {envelope['errors']}")
        return envelope.get("data")

    return call


def make_fetcher(base_url: str, token: str, engagement: str) -> Fetcher:
    """Return ``fetch(path) -> data list`` against the V2 API envelope."""
    call = make_caller(base_url, token, engagement)

    def fetch(path: str) -> list[dict]:
        data = call("GET", path, None)
        if not isinstance(data, list):
            raise RuntimeError(f"{path}: unexpected envelope shape")
        return data

    return fetch


# --- per-session marker (shared by the three hooks) --------------------------------


def marker_path(project_dir: Path, session_id: str | None) -> Path | None:
    """Where this Claude Code session's opening marker lives, or ``None``."""
    if not session_id:
        return None
    safe = "".join(ch for ch in str(session_id) if ch.isalnum() or ch in "-_")[:80]
    return project_dir / MARKER_DIR / f"{safe or 'unknown'}.json" if safe else None


def read_marker(project_dir: Path, session_id: str | None) -> dict | None:
    path = marker_path(project_dir, session_id)
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    return data if isinstance(data, dict) else None


def write_marker(project_dir: Path, session_id: str | None, data: dict) -> Path | None:
    path = marker_path(project_dir, session_id)
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
    return path


def contract_rules(contract: dict | None) -> list[dict]:
    """Every rule in a resolved contract, advisory and enforced, sorted."""
    if not contract:
        return []
    rules = [
        {"identifier": r["identifier"], "body": r.get("body", ""), "enforcement": "advisory"}
        for r in contract.get("advisory_rules") or []
    ]
    rules += [
        {
            "identifier": r["identifier"],
            "body": r.get("body", ""),
            "enforcement": r.get("enforcement") or "enforced",
            "severity": r.get("severity"),
            "predicate": r.get("predicate"),
        }
        for r in contract.get("enforced_ruleset") or []
    ]
    return sorted(rules, key=lambda r: r["identifier"])


def slim_contract(contract: dict | None) -> dict:
    """The parts of a contract the marker keeps: profile ids and rules (with
    predicates, so the pre-command check can evaluate them offline)."""
    contract = contract or {}
    return {
        "profile_id": contract.get("profile_id"),
        "segment_profile_id": contract.get("segment_profile_id"),
        "cross_cutting_profile_id": contract.get("cross_cutting_profile_id"),
        "advisory_rules": [
            {"identifier": r["identifier"], "body": r.get("body", "")}
            for r in contract.get("advisory_rules") or []
        ],
        "enforced_ruleset": [
            {
                "identifier": r["identifier"],
                "body": r.get("body", ""),
                "enforcement": r.get("enforcement"),
                "severity": r.get("severity"),
                "predicate": r.get("predicate"),
            }
            for r in contract.get("enforced_ruleset") or []
        ],
        "version_stamp": contract.get("version_stamp"),
    }


# --- selection --------------------------------------------------------------------


def _bound_rule_ids(fetch: Fetcher) -> set[str]:
    """Identifiers of rules bound to an agent profile (the ADO population)."""
    edges = fetch("/references?target_type=governance_rule&limit=5000")
    return {
        e["target_id"]
        for e in edges
        if e.get("source_type") == "agent_profile"
        and e.get("target_type") == "governance_rule"
    }


def select_session_rules(fetch: Fetcher) -> list[dict]:
    """Active rules whose audience includes a Claude Code session.

    ``resolution=effective`` asks for the engagement-resolved view where the API
    supports it (REQ-529..533); an API that does not know the parameter ignores
    it and returns the stored rows, which is the same set while no engagement
    overrides exist.
    """
    rules = fetch("/governance-rules?status=active&resolution=effective")
    bound: set[str] | None = None
    selected = []
    for rule in rules:
        audience = rule.get("applies_to")
        if audience is not None:  # PI-438 field present: it decides
            if audience in SESSION_AUDIENCES:
                selected.append(rule)
            continue
        if bound is None:
            bound = _bound_rule_ids(fetch)
        if rule["identifier"] not in bound:
            selected.append(rule)
    return sorted(selected, key=lambda r: r["identifier"])


def select_preferences(fetch: Fetcher) -> list[dict]:
    """Active preferences whose ``applies_to`` reaches a Claude Code session."""
    prefs = fetch("/preferences?status=active")
    return sorted(
        (p for p in prefs if (p.get("applies_to") or "all") in SESSION_AUDIENCES),
        key=lambda p: p["identifier"],
    )


# --- rendering --------------------------------------------------------------------


def _one_line(text: str) -> str:
    return " ".join((text or "").split())


def rule_line(r: dict) -> str:
    tags = [r.get("enforcement") or "advisory"]
    if r.get("rule_type"):
        tags.append(str(r["rule_type"]))
    if r.get("severity"):
        tags.append(f"severity {r['severity']}")
    return f"- **{r['identifier']}** [{' · '.join(tags)}] {_one_line(r.get('body', ''))}"


def render_preferences(prefs: list[dict]) -> list[str]:
    lines = [f"## Preferences ({len(prefs)})", ""]
    for p in prefs:
        cat = p.get("category") or "preference"
        lines.append(f"- **{p['identifier']}** [{cat}] {_one_line(p.get('body', ''))}")
    return lines


def render_opening(
    opening: dict, prefs: list[dict], engagement: str, fetched_at: datetime
) -> str:
    """The session-start text when the session is not yet opened: the
    cross-cutting rules, the preferences, and the opening question."""
    cross = opening.get("cross_cutting") or {}
    rules = contract_rules(cross)
    examples = opening.get("examples") or []
    lines = [
        f"# CRMBuilder session context — {engagement}, read from the V2 store "
        f"at {fetched_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "These are the cross-cutting rules — the one named set that applies in every "
        "phase of every session (single source of truth: the database, GVR-238) — "
        "and the working-style preferences. Apply them as standing instructions. "
        "`enforced` rules have or will have a mechanical check; `advisory` rules are "
        "guidance you are expected to follow.",
        "",
        f"## Cross-cutting rules ({len(rules)})",
        "",
    ]
    if cross.get("missing_cross_cutting_profile"):
        lines.append("- (no cross-cutting profile exists in the store yet — proceed on the "
                     "CLAUDE.md 'Session bootstrap' core)")
    lines += [rule_line(r) for r in rules]
    lines += ["", *render_preferences(prefs), "", "## Opening the session", ""]
    lines.append(
        f"The session opens with one question: **{opening.get('question') or 'What do you want to do today?'}** "
        "The user's first prompt is taken as the opening answer: a hook classifies it "
        "into a kind of work from the catalogue, records the session, and places the "
        "phase rules for the first segment in context before you read the prompt. "
        "You do not need to ask the question yourself. If the first prompt is a "
        "pasted prompt file, a line beginning `Opening answer:` is the answer, else its "
        "first line."
    )
    if examples:
        lines += ["", "Examples of kinds of work: " + "; ".join(examples) + "."]
    lines += [
        "",
        "If a later message says the session-open operation could not be reached, "
        "the manual fallback applies: ask the user what they want to do today and call "
        "the connector tool `open_session` with the answer.",
        "",
        "## Read on demand",
        "",
        "- Governance recording method: topic TOP-013 and its children (`GET /topics/TOP-013`).",
        "- Procedural how-tos and gotchas: `GET /lessons?category=process` (and by `signal`).",
        "- Servers, dashboards, credential locations: `GET /reference-pointers?status=active`.",
        "",
    ]
    return "\n".join(lines)


def render_opened(marker: dict, prefs: list[dict], engagement: str) -> str:
    """The session-start text on a resumed session that is already opened."""
    contract = marker.get("contract") or {}
    rules = contract_rules(contract)
    lines = [
        f"# CRMBuilder session context — {engagement}, resumed session "
        f"{marker.get('session_identifier')}",
        "",
        f"This session was opened with the answer: \"{marker.get('opening_answer') or ''}\".",
    ]
    if marker.get("confirmation_line"):
        lines.append(marker["confirmation_line"])
    if marker.get("first_line") and marker.get("first_line") != marker.get("confirmation_line"):
        lines.append(marker["first_line"])
    lines += ["", f"## Rules in force ({len(rules)})", ""]
    lines += [rule_line(r) for r in rules]
    lines += ["", *render_preferences(prefs), ""]
    return "\n".join(lines)


def render(
    rules: list[dict], prefs: list[dict], engagement: str, fetched_at: datetime
) -> str:
    """Compact instruction text for the session context."""
    lines = [
        f"# CRMBuilder session context — {engagement}, read from the V2 store "
        f"at {fetched_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "These are the binding operating rules and working-style preferences for this "
        "session (single source of truth: the database, GVR-238). Apply them as "
        "standing instructions. `enforced` rules have or will have a mechanical check; "
        "`advisory` rules are guidance you are expected to follow.",
        "",
        f"## Governance rules ({len(rules)})",
        "",
    ]
    lines += [rule_line(r) for r in rules]
    lines += ["", *render_preferences(prefs)]
    lines += [
        "",
        "## Read on demand",
        "",
        "- Governance recording method: topic TOP-013 and its children (`GET /topics/TOP-013`).",
        "- Procedural how-tos and gotchas: `GET /lessons?category=process` (and by `signal`).",
        "- Servers, dashboards, credential locations: `GET /reference-pointers?status=active`.",
        "",
    ]
    return "\n".join(lines)


# --- entry point ------------------------------------------------------------------


def build_context(
    project_dir: Path,
    fetch: Fetcher | None = None,
    *,
    call: Caller | None = None,
    session_id: str | None = None,
) -> str:
    """Fetch, render and refresh the snapshot; raise on any failure.

    Preferred path (PI-488): ``GET /sessions/opening`` gives the cross-cutting
    contract and the opening question; the marker for ``session_id`` is
    written with that contract and ``opened: false`` so the prompt-submission
    hook opens the session on the first prompt. A marker that already names a
    session record (a resumed session) is rendered as-is. When the opening
    endpoint is unavailable the flat audience query is used instead.
    """
    base, token, engagement = resolve_config(project_dir)
    if call is None and fetch is None:
        call = make_caller(base, token, engagement)
    fetch = fetch or make_fetcher(base, token, engagement)
    prefs = select_preferences(fetch)

    marker = read_marker(project_dir, session_id)
    if marker and marker.get("session_identifier"):
        text = render_opened(marker, prefs, engagement)
    else:
        opening: dict | None = None
        if call is not None:
            try:
                data = call("GET", OPENING_PATH, None)
                opening = data if isinstance(data, dict) and "question" in data else None
            except Exception as exc:  # noqa: BLE001 — an older API: fall back
                sys.stderr.write(f"[session-context] opening unavailable ({exc}); flat rules\n")
        if opening is not None:
            text = render_opening(opening, prefs, engagement, datetime.now(UTC))
            write_marker(
                project_dir,
                session_id,
                {
                    "claude_session_id": session_id,
                    "opened": False,
                    "session_identifier": None,
                    "engagement": engagement,
                    "question": opening.get("question"),
                    "examples": opening.get("examples") or [],
                    "contract": slim_contract(opening.get("cross_cutting")),
                    "cross_cutting_rule_ids": [
                        r["identifier"] for r in contract_rules(opening.get("cross_cutting"))
                    ],
                    "written_at": datetime.now(UTC).isoformat(timespec="seconds"),
                },
            )
        else:
            rules = select_session_rules(fetch)
            text = render(rules, prefs, engagement, datetime.now(UTC))
    snapshot = project_dir / SNAPSHOT_FILE
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(text, encoding="utf-8")
    return text


def fallback_context(project_dir: Path, error: Exception) -> str:
    """The snapshot under a banner, or the CLAUDE.md core pointer if none exists."""
    snapshot = project_dir / SNAPSHOT_FILE
    reason = _one_line(f"{type(error).__name__}: {error}")[:300]
    if snapshot.is_file():
        saved = datetime.fromtimestamp(snapshot.stat().st_mtime, UTC)
        banner = (
            "> **SNAPSHOT — the V2 store was unreachable at session start** "
            f"({reason}). What follows is the context saved on "
            f"{saved.strftime('%Y-%m-%d %H:%M UTC')}; it may be behind the live "
            "rulebook. Reconcile with the store once reachable.\n\n"
        )
        return banner + snapshot.read_text(encoding="utf-8")
    return (
        "> **NO SESSION CONTEXT — the V2 store was unreachable at session start** "
        f"({reason}) and no snapshot has been saved yet. Proceed on the irreducible "
        "core in the CLAUDE.md 'Session bootstrap' section and reconcile with the "
        "store once reachable.\n"
    )


def main(argv: list[str] | None = None) -> int:
    """Hook entry point. Always exits 0 — a session must never be blocked."""
    argv = list(sys.argv[1:] if argv is None else argv)
    project_dir = Path(
        argv[0] if argv else os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    )
    # Claude Code passes hook metadata on stdin: the session id keys the
    # per-session marker the prompt-submission hook reads.
    session_id = None
    if not sys.stdin.isatty():
        try:
            payload = json.loads(sys.stdin.read() or "{}")
            session_id = payload.get("session_id") if isinstance(payload, dict) else None
        except (OSError, ValueError):
            session_id = None
    try:
        text = build_context(project_dir, session_id=session_id)
    except Exception as exc:  # noqa: BLE001 — every failure degrades, none blocks
        text = fallback_context(project_dir, exc)
    sys.stdout.write(text)
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
