# PRJ-128 migration run — rehearsal report and the ruling it needs

| Field | Value |
|---|---|
| Title | PRJ-128 migration run — rehearsal report and the ruling it needs |
| Last Updated | 09-25-26 13:19 |
| Revision | 1.0 |
| Status | AWAITING RULING. The migration run is built and rehearsed (PI-579); it has not been applied to production and will not apply itself until Doug rules on the differences in section 3. |
| Source | PI-579; the approved mapping (`engagement-migration-mapping.md` revision 1.0, DEC-1176 to DEC-1182); rehearsal on a dump of production taken 09-25-26 at 13:10 and restored into the local Postgres as `crmb_rehearsal`. |
| Read by | Doug, to rule; then whoever applies the run with the commands in section 5. |

## 1. What was rehearsed

The dump of production was restored locally, the two schema revisions of PI-576 and PI-577 were applied to it, and the migration run was executed in a forced dry run that carries on past comparison stops and rolls back at the end. Every move completed:

- Clients CLI-003 Rochester Business Mentors and CLI-004 Boston Business Mentors created.
- Deployments DPL-001 (CBMTEST) and DPL-002 (CBM Production) of ENG-002 for CLI-001; DPL-003 (Lakeside rehearsal) of ENG-002 for CLI-003 holding the re-homed INST-003; DPL-004 (Boston Business Mentors CRM) of ENG-002 for CLI-004 holding INST-004. All purpose client_own.
- Rochester's instance re-homed ENG-006/INST-001 to ENG-002/INST-003 with its deploy configuration, its deploy run (DEP-001) and 961 of its 973 membership rows translated onto Cleveland's identifiers by name; 12 rows that match nothing in Cleveland's design (the three engine built-in fields and nine associations) stay with the archived copy. Its two credentials became DPL-003's own.
- Boston's instance re-homed ENG-007/INST-001 to ENG-002/INST-004 with its configuration and its three deploy runs (renumbered DEP-002 to DEP-004; the needs-action run keeps its state and open items). Its credential became DPL-004's own.
- The copied design under ENG-006 archived: 29 entities, 573 fields, 93 associations, 257 layouts, 12 roles, 9 teams soft-deleted with a note, rows retained.
- ENG-003 given CLI-002 as defining client and archived; ENG-005, ENG-006 and ENG-007 archived. The moved instance rows are retained soft-deleted under their old engagements.
- Cleveland's own DigitalOcean credential stays at the application level, shared by DPL-001 and DPL-002.

Nothing was committed. The same code path is what production runs.

## 2. The comparison, measured on production data

Structural match (section 5 of the mapping): entities 29 of 29; fields 570 of 573 by name with 3 engine built-ins excluded and 0 unmatched; the five accepted type differences of DEC-1181 present and no other; roles 12 of 12; teams 9 of 9; layouts 257 of 257; associations 84 of 93, **nine unmatched**.

Attribute differences on matched records: 32 entity attributes, 17 field attributes (all read-only flags), 26 field option sets, 20 role attributes, 15 layout contents.

## 3. The ruling needed

DEC-1181 accepted five type differences and said any other difference stops the run. The rehearsal found two kinds it did not foresee, and under DEC-1184 the assistant does not widen an approved rule; it records the choice for Doug.

**A. Nine associations the copy has and Cleveland's design does not match by name.** Five are the same relationship under the engine's name where the design uses its own (for example the copy's `Account -> Engagement engagements` beside the design's `cEngagements`); four exist only on the server (`Case -> User collaborators`, `Conversation -> PartnerProfile / SponsorProfile / User`, `MentorProfile -> User assignedUsers`). Options: (1) accept them as candidate corrections and archive the copy anyway, since the copy is retained soft-deleted and nothing is lost; (2) hold the run until Cleveland's design is corrected to name them. Recommendation: (1).

**B. Attribute differences on matched records.** In every case the copy, captured from a server that was published from Cleveland's design, is more specific than the design: default sort fields the design leaves empty, six record types the server tracks activity on where the design says no, seventeen fields the server marks read-only, twenty-six option lists the design has never recorded, role scope entries the server has and the design lacks, fifteen layouts whose content differs. Options: (1) accept them as candidate corrections to Cleveland's design and archive the copy; (2) hold the run until each is reconciled by hand. Recommendation: (1), for the same reason: the copy stays readable, and the list below is the work order for a design session.

