# CRM Builder — User Process Guide Generator

**Version:** 1.0
**Status:** Current
**Last Updated:** April 2026
**Depends On:** crmbuilder-automation-l2-PRD.docx (Section 13 — Document Generator),
               app-yaml-schema.md, feat-doc-generator.md (sibling Verification
               Spec generator)

---

## 1. Purpose

The User Process Guide Generator produces one Word document per business
process discovered during requirements work. Each guide is a CRM-aware
how-to manual that combines the business-language process narrative
captured in Phase 4 (Process Definition) with the operational detail
captured in the YAML program files (entity labels, field labels,
panel/tab structure, allowed enum values, relationships, workflows).

The generator is a ninth document type in the automation Document Generator
pipeline (`automation/docgen/`), implemented alongside the existing eight
types defined in L2 PRD Section 13.

The feature exists to close a gap between requirements documents and the
deployed CRM. The Master PRD, Domain PRDs, Process Documents, and
Verification Spec describe **what** the system requires, but they do not
tell an end-user **how** to perform a process inside the live CRM —
which menu, which panel, which field labels, which dropdown values. The
User Process Guide fills that gap.

---

## 2. Audience and Scope

Each guide serves two audiences in one document:

- **End-users of the deployed CRM** — operational how-to: open this
  record, set this field to this value, save, expect this notification.
- **Process owners and managers** — high-level walkthrough: who does
  what, when, with which records, and what decisions are made along
  the way.

The two audiences share the same source data; the guide separates them
into distinct sections so each audience can read just the section
they need.

The guide is **not** a stakeholder requirements document and does not
replace any existing requirements artifact. It is generated *after* the
CRM is configured (i.e. after YAML has been deployed) so that field
labels and enum values match what users actually see on screen.

---

## 3. Inputs

The generator combines two sources:

1. **The client SQLite database** populated by
   `automation/importer/parsers/process_doc_docx.py`. Specifically the
   tables Process, Domain, ProcessPersona, ProcessStep, Requirement,
   ProcessEntity, ProcessField, Decision, OpenIssue.
2. **The YAML program files** under `{project_folder}/programs/`,
   loaded via `tools.docgen.yaml_loader.load_programs`. Only the
   entities referenced by the Process being documented are
   projected into the guide.

The combination is keyed on entity name. Each entity referenced by the
process (via ProcessEntity) is matched against the YAML entity dict so
the guide can render the actual user-facing label, panel placement,
field labels, and translated enum option labels.

The generator never calls a live EspoCRM API. If YAML coverage is
incomplete (e.g. an entity referenced by the process has no YAML file
yet), the guide still renders in business terms and a "YAML Coverage
Notes" appendix lists the gaps.

---

## 4. Document Structure

Each User Process Guide contains the following sections:

```
Title Page
1. Process at a Glance
2. For Process Owners
3. Step-by-Step User Guide
4. Field Reference
5. Statuses and Transitions          (if any enum/multiEnum status fields exist)
6. Related Records                    (if YAML defines relationships)
7. Open Issues                        (if any unresolved TBDs)
Appendix: YAML Coverage Notes        (if any YAML data was missing)
```

### 4.1 Title Page

Client name, process label in human-readable-first form
(`{Process Name} ({PROCESS-CODE})`), document title "User Process
Guide", and a meta table listing domain, process code, primary persona,
and a one-line trigger summary.

### 4.2 Section 1 — Process at a Glance

A one-paragraph purpose statement, the process trigger, and the defined
end state. Pulls from `Process.description`, `Process.triggers`, and
`Process.completion_criteria`.

### 4.3 Section 2 — For Process Owners

A high-level narrative aimed at managers:

- **Personas involved** — every ProcessPersona row, with role and
  description.
- **Process flow** — every ProcessStep in `sort_order`, prefixed with
  the performer name.
- **Key decisions** — every Decision row in a two-column table.

This section never cites specific CRM screens or field internal names.
It is meant to be readable by someone overseeing the process without
needing to know the configuration.

### 4.4 Section 3 — Step-by-Step User Guide

The operational core of the document. For each ProcessStep:

- A subheading "Step N: {Step Name}".
- "Performed by:" line.
- The step description from the Process Document.
- An "In the CRM:" line that names the entity record to open
  (using the YAML `labels.singular` for the entity, e.g.
  "Engagement record") and the menu/list to navigate from
  (using `labels.plural`, e.g. "Engagements menu").
- A bullet list of fields touched at this step, each rendered with the
  YAML field label, the field type display name, and (for enum and
  multiEnum) the allowed values inline.

The step→entity mapping is best-effort: the generator scans the step
description for whole-word matches against the entity names declared
in `ProcessEntity` rows for this process, and uses the longest match.
When no entity is matched, the step still renders without the "In the
CRM:" line — the business narrative is preserved.

### 4.5 Section 4 — Field Reference

A per-entity field cheat-sheet pulled from YAML, intended for quick
lookup during process execution. For each entity referenced by the
process, a field table shows label, type display name, required flag,
allowed values (enum/multiEnum) or `—`, default value, internal name,
and description. Field rows fall back to the DB-stored
ProcessField description when YAML is missing.

### 4.6 Section 5 — Statuses and Transitions

Conditional. Rendered only when the YAML for any entity in scope
defines an enum or multiEnum field whose name contains "status" or
ends with "state". For each such field, a two-column table lists every
allowed value with its translated label.

### 4.7 Section 6 — Related Records

