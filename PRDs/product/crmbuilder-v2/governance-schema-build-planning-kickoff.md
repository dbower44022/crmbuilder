# Governance Entity Schema Design — Build-Planning — Kickoff Prompt

**Last Updated:** 05-22-26 17:00
**Purpose:** Seed prompt for the build-planning conversation that closes the governance entity schema-design workstream. This conversation consumes the six per-entity schema specifications produced by the workstream's per-entity conversations and integrates them into the release artifacts that drive the actual build.
**Position in workstream:** **Seventh and final conversation** of the governance entity schema-design workstream. Predecessors: the workstream-establishing conversation (SES-047) and the six per-entity schema-design conversations (SES-048 workstream, SES-049 conversation, SES-050 reference_book, SES-051 work_ticket, SES-052 close_out_payload, SES-054 deposit_event). Successor: Claude Code execution of the build slice prompts produced here, followed by a build-closeout session written through the standard apply-close-out path.
**Workstream master:** `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md`
**Schema spec template:** `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md`

---

## The task

Take the six per-entity schema specifications produced by the workstream and produce the integrating release artifacts that drive the build. Drive a structured architectural and planning discussion that produces four deliverables:

1. **`PRDs/product/crmbuilder-v2/governance-entity-PRD-v0.1.md`** — the Product Requirements Document integrating the six schemas into a coherent release. Covers the scope (six entity types, two new relationship kinds per entity-pair on average, six new vocabulary additions), the user-interface integration (sidebar position, panel layouts, dialog patterns), the apply-path modifications (deposit_event POST integrated into the apply script), the backfill scope (PI-022 refinement), and the release timing (target user-interface version, set in coordination with the active version sequence at that time).

2. **`PRDs/product/crmbuilder-v2/governance-entity-implementation-plan.md`** — the implementation plan breaking the release into Claude Code slices, in dependency order. Typical slice topology (subject to revision during this conversation):
   - Slice A: Schema migrations and access layer (Alembic migrations for six tables, vocab.py updates for new entity types and relationship kinds, access-layer methods).
   - Slice B: REST API endpoints and envelope handling for the six new entity types.
   - Slice C: User-interface panels for the six new entity types (sidebar entries, master/detail panels, CRUD dialogs where applicable, references-section integration).
   - Slice D: Apply-script modifications (deposit_event POST integration, log file capture, apply_context computation).
   - Slice E: PI-022 backfill execution script and historical record reconstruction.
   - Slice F: Documentation, About-dialog version bump, README update, closeout.

3. **Per-slice Claude Code build prompts under `PRDs/product/crmbuilder-v2/prompts/`** — one prompt per slice, following the standard `CLAUDE-CODE-PROMPT-{series-tag}-{letter}-{descriptor}.md` naming pattern. Series tag and target user-interface version set during this conversation.

