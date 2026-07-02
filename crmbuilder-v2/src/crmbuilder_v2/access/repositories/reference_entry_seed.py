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


def seed_reference_entries(session: Session) -> dict:
    """Create the initial Domain Knowledge entries; skip any that already exist.

    Idempotent by ``name`` (system scope). Returns a summary
    ``{"created": [...], "skipped": [...]}``.
    """
    existing = {
        r["name"].lower()
        for r in reference_entries.list_all(session, scope="system")
    }
    created: list[str] = []
    skipped: list[str] = []
    for entry in SEED_DOMAIN_KNOWLEDGE:
        if entry["name"].lower() in existing:
            skipped.append(entry["name"])
            continue
        row = reference_entries.create(
            session,
            name=entry["name"],
            kind="domain_knowledge",
            content=entry["content"],
            applies_to=entry["applies_to"],
            trigger_keywords=entry["trigger_keywords"],
            scope="system",
        )
        created.append(row["identifier"])
    return {"created": created, "skipped": skipped}
