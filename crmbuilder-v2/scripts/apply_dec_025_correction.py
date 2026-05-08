#!/usr/bin/env python3
"""Correct DEC-025's consequences field after the discovery that sessions
are append-only at the API surface.

The original apply_dec_025.py created DEC-025 successfully, then attempted
to PATCH conversation_reference on SES-001 / SES-002 / SES-004 / SES-005.
Those PATCHes failed with HTTP 405 because the sessions router does not
expose PATCH — sessions are append-only per DEC-013 and DEC-014.

This script PATCHes DEC-025's `consequences` field with corrected text
that acknowledges the constraint and confirms the policy is forward-only.

Run with the storage API live at http://127.0.0.1:8765:

    uv run crmbuilder-v2-api  # in another terminal
    python3 crmbuilder-v2/scripts/apply_dec_025_correction.py

After the script completes, inspect the db-export/ diff and commit.
"""
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8765"


CORRECTED_CONSEQUENCES = (
    "1. Sessions are append-only per DEC-013 and DEC-014, and the storage API "
    "does not expose a PATCH endpoint for sessions. The convention in this "
    "decision therefore applies forward only — existing session records keep "
    "the conversation_reference text they were created with.\n\n"
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
)


def main() -> int:
    body = {"consequences": CORRECTED_CONSEQUENCES}
    req = urllib.request.Request(
        f"{BASE}/decisions/DEC-025",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="PATCH",
    )
    print("PATCH /decisions/DEC-025 (consequences)")
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"  HTTP {resp.status}: updated DEC-025")
    except urllib.error.HTTPError as e:
        print(f"FAILED: HTTP {e.code}")
        print(e.read().decode())
        return 1
    print()
    print(
        "Inspect the db-export/ diff next:\n"
        "    git diff PRDs/product/crmbuilder-v2/db-export/\n\n"
        "If the diff looks right, commit:\n\n"
        "    git add PRDs/product/crmbuilder-v2/db-export/\n"
        "    git commit -m \"v2: governance — correct DEC-025 consequences after "
        "session append-only discovery\"\n"
        "    git push origin main\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
