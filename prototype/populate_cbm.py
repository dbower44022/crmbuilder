"""
Task 2 -- Populate both databases with real CBM data extracted from documents.

Run after create_schema.py.
"""

import sqlite3
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_DB = os.path.join(SCRIPT_DIR, "crmbuilder_master.db")
CLIENT_DB = os.path.join(SCRIPT_DIR, "cbm_client.db")

# ID tracking dictionaries -- populated as records are inserted
domain_ids = {}
entity_ids = {}
field_ids = {}      # keyed as "EntityCode.fieldName"
persona_ids = {}
process_ids = {}
process_step_ids = {}
work_item_ids = {}  # keyed as "item_type:scope" e.g. "master_prd:" or "entity_prd:CON"
session_ids = {}


# =============================================================================
# 2a -- Master Database
# =============================================================================

def populate_master():
    conn = sqlite3.connect(MASTER_DB)
    c = conn.cursor()
    c.execute("""
        INSERT INTO Client (name, code, description, database_path, organization_overview, crm_platform)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "Cleveland Business Mentors",
        "CBM",
        "Nonprofit organization providing free, confidential mentoring and business education "
        "to entrepreneurs, small businesses, and nonprofits in Northeast Ohio.",
        "prototype/cbm_client.db",
        # organization_overview -- narrative from Master PRD Sections 1.1-1.3
        "Cleveland Business Mentors (CBM) is a nonprofit organization providing free, "
        "confidential, and impartial mentoring and practical business education to "
        "entrepreneurs, small businesses, and nonprofits exclusively in Northeast Ohio. "
        "CBM's services are always free to clients -- no fees, commissions, equity, or "
        "referral arrangements of any kind. Mentoring is delivered by volunteer "
        "professionals with experience in business and nonprofit management. The "
        "organization also delivers workshops, clinics, and curated referrals to trusted "
        "Northeast Ohio ecosystem partners.\n\n"
        "CBM operates with a lean structure. Volunteer mentors deliver all mentoring "
        "services. A small administrative team coordinates operations, manages "
        "relationships, and supports mentors and clients. Year 1 operating targets are "
        "25-30 volunteer mentors and 100-200 clients served, with a single "
        "technology-capable administrator managing the platform.\n\n"
        "The CRM enables CBM to track the full lifecycle of a mentoring engagement from "
        "intake through completion, match clients to mentors based on expertise, industry, "
        "and availability, monitor engagement health and intervene when relationships go "
        "inactive, report impact to funders and partners, manage the mentor population "
        "through recruitment, onboarding, and ongoing participation, and track partner "
        "relationships, referral activity, and joint programming.",
        None,  # crm_platform -- not yet selected
    ))
    conn.commit()
    conn.close()
    print("2a: Master database populated (1 Client record)")


# =============================================================================
# 2b -- Domains
# =============================================================================

def populate_domains(conn):
    c = conn.cursor()
    domains = [
        # (name, code, description, sort_order, parent_code, is_service, overview_text, reconciliation_text)
        ("Mentoring", "MN",
         "The complete lifecycle of a mentoring engagement -- from a client's initial "
         "request through mentor assignment, active mentoring, and formal closure. "
         "CBM's core program delivery function.",
         1, None, False,
         # domain_overview_text
         "The Mentoring domain covers the complete lifecycle of a mentoring engagement "
         "from intake through closure. Six personas participate: Client, Client "
         "Administrator, Client Assignment Coordinator, Mentor Administrator, Mentor, "
         "and Executive Member. Five processes (INTAKE, MATCH, ENGAGE, INACTIVE, CLOSE) "
         "handle the sequential lifecycle, with a sixth (SURVEY) as an enhancement. "
         "Three entities are central: Engagement (the relationship record), Session "
         "(individual meetings), and the shared Contact and Account entities. The domain "
         "generates the highest data volume and drives the core mission metrics.",
         # domain_reconciliation_text
         "The Mentoring domain reconciliation synthesizes five process documents into a "
         "unified domain view. Key reconciliation outcomes: Engagement entity carries 19 "
         "custom fields plus 5 roll-up analytics fields across all five processes. "
         "Contact entity contributes 8 matching fields to MN-MATCH. Session entity has "
         "8 custom fields plus 7 native fields. The inactivity monitoring system uses "
         "cadence-aware thresholds with configurable multipliers. Twenty decisions were "
         "made during reconciliation, resolving cross-process conflicts in status "
         "transitions, field ownership, and notification responsibilities."),

        ("Mentor Recruitment", "MR",
         "Full lifecycle of a volunteer mentor -- from initial awareness and application "
         "through onboarding, activation, ongoing status management, and eventual departure.",
         2, None, False,
         "The Mentor Recruitment domain manages the complete mentor lifecycle across five "
         "processes. Four personas participate: Mentor Administrator (primary), Mentor "
         "Recruiter, Partner Coordinator, and Mentor. The Contact entity serves as the "
         "mentor record with 34 mentor-specific custom fields controlled by dynamic "
         "logic. The Dues entity (custom, Base type) tracks annual billing obligations. "
         "Mentor Status has ten lifecycle values governing transitions across all five "
         "processes.",
         "The Mentor Recruitment domain reconciliation synthesizes five process documents. "
         "Key outcomes: 36 system requirements across all processes. The applicationDeclineReason "
         "enum was reconciled to 7 values. Email-based duplicate detection was confirmed as "
         "the sole matching mechanism. MR-MANAGE owns Active/Paused/Inactive transitions "
         "while MR-DEPART owns Resigned/Departed. Reactivation is permitted from both "
         "Resigned and Departed states. Thirty-two decisions were made. Thirteen open issues "
         "remain, primarily around enum value lists."),

        ("Client Recruiting", "CR",
         "All activities that generate awareness of CBM's mentoring program and attract "
         "prospective clients. Organized into four sub-domains: Partner Relationship "
         "Management, Outreach and Marketing, Workshops and Event Management, and Client "
         "Reactivation and Recovery.",
         3, None, False,
         "The Client Recruiting domain covers all client attraction and awareness activities. "
         "Seven personas participate across four sub-domains. The parent domain provides "
         "unified oversight, cross-sub-domain reporting, and shared audience strategy. "
         "Partner Relationship Management (CR-PARTNER) is Core tier; the remaining three "
         "sub-domains are Important tier. Key entities include Account (Partner type), "
         "Contact (Partner type), Partnership Agreement, Event, and Event Registration.",
         None),  # No reconciliation yet

        ("Fundraising", "FU",
         "Management of relationships with sponsors, donors, and funding institutions "
         "that provide operational funding for CBM.",
         4, None, False,
         None, None),  # No overview or reconciliation yet

        # CR sub-domains
        ("Partner Relationship Management", "CR-PARTNER",
         "Full lifecycle of referral partnerships -- identifying, qualifying, establishing "
         "agreements, onboarding, managing ongoing relationships, and measuring referral "
         "performance.",
         1, "CR", False, None, None),

        ("Outreach and Marketing", "CR-MARKETING",
         "All awareness-generating activities through communications channels: digital "
         "presence, content marketing, social media, email marketing, media/PR, direct "
         "grassroots outreach.",
         2, "CR", False, None, None),

        ("Workshops and Event Management", "CR-EVENTS",
         "Planning, delivery, and follow-up of all client-facing events including "
         "workshops, seminars, open houses, speaking engagements, webinars.",
         3, "CR", False, None, None),

        ("Client Reactivation and Recovery", "CR-REACTIVATE",
         "Re-engaging people who have previously interacted with CBM but are not "
         "currently active.",
         4, "CR", False, None, None),

        # Cross-Domain Services
        ("Notes", "NOTES",
         "Attach free-form, timestamped notes to any CRM record. General-purpose notes "
         "only -- structured session notes within Mentoring remain domain-specific.",
         10, None, True, None, None),
    ]

    for d in domains:
        name, code, desc, sort_order, parent_code, is_service, overview, reconciliation = d
        parent_id = domain_ids.get(parent_code) if parent_code else None
        c.execute("""
            INSERT INTO Domain (name, code, description, sort_order, parent_domain_id,
                                is_service, domain_overview_text, domain_reconciliation_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, code, desc, sort_order, parent_id, is_service, overview, reconciliation))
        domain_ids[code] = c.lastrowid

    conn.commit()
    print(f"2b: Domains inserted ({len(domain_ids)})")


# =============================================================================
# 2c -- Entities, Fields, FieldOptions, Relationships
# =============================================================================

