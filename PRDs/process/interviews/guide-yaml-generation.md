# CRM Builder — YAML Generation Guide

**Version:** 1.1
**Last Updated:** 04-15-26 17:30
**Purpose:** AI guide for Phase 9 — YAML Generation
**Governing Process:** `PRDs/process/CRM-Builder-Document-Production-Process.docx`
**Schema Reference:** `PRDs/product/app-yaml-schema.md` (v1.1)

---

## How to Use This Guide

This guide is loaded as context for an AI performing YAML generation
for a single domain. The AI should read this guide fully before
beginning, along with `app-yaml-schema.md`.

**This is a generation task, not an interview.** The AI reads the
Domain PRD and the Entity PRDs, applies the default conventions
defined in this guide, and produces YAML. The administrator's role is
to resolve the small number of decisions that cannot be defaulted and
to review the output. Most of the work happens without interruption.

**One domain per conversation.** Each conversation produces YAML for a
single domain.

**Session length:** 30–60 minutes per domain for most domains. Longer
if many exceptions against prior YAML are found.

**Inputs:**
- The Domain PRD for the domain being processed
- All Entity PRDs for entities referenced by the domain
- `app-yaml-schema.md` (YAML structure reference)
- All YAML program files already produced by prior domains

**Outputs (three artifacts, committed to the implementation repo):**

| Artifact | Repository location |
|---|---|
| YAML program files for the domain | `programs/{DOMAIN}/*.yaml` |
| Manual Configuration List | `programs/{DOMAIN}/MANUAL-CONFIG.md` |
| Exception List (if any exceptions) | `programs/{DOMAIN}/EXCEPTIONS.md` |

Email-template body files (referenced by `emailTemplates:` entries)
are an additional output and live in `programs/{DOMAIN}/templates/`.
See Section "v1.1 YAML Constructs" for details.

---

## Methodology Extension Notice

The process document (Section 3.9) specifies YAML + an Exception List
as Phase 9 outputs. This guide adds a third required output, the
**Manual Configuration List**, for configuration items that the
target CRM requires but that the YAML schema does not express.

In schema v1.1, the Manual Configuration List covers:

- **Role-based field-level permissions** (Category 6 of the gap
  analysis), deferred to v1.2.
- **Integration mechanics** — connectors, OAuth, SMTP configuration,
  webhook endpoints, scheduled syncs. The `externallyPopulated:`
  field flag documents which fields depend on integrations, but the
  integration setup itself is manual.
- **Advanced automation** that uses trigger or action types deferred
  to v1.2 (currently `onFirstTransition` and `createRelatedRecord`).
- A small residual of domain-specific configuration the schema does
  not yet cover.

The process document should be updated to incorporate this extension
once the methodology stabilizes.

---

## Critical Rules

**Business-to-implementation bridge.** The Domain PRD is written in
business language; YAML is implementation. This phase is the only
place in the methodology where that translation happens. Do it
completely — do not leave business-language text in YAML comments
where an implementation detail is needed.

**Default wherever possible.** Every convention in Section "Default
Conventions" and the per-construct defaults in Section "v1.1 YAML
Constructs" are rules the AI applies automatically without asking.
Only stop and ask when an explicit trigger in this guide directs you
to.

**Do not invent requirements.** If the Domain PRD doesn't cover
something needed for YAML (a field type, an option value, a
cardinality, a duplicate-check field set, a workflow trigger), raise
it as an exception rather than guessing. The PRD is the source of
truth.

**Prior YAML is authoritative for previously defined entities.** When
the domain being processed adds fields to an entity already defined in
prior YAML, preserve the prior entity definition and add fields to it.
If the current PRD disagrees with prior YAML on an existing field,
that is an Exception — do not silently overwrite.

**One topic at a time when asking.** When an exception or a decision
needs the administrator, surface it alone and wait for resolution
before proceeding.

---

## Before Generation Begins

### Verify Inputs

Before producing any YAML, confirm:

