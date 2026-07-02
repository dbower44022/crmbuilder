"""Seed the initial Domain Knowledge reference entries (REL-016 / PI-063, REQ-398).

REQ-398 wants an initial library of domain knowledge for common CRM domains that
the AI can draw on when a client's domain is recognized. This module holds the
authored starter content (system-scoped ``domain_knowledge`` Reference Entries)
and seeds it create-only (idempotent by name), mirroring ``registry_seed``.

The content is framework-level starter guidance authored at ``active`` status; an
operator refines or overlays per engagement. Run explicitly against a store whose
schema includes ``reference_entries`` (a fresh bootstrap, or the live store once
migration 0106/0063 is applied) — it is not auto-run at bootstrap.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from crmbuilder_v2.access.repositories import reference_entries

# The authored initial Domain Knowledge entries. Each is a system row
# (scope defaults to system). ``trigger_keywords`` feed the PI-066 loader.
SEED_DOMAIN_KNOWLEDGE: list[dict] = [
    {
        "name": "Nonprofit Mentoring Organization",
        "applies_to": "nonprofit mentoring",
        "trigger_keywords": [
            "mentoring",
            "mentor",
            "mentee",
            "nonprofit mentoring",
            "youth mentoring",
            "business mentoring",
        ],
        "content": {
            "body": (
                "Nonprofit mentoring organizations match volunteer mentors with "
                "mentees and support the relationship over time. Core activities: "
                "recruiting and screening mentors; recruiting and assessing mentees; "
                "matching the two on fit and goals; onboarding and training; tracking "
                "the mentoring relationship (sessions, milestones, goals) through its "
                "lifecycle; and measuring outcomes for funders. Typical actors are "
                "the program coordinator (runs matching and oversight), mentors, "
                "mentees, and — for youth programs — parents/guardians. Watch for: "
                "mentor background checks and compliance; the application-to-match "
                "funnel and its drop-off; recurring session logging; and "
                "grant-reportable outcome metrics. Money usually comes from grants "
                "and donations rather than fees, so donor and grant tracking often "
                "sit alongside the mentoring program."
            )
        },
    },
    {
        "name": "Charitable Foundation",
        "applies_to": "charitable foundation",
        "trigger_keywords": [
            "foundation",
            "grantmaking",
            "grants",
            "grantee",
            "philanthropy",
            "endowment",
        ],
        "content": {
            "body": (
                "Charitable foundations exist to distribute funds to causes, usually "
                "through grantmaking. Core activities: soliciting or inviting grant "
                "applications; reviewing and scoring them against program criteria; "
                "awarding grants; disbursing funds on a schedule; and collecting "
                "grantee reports on how the money was used and what it achieved. "
                "Typical actors are program officers (own a portfolio of grantees), "
                "a review committee/board (approve awards), grantees (the funded "
                "organizations), and donors/the endowment (the funding source). "
                "Watch for: the application review workflow and its decision states; "
                "multi-year and installment grant schedules; compliance and "
                "reporting deadlines; and the distinction between the foundation's "
                "own funds (endowment/donors) and the outbound grants it makes."
            )
        },
    },
    {
        "name": "Social Marketing Program",
        "applies_to": "social marketing",
        "trigger_keywords": [
            "social marketing",
            "behavior change",
            "campaign",
            "outreach",
            "public health campaign",
            "awareness",
        ],
        "content": {
            "body": (
                "Social marketing programs apply marketing techniques to drive a "
                "public-good behavior change (health, safety, environment) rather "
                "than sell a product. Core activities: identifying a target audience "
                "and the behavior to change; designing campaigns and messaging; "
                "running outreach across channels; capturing engagement and "
                "responses; and measuring behavior-change outcomes against goals. "
                "Typical actors are the campaign manager, partner organizations and "
                "channels, the target audience/participants, and funders who require "
                "reach and outcome reporting. Watch for: campaign-to-audience "
                "targeting; multi-channel engagement tracking; consent and opt-in for "
                "outreach contacts; and outcome metrics that measure behavior change, "
                "not just impressions."
            )
        },
    },
]


# Organization Structure entries (REL-016 / PI-064, REQ-399) — the typical
# structural shape (entities + relationships) of an organization type.
SEED_ORGANIZATION_STRUCTURE: list[dict] = [
    {
        "name": "Nonprofit Mentoring Organization — Structure",
        "applies_to": "nonprofit mentoring",
        "trigger_keywords": ["mentoring", "mentor", "mentee", "nonprofit mentoring"],
        "content": {
            "typical_entities": [
                "Mentor",
                "Mentee",
                "Match",
                "Mentoring Session",
                "Program",
                "Goal",
                "Donor",
                "Grant",
            ],
            "typical_relationships": [
                "A Match links one Mentor to one Mentee",
                "A Match belongs to a Program",
                "A Mentoring Session belongs to a Match",
                "A Goal belongs to a Match (or Mentee)",
                "A Grant funds a Program",
            ],
        },
    },
    {
        "name": "Charitable Foundation — Structure",
        "applies_to": "charitable foundation",
        "trigger_keywords": ["foundation", "grantmaking", "grants", "grantee"],
        "content": {
            "typical_entities": [
                "Grant Application",
                "Grant",
                "Grantee",
                "Program Area",
                "Disbursement",
                "Grantee Report",
                "Donor",
                "Endowment Fund",
            ],
            "typical_relationships": [
                "A Grant Application is reviewed and becomes a Grant",
                "A Grant is awarded to a Grantee",
                "A Grant belongs to a Program Area",
                "A Disbursement belongs to a Grant (installment schedule)",
                "A Grantee Report belongs to a Grant",
            ],
        },
    },
    {
        "name": "Membership Organization — Structure",
        "applies_to": "membership organization",
        "trigger_keywords": ["membership", "member", "dues", "chapter", "association"],
        "content": {
            "typical_entities": [
                "Member",
                "Membership",
                "Membership Tier",
                "Dues Payment",
                "Chapter",
                "Event",
                "Event Registration",
            ],
            "typical_relationships": [
                "A Membership belongs to a Member and a Membership Tier",
                "A Dues Payment belongs to a Membership",
                "A Member may belong to a Chapter",
                "An Event Registration links a Member to an Event",
            ],
        },
    },
]

# Inventory Items entries (REL-016 / PI-065, REQ-400) — the typical entities,
# personas, and processes of an organization type (a discovery checklist).
SEED_INVENTORY_ITEMS: list[dict] = [
    {
        "name": "Nonprofit Mentoring Organization — Inventory",
        "applies_to": "nonprofit mentoring",
        "trigger_keywords": ["mentoring", "mentor", "mentee", "nonprofit mentoring"],
        "content": {
            "entities": ["Mentor", "Mentee", "Match", "Mentoring Session", "Program", "Goal"],
            "personas": ["Program Coordinator", "Mentor", "Mentee", "Parent/Guardian"],
            "processes": [
                "Recruit and screen mentors",
                "Recruit and assess mentees",
                "Match mentor to mentee",
                "Onboard and train",
                "Log mentoring sessions",
                "Measure and report outcomes",
            ],
        },
    },
    {
        "name": "Charitable Foundation — Inventory",
        "applies_to": "charitable foundation",
        "trigger_keywords": ["foundation", "grantmaking", "grants", "grantee"],
        "content": {
            "entities": ["Grant Application", "Grant", "Grantee", "Program Area", "Disbursement", "Grantee Report"],
            "personas": ["Program Officer", "Review Committee/Board", "Grantee", "Donor"],
            "processes": [
                "Solicit or invite applications",
                "Review and score applications",
                "Award grants",
                "Disburse funds on schedule",
                "Collect and review grantee reports",
            ],
        },
    },
    {
        "name": "Membership Organization — Inventory",
        "applies_to": "membership organization",
        "trigger_keywords": ["membership", "member", "dues", "chapter", "association"],
        "content": {
            "entities": ["Member", "Membership", "Membership Tier", "Dues Payment", "Chapter", "Event", "Event Registration"],
            "personas": ["Membership Manager", "Member", "Chapter Leader", "Event Organizer"],
            "processes": [
                "Enroll and renew members",
                "Collect dues",
                "Manage tiers and benefits",
                "Run member events",
                "Track engagement and retention",
            ],
        },
    },
]

# Kind → authored entries. Adding a kind is a one-line change here.
_SEED_BY_KIND: dict[str, list[dict]] = {
    "domain_knowledge": SEED_DOMAIN_KNOWLEDGE,
    "organization_structure": SEED_ORGANIZATION_STRUCTURE,
    "inventory_items": SEED_INVENTORY_ITEMS,
}


def seed_reference_entries(session: Session) -> dict:
    """Create the initial reference entries (all kinds); skip existing ones.

    Idempotent by ``name`` (system scope). Returns a summary
    ``{"created": [...], "skipped": [...]}``.
    """
    existing = {
        r["name"].lower()
        for r in reference_entries.list_all(session, scope="system")
    }
    created: list[str] = []
    skipped: list[str] = []
    for kind, entries in _SEED_BY_KIND.items():
        for entry in entries:
            if entry["name"].lower() in existing:
                skipped.append(entry["name"])
                continue
            row = reference_entries.create(
                session,
                name=entry["name"],
                kind=kind,
                content=entry["content"],
                applies_to=entry["applies_to"],
                trigger_keywords=entry["trigger_keywords"],
                scope="system",
            )
            created.append(row["identifier"])
    return {"created": created, "skipped": skipped}
