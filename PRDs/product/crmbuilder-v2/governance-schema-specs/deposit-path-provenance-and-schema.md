# Governance Schema Design Spec — Deposit-Path Provenance Vocab and Schema Additions

**Last Updated:** 06-11-26
**Status:** Draft v1.0 — produced under WTK-089 (Architecture deliverable for the audit-to-V2 deposit path)
**Position in workstream:** Cross-cutting design spec defining the storage-layer additions the Phase 1.5 audit → V2 deposit path needs (Master CRMBuilder PRD v0.2 §7): the `observed_in` provenance reference kind, the extension of `deposit_event_wrote_record` to methodology capture targets, and the `deposit_event` record shape for audit deposits (a `deposit_event_kind` discriminator plus the audit-shaped `apply_context`). Companion to `methodology-schema-specs/candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088, commit `02d67738`), which this spec sequences against in §5 and does **not** re-spec.
**Companion documents:** `deposit_event.md` v1.0 (the entity spec this design amends when implemented); `specifications/master-crmbuilder-PRD.md` §7 (Phase 1.5) and §8 (Phase 3 baseline triage); `methodology-schema-specs/candidate-lifecycle-rejected-and-utilization-evidence.md` (the PI-153 design this one orders against).

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 06-11-26 | ADO Area Specialist (storage) / Claude | Initial draft under WTK-089. Decision 1: a new generic provenance reference kind `observed_in` (source: the five Phase 1.5 capture types; target: `deposit_event`), added as the usual vocab triple — `REFERENCE_RELATIONSHIPS`, `_kinds_for_pair`, and a dual-head refs-CHECK migration. Decision 2: extend the `deposit_event_wrote_record` `_kinds_for_pair` target tuple to the same five capture types (no CHECK change — the kind is already admitted). Decision 3: a `deposit_event_kind` discriminator column (`close_out_apply` \| `audit_deposit`) making the parent-edge requirement and the `apply_context` required-key shape kind-conditional; audit deposits carry source-system identity + snapshot timestamp, one deposit event per source system. Decision 4: migration ordering — the PI-153 migrations (WTK-088 design) land first, this spec's land second; the vocab-derived CHECK-rebuild convention makes the refs-CHECK end state order-insensitive either way. Verification criteria: migration round-trip on both heads, CHECK enforcement of the new kind, kind-conditional repository rules, and seven provenance invariants. |

---

## Change Log

**Version 1.0 (06-11-26):** Initial creation. Resolves the Master CRMBuilder PRD v0.2 Phase 1.5 known limitation "Provenance reference kinds (e.g., a dedicated `observed_in` relationship) may be added to the vocabulary" and gives the audit → V2 deposit path a defined storage target on the governance side. No code, vocab, or migration changes ship with this document — it is the design the implementing Planning Item builds from. §7 enumerates the implementation surface.

---

## 1. Purpose and Position

Master CRMBuilder PRD v0.2 §7 (Phase 1.5 — Existing System Baseline) requires that every audit run deposit its candidate records through a `deposit_event` whose `wrote_record` edges point at every candidate created and whose `apply_context` carries "the source system, instance identity, and snapshot timestamp," with **one deposit event per source system**. Three storage gaps stand between that requirement and the current schema:

1. **No provenance kind exists for the candidate → audit-run direction.** `deposit_event_wrote_record` records "this apply created this row" — write provenance, created exactly once per row at deposit time. It cannot express the observational fact a *re-audit* produces: "this already-existing candidate was observed again in this snapshot." The PRD names `observed_in` as the anticipated kind.
2. **`deposit_event_wrote_record` does not admit methodology targets.** Its `_kinds_for_pair` clause covers the close-out-apply record types (`session`, `decision`, `planning_item`, `reference`, `conversation`, `work_ticket`, `commit`) — not the five capture types Phase 1.5 deposits (`entity`, `field`, `persona`, `process`, `manual_config`).
3. **The `deposit_event` record shape assumes a close-out apply.** The access layer requires exactly one `deposit_event_applies_close_out_payload` parent edge (lazy-creating the payload when absent) and `deposit_event.md` §3.2 defines `apply_context` as `{apply_script_version, invocation, runner}`. An audit deposit has no close-out payload and needs source identity + snapshot time in `apply_context`; depositing through the current shape would manufacture a meaningless lazy payload per audit run.

This spec closes all three. It is a design document in the lineage of the governance schema specs and amends `deposit_event.md` when implemented; it deliberately does **not** touch the two PI-153 decisions already designed in `candidate-lifecycle-rejected-and-utilization-evidence.md` (the `rejected` lifecycle state and the `utilization_evidence` table) — only their migration sequencing and the two designs' interaction points are in scope here (§5).

---

## 2. Summary of Decisions

| # | Decision | Resolution |
|---|----------|------------|
| D1 | Observation provenance kind | New generic reference kind `observed_in`: source ∈ {`entity`, `field`, `persona`, `process`, `manual_config`}, target `deposit_event`. Full vocab triple: `REFERENCE_RELATIONSHIPS` registration, `_kinds_for_pair` clause, dual-head refs-CHECK migration. Appendable on re-audit; distinct from write provenance. |
| D2 | Write provenance to methodology targets | Extend the `deposit_event_wrote_record` target tuple in `_kinds_for_pair` with the same five capture types. Vocab clause only — the kind is already in the refs CHECK, so no CHECK delta is attributable to this decision. |
| D3 | Audit deposit record shape | New `deposit_event_kind` column ∈ {`close_out_apply`, `audit_deposit`}, NOT NULL, default `close_out_apply` (backfills all existing rows). Kind-conditional access rules: `close_out_apply` keeps the exactly-one parent-edge requirement and the existing `apply_context` shape unchanged; `audit_deposit` **forbids** the parent edge and requires `apply_context` to carry `source_system`, `source_instance`, `snapshot_at`. One deposit event per source system per Phase 1.5 run (process invariant, §4.4). |
| D4 | Migration ordering vs. PI-153 | PI-153's migrations (WTK-088 §6 surface) land first; this spec's land second, as the next head on each chain. The vocab-derived CHECK-rebuild convention makes the refs-CHECK end state order-insensitive, so a swapped or interleaved order is safe but not the canonical sequence. A single Planning Item building both may merge the two refs-CHECK rebuilds into one migration. |

---

## 3. Decision 1 — the `observed_in` Provenance Kind

### 3.1 Semantics: observation vs. write provenance

The deposit path produces two distinct provenance facts, and conflating them is what makes `wrote_record` alone insufficient:

| Kind | Direction | Fact recorded | Cardinality over time |
|---|---|---|---|
| `deposit_event_wrote_record` | `deposit_event` → record | "This deposit created this row." Mechanical write provenance. | Exactly one inbound per audit-deposited candidate, ever — rows are created once. |
| `observed_in` | candidate → `deposit_event` | "This candidate was present in the source system as of this deposit's snapshot." Observational provenance. | One outbound per audit run that observed the candidate — accumulates on re-audit. |

On a **first audit** of a source, the deposit path creates each candidate row, its inbound `wrote_record` edge, and its outbound `observed_in` edge to the same deposit event. On a **re-audit**, candidates matched to existing records (the matching rule is deposit-path transform logic, out of scope here) get a new `observed_in` edge to the new deposit event and **no** new `wrote_record` edge — their row was not written again. A candidate present in run 1 but absent from run 2 simply gains no second `observed_in` edge; the gap *is* the disappearance signal, queryable without any tombstone machinery.

This split keeps both PRD questions answerable independently: "where did this come from?" walks the single inbound `wrote_record`; "as of when was this last seen?" takes the newest outbound `observed_in` (whose deposit event carries `snapshot_at`).

### 3.2 Kind definition

| Property | Value |
|---|---|
| Kind name | `observed_in` |
| Source types | `entity`, `field`, `persona`, `process`, `manual_config` — the five Phase 1.5 capture types (Master PRD §7 table) |
| Target type | `deposit_event` |
| Mechanism | references-entity edge (`refs` table) |
| Created by | the deposit path, mechanically, in the same transaction as the candidate write (first audit) or by itself (re-audit match) |
| Cardinality | a candidate has ≥ 1 outbound `observed_in` once audit-deposited, one per observing run; a `deposit_event` has many inbound |

Naming follows the generic-single-name precedent (`resolves`, `addresses`, `blocked_by`, and WTK-088's `rejected_by_decision`) constrained by the pair rules, not the per-type `{source}_{verb}_{target}` pattern — the semantic is uniform across the five source types, and five per-type names would say nothing the pair constraint doesn't.

The source set is deliberately **the same five types** as WTK-088's `EVIDENCE_SUBJECT_TYPES` (`candidate-lifecycle…md` §4.3/§6): the things Phase 1.5 captures are exactly the things that carry evidence and need observation provenance. The implementing build should define this set once in `vocab.py` (e.g. a `BASELINE_CAPTURE_TYPES` frozenset) and have both the `observed_in` clause and `EVIDENCE_SUBJECT_TYPES` derive from it, so the two cannot drift.

### 3.3 The vocab triple

Per the established convention (CLAUDE.md "Reference relationship vocabulary"), adding the kind requires all three:

1. **`REFERENCE_RELATIONSHIPS`** — register `observed_in`, with a comment block citing this spec.
2. **`_kinds_for_pair`** — one clause: `if source_type in BASELINE_CAPTURE_TYPES and target_type == "deposit_event": kinds.add("observed_in")`. All five source types and `deposit_event` are live in `ENTITY_TYPES`, so the clause activates unconditionally — no dormant-TODO handling needed.
3. **Refs CHECK migration, dual-head** — rebuild `ck_ref_relationship` from current vocab on both chains (§5.2). The access layer (`references.create`) validates kind membership against `REFERENCE_RELATIONSHIPS` and the UI dialog drives off `RELATIONSHIP_RULES`; the DB CHECK is the third enforcement layer and the only one needing a migration.

No new entity type is introduced, so **no `change_log` CHECK rebuild is needed** for D1 — unlike the PI-153 set, which adds the `utilization_evidence` logging type (the known gotcha that WTK-088 §6 already carries; it stays on that side of the boundary).

### 3.4 Relation to `utilization_evidence` provenance

WTK-088's evidence table carries its own soft deposit linkage (`evidence_deposit_event_identifier`, `evidence_profiled_at`, `evidence_source_label`) because evidence is a mechanical table outside the refs discipline. The two mechanisms are complementary, not redundant: `observed_in` is the *candidate's* observation trail (a refs edge, visible to the reference graph and the UI); evidence rows are the *measurements* taken at that observation. Consistency between them is invariant I5 (§6.2).

---

## 4. Decision 3 — `deposit_event` Record Shape for Audit Deposits

(D2 — the `wrote_record` target extension — is fully stated in §2 and §3.1; its only build artifact is the `_kinds_for_pair` tuple growing five entries, with the existing comment style noting the audit-chain rationale.)

### 4.1 The `deposit_event_kind` discriminator

| Property | Value |
|---|---|
| Column | `deposit_event_kind` |
| Type | `String(32)` |
| Values | `close_out_apply` \| `audit_deposit` (new `DEPOSIT_EVENT_KINDS` frozenset in `vocab.py`) |
| Nullable | no; server default `'close_out_apply'` — the migration backfills every existing row to the kind it factually is |
| CHECK | `ck_deposit_event_kind` via the standard `_check_in` |
| Mutability | none — born-terminal append-only is unchanged; kind is set at POST and never changes |

A discriminator column is chosen over sniffing `apply_context` keys (fragile, undeclared) and over a separate `audit_event` entity (the lifecycle, identifier scheme, diagnostic-field set, and born-terminal posture are identical — a second entity would duplicate the whole spec for one conditional rule). The existing `DEP-NNN` identifier sequence is shared across kinds; the `kind` column is the partition.

### 4.2 Kind-conditional access rules

| Rule | `close_out_apply` (existing behavior, unchanged) | `audit_deposit` (new) |
|---|---|---|
| `deposit_event_applies_close_out_payload` parent edge | exactly one, required; lazy-creates the target payload; first-success drives `ready → applied` | **forbidden** — a POST carrying one is refused (422, error naming this rule). No lazy payload is ever created for an audit deposit. |
| `wrote_record` edges | zero or more, targets per the close-out record types | zero or more, targets per the extended tuple (capture types included). A failed audit deposit legitimately has zero. |
| `records_summary` cross-check | sum of values == count of `wrote_record` edges | identical — keys are the capture types (`entities`, `fields`, `personas`, `processes`, `manual_configs`). **Evidence rows are not counted**: `utilization_evidence` rows are mechanical children outside the refs discipline (WTK-088 §4.2), get no `wrote_record` edges, and appear in `apply_context` diagnostics if at all. |
| `error_info` conditional | null on success, required object on failure | identical |
| `log_file_path` | repo-relative, canonical `deposit-event-logs/dep_NNN.log` | identical — the audit run tees its transcript the same way |
| `apply_context` required keys | `apply_script_version`, `invocation`, `runner` (deposit_event.md §3.2) | §4.3 shape |

The `observed_in` edges a deposit creates are **outbound from the candidates**, not from the deposit event, so they ride the deposit transaction but are not part of the deposit-event POST body's `references` array; the deposit path creates them through the references write path alongside the candidate writes. `_split_references` therefore needs no third partition.

### 4.3 `apply_context` shape for `audit_deposit`

Required keys, validated at the repository layer when `kind == 'audit_deposit'` (upgrading the existing `isinstance(dict)`-only check for this kind):

| Key | Type | Description |
|---|---|---|
| `source_system` | string, non-empty | The source product, e.g. `"espocrm"`. The stable system identity, not the instance. |
| `source_instance` | string, non-empty | Instance identity — base URL or host, e.g. `"https://crm.cbmentors.org"`. Together with `source_system` this is the "source identity" half of the PRD's provenance rule. |
| `snapshot_at` | string, ISO 8601 UTC | When the audit read the source — the "as of when" half. Snapshot time of the *source data*, not the deposit time (`deposit_event_created_at` carries that). |

Recommended optional keys (not enforced): `invocation` and `runner` (same semantics as the close-out shape — the audit run has a command line and a driver too), `adapter` / `adapter_version` (the source adapter used, anticipating the spreadsheet adapter), `audit_run_directory` (the `programs/audit-YYYYMMDD-HHMMSS/` output of the schema audit), `profiler_version`. Everything beyond the three required keys is diagnostic depth, free to grow without schema or validation changes — the JSON column absorbs it.

`evidence_source_label` on evidence rows written by this deposit should be derived as `"{source_system} @ {source_instance host}"` so the denormalized label and the authoritative `apply_context` agree (invariant I5).

### 4.4 One deposit event per source system

A Phase 1.5 run against a client with N existing systems produces N audit runs and N `audit_deposit` deposit events — never one merged event. This keeps every candidate's provenance unambiguous: one inbound `wrote_record` walk terminates at exactly one source identity.

This is a **process invariant, not a schema constraint**: the schema cannot know what "one run" spans, and a legitimate *re-audit* of the same source produces a second deposit event for that source at a later `snapshot_at`. Enforcement is the Phase 1.5 completion check (Master PRD §7): the verification query "every candidate is reachable from its source's deposit event via `wrote_record`" is run per source, and a candidate reachable from two deposit events *with the same `snapshot_at`* indicates a split run (I7, §6.2).

---

## 5. Decision 4 — Migration Ordering Relative to the PI-153 Set

### 5.1 The two migration sets

Neither design has shipped migrations yet. The build surfaces:

- **PI-153 set** (WTK-088 §6 — *already designed there; not re-specced here*): rebuild the seven `ck_*_status` CHECKs for `rejected`; rebuild `ck_ref_relationship` admitting `rejected_by_decision`; rebuild the `change_log` entity-type CHECK for `utilization_evidence`; create the `utilization_evidence` table. Dual-head.
- **This spec's set**: rebuild `ck_ref_relationship` admitting `observed_in`; add `deposit_event_kind` + `ck_deposit_event_kind` to `deposit_events` with the `'close_out_apply'` backfill default. Dual-head. (D2 contributes no migration.)

### 5.2 Canonical order and why it is safe either way

**Canonical order: PI-153 first, this spec second** — on each chain, the PI-153 migrations take the next slots after the current heads (SQLite `0045_pi_134_findings_entity`, PG `0007_pi_134_findings_entity`), and this spec's single migration per chain follows as the next head after them. Rationale: PI-153's decisions gate triage and were designed first; the deposit path *consumes* both designs (it writes evidence rows and creates provenance edges in the same run), so the canonical sequence puts the consumed substrate ahead of the consumer. Absolute numbers are not pinned here — sibling builds may claim slots in parallel; the relative order is the spec.

The order is nonetheless **insensitive at the refs-CHECK level**, by the established rebuild convention (migrations `0044`/PG `0006`): each rebuild derives its predicate from the *live* `REFERENCE_RELATIONSHIPS` at migration runtime. Once `vocab.py` carries both `rejected_by_decision` and `observed_in`, whichever rebuild runs first already admits both kinds and the second is an idempotent superset rebuild. Downgrade symmetry holds the same way (`_KINDS_OLD = REFERENCE_RELATIONSHIPS - own _NEW_KINDS` retains the other set's kinds). What the canonical order buys is not correctness but a coherent downgrade window per design and a single answer to "which migration admitted this kind."

**Collapse option:** if one Planning Item builds both designs in one slice, the two refs-CHECK rebuilds should merge into a single migration whose `_NEW_KINDS` is the union — one table rebuild instead of two, per chain. The `deposit_event_kind` delta and the PI-153 table/status deltas stay in their own migrations regardless; only the refs-CHECK rebuild is shared surface.

### 5.3 Interaction points (the only PI-153 content in scope)

- **`evidence_deposit_event_identifier` is a soft reference** (WTK-088 §4.3) — no FK, so there is no hard schema dependency between the evidence table and the `deposit_event_kind` column in either direction. The runtime dependency is on the *deposit path build*, not the migrations: the first `audit_deposit` row requires the kind column, and the evidence rows it writes require the evidence table — both must be at head before the path first runs, which the canonical order satisfies trivially.
- **Shared capture-type set** — the `observed_in` source set (D1) and `EVIDENCE_SUBJECT_TYPES` are the same five types; define once (§3.2).
- **No shared CHECK other than `ck_ref_relationship`** — PI-153's status CHECKs and `change_log` rebuild touch tables this spec never touches; this spec's `deposit_events` delta touches a table PI-153 never touches. The refs CHECK is the single overlap, handled above.

### 5.4 Migration mechanics (per established conventions)

Both of this spec's migrations follow the house rules: the refs-CHECK rebuild uses the `0044` pattern verbatim (vocab-derived predicate, `_has_refs()` mid-stream-entry guard on the SQLite chain — every migration past `0036` must guard for chain entry mid-stream — batch_alter on SQLite, plain drop/create on PG; downgrade deletes the new-kind rows then rebuilds old). The `deposit_event_kind` delta uses `batch_alter_table` on SQLite with the same mid-stream guard (skip when `deposit_events` is absent); `deposit_events` carries plain column indexes only, so the batch-recreate expression-index hazard (fixed in `0040`) does not apply, but the build should re-verify against the model at implementation time. Downgrade for the kind delta deletes `audit_deposit` rows and their refs edges (they violate the old world's unconditional parent-edge invariant), then drops the column — destructive on downgrade, consistent with the `0044` delete-then-rebuild posture.

---

## 6. Verification Criteria

### 6.1 Migration verification

| # | Criterion |
|---|---|
| M1 | **Round-trip, both heads.** On each chain (SQLite from a copy of the live DB or create_all + stamp, per the catalog-data limitation; PG from the baseline): upgrade to the new head → downgrade across this spec's migrations → upgrade again, cleanly, with `alembic check`-equivalent silence at head. |
| M2 | **CHECK enforcement of the new kind.** Pre-migration (or post-downgrade), a raw `INSERT` into `refs` with `relationship_kind = 'observed_in'` fails the CHECK; post-upgrade it succeeds for a valid pair. A still-unknown kind fails post-upgrade (the rebuild is exact, not slack). |
| M3 | **Kind-column backfill.** Post-upgrade, every pre-existing `deposit_events` row reads `deposit_event_kind = 'close_out_apply'`; a raw `INSERT` with an out-of-enum kind fails `ck_deposit_event_kind`. |
| M4 | **Mid-stream entry.** Each new SQLite migration passes the stamp-`0036` mid-stream-entry test shape (no-ops cleanly when its target tables are absent). |
| M5 | **Order insensitivity.** With both designs' vocab in place, applying the two refs-CHECK rebuilds in either order yields a CHECK admitting both `rejected_by_decision` and `observed_in` (§5.2). |

### 6.2 Provenance and access-rule invariants

| # | Invariant | Enforced at |
|---|---|---|
| I1 | `observed_in` is admitted only for (capture type, `deposit_event`) pairs — `RELATIONSHIP_RULES`, the refs CHECK, and the kind-membership check agree. | vocab `_kinds_for_pair` + `ck_ref_relationship` |
| I2 | Every audit-deposited candidate has exactly one inbound `deposit_event_wrote_record` edge, from the deposit event of the run that created it, and ≥ 1 outbound `observed_in`; on a first audit both point at the same `DEP-NNN`. | deposit path (transactional) — covered by deposit-path tests |
| I3 | A re-audit that matches an existing candidate appends one `observed_in` and zero `wrote_record` edges to it. | deposit path — covered by test |
| I4 | An `audit_deposit` POST carrying a `deposit_event_applies_close_out_payload` edge is refused (422); a `close_out_apply` POST without one is refused (422, unchanged); no lazy payload is ever created on the audit kind. | repository layer |
| I5 | For every evidence row written by an audit deposit: `evidence_deposit_event_identifier` names that deposit, `evidence_profiled_at == apply_context.snapshot_at`, and `evidence_source_label` derives from `source_system`/`source_instance` (§4.3). | deposit path — covered by test (soft reference; not a schema constraint) |
| I6 | An `audit_deposit` POST whose `apply_context` lacks any of `source_system` / `source_instance` / `snapshot_at` (or whose `snapshot_at` is not ISO 8601) is refused (422). The `close_out_apply` shape validation is unchanged. | repository layer |
| I7 | One deposit event per source system per run: per source, every candidate of that run is reachable from exactly one `audit_deposit` event via `wrote_record` (Phase 1.5 completion query; process gate, not a schema gate). | Phase 1.5 completion check |

---

## 7. Implementation Notes (for the building Planning Item)

This spec ships no code. The build surface it defines:

- **vocab.py:** add `observed_in` to `REFERENCE_RELATIONSHIPS` and its `_kinds_for_pair` clause; extend the `deposit_event_wrote_record` target tuple with the five capture types; add `DEPOSIT_EVENT_KINDS`; introduce the shared `BASELINE_CAPTURE_TYPES` frozenset and re-derive `EVIDENCE_SUBJECT_TYPES` from it when the PI-153 build lands (§3.2).
- **models.py:** `deposit_event_kind` column + `ck_deposit_event_kind` on `DepositEvent` (§4.1).
- **Migrations, dual-head:** one refs-CHECK rebuild (or the §5.2 merged rebuild) + one `deposit_events` kind delta, per chain, ordered after the PI-153 set (§5).
- **Repository layer (`deposit_events.py`):** thread `kind` through `create_deposit_event`; make the parent-edge requirement, lazy-payload creation, and `ready → applied` transition conditional on `close_out_apply`; add the `audit_deposit` `apply_context` key validation (§4.2–4.3). `_split_references` unchanged.
- **API:** `deposit_event_kind` in the POST body (optional, default `close_out_apply`) and GET payloads; a `kind` list filter on `GET /deposit-events` mirrors the existing `outcome` filter.
- **`deposit_event.md` amendment:** §3.2 gains the kind column and the kind-conditional `apply_context` shape; §3.4's parent-edge rule becomes kind-conditional; the wrote_record target list gains the capture types — each amendment pointing here for rationale.
- **UI (deferred follow-on):** a Kind filter combo on the read-only deposit-events panel; rendering `source_system`/`snapshot_at` as labeled fields in the detail pane.
- **Out of scope (deposit-path build, not storage):** the `AuditReport` → candidate transform, the candidate matching rule for re-audits (I3's matcher), the data profiler, and the Baseline Report renderer.

## 8. Open Questions and Deferred Decisions

- **Candidate matching on re-audit** (§3.1): the rule deciding "same candidate" across runs (source-key match? name match?) is deposit-path transform logic with its own design; I3 assumes its existence, not its shape.
- **Disappearance handling:** a candidate absent from the latest snapshot gains no new `observed_in` edge — sufficient for triage queries. Whether disappearance should *also* write evidence (a zero-population row) is left to the profiler design.
- **Spreadsheet adapter identity:** `source_instance` for a file-based source (file path? drive ID?) is decided when that adapter lands; the three-key shape already accommodates it.
- **`reference` in the wrote_record tuple:** the existing tuple lists `reference`, which is not in `ENTITY_TYPES` (refs rows are targeted via `REF-NNNN`); the clause is inert in `RELATIONSHIP_RULES`. Pre-existing oddity, observed here for the record — not changed by this spec.

## 9. Cross-References

- Master CRMBuilder PRD v0.2 — §7 Phase 1.5 (phase-specific rules: provenance mandatory, one deposit event per source system; Known Limitations naming `observed_in`), §8 Phase 3 triage (`specifications/master-crmbuilder-PRD.md`)
- `governance-schema-specs/deposit_event.md` v1.0 — the entity spec amended by this design (DEC-155…160; born-terminal append-only precedents)
- `methodology-schema-specs/candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088, commit `02d67738`) — the PI-153 design sequenced against in §5; `EVIDENCE_SUBJECT_TYPES`, `evidence_deposit_event_identifier`, `evidence_profiled_at`
- Migrations `0044_pi_122_registry_binding_edges` / PG `0006` — the vocab-derived refs-CHECK rebuild convention; `0040` — the expression-index batch-recreate fix; the post-`0036` mid-stream-entry guard rule
- DEC-048 (relationship-kind naming) and the v0.8 generic-name precedent (`resolves`, `addresses`, `blocked_by`)
- `PRDs/product/features/feat-audit.md` v1.3 — the Audit function's discovery scope (Phase 1.5's schema-audit half)