1. The Domain PRD is at the most recent version and has passed Phase 7
   reconciliation (check the "Last Updated" date and Phase 7 decision
   records).
2. All Entity PRDs for entities referenced by the domain are present
   and current.
3. Prior YAML files (if any) are listed and accessible.
4. The target output directory `programs/{DOMAIN}/` either does not
   exist or is empty. If it exists and contains content, stop and ask
   before proceeding.

### State the Plan

Before starting, state to the administrator:

- Which domain is being processed
- How many new entities, new fields on existing entities, and
  relationships the Domain PRD defines
- How many prior YAML files will be read as reference
- The default conventions this guide will apply
- The expected number of administrator decisions based on a scan of
  the inputs (the small count is the point — if it's large, something
  is wrong)

---

## Default Conventions

These are the rules the AI applies automatically. The administrator
is not asked about any of these unless an exception arises.

> See also: Section "v1.1 YAML Constructs" for the per-construct
> defaults that govern `settings:`, `duplicateChecks:`, `savedViews:`,
> `emailTemplates:`, `workflows:`, `requiredWhen:`, `visibleWhen:`,
> `formula:`, and `externallyPopulated:`.

### Internal Field Names

- Custom entities and custom fields use a `c` prefix internally per
  the project's existing convention documented in
  `crmbuilder/CLAUDE.md` (e.g., `contactType` → `cContactType`).
- Native entity primary sides of relationships: the tool
  auto-applies the `c` prefix to link names. Do not add it in the
  YAML.
- Field internal names are derived from the PRD field name using
  camelCase. Spaces and punctuation are removed. Acronyms are
  preserved as written in the PRD (e.g., `CBM Email Address` →
  `cbmEmailAddress`).

### Layout Assignments

- **Detail layout:** every field on the entity appears in the detail
  view by default, organized into panels matching the section
  headings of the Entity PRD (Section 5.x "Profile," "Compliance,"
  etc.). Each PRD section heading becomes one panel.
- **List layout:** required fields plus `name` (or equivalent primary
  label field) plus any field marked "status" or "type" in the PRD.
- **Edit layout:** all editable fields. Read-only and system-set
  fields are excluded.

### Category / Tab Groupings

- Category names are taken directly from the Entity PRD section
  headings that group the fields.
- If the PRD does not group fields into sections, the AI uses a single
  default category named after the entity (e.g., `Mentor`, `Account`).

### Relationship Link Names

- Link names mirror the PRD's relationship label in camelCase (e.g.,
  "Partner Liaison" → `partnerLiaison`).
- Cardinality is taken from the PRD explicitly. If ambiguous, it is
  an exception.

### Enum Options and Order

- Enum values are taken verbatim from the PRD with the exact order
  the PRD specifies.
- The first value in the list is the default when the PRD does not
  specify a default.

### Descriptions and PRD References

- Every entity and every field includes a `description` drawn from
  the PRD. Use the PRD's wording unless it mentions a product name,
  in which case rewrite for the YAML (the YAML may name the product;
  but prefer business language where equivalent).
- Every entity block includes a `# Source:` comment listing the
  Domain PRD section and the Entity PRD by name and version.

---

## v1.1 YAML Constructs

This section governs the entity-level and field-level constructs
introduced in schema v1.1. Each construct entry lists when to emit
it, the default the AI applies without asking, and the trigger that
forces a stop-and-ask. Syntax details — example shapes, property
tables, validation rules — live in `app-yaml-schema.md` v1.1; this
guide intentionally does not duplicate them.

The constructs are presented entity-level first, then field-level,
matching the spec's ordering.

### Entity-level constructs

#### `settings:` block

- **When to emit.** Always emit on custom entities. On native
  entities, emit only the specific keys whose CRM defaults are being
  overridden — omit the block entirely when no override is needed.
