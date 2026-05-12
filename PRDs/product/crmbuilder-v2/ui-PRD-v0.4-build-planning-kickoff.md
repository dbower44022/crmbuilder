# v0.4 Build-Planning Conversation — Kickoff Prompt

**Last Updated:** 05-12-26 08:45
**Purpose:** Seed prompt for a new Claude.ai conversation that integrates the four methodology-entity schema specs into a coherent v0.4 release.
**Position in workstream:** Fifth and final conversation in the methodology-entity-schema-design workstream. Predecessors: the four per-entity schema-design conversations (SES-012 domain, SES-013 entity, SES-014 process, SES-015 crm_candidate — applied via close-out payloads under `PRDs/product/crmbuilder-v2/close-out-payloads/`). Successor: Claude Code execution of the v0.4 build slice prompts this conversation produces, followed by a separate v0.4 build-closeout session.
**Workstream master:** `PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md`
**Schema specs (inputs to this conversation):**
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md`
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/entity.md`
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/process.md`
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/crm_candidate.md`

---

## The task

Integrate the four methodology-entity schema specs into the v0.4 release. Drive a structured planning discussion that produces these deliverables:

1. **The v0.4 PRD** at `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md` — same shape as v0.1 / v0.2 / v0.3 PRDs (per workstream plan section 10), specifying the four new methodology-entity panels, their backing schemas, the references-vocabulary additions, the migration sequencing, the UI sidebar group introduction, and the cross-cutting concerns (About-dialog version bump, README update, test target).
2. **The v0.4 implementation plan** at `PRDs/product/crmbuilder-v2/ui-v0.4-implementation-plan.md` — slice breakdown with explicit migration ordering and per-slice acceptance criteria, modeled on `ui-v0.3-implementation-plan.md`'s structure.
3. **Slice build prompts** at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.4-{A..*}-*.md` — one prompt per slice, executable by Claude Code in sequence. Slice count and lettering settled during this conversation's architectural discussion.
4. **An amendment to the schema-spec methodology guide** at `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — specifically a revision to section 6 ("Cross-spec consistency requirements") to reflect the two cross-spec conventions established by SES-012 and applied across SES-013 / SES-014 / SES-015 that the original guide did not pre-decide: parent-prefix field naming (per DEC-046) and `{source}_{verb}_{target}` relationship-kind naming for methodology vocab (per DEC-048). The amendment is forward-only for methodology entities; governance entities are not retrofitted in this amendment (PI-006 tracks the retrofit decision separately).

The first task in the conversation is the **cross-spec consistency check** per spec guide section 7.2. See "Architectural questions likely to arise" below.

This conversation produces design artifacts only. It does **not** execute the build prompts. Build execution happens in Claude Code after this conversation closes, possibly across multiple Claude Code sessions per slice.

---

## Context — workstream complete, ready for integration

The methodology-entity-schema-design workstream produced four per-entity schema specs across four sequenced conversations (SES-012 through SES-015). Each spec defines one new methodology entity type for v2's storage layer under minimum-viable v0.4 scope. The four entity types together cover the evolved-methodology Phase 1 outputs:

- **`domain`** (DOM-NNN) — Domain Inventory members. Phase 1's "what areas of work does the mission require?" output.
- **`entity`** (ENT-NNN) — CRM-modeled nouns. Phase 1's surfaced noun list (full Entity PRDs deferred to Phase 3).
- **`process`** (PROC-NNN) — Prioritized Backbone members. Phase 1's "what activities does the client perform that the methodology tracks?" output.
- **`crm_candidate`** (CRM-NNN) — Initial CRM Candidate Set members. Phase 1's "what are the two or three CRM products we'll multi-deploy to?" output.

The four specs collectively define five new references-vocabulary additions:

