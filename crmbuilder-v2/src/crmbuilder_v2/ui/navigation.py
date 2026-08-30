"""Phase-based navigation model (REQ-526 / PI-432).

The desktop is organised by the **phase** the user is working in. Each open
phase is a tab; each tab's sidebar is that phase's *step checklist* — the
panels the phase produces records in, numbered in the order the Master
CRMBuilder PRD performs them — above a fixed "Every session" group and a
collapsed alphabetical "All panels" index.

This module holds the phase list (PRD §4 order), the seeded phase→steps map,
and the identifier-prefix table quick open uses. It is deliberately free of Qt
so it can be unit-tested and later served from the store: ``load_phase_map``
is the single seam through which a store-held map would arrive (DEC-953 —
"the phase map is data, not code"; the seeded default ships in this module
until the store carries it).

Ordering rule (DEC-953): PRD sequence where one exists, alphabetical
otherwise, never build order.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Phases — Master CRMBuilder PRD §4, in order, plus the non-client pseudo-phase.
# ---------------------------------------------------------------------------

OPERATE_KEY = "operate"


@dataclass(frozen=True)
class Phase:
    key: str
    number: str  # "1", "1.5", … "13"; "" for Operate CRMBuilder
    name: str
    provisional: bool = False  # PRD section is a placeholder

    @property
    def tab_label(self) -> str:
        return f"{self.number} · {self.name}" if self.number else self.name

    @property
    def steps_group_title(self) -> str:
        return f"Phase {self.number} steps" if self.number else self.name


PHASES: tuple[Phase, ...] = (
    Phase("1", "1", "Business Context Capture"),
    Phase("1.5", "1.5", "Existing System Baseline"),
    Phase("2", "2", "Domain Discovery"),
    Phase("3", "3", "Inventory Reconciliation"),
    Phase("4", "4", "Domain Overview and Process Definition", provisional=True),
    Phase("5", "5", "Entity PRDs", provisional=True),
    Phase("6", "6", "Cross-Domain Service Definition", provisional=True),
    Phase("7", "7", "Domain Reconciliation", provisional=True),
    Phase("8", "8", "Stakeholder Review", provisional=True),
    Phase("9", "9", "YAML Generation", provisional=True),
    Phase("10", "10", "CRM Selection", provisional=True),
    Phase("11", "11", "CRM Deployment"),
    Phase("12", "12", "CRM Configuration"),
    Phase("13", "13", "Verification"),
    Phase(OPERATE_KEY, "", "Operate CRMBuilder"),
)

PHASES_BY_KEY: dict[str, Phase] = {p.key: p for p in PHASES}

DEFAULT_PHASE_KEY = "1"

# The four panels every phase uses (PRD §11 — Open → Conduct → Close is the
# same lifecycle in all thirteen phases). "Chat" routes to the pinned Chat tab.
EVERY_SESSION_GROUP_TITLE = "Every session"
EVERY_SESSION_STEPS: tuple[str, ...] = (
    "Sessions",
    "Decisions",
    "Planning Items",
    "Chat",
)

ALL_PANELS_GROUP_TITLE = "All panels"

# CRMBuilder's own operations — not a client phase. Alphabetical (no PRD
# sequence exists for them).
OPERATE_PANELS: tuple[str, ...] = tuple(
    sorted(
        (
            "Agent Profiles",
            "Close-Out Payloads",
            "Commits",
            "Conversations",
            "Cost",
            "Deposit Events",
            "Engagements",
            "Governance Rules",
            "Learnings",
            "Projects",
            "Releases",
            "Resource Locks",
            "Skills",
            "Status",
            "Work Tasks",
            "Work Tickets",
            "Workstreams",
        )
    )
)

# Seeded phase → ordered step panels. Step order is the order the phase's
# "Captured V2 Records" table (PRD §5, §7, §8, §9) produces them; provisional
# phases follow the legacy 13-phase process until their PRD section is
# drafted. Every label is an existing panel — the design's "Audit" and
# "Findings" steps map onto the panels that host those actions today
# (Instances hosts the audit action; Candidate Review hosts findings review).
DEFAULT_PHASE_STEPS: dict[str, tuple[str, ...]] = {
    "1": ("Charter", "Personas", "Domains", "Processes", "References", "Glossary"),
    "1.5": (
        "Instances",
        "Entities",
        "Fields",
        "Personas",
        "Processes",
        "Manual Configs",
    ),
    "2": ("Domains", "Entities", "Personas", "Processes", "Participants"),
    "3": (
        "Candidate Review",
        "Entities",
        "Fields",
        "Personas",
        "Processes",
        "Manual Configs",
    ),
    "4": ("Requirements", "Requirements Review", "Processes", "Domains"),
    "5": ("Entities", "Fields", "Requirements", "Manual Configs"),
    "6": ("Processes", "Reference Entries", "Requirements"),
    "7": ("Requirements Review", "Entities", "Fields", "Processes"),
    "8": ("Requirements Review", "Test Specs", "Topics"),
    "9": ("Reference Books",),
    "10": ("CRM Candidates",),
    "11": ("Instances", "Deploy History"),
    "12": ("Instances", "Publish History", "Manual Configs"),
    "13": ("Reconcile", "Candidate Review", "Test Specs", "Risks"),
    OPERATE_KEY: OPERATE_PANELS,
}


@dataclass
class PhaseMap:
    """Phase → ordered step labels, with the fixed groups around them."""

    steps: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: dict(DEFAULT_PHASE_STEPS)
    )

    def steps_for(self, phase_key: str) -> tuple[str, ...]:
        return tuple(self.steps.get(phase_key, ()))

    def sidebar_groups(
        self, phase_key: str, all_panels: tuple[str, ...]
    ) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """The three sidebar groups for a phase tab.

        ``all_panels`` is the registry's alphabetical label list; it becomes
        the collapsed "All panels" index so nothing is unreachable.
        """
        phase = PHASES_BY_KEY[phase_key]
        return (
            (EVERY_SESSION_GROUP_TITLE, EVERY_SESSION_STEPS),
            (phase.steps_group_title, self.steps_for(phase_key)),
            (ALL_PANELS_GROUP_TITLE, tuple(sorted(all_panels))),
        )


def load_phase_map(client=None) -> PhaseMap:
    """Return the phase map to navigate by.

    The seam for a store-held map (DEC-953). Today it returns the seeded
    default; a client is accepted so the call site does not change when the
    store starts serving the map.
    """
    return PhaseMap()


# ---------------------------------------------------------------------------
# Identifier prefixes — quick open resolves ``REQ-52`` to the Requirements
# panel through this table (prefix → reference entity_type, which the main
# window already maps to a panel label).
# ---------------------------------------------------------------------------

IDENTIFIER_PREFIX_TO_ENTITY_TYPE: dict[str, str] = {
    "DEC": "decision",
    "SES": "session",
    "RSK": "risk",
    "PI": "planning_item",
    "TOP": "topic",
    "REF": "reference",
    "DOM": "domain",
    "ENT": "entity",
    "PROC": "process",
    "REQ": "requirement",
    "MCF": "manual_config",
    "TSP": "test_spec",
    "PER": "persona",
    "PRT": "participant",
    "FLD": "field",
    "ENG": "engagement",
    "PRJ": "project",
    "CNV": "conversation",
    "CONV": "conversation",
    "RBK": "reference_book",
    "WT": "work_ticket",
    "COP": "close_out_payload",
    "DEP": "deposit_event",
    "CMT": "commit",
    "WS": "workstream",
    "WTK": "work_task",
    "TERM": "term",
    "INST": "instance",
    "REL": "release",
    "AGP": "agent_profile",
    "SKL": "skill",
    "GVR": "governance_rule",
    "LRN": "learning",
    "RFE": "reference_entry",
    "CRM": "crm_candidate",
}


def split_identifier_prefix(text: str) -> tuple[str, str] | None:
    """``"req-52"`` → ``("REQ", "REQ-52")``; ``None`` when not identifier-shaped."""
    raw = text.strip().upper()
    if "-" not in raw:
        return None
    prefix, _, rest = raw.partition("-")
    if not prefix.isalpha() or (rest and not rest.isdigit()):
        return None
    return prefix, raw