- **Default.** Custom entities get `labelSingular`, `labelPlural`,
  `stream: false`, `disabled: false`. `labelSingular` and
  `labelPlural` are taken from the Entity PRD; `stream` is set to
  `true` only if the PRD specifies an activity feed for the entity.
  Never use the deprecated v1.0 top-level entity-config form
  (`labelSingular`, `labelPlural`, `stream`, `disabled` outside
  `settings:`).
- **Stop and ask.** None — settings are fully defaulted.

#### `duplicateChecks:` block

- **When to emit.** Emit when the Domain PRD or Entity PRD mentions
  duplicate prevention, uniqueness constraints, or "already exists"
  scenarios.
- **Default.** Derive `fields:`, `onMatch:`, and `message:` from the
  PRD. Use `onMatch: block` when the PRD says "prevent" or "reject";
  use `onMatch: warn` when the PRD says "flag" or "alert." For email
  fields, default `normalize:` to `lowercase-trim`; for name and
  address fields, `case-fold-trim`; for phone fields, `e164`. Assign
  a stable `id:` derived from the entity name and the field set
  (e.g., `contact-personal-email`).
- **Stop and ask.** The PRD mentions duplicate detection but does
  not specify which fields participate in the match.

#### `savedViews:` block

- **When to emit.** Emit when the Domain PRD defines named list
  views, filtered views, or "quick filters."
- **Default.** Translate the PRD's filter criteria into a
  Section 11 condition expression — shorthand form for pure-AND
  filters, structured form when OR is involved. `columns:` defaults
  to the entity's list-layout column set unless the PRD specifies a
  different column set for the view. `orderBy:` is taken from the
  PRD; if the PRD specifies a sort field but no direction, default
  to `asc`. Assign a stable `id:` derived from the view name.
- **Stop and ask.** The PRD names a view but does not define its
  filter criteria.

#### `emailTemplates:` block

- **When to emit.** Emit when the Domain PRD references named
  emails, notifications, or correspondence the target CRM should
  send.
- **Default.** Register the template in the entity's
  `emailTemplates:` block and create a placeholder HTML body file
  at `programs/{DOMAIN}/templates/{template-id}.html` containing
  the merge-field placeholders the template will use. Derive
  `mergeFields:` from the PRD's description of what data appears in
  the email; every entry must be a real field on the template's
  `entity`. Set `audience:` only when the PRD identifies an
  intended recipient (use the `role:<role-id>`, `user:<user-id>`,
  or descriptive-string conventions from the spec). Reference the
  template `id` from any duplicate-check `alertTemplate:` or
  workflow `sendEmail` action that needs it.
- **Stop and ask.** The PRD references an email but does not
  specify which fields appear in the body.

#### `workflows:` block

- **When to emit.** Emit when the Domain PRD defines event-driven
  automation: "when [event], do [action]," "on [field change],
  set/clear [field]," "send [email] when [condition]."
- **Default.** Map PRD trigger language to one of the v1.1 trigger
  events: record creation → `onCreate`; field set to a specific
  value → `onFieldChange`; field transition with from/to constraint
  → `onFieldTransition`; record update (any field) → `onUpdate`;
  record deletion → `onDelete`. Map PRD action language to one of
  the four v1.1 actions: `setField`, `clearField`, `sendEmail`,
  `sendInternalNotification`. Express additional gating conditions
  in `where:` using the Section 11 expression. For `sendEmail`,
  reference the `emailTemplates:` `id`, not the template name.
- **Stop and ask.** The PRD describes an automation whose trigger
  or action does not map to the v1.1 vocabulary (e.g., "the first
  time the mentor is activated" → `onFirstTransition`, deferred to
  v1.2; "create a related record" → `createRelatedRecord`, deferred
  to v1.2). Such automations are recorded in the Manual
  Configuration List under Advanced Automation, not as workflow
  entries.

### Field-level constructs

#### `requiredWhen:`

- **When to emit.** Emit when the Entity PRD describes a field as
  "required when [condition]," "mandatory if [condition]," or
  similar conditional-requirement language.
