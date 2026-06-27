"""Agent Profile Registry configuration UI tests — PI-330 / REQ-367.

Covers the new "Agent Registry" sidebar group and its four panels (Agent
Profiles, Skills, Governance Rules, Learnings), the create/edit/delete dialogs,
the JSON-column editor, binding management, the effective-contract preview, and
learning promotion — end to end against a real per-test DB.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.registry_crud import (
    AddEvidenceDialog,
    AgentProfileCreateDialog,
    GovernanceRuleCreateDialog,
    JsonFieldDialog,
    LearningCreateDialog,
    PromoteToRuleDialog,
    PromoteToSkillDialog,
    SetConfidenceDialog,
    SkillCreateDialog,
    SkillEditDialog,
)
from crmbuilder_v2.ui.main_window import ENTITY_TYPE_TO_SIDEBAR_LABEL
from crmbuilder_v2.ui.panels.agent_profiles import AgentProfilesPanel
from crmbuilder_v2.ui.panels.registry_learnings import LearningsPanel
from crmbuilder_v2.ui.panels.registry_rules import GovernanceRulesPanel
from crmbuilder_v2.ui.panels.registry_skills import SkillsPanel
from crmbuilder_v2.ui.sidebar import SIDEBAR_GROUPS, Sidebar
from fastapi.testclient import TestClient


@pytest.fixture
def registry_client(v2_env) -> StorageClient:
    sc = StorageClient(base_url="http://testserver", client=TestClient(create_app()))
    sc.set_active_engagement("ENG-001")
    return sc


def _wait_rows(qtbot, panel, count: int) -> None:
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == count, timeout=3000)


# --- wiring ---------------------------------------------------------------


def test_agent_registry_group_present():
    groups = dict(SIDEBAR_GROUPS)
    assert "Agent Registry" in groups
    assert groups["Agent Registry"] == (
        "Agent Profiles",
        "Skills",
        "Governance Rules",
        "Learnings",
    )


def test_entity_type_labels_registered():
    assert ENTITY_TYPE_TO_SIDEBAR_LABEL["agent_profile"] == "Agent Profiles"
    assert ENTITY_TYPE_TO_SIDEBAR_LABEL["skill"] == "Skills"
    assert ENTITY_TYPE_TO_SIDEBAR_LABEL["governance_rule"] == "Governance Rules"
    assert ENTITY_TYPE_TO_SIDEBAR_LABEL["learning"] == "Learnings"


def test_sidebar_renders_agent_registry(qtbot):
    from crmbuilder_v2.ui.sidebar import _HEADER_ROLE  # noqa: PLC0415

    sidebar = Sidebar()
    qtbot.addWidget(sidebar)
    items = [sidebar.item(r) for r in range(sidebar.count())]
    rendered = [item.text() for item in items]
    headers = {item.text(): i for i, item in enumerate(items) if item.data(_HEADER_ROLE)}
    for entry in ("Agent Profiles", "Skills", "Governance Rules", "Learnings"):
        assert entry in rendered
        assert rendered.index(entry) > headers["Agent Registry"]


def test_panel_columns_and_titles(qtbot, registry_client):
    profiles = AgentProfilesPanel(registry_client)
    qtbot.addWidget(profiles)
    assert profiles.entity_title() == "Agent Profiles"
    assert [c.title for c in profiles.list_columns()] == [
        "Identifier", "Area", "Tier", "Scope", "Status",
    ]
    skills = SkillsPanel(registry_client)
    qtbot.addWidget(skills)
    assert skills.entity_title() == "Skills"
    rules = GovernanceRulesPanel(registry_client)
    qtbot.addWidget(rules)
    assert rules.entity_title() == "Governance Rules"
    learnings = LearningsPanel(registry_client)
    qtbot.addWidget(learnings)
    assert learnings.entity_title() == "Learnings"


# --- create via dialogs ---------------------------------------------------


def test_create_skill_via_dialog(qtbot, registry_client):
    dialog = SkillCreateDialog(registry_client)
    qtbot.addWidget(dialog)
    assert "identifier" not in dialog._widgets  # server-assigned
    dialog._widgets["name"].setText("read prior outputs")
    dialog._widgets["description"].setPlainText("Read the feed-forward context.")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    sid = dialog.created_identifier()
    assert sid
    rec = registry_client.get_skill(sid)
    assert rec["name"] == "read prior outputs"
    assert rec["scope"] == "system"


def test_create_agent_profile_via_dialog(qtbot, registry_client):
    dialog = AgentProfileCreateDialog(registry_client)
    qtbot.addWidget(dialog)
    dialog._widgets["area"].setText("ui")
    dialog._widgets["tier"].setCurrentText("developer")
    dialog._widgets["description"].setPlainText("You are a UI developer agent.")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    pid = dialog.created_identifier()
    assert pid
    rec = registry_client.get_agent_profile(pid)
    assert rec["area"] == "ui"
    assert rec["tier"] == "developer"
    assert rec["scope"] == "system"


def test_create_governance_rule_via_dialog(qtbot, registry_client):
    dialog = GovernanceRuleCreateDialog(registry_client)
    qtbot.addWidget(dialog)
    dialog._widgets["body"].setPlainText("Never force-push to main.")
    dialog._widgets["enforcement"].setCurrentText("advisory")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    rid = dialog.created_identifier()
    assert registry_client.get_governance_rule(rid)["body"] == "Never force-push to main."


def test_create_learning_via_dialog(qtbot, registry_client):
    dialog = LearningCreateDialog(registry_client)
    qtbot.addWidget(dialog)
    dialog._widgets["area"].setText("ui")
    dialog._widgets["tier"].setCurrentText("developer")
    dialog._widgets["category"].setCurrentText("gotcha")
    dialog._widgets["content"].setPlainText("Worker widgets need deleteLater().")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    lid = dialog.created_identifier()
    assert registry_client.get_learning(lid)["category"] == "gotcha"


def test_create_engagement_scoped_skill_overlay(qtbot, registry_client):
    """An engagement overlay row is creatable from the scope combo."""
    dialog = SkillCreateDialog(registry_client)
    qtbot.addWidget(dialog)
    dialog._widgets["name"].setText("engagement-only skill")
    dialog._widgets["description"].setPlainText("Overlay.")
    # The scope combo offers ENG-001 (the active engagement) as well as system.
    dialog._widgets["scope"].setCurrentText("ENG-001")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    rec = registry_client.get_skill(dialog.created_identifier())
    assert rec["scope"] == "ENG-001"
    assert rec["engagement_id"] == "ENG-001"


# --- JSON column editor ---------------------------------------------------


def test_json_field_dialog_patches_io_contract(qtbot, registry_client):
    created = registry_client.create_skill(
        {"name": "tool skill", "kind": "tool", "description": "x", "scope": "system"}
    )
    sid = created["identifier"]
    dialog = JsonFieldDialog(
        registry_client.patch_skill, sid, "io_contract", "I/O contract", None
    )
    qtbot.addWidget(dialog)
    dialog._editor.setPlainText('{"method": "GET", "returns": "object"}')
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save()
    assert registry_client.get_skill(sid)["io_contract"] == {
        "method": "GET",
        "returns": "object",
    }


def test_json_field_dialog_rejects_invalid_json(qtbot, registry_client):
    created = registry_client.create_skill(
        {"name": "tool skill 2", "kind": "tool", "description": "x", "scope": "system"}
    )
    dialog = JsonFieldDialog(
        registry_client.patch_skill, created["identifier"], "io_contract", "I/O", None
    )
    qtbot.addWidget(dialog)
    dialog._editor.setPlainText("{not valid json")
    dialog._on_save()  # should NOT accept
    assert dialog.result() != dialog.DialogCode.Accepted
    assert "Invalid JSON" in dialog._error.text()


# --- bindings + effective contract ---------------------------------------


def test_binding_management_and_contract_preview(qtbot, registry_client):
    profile = registry_client.create_agent_profile(
        {"area": "api", "tier": "developer", "description": "api dev", "scope": "system"}
    )
    skill = registry_client.create_skill(
        {"name": "call api", "kind": "tool", "description": "x", "scope": "system"}
    )
    pid, sid = profile["identifier"], skill["identifier"]

    # Bind, verify, then the panel detail extras reflect it.
    registry_client.add_agent_profile_skill(pid, sid)
    bindings = registry_client.get_agent_profile_bindings(pid)
    assert any(e["identifier"] == sid for e in bindings["skills"])

    panel = AgentProfilesPanel(registry_client)
    qtbot.addWidget(panel)
    fresh = registry_client.get_agent_profile(pid)
    extras = panel.fetch_detail_extras(fresh)
    assert any(e["identifier"] == sid for e in extras["bindings"]["skills"])

    # Contract preview formats without error.
    text = panel._format_contract(extras["contract"])
    assert "SYSTEM PROMPT" in text
    assert "version_stamp" in text

    # Remove the binding.
    registry_client.remove_agent_profile_binding(pid, sid, "agent_profile_has_skill")
    assert registry_client.get_agent_profile_bindings(pid)["skills"] == []


def test_contract_engagement_selector_resolves(qtbot, registry_client):
    profile = registry_client.create_agent_profile(
        {"area": "storage", "tier": "architect", "description": "p", "scope": "system"}
    )
    pid = profile["identifier"]
    # System-defaults-only resolution returns a contract dict.
    contract = registry_client.get_agent_profile_contract(pid, engagement="__system_only__")
    assert contract["profile_id"] == pid


# --- learning promotion ---------------------------------------------------


def test_promote_learning_to_skill(qtbot, registry_client):
    learning = registry_client.create_learning(
        {"area": "ui", "tier": "developer", "category": "pattern",
         "content": "Use the shared CRUD dialog.", "scope": "system"}
    )
    dialog = PromoteToSkillDialog(learning)
    qtbot.addWidget(dialog)
    dialog._name.setText("shared crud dialog")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_ok()
    body = dialog.body()
    assert body["name"] == "shared crud dialog"
    result = registry_client.promote_learning_to_skill(learning["identifier"], body)
    assert result  # a skill record / promotion result


def test_promote_to_rule_requires_approval_for_enforced(qtbot, registry_client):
    learning = registry_client.create_learning(
        {"area": "ui", "tier": "developer", "category": "constraint",
         "content": "Always validate.", "scope": "system"}
    )
    dialog = PromoteToRuleDialog(learning)
    qtbot.addWidget(dialog)
    dialog._enforcement.setCurrentText("enforced")
    # No approval checked → blocked.
    dialog._on_ok()
    assert dialog.result() != dialog.DialogCode.Accepted
    assert "approval" in dialog._error.text().lower()
    # Approve → accepts, body flags human_approved.
    dialog._approve.setChecked(True)
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_ok()
    assert dialog.body()["human_approved"] is True


def test_edit_skill_scope_is_editable(qtbot, registry_client):
    """Scope is editable on edit (DEC-750): a record can be re-scoped."""
    created = registry_client.create_skill(
        {"name": "editable", "kind": "instruction", "description": "x", "scope": "system"}
    )
    sid = created["identifier"]
    fresh = registry_client.get_skill(sid)
    dialog = SkillEditDialog(registry_client, fresh)
    qtbot.addWidget(dialog)
    assert dialog._widgets["identifier"].isReadOnly()
    # Change scope system -> ENG-001; the diff includes it and the change persists.
    dialog._widgets["scope"].setCurrentText("ENG-001")
    assert dialog._build_edit_diff().get("scope") == "ENG-001"
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    updated = registry_client.get_skill(sid)
    assert updated["scope"] == "ENG-001"
    assert updated["engagement_id"] == "ENG-001"


# --- learning evidence + confidence (PI-336 / DEC-762) --------------------


def test_add_learning_evidence_raises_confidence(qtbot, registry_client):
    learning = registry_client.create_learning(
        {"area": "ui", "tier": "developer", "category": "pattern",
         "content": "x", "scope": "system"}
    )
    lid = learning["identifier"]
    assert registry_client.get_learning(lid)["confidence"] == 0
    updated = registry_client.add_learning_evidence(
        lid, target_type="decision", target_id="DEC-001", contradicts=False
    )
    assert updated["confidence"] == 1
    assert registry_client.get_learning(lid)["confidence"] == 1


def test_contradicting_evidence_must_be_work_task(qtbot, registry_client):
    from crmbuilder_v2.ui.exceptions import StorageClientError  # noqa: PLC0415

    learning = registry_client.create_learning(
        {"area": "ui", "tier": "developer", "category": "gotcha",
         "content": "y", "scope": "system"}
    )
    with pytest.raises(StorageClientError):
        registry_client.add_learning_evidence(
            learning["identifier"], target_type="decision", target_id="DEC-001",
            contradicts=True,
        )


def test_set_confidence_persists(qtbot, registry_client):
    learning = registry_client.create_learning(
        {"area": "ui", "tier": "developer", "category": "preference",
         "content": "z", "scope": "system"}
    )
    lid = learning["identifier"]
    registry_client.patch_learning(lid, {"confidence": 4})
    assert registry_client.get_learning(lid)["confidence"] == 4


def test_set_confidence_dialog_value(qtbot):
    dialog = SetConfidenceDialog(3)
    qtbot.addWidget(dialog)
    assert dialog.value() == 3
    dialog._spin.setValue(7)
    assert dialog.value() == 7


def test_add_evidence_dialog_contradicts_pins_work_task(qtbot):
    dialog = AddEvidenceDialog({"identifier": "LRN-001", "confidence": 0})
    qtbot.addWidget(dialog)
    dialog._contradicts.setChecked(True)
    assert dialog._target_type.currentText() == "work_task"
    assert not dialog._target_type.isEnabled()
    dialog._contradicts.setChecked(False)
    assert dialog._target_type.isEnabled()


def test_add_evidence_dialog_requires_target_id(qtbot):
    dialog = AddEvidenceDialog({"identifier": "LRN-001", "confidence": 0})
    qtbot.addWidget(dialog)
    dialog._target_id.setText("")
    dialog._on_ok()
    assert dialog.result() != dialog.DialogCode.Accepted
    assert dialog.body() is None
    dialog._target_id.setText("WTK-012")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_ok()
    assert dialog.body()["target_id"] == "WTK-012"
    assert dialog.body()["target_type"] in ("work_task", "decision", "test_spec")


# --- cross-engagement promotion + curation (PI-337 / DEC-765) -------------


def test_promote_learning_to_system(qtbot, registry_client):
    learning = registry_client.create_learning(
        {"area": "ui", "tier": "developer", "category": "pattern",
         "content": "engagement insight", "scope": "ENG-001"}
    )
    lid = learning["identifier"]
    assert registry_client.get_learning(lid)["scope"] == "ENG-001"
    promoted = registry_client.promote_learning_to_system(lid)
    assert promoted["scope"] == "system"
    assert registry_client.get_learning(lid)["engagement_id"] is None


def test_promote_to_system_rejects_already_system(qtbot, registry_client):
    from crmbuilder_v2.ui.exceptions import StorageClientError  # noqa: PLC0415

    learning = registry_client.create_learning(
        {"area": "ui", "tier": "developer", "category": "pattern",
         "content": "already system", "scope": "system"}
    )
    with pytest.raises(StorageClientError):
        registry_client.promote_learning_to_system(learning["identifier"])


def test_curate_retires_contradicted_zero_confidence(qtbot, registry_client):
    learning = registry_client.create_learning(
        {"area": "ui", "tier": "developer", "category": "gotcha",
         "content": "stale candidate", "scope": "system"}
    )
    lid = learning["identifier"]
    # Contradicting evidence (work_task) — confidence stays floored at 0, adds the edge.
    registry_client.add_learning_evidence(
        lid, target_type="work_task", target_id="WTK-001", contradicts=True
    )
    result = registry_client.curate_learnings(area="ui", scope=None)
    assert lid in result["retired"]
    assert registry_client.get_learning(lid)["status"] == "stale"


def test_cross_engagement_candidates_returns_list(qtbot, registry_client):
    # With a single engagement there are no cross-engagement candidates, but the
    # endpoint + client return a well-formed list.
    assert registry_client.list_cross_engagement_candidates() == []


def test_curate_area_dialog_requires_area(qtbot):
    from crmbuilder_v2.ui.dialogs.registry_crud import CurateAreaDialog  # noqa: PLC0415

    dialog = CurateAreaDialog()
    qtbot.addWidget(dialog)
    dialog._area.setCurrentText("")
    dialog._on_ok()
    assert dialog.result() != dialog.DialogCode.Accepted
    assert dialog.body() is None
    dialog._area.setCurrentText("storage")
    dialog._scope.setText("ENG-001")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_ok()
    assert dialog.body() == {"area": "storage", "scope": "ENG-001"}


def test_cross_engagement_dialog_handles_empty(qtbot, registry_client):
    from crmbuilder_v2.ui.dialogs.registry_crud import (  # noqa: PLC0415
        CrossEngagementCandidatesDialog,
    )

    dialog = CrossEngagementCandidatesDialog(registry_client)
    qtbot.addWidget(dialog)
    assert dialog._list.count() == 1  # the "(no candidates)" placeholder
    assert not dialog._promote_btn.isEnabled()