def populate_entities(conn):
    c = conn.cursor()

    entities = [
        # (name, code, entity_type, is_native, singular, plural, description, primary_domain_code)
        ("Contact", "CON", "Person", True, "Contact", "Contacts",
         "Single repository for all individual people known to CBM. Spans all four "
         "domains with type-specific fields controlled by contactType discriminator.",
         None),  # cross-domain, no single owner
        ("Account", "ACT", "Company", True, "Account", "Accounts",
         "Single repository for all organizations known to CBM. Spans three domains "
         "with type-specific fields controlled by accountType discriminator.",
         None),  # cross-domain
        ("Engagement", "ENG", "Base", False, "Engagement", "Engagements",
         "Mentoring relationship linking a client organization to a volunteer mentor. "
         "Tracks full lifecycle from intake through closure.",
         "MN"),
        ("Session", "SES", "Event", False, "Session", "Sessions",
         "Individual mentoring meetings within an engagement. Uses Event entity type "
         "with native date/duration/status fields.",
         "MN"),
        ("Dues", "DUES", "Base", False, "Dues", "Dues",
         "One annual dues obligation for a single mentor. One record per mentor per "
         "billing year.",
         "MR"),
        ("Partnership Agreement", "PA", "Base", False, "Partnership Agreement",
         "Partnership Agreements",
         "Formal partnership agreement between CBM and a partner organization.",
         "CR"),
        ("Event", "EVT", "Event", False, "Event", "Events",
         "Client-facing events including workshops, seminars, open houses, webinars.",
         "CR"),
        ("Event Registration", "EVREG", "Base", False, "Event Registration",
         "Event Registrations",
         "Registration record linking a contact to an event.",
         "CR"),
        ("Contribution", "CTB", "Base", False, "Contribution", "Contributions",
         "Financial contribution record -- donation, sponsorship, grant, or pledge.",
         "FU"),
        ("Fundraising Campaign", "FC", "Base", False, "Fundraising Campaign",
         "Fundraising Campaigns",
         "Organized fundraising effort with goals and linked contributions.",
         "FU"),
        ("Note", "NOTE", "Base", False, "Note", "Notes",
         "Free-form timestamped note attached to any CRM record. Cross-domain service.",
         "NOTES"),
    ]

    for e in entities:
        name, code, etype, is_native, sing, plur, desc, dom_code = e
        dom_id = domain_ids.get(dom_code)
        c.execute("""
            INSERT INTO Entity (name, code, entity_type, is_native, singular_label,
                                plural_label, description, primary_domain_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, code, etype, is_native, sing, plur, desc, dom_id))
        entity_ids[code] = c.lastrowid

    conn.commit()
    print(f"2c: Entities inserted ({len(entity_ids)})")


def populate_fields(conn):
    """Insert all fields for Contact, Account, Engagement, Session, Dues."""
    c = conn.cursor()
    field_count = 0

    def add_field(entity_code, name, label, field_type, is_native=False,
                  is_required=False, default_value=None, read_only=False,
                  audited=False, category=None, description=None, sort_order=None):
        nonlocal field_count
        eid = entity_ids[entity_code]
        c.execute("""
            INSERT INTO Field (entity_id, name, label, field_type, is_native,
                               is_required, default_value, read_only, audited,
                               category, description, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (eid, name, label, field_type, is_native, is_required, default_value,
              read_only, audited, category, description, sort_order))
        fid = c.lastrowid
        field_ids[f"{entity_code}.{name}"] = fid
        field_count += 1
        return fid

    def add_options(field_key, options):
        """options: list of (value, label, style, is_default)"""
        fid = field_ids[field_key]
        for i, opt in enumerate(options):
            val, lbl = opt[0], opt[1]
            style = opt[2] if len(opt) > 2 else None
            is_def = opt[3] if len(opt) > 3 else False
            c.execute("""
                INSERT INTO FieldOption (field_id, value, label, style, sort_order, is_default)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (fid, val, lbl, style, i + 1, is_def))

    # ---- CONTACT: Native Fields (16) ----
    add_field("CON", "firstName", "First Name", "varchar", is_native=True, sort_order=1)
    add_field("CON", "lastName", "Last Name", "varchar", is_native=True, sort_order=2)
    add_field("CON", "middleName", "Middle Name", "varchar", is_native=True, sort_order=3)
    add_field("CON", "salutationName", "Salutation", "enum", is_native=True, sort_order=4)
    add_field("CON", "title", "Title", "varchar", is_native=True, sort_order=5)
    add_field("CON", "emailAddress", "Email", "email", is_native=True, sort_order=6)
    add_field("CON", "phoneNumber", "Phone", "phone", is_native=True, sort_order=7)
    add_field("CON", "addressStreet", "Street", "varchar", is_native=True, sort_order=8)
    add_field("CON", "addressCity", "City", "varchar", is_native=True, sort_order=9)
    add_field("CON", "addressState", "State", "varchar", is_native=True, sort_order=10)
    add_field("CON", "addressCountry", "Country", "varchar", is_native=True, sort_order=11)
    add_field("CON", "addressPostalCode", "Zip Code", "varchar", is_native=True, sort_order=12)
    add_field("CON", "description", "Description", "text", is_native=True, sort_order=13)
    add_field("CON", "createdAt", "Created At", "datetime", is_native=True, read_only=True, sort_order=14)
    add_field("CON", "modifiedAt", "Modified At", "datetime", is_native=True, read_only=True, sort_order=15)
    add_field("CON", "assignedUser", "Assigned User", "link", is_native=True, sort_order=16)

    # ---- CONTACT: Shared Custom Fields (6) ----
    add_field("CON", "contactType", "Contact Type", "multiEnum", is_required=True,
              category="shared", sort_order=20,
              description="Discriminator field. Determines type-specific field visibility.")
    add_options("CON.contactType", [
        ("Client", "Client"), ("Mentor", "Mentor"), ("Partner", "Partner"),
        ("Administrator", "Administrator"), ("Presenter", "Presenter"),
        ("Donor", "Donor"), ("Member", "Member"),
    ])
    add_field("CON", "preferredName", "Preferred Name", "varchar",
              category="shared", sort_order=21)
    add_field("CON", "linkedInProfile", "LinkedIn Profile", "url",
              category="shared", sort_order=22)
    add_field("CON", "howDidYouHearAboutCbm", "How Did You Hear About CBM", "enum",
              category="shared", sort_order=23)
    add_field("CON", "termsAndConditionsAccepted", "Terms and Conditions Accepted", "bool",
              category="shared", sort_order=24)
    add_field("CON", "termsAndConditionsAcceptanceDateTime",
              "Terms Acceptance Date/Time", "datetime",
              category="shared", sort_order=25)

    # ---- CONTACT: CBM Internal (1) ----
    add_field("CON", "boardPosition", "Board Position", "varchar",
              category="cbm_internal", sort_order=30)

    # ---- CONTACT: Mentor Lifecycle and Status (5) ----
    add_field("CON", "mentorStatus", "Mentor Status", "enum", is_required=True,
              audited=True, category="mentor_lifecycle", sort_order=40,
              description="Ten-value lifecycle from Prospect through Departed.")
    add_options("CON.mentorStatus", [
        ("Prospect", "Prospect"), ("Submitted", "Submitted"),
        ("In Review", "In Review"), ("Provisional", "Provisional"),
        ("Active", "Active", "success"), ("Paused", "Paused", "warning"),
        ("Inactive", "Inactive", "danger"), ("Resigned", "Resigned"),
        ("Departed", "Departed"), ("Declined", "Declined", "danger"),
    ])
    add_field("CON", "acceptingNewClients", "Accepting New Clients", "bool",
              is_required=True, category="mentor_lifecycle", sort_order=41)
    add_field("CON", "maximumClientCapacity", "Maximum Client Capacity", "int",
              is_required=True, category="mentor_lifecycle", sort_order=42)
    add_field("CON", "currentActiveClients", "Current Active Clients", "int",
              read_only=True, category="mentor_lifecycle", sort_order=43,
              description="System-calculated count of active engagements.")
    add_field("CON", "availableCapacity", "Available Capacity", "int",
              read_only=True, category="mentor_lifecycle", sort_order=44,
              description="System-calculated: maximumClientCapacity - currentActiveClients.")

    # ---- CONTACT: Mentor Contact and Identity (5) ----
    add_field("CON", "personalEmail", "Personal Email", "email",
              is_required=True, category="mentor_contact", sort_order=50)
    add_field("CON", "cbmEmailAddress", "CBM Email Address", "email",
              category="mentor_contact", sort_order=51)
    add_field("CON", "currentEmployer", "Current Employer", "varchar",
              category="mentor_contact", sort_order=52)
    add_field("CON", "currentlyEmployed", "Currently Employed", "bool",
              category="mentor_contact", sort_order=53)
    add_field("CON", "yearsOfBusinessExperience", "Years of Business Experience", "int",
              category="mentor_contact", sort_order=54)

    # ---- CONTACT: Mentor Profile and Matching (6) ----
    add_field("CON", "professionalBio", "Professional Bio", "wysiwyg",
              category="mentor_profile", sort_order=60)
    add_field("CON", "industrySectors", "Industry Sectors", "multiEnum",
              is_required=True, category="mentor_profile", sort_order=61,
              description="20 top-level NAICS sectors for mentor matching.")
    add_field("CON", "mentoringFocusAreas", "Mentoring Focus Areas", "multiEnum",
              is_required=True, category="mentor_profile", sort_order=62)
    add_field("CON", "skillsExpertiseTags", "Skills and Expertise Tags", "multiEnum",
              category="mentor_profile", sort_order=63)
    add_field("CON", "fluentLanguages", "Fluent Languages", "multiEnum",
              category="mentor_profile", sort_order=64)
    add_field("CON", "whyInterestedInMentoring", "Why Interested in Mentoring", "wysiwyg",
              category="mentor_profile", sort_order=65)

    # ---- CONTACT: Mentor Role Eligibility (3) ----
    add_field("CON", "isPrimaryMentor", "Is Primary Mentor", "bool",
              is_required=True, default_value="true", category="mentor_role", sort_order=70)
    add_field("CON", "isCoMentor", "Is Co-Mentor", "bool",
              is_required=True, category="mentor_role", sort_order=71)
    add_field("CON", "isSubjectMatterExpert", "Is Subject Matter Expert", "bool",
              is_required=True, category="mentor_role", sort_order=72)

    # ---- CONTACT: Mentor Onboarding and Compliance (7) ----
    add_field("CON", "ethicsAgreementAccepted", "Ethics Agreement Accepted", "bool",
              category="mentor_onboarding", sort_order=80)
    add_field("CON", "ethicsAgreementAcceptanceDateTime",
              "Ethics Agreement Acceptance Date/Time", "datetime",
              category="mentor_onboarding", sort_order=81)
    add_field("CON", "backgroundCheckCompleted", "Background Check Completed", "bool",
              category="mentor_onboarding", sort_order=82)
    add_field("CON", "backgroundCheckDate", "Background Check Date", "date",
              category="mentor_onboarding", sort_order=83)
    add_field("CON", "felonyConvictionDisclosure", "Felony Conviction Disclosure", "bool",
              category="mentor_onboarding", sort_order=84)
    add_field("CON", "trainingCompleted", "Training Completed", "bool",
              category="mentor_onboarding", sort_order=85)
    add_field("CON", "trainingCompletionDate", "Training Completion Date", "date",
              category="mentor_onboarding", sort_order=86)

    # ---- CONTACT: Mentor Dues (3) ----
    add_field("CON", "duesStatus", "Dues Status", "enum",
              category="mentor_dues", sort_order=90)
    add_options("CON.duesStatus", [
        ("Unpaid", "Unpaid", "danger"), ("Paid", "Paid", "success"),
        ("Waived", "Waived", "info"),
    ])
    add_field("CON", "duesPaymentDate", "Dues Payment Date", "date",
              category="mentor_dues", sort_order=91)
    add_field("CON", "duesRenewalDate", "Dues Renewal Date", "date",
              category="mentor_dues", sort_order=92)

    # ---- CONTACT: Mentor Application (1) ----
    add_field("CON", "applicationDeclineReason", "Application Decline Reason", "enum",
              category="mentor_application", sort_order=95)
    add_options("CON.applicationDeclineReason", [
        ("Insufficient Experience", "Insufficient Experience"),
        ("Incomplete Application", "Incomplete Application"),
        ("Failed Background Check", "Failed Background Check"),
        ("Conflict of Interest", "Conflict of Interest"),
        ("Unresponsive", "Unresponsive"),
        ("Candidate Withdrew", "Candidate Withdrew"),
        ("Other", "Other"),
    ])

    # ---- CONTACT: Mentor Analytics (3) ----
    add_field("CON", "totalLifetimeSessions", "Total Lifetime Sessions", "int",
              read_only=True, category="mentor_analytics", sort_order=100)
    add_field("CON", "totalMentoringHours", "Total Mentoring Hours", "float",
              read_only=True, category="mentor_analytics", sort_order=101)
    add_field("CON", "totalSessionsLast30Days", "Total Sessions Last 30 Days", "int",
              read_only=True, category="mentor_analytics", sort_order=102)

    # ---- CONTACT: Mentor Departure (2) ----
    add_field("CON", "departureReason", "Departure Reason", "enum",
              category="mentor_departure", sort_order=110)
    add_options("CON.departureReason", [
        ("Relocated", "Relocated"), ("Career Change", "Career Change"),
        ("Time Constraints", "Time Constraints"), ("Personal", "Personal"),
        ("Other", "Other"),
    ])
    add_field("CON", "departureDate", "Departure Date", "date",
              category="mentor_departure", sort_order=111)

    # =========================================================================
    # ACCOUNT fields
    # =========================================================================

    # Native (19)
    add_field("ACT", "name", "Name", "varchar", is_native=True, sort_order=1)
    add_field("ACT", "emailAddress", "Email", "email", is_native=True, sort_order=2)
    add_field("ACT", "phoneNumber", "Phone", "phone", is_native=True, sort_order=3)
    add_field("ACT", "website", "Website", "url", is_native=True, sort_order=4)
    add_field("ACT", "billingAddressStreet", "Billing Street", "varchar", is_native=True, sort_order=5)
    add_field("ACT", "billingAddressCity", "Billing City", "varchar", is_native=True, sort_order=6)
    add_field("ACT", "billingAddressState", "Billing State", "varchar", is_native=True, sort_order=7)
    add_field("ACT", "billingAddressCountry", "Billing Country", "varchar", is_native=True, sort_order=8)
    add_field("ACT", "billingAddressPostalCode", "Billing Postal Code", "varchar", is_native=True, sort_order=9)
    add_field("ACT", "shippingAddressStreet", "Shipping Street", "varchar", is_native=True, sort_order=10)
    add_field("ACT", "shippingAddressCity", "Shipping City", "varchar", is_native=True, sort_order=11)
    add_field("ACT", "shippingAddressState", "Shipping State", "varchar", is_native=True, sort_order=12)
    add_field("ACT", "shippingAddressCountry", "Shipping Country", "varchar", is_native=True, sort_order=13)
    add_field("ACT", "shippingAddressPostalCode", "Shipping Postal Code", "varchar", is_native=True, sort_order=14)
    add_field("ACT", "sicCode", "SIC Code", "varchar", is_native=True, sort_order=15)
    add_field("ACT", "description", "Description", "text", is_native=True, sort_order=16)
    add_field("ACT", "createdAt", "Created At", "datetime", is_native=True, read_only=True, sort_order=17)
    add_field("ACT", "modifiedAt", "Modified At", "datetime", is_native=True, read_only=True, sort_order=18)
    add_field("ACT", "assignedUser", "Assigned User", "link", is_native=True, sort_order=19)

    # Shared custom (3)
    add_field("ACT", "accountType", "Account Type", "multiEnum", is_required=True,
              category="shared", sort_order=20)
    add_options("ACT.accountType", [
        ("Client", "Client"), ("Partner", "Partner"), ("Donor/Sponsor", "Donor/Sponsor"),
    ])
    add_field("ACT", "parentOrganization", "Parent Organization", "link",
              category="shared", sort_order=21,
              description="Self-referencing link to parent Account for org hierarchies.")
    add_field("ACT", "linkedInProfile", "LinkedIn Profile", "url",
              category="shared", sort_order=22)

    # Client-specific (5)
    add_field("ACT", "organizationType", "Organization Type", "enum",
              category="client", sort_order=30)
    add_options("ACT.organizationType", [
        ("For-Profit", "For-Profit"), ("Non-Profit", "Non-Profit"),
    ])
    add_field("ACT", "businessStage", "Business Stage", "enum",
              is_required=True, category="client", sort_order=31)
    add_options("ACT.businessStage", [
        ("Pre-Startup", "Pre-Startup"), ("Startup", "Startup"),
        ("Early Stage", "Early Stage"), ("Growth Stage", "Growth Stage"),
        ("Established", "Established"),
    ])
    add_field("ACT", "industrySector", "Industry Sector", "enum",
              category="client", sort_order=32,
              description="Primary industry sector based on NAICS.")
    add_field("ACT", "industrySubsector", "Industry Subsector", "enum",
              category="client", sort_order=33,
              description="Filtered dependent on industrySector.")
    add_field("ACT", "clientNotes", "Client Notes", "wysiwyg",
              category="client", sort_order=34)

    # Partner-specific (9)
    add_field("ACT", "partnerOrganizationType", "Partner Organization Type", "enum",
              is_required=True, category="partner", sort_order=40)
    add_options("ACT.partnerOrganizationType", [
        ("Chamber of Commerce", "Chamber of Commerce"), ("SBDC", "SBDC"),
        ("Economic Development Agency", "Economic Development Agency"),
        ("University / Academic Institution", "University / Academic Institution"),
        ("Bank / Financial Institution", "Bank / Financial Institution"),
        ("Nonprofit / Community Organization", "Nonprofit / Community Organization"),
        ("Government Agency", "Government Agency"),
        ("Corporate Sponsor", "Corporate Sponsor"), ("Other", "Other"),
    ])
    add_field("ACT", "partnerType", "Partner Type", "multiEnum",
              is_required=True, category="partner", sort_order=41)
    add_options("ACT.partnerType", [
        ("Referral Partner", "Referral Partner"),
        ("Co-Delivery Partner", "Co-Delivery Partner"),
        ("Funding / Sponsorship Partner", "Funding / Sponsorship Partner"),
        ("Resource Partner", "Resource Partner"),
    ])
    add_field("ACT", "partnerStatus", "Partner Status", "enum",
              is_required=True, audited=True, category="partner", sort_order=42)
    add_options("ACT.partnerStatus", [
        ("Prospect", "Prospect"), ("Active", "Active", "success"),
        ("Lapsed", "Lapsed", "warning"), ("Inactive", "Inactive", "danger"),
    ])
    add_field("ACT", "partnershipStartDate", "Partnership Start Date", "date",
              category="partner", sort_order=43)
    add_field("ACT", "assignedLiaison", "Assigned Liaison", "link",
              category="partner", sort_order=44,
              description="CBM member responsible for this partner relationship.")
    add_field("ACT", "publicAnnouncementAllowed", "Public Announcement Allowed", "bool",
              default_value="false", category="partner", sort_order=45)
    add_field("ACT", "geographicServiceArea", "Geographic Service Area", "text",
              category="partner", sort_order=46)
    add_field("ACT", "targetPopulation", "Target Population", "text",
              category="partner", sort_order=47)
    add_field("ACT", "partnerNotes", "Partner Notes", "wysiwyg",
              category="partner", sort_order=48)

    # Donor/Sponsor-specific (4)
    add_field("ACT", "funderType", "Funder Type", "enum",
              category="donor", sort_order=50)
    add_options("ACT.funderType", [
        ("Corporation", "Corporation"), ("Foundation", "Foundation"),
        ("Government Agency", "Government Agency"),
        ("Community Foundation", "Community Foundation"),
        ("Individual (Organization)", "Individual (Organization)"),
        ("Other", "Other"),
    ])
    add_field("ACT", "funderStatus", "Funder Status", "enum",
              audited=True, category="donor", sort_order=51)
    add_options("ACT.funderStatus", [
        ("Prospect", "Prospect"), ("Contacted", "Contacted"),
        ("In Discussion", "In Discussion"), ("Committed", "Committed"),
        ("Active", "Active", "success"), ("Lapsed", "Lapsed", "warning"),
        ("Closed", "Closed"),
    ])
    add_field("ACT", "funderLifetimeGiving", "Lifetime Giving", "currency",
              read_only=True, category="donor", sort_order=52,
              description="System-calculated sum of linked Contribution records.")
    add_field("ACT", "funderNotes", "Funder Notes", "wysiwyg",
              category="donor", sort_order=53)

    # =========================================================================
    # ENGAGEMENT fields
    # =========================================================================

    # Native (2)
    add_field("ENG", "name", "Name", "varchar", is_native=True, read_only=True, sort_order=1,
              description="Auto-generated: {Client Name}-{Mentor Name}-{Start Year}")
    add_field("ENG", "description", "Description", "text", is_native=True, sort_order=2)

    # Lifecycle and Status (3)
    add_field("ENG", "engagementStatus", "Engagement Status", "enum",
              is_required=True, default_value="Submitted", audited=True,
              category="lifecycle", sort_order=10)
    add_options("ENG.engagementStatus", [
        ("Submitted", "Submitted"), ("Declined", "Declined", "danger"),
        ("Pending Acceptance", "Pending Acceptance", "warning"),
        ("Assigned", "Assigned", "info"),
        ("Active", "Active", "success"), ("On-Hold", "On-Hold", "warning"),
        ("Dormant", "Dormant", "warning"), ("Inactive", "Inactive", "danger"),
        ("Abandoned", "Abandoned", "danger"), ("Completed", "Completed", "primary"),
    ])
    add_field("ENG", "meetingCadence", "Meeting Cadence", "enum",
              is_required=True, category="lifecycle", sort_order=11)
    add_options("ENG.meetingCadence", [
        ("Weekly", "Weekly"), ("Bi-Weekly", "Bi-Weekly"),
        ("Monthly", "Monthly"), ("As Needed", "As Needed"),
    ])
    add_field("ENG", "holdEndDate", "Hold End Date", "date",
              category="lifecycle", sort_order=12)

    # Mentoring Context (2)
    add_field("ENG", "mentoringFocusAreas", "Mentoring Focus Areas", "multiEnum",
              category="context", sort_order=20)
    add_field("ENG", "mentoringNeedsDescription", "Mentoring Needs Description", "wysiwyg",
              is_required=True, category="context", sort_order=21)

    # Notes (1)
    add_field("ENG", "engagementNotes", "Engagement Notes", "wysiwyg",
              category="notes", sort_order=30)

    # Session Roll-Up Analytics (5)
    add_field("ENG", "totalSessions", "Total Sessions", "int",
              read_only=True, category="analytics", sort_order=40)
    add_field("ENG", "totalSessionsLast30Days", "Sessions Last 30 Days", "int",
              read_only=True, category="analytics", sort_order=41)
    add_field("ENG", "lastSessionDate", "Last Session Date", "date",
              read_only=True, category="analytics", sort_order=42)
    add_field("ENG", "totalSessionHours", "Total Session Hours", "float",
              read_only=True, category="analytics", sort_order=43)
    add_field("ENG", "nextSessionDateTime", "Next Session Date/Time", "datetime",
              category="analytics", sort_order=44)

    # Closure (2)
    add_field("ENG", "closeDate", "Close Date", "date",
              category="closure", sort_order=50)
    add_field("ENG", "closeReason", "Close Reason", "enum",
              category="closure", sort_order=51)
    add_options("ENG.closeReason", [
        ("Goals Achieved", "Goals Achieved"), ("Client Withdrew", "Client Withdrew"),
        ("Inactive / No Response", "Inactive / No Response"), ("Other", "Other"),
    ])

    # Outcomes (6)
    add_field("ENG", "newBusinessStarted", "New Business Started", "bool",
              category="outcomes", sort_order=60)
    add_field("ENG", "newLocationOpened", "New Location Opened", "bool",
              category="outcomes", sort_order=61)
    add_field("ENG", "significantRevenueIncrease", "Significant Revenue Increase", "bool",
              category="outcomes", sort_order=62)
    add_field("ENG", "revenueIncreasePercentage", "Revenue Increase %", "float",
              category="outcomes", sort_order=63)
    add_field("ENG", "significantEmploymentIncrease", "Significant Employment Increase", "bool",
              category="outcomes", sort_order=64)
    add_field("ENG", "employmentIncreasePercentage", "Employment Increase %", "float",
              category="outcomes", sort_order=65)

    # =========================================================================
    # SESSION fields
    # =========================================================================

    # Native (10)
    add_field("SES", "name", "Name", "varchar", is_native=True, read_only=True, sort_order=1,
              description="Auto-generated: {Engagement Name} -- {Session Date}")
    add_field("SES", "dateStart", "Session Date/Time", "datetime", is_native=True, sort_order=2)
    add_field("SES", "dateEnd", "End Time", "datetime", is_native=True, read_only=True, sort_order=3)
    add_field("SES", "duration", "Duration (minutes)", "int", is_native=True, sort_order=4)
    add_field("SES", "status", "Status", "enum", is_native=True,
              default_value="Scheduled", audited=True, sort_order=5)
    add_options("SES.status", [
        ("Scheduled", "Scheduled"), ("Completed", "Completed", "success"),
        ("Canceled by Client", "Canceled by Client"),
        ("Canceled by Mentor", "Canceled by Mentor"),
        ("Missed by Client", "Missed by Client", "danger"),
        ("Rescheduled by Client", "Rescheduled by Client"),
        ("Rescheduled by Mentor", "Rescheduled by Mentor"),
    ])
    add_field("SES", "parent", "Engagement", "link", is_native=True, sort_order=6)
    add_field("SES", "description", "Description", "text", is_native=True, sort_order=7)
    add_field("SES", "createdAt", "Created At", "datetime", is_native=True, read_only=True, sort_order=8)
    add_field("SES", "modifiedAt", "Modified At", "datetime", is_native=True, read_only=True, sort_order=9)
    add_field("SES", "assignedUser", "Assigned User", "link", is_native=True, sort_order=10)

    # Session Detail (4)
    add_field("SES", "sessionType", "Session Type", "enum", category="detail", sort_order=20)
    add_options("SES.sessionType", [
        ("In-Person", "In-Person"), ("Video Call", "Video Call"),
        ("Phone Call", "Phone Call"),
    ])
    add_field("SES", "meetingLocationType", "Meeting Location Type", "enum",
              category="detail", sort_order=21)
    add_options("SES.meetingLocationType", [
        ("Organization Office", "Organization Office"),
        ("Client's Place of Business", "Client's Place of Business"),
        ("Other", "Other"),
    ])
    add_field("SES", "locationDetails", "Location Details", "varchar",
              category="detail", sort_order=22)
    add_field("SES", "topicsCovered", "Topics Covered", "multiEnum",
              category="detail", sort_order=23)

    # Notes and Follow-Up (3)
    add_field("SES", "sessionNotes", "Session Notes", "wysiwyg",
              category="notes", sort_order=30)
    add_field("SES", "nextSteps", "Next Steps", "wysiwyg",
              category="notes", sort_order=31)
    add_field("SES", "nextSessionDateTime", "Next Session Date/Time", "datetime",
              category="notes", sort_order=32)

    # Rescheduling (1)
    add_field("SES", "rescheduledFromSession", "Rescheduled From", "link",
              category="rescheduling", sort_order=40,
              description="Self-referential link to predecessor Session.")

    # =========================================================================
    # DUES fields
    # =========================================================================

    # Native (4)
    add_field("DUES", "name", "Name", "varchar", is_native=True, read_only=True, sort_order=1,
              description="Auto-generated: {Mentor Name} -- {Billing Year}")
    add_field("DUES", "createdAt", "Created At", "datetime", is_native=True, read_only=True, sort_order=2)
    add_field("DUES", "modifiedAt", "Modified At", "datetime", is_native=True, read_only=True, sort_order=3)
    add_field("DUES", "assignedUser", "Assigned User", "link", is_native=True, sort_order=4)

    # Billing (3)
    add_field("DUES", "billingYear", "Billing Year", "int",
              is_required=True, category="billing", sort_order=10)
    add_field("DUES", "amount", "Amount", "currency",
              is_required=True, category="billing", sort_order=11)
    add_field("DUES", "dueDate", "Due Date", "date",
              is_required=True, category="billing", sort_order=12)

    # Payment (3)
    add_field("DUES", "paymentStatus", "Payment Status", "enum",
              is_required=True, default_value="Unpaid", category="payment", sort_order=20)
    add_options("DUES.paymentStatus", [
        ("Unpaid", "Unpaid", "danger", True), ("Paid", "Paid", "success"),
        ("Waived", "Waived", "info"),
    ])
    add_field("DUES", "paymentDate", "Payment Date", "date",
              category="payment", sort_order=21)
    add_field("DUES", "paymentMethod", "Payment Method", "enum",
              category="payment", sort_order=22)
    add_options("DUES.paymentMethod", [
        ("Online Payment", "Online Payment"), ("Check", "Check"),
    ])

    # Notes (1)
    add_field("DUES", "notes", "Notes", "text", category="notes", sort_order=30)

    conn.commit()
    print(f"2c: Fields inserted ({field_count})")

    # Count field options
    opt_count = c.execute("SELECT COUNT(*) FROM FieldOption").fetchone()[0]
    print(f"2c: FieldOptions inserted ({opt_count})")


def populate_relationships(conn):
    c = conn.cursor()

    rels = [
        # (name, desc, entity_code, foreign_code, link_type, link, link_foreign,
        #  label, label_foreign, relation_name)
        ("contactToAccount", "Native Contact-Account manyToMany",
         "CON", "ACT", "manyToMany", "accounts", "contacts",
         "Accounts", "Contacts", "contactAccount"),
        ("accountToEngagement", "Client Organization owns Engagements (MN-INTAKE)",
         "ACT", "ENG", "oneToMany", "engagements", "clientOrganization",
         "Engagements", "Client Organization", None),
        ("mentorToEngagement", "Assigned Mentor on Engagement (MN-MATCH-DAT-019)",
         "CON", "ENG", "oneToMany", "mentorEngagements", "assignedMentor",
         "Mentor Engagements", "Assigned Mentor", None),
        ("primaryContactToEngagement",
         "Primary Engagement Contact (MN-INTAKE-DAT-020)",
         "CON", "ENG", "oneToMany", "primaryEngagements", "primaryEngagementContact",
         "Primary Engagements", "Primary Engagement Contact", None),
        ("engagementContacts", "Engagement Contacts manyToMany (MN-MATCH-DAT-021)",
         "CON", "ENG", "manyToMany", "engagementsAsContact", "engagementContacts",
         "Engagement Participations", "Engagement Contacts", "contactEngagement"),
        ("additionalMentors", "Additional Mentors manyToMany (MN-ENGAGE-DAT-015)",
         "CON", "ENG", "manyToMany", "additionalMentorEngagements", "additionalMentors",
         "Additional Mentor Engagements", "Additional Mentors", "engagementAdditionalMentor"),
        ("engagementToSession", "Engagement owns Sessions (MN-ENGAGE)",
         "ENG", "SES", "oneToMany", "sessions", "engagement",
         "Sessions", "Engagement", None),
        ("mentorAttendees", "Session Mentor Attendees (MN-ENGAGE-DAT-034)",
         "CON", "SES", "manyToMany", "sessionsAsMentor", "mentorAttendees",
         "Sessions as Mentor", "Mentor Attendees", "sessionMentorAttendee"),
        ("clientAttendees", "Session Client Attendees (MN-ENGAGE-DAT-035)",
         "CON", "SES", "manyToMany", "sessionsAsClient", "clientAttendees",
         "Sessions as Client", "Client Attendees", "sessionClientAttendee"),
        ("mentorToDues", "Mentor owns Dues records (MR-MANAGE-DAT-028)",
         "CON", "DUES", "oneToMany", "dues", "mentorContact",
         "Dues", "Mentor", None),
        ("rescheduledFromSession", "Session self-referential rescheduling (SES-DEC-007)",
         "SES", "SES", "manyToOne", "rescheduledSessions", "rescheduledFromSession",
         "Rescheduled Sessions", "Rescheduled From", None),
        ("accountToPartnershipAgreement",
         "Partner Account owns Partnership Agreements (CR-PARTNER-REQ-006)",
         "ACT", "PA", "oneToMany", "partnershipAgreements", "partnerOrganization",
         "Partnership Agreements", "Partner Organization", None),
        ("accountToContribution",
         "Donor/Sponsor Account owns Contributions (FU-RECORD)",
         "ACT", "CTB", "oneToMany", "contributions", "donorOrganization",
         "Contributions", "Donor Organization", None),
    ]

    for r in rels:
        name, desc, ecode, fcode, ltype, link, link_f, lbl, lbl_f, rel_name = r
        c.execute("""
            INSERT INTO Relationship (name, description, entity_id, entity_foreign_id,
                                      link_type, link, link_foreign, label, label_foreign,
                                      relation_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, desc, entity_ids[ecode], entity_ids[fcode], ltype, link, link_f,
              lbl, lbl_f, rel_name))

    conn.commit()
    rel_count = c.execute("SELECT COUNT(*) FROM Relationship").fetchone()[0]
    print(f"2c: Relationships inserted ({rel_count})")


# =============================================================================
# 2d -- Personas
# =============================================================================

def populate_personas(conn):
    c = conn.cursor()

    personas = [
        # (name, code, description, entity_code, field_key, field_value)
        ("System Administrator", "MST-PER-001",
         "Configure and maintain the CRM platform. Full access to all system settings.",
         None, None, None),
        ("Executive Member", "MST-PER-002",
         "Review organizational dashboards and analytics. Full read access for strategic oversight.",
         None, None, None),
        ("Client Administrator", "MST-PER-003",
         "Review and process client applications. Maintain client records. Track client lifecycle.",
         None, None, None),
        ("Client Assignment Coordinator", "MST-PER-004",
         "Match approved clients with appropriate mentors based on expertise, availability, capacity.",
         None, None, None),
        ("Mentor Administrator", "MST-PER-005",
         "Review mentor applications, manage onboarding, monitor active mentors, handle departures.",
         None, None, None),
        ("Mentor Recruiter", "MST-PER-006",
         "Develop and execute outreach campaigns targeting prospective mentors.",
         None, None, None),
        ("Client Recruiter", "MST-PER-007",
         "Develop and execute outreach campaigns targeting prospective client businesses.",
         None, None, None),
        ("Partner Coordinator", "MST-PER-008",
         "Manage partner organization lifecycle from prospect through active.",
         None, None, None),
        ("Content and Event Administrator", "MST-PER-009",
         "Create and manage events, workshops. Handle registration and attendance tracking.",
         None, None, None),
        ("Donor / Sponsor Coordinator", "MST-PER-010",
         "Manage donor/sponsor relationships and fundraising campaigns.",
         None, None, None),
        ("Mentor", "MST-PER-011",
         "Volunteer professional who mentors clients. Manages profile, sessions, engagements.",
         "CON", "CON.contactType", "Mentor"),
        ("Member", "MST-PER-012",
         "Participate in CBM events and organizational activities. Maintain profile.",
         "CON", "CON.contactType", "Member"),
        ("Client", "MST-PER-013",
         "Submit mentoring requests, participate in intake, engage with assigned mentor.",
         "CON", "CON.contactType", "Client"),
    ]

    for p in personas:
        name, code, desc, ent_code, field_key, field_value = p
        ent_id = entity_ids.get(ent_code) if ent_code else None
        fld_id = field_ids.get(field_key) if field_key else None
        c.execute("""
            INSERT INTO Persona (name, code, description, persona_entity_id,
                                 persona_field_id, persona_field_value)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, code, desc, ent_id, fld_id, field_value))
        persona_ids[code] = c.lastrowid

    conn.commit()
    print(f"2d: Personas inserted ({len(persona_ids)})")


# =============================================================================
# 2c (continued) -- Business Objects
# =============================================================================

def populate_business_objects(conn):
    c = conn.cursor()

    # From Entity Inventory: 25 business entity concepts mapped to CRM entities
    bos = [
        # (name, description, status, resolution, entity_code, resolution_detail)
        ("Client Contact", "Individual client person", "classified", "entity", "CON",
         "Maps to Contact with contactType=Client"),
        ("Mentor Contact", "Individual mentor person", "classified", "entity", "CON",
         "Maps to Contact with contactType=Mentor"),
        ("Partner Contact", "Individual partner contact", "classified", "entity", "CON",
         "Maps to Contact with contactType=Partner"),
        ("Administrator", "CBM staff member", "classified", "entity", "CON",
         "Maps to Contact with contactType=Administrator"),
        ("Presenter", "Event presenter", "classified", "entity", "CON",
         "Maps to Contact with contactType=Presenter"),
        ("Donor/Sponsor Contact", "Individual donor/sponsor", "classified", "entity", "CON",
         "Maps to Contact with contactType=Donor"),
        ("Member", "CBM organizational member", "classified", "entity", "CON",
         "Maps to Contact with contactType=Member"),
        ("Client Organization", "Client business entity", "classified", "entity", "ACT",
         "Maps to Account with accountType=Client"),
        ("Partner Organization", "Partner org entity", "classified", "entity", "ACT",
         "Maps to Account with accountType=Partner"),
        ("Donor/Sponsor Organization", "Funding org entity", "classified", "entity", "ACT",
         "Maps to Account with accountType=Donor/Sponsor"),
        ("Engagement", "Mentoring relationship record", "classified", "entity", "ENG",
         "Custom Base entity owned by MN domain"),
        ("Session", "Individual mentoring meeting", "classified", "entity", "SES",
         "Custom Event entity owned by MN domain"),
        ("Dues", "Annual mentor dues obligation", "classified", "entity", "DUES",
         "Custom Base entity owned by MR domain"),
        ("Partnership Agreement", "Formal partnership record", "classified", "entity", "PA",
         "Custom Base entity owned by CR domain"),
        ("Event/Workshop", "Client-facing event", "classified", "entity", "EVT",
         "Custom Event entity owned by CR domain"),
        ("Event Registration", "Event registration record", "classified", "entity", "EVREG",
         "Custom Base entity owned by CR domain"),
        ("Donation", "Individual donation", "classified", "entity", "CTB",
         "Maps to Contribution with contributionType=Donation"),
        ("Sponsorship", "Sponsorship commitment", "classified", "entity", "CTB",
         "Maps to Contribution with contributionType=Sponsorship"),
        ("Grant", "Grant award", "classified", "entity", "CTB",
         "Maps to Contribution with contributionType=Grant"),
        ("Pledge", "Pledge commitment", "classified", "entity", "CTB",
         "Maps to Contribution with contributionType=Pledge"),
        ("Fundraising Campaign", "Organized fundraising effort", "classified", "entity", "FC",
         "Custom Base entity owned by FU domain"),
        ("Note", "Free-form timestamped note", "classified", "entity", "NOTE",
         "Cross-domain service entity. TBD platform implementation."),
    ]

    for bo in bos:
        name, desc, status, resolution, ent_code, res_detail = bo
        ent_id = entity_ids.get(ent_code)
        c.execute("""
            INSERT INTO BusinessObject (name, description, status, resolution,
                                        resolved_to_entity_id, resolution_detail)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, desc, status, resolution, ent_id, res_detail))

    conn.commit()
    bo_count = c.execute("SELECT COUNT(*) FROM BusinessObject").fetchone()[0]
    print(f"2c: BusinessObjects inserted ({bo_count})")


