"""Tests for the field-level security rule manager (Section 12.7)."""

import pytest

from espo_impl.core.models import (
    FieldPermissionSpec,
    FieldVisibilitySpec,
    SecurityRuleStatus,
)
from espo_impl.core.security_rule_manager import (
    SecurityRuleManager,
    SecurityRuleManagerError,
)


class FakeClient:
    """Minimal stateful stand-in for ``EspoAdminClient`` Role I/O.

    Holds Role records keyed by id. ``update_role`` records every PATCH
    and (when ``persist``) applies the new ``fieldData`` so a post-PATCH
    re-read reflects the change — which is what the VERIFY phase reads.
    """

    def __init__(self, roles, *, persist=True, update_status=200):
        self._roles = {r["id"]: r for r in roles}
        self.persist = persist
        self.update_status = update_status
        self.update_calls: list[tuple[str, dict]] = []
        self.get_roles_calls = 0

    def get_roles(self):
        self.get_roles_calls += 1
        return (
            200,
            {"total": len(self._roles), "list": list(self._roles.values())},
        )

    def update_role(self, role_id, payload):
        self.update_calls.append((role_id, payload))
        rec = self._roles.get(role_id)
        if rec is None:
            return (404, {"message": "not found"})
        if self.update_status != 200:
            return (self.update_status, {"message": "boom"})
        if self.persist and "fieldData" in payload:
            rec["fieldData"] = payload["fieldData"]
        return (200, rec)


def role(id_, name, field_data=None):
    return {"id": id_, "name": name, "fieldData": field_data or {}}


def make_manager(client):
    log: list[tuple[str, str]] = []
    mgr = SecurityRuleManager(client, lambda m, c: log.append((m, c)))
    return mgr, log


# --- field_visibility: always NOT_SUPPORTED ---


def test_field_visibility_all_not_supported():
    client = FakeClient([])
    mgr, log = make_manager(client)
    vis = [
        FieldVisibilitySpec(role="Mentor Role", entity="CMentorProfile",
                            field="ssn", visible=False),
        FieldVisibilitySpec(role="Mentor Role", entity="CMentorProfile",
                            field="notes", visible=True),
    ]
    results = mgr.process_security_rules([], vis)
    assert [r.status for r in results] == [
        SecurityRuleStatus.NOT_SUPPORTED,
        SecurityRuleStatus.NOT_SUPPORTED,
    ]
    # No server round-trip for visibility-only input.
    assert client.update_calls == []
    assert any("[NOT SUPPORTED]" in m for m, _ in log)


# --- CHECK groups by role ---


def test_check_groups_by_role():
    client = FakeClient([
        role("r1", "Mentor Role"),
        role("r2", "Staff Role"),
    ])
    mgr, _ = make_manager(client)
    perms = [
        FieldPermissionSpec("Mentor Role", "CMentorProfile", "f1", "read_only"),
        FieldPermissionSpec("Staff Role", "CMentorProfile", "f2", "read_write"),
        FieldPermissionSpec("Mentor Role", "CMentorProfile", "f3", "no_access"),
    ]
    results = mgr.process_security_rules(perms, [])
    assert len(results) == 3
    # One PATCH per role, not per rule.
    assert len(client.update_calls) == 2
    patched_ids = {rid for rid, _ in client.update_calls}
    assert patched_ids == {"r1", "r2"}


# --- level -> fieldData cell mapping (all three levels) ---


@pytest.mark.parametrize("level,expected", [
    ("read_write", {"read": "yes", "edit": "yes"}),
    ("read_only", {"read": "yes", "edit": "no"}),
    ("no_access", {"read": "no", "edit": "no"}),
])
def test_level_to_field_data_cell(level, expected):
    client = FakeClient([role("r1", "Mentor Role")])
    mgr, _ = make_manager(client)
    perms = [FieldPermissionSpec("Mentor Role", "CMentorProfile", "f1", level)]
    results = mgr.process_security_rules(perms, [])
    assert results[0].status == SecurityRuleStatus.CREATED
    _, payload = client.update_calls[0]
    assert payload["fieldData"]["CMentorProfile"]["f1"] == expected


# --- MATCHES when already correct (no PATCH) ---


def test_matches_when_already_correct():
    existing = {"CMentorProfile": {"f1": {"read": "yes", "edit": "no"}}}
    client = FakeClient([role("r1", "Mentor Role", existing)])
    mgr, _ = make_manager(client)
    perms = [FieldPermissionSpec("Mentor Role", "CMentorProfile", "f1", "read_only")]
    results = mgr.process_security_rules(perms, [])
    assert results[0].status == SecurityRuleStatus.MATCHES
    assert client.update_calls == []


# --- CREATED vs UPDATED ---


