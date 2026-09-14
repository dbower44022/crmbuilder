"""The thirteen-row Mentor Application status-transition table as a fixture.

PI-471's acceptance content (REQ-577, REQ-584, REQ-585, REQ-586). The table is
the one the product owner approved on 09-05-26 for the Cleveland Business
Mentors engagement: one row per allowed move of the mentor status field on the
mentor profile within the Mentor Application process. Its authoritative copy is
section 10 of that engagement's rendered process document and the notes on the
process record; this module holds it in the shape the transition repository
takes, so the build can be tested against the approved content without reaching
into another engagement's store.

``Team`` in the approved table is the Mentor Administration Team persona;
``System`` is the CRM and the intake application together, which is why several
system rows carry an occasion naming which one acts (DEC-1070).

The seed helper builds the surrounding records the checks require — a domain, a
process, the two entities the process touches, the status field with its ten
options, the fields a move requires, the persona, and one view, one message
template and one automation to stand as referenced consequences.
"""

from __future__ import annotations

from crmbuilder_v2.access.repositories import (
    automation,
    domain,
    entity,
    field,
    message_template,
    persona,
    process,
    references,
    view,
)

#: The ten values of the mentor status field, in the order the table uses them.
MENTOR_STATUS_OPTIONS = [
    "Prospect",
    "Candidate",
    "Under Review",
    "Accepted-Provisional",
    "Provisional",
    "Approved",
    "Active",
    "Declined",
    "Dormant",
    "Inactive",
]

#: The five statuses the approved table calls "any pre-Active status".
PRE_ACTIVE = [
    "Candidate",
    "Under Review",
    "Accepted-Provisional",
    "Provisional",
    "Approved",
]


def seed_mentor_application(session) -> dict:
    """Create the records the thirteen rows refer to; return their identifiers.

    Returns a mapping with the process, the entities, the status field, the
    named fields the moves require, the persona, and the three records that
    stand as referenced consequences.
    """
    dom = domain.create_domain(
        session,
        name="Mentor Recruiting",
        purpose="Bring new mentors in.",
        description="Recruiting and onboarding mentors.",
    )["domain_identifier"]
    proc = process.create_process(
        session,
        name="Mentor Application",
        domain_identifier=dom,
        purpose="Take a prospective mentor from application to active.",
    )["process_identifier"]

    profile = entity.create_entity(
        session, name="MentorProfile", description="A mentor's profile."
    )["entity_identifier"]
    submission = entity.create_entity(
        session, name="IntakeSubmission", description="A submitted form."
    )["entity_identifier"]
    # An entity the process does not touch, for the negative check.
    unrelated = entity.create_entity(
        session, name="Invoice", description="Not part of this process."
    )["entity_identifier"]

    for target in (profile, submission):
        references.create(
            session,
            source_type="process",
            source_id=proc,
            target_type="entity",
            target_id=target,
            relationship="process_touches_entity",
        )

    status_field = field.create_field(
        session,
        field_belongs_to_entity_identifier=profile,
        name="mentorStatus",
        description="Where the mentor is in the application.",
        type="enum",
        options=[
            {"option_value": value, "option_order": index}
            for index, value in enumerate(MENTOR_STATUS_OPTIONS)
        ],
    )["field_identifier"]

    def _text_field(parent: str, name: str) -> str:
        return field.create_field(
            session,
            field_belongs_to_entity_identifier=parent,
            name=name,
            description=name,
            type="text",
        )["field_identifier"]

    fields = {
        "decline_reason": _text_field(profile, "declineReason"),
        "decision_summary": _text_field(profile, "decisionSummary"),
        "member_notes": _text_field(profile, "memberNotes"),
        "chapter_email": _text_field(profile, "chapterEmail"),
        "crm_login": _text_field(profile, "crmLogin"),
        "contact_assignment": _text_field(profile, "contactAssignment"),
        "second_application_note": _text_field(
            profile, "secondApplicationNote"
        ),
        "raw_form_content": _text_field(submission, "rawFormContent"),
        "intake_status": _text_field(submission, "intakeStatus"),
        # On an entity the process does not touch — used by the negative check.
        "unrelated": _text_field(unrelated, "invoiceTotal"),
    }

    team = persona.create_persona(
        session,
        name="Mentor Administration Team",
        role_summary="Reviews and votes on mentor applicants.",
    )["persona_identifier"]
    references.create(
        session,
        source_type="process",
        source_id=proc,
        target_type="persona",
        target_id=team,
        relationship="process_performed_by_persona",
    )

    candidates_view = view.create_view(
        session,
        name="Mentor candidates",
        entity=profile,
        columns=["mentorStatus"],
    )["view_identifier"]
    confirmation = message_template.create_message_template(
        session,
        name="Mentor application confirmation",
        body="Thank you for applying.",
    )["message_template_identifier"]
    provisioning = automation.create_automation(
        session,
        name="Mentor email provisioning",
        entity=profile,
        trigger="on_update",
        actions=[{"type": "webhook", "url": "https://example.invalid/mailbox"}],
    )["automation_identifier"]

    return {
        "domain": dom,
        "process": proc,
        "profile_entity": profile,
        "submission_entity": submission,
        "unrelated_entity": unrelated,
        "status_field": status_field,
        "fields": fields,
        "team_persona": team,
        "candidates_view": candidates_view,
        "confirmation_template": confirmation,
        "provisioning_automation": provisioning,
    }