# =============================================================================
# 2e -- Processes, Steps, Requirements
# =============================================================================

def populate_processes(conn):
    c = conn.cursor()

    processes = [
        # MN domain
        ("Client Intake", "MN-INTAKE", "MN", 1,
         "The process by which a prospective client requests mentoring services and is reviewed and approved.",
         "Client submits Phase 1 Mentoring Request form via public website",
         "Client approved and Engagement status set to Submitted, ready for MN-MATCH"),
        ("Mentor Matching", "MN-MATCH", "MN", 2,
         "The process by which an approved client is matched with the most appropriate available mentor.",
         "New approved intake from MN-INTAKE or reassignment from MR-DEPART",
         "Mentor accepts assignment, Engagement status set to Assigned"),
        ("Engagement Management", "MN-ENGAGE", "MN", 3,
         "Ongoing management of an active mentoring relationship between a mentor and client.",
         "Engagement status transitions to Assigned (from MN-MATCH)",
         "Engagement reaches closure criteria or transitions via MN-INACTIVE/MN-CLOSE"),
        ("Activity Monitoring", "MN-INACTIVE", "MN", 4,
         "Continuous monitoring of active engagement activity levels to detect relationships that have gone quiet.",
         "Daily automated scan of all Active and On-Hold engagements",
         "Engagement transitions to Abandoned with auto-populated Close Date and Close Reason"),
        ("Engagement Closure", "MN-CLOSE", "MN", 5,
         "Formally closing a completed or terminated mentoring engagement and recording outcomes.",
         "Mentor or Client Administrator changes Engagement status to Completed",
         "Close Date populated, outcome fields reviewed, survey sent, thank-you email generated"),
        ("Client Satisfaction Tracking", "MN-SURVEY", "MN", 6,
         "Collecting and recording client feedback throughout and at the conclusion of an engagement.",
         "Defined survey intervals or engagement closure event",
         "Survey responses recorded and linked to client and engagement records"),

        # MR domain
        ("Mentor Recruitment", "MR-RECRUIT", "MR", 1,
         "Raising awareness of CBM's volunteer mentoring program and attracting qualified applicants.",
         "Ongoing recruitment activity by Mentor Recruiter",
         "Prospect submits application, transitioning to MR-APPLY"),
        ("Mentor Application", "MR-APPLY", "MR", 2,
         "Prospective mentor submits application and CBM reviews and makes admission decision.",
         "Mentor submits application via website or prospect record is updated",
         "Mentor Administrator approves (status=Provisional) or declines with reason"),
        ("Mentor Onboarding", "MR-ONBOARD", "MR", 3,
         "Activating a provisionally approved mentor through training, co-mentoring, and final activation.",
         "Mentor status transitions to Provisional (from MR-APPLY)",
         "Mentor status transitions to Active with capacity and role eligibility set"),
        ("Mentor Management", "MR-MANAGE", "MR", 4,
         "Ongoing management of active mentor profiles, capacity, and participation.",
         "Mentor status is Active, Paused, or Inactive",
         "Ongoing -- no terminal state within this process"),
        ("Mentor Departure and Reactivation", "MR-DEPART", "MR", 5,
         "Managing a mentor's transition to inactive/departed status and supporting reactivation.",
         "Mentor Administrator initiates departure or mentor requests reactivation",
         "Mentor status set to Resigned or Departed with reason, or reactivated to Active/Provisional"),

        # FU domain
        ("Donor and Sponsor Prospecting", "FU-PROSPECT", "FU", 1,
         "Identifying and pursuing prospective donors, sponsors, and funding institutions.",
         "Donor/Sponsor Coordinator identifies a prospective funder",
         "Prospect status transitions to Committed or Closed"),
        ("Contribution Recording", "FU-RECORD", "FU", 2,
         "Recording and maintaining accurate records of all incoming funding.",
         "Donation, sponsorship, grant, or pledge is received or committed",
         "Contribution record created with full traceability"),
        ("Donor and Sponsor Stewardship", "FU-STEWARD", "FU", 3,
         "Maintaining active relationships with committed donors and sponsors.",
         "Funder status is Active",
         "Ongoing relationship management with tracked communications"),
        ("Fundraising Reporting", "FU-REPORT", "FU", 4,
         "Producing accurate fundraising analytics for internal and external reporting.",
         "Reporting period end or ad-hoc request",
         "Analytics reports generated"),
    ]

    for p in processes:
        name, code, dom_code, sort_order, desc, triggers, completion = p
        c.execute("""
            INSERT INTO Process (domain_id, name, code, description, triggers,
                                 completion_criteria, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (domain_ids[dom_code], name, code, desc, triggers, completion, sort_order))
        process_ids[code] = c.lastrowid

    conn.commit()
    print(f"2e: Processes inserted ({len(process_ids)})")


def populate_process_steps(conn):
    c = conn.cursor()
    step_count = 0

    def add_step(proc_code, name, desc, step_type, persona_code, sort_order):
        nonlocal step_count
        pid = process_ids[proc_code]
        per_id = persona_ids.get(persona_code)
        c.execute("""
            INSERT INTO ProcessStep (process_id, name, description, step_type,
                                     performer_persona_id, sort_order)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (pid, name, desc, step_type, per_id, sort_order))
        step_count += 1
        return c.lastrowid

    # MN-INTAKE steps
    add_step("MN-INTAKE", "Submit Mentoring Request",
             "Client submits Phase 1 form with org info, contact info, mentoring needs. "
             "Optionally selects preferred mentor.",
             "action", "MST-PER-013", 1)
    add_step("MN-INTAKE", "Create Linked Records",
             "System creates Account (Client), Contact (Client), Engagement (Submitted).",
             "system", None, 2)
    add_step("MN-INTAKE", "Notify Client Administrator",
             "Email notification sent to Client Administrator using New Client Submission template.",
             "notification", None, 3)
    add_step("MN-INTAKE", "Review Application",
             "Client Administrator reviews via New Client Submissions filter view.",
             "action", "MST-PER-003", 4)
    add_step("MN-INTAKE", "Eligibility Decision",
             "If eligible: proceed to MN-MATCH. If not: set Engagement to Declined with reason.",
             "decision", "MST-PER-003", 5)
    add_step("MN-INTAKE", "Notify Applicant of Decline",
             "Applicant notified directly if application is declined.",
             "notification", None, 6)

    # MN-MATCH steps
    add_step("MN-MATCH", "Review Client Records",
             "Coordinator reviews Client Organization and Engagement records.",
             "action", "MST-PER-004", 1)
    add_step("MN-MATCH", "Check Requested Mentor",
             "If Requested Mentor preference exists, review fit and availability.",
             "action", "MST-PER-004", 2)
    add_step("MN-MATCH", "Search Mentor Roster",
             "Search active mentor roster filtered by expertise, industry, availability, capacity.",
             "action", "MST-PER-004", 3)
    add_step("MN-MATCH", "Nominate Primary Mentor",
             "Select candidate, system transitions Engagement to Pending Acceptance, sends notification.",
             "action", "MST-PER-004", 4)
    add_step("MN-MATCH", "Mentor Acceptance Decision",
             "Mentor accepts (status to Assigned) or declines (reverts to Submitted).",
             "decision", "MST-PER-011", 5)
    add_step("MN-MATCH", "Mentor Introduction",
             "Mentor personally introduces themselves to client via email.",
             "action", "MST-PER-011", 6)

    # MN-ENGAGE steps
    add_step("MN-ENGAGE", "Create First Session",
             "Mentor creates Session record with Scheduled status and date/time.",
             "action", "MST-PER-011", 1)
    add_step("MN-ENGAGE", "Record Session Details",
             "After meeting, mentor records duration, type, topics, notes, next steps.",
             "action", "MST-PER-011", 2)
    add_step("MN-ENGAGE", "Activate Engagement",
             "First Completed session auto-transitions Engagement from Assigned to Active.",
             "system", None, 3)
    add_step("MN-ENGAGE", "Set Meeting Cadence",
             "Mentor sets Meeting Cadence on Engagement (Weekly, Bi-Weekly, Monthly, As Needed).",
             "action", "MST-PER-011", 4)
    add_step("MN-ENGAGE", "Schedule Next Session",
             "Mentor sets Next Session Date/Time, system creates calendar event and new Session.",
             "action", "MST-PER-011", 5)
    add_step("MN-ENGAGE", "Send Session Summary",
             "System drafts session summary email; mentor reviews and sends.",
             "notification", "MST-PER-011", 6)
    add_step("MN-ENGAGE", "Update Roll-Up Analytics",
             "System updates Engagement roll-ups: total sessions, hours, last session date.",
             "system", None, 7)

    # MN-INACTIVE steps
    add_step("MN-INACTIVE", "Daily Activity Scan",
             "Automated scan compares today vs Next Session Date/Time using cadence thresholds.",
             "system", None, 1)
    add_step("MN-INACTIVE", "Transition to Dormant",
             "Elapsed > 1x multiplier: Active to Dormant. Notify mentor and Client Administrator.",
             "system", None, 2)
    add_step("MN-INACTIVE", "Transition to Inactive",
             "Elapsed > 2x multiplier: Dormant to Inactive. Notify mentor and Client Administrator.",
             "system", None, 3)
    add_step("MN-INACTIVE", "Transition to Abandoned",
             "Elapsed > 3x multiplier: Inactive to Abandoned. Auto-set Close Date and Close Reason.",
             "system", None, 4)
    add_step("MN-INACTIVE", "Activity Resumes",
             "Scheduling or completing a session resets clock and returns to Active.",
             "system", None, 5)

    # MN-CLOSE steps
    add_step("MN-CLOSE", "Initiate Closure",
             "Mentor or Client Administrator changes Engagement status to Completed.",
             "action", "MST-PER-011", 1)
    add_step("MN-CLOSE", "Validate Eligible Status",
             "System validates current status is Active, On-Hold, Dormant, or Inactive.",
             "system", None, 2)
    add_step("MN-CLOSE", "Record Close Reason",
             "System requires Close Reason selection.",
             "action", "MST-PER-011", 3)
    add_step("MN-CLOSE", "Auto-Populate Close Date",
             "System sets Close Date to current date.",
             "system", None, 4)
    add_step("MN-CLOSE", "Review Outcome Fields",
             "System presents outcome fields for optional review.",
             "action", "MST-PER-011", 5)
    add_step("MN-CLOSE", "Send Closure Survey",
             "System sends Closed Engagement Survey to Primary Engagement Contact.",
             "notification", None, 6)
    add_step("MN-CLOSE", "Generate Thank-You Email",
             "System generates thank-you email; mentor may modify and send.",
             "notification", "MST-PER-011", 7)

    # MR-RECRUIT steps
    add_step("MR-RECRUIT", "Identify Prospects",
             "Recruiter identifies prospective mentors through outreach and partner channels.",
             "action", "MST-PER-006", 1)
    add_step("MR-RECRUIT", "Create Prospect Record",
             "Create Contact with contactType=Mentor, mentorStatus=Prospect.",
             "action", "MST-PER-006", 2)
    add_step("MR-RECRUIT", "Record Outreach Activity",
             "Record referral source and outreach notes on prospect records.",
             "action", "MST-PER-006", 3)
    add_step("MR-RECRUIT", "Track Campaign Results",
             "Monitor application volume and pipeline trends.",
             "action", "MST-PER-006", 4)

    # MR-APPLY steps
    add_step("MR-APPLY", "Submit Application",
             "Mentor submits application via website. System updates existing prospect or creates new Contact.",
             "action", "MST-PER-011", 1)
    add_step("MR-APPLY", "Record Terms Acceptance",
             "Terms & Conditions Accepted = Yes with timestamp.",
             "system", None, 2)
    add_step("MR-APPLY", "Send Confirmation",
             "Automatic confirmation email sent to applicant.",
             "notification", None, 3)
    add_step("MR-APPLY", "Notify Mentor Administrator",
             "Immediate notification to Mentor Administrator of new application.",
             "notification", None, 4)
    add_step("MR-APPLY", "Review Application",
             "Mentor Administrator reviews via Submitted/In Review filter view.",
             "action", "MST-PER-005", 5)
    add_step("MR-APPLY", "Admission Decision",
             "Approve (status=Provisional) or decline with required reason.",
             "decision", "MST-PER-005", 6)

    # MR-ONBOARD steps
    add_step("MR-ONBOARD", "Begin Onboarding",
             "Provisional mentor begins training and compliance requirements.",
             "action", "MST-PER-011", 1)
    add_step("MR-ONBOARD", "Complete Training",
             "LMS integration tracks training completion; manual fallback available.",
             "action", "MST-PER-011", 2)
    add_step("MR-ONBOARD", "Accept Ethics Agreement",
             "Admin records ethics agreement acceptance with timestamp.",
             "action", "MST-PER-005", 3)
    add_step("MR-ONBOARD", "Background Check",
             "Admin records background check completion. Optional.",
             "action", "MST-PER-005", 4)
    add_step("MR-ONBOARD", "Assign CBM Email",
             "Admin provisions and records CBM email address.",
             "action", "MST-PER-005", 5)
    add_step("MR-ONBOARD", "Set Capacity and Activate",
             "Set Maximum Client Capacity and Accepting New Clients. Transition to Active.",
             "action", "MST-PER-005", 6)

    # MR-MANAGE steps
    add_step("MR-MANAGE", "Maintain Profile",
             "Mentor self-service editing of profile fields with immediate effect.",
             "action", "MST-PER-011", 1)
    add_step("MR-MANAGE", "Manage Capacity",
             "System calculates Current Active Clients and Available Capacity.",
             "system", None, 2)
    add_step("MR-MANAGE", "Track Dues",
             "Annual dues billing with Dues records per mentor per year.",
             "action", "MST-PER-005", 3)
    add_step("MR-MANAGE", "Monitor Inactivity",
             "Alert at 60 days (configurable) regardless of engagement status.",
             "system", None, 4)
    add_step("MR-MANAGE", "Status Transitions",
             "Active <-> Paused, Active <-> Inactive. Set Accepting New Clients = No on Paused/Inactive.",
             "action", "MST-PER-005", 5)

    # MR-DEPART steps
    add_step("MR-DEPART", "Initiate Departure",
             "Transition to Resigned or Departed with departure reason and date.",
             "action", "MST-PER-005", 1)
    add_step("MR-DEPART", "Review Active Engagements",
             "View departing mentor's Active/Assigned/On-Hold engagements for reassignment.",
             "action", "MST-PER-005", 2)
    add_step("MR-DEPART", "Trigger Reassignment",
             "Active engagements handed off to MN-MATCH for re-matching.",
             "system", None, 3)
    add_step("MR-DEPART", "Process Reactivation",
             "If requested: reactivate from Resigned/Departed to Active or Provisional.",
             "action", "MST-PER-005", 4)

    conn.commit()
    print(f"2e: ProcessSteps inserted ({step_count})")


