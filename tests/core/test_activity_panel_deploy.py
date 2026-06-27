"""Tests for the activity-panel deploy coordinator (PI-338 / REQ-379).

SSH and the metadata-patch I/O are mocked; the coordinator's sequencing and
result aggregation are exercised against a stateful fake EspoAdminClient.
"""

from unittest.mock import patch

from automation.core.deployment import activity_panel_deploy as apd
from espo_impl.core.activity_panel_manager import build_bottom_panels_detail_layout


class StatefulClient:
    """Fake EspoAdminClient: tracks which entities are registered / streamed /
    have panel layouts, so the coordinator's reads reflect its writes."""

    def __init__(self, registered=()):
        self.registered = set(registered)
        self.streamed = set()
        self.layouts = {}

    # --- reads ---
    def get_metadata(self, key):
        if key.endswith("parent.entityList"):
            return 200, sorted(self.registered)
        return 200, None

    def get_layout(self, entity, layout_type):
        if entity in self.layouts:
            return 200, self.layouts[entity]
        return 200, {}

    # --- writes ---
    def update_entity(self, payload):
        if payload.get("stream"):
            self.streamed.add(payload["name"])
        return 200, {}

    def save_layout(self, entity, layout_type, payload):
        self.layouts[entity] = payload
        return 200, {}


class FakeSSH:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def _patches(client):
    """Patch connect_ssh + the SSH I/O so register marks the client registered."""

    def fake_register(ssh, c, entities, ts, holders=apd.PANEL_HOLDERS, log=None):
        c.registered.update(entities)
        return dict.fromkeys(holders, True)

    return (
        patch.object(apd, "connect_ssh", return_value=FakeSSH()),
        patch.object(apd.ams, "register_activity_parents", side_effect=fake_register),
        patch.object(apd.ams, "rebuild_in_container", return_value=True),
    )


def _run(client, entities, **kw):
    p_ssh, p_reg, p_rebuild = _patches(client)
    with p_ssh, p_reg, p_rebuild:
        return apd.deploy_activity_panels(
            client, object(), entities, timestamp="ts", **kw
        )


class TestDeployActivityPanels:
    def test_registers_unregistered_and_enables_panels(self):
        client = StatefulClient(registered=["Account"])
        result = _run(client, ["CEngagement", "CMentorProfile"])
        assert result.registered_via_ssh == ["CEngagement", "CMentorProfile"]
        assert result.all_ok
        for e in ("CEngagement", "CMentorProfile"):
            r = result.entities[e]
            assert r.registered and r.panels_enabled
            assert client.layouts[e] == build_bottom_panels_detail_layout()

    def test_skips_registration_when_already_registered(self):
        client = StatefulClient(registered=["CEngagement"])
        result = _run(client, ["CEngagement"])
        assert result.registered_via_ssh == []  # nothing to register
        assert result.entities["CEngagement"].ok

    def test_stream_enabled_only_for_requested_entities(self):
        client = StatefulClient()
        result = _run(
            client,
            ["CInformationRequest", "CEngagement"],
            stream_entities=("CInformationRequest",),
        )
        assert "CInformationRequest" in client.streamed
        assert "CEngagement" not in client.streamed
        assert result.entities["CInformationRequest"].stream_set is True
        assert result.entities["CEngagement"].stream_set is None

    def test_all_ok_false_when_registration_does_not_take(self):
        # register is a no-op (patched away) so the entity never becomes
        # registered -> verification fails -> not ok.
        client = StatefulClient()
        with patch.object(apd, "connect_ssh", return_value=FakeSSH()), patch.object(
            apd.ams, "register_activity_parents", return_value={}
        ), patch.object(apd.ams, "rebuild_in_container", return_value=True):
            result = apd.deploy_activity_panels(
                client, object(), ["CEngagement"], timestamp="ts", verify_timeout=0
            )
        assert not result.all_ok
        assert result.entities["CEngagement"].registered is False

    def test_ssh_closed_even_on_no_entities(self):
        client = StatefulClient()
        closed = {"v": False}

        class FakeSSH:
            def close(self):
                closed["v"] = True

        with patch.object(apd, "connect_ssh", return_value=FakeSSH()), patch.object(
            apd.ams, "rebuild_in_container", return_value=True
        ):
            apd.deploy_activity_panels(client, object(), [], timestamp="ts")
        assert closed["v"] is True
