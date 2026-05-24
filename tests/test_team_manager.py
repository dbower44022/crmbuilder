"""Tests for the team manager orchestration logic."""

from unittest.mock import MagicMock

import pytest

from espo_impl.core.models import (
    TeamDefinition,
    TeamStatus,
)
from espo_impl.core.team_manager import TeamManager, TeamManagerError


def make_manager(client=None) -> tuple[TeamManager, list]:
    if client is None:
        client = MagicMock()
    output_log: list[tuple[str, str]] = []
    manager = TeamManager(
        client, lambda msg, color: output_log.append((msg, color)),
    )
    return manager, output_log


def server_response(teams: list[dict]) -> tuple[int, dict]:
    return (200, {"total": len(teams), "list": teams})


# --- Empty input ---


def test_empty_teams_returns_empty_list_no_api_call():
    client = MagicMock()
    manager, _ = make_manager(client)
    results = manager.process_teams([], dry_run=False)
    assert results == []
    assert client.get_teams.call_count == 0
    assert client.create_team.call_count == 0
    assert client.update_team.call_count == 0


# --- Create path ---


def test_create_when_server_has_no_teams():
    client = MagicMock()
    client.get_teams.return_value = server_response([])
    client.create_team.return_value = (
        201, {"id": "team-abc", "name": "Mentors"},
    )
    manager, _ = make_manager(client)
    teams = [TeamDefinition(name="Mentors", description="The mentors team")]
    results = manager.process_teams(teams)
    assert len(results) == 1
    assert results[0].status == TeamStatus.CREATED
    assert results[0].team_id == "team-abc"
    assert results[0].error is None
    client.create_team.assert_called_once_with("Mentors", "The mentors team")


def test_create_status_200_also_accepted():
    client = MagicMock()
    client.get_teams.return_value = server_response([])
    client.create_team.return_value = (200, {"id": "team-200"})
    manager, _ = make_manager(client)
    teams = [TeamDefinition(name="Staff")]
    results = manager.process_teams(teams)
    assert results[0].status == TeamStatus.CREATED
    assert results[0].team_id == "team-200"


def test_create_dry_run_does_not_call_api():
    client = MagicMock()
    client.get_teams.return_value = server_response([])
    manager, _ = make_manager(client)
    teams = [TeamDefinition(name="Mentors", description="x")]
    results = manager.process_teams(teams, dry_run=True)
    assert results[0].status == TeamStatus.CREATED
    assert results[0].team_id is None
    assert client.create_team.call_count == 0


def test_create_with_no_description_passes_none():
    client = MagicMock()
    client.get_teams.return_value = server_response([])
    client.create_team.return_value = (201, {"id": "team-x"})
    manager, _ = make_manager(client)
    teams = [TeamDefinition(name="Plain")]
    manager.process_teams(teams)
    client.create_team.assert_called_once_with("Plain", None)


# --- Skip path ---


def test_skip_when_name_and_description_match():
    client = MagicMock()
    client.get_teams.return_value = server_response([
        {"id": "team-1", "name": "Mentors", "description": "x"},
    ])
    manager, _ = make_manager(client)
    teams = [TeamDefinition(name="Mentors", description="x")]
    results = manager.process_teams(teams)
    assert results[0].status == TeamStatus.SKIPPED
    assert results[0].team_id == "team-1"
    assert client.update_team.call_count == 0


def test_skip_server_empty_string_vs_yaml_none():
    client = MagicMock()
    client.get_teams.return_value = server_response([
        {"id": "team-1", "name": "Mentors", "description": ""},
    ])
    manager, _ = make_manager(client)
    teams = [TeamDefinition(name="Mentors", description=None)]
    results = manager.process_teams(teams)
    assert results[0].status == TeamStatus.SKIPPED
    assert client.update_team.call_count == 0


def test_skip_server_none_vs_yaml_empty_string():
    client = MagicMock()
    client.get_teams.return_value = server_response([
        {"id": "team-1", "name": "Mentors", "description": None},
    ])
    manager, _ = make_manager(client)
    teams = [TeamDefinition(name="Mentors", description="")]
    results = manager.process_teams(teams)
    assert results[0].status == TeamStatus.SKIPPED
    assert client.update_team.call_count == 0


# --- Update path ---


def test_update_when_description_differs():
    client = MagicMock()
    client.get_teams.return_value = server_response([
        {"id": "team-1", "name": "Mentors", "description": "old"},
    ])
    client.update_team.return_value = (200, {})
    manager, _ = make_manager(client)
    teams = [TeamDefinition(name="Mentors", description="new")]
    results = manager.process_teams(teams)
    assert results[0].status == TeamStatus.UPDATED
    assert results[0].team_id == "team-1"
    client.update_team.assert_called_once_with("team-1", "new")