def populate_requirements(conn):
    c = conn.cursor()
    req_count = 0

    def add_req(proc_code, num, desc, priority="must"):
        nonlocal req_count
        identifier = f"{proc_code}-REQ-{num:03d}"
        c.execute("""
            INSERT INTO Requirement (identifier, process_id, description, priority, status)
            VALUES (?, ?, ?, ?, 'approved')
        """, (identifier, process_ids[proc_code], desc, priority))
        req_count += 1

    # MN-INTAKE (9 requirements)
    add_req("MN-INTAKE", 1, "Accept mentoring requests from public website intake form")
    add_req("MN-INTAKE", 2, "Auto-create linked Account, Contact, and Engagement records from intake submission")
    add_req("MN-INTAKE", 3, "Send email notification to Client Administrator on new submission")
    add_req("MN-INTAKE", 4, "Provide filtered view of new client submissions for administrator review")
    add_req("MN-INTAKE", 5, "Support approve or decline decision with required decline reason")
    add_req("MN-INTAKE", 6, "Send status notification to applicant on decision")
    add_req("MN-INTAKE", 7, "Retain all application records permanently regardless of decision outcome")
    add_req("MN-INTAKE", 8, "Derive Account name as '{First} {Last} (Pre-Startup)' when Business Name is blank")
    add_req("MN-INTAKE", 9, "Support optional Requested Mentor preference from intake form")

    # MN-MATCH (9 requirements)
    add_req("MN-MATCH", 1, "Provide searchable mentor roster filtered by expertise, industry, availability, capacity")
    add_req("MN-MATCH", 2, "Track mentor candidates with selection rationale for each engagement")
    add_req("MN-MATCH", 3, "Support primary mentor assignment with optional co-mentor and SME")
    add_req("MN-MATCH", 4, "Auto-transition Engagement to Pending Acceptance on mentor nomination")
    add_req("MN-MATCH", 5, "Send notification to nominated mentor with client summary and acceptance link")
    add_req("MN-MATCH", 6, "Support mentor acceptance or declination with automatic status transitions")
    add_req("MN-MATCH", 7, "Alert coordinator when mentor does not respond within acceptance window")
    add_req("MN-MATCH", 8, "Record matching rationale for accountability and continuous improvement")
    add_req("MN-MATCH", 9, "Review Requested Mentor preference before general roster search")

    # MN-ENGAGE (11 requirements)
    add_req("MN-ENGAGE", 1, "Support Session record creation with date/time and Scheduled status")
    add_req("MN-ENGAGE", 2, "Auto-transition Engagement to Active on first Completed session")
    add_req("MN-ENGAGE", 3, "Capture session details: duration, type, location, topics, notes, next steps")
    add_req("MN-ENGAGE", 4, "Support Meeting Cadence setting on Engagement")
    add_req("MN-ENGAGE", 5, "Auto-create calendar event and new Session from Next Session Date/Time")
    add_req("MN-ENGAGE", 6, "Generate session summary email for mentor review and send")
    add_req("MN-ENGAGE", 7, "Update Engagement roll-up analytics on Session status change")
    add_req("MN-ENGAGE", 8, "Support additional mentor assignment at any time during active engagement")
    add_req("MN-ENGAGE", 9, "Support On-Hold status with Hold End Date and manual return to Active")
    add_req("MN-ENGAGE", 10, "Preserve rescheduled Sessions with self-referential link to predecessor")
    add_req("MN-ENGAGE", 11, "Track separate Mentor Attendees and Client Attendees per Session")

    # MN-INACTIVE (12 requirements)
    add_req("MN-INACTIVE", 1, "Run daily automated scan of all Active and On-Hold engagements")
    add_req("MN-INACTIVE", 2, "Calculate inactivity thresholds based on Meeting Cadence with configurable multiplier")
    add_req("MN-INACTIVE", 3, "Auto-transition Active to Dormant when elapsed exceeds 1x threshold")
    add_req("MN-INACTIVE", 4, "Auto-transition Dormant to Inactive when elapsed exceeds 2x threshold")
    add_req("MN-INACTIVE", 5, "Auto-transition Inactive to Abandoned with Close Date and Close Reason")
    add_req("MN-INACTIVE", 6, "Send notification on Dormant and Inactive transitions to mentor and Client Administrator")
    add_req("MN-INACTIVE", 7, "Auto-revert to Active when session activity resumes at Dormant or Inactive")
    add_req("MN-INACTIVE", 8, "Display warning when manually reverting to Active without new session")
    add_req("MN-INACTIVE", 9, "Support configurable default cadence for As Needed engagements")
    add_req("MN-INACTIVE", 10, "Support configurable escalation multiplier (default 2x)")
    add_req("MN-INACTIVE", 11, "Provide two configurable notification templates (Dormant and Inactive)")
    add_req("MN-INACTIVE", 12, "Provide Engagement Health dashboard with pipeline status counts")

    # MN-CLOSE (8 requirements)
    add_req("MN-CLOSE", 1, "Support Engagement closure from Active, On-Hold, Dormant, or Inactive status")
    add_req("MN-CLOSE", 2, "Require Close Reason selection on closure")
    add_req("MN-CLOSE", 3, "Auto-populate Close Date on closure")
    add_req("MN-CLOSE", 4, "Present outcome fields for optional review at closure")
    add_req("MN-CLOSE", 5, "Send Closed Engagement Survey to Primary Engagement Contact")
    add_req("MN-CLOSE", 6, "Generate thank-you email from template for mentor review and send")
    add_req("MN-CLOSE", 7, "Support reopening Completed engagement to Active with outcome data retained")
    add_req("MN-CLOSE", 8, "Retain complete engagement history permanently after closure")

    # MR-RECRUIT (5 requirements)
    add_req("MR-RECRUIT", 1, "Maintain prospect records with Contact Type=Mentor, Status=Prospect and dedicated pipeline view")
    add_req("MR-RECRUIT", 2, "Record referral source (How Did You Hear About CBM)")
    add_req("MR-RECRUIT", 3, "Record outreach activity as notes on prospect records")
    add_req("MR-RECRUIT", 4, "Support prospect list export for external marketing")
    add_req("MR-RECRUIT", 5, "Provide roster analysis data for gap identification")

    # MR-APPLY (9 requirements)
    add_req("MR-APPLY", 1, "Accept applications from website; update existing prospect or create new Contact")
    add_req("MR-APPLY", 2, "Record Terms & Conditions Accepted with timestamp")
    add_req("MR-APPLY", 3, "Send automatic confirmation email to applicant")
    add_req("MR-APPLY", 4, "Notify Mentor Administrator immediately on new application")
    add_req("MR-APPLY", 5, "Provide single view of Submitted and In Review applications with filters")
    add_req("MR-APPLY", 6, "Require application decline reason when Status = Declined")
    add_req("MR-APPLY", 7, "Retain permanent records regardless of outcome")
    add_req("MR-APPLY", 8, "Detect duplicate applications by email with three outcomes")
    add_req("MR-APPLY", 9, "Support manual contact merge function for Mentor Administrator")

    # MR-ONBOARD (7 requirements)
    add_req("MR-ONBOARD", 1, "Support Provisional to Active and Provisional to Declined transitions")
    add_req("MR-ONBOARD", 2, "Integrate with LMS for training completion tracking with manual fallback")
    add_req("MR-ONBOARD", 3, "Record ethics agreement acceptance with datetime timestamp")
    add_req("MR-ONBOARD", 4, "Record background check fields; admin-only, hidden from mentors")
    add_req("MR-ONBOARD", 5, "Support CBM email address assignment")
    add_req("MR-ONBOARD", 6, "Require Maximum Client Capacity and Accepting New Clients before activation")
    add_req("MR-ONBOARD", 7, "Auto-set isPrimaryMentor = Yes when status changes to Active")

    # MR-MANAGE (11 requirements)
    add_req("MR-MANAGE", 1, "Support full mentor profile self-service editing with immediate effect")
    add_req("MR-MANAGE", 2, "Maintain three role eligibility flags: isPrimaryMentor, isCoMentor, isSubjectMatterExpert")
    add_req("MR-MANAGE", 3, "System-calculate Current Active Clients and Available Capacity")
    add_req("MR-MANAGE", 4, "Provide searchable mentor directory (professional fields only)")
    add_req("MR-MANAGE", 5, "Support board position text field")
    add_req("MR-MANAGE", 6, "Support annual dues billing with Dues records per mentor per year")
    add_req("MR-MANAGE", 7, "Alert at 60 days inactivity (configurable threshold)")
    add_req("MR-MANAGE", 8, "Calculate three mentor-level analytics fields")
    add_req("MR-MANAGE", 9, "Support admin-only notes on mentor records")
    add_req("MR-MANAGE", 10, "Support Active/Paused/Inactive transitions with auto-set Accepting New Clients")
    add_req("MR-MANAGE", 11, "Support admin override of any mentor-editable field")

    # MR-DEPART (4 requirements)
    add_req("MR-DEPART", 1, "Support transition to Resigned/Departed with departure reason and date")
    add_req("MR-DEPART", 2, "Support reactivation from Resigned/Departed to Active or Provisional")
    add_req("MR-DEPART", 3, "Provide view of departing mentor's active engagements for reassignment")
    add_req("MR-DEPART", 4, "Retain permanent records after departure")

    conn.commit()
    print(f"2e: Requirements inserted ({req_count})")


