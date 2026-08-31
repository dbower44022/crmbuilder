"""Panel registry — the one label → panel-class table (REQ-526 / PI-432).

Replaces the label-keyed ``if/elif`` chain that used to live in
``main_window.build_panel``. Every phase tab, the detail-window manager and
quick open build panels through :func:`build_panel`; ``ALL_PANEL_LABELS`` is
the alphabetical index the "All panels" sidebar group renders, so a new panel
is registered exactly once, here.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from crmbuilder_v2.config import get_settings
from crmbuilder_v2.ui.base.list_detail_panel import ListDetailPanel
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.panels.agent_profiles import AgentProfilesPanel
from crmbuilder_v2.ui.panels.candidate_review import CandidateReviewPanel
from crmbuilder_v2.ui.panels.charter import CharterPanel
from crmbuilder_v2.ui.panels.chat import ChatPanel
from crmbuilder_v2.ui.panels.close_out_payloads import CloseOutPayloadsPanel
from crmbuilder_v2.ui.panels.commits import CommitsPanel
from crmbuilder_v2.ui.panels.conversations import ConversationsPanel
from crmbuilder_v2.ui.panels.cost import CostPanel
from crmbuilder_v2.ui.panels.crm_candidates import CrmCandidatesPanel
from crmbuilder_v2.ui.panels.decisions import DecisionsPanel
from crmbuilder_v2.ui.panels.deploy_history import DeployHistoryPanel
from crmbuilder_v2.ui.panels.deposit_events import DepositEventsPanel
from crmbuilder_v2.ui.panels.domains import DomainsPanel
from crmbuilder_v2.ui.panels.engagements import EngagementsPanel
from crmbuilder_v2.ui.panels.entities import EntitiesPanel
from crmbuilder_v2.ui.panels.field import FieldsPanel
from crmbuilder_v2.ui.panels.glossary import GlossaryPanel
from crmbuilder_v2.ui.panels.instances import InstancesPanel
from crmbuilder_v2.ui.panels.manual_config import ManualConfigPanel
from crmbuilder_v2.ui.panels.participant import ParticipantsPanel
from crmbuilder_v2.ui.panels.persona import PersonasPanel
from crmbuilder_v2.ui.panels.planning_items import PlanningItemsPanel
from crmbuilder_v2.ui.panels.processes import ProcessesPanel
from crmbuilder_v2.ui.panels.projects import ProjectsPanel
from crmbuilder_v2.ui.panels.publish_history import PublishHistoryPanel
from crmbuilder_v2.ui.panels.reconcile_grid import ReconcileGridPanel
from crmbuilder_v2.ui.panels.reference_books import ReferenceBooksPanel
from crmbuilder_v2.ui.panels.reference_entries import ReferenceEntriesPanel
from crmbuilder_v2.ui.panels.references import ReferencesPanel
from crmbuilder_v2.ui.panels.registry_learnings import LearningsPanel
from crmbuilder_v2.ui.panels.registry_rules import GovernanceRulesPanel
from crmbuilder_v2.ui.panels.registry_skills import SkillsPanel
from crmbuilder_v2.ui.panels.releases import ReleasesPanel
from crmbuilder_v2.ui.panels.requirements import RequirementsPanel
from crmbuilder_v2.ui.panels.resource_locks import ResourceLocksPanel
from crmbuilder_v2.ui.panels.review import ReviewPanel
from crmbuilder_v2.ui.panels.risks import RisksPanel
from crmbuilder_v2.ui.panels.sessions import SessionsPanel
from crmbuilder_v2.ui.panels.status import StatusPanel
from crmbuilder_v2.ui.panels.test_spec import TestSpecsPanel
from crmbuilder_v2.ui.panels.topics import TopicsPanel
from crmbuilder_v2.ui.panels.work_tasks import WorkTasksPanel
from crmbuilder_v2.ui.panels.work_tickets import WorkTicketsPanel
from crmbuilder_v2.ui.panels.workstreams import WorkstreamsPanel

PanelFactory = Callable[[StorageClient, object], QWidget]


def _simple(cls):
    return lambda client, _ctx: cls(client)


# Label → factory(client, active_context). Chat consumes the FastAPI surface
# directly (DEC-253) so it takes the API base URL; Engagements additionally
# takes the active context.
PANEL_REGISTRY: dict[str, PanelFactory] = {
    "Agent Profiles": _simple(AgentProfilesPanel),
    "Candidate Review": _simple(CandidateReviewPanel),
    "Charter": _simple(CharterPanel),
    "Chat": lambda _client, _ctx: ChatPanel(get_settings().api_base_url),
    "Close-Out Payloads": _simple(CloseOutPayloadsPanel),
    "Commits": _simple(CommitsPanel),
    "Conversations": _simple(ConversationsPanel),
    "Cost": _simple(CostPanel),
    "CRM Candidates": _simple(CrmCandidatesPanel),
    "Decisions": _simple(DecisionsPanel),
    "Deploy History": _simple(DeployHistoryPanel),
    "Deposit Events": _simple(DepositEventsPanel),
    "Domains": _simple(DomainsPanel),
    "Engagements": lambda client, ctx: EngagementsPanel(client, active_context=ctx),
    "Entities": _simple(EntitiesPanel),
    "Fields": _simple(FieldsPanel),
    "Glossary": _simple(GlossaryPanel),
    "Governance Rules": _simple(GovernanceRulesPanel),
    "Instances": _simple(InstancesPanel),
    "Learnings": _simple(LearningsPanel),
    "Manual Configs": _simple(ManualConfigPanel),
    "Participants": _simple(ParticipantsPanel),
    "Personas": _simple(PersonasPanel),
    "Planning Items": _simple(PlanningItemsPanel),
    "Processes": _simple(ProcessesPanel),
    "Projects": _simple(ProjectsPanel),
    "Publish History": _simple(PublishHistoryPanel),
    "Reconcile": _simple(ReconcileGridPanel),
    "Reference Books": _simple(ReferenceBooksPanel),
    "Reference Entries": _simple(ReferenceEntriesPanel),
    "References": _simple(ReferencesPanel),
    "Releases": _simple(ReleasesPanel),
    "Requirements": _simple(RequirementsPanel),
    "Requirements Review": _simple(ReviewPanel),
    "Resource Locks": _simple(ResourceLocksPanel),
    "Risks": _simple(RisksPanel),
    "Sessions": _simple(SessionsPanel),
    "Skills": _simple(SkillsPanel),
    "Status": _simple(StatusPanel),
    "Test Specs": _simple(TestSpecsPanel),
    "Topics": _simple(TopicsPanel),
    "Work Tasks": _simple(WorkTasksPanel),
    "Work Tickets": _simple(WorkTicketsPanel),
    "Workstreams": _simple(WorkstreamsPanel),
}

# Alphabetical index of every registered panel — the "All panels" group.
ALL_PANEL_LABELS: tuple[str, ...] = tuple(sorted(PANEL_REGISTRY))


def build_panel(
    label: str,
    client: StorageClient,
    *,
    active_context=None,
) -> QWidget:
    """Construct the page widget for a panel label.

    An unmapped label falls through to a placeholder ``QLabel`` (which the
    detail-window manager treats as non-openable).
    """
    factory = PANEL_REGISTRY.get(label)
    if factory is not None:
        panel = factory(client, active_context)
        _stamp_view_entity_type(panel, label)
        return panel
    placeholder = QLabel(f"Panel for {label} — not yet implemented.")
    placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
    placeholder.setObjectName(f"placeholder_{label.lower().replace(' ', '_')}")
    return placeholder


def _stamp_view_entity_type(panel: QWidget, label: str) -> None:
    """Give a list panel the entity type its ``View`` action opens (REQ-534).

    Reverse-looks-up ``label`` in the main window's entity-type → label
    map so ``View`` can hand ``open_requested`` the same ``entity_type`` the
    detail-window manager resolves. Panels whose label has no entity type
    (or that are not ``ListDetailPanel``s) are left at ``None``.
    """
    if not isinstance(panel, ListDetailPanel):
        return
    # Lazy import: main_window imports this module at load time.
    from crmbuilder_v2.ui.main_window import ENTITY_TYPE_TO_SIDEBAR_LABEL

    for entity_type, panel_label in ENTITY_TYPE_TO_SIDEBAR_LABEL.items():
        if panel_label == label:
            panel.view_entity_type = entity_type
            return