| Change | Source | Detail |
|--------|--------|--------|
| `ENTITY_TYPES` expansion | DEC-053, DEC-058, DEC-063, and the domain spec's section 3.3.1 | Add `domain`, `entity`, `process`, `crm_candidate` to `ENTITY_TYPES` in `vocab.py`. |
| `entity_scopes_to_domain` | DEC-053 (entity → domain spec) | New relationship kind. Source=`entity`, target=`domain`. Many-to-many via references edge. |
| `process_hands_off_to_process` | DEC-058 (process spec) | New relationship kind. Source=`process`, target=`process`. Many-to-many directional via references edge. |
| `process_belongs_to_domain` (conceptual only) | DEC-058 (process spec) | Direct FK column on `process` table; NOT registered in `REFERENCE_RELATIONSHIPS`. Documented for completeness; no `vocab.py` change. |
| `refs.source_type` / `refs.target_type` CHECK constraint extension | DEC-053, DEC-058, DEC-063, and the domain spec | Alembic migration admits the four new entity types. |

The four specs have **three documented deviations** from the cross-spec norms the workstream established:

1. **`PROC` four-letter prefix** (DEC-055, process spec section 3.1) — invokes domain's soft-3-letter explicit-deviation clause; justified by the ambiguity of the three-letter `PRC` alternative.
2. **No `status` field on `process`** (DEC-056, process spec section 3.4.1) — `process_classification` carries engagement-scope lifecycle information instead; justified by the methodology distinguishing process priority (Principle 3) from process definitional completeness (Phase 3 territory).
3. **`removed` as a first-class status value on `crm_candidate`** (DEC-062, crm_candidate spec section 3.4.4) — deviates from the rejection-via-soft-delete cross-spec principle; justified by the methodology distinguishing lived-deployment-driven adjustments from authoring-error rejections.

Each deviation has rationale in its source spec. The cross-spec consistency check confirms each is well-justified and that the four specs as a set produce a coherent release.

---

## Methodology context

v0.4 ships the four methodology-entity panels as a single unit. The release goal is to enable the upcoming CBM-redo engagement to use v2 as system of record for both governance (already supported in v0.3) and Phase 1 methodology content (this release). CBM-redo is also the adoption pilot for the evolved methodology; v0.4 is what lets the pilot use v2 instead of falling back to Word documents or a separate authoring system.

The minimum-viable v0.4 scope philosophy applies across the four schemas: each ships the thinnest shape that can faithfully host its Phase 1 output, with growth deferred to v0.5+ as Phase 3 and later phases reveal what each entity needs to carry. The workstream plan section 3.2 names the deliberate deferrals (`persona` per PI-003; `field` / `requirement` / `manual_config` / `test_spec` per PI-004; `process` schema growth per PI-005; `crm_candidate` structured-metadata enums per PI-012).

---

## Read this first

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. `PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md` — workstream master plan.
3. `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — schema spec template; especially section 6 (cross-spec consistency requirements) and section 7 (validation gates).
4. `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` — first schema spec.
5. `PRDs/product/crmbuilder-v2/methodology-schema-specs/entity.md` — second schema spec.
6. `PRDs/product/crmbuilder-v2/methodology-schema-specs/process.md` — third schema spec.
7. `PRDs/product/crmbuilder-v2/methodology-schema-specs/crm_candidate.md` — fourth and final schema spec.
8. `PRDs/product/crmbuilder-v2/ui-PRD-v0.3.md` and `PRDs/product/crmbuilder-v2/ui-v0.3-implementation-plan.md` — shape precedent for the v0.4 PRD and implementation plan.
9. `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.3-*.md` (any one) — shape precedent for slice build prompts.
10. `PRDs/product/crmbuilder-v2/db-export/sessions.json` — session records SES-011 through SES-015 for the workstream context.
11. `PRDs/product/crmbuilder-v2/db-export/decisions.json` — DEC-044 through DEC-064 for the cumulative workstream decisions.
12. `PRDs/product/crmbuilder-v2/db-export/planning_items.json` — PI-001 through PI-012 for tracked deferrals.
13. `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — current `ENTITY_TYPES`, `REFERENCE_RELATIONSHIPS`, and `_kinds_for_pair` shape (the additions in this v0.4 release modify this file).

