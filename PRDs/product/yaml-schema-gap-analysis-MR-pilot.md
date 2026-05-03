# YAML Schema Gap Analysis — MR Pilot Findings

**Pilot:** Cleveland Business Mentors Process Validation Pilot
**Source:** `ClevelandBusinessMentoring/programs/MR/MANUAL-CONFIG.md` (Phase 9, 04-13-26)
**Purpose:** For each Manual Configuration category produced by the MR
pilot, decide whether the CRM Builder YAML schema should be extended to
express the configuration declaratively, defer the gap, or leave it out
of scope. Each section records the source items, a proposed YAML syntax
sketch, implementation considerations, a recommended priority, and any
open design questions.

This document is a working design artifact. Once the categories are
walked and decisions recorded, the green-lit items will be promoted to
a focused L2 PRD update (currently L2 PRD v1.16 → v1.17) and then to
implementation prompts.

**Priority scale.** Must = block next pilot domain; Should = address
before MR goes to production; Could = nice-to-have, defer to future
release; Defer = out of scope for v1.x; Out of scope = not a YAML
schema concern.

**EXCEPTIONS.md framing.** The five Phase 9 exceptions are upstream
PRD reconciliation issues (TBD value lists, field-name mismatches),
not YAML capability gaps. They are addressed by tightening the Phase 7
Domain Reconciliation guide, recorded as a separate pilot finding,
and otherwise out of scope for this gap analysis.

## Change Log

| Date | Change |
|---|---|
| 04-13-26 22:00 | Initial gap analysis covering Categories 1–10 from MR pilot Manual Configuration findings. |
| 05-03-26 14:00 | Added Category 6 Part D — Panel and layout visibility by role. Captures gap raised during yaml-v1.1 deployment review: panel-level `visibleWhen:` (Section 7.3) cannot reference user role, and layouts cannot be scoped to roles. Proposes role-aware leaf clauses in Section 11 (Part D.1) and `forRoles:` on layout declarations (Part D.2). Targeted for v1.2 alongside Parts A–C. |

---

## 1. Stream and Audit Logging

**Source items.** MR-MC-AU-001 (Contact entity stream enable),
MR-MC-AU-002 (audit verification, no YAML change required).

### Analysis

Two items, different in kind:

- **MR-MC-AU-002 is not a real gap.** YAML already supports
  `audited: true` per field, and the three relevant fields
  (`contactType`, `mentorStatus`, `paymentStatus`) already have it
  set. The MANUAL-CONFIG entry is a "verify after deployment"
  reminder. The right home for this is the Verification Spec
  (Phase 13 output), not the YAML schema. No YAML enhancement
  needed.
- **MR-MC-AU-001 is a small but real gap.** YAML can set `stream`
  when *creating* a custom entity (e.g., `stream: false` on Dues),
  but cannot toggle the stream flag on a *native* entity such as
  Contact. The MR YAML files only add fields to native Contact —
  they cannot modify Contact's own stream setting.

### Proposed YAML capability

Introduce a new optional `settings:` block on every entity (native or
custom) that holds entity-level configuration. All entity
configuration moves into this block from its current top-level
location. The top level keeps only structural / deploy directives
(`description`, `action`, `type`).

**Before (today):**

```yaml
entities:
  Dues:
    description: ...
    action: create
    type: Base
    labelSingular: "Dues"
    labelPlural: "Dues"
    stream: false
    fields:
      - name: billingYear
        ...
```

**After (proposed):**

```yaml
entities:
  Dues:
    description: ...
    action: create
    type: Base
    settings:
      labelSingular: "Dues"
      labelPlural: "Dues"
      stream: false
      # future entity-level toggles also go here:
      # defaultSortBy: name
      # defaultSortOrder: asc
      # color: "#1F3864"
      # iconClass: "fas fa-dollar-sign"
      # disabled: false
    fields:
      ...

  # Native entity — also uses settings: to override CRM defaults
  Contact:
    settings:
      stream: true
    fields:
      ...
```

### Implementation considerations

- The deploy manager needs a CHECK→ACT path for entity settings,
  parallel to the existing field, layout, and relationship paths.
  Settings drift detection (CHECK) reads the current entity
  configuration from the CRM API and compares to the YAML.
- `settings:` on a native entity is an *override* to whatever the
  CRM ships with by default. `settings:` on a custom entity is the
  *original declaration*. From the YAML reader's perspective these
  look identical; the deploy manager handles the distinction.
- Backward compatibility: the existing top-level `stream`,
  `labelSingular`, `labelPlural` keys on custom entities should
  continue to work for at least one minor version, with a
  deprecation warning emitted on load. A migration helper script
  in `tools/` could rewrite v1.0 YAMLs forward.
- The `settings:` key list should be defined in the YAML schema
  spec and validated at load time. Unknown keys fail validation
  rather than silently passing through.

### Recommended priority

**Should.** Small scope, fixes a real gap on Contact in the MR
pilot. Becomes **Must** if Account, Engagement, Session, or any
future domain entity also needs stream toggled — which is likely
once those domains run Phase 9.

### Open questions / decisions recorded

- **Q1 (resolved):** Scope of `settings:` block — anticipate other
  settings up front, do not scope minimally to just `stream`.
- **Q2 (resolved):** Native vs custom entity behavior — full
  migration, all entity-level settings move into `settings:` for
  both native and custom entities. Top level keeps only
  `description`, `action`, `type`.

---

## 2. Duplicate Detection Rules

**Source items.** MR-MC-DD-001 (Contact duplicate detection on
`personalEmail`).

### Analysis

One item in MR pilot, but high-leverage. Duplicate detection is a
near-universal CRM concern — future domains will want it on Account
(name + city, EIN), on Contact for other fields (work email), and
likely on more entities as the implementation grows.

The schema must support:

1. Single-field and compound-field checks.
2. Configurable match action (block vs. warn).
3. Per-field normalization (email lowercased, names case-folded,
   phones E.164-normalized).

### Proposed YAML capability

A new optional `duplicateChecks:` block at the entity level, sibling
to `settings:` and `fields:`. Each rule lists participating fields,
the match action, an optional normalization map, and a user-facing
message.

```yaml
entities:
  Contact:
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
      # Future compound example:
      # - id: account-name-city
      #   fields: [name, billingCity]
      #   normalize:
      #     name: case-fold-trim
      #     billingCity: case-fold-trim
      #   onMatch: warn
    fields:
      ...
```

### Implementation considerations

- The deploy manager needs a CHECK→ACT path for duplicate-check
  rules, parallel to fields, layouts, relationships, and settings.
- Supported `onMatch` values in v1: `block` (reject the create) and
  `warn` (allow but flag). Merge-prompt and similar UI flows are
  target-CRM concerns and not declarable from YAML in v1.