def test_created_when_cell_absent_updated_when_changed():
    existing = {"CMentorProfile": {"f1": {"read": "no", "edit": "no"}}}
    client = FakeClient([role("r1", "Mentor Role", existing)])
    mgr, _ = make_manager(client)
    perms = [
        # f1 exists, changing -> UPDATED
        FieldPermissionSpec("Mentor Role", "CMentorProfile", "f1", "read_write"),
        # f2 absent -> CREATED
        FieldPermissionSpec("Mentor Role", "CMentorProfile", "f2", "read_only"),
    ]
    results = mgr.process_security_rules(perms, [])
    by_field = {r.field: r.status for r in results}
    assert by_field["f1"] == SecurityRuleStatus.UPDATED
    assert by_field["f2"] == SecurityRuleStatus.CREATED
    assert len(client.update_calls) == 1


# --- merge preserves unrelated fieldData cells ---


def test_merge_preserves_unrelated_cells():
    existing = {
        "OtherEntity": {"keep": {"read": "yes", "edit": "yes"}},
        "CMentorProfile": {"untouched": {"read": "yes", "edit": "no"}},
    }
    client = FakeClient([role("r1", "Mentor Role", existing)])
    mgr, _ = make_manager(client)
    perms = [FieldPermissionSpec("Mentor Role", "CMentorProfile", "f1", "no_access")]
    mgr.process_security_rules(perms, [])
    _, payload = client.update_calls[0]
    fd = payload["fieldData"]
    # New cell present.
    assert fd["CMentorProfile"]["f1"] == {"read": "no", "edit": "no"}
    # Unrelated cells preserved.
    assert fd["OtherEntity"]["keep"] == {"read": "yes", "edit": "yes"}
    assert fd["CMentorProfile"]["untouched"] == {"read": "yes", "edit": "no"}


# --- missing role -> per-rule ERROR (not a process abort) ---


def test_missing_role_yields_error():
    client = FakeClient([role("r1", "Staff Role")])
    mgr, _ = make_manager(client)
    perms = [FieldPermissionSpec("Mentor Role", "CMentorProfile", "f1", "read_only")]
    results = mgr.process_security_rules(perms, [])
    assert results[0].status == SecurityRuleStatus.ERROR
    assert "not found" in results[0].error
    assert client.update_calls == []


def test_missing_role_does_not_abort_other_roles():
    client = FakeClient([role("r2", "Staff Role")])
    mgr, _ = make_manager(client)
    perms = [
        FieldPermissionSpec("Mentor Role", "CMentorProfile", "f1", "read_only"),
        FieldPermissionSpec("Staff Role", "CMentorProfile", "f2", "read_write"),
    ]
    results = mgr.process_security_rules(perms, [])
    by_role = {(r.role, r.field): r.status for r in results}
    assert by_role[("Mentor Role", "f1")] == SecurityRuleStatus.ERROR
    assert by_role[("Staff Role", "f2")] == SecurityRuleStatus.CREATED


# --- VERIFY mismatch -> ERROR ---


def test_verify_mismatch_yields_error():
    # persist=False: PATCH "succeeds" but the read-back never reflects it,
    # so the VERIFY re-read sees the unchanged (empty) fieldData.
    client = FakeClient([role("r1", "Mentor Role")], persist=False)
    mgr, _ = make_manager(client)
    perms = [FieldPermissionSpec("Mentor Role", "CMentorProfile", "f1", "read_write")]
    results = mgr.process_security_rules(perms, [])
    assert results[0].status == SecurityRuleStatus.ERROR
    assert "verification mismatch" in results[0].error


# --- PATCH HTTP failure -> ERROR ---


def test_patch_failure_yields_error():
    client = FakeClient([role("r1", "Mentor Role")], update_status=500)
    mgr, _ = make_manager(client)
    perms = [FieldPermissionSpec("Mentor Role", "CMentorProfile", "f1", "read_only")]
    results = mgr.process_security_rules(perms, [])
    assert results[0].status == SecurityRuleStatus.ERROR
    assert "HTTP 500" in results[0].error


# --- 401 propagates as SecurityRuleManagerError ---


def test_auth_failure_on_patch_raises():
    client = FakeClient([role("r1", "Mentor Role")], update_status=401)
    mgr, _ = make_manager(client)
    perms = [FieldPermissionSpec("Mentor Role", "CMentorProfile", "f1", "read_only")]
    with pytest.raises(SecurityRuleManagerError):
        mgr.process_security_rules(perms, [])


# --- dry_run issues no writes ---


def test_dry_run_issues_no_writes():
    client = FakeClient([role("r1", "Mentor Role")])
    mgr, _ = make_manager(client)
    perms = [FieldPermissionSpec("Mentor Role", "CMentorProfile", "f1", "read_write")]
    results = mgr.process_security_rules(perms, [], dry_run=True)
    assert results[0].status == SecurityRuleStatus.CREATED
    assert client.update_calls == []


# --- empty input is a clean no-op ---


def test_empty_input_no_op():
    client = FakeClient([role("r1", "Mentor Role")])
    mgr, _ = make_manager(client)
    results = mgr.process_security_rules([], [])
    assert results == []
    assert client.get_roles_calls == 0
    assert client.update_calls == []
