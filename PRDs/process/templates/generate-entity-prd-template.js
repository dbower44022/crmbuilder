// ═══════════════════════════════════════════════════════════════════════
// CRM Builder — Entity PRD Generator Template
// ═══════════════════════════════════════════════════════════════════════
//
// Reference implementation for generating Phase 2b Entity PRD documents
// as Word (.docx) files. This template defines the standard formatting,
// table layouts, and document structure used across all CRM Builder
// Entity PRDs.
//
// Usage:
//   Copy this file per entity, replace the ENTITY DATA section with
//   the entity-specific data, then run with Node.js:
//     node generate-{EntityName}-Entity-PRD.js
//
// Reference document: Contact-Entity-PRD.docx (Cleveland Business Mentors)
//
// Document structure (9 sections per Entity Definition guide v1.0):
//   1. Entity Overview        — metadata, description, domain coverage
//   2. Native Fields          — fields that exist on the platform entity type
//   3. Custom Fields          — fields created via YAML, grouped by scope
//   4. Relationships          — all relationships involving this entity
//   5. Dynamic Logic Rules    — visibility rules grouped by discriminator
//   6. Layout Guidance        — suggested panel/tab grouping
//   7. Implementation Notes   — calculated fields, access control, etc.
//   8. Open Issues            — unresolved questions
//   9. Decisions Made         — decisions from the entity definition session
//
// Formatting standards (also stored in Claude memory):
//   - Font: Arial throughout
//   - Colors: Header bg #1F3864, header text white, title/heading #1F3864,
//     alt row shading #F2F7FB, borders #AAAAAA, gray text #888888
//   - Field tables: Two rows per field
//     Row 1: Field Name (bold) | Type | Required (Yes/No) | Values | Default | ID (small gray)
//     Row 2: Description (full-width span, gray font)
//     Description includes: PRD mapping, domain(s), visibility rule,
//     implementation notes — all in the gray description row
//     Alternating shading per field pair
//   - Column widths (DXA): 2200 + 1100 + 800 + 2400 + 1000 + 1860 = 9360
//   - Required column: strictly Yes/No — nuance goes in description
//   - Page: US Letter, 1" margins
//   - Header: org name left, entity PRD label right
//   - Footer: "Entity PRD — [Entity Name]"
//   - Human-readable-first identifiers throughout
//
// Dependencies:
//   npm install -g docx
//
// ═══════════════════════════════════════════════════════════════════════


// ═══════════════════════════════════════════════════════════════════════
// ENTITY DATA — Replace this section for each entity
// ═══════════════════════════════════════════════════════════════════════