def thirteen_rows(seed: dict) -> list[dict]:
    """The approved thirteen rows as ``create_transition`` keyword arguments.

    Row order is the order of the approved table, and becomes the process's
    transition order. Where the approved table names a routine that has no
    automation record — mentor login provisioning and the CRM welcome email —
    the row carries the words instead and so appears in the incompleteness
    report (REQ-581); mentor email provisioning does have a record here and is
    referenced.
    """
    f = seed["fields"]
    team = seed["team_persona"]
    process_identifier = seed["process"]
    field_identifier = seed["status_field"]

    def row(**kwargs) -> dict:
        base = {"process": process_identifier, "field": field_identifier}
        base.update(kwargs)
        return base

    return [
        # 1. (no record) -> Candidate, System.
        row(
            from_kind="record_creation",
            to_value="Candidate",
            actor_kind="system",
            actor_occasion="the intake application",
            required_fields=[f["intake_status"], f["raw_form_content"]],
            precondition="No Contact matches the submitter email.",
            consequences=[
                seed["candidates_view"],
                seed["confirmation_template"],
            ],
            notes="Submission record first (DEC-018); email-match rule "
            "(DEC-019); confirmation setting (DEC-043).",
        ),
        # 2. Prospect -> Candidate, System.
        row(
            from_values=["Prospect"],
            to_value="Candidate",
            actor_kind="system",
            actor_occasion="the intake application",
            required_fields=[f["intake_status"]],
            precondition="The email matches a Contact whose profile is "
            "Prospect.",
            consequences=[seed["candidates_view"]],
            notes="Prospect match updates the profile (DEC-019, DEC-040).",
        ),
        # 3. Declined -> Candidate, System.
        row(
            from_values=["Declined"],
            to_value="Candidate",
            actor_kind="system",
            actor_occasion="the intake application",
            required_fields=[f["intake_status"], f["second_application_note"]],
            precondition="The email matches a Declined profile.",
            consequences=[seed["candidates_view"]],
            notes="Re-application returns to Candidate (DEC-029).",
        ),
        # 4. Candidate -> Under Review, Team.
        row(
            from_values=["Candidate"],
            to_value="Under Review",
            actor_kind="persona",
            actor_persona=team,
            precondition="Nothing; the preliminary review is judgment.",
            notes="Preliminary review (DEC-020).",
        ),
        # 5. Candidate -> Declined, Team.
        row(
            from_values=["Candidate"],
            to_value="Declined",
            actor_kind="persona",
            actor_persona=team,
            required_fields=[f["decline_reason"]],
            manual_follow_up="A decline email is optional and sent by hand.",
            notes="Preliminary decline (DEC-020, DEC-024, DEC-044, DEC-026).",
        ),
        # 6. Under Review -> Accepted-Provisional, Team, first vote.
        row(
            from_values=["Under Review"],
            to_value="Accepted-Provisional",
            actor_kind="persona",
            actor_persona=team,
            actor_occasion="first vote",
            required_fields=[f["member_notes"], f["decision_summary"]],
            consequences=[seed["provisioning_automation"]],
            notes="First vote (DEC-023); provisioning on save (DEC-041).",
        ),
        # 7. Under Review -> Declined, Team, first vote.
        row(
            from_values=["Under Review"],
            to_value="Declined",
            actor_kind="persona",
            actor_persona=team,
            actor_occasion="first vote",
            required_fields=[f["decision_summary"], f["decline_reason"]],
            manual_follow_up="A decline email is optional and sent by hand.",
            notes="First vote (DEC-023, DEC-024, DEC-026).",
        ),
        # 8. Accepted-Provisional -> Provisional, System.
        row(
            from_values=["Accepted-Provisional"],
            to_value="Provisional",
            actor_kind="system",
            actor_occasion="the CRM",
            required_fields=[f["chapter_email"]],
            precondition="The chapter mailbox is confirmed to exist and is in "
            "the members group. If it is not confirmable the status stays and "
            "the roster sweep names the person.",
            manual_follow_up="A member arranges training and emails the "
            "candidate the one-time password by hand.",
            notes="System sets Provisional (DEC-041).",
        ),
        # 9. Provisional -> Approved, Team, second vote.
        row(
            from_values=["Provisional"],
            to_value="Approved",
            actor_kind="persona",
            actor_persona=team,
            actor_occasion="second vote",
            required_fields=[f["decision_summary"]],
            consequence_notes="Mentor login provisioning runs on the save: a "
            "CRM login is created in the Mentor Team and assigned to the "
            "profile and the Contact, and the CRM's welcome and set-password "
            "email goes to the chapter mailbox.",
            notes="Second vote (DEC-023, DEC-027, DEC-042).",
        ),
        # 10. Provisional -> Declined, Team, second vote.
        row(
            from_values=["Provisional"],
            to_value="Declined",
            actor_kind="persona",
            actor_persona=team,
            actor_occasion="second vote",
            required_fields=[f["decision_summary"], f["decline_reason"]],
            manual_follow_up="A decline email is optional and sent by hand.",
            notes="Second vote (DEC-023, DEC-024, DEC-026).",
        ),
        # 11. Approved -> Active, Team.
        row(
            from_values=["Approved"],
            to_value="Active",
            actor_kind="persona",
            actor_persona=team,
            required_fields=[
                f["chapter_email"],
                f["crm_login"],
                f["contact_assignment"],
            ],
            consequences=[process_identifier],
            manual_follow_up="A member emails the new mentor by hand.",
            notes="Active by hand (DEC-042); process boundary (DEC-021).",
        ),
        # 12. any pre-Active -> Dormant, Team.
        row(
            from_values=list(PRE_ACTIVE),
            to_value="Dormant",
            actor_kind="persona",
            actor_persona=team,
            precondition="Nothing required by the rulings.",
            notes="Unresponsive is Dormant (DEC-029); no exit (DEC-036).",
        ),
        # 13. any pre-Active -> Declined, by withdrawal, Team.
        row(
            from_values=list(PRE_ACTIVE),
            to_value="Declined",
            actor_kind="persona",
            actor_persona=team,
            actor_occasion="withdrawal",
            required_fields=[f["decline_reason"]],
            precondition="A note that the candidate withdrew, with the "
            "decline reason Candidate Withdrew.",
            manual_follow_up="A decline email is optional and sent by hand.",
            notes="Withdrawal is Declined with a note (DEC-029, DEC-045).",
        ),
    ]
