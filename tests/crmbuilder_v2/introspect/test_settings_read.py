"""Reading governed setting values with the ordinary credential — PI-406 (REQ-488)."""

from __future__ import annotations

from crmbuilder_v2.introspect.settings_read import (
    ABSENT,
    FORBIDDEN,
    OK,
    SETTINGS_ENTITY,
    UNAUTHENTICATED,
    UNREACHABLE,
    read_setting_values,
)


class _Client:
    """Returns one canned ``(status, body)``, and records what was asked for."""

    def __init__(self, status, body=None):
        self._status, self._body = status, body
        self.calls: list[str] = []

    def get_records(self, entity, **kwargs):
        self.calls.append(entity)
        return self._status, self._body


def _one(settings):
    return {"total": 1, "list": [{"id": "x", "settings": settings}]}


def test_values_are_returned_for_a_grant_backed_read():
    r = read_setting_values(
        _Client(200, _one({"outboundEmailFromAddress": "info@cbm.org"}))
    )
    assert r.outcome == OK
    assert r.values == {"outboundEmailFromAddress": "info@cbm.org"}
    assert r.configured is True


def test_nothing_configured_is_a_successful_read():
    """An instance built to report but never applied to holds no values. That is
    a real answer and the honest state of every instance before a first apply —
    it must not read as a failure."""
    r = read_setting_values(_Client(200, {"total": 0, "list": []}))
    assert r.outcome == OK
    assert r.values == {}
    assert r.configured is False
    assert r.reason is None


def test_a_missing_grant_is_never_reported_as_nothing_configured():
    """REQ-488's second clause. The CBM build hit exactly this on first attempt:
    the entity was correct in every structural respect and the API role had no
    grant on the scope. Reporting that as 'no values' would send someone to fix
    the design when the fix is one ACL grant."""
    r = read_setting_values(_Client(403))
    assert r.outcome == FORBIDDEN
    assert r.values == {}
    assert r.configured is False
    assert "grant" in r.reason


def test_a_rejected_credential_is_its_own_outcome():
    r = read_setting_values(_Client(401))
    assert r.outcome == UNAUTHENTICATED
    assert "credential" in r.reason


def test_an_unreachable_instance_leaves_the_values_unknown():
    """Not absent. The consumer's own documented failure mode is the silent
    pass, and an instance nobody could reach has told us nothing."""
    r = read_setting_values(_Client(-1, {"_request_failed": True}))
    assert r.outcome == UNREACHABLE
    assert r.configured is False


def test_a_missing_carrier_entity_is_absent_not_forbidden():
    r = read_setting_values(_Client(404))
    assert r.outcome == ABSENT
    assert "not present" in r.reason


def test_a_record_with_no_carrier_value_is_simply_unconfigured():
    r = read_setting_values(_Client(200, _one(None)))
    assert r.outcome == OK and r.values == {}


def test_an_uninterpretable_carrier_is_not_read_as_empty():
    """A carrier holding something other than a key-to-value mapping is not
    evidence that nothing is configured — reading it as empty would assert the
    instance holds nothing on the strength of a field we failed to understand."""
    r = read_setting_values(_Client(200, _one("outboundEmail=info@cbm.org")))
    assert r.outcome == UNREACHABLE
    assert r.values == {}


def test_only_the_governed_carrier_is_read():
    """REQ-488 forbids a second credential or a call to any other service. The
    read asks for one scope and nothing else."""
    client = _Client(200, {"total": 0, "list": []})
    read_setting_values(client)
    assert client.calls == [SETTINGS_ENTITY]


def test_every_failure_outcome_carries_a_reason_and_no_values():
    """A caller that ignores the outcome and reads values gets an empty mapping
    rather than a confident wrong answer about what the instance holds."""
    for status in (-1, 401, 403, 404, 500):
        r = read_setting_values(_Client(status))
        assert r.outcome != OK, status
        assert r.values == {}, status
        assert r.reason, status


def test_the_stamp_rides_along_with_a_successful_read():
    """REQ-495: the stamp lives in the instance and is readable with the same
    ordinary credential as the governed values."""
    from crmbuilder_v2.introspect.settings_read import OK, read_setting_values

    class _Client:
        def get_records(self, entity, **kwargs):
            return 200, {
                "total": 1,
                "list": [
                    {
                        "id": "r1",
                        "settings": {"orgName": "Cleveland"},
                        "standardVersion": "REL-045",
                        "planFingerprint": "f" * 64,
                    }
                ],
            }

    read = read_setting_values(_Client())
    assert read.outcome == OK
    assert read.standard_version == "REL-045"
    assert read.plan_fingerprint == "f" * 64


def test_a_never_stamped_instance_reads_as_unstamped_not_empty_string():
    from crmbuilder_v2.introspect.settings_read import OK, read_setting_values

    class _Client:
        def get_records(self, entity, **kwargs):
            return 200, {
                "total": 1,
                "list": [{"id": "r1", "settings": {}, "standardVersion": ""}],
            }

    read = read_setting_values(_Client())
    assert read.outcome == OK
    assert read.standard_version is None
    assert read.plan_fingerprint is None
