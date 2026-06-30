"""Governance enforcement gate validator — REQ-320 / PI-286.

The verdict core (:func:`evaluate`) is pure given an injected ``get_json``, so
these tests exercise every reject reason, the trivial-exemption path, and the
doc-only skip with no git, no server, no real commit.
"""

from __future__ import annotations

from crmbuilder_v2.governance_gate import (
    evaluate,
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
    pis, reason = parse_governance_trailers("feat\n\nGoverned-By: PI-286\n")
    assert pis == ["PI-286"] and reason is None


def test_parse_multiple_pis():
    pis, _ = parse_governance_trailers("x\n\nGoverned-By: PI-1\nGoverned-By: PI-2\n")
    assert pis == ["PI-1", "PI-2"]


def test_parse_trivial_with_reason():
    pis, reason = parse_governance_trailers(
        "typo\n\nGoverned-By: trivial\nExemption-Reason: fix a comment typo\n")
    assert pis == [] and reason == "fix a comment typo"


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