const ENTITY = {

  // ── Document metadata ────────────────────────────────────────────
  orgName: "Cleveland Business Mentors",
  entityName: "Contact",
  version: "1.0",
  status: "Draft",
  lastUpdated: "04-01-26 21:00",
  sourceDocuments: "Master PRD v2.0, Entity Inventory v1.0, MN Domain PRD v1.0, MR Domain PRD v1.0 (legacy), CR Domain PRD v1.0 (legacy, summary), FU Domain PRD v1.0 (legacy, summary)",
  outputFile: "/home/claude/Contact-Entity-PRD.docx",

  // ── Entity overview (Section 1) ──────────────────────────────────
  overview: {
    crmEntityName: "Contact",
    nativeOrCustom: "Native",
    entityType: "Person",
    labelSingular: "Contact",
    labelPlural: "Contacts",
    activityStream: "Yes",
    contributingDomains: "Mentoring (MN), Mentor Recruitment (MR), Client Recruiting (CR), Fundraising (FU)",
    // For shared entities with a discriminator:
    discriminatorField: "contactType (multiEnum)",
    discriminatorValues: "Client, Mentor, Partner, Administrator, Presenter, Donor, Member",
    // Set to null for non-shared entities:
    // discriminatorField: null,
    // discriminatorValues: null,
  },

  // Free-form paragraphs after the overview table.
  // Each string becomes one paragraph.
  overviewText: [
    "The Contact entity is the single repository for all individual people known to Cleveland Business Mentors. It is the most complex entity in the implementation, spanning all four business domains with type-specific fields controlled by dynamic logic visibility rules based on the contactType discriminator.",
    "A single Contact can hold multiple types simultaneously. A volunteer mentor who also presents at workshops and serves on the board would have contactType values of Mentor, Presenter, and Administrator. Dynamic logic uses the \u201CcontactType has [value]\u201D condition to show or hide type-specific fields, meaning a Contact with multiple types sees the union of all relevant fields.",
    "Prospect is a lifecycle state, not a contactType value. A mentor prospect is a Contact with contactType = Mentor at Mentor Status = Prospect. Client prospects have not yet entered the system through the intake process.",
  ],

  // Optional: rich text paragraph with bold label prefix.
  // Format: { label: "Bold prefix:", text: "Rest of paragraph" }
  overviewNotes: [
    { label: "Domain coverage:", text: " The Mentoring (MN) domain has complete field-level detail from the reconciled Domain PRD v1.0 and five process documents. The Mentor Recruitment (MR) domain has detailed field definitions from the legacy Domain PRD v1.0. The Client Recruiting (CR) and Fundraising (FU) domains have summary-level data from the Master PRD only. This Entity PRD will require updates when CR and FU domain process documents are completed." },
  ],

  // ── Native fields (Section 2) ────────────────────────────────────
  // Format: [nativeFieldName, type, prdMapping, referencedBy]
  nativeFieldsIntro: "The following fields already exist on the Contact entity because of its Person entity type. These fields are not created by YAML. They are documented here so process documents and Entity PRDs can reference them correctly, and to prevent duplicate field creation during YAML generation.",
  nativeFields: [
    ["firstName", "varchar", "First Name (MN-INTAKE-DAT-008)", "MN-INTAKE, MN-ENGAGE, MN-INACTIVE, MN-CLOSE"],
    ["lastName", "varchar", "Last Name (MN-INTAKE-DAT-009)", "MN-INTAKE, MN-ENGAGE, MN-INACTIVE, MN-CLOSE"],
    ["middleName", "varchar", "Middle Name (MN-INTAKE-DAT-010)", "MN-INTAKE"],
    ["salutationName", "enum", "Salutation (Mr., Mrs., Ms., Dr.)", "Not explicitly referenced in PRDs"],
    ["title", "varchar", "Professional Title (MR domain)", "MR-MANAGE; shared across all types"],
    ["emailAddress", "email (multi)", "Email (MN-INTAKE-DAT-012)", "MN-INTAKE, MN-ENGAGE, MN-CLOSE"],
    ["phoneNumber", "phone (multi)", "Phone (MN-INTAKE-DAT-013)", "MN-INTAKE, MN-ENGAGE"],
    ["addressStreet", "varchar", "Address composite \u2014 street portion", "MN-INTAKE (partial: zip code only)"],
    ["addressCity", "varchar", "Address composite \u2014 city portion", "MN-INTAKE (partial: zip code only)"],
    ["addressState", "varchar", "Address composite \u2014 state portion", "MN-INTAKE (partial: zip code only)"],
    ["addressCountry", "varchar", "Address composite \u2014 country portion", "MN-INTAKE (partial: zip code only)"],
    ["addressPostalCode", "varchar", "Zip Code (MN-INTAKE-DAT-014)", "MN-INTAKE"],
    ["description", "text", "General description/notes", "Not explicitly referenced in PRDs"],
    ["createdAt", "datetime", "System \u2014 record creation timestamp", "System"],
    ["modifiedAt", "datetime", "System \u2014 last modified timestamp", "System"],
    ["assignedUser", "link", "System \u2014 assigned CRM user", "System"],
  ],
  // Optional notes after the native fields table.
  // Format: { label: "Bold prefix:", text: "Rest of paragraph" }
  nativeFieldNotes: [
    { label: "Note on emailAddress:", text: " The native emailAddress field supports multiple email addresses with a primary designation. For Client, Partner, Donor, Administrator, Presenter, and Member contacts, the native email field is sufficient. For Mentor contacts, two additional custom email fields (personalEmail, cbmEmailAddress) are defined in Section 3 to maintain an explicit distinction between personal and organizational email addresses. The native emailAddress field remains available on Mentor contacts but is not the primary mechanism for mentor email management." },
    { label: "Note on address:", text: " The Client Intake process collects only zip code (MN-INTAKE-DAT-014), which maps to the native addressPostalCode field. The full address composite is available for any contact type where a complete address is needed. No custom address fields are required." },
  ],

  // ── Custom fields (Section 3) ────────────────────────────────────
  // Organized as named groups. Each group gets a heading and optional
  // intro text. Fields within a group use the standard field table
  // format with rich descriptions.
  //
  // Field format:
  //   [fieldName, type, required, values, default, id, descParts]
  //
  // descParts is an array of objects:
  //   { text: "plain text" }
  //   { bold: "bold text" }
  // These are concatenated into a single description row.
  //
  // Groups are rendered in array order. Use headingLevel to control
  // the heading depth (2 = H2, 3 = H3).

  customFieldGroups: [
    {
      heading: "3.1 Shared Fields",
      headingLevel: 2,
      intro: "The following custom fields apply to all contact types. No dynamic logic visibility rules are required.",
      fields: [
        ["contactType", "multiEnum", "Yes", "Client, Mentor, Partner, Administrator, Presenter, Donor, Member", "\u2014", "EI-2a", [
          { text: "The discriminator field for the Contact entity. Determines which type-specific fields and panels are visible. A Contact may hold any combination of values. Set based on how the Contact enters the system (e.g., Mentor at MR-APPLY submission, Client at MN-INTAKE submission). " },
          { bold: "Domains: " }, { text: "All." },
        ]],
        ["preferredName", "varchar", "No", "\u2014", "\u2014", "MN-INTAKE-DAT-011", [
          { text: "The name the contact prefers to be called. Used in communications when provided. Originally defined for Client contacts; applicable to all contact types. " },
          { bold: "Domains: " }, { text: "MN, MR, CR, FU." },
        ]],
        ["linkedInProfile", "url", "No", "\u2014", "\u2014", "MN-INTAKE-DAT-015", [
          { text: "The contact\u2019s LinkedIn profile URL. Provides professional background context. Defined in MN-INTAKE for Client contacts and in MR domain for Mentor contacts. " },
          { bold: "Domains: " }, { text: "MN, MR." },
        ]],
        ["howDidYouHearAboutCbm", "enum", "No", "TBD \u2014 see CON-ISS-005", "\u2014", "MR-ISS-003", [
          { text: "How the contact learned about CBM. Recorded at point of first contact for any contact type. Supports referral channel and outreach effectiveness reporting. Values to be defined by CBM leadership. " },
          { bold: "Domains: " }, { text: "MR, CR." },
        ]],
        ["termsAndConditionsAccepted", "bool", "No", "\u2014", "\u2014", "MR-APPLY", [
          { text: "Whether the contact has accepted CBM\u2019s terms and conditions. System-populated from application or portal form submission. Admin-only; read-only for contacts. Shared for portal readiness. " },
          { bold: "Domains: " }, { text: "MR (currently), all (future). " },
          { bold: "Implementation: " }, { text: "readOnly, admin-only." },
        ]],
        ["termsAndConditionsAcceptanceDateTime", "datetime", "No", "\u2014", "\u2014", "MR-APPLY", [
          { text: "Timestamp of terms and conditions acceptance. System-populated. Admin-only; read-only for contacts. " },
          { bold: "Domains: " }, { text: "MR (currently), all (future). " },
          { bold: "Implementation: " }, { text: "readOnly, admin-only." },
        ]],
      ],
    },
    {
      heading: "3.2 CBM Internal Fields",
      headingLevel: 2,
      intro: "The following custom fields are visible when contactType has any CBM organizational member value: Mentor, Member, Administrator, or Presenter. Hidden for external relationship types: Client, Partner, Donor.",
      fields: [
        ["boardPosition", "varchar", "No", "\u2014", "\u2014", "MR-MANAGE", [
          { text: "The contact\u2019s title or role on the CBM board (e.g., Board Chair, Treasurer, Secretary). A board member must be a CBM organizational member but may hold any internal contact type. " },
          { bold: "Visibility: " }, { text: "contactType has Mentor OR Member OR Administrator OR Presenter. " },
          { bold: "Domains: " }, { text: "MR." },
        ]],
      ],
    },
    // ── Mentor-Specific: Lifecycle ──
    {
      heading: "3.3 Mentor-Specific Fields",
      headingLevel: 2,
      intro: "The following custom fields are visible only when contactType has Mentor. All fields in this section use the dynamic logic visibility rule: contactType has Mentor.",
      subheading: "Lifecycle and Status",
      fields: [
        ["mentorStatus", "enum", "Yes", "Prospect, Submitted, In Review, Provisional, Active, Paused, Inactive, Resigned, Departed, Declined", "\u2014", "MN-MATCH-DAT-015", [
          { text: "The current lifecycle stage of the mentor\u2019s relationship with CBM. Drives assignment eligibility, role-based access control, and inactivity monitoring. Only Active mentors are eligible for new assignments. " },
          { bold: "Domains: " }, { text: "MR (owner), MN (read-only reference). " },
          { bold: "Implementation: " }, { text: "audited." },
        ]],
        ["acceptingNewClients", "bool", "Yes", "\u2014", "\u2014", "MN-MATCH-DAT-016", [
          { text: "Whether the mentor is currently available for new client assignments. Relevant only when mentorStatus = Active. Mentor-editable. Set by Mentor Administrator at activation. " },
          { bold: "Domains: " }, { text: "MR, MN." },
        ]],
        ["maximumClientCapacity", "int", "Yes", "\u2014", "\u2014", "MN-MATCH-DAT-017", [
          { text: "Maximum number of simultaneous active client engagements this mentor will accept. Set by Mentor Administrator at activation. Mentor-editable. " },
          { bold: "Domains: " }, { text: "MR, MN." },
        ]],
        ["currentActiveClients", "int", "No", "\u2014", "\u2014", "MR-MANAGE", [
          { text: "Count of Engagements where this mentor is Assigned Mentor and Engagement Status is Active or Assigned. " },
          { bold: "Domains: " }, { text: "MR. " },
          { bold: "Implementation: " }, { text: "system-calculated, readOnly." },
        ]],
        ["availableCapacity", "int", "No", "\u2014", "\u2014", "MN-MATCH-DAT-018", [
          { text: "maximumClientCapacity minus currentActiveClients. Used during mentor nomination to verify capacity before assignment. " },
          { bold: "Domains: " }, { text: "MR, MN. " },
          { bold: "Implementation: " }, { text: "system-calculated, readOnly." },
        ]],
      ],
    },
    // ── Mentor-Specific: Contact and Identity ──
    {
      heading: null, // continuation of 3.3, no new heading
      subheading: "Contact and Identity",
      fields: [
        ["personalEmail", "email", "Yes", "\u2014", "\u2014", "MR-APPLY", [
          { text: "The mentor\u2019s personal email address. Used for all onboarding communications prior to CBM email activation and as a permanent contact address independent of their CBM account. " },
          { bold: "Domains: " }, { text: "MR." },
        ]],
        ["cbmEmailAddress", "email", "No", "\u2014", "\u2014", "MR-ONBOARD", [
          { text: "The mentor\u2019s assigned CBM organizational email address. Populated by Mentor Administrator during activation. Used for all ongoing mentoring communications after activation. Cleared on departure. " },
          { bold: "Domains: " }, { text: "MR. " },
          { bold: "Implementation: " }, { text: "admin-populated." },
        ]],
        ["currentEmployer", "varchar", "No", "\u2014", "\u2014", "MR-APPLY", [
          { text: "The name of the mentor\u2019s current employer or organization. " },
          { bold: "Domains: " }, { text: "MR." },
        ]],
        ["currentlyEmployed", "bool", "No", "\u2014", "\u2014", "MR-APPLY", [
          { text: "Whether the mentor was employed at the time of application. Point-in-time snapshot collected on the application form. " },
          { bold: "Domains: " }, { text: "MR." },
        ]],
        ["yearsOfBusinessExperience", "int", "No", "\u2014", "\u2014", "MR-MANAGE", [
          { text: "Total years of professional business experience. Used for mentor profile and matching. " },
          { bold: "Domains: " }, { text: "MR." },
        ]],
      ],
    },
    // ── Mentor-Specific: Profile and Matching ──
    {
      heading: null,
      subheading: "Profile and Matching",
      fields: [
        ["professionalBio", "wysiwyg", "No", "\u2014", "\u2014", "MR-APPLY", [
          { text: "Free-form description of the mentor\u2019s professional background and work experience. Used for mentor profiles and matching communications. Collected on the application form. " },
          { bold: "Domains: " }, { text: "MR." },
        ]],
        ["industrySectors", "multiEnum", "Yes", "Same as Client Org Industry Sector (20 NAICS sectors)", "\u2014", "MN-MATCH-DAT-011", [
          { text: "Industry sectors where the mentor has experience. Primary matching criterion \u2014 compared against the client\u2019s Industry Sector. Values must align with the Industry Sector field on Client Organization. " },
          { bold: "Domains: " }, { text: "MR (owner), MN (read-only reference)." },
        ]],
        ["mentoringFocusAreas", "multiEnum", "Yes", "TBD \u2014 see CON-ISS-003", "\u2014", "MN-MATCH-DAT-012", [
          { text: "Areas where the mentor can provide guidance. Primary matching criterion \u2014 compared against the client\u2019s Mentoring Focus Areas on the Engagement record. Values must align with the Engagement-level Mentoring Focus Areas field. " },
          { bold: "Domains: " }, { text: "MR (owner), MN (read-only reference)." },
        ]],
        ["skillsExpertiseTags", "multiEnum", "No", "TBD \u2014 see CON-ISS-004", "\u2014", "MN-MATCH-DAT-013", [
          { text: "Finer-grained expertise tags beyond industry sector and focus areas. Supports advanced mentor-client matching. Values to be defined by CBM leadership. " },
          { bold: "Domains: " }, { text: "MR (owner), MN (read-only reference)." },
        ]],
        ["fluentLanguages", "multiEnum", "No", "TBD \u2014 see CON-ISS-005", "\u2014", "MN-MATCH-DAT-014", [
          { text: "Languages the mentor is fluent in. Used to match clients who prefer to work in a language other than English. Values to be defined by CBM leadership. " },
          { bold: "Domains: " }, { text: "MR (owner), MN (read-only reference)." },
        ]],
        ["whyInterestedInMentoring", "wysiwyg", "No", "\u2014", "\u2014", "MR-APPLY", [
          { text: "The mentor\u2019s stated motivation for joining CBM as a volunteer mentor. Collected on the application form. " },
          { bold: "Domains: " }, { text: "MR." },
        ]],
      ],
    },
    // ── Mentor-Specific: Role Eligibility ──
    {
      heading: null,
      subheading: "Role Eligibility",
      fields: [
        ["isPrimaryMentor", "bool", "Yes", "\u2014", "Yes", "MR-MANAGE", [
          { text: "Whether this mentor is eligible for primary mentor assignments. Set by Mentor Administrator. Defaults to Yes on activation. " },
          { bold: "Domains: " }, { text: "MR." },
        ]],
        ["isCoMentor", "bool", "Yes", "\u2014", "\u2014", "MR-MANAGE", [
          { text: "Whether this mentor is eligible for co-mentor assignments. Set by Mentor Administrator. " },
          { bold: "Domains: " }, { text: "MR." },
        ]],
        ["isSubjectMatterExpert", "bool", "Yes", "\u2014", "\u2014", "MR-MANAGE", [
          { text: "Whether this mentor is eligible for subject matter expert assignments. Set by Mentor Administrator. " },
          { bold: "Domains: " }, { text: "MR." },
        ]],
      ],
    },
    // ── Mentor-Specific: Onboarding and Compliance ──
    {
      heading: null,
      subheading: "Onboarding and Compliance",
      fields: [
        ["ethicsAgreementAccepted", "bool", "No", "\u2014", "\u2014", "MR-ONBOARD", [
          { text: "Whether the mentor has accepted the current CBM ethics agreement. Set by Mentor Administrator. " },
          { bold: "Domains: " }, { text: "MR. " },
          { bold: "Implementation: " }, { text: "admin-only, readOnly for mentors." },
        ]],
        ["ethicsAgreementAcceptanceDateTime", "datetime", "No", "\u2014", "\u2014", "MR-ONBOARD", [
          { text: "Date and time of the mentor\u2019s most recent ethics agreement acceptance. Set by Mentor Administrator. " },
          { bold: "Domains: " }, { text: "MR. " },
          { bold: "Implementation: " }, { text: "admin-only." },
        ]],
        ["backgroundCheckCompleted", "bool", "No", "\u2014", "\u2014", "MR-ONBOARD", [
          { text: "Whether a background check has been completed for this mentor. " },
          { bold: "Domains: " }, { text: "MR. " },
          { bold: "Implementation: " }, { text: "admin-only, hidden from mentor." },
        ]],
        ["backgroundCheckDate", "date", "No", "\u2014", "\u2014", "MR-ONBOARD", [
          { text: "The date the background check was completed. " },
          { bold: "Domains: " }, { text: "MR. " },
          { bold: "Implementation: " }, { text: "admin-only, hidden from mentor." },
        ]],
        ["felonyConvictionDisclosure", "bool", "No", "\u2014", "\u2014", "MR-APPLY", [
          { text: "Whether the applicant disclosed a felony conviction. System-populated from the mentor application form. Protects the integrity of the review process. " },
          { bold: "Domains: " }, { text: "MR. " },
          { bold: "Implementation: " }, { text: "system-populated, admin-only, hidden from mentor after submission." },
        ]],
        ["trainingCompleted", "bool", "No", "\u2014", "\u2014", "MR-ONBOARD", [
          { text: "System-populated via learning management system integration when required training is completed. Mentor can see their own status. " },
          { bold: "Domains: " }, { text: "MR. " },
          { bold: "Implementation: " }, { text: "system-populated, readOnly." },
        ]],
        ["trainingCompletionDate", "date", "No", "\u2014", "\u2014", "MR-ONBOARD", [
          { text: "Date required training was completed. System-populated via LMS integration. " },
          { bold: "Domains: " }, { text: "MR. " },
          { bold: "Implementation: " }, { text: "system-populated, readOnly." },
        ]],
      ],
    },
    // ── Mentor-Specific: Dues ──
    {
      heading: null,
      subheading: "Dues and Financial",
      fields: [
        ["duesStatus", "enum", "No", "Unpaid, Paid, Waived", "\u2014", "MR-MANAGE", [
          { text: "The mentor\u2019s current-year dues standing. Summary field maintained by the Mentor Administrator, independent of individual Dues entity records. " },
          { bold: "Domains: " }, { text: "MR. " },
          { bold: "Implementation: " }, { text: "admin-only." },
        ]],
        ["duesPaymentDate", "date", "No", "\u2014", "\u2014", "MR-MANAGE", [
          { text: "Date of most recent dues payment. Not applicable when duesStatus = Waived. " },
          { bold: "Domains: " }, { text: "MR. " },
          { bold: "Implementation: " }, { text: "admin-only." },
        ]],
      ],
    },
    // ── Mentor-Specific: Departure ──
    {
      heading: null,
      subheading: "Departure",
      fields: [
        ["departureReason", "enum", "No", "Relocated, Career Change, Time Constraints, Personal, Other", "\u2014", "MR-DEPART", [
          { text: "Reason the mentor exited CBM. Shown only when mentorStatus = Departed. Set by Mentor Administrator at offboarding. " },
          { bold: "Domains: " }, { text: "MR. " },
          { bold: "Implementation: " }, { text: "admin-only. Dynamic logic: visible when mentorStatus = Departed." },
        ]],
        ["departureDate", "date", "No", "\u2014", "\u2014", "MR-DEPART", [
          { text: "Date the mentor formally departed. Shown only when mentorStatus = Departed. " },
          { bold: "Domains: " }, { text: "MR. " },
          { bold: "Implementation: " }, { text: "admin-only. Dynamic logic: visible when mentorStatus = Departed." },
        ]],
      ],
    },
    // ── Incomplete domain notice ──
    {
      heading: "3.4 Incomplete Domain Fields",
      headingLevel: 2,
      intro: "The following contact types have no type-specific custom fields defined yet. Additional fields are expected when their respective domain process documents are completed.",
      // Use bulletItems instead of fields for prose-style content
      bulletItems: [
        { label: "Client", text: " \u2014 No custom fields beyond the shared fields in Section 3.1. A Client-specific lifecycle field (analogous to mentorStatus) is an open issue (CON-ISS-001). Field-level detail is available from the MN Domain PRD for Client Contact identity fields, but these map to native fields (Section 2)." },
        { label: "Partner", text: " \u2014 No custom fields defined. A Partner-specific lifecycle field is an open issue (CON-ISS-002). Partner Contact fields will be defined during CR domain process definition." },
        { label: "Donor", text: " \u2014 No custom fields defined. A Donor-specific lifecycle field is an open issue (CON-ISS-003). Donor Contact fields will be defined during FU domain process definition." },
        { label: "Administrator", text: " \u2014 No type-specific custom fields anticipated beyond shared and CBM internal fields." },
        { label: "Presenter", text: " \u2014 No custom fields defined. Presenter-specific fields (if any) will be defined during CR domain process definition." },
        { label: "Member", text: " \u2014 No custom fields defined. Member-specific fields (if any) will be defined during CR domain process definition." },
      ],
    },
  ],

  // ── Relationships (Section 4) ────────────────────────────────────
  // Format: [name, relatedEntity, linkType, prdReference, domains]
  relationshipsIntro: "All relationships involving the Contact entity, compiled from all domains. Relationship implementation details (link names, labels) will be finalized during YAML generation.",
  relationships: [
    ["Contact \u2192 Account", "Account", "manyToMany", "Native relationship", "MN, CR, FU"],
    ["Assigned Mentor \u2192 Engagement", "Engagement", "oneToMany", "MN-MATCH-DAT-019", "MN"],
    ["Additional Mentors \u2192 Engagement", "Engagement", "manyToMany", "MN-ENGAGE-DAT-015", "MN"],
    ["Engagement Contacts \u2192 Engagement", "Engagement", "manyToMany", "MN-MATCH-DAT-021", "MN"],
    ["Primary Engagement Contact \u2192 Engagement", "Engagement", "oneToMany", "MN-INTAKE-DAT-020", "MN"],
    ["Mentor Attendees \u2192 Session", "Session", "manyToMany", "MN-ENGAGE-DAT-034", "MN"],
    ["Client Attendees \u2192 Session", "Session", "manyToMany", "MN-ENGAGE-DAT-035", "MN"],
    ["Mentor \u2192 Dues", "Dues", "oneToMany", "MR-MANAGE", "MR"],
    ["Requesting Mentor \u2192 SME Request", "SME Request", "oneToMany", "MR entity", "MR"],
    ["Assigned SME \u2192 SME Request", "SME Request", "oneToMany", "MR entity", "MR"],
  ],
  // Optional notes after the relationship table
  relationshipNotes: [
    { label: "Note on Primary Contact:", text: " The \u201CPrimary Contact\u201D designation (MN-INTAKE-DAT-016) is implemented as a bool on the Contact-to-Account relationship, not as a field on the Contact entity. This allows a single Contact to be the primary contact for one Account but not for another. The relationship-level implementation is defined in the Account Entity PRD." },
    { label: "Anticipated future relationships:", text: " Contact \u2192 Event Registration (CR domain), Contact \u2192 Event as Presenter (CR domain), Contact \u2192 Contribution as Donor (FU domain), Contact \u2192 Fundraising Campaign (FU domain). These will be defined when their respective domain process documents are completed." },
  ],

  // ── Dynamic logic rules (Section 5) ──────────────────────────────
  // Free-form sections. Each entry gets a heading and paragraphs.
  dynamicLogicIntro: "Dynamic logic visibility rules control which fields and panels are visible based on the contactType discriminator. Because contactType is a multiEnum, rules use the \u201Chas\u201D operator \u2014 a Contact with contactType = [Mentor, Presenter] would see both Mentor-specific and Presenter-specific fields.",
  dynamicLogicSections: [
    { heading: "5.1 CBM Internal Types", paragraphs: [
      { label: "Condition:", text: " contactType has Mentor OR contactType has Member OR contactType has Administrator OR contactType has Presenter" },
      { label: "Show:", text: " boardPosition" },
    ]},
    { heading: "5.2 Mentor (contactType has Mentor)", paragraphs: [
      { label: "Condition:", text: " contactType has Mentor" },
      { label: "Show all fields in Section 3.3:", text: " mentorStatus, acceptingNewClients, maximumClientCapacity, currentActiveClients, availableCapacity, personalEmail, cbmEmailAddress, currentEmployer, currentlyEmployed, yearsOfBusinessExperience, professionalBio, industrySectors, mentoringFocusAreas, skillsExpertiseTags, fluentLanguages, whyInterestedInMentoring, isPrimaryMentor, isCoMentor, isSubjectMatterExpert, ethicsAgreementAccepted, ethicsAgreementAcceptanceDateTime, backgroundCheckCompleted, backgroundCheckDate, felonyConvictionDisclosure, trainingCompleted, trainingCompletionDate, duesStatus, duesPaymentDate, departureReason, departureDate" },
    ]},
    { heading: "5.3 Additional Mentor Conditional Rules", paragraphs: [
      { text: "Within the Mentor-specific fields, the following fields have secondary visibility conditions:" },
    ], bullets: [
      { label: "departureReason, departureDate", text: " \u2014 visible only when mentorStatus = Departed" },
    ]},
    { heading: "5.4 Client (contactType has Client)", paragraphs: [
      { text: "No Client-specific custom fields are defined yet. When the Client lifecycle field is defined (CON-ISS-001), it will require a visibility rule: contactType has Client." },
    ]},
    { heading: "5.5 Partner (contactType has Partner)", paragraphs: [
      { text: "No Partner-specific custom fields are defined yet. When the Partner lifecycle field is defined (CON-ISS-002), it will require a visibility rule: contactType has Partner." },
    ]},
    { heading: "5.6 Donor (contactType has Donor)", paragraphs: [
      { text: "No Donor-specific custom fields are defined yet. When the Donor lifecycle field is defined (CON-ISS-003), it will require a visibility rule: contactType has Donor." },
    ]},
    { heading: "5.7 Administrator, Presenter, Member", paragraphs: [
      { text: "No type-specific custom fields are defined for these types beyond the CBM internal fields in Section 5.1. Dynamic logic rules will be added if type-specific fields are defined during CR domain process work." },
    ]},
  ],

  // ── Layout guidance (Section 6) ──────────────────────────────────
  // Free-form labeled panels
  layoutIntro: "The following panel/tab grouping is a recommendation for the Contact detail view. Final layout is determined during YAML generation. Dynamic logic hides entire panels when the relevant contactType is not present.",
  layoutPanels: [
    { name: "Overview Panel (always visible)", text: "Native identity fields: salutationName, firstName, middleName, lastName, title. Custom shared fields: contactType, preferredName, linkedInProfile, howDidYouHearAboutCbm. Native contact fields: emailAddress, phoneNumber, address composite." },
    { name: "Mentor Profile Panel (contactType has Mentor)", text: "personalEmail, cbmEmailAddress, currentEmployer, currentlyEmployed, yearsOfBusinessExperience, professionalBio." },
    { name: "Mentor Matching Panel (contactType has Mentor)", text: "industrySectors, mentoringFocusAreas, skillsExpertiseTags, fluentLanguages." },
    { name: "Mentor Status Panel (contactType has Mentor)", text: "mentorStatus, acceptingNewClients, maximumClientCapacity, currentActiveClients, availableCapacity, isPrimaryMentor, isCoMentor, isSubjectMatterExpert." },
    { name: "Mentor Onboarding Panel (contactType has Mentor)", text: "ethicsAgreementAccepted, ethicsAgreementAcceptanceDateTime, backgroundCheckCompleted, backgroundCheckDate, felonyConvictionDisclosure, trainingCompleted, trainingCompletionDate, termsAndConditionsAccepted, termsAndConditionsAcceptanceDateTime, whyInterestedInMentoring." },
    { name: "Mentor Dues Panel (contactType has Mentor)", text: "duesStatus, duesPaymentDate." },
    { name: "Mentor Departure Panel (mentorStatus = Departed)", text: "departureReason, departureDate." },
    { name: "CBM Membership Panel (CBM internal types)", text: "boardPosition." },
  ],

  // ── Implementation notes (Section 7) ─────────────────────────────
  // Each entry: { label: "N. Bold prefix:", text: "Rest of note" }
  implementationNotes: [
    { label: "1. Calculated fields:", text: " currentActiveClients is the count of Engagements where this Contact is the Assigned Mentor and Engagement Status is Active or Assigned. availableCapacity is maximumClientCapacity minus currentActiveClients. Both are system-calculated and read-only." },
    { label: "2. Field-level access control:", text: " backgroundCheckCompleted, backgroundCheckDate, and felonyConvictionDisclosure are restricted to Mentor Administrator access only and hidden from the mentor\u2019s own record view. duesStatus, duesPaymentDate, departureReason, and departureDate are admin-only. ethicsAgreementAccepted is read-only for mentors." },
    { label: "3. System-populated fields:", text: " termsAndConditionsAccepted and termsAndConditionsAcceptanceDateTime are populated from form submissions. trainingCompleted and trainingCompletionDate are populated via LMS integration. felonyConvictionDisclosure is populated from the application form. None of these fields should be manually editable by end users." },
    { label: "4. Audited fields:", text: " mentorStatus should be audited to maintain a complete transition history for compliance and reporting." },
    { label: "5. Multi-type contacts:", text: " Because contactType is multiEnum, a Contact with multiple types sees the union of all type-specific fields. The layout should group fields by type panel so the UI remains organized when multiple types are active." },
    { label: "6. Native email handling:", text: " Mentor contacts use personalEmail and cbmEmailAddress as separate custom fields rather than the native multi-email capability. The native emailAddress field remains available but is not the primary mechanism for Mentor email management. For all other contact types, the native emailAddress field is the primary email field." },
    { label: "7. Product name restriction:", text: " This document is a Level 2 Entity PRD. No specific CRM product names appear in this document. All references to platform capabilities use generic terminology. Product-specific implementation details belong in YAML program files and implementation documentation only." },
  ],

  // ── Open issues (Section 8) ──────────────────────────────────────
  // Format: [id, description]
  openIssues: [
    ["CON-ISS-001", "Client lifecycle field not yet defined. Contact type Client needs a lifecycle field analogous to mentorStatus. The lifecycle stages and field definition will be established during CR domain process definition or MN-INTAKE Entity PRD work. Carried forward from EI-ISS-004."],
    ["CON-ISS-002", "Partner lifecycle field not yet defined. The Master PRD describes partner status tracking (prospect through active). The lifecycle stages and field definition will be established during CR domain process definition. Carried forward from EI-ISS-005."],
    ["CON-ISS-003", "Donor lifecycle field not yet defined. The Master PRD describes donor/sponsor pipeline stages (Prospect, Contacted, In Discussion, Committed, Active, Lapsed, Closed). The lifecycle stages and field definition will be established during FU domain process definition. Carried forward from EI-ISS-006."],
    ["CON-ISS-004", "Incomplete domain coverage for Contact entity. The MR, CR, and FU domains have only summary-level data. This Entity PRD will require updates when those domain process documents are completed. Additional type-specific custom fields, relationships, and dynamic logic rules are expected. Carried forward from EI-ISS-008."],
    ["CON-ISS-005", "Mentoring Focus Areas: complete list of allowed values not defined. Must align between the Engagement-level field and the Mentor Contact field. Carried forward from MN-INTAKE-ISS-001."],
    ["CON-ISS-006", "Skills and Expertise Tags: values not yet defined by CBM leadership. Carried forward from MR-ISS-001."],
    ["CON-ISS-007", "Fluent Languages: values not yet defined by CBM leadership. Carried forward from MR-ISS-002."],
    ["CON-ISS-008", "How Did You Hear About CBM: dropdown values not yet defined by CBM leadership. Carried forward from MR-ISS-003."],
  ],

  // ── Decisions made (Section 9) ───────────────────────────────────
  // Format: [id, description]
  decisions: [
    ["CON-DEC-001", "Primary Contact is a bool on the Contact-to-Account relationship, not a field on the Contact entity. A single Contact can be the primary contact for one Account but not for another. Implementation details defined in the Account Entity PRD."],
    ["CON-DEC-002", "Native title field treated as shared across all contact types. No dynamic logic visibility required. Maps to Professional Title from the MR domain."],
    ["CON-DEC-003", "preferredName and linkedInProfile are shared fields, not type-specific. Applicable to all contact types."],
    ["CON-DEC-004", "Mentor email addresses implemented as two separate custom fields (personalEmail, cbmEmailAddress) rather than using the native multi-email capability. The distinction matters operationally for onboarding vs. mentoring communications and departure cleanup."],
    ["CON-DEC-005", "termsAndConditionsAccepted and termsAndConditionsAcceptanceDateTime are shared fields (not Mentor-specific) for portal readiness. Currently populated only for Mentors; will be used for all contact types when a client portal is implemented."],
    ["CON-DEC-006", "howDidYouHearAboutCbm is shared across all contact types. Both MR and CR domains reference recording how contacts heard about CBM. A single shared field supports unified referral channel reporting."],
    ["CON-DEC-007", "boardPosition is visible for CBM organizational member types (Mentor, Member, Administrator, Presenter) and hidden for external relationship types (Client, Partner, Donor). Board membership requires being a CBM organizational member."],
    ["CON-DEC-008", "Mentor Status has ten values: Prospect, Submitted, In Review, Provisional, Active, Paused, Inactive, Resigned, Departed, Declined. Prospect was added to the nine values from the MN Domain PRD based on Entity Inventory confirmation (EI-ISS-003)."],
    ["CON-DEC-009", "Client Zip Code maps to native addressPostalCode. The intake form collects only zip code, but the full native address composite is available for any contact type. No custom address field needed."],
  ],
};


