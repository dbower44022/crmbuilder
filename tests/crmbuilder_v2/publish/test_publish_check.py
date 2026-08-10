"""Tests for the live publish check's judgement — REQ-483 / PI-404.

The check itself talks to a live service, so its *decision* is separated from
its I/O: :func:`evaluate` is pure, and everything worth testing lives there.
Each case below is a way the publish path has broken or could break.
"""

from __future__ import annotations

import io

import pytest
from crmbuilder_v2.publish import check


def _expected(**entities: list[str]) -> dict:
    return {"entities": dict(entities), "association_count": 0}


def _result(programs: list[dict], **overrides) -> dict:
    body = {
        "validate_only": True,
        "validation_failed": False,
        "aborted": False,
        "abort_reason": None,
        "backup_captured": False,
        "verification": None,
        "deferrals": [],
        "programs": programs,
    }
    body.update(overrides)
    return body


def _program(filename: str, entity: str, fields: list[str], **overrides) -> dict:
    body = {
        "filename": filename,
        "entities": [entity],
        "field_names": fields,
        "field_count": len(fields),
        "relationship_count": 0,
        "deployed": False,
        "validation_errors": [],
    }
    body.update(overrides)
    return body


# -- the healthy case --------------------------------------------------------


def test_a_healthy_run_reports_nothing():
    result = _result([_program("Contact.yaml", "Contact", ["birthday", "suffix"])])
    assert check.evaluate(result, _expected(Contact=["birthday", "suffix"]), 0, 0) == []


# -- defect #3: the run is green and the output is hollow --------------------


def test_every_field_losing_its_parent_is_caught():
    """The signature failure. Programs are generated, validation passes, HTTP is
    200 — and not one field arrived. Status alone cannot tell this from health."""
    result = _result([_program("Contact.yaml", "Contact", [])])
    failures = check.evaluate(result, _expected(Contact=["birthday", "suffix"]), 0, 0)
    assert len(failures) == 1
    assert "generated none" in failures[0]


def test_a_partial_loss_is_caught_too():
    result = _result([_program("Contact.yaml", "Contact", ["birthday"])])
    failures = check.evaluate(
        result, _expected(Contact=["birthday", "suffix", "nickname"]), 0, 0
    )
    assert len(failures) == 1
    assert "went missing without being announced" in failures[0]


def test_an_announced_deferral_is_not_a_failure():
    """A field the adapter said it was not emitting is design working as
    intended — counting it as loss would make ordinary reference fields fail the
    check every run."""
    result = _result(
        [_program("Contact.yaml", "Contact", ["birthday"])],
        deferrals=[
            {
                "kind": "reference_field",
                "identifier": "FLD-9",
                "name": "referring_partner",
                "parent": "Contact",
                "detail": "reference fields are deferred",
            }
        ],
    )
    assert check.evaluate(result, _expected(Contact=["birthday", "ref"]), 0, 0) == []


def test_an_attribute_deferral_does_not_excuse_a_missing_field():
    """``field_attribute`` defers something *about* a field that was emitted. It
    must not be spent as an excuse for a field that never arrived."""
    result = _result(
        [_program("Contact.yaml", "Contact", ["birthday"])],
        deferrals=[
            {
                "kind": "field_attribute",
                "identifier": "FLD-9",
                "name": "birthday",
                "parent": "Contact",
                "detail": "maxLength not expressible",
            }
        ],
    )
    failures = check.evaluate(result, _expected(Contact=["birthday", "suffix"]), 0, 0)
    assert len(failures) == 1
    assert "deferred 0" in failures[0]


def test_two_programs_extending_one_entity_are_summed():
    """A native entity extended by several domain files must have its fields
    added up, not overwritten by whichever program came last."""
    result = _result(
        [
            _program("MR-Contact.yaml", "Contact", ["birthday"]),
            _program("FU-Contact.yaml", "Contact", ["suffix"]),
        ]
    )
    assert check.evaluate(result, _expected(Contact=["birthday", "suffix"]), 0, 0) == []


