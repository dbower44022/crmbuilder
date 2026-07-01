"""Governance enforcement gate validator — REQ-320 / PI-286.

The verdict core (:func:`evaluate`) is pure given an injected ``get_json``, so
these tests exercise every reject reason, the trivial-exemption path, and the
doc-only skip with no git, no server, no real commit.
"""

from __future__ import annotations

from crmbuilder_v2 import governance_gate
from crmbuilder_v2.governance_gate import (
    _api_config,
    _http_get_json,
    _push_rev_list_args,
    evaluate,
    guarded_evaluate,
    parse_governance_trailers,
    touches_code,
    validate_planning_item,
)

CODE = ["crmbuilder-v2/src/crmbuilder_v2/access/models.py"]
DOCS = ["PRDs/product/crmbuilder-v2/foo.md", "README.md"]


def _fake_api(pis: dict[str, dict], edges: dict[str, list], reqs: dict[str, str]):
    """Build a get_json over canned PI / edge / requirement state."""
    def get_json(path: str):
        if path.startswith("/planning-items/"):
            return pis.get(path.rsplit("/", 1)[-1])
        if path.startswith("/references?source_id="):
            pi = path.split("source_id=")[-1].split("&")[0]
            return edges.get(pi, [])
        if path.startswith("/requirements/"):
            rid = path.rsplit("/", 1)[-1]
            return {"requirement_status": reqs[rid]} if rid in reqs else None
        return None
    return get_json


def _good_api(pi="PI-286", status="Draft", req="REQ-320", req_status="confirmed"):
    return _fake_api(
        pis={pi: {"status": status}},
        edges={pi: [
            {"relationship": "planning_item_belongs_to_project", "target_id": "PRJ-048"},
            {"relationship": "planning_item_implements_requirement", "target_id": req},
        ]},
        reqs={req: req_status},
    )


# --- parsing ----------------------------------------------------------------

def test_touches_code():
    assert touches_code(CODE) is True
    assert touches_code(DOCS) is False
    assert touches_code(CODE + DOCS) is True  # code wins on a mixed commit


def test_parse_pi_trailer():
    pis, reason, malformed = parse_governance_trailers("feat\n\nGoverned-By: PI-286\n")
    assert pis == ["PI-286"] and reason is None and malformed == []


def test_parse_multiple_pis():
    pis, _, malformed = parse_governance_trailers(
        "x\n\nGoverned-By: PI-1\nGoverned-By: PI-2\n")
    assert pis == ["PI-1", "PI-2"] and malformed == []


def test_parse_trivial_with_reason():
    pis, reason, malformed = parse_governance_trailers(
        "typo\n\nGoverned-By: trivial\nExemption-Reason: fix a comment typo\n")
    assert pis == [] and reason == "fix a comment typo" and malformed == []


def test_parse_malformed_trailer_is_not_a_pi():
    """REQ-449: a malformed value is collected as malformed, never a lookup id."""
    pis, reason, malformed = parse_governance_trailers(
        "x\n\nGoverned-By: REQ-435 (confirmed via DEC-856) / PI-374 / PRJ-088\n")
    assert pis == []
    assert malformed == ["REQ-435 (confirmed via DEC-856) / PI-374 / PRJ-088"]


# --- evaluation -------------------------------------------------------------

def test_doc_only_commit_skips_the_gate():
    d = evaluate("docs", DOCS, get_json=_good_api())
    assert d.allow is True and d.skipped is True


def test_code_without_trailer_is_blocked():
    d = evaluate("feat: thing", CODE, get_json=_good_api())
    assert d.allow is False and any("no 'Governed-By" in r for r in d.reasons)


def test_code_with_valid_draft_pi_is_allowed():
    d = evaluate("feat\n\nGoverned-By: PI-286", CODE, get_json=_good_api())
    assert d.allow is True and d.governed_pis == ["PI-286"]


def test_trivial_with_reason_allowed_and_carries_reason():
    d = evaluate("x\n\nGoverned-By: trivial\nExemption-Reason: one-char rename",
                 CODE, get_json=_good_api())
    assert d.allow is True and d.exemption_reason == "one-char rename"


def test_trivial_without_reason_is_blocked():
    d = evaluate("x\n\nGoverned-By: trivial", CODE, get_json=_good_api())
    assert d.allow is False and any("non-empty" in r for r in d.reasons)


def test_pi_not_found_blocked():
    d = evaluate("feat\n\nGoverned-By: PI-999", CODE,
                 get_json=_good_api())  # only PI-286 known
    assert d.allow is False and any("not found" in r for r in d.reasons)


def test_terminal_pi_blocked():
    d = evaluate("feat\n\nGoverned-By: PI-286", CODE,
                 get_json=_good_api(status="Resolved"))
    assert d.allow is False and any("executable" in r for r in d.reasons)


def test_pi_without_project_blocked():
    api = _fake_api(
        pis={"PI-286": {"status": "Draft"}},
        edges={"PI-286": [
            {"relationship": "planning_item_implements_requirement",
             "target_id": "REQ-320"}]},
        reqs={"REQ-320": "confirmed"},
    )
    d = evaluate("feat\n\nGoverned-By: PI-286", CODE, get_json=api)
    assert d.allow is False and any("project" in r for r in d.reasons)


