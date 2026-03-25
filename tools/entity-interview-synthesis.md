# CRM Builder — Entity Synthesis Guide

**Version:** 1.1  
**Last Updated:** March 2026  
**Purpose:** AI guide for Phase 2 Session C — Synthesis  
**Changelog:** See end of document.

---

## How to Use This Guide

This guide is for Session C — synthesizing the outputs of Session A
(data) and Session B (process) into a complete, deployment-ready
specification for one entity variant.

Session C is primarily an AI production task, not an interview. The
AI takes all collected information and produces three outputs. The user
reviews and approves.

**Session length:** 15–30 minutes (mostly AI production + user review).

**Prerequisites:**
- Session A complete — full field inventory with layout
- Session B complete — full process definition with additional fields

**Outputs:**
1. **PRD Section** — human-readable entity description including full session transcript
2. **YAML Program File** — complete, deployment-ready configuration
3. **Task List** — all TBDs and manual config items

The session transcript is embedded in the PRD as the final section.
It captures every question and answer across both Session A and Session B,
verbatim. Stakeholders who were not present can review it, and future
sessions can reference it when amending requirements.

---

## Before Synthesis Begins

### Merge Additional Fields

Before producing outputs, merge any fields discovered in Session B
into the Session A field inventory. For each new field, apply the
same per-field definition process from Session A (type, required,
default, options, rationale).

> "During our process session, we identified some additional fields.
> Let me quickly confirm a few details before I produce the
> specification."

Ask only what is necessary — type, required, options for enums.
Don't repeat the full Session A process for simple fields.

### Final Completeness Check

> "Before I produce the outputs, a quick check — is there anything
> about [variant] that we haven't covered in either session? Any
> field, process, or rule that's come to mind since we last spoke?"

---

## Producing the Outputs

### PRD Section Format

```markdown
## [Entity Name] — [Variant Name]

**Purpose:** One paragraph describing what this variant represents,
why it exists, and what business problem it solves.

**Entity Type:** Base / Person / Company / Event
**CRM Entity:** [Native entity name, e.g., Contact, Account, or custom]

---

### Data Fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| [Label] | [Type] | Yes/No | [default or —] | [Business rationale] |

---

### Dropdown Values

**[Field Name]:**
| Value | Color | Description |
|---|---|---|
| [Value] | [color/none] | [Meaning] |

---

### Layout

**Tab: [Name]** *(Dynamic Logic: [condition if applicable])*
Fields: [field 1], [field 2], [field 3]

**List View Columns:** [field 1], [field 2]...

---

### Processes

**Creation:**
[Description of how records are created, who creates them,
what triggers, what happens automatically]

**Lifecycle Transitions:**

| From | To | Trigger | Prerequisites | Data Captured | Notifications |
|---|---|---|---|---|---|
| [Status] | [Status] | [Who/what] | [Conditions] | [Fields set] | [Who notified] |

**Termination:**
[Description of end-of-life process, what happens to related
records, retention policy, reactivation path]

---

### Relationships

| Relationship | Type | Panel Label (this side) | Panel Label (other side) |
|---|---|---|---|
| [Variant] → [Entity] | [type] | [label] | [label] |

---

### Open Items

**TBD — Required Before Go-Live:**
| # | Item | Question | Needs Input From |
|---|---|---|---|

**Manual Configuration Required:**
| # | Item | Where to Configure |
|---|---|---|
```

---

### YAML File Format

Produce a complete, valid YAML file. Key requirements:

**Header:**
```yaml
version: "1.0"
content_version: "1.0.0"
description: "[Client] EspoCRM Configuration — [Entity] ([Variant])"

# Source: [Client] Entity Definition Session — [Variant]
# Generated: [Date]
# PRD Reference: [PRD document and section]

# MANUAL CONFIG REQUIRED:
# - [Item]: configure in [location] after deployment
```

