"""Tests for the relationship manager."""

from unittest.mock import MagicMock

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.models import (
    RelationshipDefinition,
    RelationshipStatus,
)
from espo_impl.core.relationship_manager import (
    RelationshipManager,
)


def make_rel(**kwargs) -> RelationshipDefinition:
    defaults = {
        "name": "testRel",
        "entity": "Session",
        "entity_foreign": "Engagement",
        "link_type": "manyToOne",
        "link": "sessionEngagement",
        "link_foreign": "engagementSessions",
        "label": "Engagement",
        "label_foreign": "Sessions",
    }
    defaults.update(kwargs)
    return RelationshipDefinition(**defaults)


def make_manager(client=None) -> tuple[RelationshipManager, list]:
    if client is None:
        client = MagicMock(spec=EspoAdminClient)
    output_log: list[tuple[str, str]] = []

    def output_fn(msg, color):
        output_log.append((msg, color))

    manager = RelationshipManager(client, output_fn)
    return manager, output_log


def test_build_payload_one_to_many():
    manager, _ = make_manager()
    rel = make_rel(
        entity="Engagement",
        entity_foreign="Session",
        link_type="oneToMany",
        link="engagementSessions",
        link_foreign="sessionEngagement",
    )
    payload = manager._build_payload(rel)
    assert payload["entity"] == "CEngagement"
    assert payload["entityForeign"] == "CSessions"
    assert payload["linkType"] == "oneToMany"
    assert payload["relationName"] is None


def test_build_payload_many_to_many():
    manager, _ = make_manager()
    rel = make_rel(
        link_type="manyToMany",
        relation_name="cSessionMentorAttendee",
    )
    payload = manager._build_payload(rel)
    assert payload["linkType"] == "manyToMany"
    assert payload["relationName"] == "cSessionMentorAttendee"


def test_compare_link_matches():
    manager, _ = make_manager()
    existing = {
        "type": "belongsTo",
        "entity": "CEngagement",
        "foreign": "engagementSessions",
    }
    rel = make_rel()
    assert manager._compare_link(existing, rel, "CEngagement") is True


def test_compare_link_type_mismatch():
    manager, _ = make_manager()
    existing = {
        "type": "hasMany",
        "entity": "CEngagement",
        "foreign": "engagementSessions",
    }
    rel = make_rel()
    assert manager._compare_link(existing, rel, "CEngagement") is False


def test_compare_link_entity_mismatch():
    manager, _ = make_manager()
    existing = {
        "type": "belongsTo",
        "entity": "Contact",
        "foreign": "engagementSessions",
    }
    rel = make_rel()
    assert manager._compare_link(existing, rel, "CEngagement") is False


def test_action_skip_immediately():
    client = MagicMock(spec=EspoAdminClient)
    manager, output_log = make_manager(client)
    rel = make_rel(action="skip")

    results = manager.process_relationships([rel])

    assert len(results) == 1
    assert results[0].status == RelationshipStatus.SKIPPED
    client.get_link.assert_not_called()
    client.create_link.assert_not_called()


def test_existing_matching_link_skips():
    client = MagicMock(spec=EspoAdminClient)
    client.get_link.return_value = (200, {
        "type": "belongsTo",
        "entity": "CEngagement",
        "foreign": "engagementSessions",
    })

    manager, output_log = make_manager(client)
    results = manager.process_relationships([make_rel()])

    assert results[0].status == RelationshipStatus.SKIPPED
    client.create_link.assert_not_called()


def test_existing_mismatched_link_warns():
    client = MagicMock(spec=EspoAdminClient)
    client.get_link.return_value = (200, {
        "type": "hasMany",
        "entity": "Contact",
        "foreign": "differentLink",
    })

    manager, output_log = make_manager(client)
    results = manager.process_relationships([make_rel()])

    assert results[0].status == RelationshipStatus.WARNING
    client.create_link.assert_not_called()
    messages = [m for m, _ in output_log]
    assert any("DIFFERS" in m for m in messages)


def test_missing_link_creates():
    client = MagicMock(spec=EspoAdminClient)
    # Check returns empty (missing)
    client.get_link.side_effect = [
        (200, None),  # check
        (200, {       # verify
            "type": "belongsTo",
            "entity": "CEngagement",
            "foreign": "engagementSessions",
        }),
    ]
    client.create_link.return_value = (200, {})

    manager, output_log = make_manager(client)
    results = manager.process_relationships([make_rel()])

    assert results[0].status == RelationshipStatus.CREATED
    assert results[0].verified is True
    client.create_link.assert_called_once()


