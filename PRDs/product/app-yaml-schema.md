# CRM Builder — YAML Program File Schema

**Version:** 1.2.1
**Status:** Current
**Last Updated:** 05-03-26 14:00
**Applies To:** All YAML program files used by CRM Builder

---

## Revision History

| Version | Date | Summary |
|---|---|---|
| 1.0 | March 2026 | Initial schema. |
| 1.1 | 04-13-26 22:30 | Adds Categories 1–10 of MR-pilot gap analysis. Category 1: `settings:` block (existing `labelSingular`, `labelPlural`, `stream`, `disabled` deprecated). Category 2: `duplicateChecks:` block. Category 3: `savedViews:` block; shared condition-expression construct introduced in new Section 11. Category 4: `requiredWhen:` field-level property for conditional requirement. Category 5: `visibleWhen:` field-level and panel-level property for conditional visibility (panel-level `dynamicLogicVisible:` deprecated). Category 6 deferred to v1.2. Category 7: `emailTemplates:` block with external HTML body files and validated `mergeFields:`. Category 8: field-level `formula:` block (three types — `aggregate`, `arithmetic`, `concat`; seven aggregate functions). Category 9: entity-level `workflows:` block with five trigger events and four actions (`onFirstTransition` and `createRelatedRecord` deferred to v1.2). Category 10: field-level `externallyPopulated:` flag for fields supplied by external systems. See `yaml-schema-gap-analysis-MR-pilot.md`. |
| 1.2 | 05-03-26 | Adds Section 5.9 `filteredTabs:` — declarative left-navigation filtered list views, implemented as Report Filter records (Advanced Pack) plus a generated metadata bundle (`scopes/`, `clientDefs/`, `i18n/en_US/Global.json`) the operator copies onto the EspoCRM server before rebuild and Tab List add. Reuses the Section 11 condition-expression construct for the filter criteria. Validation rules for the new block are added to Section 10. |
| 1.2.1 | 05-03-26 14:00 | Documents the existing schema rule that link relationships are declared exclusively in the top-level `relationships:` block — `type: link` is not a valid field type and is rejected at validation time with a hard-reject error. Rule was implicit in v1.0–v1.2; now explicit in Sections 6.2, 8, and 10 following its enforcement by `validate_program()` (crmbuilder error-handling Prompt E, 05-02-26). Discovery: FU-Contribution.yaml v1.0.0 dual-declared three relationships as both `type: link` fields and `relationships:` entries, causing HTTP 409 Conflict at deploy time because EspoCRM's fieldManager created stub link fields that subsequently conflicted with `EntityManager/action/createLink`. Documents that field-level metadata (description, category) does not propagate onto link records — configure post-deployment via the EspoCRM admin UI if needed. Documents that three EspoCRM features have no public REST API write path (saved views, duplicate-check rules, workflows): YAML directives are recognized and surfaced in a MANUAL CONFIGURATION REQUIRED block at end of run rather than applied via API. |

---

## 1. Purpose

This document defines the schema for CRM Builder YAML program files —
the machine-readable configuration files that describe the desired state
of a CRM instance. All features that read or write YAML program files
must conform to this schema.

YAML program files are the single source of truth for CRM configuration.
They are CRM-agnostic at the requirements level and are translated into
platform-specific API calls at deployment time.

---

## 2. Design Principles

**Declarative.** A program file describes the desired end state, not a
sequence of steps. The tool determines what needs to change by comparing
the desired state to the current instance state.

**Idempotent.** Running the same program file multiple times produces
the same result. The tool only creates or updates objects where the
current state differs from the spec.

**Human-readable.** Program files are intended to be read and reviewed
by people, not just machines. Field descriptions, entity descriptions,
and comments are first-class citizens of the schema.

**No instance-specific information.** Program files contain no
credentials, URLs, or instance identifiers. The same file can be applied
to any compatible CRM instance.

**Natural names.** Program files use natural, human-readable names for
entities and fields. The tool handles any platform-specific prefixing
or naming transformations at deployment time.

---

## 3. Top-Level Structure

Every YAML program file has the following top-level structure. This
example shows all major sections — a file may include any combination
of these:

```yaml
version: "1.0"
content_version: "1.0.0"
description: "Human-readable description of what this file configures"

# Optional: source reference
# Source: PRD document name and section

entities:
  EntityName:
    description: "Why this entity exists and its PRD reference"
    action: delete_and_create   # omit for native entities
    type: Base
    labelSingular: "Entity Name"
    labelPlural: "Entity Names"
    stream: false
    fields:
      - name: fieldName
        type: enum
        label: "Field Label"
        description: "Why this field exists"
        category: "Tab Name"
        options:
          - "Value A"
          - "Value B"
    layout:
      detail:
        panels:
          - label: "Panel Label"
            tabBreak: true
            tabLabel: "Tab"
            rows:
              - [fieldName, null]
      list:
        columns:
          - field: fieldName
            width: 25

relationships:
  - name: relationshipName
    description: "Why this relationship exists and its PRD reference"
    entity: EntityName
    entityForeign: OtherEntity
    linkType: manyToOne
    link: linkName
    linkForeign: linkForeignName
    label: "Label"
    labelForeign: "Foreign Label"
```

### 3.1 Top-Level Properties

| Property | Type | Required | Description |
|---|---|---|---|
| `version` | string | yes | Schema version of this file format. Currently `"1.0"` |
| `content_version` | string | yes | Semantic version of this file's content (see Section 4) |
| `description` | string | yes | Human-readable description of what this file configures |
| `entities` | map | no | Map of entity name → entity definition (see Section 5). Each entity block contains `fields` (Section 6) and optionally `layout` (Section 7) |
| `relationships` | list | no | List of relationship definitions (see Section 8) |

A file may contain `entities`, `relationships`, or both. A file with
neither is valid but produces no output.

All program files are validated before any API calls are made. Validation
rules for each section are defined in Section 10.


---

## 4. Content Versioning

The `content_version` property uses semantic versioning (`MAJOR.MINOR.PATCH`)
to communicate the significance of changes to a program file.

| Change Type | Version Bump | Examples |
|---|---|---|
| Descriptions, comments, minor corrections | PATCH | `1.0.0 → 1.0.1` |
| New fields, new enum values, new relationships | MINOR | `1.0.0 → 1.1.0` |
| Fields removed, types changed, entities restructured | MAJOR | `1.0.0 → 2.0.0` |

`content_version` must be incremented whenever a file is changed. It is
displayed alongside the filename in the Program File panel so users can
confirm they are working with the correct version.

---

## 5. Entity Block

The `entities` map contains one entry per entity. The key is the
entity's natural name.

```yaml
entities:
  Contact:           # native entity — fields only
    description: >
      The Contact entity represents individuals tracked in the CRM.
    settings:
      stream: true
    fields:
      - ...

  Engagement:        # custom entity — full definition
    description: >
      An Engagement represents an active mentoring relationship between
      a mentor Contact and a client organization Account.
    action: delete_and_create
    type: Base
    settings:
      labelSingular: "Engagement"
      labelPlural: "Engagements"
      stream: true
      disabled: false
    fields:
      - ...
    layout:
      ...
```

### 5.1 Entity Properties

Top-level properties on an entity block:

| Property | Type | Required | Description |
|---|---|---|---|
| `description` | string | yes | Business rationale, role in data model, and PRD reference |
| `action` | string | no | Entity-level action (see Section 5.2). Default: none (fields only) |
| `type` | string | create only | Entity type: `Base`, `Person`, `Company`, or `Event` |
| `settings` | map | no | Entity-level configuration (see Section 5.4) |
| `fields` | list | no | List of field definitions (see Section 6) |
| `layout` | map | no | Layout definitions (see Section 7) |

The `description` property is required on all entity blocks, including
native entities. It documents why the entity exists and where it is
defined in the PRD.

**Deprecated top-level properties (v1.1).** The properties
`labelSingular`, `labelPlural`, `stream`, and `disabled` were top-level
in v1.0 and have moved into the `settings:` block in v1.1. The v1.0
form is accepted in v1.1 with a deprecation warning emitted at load
time and is removed in v1.2.

### 5.2 Entity Action Values

| Action | When to Use |
|---|---|
| *(omit)* | Native entities (Account, Contact) — field and layout operations only |
| `create` | Custom entities — create if not already present |
| `delete` | Remove a custom entity. No `fields` or `layout` allowed |
| `delete_and_create` | Delete and recreate a custom entity. Used for clean rebuilds |

`delete` and `delete_and_create` are destructive operations. They require
explicit user confirmation before execution (see `app-ui-patterns.md`,
Section 5.3).

