"""Prompt-submission hook: the first user prompt is the opening answer.

Implements REQ-575 (PI-488, DEC-1062), the second half of the two-hook session
opening. Registered as a Claude Code ``UserPromptSubmit`` hook, this module
runs when the user submits a prompt, before the model reads it. On the first
prompt of a session it takes the prompt as the **opening answer** (TERM-060),
calls the session-open operation (``POST /sessions/open``), and prints the
confirmation line, the follow-up question when the answer was not recognised,
and the first phase segment's rules — the phase profile's role text, its
instruction skills and the rules the cross-cutting set does not already
carry. Claude Code adds that text to the model's context, so the session
record exists and the phase rules are in force before the model acts. Later
prompts do nothing: the per-session marker written by ``session_context.py``
says the session is opened.

A pasted prompt file supplies its answer on a line beginning ``Opening
answer:`` (any case, colon or dash); when no line is marked, the first
non-empty line is the answer, with heading and bullet marks stripped.

When the operation cannot be reached the hook prints a notice, marks the
attempt so the next prompt is not mistaken for the answer, and names the
manual fallback: the model asks the question and calls the connector's
``open_session`` tool. The hook never blocks a prompt. Stdlib-only, like the
other two hooks.

**What the user sees (REQ-594 / PI-500, DEC-1080).** Plain text a
``UserPromptSubmit`` hook prints reaches the model only; Claude Code shows the
user none of it. So the hook answers in Claude Code's JSON hook output: the
rules go in ``hookSpecificOutput.additionalContext`` for the model, and the
line the user must be able to check — the confirmation line, the follow-up
question for an unrecognised answer, or the notice that the session could not
be opened — goes in ``systemMessage``, which Claude Code displays to the user
before the model replies.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crmbuilder_v2.session_context import (  # noqa: E402
    Caller,
    contract_rules,
    make_caller,
    read_marker,
    resolve_config,
    rule_line,
    slim_contract,
    write_marker,
)

OPEN_PATH = "/sessions/open"
MAX_ANSWER_CHARS = 300
_MARKED_LINE_RE = re.compile(
    r"^\s*(?:opening answer|what do you want to do today)\s*[:\-—]\s*(?P<answer>.+?)\s*$",
    re.IGNORECASE,
)
_LEADING_MARKS_RE = re.compile(r"^\s*(?:[#>*\-+]+\s*|\d+[.)]\s*)+")
_CROSS_CUTTING_SPLIT = "CROSS-CUTTING RULES — these apply in every phase segment."


# --- the opening answer ---------------------------------------------------------


def extract_opening_answer(prompt: str) -> str:
    """The opening answer in a prompt: the marked line, else the first line."""
    lines = [ln for ln in (prompt or "").splitlines() if ln.strip()]
    for ln in lines:
        m = _MARKED_LINE_RE.match(ln)
        if m:
            return " ".join(m.group("answer").split())[:MAX_ANSWER_CHARS]
    if not lines:
        return ""
    first = _LEADING_MARKS_RE.sub("", lines[0])
    return " ".join(first.split())[:MAX_ANSWER_CHARS]


# --- rendering -------------------------------------------------------------------


def _segment_prompt(contract: dict) -> str:
    """The segment's own role text and skills, without the cross-cutting tail."""
    text = contract.get("system_prompt") or ""
    if _CROSS_CUTTING_SPLIT in text:
        text = text.split(_CROSS_CUTTING_SPLIT, 1)[0]
    return text.strip()


def render_opened(result: dict, already_in_context: set[str]) -> str:
    session = result.get("session") or {}
    contract = result.get("contract") or {}
    rules = [r for r in contract_rules(contract) if r["identifier"] not in already_in_context]
    lines = [
        f"# Session opened — {session.get('session_identifier')} "
        f"(opening answer: \"{session.get('session_opening_answer') or ''}\")",
        "",
    ]
    if result.get("confirmation_line"):
        lines.append(result["confirmation_line"])
    elif result.get("first_line"):
        lines.append(result["first_line"])
    if contract.get("first_reply_instruction"):
        lines += ["", contract["first_reply_instruction"]]
    if result.get("follow_up_question"):
        lines += [
            "",
            "The answer matched no kind of work in the catalogue. Before doing anything "
            "else, ask the user this one question in their own words, then continue "
            f"with the answer they give: \"{result['follow_up_question']}\"",
        ]
        if result.get("planning_item"):
            pi = result["planning_item"]
            lines.append(
                f"The miss was recorded as planning item {pi.get('identifier')} so the "
                "catalogue can grow."
            )
    segment = result.get("segment")
    if segment:
        label = segment.get("label") or segment.get("area")
        lines += ["", f"Phase segment 1 of this session: **{label}** "
                  f"(profile {segment.get('profile') or 'pending'}, domain {segment.get('domain')}). "
                  "Advance to the next segment with the connector tool `advance_session_segment` "
                  f"on {session.get('session_identifier')} when this segment's work is done."]
    role = _segment_prompt(contract) if contract.get("segment_profile_id") else ""
    if role:
        lines += ["", "## Phase profile", "", role]
    lines += ["", f"## Rules for this segment ({len(rules)} beyond the cross-cutting set)", ""]
    lines += [rule_line(r) for r in rules] or ["- (none — the cross-cutting rules already in context apply)"]
    lines.append("")
    return "\n".join(lines)