- **Default.** Express the condition using the Section 11
  construct — shorthand for pure-AND, structured for OR or mixed
  logic. Set `required: false` (or omit `required:`); never set
  both `required: true` and `requiredWhen:`.
- **Stop and ask.** The PRD describes a conditional requirement
  but the condition is ambiguous (cannot determine the field, the
  operator, or the value).

#### `visibleWhen:` (field-level and panel-level)

- **When to emit.** Emit when the Entity PRD or Domain PRD says a
  field or panel is "shown when," "visible when," "hidden unless,"
  or similar conditional-visibility language. Field-level
  `visibleWhen:` lives on the field; panel-level `visibleWhen:`
  lives on the panel definition.
- **Default.** Express the condition using the Section 11
  construct. For panel-level visibility, always use `visibleWhen:`;
  never use the deprecated v1.0 `dynamicLogicVisible:`. Never set
  both `required: true` and `visibleWhen:` on the same field —
  authors who want "required only when visible" use `requiredWhen:`
  with the same condition.
- **Stop and ask.** The PRD describes conditional visibility but
  the condition is ambiguous.

#### `formula:` block

- **When to emit.** Emit when the Entity PRD describes a field as
  "calculated," "derived," "computed," "auto-populated from
  [other fields/entities]," "rolled up from," or similar.
- **Default.** Choose the formula type from PRD intent:
  `aggregate` for roll-ups across related entities (count, sum,
  avg, min, max, first, last); `arithmetic` for computations from
  same-record fields; `concat` for text assembly. Always set
  `readOnly: true` on the field. For aggregates, use explicit
  `join:` lists for multi-hop traversals. Express filtering
  predicates with `where:` using the Section 11 construct, including
  the relative-date vocabulary (`today`, `lastNDays:N`, etc.) where
  the PRD specifies a time window.
- **Stop and ask.** The PRD describes a calculation but the
  formula is ambiguous, the formula type is unclear, or the
  formula references entities or relationships not yet defined in
  YAML.

#### `externallyPopulated:` flag

- **When to emit.** Emit when the Entity PRD says a field is
  "populated by [external system]," "set by integration," "synced
  from," or similar.
- **Default.** Set `externallyPopulated: true` and include a
  `description:` naming the external system (the Verification Spec
  generator uses this in its External Integration Dependencies
  section). Add a corresponding entry to the Manual Configuration
  List under Integration Mechanics describing the integration the
  field depends on.
- **Stop and ask.** None — the flag is documentary; the
  integration itself is always Manual Configuration.

---

## When to Stop and Ask

Stop the generation pass and ask the administrator only in the
specific situations listed below. The list is split into general
situations that have applied since v1.0 and v1.1-specific situations
introduced with the new constructs.

### General

1. **A required field property is missing from the PRDs.** Example:
   the PRD defines an enum field but lists no options, or defines a
   reference field but does not specify the target entity.

2. **Prior YAML disagrees with the current Domain PRD.** Example: an
   existing entity's field is defined as `varchar(100)` in prior YAML
   but the current Entity PRD defines it as `text` with no length
   cap. Record as an Exception and ask which to use.

3. **Cardinality is ambiguous.** Example: the PRD describes a
   relationship as "each Contact may have multiple Accounts" without
   specifying whether the reverse is also multiple. Ask.

4. **A field appears in the Domain PRD's data tables but is not in
   any Entity PRD.** Raise as an exception and ask whether to add it
   to the Entity PRD (which blocks Phase 9 until the Entity PRD is
   updated) or defer.

5. **A configuration item is clearly required but is not expressible
   in YAML.** Do not ask — add it to the Manual Configuration List
   automatically and continue. See "The Manual Configuration List."

### v1.1-specific

1. **Duplicate detection without a field set.** The PRD mentions
   duplicate prevention, uniqueness, or "already exists" handling
   but does not specify which fields participate in the match.