### 5.3 Entity Types

| Type | Description |
|---|---|
| `Base` | General-purpose entity with name and description fields |
| `Person` | Includes first/last name, email, phone, and address fields |
| `Company` | Includes email, phone, billing/shipping address fields |
| `Event` | Includes date start/end, duration, status, and parent fields |

### 5.4 Entity Settings

The `settings:` block holds entity-level configuration. It applies to
both native and custom entities — for native entities the values
override the CRM's defaults; for custom entities the values are the
original declaration.

```yaml
entities:
  Contact:                 # native entity — overrides
    description: >
      The Contact entity represents individuals tracked in the CRM.
    settings:
      stream: true
    fields:
      - ...

  Dues:                    # custom entity — original declaration
    description: >
      One annual dues obligation for a single mentor.
    action: create
    type: Base
    settings:
      labelSingular: "Dues"
      labelPlural: "Dues"
      stream: false
      disabled: false
    fields:
      - ...
```

| Setting | Type | Required | Description |
|---|---|---|---|
| `labelSingular` | string | create only | Singular display name shown in the CRM UI |
| `labelPlural` | string | create only | Plural display name shown in the CRM UI |
| `stream` | boolean | no | Enable the Stream (activity feed) panel. Default for custom entities: `false`. For native entities: omit unless overriding the CRM default |
| `disabled` | boolean | no | Mark the entity as disabled. Default: `false` |

The `settings:` block is reserved for scalar configuration toggles.
Rule-shaped collections (duplicate checks, saved views, workflows,
email templates) are sibling top-level blocks on the entity, not
nested inside `settings:`. See Sections 5.5 and following (added in
v1.1 Categories 2–9).

The schema validator rejects unknown settings keys at load time. Any
key in `settings:` not listed in the table above produces an error.

**Native vs custom entity behavior.** From the YAML reader's
perspective `settings:` looks identical for both; the deploy manager
distinguishes native from custom under the hood. For native entities
omit any setting whose CRM default is acceptable — only specify
overrides.

**Audited fields (no entity-level setting).** Per-field auditing is
expressed on the field itself via `audited: true` (see Section 6).
There is no entity-level "audit everything" toggle; auditing is
intentionally per-field to keep audit logs focused.

### 5.5 Duplicate Detection

The optional `duplicateChecks:` block declares rules that prevent
duplicate records from being created on an entity. Each rule names one
or more fields whose combined values must be unique, an action to take
when a match is found, and a user-facing message.

`duplicateChecks:` is a sibling of `settings:` and `fields:` on the
entity, not nested inside `settings:`. Each rule has its own structure
and identifier.

```yaml
entities:

  Contact:
    description: >
      The Contact entity represents individuals tracked in the CRM.
    settings:
      stream: true
    duplicateChecks:
      - id: contact-personal-email
        fields: [personalEmail]
        normalize:
          personalEmail: lowercase-trim
        onMatch: block
        message: >
          A Contact with this personal email address already
          exists. Locate and update the existing record rather
          than creating a duplicate.
        alertTemplate: mentor-duplicate-email-alert    # optional
        alertTo: role:mentor-administrator             # optional

      - id: account-name-city
        fields: [name, billingCity]
        normalize:
          name: case-fold-trim
          billingCity: case-fold-trim
        onMatch: warn
    fields:
      - ...
```

| Property | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Stable identifier for drift detection. Unique within the entity |
| `fields` | list | yes | One or more field names whose combined values must be unique |
| `normalize` | map | no | Per-field normalization applied before comparison (see below) |
| `onMatch` | string | yes | Action to take on duplicate detection: `block` or `warn` |
| `message` | string | required for `block` | User-facing message shown when the duplicate is detected |
| `alertTemplate` | string | no | Email template ID to send when a duplicate is detected (Section 5.7) |
| `alertTo` | string | no | Recipient for `alertTemplate`: a field name, a literal address, or `role:<role-id>` |

**Normalization values.** The `normalize:` map specifies how each field
is transformed before comparison. Supported values:

| Value | Behavior |
|---|---|
| `none` | No transformation (default if field omitted from `normalize:`) |
| `lowercase-trim` | Lowercase and trim leading/trailing whitespace. Use for emails |
| `case-fold-trim` | Unicode case-fold and trim. Use for names and other text |
| `e164` | Normalize to E.164 phone format |

**`onMatch` actions.**

- `block` — Reject the create/update operation. The `message` is shown
  to the user; if `alertTemplate` is present, the corresponding email
  is sent to `alertTo`.
- `warn` — Allow the operation, flag the record. The `message` is
  optional; the user sees the warning but can proceed.

The deploy manager translates each rule into the target CRM's native
duplicate-detection mechanism. Rules with `alertTemplate` reference
templates declared in the entity's `emailTemplates:` block (Section 5.7,
added in Category 7).

### 5.6 Saved Views

The optional `savedViews:` block declares predefined list-view filters
on the entity. Each saved view appears in the CRM's list-view selector
and applies its filter, column set, and sort order when chosen.

`savedViews:` is a sibling of `settings:`, `duplicateChecks:`, and
`fields:` on the entity.

```yaml
entities:

  Contact:
    description: >
      The Contact entity represents individuals tracked in the CRM.
    settings:
      stream: true
    savedViews:

      # Shorthand form — flat list, implicit AND across clauses
      - id: mentor-active
        name: "Mentor — Active"
        description: "All currently active mentors."
        columns: [name, primaryEmail, mentorStatus, currentActiveClients, availableCapacity]
        filter:
          - { field: contactType,  op: contains, value: "Mentor" }
          - { field: mentorStatus, op: equals,   value: "Active" }
        orderBy: { field: name, direction: asc }

      - id: mentor-submitted-applications
        name: "Mentor — Submitted Applications"
        columns: [name, personalEmail, mentorStatus, createdAt]
        filter:
          - { field: contactType,  op: contains, value: "Mentor" }
          - { field: mentorStatus, op: in,       value: ["Submitted", "In Review"] }
        orderBy: { field: createdAt, direction: asc }

      # Structured form — explicit all: / any: blocks, freely nestable
      - id: mentor-needs-attention
        name: "Mentor — Needs Attention"
        columns: [name, mentorStatus, backgroundCheckCompleted]
        filter:
          all:
            - { field: contactType, op: contains, value: "Mentor" }
            - any:
                - { field: mentorStatus, op: equals, value: "Active" }
                - { field: mentorStatus, op: equals, value: "Provisional" }
            - { field: backgroundCheckCompleted, op: equals, value: false }
        orderBy: { field: applicationDate, direction: asc }
    fields:
      - ...

  Dues:
    settings:
      labelSingular: "Dues"
      labelPlural: "Dues"
    savedViews:
      - id: dues-outstanding
        name: "Dues — Outstanding"
        columns: [name, billingYear, amount, dueDate, paymentStatus]
        filter:
          - { field: paymentStatus, op: equals,   value: "Unpaid" }
          - { field: dueDate,       op: lessThan, value: "today" }
        orderBy: { field: dueDate, direction: asc }
    fields:
      - ...
```

| Property | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Stable identifier for drift detection. Unique within the entity |
| `name` | string | yes | User-visible label shown in the CRM's list-view selector |
| `description` | string | no | Optional descriptive text |
| `columns` | list | no | Field names to show in display order. If omitted, CRM defaults are used |
| `filter` | filter | yes | Condition expression (see Section 11) |
| `orderBy` | orderBy clause or list | no | Sort specification (see below) |

**Filter forms.** `filter:` accepts either shorthand or structured form:

- **Shorthand** — a flat list of clauses combined with implicit AND.
  Use for simple filters where every condition must hold.
- **Structured** — a single `{ all: [...] }` or `{ any: [...] }` block
  at the root, freely nestable. `all:` and `any:` blocks may contain
  leaf clauses, other `all:` blocks, or other `any:` blocks. Use when
  OR or mixed conjunction/disjunction is needed.

Both forms use the same leaf-clause syntax and the same operator
vocabulary. See Section 11 for the full specification.

**orderBy clauses.** Each `orderBy` entry is an object of the form
`{ field: <fieldName>, direction: asc|desc }`. `orderBy` may be a
single object or a list of such objects for multi-field ordering:

```yaml
orderBy:
  - { field: lastName,  direction: asc }
  - { field: firstName, direction: asc }
```

`direction:` defaults to `asc` when omitted.

### 5.7 Email Templates

