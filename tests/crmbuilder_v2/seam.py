"""Shared Phase 1.5 seam-contract checker (WTK-110 §7.2 criterion C1).

The seam is the serialized manifest pair ``plan_deposit`` consumes,
pinned as the exact key set the landed consumer reads (WTK-110 §2.2).
This module encodes it as executable assertions that **both** adapters'
fixtures must pass — the spreadsheet golden outputs and the landed
EspoCRM transform fixtures. One checker, two adapters: the seam is a
thing the suite owns, not prose.
"""

from __future__ import annotations

from crmbuilder_v2.transform.normalize import SYSTEM_TYPE_MAPS

_ENTITY_CLASSES = frozenset({"custom", "native", "system"})
# Typed per-field metric keys (WTK-096 §6 via WTK-110 §2.2).
_INT_FIELD_METRICS = (
    "populated_count",
    "distinct_value_count",
    "declared_option_count",
    "used_option_count",
)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return _is_int(value) or isinstance(value, float)


def _assert_manifest(manifest: dict) -> dict[str, set[str]]:
    assert manifest["manifest_version"] == 1
    for key in ("timestamp", "source_url", "source_name"):
        assert isinstance(manifest[key], str) and manifest[key], key
    # Optional `source_system` (delta D1); absent -> espocrm. The value
    # must select a registered stage-1 table.
    assert manifest.get("source_system", "espocrm") in SYSTEM_TYPE_MAPS
    for key in ("errors", "warnings"):
        lines = manifest.get(key) or []
        assert isinstance(lines, list), key
        assert all(isinstance(line, str) for line in lines), key
    for key in ("relationships", "roles", "teams"):
        assert isinstance(manifest.get(key) or [], list), key

    entities = manifest["entities"]
    assert isinstance(entities, list)
    join_index: dict[str, set[str]] = {}
    for entity in entities:
        for key in ("yaml_name", "espo_name"):
            assert isinstance(entity[key], str) and entity[key], key
        assert entity["entity_class"] in _ENTITY_CLASSES
        for layout in entity.get("layouts") or []:
            layout_type = layout.get("layout_type")
            assert layout_type is None or isinstance(layout_type, str)
        fields = entity["fields"]
        assert isinstance(fields, list)
        api_names: set[str] = set()
        for field in fields:
            for key in ("yaml_name", "api_name", "field_type"):
                assert isinstance(field[key], str) and field[key], key
            field_class = field.get("field_class")
            assert field_class is None or field_class in _ENTITY_CLASSES
            properties = field.get("properties") or {}
            assert isinstance(properties, dict)
            options = properties.get("options")
            assert options is None or isinstance(options, list)
            assert isinstance(properties.get("required", False), bool)
            api_names.add(field["api_name"])
        join_index[entity["espo_name"]] = api_names
    return join_index


def _assert_profile(profile: dict, join_index: dict[str, set[str]]) -> None:
    assert profile["manifest_version"] == 1
    assert isinstance(profile["profiled_at"], str) and profile["profiled_at"]
    options = profile.get("options")
    assert options is None or isinstance(options, dict)
    anomalies = profile.get("anomalies")
    assert anomalies is None or isinstance(anomalies, list)
    for entity_key, entry in (profile.get("entities") or {}).items():
        # The join `plan_deposit` performs (criterion C7): profile keys
        # are the manifest's espo_name / api_name values — a mismatch
        # is silent evidence loss.
        assert entity_key in join_index, entity_key
        record_count = entry.get("record_count")
        assert record_count is None or _is_int(record_count)
        last_created = entry.get("last_record_created_at")
        assert last_created is None or isinstance(last_created, str)
        detail = entry.get("detail")
        assert detail is None or isinstance(detail, dict)
        for field_key, metrics in (entry.get("fields") or {}).items():
            assert field_key in join_index[entity_key], (
                entity_key,
                field_key,
            )
            for key in _INT_FIELD_METRICS:
                value = metrics.get(key)
                assert value is None or _is_int(value), (field_key, key)
            rate = metrics.get("population_rate")
            assert rate is None or _is_number(rate), field_key
            last_populated = metrics.get("last_populated_at")
            assert last_populated is None or isinstance(last_populated, str)
            field_detail = metrics.get("detail")
            assert field_detail is None or isinstance(field_detail, dict)


def assert_seam_conformant(manifest: dict, profile: dict | None = None) -> None:
    """Assert one adapter output (manifest + optional profile) conforms
    to the WTK-110 §2.2 key contract."""
    join_index = _assert_manifest(manifest)
    if profile is not None:
        _assert_profile(profile, join_index)