2. **Saved view without filter criteria.** The PRD names a list view
   but does not define the filter criteria that select its records.

3. **Ambiguous condition for `requiredWhen:` or `visibleWhen:`.**
   The PRD describes a conditional requirement or visibility rule
   but the condition is ambiguous — cannot determine the field, the
   operator, or the value.

4. **Calculated field with ambiguous or undefined references.** The
   PRD describes a calculation but the formula type is unclear, or
   the formula references entities or relationships not yet defined
   in YAML.

5. **Email template without merge-field specification.** The PRD
   references an email but does not specify which fields appear in
   the body. (Body content authoring is always manual; what the AI
   needs from the PRD is the merge-field set.)

6. **Workflow trigger or action outside the v1.1 vocabulary.** The
   PRD describes an automation that does not map to the five v1.1
   triggers or four v1.1 actions — typically because it requires
   `onFirstTransition` or `createRelatedRecord`, both deferred to
   v1.2. Record in the Manual Configuration List under Advanced
   Automation rather than emitting a malformed workflow entry.

Do not ask about: field internal names, layout structure, category
groupings, link naming, description wording, default enum values,
ordering. These are handled by defaults.

---

## The Manual Configuration List

Every configuration concern that is required by the Domain PRD but is
not expressible in the CRM Builder YAML schema is recorded in the
Manual Configuration List. The list is produced automatically during
YAML generation — it does not require administrator interaction.

### What moved into YAML in v1.1

Schema v1.1 brought several previously-manual capability categories
into YAML scope: stream and audit settings, duplicate detection,
saved views, conditional requirement, conditional visibility, email
templates, calculated-field formulas, and event-driven workflows
(within the v1.1 trigger and action vocabulary). If the Domain PRD
calls for any of these, emit the corresponding YAML construct from
Section "v1.1 YAML Constructs" — do not add it to the Manual
Configuration List.

The categories below are what remains outside YAML scope after v1.1.

### Required Categories

Include only those that apply to the domain being processed.

- **Role-Based Field Visibility** — which fields are visible or
  editable to which roles. Category 6 of the gap analysis, deferred
  to v1.2.
- **Integration Mechanics** — connectors, OAuth flows, SMTP
  configuration, webhook endpoints, scheduled syncs, credentials,
  and transport configuration. The `externallyPopulated:` flag on
  individual fields documents the dependency in YAML, but the
  integration itself is configured manually.
- **Advanced Automation** — automations that require trigger or
  action types deferred to v1.2 (currently `onFirstTransition` and
  `createRelatedRecord`), or other automations the v1.1 workflow
  vocabulary cannot express.
- **Anything else** — domain-specific configuration the YAML schema
  does not yet cover. Use this category sparingly; an item that
  arrives here often signals a schema gap worth logging for the next
  schema revision.

### Item Format

Each item in the list records:

