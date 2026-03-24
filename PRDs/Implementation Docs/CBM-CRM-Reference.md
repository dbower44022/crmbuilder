# CBM CRM Implementation Reference

## CRM Implementation Reference

Generated from YAML program files
  Version: 1.0
  Generated: 2026-03-23 18:35 UTC

This document defines the EspoCRM configuration required to support the requirements specified in the CBM PRD documents. It is generated automatically from the YAML program files and must not be edited manually.

---

# Introduction

This document is the authoritative implementation reference for the Cleveland Business Mentors CRM system built on EspoCRM. It defines every entity, field, layout, and configuration item required to support the requirements stated in the CBM PRD documents.

This document is generated automatically from the YAML program files used by the EspoCRM Implementation Tool. To update this document, update the YAML files and regenerate.

Sections marked 'Planned — Not Yet Implemented' describe future capability not yet supported by the deployment tool.

# Entities

## Company (Account)

| Property | Value |
| --- | --- |
| EspoCRM Entity Name | Account |
| Display Name (Singular) | Company |
| Display Name (Plural) | Companies |
| Entity Type | Native (Account) |
| Stream Enabled | No |
| Deployment Method | Field configuration only |

Represents all organizations in CBM's ecosystem — client businesses receiving mentoring, Partner organizations, CBM itself, sponsors, and vendors. A single Account entity covers all organization types, distinguished by the Account Type multi-select field which drives Dynamic Logic panel visibility. An account may hold multiple types simultaneously. Requirement: CBM-PRD-CRM-Client.docx Section 2.1, CBM-PRD-CRM-Partners.docx Section 15.1.

## Contact

| Property | Value |
| --- | --- |
| EspoCRM Entity Name | Contact |
| Display Name (Singular) | Contact |
| Display Name (Plural) | Contacts |
| Entity Type | Native (Contact) |
| Stream Enabled | No |
| Deployment Method | Field configuration only |

Extended with Partner Contact fields to support CBM's Partner Management module. Partner Contacts are individuals at Partner organizations whom CBM communicates with, invites to events, and coordinates with on joint activities. A Contact may be both a CBM Mentor and a Partner Contact — the system supports this overlap without duplication using the isPartnerContact flag alongside the existing contactType field. Requirement: CBM-PRD-CRM-Partners.docx Section 6.

## Engagement

| Property | Value |
| --- | --- |
| EspoCRM Entity Name | CEngagement |
| Display Name (Singular) | Engagement |
| Display Name (Plural) | Engagements |
| Entity Type | Custom (Base) |
| Stream Enabled | Yes |
| Deployment Method | delete_and_create |

No description provided.

## Session

| Property | Value |
| --- | --- |
| EspoCRM Entity Name | CSession |
| Display Name (Singular) | Session |
| Display Name (Plural) | Sessions |
| Entity Type | Custom (Base) |
| Stream Enabled | Yes |
| Deployment Method | delete_and_create |

No description provided.

## NPS Survey Response (NpsSurveyResponse)

| Property | Value |
| --- | --- |
| EspoCRM Entity Name | CNpsSurveyResponse |
| Display Name (Singular) | NPS Survey Response |
| Display Name (Plural) | NPS Survey Responses |
| Entity Type | Custom (Base) |
| Stream Enabled | No |
| Deployment Method | delete_and_create |

No description provided.

## Workshop

| Property | Value |
| --- | --- |
| EspoCRM Entity Name | CWorkshop |
| Display Name (Singular) | Workshop |
| Display Name (Plural) | Workshops |
| Entity Type | Custom (Base) |
| Stream Enabled | Yes |
| Deployment Method | delete_and_create |

No description provided.

## Workshop Attendance (WorkshopAttendance)

| Property | Value |
| --- | --- |
| EspoCRM Entity Name | CWorkshopAttendance |
| Display Name (Singular) | Workshop Attendance |
| Display Name (Plural) | Workshop Attendance |
| Entity Type | Custom (Base) |
| Stream Enabled | No |
| Deployment Method | delete_and_create |

No description provided.

## Dues

| Property | Value |
| --- | --- |
| EspoCRM Entity Name | CDues |
| Display Name (Singular) | Dues |
| Display Name (Plural) | Dues |
| Entity Type | Custom (Base) |
| Stream Enabled | No |
| Deployment Method | delete_and_create |

No description provided.

## Partner Agreement (PartnerAgreement)

| Property | Value |
| --- | --- |
| EspoCRM Entity Name | CPartnerAgreement |
| Display Name (Singular) | Partner Agreement |
| Display Name (Plural) | Partner Agreements |
| Entity Type | Custom (Base) |
| Stream Enabled | No |
| Deployment Method | delete_and_create |

Tracks formal written agreements between CBM and a Partner organization. A Partner may have more than one agreement on file over time (e.g., an original MOU and a subsequent renewal). All agreements are retained for historical reference even when superseded. Agreement documents are restricted to management-level access — liaisons and mentors without management access cannot view or download agreement attachments. Requirement: CBM-PRD-CRM-Partners.docx Section 7.

## Client-Partner Association (ClientPartnerAssociation)

| Property | Value |
| --- | --- |
| EspoCRM Entity Name | CClientPartnerAssociation |
| Display Name (Singular) | Client-Partner Association |
| Display Name (Plural) | Client-Partner Associations |
| Entity Type | Custom (Base) |
| Stream Enabled | No |
| Deployment Method | delete_and_create |

Junction entity linking a Client Account to a Partner Account. Enables CBM to track which clients belong to each Partner's population, which is the foundation for all Partner-specific analytics reporting. A client may be associated with multiple Partners simultaneously — geographic overlap is common in Northeast Ohio. Associations are established at intake when the client indicates a referral source or partnership program, and persist unless explicitly removed. Detailed client-level data shared with Partners may require client consent; aggregate analytics may be provided without individual consent. Requirement: CBM-PRD-CRM-Partners.docx Section 8.

## Partner Activity (PartnerActivity)

| Property | Value |
| --- | --- |
| EspoCRM Entity Name | CPartnerActivity |
| Display Name (Singular) | Partner Activity |
| Display Name (Plural) | Partner Activities |
| Entity Type | Custom (Base) |
| Stream Enabled | Yes |
| Deployment Method | delete_and_create |