def test_a_confirmed_entity_generating_no_program_is_caught():
    result = _result([_program("Contact.yaml", "Contact", ["birthday"])])
    failures = check.evaluate(
        result, _expected(Contact=["birthday"], Session=[]), 0, 0
    )
    assert any("generated no program" in f for f in failures)


# -- the run must write nothing ----------------------------------------------


@pytest.mark.parametrize(
    "overrides,expected_text",
    [
        ({"validate_only": False}, "not validate-only"),
        ({"backup_captured": True}, "captured a backup"),
        ({"verification": {"ran": True}}, "post-publish verification"),
    ],
)
def test_a_run_that_touched_the_target_is_caught(overrides, expected_text):
    result = _result(
        [_program("Contact.yaml", "Contact", ["birthday"])], **overrides
    )
    failures = check.evaluate(result, _expected(Contact=["birthday"]), 0, 0)
    assert any(expected_text in f for f in failures)


def test_a_deployed_program_is_caught():
    result = _result(
        [_program("Contact.yaml", "Contact", ["birthday"], deployed=True)]
    )
    failures = check.evaluate(result, _expected(Contact=["birthday"]), 0, 0)
    assert any("was deployed by a validate run" in f for f in failures)


def test_a_recorded_publish_run_is_caught():
    """A validate run records nothing. A new row means something wrote."""
    result = _result([_program("Contact.yaml", "Contact", ["birthday"])])
    failures = check.evaluate(result, _expected(Contact=["birthday"]), 3, 4)
    assert any("publish_runs changed 3 -> 4" in f for f in failures)


# -- the ordinary failures ---------------------------------------------------


def test_an_abort_is_reported_with_its_reason():
    result = _result([], aborted=True, abort_reason="could not read scopes")
    failures = check.evaluate(result, _expected(), 0, 0)
    assert any("could not read scopes" in f for f in failures)


def test_validation_errors_are_reported_individually():
    result = _result(
        [
            _program(
                "Contact.yaml", "Contact", ["birthday"],
                validation_errors=["unknown field accountType"],
            )
        ],
        validation_failed=True,
    )
    failures = check.evaluate(result, _expected(Contact=["birthday"]), 0, 0)
    assert any("unknown field accountType" in f for f in failures)


# -- the production guard ----------------------------------------------------


def test_the_check_refuses_the_production_instance():
    """Validate-only writes nothing, but a check that runs unattended must not
    be one flag away from touching production (DEC-915)."""
    out = io.StringIO()
    code = check.run_check(
        instance="INST-002", engagement="ENG-002",
        base_url="http://unused", env_file="/nonexistent", out=out,
    )
    assert code == check.EXIT_CANNOT_RUN


def test_being_unable_to_run_is_not_the_same_as_failing():
    """An unreachable service must exit 2, not 1. A check that reports failure
    when it could not run teaches the operator to ignore it."""
    out = io.StringIO()
    code = check.run_check(
        instance="INST-001", engagement="ENG-002",
        base_url=None, env_file="/nonexistent", out=out,
    )
    assert code == check.EXIT_CANNOT_RUN


def test_a_service_without_the_census_cannot_be_judged():
    """An older service returns programs with no field_names. Read naively that
    is the catastrophic defect; it is really a service that needs deploying, and
    conflating the two would burn the check's credibility on its first run."""
    stale = _result([{"filename": "Contact.yaml", "deployed": False,
                      "validation_errors": []}])
    with pytest.raises(check.CheckError, match="predates the per-program census"):
        check.assert_census_available(stale)


def test_a_current_service_passes_the_census_precondition():
    check.assert_census_available(
        _result([_program("Contact.yaml", "Contact", ["birthday"])])
    )


