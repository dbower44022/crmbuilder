"""ADO runtime — contract tools surfaced into the agent prompt (REQ-380 / PI-339).

The registry contract is resolved and injected into a spawned agent's prompt by
``build_agent_prompt``; PI-339 adds the tools section (so the registry's tool
bindings actually reach the agent) and threads the contract ``version_stamp``
onto the resolved assignment for run provenance.
"""

from __future__ import annotations

from crmbuilder_v2.scheduler import agent_prompt
from crmbuilder_v2.scheduler.agent_prompt import _tools_section, build_agent_prompt
from crmbuilder_v2.scheduler.coordinating_scheduler import _ResolvedAssignment


def test_tools_section_renders_name_description_call_and_io():
    section = _tools_section(
        [
            {
                "identifier": "SKL-001",
                "name": "scope workstream",
                "description": "Record the phase's Work Tasks.",
                "backing_callable": "POST /workstreams/{id}/scope",
                "io_contract": {"type": "object"},
            }
        ]
    )
    assert "Tools available to you" in section
    assert "scope workstream" in section
    assert "Record the phase's Work Tasks." in section
    assert "POST /workstreams/{id}/scope" in section
    assert '"type": "object"' in section


def test_tools_section_empty_is_blank():
    assert _tools_section([]) == ""


def test_tools_section_tolerates_missing_optional_fields():
    section = _tools_section([{"identifier": "SKL-009", "name": "bare tool"}])
    assert "bare tool" in section
    assert "how to call" not in section  # no backing_callable
    assert "I/O contract" not in section  # no io_contract


def _stub_get(contract, work_task):
    def _get(api_base, path, engagement):
        return contract if "/contract" in path else work_task
    return _get


def test_build_agent_prompt_includes_tools(monkeypatch):
    contract = {
        "system_prompt": "You are a {AREA} agent.",
        "enforced_ruleset": [],
        "active_learnings": [],
        "tools": [
            {
                "identifier": "SKL-001",
                "name": "call api",
                "description": "Hit the REST API.",
                "backing_callable": "GET /things",
                "io_contract": None,
            }
        ],
        "version_stamp": "abc123",
    }
    work_task = {
        "work_task_area": "api",
        "work_task_title": "Build the thing",
        "work_task_description": "Do it.",
    }
    monkeypatch.setattr(agent_prompt, "_get", _stub_get(contract, work_task))
    inv = build_agent_prompt("http://x", "ENG-001", "AGP-001", "WTK-001")
    assert "Tools available to you" in inv.system_prompt
    assert "call api" in inv.system_prompt
    assert "Hit the REST API." in inv.system_prompt
    assert "GET /things" in inv.system_prompt
    # The version_stamp is available on the resolved contract for provenance.
    assert inv.contract["version_stamp"] == "abc123"


def test_build_agent_prompt_omits_tools_section_when_none(monkeypatch):
    contract = {
        "system_prompt": "You are a {AREA} agent.",
        "enforced_ruleset": [],
        "active_learnings": [],
        "tools": [],
        "version_stamp": "v0",
    }
    work_task = {
        "work_task_area": "api",
        "work_task_title": "t",
        "work_task_description": "d",
    }
    monkeypatch.setattr(agent_prompt, "_get", _stub_get(contract, work_task))
    inv = build_agent_prompt("http://x", "ENG-001", "AGP-001", "WTK-001")
    assert "Tools available to you" not in inv.system_prompt


def test_resolved_assignment_carries_version_stamp():
    a = _ResolvedAssignment(
        work_task={}, work_task_id="WTK-001", area="api", profile_id="AGP-001",
        branch="ado/wtk-001", prompt="...", version_stamp="stamp-xyz",
    )
    assert a.version_stamp == "stamp-xyz"
    # Defaults to None (the built-in fallback path has no registry contract).
    b = _ResolvedAssignment(
        work_task={}, work_task_id="WTK-002", area="api", profile_id="AGP-runtime",
        branch="ado/wtk-002", prompt="...",
    )
    assert b.version_stamp is None