- **Category** (one of the categories above)
- **Name** (the item's label, e.g., "Mentor Application Roles")
- **Source** (the Domain PRD requirement identifier or section that
  drives it, e.g., `MR-APPLY-REQ-003`)
- **Description** (one or two sentences explaining what the
  administrator must configure)
- **Dependencies** (any YAML entities, fields, or relationships this
  configuration assumes are already in place)

### Hand-Off

The Manual Configuration List is the primary hand-off from Phase 9 to
Phase 12 (CRM Configuration). The administrator works through the
list after CRM Builder applies the YAML.

---

## The Exception List

The Exception List records anything that needed administrator
resolution during generation. Each entry:

- **Exception identifier** — `{DOMAIN}-Y9-EXC-NNN` (e.g.,
  `MR-Y9-EXC-001`)
- **Trigger** — which of the "When to Stop and Ask" situations
  applied
- **Context** — the PRD location and prior-YAML location (if any)
- **Question asked**
- **Resolution** — what the administrator decided
- **Where applied** — which YAML file(s) and line(s) reflect the
  resolution

If no exceptions arose, the Exception List is a single file stating
"No exceptions raised during Phase 9 for this domain."

---

## Completion Criteria

Phase 9 for a domain is complete when all of the following are true:

1. Every new entity defined in the Domain PRD has a corresponding
   entity block in a `programs/{DOMAIN}/*.yaml` file.
2. Every new field on an existing entity has a field entry in the
   appropriate YAML file.
3. Every relationship involving entities in this domain is expressed
   in YAML.
4. Every "Stop and Ask" situation encountered has been logged in the
   Exception List with a recorded resolution.
5. Every configuration item outside YAML scope has been recorded in
   the Manual Configuration List.
6. All produced YAML passes schema validation against
   `app-yaml-schema.md` (if a validator is available).
7. The YAML files, Manual Configuration List, and Exception List are
   committed to the implementation repo in a single commit.
8. Every conditional requirement and conditional visibility rule
   defined in the Entity or Domain PRD is expressed as
   `requiredWhen:` or `visibleWhen:` in YAML, or recorded in the
   Exception List with a resolution.
9. Every calculated, derived, computed, or rolled-up field defined
   in the Entity PRD is expressed as a `formula:` block.
10. Every event-driven automation defined in the Domain PRD is
    either expressed as a `workflows:` entry or recorded in the
    Manual Configuration List under Advanced Automation with a
    reason.
11. Every email template referenced by a workflow or duplicate-check
    rule is registered in the entity's `emailTemplates:` block, and
    a corresponding HTML body file exists at
    `programs/{DOMAIN}/templates/{template-id}.html`.
12. Every field populated by an external system is flagged
    `externallyPopulated: true` and has a corresponding entry in
    the Manual Configuration List under Integration Mechanics.

---

## Important AI Behaviors During Generation

**Default first, ask last.** The purpose of this phase is to produce
YAML with minimum administrator interruption. Every default in
Section "Default Conventions" and every per-construct default in
Section "v1.1 YAML Constructs" is a question you do not ask. If you
find yourself about to ask something not in the "When to Stop and
Ask" list, stop — apply the default.

**Batch and report, don't narrate.** Do not announce each entity or
field as you create it. Generate the full YAML file for a logical
unit (an entity plus its fields, or a set of closely related
relationships), then present a summary: what was produced, what was
defaulted, what was flagged.

**Be explicit about what's not in YAML.** When adding an item to the
Manual Configuration List, state it. Don't hide it in a file for the
administrator to discover later.

**Trace everything.** Every entity, field, relationship, and Manual
Configuration List item carries a PRD-identifier reference back to
the source requirement or data item. If you can't trace it, you
shouldn't be producing it.

**After Claude produces Phase 9 outputs, the administrator owns
them.** The administrator may refine wording, adjust category
groupings, or reorganize files. Claude is not the permanent custodian
of the YAML.

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 1.0 | 04-13-26 | Initial release. Authored during the CBM MR pilot as the first Phase 9 execution under the document production methodology. Introduces the Manual Configuration List as a required Phase 9 output (methodology extension, to be back-propagated to the process document). |
| 1.1 | 04-15-26 | Aligned with `app-yaml-schema.md` v1.1. Added Section "v1.1 YAML Constructs" covering nine new constructs (`settings:`, `duplicateChecks:`, `savedViews:`, `emailTemplates:`, `workflows:`, `requiredWhen:`, `visibleWhen:`, `formula:`, `externallyPopulated:`) with per-construct emit triggers, defaults, and stop-and-ask criteria. Split "When to Stop and Ask" into General and v1.1-specific subsections; added six v1.1-specific situations. Rewrote "Methodology Extension Notice" around v1.1 scope. Rewrote "Manual Configuration List" categories to reflect what remains outside YAML scope (Role-Based Field Visibility, Integration Mechanics, Advanced Automation, residual); added "What moved into YAML in v1.1" pointer. Appended completion criteria #8–#12 covering the new constructs. Added cross-reference from "Default Conventions" to the new constructs section. |
