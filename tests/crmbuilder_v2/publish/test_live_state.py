"""V2 publish live-state reads — PI-449 (REQ-549).

Ports the behaviour the publish path relied on from the V1 module it used to
import: scope mapping with the C-prefix rule, natural-form field discovery
(c-prefix stripped on native entities only, system fields skipped, native
fields kept), non-fatal failure reporting — plus the structural guard that
no V2 module imports the V1 audit any more.
"""

from __future__ import annotations

import re
from pathlib import Path

from crmbuilder_v2.publish.live_state import (
    gather_server_fields,
    map_entity_specs,
)


class _FakeAdmin:
    def __init__(self, scopes, fields_by_entity, *, scopes_status=200):
        self._scopes = scopes
        self._fields = fields_by_entity
        self._scopes_status = scopes_status

    def get_all_scopes(self):
        return self._scopes_status, self._scopes

    def get_entity_field_list(self, espo_name):
        if espo_name not in self._fields:
            return 500, None
        return 200, self._fields[espo_name]


def test_map_entity_specs_applies_the_c_prefix_rule():
    scopes = {
        "Contact": {"type": "Person"},
        "CSession": {"type": "Base"},
    }
    specs, unmapped = map_entity_specs(["Contact", "Session", "Ghost"], scopes)
    by_name = {s.yaml_name: s for s in specs}
    assert by_name["Contact"].espo_name == "Contact"
    assert by_name["Contact"].entity_type == "Person"
    assert by_name["Session"].espo_name == "CSession"
    assert unmapped == ["Ghost"]


def test_gather_strips_custom_prefix_on_native_entity_only():
    scopes = {"Contact": {"type": "Person"}, "CSession": {"type": "Base"}}
    fields = {
        "Contact": {
            "cContactType": {"isCustom": True, "type": "enum"},
            "firstName": {"type": "varchar"},
            "createdAt": {"type": "datetime"},  # system — skipped
        },
        "CSession": {
            "topicsCovered": {"isCustom": True, "type": "multiEnum"},
            "name": {"type": "varchar"},
        },
    }
    server, warnings = gather_server_fields(
        _FakeAdmin(scopes, fields), ["Contact", "Session"]
    )
    assert warnings == []
    assert server["Contact"] == frozenset({"contactType", "firstName"})
    # custom entity: natural names kept, no stripping
    assert server["Session"] == frozenset({"topicsCovered", "name"})


def test_gather_reports_unmapped_and_fetch_failures_without_raising():
    scopes = {"Contact": {"type": "Person"}, "CBroken": {"type": "Base"}}
    server, warnings = gather_server_fields(
        _FakeAdmin(scopes, {"Contact": {"firstName": {"type": "varchar"}}}),
        ["Contact", "Broken", "Ghost"],
    )
    assert server == {"Contact": frozenset({"firstName"})}
    assert any("Ghost" in w for w in warnings)
    assert any("Broken" in w and "HTTP 500" in w for w in warnings)


def test_gather_scopes_read_failure_is_nonfatal():
    server, warnings = gather_server_fields(
        _FakeAdmin(None, {}, scopes_status=401), ["Contact"]
    )
    assert server == {}
    assert warnings and "HTTP 401" in warnings[0]


def test_gather_empty_input_reads_nothing():
    class _Exploding:
        def get_all_scopes(self):  # pragma: no cover - must not be called
            raise AssertionError("should not read scopes for an empty batch")

    assert gather_server_fields(_Exploding(), []) == ({}, [])


def test_no_v2_module_imports_the_v1_audit():
    """REQ-549's structural guard: nothing under crmbuilder_v2 imports the V1
    reconcile/audit modules any more, so removing the V1 audit (PI-454)
    cannot break V2. Scans import statements in source text rather than
    sys.modules so lazy imports are caught too (docstring provenance notes
    naming the V1 module are fine)."""
    root = Path(__file__).resolve()
    while root.name != "tests":
        root = root.parent
    src_root = root.parent / "crmbuilder-v2" / "src" / "crmbuilder_v2"
    assert src_root.is_dir(), src_root
    forbidden = re.compile(
        r"^\s*(from|import)\s+espo_impl\.(core\.(reconcile\.live_state|"
        r"audit_manager|audit_utils|audit_db|data_profiler)|"
        r"workers\.audit_worker)\b",
        re.MULTILINE,
    )
    offenders = [
        str(path.relative_to(src_root))
        for path in src_root.rglob("*.py")
        if forbidden.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"V1 audit imports remain in: {offenders}"
