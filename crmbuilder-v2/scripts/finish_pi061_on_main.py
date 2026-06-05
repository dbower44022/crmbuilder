"""PI-061 build-closure — run ON main AFTER merging the pi-061 branch.

Governance for PI-061 was recorded live (DEC-383), so there is no close-out
payload to apply. This finisher only does the two deferred-to-merge steps:

  1. Create the ``resolves`` edge CNV-063 -> PI-061 (atomically flips PI-061
     to Resolved).
  2. Complete the conversation (CNV-063) and the session (SES-161).

Optionally (default on, best-effort) it authors a ``commit`` governance record
for the merge/squash commit now on main's history, attributed to CNV-063.

Everything is idempotent: re-running skips work already done. It refuses to run
off ``main``.

Run (after merge):  uv run python scripts/finish_pi061_on_main.py
Skip the commit record:  uv run python scripts/finish_pi061_on_main.py --no-commit
Use a specific SHA:      uv run python scripts/finish_pi061_on_main.py --sha <sha>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8765"
ENGAGEMENT = "CRMBUILDER"

PI = "PI-061"
CONVERSATION = "CNV-063"
SESSION = "SES-161"


def _req(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("X-Engagement", ENGAGEMENT)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return {"_status": exc.code, "_body": exc.read().decode()}


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def _abort(msg: str) -> int:
    print(f"✗ {msg}")
    return 1


def _ensure_on_main() -> bool:
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if branch != "main":
        print(f"✗ Refusing to run off 'main' (current branch: {branch!r}).")
        print("  Merge pi-061 into main first, then re-run this on main.")
        return False
    return True


def _exists(entity_path: str, key: str) -> bool:
    r = _req("GET", entity_path)
    return bool(r.get("data")) and r.get("data", {}).get(key) is not None


def _resolve_pi() -> bool:
    # Idempotent: skip if the resolves edge already exists.
    refs = _req("GET", f"/references?source_id={CONVERSATION}").get("data", [])
    for ref in refs:
        if (
            ref.get("relationship") == "resolves"
            and ref.get("target_id") == PI
        ):
            print(f"• resolves edge {CONVERSATION} -> {PI} already exists; skipping.")
            return True
    r = _req(
        "POST",
        "/references",
        {
            "source_type": "conversation",
            "source_id": CONVERSATION,
            "target_type": "planning_item",
            "target_id": PI,
            "relationship": "resolves",
        },
    )
    if r.get("data"):
        print(f"✓ created resolves edge {CONVERSATION} -> {PI}")
        return True
    print(f"✗ failed to create resolves edge: {r}")
    return False


def _author_commit_record(sha: str) -> None:
    # Best-effort: a failure here never blocks the resolve/close steps.
    full_sha = _git("rev-parse", sha)
    # Skip if a commit record for this SHA already exists.
    existing = _req("GET", f"/commits/by-sha/{full_sha}")
    if existing.get("data"):
        ident = existing["data"].get("commit_identifier")
        print(f"• commit record {ident} for {full_sha[:8]} already exists; skipping.")
        return
    subject = _git("show", "-s", "--format=%s", full_sha)
    body_full = _git("show", "-s", "--format=%B", full_sha)
    author_name = _git("show", "-s", "--format=%an", full_sha)
    author_email = _git("show", "-s", "--format=%ae", full_sha)
    committed_at = _git("show", "-s", "--format=%cI", full_sha)
    parents = _git("show", "-s", "--format=%P", full_sha).split()
    files_changed = len(
        [
            line
            for line in _git(
                "show", "--name-only", "--format=", full_sha
            ).splitlines()
            if line.strip()
        ]
    )
    body = {
        "commit_sha": full_sha,
        "commit_message_first_line": subject,
        "commit_message_full": body_full,
        "commit_author_name": author_name,
        "commit_author_email": author_email,
        "commit_committed_at": committed_at,
        "commit_repository": "dbower44022/crmbuilder",
        "commit_branch": "main",
        "commit_parent_shas": parents,
        "commit_files_changed_count": files_changed,
        "commit_session_id": CONVERSATION,
    }
    r = _req("POST", "/commits", body)
    if r.get("data"):
        print(
            f"✓ authored commit record {r['data']['commit_identifier']} "
            f"for {full_sha[:8]} (attributed to {CONVERSATION})"
        )
    else:
        print(f"⚠ could not author commit record for {full_sha[:8]} (non-fatal): {r}")


def _complete_conversation() -> None:
    cur = _req("GET", f"/conversations/{CONVERSATION}").get("data", {})
    if cur.get("conversation_status") == "complete":
        print(f"• {CONVERSATION} already complete; skipping.")
        return
    r = _req(
        "PATCH",
        f"/conversations/{CONVERSATION}",
        {
            "conversation_status": "complete",
            "conversation_summary": (
                "Built the V2 term (glossary) entity end to end: storage model + "
                "table, access repository, /terms API, and the Glossary desktop "
                "panel, with tests. Migrated the five existing glossary terms and "
                "seeded the agent-system terms (19 total). Retired "
                "specifications/glossary.md to a pointer. Resolves PI-061."
            ),
        },
    )
    if r.get("data"):
        print(f"✓ completed conversation {CONVERSATION}")
    else:
        print(f"✗ failed to complete {CONVERSATION}: {r}")


def _complete_session() -> None:
    cur = _req("GET", f"/sessions/{SESSION}").get("data", {})
    if cur.get("session_status") == "complete":
        print(f"• {SESSION} already complete; skipping.")
        return
    r = _req(
        "PATCH",
        f"/sessions/{SESSION}",
        {"session_status": "complete"},
    )
    if r.get("data"):
        print(f"✓ completed session {SESSION}")
    else:
        print(f"✗ failed to complete {SESSION}: {r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sha", default="HEAD", help="commit to record (default HEAD)")
    parser.add_argument(
        "--no-commit", action="store_true", help="skip authoring the commit record"
    )
    args = parser.parse_args()

    if not _ensure_on_main():
        return 1
    if _req("GET", "/status").get("_status") == 500:
        pass  # status may legitimately 500 on some setups; the entity reads below gate us.
    if not _exists(f"/planning-items/{PI}", "identifier"):
        return _abort(f"{PI} not found via the live API — is the API up and on the unified DB?")
    if not _exists(f"/conversations/{CONVERSATION}", "conversation_identifier"):
        return _abort(f"{CONVERSATION} not found.")
    if not _exists(f"/sessions/{SESSION}", "session_identifier"):
        return _abort(f"{SESSION} not found.")

    print("== PI-061 build-closure on main ==")
    if not _resolve_pi():
        return 1
    if not args.no_commit:
        try:
            _author_commit_record(args.sha)
        except Exception as exc:  # noqa: BLE001 — best-effort, never blocks closure
            print(f"⚠ commit-record step skipped (non-fatal): {exc}")
    _complete_conversation()
    _complete_session()

    final = _req("GET", f"/planning-items/{PI}").get("data", {})
    print(f"\n{PI} status: {final.get('status')}")
    if final.get("status") == "Resolved":
        print("✓ PI-061 resolved. Build-closure complete.")
        return 0
    print("⚠ PI-061 is not Resolved — check the resolves edge above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
