# CBM CRM Implementation Reference

## CRM Implementation Reference

Generated from YAML program files
  Version: 1.0
  Generated: 2026-03-23 04:58 UTC

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
| Display Name (Plural) | Companys |
| Entity Type | Native (Account) |
| Stream Enabled | No |
| Deployment Method | Field configuration only |

No description provided.

## Contact

| Property | Value |
| --- | --- |
| EspoCRM Entity Name | Contact |
| Display Name (Singular) | Contact |
| Display Name (Plural) | Contacts |
| Entity Type | Native (Contact) |
| Stream Enabled | No |
| Deployment Method | Field configuration only |

No description provided.

## Engagement

| Property | Value |
| --- | --- |
| EspoCRM Entity Name | CEngagement |
| Display Name (Singular) | Engagement |
| Display Name (Plural) | Engagements |
| Entity Type | Custom (Base) |
| Stream Enabled | Yes |
| Deployment Method | create |

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

# Fields

## Company (Account)

| Field Name | Internal Name | Type | Required | Category | Description | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Organization Type | `cOrganizationType` | Enum | Yes | — | — | Values: For-Profit, Non-Profit |
| Business Stage | `cBusinessStage` | Enum | Yes | — | — | Values: Pre-Startup, Startup, Early Stage, Growth Stage, Established |
| Mentoring Focus Areas | `cMentoringFocusAreas` | Multi-select | Yes | — | — | See Appendix A |
| Mentoring Needs Description | `cMentoringNeedsDescription` | Rich Text | Yes | — | — | — |
| Company Role | `cCompanyRole` | Enum | No | — | — | Values: Client Company, Partner, Funder, Other; Default: Client Company |
| Business Description | `cBusinessDescription` | Rich Text | No | — | — | — |
| Time in Operation | `cTimeInOperation` | Text | No | — | — | Max length: 100 |
| Current Team Size | `cCurrentTeamSize` | Integer | No | — | — | Min: 0 |
| Revenue Range | `cRevenueRange` | Enum | No | — | — | See Appendix A |
| Funding Situation | `cFundingSituation` | Rich Text | No | — | — | — |
| Current Challenges | `cCurrentChallenges` | Rich Text | No | — | — | — |
| Goals and Objectives | `cGoalsAndObjectives` | Rich Text | No | — | — | — |
| Desired Outcomes (6-12 Months) | `cDesiredOutcomes` | Rich Text | No | — | — | — |
| Previous Mentoring/Advisory Experience | `cPreviousMentoringExperience` | Rich Text | No | — | — | — |
| Current Professional Advisors | `cCurrentProfessionalAdvisors` | Multi-select | No | — | — | See Appendix A |
| Registered with State | `cRegisteredWithState` | Boolean | No | — | — | Default: False |
| State of Registration | `cStateOfRegistration` | Enum | No | — | — | See Appendix A |
| Legal Business Structure | `cLegalBusinessStructure` | Enum | No | — | — | See Appendix A |
| EIN on File | `cEinOnFile` | Boolean | No | — | — | Default: False |
| Date of Formation | `cDateOfFormation` | Date | No | — | — | — |
| Registered Agent | `cRegisteredAgent` | Boolean | No | — | — | Default: False |
| EIN Number | `cEinNumber` | Text | No | — | — | Max length: 20 |

## Contact

| Field Name | Internal Name | Type | Required | Category | Description | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Contact Type | `cContactType` | Enum | No | — | — | Values: Mentor, Client |
| Mentor Status | `cMentorStatus` | Enum | No | — | — | Values: Provisional, Active, Inactive, Departed |
| Is Mentor | `cIsMentor` | Boolean | No | — | — | Default: False |
| Is Co-Mentor | `cIsCoMentor` | Boolean | No | — | — | Default: False |
| Is SME | `cIsSme` | Boolean | No | — | — | Default: False |
| Role at Business | `cRoleAtBusiness` | Text | No | — | — | Max length: 150 |
| Primary Contact | `cIsPrimaryContact` | Boolean | No | — | — | Default: False |

## Engagement

