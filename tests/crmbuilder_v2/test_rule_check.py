"""REQ-542 / PI-439 — the pre-action rule check hook.

Pure tests against canned rules: each check kind, the deny payload, the
override marker (recorded to the store, or to the exemption log when the store
refuses), snapshot TTL, and fail-open when nothing can be read.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from crmbuilder_v2 import rule_check as rc

TRAILER = {
    "identifier": "GVR-229", "enforcement": "enforced_with_override", "applies_to": "all",
    "predicate": {"kind": "required_trailer", "trailer": "Governed-By",
                  "pattern": r"PI-\d{3}|trivial"},
    "body": "Every code commit carries a Governed-By trailer.",
}
PATHSPEC = {
    "identifier": "GVR-235", "enforcement": "enforced_with_override", "applies_to": "claude_code",
    "predicate": {"kind": "forbidden_command",
                  "pattern": r"\bgit\b(?:\s+-\S+)*\s+commit\b(?![^\n]*\s--\s)",
                  "message": "commit with an explicit pathspec: git commit ... -- <files>"},
    "body": "Always commit with an explicit pathspec.",
}
DEPLOY = {
    "identifier": "GVR-240", "enforcement": "enforced", "applies_to": "all",
    "predicate": {"kind": "forbidden_command",
                  "pattern": r"(?:\./)?scripts/deploy-production\.sh|(?:rsync|ssh|scp)\b[^\n]*138\.197\.72\.15[^\n]*\b(?:systemctl\s+restart|alembic\s+upgrade|git\s+pull)\b|rsync\b[^\n]*138\.197\.72\.15",
                  "message": "production deploy is human-only"},
    "body": "Production deploy is human-only.",
}
SECRET = {
    "identifier": "GVR-900", "enforcement": "enforced", "applies_to": "all",
    "predicate": {"kind": "protected_path", "pattern": r"crmbuilder-v2/data/crmbuilder\.env"},
    "body": "The env file is never edited by a command.",
}
RULES = [TRAILER, PATHSPEC, DEPLOY, SECRET]


def _ids(items):
    # evaluate() yields (rule, fragment) pairs; load_rules() yields rule dicts.
    return [(r[0] if isinstance(r, tuple) else r)["identifier"] for r in items]


def test_forbidden_command_blocks_bare_commit_and_allows_pathspec():
    assert _ids(rc.evaluate('git commit -m "x"', [PATHSPEC])) == ["GVR-235"]
    assert rc.evaluate('git commit -F /dev/stdin -- a.py b.py <<EOF\nmsg\nEOF', [PATHSPEC]) == []
    assert rc.evaluate("git merge --no-ff pi-1", [PATHSPEC]) == []


def test_required_trailer_only_judges_inline_commit_messages():
    good = 'git commit -F /dev/stdin -- a.py <<EOF\nfeat\n\nGoverned-By: PI-439\nEOF'
    bad = 'git commit -m "feat" -- a.py'
    assert rc.evaluate(good, [TRAILER]) == []
    assert _ids(rc.evaluate(bad, [TRAILER])) == ["GVR-229"]
    assert rc.evaluate("git commit -F /tmp/msg.txt -- a.py", [TRAILER]) == []  # commit-msg gate's job
    assert rc.evaluate("ls -la", [TRAILER]) == []
    # a commit quoted inside a heredoc or a string is data, not a command
    quoted = "python3 - <<'EOF'\ncases = [('git commit -m \"x\"', True)]\nEOF"
    assert rc.evaluate(quoted, [TRAILER]) == []
    assert _ids(rc.evaluate('ls; git commit -m "x" -- a.py', [TRAILER])) == ["GVR-229"]


def test_protected_path_and_deploy_are_blocked():
    assert _ids(rc.evaluate("scripts/deploy-production.sh", [DEPLOY])) == ["GVR-240"]
    assert _ids(rc.evaluate("sed -i s/a/b/ crmbuilder-v2/data/crmbuilder.env", [SECRET])) == ["GVR-900"]
    assert rc.evaluate("ssh root@138.197.72.15 'cat /etc/hostname'", [DEPLOY]) == []


def test_decide_denies_with_rule_named_and_override_hint(tmp_path: Path):
    verdict = rc.decide(tmp_path, 'git commit -m "x"', "sess", [PATHSPEC, DEPLOY])
    out = verdict["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "GVR-235" in out["permissionDecisionReason"]
    assert "GVR_OVERRIDE='GVR-235:" in out["permissionDecisionReason"]
    assert rc.decide(tmp_path, "ls", "sess", RULES) is None


def test_enforced_rule_cannot_be_overridden(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(rc, "record_override", lambda *a, **k: "store")
    verdict = rc.decide(tmp_path, "GVR_OVERRIDE='GVR-240: hurry' scripts/deploy-production.sh", "s", [DEPLOY])
    assert verdict["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_override_marker_waves_through_and_records(tmp_path: Path, monkeypatch):
    recorded = []
    monkeypatch.setattr(rc, "record_override", lambda *a, **k: recorded.append(a) or "store")
    cmd = "GVR_OVERRIDE='GVR-235: amending a merge message' git commit --amend -m x"
    assert rc.decide(tmp_path, cmd, "sess-1", [PATHSPEC]) is None
    assert recorded and recorded[0][1:3] == ("GVR-235", "amending a merge message")


def test_override_falls_back_to_exemption_log(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CRMBUILDER_V2_API_BASE_URL", "https://127.0.0.1:9")
    monkeypatch.setenv("CRMBUILDER_V2_API_TOKEN", "t")
    (tmp_path / rc.EXEMPTION_LOG).parent.mkdir(parents=True)
    where = rc.record_override(tmp_path, "GVR-235", "why", "git commit -m x", "s")
    assert where == "exemption-log"
    line = (tmp_path / rc.EXEMPTION_LOG).read_text()
    assert "\toverride\tGVR-235\twhy\t" in line


def test_load_rules_uses_fresh_snapshot_and_refreshes_stale(tmp_path: Path):
    calls = []

    def fetch(path):
        calls.append(path)
        if path.startswith("/governance-rules"):
            return [dict(DEPLOY), {"identifier": "GVR-001", "enforcement": "advisory", "applies_to": "all"}]
        return []

    rules, source = rc.load_rules(tmp_path, fetch=fetch)
    assert source == "live" and _ids(rules) == ["GVR-240"]
    rules, source = rc.load_rules(tmp_path, fetch=fetch)
    assert source == "snapshot" and len(calls) == 1
    snap = tmp_path / rc.SNAPSHOT_FILE
    saved = json.loads(snap.read_text())
    saved["fetched_at"] = time.time() - rc.SNAPSHOT_TTL_SECONDS - 1
    snap.write_text(json.dumps(saved))
    _, source = rc.load_rules(tmp_path, fetch=fetch)
    assert source == "live" and len(calls) == 2


def test_load_rules_fails_open_without_store_or_snapshot(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.delenv("CRMBUILDER_V2_API_BASE_URL", raising=False)
    rules, source = rc.load_rules(tmp_path)
    assert rules == [] and source == "none"
    assert "fail open" in capsys.readouterr().err


def test_main_allows_when_no_command(monkeypatch, capsys):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"tool_input": {}})))
    assert rc.main([]) == 0
    assert capsys.readouterr().out == ""


# --- REQ-547 / PI-445: matching is positional, payloads are data ----------------


def test_reading_or_naming_the_protected_script_is_allowed():
    # the three 2026-08-31 false positives
    assert rc.evaluate("cat scripts/deploy-production.sh", [DEPLOY]) == []
    assert rc.evaluate("sed -n 1,50p scripts/deploy-production.sh", [DEPLOY]) == []
    assert rc.evaluate('git commit -m "x" -- scripts/deploy-production.sh', [DEPLOY]) == []


def test_mentioning_the_script_in_a_write_payload_is_allowed():
    heredoc = "python3 - <<EOF\nprint('scripts/deploy-production.sh')\nEOF"
    assert rc.evaluate(heredoc, [DEPLOY]) == []
    payload = "curl -sS -d '{\"note\": \"see scripts/deploy-production.sh\"}' https://api.example/notes"
    assert rc.evaluate(payload, [DEPLOY]) == []


def test_executing_the_script_still_blocks_and_names_the_fragment():
    for cmd in ("scripts/deploy-production.sh", "./scripts/deploy-production.sh", "cd /x && scripts/deploy-production.sh", "FOO=1 scripts/deploy-production.sh"):
        hits = rc.evaluate(cmd, [DEPLOY])
        assert _ids(hits) == ["GVR-240"], cmd
        assert "scripts/deploy-production.sh" in hits[0][1]


def test_droplet_mutations_still_block_and_remote_reads_pass():
    assert _ids(rc.evaluate("rsync -av . root@138.197.72.15:/opt/", [DEPLOY])) == ["GVR-240"]
    assert _ids(rc.evaluate("ssh root@138.197.72.15 'systemctl restart api'", [DEPLOY])) == ["GVR-240"]
    assert _ids(rc.evaluate("ssh -i ~/.ssh/k root@138.197.72.15 'cd /opt && git pull'", [DEPLOY])) == ["GVR-240"]
    assert rc.evaluate("ssh root@138.197.72.15 'cat /etc/hostname'", [DEPLOY]) == []


def test_denial_message_names_the_matched_fragment(tmp_path: Path):
    verdict = rc.decide(tmp_path, "scripts/deploy-production.sh", "sess", [DEPLOY])
    reason = verdict["hookSpecificOutput"]["permissionDecisionReason"]
    assert "matched:" in reason and "scripts/deploy-production.sh" in reason


def test_protected_path_ignores_heredoc_payloads_but_guards_arguments():
    heredoc = "python3 - <<EOF\nopen('crmbuilder-v2/data/crmbuilder.env')\nEOF"
    assert rc.evaluate(heredoc, [SECRET]) == []
    assert _ids(rc.evaluate("sed -i s/a/b/ crmbuilder-v2/data/crmbuilder.env", [SECRET])) == ["GVR-900"]