**Entity block:**
```yaml
entities:
  EntityName:
    description: >
      [PRD purpose statement — one paragraph]
    action: delete_and_create    # custom entities only
    type: Base                   # or Person, Company, Event
    labelSingular: "[Label]"
    labelPlural: "[Labels]"
    stream: true
    fields:
      ...
    layout:
      detail:
        panels: [...]
      list:
        columns: [...]
```

**Field requirements:**
- Every field has `description` with business rationale and PRD reference
- Every field has `category` matching a layout tab
- TBD enum values marked:
  ```yaml
  description: >
    [Rationale].
    TBD: [Specific question]. Needs input from: [stakeholder].
  ```
- Read-only calculated fields marked:
  ```yaml
  readOnly: true
  description: >
    [Rationale]. Calculated automatically via entity formula.
    MANUAL CONFIG: Configure formula in Entity Manager → [Entity] → Formula.
  ```

**Layout requirements:**
- Every field appears in exactly one tab
- Dynamic Logic conditions specified for conditional tabs
- List columns specified with widths summing to ~100

**Relationships block:**
```yaml
relationships:
  - name: [uniqueName]
    description: >
      [Why this relationship exists]
    entity: [Primary]
    entityForeign: [Foreign]
    linkType: [manyToOne/oneToMany/manyToMany]
    link: [linkName]
    linkForeign: [foreignLinkName]
    label: "[Panel label on primary]"
    labelForeign: "[Panel label on foreign]"
    action: skip    # if already exists in CRM
```

---

### Task List Format

```markdown
# Task List — [Entity] ([Variant])
# Sessions: [dates of Session A and B]

## TBD Items (Required Before Go-Live)

| # | Field/Item | Question | Needs Input From |
|---|---|---|---|

## Manual Configuration Items (Post-Deployment)

| # | Item | Where to Configure | Notes |
|---|---|---|---|

## Additional Fields Discovered in Process Session

| Field | Type | Description | Added to YAML |
|---|---|---|---|

## Decisions Made

| # | Decision | Rationale |
|---|---|---|
| 1 | [Decision] | [Why] |

---

## Session Transcript

### Session A — Data Definition ([date])

**Q:** [Question as asked]
**A:** [User response verbatim]

[Continue for all exchanges in Session A]

---

### Session B — Process Definition ([date])

**Q:** [Question as asked]
**A:** [User response verbatim]

[Continue for all exchanges in Session B]
```

---

## User Review

After producing outputs, walk the user through the key sections:

> "I've produced three outputs for [variant]. Let me walk you
> through the highlights:
>
> **PRD Section** — [brief summary of what's documented]
>
> **YAML file** — [X] fields, [X] tabs, [X] relationships.
> [X] fields are marked TBD.
>
> **Task list** — [X] items need stakeholder input before
> go-live, [X] items need manual configuration after deployment.
>
> Does anything look wrong or incomplete?"

---

## Multi-Variant Entities

When an entity has multiple variants (e.g., Contact has Mentor,
Client Contact, Partner Contact):

**Produce one YAML file per variant** during synthesis, then
**merge into a single entity YAML file** after all variants
are complete.

The merged file combines all fields from all variants, with:
- A `contactType` or equivalent enum to distinguish variants
- Dynamic Logic on tabs to show/hide variant-specific sections
- All relationships from all variants

> "We've now completed [variant 1] and [variant 2]. I'll merge
> these into a single Contact YAML file with Dynamic Logic to
> show the right fields for each type. Review the merged file
> before we consider the entity complete."

---

## Finalizing the Entity

An entity is complete when:
- [ ] All variants have completed Sessions A, B, and C
- [ ] All variant YAMLs merged into a single entity file
- [ ] User has reviewed and approved the merged file
- [ ] TBD items documented and assigned to stakeholders
- [ ] Manual config items documented with locations
- [ ] YAML committed to client repository

> "The [Entity] entity is complete. The YAML is committed to
> the repository and ready for deployment once the TBD items
> are resolved.
>
> The next entity on our list is [next entity]. Shall we
> schedule the data session for that one?"

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 1.1 | March 2026 | Added session transcript as required PRD section |
| 1.0 | March 2026 | Initial release — split from original entity-interview.md |