The optional `emailTemplates:` block registers named email templates
that can be referenced by workflows, duplicate-check alerts, and other
automation. Template metadata is declared in YAML; the body content
lives in external HTML files co-located with the program YAML.

`emailTemplates:` is a sibling of `settings:`, `duplicateChecks:`,
`savedViews:`, and `fields:` on the entity.

```yaml
entities:

  Contact:
    description: >
      The Contact entity represents individuals tracked in the CRM.
    settings:
      stream: true
    emailTemplates:

      - id: mentor-application-confirmation
        name: "Mentor Application Confirmation"
        description: >
          Sent on creation of a new Contact with contactType containing
          "Mentor" and mentorStatus = "Submitted".
        entity: Contact
        subject: "Thank you for applying to Cleveland Business Mentors"
        bodyFile: "templates/mentor-application-confirmation.html"
        mergeFields:
          - name
          - personalEmail
          - applicationDate

      - id: mentor-application-decline
        name: "Mentor Application Decline"
        description: >
          Sent when mentorStatus changes to Declined. Body content
          varies by applicationDeclineReason; conditional sections
          handled inside the body template.
        entity: Contact
        subject: "Update on your Cleveland Business Mentors application"
        bodyFile: "templates/mentor-application-decline.html"
        mergeFields:
          - name
          - personalEmail
          - applicationDeclineReason

      - id: mentor-duplicate-email-alert
        name: "Mentor Application Duplicate Email Alert"
        description: >
          Internal notification when an application submission
          collides with an existing personal email. Referenced from
          the Contact duplicate-check rule.
        entity: Contact
        audience: role:mentor-administrator   # documentation hint in v1.1
        subject: "Duplicate mentor application: {{personalEmail}}"
        bodyFile: "templates/mentor-duplicate-email-alert.html"
        mergeFields:
          - personalEmail
          - existingContactName
          - submissionTimestamp
    fields:
      - ...
```

| Property | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Stable identifier referenced by workflows, duplicate checks, and other automation. Unique within the entity |
| `name` | string | yes | Human-readable template name shown in the CRM's template selector |
| `description` | string | no | Business rationale; when and why the template is sent |
| `entity` | string | yes | The entity the template operates against; used for merge-field validation |
| `subject` | string | yes | Subject line. May contain `{{mergeField}}` placeholders |
| `bodyFile` | string | yes | Path to the HTML body file, relative to the program YAML |
| `mergeFields` | list | yes | Field names used as merge placeholders in subject and body. Every field must exist on `entity` |
| `audience` | string | no | Documentation hint for intended recipients; free-form string in v1.1. Full role-based audience handling arrives in v1.2 with Category 6 |

**Body file format.** Body files are HTML with `{{mergeField}}`
placeholders. Placeholder names must correspond to entries in
`mergeFields:`. The deploy manager reads each body file at deploy
time and uploads it to the target CRM alongside the subject and
metadata.

**Per-domain file location.** Body files live in a `templates/`
subdirectory co-located with the program YAML that registers them.
For MR-domain templates:

```
programs/MR/
├── MR-Contact.yaml
├── MR-Dues.yaml
└── templates/
    ├── mentor-application-confirmation.html
    ├── mentor-application-decline.html
    └── mentor-duplicate-email-alert.html
```

This mirrors the per-domain YAML organization and keeps cross-domain
independence. Templates used by multiple domains are declared in the
domain that owns the underlying entity.

**Merge-field validation.** At load time the validator confirms:

- Every entry in `mergeFields:` corresponds to a real field on `entity`
- Every `{{placeholder}}` in `subject:` and `bodyFile:` corresponds
  to an entry in `mergeFields:`
- No entry in `mergeFields:` is unused in `subject:` or `bodyFile:`

Bad references fail validation rather than producing broken templates
at runtime.

**Audience handling.** In v1.1, `audience:` is a free-form documentation
string. Common conventions for readability: `role:<role-id>` to hint
at a persona role, `user:<user-id>` for a specific user, or a
descriptive phrase for applicant-facing vs. internal notifications.
Full role-based audience resolution arrives in v1.2 alongside the
Roles declaration (Category 6 of the gap analysis).

### 5.8 Workflows

The optional `workflows:` block declares event-triggered automations on
the entity. Each workflow fires on an event, optionally filters on
additional conditions, and executes an ordered sequence of actions.

`workflows:` is a sibling of `settings:`, `duplicateChecks:`,
`savedViews:`, `emailTemplates:`, and `fields:` on the entity.

```yaml
entities:

  Contact:
    description: >
      The Contact entity represents individuals tracked in the CRM.
    settings:
      stream: true
    workflows:

      # Send confirmation email on new mentor application
      - id: mentor-application-confirmation
        name: "Send confirmation email on new mentor application"
        trigger: { event: onCreate }
        where:
          all:
            - { field: contactType,  op: contains, value: "Mentor" }
            - { field: mentorStatus, op: equals,   value: "Submitted" }
        actions:
          - { type: sendEmail, template: mentor-application-confirmation, to: personalEmail }

      # Send decline email when status flips to Declined
      - id: mentor-application-decline-notification
        name: "Send decline email on application decline"
        trigger:
          event: onFieldChange
          field: mentorStatus
          to: "Declined"
        where:
          - { field: applicationDeclineReason, op: isNotNull }
        actions:
          - { type: sendEmail, template: mentor-application-decline, to: personalEmail }

      # Stamp acceptance timestamp when terms & conditions flip to true
      - id: terms-acceptance-timestamp
        name: "Stamp terms and conditions acceptance time"
        trigger:
          event: onFieldChange
          field: termsAndConditionsAccepted
          to: true
        actions:
          - { type: setField, field: termsAndConditionsAcceptanceDateTime, value: now }

      # Auto-stop accepting new clients on pause or inactive (one-way)
      - id: pause-stops-new-clients
        name: "Stop accepting new clients on pause or inactive"
        trigger:
          event: onFieldTransition
          field: mentorStatus
          to: ["Paused", "Inactive"]
        actions:
          - { type: setField, field: acceptingNewClients, value: false }

      # Clear departure fields when the mentor is reactivated
      - id: clear-departure-on-reactivation
        name: "Clear departure fields on reactivation"
        trigger:
          event: onFieldTransition
          field: mentorStatus
          from: ["Resigned", "Departed"]
          to:   ["Active",   "Provisional"]
        actions:
          - { type: clearField, field: departureReason }
          - { type: clearField, field: departureDate }
    fields:
      - ...
```

| Property | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Stable identifier for drift detection. Unique within the entity |
| `name` | string | yes | Human-readable workflow name |
| `description` | string | no | Business rationale and PRD reference |
| `trigger` | trigger block | yes | Event that fires the workflow (see below) |
| `where` | condition | no | Additional condition expression (Section 11). Workflow fires only when the condition also holds |
| `actions` | list | yes | Ordered list of actions to execute (see below) |

#### Trigger events (v1.1)

| Event | Fires on | Required clauses |
|---|---|---|
| `onCreate` | Record created | (none) |
| `onUpdate` | Any field updated | (none) |
| `onFieldChange` | Specific field set to a new value | `field:`; optional `to:` (value or list) |
| `onFieldTransition` | Field transitions with `from:` / `to:` constraint | `field:`; `from:` and/or `to:` (either may be a list) |
| `onDelete` | Record deleted | (none) |

`onFirstTransition` (fires only the first time a transition occurs
for a record) is deferred to v1.2 because its correct implementation
requires audit-history awareness across multiple target CRMs.

**Trigger examples.**

```yaml
trigger: { event: onCreate }

trigger:
  event: onFieldChange
  field: mentorStatus
  to: "Declined"

trigger:
  event: onFieldTransition
  field: mentorStatus
  to: ["Paused", "Inactive"]           # list expresses multiple target values

trigger:
  event: onFieldTransition
  field: mentorStatus
  from: ["Resigned", "Departed"]
  to:   ["Active",   "Provisional"]
```

#### Actions (v1.1)

| Action | Effect | Required clauses |
|---|---|---|
| `setField` | Set a field to a literal or computed value | `field:`, `value:` |
| `clearField` | Clear a field to null | `field:` |
| `sendEmail` | Send an email using a registered template | `template:`, `to:` |
| `sendInternalNotification` | Send an in-CRM notification to a role or user | `template:`, `to:` |

`createRelatedRecord` is deferred to v1.2 — its design questions
(new-record field values, relationship-link setup) deserve a real use
case.

**`setField.value:`** accepts:

- A literal (string, number, boolean)
- The special token `now` — resolves to the server-side current
  timestamp at fire time
- A small arithmetic expression in the same mini-language as
  Section 6.1.3 `arithmetic.expression`