def test_no_programs_at_all_is_judged_rather_than_excused():
    """An empty program list is a real outcome, not a stale service — it must
    reach evaluate() and be judged there."""
    check.assert_census_available(_result([]))


# -- reading the design ------------------------------------------------------


class _FakeApi:
    def __init__(self, payloads: dict) -> None:
        self.payloads = payloads

    def get(self, path: str):
        for prefix, value in self.payloads.items():
            if path.startswith(prefix):
                return value
        raise AssertionError(f"unexpected path {path}")


def _wire(monkeypatch, *, design: dict, result: dict, runs=(0, 0)):
    """Swap the HTTP client so run_check's composition can be driven offline."""
    calls: list[str] = []

    class _Stub:
        def __init__(self, *a, **k) -> None:
            pass

        def get(self, path: str):
            calls.append(f"GET {path}")
            if path.startswith("/publish-runs"):
                return [{}] * (runs[1] if any("POST" in c for c in calls) else runs[0])
            return []

        def post(self, path: str):
            calls.append(f"POST {path}")
            return result

    monkeypatch.setattr(check, "_Api", _Stub)
    monkeypatch.setattr(check, "read_expected_design", lambda api: design)
    monkeypatch.setenv("CRMBUILDER_V2_API_BASE_URL", "http://stub")
    return calls


def test_run_check_composes_into_a_healthy_zero_exit(monkeypatch):
    out = io.StringIO()
    calls = _wire(
        monkeypatch,
        design=_expected(Contact=["birthday", "suffix"]),
        result=_result([_program("Contact.yaml", "Contact", ["birthday", "suffix"])]),
    )
    code = check.run_check(
        instance="INST-001", engagement="ENG-002",
        base_url=None, env_file="/nonexistent", out=out,
    )
    assert code == check.EXIT_OK, out.getvalue()
    assert "POST /instances/INST-001/publish-validate" in calls
    assert "nothing written to the target" in out.getvalue()


def test_run_check_exits_one_and_names_the_loss(monkeypatch):
    """A hollow publish must exit 1 and say what went missing — an exit code
    with no explanation gets re-run rather than investigated."""
    out = io.StringIO()
    _wire(
        monkeypatch,
        design=_expected(Contact=["birthday", "suffix"]),
        result=_result([_program("Contact.yaml", "Contact", [])]),
    )
    code = check.run_check(
        instance="INST-001", engagement="ENG-002",
        base_url=None, env_file="/nonexistent", out=out,
    )
    assert code == check.EXIT_FAILED
    assert "generated none" in out.getvalue()


def test_expected_design_joins_fields_to_confirmed_parents_only():
    """A confirmed field under a candidate entity is never published, so it must
    not be counted as expected — otherwise the check fails on unfinished design
    rather than on a regression."""
    api = _FakeApi(
        {
            "/entities": [
                {"entity_identifier": "ENT-1", "entity_name": "Contact",
                 "entity_status": "confirmed"},
                {"entity_identifier": "ENT-2", "entity_name": "Draft",
                 "entity_status": "candidate"},
            ],
            "/fields": [
                {"field_identifier": "FLD-1", "field_name": "birthday",
                 "field_status": "confirmed"},
                {"field_identifier": "FLD-2", "field_name": "scratch",
                 "field_status": "confirmed"},
                {"field_identifier": "FLD-3", "field_name": "unfinished",
                 "field_status": "candidate"},
            ],
            "/references": [
                {"source_id": "FLD-1", "target_id": "ENT-1"},
                {"source_id": "FLD-2", "target_id": "ENT-2"},
                {"source_id": "FLD-3", "target_id": "ENT-1"},
            ],
            "/associations": [
                {"association_identifier": "ASN-1", "association_status": "confirmed"},
                {"association_identifier": "ASN-2", "association_status": "candidate"},
            ],
        }
    )
    expected = check.read_expected_design(api)
    assert expected["entities"] == {"Contact": ["birthday"]}
    assert expected["association_count"] == 1