// ═══════════════════════════════════════════════════════════════════════
// RENDERING ENGINE — Do not modify below this line
// ═══════════════════════════════════════════════════════════════════════

const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat,
  HeadingLevel, BorderStyle, WidthType, ShadingType,
  PageBreak, TabStopType, TabStopPosition
} = require("docx");

// ── Shared styles ──────────────────────────────────────────────────
const FONT = "Arial";
const SZ = { body: 22, small: 20, xs: 16, h1: 32, h2: 28, h3: 24, meta: 20 };
const COLORS = {
  headerBg: "1F3864",
  headerText: "FFFFFF",
  altRowBg: "F2F7FB",
  borderColor: "AAAAAA",
  titleColor: "1F3864",
  idColor: "888888",
};

const border = { style: BorderStyle.SINGLE, size: 1, color: COLORS.borderColor };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 60, bottom: 60, left: 100, right: 100 };
const descMargins = { top: 40, bottom: 80, left: 100, right: 100 };
const TABLE_WIDTH = 9360;

// ── Primitive helpers ──────────────────────────────────────────────

function r(text, opts = {}) {
  return new TextRun({ text, font: FONT, size: opts.size || SZ.body, bold: opts.bold || false, italics: opts.italics || false, color: opts.color });
}

function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: opts.after ?? 120 },
    alignment: opts.align,
    children: Array.isArray(text) ? text : [r(text, opts)],
  });
}