- Supported `normalize` values in v1: `lowercase-trim`,
  `case-fold-trim`, `e164`, `none` (default). Small named
  vocabulary; no expression language for a config field.
- Rule `id` is required and unique within the entity so drift
  detection can identify and update an existing rule rather than
  recreating it on every deploy.
- `message` is required when `onMatch: block`; optional when
  `onMatch: warn`.

### Recommended priority

**Should.** One item in MR pilot, but every CRM implementation will
hit this on Contact and Account at minimum. Cheap once the CHECK→ACT
plumbing from Category 1 is in place.

### Open questions / decisions recorded

- **Q1 (resolved):** Placement — sibling to `settings:`, not nested
  inside it. `settings:` is for scalar toggles; rule blocks with
  their own structure live at their own top level.
- **Q2 (resolved):** `onMatch` vocabulary for v1 — `block` and
  `warn` only. No `log-only`.

---

## 3. Saved Views and List Filters

**Source items.** MR-MC-SV-001 (Mentor — Active), MR-MC-SV-002
(Mentor — Prospects), MR-MC-SV-003 (Mentor — Submitted
Applications), MR-MC-SV-004 (Dues — Outstanding), MR-MC-SV-005
(Mentor — Inactivity Alert).

### Analysis

Five items in the MR pilot, scaling to dozens across all domains
(MN, MR, CR, FU). Every implementation will accumulate a similar
roster of standard list views; recreating them by hand in the target
CRM after every deployment is wasteful and error-prone.

The five examples cover a narrow but representative range:
single-value equality, multiEnum membership (`contains`), value-set
membership (`in`), past-date comparison, and conjoint conditions on
three fields. None of the five strictly requires OR or nested
grouping, but the design supports both because real-world saved
views regularly need them and the cost of designing the structure
now is low.

### Proposed YAML capability

A new `savedViews:` block at the entity level, sibling to
`settings:`, `duplicateChecks:`, and `fields:`. Each saved view
declares an `id`, a display `name`, an optional `description`, the
`columns` to show, a `filter`, and an optional `orderBy`.

The `filter` accepts two forms:

- **Shorthand** — a flat list of clauses combined with implicit
  AND.
- **Structured** — an `all:` or `any:` block, freely nestable, for
  expressing OR conditions and complex grouping.

```yaml
entities:
  Contact:
    settings:
      stream: true
    savedViews:

      # Shorthand form (implicit AND across clauses)
      - id: mentor-active
        name: "Mentor — Active"
        description: "All currently active mentors."
        columns: [name, primaryEmail, mentorStatus, currentActiveClients, availableCapacity]
        filter:
          - { field: contactType,  op: contains, value: "Mentor" }
          - { field: mentorStatus, op: equals,   value: "Active" }
        orderBy: { field: name, direction: asc }

      - id: mentor-prospects
        name: "Mentor — Prospects"
        columns: [name, personalEmail, mentorStatus, lastModifiedAt]
        filter:
          - { field: contactType,  op: contains, value: "Mentor" }
          - { field: mentorStatus, op: equals,   value: "Prospect" }
        orderBy: { field: lastModifiedAt, direction: desc }

      - id: mentor-submitted-applications
        name: "Mentor — Submitted Applications"
        columns: [name, personalEmail, mentorStatus, createdAt]
        filter:
          - { field: contactType,  op: contains, value: "Mentor" }
          - { field: mentorStatus, op: in,       value: ["Submitted", "In Review"] }
        orderBy: { field: createdAt, direction: asc }

      - id: mentor-inactivity-alert
        name: "Mentor — Inactivity Alert"
        columns: [name, primaryEmail, totalSessionsLast30Days, lastSessionDate]
        filter:
          - { field: contactType,             op: contains, value: "Mentor" }
          - { field: mentorStatus,            op: equals,   value: "Active" }
          - { field: totalSessionsLast30Days, op: equals,   value: 0 }
        orderBy: { field: lastSessionDate, direction: asc }

      # Structured form — illustrates OR via any:, freely nestable
      - id: mentor-needs-attention   # illustrative, not from MR pilot
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
      ...

  Dues:
    savedViews:
      - id: dues-outstanding
        name: "Dues — Outstanding"
        columns: [name, billingYear, amount, dueDate, paymentStatus]
        filter:
          - { field: paymentStatus, op: equals,   value: "Unpaid" }
          - { field: dueDate,       op: lessThan, value: "today" }
        orderBy: { field: dueDate, direction: asc }
    fields:
      ...
```

### Implementation considerations

- The deploy manager needs a CHECK→ACT path for saved views,
  parallel to other entity-level structures.
- Supported `op` values in v1: `equals`, `notEquals`, `contains`,
  `in`, `notIn`, `lessThan`, `greaterThan`, `lessThanOrEqual`,
  `greaterThanOrEqual`, `isNull`, `isNotNull`. Small fixed set; no
  expression language.
- Supported relative-date string values: `today`, `yesterday`,
  `lastNDays:30`, `nextNDays:7`, `thisMonth`, `lastMonth`. Limited
  and named; extend the list later if needed.
- `filter:` accepts either a flat list (implicit AND) or a single
  `{ all: [...] }` / `{ any: [...] }` block. `all:` and `any:`
  blocks may nest freely and may contain leaf clauses, other
  `all:` blocks, or other `any:` blocks.
- `orderBy` is optional; format is
  `{ field: <fieldName>, direction: asc|desc }`. Multiple
  orderings can be expressed as a list of such objects when
  needed.
- `columns:` lists field names in display order. Optional; if
  omitted, the CRM's default columns are used.
- `name` is the user-visible label; `id` is the stable identifier
  for drift detection.
- The MR-MC-SV-004 description references a "configurable grace
  window" for overdue dues. That is a separate problem (a
  system-level configurable parameter) and is out of scope for the
  saved-view itself — the YAML expresses the filter; the
  grace-window configuration would belong in a future
  system-settings facility.

### Recommended priority

**Should.** Five items in MR pilot, scaling to dozens across
domains. Saves real administrative effort on every deployment and
re-deployment.

### Open questions / decisions recorded

- **Q1 (resolved):** Per-view role/persona scoping — none in v1.
  All saved views are visible to all users. Role-scoped visibility
  comes later, alongside a general Roles declaration in YAML.
- **Q2 (resolved):** Filter logic — support both shorthand
  (flat-list implicit AND) and structured (`all:` / `any:` blocks,
  freely nestable) forms in v1.
- **Q3 (resolved):** Default sort — yes, optional `orderBy:`
  clause supported in v1.

---

## 4. Conditional-Required Logic