def test_update_dry_run_does_not_call_api():
    client = MagicMock()
    client.get_teams.return_value = server_response([
        {"id": "team-1", "name": "Mentors", "description": "old"},
    ])
    manager, _ = make_manager(client)
    teams = [TeamDefinition(name="Mentors", description="new")]
    results = manager.process_teams(teams, dry_run=True)
    assert results[0].status == TeamStatus.UPDATED
    assert results[0].team_id == "team-1"
    assert client.update_team.call_count == 0


# --- Error paths ---


def test_get_teams_401_raises():
    client = MagicMock()
    client.get_teams.return_value = (401, None)
    manager, _ = make_manager(client)
    with pytest.raises(TeamManagerError):
        manager.process_teams([TeamDefinition(name="Mentors")])


def test_get_teams_500_raises():
    client = MagicMock()
    client.get_teams.return_value = (500, {"message": "boom"})
    manager, _ = make_manager(client)
    with pytest.raises(TeamManagerError):
        manager.process_teams([TeamDefinition(name="Mentors")])


def test_server_duplicate_names_produce_per_team_error():
    client = MagicMock()
    client.get_teams.return_value = server_response([
        {"id": "team-a", "name": "Mentors", "description": "first"},
        {"id": "team-b", "name": "Mentors", "description": "second"},
        {"id": "team-c", "name": "Staff", "description": ""},
    ])
    manager, _ = make_manager(client)
    teams = [
        TeamDefinition(name="Mentors", description="x"),
        TeamDefinition(name="Staff"),
    ]
    results = manager.process_teams(teams)
    assert results[0].status == TeamStatus.ERROR
    assert "multiple server teams" in results[0].error
    assert results[1].status == TeamStatus.SKIPPED
    assert results[1].team_id == "team-c"


def test_create_500_produces_per_team_error_batch_continues():
    client = MagicMock()
    client.get_teams.return_value = server_response([])
    client.create_team.side_effect = [
        (500, {"message": "boom"}),
        (201, {"id": "team-ok"}),
    ]
    manager, _ = make_manager(client)
    teams = [
        TeamDefinition(name="Fails"),
        TeamDefinition(name="Works"),
    ]
    results = manager.process_teams(teams)
    assert results[0].status == TeamStatus.ERROR
    assert "500" in results[0].error
    assert results[1].status == TeamStatus.CREATED
    assert results[1].team_id == "team-ok"


def test_update_500_produces_per_team_error_batch_continues():
    client = MagicMock()
    client.get_teams.return_value = server_response([
        {"id": "team-1", "name": "Fails", "description": "old"},
        {"id": "team-2", "name": "Works", "description": "old"},
    ])
    client.update_team.side_effect = [
        (500, {"message": "boom"}),
        (200, {}),
    ]
    manager, _ = make_manager(client)
    teams = [
        TeamDefinition(name="Fails", description="new"),
        TeamDefinition(name="Works", description="new"),
    ]
    results = manager.process_teams(teams)
    assert results[0].status == TeamStatus.ERROR
    assert "500" in results[0].error
    assert results[1].status == TeamStatus.UPDATED


def test_create_401_raises_halts_batch():
    client = MagicMock()
    client.get_teams.return_value = server_response([])
    client.create_team.return_value = (401, None)
    manager, _ = make_manager(client)
    teams = [
        TeamDefinition(name="A"),
        TeamDefinition(name="B"),
    ]
    with pytest.raises(TeamManagerError):
        manager.process_teams(teams)


def test_update_401_raises_halts_batch():
    client = MagicMock()
    client.get_teams.return_value = server_response([
        {"id": "team-1", "name": "A", "description": "old"},
    ])
    client.update_team.return_value = (401, None)
    manager, _ = make_manager(client)
    teams = [TeamDefinition(name="A", description="new")]
    with pytest.raises(TeamManagerError):
        manager.process_teams(teams)


# --- Mixed batch ---


def test_mixed_batch_create_skip_update():
    client = MagicMock()
    client.get_teams.return_value = server_response([
        {"id": "team-skip", "name": "Skipper", "description": "same"},
        {"id": "team-upd", "name": "Updater", "description": "old"},
    ])
    client.create_team.return_value = (201, {"id": "team-new"})
    client.update_team.return_value = (200, {})
    manager, _ = make_manager(client)
    teams = [
        TeamDefinition(name="Creator", description="fresh"),
        TeamDefinition(name="Skipper", description="same"),
        TeamDefinition(name="Updater", description="new"),
    ]
    results = manager.process_teams(teams)
    assert len(results) == 3
    assert results[0].status == TeamStatus.CREATED
    assert results[0].team_id == "team-new"
    assert results[1].status == TeamStatus.SKIPPED
    assert results[1].team_id == "team-skip"
    assert results[2].status == TeamStatus.UPDATED
    assert results[2].team_id == "team-upd"
    client.create_team.assert_called_once_with("Creator", "fresh")
    client.update_team.assert_called_once_with("team-upd", "new")
