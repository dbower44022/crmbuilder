"""Round-trip fidelity tests for every EspoCRM layout type.

Drives the real JSON captured from a live EspoCRM 9.x instance
(``tests/fixtures/layouts/*.json``) through the full audit→YAML→deploy chain:

    api_json --reverse--> yaml_value --parse--> LayoutSpec --build--> api_payload

The guarantee being asserted is **repeatable recreation**: the built payload is a
fixed point — feeding it back through reverse→parse→build yields the identical
payload. For the classes EspoCRM does not pad with defaults (COLUMNS, FIELD_LIST,
PANEL_MAP), the first built payload already equals the captured fixture exactly.

c-prefix normalization is exercised separately by the manager/audit unit tests;
here both directions use an empty custom-field set so it is a no-op and the test
isolates structural fidelity.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from espo_impl.core.audit_manager import AuditManager
from espo_impl.core.config_loader import ConfigLoader
from espo_impl.core.layout_manager import LayoutManager
from espo_impl.core.layout_types import LayoutClass, structure_class

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "layouts"
NO_CUSTOM: set[str] = set()


def _fixtures() -> list[tuple[str, str, Path]]:
    """Yield (entity, layout_type, path) for each captured fixture."""
    out: list[tuple[str, str, Path]] = []
    for path in sorted(FIXTURE_DIR.glob("*.json")):
        entity, layout_type = path.stem.split(".", 1)
        out.append((entity, layout_type, path))
    return out


def _reverse(audit: AuditManager, layout_type: str, api_json):
    """Reverse API JSON to the YAML value emitted under the layout type."""
    cls = structure_class(layout_type)
    if cls is LayoutClass.COLUMNS:
        return {"columns": audit._reverse_list_layout(api_json, NO_CUSTOM)}
    if cls is LayoutClass.PANELS:
        return {"panels": audit._reverse_detail_layout(api_json, NO_CUSTOM)}
    if cls is LayoutClass.FIELD_LIST:
        return audit._reverse_field_list_layout(api_json, NO_CUSTOM)
    if cls is LayoutClass.PANEL_MAP:
        return audit._reverse_panel_map_layout(api_json)
    raise AssertionError(f"unclassified layout type {layout_type}")


def _build(loader: ConfigLoader, mgr: LayoutManager, layout_type: str, yaml_value):
    """Parse a YAML layout value and build its API payload."""
    spec = loader._parse_layout(layout_type, yaml_value)
    return mgr._build_payload(
        spec,
        field_definitions=[],
        custom_field_names=NO_CUSTOM,
        auto_place_name=False,
    )


@pytest.fixture
def audit() -> AuditManager:
    return AuditManager(client=None)  # reverse-mappers do not touch the client


@pytest.fixture
def loader() -> ConfigLoader:
    return ConfigLoader()


@pytest.fixture
def mgr() -> LayoutManager:
    return LayoutManager(client=None, output_fn=lambda *a: None)


def test_fixtures_present() -> None:
    assert _fixtures(), "no layout fixtures captured — run tools/capture_layouts.py"


@pytest.mark.parametrize(
    ("entity", "layout_type", "path"),
    _fixtures(),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_roundtrip_is_a_fixed_point(
    entity: str,
    layout_type: str,
    path: Path,
    audit: AuditManager,
    loader: ConfigLoader,
    mgr: LayoutManager,
) -> None:
    """audit→parse→build is idempotent — recreation reproduces the payload."""
    api_json = json.loads(path.read_text())

    first = _build(loader, mgr, layout_type, _reverse(audit, layout_type, api_json))
    second = _build(loader, mgr, layout_type, _reverse(audit, layout_type, first))

    assert first == second, f"{entity}.{layout_type} not a fixed point"


@pytest.mark.parametrize(
    ("entity", "layout_type", "path"),
    [f for f in _fixtures()
     if structure_class(f[1]) in (
         LayoutClass.COLUMNS, LayoutClass.FIELD_LIST, LayoutClass.PANEL_MAP)],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_roundtrip_equals_fixture_for_default_free_classes(
    entity: str,
    layout_type: str,
    path: Path,
    audit: AuditManager,
    loader: ConfigLoader,
    mgr: LayoutManager,
) -> None:
    """COLUMNS / FIELD_LIST / PANEL_MAP rebuild to the captured JSON exactly."""
    api_json = json.loads(path.read_text())
    built = _build(loader, mgr, layout_type, _reverse(audit, layout_type, api_json))
    assert built == api_json, f"{entity}.{layout_type} did not round-trip exactly"