**Source items.** MR-MC-CR-001 (Dues `paymentDate` required when
Paid), MR-MC-CR-002 (Dues `paymentMethod` required when Paid),
MR-MC-CR-003 (Contact `applicationDeclineReason` required when
Declined), MR-MC-CR-004 (Contact background check fields
conditionally required by administrative decision).

### Analysis

Three of four items are clean field-driven rules ("field X is
required when field Y has value Z"). The fourth (MR-MC-CR-004) is
conditioned on an out-of-band administrative decision — the
MANUAL-CONFIG entry itself notes this "may be operational discipline
rather than system-enforced conditional requiring." MR-MC-CR-004 is
therefore not addressed by this capability and stays on the Manual
Configuration list as operational discipline.

This category introduces the first **condition expression** — a
field/operator/value comparison construct. The same construct is
reused in Category 5 (Field-Level Dynamic Logic) and likely in
Category 9 (Workflows). The shorthand and structured forms from
Category 3 saved-view filters apply here as well, for cross-category
consistency.

### Proposed YAML capability

Add an optional `requiredWhen:` clause to any field. The static
`required:` flag and `requiredWhen:` are mutually exclusive — schema
validation rejects a field that sets both.

```yaml
# Dues entity
- name: paymentDate
  type: date
  label: "Payment Date"
  required: false
  requiredWhen:
    - { field: paymentStatus, op: equals, value: "Paid" }

- name: paymentMethod
  type: enum
  label: "Payment Method"
  required: false
  requiredWhen:
    - { field: paymentStatus, op: equals, value: "Paid" }

# Contact custom field added by MR-Contact.yaml
- name: applicationDeclineReason
  type: enum
  label: "Application Decline Reason"
  required: false
  requiredWhen:
    - { field: mentorStatus, op: equals, value: "Declined" }

# Compound case (illustrative; supported by structured form)
- name: someField
  required: false
  requiredWhen:
    all:
      - { field: status, op: equals, value: "Active" }
      - any:
          - { field: tier, op: equals, value: "Gold" }
          - { field: tier, op: equals, value: "Platinum" }
```

### Implementation considerations

- Field validation now has two evaluation paths: static
  (`required: true`) and dynamic (`requiredWhen` evaluated on
  save).
- Operator vocabulary and shorthand/structured forms mirror
  Category 3 saved-view filters. Deliberate cross-category
  consistency.
- The deploy manager translates `requiredWhen:` into the target
  CRM's native conditional-required mechanism (typically a
  "dynamic logic" or "conditional validation" rule attached to the
  field).
- Drift detection: changes to `requiredWhen:` are detected and
  reapplied alongside changes to other field properties.
- Schema validation rejects any field that sets both `required:
  true` and `requiredWhen:` — these almost always indicate
  authoring confusion. Authors who want "always required" set
  `required: true`; authors who want "conditionally required" set
  `required: false` with `requiredWhen:`.
- MR-MC-CR-004 (background check fields) is **not addressed by
  this capability**. The trigger is administrative discretion
  rather than a field condition; it stays on the Manual
  Configuration list as operational discipline.

### Recommended priority

**Should.** Three of four MR-pilot items addressed; the fourth is
genuinely manual. Conditional-required is a near-universal
requirement; absence of it in YAML v1.0 was a real friction point.

### Open questions / decisions recorded

- **Q1 (resolved):** Naming — `requiredWhen:`.
- **Q2 (resolved):** Interaction with static `required:` — schema
  validation rejects fields that set both. Mutually exclusive.

---

## 5. Field-Level Dynamic Logic

**Source items.** MR-MC-DL-001 (Dues `paymentDate` visible when
Paid), MR-MC-DL-002 (Dues `paymentMethod` hidden when Waived),
MR-MC-DL-003 (Contact `applicationDeclineReason` visible when
Declined), MR-MC-DL-004 (Contact `departureReason` and
`departureDate` visible when Resigned or Departed).

### Analysis

Natural sibling of Category 4 — same condition-expression construct
applied to visibility instead of required. The MANUAL-CONFIG note
observes that YAML v1.0 already supports panel-level
`dynamicLogicVisible:` but not field-level. The gap is well-defined:
extend the existing dynamic-logic mechanism down to the field.

The four examples are structurally near-identical to the Category 4
cases — three of the four conditional-required fields
(`paymentDate`, `paymentMethod`, `applicationDeclineReason`)
reappear here as conditional-visibility fields. Most fields that
are conditionally required are also conditionally visible.

### Proposed YAML capability

Add an optional `visibleWhen:` clause to any field, parallel to
`requiredWhen:`. Same shorthand/structured forms, same operator
vocabulary as Categories 3 and 4. The existing panel-level
`dynamicLogicVisible:` is renamed to `visibleWhen:` for consistency,
with `dynamicLogicVisible:` accepted as a deprecated alias for one
minor version then removed.

```yaml
# Dues entity
- name: paymentDate
  type: date
  required: false
  requiredWhen:
    - { field: paymentStatus, op: equals, value: "Paid" }
  visibleWhen:
    - { field: paymentStatus, op: equals, value: "Paid" }

- name: paymentMethod
  type: enum
  required: false
  requiredWhen:
    - { field: paymentStatus, op: equals, value: "Paid" }
  visibleWhen:
    - { field: paymentStatus, op: notEquals, value: "Waived" }
    # MR-MC-DL-002 also notes "effectively hidden when Unpaid"
    # because there is no method to display before payment. Using
    # notEquals: Waived intentionally keeps paymentMethod visible
    # during Unpaid so the data-entry path can fill it in once
    # payment is recorded. notIn: ["Waived", "Unpaid"] is also
    # expressible if stricter hiding is preferred.

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

# Panel-level use of the same construct (renamed from
# dynamicLogicVisible:)
panels:
  - name: "Departure Details"
    visibleWhen:
      - { field: mentorStatus, op: in, value: ["Resigned", "Departed"] }
    fields: [departureReason, departureDate]
```

### Implementation considerations

- The deploy manager translates field-level `visibleWhen:` into
  the target CRM's native field-level dynamic-logic mechanism.
  Panel-level translation already exists; the field-level path
  follows the same pattern at finer granularity.
- Operator vocabulary and shorthand/structured forms mirror
  Categories 3 and 4. The same condition expression appears in
  saved-view filters, `requiredWhen:`, and `visibleWhen:`.
- Schema validation rejects any field that sets both `required:
  true` and `visibleWhen:`. A field a user is required to fill in
  but cannot see is almost always an authoring bug. Authors who
  want "required only when visible" should use `requiredWhen:`
  with the same condition.
- Drift detection handles `visibleWhen:` alongside other field
  properties.