4. **PI-022 refinement** — the existing planning item for retroactive backfill of governance entity records, authored by SES-046, is refined here into a concrete execution plan. The refinement names which historical workstreams and conversations to populate, in what order, and with what authoring path (one-off script per Slice E, per the deposit_event spec's section 3.8.2 working assumption).

---

## Context — why build-planning last

The build-planning conversation runs after all six schema specifications exist because the cross-cutting concerns of the release require all six schemas to be visible at once. Concrete cross-cutting concerns:

- **Reference-vocabulary aggregation.** Each per-entity spec named the new vocabulary entries it requires (`vocab.py` `REFERENCE_RELATIONSHIPS` set additions and `_kinds_for_pair` clause additions). The aggregate is one consolidated `vocab.py` update plus one Alembic migration on the `refs.relationship_kind` CHECK constraint — the per-entity specs identify the pieces, build-planning produces the consolidation.
- **Sidebar grouping.** Six new entity panels join the Governance sidebar group. The build-planning conversation decides whether the resulting group is scannable as-is (the simple case — just append in workstream order at the end) or whether a sub-grouping is needed (e.g., "Governance — workflow" for the new six). The decision requires visibility into the existing Governance group's size plus all six new panel shapes.
- **Migration sequencing.** Six new tables, multiple `vocab.py` updates, and a `refs.relationship_kind` CHECK constraint relaxation. The order matters (the constraint must be relaxed before the new kinds are referenced; the new entity types must be in `ENTITY_TYPES` before the per-table migrations reference them as foreign-key targets via the references table). The build-planning conversation produces the canonical sequence.
- **Apply-path integration.** The deposit_event spec depends on the apply script being modified to write log files and POST deposit_event records. The modification is itself a slice, dependent on the API endpoints (Slice B) and the access-layer logic (Slice A) being in place first. Sequencing this slice against the user-interface slices is the build-planning conversation's call.
- **PI-022 refinement.** The retroactive backfill of governance entity records (for prior workstreams and conversations, including the schema-design workstream's own seven conversations) is a build-planning concern. The deposit_event spec's section 3.8.2 outlined the reconstruction strategy; the build-planning conversation produces the actual execution plan including ordering, the apply_context value for backfilled records, and the policy for placeholder fields where historical artifacts don't survive.
- **Cross-spec consistency reconciliation.** Inter-spec inconsistencies that surfaced during the per-entity conversations need resolution before the build proceeds — see "First task" below.

---

## First task — cross-spec consistency check (per spec guide section 7.2)

Per `governance-entity-schema-spec-guide.md` section 7.2, the build-planning conversation's first task is the cross-spec consistency check across all six schema specifications. The check verifies:

- No identifier prefix collisions across the six new entity types or against the existing prefix list.
- All six specifications use the cross-spec conventions in spec guide section 6, or explicitly justify deviations.
- Relationship-kind vocabulary additions across the six do not conflict.
- Status-value naming is consistent across specifications where the same concept is reused.
- Lifecycle interactions across specifications are coherent.
- User-interface panel layouts are either default or have rationale-justified deviations.
- Append-only versus soft-delete choices across specifications are coherent and intentional.

**One specific consistency finding is already known at this conversation's open**, surfaced by SES-054 (deposit_event schema-design conversation, Decision 2): the `close_out_payload.md` spec's at-most-one inbound `deposit_event_applies_close_out_payload` edge default needs to be relaxed to zero-or-more, per the multi-event-per-payload precedent established by SES-054. The close_out_payload spec section 3.8.3 explicitly invited that relaxation; SES-054 settled the question; this conversation reconciles the close_out_payload spec text. The reconciliation is a one-paragraph text revision to `close_out_payload.md` sections 3.3.2 and 3.4.3, with a corresponding change-log entry citing this conversation as the source.

The conversation may surface additional consistency findings during the systematic check; each is resolved before build-planning proper begins.

---

## Read this first

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md` — workstream master plan.
3. `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md` — schema spec template, especially section 6 (cross-spec consistency conventions) and section 7 (validation gates).
4. **All six completed schema specifications** at `PRDs/product/crmbuilder-v2/governance-schema-specs/`:
   - `workstream.md`
   - `conversation.md`
   - `reference_book.md`
   - `work_ticket.md`
   - `close_out_payload.md`
   - `deposit_event.md`
5. The seven session records for the workstream conversations (SES-047 workstream-establishing, SES-048 workstream, SES-049 conversation, SES-050 reference_book, SES-051 work_ticket, SES-052 close_out_payload, SES-054 deposit_event) in `db-export/sessions.json`.
6. The 36 decisions from those conversations (DEC-117 through DEC-160, minus DEC-153 and DEC-154 which are unrelated YAML schema decisions interleaved chronologically) in `db-export/decisions.json`.
7. **PI-022** — retroactive backfill planning item, authored by SES-046, refined by this conversation. In `db-export/planning_items.json`.
8. `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — current reference vocabulary; the consolidation target for the six specs' vocabulary additions.
9. `crmbuilder-v2/scripts/apply_close_out.py` — apply script; Slice D's modification target.
10. The closest precedent for an analogous build-planning effort: the methodology entity schema-design workstream's build-planning conversation (which produced `ui-PRD-v0.4.md` and its implementation plan). Inspect `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md` and `ui-PRD-v0.4-build-planning-kickoff.md` for the analog.
11. The active user-interface version sequence at the time of this conversation. Likely candidates for the governance-entity release: a fresh user-interface version (e.g., `v0.6`, `v0.7`, depending on what has shipped by the time this conversation opens) or bundling with a parallel release if timing aligns. The conversation sets the target version in coordination with the active sequence.

---

## Architectural and planning questions likely to arise

The conversation will surface these in some order. The list is illustrative, not exhaustive.

- **Target user-interface version.** Open at this writing — set during the conversation based on the active version sequence (e.g., the multi-tenancy routing fix slices' progress, the styling workstream's progress, any newer in-flight workstreams). Could be a dedicated version (governance-entity release) or bundled with adjacent work.
- **Slice topology.** The six slices named above (A schema, B API, C UI, D apply-path, E backfill, F closeout) are a working assumption. The actual slicing may differ — e.g., the six entity types could be split into multiple UI sub-slices if Slice C is too large for one Claude Code session; the apply-path slice could be merged with the API slice if the access-layer transactional logic is small enough.
- **Sidebar grouping policy.** Six new panels in the Governance group. Append at end versus sub-grouping (e.g., "Governance — workflow") versus reordering the existing group.
- **PI-022 refinement.** Which historical workstreams and conversations to populate, in what order. Strawman: populate the seven schema-design workstream conversations first (this gives the database its first workstream and conversation records, validating the new entity types end-to-end against real content), then expand backward to prior governance workstreams (methodology entity schema-design, user-interface v0.4 / v0.5, multi-tenancy routing fix), then to ad-hoc conversations. Each phase is its own backfill pass; deferring later phases to a future planning item is admitted.
- **Deposit-event log file tracking policy.** Per `deposit_event.md` section 3.8.1: are the captured log files git-tracked alongside the close_out_payload commit, or gitignored as ephemeral local artifacts? The build-planning conversation sets the policy and updates `.gitignore` accordingly.
- **About-dialog version bump.** The release closeout slice (Slice F or whatever its letter ends up being) bumps `crmbuilder-v2/src/crmbuilder_v2/__init__.py`'s `__version__` and updates the About dialog content.
- **Documentation updates.** README, `crmbuilder/CLAUDE.md` v2 section, the v2 Product Requirements Document index — what needs to update with the release.
- **Acceptance criteria aggregation.** Each per-entity spec contains its own acceptance criteria (typically 15 per spec, ~90 total). The implementation plan aggregates them into per-slice acceptance lists.
- **Backward compatibility.** No existing data lives in the new tables (they don't exist yet), so backward compatibility concerns are limited to: existing references-table data must continue to validate against the relaxed CHECK constraint; existing close_out_payload semantics must continue to hold under the at-most-one → zero-or-more relaxation. Both should be incidental.

---

## Working style

Per Doug's preferences:

- Discuss one architectural decision at a time. Wait for explicit approval before moving to the next.
- Plain text discussion. Bold section headings acceptable. Avoid bullet-point overload.
- Terse approvals ("yes", "confirm", "a", "1 good") are sufficient — do not re-summarize.
- Propose document structures and outlines; the user approves before drafting begins.
- Once architectural questions are settled and the implementation plan and PRD outlines are approved, execute the drafting end-to-end without per-step confirmation. Full review at the end.
- Slice build prompts may be drafted after the implementation plan is approved, in a single batch.

For repo work: sparse checkout (`git clone --filter=blob:none --sparse` then `git sparse-checkout set --skip-checks CLAUDE.md PRDs/ crmbuilder-v2/`). Set git identity before first commit. Always `git pull --rebase origin main` before pushing. Per the sandbox push convention, commit and push together in the same turn.

---

## Pre-flight checks

Before the first architectural question:

1. `curl -sf http://127.0.0.1:8765/health` — API up.
2. `uv run pytest tests/crmbuilder_v2/ -v` — test suite green.
3. `git pull --rebase origin main` — clone current.
4. Read items 1–11 in "Read this first."

---

## Governance — at conversation close

Per DEC-013, one Claude.ai conversation produces one session record. This conversation's session record is written **at the actual close of the conversation**, via the standard close-out apply path (payload at `close-out-payloads/ses_NNN.json` plus apply prompt at `prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md`).

The record captures:

- `identifier`: next available session identifier at conversation close (assigned per standard close-out flow).
- `conversation_reference`: descriptive text identifying the conversation by its deliverables. Example template: `"Claude.ai build-planning conversation that produced governance-entity-PRD-v0.1.md, governance-entity-implementation-plan.md, the per-slice Claude Code build prompts, and PI-022 refinement. No transcript preserved per DEC-025."`
- `topics_covered`: opens with the verbatim seed prompt rendered as `Seed prompt: "<the task statement at the top of this document>"`, followed by a structured summary of architectural and planning questions discussed.
- `artifacts_produced`: `governance-entity-PRD-v0.1.md`, `governance-entity-implementation-plan.md`, the per-slice build prompts (listed by filename), PI-022 refinement (patched in the close-out payload), plus decision records authored.
- `in_flight_at_end`: `"Claude Code execution of the build slice prompts. First slice: <Slice A schema or whichever slice the conversation decides to lead with>. Build-closeout session written through standard close-out path when the release ships."`

---

## What this conversation does NOT do

- Re-litigate the six schema specifications' content. Each spec is settled. The cross-spec consistency check may surface specific text revisions (the close_out_payload at-most-one relaxation is one known case), but the schemas' substantive design is not reopened.
- Execute the build. Build execution happens in Claude Code against the slice prompts produced here.
- Modify the existing methodology entity schemas (domain, entity, process, crm_candidate, engagement). Those remain unchanged per the workstream's scope.
- Touch in-flight parallel work (multi-tenancy routing fix slices, styling workstream, Cleveland Business Mentors Planning Item 001) beyond the release-version-coordination conversation needed to choose the target user-interface version.
- Open the Cleveland Business Mentors redo Phase 1 conversation. That waits on Planning Item 001 in the Cleveland Business Mentors engagement.
- Retroactively populate governance entity records during the conversation. The backfill is Slice E's responsibility, executed in Claude Code after the build slices land.

---

End of kickoff prompt.
