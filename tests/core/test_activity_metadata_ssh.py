"""Tests for the activity-parent SSH metadata patch (PI-338 / REQ-379).

The remote calls are mocked: ``run_remote`` is patched so the module's command
construction and merge logic are exercised without a live droplet.
"""

import base64
import json
from unittest.mock import patch

from automation.core.deployment import activity_metadata_ssh as mod


class FakeClient:
    def __init__(self, metadata=None):
        self._metadata = metadata or {}

    def get_metadata(self, key):
        if key in self._metadata:
            return 200, self._metadata[key]
        return 200, None


def _b64(obj) -> str:
    return base64.b64encode(json.dumps(obj).encode()).decode()


class TestReadCustomHolderDef:
    def test_decodes_base64_json(self):
        holder_def = {"fields": {"parent": {"entityList": ["Account"]}}}
        with patch.object(
            mod, "run_remote", return_value=(0, _b64(holder_def))
        ):
            assert mod.read_custom_holder_def(None, "Meeting") == holder_def

    def test_missing_file_returns_empty(self):
        with patch.object(mod, "run_remote", return_value=(0, "")):
            assert mod.read_custom_holder_def(None, "Meeting") == {}

    def test_nonzero_exit_returns_empty(self):
        with patch.object(mod, "run_remote", return_value=(1, "boom")):
            assert mod.read_custom_holder_def(None, "Meeting") == {}


class TestWriteCustomHolderDef:
    def test_command_backs_up_and_writes_as_root(self):
        captured = {}

        def fake_run_remote(ssh, command):
            captured["command"] = command
            return 0, ""

        data = {"fields": {"parent": {"entityList": ["Account", "CEngagement"]}}}
        with patch.object(mod, "run_remote", side_effect=fake_run_remote):
            ok = mod.write_custom_holder_def(None, "Meeting", data, "20260627")
        assert ok is True
        cmd = captured["command"]
        assert "-u root" in cmd  # writes to the root-owned tree
        assert "cp " in cmd and "/var/backups/espocrm/metadata/20260627" in cmd
        assert "chown www-data:www-data" in cmd
        assert "base64 -d" in cmd

    def test_failure_returns_false(self):
        with patch.object(mod, "run_remote", return_value=(1, "denied")):
            ok = mod.write_custom_holder_def(None, "Meeting", {}, "ts")
        assert ok is False


class TestRegisterActivityParents:
    def test_unions_merged_list_and_writes_each_holder(self):
        # Live merged list for all three holders carries the platform defaults.
        md = {
            f"entityDefs.{h}.fields.parent.entityList": ["Account", "Contact"]
            for h in ("Meeting", "Call", "Task")
        }
        client = FakeClient(md)
        writes = []

        def fake_write(ssh, holder, data, ts, log=None):
            writes.append((holder, data["fields"]["parent"]["entityList"]))
            return True

        with patch.object(mod, "read_custom_holder_def", return_value={}), patch.object(
            mod, "write_custom_holder_def", side_effect=fake_write
        ):
            results = mod.register_activity_parents(
                None, client, ["CEngagement"], "ts"
            )

        assert results == {"Meeting": True, "Call": True, "Task": True}
        for _holder, entity_list in writes:
            # full list preserved + new entity appended
            assert entity_list == ["Account", "Contact", "CEngagement"]

    def test_skips_holder_already_registered(self):
        md = {
            "entityDefs.Meeting.fields.parent.entityList": ["CEngagement"],
            "entityDefs.Call.fields.parent.entityList": ["Account"],
            "entityDefs.Task.fields.parent.entityList": ["Account"],
        }
        client = FakeClient(md)
        with patch.object(mod, "read_custom_holder_def", return_value={}), patch.object(
            mod, "write_custom_holder_def", return_value=True
        ) as write_mock:
            results = mod.register_activity_parents(
                None, client, ["CEngagement"], "ts"
            )
        assert results["Meeting"] is False  # already present, no write
        assert results["Call"] is True
        # Meeting must not have triggered a write
        written_holders = {call.args[1] for call in write_mock.call_args_list}
        assert "Meeting" not in written_holders