**`sendEmail.template:`** references an `id` in the entity's
`emailTemplates:` block (Section 5.7).

**`sendEmail.to:`** is one of:

- A field name on the entity whose value is an email address
- A literal email address

**`sendInternalNotification.to:`** is one of:

- A literal email address
- A string of the form `role:<role-id>` (role handling lands properly
  in v1.2 with Category 6)
- A string of the form `user:<user-id>`

#### Execution order

When multiple workflows fire on the same event, they execute in YAML
declaration order. No explicit priority field in v1.1.

Actions within a single workflow execute top-to-bottom. If an action
fails, subsequent actions in the same workflow are skipped and the
failure is logged.

#### Cross-references

- `where:` uses the Section 11 condition expression.
- `sendEmail` actions reference templates declared in the entity's
  `emailTemplates:` block (Section 5.7).
- Duplicate-detection notifications (the MR-pilot's WF-003 pattern)
  are **not** expressed as separate workflows. They are handled by
  the `alertTemplate:` / `alertTo:` clauses on a duplicate-check rule
  (Section 5.5).

### 5.9 Filtered Tabs

The optional `filteredTabs:` block declares left-navigation entries
that open a pre-filtered list view of an entity. A filtered tab differs
from a saved view (Section 5.6): a saved view is a selectable filter
*inside* an entity's existing list view, while a filtered tab is a
separate top-level navigation entry that lands the user directly on the
filtered records.

`filteredTabs:` is a sibling of `settings:`, `duplicateChecks:`,
`savedViews:`, `emailTemplates:`, `workflows:`, and `fields:` on the
entity.

#### How EspoCRM implements this pattern

EspoCRM has no GUI option to add a filtered list view to the left
navigation. The supported pattern combines two parts:

1. A **Report Filter** record (the EspoCRM "Advanced Pack" extension)
   that holds the filter criteria. Report Filters are first-class
   records reachable over REST at `/api/v1/ReportFilter`.
2. Three **metadata files** on the server filesystem under
   `custom/Espo/Custom/Resources/` that register a custom scope as a
   navigable tab and bind it to the Report Filter:
   - `scopes/<Scope>.json` — declares the scope as `tab: true`
   - `clientDefs/<Scope>.json` — points the scope at an entity and
     sets `defaultFilter: reportFilter<id>`
   - `i18n/en_US/Global.json` — adds the scope's display label to
     `scopeNames`

Because EspoCRM's `/api/v1/Metadata` endpoint is GET-only, the three
metadata files cannot be written over REST. CRM Builder generates them
into a deploy bundle (see "Deploy artifact" below) and the operator
copies the bundle onto the server before running Admin → Rebuild and
Admin → User Interface → Tab List → Add.

#### YAML form

```yaml
entities:

  Engagement:
    description: >
      An Engagement represents an active mentoring relationship.
    filteredTabs:

      - id: my-open
        scope: MyOpenEngagements
        label: "My Open Engagements"
        navOrder: 4
        acl: boolean
        filter:
          all:
            - { field: status,         op: equals, value: "Open" }
            - { field: assignedUserId, op: equals, value: "$user" }

      - id: stalled
        scope: StalledEngagements
        label: "Stalled Engagements"
        filter:
          all:
            - { field: status,         op: equals,    value: "Open" }
            - { field: lastActivityAt, op: lessThan,  value: "-30d" }
    fields:
      - ...
```

| Property | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Stable identifier for drift detection. Unique within the entity |
| `scope` | string | yes | PascalCase scope name (max 60 chars, ASCII letters and digits only). Becomes the filename for `scopes/<scope>.json` and `clientDefs/<scope>.json`. **Must be unique across the entire program file**, since EspoCRM scope names occupy a single global namespace |
| `label` | string | yes | Human-readable label that appears in the left nav and the Tab List configuration screen. Becomes the value in `i18n.scopeNames` |
| `filter` | filter | yes | Condition expression (see Section 11). Applied verbatim to the Report Filter's `data.where` |
| `navOrder` | integer | no | Optional ordinal position for the Tab List. Lower numbers sort earlier. When omitted, the operator decides position at install |
| `acl` | string | no | ACL strategy for the scope. One of `boolean`, `team`, `strict`. Default: `boolean` |

**Filter forms.** Identical to saved views and workflows: shorthand
list (implicit AND across leaf clauses) or structured `all:` / `any:`
blocks. See Section 11.

**The `$user` sentinel.** A leaf clause of the form
`{ field: <X>, op: equals, value: "$user" }` is translated to EspoCRM's
built-in `currentUser` where-type, so the resulting filter resolves to
the viewing user at request time rather than to a fixed user id baked
in at deploy time. `notEquals` is similarly translated. This is the
mechanism behind "My …" tabs (see `MyOpenEngagements` above).

**Relative-date tokens.** The relative-date vocabulary from Section 11
(`today`, `yesterday`, `+Nd`, `-Nd`, etc.) is resolved to absolute
`YYYY-MM-DD` strings at deploy time before being written to the Report
Filter. The Report Filter does *not* re-resolve these dates over time;
re-running the configuration step will refresh them. Where a sliding
window is required, prefer EspoCRM's built-in date where-types via a
manually-authored Report Filter rather than this declarative path.

#### Deploy artifact

Each Run that processes any `filteredTabs:` writes a bundle to:

```
{project_folder}/reports/filtered_tabs/{run_ts}/
├── README.txt              # operator install steps
├── manifest.json           # machine-readable index of every tab
├── scopes/<Scope>.json
├── clientDefs/<Scope>.json
└── i18n/en_US/Global.json  # consolidated scopeNames map for the run
```

The bundle's directory layout mirrors `custom/Espo/Custom/Resources/`
so the operator can `scp -r` its contents onto the server and trigger
`Admin → Rebuild` plus `Admin → User Interface → Tab List → Add`. The
bundle is always emitted, even when the Report Filter step failed or
was skipped (Advanced Pack absent), so the operator has a complete
artifact to inspect or hand-edit.

#### Run-time behavior

For each tab, the configuration step performs:

1. **CHECK** — `GET /api/v1/ReportFilter?where[entityType]=<entity>`.
   - HTTP 404 ⇒ Advanced Pack is not installed; the tab is recorded
     with status `not_supported`. The bundle is still written, with
     `defaultFilter` set to the placeholder
     `REPLACE_WITH_reportFilter<id>` for the operator to fill in once
     the filter is created manually.
   - HTTP 200 with a list entry whose `name` matches the YAML
     `label` ⇒ the tab is recorded as `skipped` and the existing id
     is reused in the bundle.
2. **CREATE** — `POST /api/v1/ReportFilter` with the entity name, the
   YAML `label` as the filter name, and `data.where` rendered from the
   condition AST. The returned id is captured and used to populate
   `defaultFilter: reportFilter<id>` in the clientDef bundle file.
3. **BUNDLE** — append the scope/clientDef files for this tab and
   merge the label into the per-run `Global.json`.

After all tabs are processed, the run worker emits a
`MANUAL CONFIGURATION REQUIRED` block listing every tab's bundle path
and the rebuild + Tab List steps the operator must perform. This
appears even on the success path because the metadata files cannot be
applied via REST.

#### Cross-references

- `filter:` uses the Section 11 condition expression and the same
  relative-date vocabulary as saved views.
- A saved view (Section 5.6) and a filtered tab can both surface the
  same logical filter — saved views are appropriate when the user
  should pick from a dropdown inside an existing list view; filtered
  tabs are appropriate when the filter deserves its own top-level
  navigation entry.

---

## 6. Field Definitions

Fields are defined in the `fields` list under an entity block.

```yaml
fields:
  - name: mentorStatus
    type: enum
    label: "Mentor Status"
    description: >
      Tracks the lifecycle stage of a mentor. Drives UI visibility
      for departure-related fields. See PRD Section 4.2.
    category: "Mentor Role & Capacity"
    required: false
    default: "Provisional"
    options:
      - "Provisional"
      - "Active"
      - "Inactive"
      - "Departed"
    translatedOptions:
      "Provisional": "Provisional"
      "Active": "Active"
      "Inactive": "Inactive"
      "Departed": "Departed"
    style:
      "Provisional": "info"
      "Active": "success"
      "Inactive": "default"
      "Departed": "danger"
```

### 6.1 Common Field Properties

These properties apply to all field types:

| Property | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Internal field name in lowerCamelCase. No c-prefix |
| `type` | string | yes | Field type (see Section 6.2) |
| `label` | string | yes | Display label shown in the CRM UI |
| `description` | string | recommended | Business rationale and PRD reference for this field |
| `category` | string | no | UI grouping used for layout tab assignment (see Section 7.4) |
| `required` | boolean | no | Whether the field is required. Default: `false` |
| `requiredWhen` | condition | no | Condition expression (Section 11). Field is required when condition evaluates true. Mutually exclusive with `required: true` |
| `default` | string | no | Default value for the field |
| `readOnly` | boolean | no | Whether the field is read-only. Default: `false` |
| `audited` | boolean | no | Whether changes are tracked in the audit log. Default: `false` |
| `visibleWhen` | condition | no | Condition expression (Section 11). Field is shown when condition evaluates true, hidden otherwise. Mutually exclusive with `required: true` |
| `formula` | formula block | no | Declarative formula that computes the field's value. Requires `readOnly: true`. See Section 6.1.3 |
| `externallyPopulated` | boolean | no | Field is populated by an external system rather than user entry or formula. Default: `false`. See Section 6.1.4 |

The `description` property is optional but strongly recommended on all
fields. Fields without a description are flagged in the documentation
generator output.

### 6.1.1 Conditional Requirement

A field may be marked conditionally required using `requiredWhen:`,
which holds a condition expression (see Section 11). When the
condition evaluates true against the record being saved, the field is
required; otherwise it is optional.

```yaml
# Dues entity
- name: paymentDate
  type: date
  label: "Payment Date"
  required: false
  requiredWhen:
    - { field: paymentStatus, op: equals, value: "Paid" }

# Contact entity
- name: applicationDeclineReason
  type: enum
  label: "Application Decline Reason"
  required: false
  requiredWhen:
    - { field: mentorStatus, op: equals, value: "Declined" }
```

Compound triggers use the structured form from Section 11:

```yaml
- name: someField
  required: false
  requiredWhen:
    all:
      - { field: status, op: equals, value: "Active" }
      - any:
          - { field: tier, op: equals, value: "Gold" }
          - { field: tier, op: equals, value: "Platinum" }
```

**Mutual exclusion with `required: true`.** A field must not set both
`required: true` and `requiredWhen:`. Authors who want unconditional
requirement set `required: true`; authors who want conditional
requirement set `required: false` (or omit it) with `requiredWhen:`.
Setting both is a schema validation error.

The deploy manager translates `requiredWhen:` into the target CRM's
native conditional-validation mechanism.

### 6.1.2 Conditional Visibility

A field may be shown or hidden based on record state using
`visibleWhen:`, which holds a condition expression (see Section 11).
When the condition evaluates true against the record being viewed or
edited, the field is shown; otherwise it is hidden.

```yaml
# Dues entity
- name: paymentDate
  type: date
  label: "Payment Date"
  required: false
  requiredWhen:
    - { field: paymentStatus, op: equals, value: "Paid" }
  visibleWhen:
    - { field: paymentStatus, op: equals, value: "Paid" }

# Contact entity
- name: applicationDeclineReason
  type: enum
  required: false
  requiredWhen:
    - { field: mentorStatus, op: equals, value: "Declined" }
  visibleWhen:
    - { field: mentorStatus, op: equals, value: "Declined" }

- name: departureReason
  type: enum
  required: false
  visibleWhen:
    - { field: mentorStatus, op: in, value: ["Resigned", "Departed"] }

- name: departureDate
  type: date
  required: false
  visibleWhen:
    - { field: mentorStatus, op: in, value: ["Resigned", "Departed"] }
```

Compound visibility rules use the structured form from Section 11.

**Mutual exclusion with `required: true`.** A field must not set both
`required: true` and `visibleWhen:`. A field a user is required to
fill in but cannot see is almost always an authoring bug. Authors who
want "required only when visible" should use `requiredWhen:` with the
same condition.

Panel-level visibility uses the same `visibleWhen:` name and the same
Section 11 construct (see Section 7.3).

### 6.1.3 Calculated Fields

A field may be computed declaratively from other fields or from
related-entity records using `formula:`. Calculated fields are
**always read-only** — setting `formula:` on a field that does not
have `readOnly: true` is a schema validation error.

The `formula:` block has three mutually-exclusive types:

| Type | Use when |
|---|---|
| `aggregate` | Counting, summing, averaging, or selecting values across records of a related entity |
| `arithmetic` | Computing a numeric value from other fields on the same record |
| `concat` | Building a text value by concatenating literal strings, same-record fields, and looked-up related-record fields |

#### Aggregate formulas

The `aggregate` type rolls up values from a related entity back to
the current record.

```yaml
# Dues entity — count current active engagements per mentor Contact
- name: currentActiveClients
  type: int
  readOnly: true
  formula:
    type: aggregate
    function: count
    relatedEntity: Engagement
    via: assignedMentor
    where:
      - { field: engagementStatus, op: in, value: ["Active", "Assigned"] }

# Multi-hop: sum of session hours where the mentor on the linked
# Engagement is this Contact
- name: totalMentoringHours
  type: float
  readOnly: true
  formula:
    type: aggregate
    function: sum
    field: hours
    relatedEntity: Session
    via: assignedMentor
    join:
      - { from: Session, link: engagement, to: Engagement }
    where:
      - { field: type, op: equals, value: "Completed" }

# Latest Completed session date (max of a date field expresses "latest")
- name: lastSessionDate
  type: date
  readOnly: true
  formula:
    type: aggregate
    function: max
    field: sessionDate
    relatedEntity: Session
    via: assignedMentor
    join:
      - { from: Session, link: engagement, to: Engagement }
    where:
      - { field: type, op: equals, value: "Completed" }

# last — value of one field, ordered by another. Use when the field
# returned differs from the field ordered by.
- name: lastSessionNotes
  type: text
  readOnly: true
  formula:
    type: aggregate
    function: last
    pickField: notes
    orderBy: { field: sessionDate, direction: desc }
    relatedEntity: Session
    via: assignedMentor
    join:
      - { from: Session, link: engagement, to: Engagement }
    where:
      - { field: type, op: equals, value: "Completed" }

# Relative-date filter (Section 11.4 vocabulary)
- name: totalSessionsLast30Days
  type: int
  readOnly: true
  formula:
    type: aggregate
    function: count
    relatedEntity: Session
    via: assignedMentor
    join:
      - { from: Session, link: engagement, to: Engagement }
    where:
      - { field: type,        op: equals,             value: "Completed" }
      - { field: sessionDate, op: greaterThanOrEqual, value: "lastNDays:30" }
```

**Aggregate functions.**

| Function | Returns | Required clauses |
|---|---|---|
| `count` | integer | (none beyond `relatedEntity` / `via`) |
| `sum` | numeric | `field:` |
| `avg` | numeric | `field:` |
| `min` | same type as field | `field:` |
| `max` | same type as field | `field:` |
| `first` | type of `pickField:` | `orderBy:`, `pickField:` |
| `last` | type of `pickField:` | `orderBy:`, `pickField:` |

`max` of a date field is the cleanest expression for "latest value."
`first` / `last` are reserved for the case where the field being
returned differs from the field being ordered by.

**Aggregate clauses.**

| Clause | Required | Description |
|---|---|---|
| `type` | yes | Must be `aggregate` |
| `function` | yes | One of the seven aggregate functions |
| `field` | see table above | The field on `relatedEntity` being aggregated |
| `pickField` | `first` / `last` only | The field whose value is returned |
| `orderBy` | `first` / `last` only | `{ field, direction }` ordering clause |
| `relatedEntity` | yes | Name of the related entity |
| `via` | yes | Name of the relationship/link from `relatedEntity` back to this entity |
| `join` | multi-hop only | Ordered list of intermediate entity traversals (see below) |
| `where` | no | Section 11 condition expression evaluated against `relatedEntity` records |

**Multi-hop traversal.** When the path from this entity to the target
related entity passes through one or more intermediate entities, use
an explicit `join:` list. Each entry is `{ from: <Entity>, link:
<field>, to: <Entity> }`. The loader validates each hop
independently. Dotted-path strings (e.g., `via: "engagement.assignedMentor"`)
are not supported in v1.1 — explicit joins are required.

#### Arithmetic formulas

The `arithmetic` type computes a numeric value from other fields on
the same record.

```yaml
- name: availableCapacity
  type: int
  readOnly: true
  formula:
    type: arithmetic
    expression: "maximumClientCapacity - currentActiveClients"
```

**Expression syntax (v1.1).** The `expression:` string accepts:

- Field references (by name) — must exist on the same entity
- Integer and float literals
- The four basic operators: `+`, `-`, `*`, `/`
- Parentheses for grouping

No functions (`min`, `max`, `abs`, `round`, `coalesce`, etc.) in v1.1
— they may be added in v1.2 if real use cases arise.

The validator parses the expression at load time. Every field
reference must exist on the entity; bad references fail validation
rather than producing runtime errors.

#### Concat formulas

The `concat` type builds a text value by concatenating literal strings,
same-record fields, and looked-up related-record fields.

```yaml
# Dues.name — auto-generated as "{Mentor Name} — {Billing Year}"
- name: name
  type: varchar
  readOnly: true
  formula:
    type: concat
    parts:
      - { lookup: { via: duesToMentor, field: name } }
      - { literal: " — " }
      - { field: billingYear }
```

**Part types.**

| Part | Description |
|---|---|
| `{ literal: "..." }` | A literal string |
| `{ field: <fieldName> }` | The value of a field on the same record |
| `{ lookup: { via: <relationship>, field: <fieldName> } }` | The value of a field on a record reached via a relationship from this entity |

Parts are concatenated in order. No separators are implied; include
them as literals where needed.

**Numeric and date conversion.** Non-text field values (integers,
floats, dates, booleans) are converted to their natural string
representation when used in `concat`. Date formatting is
CRM-dependent in v1.1; a `format:` clause on `field` / `lookup`
parts is deferred to v1.2.

#### Validation

- `formula:` requires `readOnly: true` on the field
- Exactly one of `type: aggregate`, `type: arithmetic`, or `type:
  concat` must be specified
- All field references (including `field:`, `pickField:`, `where:`
  clauses, `arithmetic.expression` parses, and `concat` parts) are
  validated against the appropriate entity at load time
- Aggregate `function:` must be one of the seven supported functions
- `first` and `last` require both `pickField:` and `orderBy:`
- `count` must not specify `field:`
- `sum`, `avg`, `min`, `max` must specify `field:`
- Multi-hop traversals use explicit `join:` lists; dotted-path `via:`
  strings are not accepted in v1.1

### 6.1.4 Externally-Populated Fields

`externallyPopulated: true` declares that a field's value is supplied
by an external system — for example, a learning-management-system
integration that populates training-completion fields, or a payment
processor that populates dues-payment fields.

```yaml
- name: trainingCompleted
  type: bool
  label: "Training Completed"
  required: false
  externallyPopulated: true
  description: >
    Set automatically by learning management system integration,
    or set manually by Mentor Administrator as fallback if the
    integration is unavailable.

- name: trainingCompletionDate
  type: date
  label: "Training Completion Date"
  required: false
  externallyPopulated: true
```

The flag is a documentation-and-validation marker only. It does not
declare or implement the integration itself. Effects:

- The field is skipped in seed-data import expectations (no warning
  is emitted when it is absent from import data).
- The Verification Spec generator (Phase 13) groups all
  `externallyPopulated` fields under an "External Integration
  Dependencies" section, listing them by entity and noting which
  external system they depend on (taken from the field's
  `description:`).
- The flag is purely informational at deploy time and produces no
  changes to the target CRM's field configuration.

Integration mechanics — connectors, scheduled syncs, webhook
receivers, credentials, transport configuration — are out of scope
for the YAML program-file schema and are handled separately in deploy-
instance configuration.

### 6.2 Supported Field Types

| Type | Display Name | Additional Properties |
|---|---|---|
| `varchar` | Text | `maxLength` |
| `text` | Text (multi-line) | — |
| `wysiwyg` | Rich Text | — |
| `bool` | Boolean | — |
| `int` | Integer | `min`, `max` |
| `float` | Decimal | `min`, `max` |
| `date` | Date | — |
| `datetime` | Date/Time | — |
| `currency` | Currency | — |
| `url` | URL | — |
| `email` | Email | — |
| `phone` | Phone | — |
| `enum` | Enum | `options`, `translatedOptions`, `style`, `isSorted`, `displayAsLabel` |
| `multiEnum` | Multi-select | `options`, `translatedOptions`, `style`, `isSorted` |

**`link` is not a valid field type.** Link relationships between entities
are declared exclusively in the top-level `relationships:` block (Section
8), not in the entity `fields:` block. A field with `type: link` is
rejected at validation time with a hard-reject error. This rule has
existed since v1.0 and is now enforced by `validate_program()`. Reason:
EspoCRM creates link fields automatically from the `relationships:` block
via `EntityManager/action/createLink`; declaring them additionally as
`type: link` fields causes the field-creation API to create stub link
fields without proper foreign-entity wiring, which in turn causes
`createLink` to return HTTP 409 Conflict.

Field-level metadata that an operator might want to attach to a link
relationship (e.g., `description`, `category` for layout grouping) does
not propagate onto link records via the deploy pipeline. If such metadata
is needed, configure it post-deployment via the EspoCRM admin UI. The
relationship payload itself supports `audited` (and `auditedForeign`); see
Section 8.1.

### 6.3 Enum and Multi-Select Properties

These properties apply only to `enum` and `multiEnum` fields:

| Property | Type | Required | Description |
|---|---|---|---|
| `options` | list | yes | Ordered list of allowed values |
| `translatedOptions` | map | no | Display label for each option value |
| `style` | map | no | Color style per option (see Section 6.4) |
| `isSorted` | boolean | no | Sort options alphabetically. Default: `false` |
| `displayAsLabel` | boolean | enum only | Display value as a colored badge. Default: `false` |

### 6.4 Enum Style Values

| Style | Display |
|---|---|
| `null` or omitted | Default (no color) |
| `"default"` | Gray |
| `"primary"` | Blue |
| `"success"` | Green |
| `"danger"` | Red |
| `"warning"` | Orange |
| `"info"` | Light blue |

### 6.5 Numeric Field Properties

These properties apply only to `int` and `float` fields:

| Property | Type | Description |
|---|---|---|
| `min` | integer | Minimum allowed value |
| `max` | integer | Maximum allowed value |

### 6.6 Text Field Properties

This property applies only to `varchar` fields:

| Property | Type | Description |
|---|---|---|
| `maxLength` | integer | Maximum character length |

### 6.7 Naming Conventions

Field names in YAML use lowerCamelCase without any platform-specific
prefix (e.g., `contactType`, not `cContactType`). The tool applies any
required prefix transformations at deployment time.

No two fields within the same entity may have the same `name`.

---

## 7. Layout Definitions

Layouts are defined under a `layout` key within an entity block. See
`features/feat-layouts.md` for the full layout specification.

### 7.1 Layout Types

```yaml
layout:
  detail:
    panels:
      - ...
  list:
    columns:
      - ...
```

| Layout Type | Description |
|---|---|
| `detail` | Fields shown when viewing a record. Panel and tab structure |
| `list` | Columns shown in the entity list view |

### 7.2 Detail Layout — Panel Structure

Each panel in a detail layout has the following properties:

| Property | Type | Required | Description |
|---|---|---|---|
| `label` | string | yes | Panel header label |
| `description` | string | no | Business rationale for this panel grouping |
| `tabBreak` | boolean | no | Render this panel as a tab. Default: `false` |
| `tabLabel` | string | if tabBreak | Short label shown on the tab |
| `style` | string | no | Panel accent color (same values as enum style, Section 6.4) |
| `hidden` | boolean | no | Whether the panel is hidden by default. Default: `false` |
| `visibleWhen` | condition | no | Condition controlling panel visibility (see Section 7.3). Replaces v1.0 `dynamicLogicVisible` |
| `rows` | list | no | Explicit field placement (see Section 7.5) |
| `tabs` | list | no | Category-based sub-tabs (see Section 7.4) |

A panel must have either `rows` or `tabs`, not both.

### 7.3 Panel Visibility (`visibleWhen:`)

Controls when a panel is visible using the Section 11 condition
expression:

```yaml
# Shorthand form — single leaf clause
visibleWhen:
  - { field: contactType, op: contains, value: "Mentor" }

# Structured form — any of several status values
visibleWhen:
  any:
    - { field: mentorStatus, op: equals, value: "Resigned" }
    - { field: mentorStatus, op: equals, value: "Departed" }
```

Field names use natural names without any platform-specific prefix.
The tool applies prefix transformations at deployment time.

**Deprecation of v1.0 `dynamicLogicVisible:`.** In v1.0, panel
visibility was expressed as:

```yaml
dynamicLogicVisible:
  attribute: contactType
  value: "Mentor"
```

This form is accepted in v1.1 with a deprecation warning emitted at
load time and is removed in v1.2. The v1.0 form is equivalent to a
single-clause v1.1 `visibleWhen:` with `op: equals` (or `op: contains`
for a multiEnum field — the loader chooses based on the field's type).
Migrated files should use `visibleWhen:` directly and gain access to
the full Section 11 operator vocabulary.

### 7.4 Category-Based Sub-Tabs

When a panel has `tabs`, each tab references a `category`. The tool
automatically collects all fields whose `category` matches and arranges
them into rows:

```yaml
tabs:
  - label: "Identity"
    category: "Mentor Identity & Contact"
  - label: "Skills"
    category: "Mentor Skills & Expertise"
```

Each tab's `category` value must match the `category` property on at
least one field in the entity's field list.

Fields within a category are placed two per row by default. Fields of
type `wysiwyg`, `text`, or `address` are placed full-width, one per row.

### 7.5 Explicit Rows

When a panel specifies `rows` directly, fields are placed exactly as
specified:

```yaml
rows:
  - [firstName, lastName]
  - [emailAddress, phoneNumber]
  - [address, null]         # null = empty cell
  - [description]           # full-width single field
```

Field names in rows use natural names without any platform-specific
prefix. `null` represents an empty cell used for alignment.

### 7.6 List Layout

List layouts define the columns shown in the entity list view:

```yaml
list:
  columns:
    - field: name
      width: 25
    - field: contactType
      width: 15
    - field: emailAddress
      width: 25
```

| Property | Type | Required | Description |
|---|---|---|---|
| `field` | string | yes | Field name (natural name, no prefix) |
| `width` | integer | no | Column width as a percentage. Columns should sum to ~100 |

---

## 8. Relationship Definitions

Relationships are defined in a top-level `relationships` list, separate
from the `entities` block. See `features/feat-relationships.md` for the
full relationship specification.

**Where links live in the YAML.** Link relationships between entities are
declared exclusively in this top-level `relationships:` block. They are
not also listed as `type: link` fields inside an entity's `fields:`
block — `link` is not a valid field type (Section 6.2). The deploy
pipeline relies on this rule: it routes link creation through
`EntityManager/action/createLink` based on this block alone.
Dual-declaration causes the field-creation API to create stub link
fields that subsequently conflict with `createLink` (HTTP 409). The
rule is enforced at validation time with a hard-reject error.

```yaml
relationships:
  - name: duesToMentor
    description: >
      Links Dues records to the mentor Contact who paid them.
      See PRD Section 6.3.
    entity: Dues
    entityForeign: Contact
    linkType: manyToOne
    link: mentor
    linkForeign: duesRecords
    label: "Mentor"
    labelForeign: "Dues Records"
    audited: false
```

### 8.1 Relationship Properties

| Property | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Identifier for this relationship. Used in reports |
| `description` | string | yes | Business rationale and PRD reference |
| `entity` | string | yes | Primary entity (natural name) |
| `entityForeign` | string | yes | Foreign entity (natural name) |
| `linkType` | string | yes | `oneToMany`, `manyToOne`, or `manyToMany` |
| `link` | string | yes | Link name on the primary entity |
| `linkForeign` | string | yes | Link name on the foreign entity |
| `label` | string | yes | Panel label on the primary entity's detail view |
| `labelForeign` | string | yes | Panel label on the foreign entity's detail view |
| `relationName` | string | manyToMany only | Junction table name |
| `audited` | boolean | no | Track changes in audit log. Default: `false` |
| `auditedForeign` | boolean | no | Track changes on foreign side. Default: `false` |
| `action` | string | no | `skip` to document without deploying. Default: deploy |

### 8.2 Link Types

| Type | Meaning |
|---|---|
| `oneToMany` | One record of the primary entity relates to many of the foreign entity |
| `manyToOne` | Many records of the primary entity relate to one of the foreign entity |
| `manyToMany` | Many records on both sides. Requires `relationName` |

Entity names in relationship definitions use natural names without any
platform-specific prefix. The tool applies prefix transformations at
deployment time.

### 8.3 The `action: skip` Pattern

Relationships that were created manually on the CRM instance before the
YAML file was written can be documented with `action: skip`. The tool
records them in the report but makes no API calls. This ensures full
reproducibility — if the instance were rebuilt from scratch, all
relationships (including previously manual ones) would be created.

---

## 9. Comments and Documentation

YAML comments (lines beginning with `#`) are encouraged throughout
program files. Comments are especially valuable for:

- Explaining why a particular configuration choice was made
- Referencing the PRD section that defines a requirement
- Warning about known quirks or constraints
- Grouping related entities or fields with section headers

```yaml
# --- Custom Entities ---

Engagement:
  description: >
    ...

# --- Native Entities ---

Contact:
  description: >
    ...
```

---

## 10. Validation Rules

Program files are validated before any API calls are made. The following
rules apply to all program files:

**Top-level:**
- `version`, `content_version`, and `description` are required
- `version` must be a recognized schema version

**Entity-level:**
- `description` is required on all entity blocks
- `create` and `delete_and_create` require `type`, `settings.labelSingular`,
  and `settings.labelPlural` (or the deprecated top-level
  `labelSingular` / `labelPlural` in v1.1; see Section 5.1)
- `type` must be one of: `Base`, `Person`, `Company`, `Event`
- `delete` must not contain `fields` or `layout`

**Settings-level:**
- All keys inside `settings:` must be recognized (Section 5.4); unknown
  keys are an error
- `labelSingular` and `labelPlural` are required only for entities with
  `action: create` or `action: delete_and_create`
- Use of any deprecated top-level entity property (`labelSingular`,
  `labelPlural`, `stream`, `disabled`) emits a deprecation warning at
  load time pointing to the equivalent `settings:` location

**Duplicate-detection-level:**
- Each `duplicateChecks:` rule must have a unique `id` within its
  entity
- `fields:` must list at least one field name; every name must exist
  on the entity
- `onMatch: block` requires a non-empty `message`
- `normalize:` keys must be field names listed in `fields:`; values
  must be one of `none`, `lowercase-trim`, `case-fold-trim`, `e164`
- `alertTemplate`, when present, must reference an `id` in the same
  entity's `emailTemplates:` block (Section 5.7, added in Category 7)
- `alertTo`, when present, must be a field name on the entity, a
  literal email address, or a string of the form `role:<role-id>`

**Saved-view-level:**
- Each `savedViews:` rule must have a unique `id` within its entity
- `name` is required
- `columns:`, when present, must list field names that exist on the
  entity
- `filter:` must be a valid condition expression (Section 11)
- `orderBy:`, when present, must reference field names that exist on
  the entity; `direction:` must be `asc` or `desc` (defaults to `asc`)

**Email-template-level:**
- Each `emailTemplates:` entry must have a unique `id` within its
  entity
- `name`, `entity`, `subject`, `bodyFile`, and `mergeFields` are
  required
- `entity:` must match the parent entity block's key
- `bodyFile:` path must resolve to an existing HTML file relative to
  the program YAML
- Every entry in `mergeFields:` must be a real field on `entity`
- Every `{{placeholder}}` in `subject:` or the body file must be
  listed in `mergeFields:`
- Every entry in `mergeFields:` must be used at least once in
  `subject:` or the body file

**Workflow-level:**
- Each `workflows:` entry must have a unique `id` within its entity
- `name`, `trigger`, and `actions` are required; `actions` must be
  non-empty
- `trigger.event` must be one of `onCreate`, `onUpdate`,
  `onFieldChange`, `onFieldTransition`, `onDelete`
- `onFieldChange` and `onFieldTransition` require a valid `field:`
  on the entity; `onFieldTransition` additionally requires `from:`
  and/or `to:`
- `where:`, when present, must be a valid condition expression
  (Section 11)
- Action `type:` must be one of `setField`, `clearField`, `sendEmail`,
  `sendInternalNotification`
- `setField` and `clearField` require `field:` referencing a real
  field on the entity
- `setField.value:` must be a literal, the token `now`, or a valid
  arithmetic expression per Section 6.1.3
- `sendEmail.template:` must reference an `id` in the entity's
  `emailTemplates:` block (Section 5.7)
- `sendEmail.to:` must be a field name on the entity or a literal
  email address
- `sendInternalNotification.to:` must be a literal email address or
  a string of the form `role:<role-id>` or `user:<user-id>`

**Filtered-tab-level:**
- Each `filteredTabs:` entry must have a unique `id` within its entity
- `scope`, `label`, and `filter` are required
- `scope:` must match the regex `^[A-Z][A-Za-z0-9]{0,59}$` (PascalCase,
  starts uppercase, ASCII letters and digits only, max 60 characters)
- `scope:` must be unique across the entire program file (EspoCRM scope
  names occupy a single global namespace)
- `filter:` must be a valid condition expression (Section 11); every
  field reference must resolve against the parent entity
- `acl:`, when present, must be one of `boolean`, `team`, `strict`
  (default `boolean`)
- `navOrder:`, when present, must be a non-negative integer

**Field-level:**
- `name`, `type`, and `label` are required on every field
- `type` must be a supported field type (Section 6.2)
- `type: link` is explicitly rejected — link relationships go in the
  top-level `relationships:` block (Section 8). The validation error
  message points to this rule
- `enum` and `multiEnum` fields must have a non-empty `options` list
- No two fields within the same entity may share the same `name`
- `requiredWhen:`, when present, must be a valid condition expression
  (Section 11)
- A field must not set both `required: true` and `requiredWhen:`
- `visibleWhen:`, when present, must be a valid condition expression
  (Section 11)
- A field must not set both `required: true` and `visibleWhen:`
- `formula:`, when present, requires `readOnly: true`
- `formula.type` must be one of `aggregate`, `arithmetic`, or `concat`
- Aggregate formulas: `function:` must be one of `count`, `sum`,
  `avg`, `min`, `max`, `first`, `last`. `first` / `last` require both
  `pickField:` and `orderBy:`. `count` must not specify `field:`.
  `sum`, `avg`, `min`, `max` must specify `field:`
- Arithmetic formulas: `expression:` must be parseable per Section
  6.1.3 (field refs, numeric literals, `+`, `-`, `*`, `/`, parens).
  Every field reference must exist on the same entity
- Concat formulas: every `field:` reference must exist on the same
  entity; every `lookup.via:` must name a valid relationship; every
  `lookup.field:` must exist on the related entity
- Multi-hop aggregate formulas: every `join:` entry's `from`, `link`,
  and `to` must be valid; the resulting path must connect this entity
  to `relatedEntity`

**Layout-level:**
- Each panel must have `rows` or `tabs`, not both
- `tabBreak: true` requires `tabLabel`
- Each tab `category` must match the `category` of at least one field
  in the entity's field list
- Field names in explicit `rows` must exist in the entity's field list
- A panel may specify either `visibleWhen:` or the deprecated
  `dynamicLogicVisible:`, not both. Use of `dynamicLogicVisible:`
  emits a deprecation warning

**Relationship-level:**
- All required properties must be present (see Section 8.1)
- `manyToMany` relationships must include `relationName`

Validation errors are reported individually with enough detail for the
user to locate and fix each issue. Validation failures prevent the Run
action from proceeding (hard-reject): a YAML file with any validation
error is excluded from the deployment batch entirely, with the error
list shown in the run log and on the file's status row. Other files in
the same batch run normally.

### 10.1 Features Without REST API Write Paths

Three features are recognized at validation and parse time but cannot be
applied via EspoCRM's REST API in their current form:

- **Saved views** (`savedViews:`, Section 5.6) — written to `clientDefs`
  metadata; EspoCRM exposes no public REST endpoint for `clientDefs`
  writes. Manual configuration via the admin UI or by editing
  `custom/Espo/Custom/Resources/metadata/clientDefs/{Entity}.json` on
  disk and rebuilding cache.
- **Duplicate-check rules** (`duplicateChecks:`, Section 5.5) —
  configured through the EntityManager endpoint, not via metadata
  writes. A REST-capable reimplementation against EntityManager is a
  future workstream.
- **Workflows** (`workflows:`, Section 5.8) — implemented in EspoCRM as
  records (CRUD via `/api/v1/Workflow`) and gated on the Advanced Pack
  extension. A REST-capable reimplementation against the Workflow
  entity API is a future workstream.

For these three features, the YAML directives are valid input. The
deploy pipeline acknowledges each item, returns a `NOT_SUPPORTED` status
in the per-feature result list, and consolidates them in a MANUAL
CONFIGURATION REQUIRED block emitted at the end of every run that has
such items. `NOT_SUPPORTED` items do not count as step failures — these
are platform constraints, not deployment errors. The operator
configures the items manually before the deployment is considered
complete.

---

## 11. Shared Condition Expressions

Several v1.1 features use a common condition-expression construct to
specify which records or situations a rule applies to. These features
are:

- Saved view `filter:` (Section 5.6)
- Field-level `requiredWhen:` (Section 6, Category 4)
- Field-level `visibleWhen:` and panel-level `visibleWhen:`
  (Sections 6 and 7, Category 5)
- Calculated field `aggregate.where:` (Section 6, Category 8)
- Workflow `where:` and trigger conditions (Section 5.8, Category 9)

All of them share the same syntax, operator vocabulary, relative-date
vocabulary, and structural forms described in this section.

### 11.1 Structural Forms

**Shorthand form.** A flat list of leaf clauses combined with implicit
AND:

```yaml
- { field: contactType,  op: contains, value: "Mentor" }
- { field: mentorStatus, op: equals,   value: "Active" }
```

**Structured form.** A single `{ all: [...] }` or `{ any: [...] }`
block at the root. `all:` and `any:` blocks are freely nestable and
may contain leaf clauses, other `all:` blocks, or other `any:` blocks:

```yaml
all:
  - { field: contactType, op: contains, value: "Mentor" }
  - any:
      - { field: mentorStatus, op: equals, value: "Active" }
      - { field: mentorStatus, op: equals, value: "Provisional" }
  - { field: backgroundCheckCompleted, op: equals, value: false }
```

The two forms are equivalent where both can express the condition;
shorthand is preferred for pure-AND filters, structured is required
when OR is involved or when mixed conjunction/disjunction is needed.

### 11.2 Leaf Clause Syntax

Every leaf clause has the same shape:

```yaml
{ field: <fieldName>, op: <operator>, value: <value> }
```

- `field` — The name of the field to compare. Must exist on the
  entity the expression is evaluated against. For aggregate `where:`
  clauses (Section 6, Category 8), `field` refers to a field on the
  related entity.
- `op` — One of the operators in Section 11.3.
- `value` — A literal value, a list of literals (for `in` / `notIn`),
  or a relative-date string (Section 11.4). Omitted entirely for
  `isNull` and `isNotNull`.

### 11.3 Operator Vocabulary

| Operator | Applies To | Semantics |
|---|---|---|
| `equals` | any | Field value equals `value` |
| `notEquals` | any | Field value does not equal `value` |
| `contains` | multiEnum, list | `value` is a member of the field's list |
| `in` | any | Field value is in `value` (a list) |
| `notIn` | any | Field value is not in `value` (a list) |
| `lessThan` | numeric, date, datetime | Field value is less than `value` |
| `greaterThan` | numeric, date, datetime | Field value is greater than `value` |
| `lessThanOrEqual` | numeric, date, datetime | Field value is less than or equal to `value` |
| `greaterThanOrEqual` | numeric, date, datetime | Field value is greater than or equal to `value` |
| `isNull` | any | Field value is null / unset. No `value` clause |
| `isNotNull` | any | Field value is not null / unset. No `value` clause |

Operators not listed above (regex matching, case-insensitive compare,
arithmetic on both sides, etc.) are not supported in v1.1.

### 11.4 Relative-Date Vocabulary

Values for date/datetime comparisons may be ISO-format literals (e.g.,
`"2026-04-13"`) or relative-date strings. Supported relative-date
strings:

| String | Resolves to |
|---|---|
| `today` | Current date at load time |
| `yesterday` | Current date minus one day |
| `lastNDays:N` | N days ago (e.g., `lastNDays:30`) |
| `nextNDays:N` | N days from now (e.g., `nextNDays:7`) |
| `thisMonth` | First day of the current month |
| `lastMonth` | First day of the previous month |

Relative-date strings are resolved at rule-evaluation time by the
target CRM, not at YAML load time. Additional tokens may be added in
future minor versions.

### 11.5 Validation

- Every `field:` referenced in a leaf clause must exist on the entity
  the expression is evaluated against (or on the related entity for
  aggregate `where:` clauses)
- `op:` must be one of the operators in Section 11.3
- `in` and `notIn` require `value:` to be a list
- `lessThan`, `greaterThan`, `lessThanOrEqual`, `greaterThanOrEqual`
  require `value:` to be numeric, a date, a datetime, or a
  relative-date string
- `isNull` and `isNotNull` must not include a `value:` clause
- Structured form: `all:` and `any:` values must each be a non-empty
  list
- Structured form: the root of a `filter:` may contain either a flat
  list (shorthand) or a single `all:` / `any:` object, not both
