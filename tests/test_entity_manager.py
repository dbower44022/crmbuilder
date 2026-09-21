"""Tests for the entity manager orchestration logic."""

from unittest.mock import MagicMock, patch

from espo_impl.core.entity_manager import EntityManager
from espo_impl.core.models import EntityAction, EntityDefinition


def make_entity(
    name="TestEntity",
    action=EntityAction.CREATE,
    **kwargs,
) -> EntityDefinition:
    defaults = {
        "fields": [],
        "type": "Base",
        "labelSingular": name,
        "labelPlural": f"{name}s",
    }
    defaults.update(kwargs)
    return EntityDefinition(name=name, action=action, **defaults)


def make_manager(client=None) -> tuple[EntityManager, list]:
    if client is None:
        client = MagicMock()
    output_log: list[tuple[str, str]] = []

    def output_fn(msg, color):
        output_log.append((msg, color))

    manager = EntityManager(client, output_fn)
    return manager, output_log


def test_rebuild_cache_success():
    client = MagicMock()
    client.rebuild.return_value = (200, {})

    manager, output_log = make_manager(client)
    result = manager.rebuild_cache()

    assert result is True
    messages = [msg for msg, _ in output_log]
    assert any("rebuild complete" in msg for msg in messages)


def test_rebuild_cache_failure():
    client = MagicMock()
    client.rebuild.return_value = (500, {"message": "Error"})

    manager, output_log = make_manager(client)
    result = manager.rebuild_cache()

    assert result is False


def test_wait_for_metadata_ready_returns_true_immediately_when_cached():
    """When metadata is already cached, wait returns True on first
    poll without sleeping noticeably."""
    client = MagicMock()
    client.get_entity_full_metadata.return_value = (
        200,
        {"name": "CEngagement", "fields": {}},
    )

    manager, output_log = make_manager(client)
    with patch("espo_impl.core.entity_manager.time.sleep"):
        result = manager.wait_for_metadata_ready(
            ["Engagement"], timeout_seconds=10.0
        )

    assert result is True
    assert client.get_entity_full_metadata.call_count == 1
    messages = [msg for msg, _ in output_log]
    assert any("Metadata cache ready" in msg for msg in messages)


def test_wait_for_metadata_ready_polls_until_ready():
    """When metadata is initially unavailable, wait polls until it
    materializes, then returns True."""
    client = MagicMock()
    client.get_entity_full_metadata.side_effect = [
        (200, None),
        (200, None),
        (200, {"name": "CSession", "fields": {}}),
    ]

    manager, output_log = make_manager(client)
    with patch("espo_impl.core.entity_manager.time.sleep"):
        result = manager.wait_for_metadata_ready(
            ["Session"], timeout_seconds=30.0
        )

    assert result is True
    assert client.get_entity_full_metadata.call_count == 3
    messages = [msg for msg, _ in output_log]
    assert any("ready" in msg for msg in messages)


def test_wait_for_metadata_ready_returns_false_on_timeout():
    """When metadata never materializes within the timeout, wait
    returns False and emits a TIMED OUT line for each entity."""
    client = MagicMock()
    client.get_entity_full_metadata.return_value = (200, None)

    # time.monotonic() advances rapidly to expire the deadline
    # after a couple of polls. The first call is when the deadline
    # is computed; subsequent calls are the loop guard.
    monotonic_values = iter([0.0, 1.0, 100.0, 200.0])

    manager, output_log = make_manager(client)
    with (
        patch("espo_impl.core.entity_manager.time.sleep"),
        patch(
            "espo_impl.core.entity_manager.time.monotonic",
            side_effect=lambda: next(monotonic_values),
        ),
    ):
        result = manager.wait_for_metadata_ready(
            ["Session"], timeout_seconds=5.0
        )

    assert result is False
    messages = [msg for msg, _ in output_log]
    assert any("TIMED OUT" in msg for msg in messages)
    assert any("proceeding anyway" in msg for msg in messages)


def test_wait_for_metadata_ready_handles_mixed_entities():
    """When some entities are ready and others aren't, wait keeps
    polling only the unready ones."""
    client = MagicMock()
    # Iteration 1: Engagement ready, Session not. Iteration 2:
    # Session still not. Iteration 3: Session ready.
    call_log: list[str] = []

    def fake_get_meta(espo_name: str):
        call_log.append(espo_name)
        if espo_name == "CEngagement":
            return (200, {"name": "CEngagement", "fields": {}})
        # CSession: empty on first 2 calls, ready on 3rd
        sessions_calls = sum(
            1 for n in call_log if n == "CSession"
        )
        if sessions_calls <= 2:
            return (200, None)
        return (200, {"name": "CSession", "fields": {}})

    client.get_entity_full_metadata.side_effect = fake_get_meta

    manager, output_log = make_manager(client)
    with patch("espo_impl.core.entity_manager.time.sleep"):
        result = manager.wait_for_metadata_ready(
            ["Engagement", "Session"], timeout_seconds=30.0
        )

    assert result is True
    engagement_calls = sum(1 for n in call_log if n == "CEngagement")
    sessions_calls = sum(1 for n in call_log if n == "CSession")
    assert engagement_calls == 1
    assert sessions_calls >= 3


def test_wait_for_metadata_ready_no_entities_returns_true():
    """Calling with an empty list short-circuits to True with no polls."""
    client = MagicMock()

    manager, output_log = make_manager(client)
    result = manager.wait_for_metadata_ready([])

    assert result is True
    client.get_entity_full_metadata.assert_not_called()


def test_get_espo_entity_name_universal_c_prefix_rule():
    """Custom entity names always resolve to f'C{name}', with no
    pluralization or renaming. Native entities are unchanged."""
    from espo_impl.ui.confirm_delete_dialog import get_espo_entity_name

    # Custom entities — universal C prefix rule
    assert get_espo_entity_name("Engagement") == "CEngagement"
    assert get_espo_entity_name("Session") == "CSession"
    assert get_espo_entity_name("Workshop") == "CWorkshop"
    assert get_espo_entity_name("WorkshopAttendance") == "CWorkshopAttendance"
    assert get_espo_entity_name("NpsSurveyResponse") == "CNpsSurveyResponse"
    assert get_espo_entity_name("Contribution") == "CContribution"

    # Native entities — unchanged
    assert get_espo_entity_name("Contact") == "Contact"
    assert get_espo_entity_name("Account") == "Account"
    assert get_espo_entity_name("Lead") == "Lead"
    assert get_espo_entity_name("Meeting") == "Meeting"