# =============================================================================
# 2f -- Cross-References
# =============================================================================

def populate_cross_references(conn):
    c = conn.cursor()

    # ProcessEntity -- which entities each process uses
    pe_data = [
        # MN-INTAKE
        ("MN-INTAKE", "ACT", "created", "Client Organization created from intake form"),
        ("MN-INTAKE", "CON", "created", "Client Contact created from intake form"),
        ("MN-INTAKE", "ENG", "created", "Engagement created with Submitted status"),
        # MN-MATCH
        ("MN-MATCH", "ACT", "referenced", "Client Organization reviewed for matching context"),
        ("MN-MATCH", "CON", "referenced", "Mentor roster searched; Contact data displayed"),
        ("MN-MATCH", "ENG", "updated", "Engagement assigned mentor, status updated"),
        # MN-ENGAGE
        ("MN-ENGAGE", "ENG", "updated", "Engagement status, cadence, analytics updated"),
        ("MN-ENGAGE", "SES", "created", "Sessions created and completed within engagements"),
        ("MN-ENGAGE", "CON", "referenced", "Mentor and client contacts referenced for sessions"),
        # MN-INACTIVE
        ("MN-INACTIVE", "ENG", "updated", "Engagement status transitioned through inactivity stages"),
        # MN-CLOSE
        ("MN-CLOSE", "ENG", "updated", "Engagement closed with reason and outcomes"),
        ("MN-CLOSE", "CON", "referenced", "Primary Engagement Contact for survey and thank-you"),
        # MR-RECRUIT
        ("MR-RECRUIT", "CON", "created", "Prospect Contact records created"),
        # MR-APPLY
        ("MR-APPLY", "CON", "updated", "Contact updated from Prospect to Submitted/In Review"),
        # MR-ONBOARD
        ("MR-ONBOARD", "CON", "updated", "Contact updated through onboarding compliance fields"),
        # MR-MANAGE
        ("MR-MANAGE", "CON", "updated", "Mentor profile and status managed"),
        ("MR-MANAGE", "DUES", "created", "Annual Dues records created per mentor"),
        # MR-DEPART
        ("MR-DEPART", "CON", "updated", "Contact status to Resigned/Departed"),
        ("MR-DEPART", "ENG", "referenced", "Active engagements reviewed for reassignment"),
    ]

    for proc_code, ent_code, role, desc in pe_data:
        c.execute("""
            INSERT INTO ProcessEntity (process_id, entity_id, role, description)
            VALUES (?, ?, ?, ?)
        """, (process_ids[proc_code], entity_ids[ent_code], role, desc))

    # ProcessField -- specific fields used by processes
    pf_data = [
        # MN-INTAKE collected fields
        ("MN-INTAKE", "ACT.name", "collected", "Business Name from intake form"),
        ("MN-INTAKE", "ACT.website", "collected", "Website from intake form"),
        ("MN-INTAKE", "ACT.organizationType", "collected", "For-Profit or Non-Profit"),
        ("MN-INTAKE", "ACT.businessStage", "collected", "Business development stage"),
        ("MN-INTAKE", "ACT.industrySector", "collected", "Primary NAICS sector"),
        ("MN-INTAKE", "CON.firstName", "collected", "Client first name"),
        ("MN-INTAKE", "CON.lastName", "collected", "Client last name"),
        ("MN-INTAKE", "CON.emailAddress", "collected", "Client email"),
        ("MN-INTAKE", "CON.phoneNumber", "collected", "Client phone"),
        ("MN-INTAKE", "CON.addressPostalCode", "collected", "Client zip code"),
        ("MN-INTAKE", "CON.linkedInProfile", "collected", "LinkedIn URL"),
        ("MN-INTAKE", "ENG.engagementStatus", "updated", "Set to Submitted on creation"),
        ("MN-INTAKE", "ENG.mentoringFocusAreas", "collected", "Areas of mentoring need"),
        ("MN-INTAKE", "ENG.mentoringNeedsDescription", "collected", "Detailed needs narrative"),
        # MN-MATCH evaluated/displayed fields
        ("MN-MATCH", "CON.industrySectors", "filtered", "Mentor industry match filter"),
        ("MN-MATCH", "CON.mentoringFocusAreas", "filtered", "Mentor focus area match filter"),
        ("MN-MATCH", "CON.mentorStatus", "filtered", "Filter for Active mentors"),
        ("MN-MATCH", "CON.acceptingNewClients", "filtered", "Filter for accepting mentors"),
        ("MN-MATCH", "CON.availableCapacity", "displayed", "Available capacity shown in roster"),
        ("MN-MATCH", "ENG.engagementStatus", "updated", "Transition to Pending Acceptance/Assigned"),
        # MN-ENGAGE collected/updated fields
        ("MN-ENGAGE", "ENG.meetingCadence", "collected", "Meeting frequency set by mentor"),
        ("MN-ENGAGE", "ENG.engagementStatus", "updated", "Transition to Active on first session"),
        ("MN-ENGAGE", "ENG.totalSessions", "calculated", "Roll-up updated on session completion"),
        ("MN-ENGAGE", "ENG.totalSessionHours", "calculated", "Roll-up updated on session completion"),
        ("MN-ENGAGE", "SES.dateStart", "collected", "Session date/time set by mentor"),
        ("MN-ENGAGE", "SES.duration", "collected", "Session duration in minutes"),
        ("MN-ENGAGE", "SES.sessionType", "collected", "In-Person, Video Call, or Phone Call"),
        ("MN-ENGAGE", "SES.sessionNotes", "collected", "Mentor's session notes"),
        ("MN-ENGAGE", "SES.nextSteps", "collected", "Agreed next actions"),
        # MN-INACTIVE evaluated fields
        ("MN-INACTIVE", "ENG.engagementStatus", "evaluated", "Status checked for inactivity thresholds"),
        ("MN-INACTIVE", "ENG.meetingCadence", "evaluated", "Cadence determines threshold periods"),
        ("MN-INACTIVE", "ENG.nextSessionDateTime", "evaluated", "Compared against current date"),
        ("MN-INACTIVE", "ENG.closeDate", "updated", "Auto-set on Abandoned transition"),
        ("MN-INACTIVE", "ENG.closeReason", "updated", "Auto-set to Inactive / No Response"),
        # MN-CLOSE collected fields
        ("MN-CLOSE", "ENG.closeDate", "updated", "Auto-populated on closure"),
        ("MN-CLOSE", "ENG.closeReason", "collected", "Required selection by mentor"),
        ("MN-CLOSE", "ENG.newBusinessStarted", "collected", "Outcome: new business started"),
        ("MN-CLOSE", "ENG.significantRevenueIncrease", "collected", "Outcome: revenue increase"),
    ]

    for proc_code, field_key, usage, desc in pf_data:
        fid = field_ids.get(field_key)
        if fid:
            c.execute("""
                INSERT INTO ProcessField (process_id, field_id, usage, description)
                VALUES (?, ?, ?, ?)
            """, (process_ids[proc_code], fid, usage, desc))

    # ProcessPersona
    pp_data = [
        ("MN-INTAKE", "MST-PER-013", "initiator", "Client submits mentoring request"),
        ("MN-INTAKE", "MST-PER-003", "performer", "Client Administrator reviews and decides"),
        ("MN-MATCH", "MST-PER-004", "performer", "Coordinator searches and nominates"),
        ("MN-MATCH", "MST-PER-005", "performer", "Provides mentor availability info"),
        ("MN-MATCH", "MST-PER-011", "performer", "Accepts or declines assignment"),
        ("MN-ENGAGE", "MST-PER-011", "performer", "Records sessions, manages engagement"),
        ("MN-ENGAGE", "MST-PER-003", "observer", "Monitors engagement health"),
        ("MN-INACTIVE", "MST-PER-003", "recipient", "Receives inactivity notifications"),
        ("MN-INACTIVE", "MST-PER-011", "recipient", "Receives inactivity notifications"),
        ("MN-INACTIVE", "MST-PER-002", "observer", "Views Engagement Health dashboard"),
        ("MN-CLOSE", "MST-PER-011", "initiator", "Initiates closure"),
        ("MN-CLOSE", "MST-PER-003", "performer", "Can also initiate closure"),
        ("MN-CLOSE", "MST-PER-013", "recipient", "Receives survey and thank-you"),
        ("MR-RECRUIT", "MST-PER-006", "performer", "Plans and executes outreach"),
        ("MR-RECRUIT", "MST-PER-008", "performer", "Supports via partner channels"),
        ("MR-APPLY", "MST-PER-011", "initiator", "Submits application"),
        ("MR-APPLY", "MST-PER-005", "performer", "Reviews and decides"),
        ("MR-ONBOARD", "MST-PER-011", "performer", "Completes training requirements"),
        ("MR-ONBOARD", "MST-PER-005", "performer", "Records compliance, activates"),
        ("MR-MANAGE", "MST-PER-011", "performer", "Manages own profile"),
        ("MR-MANAGE", "MST-PER-005", "performer", "Manages status, dues, admin notes"),
        ("MR-MANAGE", "MST-PER-001", "performer", "Configures inactivity threshold"),
        ("MR-DEPART", "MST-PER-005", "performer", "Initiates departure, manages reactivation"),
        ("MR-DEPART", "MST-PER-011", "performer", "Requests reactivation"),
    ]

    for proc_code, per_code, role, desc in pp_data:
        c.execute("""
            INSERT INTO ProcessPersona (process_id, persona_id, role, description)
            VALUES (?, ?, ?, ?)
        """, (process_ids[proc_code], persona_ids[per_code], role, desc))

    conn.commit()
    pe_count = c.execute("SELECT COUNT(*) FROM ProcessEntity").fetchone()[0]
    pf_count = c.execute("SELECT COUNT(*) FROM ProcessField").fetchone()[0]
    pp_count = c.execute("SELECT COUNT(*) FROM ProcessPersona").fetchone()[0]
    print(f"2f: ProcessEntity={pe_count}, ProcessField={pf_count}, ProcessPersona={pp_count}")


