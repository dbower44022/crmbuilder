"""Live-state capture transform tests (offline, fake client).

Covers the field reverse-mapping (c-prefix strip), system-field skipping, native
inclusion/exclusion, label enrichment via the injected resolver, and HTTP-error
handling. End-to-end against a real instance (real API + i18n) is verified
separately.
"""
from __future__ import annotations

from espo_impl.core.audit_utils import SYSTEM_FIELDS
from espo_impl.core.reconcile.live_state import EntitySpec, LiveStateCapture

_SYS = next(iter(SYSTEM_FIELDS))  # a real system field name, whatever it is


class _FakeClient:
    def __init__(self, responses):
        self._responses = responses

    def get_entity_field_list(self, espo_name):
        return self._responses.get(espo_name, (404, None))


def test_custom_field_prefix_stripped_and_label_enriched():
    client = _FakeClient({
        "CSession": (200, {
            "cSessionType": {"type": "enum", "isCustom": True},
            _SYS: {"type": "varchar"},
        }),
    })
    cap = LiveStateCapture(
        client, label_resolver=lambda espo, api, fb: {"cSessionType": "Session Type"}.get(api, fb)
    )

    live, warnings = cap.capture_fields([EntitySpec("Session", "CSession", "Base")])

    assert warnings == []
    session = live["Session"]
    assert _SYS not in session                      # system field skipped
    assert "sessionType" in session                  # c-prefix stripped
    assert session["sessionType"]["type"] == "enum"
    assert session["sessionType"]["label"] == "Session Type"  # i18n enrichment


def test_native_inclusion_toggle():
    meta = {"firstName": {"type": "varchar"}}
    client = _FakeClient({"Contact": (200, meta)})

    inc, _ = LiveStateCapture(client, include_native=True).capture_fields(
        [EntitySpec("Contact", "Contact", "Person")]
    )
    exc, _ = LiveStateCapture(client, include_native=False).capture_fields(
        [EntitySpec("Contact", "Contact", "Person")]
    )

    assert "firstName" in inc["Contact"]
    assert exc["Contact"] == {}


def test_http_error_warns_and_omits_entity():
    client = _FakeClient({"CGhost": (500, None)})

    live, warnings = cap_result = LiveStateCapture(client).capture_fields(
        [EntitySpec("Ghost", "CGhost", "Base")]
    )

    assert "Ghost" not in live
    assert len(warnings) == 1
    assert "Ghost" in warnings[0] and "500" in warnings[0]


def test_default_resolver_uses_fallback_name():
    client = _FakeClient({"CSession": (200, {"cTopic": {"type": "varchar", "isCustom": True}})})
    live, _ = LiveStateCapture(client).capture_fields([EntitySpec("Session", "CSession")])
    # No resolver supplied -> label falls back to the yaml field name.
    assert live["Session"]["topic"]["label"] == "topic"