function heading(text, level) {
  return new Paragraph({
    heading: level,
    spacing: { before: level === HeadingLevel.HEADING_1 ? 360 : 240, after: 120 },
    children: [r(text, { bold: true, size: level === HeadingLevel.HEADING_1 ? SZ.h1 : level === HeadingLevel.HEADING_2 ? SZ.h2 : SZ.h3, color: COLORS.titleColor })],
  });
}

function labeledParagraph(obj) {
  if (obj.label) {
    return p([r(obj.label, { bold: true }), r(obj.text)]);
  }
  return p(obj.text);
}

function labeledBullet(obj) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    spacing: { after: 60 },
    children: [r(obj.label, { bold: true }), r(obj.text)],
  });
}

// ── Table helpers ──────────────────────────────────────────────────

function hdrCell(text, width) {
  return new TableCell({ borders, width: { size: width, type: WidthType.DXA }, shading: { fill: COLORS.headerBg, type: ShadingType.CLEAR }, margins: cellMargins, children: [new Paragraph({ children: [r(text, { bold: true, size: SZ.small, color: COLORS.headerText })] })] });
}

function dataCell(text, width, opts = {}) {
  return new TableCell({ borders, width: { size: width, type: WidthType.DXA }, shading: opts.shaded ? { fill: COLORS.altRowBg, type: ShadingType.CLEAR } : undefined, margins: cellMargins, columnSpan: opts.columnSpan, children: [new Paragraph({ children: [r(text, { size: opts.size || SZ.small, bold: opts.bold, color: opts.color, italics: opts.italics })] })] });
}

