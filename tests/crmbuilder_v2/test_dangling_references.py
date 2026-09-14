"""The dangling-references check — PI-502 (REQ-598).

The report and exit code are pure; the census endpoint is exercised through the
API; ``main`` refuses to guess when it has no credentials.
"""

from __future__ import annotations

from crmbuilder_v2 import dangling_references as dr

_ROW = {
    "id": 7, "reference_identifier": "REF-0007", "relationship": "is_about",
    "source_type": "decision", "source_id": "DEC-001",
    "target_type": "instance", "target_id": "INST-001", "missing": ["target"],
}


def test_report_lists_each_reference_and_exits_one():
    text, code = dr.report({"ENG-001": [_ROW]}, ["ENG-001", "ENG-002"])
    assert code == 1
    assert "1 reference(s) point at a record that does not exist" in text
    assert "REF-0007: decision 'DEC-001' --is_about--> instance 'INST-001' (missing: target)" in text
    assert "never changes a reference" in text


def test_clean_census_exits_zero():
    text, code = dr.report({}, ["ENG-001", "ENG-002"])
    assert code == 0 and "2 engagement(s) checked" in text


def test_census_reads_every_engagement_and_omits_clean_ones():
    calls = []

    def fetch(path, engagement):
        calls.append((path, engagement))
        if path == "/engagements":
            return [{"engagement_identifier": "ENG-002"}, {"engagement_identifier": "ENG-001"}]
        return [_ROW] if engagement == "ENG-002" else []

    ids = dr.engagements(fetch)
    assert ids == ["ENG-001", "ENG-002"]
    assert dr.census(fetch, ids) == {"ENG-002": [_ROW]}
    assert ("/references/dangling", "ENG-001") in calls


def test_main_without_credentials_cannot_run(monkeypatch, capsys):
    monkeypatch.delenv("CRMBUILDER_V2_API_BASE_URL", raising=False)
    monkeypatch.delenv("CRMBUILDER_V2_API_TOKEN", raising=False)
    assert dr.main([]) == 2
    assert "CRMBUILDER_V2_API_TOKEN" in capsys.readouterr().out
