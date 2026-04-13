# CRM Builder — YAML Generation Guide

**Version:** 1.0
**Last Updated:** 04-13-26 05:12
**Purpose:** AI guide for Phase 9 — YAML Generation
**Governing Process:** `PRDs/process/CRM-Builder-Document-Production-Process.docx`
**Schema Reference:** `PRDs/product/app-yaml-schema.md`

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

---

## Methodology Extension Notice

The process document (Section 3.9) specifies YAML + an Exception List
as Phase 9 outputs. This guide adds a third required output, the
**Manual Configuration List**, based on empirical evidence from prior
CBM work that the YAML schema cannot express every configuration the
target CRM requires to function (workflows, email templates, role
field-level permissions, calculated-field formulas, duplicate-detection
rules, stream/audit settings, saved views, integrations).

The process document should be updated to incorporate this extension
once the MR pilot confirms the Manual Configuration List is correct in
concept and in format.

---

## Critical Rules

**Business-to-implementation bridge.** The Domain PRD is written in
business language; YAML is implementation. This phase is the only
place in the methodology where that translation happens. Do it
completely — do not leave business-language text in YAML comments
where an implementation detail is needed.

**Default wherever possible.** Every convention in Section "Default
Conventions" below is a rule the AI applies automatically without
asking. Only stop and ask when an explicit exception in this guide
directs you to.

**Do not invent requirements.** If the Domain PRD doesn't cover
something needed for YAML (a field type, an option value, a
cardinality), raise it as an exception rather than guessing. The PRD
is the source of truth.

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

## When to Stop and Ask

Stop the generation pass and ask the administrator only in these
specific situations:

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
   automatically and continue. See next section.

Do not ask about: field internal names, layout structure, category
groupings, link naming, description wording, default enum values,
ordering. These are handled by defaults.

---

## The Manual Configuration List

Every configuration concern that is required by the Domain PRD but is
not expressible in the CRM Builder YAML schema is recorded in the
Manual Configuration List. The list is produced automatically during
YAML generation — it does not require administrator interaction.

### Required Categories

At minimum, the list covers the following categories (include only
those that apply to the domain being processed):

- **Workflows** — event-driven automation (e.g., confirmation email
  on record creation, status-change triggers).
- **Email Templates** — named templates referenced by workflows.
- **Role-Based Field Visibility** — which fields are visible or
  editable to which roles beyond what the YAML role block expresses.
- **Calculated Fields and Formulas** — formulas for derived fields
  (e.g., `lastActivityDate`, engagement counts, badge levels).
- **Duplicate Detection Rules** — matching criteria for duplicate
  prevention or detection.
- **Stream and Audit Logging** — per-entity stream settings, audit
  log configuration.
- **Saved Views and List Filters** — named list views referenced by
  the Domain PRD.
- **Integrations** — external system connections (Google Workspace,
  marketing platforms, LMS, etc.).

### Item Format

Each item in the list records:

- **Category** (one of the categories above)
- **Name** (the item's label, e.g., "Application Confirmation Email
  Workflow")
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

---

## Important AI Behaviors During Generation

**Default first, ask last.** The purpose of this phase is to produce
YAML with minimum administrator interruption. Every default in
Section "Default Conventions" is a question you do not ask. If you
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