// ── Metadata table ─────────────────────────────────────────────────
const MC = [2800, 6560];
function metaTable(rows) {
  return new Table({ width: { size: TABLE_WIDTH, type: WidthType.DXA }, columnWidths: MC, rows: rows.map((row, i) => new TableRow({ children: [dataCell(row[0], MC[0], { shaded: i % 2 === 1, bold: true, size: SZ.small }), dataCell(row[1], MC[1], { shaded: i % 2 === 1, size: SZ.small })] })) });
}

// ── Native field table ─────────────────────────────────────────────
const NFC = [2200, 1400, 3000, 2760];
function nativeFieldTable(fields) {
  const hdr = new TableRow({ children: [hdrCell("Native Field", NFC[0]), hdrCell("Type", NFC[1]), hdrCell("PRD Name(s) / Mapping", NFC[2]), hdrCell("Referenced By", NFC[3])] });
  const rows = fields.map((f, i) => new TableRow({ children: [dataCell(f[0], NFC[0], { shaded: i % 2 === 1, bold: true, size: SZ.small }), dataCell(f[1], NFC[1], { shaded: i % 2 === 1, size: SZ.small }), dataCell(f[2], NFC[2], { shaded: i % 2 === 1, size: SZ.small }), dataCell(f[3], NFC[3], { shaded: i % 2 === 1, size: SZ.small })] }));
  return new Table({ width: { size: TABLE_WIDTH, type: WidthType.DXA }, columnWidths: NFC, rows: [hdr, ...rows] });
}

