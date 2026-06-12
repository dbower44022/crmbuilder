"""Round-trip test for the audit-report.json manifest writer (WTK-090 §2.1).

The manifest is the seam between the V1 audit and the V2 deposit
transform. This test builds a small AuditReport tree exercising the two
§2.1 serialization adjustments (enum ``.value`` strings, filtered-tab
filter AST rendered via ``render_condition``), writes it, reloads it,
and validates the result against the suite-owned seam contract checker
(``tests/crmbuilder_v2/seam.py``).
"""

from __future__ import annotations

import json

from espo_impl.core.audit_manager import (
    MANIFEST_FILENAME,
    MANIFEST_VERSION,
    AuditReport,
    EntityAuditResult,
    FieldAuditResult,
    FilteredTabAuditResult,
    LayoutAuditResult,
    RelationshipAuditResult,
    TeamAuditResult,
    write_manifest,
)
from espo_impl.core.audit_utils import EntityClass
from espo_impl.core.condition_expression import parse_condition
from tests.crmbuilder_v2.seam import assert_seam_conformant


def _sample_report() -> AuditReport:
    tab_filter = parse_condition(
        {"all": [{"field": "status", "op": "equals", "value": "Active"}]}
    )
    entity = EntityAuditResult(
        yaml_name="Engagement",
        espo_name="CEngagement",
        entity_class=EntityClass.CUSTOM,
        entity_type="Base",
        label_singular="Engagement",
        label_plural="Engagements",
        stream=True,
        fields=[
            FieldAuditResult(
                yaml_name="status",
                api_name="status",
                field_type="enum",
                label="Status",
                properties={"options": ["Active", "Closed"], "required": True},
            )
        ],
        layouts=[LayoutAuditResult(layout_type="detail", data={"panels": []})],
        filtered_tabs=[
            FilteredTabAuditResult(
                id="activeEngagements",
                scope="ActiveEngagements",
                label="Active Engagements",
                filter=tab_filter,
            ),
            FilteredTabAuditResult(
                id="unrecovered",
                scope="Unrecovered",
                label="Unrecovered",
                filter=None,
            ),
        ],
    )
    return AuditReport(
        source_url="https://example.invalid/",
        source_name="Round-Trip Fixture",
        timestamp="2026-06-12T00:00:00Z",
        output_dir="ignored",
        entities=[entity],
        relationships=[
            RelationshipAuditResult(
                name="engagementContact",
                entity="Engagement",
                entity_foreign="Contact",
                link_type="manyToOne",
                link="contact",
                link_foreign="engagements",
                label="Contact",
                label_foreign="Engagements",
            )
        ],
        teams=[TeamAuditResult(name="Mentors")],
        warnings=["sample warning"],
    )


def test_manifest_round_trip_is_seam_conformant(tmp_path):
    report = _sample_report()
    path = write_manifest(report, tmp_path)

    assert path.name == MANIFEST_FILENAME
    manifest = json.loads(path.read_text(encoding="utf-8"))

    assert manifest["manifest_version"] == MANIFEST_VERSION
    # Enum serialized as its .value string (§2.1 adjustment 1).
    assert manifest["entities"][0]["entity_class"] == "custom"
    # Filter AST rendered to the canonical structured form, None kept
    # as null (§2.1 adjustment 2).
    tabs = manifest["entities"][0]["filtered_tabs"]
    assert tabs[0]["filter"] == {
        "all": [{"field": "status", "op": "equals", "value": "Active"}]
    }
    assert tabs[1]["filter"] is None

    # The suite-owned seam contract the deposit transform consumes.
    assert_seam_conformant(manifest)


def test_manifest_write_is_idempotent_overwrite(tmp_path):
    report = _sample_report()
    write_manifest(report, tmp_path)
    report.warnings.append("second pass")
    path = write_manifest(report, tmp_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert "second pass" in manifest["warnings"]
    assert not list(tmp_path.glob("*.tmp"))