- Rename of panel-level `dynamicLogicVisible:` to `visibleWhen:`
  is a coordinated rename: the loader accepts both for one minor
  version, emits a deprecation warning when the old name is used,
  and removes the old name in the next minor version. A migration
  helper script in `tools/` rewrites existing YAML files forward.

### Recommended priority

**Should.** Four items in MR pilot, near-universal need across
domains. Trivial incremental cost given Categories 3 and 4
establish the condition-expression mechanics.

### Open questions / decisions recorded

- **Q1 (resolved):** Rename panel-level construct — yes, rename
  `dynamicLogicVisible:` to `visibleWhen:` with one-minor-version
  deprecation alias.
- **Q2 (resolved):** Required-but-invisible — schema validation
  errors when `required: true` and `visibleWhen:` are combined on
  the same field. Authors should use `requiredWhen:` instead.

---

## 6. Field-Level Access Control

**Source items.** MR-MC-AC-001 (ten Contact fields admin-only),
MR-MC-AC-002 (ten Contact fields mentor-editable when
`mentorStatus = "Active"`).

### Analysis

Substantially harder than Categories 1–5, for two reasons:

1. **YAML has no Roles concept yet.** MR-MC-AC-001 references the
   Mentor Administrator persona MST-PER-005 — defined in the
   Master PRD, not in any YAML file. Roles must be declared in
   YAML before field permissions can grant access to them.
2. **MR-MC-AC-002 introduces a state-dependent permission.**
   Mentor-editability of ten fields depends on the *record's own*
   `mentorStatus`. That is a record-level access rule, not a
   pure field-level rule, and crosses into territory that most
   CRMs handle through scripting or role-based row filters.

The MANUAL-CONFIG entry on MR-MC-AC-002 explicitly notes neither
piece is expressible in YAML v1.0. Both deserve careful design
across at least one more pilot domain before commitment.

### Proposed YAML capability — three parts

#### Part A — Roles declaration (prerequisite)

A dedicated roles file applied before any domain file. Each role
maps to one or more Master PRD personas.

```yaml
# programs/roles.yaml — applied before any domain program file
roles:
  - id: mentor-administrator
    name: "Mentor Administrator"
    persona: MST-PER-005
    description: >
      Manages mentor recruitment, onboarding, and lifecycle.
      Owns acceptance, background check, and decline workflows.

  - id: mentor
    name: "Mentor"
    persona: MST-PER-011
    description: >
      Active mentor with self-service edit access to public-facing
      profile fields when their mentorStatus is Active.

  - id: system-administrator
    name: "System Administrator"
    persona: MST-PER-001
```

#### Part B — Field-level permissions

Add an optional `permissions:` clause to any field. Each role
listed gets `read` and `edit` settings, each of which is `yes`,
`no`, or a condition expression (the same construct from Categories
3–5). Roles not listed inherit the entity's default permissions.

```yaml
# Static admin-only field (MR-MC-AC-001 pattern)
- name: backgroundCheckCompleted
  type: bool
  permissions:
    mentor-administrator:
      read: yes
      edit: yes
    mentor:
      read: no
      edit: no

# State-dependent mentor-editable field (MR-MC-AC-002 pattern)
- name: professionalBio
  type: text
  permissions:
    mentor:
      read: yes
      edit:
        - { field: mentorStatus, op: equals, value: "Active" }
    # mentor-administrator inherits entity defaults (full access)
```

#### Part C — Permission presets

Named bundles declared once, referenced per field by name to avoid
repeating the same `permissions:` block on twenty fields.

```yaml
permissionPresets:
  admin-only:
    mentor-administrator: { read: yes, edit: yes }
    mentor:                { read: no,  edit: no  }
  mentor-editable-when-active:
    mentor:
      read: yes
      edit:
        - { field: mentorStatus, op: equals, value: "Active" }

# Then per field:
- name: backgroundCheckCompleted
  type: bool
  permissions: admin-only

- name: professionalBio
  type: text
  permissions: mentor-editable-when-active
```

#### Part D — Panel and layout visibility by role

**Source.** Pilot question raised during yaml-v1.1 deployment
review (05-03-26): can a panel of fields be hidden entirely based
on the viewing user's role, rather than declaring `permissions:`
on every individual field in the panel?

**Current gap.** Schema v1.1 Section 7.3 panel-level `visibleWhen:`
uses the Section 11 condition expression, whose leaf clauses
reference fields on the record being evaluated. There is no
operator that references the current user's role, so panels
cannot be hidden by role. The same gap applies at the layout
level — there is no way to declare "this layout for these roles,
that layout for those roles" in YAML. Both situations currently
fall back to post-deployment manual configuration in the target
CRM.

**Proposed YAML capability — two parts.**

**Part D.1 — Role-aware leaf clauses in Section 11.** Extend the
shared condition expression to accept a `role:` leaf clause
alongside the existing `field:` form:

```yaml
# Shorthand — single role
visibleWhen:
  - { role: equals, value: "mentor-administrator" }

# Set of roles
visibleWhen:
  - { role: in, value: [mentor-administrator, system-administrator] }

# Compound — role OR record state
visibleWhen:
  any:
    - { role: in, value: [mentor-administrator, system-administrator] }
    - { field: mentorStatus, op: equals, value: "Active" }
```

This form is available everywhere `visibleWhen:` is used (panel
level and field level) and reuses the existing `equals`,
`notEquals`, `in`, `notIn` operators. Other Section 11 consumers
(saved view `filter:`, workflow `where:`, aggregate `where:`)
are out of scope for `role:` since they evaluate against records,
not viewing context.

**Part D.2 — Layout-level role scoping.** Allow a layout
declaration to specify which roles see it:

```yaml
layouts:
  - name: detail
    forRoles: [mentor-administrator, system-administrator]
    panels:
      - label: "Administrative"
        rows: [...]

  - name: detail
    forRoles: [mentor]
    panels:
      - label: "My Profile"
        rows: [...]
```

When `forRoles:` is omitted, the layout applies to all roles
(current behavior).

**Relationship to Parts A–C.** Part D depends on Part A (Roles
declaration must exist before role IDs can be referenced). Part D
does not replace Part B — field-level `permissions:` remain the
right tool for read/edit asymmetry on individual fields, while
Part D is the right tool for hiding whole panels or swapping
whole layouts.

**Implementation note.** Target-CRM mappings differ. Some CRMs
express role-based panel visibility through dynamic-logic
expressions that include user attributes; others do it through
per-role layout assignment. The deploy manager hides the
difference, but the loader must validate that any `role:` ID
referenced exists in the roles declaration before deployment.

**Open questions / decisions to record at design time.**

- **Q4:** Should `role:` be a separate leaf-clause discriminator
  (`role:` vs `field:`) or a reserved field name (`field: $role`)?
  Separate discriminator is clearer; reserved name is more
  uniform with the existing parser. Recommendation: separate
  discriminator.