---

## Architectural questions likely to arise

The conversation will surface these in some order. The list is illustrative; some items are mechanical and decided quickly, others architectural and warranting full discussion.

### Cross-spec consistency check (first task)

Per spec guide section 7.2, the build-planning conversation begins by verifying the four specs as a set against the consistency requirements:

- **No identifier prefix collisions.** `DOM`, `ENT`, `PROC`, `CRM` against existing `DEC`, `SES`, `RSK`, `PI`, `TOP`, `REF`, `CHR`, `STA`. (Confirmed clean by visual inspection during SES-015; the build-planning conversation re-verifies.)
- **Cross-spec conventions applied consistently or deviations justified.** Parent-prefix field naming applied in all four specs. `{source}_{verb}_{target}` naming applied in all relationship-kind registrations (only entity and process register kinds; domain and crm_candidate are trivially compliant). Soft-3-letter prefix posture applied with one explicit deviation (process at four letters with justification).
- **Status-value naming consistent across specs.** `candidate`, `confirmed`, `deferred` are used identically by domain and entity. Process does not have a `status` field (justified deviation). `crm_candidate` introduces a new four-status enum (`active`, `selected`, `declined`, `removed`) reflecting its distinct lifecycle; the values do not collide with domain/entity status values when both schemas are considered together.
- **Relationship-kind vocabulary additions do not conflict.** `entity_scopes_to_domain` (entity → domain) and `process_hands_off_to_process` (process → process) are the only new kinds across the four specs. `process_belongs_to_domain` is conceptual only (direct FK, not registered). No `crm_candidate`-related kinds are registered. No collisions.
- **UI panel layouts either default or rationale-justified deviations.** All four specs adopt the default `ListDetailPanel` layout under a new Methodology sidebar group; no architectural deviations.

If the check surfaces issues, they're resolved by small revisions to the affected schemas before build planning proper begins.

### Slice breakdown

How does v0.4 decompose into Claude Code-executable slices? Options to consider:

