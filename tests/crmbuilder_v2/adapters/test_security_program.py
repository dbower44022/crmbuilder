"""The instance-wide security program — PI-417 (REQ-519 / DEC-998)."""

from __future__ import annotations

import pathlib
import tempfile

from crmbuilder_v2.adapters.espocrm.emit import emit_program_yaml
from crmbuilder_v2.adapters.espocrm.model import (
    SECURITY_FILENAME,
    _security_program,
    _translate_system_permissions,
)

from espo_impl.core.config_loader import ConfigLoader


def _role(identifier="ROL-001", name="Mentor Role", status="confirmed", **extra):
    return {"role_identifier": identifier, "role_name": name,
            "role_status": status, **extra}


def _team(identifier="TM-001", name="Mentor Team", status="confirmed", **extra):
    return {"team_identifier": identifier, "team_name": name,
            "team_status": status, **extra}


def test_the_security_program_owns_no_entity():
    """DEC-998: roles span many entities and teams belong to none, so the
    program that carries them names none — which is the assumption this
    amends."""
    prog = _security_program([_role()], [_team()], [])
    assert prog.entity_identifier is None
    assert prog.entity_name is None
    assert prog.is_security is True
    assert prog.filename == SECURITY_FILENAME


def test_nothing_confirmed_produces_no_program_at_all():
    """A file declaring no roles is not the same as no file. Publishing an
    empty one would invite a reader to think the design had decided there are
    none."""
    assert _security_program([_role(status="candidate")], [], []) is None
    assert _security_program([], [], []) is None


def test_only_confirmed_records_are_emitted_and_the_rest_are_named():
    """A candidate role is unfinished design, not access control to push at a
    live CRM — but it is deferred by name rather than dropped."""
    deferrals = []
    prog = _security_program(
        [_role(), _role("ROL-002", "Draft Role", status="candidate")],
        [_team("TM-002", "Draft Team", status="deferred")],
        deferrals,
    )
    assert [r["name"] for r in prog.program["roles"]] == ["Mentor Role"]
    assert "teams" not in prog.program
    assert {(d.kind, d.identifier) for d in deferrals} == {
        ("unconfirmed_role", "ROL-002"), ("unconfirmed_team", "TM-002"),
    }


# --- the translation the design's stored shape needs ------------------------

def test_espocrm_permission_keys_become_the_schema_s_neutral_ones():
    """The design stores what the audit read from the CRM; the deployable
    schema speaks a smaller neutral vocabulary. An untranslated key is rejected
    by the loader outright, so this is not cosmetic."""
    out = _translate_system_permissions(
        {"exportPermission": "no", "assignmentPermission": "all"},
        "Mentor Role", [], "ROL-001",
    )
    assert out == {"export": False, "assignment_permission": "all"}


def test_a_yes_no_permission_becomes_a_boolean():
    out = _translate_system_permissions(
        {"exportPermission": "yes", "massUpdatePermission": "no"},
        "R", [], "ROL-001",
    )
    assert out == {"export": True, "mass_update": False}


def test_not_set_is_dropped_rather_than_translated():
    """EspoCRM's not-set means its own default applies. The schema's rule is
    that an omitted permission defaults to deny, so writing a value would
    assert a decision the design never made."""
    assert _translate_system_permissions(
        {"exportPermission": "not-set", "userPermission": "not-set"},
        "R", [], "ROL-001",
    ) == {}


def test_a_permission_the_schema_cannot_express_is_deferred_by_name():
    """EspoCRM carries several the schema never modelled. Silently discarding
    one would publish a role quietly weaker or stronger than the design
    describes."""
    deferrals = []
    out = _translate_system_permissions(
        {"auditPermission": "yes", "exportPermission": "no"},
        "Mentor Role", deferrals, "ROL-001",
    )
    assert out == {"export": False}
    assert len(deferrals) == 1
    assert deferrals[0].kind == "unmapped_system_permission"
    assert "auditPermission" in deferrals[0].name


# --- the whole thing, against the real v1 loader ----------------------------

def test_the_emitted_program_is_accepted_by_the_deploy_schema():
    """The arbiter is the loader the deploy engine actually uses, not our own
    idea of the shape. This is the real ROL-003 permission set read from CBM
    production, which is what exposed the key mismatch in the first place."""
    prog = _security_program(
        [_role(
            role_description="Mentors",
            role_scope_access={"Contact": {"read": "all", "edit": "own"}},
            role_system_permissions={
                "exportPermission": "no", "portalPermission": "no",
                "massUpdatePermission": "no", "assignmentPermission": "all",
                "userPermission": "not-set", "auditPermission": "not-set",
            },
        )],
        [_team()],
        [],
    )
    path = pathlib.Path(tempfile.mkdtemp()) / SECURITY_FILENAME
    path.write_text(emit_program_yaml(prog, rendered_at="2026-09-02T00:00:00Z"))

    loaded = ConfigLoader().load_program(path)
    assert [r.name for r in loaded.roles] == ["Mentor Role"]
    assert [t.name for t in loaded.teams] == ["Mentor Team"]
    assert loaded.roles[0].system_permissions.export is False
    assert loaded.roles[0].system_permissions.assignment_permission == "all"
    assert loaded.roles[0].scope_access["Contact"].read == "all"
    # A security program declares no entities — the point of DEC-998.
    assert not loaded.entities
