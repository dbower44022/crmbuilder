"""Tests for the live-capture glue (label resolver + entity-spec mapping)."""
from __future__ import annotations

from espo_impl.core.reconcile.live_state import (
    EntitySpec,
    build_label_resolver,
    map_entity_specs,
)


class _FakeClient:
    def __init__(self, i18n_status=200, i18n=None):
        self._i18n_status = i18n_status
        self._i18n = i18n or {}

    def get_i18n(self):
        return self._i18n_status, self._i18n


def test_resolver_scope_then_global_then_fallback():
    i18n = {
        "Contact": {"fields": {"title": "Account Title"}},
        "Global": {"fields": {"name": "Name"}},
    }
    r = build_label_resolver(_FakeClient(200, i18n))
    assert r("Contact", "title", "title") == "Account Title"   # scoped wins
    assert r("Contact", "name", "name") == "Name"              # falls to Global
    assert r("Contact", "unknown", "fb") == "fb"               # fallback


def test_resolver_handles_i18n_fetch_failure():
    r = build_label_resolver(_FakeClient(500, None))
    assert r("Contact", "title", "fallback") == "fallback"


def test_map_specs_native_custom_and_unmapped():
    scopes = {
        "Contact": {"type": "Person"},
        "Account": {"type": "Company"},
        "CSession": {"type": "Event"},
    }
    specs, unmapped = map_entity_specs(["Contact", "Session", "Account", "Ghost"], scopes)

    by_name = {s.yaml_name: s for s in specs}
    assert by_name["Contact"] == EntitySpec("Contact", "Contact", "Person")
    assert by_name["Session"] == EntitySpec("Session", "CSession", "Event")  # C-prefixed
    assert by_name["Account"].entity_type == "Company"
    assert unmapped == ["Ghost"]  # not deployed live
