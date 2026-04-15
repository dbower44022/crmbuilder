# SESSION-PROMPT — Update YAML Generation Guide for Schema v1.1

**Repo:** `crmbuilder`
**Target file:** `PRDs/process/interviews/guide-yaml-generation.md`
**Last Updated:** 04-15-26 05:00
**Created in:** the session that drafted yaml-v1.1 Prompts B–H

## Purpose

Update the Phase 9 YAML Generation Guide from v1.0 to v1.1 to
reflect the expanded YAML schema. The guide was written when most
automation constructs (workflows, email templates, calculated
fields, duplicate detection, stream/audit settings, saved views)
were outside YAML scope and routed to the Manual Configuration
List. With `app-yaml-schema.md` v1.1, most of those are now
expressible in YAML. The guide must be rewritten to match.

## Pre-flight — read these before editing

1. **`crmbuilder/CLAUDE.md`** — current state, including the
   "YAML Schema v1.1 — Active Implementation Series" section.
2. **`PRDs/product/app-yaml-schema.md` v1.1** — the spec the
   guide must align with. Pay attention to the new entity-level
   blocks (Sections 5.4–5.8), field-level properties (Sections
   6.1.1–6.1.4), panel-level `visibleWhen:` (Section 7.3), and
   the shared condition-expression construct (Section 11).
3. **`PRDs/process/interviews/guide-yaml-generation.md` v1.0** —
   the file being updated.
4. **`PRDs/product/yaml-schema-gap-analysis-MR-pilot.md`** —
   the "Summary" section maps which MR-pilot Manual Configuration
   items are now expressible in YAML v1.1 and which remain manual.

## What changes and what stays

### Stays the same (preserve)

- The guide's overall structure and purpose: an AI guide for
  Phase 9 YAML Generation.
- "How to Use This Guide" — inputs, outputs, session length.
  (Outputs table stays: YAML files, Manual Configuration List,
  Exception List. The Manual Config list shrinks but doesn't
  disappear.)
- "Critical Rules" — all still apply.
- "Before Generation Begins" — all still apply.
- "Default Conventions" — all still apply. Add new defaults for
  v1.1 constructs (see below).
- "When to Stop and Ask" — situations 1–5 still apply. Add new
  situations for v1.1 (see below).
- "The Exception List" — format unchanged.
- "Completion Criteria" — update to include v1.1 constructs.
- "Important AI Behaviors During Generation" — all still apply.

### Must change

1. **Version header:** bump to v1.1, update Last Updated date.

2. **Methodology Extension Notice (Section 2):** rewrite. The
   notice currently lists workflows, email templates, role
   field-level permissions, calculated-field formulas, duplicate-
   detection rules, stream/audit settings, saved views, and
   integrations as outside YAML scope. With v1.1, only **role-
   based field-level permissions** (Category 6, deferred to v1.2)
   and **integration mechanics** (beyond the `externallyPopulated`
   flag) remain outside scope. The notice should:
   - State that v1.1 covers Categories 1–5, 7–10 from the gap
     analysis.
   - State that Category 6 (Roles) is deferred to v1.2 and
     remains in the Manual Configuration List.
   - State that integration *mechanics* remain manual; the
     `externallyPopulated:` flag documents the dependency.

3. **New section: "v1.1 YAML Constructs"** (or integrate into
   Default Conventions). For each new construct, provide:
   - When to use it (what PRD requirement patterns trigger it).
   - The default convention the AI applies without asking.
   - When the AI should stop and ask.

   Constructs to cover:

   a. **`settings:` block** — default: always emit for custom
      entities (labelSingular, labelPlural, stream: false,
      disabled: false). For native entities, only emit settings
      that override CRM defaults. Never use deprecated top-level
      form.

   b. **`duplicateChecks:`** — default: emit when the Domain PRD
      or Entity PRD mentions duplicate prevention, uniqueness
      constraints, or "already exists" scenarios. Derive `fields`,
      `onMatch`, and `message` from the PRD. Stop and ask if the
      PRD mentions duplicate detection but doesn't specify which
      fields to match on.

   c. **`savedViews:`** — default: emit when the Domain PRD
      defines named list views, filtered views, or "quick
      filters." Derive `filter:` from the PRD's filter criteria
      using the Section 11 condition-expression construct.
      `columns:` defaults to the entity's list-layout columns
      unless the PRD specifies a different column set. Stop and
      ask if the PRD names a view but doesn't define the filter
      criteria.

   d. **`requiredWhen:`** — default: emit when the Entity PRD
      defines a field as "required when [condition]" or
      "mandatory if [condition]." Use the Section 11 construct.
      Never set both `required: true` and `requiredWhen:`.

   e. **`visibleWhen:`** (field-level and panel-level) — default:
      emit when the Entity PRD or Domain PRD says a field or
      panel is "shown when," "visible when," "hidden unless," or
      similar conditional-visibility language. Use the Section 11
      construct. For panel-level, always use `visibleWhen:`, never
      the deprecated `dynamicLogicVisible:`. Never set both
      `required: true` and `visibleWhen:`.

   f. **`emailTemplates:`** — default: emit when the Domain PRD
      references named emails, notifications, or correspondence
      that should be automated. Create the template registration
      in YAML and a placeholder HTML body file in
      `programs/{DOMAIN}/templates/`. Derive `mergeFields:` from
      the PRD's description of what data appears in the email.
      Stop and ask if the PRD references an email but doesn't
      specify which fields appear in it.

   g. **`formula:`** — default: emit when the Entity PRD defines
      a field as "calculated," "derived," "computed," or
      "auto-populated from [other fields/entities]." Choose the
      appropriate formula type:
      - `aggregate` for roll-ups from related entities (count,
        sum, avg, min, max, first, last).
      - `arithmetic` for computations from same-record fields.
      - `concat` for text assembly from multiple sources.
      Always set `readOnly: true` on formula fields. Stop and ask
      if the PRD describes a calculation but the formula is
      ambiguous or references entities/fields not yet defined.

   h. **`workflows:`** — default: emit when the Domain PRD
      defines event-driven automation: "when [event], do
      [action]." Map PRD trigger language to the five trigger
      events. Map PRD action language to the four action types.
      Reference `emailTemplates:` entries by `id` for `sendEmail`
      actions. Stop and ask if the PRD describes an automation
      that doesn't map cleanly to the supported triggers or
      actions (it may need to go to Manual Configuration).

   i. **`externallyPopulated: true`** — default: emit when the
      Entity PRD says a field is "populated by [external system],"
      "set by integration," or similar. Include a `description:`
      noting the external system.

