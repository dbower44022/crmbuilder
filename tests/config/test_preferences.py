"""Tests for automation.config.preferences — per-machine app preferences."""

import json

from automation.config import preferences


class TestGetLastActiveTab:

    def test_returns_none_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(preferences, "_get_prefs_dir", lambda: tmp_path)
        assert preferences.get_last_active_tab() is None

    def test_returns_valid_tab(self, tmp_path, monkeypatch):
        monkeypatch.setattr(preferences, "_get_prefs_dir", lambda: tmp_path)
        (tmp_path / "preferences.json").write_text(
            json.dumps({"last_active_tab": "requirements"})
        )
        assert preferences.get_last_active_tab() == "requirements"

    def test_returns_none_for_invalid_tab(self, tmp_path, monkeypatch):
        monkeypatch.setattr(preferences, "_get_prefs_dir", lambda: tmp_path)
        (tmp_path / "preferences.json").write_text(
            json.dumps({"last_active_tab": "bogus"})
        )
        assert preferences.get_last_active_tab() is None

    def test_returns_none_for_corrupt_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr(preferences, "_get_prefs_dir", lambda: tmp_path)
        (tmp_path / "preferences.json").write_text("{bad json")
        assert preferences.get_last_active_tab() is None

    def test_all_valid_tab_names(self, tmp_path, monkeypatch):
        monkeypatch.setattr(preferences, "_get_prefs_dir", lambda: tmp_path)
        for name in ("clients", "requirements", "deployment"):
            (tmp_path / "preferences.json").write_text(
                json.dumps({"last_active_tab": name})
            )
            assert preferences.get_last_active_tab() == name


class TestSetLastActiveTab:

    def test_creates_file(self, tmp_path, monkeypatch):
        prefs_dir = tmp_path / "sub"
        monkeypatch.setattr(preferences, "_get_prefs_dir", lambda: prefs_dir)
        preferences.set_last_active_tab("deployment")

        data = json.loads((prefs_dir / "preferences.json").read_text())
        assert data["last_active_tab"] == "deployment"

    def test_preserves_existing_keys(self, tmp_path, monkeypatch):
        monkeypatch.setattr(preferences, "_get_prefs_dir", lambda: tmp_path)
        (tmp_path / "preferences.json").write_text(
            json.dumps({"other_key": 42})
        )
        preferences.set_last_active_tab("clients")

        data = json.loads((tmp_path / "preferences.json").read_text())
        assert data["last_active_tab"] == "clients"
        assert data["other_key"] == 42


class TestGetLastSelectedClientId:

    def test_returns_none_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(preferences, "_get_prefs_dir", lambda: tmp_path)
        assert preferences.get_last_selected_client_id() is None

    def test_returns_int(self, tmp_path, monkeypatch):
        monkeypatch.setattr(preferences, "_get_prefs_dir", lambda: tmp_path)
        (tmp_path / "preferences.json").write_text(
            json.dumps({"last_selected_client_id": 7})
        )
        assert preferences.get_last_selected_client_id() == 7

    def test_returns_none_for_string_value(self, tmp_path, monkeypatch):
        monkeypatch.setattr(preferences, "_get_prefs_dir", lambda: tmp_path)
        (tmp_path / "preferences.json").write_text(
            json.dumps({"last_selected_client_id": "not_an_int"})
        )
        assert preferences.get_last_selected_client_id() is None

    def test_returns_none_for_null_value(self, tmp_path, monkeypatch):
        monkeypatch.setattr(preferences, "_get_prefs_dir", lambda: tmp_path)
        (tmp_path / "preferences.json").write_text(
            json.dumps({"last_selected_client_id": None})
        )
        assert preferences.get_last_selected_client_id() is None


class TestSetLastSelectedClientId:

    def test_set_and_get(self, tmp_path, monkeypatch):
        monkeypatch.setattr(preferences, "_get_prefs_dir", lambda: tmp_path)
        preferences.set_last_selected_client_id(42)
        assert preferences.get_last_selected_client_id() == 42

    def test_set_none_clears(self, tmp_path, monkeypatch):
        monkeypatch.setattr(preferences, "_get_prefs_dir", lambda: tmp_path)
        preferences.set_last_selected_client_id(5)
        preferences.set_last_selected_client_id(None)
        assert preferences.get_last_selected_client_id() is None


class TestRoundTrip:

    def test_set_both_and_read_back(self, tmp_path, monkeypatch):
        monkeypatch.setattr(preferences, "_get_prefs_dir", lambda: tmp_path)
        preferences.set_last_active_tab("requirements")
        preferences.set_last_selected_client_id(3)

        assert preferences.get_last_active_tab() == "requirements"
        assert preferences.get_last_selected_client_id() == 3