- **Q5:** Does `forRoles:` on a layout need a fallback layout for
  roles not listed, or is omission an error caught by the
  loader? Recommendation: loader error — every role must resolve
  to exactly one layout per layout name.
- **Q6:** Should Part D ship in v1.2 alongside Parts A–C, or be
  staged separately? Recommendation: ship together — Part A is
  the prerequisite for both, and pilot users will hit Part D
  needs the moment they try to use Part B at scale.

### Implementation considerations

- The deploy manager needs CHECK→ACT paths for both Roles and
  field-level permissions. Role creation/update is a new
  entity-class operation, parallel to fields and relationships.
- Roles must exist before any field references them; the loader
  validates this and orders deployment accordingly. Dedicated
  roles file applied first per Q2.
- Persona IDs (MST-PER-*) must match those defined in the Master
  PRD. The loader can optionally validate against a known list,
  though this means reading outside the immediate program file.
- State-dependent edit rules (Part B condition expressions)
  translate to the target CRM's record-level access mechanism.
  Some CRMs handle this natively; others need scripting. The
  deploy manager hides the difference.
- `permissionPresets:` is a YAML-only convenience — it expands to
  inline `permissions:` blocks at load time. The CRM never sees
  the preset name.
- This category deserves a dedicated Phase 9 session prompt or
  interview rather than a sub-decision inside a broader YAML
  generation conversation.

### Recommended priority

**Could** for v1.1; **Should** for v1.2 once Roles is designed
across a second pilot domain.

The reasoning: this category is meaningfully more complex than
Categories 1–5, requires a brand-new top-level concept (Roles), and
the MR pilot's two access-control items are specific enough to
remain Manual Configuration for one more pilot cycle without
serious pain. Better to design Roles thoughtfully against a future
MN, CR, or FU pilot than to rush a Mentor-Administrator-only
design now.

### Open questions / decisions recorded

- **Q1 (resolved):** Defer to v1.2. The two MR-pilot items remain
  on the Manual Configuration list for the immediate next pilot
  cycle. Roles capability designed in conjunction with another
  domain's pilot, then this category lands together.
- **Q2 (resolved):** Roles location — dedicated roles file
  (`programs/roles.yaml`), applied before any domain program file.
- **Q3 (resolved):** Permission presets supported from the start.
  Twenty fields in the MR pilot alone already justify the
  facility.

---

## 7. Email Templates

**Source items.** MR-MC-ET-001 (application confirmation),
MR-MC-ET-002 (application decline, varies by reason), MR-MC-ET-003
(duplicate-email administrator alert).

### Analysis

A different kind of category from the others. The MANUAL-CONFIG
entries say content "is not defined in any Product Requirements
Document" and "Administrator to decide and author." Template
**content** is genuinely manual — it is a content-authoring
problem, not a YAML schema problem.

But template **registration** is YAML-addressable. Workflows
(Category 9) will need to reference templates by stable identifier;
those identifiers should be declared in YAML, version-controlled
alongside everything else, even if the body text is authored by a
human.

### Proposed YAML capability

A new top-level `emailTemplates:` block. Each template has a stable
`id`, a display `name`, the entity it operates against, the subject
line, a path to an external HTML body file, and the explicit list
of merge fields the template uses. Body content lives in HTML files
co-located with the YAML in a per-domain `templates/` subdirectory.

```yaml
emailTemplates:

  - id: mentor-application-confirmation
    name: "Mentor Application Confirmation"
    description: >
      Sent on creation of a new Contact with contactType containing
      "Mentor" and mentorStatus = "Submitted". See MR-MC-WF-001.
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
      handled inside the body template. See MR-MC-WF-002.
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
      Internal notification to Mentor Administrator when an
      application submission collides with an existing personal
      email. See MR-MC-WF-003.
    entity: Contact
    audience: role:mentor-administrator   # documentation hint in v1
    subject: "Duplicate mentor application: {{personalEmail}}"
    bodyFile: "templates/mentor-duplicate-email-alert.html"
    mergeFields:
      - personalEmail
      - existingContactName
      - submissionTimestamp
```

### Implementation considerations

- The deploy manager needs a CHECK→ACT path for email templates:
  create or update each template in the target CRM, comparing both
  metadata (subject, merge field list) and body content (file
  hash) against deployed state.
- `bodyFile` paths resolve relative to the program file, matching
  the pattern used elsewhere in the project structure.
- Body file format is HTML with `{{mergeField}}` placeholders.
  Workflows (Category 9) reference the template by `id` to send.
- Merge fields are required and validated at deploy time. Each
  entry in `mergeFields:` must correspond to a real field on the
  named `entity`; bad references fail validation rather than
  producing broken templates at runtime. Unused merge fields in
  the body also fail validation.
- Template files live in a per-domain `templates/` subdirectory
  co-located with the YAML, e.g.,
  `programs/MR/templates/mentor-application-confirmation.html`.
  Mirrors the existing per-domain YAML organization, keeps
  cross-domain independence, avoids a giant flat templates folder
  as domains accumulate.
- Content authoring remains a human task — but the resulting file
  is in the repo, version-controlled, reviewable, and round-trips
  cleanly through Phase 9 → Phase 12 → Phase 13. Substantial
  improvement over "log in to the CRM and type into a textbox."
- The `audience:` clause on MR-MC-ET-003 is a free-form
  documentation string in v1. Proper role-based audience handling
  is deferred to Category 6 v1.2.

### Recommended priority

**Should.** Three items in MR pilot; every domain that triggers
any user-visible automation will need email templates. Cheap once
Categories 1–5 plumbing exists.

### Open questions / decisions recorded

- **Q1 (resolved):** Body location — external HTML files only, no
  inline body strings, no hybrid.
- **Q2 (resolved):** Merge field list — required and validated at
  deploy time. Catches typos and stale references before the first
  send.
- **Q3 (resolved):** Template file location — per-domain
  `templates/` subdirectory co-located with the YAML.

---

## 8. Calculated Field Formulas

**Source items.** MR-MC-CF-001 (Contact.currentActiveClients),
MR-MC-CF-002 (Contact.availableCapacity), MR-MC-CF-003
(Contact.totalLifetimeSessions), MR-MC-CF-004
(Contact.totalMentoringHours), MR-MC-CF-005
(Contact.totalSessionsLast30Days), MR-MC-CF-006 (Dues.name
auto-generation).

### Analysis

The second-largest jump in schema complexity (after Category 6
Roles). Six MR-pilot formulas cluster into three shapes:

1. **Aggregate over related records** (CF-001, CF-003, CF-004,
   CF-005) — count or sum across a related entity, possibly with
   a multi-hop relationship traversal and a date filter.
