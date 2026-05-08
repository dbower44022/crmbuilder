#!/usr/bin/env python3
"""Apply DEC-025 and clean up conversation_reference on SES-001/002/004/005.

Run with the storage API live at http://127.0.0.1:8765 (start it via
`uv run crmbuilder-v2-api` in another terminal first).

After this script completes successfully, inspect the db-export/ diff
and commit the snapshot updates with the message in the trailing
comment block of this file.
"""
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8765"


def _request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw": body}
        return e.code, payload


# ---------------------------------------------------------------------------
# DEC-025 body
# ---------------------------------------------------------------------------

DEC_025 = {
    "identifier": "DEC-025",
    "title": "Defer per-conversation transcript capture from Claude.ai",
    "decision_date": "05-09-26",
    "status": "Active",
    "context": (
        "v2 session records carry a `conversation_reference` field intended to "
        "point at the actual conversation that produced the artifacts attributed "
        "to that session. Several existing records carry placeholder text "
        "(\"Claude.ai session (transcript preserved separately if needed)\") "
        "that fulfills neither the literal promise (no transcript is preserved) "
        "nor the practical need (no way to find the conversation later). The "
        "v2-ui workstream surfaced this gap, and an extended discussion considered "
        "options for making `conversation_reference` actually resolvable: live URLs "
        "to Claude.ai conversations, manually-committed transcript files, "
        "browser-extension or browser-console export tooling combined with a commit "
        "script, and the account-wide bulk export. Each option carries different "
        "operational and durability properties, and none is fully automatic."
    ),
    "decision": (
        "Per-conversation transcript capture from Claude.ai is deferred. v2 "
        "governance records do not require committed transcripts as a referencable "
        "artifact. The `conversation_reference` field carries descriptive text "
        "identifying the conversation by its outputs — deliverables, prompts, and "
        "decisions produced. The seed prompt of each conversation is captured "
        "verbatim in the corresponding session record's `topics_covered` field. "
        "Deliverables — PRDs, decision records, execution prompts, and the session "
        "summary itself — are treated as the durable governance record."
    ),
    "rationale": (
        "1. Anthropic does not currently expose a per-conversation API or webhook "
        "for Claude.ai. No fully-automatic capture path exists.\n\n"
        "2. All available capture paths (manual copy/paste, browser extension, "
        "browser console script, account-wide bulk export) require human discipline "
        "at the per-conversation level. A process whose reliability depends on "
        "remembering to take an action, every time, after a conversation ends, "
        "predictably fails.\n\n"
        "3. A capture process that \"mostly works\" produces a partial archive — "
        "some conversations have transcripts, others don't. Partial archives mislead "
        "worse than absent archives, because they imply a record exists that does "
        "not.\n\n"
        "4. The substantive reasoning that would be in a transcript is largely "
        "already captured by other v2 governance artifacts. Decision records carry "
        "full `context`, `rationale`, `alternatives_considered`, and `consequences` "
        "fields. Execution prompts enumerate implementation choices and out-of-slice "
        "notes. PRDs capture intent and acceptance criteria. Session summaries cover "
        "topics and deliverables. The marginal value of a transcript over those "
        "artifacts — preserving clarifying questions, the order of architectural "
        "exploration, the texture of back-and-forth — is real but does not justify "
        "the operational cost given current tooling.\n\n"
        "5. The account-wide bulk export from Settings → Privacy remains available "
        "as a one-time retrieval mechanism if a specific conversation is needed "
        "later for audit, dispute resolution, or methodology study. The backstop is "
        "preserved without per-conversation overhead."
    ),
    "alternatives_considered": (
        "- Direct URL to a live Claude.ai conversation in `conversation_reference`. "
        "Rejected — URLs are private (only the conversation owner can resolve when "
        "logged in), ephemeral (broken if the conversation is deleted), and mutable "
        "(Claude.ai allows editing or deleting messages after the fact). Insufficient "
        "durability for a governance record.\n\n"
        "- Manual transcript export with file commit. Rejected — too many manual "
        "steps per conversation (export, locate the downloaded file, redact sensitive "
        "content, rename to the convention, place at the convention path, commit, "
        "push). Predicted to decay silently.\n\n"
        "- Browser extension for one-click export plus a small commit script. "
        "Rejected — reduces but does not eliminate operational friction; still "
        "requires remembering to run the export and the commit after every "
        "conversation; introduces third-party code with broad page access in "
        "Claude.ai.\n\n"
        "- Browser console script or bookmarklet for one-click export plus a commit "
        "script. Rejected — comparable friction to the extension path with "
        "marginally better security posture from auditable JavaScript. Still "
        "operationally untenable per (2) above.\n\n"
        "- Account-wide bulk export as the routine archive mechanism. Rejected as a "
        "primary record path — full-account ZIPs delivered by email link with "
        "24-hour validity are heavy-handed for per-session governance. Retained as "
        "a backstop for one-off retrieval when needed."
    ),
    "consequences": (
        "1. `conversation_reference` fields on session records carry descriptive "
        "text per a documented convention rather than transcript file paths. "
        "Existing records with placeholder or incomplete text (SES-001 — Initial "
        "Planning; SES-002 — Pacing planning; SES-004 — UI v0.1 planning; SES-005 — "
        "UI v0.1 build) receive cleanup updates to follow the new convention.\n\n"
        "2. Going forward, every new session record's `topics_covered` field opens "
        "with the seed prompt of the conversation, rendered verbatim. This "
        "preserves original intent without requiring any transcript work.\n\n"
        "3. Decision records, execution prompts, and PRDs become the unambiguous "
        "durable governance record. Session records function as index entries, not "
        "full archives.\n\n"
        "4. This decision is revisitable. If Anthropic ships a per-conversation "
        "export API or webhook, or if browser-side automation becomes durable enough "
        "to be reliable (for example, via first-party Claude Code integration or "
        "some other Anthropic-supported mechanism), DEC-025 should be reconsidered "
        "for a v0.2 update."
    ),
}