# =============================================================================
# 2g -- Decisions and Open Issues
# =============================================================================

def populate_decisions_and_issues(conn):
    c = conn.cursor()

    # Decisions from Contact Entity PRD, Account Entity PRD, Domain PRDs
    decisions = [
        # Contact Entity PRD decisions
        ("CON-DEC-001", "Primary Contact on Relationship",
         "Primary Contact is a bool on Contact-to-Account relationship, not a Contact field.",
         "locked", None, "CON", None, None),
        ("CON-DEC-002", "Title Field Shared",
         "Native title field treated as shared across all contact types. No dynamic logic required.",
         "locked", None, "CON", None, None),
        ("CON-DEC-003", "preferredName and linkedInProfile Shared",
         "preferredName and linkedInProfile are shared fields, not type-specific.",
         "locked", None, "CON", None, None),
        ("CON-DEC-004", "Mentor Email Implementation",
         "Two separate custom fields (personalEmail, cbmEmailAddress) rather than native multi-email.",
         "locked", None, "CON", None, None),
        ("CON-DEC-005", "Terms Fields Shared",
         "termsAndConditionsAccepted and timestamp are shared for portal readiness.",
         "locked", None, "CON", None, None),
        ("CON-DEC-006", "howDidYouHearAboutCbm Shared",
         "Shared across all contact types.",
         "locked", None, "CON", None, None),
        ("CON-DEC-007", "boardPosition CBM Internal",
         "Visible for CBM organizational member types, hidden for external types.",
         "locked", None, "CON", None, None),
        ("CON-DEC-008", "Mentor Status Ten Values",
         "Prospect, Submitted, In Review, Provisional, Active, Paused, Inactive, Resigned, Departed, Declined.",
         "locked", None, "CON", None, None),
        ("CON-DEC-009", "Zip Code Maps to Native",
         "Client Zip Code maps to native addressPostalCode. No custom address field needed.",
         "locked", None, "CON", None, None),

        # Account Entity PRD decisions
        ("ACT-DEC-001", "Primary Contact on Relationship Middle Table",
         "primaryContact bool on Contact-Account manyToMany middle table.",
         "locked", None, "ACT", None, None),
        ("ACT-DEC-002", "assignedLiaison Separate from assignedUser",
         "Separate custom Partner-specific link to Contact for dual-type accounts.",
         "locked", None, "ACT", None, None),
        ("ACT-DEC-003", "parentOrganization Shared",
         "Shared field available to all account types, not Partner-specific.",
         "locked", None, "ACT", None, None),
        ("ACT-DEC-004", "linkedInProfile Shared URL",
         "Structured URL field replacing free-text socialMedia.",
         "locked", None, "ACT", None, None),
        ("ACT-DEC-005", "Type-Specific Notes Fields",
         "clientNotes, partnerNotes, funderNotes with field-level security.",
         "locked", None, "ACT", None, None),

        # Engagement Entity PRD decisions
        ("ENG-DEC-001", "Auto-Generated Name",
         "Native name auto-generated as {Client Name}-{Mentor Name}-{Start Year}.",
         "locked", None, "ENG", None, None),
        ("ENG-DEC-002", "Description Hidden",
         "Native description field hidden from layouts.",
         "locked", None, "ENG", None, None),
        ("ENG-DEC-003", "Session Roll-Up Stored Fields",
         "Workflow-updated stored fields, not formula fields.",
         "locked", None, "ENG", None, None),
        ("ENG-DEC-006", "On-Hold as Enum Value",
         "On-Hold is one of 10 engagementStatus enum values, not a separate boolean.",
         "locked", None, "ENG", None, None),

        # Session Entity PRD decisions
        ("SES-DEC-003", "Custom Session Status Values",
         "Seven custom values replace platform defaults: Scheduled, Completed, etc.",
         "locked", None, "SES", None, None),
        ("SES-DEC-009", "Two Separate Attendee Relationships",
         "Mentor Attendees and Client Attendees as separate manyToMany.",
         "locked", None, "SES", None, None),

        # Dues Entity PRD decisions
        ("DUES-DEC-001", "Dues Custom Base Entity",
         "Dues is a Custom Base entity with one record per mentor per billing year.",
         "locked", None, "DUES", None, None),
        ("DUES-DEC-004", "paymentMethod No Waived Value",
         "Payment method values: Online Payment, Check only. When Waived, field hidden.",
         "locked", None, "DUES", None, None),

        # MN Domain decisions (representative sample)
        ("MN-DEC-001", "Engagement as Central Entity",
         "Engagement is the central entity linking client org, mentors, contacts, sessions.",
         "locked", "MN", None, None, None),
        ("MN-DEC-002", "Cadence-Aware Inactivity",
         "Inactivity thresholds adapt to engagement's Meeting Cadence setting.",
         "locked", "MN", None, None, None),

        # MR Domain decisions (representative sample)
        ("MR-DEC-001", "Email-Only Duplicate Detection",
         "Duplicate detection during MR-APPLY uses email address only.",
         "locked", "MR", None, None, None),
        ("MR-DEC-002", "Reactivation from Both Resigned and Departed",
         "Reactivation permitted from both Resigned and Departed states.",
         "locked", "MR", None, None, None),
    ]

    for d in decisions:
        ident, title, desc, status, dom_code, ent_code, proc_code, fld_key = d
        c.execute("""
            INSERT INTO Decision (identifier, title, description, status,
                                  domain_id, entity_id, process_id, field_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ident, title, desc, status,
              domain_ids.get(dom_code), entity_ids.get(ent_code),
              process_ids.get(proc_code), field_ids.get(fld_key)))

    # Open Issues
    issues = [
        # Contact Entity PRD issues
        ("CON-ISS-001", "Client Lifecycle Field Not Defined",
         "Client lifecycle field analogous to mentorStatus not yet defined.",
         "open", "medium", None, "CON", None, None),
        ("CON-ISS-002", "Partner Lifecycle Field Not Defined",
         "Partner lifecycle field not yet defined.",
         "open", "medium", None, "CON", None, None),
        ("CON-ISS-003", "Donor Lifecycle Field Not Defined",
         "Donor lifecycle field not yet defined.",
         "open", "medium", None, "CON", None, None),
        ("CON-ISS-004", "Incomplete Domain Coverage",
         "MR, CR, and FU have only summary-level data for Contact entity.",
         "open", "high", None, "CON", None, None),
        ("CON-ISS-005", "Mentoring Focus Areas Values",
         "Complete list of allowed values for mentoringFocusAreas not defined.",
         "open", "medium", None, "CON", None, "CON.mentoringFocusAreas"),
        ("CON-ISS-006", "Skills Expertise Tags Values",
         "Values for skillsExpertiseTags not yet defined.",
         "open", "low", None, "CON", None, "CON.skillsExpertiseTags"),
        ("CON-ISS-007", "Fluent Languages Values",
         "Values for fluentLanguages not yet defined.",
         "open", "low", None, "CON", None, "CON.fluentLanguages"),
        ("CON-ISS-008", "How Did You Hear Values",
         "Dropdown values for howDidYouHearAboutCbm not yet defined.",
         "open", "low", None, "CON", None, "CON.howDidYouHearAboutCbm"),

        # Account Entity PRD issues
        ("ACT-ISS-001", "Client Lifecycle Field",
         "Client account type does not have lifecycle status field. Deferred to CR domain.",
         "open", "medium", None, "ACT", None, None),
        ("ACT-ISS-002", "Incomplete Domain Coverage for Account",
         "CR and FU domains have only summary-level data.",
         "open", "high", None, "ACT", None, None),
        ("ACT-ISS-003", "NAICS Subsector Values",
         "Complete list of ~100 subsectors filtered by Industry Sector not defined.",
         "open", "medium", None, "ACT", None, "ACT.industrySubsector"),
        ("ACT-ISS-004", "Geographic Service Area Format",
         "Free text vs. controlled list not decided.",
         "open", "low", None, "ACT", None, "ACT.geographicServiceArea"),

        # Engagement Entity PRD issues
        ("ENG-ISS-001", "Mentoring Focus Areas Values",
         "Complete list of allowed values for Engagement mentoringFocusAreas not defined.",
         "open", "medium", None, "ENG", None, "ENG.mentoringFocusAreas"),
        ("ENG-ISS-002", "Close Reason Values",
         "Complete list of Close Reason values needs finalization.",
         "open", "medium", None, "ENG", None, "ENG.closeReason"),

        # Session Entity PRD issues
        ("SES-ISS-001", "Topics Covered Values",
         "Topics Covered multiEnum values not yet defined.",
         "open", "medium", None, "SES", None, "SES.topicsCovered"),
    ]

    for iss in issues:
        ident, title, desc, status, priority, dom_code, ent_code, proc_code, fld_key = iss
        c.execute("""
            INSERT INTO OpenIssue (identifier, title, description, status, priority,
                                   domain_id, entity_id, process_id, field_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ident, title, desc, status, priority,
              domain_ids.get(dom_code), entity_ids.get(ent_code),
              process_ids.get(proc_code), field_ids.get(fld_key)))

    conn.commit()
    dec_count = c.execute("SELECT COUNT(*) FROM Decision").fetchone()[0]
    iss_count = c.execute("SELECT COUNT(*) FROM OpenIssue").fetchone()[0]
    print(f"2g: Decisions={dec_count}, OpenIssues={iss_count}")