2. **Arithmetic on same-record fields** (CF-002) — pure local
   computation.
3. **String concatenation with related-record lookup** (CF-006) —
   pull a field through a relationship and concatenate with local
   values.

A real expression language is unnecessary for these six cases.
Three structured formula types (`aggregate`, `arithmetic`,
`concat`) cover everything, with one small string parser confined
to `arithmetic.expression`.

The aggregate function vocabulary needs to cover the standard CRM
roll-up patterns: counts, sums, averages, mins/maxes, and "value
from the first/last record by some ordering." Seven functions
total: `count`, `sum`, `avg`, `min`, `max`, `first`, `last`. Note
that `max` of a date field is the cleanest way to express "latest
date" — `last` is reserved for the case where the field being
returned differs from the field being ordered by (e.g., "notes
from the most recent session").

### Proposed YAML capability — structured, three formula types

```yaml
# --- aggregate: count ---
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

# --- aggregate: count with multi-hop traversal ---
- name: totalLifetimeSessions
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
      - { field: type, op: equals, value: "Completed" }

# --- aggregate: sum ---
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

# --- aggregate: avg ---
- name: averageSessionHours
  type: float
  readOnly: true
  formula:
    type: aggregate
    function: avg
    field: hours
    relatedEntity: Session
    via: assignedMentor
    join:
      - { from: Session, link: engagement, to: Engagement }
    where:
      - { field: type, op: equals, value: "Completed" }

# --- aggregate: max (latest date) ---
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

# --- aggregate: count with relative-date filter ---
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

# --- aggregate: last (value of one field, ordered by another) ---
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

# --- arithmetic ---
- name: availableCapacity
  type: int
  readOnly: true
  formula:
    type: arithmetic
    expression: "maximumClientCapacity - currentActiveClients"

# --- concat ---
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

### Aggregate function vocabulary (v1)

| Function | Returns | Required clauses |
|---|---|---|
| `count` | integer | (none beyond `relatedEntity`/`via`) |
| `sum` | numeric | `field:` |
| `avg` | numeric | `field:` |
| `min` | same type as field | `field:` |
| `max` | same type as field | `field:` |
| `first` | type of `pickField` | `orderBy:`, `pickField:` |
| `last` | type of `pickField` | `orderBy:`, `pickField:` |

`max` of a date field expresses "latest" cleanly. `first` and
`last` are for the case where the field being returned differs
from the field being ordered by.

### Implementation considerations

- The deploy manager translates each `formula:` block into the
  target CRM's native formula syntax. Per-CRM translator backend,
  parallel to existing field/layout translators.
- Expression-language complexity is contained to one place:
  `arithmetic.expression` accepts field references, integer/float
  literals, the four basic operators (`+`, `-`, `*`, `/`), and
  parentheses. No functions in v1; add `min`/`max`/`abs`/`round`/
  `coalesce` in v1.2 if real cases arise.
- All field references in any `formula:` block — including the
  parsed `arithmetic.expression` — are validated at load time
  against the entity's known fields and the related entity's
  known fields. Catches typos and rename drift.
- Relative date values (`lastNDays:30`) reuse Category 3's
  relative-date vocabulary.
- For `aggregate`, `via:` names the relationship from the related
  entity *back to* this entity (e.g., `Engagement.assignedMentor`
  points to Contact). Multi-hop traversals use an explicit
  `join:` list spelling out each intermediate entity. Verbose but
  legible and statically validatable. No dotted-path strings.
- The deploy manager rejects any `formula:` block on a field
  without `readOnly: true`. Calculated fields are always
  read-only.
- Drift detection compares the structured `formula:` block
  field-by-field, not the translated string. Cleaner equality
  semantics; handles whitespace and ordering differences in the
  CRM's stored representation.
- This category is dense enough to deserve its own session prompt
  during Phase 9.

### Recommended priority

**Should.** Six items in MR pilot, scaling to many more once
real CBM users start asking for the standard roll-ups they expect
on Engagement and Account. Highest implementation cost of any
"Should" category but high user-visible payoff.

### Open questions / decisions recorded

- **Q1 (resolved):** Approach — structured YAML with three
  formula types (`aggregate`, `arithmetic`, `concat`). No native
  pass-through, no full custom DSL.
- **Q2 (resolved):** `arithmetic.expression` parser scope —
  minimal in v1: field references, numeric literals, four
  operators, parentheses. No functions; revisit in v1.2.
- **Q3 (resolved):** Relationship traversal — explicit `join:`
  list. No dotted-path strings.
- **Domain follow-up (CBM repo):** `lastSessionDate` is more
  naturally placed on Engagement (and possibly aggregated up to
  Account) than on Contact. Carry this back to the MN Engagement
  Entity PRD (candidate v1.1) and, if appropriate, the Account
  Entity PRD (candidate v1.5) when the MN Entity PRDs are next
  revised. Logged here so the observation is not lost.

---

## 9. Workflows

**Source items.** MR-MC-WF-001 through MR-MC-WF-009. Eight of nine
addressable in v1; WF-007 deferred to v1.2; WF-009 stays Manual
(PRD gap, not a YAML capability gap); WF-003 folded into Category 2.

### Analysis

Largest category by item count and surface area. With Categories
4–8 in place, the building blocks for workflows are mostly already
designed. A workflow is fundamentally a **trigger** (event +
condition expression) plus an **action sequence**.

Item-by-item disposition:

- **Email-sending (WF-001, WF-002)** — straightforward
  trigger + `sendEmail` action.
- **Field-population (WF-004, WF-005, WF-006, WF-008)** —
  straightforward trigger + `setField` / `clearField` actions.
- **WF-007** — `onFirstTransition` semantics (fires only on the
  first occurrence) require audit-history awareness; deferred to
  v1.2 to avoid rushing the design across multiple target CRMs.
  WF-007 stays Manual for one more pilot cycle.
- **WF-003** — folded into Category 2's duplicate-check rule.
  The duplicate-check `onMatch: block` clause grows optional
  `alertTemplate:` and `alertTo:` to handle the notification
  half. WF-003 disappears as a free-standing workflow.
- **WF-009** — dues renewal date algorithm is not specified in
  any PRD. Stays Manual Configuration. Logged as a Phase 7 / PRD
  gap, not a YAML capability gap.

### Proposed YAML capability

A new `workflows:` block at the entity level. Each workflow has an
`id`, a human-readable `name`, a `trigger`, optional `where`
(additional conditions), and an ordered list of `actions`.

```yaml
entities:
  Contact:
    workflows:

      # WF-001 — application confirmation email
      - id: mentor-application-confirmation
        name: "Send confirmation email on new mentor application"
        trigger: { event: onCreate }
        where:
          all:
            - { field: contactType,  op: contains, value: "Mentor" }
            - { field: mentorStatus, op: equals,   value: "Submitted" }
        actions:
          - { type: sendEmail, template: mentor-application-confirmation, to: personalEmail }

      # WF-002 — decline notification email
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

      # WF-004 — populate acceptance timestamp
      - id: terms-acceptance-timestamp
        name: "Stamp terms and conditions acceptance time"
        trigger:
          event: onFieldChange
          field: termsAndConditionsAccepted
          to: true
        actions:
          - { type: setField, field: termsAndConditionsAcceptanceDateTime, value: now }

      # WF-005 — ethics acceptance timestamp
      - id: ethics-acceptance-timestamp
        name: "Stamp ethics agreement acceptance time"
        trigger:
          event: onFieldChange
          field: ethicsAgreementAccepted
          to: true
        actions:
          - { type: setField, field: ethicsAgreementAcceptanceDateTime, value: now }

      # WF-006 — auto-Off acceptingNewClients (one-way)
      - id: pause-stops-new-clients
        name: "Stop accepting new clients on pause or inactive"
        trigger:
          event: onFieldTransition
          field: mentorStatus
          to: ["Paused", "Inactive"]
        actions:
          - { type: setField, field: acceptingNewClients, value: false }

      # WF-008 — clear departure on reactivation
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

      # WF-007 — DEFERRED to v1.2 (onFirstTransition)
      # MR-MC-WF-007 stays on Manual Configuration list for now.
```

### Trigger event vocabulary (v1)

| Event | Fires on | Required clauses |
|---|---|---|
| `onCreate` | Record created | (none) |
| `onUpdate` | Any field updated | (none) |
| `onFieldChange` | Specific field set to a new value | `field:`, optional `to:` (value or list) |
| `onFieldTransition` | Field transitions, with `from:`/`to:` constraint | `field:`, `from:`, `to:` (either may be a list) |
| `onDelete` | Record deleted | (none) |

`onFirstTransition` deferred to v1.2 — needs audit-history
awareness across multiple target CRMs and deserves a careful
design. WF-007 (`isPrimaryMentor` initialization) is the only MR
item depending on it; stays Manual for one cycle.

### Action vocabulary (v1)

| Action | Effect | Required clauses |
|---|---|---|
| `setField` | Set a field to a literal or computed value | `field:`, `value:` (literal, `now`, or simple expression) |
| `clearField` | Clear a field to null | `field:` |
| `sendEmail` | Send an email using a registered template | `template:`, `to:` (field name or literal address) |
| `sendInternalNotification` | Send an in-CRM notification to a role or user | `template:`, `to:` (`role:*` or `user:*`) |

`value:` on `setField` accepts: a literal, the special token
`now` (server-side current timestamp), or a small expression in
the same `arithmetic` mini-language from Category 8.
`createRelatedRecord` deferred to v1.2 — no MR item demands it
and its design questions (new-record field values, relationship
link setup) deserve a real use case.

### Implementation considerations

- The deploy manager needs a CHECK→ACT path for workflows. Each
  workflow translates to the target CRM's native automation
  primitive (workflow, business rule, formula, scheduled job —
  varies by CRM and trigger type).
- `where:` clauses use the same condition-expression construct
  from Categories 3–8. Cross-category consistency.
- Field-reference validation: at load time, every `field:`
  mentioned in trigger, where, or action must exist on the
  entity. Email templates referenced in actions must exist in the
  registered `emailTemplates:` block (Category 7).
- Cross-workflow ordering: when multiple workflows fire on the
  same event, they execute in YAML declaration order. No
  explicit priority field in v1.
- This category is dense enough to deserve its own session
  prompt during Phase 9, parallel to Categories 6 and 8.

### What stays Manual / what folds elsewhere

- **MR-MC-WF-003** folded into Category 2: the duplicate-check
  rule grows `alertTemplate:` and `alertTo:` clauses to handle
  the duplicate-detection notification. No free-standing
  workflow.
- **MR-MC-WF-007** deferred to v1.2; stays Manual for one cycle.
- **MR-MC-WF-009** stays Manual. The dues renewal date algorithm
  is undefined in any PRD — Phase 7 / PRD gap, not a YAML
  capability gap. Logged as follow-up: the Dues Entity PRD or
  Contact Entity PRD should specify the exact algorithm before
  WF-009 can be promoted out of Manual Configuration.

### Recommended priority

**Should.** Eight of nine items addressable; one PRD gap, one
deferred. Workflows are core to making a deployed CRM actually
behave correctly — without them every state transition becomes a
manual checklist for the administrator.

### Open questions / decisions recorded

- **Q1 (resolved):** `onFirstTransition` in v1 — defer to v1.2.
  v1 supports `onCreate`, `onUpdate`, `onFieldChange`,
  `onFieldTransition`, `onDelete` only. WF-007 stays Manual one
  cycle.
- **Q2 (resolved):** `createRelatedRecord` action — defer.
  YAGNI; no MR item demands it.
- **Q3 (resolved):** WF-003 disposition — fold into Category 2's
  duplicate-check rule; no separate workflow.

---

## 10. Integrations

**Source items.** MR-MC-IN-001 (LMS integration for training
completion fields), MR-MC-IN-002 (outbound email transport).

### Analysis

Both items are **out of scope** for the domain YAML schema, but
for different reasons.

- **MR-MC-IN-001 (LMS integration).** The schema can declare
  *that* an integration exists and which fields it populates,
  but it cannot declare *how* the integration works. The actual
  integration is a code/connector deliverable — every LMS speaks
  a different protocol; there is no portable abstraction. The
  CRM Builder app is a config tool, not an integration platform.
- **MR-MC-IN-002 (outbound email transport).** Configuring SMTP
  credentials, OAuth tokens, or third-party sender API keys is
  fundamentally a per-instance secrets-handling concern. The
  CRM Builder app already has explicit policy that credentials
  are not in YAML and not in commits. This belongs in
  deploy-instance configuration (`data/instances/{slug}.json`,
  `{slug}_deploy.json`), not in domain YAML.

Both items remain on the Manual Configuration list. There is one
small adjacent capability worth adding to the domain YAML schema.

### Proposed YAML capability — `externallyPopulated` flag

Add an optional `externallyPopulated: true` boolean to fields
populated by an external system rather than by user entry or
formula. This is a documentation-and-validation flag, not an
integration mechanism.

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

### Implementation considerations

- `externallyPopulated: true` is a field property only; it does
  not change deployment behavior beyond the
  validation/verification adjustments described.
- Excludes the field from required-field validation when the
  unpopulated state is acceptable.
- Skips the field in seed-data import expectations (no warning
  when not present in import data).
- The Verification Spec generator (Phase 13) groups all
  `externallyPopulated` fields under an "External Integration
  Dependencies" section, listing them by entity and
  cross-referencing the relevant Manual Configuration item.

### What stays Manual / what is logged for future work

- **MR-MC-IN-001** — LMS integration mechanics. Declared via
  `externallyPopulated:` but the integration code itself is not
  in scope.
- **MR-MC-IN-002** — Outbound email transport configuration.
  Stays in deploy-instance configuration today. **Backlog
  follow-up:** consider a future deploy-config schema gap
  analysis covering SMTP/OAuth and other per-instance
  integration settings consistently across instances. Separate
  scope from this domain YAML gap analysis.

### Recommended priority

**Could.** The `externallyPopulated:` flag is trivial and
meaningfully improves Verification Spec quality, but neither MR
item *needs* it to function. Bundle with v1.1 if other categories
are landing anyway.

### Open questions / decisions recorded

- **Q1 (resolved):** Include `externallyPopulated:` flag in
  v1.1 — yes.
- **Q2 (resolved):** Log MR-MC-IN-002 as a backlog item for a
  future deploy-config schema gap analysis — yes.

---

## Summary and Recommended v1.17 PRD Scope

### Decisions across all ten categories

| # | Category | Disposition | Priority |
|---|---|---|---|
| 1 | Stream and Audit Logging | New `settings:` block; full migration of entity-level config into it | Should |
| 2 | Duplicate Detection Rules | New `duplicateChecks:` block; supports `block`/`warn`; folds in Category 9 WF-003 alert | Should |
| 3 | Saved Views and List Filters | New `savedViews:` block; shorthand AND + structured `all`/`any`; optional `orderBy:` | Should |
| 4 | Conditional-Required Logic | New `requiredWhen:` field clause; mutually exclusive with `required: true` | Should |
| 5 | Field-Level Dynamic Logic | New `visibleWhen:` field clause; renames panel-level `dynamicLogicVisible:` (deprecation alias one minor version) | Should |
| 6 | Field-Level Access Control | Roles + field permissions + presets — **deferred to v1.2** | Could → Should v1.2 |
| 7 | Email Templates | New `emailTemplates:` block; external HTML body files; required validated `mergeFields:` | Should |
| 8 | Calculated Field Formulas | Three structured formula types (`aggregate`, `arithmetic`, `concat`); seven aggregate functions including `avg`, `max`, `last`; minimal arithmetic parser | Should |
| 9 | Workflows | New `workflows:` block; five trigger events (no `onFirstTransition` in v1); four actions | Should |
| 10 | Integrations | `externallyPopulated:` flag only; integration mechanics out of scope | Could |

### What lands in v1.17 (proposed PRD update)

The eight **Should** capabilities (Categories 1, 2, 3, 4, 5, 7, 8, 9)
plus the **Could** Category 10 flag.

These eight Should capabilities together address roughly 30 of the
38 MR-pilot Manual Configuration items, and establish a consistent
condition-expression construct used across `where`, `requiredWhen`,
`visibleWhen`, `aggregate.where`, and workflow `trigger` /
`where` clauses.

### What remains Manual after v1.17

- **MR-MC-AC-001, MR-MC-AC-002** — Field-level access control.
  Deferred to v1.2 alongside the broader Roles capability.
- **MR-MC-CR-004** — Background check fields conditionally
  required by administrative discretion (not a field-driven
  condition). Operational discipline; not addressable by schema.
- **MR-MC-WF-007** — `isPrimaryMentor` initialization on first
  activation. Deferred to v1.2 with the `onFirstTransition`
  trigger.
- **MR-MC-WF-009** — Dues renewal date algorithm. PRD gap, not a
  YAML capability gap. Resolution requires the Dues Entity PRD or
  Contact Entity PRD to specify the algorithm.
- **MR-MC-IN-001, MR-MC-IN-002** — Integration mechanics. Out of
  scope; the `externallyPopulated:` flag documents the dependency
  but does not implement it.
- **MR-MC-AU-002** — Audit verification. Not actually a gap;
  belongs in the Verification Spec, not the YAML schema.
- **MR-MC-ET-001, MR-MC-ET-002, MR-MC-ET-003** — Email template
  *content*. The registration is YAML; the body authoring stays
  human.

### Cross-cutting design decisions adopted

- One **condition expression** construct used everywhere: saved
  view filters, `requiredWhen`, `visibleWhen`, formula `where`,
  permission edit conditions (Cat 6, future), workflow `where`.
  Two surface forms — flat-list shorthand (implicit AND) and
  structured `all:` / `any:` blocks (freely nestable).
- One **operator vocabulary** across all condition expressions:
  `equals`, `notEquals`, `contains`, `in`, `notIn`, `lessThan`,
  `greaterThan`, `lessThanOrEqual`, `greaterThanOrEqual`,
  `isNull`, `isNotNull`.
- One **relative-date vocabulary**: `today`, `yesterday`,
  `lastNDays:N`, `nextNDays:N`, `thisMonth`, `lastMonth`.
- All entity-level configuration in one canonical location:
  `settings:` for scalar toggles; sibling top-level blocks
  (`duplicateChecks:`, `savedViews:`, `emailTemplates:`,
  `workflows:`) for rule-shaped collections.
- All new schema additions validated at load time. Field
  references checked against actual entity definitions; bad
  references fail validation rather than producing broken
  deployments.
- Drift detection extended in parallel for every new top-level
  block.

### Cross-references logged for follow-up

- **EXCEPTIONS.md (5 items)** — Phase 7 Domain Reconciliation
  guide tightening. Separate workstream; pilot finding to be
  drafted after this gap analysis is approved.
- **`lastSessionDate` placement** — recommend Engagement (and
  possibly Account) rather than Contact, as part of the next
  revision of the MN Engagement Entity PRD (candidate v1.1) and
  Account Entity PRD (candidate v1.5). CBM repo follow-up.
- **WF-009 dues renewal algorithm** — PRD gap. Dues Entity PRD
  or Contact Entity PRD must specify the algorithm before the
  workflow can leave Manual Configuration.
- **Deploy-config schema gap analysis** — backlog item. SMTP /
  OAuth / external integration credentials and per-instance
  settings deserve the same treatment we just gave domain YAML.

### Next step

If this gap analysis is approved, the next deliverable is a
focused L2 PRD update (v1.16 → v1.17) that incorporates the eight
Should categories and the Category 10 flag, with new ISS-* entries
for each capability. After that, a CLAUDE-CODE-PROMPT-* series
implements them in the CRM Builder app.

**Last Updated:** 05-03-26 14:00

