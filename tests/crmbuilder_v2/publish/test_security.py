"""Tests for applying declared teams, roles and field permissions
(REQ-614 / PI-528).
"""

from __future__ import annotations

from typing import Any

import pytest
from crmbuilder_v2.publish import security as sec
from crmbuilder_v2.publish.entities import AuthenticationRejected
from crmbuilder_v2.publish.security import (
    FieldPermission,
    RoleIntent,
    TeamIntent,
    apply_role,
    apply_teams,
    merged_field_data,
    role_payload,
    scope_data,
)


class FakeClient:
    def __init__(
        self,
        teams: list[dict[str, Any]] | None = None,
        roles: list[dict[str, Any]] | None = None,
        scopes: dict[str, Any] | None = None,
    ) -> None:
        self.teams = teams or []
        self.roles = roles or []
        self.scopes = scopes if scopes is not None else {"Account": {}, "CEngagement": {}}
        self.teams_status = 200
        self.roles_status = 200
        self.scopes_status = 200
        self.calls: list[tuple[str, Any]] = []
        self.create_role_answers: list[tuple[int, Any]] = [(200, {})]
        self.update_role_answers: list[tuple[int, Any]] = [(200, {})]
        self.create_team_answers: list[tuple[int, Any]] = [(200, {})]
        self.update_team_answers: list[tuple[int, Any]] = [(200, {})]
        #: What the role looks like when read back after writing.
        self.roles_after_write: list[dict[str, Any]] | None = None

    @staticmethod
    def _next(queue: list) -> Any:
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def get_all_scopes(self) -> tuple[int, Any]:
        self.calls.append(("scopes", None))
        return self.scopes_status, self.scopes

    def get_teams(self) -> tuple[int, Any]:
        self.calls.append(("teams", None))
        return self.teams_status, {"list": list(self.teams)}

    def get_roles(self) -> tuple[int, Any]:
        self.calls.append(("roles", None))
        wrote = any(kind in ("create_role", "update_role") for kind, _ in self.calls)
        rows = (
            self.roles_after_write
            if wrote and self.roles_after_write is not None
            else self.roles
        )
        return self.roles_status, {"list": list(rows)}

    def create_team(self, name: str, description: str | None = None):
        self.calls.append(("create_team", (name, description)))
        return self._next(self.create_team_answers)

    def update_team(self, team_id: str, description: str | None = None):
        self.calls.append(("update_team", (team_id, description)))
        return self._next(self.update_team_answers)

    def create_role(self, payload: dict):
        self.calls.append(("create_role", payload))
        return self._next(self.create_role_answers)

    def update_role(self, role_id: str, payload: dict):
        self.calls.append(("update_role", (role_id, payload)))
        return self._next(self.update_role_answers)

    @property
    def kinds(self) -> list[str]:
        return [kind for kind, _ in self.calls]


# --- teams ------------------------------------------------------------------


def test_a_missing_team_is_created() -> None:
    client = FakeClient()
    [outcome] = apply_teams(client, [TeamIntent("Mentors", "The cohort")])
    assert outcome.status == sec.CREATED
    assert ("create_team", ("Mentors", "The cohort")) in client.calls


def test_a_team_already_as_declared_is_left_alone() -> None:
    client = FakeClient(teams=[{"id": "1", "name": "Mentors", "description": "X"}])
    [outcome] = apply_teams(client, [TeamIntent("Mentors", "X")])
    assert outcome.status == sec.SKIPPED


def test_only_the_description_is_ever_changed() -> None:
    """A rename would detach the team from the design that names it."""
    client = FakeClient(teams=[{"id": "1", "name": "Mentors", "description": "Old"}])
    [outcome] = apply_teams(client, [TeamIntent("Mentors", "New")])
    assert outcome.status == sec.UPDATED
    assert ("update_team", ("1", "New")) in client.calls


def test_a_team_whose_description_the_design_omits_is_left_alone() -> None:
    client = FakeClient(teams=[{"id": "1", "name": "Mentors", "description": "Old"}])
    [outcome] = apply_teams(client, [TeamIntent("Mentors")])
    assert outcome.status == sec.SKIPPED


def test_teams_that_cannot_be_listed_fail_rather_than_being_recreated() -> None:
    client = FakeClient()
    client.teams_status = 500
    [outcome] = apply_teams(client, [TeamIntent("Mentors")])
    assert outcome.failed
    assert "create_team" not in client.kinds