Records joint activities and events between CBM and a Partner organization. Covers the full spectrum of Partner engagement: CBM-hosted events where a Partner was invited, co-hosted events, joint workshops or programs, co-developed content, coordination meetings, and other activities. Used by the assigned liaison to maintain a complete activity log for each Partner, and to produce the portfolio-level reporting CBM leadership needs on partnership engagement frequency and depth. This is CBM's first structured event tracking capability — individual contact attendees are tracked to know which specific Partner contacts were present at each activity. Requirement: CBM-PRD-CRM-Partners.docx Section 10.

# Fields

## Company (Account)

| Field Name | Internal Name | Type | Required | Category | Description | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| — Business Identity — |  |  |  |  |  |  |
| Organization Type | `cOrganizationType` | Enum | Yes | Business Identity | Distinguishes for-profit businesses from nonprofits. Drives reporting segmentation and determines which intake fields are relevant. Required at intake. Requirement: CBM-PRD-CRM-Client.docx Section 3.1 | Values: For-Profit \| Non-Profit |
| Account Type | `cAccountType` | Multi-select | Yes | Business Identity | Multi-select classification of the account's role in CBM's ecosystem. An account may hold more than one type simultaneously — for example, a Partner organization that is also a mentoring client would ... | Values: Client Company \| Partner \| Mentoring Company \| Sponsor \| Vendor |
| Business Stage | `cBusinessStage` | Enum | Yes | Business Identity | Indicates the maturity stage of the client's business at the time of intake. Used for mentor matching — some mentors specialize in early-stage businesses — and for funder reporting on client demograph... | Values: Pre-Startup \| Startup \| Early Stage \| Growth Stage \| Established |
| — Business Classification — |  |  |  |  |  |  |
| NAICS Sector | `cNaicsSector` | Enum | Yes | Business Classification | Top-level federal industry classification (20 sectors). Used for mentor-client matching — mentors specify which sectors they serve. Also used for funder reporting on industry distribution of clients s... | See Appendix A |
| NAICS Subsector | `cNaicsSubsector` | Enum | Yes | Business Classification | 3-digit NAICS subsector providing more specific industry classification within the selected sector. Approximately 100 values aligned to the 2022 federal standard. Used for detailed funder reporting an... | See Appendix A |
| — Mentoring Context — |  |  |  |  |  |  |
| Mentoring Focus Areas | `cMentoringFocusAreas` | Multi-select | Yes | Mentoring Context | The specific business areas where the client is seeking mentoring support. Multi-select because clients often need help across multiple domains. Used for mentor matching — mentors specify which focus ... | See Appendix A |
| Mentoring Needs Description | `cMentoringNeedsDescription` | Rich Text | Yes | Mentoring Context | Free-form description of what the client is seeking from CBM mentoring. Collected on the intake form and used by the admin during mentor matching to understand context beyond the structured focus area... | — |
| — Business Detail — |  |  |  |  |  |  |
| Business Description | `cBusinessDescription` | Rich Text | No | Business Detail | Narrative overview of the client's business — what they do, who they serve, and their business model. Populated post-assignment by the assigned mentor during initial discovery sessions. Requirement: C... | — |
| Time in Operation | `cTimeInOperation` | Enum | No | Business Detail | How long the business has been operating. Used alongside Business Stage for funder reporting on client maturity. Ranges are intentionally broad to reduce friction at intake. Requirement: CBM-PRD-CRM-C... | Values: Not yet started \| Less than 1 year \| 1 - 2 years \| 3 - 5 years \| 6 - 10 years \| More than 10 years |
| Current Team Size | `cCurrentTeamSize` | Integer | No | Business Detail | Total number of people currently working in the business including owners, full-time, and part-time employees. Used for funder reporting on job creation and retention impact. Requirement: CBM-PRD-CRM-... | Min: 0 |
| Revenue Range | `cRevenueRange` | Enum | No | Business Detail | Annual revenue bracket. Collected post-assignment as part of the business profile. Used for funder reporting and for segmenting clients by business maturity. Ranges rather than exact figures reduce cl... | See Appendix A |
| Funding Situation | `cFundingSituation` | Rich Text | No | Business Detail | Description of the client's current funding sources, capital needs, and financing history. Populated post-assignment. Helps the mentor understand financial constraints and identify appropriate capital... | — |
| Current Challenges | `cCurrentChallenges` | Rich Text | No | Business Detail | The primary obstacles the client is currently facing in their business. Populated post-assignment during discovery. Guides the mentor's focus areas and session planning. Requirement: CBM-PRD-CRM-Clien... | — |
| Goals and Objectives | `cGoalsAndObjectives` | Rich Text | No | Business Detail | The client's stated goals for their business over the next 1-3 years. Populated post-assignment. Used to define engagement success criteria and measure outcomes at close. Requirement: CBM-PRD-CRM-Clie... | — |
| Desired Outcomes (6-12 Months) | `cDesiredOutcomes` | Rich Text | No | Business Detail | Specific outcomes the client hopes to achieve within the near-term mentoring period. More concrete than Goals and Objectives. Used to set engagement milestones and evaluate progress at NPS survey poin... | — |
| Previous Mentoring/Advisory Experience | `cPreviousMentoringExperience` | Rich Text | No | Business Detail | Summary of any prior mentoring, coaching, or advisory relationships the client has had. Helps the mentor calibrate their approach and avoid repeating work already done with previous advisors. Requirem... | — |
| — Professional Advisors — |  |  |  |  |  |  |
| Current Professional Advisors | `cCurrentProfessionalAdvisors` | Multi-select | No | Professional Advisors | The professional advisors currently supporting the client's business. Helps the mentor understand the client's existing support network and coordinate rather than duplicate advice. Multi-select becaus... | See Appendix A |
| — Business Registration — |  |  |  |  |  |  |
| Registered with State | `cRegisteredWithState` | Boolean | No | Business Registration | Whether the business is formally registered with the state. Gates the display of all registration detail fields via Dynamic Logic. Pre-startup businesses may not yet be registered. Required for funder... | Default: False |
| State of Registration | `cStateOfRegistration` | Enum | No | Business Registration | The US state where the business is officially registered. Visible only when Registered with State = Yes (Dynamic Logic). Most CBM clients will be registered in Ohio. Requirement: CBM-PRD-CRM-Client.do... | See Appendix A |
| Legal Business Structure | `cLegalBusinessStructure` | Enum | No | Business Registration | The legal form of the business entity. Visible only when Registered with State = Yes. Relevant for mentoring advice on liability, taxation, and growth structure. Requirement: CBM-PRD-CRM-Client.docx S... | See Appendix A |
| EIN on File | `cEinOnFile` | Boolean | No | Business Registration | Whether CBM has the business's Employer Identification Number on file. Visible only when Registered with State = Yes. Required for certain grant programs and funder compliance. Requirement: CBM-PRD-CR... | Default: False |
| Date of Formation | `cDateOfFormation` | Date | No | Business Registration | The official date the business was registered with the state. Visible only when Registered with State = Yes. Used to calculate time in operation and for funder reporting. Requirement: CBM-PRD-CRM-Clie... | — |
| Registered Agent | `cRegisteredAgent` | Boolean | No | Business Registration | Whether the business has designated a registered agent for state compliance purposes. Visible only when Registered with State = Yes. Indicates compliance maturity. Requirement: CBM-PRD-CRM-Client.docx... | Default: False |
| EIN Number | `cEinNumber` | Text | No | Business Registration | The business's 9-digit Employer Identification Number (format: XX-XXXXXXX). Restricted field — visible to Admin and Primary Mentor roles only. Not collected on the intake form; mentor-populated after ... | Max length: 20 |
| — Partner Profile — |  |  |  |  |  |  |
| Partner Type(s) | `cPartnerTypes` | Multi-select | Yes | Partner Profile | Classifies the nature of CBM's relationship with this Partner. Multi-select — a Partner may hold more than one type simultaneously. Referral Partner: refers clients to CBM. Co-Delivery Partner: collab... | Values: Referral Partner \| Co-Delivery Partner \| Funding/Sponsorship Partner \| Resource Partner |
| Partner Status | `cPartnerStatus` | Enum | Yes | Partner Profile | The current state of CBM's relationship with this Partner. Prospect: known but not yet formally engaged. Active: current working partner with ongoing engagement. Lapsed: engagement has slowed or stopp... | Values: Prospect \| Active \| Lapsed \| Inactive; Default: Prospect |
| Partnership Start Date | `cPartnershipStartDate` | Date | No | Partner Profile | The date the partnership was formally established. Optional for Prospects; required when status moves to Active. Used to calculate partnership tenure for reporting and to track milestone anniversaries... | — |
| Public Announcement Allowed | `cPublicAnnouncementAllowed` | Boolean | No | Partner Profile | Whether CBM may publicly announce or reference this partnership in its marketing, website, social media, and communications. Defaults to No — must be explicitly set to Yes by the admin before any publ... | Default: False |
| Geographic Service Area | `cGeographicServiceArea` | Multi-select | No | Partner Profile | The geographic territory or communities the Partner primarily serves. Used to identify Partners with overlap in CBM's service areas and to filter the Partner directory by geography for liaison outreac... | See Appendix A |
| Target Population | `cTargetPopulation` | Multi-select | No | Partner Profile | The specific community segment or business population the Partner focuses on. Used for mentor-client matching referrals and to identify Partners serving populations aligned with a specific client's ba... | See Appendix A |
| Social Media | `cSocialMedia` | Text | No | Partner Profile | Links to the Partner's LinkedIn, Facebook, or other relevant social media profiles. Stored as a text field — enter each URL on a separate line. Used by liaisons for social media engagement and to shar... | Max length: 500 |
| — Partner Notes — |  |  |  |  |  |  |
| Partner Notes | `cPartnerNotes` | Rich Text | No | Partner Notes | General notes on the partner relationship, key milestones, and relevant context. Used by the assigned liaison to record summaries of conversations, relationship developments, status change explanation... | — |

