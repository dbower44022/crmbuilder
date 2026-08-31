"""Session-start context: the effective governance rules and preferences.

Implements REQ-540 (PI-437, DEC-962): a Claude Code ``SessionStart`` hook runs
this module before the first prompt. It fetches the governance rules whose
audience includes a Claude Code session, plus the active preferences, from the
V2 store and prints them as compact instruction text, which Claude Code adds to
the session's context. Every session therefore starts with the same rules
without relying on the session to do the bootstrap read itself.

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


def make_fetcher(base_url: str, token: str, engagement: str) -> Fetcher:
    """Return ``fetch(path) -> data list`` against the V2 API envelope."""
    if not base_url:
        raise RuntimeError("no API base URL configured (CRMBUILDER_V2_API_BASE_URL)")

    def fetch(path: str) -> list[dict]:
        req = urllib.request.Request(
            base_url + path,
            headers={
                "Authorization": f"Bearer {token}",
                "X-Engagement": engagement,
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            envelope = json.loads(resp.read())
        if envelope.get("errors"):
            raise RuntimeError(f"{path}: {envelope['errors']}")
        data = envelope.get("data")
        if not isinstance(data, list):
            raise RuntimeError(f"{path}: unexpected envelope shape")
        return data

    return fetch


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
    for r in rules:
        tags = [r.get("enforcement") or "advisory"]
        if r.get("rule_type"):
            tags.append(str(r["rule_type"]))
        if r.get("severity"):
            tags.append(f"severity {r['severity']}")
        lines.append(f"- **{r['identifier']}** [{' · '.join(tags)}] {_one_line(r['body'])}")
    lines += ["", f"## Preferences ({len(prefs)})", ""]
    for p in prefs:
        cat = p.get("category") or "preference"
        lines.append(f"- **{p['identifier']}** [{cat}] {_one_line(p.get('body', ''))}")
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


def build_context(project_dir: Path, fetch: Fetcher | None = None) -> str:
    """Fetch, render and refresh the snapshot; raise on any failure."""
    base, token, engagement = resolve_config(project_dir)
    fetch = fetch or make_fetcher(base, token, engagement)
    rules = select_session_rules(fetch)
    prefs = select_preferences(fetch)
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
    # Claude Code passes hook metadata on stdin; it is not needed here but the
    # pipe is drained so the harness never blocks on an unread stream.
    if not sys.stdin.isatty():
        try:
            sys.stdin.read()
        except OSError:
            pass
    try:
        text = build_context(project_dir)
    except Exception as exc:  # noqa: BLE001 — every failure degrades, none blocks
        text = fallback_context(project_dir, exc)
    sys.stdout.write(text)
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