# --- the shape of a role ----------------------------------------------------


def test_object_types_are_named_the_platform_s_way() -> None:
    data = scope_data({"Engagement": {"read": "own"}})
    assert "CEngagement" in data


def test_whether_someone_may_create_is_a_yes_or_no() -> None:
    data = scope_data({"Account": {"create": True, "read": "all"}})
    assert data["Account"]["create"] == "yes"
    assert data["Account"]["read"] == "all"


def test_an_object_type_the_design_omits_is_omitted_from_the_role() -> None:
    """Omission denies; it does not inherit."""
    data = scope_data({"Account": {"read": "all"}})
    assert list(data) == ["Account"]


def test_only_the_permissions_the_design_declares_are_sent() -> None:
    """A role carries permissions this system does not model, and a person
    may have set them."""
    intent = RoleIntent("Mentor", {"Account": {"read": "all"}}, {"export": "no"})
    payload = role_payload(intent, include_name=False)
    assert payload["exportPermission"] == "no"
    assert "assignmentPermission" not in payload
    assert "name" not in payload


# --- field permissions ------------------------------------------------------


def test_only_the_named_cells_are_merged() -> None:
    current = {"Account": {"sicCode": "no"}, "Contact": {"salary": "no"}}
    merged = merged_field_data(
        current, [FieldPermission("Account", "revenue", "read")]
    )
    assert merged["Account"] == {"sicCode": "no", "revenue": "read"}
    assert merged["Contact"] == {"salary": "no"}


def test_a_field_permission_is_proved_by_reading_the_role_back() -> None:
    client = FakeClient(roles=[{"id": "1", "name": "Mentor", "fieldData": {}}])
    client.roles_after_write = [
        {
            "id": "1",
            "name": "Mentor",
            "fieldData": {"Account": {"revenue": "read"}},
        }
    ]
    outcome = apply_role(
        client,
        RoleIntent(
            "Mentor",
            {"Account": {"read": "all"}},
            field_permissions=[FieldPermission("Account", "revenue", "read")],
        ),
    )
    assert outcome.status == sec.UPDATED
    assert outcome.verified


def test_a_field_permission_the_instance_did_not_keep_is_a_failure() -> None:
    """Silently dropped is indistinguishable from applied, until somebody
    sees a field they should not."""
    client = FakeClient(roles=[{"id": "1", "name": "Mentor", "fieldData": {}}])
    client.roles_after_write = [{"id": "1", "name": "Mentor", "fieldData": {}}]
    outcome = apply_role(
        client,
        RoleIntent(
            "Mentor",
            {"Account": {"read": "all"}},
            field_permissions=[FieldPermission("Account", "revenue", "read")],
        ),
    )
    assert outcome.failed
    assert "Account.revenue" in outcome.detail


# --- applying a role --------------------------------------------------------


def test_a_missing_role_is_created_with_its_name() -> None:
    client = FakeClient()
    outcome = apply_role(client, RoleIntent("Mentor", {"Account": {"read": "all"}}))
    assert outcome.status == sec.CREATED
    sent = next(payload for kind, payload in client.calls if kind == "create_role")
    assert sent["name"] == "Mentor"


def test_a_role_naming_an_object_type_the_instance_lacks_is_refused() -> None:
    client = FakeClient(scopes={"Account": {}})
    outcome = apply_role(
        client, RoleIntent("Mentor", {"Engagement": {"read": "all"}})
    )
    assert outcome.status == sec.REFUSED
    assert "Engagement" in outcome.detail
    assert "create_role" not in client.kinds


def test_a_refused_role_write_is_reported() -> None:
    client = FakeClient()
    client.create_role_answers = [(400, {"message": "bad data"})]
    outcome = apply_role(client, RoleIntent("Mentor", {"Account": {"read": "all"}}))
    assert outcome.failed
    assert "400" in outcome.detail


def test_a_rejected_credential_stops_the_run() -> None:
    client = FakeClient()
    client.scopes_status = 401
    with pytest.raises(AuthenticationRejected):
        apply_role(client, RoleIntent("Mentor", {"Account": {"read": "all"}}))


def test_preview_writes_nothing() -> None:
    client = FakeClient(roles=[{"id": "1", "name": "Mentor"}])
    outcome = apply_role(
        client, RoleIntent("Mentor", {"Account": {"read": "all"}}), preview=True
    )
    assert outcome.status == sec.PREVIEWED
    assert "update_role" not in client.kinds