Conditional. Rendered only when the YAML for any entity in scope
defines `relationships`. Each relationship is described in business
terms — for example, "Engagement → Mentor (belongsTo) via
'mentorContact'."

### 4.8 Section 7 — Open Issues

Conditional. Rendered only when OpenIssue rows exist for the process.
A two-column table of identifier and description.

### 4.9 Appendix — YAML Coverage Notes

Conditional. Rendered when the query layer raises any
`yaml_load_errors` — for example, the `programs/` directory does not
exist, or an entity referenced by `ProcessEntity` has no matching YAML
file. Each gap is listed as a bullet.

---

## 5. Trigger and Output Location

### 5.1 From the Application UI

A `user_process_guide` row appears in the Documents inventory
(`automation/ui/documents/documents_view.py`) for every process,
sibling to the existing `process_definition` row. The standard "Generate
Final" / "Generate Draft" buttons drive generation. Batch regeneration
treats user process guides identically to other document types.

### 5.2 Output Path

```
PRDs/{domain_code}/{PROCESS-CODE}-user-guide.docx
```

Sub-domains nest the same way as the corresponding Process Document:

```
PRDs/{parent_domain_code}/{subdomain_code}/{PROCESS-CODE}-user-guide.docx
```

The path is computed by `automation/docgen/paths.py::resolve_output_path`.

### 5.3 Workflow Integration

A `user_process_guide` work item is created automatically alongside
the `process_definition` work item for every process discovered by
`after_business_object_discovery_import`, `add_process`, and
`add_domain` in `automation/workflow/graph.py`. The guide work item
depends on its sibling `process_definition` — it becomes "ready" when
the requirements PRD is complete.

For databases that pre-date this feature, the helper
`automation/workflow/graph.py::backfill_user_process_guides` creates
the missing guide work items. The same helper runs as part of client
schema migration `_client_v8`.

---

## 6. Format and Conventions

The User Process Guide uses the same shared formatting helpers as the
other automation document types
(`automation/docgen/templates/doc_helpers.py`,
`formatting.py`):

- Banded-row tables, shaded header rows, identical font and color
  scheme.
- Page header (client name + process label) and footer
  (document type + domain).
- Draft mode adds a `[Draft]` watermark via `set_draft_header`.

Output is a Word `.docx` file only. Markdown output is not produced by
the automation pipeline at this time and is captured as a future
consideration in Section 9.

---

## 7. Validation

The query layer never blocks generation. The validator
(`automation/docgen/validation.py::_validate_user_process_guide`)
emits non-blocking warnings when:

- The Process row cannot be found.
- The process has no ProcessStep rows.
- `yaml_by_entity` is empty (no project folder configured, or no YAML
  in the configured folder).
- Any `yaml_load_errors` were recorded during the query.

Warnings appear in the UI alongside the generated file.

---

## 8. Staleness

A User Process Guide becomes stale under the same conditions as the
sibling `process_definition` document. The shared scope is registered
in `automation/impact/staleness.py::_build_scope_conditions` for the
combined set `('process_definition', 'user_process_guide')`. Any
ChangeLog entry that touches Process, ProcessStep, Requirement,
ProcessEntity, ProcessField, or ProcessPersona rows for this process
flags both documents as stale.

YAML-side staleness is **out of scope** for v1.0 — changes to
`programs/*.yaml` do not yet flag a generated guide as stale, even
though they may change the rendered field labels. This is captured as
a follow-up in Section 9.

---

## 9. Future Considerations

- **Markdown output.** Mirror the dual-format pattern from the
  Verification Spec generator once the broader automation pipeline
  gains `.md` support.
- **YAML-side staleness.** Hash the relevant YAML files at generation
  time, store the hash in `GenerationLog`, and flag stale when the
  hash differs.
- **Diagram embedding.** Embed the workflow diagram (already produced
  by the Process Document generator via
  `automation/docgen/workflow_diagram.py`) into the guide's Section 3
  so end-users see the flow alongside the steps.
- **Per-persona variants.** Generate one guide per persona rather than
  one per process, surfacing only the steps that persona performs.
  Useful for large processes with many handoffs.
- **Multi-language output.** Use the YAML field
  `translatedOptions` and `translations` blocks to render guides in
  the languages the deployed CRM supports.

---

## 10. Implementation Reference

| Concern | File |
|---|---|
| DocumentType enum + work item type mapping | `automation/docgen/__init__.py` |
| Pipeline registration + project_folder injection | `automation/docgen/pipeline.py` |
| Output path resolution | `automation/docgen/paths.py` |
| DB + YAML data assembly | `automation/docgen/queries/user_process_guide.py` |
| Word document rendering | `automation/docgen/templates/user_process_guide_template.py` |
| Non-blocking validation | `automation/docgen/validation.py` |
| Staleness scope | `automation/impact/staleness.py`, `automation/impact/work_item_mapping.py` |
| Work-item creation hook + backfill | `automation/workflow/graph.py` |
| Schema CHECK constraint | `automation/db/client_schema.py` |
| Schema migration `_client_v8` | `automation/db/migrations.py` |
| Tests | `automation/tests/test_docgen_user_process_guide.py` |

---

*This document defines the User Process Guide Generator feature within
the CRM Builder document architecture. The governing
document architecture, identifier scheme, and document hierarchy are
defined in `crmbuilder-automation-l2-PRD.docx` (Section 13). When that
document is next revised, it should add the User Process Guide as a
ninth row in the document-type table and reference this feature spec
for the full specification.*