# ---------------------------------------------------------------------------
# Session conversation_reference cleanups
# ---------------------------------------------------------------------------

SES_004_SEED_PROMPT = (
    "Please review the API created and create a plan for Claude to develop a UI "
    "in Python and Pysides6 to allow local users to interact with the API and "
    "view information and make changes to the data."
)

# Preserves the existing seven-question summary; seed prompt prepended.
SES_004_TOPICS_NEW = (
    f'Seed prompt: "{SES_004_SEED_PROMPT}"\n\n'
    "Seven architectural questions for the v2 desktop UI: (1) standalone PySide6 "
    "application versus a new tab embedded in the v1 PySide6 application; "
    "(2) transport choice — REST API over HTTP versus direct in-process imports "
    "of the access layer; (3) v0.1 scope boundary — read-only across all "
    "governance entities versus a broader CRUD surface, with full create/read/"
    "update/delete reserved for decisions only; (4) screen layout — sidebar "
    "navigation with master/detail panes versus top-tab and dashboard "
    "alternatives; (5) refresh strategy — file-watching the db-export/ snapshot "
    "directory as the change signal, with a manual Refresh button as fallback, "
    "in preference to polling or push; (6) server lifecycle — detect-then-launch "
    "QProcess management of the API subprocess so the UI cooperates with "
    "externally-launched API instances; (7) styling — native Qt look with a "
    "minimal QSS accent stub for v0.1, with a real designed pass deferred to v0.2."
)

PATCHES = [
    (
        "SES-001",
        {
            "conversation_reference": (
                "Original v2 bootstrap conversation in Claude.ai (no transcript "
                "preserved per DEC-025; produced charter v1, status v1, DEC-001 "
                "through DEC-005, and SES-001 itself)."
            ),
        },
    ),
    (
        "SES-002",
        {
            "conversation_reference": (
                "Original v2 pacing-planning conversation in Claude.ai (no transcript "
                "preserved per DEC-025; produced the pacing planning dimension and "
                "the corresponding status update)."
            ),
        },
    ),
    (
        "SES-004",
        {
            "conversation_reference": (
                "Claude.ai planning conversation that produced ui-PRD-v0.1.md, "
                "ui-implementation-plan.md, and CLAUDE-CODE-PROMPT-v2-ui-A through H "
                "under PRDs/product/crmbuilder-v2/. No transcript preserved per "
                "DEC-025."
            ),
            "topics_covered": SES_004_TOPICS_NEW,
        },
    ),
    (
        "SES-005",
        {
            "conversation_reference": (
                "Claude Code execution of CLAUDE-CODE-PROMPT-v2-ui-A through "
                "CLAUDE-CODE-PROMPT-v2-ui-H under PRDs/product/crmbuilder-v2/prompts/. "
                "No Claude.ai transcript applies per DEC-025."
            ),
        },
    ),
]


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 70)
    print("Step 1 — POST /decisions for DEC-025")
    print("=" * 70)
    code, payload = _request("POST", "/decisions", DEC_025)
    if code != 201:
        print(f"FAILED: HTTP {code}")
        print(json.dumps(payload, indent=2))
        return 1
    print(f"  HTTP {code}: created {payload['data']['identifier']}")
    print()

    for identifier, body in PATCHES:
        print("=" * 70)
        print(f"Step — PATCH /sessions/{identifier} ({sorted(body.keys())})")
        print("=" * 70)
        code, payload = _request("PATCH", f"/sessions/{identifier}", body)
        if code != 200:
            print(f"FAILED: HTTP {code}")
            print(json.dumps(payload, indent=2))
            return 1
        print(f"  HTTP {code}: updated {identifier}")
        print()

    print("=" * 70)
    print("All writes succeeded.")
    print("=" * 70)
    print(
        "Inspect the db-export/ snapshot diff next:\n"
        "    git diff PRDs/product/crmbuilder-v2/db-export/\n\n"
        "If the diff looks right, commit:\n\n"
        "    git add PRDs/product/crmbuilder-v2/db-export/\n"
        "    git commit -m \"v2: governance — DEC-025 transcript capture deferred; "
        "session reference cleanup\"\n"
        "    git push origin main\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Suggested commit message for the snapshot diff produced by this script:
#
# v2: governance — DEC-025 transcript capture deferred; session reference cleanup
#
# Records DEC-025 (Defer per-conversation transcript capture from Claude.ai)
# per the planning conversation that surfaced the gap in the
# conversation_reference field on session records.
#
# Implements the documented convention by cleaning up the conversation_reference
# fields on SES-001, SES-002, SES-004, and SES-005, and prepending the seed
# prompt to SES-004's topics_covered.