## Contact

| Field Name | Internal Name | Type | Required | Category | Description | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| — General — |  |  |  |  |  |  |
| Middle Name | `cMiddleName` | Text | No | — | — | Max length: 100 |
| Preferred Name | `cPreferredName` | Text | No | — | — | Max length: 150 |
| LinkedIn Profile | `cLinkedInProfile` | URL | No | — | — | — |
| Contact Type | `cContactType` | Enum | Yes | — | — | Values: Mentor \| Client |
| Personal Email | `cPersonalEmail` | Email | No | — | — | — |
| CBM Gmail Address | `cCbmGmailAddress` | Email | No | — | — | Read-only. |
| Professional Title | `cProfessionalTitle` | Text | No | — | — | Max length: 150 |
| Current Employer | `cCurrentEmployer` | Text | No | — | — | Max length: 255 |
| Currently Employed | `cCurrentlyEmployed` | Boolean | No | — | — | Default: False |
| Years of Business Experience | `cYearsOfBusinessExperience` | Integer | No | — | — | Min: 0 |
| Professional Bio / Work Experience | `cProfessionalBio` | Rich Text | No | — | — | — |
| NAICS Sectors | `cNaicsSectors` | Multi-select | Yes | — | — | See Appendix A |
| Mentoring Focus Areas | `cMentoringFocusAreas` | Multi-select | Yes | — | — | See Appendix A |
| Skills & Expertise Tags | `cSkillsAndExpertiseTags` | Multi-select | No | — | — | See Appendix A |
| Fluent Languages | `cFluentLanguages` | Multi-select | No | — | — | See Appendix A |
| Why Interested in Mentoring | `cWhyInterestedInMentoring` | Rich Text | No | — | — | — |
| How Did You Hear About CBM | `cHowDidYouHearAboutCbm` | Enum | No | — | — | See Appendix A |
| Is Mentor | `cIsMentor` | Boolean | No | — | — | Default: False |
| Is Co-Mentor | `cIsCoMentor` | Boolean | No | — | — | Default: False |
| Is SME | `cIsSme` | Boolean | No | — | — | Default: False |
| Mentor Status | `cMentorStatus` | Enum | Yes | — | — | Values: Submitted \| Provisional \| Declined \| Active \| Inactive \| Departed |
| Accepting New Clients | `cAcceptingNewClients` | Boolean | No | — | — | Default: True |
| Maximum Client Capacity | `cMaximumClientCapacity` | Integer | Yes | — | — | Min: 0 |
| Current Active Clients | `cCurrentActiveClients` | Integer | No | — | — | Read-only.; Min: 0 |
| Available Capacity | `cAvailableCapacity` | Integer | No | — | — | Read-only.; Min: 0 |
| Ethics Agreement Accepted | `cEthicsAgreementAccepted` | Boolean | No | — | — | Read-only.; Default: False |
| Ethics Agreement Acceptance Date/Time | `cEthicsAgreementAcceptanceDateTime` | Date/Time | No | — | — | Read-only. |
| Terms & Conditions Accepted | `cTermsAndConditionsAccepted` | Boolean | No | — | — | Read-only.; Default: False |
| Terms & Conditions Acceptance Date/Time | `cTermsAndConditionsAcceptanceDateTime` | Date/Time | No | — | — | Read-only. |
| Background Check Completed | `cBackgroundCheckCompleted` | Boolean | No | — | — | Default: False |
| Background Check Date | `cBackgroundCheckDate` | Date | No | — | — | — |
| Felony Conviction | `cFelonyConviction` | Boolean | No | — | — | Default: False |
| Moodle Training Completed | `cMoodleTrainingCompleted` | Boolean | No | — | — | Read-only.; Default: False |
| Moodle Completion Date | `cMoodleCompletionDate` | Date | No | — | — | Read-only. |
| Dues Status | `cDuesStatus` | Enum | No | — | — | Values: Unpaid \| Paid \| Waived |
| Dues Payment Date | `cDuesPaymentDate` | Date | No | — | — | — |
| Departure Reason | `cDepartureReason` | Enum | No | — | — | Values: Relocated \| Career Change \| Time Constraints \| Personal \| Other |
| Departure Date | `cDepartureDate` | Date | No | — | — | — |
| Role at Business | `cRoleAtBusiness` | Text | No | — | — | Max length: 150 |
| Primary Contact | `cIsPrimaryContact` | Boolean | No | — | — | Default: True |
| Zip Code | `cZipCode` | Text | No | — | — | Max length: 20 |
| — Partner Contact — |  |  |  |  |  |  |
| Is Partner Contact | `cIsPartnerContact` | Boolean | No | Partner Contact | Flags this contact as a representative of a Partner organization. When true, shows the Partner Contact fields panel via Dynamic Logic. Can be true simultaneously with contactType = Mentor (for CBM men... | Default: False |
| Birthdate | `cBirthdate` | Date | No | Partner Contact | Contact's date of birth. Used to recognize birthdays and strengthen the Partner relationship through personal outreach. Optional. Stored securely and accessible to the assigned liaison and admin only.... | — |
| Primary Contact For | `cPrimaryContactFor` | Multi-select | No | Partner Contact | Designates the function(s) for which this individual is the primary point of contact at their Partner organization. A Partner may have different primary contacts for different functions — e.g., one pe... | Values: Referrals \| Events \| Billing \| General \| Agreements |
| Is CBM Mentor | `cIsCbmMentor` | Boolean | No | Partner Contact | Indicates that this Partner Contact is also a CBM Mentor. When true, the admin should link this Contact record to the corresponding Mentor record or confirm they are the same record. Prevents duplicat... | Default: False |
| Partner Contact Notes | `cPartnerContactNotes` | Rich Text | No | Partner Contact | Notes specific to this individual in their capacity as a Partner Contact. Used by the liaison to capture relationship context, communication history summaries, and key background about this person. Se... | — |

## Engagement

| Field Name | Internal Name | Type | Required | Category | Description | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Status | `cStatus` | Enum | Yes | — | — | See Appendix A; Default: Submitted |
| Start Date | `cStartDate` | Date | No | — | — | Read-only. |
| Close Date | `cCloseDate` | Date | No | — | — | Read-only. |
| Mentor Assigned Date | `cMentorAssignedDate` | Date | No | — | — | Read-only. |
| Meeting Cadence | `cMeetingCadence` | Enum | Yes | — | — | Values: Weekly \| Bi-Weekly \| Monthly \| As Needed |
| Engagement Close Reason | `cEngagementCloseReason` | Enum | No | — | — | Values: Goals Achieved \| Client Withdrew \| Inactive / No Response \| Other |
| Total Sessions | `cTotalSessions` | Integer | No | — | — | Read-only.; Min: 0 |
| Total Sessions (Last 30 Days) | `cTotalSessionsLast30Days` | Integer | No | — | — | Read-only.; Min: 0 |
| Last Session Date | `cLastSessionDate` | Date | No | — | — | Read-only. |
| Total Session Hours | `cTotalSessionHours` | Decimal | No | — | — | Read-only.; Min: 0 |
| Next Session Date/Time | `cNextSessionDateTime` | Date/Time | No | — | — | — |

## Session

| Field Name | Internal Name | Type | Required | Category | Description | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Session Date/Time | `cSessionDateTime` | Date/Time | Yes | — | — | — |
| Duration (minutes) | `cDuration` | Integer | Yes | — | — | Min: 1 |
| Session Type | `cSessionType` | Enum | Yes | — | — | Values: In-Person \| Video Call \| Phone Call |
| Meeting Location Type | `cMeetingLocationType` | Enum | No | — | — | Values: CBM Office \| Client's Place of Business \| Other |
| Location Details | `cLocationDetails` | Text | No | — | — | Max length: 255 |
| Topics Covered | `cTopicsCovered` | Multi-select | No | — | — | See Appendix A |
| Topics Covered Notes | `cTopicsCoveredNotes` | Rich Text | No | — | — | — |
| Mentor Notes | `cMentorNotes` | Rich Text | No | — | — | — |
| Next Steps | `cNextSteps` | Rich Text | No | — | — | — |
| New Business Started | `cNewBusinessStarted` | Boolean | No | — | — | Default: False |
| Next Session Date/Time | `cNextSessionDateTime` | Date/Time | No | — | — | — |

## NPS Survey Response (NpsSurveyResponse)

| Field Name | Internal Name | Type | Required | Category | Description | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Survey Trigger | `cSurveyTrigger` | Enum | No | — | — | Values: 2nd Session \| Every 5 Sessions \| Engagement Close; Read-only. |
| Survey Date/Time | `cSurveyDateTime` | Date/Time | No | — | — | Read-only. |
| NPS Score | `cNpsScore` | Integer | Yes | — | — | Range: 0–10 |
| Did CBM Help You? | `cDidCbmHelpYou` | Boolean | Yes | — | — | — |
| I Would Return to See This Mentor Again | `cWouldReturnToMentor` | Integer | Yes | — | — | Range: 1–5 |
| Mentor Listened and Understood My Needs | `cMentorListenedAndUnderstood` | Integer | Yes | — | — | Range: 1–5 |
| How Could CBM Better Meet Your Needs? | `cImprovementFeedback` | Rich Text | No | — | — | — |

## Workshop

| Field Name | Internal Name | Type | Required | Category | Description | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Title | `cTitle` | Text | Yes | — | — | Max length: 255 |
| Date/Time | `cWorkshopDateTime` | Date/Time | Yes | — | — | — |
| Topic/Category | `cTopicCategory` | Enum | Yes | — | — | See Appendix A |
| Presenter | `cPresenter` | Text | No | — | — | Max length: 255 |
| Location | `cLocation` | Text | No | — | — | Max length: 255 |
| Description | `cWorkshopDescription` | Rich Text | No | — | — | — |
| Maximum Capacity | `cMaximumCapacity` | Integer | No | — | — | Min: 0 |
| Status | `cStatus` | Enum | Yes | — | — | Values: Scheduled \| Completed \| Cancelled; Default: Scheduled |

## Workshop Attendance (WorkshopAttendance)

| Field Name | Internal Name | Type | Required | Category | Description | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Attendance Date | `cAttendanceDate` | Date | No | — | — | Read-only. |
| Attended | `cAttended` | Boolean | Yes | — | — | Default: True |

## Dues

| Field Name | Internal Name | Type | Required | Category | Description | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Billing Year | `cBillingYear` | Integer | Yes | — | — | Min: 2000 |
| Amount Due | `cAmountDue` | Currency | Yes | — | — | — |
| Invoice Date | `cInvoiceDate` | Date | No | — | — | — |
| Payment Date | `cPaymentDate` | Date | No | — | — | — |
| Payment Method | `cPaymentMethod` | Enum | No | — | — | Values: Stripe \| Waived \| Other |
| Notes | `cNotes` | Rich Text | No | — | — | — |

## Partner Agreement (PartnerAgreement)

| Field Name | Internal Name | Type | Required | Category | Description | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| — Agreement Details — |  |  |  |  |  |  |
| Agreement Type | `cAgreementType` | Enum | Yes | Agreement Details | Categorizes the type of formal agreement in place. MOU: Memorandum of Understanding — a non-binding statement of intent and shared goals. Partnership Agreement: a binding agreement defining terms, res... | Values: Memorandum of Understanding (MOU) \| Partnership Agreement \| Letter of Intent \| Other |
| Creation Date | `cCreationDate` | Date | Yes | Agreement Details | The date the agreement was created or signed. Required. Used as the primary sort field on the Partner Agreements list view and for tracking agreement history over time. Requirement: CBM-PRD-CRM-Partne... | — |
| Expiration / Renewal Date | `cExpirationRenewalDate` | Date | No | Agreement Details | The date the agreement expires or is due for renewal. Optional — some agreements (e.g., MOUs) may not have a formal expiration. Used in the CBM internal portfolio dashboard to surface agreements expir... | — |
| — Agreement Document — |  |  |  |  |  |  |
| Agreement Document URL | `cAgreementDocumentUrl` | URL | No | Agreement Document | URL to the signed agreement document stored in Google Drive or another document management system. Used as an alternative to a native EspoCRM file attachment when direct file upload is not available o... | — |
| — Notes — |  |  |  |  |  |  |
| Notes | `cNotes` | Rich Text | No | Notes | Any relevant notes about the agreement — context for the agreement's creation, key provisions or commitments referenced in the document, renewal history, or any exceptions to standard terms. Admin and... | — |

## Client-Partner Association (ClientPartnerAssociation)

| Field Name | Internal Name | Type | Required | Category | Description | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Association Type | `cAssociationType` | Enum | No | Association Details | How the client is connected to the Partner organization. Referred By: the Partner referred this client to CBM. Serves Same Population: the Partner serves the same community segment as this client, eve... | Values: Referred By \| Serves Same Population \| Program Participant \| Other |
| Notes | `cNotes` | Text | No | Association Details | Brief context about why this association exists — e.g., the name of the program the client participates in, how the referral was made, or any other relevant background. Optional. Requirement: CBM-PRD-... | Max length: 500 |

## Partner Activity (PartnerActivity)

| Field Name | Internal Name | Type | Required | Category | Description | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| — Activity Details — |  |  |  |  |  |  |
| Activity Name | `cActivityName` | Text | Yes | Activity Details | Name or title of the activity or event. Required. Should be descriptive enough to distinguish similar activities (e.g., "Q1 2026 Liaison Check-In with SBDC" vs. "Q2 2026 Co-Hosted Workshop — Marketing... | Max length: 255 |
| Activity Type | `cActivityType` | Enum | Yes | Activity Details | Classifies the nature of the activity. CBM-Hosted Event: a CBM event to which the Partner was invited or attended. Co-Hosted Event: jointly organized and/or funded by both CBM and the Partner. Joint W... | Values: CBM-Hosted Event \| Co-Hosted Event \| Joint Workshop / Program \| Co-Developed Content \| Meeting / Coordination Call \| Other |
| Date | `cActivityDate` | Date | Yes | Activity Details | Date the activity occurred or is scheduled to occur. Required. Primary sort field on the Partner Activities list view (descending — most recent first). Used by CBM leadership to identify Partners with... | — |
| — Activity Content — |  |  |  |  |  |  |
| Description | `cActivityDescription` | Rich Text | No | Activity Content | Description of the activity — its purpose, agenda, and any outcomes or decisions. Used by the liaison to document what occurred and to provide context for future reference when reviewing the Partner's... | — |
| Notes | `cActivityNotes` | Rich Text | No | Activity Content | Additional notes or follow-up items arising from the activity. Used for action items, next steps, and any context not captured in the Activity Description field. Requirement: CBM-PRD-CRM-Partners.docx... | — |

# Layouts

## Company (Account)

### Detail View

**Panel 1: Partner Profile (Tab: Partner) — visible when accountType = Partner**

Partner-specific identity and classification fields. Visible only when Account Type includes Partner.

  Profile: Partner Type(s), Partner Status, Partnership Start Date, Public Announcement Allowed, Geographic Service Area, Target Population, Social Media

  Notes: Partner Notes

## Contact

### Detail View

**Panel 1: Partner Contact (Tab: Partner) — visible when isPartnerContact = True**

Partner Contact-specific fields. Visible only when Is Partner Contact = true. Independent of the Mentor/Client contact type — a person can be both a CBM Mentor and a Partner Contact simultaneously.

  Partner Contact: Is Partner Contact, Birthdate, Primary Contact For, Is CBM Mentor, Partner Contact Notes

## Partner Agreement (PartnerAgreement)

### Detail View

**Panel 1: Agreement Details (Tab: Details)**

Core agreement fields. Access restricted to management-level users — liaisons and mentors without management access cannot view or download agreement records.

  Fields: agreementType, creationDate, expirationRenewalDate

**Panel 2: Agreement Document (Tab: Document)**

Link to or attachment of the signed agreement document.

  Document: Agreement Document URL

**Panel 3: Notes (Tab: Notes)**

Admin notes on the agreement context and history.

  Notes: Notes

### List View

| # | Field | Width |
| --- | --- | --- |
| 1 | name | 25% |
| 2 | agreementType | 25% |
| 3 | creationDate | 18% |
| 4 | expirationRenewalDate | 18% |
| 5 | agreementDocumentUrl | 14% |

## Client-Partner Association (ClientPartnerAssociation)

### Detail View

**Panel 1: Association Details (Tab: Details)**

Association classification and context. The Client and Partner links are managed as relationship fields.

  Fields: associationType, notes

### List View

| # | Field | Width |
| --- | --- | --- |
| 1 | name | 30% |
| 2 | associationType | 25% |
| 3 | notes | 45% |

## Partner Activity (PartnerActivity)

### Detail View

**Panel 1: Activity Details (Tab: Details)**

Core activity logistics — what, what type, and when.

  Fields: activityName, activityType, activityDate

**Panel 2: Activity Content (Tab: Content)**

Description of the activity and follow-up notes.

  Content: Description, Notes

### List View

| # | Field | Width |
| --- | --- | --- |
| 1 | activityDate | 12% |
| 2 | activityName | 30% |
| 3 | activityType | 25% |
| 4 | name | 33% |

# Views (List Views)

> ⚠️ **Status: Defined in YAML — Implemented**

## Partner Agreement (PartnerAgreement)

| # | Field | Width |
| --- | --- | --- |
| 1 | name | 25% |
| 2 | agreementType | 25% |
| 3 | creationDate | 18% |
| 4 | expirationRenewalDate | 18% |
| 5 | agreementDocumentUrl | 14% |

## Client-Partner Association (ClientPartnerAssociation)

| # | Field | Width |
| --- | --- | --- |
| 1 | name | 30% |
| 2 | associationType | 25% |
| 3 | notes | 45% |

## Partner Activity (PartnerActivity)

| # | Field | Width |
| --- | --- | --- |
| 1 | activityDate | 12% |
| 2 | activityName | 30% |
| 3 | activityType | 25% |
| 4 | name | 33% |

# Filters (Search Presets)

> ⚠️ **Planned — Not Yet Implemented**

This section will define the named search presets (saved views) configured in EspoCRM for each entity. Search presets allow administrators and mentors to quickly access commonly-used filtered views of CRM data.

Search preset definitions will be added to the YAML program files in a future release of the implementation tool.

# Relationships

> ⚠️ **Planned — Not Yet Implemented**

This section will define the relationships between entities — the links that allow EspoCRM to connect related records across entity types.

Planned relationships include:
  • Account (Company) → Contact (one-to-many)
  • Account (Company) → Engagement (one-to-many)
  • Engagement → Contact / Assigned Mentor (many-to-one)
  • Engagement → Session (one-to-many)
  • Engagement → NPS Survey Response (one-to-many)
  • Workshop → Workshop Attendance (one-to-many)
  • Contact → Workshop Attendance (one-to-many)
  • Contact → Dues (one-to-many)

# Processes (Dynamic Logic & Automation)

> ⚠️ **Partially Defined — Not Yet Implemented by Tool**

This section defines conditional field behavior (Dynamic Logic) and automated field-setting rules (Entity Formula Scripts) configured in EspoCRM.

| Entity | Trigger | Condition | Action |
| --- | --- | --- | --- |
| Contact | Display | Contact Type = Mentor | Show Mentor panels |
| Contact | Display | Contact Type = Client | Show Client Details panel |
| Contact | Display | Mentor Status = Departed | Show Departure Reason, Departure Date |
| Session | Display | Session Type = In-Person | Show Meeting Location Type |
| Session | Display | Meeting Location Type = Other | Show Location Details |
| Account | Display | Registered with State = Yes | Show registration fields |
| Engagement | On Save | Status changed to Assigned AND Mentor Assigned Date is empty | Set Mentor Assigned Date = today |

# Appendix A — Enum Value Reference

## Company (Account)

### NAICS Sector

• 11 - Agriculture, Forestry, Fishing

• 21 - Mining, Quarrying, Oil & Gas

• 22 - Utilities

• 23 - Construction

• 31-33 - Manufacturing

• 42 - Wholesale Trade

• 44-45 - Retail Trade

• 48-49 - Transportation & Warehousing

• 51 - Information

• 52 - Finance & Insurance

• 53 - Real Estate

• 54 - Professional, Scientific & Technical

• 55 - Management of Companies

• 56 - Administrative & Support Services

• 61 - Educational Services

• 62 - Health Care & Social Assistance

• 71 - Arts, Entertainment & Recreation

• 72 - Accommodation & Food Services

• 81 - Other Services

• 92 - Public Administration

### NAICS Subsector

• 111 - Crop Production

• 112 - Animal Production and Aquaculture

• 113 - Forestry and Logging

• 114 - Fishing, Hunting and Trapping

• 115 - Support Activities for Agriculture and Forestry

• 211 - Oil and Gas Extraction

• 212 - Mining (except Oil and Gas)

• 213 - Support Activities for Mining

• 221 - Utilities

• 236 - Construction of Buildings

• 237 - Heavy and Civil Engineering Construction

• 238 - Specialty Trade Contractors

• 311 - Food Manufacturing

• 312 - Beverage and Tobacco Product Manufacturing

• 313 - Textile Mills

• 314 - Textile Product Mills

• 315 - Apparel Manufacturing

• 316 - Leather and Allied Product Manufacturing

• 321 - Wood Product Manufacturing

• 322 - Paper Manufacturing

• 323 - Printing and Related Support Activities

• 324 - Petroleum and Coal Products Manufacturing

• 325 - Chemical Manufacturing

• 326 - Plastics and Rubber Products Manufacturing

• 327 - Nonmetallic Mineral Product Manufacturing

• 331 - Primary Metal Manufacturing

• 332 - Fabricated Metal Product Manufacturing

• 333 - Machinery Manufacturing

• 334 - Computer and Electronic Product Manufacturing

• 335 - Electrical Equipment, Appliance, and Component Manufacturing

• 336 - Transportation Equipment Manufacturing

• 337 - Furniture and Related Product Manufacturing

• 339 - Miscellaneous Manufacturing

• 423 - Merchant Wholesalers, Durable Goods

• 424 - Merchant Wholesalers, Nondurable Goods

• 425 - Wholesale Trade Agents and Brokers

• 441 - Motor Vehicle and Parts Dealers

• 444 - Building Material and Garden Equipment and Supplies Dealers

• 445 - Food and Beverage Retailers

• 449 - Furniture, Home Furnishings, Electronics, and Appliance Retailers

• 451 - Sporting Goods, Hobby, Musical Instrument, Book, and Miscellaneous Retailers

• 455 - General Merchandise Retailers

• 456 - Health and Personal Care Retailers

• 457 - Gasoline Stations and Fuel Dealers

• 458 - Clothing, Clothing Accessories, Shoe, and Jewelry Retailers

• 481 - Air Transportation

• 482 - Rail Transportation

• 483 - Water Transportation

• 484 - Truck Transportation

• 485 - Transit and Ground Passenger Transportation

• 486 - Pipeline Transportation

• 487 - Scenic and Sightseeing Transportation

• 488 - Support Activities for Transportation

• 491 - Postal Service

• 492 - Couriers and Messengers

• 493 - Warehousing and Storage

• 512 - Motion Picture and Sound Recording Industries

• 513 - Publishing Industries

• 516 - Broadcasting and Content Providers

• 517 - Telecommunications

• 518 - Computing Infrastructure Providers, Data Processing, Web Hosting

• 519 - Web Search Portals, Libraries, Archives, and Other Information Services

• 521 - Monetary Authorities-Central Bank

• 522 - Credit Intermediation and Related Activities

• 523 - Securities, Commodity Contracts, and Other Financial Investments

• 524 - Insurance Carriers and Related Activities

• 525 - Funds, Trusts, and Other Financial Vehicles

• 531 - Real Estate

• 532 - Rental and Leasing Services

• 533 - Lessors of Nonfinancial Intangible Assets

• 541 - Professional, Scientific, and Technical Services

• 551 - Management of Companies and Enterprises

• 561 - Administrative and Support Services

• 562 - Waste Management and Remediation Services

• 611 - Educational Services

• 621 - Ambulatory Health Care Services

• 622 - Hospitals

• 623 - Nursing and Residential Care Facilities

• 624 - Social Assistance

• 711 - Performing Arts, Spectator Sports, and Related Industries

• 712 - Museums, Historical Sites, and Similar Institutions

• 713 - Amusement, Gambling, and Recreation Industries

• 721 - Accommodation

• 722 - Food Services and Drinking Places

• 811 - Repair and Maintenance

• 812 - Personal and Laundry Services

• 813 - Religious, Grantmaking, Civic, Professional, and Similar Organizations

• 814 - Private Households

• 921 - Executive, Legislative, and Other General Government Support

• 922 - Justice, Public Order, and Safety Activities

• 923 - Administration of Human Resource Programs

• 924 - Administration of Environmental Quality Programs

• 925 - Administration of Housing Programs, Urban Planning, and Community Development

• 926 - Administration of Economic Programs

• 927 - Space Research and Technology

• 928 - National Security and International Affairs

### Mentoring Focus Areas

• Business Planning & Strategy

• Marketing & Sales

• Financial Management & Accounting

• Operations & Process Improvement

• Human Resources & Team Building

• Legal & Compliance

• Technology & Digital Transformation

• Access to Capital & Funding

• E-Commerce & Online Business

• Export & International Trade

• Nonprofit Management

• Social Entrepreneurship

• Real Estate & Property Management

• Retail & Consumer Goods

• Food & Beverage

• Healthcare & Wellness

• Manufacturing & Supply Chain

• Construction & Trades

### Revenue Range

• Pre-Revenue

• Under $50K

• $50K - $100K

• $100K - $250K

• $250K - $500K

• $500K - $1M

• Over $1M

### Current Professional Advisors

• Banker / Financial Institution

• Attorney / Legal Counsel

• Accountant / CPA

• IT Consultant

• Insurance Agent

• Marketing / PR Consultant

• Business Coach

### State of Registration

• Alabama

• Alaska

• Arizona

• Arkansas

• California

• Colorado

• Connecticut

• Delaware

• Florida

• Georgia

• Hawaii

• Idaho

• Illinois

• Indiana

• Iowa

• Kansas

• Kentucky

• Louisiana

• Maine

• Maryland

• Massachusetts

• Michigan

• Minnesota

• Mississippi

• Missouri

• Montana

• Nebraska

• Nevada

• New Hampshire

• New Jersey

• New Mexico

• New York

• North Carolina

• North Dakota

• Ohio

• Oklahoma

• Oregon

• Pennsylvania

• Rhode Island

• South Carolina

• South Dakota

• Tennessee

• Texas

• Utah

• Vermont

• Virginia

• Washington

• West Virginia

• Wisconsin

• Wyoming

• District of Columbia

### Legal Business Structure

• Sole Proprietor

• Partnership

• LLC

• S-Corp

• C-Corp

• Non-Profit 501(c)(3)

• Other

### Geographic Service Area

• City of Cleveland

• Cuyahoga County

• Greater Cleveland

• Akron / Summit County

• Greater Akron

• Lake County

• Lorain County

• Medina County

• Geauga County

• Portage County

• Stark County

• Northeast Ohio (Regional)

• Statewide

• National

### Target Population

• General Business Community

• Minority-Owned Businesses

• Women Entrepreneurs

• Veteran-Owned Businesses

• Immigrant & Refugee Entrepreneurs

• Youth Entrepreneurs

• Low-Income Entrepreneurs

• Tech Startups

• Food & Beverage

• Manufacturing

• Healthcare

• Non-Profit Organizations

• LGBTQ+ Entrepreneurs

• Rural Businesses

## Contact

### NAICS Sectors

• 11 - Agriculture, Forestry, Fishing

• 21 - Mining, Quarrying, Oil & Gas

• 22 - Utilities

• 23 - Construction

• 31-33 - Manufacturing

• 42 - Wholesale Trade

• 44-45 - Retail Trade

• 48-49 - Transportation & Warehousing

• 51 - Information

• 52 - Finance & Insurance

• 53 - Real Estate

• 54 - Professional, Scientific & Technical

• 55 - Management of Companies

• 56 - Administrative & Support Services

• 61 - Educational Services

• 62 - Health Care & Social Assistance

• 71 - Arts, Entertainment & Recreation

• 72 - Accommodation & Food Services

• 81 - Other Services

• 92 - Public Administration

### Mentoring Focus Areas

• Business Planning & Strategy

• Marketing & Sales

• Financial Management & Accounting

• Operations & Process Improvement

• Human Resources & Team Building

• Legal & Compliance

• Technology & Digital Transformation

• Access to Capital & Funding

• E-Commerce & Online Business

• Export & International Trade

• Nonprofit Management

• Social Entrepreneurship

• Real Estate & Property Management

• Retail & Consumer Goods

• Food & Beverage

• Healthcare & Wellness

• Manufacturing & Supply Chain

• Construction & Trades

### Skills & Expertise Tags

• Startup Formation

• Business Plan Writing

• Pitch Deck Development

• Financial Modeling

• QuickBooks / Bookkeeping

• Grant Writing

• SBA Loans

• Angel & Venture Capital

• Crowdfunding

• SEO & Digital Marketing

• Social Media Strategy

• Brand Development

• Contract Negotiation

• Intellectual Property

• HR Policies & Procedures

• Hiring & Recruiting

• Leadership Coaching

• Franchise Development

• Exit Planning & Business Sale

• Import / Export Compliance

• Website Development

• CRM & Sales Automation

• Data Analytics

• Cybersecurity Basics

### Fluent Languages

• English

• Spanish

• Arabic

• Chinese (Mandarin)

• Chinese (Cantonese)

• French

• German

• Hindi

• Italian

• Japanese

• Korean

• Polish

• Portuguese

• Russian

• Somali

• Tagalog

• Ukrainian

• Vietnamese

• Other

### How Did You Hear About CBM

• CBM Website

• Google Search

• Social Media

• Referred by a Mentor

• Referred by a Client

• Chamber of Commerce

• SBDC / SCORE

• Community Organization

• University / College

• Event or Workshop

• News / Media

• Other

## Engagement

### Status

• Submitted

• Pending Acceptance

• Assigned

• Mentor Declined

• Active

• On-Hold

• Dormant

• Inactive

• Abandoned

• Completed

## Session

### Topics Covered

• Business Planning

• Marketing Strategy

• Financial Review

• Sales & Revenue Growth

• Operations & Processes

• HR & Staffing

• Legal & Compliance

• Technology & Systems

• Funding & Capital

• Customer Discovery

• Product / Service Development

• Partnerships & Networking

• Goal Setting & Accountability

• Crisis & Problem Solving

• Other

## Workshop

### Topic/Category

• Business Planning & Strategy

• Marketing & Sales

• Financial Management & Accounting

• Operations & Process Improvement

• Human Resources & Team Building

• Legal & Compliance

• Technology & Digital Transformation

• Access to Capital & Funding

• E-Commerce & Online Business

• Export & International Trade

• Nonprofit Management

• Social Entrepreneurship

• Real Estate & Property Management

• Retail & Consumer Goods

• Food & Beverage

• Healthcare & Wellness

• Manufacturing & Supply Chain

• Construction & Trades

# Appendix B — Deployment Status

| Entity | Fields | Layout | Relationships | Status |
| --- | --- | --- | --- | --- |
| Company | ✓ Defined (32) | ✓ Defined | Planned | Ready to deploy |
| Contact | ✓ Defined (46) | ✓ Defined | Planned | Ready to deploy |
| Engagement | ✓ Defined (11) | Planned | Planned | Partially defined |
| Session | ✓ Defined (11) | Planned | Planned | Partially defined |
| NPS Survey Response | ✓ Defined (7) | Planned | Planned | Partially defined |
| Workshop | ✓ Defined (8) | Planned | Planned | Partially defined |
| Workshop Attendance | ✓ Defined (2) | Planned | Planned | Partially defined |
| Dues | ✓ Defined (6) | Planned | Planned | Partially defined |
| Partner Agreement | ✓ Defined (5) | ✓ Defined | Planned | Ready to deploy |
| Client-Partner Association | ✓ Defined (2) | ✓ Defined | Planned | Ready to deploy |
| Partner Activity | ✓ Defined (5) | ✓ Defined | Planned | Ready to deploy |