| Field Name | Internal Name | Type | Required | Category | Description | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Status | `cStatus` | Enum | Yes | — | — | See Appendix A; Default: Submitted |
| Start Date | `cStartDate` | Date | No | — | — | — |
| Close Date | `cCloseDate` | Date | No | — | — | — |
| Meeting Cadence | `cMeetingCadence` | Enum | No | — | — | Values: Weekly, Bi-Weekly, Monthly, As Needed |
| Engagement Close Reason | `cEngagementCloseReason` | Enum | No | — | — | Values: Goals Achieved, Client Withdrew, Inactive / No Response, Other |
| Submission Date | `cSubmissionDate` | Date/Time | No | — | — | — |
| Total Sessions | `cTotalSessions` | Integer | No | — | — | Read-only; Min: 0 |
| Total Sessions (Last 30 Days) | `cTotalSessionsLast30Days` | Integer | No | — | — | Read-only; Min: 0 |
| Last Session Date | `cLastSessionDate` | Date/Time | No | — | — | Read-only |
| Total Session Hours | `cTotalSessionHours` | Decimal | No | — | — | Read-only; Min: 0 |
| Next Session Date/Time | `cNextSessionDateTime` | Date/Time | No | — | — | — |

## Session

| Field Name | Internal Name | Type | Required | Category | Description | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Session Date/Time | `cSessionDateTime` | Date/Time | Yes | — | — | — |
| Duration (minutes) | `cDuration` | Integer | Yes | — | — | Min: 1 |
| Session Type | `cSessionType` | Enum | Yes | — | — | Values: In-Person, Video Call, Phone Call |
| Meeting Location Type | `cMeetingLocationType` | Enum | No | — | — | Values: CBM Office, Client's Place of Business, Other |
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
| Survey Trigger | `cSurveyTrigger` | Enum | No | — | — | Values: 2nd Session, Every 5 Sessions, Engagement Close; Read-only |
| Survey Date/Time | `cSurveyDateTime` | Date/Time | No | — | — | Read-only |
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
| Status | `cStatus` | Enum | Yes | — | — | Values: Scheduled, Completed, Cancelled; Default: Scheduled |

## Workshop Attendance (WorkshopAttendance)

| Field Name | Internal Name | Type | Required | Category | Description | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Attendance Date | `cAttendanceDate` | Date | No | — | — | Read-only |
| Attended | `cAttended` | Boolean | Yes | — | — | Default: True |

## Dues

| Field Name | Internal Name | Type | Required | Category | Description | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Billing Year | `cBillingYear` | Integer | Yes | — | — | Min: 2000 |
| Amount Due | `cAmountDue` | Currency | Yes | — | — | — |
| Invoice Date | `cInvoiceDate` | Date | No | — | — | — |
| Payment Date | `cPaymentDate` | Date | No | — | — | — |
| Payment Method | `cPaymentMethod` | Enum | No | — | — | Values: Stripe, Waived, Other |
| Notes | `cNotes` | Rich Text | No | — | — | — |

# Layouts

# Views (List Views)

> ⚠️ **Status: Defined in YAML — Implemented**

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

### Mentoring Focus Areas

• Business Planning

• Marketing & Sales

• Financial Management

• Operations

• Human Resources

• Legal & Compliance

• Technology

• Funding & Capital

• Leadership & Management

• Growth Strategy

### Revenue Range

• Pre-Revenue

• Under $50K

• $50K - $100K

• $100K - $250K

• $250K - $500K

• $500K - $1M

• $1M - $5M

• Over $5M

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

## Engagement

### Status

• Submitted

• Pending Acceptance

• Assigned

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
| Company | ✓ Defined (22) | Planned | Planned | Partially defined |
| Contact | ✓ Defined (7) | Planned | Planned | Partially defined |
| Engagement | ✓ Defined (11) | Planned | Planned | Partially defined |
| Session | ✓ Defined (11) | Planned | Planned | Partially defined |
| NPS Survey Response | ✓ Defined (7) | Planned | Planned | Partially defined |
| Workshop | ✓ Defined (8) | Planned | Planned | Partially defined |
| Workshop Attendance | ✓ Defined (2) | Planned | Planned | Partially defined |
| Dues | ✓ Defined (6) | Planned | Planned | Partially defined |
