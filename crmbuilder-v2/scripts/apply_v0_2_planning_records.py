#!/usr/bin/env python3
"""Write v0.2 planning records — slice A Step 1.

Reads the verbatim body text for SES-006 and DEC-026 through DEC-031
from the slice A execution prompt's appendices, then POSTs them through
the local storage API at http://127.0.0.1:8765 along with six
``decided_in`` references and a new status version reflecting that v0.2
is now in build.

Source of truth for the verbatim text:
``PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.2-A-foundation-refactor.md``
Appendix A (decision body text), Appendix B (SES-006 topics_covered),
Appendix C (SES-006 summary), Appendix D (SES-006 artifacts_produced).

Idempotent on re-run: each POST treats HTTP 409 conflict as already-
present and continues. The status PUT always creates a new version.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8765"
REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = (
    REPO_ROOT
    / "PRDs"
    / "product"
    / "crmbuilder-v2"
    / "prompts"
    / "CLAUDE-CODE-PROMPT-v2-ui-v0.2-A-foundation-refactor.md"
)
DECISION_DATE = "05-08-26"
SESSION_DATE = "05-08-26"
SESSION_ID = "SES-006"
DECISION_IDS = (
    "DEC-026",
    "DEC-027",
    "DEC-028",
    "DEC-029",
    "DEC-030",
    "DEC-031",
)


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
        body_bytes = e.read().decode()
        try:
            payload = json.loads(body_bytes)
        except json.JSONDecodeError:
            payload = {"raw": body_bytes}
        return e.code, payload


def _read_prompt() -> str:
    if not PROMPT_PATH.exists():
        raise SystemExit(f"Slice A prompt not found at {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8")


def _section(text: str, start_marker: str, end_marker: str | None) -> str:
    start = text.index(start_marker)
    if end_marker is None:
        return text[start:]
    end = text.index(end_marker, start)
    return text[start:end]


def _parse_decisions(appendix_a: str) -> list[dict]:
    """Each block starts at '### DEC-NNN — title' and contains five
    bold-marked fields: **context**, **decision**, **rationale**,
    **alternatives_considered**, **consequences**.

    Returns a list of dicts ready for POST /decisions.
    """
    blocks = re.split(r"\n### (DEC-\d+) — ([^\n]+)\n", appendix_a)
    # blocks layout: [preamble, id, title, body, id, title, body, ...]
    decisions = []
    for i in range(1, len(blocks), 3):
        identifier = blocks[i].strip()
        title = blocks[i + 1].strip()
        body = blocks[i + 2]
        fields = _parse_decision_fields(body)
        decisions.append(
            {
                "identifier": identifier,
                "title": title,
                "decision_date": DECISION_DATE,
                "status": "Active",
                **fields,
            }
        )
    return decisions


def _parse_decision_fields(body: str) -> dict:
    """Body text contains the five bold-marked sections in order. Splits
    on the bold markers and trims surrounding whitespace.
    """
    pattern = re.compile(
        r"\n\*\*(context|decision|rationale|alternatives_considered|consequences)\*\*\n+"
    )
    parts = pattern.split(body)
    # parts layout: [preamble, key, content, key, content, ...]
    fields = {}
    for i in range(1, len(parts), 2):
        key = parts[i]
        content = parts[i + 1]
        # Trim trailing horizontal-rule separator and whitespace.
        content = re.sub(r"\n+---\n.*$", "", content, flags=re.DOTALL).strip()
        fields[key] = content
    expected = {"context", "decision", "rationale", "alternatives_considered", "consequences"}
    missing = expected - set(fields)
    if missing:
        raise SystemExit(f"Decision body missing fields: {missing}")
    return fields


def _parse_session(prompt_text: str) -> dict:
    """Pull SES-006 fields from Appendices B (topics_covered), C
    (summary), D (artifacts_produced)."""
    topics_block = _section(
        prompt_text,
        "## Appendix B — SES-006 `topics_covered` (verbatim)",
        "## Appendix C",
    )
    summary_block = _section(
        prompt_text,
        "## Appendix C — SES-006 `summary` (verbatim)",
        "## Appendix D",
    )
    artifacts_block = _section(
        prompt_text,
        "## Appendix D — SES-006 `artifacts_produced` (verbatim)",
        None,
    )
    topics = _extract_fenced_code(topics_block)
    summary = _extract_fenced_code(summary_block)
    artifacts = _extract_fenced_code(artifacts_block)
    return {
        "identifier": SESSION_ID,
        "title": "UI v0.2 planning",
        "session_date": SESSION_DATE,
        "status": "Complete",
        "conversation_reference": (
            "Claude.ai planning conversation that produced "
            "ui-PRD-v0.2.md, ui-v0.2-implementation-plan.md, and the "
            "CLAUDE-CODE-PROMPT-v2-ui-v0.2 series under "
            "PRDs/product/crmbuilder-v2/. No transcript preserved per DEC-025."
        ),
        "topics_covered": topics,
        "summary": summary,
        "artifacts_produced": artifacts,
        "in_flight_at_end": "",
    }


def _extract_fenced_code(block: str) -> str:
    match = re.search(r"```\n(.*?)\n```", block, flags=re.DOTALL)
    if match is None:
        raise SystemExit(
            "Could not find fenced code block in appendix section:\n"
            + block[:200]
        )
    return match.group(1).strip()


def _build_status_payload() -> dict:
    """New status version reflecting v0.2 in build, slice A in progress.

    Built from current status v0.6's payload (read from the API) with
    fields updated per slice A's spec.
    """
    code, body = _request("GET", "/status")
    if code != 200:
        raise SystemExit(f"GET /status failed: {code} {body}")
    current = body["data"]["payload"]
    new_payload = dict(current)
    new_payload["phase"] = "v0.2 in build"
    new_payload["sub_step"] = (
        "Slice A foundation refactor in progress: extracting "
        "EntityCrudDialog and VersionedReplaceDialog base classes, "
        "adding widgets/ subpackage with DateField + ReferencesSection "
        "+ HierarchicalEntityPicker, migrating decisions dialogs to the "
        "new base."
    )
    new_payload["active_work"] = (
        "Slice A — foundation refactor (this conversation's execution work)."
    )
    new_payload["version_label"] = "0.7"
    metadata = dict(new_payload.get("metadata") or {})
    metadata["Last Updated"] = "05-08-26"
    new_payload["metadata"] = metadata
    live_inventory = dict(new_payload.get("live_inventory") or {})
    live_inventory["in_database"] = [
        "30 decisions (DEC-001 through DEC-031)",
        "6 sessions (SES-001 through SES-006)",
        "4 charter versions (latest is_current)",
        "7 status versions (this is the new current)",
        "30 references (24 from prior sessions + 6 from SES-006 to DEC-026 through DEC-031)",
    ]
    new_payload["live_inventory"] = live_inventory
    pending = dict(new_payload.get("pending") or {})
    pending["ui_v0_2_remaining_slices"] = [
        "v2-ui-v0.2-B — risks CRUD",
        "v2-ui-v0.2-C — planning items CRUD",
        "v2-ui-v0.2-D — topics CRUD + QTreeView + HierarchicalEntityPicker",
        "v2-ui-v0.2-E — charter and status replace flows + sessions references section",
        "v2-ui-v0.2-F — show-deleted toggle + polish + closeout (SES-007)",
    ]
    pending.pop("ui_v0_2_backlog", None)  # superseded by the slice list
    new_payload["pending"] = pending
    return new_payload


def main() -> int:
    prompt_text = _read_prompt()
    appendix_a = _section(
        prompt_text,
        "## Appendix A — Decision body text (verbatim)",
        "## Appendix B",
    )
    decisions = _parse_decisions(appendix_a)
    if [d["identifier"] for d in decisions] != list(DECISION_IDS):
        raise SystemExit(
            "Parsed decision IDs do not match expected: "
            f"{[d['identifier'] for d in decisions]} vs {list(DECISION_IDS)}"
        )

    print(f"Parsed {len(decisions)} decisions from {PROMPT_PATH.name}")
    for d in decisions:
        print(f"  POST /decisions {d['identifier']} — {d['title'][:60]}…")
        code, body = _request("POST", "/decisions", d)
        if code in (200, 201):
            print(f"    OK ({code})")
        elif code == 409:
            print("    409 conflict (already exists) — continuing")
        else:
            print(f"    FAILED ({code}): {body}")
            return 1

    session = _parse_session(prompt_text)
    print(f"POST /sessions {session['identifier']}")
    code, body = _request("POST", "/sessions", session)
    if code in (200, 201):
        print(f"  OK ({code})")
    elif code == 409:
        print("  409 conflict (already exists) — continuing")
    else:
        print(f"  FAILED ({code}): {body}")
        return 1

    for dec_id in DECISION_IDS:
        ref = {
            "source_type": "session",
            "source_id": SESSION_ID,
            "target_type": "decision",
            "target_id": dec_id,
            "relationship": "decided_in",
        }
        print(f"POST /references SES-006 → {dec_id}")
        code, body = _request("POST", "/references", ref)
        if code in (200, 201):
            print(f"  OK ({code})")
        elif code == 409:
            print("  409 conflict (already exists) — continuing")
        else:
            print(f"  FAILED ({code}): {body}")
            return 1

    payload = _build_status_payload()
    print("PUT /status (new version, phase=v0.2 in build)")
    code, body = _request("PUT", "/status", {"payload": payload})
    if code in (200, 201):
        print(f"  OK ({code})")
    else:
        print(f"  FAILED ({code}): {body}")
        return 1

    print("\nAll planning records written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