// ── Custom field table (two-row format with rich descriptions) ─────
const FC = [2200, 1100, 800, 2400, 1000, 1860];

function buildDescRuns(descParts) {
  return descParts.map(part => {
    if (part.bold) return r(part.bold, { size: SZ.small, color: COLORS.idColor, bold: true });
    return r(part.text, { size: SZ.small, color: COLORS.idColor });
  });
}

function fieldTable(fields) {
  const hdr = new TableRow({ children: [hdrCell("Field Name", FC[0]), hdrCell("Type", FC[1]), hdrCell("Required", FC[2]), hdrCell("Values", FC[3]), hdrCell("Default", FC[4]), hdrCell("ID", FC[5])] });
  const rows = [hdr];
  fields.forEach((f, i) => {
    const [name, type, required, values, defaultVal, id, descParts] = f;
    const shaded = i % 2 === 1;
    rows.push(new TableRow({ children: [dataCell(name, FC[0], { shaded, bold: true }), dataCell(type, FC[1], { shaded }), dataCell(required, FC[2], { shaded }), dataCell(values, FC[3], { shaded }), dataCell(defaultVal, FC[4], { shaded }), dataCell(id, FC[5], { shaded, size: SZ.xs, color: COLORS.idColor })] }));
    rows.push(new TableRow({ children: [new TableCell({ borders, width: { size: TABLE_WIDTH, type: WidthType.DXA }, columnSpan: 6, shading: shaded ? { fill: COLORS.altRowBg, type: ShadingType.CLEAR } : undefined, margins: descMargins, children: [new Paragraph({ children: buildDescRuns(descParts) })] })] }));
  });
  return new Table({ width: { size: TABLE_WIDTH, type: WidthType.DXA }, columnWidths: FC, rows });
}