def render_failure(answer: str, reason: str) -> str:
    return (
        "> **SESSION NOT OPENED — the session-open operation could not be reached** "
        f"({reason}). The opening answer was: \"{answer}\". No session record was "
        "written and no phase rules were loaded; the cross-cutting rules in context "
        "apply. Manual fallback: ask the user what they want to do today, then call "
        "the connector tool `open_session` with the answer and continue under the "
        "contract it returns.\n"
    )


def user_message_opened(result: dict) -> str:
    """The line the user sees when the operation answered (REQ-594).

    The operation's first line already carries the confirmation line, or the
    no-kind-of-work line with the follow-up question; the question is added when
    a caller supplied it separately.
    """
    session = result.get("session") or {}
    said = result.get("first_line") or result.get("confirmation_line") or ""
    question = result.get("follow_up_question")
    if question and question not in said:
        said = f"{said} {question}".strip()
    identifier = session.get("session_identifier")
    return f"Session {identifier} opened. {said}".strip() if identifier else said


def user_message_failure(reason: str) -> str:
    """The notice the user sees when the operation could not be reached."""
    return (
        f"Session not opened: the session-open operation could not be reached "
        f"({reason}). Only the cross-cutting rules are loaded. Ask Claude to open "
        "the session with the connector tool open_session."
    )


def hook_output(context: str, user_message: str) -> str:
    """Claude Code's JSON hook output: the rules for the model, a line for the user."""
    return json.dumps(
        {
            "systemMessage": user_message,
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context,
            },
        }
    )


# --- the hook ---------------------------------------------------------------------


def open_from_prompt(
    project_dir: Path,
    session_id: str | None,
    prompt: str,
    *,
    call: Caller | None = None,
    cwd: str | None = None,
) -> str:
    """Open the session for the first prompt; empty text for later prompts.

    Returns the text for the model's context; :func:`open_from_prompt_with_message`
    also returns the line shown to the user.
    """
    return open_from_prompt_with_message(
        project_dir, session_id, prompt, call=call, cwd=cwd
    )[0]


def open_from_prompt_with_message(
    project_dir: Path,
    session_id: str | None,
    prompt: str,
    *,
    call: Caller | None = None,
    cwd: str | None = None,
) -> tuple[str, str]:
    """Open the session for the first prompt.

    Returns ``(context, user_message)``: the text the model reads and the line
    the user sees. Both are empty for a later prompt.
    """
    marker = read_marker(project_dir, session_id) or {}
    if marker.get("session_identifier") or marker.get("open_failed_at"):
        return "", ""
    answer = extract_opening_answer(prompt)
    base, token, engagement = resolve_config(project_dir)
    metadata = {"claude_session_id": session_id, "cwd": cwd or str(project_dir)}
    body = {
        "opening_answer": answer,
        "medium": "claude_code",
        "medium_metadata": metadata,
    }
    project = os.environ.get("CRMBUILDER_V2_SESSION_PROJECT")
    if project:
        body["project_identifier"] = project
    try:
        call = call or make_caller(base, token, engagement)
        result = call("POST", OPEN_PATH, body)
        if not isinstance(result, dict) or not result.get("session"):
            raise RuntimeError("unexpected response shape")
    except Exception as exc:  # noqa: BLE001 — never block a prompt
        reason = " ".join(f"{type(exc).__name__}: {exc}".split())[:300]
        write_marker(
            project_dir,
            session_id,
            {**marker, "opened": False, "open_failed_at": datetime.now(UTC).isoformat(timespec="seconds"),
             "opening_answer": answer, "failure": reason},
        )
        return render_failure(answer, reason), user_message_failure(reason)
    session = result["session"]
    write_marker(
        project_dir,
        session_id,
        {
            **marker,
            "opened": True,
            "session_identifier": session.get("session_identifier"),
            "opening_answer": session.get("session_opening_answer"),
            "kind_of_work": result.get("kind_of_work"),
            "kind_of_work_name": result.get("kind_of_work_name"),
            "confirmation_line": result.get("confirmation_line"),
            "first_line": result.get("first_line"),
            "follow_up_question": result.get("follow_up_question"),
            "segment": result.get("segment"),
            "contract": slim_contract(result.get("contract")),
            "opened_at": datetime.now(UTC).isoformat(timespec="seconds"),
        },
    )
    return (
        render_opened(result, set(marker.get("cross_cutting_rule_ids") or [])),
        user_message_opened(result),
    )


def main(argv: list[str] | None = None) -> int:
    """Hook entry point. Always exits 0 — a prompt is never blocked."""
    argv = list(sys.argv[1:] if argv is None else argv)
    project_dir = Path(
        argv[0] if argv else os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    )
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    prompt = str(payload.get("prompt") or "")
    session_id = payload.get("session_id")
    try:
        text, message = open_from_prompt_with_message(
            project_dir, session_id, prompt, cwd=payload.get("cwd")
        )
    except Exception as exc:  # noqa: BLE001 — a hook defect must never block work
        sys.stderr.write(f"[session-open] internal error ({exc}) — continuing\n")
        return 0
    if text:
        # JSON so Claude Code shows the user the line to check (REQ-594) and
        # gives the model the rules; plain text would reach the model only.
        sys.stdout.write(hook_output(text, message))
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
