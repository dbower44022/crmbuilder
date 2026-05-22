# UPDATE-PROMPT — YAML Schema v1.2 Sections for Category 6 Parts A–E

**Repo:** `crmbuilder`
**Target document:** `PRDs/product/app-yaml-schema.md`
**Operating mode:** ARCHITECTURE (project default)
**Last Updated:** 05-20-26 21:30
**Created in:** the prior session that landed the Option C reordering decision and amended Category 6 of the gap analysis (commit `eb1d7e7`).

## Purpose

Draft the new sections of `PRDs/product/app-yaml-schema.md` that extend YAML schema v1.1 to v1.2 by adding Category 6 Parts A–E: Roles declaration, Teams declaration, scope-level entity access, system permissions, and panel/layout role-aware visibility.

This is a documentation drafting session. No application code is changed. No Claude Code prompts are produced. The output is one updated reference document.

## Pre-flight — read these before doing any drafting

Confirm with Doug that `crmbuilder/CLAUDE.md` is the right CLAUDE.md to read, then proceed in this order:

1. **`crmbuilder/CLAUDE.md`** — repo context, working patterns, YAML Schema v1.1 implementation status, YAML Schema Rules.

2. **`crmbuilder/PRDs/product/yaml-schema-gap-analysis-MR-pilot.md`** Section 6 (as amended 05-20-26 21:18). **Authoritative source for what Parts A–E must express.** The 05-20-26 change log entry records the Option C reordering decision and the rationale. Decisions Q1–Q8 are resolved as recorded. Do not extend or contradict this design — translate it into reference-spec form.

3. **`crmbuilder/PRDs/product/app-yaml-schema.md`** existing v1.1 sections. Read enough of them to internalize voice, structure, and depth. Especially:
   - Section 5 (entity-level blocks — `settings:`, `duplicateChecks:`, `savedViews:`, `emailTemplates:`, `workflows:`)
   - Section 7 (layouts and panels, including the panel-level `visibleWhen:`)
   - Section 11 (the shared condition-expression construct — Part E.1 extends this with a `role:` leaf clause)

4. **`crmbuilder/espo_impl/core/config_loader.py`** — confirm the current top-level key set the loader recognizes (`version`, `description`, `content_version`, `entities`, `relationships`) before specifying how `roles:` and `teams:` slot in.

If the gap-analysis Section 6 design and the existing schema spec conflict on any point, **stop and ask Doug before drafting** — do not silently reconcile.

## Deliverable

Updated `PRDs/product/app-yaml-schema.md` with:

- New sections covering Category 6 Parts A–E for v1.2 scope. Each part needs:
  - Prose intro explaining what the part addresses and why it exists.
  - Complete YAML syntax with every key, value type, and enum value documented.
  - Validation rules — what the loader enforces, what the validator hard-rejects.
  - Deploy-ordering notes where applicable (Parts A and B must deploy before any reference to them; Part E.1 extends Section 11 and inherits its rules).
- Change log entry recording the v1.1 → v1.2 schema bump, with rationale matching the gap-analysis Section 6 amendment.
- "Last Updated" timestamp refreshed in MM-DD-YY HH:MM format (Doug's local time, Eastern).
- Forward references to v1.3 (deferred field-level permissions and permission presets) clearly marked as deferred and not implemented in v1.2.
- Match the depth bar set by existing v1.1 sections — YAML examples, validation rules, deploy-ordering notes, footnotes for edge cases.

## Constraints

- **Level 3 / implementation-reference documentation.** Product names (EspoCRM, etc.) are permitted in this document; it is the operator-facing reference, not a client deliverable.
- **No new design.** Do not introduce capabilities beyond what gap-analysis Section 6 specifies. If ambiguity surfaces during drafting, present it as a consequential decision before proceeding — do not unilaterally resolve.
- **No code in scope.** The v1.2 implementation prompt series (analogous to v1.1's archived A–H series at `PRDs/_archive/yaml-schema-prompts/`) is a downstream artifact for a future session.
- **Working pattern.** Doug never hand-edits documents. Claude edits the file directly via `str_replace` or rewrite. After the session reaches a complete draft, commit in the sandbox; Doug handles push.

## Decisions likely to need approval before drafting

These probably pass the two-part test. Present each using the eight-element consequential decision template before drafting the corresponding sections:

1. **Section placement.** Where does Category 6 land in `app-yaml-schema.md` — a new top-level section (Section 12, with sub-sections per Part), or slotted under the existing structure (e.g., extending Section 5 with security blocks)? Influences the document's organizational logic going forward and how operators navigate it.

2. **File-type concept.** Does v1.2 introduce a new program-file *type* — a "security file" with required `roles:` and `teams:` top-level blocks and no `entities:` block — or does it extend the existing single program-file type to allow `roles:` and `teams:` as optional top-level keys alongside `entities:` and `relationships:`? This affects how `validate_program()` enforces shape, how the file is discovered, and what the loader does when a file mixes security and entity content.

3. **Deploy ordering expression.** Gap-analysis Section 6 states `programs/security.yaml` is applied before domain files. Is that a schema-level constraint (the file's content signals it must run first — e.g., via a `file_type: security` discriminator or some equivalent), a deployment-pipeline-level convention (the operator orders the batch correctly and the pipeline trusts them), or a loader-level discovery rule (files matching `security.yaml` are always queued first)?

Other choices — section numbering, key naming, choice of example role, depth of native-permission enumeration — are routine. Decide and announce.

## Next required step after this session

Author the v1.2 implementation prompt series for Claude Code. This will be a multi-prompt series following the `CLAUDE-CODE-PROMPT-{series-tag}-{letter}-{descriptor}.md` naming convention, covering:

- Loader extensions to parse `roles:`, `teams:`, `scope_access:`, `system_permissions:`, and `forRoles:` on layouts.
- Validator extensions enforcing whitelist semantics, role-name cross-references, and the per-action enum on `scope_access:`.
- New deploy managers — `role_manager.py` and `team_manager.py` — wired into the Configure pipeline ahead of fields and relationships.
- API client extensions for `/api/v1/Role` and `/api/v1/Team` CRUD.
- Test coverage matching the v1.1 series pattern.

That series is **not** in scope for this session.