// ── Relationship table ─────────────────────────────────────────────
const RLC = [2600, 1800, 1400, 1700, 1860];
function relTable(rels) {
  const hdr = new TableRow({ children: [hdrCell("Relationship", RLC[0]), hdrCell("Related Entity", RLC[1]), hdrCell("Link Type", RLC[2]), hdrCell("PRD Reference", RLC[3]), hdrCell("Domain(s)", RLC[4])] });
  const rows = rels.map((rel, i) => new TableRow({ children: [dataCell(rel[0], RLC[0], { shaded: i % 2 === 1, bold: true, size: SZ.small }), dataCell(rel[1], RLC[1], { shaded: i % 2 === 1, size: SZ.small }), dataCell(rel[2], RLC[2], { shaded: i % 2 === 1, size: SZ.small }), dataCell(rel[3], RLC[3], { shaded: i % 2 === 1, size: SZ.small }), dataCell(rel[4], RLC[4], { shaded: i % 2 === 1, size: SZ.small })] }));
  return new Table({ width: { size: TABLE_WIDTH, type: WidthType.DXA }, columnWidths: RLC, rows: [hdr, ...rows] });
}

// ── Two-column table (issues, decisions) ───────────────────────────
const TC = [1500, 7860];
function twoColTable(h1, h2, rows) {
  const hdr = new TableRow({ children: [hdrCell(h1, TC[0]), hdrCell(h2, TC[1])] });
  return new Table({ width: { size: TABLE_WIDTH, type: WidthType.DXA }, columnWidths: TC, rows: [hdr, ...rows.map((row, i) => new TableRow({ children: [dataCell(row[0], TC[0], { shaded: i % 2 === 1, bold: true, size: SZ.small }), dataCell(row[1], TC[1], { shaded: i % 2 === 1, size: SZ.small })] }))] });
}


// ═══════════════════════════════════════════════════════════════════════
// DOCUMENT ASSEMBLY
// ═══════════════════════════════════════════════════════════════════════