# =============================================================================
# 2h -- Work Items and Dependencies
# =============================================================================

def populate_work_items(conn):
    c = conn.cursor()

    def add_wi(item_type, phase, status, dom_code=None, ent_code=None, proc_code=None,
               started_at=None, completed_at=None):
        key = f"{item_type}:{dom_code or ''}{ent_code or ''}{proc_code or ''}"
        c.execute("""
            INSERT INTO WorkItem (item_type, domain_id, entity_id, process_id,
                                  phase, status, started_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (item_type,
              domain_ids.get(dom_code), entity_ids.get(ent_code),
              process_ids.get(proc_code),
              phase, status, started_at, completed_at))
        work_item_ids[key] = c.lastrowid
        return c.lastrowid

    # Phase 1: Master PRD
    add_wi("master_prd", "Phase 1", "complete",
           started_at="2026-01-15T09:00:00", completed_at="2026-01-20T17:00:00")

    # Phase 2: Business Object Discovery
    add_wi("business_object_discovery", "Phase 2", "complete",
           started_at="2026-01-25T09:00:00", completed_at="2026-02-01T17:00:00")

    # Phase 2: Entity PRDs -- one per entity
    entity_prd_status = {
        "CON": ("complete", "2026-02-05T09:00:00", "2026-02-10T17:00:00"),
        "ACT": ("complete", "2026-02-12T09:00:00", "2026-02-15T17:00:00"),
        "ENG": ("complete", "2026-02-17T09:00:00", "2026-02-20T17:00:00"),
        "SES": ("complete", "2026-02-22T09:00:00", "2026-02-25T17:00:00"),
        "DUES": ("complete", "2026-02-27T09:00:00", "2026-03-02T17:00:00"),
        "PA": ("not_started", None, None),
        "EVT": ("not_started", None, None),
        "EVREG": ("not_started", None, None),
        "CTB": ("not_started", None, None),
        "FC": ("not_started", None, None),
        "NOTE": ("not_started", None, None),
    }
    for ent_code, (status, started, completed) in entity_prd_status.items():
        add_wi("entity_prd", "Phase 2", status, ent_code=ent_code,
               started_at=started, completed_at=completed)

    # Phase 3: Domain Overviews
    do_status = {
        "MN": ("complete", "2026-03-01T09:00:00", "2026-03-03T17:00:00"),
        "MR": ("complete", "2026-03-04T09:00:00", "2026-03-06T17:00:00"),
        "CR": ("complete", "2026-03-07T09:00:00", "2026-03-10T17:00:00"),
        "CR-PARTNER": ("complete", "2026-03-11T09:00:00", "2026-03-13T17:00:00"),
        "CR-MARKETING": ("not_started", None, None),
        "CR-EVENTS": ("not_started", None, None),
        "CR-REACTIVATE": ("not_started", None, None),
        "FU": ("not_started", None, None),
        "NOTES": ("not_started", None, None),
    }
    for dom_code, (status, started, completed) in do_status.items():
        add_wi("domain_overview", "Phase 3", status, dom_code=dom_code,
               started_at=started, completed_at=completed)

    # Phase 4: Process Definitions
    pd_status = {
        # MN processes -- all complete
        "MN-INTAKE": ("complete", "2026-03-10T09:00:00", "2026-03-12T17:00:00"),
        "MN-MATCH": ("complete", "2026-03-13T09:00:00", "2026-03-15T17:00:00"),
        "MN-ENGAGE": ("complete", "2026-03-16T09:00:00", "2026-03-20T17:00:00"),
        "MN-INACTIVE": ("complete", "2026-03-21T09:00:00", "2026-03-23T17:00:00"),
        "MN-CLOSE": ("complete", "2026-03-24T09:00:00", "2026-03-26T17:00:00"),
        "MN-SURVEY": ("not_started", None, None),
        # MR processes -- all complete
        "MR-RECRUIT": ("complete", "2026-03-27T09:00:00", "2026-03-29T17:00:00"),
        "MR-APPLY": ("complete", "2026-03-30T09:00:00", "2026-04-01T17:00:00"),
        "MR-ONBOARD": ("complete", "2026-04-01T09:00:00", "2026-04-02T17:00:00"),
        "MR-MANAGE": ("complete", "2026-04-02T09:00:00", "2026-04-03T17:00:00"),
        "MR-DEPART": ("complete", "2026-04-03T09:00:00", "2026-04-04T17:00:00"),
        # FU processes -- not started
        "FU-PROSPECT": ("not_started", None, None),
        "FU-RECORD": ("not_started", None, None),
        "FU-STEWARD": ("not_started", None, None),
        "FU-REPORT": ("not_started", None, None),
    }
    for proc_code, (status, started, completed) in pd_status.items():
        add_wi("process_definition", "Phase 4", status, proc_code=proc_code,
               started_at=started, completed_at=completed)

    # Phase 5: Domain Reconciliation
    dr_status = {
        "MN": ("complete", "2026-04-04T09:00:00", "2026-04-05T17:00:00"),
        "MR": ("complete", "2026-04-05T09:00:00", "2026-04-06T17:00:00"),
        "CR": ("not_started", None, None),
        "FU": ("not_started", None, None),
    }
    for dom_code, (status, started, completed) in dr_status.items():
        add_wi("domain_reconciliation", "Phase 5", status, dom_code=dom_code,
               started_at=started, completed_at=completed)

    # Phases 6-11: all not_started for all domains/global
    for dom_code in ["MN", "MR", "CR", "FU"]:
        add_wi("stakeholder_review", "Phase 6", "not_started", dom_code=dom_code)
        add_wi("yaml_generation", "Phase 7", "not_started", dom_code=dom_code)

    add_wi("crm_selection", "Phase 8", "not_started")
    add_wi("crm_deployment", "Phase 9", "not_started")
    add_wi("crm_configuration", "Phase 10", "not_started")
    add_wi("verification", "Phase 11", "not_started")

    conn.commit()
    wi_count = c.execute("SELECT COUNT(*) FROM WorkItem").fetchone()[0]
    print(f"2h: WorkItems inserted ({wi_count})")


def populate_dependencies(conn):
    c = conn.cursor()

    def dep(waiting_key, depends_key):
        w_id = work_item_ids.get(waiting_key)
        d_id = work_item_ids.get(depends_key)
        if w_id and d_id:
            c.execute("INSERT INTO Dependency (work_item_id, depends_on_id) VALUES (?, ?)",
                      (w_id, d_id))

    master_key = "master_prd:"
    bod_key = "business_object_discovery:"

    # Rule 2: BOD depends on Master PRD
    dep(bod_key, master_key)

    # Rule 3: Each entity_prd depends on BOD
    for ent_code in entity_ids:
        dep(f"entity_prd:{ent_code}", bod_key)

    # Rule 4a: Each domain_overview depends on BOD
    for dom_code in ["MN", "MR", "CR", "CR-PARTNER", "CR-MARKETING",
                     "CR-EVENTS", "CR-REACTIVATE", "FU", "NOTES"]:
        dep(f"domain_overview:{dom_code}", bod_key)

    # Rule 4b: Domain overviews depend on entity_prds for entities in that domain
    # MN: Contact, Account, Engagement, Session
    for ent in ["CON", "ACT", "ENG", "SES"]:
        dep(f"domain_overview:MN", f"entity_prd:{ent}")
    # MR: Contact, Dues
    for ent in ["CON", "DUES"]:
        dep(f"domain_overview:MR", f"entity_prd:{ent}")
    # CR: Contact, Account, PA, EVT, EVREG
    for ent in ["CON", "ACT", "PA", "EVT", "EVREG"]:
        dep(f"domain_overview:CR", f"entity_prd:{ent}")
    # CR sub-domains depend on CR parent overview
    for sub in ["CR-PARTNER", "CR-MARKETING", "CR-EVENTS", "CR-REACTIVATE"]:
        dep(f"domain_overview:{sub}", "domain_overview:CR")
    # FU: Account, CTB, FC
    for ent in ["ACT", "CTB", "FC"]:
        dep(f"domain_overview:FU", f"entity_prd:{ent}")

    # Rule 4c: MR domain overview optionally depends on MN reconciliation (cross-domain)
    dep("domain_overview:MR", "domain_reconciliation:MN")

    # Rule 5a: Process definitions depend on domain overview
    proc_to_domain = {
        "MN-INTAKE": "MN", "MN-MATCH": "MN", "MN-ENGAGE": "MN",
        "MN-INACTIVE": "MN", "MN-CLOSE": "MN", "MN-SURVEY": "MN",
        "MR-RECRUIT": "MR", "MR-APPLY": "MR", "MR-ONBOARD": "MR",
        "MR-MANAGE": "MR", "MR-DEPART": "MR",
        "FU-PROSPECT": "FU", "FU-RECORD": "FU", "FU-STEWARD": "FU",
        "FU-REPORT": "FU",
    }
    for proc_code, dom_code in proc_to_domain.items():
        dep(f"process_definition:{proc_code}", f"domain_overview:{dom_code}")

    # Rule 5b: Sequential process definitions within domain
    mn_order = ["MN-INTAKE", "MN-MATCH", "MN-ENGAGE", "MN-INACTIVE", "MN-CLOSE", "MN-SURVEY"]
    for i in range(1, len(mn_order)):
        dep(f"process_definition:{mn_order[i]}", f"process_definition:{mn_order[i-1]}")
    mr_order = ["MR-RECRUIT", "MR-APPLY", "MR-ONBOARD", "MR-MANAGE", "MR-DEPART"]
    for i in range(1, len(mr_order)):
        dep(f"process_definition:{mr_order[i]}", f"process_definition:{mr_order[i-1]}")
    fu_order = ["FU-PROSPECT", "FU-RECORD", "FU-STEWARD", "FU-REPORT"]
    for i in range(1, len(fu_order)):
        dep(f"process_definition:{fu_order[i]}", f"process_definition:{fu_order[i-1]}")

    # Rule 6: Domain reconciliation depends on all process_definitions in domain
    for proc_code, dom_code in proc_to_domain.items():
        dep(f"domain_reconciliation:{dom_code}", f"process_definition:{proc_code}")

    # Rule 7: Stakeholder review depends on domain reconciliation
    for dom_code in ["MN", "MR", "CR", "FU"]:
        dep(f"stakeholder_review:{dom_code}", f"domain_reconciliation:{dom_code}")

    # Rule 8: YAML generation depends on stakeholder review
    for dom_code in ["MN", "MR", "CR", "FU"]:
        dep(f"yaml_generation:{dom_code}", f"stakeholder_review:{dom_code}")

    # Rule 9: CRM Selection depends on all yaml_generation
    for dom_code in ["MN", "MR", "CR", "FU"]:
        dep("crm_selection:", f"yaml_generation:{dom_code}")

    # Rules 10-12: linear chain
    dep("crm_deployment:", "crm_selection:")
    dep("crm_configuration:", "crm_deployment:")
    dep("verification:", "crm_configuration:")

    conn.commit()
    dep_count = c.execute("SELECT COUNT(*) FROM Dependency").fetchone()[0]
    print(f"2h: Dependencies inserted ({dep_count})")


# =============================================================================
# 2i -- Audit Records (AISessions, ChangeLogs, ChangeImpacts)
# =============================================================================

def populate_audit_records(conn):
    c = conn.cursor()

    # AISession records for completed work items
    ai_sessions = [
        ("master_prd:", "initial", "2026-01-15T09:00:00", "2026-01-20T17:00:00"),
        ("business_object_discovery:", "initial", "2026-01-25T09:00:00", "2026-02-01T17:00:00"),
        ("entity_prd:CON", "initial", "2026-02-05T09:00:00", "2026-02-10T17:00:00"),
        ("entity_prd:ACT", "initial", "2026-02-12T09:00:00", "2026-02-15T17:00:00"),
        ("entity_prd:ENG", "initial", "2026-02-17T09:00:00", "2026-02-20T17:00:00"),
        ("entity_prd:SES", "initial", "2026-02-22T09:00:00", "2026-02-25T17:00:00"),
        ("entity_prd:DUES", "initial", "2026-02-27T09:00:00", "2026-03-02T17:00:00"),
        ("domain_overview:MN", "initial", "2026-03-01T09:00:00", "2026-03-03T17:00:00"),
        ("domain_overview:MR", "initial", "2026-03-04T09:00:00", "2026-03-06T17:00:00"),
        ("process_definition:MN-INTAKE", "initial", "2026-03-10T09:00:00", "2026-03-12T17:00:00"),
        ("process_definition:MN-MATCH", "initial", "2026-03-13T09:00:00", "2026-03-15T17:00:00"),
        ("process_definition:MN-ENGAGE", "initial", "2026-03-16T09:00:00", "2026-03-20T17:00:00"),
        ("process_definition:MN-INACTIVE", "initial", "2026-03-21T09:00:00", "2026-03-23T17:00:00"),
        ("process_definition:MN-CLOSE", "initial", "2026-03-24T09:00:00", "2026-03-26T17:00:00"),
        ("process_definition:MR-RECRUIT", "initial", "2026-03-27T09:00:00", "2026-03-29T17:00:00"),
        ("process_definition:MR-APPLY", "initial", "2026-03-30T09:00:00", "2026-04-01T17:00:00"),
        ("process_definition:MR-ONBOARD", "initial", "2026-04-01T09:00:00", "2026-04-02T17:00:00"),
        ("process_definition:MR-MANAGE", "initial", "2026-04-02T09:00:00", "2026-04-03T17:00:00"),
        ("process_definition:MR-DEPART", "initial", "2026-04-03T09:00:00", "2026-04-04T17:00:00"),
        ("domain_reconciliation:MN", "initial", "2026-04-04T09:00:00", "2026-04-05T17:00:00"),
        ("domain_reconciliation:MR", "initial", "2026-04-05T09:00:00", "2026-04-06T17:00:00"),
    ]

    for wi_key, stype, started, completed in ai_sessions:
        wi_id = work_item_ids.get(wi_key)
        if wi_id:
            c.execute("""
                INSERT INTO AISession (work_item_id, session_type, generated_prompt,
                                       raw_output, structured_output, import_status,
                                       started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, 'imported', ?, ?)
            """, (wi_id, stype,
                  f"[Generated prompt for {wi_key}]",
                  f"[Raw AI output for {wi_key}]",
                  f"[Structured output for {wi_key}]",
                  started, completed))
            session_ids[wi_key] = c.lastrowid

    # ChangeLog: Contact entity creation
    contact_session_id = session_ids.get("entity_prd:CON")
    c.execute("""
        INSERT INTO ChangeLog (session_id, table_name, record_id, change_type,
                               rationale, changed_at)
        VALUES (?, 'Entity', ?, 'insert', 'Contact entity created during Entity PRD session',
                '2026-02-05T10:00:00')
    """, (contact_session_id, entity_ids["CON"]))
    cl_insert_id = c.lastrowid

    # ChangeLog: Field update on Contact (simulate revision that changed field type)
    # mentorStatus field had its options refined
    mentor_status_field_id = field_ids["CON.mentorStatus"]
    c.execute("""
        INSERT INTO ChangeLog (session_id, table_name, record_id, change_type,
                               field_name, old_value, new_value, rationale, changed_at)
        VALUES (?, 'Field', ?, 'update', 'description',
                'Eight-value lifecycle from Prospect through Departed.',
                'Ten-value lifecycle from Prospect through Departed.',
                'MR Domain PRD reconciliation added Paused and Declined values to mentorStatus',
                '2026-04-05T14:00:00')
    """, (session_ids.get("domain_reconciliation:MR"), mentor_status_field_id))
    cl_update_id = c.lastrowid

    # ChangeImpact for the field update
    # Impact 1: ProcessField reference in MN-MATCH (action_required = TRUE)
    pf_row = c.execute("""
        SELECT pf.id FROM ProcessField pf
        WHERE pf.field_id = ? AND pf.process_id = ?
    """, (mentor_status_field_id, process_ids["MN-MATCH"])).fetchone()
    if pf_row:
        c.execute("""
            INSERT INTO ChangeImpact (change_log_id, affected_table, affected_record_id,
                                      impact_description, requires_review, reviewed,
                                      action_required)
            VALUES (?, 'ProcessField', ?, 'MN-MATCH filters on mentorStatus; new values may affect filter logic',
                    1, 0, 0)
        """, (cl_update_id, pf_row[0]))

    # Impact 2: LayoutRow reference (action_required = FALSE -- informational)
    # We'll create this after layouts are populated; for now use a placeholder record_id
    c.execute("""
        INSERT INTO ChangeImpact (change_log_id, affected_table, affected_record_id,
                                  impact_description, requires_review, reviewed,
                                  reviewed_at, action_required)
        VALUES (?, 'LayoutRow', 999, 'Layout row displaying mentorStatus may need label update',
                1, 1, '2026-04-05T16:00:00', 0)
    """, (cl_update_id,))

    # One more ChangeImpact with action_required = TRUE
    c.execute("""
        INSERT INTO ChangeImpact (change_log_id, affected_table, affected_record_id,
                                  impact_description, requires_review, reviewed,
                                  reviewed_at, action_required)
        VALUES (?, 'ProcessField', ?, 'MN-INACTIVE evaluates mentorStatus; Paused state affects inactivity logic',
                1, 1, '2026-04-05T16:30:00', 1)
    """, (cl_update_id, pf_row[0] if pf_row else 1))

    conn.commit()
    sess_count = c.execute("SELECT COUNT(*) FROM AISession").fetchone()[0]
    cl_count = c.execute("SELECT COUNT(*) FROM ChangeLog").fetchone()[0]
    ci_count = c.execute("SELECT COUNT(*) FROM ChangeImpact").fetchone()[0]
    print(f"2i: AISessions={sess_count}, ChangeLogs={cl_count}, ChangeImpacts={ci_count}")


# =============================================================================
# 2j -- Layout Records
# =============================================================================

def populate_layouts(conn):
    c = conn.cursor()
    con_id = entity_ids["CON"]

    # Contact: Overview Panel
    c.execute("""
        INSERT INTO LayoutPanel (entity_id, label, sort_order, layout_mode)
        VALUES (?, 'Overview', 1, 'rows')
    """, (con_id,))
    overview_panel = c.lastrowid

    # Contact: Mentor Profile Panel
    c.execute("""
        INSERT INTO LayoutPanel (entity_id, label, sort_order, layout_mode,
                                 dynamic_logic_attribute, dynamic_logic_value)
        VALUES (?, 'Mentor Profile', 2, 'rows', 'contactType', 'Mentor')
    """, (con_id,))
    mentor_panel = c.lastrowid

    # Contact: Mentor Status Panel
    c.execute("""
        INSERT INTO LayoutPanel (entity_id, label, sort_order, layout_mode,
                                 dynamic_logic_attribute, dynamic_logic_value)
        VALUES (?, 'Mentor Status', 3, 'rows', 'contactType', 'Mentor')
    """, (con_id,))
    status_panel = c.lastrowid

    # LayoutRows for Overview panel
    overview_fields = [
        ("CON.salutationName", "CON.firstName"),
        ("CON.middleName", "CON.lastName"),
        ("CON.title", "CON.contactType"),
        ("CON.preferredName", "CON.linkedInProfile"),
        ("CON.emailAddress", "CON.phoneNumber"),
    ]
    for i, (f1_key, f2_key) in enumerate(overview_fields):
        c.execute("""
            INSERT INTO LayoutRow (panel_id, sort_order, cell_1_field_id, cell_2_field_id)
            VALUES (?, ?, ?, ?)
        """, (overview_panel, i + 1, field_ids.get(f1_key), field_ids.get(f2_key)))

    # LayoutRows for Mentor Profile panel
    profile_fields = [
        ("CON.personalEmail", "CON.cbmEmailAddress"),
        ("CON.currentEmployer", "CON.currentlyEmployed"),
        ("CON.yearsOfBusinessExperience", None),
        ("CON.industrySectors", "CON.mentoringFocusAreas"),
        ("CON.skillsExpertiseTags", "CON.fluentLanguages"),
    ]
    for i, (f1_key, f2_key) in enumerate(profile_fields):
        c.execute("""
            INSERT INTO LayoutRow (panel_id, sort_order, cell_1_field_id, cell_2_field_id)
            VALUES (?, ?, ?, ?)
        """, (mentor_panel, i + 1, field_ids.get(f1_key),
              field_ids.get(f2_key) if f2_key else None))

    # Full-width row for professionalBio
    c.execute("""
        INSERT INTO LayoutRow (panel_id, sort_order, cell_1_field_id, is_full_width)
        VALUES (?, 6, ?, 1)
    """, (mentor_panel, field_ids.get("CON.professionalBio")))

    # LayoutRows for Mentor Status panel
    status_fields = [
        ("CON.mentorStatus", "CON.acceptingNewClients"),
        ("CON.maximumClientCapacity", "CON.currentActiveClients"),
        ("CON.availableCapacity", None),
        ("CON.isPrimaryMentor", "CON.isCoMentor"),
        ("CON.isSubjectMatterExpert", None),
    ]
    for i, (f1_key, f2_key) in enumerate(status_fields):
        c.execute("""
            INSERT INTO LayoutRow (panel_id, sort_order, cell_1_field_id, cell_2_field_id)
            VALUES (?, ?, ?, ?)
        """, (status_panel, i + 1, field_ids.get(f1_key),
              field_ids.get(f2_key) if f2_key else None))

    # ListColumn for Contact list view
    list_fields = [
        ("CON.firstName", 15), ("CON.lastName", 15), ("CON.contactType", 15),
        ("CON.emailAddress", 20), ("CON.phoneNumber", 15), ("CON.mentorStatus", 10),
    ]
    for i, (fkey, width) in enumerate(list_fields):
        fid = field_ids.get(fkey)
        if fid:
            c.execute("""
                INSERT INTO ListColumn (entity_id, field_id, width, sort_order)
                VALUES (?, ?, ?, ?)
            """, (con_id, fid, width, i + 1))

    conn.commit()

    # Update ChangeImpact placeholder with real LayoutRow id
    lr_row = c.execute("""
        SELECT id FROM LayoutRow
        WHERE panel_id = ? AND cell_1_field_id = ?
    """, (status_panel, field_ids.get("CON.mentorStatus"))).fetchone()
    if lr_row:
        c.execute("UPDATE ChangeImpact SET affected_record_id = ? WHERE affected_record_id = 999",
                  (lr_row[0],))
        conn.commit()

    panel_count = c.execute("SELECT COUNT(*) FROM LayoutPanel").fetchone()[0]
    row_count = c.execute("SELECT COUNT(*) FROM LayoutRow").fetchone()[0]
    lc_count = c.execute("SELECT COUNT(*) FROM ListColumn").fetchone()[0]
    print(f"2j: LayoutPanels={panel_count}, LayoutRows={row_count}, ListColumns={lc_count}")


# =============================================================================
# 2k -- GenerationLog
# =============================================================================

def populate_generation_log(conn):
    c = conn.cursor()

    # MN-INTAKE process document -- generated as final
    intake_wi = work_item_ids.get("process_definition:MN-INTAKE")
    if intake_wi:
        c.execute("""
            INSERT INTO GenerationLog (work_item_id, document_type, file_path,
                                       generated_at, generation_mode)
            VALUES (?, 'process_document', 'PRDs/MN/MN-INTAKE.docx',
                    '2026-03-12T17:00:00', 'final')
        """, (intake_wi,))

    # Contact Entity PRD -- generated as final
    contact_wi = work_item_ids.get("entity_prd:CON")
    if contact_wi:
        c.execute("""
            INSERT INTO GenerationLog (work_item_id, document_type, file_path,
                                       generated_at, generation_mode)
            VALUES (?, 'entity_prd', 'PRDs/entities/Contact-Entity-PRD.docx',
                    '2026-02-10T17:00:00', 'final')
        """, (contact_wi,))

    conn.commit()
    gl_count = c.execute("SELECT COUNT(*) FROM GenerationLog").fetchone()[0]
    print(f"2k: GenerationLog records={gl_count}")


# =============================================================================
# Summary
# =============================================================================

def print_summary(conn):
    c = conn.cursor()
    print("\n" + "=" * 50)
    print("POPULATION SUMMARY")
    print("=" * 50)

    tables = [
        "Domain", "Entity", "Field", "FieldOption", "Relationship",
        "Persona", "BusinessObject", "Process", "ProcessStep", "Requirement",
        "ProcessEntity", "ProcessField", "ProcessPersona",
        "Decision", "OpenIssue", "WorkItem", "Dependency",
        "AISession", "ChangeLog", "ChangeImpact", "GenerationLog",
        "LayoutPanel", "LayoutRow", "LayoutTab", "ListColumn",
    ]
    total = 0
    for table in tables:
        count = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table + ':':.<30} {count:>4}")
        total += count
    print(f"  {'TOTAL:':.<30} {total:>4}")


# =============================================================================
# Main
# =============================================================================

def main():
    populate_master()

    conn = sqlite3.connect(CLIENT_DB)
    # Disable FK checking during bulk load (circular refs between tables)
    conn.execute("PRAGMA foreign_keys = OFF")

    populate_domains(conn)
    populate_entities(conn)
    populate_fields(conn)
    populate_relationships(conn)
    populate_personas(conn)
    populate_business_objects(conn)
    populate_processes(conn)
    populate_process_steps(conn)
    populate_requirements(conn)
    populate_cross_references(conn)
    populate_decisions_and_issues(conn)
    populate_work_items(conn)
    populate_dependencies(conn)
    populate_audit_records(conn)
    populate_layouts(conn)
    populate_generation_log(conn)

    # Compute ready status: not_started items whose dependencies are all complete
    ready_count = conn.execute("""
        UPDATE WorkItem SET status = 'ready', updated_at = datetime('now')
        WHERE status = 'not_started'
          AND id NOT IN (
              SELECT dep.work_item_id FROM Dependency dep
              JOIN WorkItem upstream ON dep.depends_on_id = upstream.id
              WHERE upstream.status != 'complete'
          )
          AND id IN (SELECT work_item_id FROM Dependency)
    """).rowcount
    conn.commit()
    print(f"\nWorkflow engine: {ready_count} items transitioned not_started → ready")

    # Re-enable FK checking and verify
    conn.execute("PRAGMA foreign_keys = ON")
    fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk_errors:
        print(f"\nWARNING: {len(fk_errors)} FK violations found:")
        for err in fk_errors[:10]:
            print(f"  {err}")
    else:
        print("\nFK integrity check: PASSED")

    print_summary(conn)
    conn.close()


if __name__ == "__main__":
    main()
