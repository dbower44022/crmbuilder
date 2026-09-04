"""The complete option list deploys identically whatever the active subsets —
PI-407 (REQ-486).

Two instances whose active subsets differ receive byte-identical programs:
the option list the emitter writes comes from ``field_options`` and nothing
else, and the subset reaches an instance only as a governed setting value.
So a per-instance deviation in the deployed list has nowhere to come from
but the instance itself, and stays drift.
"""

from __future__ import annotations

import pathlib
import tempfile

import yaml as pyyaml
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.reconcile_compare import (
    option_sets_equal,
    summarize_option_diff,
)
from crmbuilder_v2.access.repositories import entity, field
from crmbuilder_v2.access.repositories import instances as inst_repo
from crmbuilder_v2.access.repositories import system_settings as ss
from crmbuilder_v2.adapters.espocrm.adapter import EspoCrmAdapter
from crmbuilder_v2.adapters.espocrm.client import AccessDesignClient
from crmbuilder_v2.adapters.espocrm.model import build_program_model
from crmbuilder_v2.publish.service import (
    declared_setting_values,
    plan_fingerprint_for,
)

from espo_impl.core.config_loader import ConfigLoader

RENDERED_AT = "2026-09-02T12:00:00+00:00"
_COMPLETE = ["Cuyahoga", "Summit", "Lorain", "Medina"]


def _seed() -> tuple[str, str, str, str]:
    with session_scope() as s:
        ent = entity.create_entity(
            s, name="Account", description="d", kind="organization",
            status="confirmed",
        )["entity_identifier"]
        fid = field.create_field(
            s,
            field_belongs_to_entity_identifier=ent,
            name="area_of_service",
            description="d",
            type="enum",
            status="confirmed",
            data_bearing=True,
            options=[
                {"option_value": v, "option_order": i} for i, v in enumerate(_COMPLETE)
            ],
        )["field_identifier"]
        sid = ss.create_system_setting(
            s,
            key="activeAreasOfService",
            name="Active areas of service",
            value_type="enum",
            status="confirmed",
            active_subset_field=fid,
        )["system_setting_identifier"]
        cle = inst_repo.create_instance(
            s, name="cleveland", url="https://cleveland.example.org", role="both"
        )["instance_identifier"]
        akr = inst_repo.create_instance(
            s, name="akron", url="https://akron.example.org", role="both"
        )["instance_identifier"]
        ss.set_value(
            s, system_setting_identifier=sid, instance_identifier=cle,
            value=["Cuyahoga", "Lorain"],
        )
        ss.set_value(
            s, system_setting_identifier=sid, instance_identifier=akr,
            value=["Summit"],
        )
    return fid, sid, cle, akr


def _generate(client: AccessDesignClient):
    return EspoCrmAdapter().generate(
        client.list_entities(),
        client.list_fields(),
        client.list_engine_overrides(),
        rendered_at=RENDERED_AT,
        engagement="ENG-001",
    )


def test_two_instances_with_different_subsets_receive_the_same_program(v2_env):
    _fid, _sid, cle, akr = _seed()
    client = AccessDesignClient()

    # The subsets really differ.
    assert declared_setting_values(client, cle) == {
        "activeAreasOfService": ["Cuyahoga", "Lorain"]
    }
    assert declared_setting_values(client, akr) == {
        "activeAreasOfService": ["Summit"]
    }

    # Generation takes no instance: there is one program, and it carries the
    # complete list. Deriving it once per instance yields the same bytes.
    for_cle = _generate(client)
    for_akr = _generate(client)
    assert [p.content for p in for_cle.programs] == [p.content for p in for_akr.programs]
    [program] = for_cle.programs
    assert "activeAreasOfService" not in program.content
    for value in _COMPLETE:
        assert value in program.content

    # The emitted field block lists every option, in the design's order.
    model = build_program_model(
        client.list_entities(), client.list_fields(), client.list_engine_overrides(),
        rendered_at=RENDERED_AT,
    )
    [program_model] = model.programs
    block = program_model.program["entities"][program_model.entity_name]
    [emitted] = [f for f in block["fields"] if f["name"] == "areaOfService"]
    assert emitted["options"] == _COMPLETE

    # Read back with the consumers' readers, not the writer's dialect (LSN-070):
    # the deploy engine's loader must see the same four options, and none of
    # them may have turned into anything but text on the way.
    entity_block = pyyaml.safe_load(program.content)["entities"][program_model.entity_name]
    [read_back] = [f for f in entity_block["fields"] if f["name"] == "areaOfService"]
    assert read_back["options"] == _COMPLETE
    path = pathlib.Path(tempfile.mkdtemp()) / program.filename
    path.write_text(program.content)
    loaded = ConfigLoader().load_program(path)
    [loaded_field] = [f for f in loaded.entities[0].fields if f.name == "areaOfService"]
    assert loaded_field.options == _COMPLETE

    # What differs per instance is the plan's setting values, not its programs:
    # the same artifacts fingerprint differently only because of them.
    artifacts = [(p.filename, p.content) for p in for_cle.programs]
    fp_cle = plan_fingerprint_for(
        artifacts, target_identifier=cle,
        setting_values=declared_setting_values(client, cle),
    )
    fp_akr = plan_fingerprint_for(
        artifacts, target_identifier=akr,
        setting_values=declared_setting_values(client, akr),
    )
    assert fp_cle != fp_akr


def test_an_instance_holding_only_its_subset_reads_as_drift(v2_env):
    """The comparison is against the complete list, never against the subset:
    an instance whose deployed list has been narrowed to its active subset is
    drifted, exactly as one that grew a stray value is."""
    fid, _sid, _cle, _akr = _seed()
    with session_scope() as s:
        design_options = field.get_field(s, fid)["field_options"]
    narrowed = [o for o in design_options if o["option_value"] in ("Cuyahoga", "Lorain")]
    assert not option_sets_equal(design_options, narrowed)
    diff = summarize_option_diff(design_options, narrowed)
    assert diff["removed"] == ["Medina", "Summit"] or set(diff["removed"]) == {"Summit", "Medina"}
    assert option_sets_equal(design_options, list(design_options))