function buildContent() {
  const c = [];
  const E = ENTITY;
  const O = E.overview;

  // ── Section 1: Entity Overview ───────────────────────────────────
  c.push(heading("1. Entity Overview", HeadingLevel.HEADING_1));
  const metaRows = [
    ["CRM Entity Name", O.crmEntityName],
    ["Native / Custom", O.nativeOrCustom],
    ["Entity Type", O.entityType],
    ["Display Label (Singular)", O.labelSingular],
    ["Display Label (Plural)", O.labelPlural],
    ["Activity Stream", O.activityStream],
    ["Contributing Domains", O.contributingDomains],
  ];
  if (O.discriminatorField) {
    metaRows.push(["Discriminator Field", O.discriminatorField]);
    metaRows.push(["Discriminator Values", O.discriminatorValues]);
  }
  c.push(metaTable(metaRows));
  c.push(p(""));
  E.overviewText.forEach(text => c.push(p(text)));
  if (E.overviewNotes) E.overviewNotes.forEach(n => c.push(labeledParagraph(n)));

  // ── Section 2: Native Fields ─────────────────────────────────────
  c.push(new Paragraph({ children: [new PageBreak()] }));
  c.push(heading("2. Native Fields", HeadingLevel.HEADING_1));
  c.push(p(E.nativeFieldsIntro));
  c.push(nativeFieldTable(E.nativeFields));
  c.push(p(""));
  if (E.nativeFieldNotes) E.nativeFieldNotes.forEach(n => c.push(labeledParagraph(n)));

  // ── Section 3: Custom Fields ─────────────────────────────────────
  c.push(new Paragraph({ children: [new PageBreak()] }));
  c.push(heading("3. Custom Fields", HeadingLevel.HEADING_1));
  c.push(p("Custom fields must be created via YAML program files. Fields are organized by scope: shared fields (visible for all types, no dynamic logic required) and type-specific fields (controlled by dynamic logic visibility rules)."));

  E.customFieldGroups.forEach(group => {
    if (group.heading) {
      const lvl = group.headingLevel === 3 ? HeadingLevel.HEADING_3 : HeadingLevel.HEADING_2;
      c.push(heading(group.heading, lvl));
    }
    if (group.intro) c.push(p(group.intro));
    if (group.subheading) {
      c.push(p([r(group.subheading, { bold: true, color: COLORS.titleColor })]));
    }
    if (group.fields && group.fields.length > 0) {
      c.push(fieldTable(group.fields));
      c.push(p(""));
    }
    if (group.bulletItems) {
      group.bulletItems.forEach(item => c.push(labeledBullet(item)));
    }
  });

  // ── Section 4: Relationships ─────────────────────────────────────
  c.push(new Paragraph({ children: [new PageBreak()] }));
  c.push(heading("4. Relationships", HeadingLevel.HEADING_1));
  c.push(p(E.relationshipsIntro));
  c.push(relTable(E.relationships));
  c.push(p(""));
  if (E.relationshipNotes) E.relationshipNotes.forEach(n => c.push(labeledParagraph(n)));

  // ── Section 5: Dynamic Logic Rules ───────────────────────────────
  c.push(new Paragraph({ children: [new PageBreak()] }));
  c.push(heading("5. Dynamic Logic Rules", HeadingLevel.HEADING_1));
  c.push(p(E.dynamicLogicIntro));
  E.dynamicLogicSections.forEach(section => {
    c.push(heading(section.heading, HeadingLevel.HEADING_2));
    section.paragraphs.forEach(para => c.push(labeledParagraph(para)));
    if (section.bullets) section.bullets.forEach(b => c.push(labeledBullet(b)));
  });

  // ── Section 6: Layout Guidance ───────────────────────────────────
  c.push(new Paragraph({ children: [new PageBreak()] }));
  c.push(heading("6. Layout Guidance", HeadingLevel.HEADING_1));
  c.push(p(E.layoutIntro));
  E.layoutPanels.forEach(panel => {
    c.push(p([r(panel.name, { bold: true, color: COLORS.titleColor })]));
    c.push(p(panel.text));
  });

  // ── Section 7: Implementation Notes ──────────────────────────────
  c.push(heading("7. Implementation Notes", HeadingLevel.HEADING_1));
  E.implementationNotes.forEach(note => c.push(labeledParagraph(note)));

  // ── Section 8: Open Issues ───────────────────────────────────────
  c.push(new Paragraph({ children: [new PageBreak()] }));
  c.push(heading("8. Open Issues", HeadingLevel.HEADING_1));
  c.push(twoColTable("ID", "Issue", E.openIssues));

  // ── Section 9: Decisions Made ────────────────────────────────────
  c.push(heading("9. Decisions Made", HeadingLevel.HEADING_1));
  c.push(twoColTable("ID", "Decision", E.decisions));

  return c;
}

const content = buildContent();

const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: SZ.body } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: SZ.h1, bold: true, font: FONT, color: COLORS.titleColor }, paragraph: { spacing: { before: 360, after: 120 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: SZ.h2, bold: true, font: FONT, color: COLORS.titleColor }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: SZ.h3, bold: true, font: FONT, color: COLORS.titleColor }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }],
    }],
  },
  sections: [{
    properties: {
      page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          children: [
            r(ENTITY.orgName, { size: SZ.meta, bold: true, color: COLORS.titleColor }),
            new TextRun({ children: ["\t"], font: FONT }),
            r(`${ENTITY.entityName} Entity PRD`, { size: SZ.meta, color: COLORS.idColor }),
          ],
          tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
          spacing: { after: 0 },
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: COLORS.headerBg, space: 4 } },
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          children: [r(`Entity PRD \u2014 ${ENTITY.entityName}`, { size: SZ.xs, color: COLORS.idColor })],
          alignment: AlignmentType.CENTER,
          spacing: { before: 0 },
        })],
      }),
    },
    children: [
      p(ENTITY.orgName, { bold: true, size: 20, color: COLORS.idColor, after: 40 }),
      p(`${ENTITY.entityName} Entity PRD`, { bold: true, size: 40, color: COLORS.titleColor, after: 200 }),
      metaTable([
        ["Document Type", "Entity PRD"],
        ["Entity", `${ENTITY.overview.crmEntityName} (${ENTITY.overview.nativeOrCustom} \u2014 ${ENTITY.overview.entityType} Type)`],
        ["Implementation", ENTITY.orgName],
        ["Version", ENTITY.version],
        ["Status", ENTITY.status],
        ["Last Updated", ENTITY.lastUpdated],
        ["Source Documents", ENTITY.sourceDocuments],
      ]),
      new Paragraph({ children: [new PageBreak()] }),
      ...content,
    ],
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(ENTITY.outputFile, buffer);
  console.log(`Generated: ${ENTITY.outputFile}`);
});