- **By entity type** — slice A introduces shared infrastructure (Methodology sidebar group, `ENTITY_TYPES` expansion, `refs` CHECK constraint migration, vocabulary additions for `entity_scopes_to_domain` and `process_hands_off_to_process`); slices B / C / D / E introduce each of the four entity panels in turn. Five slices total.
- **By layer** — slice A schema migrations + access layer for all four entities; slice B REST endpoints; slice C UI panels; slice D close-out. Four slices total.
- **Hybrid** — slice A foundation (Methodology group, vocab additions, `entity_scopes_to_domain` and `process_hands_off_to_process` vocab + Alembic), slice B domain end-to-end, slice C entity end-to-end (depends on B's vocab; introduces references-create dialog use case in master pane), slice D process end-to-end (depends on B), slice E crm_candidate end-to-end, slice F close-out. Six slices.

The hybrid pattern most closely mirrors how v0.3 was decomposed (slice A foundation; B / C / D / E feature slices; F close-out). Working assumption: hybrid, six slices. To be confirmed in the conversation.

### Migration ordering

In what order do the Alembic migrations run? Options:

- One large migration adding all four tables, the references-table CHECK constraint extensions, and all `vocab.py` additions in a single revision. Atomic; either everything succeeds or everything rolls back.
- One migration per entity type, with the `vocab.py` and CHECK-constraint changes split across them in dependency order (e.g., the CHECK extensions added incrementally). More granular history, more migration files.
- Two-phase: one foundation migration (CHECK constraints, `ENTITY_TYPES` expansion); one per-entity migration each with its table creation and any relationship-vocab additions.

v2's existing migration discipline (per the v0.3 build) is one migration per coherent feature slice. The hybrid slice breakdown above naturally produces one migration per slice; the build-planning conversation confirms.

### Sidebar ordering

Each of the four schema specs places its entity at a specific position in the Methodology sidebar group (domain at #1, entity at #2, process at #3, crm_candidate at #4). The build-planning conversation confirms that the four positions ship as a single visible-to-user unit when v0.4 lands. The Methodology group itself is positioned below the existing Governance group per domain spec section 3.6.1.

### Coordinated affiliation/handoff create-dialog flow

Both `entity.md` section 3.6.4 and `process.md` section 3.6.4 explicitly defer their create-dialog reference-attachment flow to v0.4 build planning, with the suggestion that both panels behave consistently. The two patterns to choose between:

- **Create-then-attach.** The New dialog creates the entity-type record only; the user adds references from the detail pane via the existing "Add reference" affordance afterward. Two or more gestures per record.
- **Create-with-attach.** The New dialog includes multi-selects for the relevant reference targets (domains for entity; upstream/downstream processes for process); on submit the UI runs POST `/{entity-type}` followed by N × POST `/references` in sequence. One gesture per record regardless of reference count.

The decision applies to both `entity` and `process` panels uniformly (so users don't have to remember two patterns). The decision is UI-layer, not schema-layer; either choice satisfies the spec acceptance criteria.

### Spec guide section 6 amendment scope

The amendment to `methodology-entity-schema-spec-guide.md` section 6 reflects two conventions established by SES-012 and applied across SES-013 / SES-014 / SES-015:

1. **Parent-prefix field naming.** All non-identifier, non-timestamp fields on a methodology entity are prefixed with the parent entity name. Forward-only for methodology entities; governance-entity retrofit tracked separately as PI-006.
2. **`{source}_{verb}_{target}` relationship-kind naming.** New relationship-kind values involving methodology entities are named source-first. Forward-only for methodology vocab; governance vocab (`is_about`, `references`, `decided_in`, `supersedes`, `affects`, `covers`, `blocks`) unchanged.

The amendment is small (one paragraph per convention, plus a row addition or two to the cross-spec consistency table). The build-planning conversation produces the amendment as part of slice A or as a small companion edit.

### About-dialog version bump

Per the v2 version-source convention (CLAUDE.md line 50), `__version__` in `crmbuilder-v2/src/crmbuilder_v2/__init__.py` is the version source for the About dialog. The v0.4 close-out slice bumps `__version__` to `0.4.0`.

### README update

The v2 README at `crmbuilder-v2/README.md` (or wherever the current pointer lives) gets a v0.4 release note added. The build-planning conversation confirms the location and the format precedent from v0.3.

### Test target

`uv run pytest tests/crmbuilder_v2/ -v` continues to be the test target. The four new entity types add test coverage under `tests/crmbuilder_v2/`; the build-planning conversation confirms whether the existing test discovery pattern picks up the new modules without changes (it should).

### Closeout pattern

PI-008 — in-app inbox folder watcher for close-out JSON payloads — was authored at SES-012 with the suggestion that it could eliminate the apply_close_out.py script for future conversations. The build-planning conversation decides whether PI-008 ships in v0.4 (a sizable UI addition that goes beyond the per-entity panels) or defers to v0.5+. Working assumption: defer to v0.5+ to keep v0.4 focused on the methodology entity panels; PI-008 has its own architectural questions (which folder to watch, how to handle duplicate payloads, etc.) that warrant their own planning conversation.

### PI-006 sizing

PI-006 — governance-entity retrofit to parent-prefix field naming — was authored at SES-012 noting the substantial migration scope (eight existing tables, access-layer methods, REST API serialization, MCP I/O, UI dialogs, DB-export snapshots). The build-planning conversation decides whether to pull this retrofit into v0.4 or defer to v0.5+. Working assumption: defer to v0.5+, because the methodology entities ship with the new convention regardless and the retrofit is independent of the v0.4 release content.

---

## Working style

Per Doug's preferences:

- Discuss one architectural decision at a time. Wait for explicit approval before moving to the next.
- Plain text. Bold section headings OK. Avoid bullet-point overload.
- Terse approvals sufficient.
- Propose outlines; user approves before drafting begins. Once architectural questions are settled, execute the drafting end-to-end.
- The mode for this conversation is **ARCHITECTURE** (project default). Switch to DETAIL mode for the build prompts themselves at the appropriate point in the conversation if Doug requests it; the build prompts are surgical Claude Code instructions that may benefit from one-thing-at-a-time discussion.

For repo work: sparse checkout (CLAUDE.md, PRDs/product/crmbuilder-v2, crmbuilder-v2/src/, tests/crmbuilder_v2/), set git identity, `git pull --rebase origin main` before pushing. Doug commits; Doug pushes.

---

## Pre-flight checks

1. `curl -sf http://127.0.0.1:8765/health` — API up.
2. `uv run pytest tests/crmbuilder_v2/ -v` — v0.3 test suite green.
3. `git pull --rebase origin main` — clone current; SES-015 close-out applied (HEAD should be at or past the apply commit for `ses_015.json`).
4. Read items 1–13 in "Read this first".

---

## Governance — at conversation close

The conversation's actual close happens after the architectural discussion settles, the v0.4 PRD and implementation plan are drafted and committed, the slice build prompts are drafted and committed, and the spec guide section 6 amendment is committed. At that close, the conversation records:

- **Decisions.** Each architectural resolution becomes a DEC-NNN record. Working assumption: 4–8 decisions covering slice breakdown, migration ordering, affiliation/handoff create-dialog flow choice, spec guide amendment scope, PI-006 and PI-008 sizing, and any cross-spec-consistency-check issues that surfaced and were resolved.
- **Planning items.** Anything deferred to v0.5+ or v0.5+ that surfaces during planning. The build-planning conversation typically does not author many new PIs because the schema-design conversations already populated the v0.5+ candidate set; new PIs surface only if the build conversation reveals a new deferred surface (e.g., a slice acceptance criterion that's better evaluated post-CBM-redo).
- **Session record.** SES-016 (or whatever number lands) written through the v0.3 desktop New Session dialog at conversation's actual close. `topics_covered` opens with this seed prompt verbatim, then a structured summary of the cross-spec consistency check outcome and each architectural decision's resolution. `artifacts_produced` lists `ui-PRD-v0.4.md`, `ui-v0.4-implementation-plan.md`, the slice build prompts, the spec guide section 6 amendment, plus DEC-NNNs and PI-NNNs authored. `in_flight_at_end` names the next planned activity (Claude Code execution of slice A, then B, etc.).

The build-planning conversation is the last in the methodology-entity-schema-design workstream's planning arc. After it closes, the workstream's planning portion is complete and the build portion begins under Claude Code.

---

## What this conversation does NOT do

- **Execute build prompts.** The slice build prompts this conversation produces are executed by Claude Code in separate sessions. This conversation only writes them.
- **Modify v2's storage architecture beyond the additive extensions named in the four specs.** Per spec guide section 5, methodology-entity-schema design is additive: new tables, new endpoints, new access-layer methods, new vocabulary entries, no changes to existing entity types' shapes or behaviors. The build-planning conversation honors the same constraint.
- **Reopen schema design.** If the cross-spec consistency check surfaces an issue, it's resolved by small revisions to the affected schemas (per spec guide section 7.2's "small revisions" allowance). Material redesign would warrant reopening a per-entity schema-design conversation, which is a workstream-restart move not undertaken lightly.
- **Engage v0.5+ planning.** v0.5+ scope is captured in the PIs already authored by the workstream. The build-planning conversation does not pre-decide v0.5+ shape.
- **Address client-side methodology-content authoring tooling.** The four panels are the v0.4 surface for authoring Phase 1 content. Whether and how Phase 1 interview guides connect to these panels (e.g., auto-population from interview transcripts) is methodology-tooling territory deferred to a future workstream.

---

End of kickoff prompt.