def test_pi_with_unconfirmed_requirement_blocked():
    d = evaluate("feat\n\nGoverned-By: PI-286", CODE,
                 get_json=_good_api(req_status="candidate"))
    assert d.allow is False and any("CONFIRMED" in r for r in d.reasons)


def test_validate_planning_item_happy_path():
    ok, why = validate_planning_item("PI-286", _good_api())
    assert ok is True and "confirmed" in why


# --- REQ-449: malformed trailer must not crash / must not be looked up -------

def test_malformed_trailer_is_reported_and_never_looked_up():
    """A malformed Governed-By value blocks (warn/enforce) without any lookup."""
    def exploding_get_json(path: str):
        raise AssertionError(f"malformed value must never be looked up: {path!r}")

    d = evaluate(
        "feat\n\nGoverned-By: REQ-435 (confirmed via DEC-856) / PI-374 / PRJ-088",
        CODE, get_json=exploding_get_json)
    assert d.allow is False
    assert any("malformed" in r for r in d.reasons)


def test_guarded_evaluate_warn_mode_never_crashes_on_unexpected_error():
    """An unexpected error inside evaluation degrades to a warning in warn mode."""
    def boom_get_json(path: str):
        raise ValueError("URL can't contain control characters")  # simulate the old crash

    d = guarded_evaluate("feat\n\nGoverned-By: PI-286", CODE,
                         get_json=boom_get_json, mode="warn")
    assert d.allow is True  # warn mode never blocks, even on a gate defect
    assert any("unexpected gate error" in w for w in d.warnings)


def test_guarded_evaluate_enforce_mode_blocks_on_unexpected_error():
    def boom_get_json(path: str):
        raise ValueError("kaboom")

    d = guarded_evaluate("feat\n\nGoverned-By: PI-286", CODE,
                         get_json=boom_get_json, mode="enforce")
    assert d.allow is False and any("unexpected gate error" in r for r in d.reasons)


def test_guarded_evaluate_unreachable_store_degrades():
    import urllib.error

    def unreachable(path: str):
        raise urllib.error.URLError("connection refused")

    warn = guarded_evaluate("feat\n\nGoverned-By: PI-286", CODE,
                            get_json=unreachable, mode="warn")
    assert warn.allow is True and any("unreachable" in w for w in warn.warnings)
    enforce = guarded_evaluate("feat\n\nGoverned-By: PI-286", CODE,
                               get_json=unreachable, mode="enforce")
    assert enforce.allow is False


# --- REQ-450: new-branch push range ------------------------------------------

def test_push_range_existing_branch_uses_remote_dot_local():
    assert _push_rev_list_args("abc", "def") == ["def..abc"]


def test_push_range_new_branch_excludes_already_pushed():
    """A new remote branch validates only commits not already on a remote."""
    args = _push_rev_list_args("abc", "0" * 40)
    assert args == ["abc", "--not", "--remotes"]  # not the whole ancestor history


# --- REQ-451: gate targets the configured store with auth --------------------

def test_api_config_prefers_env(monkeypatch):
    monkeypatch.setenv("CRMBUILDER_V2_API_BASE", "https://api.example.test")
    monkeypatch.setenv("CRMBUILDER_V2_GATE_TOKEN", "tok-123")
    monkeypatch.setenv("CRMBUILDER_V2_GATE_ENGAGEMENT", "ENG-001")
    base, token, engagement = _api_config()
    assert base == "https://api.example.test"
    assert token == "tok-123"
    assert engagement == "ENG-001"


def test_http_get_json_sends_bearer_when_token_set(monkeypatch):
    """The lookup authenticates when a token is configured (REQ-451)."""
    monkeypatch.setattr(
        governance_gate, "_api_config",
        lambda: ("https://api.example.test", "tok-abc", "ENG-001"),
    )
    seen = {}

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"data": {"status": "Draft"}}'

    def fake_urlopen(req, timeout=0):
        seen["auth"] = req.headers.get("Authorization")
        seen["engagement"] = req.headers.get("X-engagement")
        seen["url"] = req.full_url
        return _Resp()

    monkeypatch.setattr(governance_gate.urllib.request, "urlopen", fake_urlopen)
    _http_get_json("/planning-items/PI-1")
    assert seen["auth"] == "Bearer tok-abc"
    assert seen["url"].startswith("https://api.example.test/")


def test_http_get_json_no_auth_header_without_token(monkeypatch):
    monkeypatch.setattr(
        governance_gate, "_api_config",
        lambda: ("http://127.0.0.1:8765", "", "CRMBUILDER"),
    )
    seen = {}

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"data": null}'

    def fake_urlopen(req, timeout=0):
        seen["auth"] = req.headers.get("Authorization")
        return _Resp()

    monkeypatch.setattr(governance_gate.urllib.request, "urlopen", fake_urlopen)
    _http_get_json("/planning-items/PI-1")
    assert seen["auth"] is None