4. **Manual Configuration List categories (Section "Required
   Categories"):** shrink dramatically. The remaining categories
   after v1.1 are:
   - **Role-Based Field Visibility** — Category 6, deferred to
     v1.2.
   - **Integration Mechanics** — connectors, OAuth, SMTP config,
     webhook endpoints, scheduled syncs. The
     `externallyPopulated:` flag documents which fields depend on
     integrations, but the integration setup itself is manual.
   - **Advanced Automation** — any PRD-specified automation that
     uses `onFirstTransition`, `createRelatedRecord`, or other
     deferred trigger/action types.
   - **Anything else** — catch-all for domain-specific
     configuration the YAML schema does not yet cover.

   Remove the old categories that are now in YAML: Workflows,
   Email Templates, Calculated Fields and Formulas, Duplicate
   Detection Rules, Stream and Audit Logging, Saved Views and
   List Filters.

5. **"When to Stop and Ask" additions:** add situations for
   v1.1-specific ambiguities. Suggested additions:
   - The PRD describes a conditional requirement or visibility
     rule but the condition is ambiguous (can't determine the
     field or operator).
   - The PRD describes a calculated field but the formula
     references entities or relationships not yet defined in
     YAML.
   - The PRD describes a workflow whose trigger or action doesn't
     map to the v1.1 vocabulary (deferred trigger/action types).
   - The PRD describes an email template but doesn't specify
     which merge fields appear in the body.

6. **Completion Criteria updates:** add:
   - Every conditional requirement/visibility rule in the PRD is
     expressed as `requiredWhen:` / `visibleWhen:` in YAML.
   - Every calculated field in the PRD is expressed as a
     `formula:` block.
   - Every event-driven automation in the PRD is either expressed
     as a `workflows:` entry or recorded in the Manual
     Configuration List with a reason.
   - Every email template referenced by a workflow or
     duplicate-check rule is registered in `emailTemplates:` with
     a corresponding body file.
   - Every externally-populated field is flagged with
     `externallyPopulated: true`.

7. **Changelog:** add a v1.1 entry summarizing the changes.

## What NOT to do

- Don't change the guide's role (it's an AI guide for Phase 9,
  not a spec).
- Don't duplicate the spec's YAML examples — reference
  `app-yaml-schema.md` v1.1 for syntax details.
- Don't remove the Manual Configuration List entirely — it still
  has a role for Category 6 and integration mechanics.
- Don't change the Exception List format.
- Don't change the file's location or filename.

## Acceptance criteria

1. Guide version is v1.1, Last Updated reflects the session date.
2. Methodology Extension Notice accurately reflects v1.1 scope.
3. Every v1.1 construct has a default convention and a "stop and
   ask" trigger documented.
4. Manual Configuration List categories reflect only what remains
   outside YAML scope after v1.1.
5. Completion Criteria include v1.1 constructs.
6. Changelog has a v1.1 entry.
7. The guide references `app-yaml-schema.md` v1.1 (not v1.0) as
   the schema reference.
8. File committed and pushed to `main`.

## Confirm with Doug at session start

- Has the yaml-v1.1 series been fully executed (Prompts B–H)?
  If not, the guide update can still proceed since it's based on
  the spec, not the implementation — but note any prompts that
  haven't shipped yet.
- Any MR-pilot findings since the gap analysis that would change
  the guide's advice?
