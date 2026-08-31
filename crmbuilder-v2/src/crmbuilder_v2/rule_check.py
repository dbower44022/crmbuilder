"""Pre-action rule check: the machine check behind an enforced governance rule.

Implements REQ-542 (PI-439, DEC-964). Registered as a Claude Code ``PreToolUse``
hook on the Bash tool, this module reads the pending command, fetches the
enforced governance rules whose audience includes a Claude Code session, and
evaluates each rule's check (TERM-044) against the command:

- ``forbidden_command`` — the command must not match ``pattern``.
- ``required_trailer`` — a ``git commit`` whose message is inline (``-m``, a
  heredoc, or ``-F /dev/stdin``) must carry ``<trailer>: <pattern>``; a commit
  whose message comes from elsewhere is left to the git ``commit-msg`` gate.
- ``protected_path`` — the command must not name a path matching ``pattern``.

A failing ``enforced`` rule denies the command with the rule named. A failing
``enforced_with_override`` rule is waved through only when the command carries
an override marker — ``GVR_OVERRIDE='GVR-NNN: <reason>'`` at its start — and
the waiver is recorded in the store (``POST
/governance-rules/{id}/enforcement-overrides``); if the store cannot take the
record it is appended to the git-tracked exemption log instead.

Rules are cached in a gitignored snapshot with a short TTL so the hook does not
call the API on every command; when the store is unreachable and no snapshot
exists the hook fails open with a warning — a check that cannot be read must
never silently block work. Stdlib-only, like ``session_context``.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crmbuilder_v2.session_context import (  # noqa: E402
    SESSION_AUDIENCES,
    Fetcher,
    _bound_rule_ids,
    make_fetcher,
    resolve_config,
)

ENFORCED_MODES: frozenset[str] = frozenset({"enforced", "enforced_with_override"})
SNAPSHOT_FILE = Path("crmbuilder-v2/data/rule-checks.snapshot.json")
EXEMPTION_LOG = Path("PRDs/product/crmbuilder-v2/governance-exemptions.log")
SNAPSHOT_TTL_SECONDS = 600
OVERRIDE_RE = re.compile(r"""GVR_OVERRIDE=(['"])(?P<rule>GVR-\d{3}):\s*(?P<reason>.+?)\1""")
# Command position only (start of text/line or after && ; |, with optional
# VAR=value prefixes) — a git invocation quoted inside a heredoc or a string is
# data, not a commit.
_GIT_COMMIT_RE = re.compile(
    r"(?:^|[;&|]\s*|\n\s*)(?:\w+=(?:'[^']*'|\"[^\"]*\"|\S+)\s+)*"
    r"git\b(?:\s+-\S+)*\s+commit\b",
    re.M,
)
_INLINE_MESSAGE_RE = re.compile(r"(?:\s-m\b|\s--message\b|<<|-F\s*/dev/stdin|--file[= ]/dev/stdin)")


# --- rules -------------------------------------------------------------------------


def select_enforced_rules(fetch: Fetcher) -> list[dict]:
    """Active enforced rules whose audience includes a Claude Code session."""
    rules = fetch("/governance-rules?status=active&resolution=effective")
    bound: set[str] | None = None
    selected = []
    for rule in rules:
        if rule.get("enforcement") not in ENFORCED_MODES:
            continue
        audience = rule.get("applies_to")
        if audience is not None:
            if audience in SESSION_AUDIENCES:
                selected.append(rule)
            continue
        if bound is None:
            bound = _bound_rule_ids(fetch)
        if rule["identifier"] not in bound:
            selected.append(rule)
    return sorted(selected, key=lambda r: r["identifier"])


def load_rules(project_dir: Path, fetch: Fetcher | None = None) -> tuple[list[dict], str]:
    """``(rules, source)`` — ``live`` / ``snapshot`` / ``none`` (fail open)."""
    snapshot = project_dir / SNAPSHOT_FILE
    if snapshot.is_file():
        try:
            saved = json.loads(snapshot.read_text(encoding="utf-8"))
            if time.time() - float(saved.get("fetched_at", 0)) < SNAPSHOT_TTL_SECONDS:
                return saved["rules"], "snapshot"
        except (ValueError, KeyError, OSError):
            pass
    try:
        base, token, engagement = resolve_config(project_dir)
        fetch = fetch or make_fetcher(base, token, engagement)
        rules = select_enforced_rules(fetch)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(
            json.dumps({"fetched_at": time.time(), "rules": rules}), encoding="utf-8"
        )
        return rules, "live"
    except Exception as exc:  # noqa: BLE001 — degrade, never crash the hook
        if snapshot.is_file():
            try:
                return json.loads(snapshot.read_text(encoding="utf-8"))["rules"], "snapshot"
            except (ValueError, KeyError, OSError):
                pass
        sys.stderr.write(f"[rule-check] store unreachable ({exc}); no snapshot — fail open\n")
        return [], "none"


# --- evaluation --------------------------------------------------------------------


def _violates(rule: dict, command: str) -> bool:
    check = rule.get("predicate") or {}
    kind, pattern = check.get("kind"), check.get("pattern")
    if not kind or not pattern:
        return False
    try:
        rx = re.compile(pattern, re.MULTILINE | re.DOTALL)
    except re.error:
        return False
    if kind in ("forbidden_command", "protected_path"):
        return rx.search(command) is not None
    if kind == "required_trailer":
        m = _GIT_COMMIT_RE.search(command)
        if not m or not _INLINE_MESSAGE_RE.search(command[m.start():]):
            return False
        trailer = re.escape(check.get("trailer") or "")
        return re.search(rf"^\s*{trailer}:\s*(?:{pattern})\s*$", command, re.M) is None
    return False


def evaluate(command: str, rules: list[dict]) -> list[dict]:
    """The rules ``command`` violates, in identifier order."""
    return [r for r in rules if _violates(r, command)]


def parse_override(command: str) -> tuple[str, str] | None:
    m = OVERRIDE_RE.search(command)
    return (m.group("rule"), m.group("reason").strip()) if m else None


def describe(rule: dict) -> str:
    check = rule.get("predicate") or {}
    message = check.get("message") or " ".join((rule.get("body") or "").split())[:240]
    return f"{rule['identifier']} [{rule.get('enforcement')}]: {message}"


# --- recording an override ---------------------------------------------------------


def record_override(
    project_dir: Path, rule_id: str, reason: str, command: str, session_ref: str | None
) -> str:
    """Store the waiver; fall back to the exemption log. Returns where it landed."""
    base, token, engagement = resolve_config(project_dir)
    try:
        req = urllib.request.Request(
            f"{base}/governance-rules/{rule_id}/enforcement-overrides",
            method="POST",
            data=json.dumps(
                {"reason": reason, "command": command[:2000], "session_ref": session_ref}
            ).encode(),
            headers={
                "Authorization": f"Bearer {token}",
                "X-Engagement": engagement,
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            envelope = json.loads(resp.read())
        if not envelope.get("errors"):
            return "store"
        detail = str(envelope["errors"])[:200]
    except Exception as exc:  # noqa: BLE001 — fall back to the git-tracked log
        detail = f"{type(exc).__name__}: {exc}"[:200]
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    line = f"{stamp}\toverride\t{rule_id}\t{reason}\t{' '.join(command.split())[:120]!r}\t{detail}\n"
    try:
        with open(project_dir / EXEMPTION_LOG, "a", encoding="utf-8") as fh:
            fh.write(line)
        return "exemption-log"
    except OSError:
        return "stderr"


# --- entry point ---------------------------------------------------------------------


def decide(project_dir: Path, command: str, session_ref: str | None, rules: list[dict]) -> dict | None:
    """``None`` to allow; a PreToolUse deny payload otherwise."""
    violated = evaluate(command, rules)
    if not violated:
        return None
    override = parse_override(command)
    blocking: list[dict] = []
    for rule in violated:
        if rule.get("enforcement") == "enforced_with_override" and override and override[0] == rule["identifier"]:
            where = record_override(project_dir, rule["identifier"], override[1], command, session_ref)
            sys.stderr.write(f"[rule-check] {rule['identifier']} waved through — reason recorded ({where})\n")
            continue
        blocking.append(rule)
    if not blocking:
        return None
    lines = [describe(r) for r in blocking]
    overridable = [r["identifier"] for r in blocking if r.get("enforcement") == "enforced_with_override"]
    hint = ""
    if overridable:
        hint = (
            f" To wave {', '.join(overridable)} through with a stated reason, prefix the command "
            f"with GVR_OVERRIDE='{overridable[0]}: <reason>' — the reason is recorded."
        )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "Blocked by governance rule check — " + "; ".join(lines) + hint,
        }
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    project_dir = Path(argv[0] if argv else os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        payload = {}
    command = str((payload.get("tool_input") or {}).get("command") or "")
    if not command:
        return 0
    try:
        rules, _source = load_rules(project_dir)
        verdict = decide(project_dir, command, payload.get("session_id"), rules)
    except Exception as exc:  # noqa: BLE001 — a hook defect must never block work
        sys.stderr.write(f"[rule-check] internal error ({exc}) — allowing\n")
        return 0
    if verdict is not None:
        sys.stdout.write(json.dumps(verdict))
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