def test_401_raises_error():
    client = MagicMock(spec=EspoAdminClient)
    client.get_link.return_value = (401, None)

    manager, output_log = make_manager(client)
    results = manager.process_relationships([make_rel()])

    assert results[0].status == RelationshipStatus.ERROR
    assert "401" in results[0].message


def test_403_continues():
    client = MagicMock(spec=EspoAdminClient)
    client.get_link.side_effect = [
        (200, None),  # check — missing
    ]
    client.create_link.return_value = (403, {"message": "Forbidden"})

    manager, output_log = make_manager(client)
    results = manager.process_relationships([make_rel()])

    assert results[0].status == RelationshipStatus.ERROR
    messages = [m for m, _ in output_log]
    assert any("403" in m for m in messages)


def test_create_and_verify():
    client = MagicMock(spec=EspoAdminClient)
    client.get_link.side_effect = [
        (200, None),  # check — missing
        (200, {       # verify — matches
            "type": "belongsTo",
            "entity": "CEngagement",
            "foreign": "engagementSessions",
        }),
    ]
    client.create_link.return_value = (200, {})

    manager, output_log = make_manager(client)
    results = manager.process_relationships([make_rel()])

    assert results[0].status == RelationshipStatus.CREATED
    assert results[0].verified is True
    messages = [m for m, _ in output_log]
    assert any("VERIFIED" in m for m in messages)


def test_verify_always_logged_after_create():
    """Verify is always called and logged after a successful create."""
    client = MagicMock(spec=EspoAdminClient)
    # Check returns missing, then verify returns non-matching data
    client.get_link.side_effect = [
        (200, None),  # check — missing
        (200, {       # verify — does NOT match
            "type": "hasMany",
            "entity": "WrongEntity",
            "foreign": "wrongLink",
        }),
    ]
    client.create_link.return_value = (200, {})

    manager, output_log = make_manager(client)
    results = manager.process_relationships([make_rel()])

    assert results[0].status == RelationshipStatus.CREATED
    assert results[0].verified is False
    messages = [m for m, _ in output_log]
    # Must have CREATED OK followed by a verify log line
    assert any("CREATED OK" in m for m in messages)
    assert any("VERIFY FAILED" in m for m in messages)


def test_compare_link_missing_foreign_key():
    """Missing foreign key in metadata is treated as a match."""
    manager, _ = make_manager()
    existing = {
        "type": "belongsTo",
        "entity": "CEngagement",
        # No "foreign" key
    }
    rel = make_rel()
    assert manager._compare_link(existing, rel, "CEngagement") is True


def test_verify_uses_c_prefix_for_native_entity():
    """Verify step checks c-prefixed link name for native entity primary side."""
    client = MagicMock(spec=EspoAdminClient)
    # For native entity "Account":
    # 1. c-prefix probe: not found yet (before create)
    # 2. check with original name: missing
    # 3. verify with c-prefixed name: matches
    client.get_link.side_effect = [
        (200, None),  # c-prefix probe
        (200, None),  # check with original name — missing
        (200, {       # verify with c-prefixed name — matches
            "type": "hasMany",
            "entity": "Contact",
            "foreign": "cAccountPartners",
        }),
    ]
    client.create_link.return_value = (200, {})

    manager, output_log = make_manager(client)
    rel = make_rel(
        entity="Account",
        entity_foreign="Contact",
        link_type="oneToMany",
        link="partnerAgreements",
        link_foreign="accountPartners",
    )
    results = manager.process_relationships([rel])

    assert results[0].status == RelationshipStatus.CREATED
    assert results[0].verified is True
    messages = [m for m, _ in output_log]
    assert any("VERIFIED" in m for m in messages)
    # Verify was called with c-prefixed name
    verify_call = client.get_link.call_args_list[-1]
    assert verify_call[0] == ("Account", "cPartnerAgreements")


def test_error_includes_response_body():
    """Error output includes EspoCRM response body, not just status code."""
    client = MagicMock(spec=EspoAdminClient)
    client.get_link.return_value = (200, None)  # check — missing
    client.create_link.return_value = (
        409,
        {"message": "Link already exists with a different configuration"},
    )

    manager, output_log = make_manager(client)
    results = manager.process_relationships([make_rel()])

    assert results[0].status == RelationshipStatus.ERROR
    messages = [m for m, _ in output_log]
    error_msgs = [m for m in messages if "ERROR" in m]
    assert len(error_msgs) >= 1
    # The error detail must be in the main error line, not a separate line
    assert any("Link already exists" in m for m in error_msgs)
    assert "409" in error_msgs[0]
