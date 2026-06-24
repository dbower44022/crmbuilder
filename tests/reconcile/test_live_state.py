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


def test_native_custom_field_prefix_stripped_and_label_enriched():
    # On a NATIVE entity, EspoCRM c-prefixes custom fields, so the prefix
    # is stripped back to the natural YAML name.
    client = _FakeClient({
        "Account": (200, {
            "cIndustry": {"type": "enum", "isCustom": True},
            _SYS: {"type": "varchar"},
        }),
    })
    cap = LiveStateCapture(
        client, label_resolver=lambda espo, api, fb: {"cIndustry": "Industry"}.get(api, fb)
    )

    live, warnings = cap.capture_fields([EntitySpec("Account", "Account", "Company")])

    assert warnings == []
    account = live["Account"]
    assert _SYS not in account                       # system field skipped
    assert "industry" in account                     # c-prefix stripped
    assert account["industry"]["type"] == "enum"
    assert account["industry"]["label"] == "Industry"  # i18n enrichment


def test_custom_entity_field_name_not_stripped():
    # On a CUSTOM entity, fields keep their natural names. A name that
    # legitimately begins with c+Uppercase must NOT be stripped (REQ-342).
    client = _FakeClient({
        "CPartnerProfile": (200, {
            "cBMValueProvided": {"type": "text", "isCustom": True},
            "areaOfFocus": {"type": "varchar", "isCustom": True},
        }),
    })
    cap = LiveStateCapture(client)

    live, warnings = cap.capture_fields(
        [EntitySpec("PartnerProfile", "CPartnerProfile", "Base")]
    )

    assert warnings == []
    pp = live["PartnerProfile"]
    assert "cBMValueProvided" in pp                   # NOT mangled to bMValueProvided
    assert "bMValueProvided" not in pp
    assert "areaOfFocus" in pp


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

    live, warnings = LiveStateCapture(client).capture_fields(
        [EntitySpec("Ghost", "CGhost", "Base")]
    )

    assert "Ghost" not in live
    assert len(warnings) == 1
    assert "Ghost" in warnings[0] and "500" in warnings[0]


def test_default_resolver_uses_fallback_name():
    # Custom-entity field keeps its natural name (no c-prefix to strip).
    client = _FakeClient({"CSession": (200, {"topic": {"type": "varchar", "isCustom": True}})})
    live, _ = LiveStateCapture(client).capture_fields([EntitySpec("Session", "CSession")])
    # No resolver supplied -> label falls back to the yaml field name.
    assert live["Session"]["topic"]["label"] == "topic"


# --- gather_server_fields (validation-side discovery) ----------------------

class _FakeScopeClient:
    """Fake exposing the two methods gather_server_fields needs."""

    def __init__(self, scopes, fields, scopes_status=200):
        self._scopes = scopes
        self._fields = fields
        self._scopes_status = scopes_status

    def get_all_scopes(self):
        return (self._scopes_status, self._scopes)

    def get_entity_field_list(self, espo_name):
        return self._fields.get(espo_name, (404, None))


def test_gather_server_fields_maps_strips_and_warns_unmapped():
    from espo_impl.core.reconcile.live_state import gather_server_fields

    client = _FakeScopeClient(
        scopes={
            "Account": {"type": "Company"},
            "CEngagement": {"type": "Base"},
        },
        fields={
            "Account": (200, {
                "cAccountType": {"type": "enum", "isCustom": True},
                "name": {"type": "varchar"},
                _SYS: {"type": "varchar"},
            }),
            "CEngagement": (200, {
                # Custom-entity field — natural name, no platform prefix.
                "stage": {"type": "enum", "isCustom": True},
            }),
        },
    )

    server_fields, warnings = gather_server_fields(
        client, ["Account", "Engagement", "Ghost"]
    )

    # Native entity: custom field c-prefix stripped to natural form.
    assert "accountType" in server_fields["Account"]
    assert "name" in server_fields["Account"]
    assert _SYS not in server_fields["Account"]          # system skipped
    # Custom entity (CEngagement) keeps its natural field name.
    assert server_fields["Engagement"] == frozenset({"stage"})
    # Entity absent from the live instance is reported, not fatal.
    assert any("Ghost" in w for w in warnings)
    assert "Ghost" not in server_fields


def test_gather_server_fields_empty_input():
    from espo_impl.core.reconcile.live_state import gather_server_fields

    client = _FakeScopeClient(scopes={}, fields={})
    assert gather_server_fields(client, []) == ({}, [])


def test_gather_server_fields_scopes_read_failure_is_nonfatal():
    from espo_impl.core.reconcile.live_state import gather_server_fields

    client = _FakeScopeClient(scopes=None, fields={}, scopes_status=503)
    server_fields, warnings = gather_server_fields(client, ["Account"])
    assert server_fields == {}
    assert warnings and "scopes" in warnings[0].lower()
