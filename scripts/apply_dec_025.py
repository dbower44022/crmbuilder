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
        "full `context`, `rationale`, `alternatives_considered`, and `consequences`