If Doug rules (1) for both, the run is applied with the second command in section 5, naming the ruling's decision. If he rules (2) for either, the run waits.

## 4. The differences in full (candidate corrections to Cleveland's design)

```
ENTITY attribute differences (copy value -> design value):
  Email.entity_default_sort_field: 'dateSent' vs design None
  Email.entity_default_sort_direction: 'desc' vs design None
  User.entity_default_sort_field: 'userName' vs design None
  User.entity_default_sort_direction: 'asc' vs design None
  Account.entity_default_sort_field: 'name' vs design None
  Account.entity_default_sort_direction: 'asc' vs design None
  Contact.entity_default_sort_field: 'lastName' vs design None
  Contact.entity_default_sort_direction: 'asc' vs design None
  Contact.entity_track_activity: True vs design False
  Document.entity_default_sort_field: 'createdAt' vs design None
  Document.entity_default_sort_direction: 'desc' vs design None
  ClientProfile.entity_default_sort_field: 'name' vs design 'createdAt'
  ClientProfile.entity_default_sort_direction: 'asc' vs design 'desc'
  Contribution.entity_default_sort_field: 'createdAt' vs design None
  Contribution.entity_default_sort_direction: 'desc' vs design None
  Engagement.entity_track_activity: True vs design False
  Event.entity_default_sort_field: 'dateStart' vs design None
  Event.entity_default_sort_direction: 'desc' vs design None
  Event.entity_track_activity: True vs design False
  EventRegistration.entity_default_sort_field: 'createdAt' vs design None
  EventRegistration.entity_default_sort_direction: 'desc' vs design None
  InformationRequest.entity_default_sort_field: 'createdAt' vs design None
  InformationRequest.entity_default_sort_direction: 'desc' vs design None
  InformationRequest.entity_track_activity: True vs design False
  IntakeSubmission.entity_default_sort_field: 'createdAt' vs design None
  IntakeSubmission.entity_default_sort_direction: 'desc' vs design None
  Resource.entity_default_sort_field: 'createdAt' vs design None
  Resource.entity_default_sort_direction: 'desc' vs design None
  Resource.entity_track_activity: True vs design False
  Session.entity_track_activity: True vs design False
  SponsorProfile.entity_default_sort_field: 'createdAt' vs design None
  SponsorProfile.entity_default_sort_direction: 'desc' vs design None
FIELD read_only differences:
  Account.applicantSinceTimestamp: True vs design False
  Account.annualPledgeAmountConverted: True vs design False
  ClientProfile.clientContactEmail: True vs design False
  Engagement.closeDate: True vs design False
  Engagement.lastSessionDate: True vs design False
  Engagement.totalSessionHours: True vs design False
  Engagement.totalSessions: True vs design False
  Engagement.totalSessionsLast30Days: True vs design False
  EventRegistration.confirmationSentAt: True vs design False
  EventRegistration.postEventFollowUpSentAt: True vs design False
  MentorProfile.contactStreet: True vs design False
  NetworkStandard.appliedAt: True vs design False
  NetworkStandard.appliedBy: True vs design False
  NetworkStandard.planFingerprint: True vs design False
  NetworkStandard.appliedByTool: True vs design False
  PartnerProfile.partnerEmail: True vs design False
  Resource.publishedAt: True vs design False
FIELD option sets the design lacks:
  Account.companyType: copy has ['Client', 'Other', 'Partner', 'Sponsor']; design has []
  Account.sponsorshipLevel: copy has ['Bronze', 'Gold', 'Platinum', 'Silver', 'Title']; design has []
  Contact.howDidYouHear: copy has ['CBM Client or Volunteer', 'CBM Email', 'News or Media', 'Online Search', 'Other', 'Partner Referral', 'Personal Referral', 'Social Media', 'Workshop or Event']; design has []
  Contact.notificationPreference: copy has ['Email', 'Text']; design has []
  ActionLog.outcome: copy has ['Failed', 'Partial', 'Success']; design has []
  ClientProfile.revenueTrend: copy has ['Declining Modestly', 'Declining Significantly', 'Flat', 'Growing Modestly', 'Growing Significantly', 'Too New to Tell']; design has []
  ClientProfile.salesChannels: copy has ['Franchise']; design has []
  Communication.direction: copy has ['Inbound', 'Outbound']; design has []
  Conversation.conversationStatus: copy has ['Closed', 'Open', 'Uncertain']; design has []
  Engagement.closeReason: copy has ['Client Withdrew', 'Goals Achieved', 'Inactive / No Response', 'Other']; design has []
  EventRegistration.registrationSource: copy has ['Import', 'Online', 'Staff', 'Walk-In']; design has []
  EventRegistration.attendanceStatus: copy has ['Attended', 'Cancelled', 'No-Show', 'Registered', 'Waitlisted']; design has []
  EventRegistration.remindersSent: copy has ['1-day', '1-hour', '7-day']; design has []
  EventRegistration.attendanceSource: copy has ['Check-in', 'Manual', 'Zoom Report']; design has []
  EventRegistration.followUpsSent: copy has ['Mentor CTA', 'No Show', 'Recording', 'Reminder', 'Survey']; design has []
  InformationRequest.requestStatus: copy has ['Closed', 'In Progress', 'New', 'Responded']; design has []
  IntakeSubmission.intakeStatus: copy has ['Completed', 'Discarded', 'Error', 'Held-Email', 'Held-Spam', 'Received']; design has []
  MentorProfile.mentorStatus: copy has ['Terminated']; design has []
  MentorProfile.howDidYouHearAboutCBM: copy has ['CBM Client or Volunteer', 'CBM Email', 'News or Media', 'Online Search', 'Other', 'Partner Referral', 'Personal Referral', 'Social Media', 'Workshop or Event']; design has []
  MentorProfile.mentorBusinessStagePref: copy has ['All', 'Business Challenges', 'Growth Challenges', 'Merger & Acquisitions', 'Pre-Startup', 'Sale', 'Succession']; design has []
  MentorProfile.preferredMeetingProvider: copy has ['Google Meet', 'Zoom Personal Meeting']; design has []
  PartnerProfile.partnerContactCadence: copy has ['Annually', 'As-Needed', 'Monthly', 'Quarterly', 'Semi-Annually']; design has []
  PartnerProfile.partnershipType: copy has ['Other']; design has ['other']
  PartnerProfile.relationGoalsEst: copy has ['In Progress', 'No', 'Yes']; design has []
  Session.meetingLocationType: copy has ["Client's Place of Business", 'Organization Office', 'Other']; design has []
  Session.meetingType: copy has ['Email']; design has []
ROLE differences (attribute only):
  Client Assignment Role.role_scope_access: copy-only keys []; design-only keys ['GoogleCalendar', 'GoogleContacts', 'Report']; changed []
  Client Assignment Role.role_system_permissions: copy-only keys ['lockPermission']; design-only keys []; changed []
  ClientMentorIntakeRole.role_scope_access: copy-only keys ['CActionLog', 'CCommunication', 'CContribution', 'CConversation', 'CEventRegistration', 'CResource', 'CSession']; design-only keys []; changed []
  ClientMentorIntakeRole.role_system_permissions: copy-only keys ['lockPermission']; design-only keys []; changed []
  ContentAndEventAdmin.role_system_permissions: copy-only keys ['lockPermission']; design-only keys []; changed []
  CustomAppAPIRole.role_scope_access: copy-only keys ['CActionLog', 'CCommunication', 'CConversation', 'EmailTemplate', 'Team', 'User']; design-only keys []; changed ['Account', 'CClientProfile', 'CContribution', 'CEngagement', 'CEvent', 'CEventRegistration', 'CInformationRequest', 'CIntakeSubmission', 'CMentorProfile', 'CNetworkStandard', 'CPartnerProfile', 'CResource', 'CSession', 'CSponsorProfile', 'Contact']
  CustomAppAPIRole.role_system_permissions: copy-only keys ['lockPermission']; design-only keys []; changed ['assignmentPermission']
  Data Integrity Team Role.role_system_permissions: copy-only keys ['lockPermission']; design-only keys []; changed []
  Event Manager Role.role_system_permissions: copy-only keys ['lockPermission']; design-only keys []; changed []
  Marketing Admin Role.role_system_permissions: copy-only keys ['lockPermission']; design-only keys []; changed []
  Mentor Administration Role.role_scope_access: copy-only keys []; design-only keys ['Report']; changed []
  Mentor Administration Role.role_system_permissions: copy-only keys ['lockPermission']; design-only keys []; changed []
  Mentor Role.role_scope_access: copy-only keys ['CCommunication', 'CConversation', 'CPartnerProfile', 'EmailTemplateCategory']; design-only keys ['GoogleCalendar', 'GoogleContacts', 'Report', 'ReportCategory']; changed ['CMentorProfile', 'Document']
  Mentor Role.role_system_permissions: copy-only keys ['lockPermission']; design-only keys []; changed []
  Partner Manager Role.role_scope_access: copy-only keys ['CCommunication', 'CConversation', 'EmailTemplate', 'EmailTemplateCategory']; design-only keys ['Report']; changed []
  Partner Manager Role.role_system_permissions: copy-only keys ['lockPermission']; design-only keys []; changed []
  Sponsor Manager Role.role_scope_access: copy-only keys ['CCommunication', 'CContribution', 'CConversation', 'EmailTemplate', 'EmailTemplateCategory']; design-only keys []; changed []
  Sponsor Manager Role.role_system_permissions: copy-only keys ['lockPermission']; design-only keys []; changed []
  Standard User.role_scope_access: copy-only keys []; design-only keys ['GoogleCalendar']; changed ['Email']
  Standard User.role_system_permissions: copy-only keys ['lockPermission']; design-only keys []; changed ['userCalendarPermission']
LAYOUT content differences: [['Campaign', 'list'], ['Account', 'detail'], ['Campaign', 'list_small'], ['Contact', 'detail'], ['Lead', 'list'], ['Lead', 'list_small'], ['Meeting', 'detail'], ['Opportunity', 'detail'], ['Opportunity', 'detail_small'], ['IntakeSubmission', 'detail'], ['InformationRequest', 'detail'], ['MentorProfile', 'detail'], ['MentorProfile', 'list_small'], ['Session', 'detail'], ['Session', 'detail_small']]
ASSOCIATIONS unmatched: [['Account', 'Engagement', 'engagements'], ['Account', 'SponsorProfile', 'sponsorProfiles'], ['Case', 'User', 'collaborators'], ['Contact', 'SponsorProfile', 'sponsorProfiles'], ['Contact', 'User', 'assignedUsers'], ['Conversation', 'PartnerProfile', 'partnerProfiles'], ['Conversation', 'SponsorProfile', 'sponsorProfiles'], ['Conversation', 'User', 'assignedUsers'], ['MentorProfile', 'User', 'assignedUsers']]
```

## 5. How the run is applied after the ruling

The schema revisions ship with the normal rollout. The data revision `operate_0005_prj128_migration_run` runs in that rollout, finds the comparison stopped, prints `PRJ-128 migration run NOT applied` in the migrate log, and leaves the store untouched. After the ruling is recorded as a decision, on the droplet:

```bash
cd /opt/crmbuilder && set -a && . crmbuilder-v2/data/crmbuilder.env && set +a
```

then a dry run that reports and rolls back:

```bash
.venv/bin/python -m crmbuilder_v2.segments.operate.prj128_migration --url "$CRMBUILDER_V2_DATABASE_URL" --accept-attribute-differences --ruling DEC-NNNN --report /opt/crmbuilder/backups/prj128-dryrun.json
```

and, when that reports every move as expected, the same command with `--apply`, after a `pg_dump` into `/opt/crmbuilder/backups/` as the rebuild rule requires. The nine unmatched associations are a structural stop, so if ruling A is (1) the accepted set in the module must be widened to name them before the apply; that is a one-line code change recorded against the ruling.

## Change log

| Revision | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-25-26 13:19 | Claude (Claude Code), for Doug Bower | First version from the rehearsal of 09-25-26. |
