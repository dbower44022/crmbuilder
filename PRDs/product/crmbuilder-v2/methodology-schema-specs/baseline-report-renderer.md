# Methodology Design Spec — Baseline Report Renderer

**Last Updated:** 06-12-26
**Status:** Draft v1.0 — produced under WTK-116 (storage-area spec deliverable for the Phase 1.5 Baseline Report renderer)
**Position in workstream:** Closes the last named gap of the Phase 1.5 baseline family. Five sibling specs each declared the renderer out of scope while pinning the surfaces it consumes: `audit-report-to-candidate-deposit-transform.md` (WTK-090 — the candidate graph and the manifest boundary), `espocrm-data-profiling-pass.md` (WTK-096 — the metrics and advisory flags), `utilization-evidence-inline-on-candidates.md` (WTK-097 — the inline evidence object every surface presents, naming the renderer as a §6.2 consumer), `catalog-normalizer-type-mapping-and-partition.md` (WTK-102 — the T1–T4 priority bands "the Baseline Report orders by"), and `spreadsheet-source-store-and-profiling-output-persistence.md` (WTK-111 — the content-class rule that decides where a rendered document may live). This spec defines the renderer that composes them: Master CRMBuilder PRD v0.2 §7 Activity 5 — the generated document grouping candidates by best-guess domain, showing the standard/custom partition and the utilization findings, and leading with the gaps-and-ghosts list. Spec only — no code ships with this document.
**Companion documents:** `specifications/master-crmbuilder-PRD.md` §7 (Activity 5, output, completion criteria) and §8 (the triage conduct the report feeds); `governance-schema-specs/deposit-path-provenance-and-schema.md` (WTK-089 — `audit_deposit` apply_context, `observed_in`); `PRDs/process/interviews/interview-domain-discovery.md` (the Domain Discovery Report whose role this report is analogous to).

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 06-12-26 | ADO Area Specialist (storage) / Claude | Initial draft under WTK-116. Defines the input contract (the per-source candidate graph read via the landed `include_evidence=latest` projection, keyed by `evidence_source_label`; the manifest pair for the stock-schema signal that is deliberately not deposited; Phase 1 domain records as the grouping vocabulary), a deterministic render-time best-guess domain grouping that is never written back, the report structure (provenance header, summary, headline gaps-and-ghosts list with per-category v1 derivations and honest not-auditable postures, candidates by domain group ordered by the landed T1–T4 bands, personas, stock-usage section, coverage appendix, Phase 2/3 handoff), the output rule (one Markdown document per source system, written beside the manifest pair it renders from — inheriting WTK-111's content-class homes — with the deposit run rendering by default and recording `baseline_report_path` in `apply_context`), the read-only renderer invariant, and verification criteria R1–R12 including empty/missing-section behavior from a known fixture graph. |

---

## Change Log

**Version 1.0 (06-12-26):** Initial creation. No code ships with this document — it is the design the implementing Work Tasks build from. §9 enumerates the build surface.

---

## 1. Purpose and Position

Master CRMBuilder PRD v0.2 §7 Activity 5:

> **Render the Baseline Report.** A generated document grouping candidates by best-guess domain, showing the standard/custom partition, the utilization findings, and a headline **gaps-and-ghosts list**: items the system has that nobody may want anymore (low population, dormant), and structural oddities (workflows referencing deleted fields, empty roles). This report is working input to Phases 2 and 3 — analogous to the Domain Discovery Report, but machine-produced.

The supply side is fully landed: the deposit path writes the candidate graph with provenance (`transform/audit_deposit.py`, WTK-090), the profiler computes the metrics and advisory flags (WTK-096), the evidence projection delivers one normalized object per candidate per source (`access/evidence_projection.project_evidence_object`, the `include_evidence=latest` parameter — WTK-097), and the normalizer derives the T1–T4 triage bands at read time (`transform/normalize.derive_priority_band`, WTK-102 §5). The renderer is the **document-producing consumer** of all four — and it is strictly a consumer:

- **Read-only, both directions.** The renderer issues `GET` requests only against the V2 API and reads files the prior steps wrote; it never contacts the source system and never writes a DB record. All judgment-bearing derivations it performs (domain guesses, band ordering, probe seeds) exist only in the rendered document — nothing is stored (the WTK-102 §5.1 derived-not-stored posture, extended from bands to the whole render).
- **Mechanical.** No keep/drop judgment, no suppression. Every flag it prints is a WTK-096 flag or a re-derivation from typed metrics at recorded thresholds; every number is the inline evidence object's number, never recomputed (§7.2).
- **Per source system.** One rendered report per source, mirroring the one-deposit-event-per-source phase rule. A client with N existing systems gets N reports.

What "analogous to the Domain Discovery Report" means is pinned in §4.1: same *role* (a working artifact feeding Phase 2 discovery and Phase 3 reconciliation, deliberately not durable, no canonical IDs invented beyond what V2 already assigned), with the interview-derived sections replaced by their machine-derived counterparts.

---

## 2. Input Contract

The renderer assembles a **render model** (§7.1) from three inputs, all read per source system. None is the renderer's to produce; each was pinned by a prior spec.

### 2.1 The per-source candidate graph

**Definition.** The candidate set of source *S* is every methodology record whose evidence trail includes *S*: graph-theoretically, every record with an `observed_in` edge to an `audit_deposit` deposit event whose `apply_context` names *S* (WTK-089 §3.1); operationally — the normative read — every record of the five capture families whose `utilization_evidence.snapshots` contain an object with `source_label == S` (the WTK-088 per-(subject, source) key; the two definitions agree by WTK-089 invariant I5).

**Read path.** The landed WTK-097 §6 projection, exactly as that spec directed (`§6.2 Consumers: … the Baseline Report renderer … read this projection rather than assembling their own joins`):

- `GET /entities`, `/fields`, `/personas`, `/processes`, `/manual-configs` with `include_evidence=latest`, filtered client-side to records whose `snapshots` carry the source's label. Each retained record arrives with its current WTK-097 §3 inline evidence object for *S* — the only evidence object the report renders (other sources' objects are ignored; a multi-source candidate appears in each source's report under that source's evidence, per WTK-102 §5.4).
- `GET /deposit-events`, filtered to `audit_deposit` events whose `apply_context` matches *S* — the provenance header's facts (`snapshot_at`, `source_instance`, the `DEP-NNN` list) and the discovery route to the manifest pair (§2.2). The newest event's context is the header of record; older events are listed as audit history. (The WTK-089 §7 `kind` query filter was specified but is not yet landed; the renderer filters client-side and switches to the server filter when it exists — neither blocks this build.)
- `GET /references?target_id=DEP-NNN&relationship=observed_in` is **not** required: the evidence projection already carries per-source currency, and `snapshot_count` exposes history depth without a second query family.

**Statuses.** All live statuses render — `candidate`, `confirmed`, `deferred`, `rejected` — with status printed per item. At Phase 1.5 close everything is `candidate` (the phase rule), so the first render is homogeneous; a re-render after triage began is a legitimate working snapshot and must not hide disposed items (evidence survives disposition — WTK-097 A7). Soft-deleted records are excluded (they are not in the API reads).

**The placeholder domain.** The per-source `Baseline: {source_label}` domain (WTK-090 §4.4) is a mechanical container, not a finding. The renderer never presents it as a domain group; its processes are grouped by §3 like everything else, and the placeholder itself is noted once in the coverage appendix as a pending triage item.

### 2.2 The manifest pair — the stock-schema signal

Bare standard items are deliberately **not** deposited as candidates (WTK-090 §3.2 scope rule); the Master PRD routes their signal through this report: "standard items are signal only where the data profile shows real use", and the WTK-102 made it concrete — T3 "surfaces as: Baseline Report stock-usage section", T4 "coverage appendix only". The DB therefore cannot supply §4.6; the renderer reads the **manifest pair** directly:

- `audit-report.json` — the full discovery scope (including skipped natives and stock fields when `include_native_fields` was set), the classification markers, and the filter ASTs §5's G5 cross-checks.
- `utilization-profile.json` — record counts, recency, population, distributions, and the §5-feeding flags for everything profiled, *including entities and fields that produced no candidate* (WTK-096 §2.1: "a bare native entity's record count and recency still inform the Baseline Report even though no candidate is deposited for it").

**Location.** The deposit-run-integrated render (§6.3) has the pair trivially — it is the run's own input. For standalone re-renders: spreadsheet sources resolve it from the newest event's `apply_context.source_instance` (the `file://` snapshot URI — the pair lives in the snapshot, WTK-111 §4.1); EspoCRM sources have no file path on the landed event (the WTK-090 §4.3 `audit_manifest_path` key was specified but not built), so the build adds it as an additive diagnostic key (§9 item 2 — the WTK-089 §4.3 free-growth posture), and `--manifest`/`--profile` remain the explicit override, required against historical events that predate the key.

### 2.3 Phase 1 domain vocabulary

`GET /domains` (and `GET /processes` already fetched in 2.1) supplies the grouping vocabulary of §3: each Phase 1 domain's name, two-letter code, purpose text, and its Phase 1 process names (Master PRD §5 capture table). Phase 1 completion is a Phase 1.5 input precondition ("triage and discovery cannot organize baseline output without them" — Master PRD §7 Inputs), so a live engagement always has domains at render time; the §3 heuristic nonetheless degrades cleanly to a single Unassigned group when none exist (fixture and edge case, not the designed path).

### 2.4 Degraded modes

| Missing input | Behavior |
|---|---|
| `utilization-profile.json` absent (schema-only deposit) | Render proceeds. Bands collapse to the landed `T1/T2 (use unprofiled)` / `T3/T4 (use unprofiled)` values; the header and every band heading state that profiling is pending (the WTK-102 §5.3 rule, already encoded in `normalize.py`); §5 categories that need data metrics render their not-derivable note (§5.2). |
| Manifest pair unlocatable (moved client repo, purged snapshot) | **DB-only render.** §4.4/§4.5 render from candidates and evidence alone; §4.6 (stock usage) and the G5 cross-check render an explicit unavailability note naming the path that failed. Loud, never silent — the §4.7 coverage accounting marks itself partial. |
| No candidates for the named source | The render refuses with a clear error naming the label and the labels that do exist (a typo'd label must not produce an empty-but-plausible report). |
| No domains (§2.3) | Single `Unassigned` group; header notes Phase 1 domain capture was not found. |

---

## 3. Best-Guess Domain Grouping

**Posture.** The grouping is **advisory, render-time, and never written back**. Domain assignment is Phase 2/3 judgment (the deposit path refused to guess — WTK-090 §4.4 — and the renderer guessing *in the DB* would be the same violation); a printed guess in a working document is exactly as authoritative as a consultant's pencil note, which is the intent. Every group heading carries the qualifier "(best guess — triage assigns)".

**Algorithm (deterministic, fixture-stable).** For each candidate **entity**:

1. Build the candidate's token set: `entity_name`, the `Source:` block wire names from `notes`, and `detail.wire_name` — lower-cased, split on non-alphanumerics, stemmed only by trivial plural-strip (`s`/`es`), stop-words dropped.
2. Build each domain's token set once: domain name, two-letter code, purpose text, and the names of the domain's Phase 1 processes.
3. Score = count of shared tokens, weighted ×2 for tokens from the domain *name* (vs purpose/process text). Highest score wins; ties break by domain identifier ascending; score 0 → **Unassigned**.

**Inheritance and the other types:** fields inherit their parent entity's group unconditionally (a field never out-guesses its entity). Processes and manual_configs are scored independently by the same algorithm (their token sets: name, purpose/instructions, the filter's target entity name). **Personas are not grouped** — baseline persona candidates are roles and teams with no domain signal (WTK-090 §3.4), and a forced guess is noise; they render in their own cross-cutting section (§4.5), as the Domain Discovery Report's persona inventory also stands apart from its domain list.

The algorithm is deliberately modest: lexical, transparent, and cheap to be wrong — a misgroup costs the reader one scan of a short report, and triage reassigns regardless. A smarter (embedding- or LLM-assisted) grouping is a named deferral (§10) behind the same render-only boundary; the report format does not change when the heuristic does.

---

## 4. Report Structure

### 4.1 Analogy to the Domain Discovery Report

The Domain Discovery Report (interview guide, "What the Domain Discovery Report Must Contain") has four required sections; the Baseline Report is its machine-produced mirror — same role (working artifact, feeds Phase 2/3, nothing in it authoritative until reconciled), with interview provenance replaced by system provenance:

| Domain Discovery Report | Baseline Report counterpart |
|---|---|
| 1 Domain List (stakeholder-derived) | §4.4 group headings — Phase 1 domains applied as best guesses, plus Unassigned |
| 2 Candidate Entity Inventory ("source stakeholder and moment-in-interview") | §4.4 candidate listings — source-system evidence and `DEP-NNN` provenance per item |
| 3 Candidate Persona Inventory | §4.5 personas (roles/teams as persona *evidence*) |
| 4 Interview Transcript | §4.2 provenance header + §4.7 coverage appendix — the machine's transcript is its provenance and completeness trail |

What the report deliberately does **not** contain mirrors the Discovery Report's "deliberately not complete" list: no dispositions, no migration mappings, no canonical renames, no confirmation of anything — those are Phase 3 products.

### 4.2 Section map

One document, sections in this order. Every section has a defined empty state (third column) — a section is **never silently omitted**; absence of findings is itself a finding (the "renders without unexplained gaps" completion criterion).

| # | Section | Empty / degraded state |
|---|---|---|
| H | Provenance header | n/a — always renderable (a source with no deposit event fails §2.4 before rendering) |
| S | Summary | n/a — counts may be zero, table still renders |
| G | **Gaps and ghosts** (headline) | "No gaps or ghosts detected" + per-category notes for the not-derivable categories (§5.2) |
| D | Candidates by best-guess domain | A domain group with no candidates is omitted (groups exist *for* their content); zero candidates overall is unreachable per §2.4 |
| P | Personas | "No roles or teams were discovered in this source" (true for every spreadsheet source — WTK-110 emits none) |
| U | Standard/custom partition and stock usage | "Profiling pending" (schema-only) / "Manifest pair unavailable at `<path>`" (DB-only) / "No standard items in scope" (spreadsheet: all-custom by construction, D4) |
| C | Coverage appendix | Always renders — it is the completeness accounting |
| N | Phase 2/3 handoff notes | Static-plus-counts; always renders |

### 4.3 Provenance header (H) and summary (S)

**H** prints, from the newest deposit event and the inputs actually read: source label, `source_system` / `source_instance`, `snapshot_at`, `profiled_at` (or `schema-only: true`), the `DEP-NNN` list (newest first), the thresholds in force (`detail.thresholds`, else the `normalize.py` defaults — named either way so every flag in the document is reproducible), engagement, anomaly-PI identifier when one exists, and tool versions (`transform_version`, `profiler_version`, renderer version). **Product names are permitted** — the report is an internal working artifact (Master PRD §7: "Business-language rule applies to renders, not records" exempts this report explicitly; the L1/L2 neutrality rule binds the *client-facing* documents generated later).

**S** prints the counts table: candidates by type and status; band totals (T1/T2/T3/T4 or the collapsed forms); gaps-and-ghosts count by category; sources-of-record (manifest pair paths). The summary is derived from the same render model as the body, so the two cannot disagree (§7.1).

### 4.4 Candidates by best-guess domain (D)

Domain groups ordered by domain identifier ascending, **Unassigned last**. Within each group, the landed ordering rules apply verbatim (WTK-102 §5.4): entities by `record_count` descending then name; per entity, a fields table; T1 before T2 (band from `derive_priority_band` over the item's inline object); within T1 by `population_rate` descending, within T2 by `last_populated_at` descending (freshest ghost first); ties by name.

Per **entity**: identifier (`ENT-NNN`), name, status, band, kind (or "—"), the entity object's metrics one-liner (`412 records, newest 2026-06-09`), flags, and the `layouts_captured` curated-UI note when present. Per **field** (table columns): `FLD-NNN`, name, type, band, population (`398 / 96.6%`), last populated, option usage (`5 of 7 used` when enum), flags. Per **process** / **manual_config**: identifier, name, classification/category, the one-line filter render, flags. Identifier discipline throughout — every item leads with its V2 identifier, because triage dispositions reference these identifiers (Master PRD §8 conduct).

Numbers and flags come from the inline evidence object **verbatim** (§7.2). Where a metric is absent the cell prints `—` with the reason class distinguishable: `— (schema-only)` vs `— (no records)` — the WTK-097 A3 "unprofiled vs profiled-and-empty" distinction carried into print.

### 4.5 Personas (P)

Roles then teams, name ascending: `PER-NNN`, name, kind, the role's compact scope-access summary from `detail.scope_access`, status. The section restates the Master PRD capture-table caveat in one line — *source roles and teams are persona evidence, not personas; triage confirms or merges them against the Phase 1 interview personas* — and the G6 empty-roles posture (§5.2) is cross-referenced, not duplicated.

### 4.6 Standard/custom partition and stock usage (U)

Rendered **from the manifest pair**, not the candidate graph (§2.2):

- The partition summary: counts of custom vs standard entities and fields discovered, and the reminder that custom items are the candidate sections above while bare standard items deposit nothing by design.
- The **T3 table** — standard items in real use, ordered by population rate descending (entities by record count): the stock schema the organization actually leans on, each row noting "confirmable into a candidate at triage" status. Stock *fields* appear only when the audit captured them (`include_native_fields`); when it did not, the subsection states so rather than presenting entity-level-only data as complete.
- **T4 is not rendered here** — standard + dormant is the product noise floor and goes to the coverage appendix (§4.7), per the band table.

### 4.7 Coverage appendix (C)

The completeness accounting that makes "no unexplained gaps" checkable rather than asserted:

- **Reconciliation counts:** items in the manifest = items rendered in D + items rendered in U + items excluded by a *named* rule (skipped bare natives → WTK-090 §3.1; system class → never maps; stock fields undeposited → §3.2; T4 → noise floor), with the arithmetic printed. A nonzero unexplained remainder fails verification (R10).
- **T4 listing**, compact (name, class, dormancy fact) — present so completeness is auditable, per WTK-102 N5.
- **Anomalies:** the profile's `anomalies` array and the run's anomaly Planning Item (`PI-NNN`) — every unauditable or degraded item is visible here, satisfying "anything unauditable is logged as a Planning Item, not silently dropped".
- The placeholder domain note (§2.1) and, for spreadsheet sources, the snapshot path + content-identity reminder (the §4.2-of-WTK-111 chain the migration pre-flight will walk).

### 4.8 Phase 2/3 handoff notes (N)

A short fixed section: the **anchoring discipline** restated (this report is withheld from the stakeholder during Phase 2 until their unprompted account is captured; ghosts are introduced as probes, never as the opening frame — Master PRD §7), the instruction that the consultant reviews §G and flags the items to raise as probes (the §7 completion criterion), and the pointer that triage sessions batch by the §4.4 domain groups (Master PRD §8 "Batch by domain … using the Baseline Report grouping").

---

## 5. The Gaps-and-Ghosts List

The headline section (G) — rendered **before** the candidate body because it is the part the consultant must act on (review + flag probes is a phase completion criterion). Two source streams feed it: the **T2 band** (custom + dormant — WTK-102 §5.3: "surfaces as: the gaps-and-ghosts list") and the **structural-oddity categories** below. Each item renders as: category tag, identifier + name, the evidence one-liner, and a mechanically synthesized **probe seed** — a deterministic sentence in the Master PRD's probe shape (*"Your current system tracks X, but it hasn't been filled in since 2024 — tell me about that"*), advisory wording the consultant adapts.

### 5.1 Categories and v1 derivations

| # | Category | Derivation (v1) | Source of truth |
|---|---|---|---|
| G1 | Dormant / empty entities | `flags.dormant` / `flags.empty` on entity objects; *empty* renders distinctly ("never used" vs "no longer used" are different conversations — WTK-096 §5) | inline object flags |
| G2 | Low-population fields | `flags.low_population` | inline object flags |
| G3 | Stale fields | `flags.stale` ("hasn't been filled in since …") | inline object flags |
| G4 | Ghost options & undeclared values | `flags.ghost_options > 0` (declared-but-unused options, with the zeros from `detail.value_distribution`); `detail.undeclared_values` nonempty (values in data with no declared option — stale data or direct DB writes) | inline object detail |
| G5 | Automation referencing missing fields | Per process candidate with a recovered filter AST: each leaf attribute is resolved against (a) the manifest's audited fields for the tab's scope entity, then (b) the catalog's standard attributes for the source system (the WTK-102 tier-2 lookup). Unresolved → flagged ("filtered tab *Active Mentors* filters on `mentorStatus`, which no longer exists"). Catalog unseeded (the gitignored-catalog limitation) → the check degrades to manifest-only and says so per item ("unverified — stock fields not in catalog"), never silently passing or failing. Workflows join this category when their capture lands (WTK-090 §3.5 named the mapping); the category text and derivation are written to take them without restructuring. | manifest + catalog + filter ASTs |
| G6 | Empty roles | **Not derivable in v1, stated honestly.** The audit captures role/team identity and permissions, not membership (`RoleAuditResult` carries no user list or count), and the profiler's work-list is entities and fields. The category renders as a one-line not-auditable note for EspoCRM sources ("role membership is not captured by the v1 audit; review role assignment in the source admin UI during triage"), and is absent for spreadsheet sources (no roles exist — the P empty state covers it). The evidence key is reserved now — `detail.member_count` on persona-subject evidence — so when a source adapter supplies membership, G6 lights up with **zero renderer changes** beyond reading the key. | reserved `detail.member_count` |

Ordering within G: categories in the table's order; within a category, the T2 ordering rule (most-recently-abandoned first) for flag-derived items, name ascending for structural ones. An item matching multiple categories renders once per category — the categories are different conversations, and triage works them as such.

### 5.2 Empty and not-derivable states

A category with no findings prints `none found` under its heading. A category that **could not be evaluated** prints *why* (`schema-only deposit — data flags unavailable` for G1–G4; the G5 catalog note; the G6 posture above). The distinction is load-bearing: "we looked and found nothing" and "we could not look" must never render identically (the same A3 rule that governs metrics).

---

## 6. Output — Document, Home, and Deposit

### 6.1 One Markdown document per source system

The render target is **Markdown** (`baseline-report.md`) — the 05-26-26 format rule (all internal documents MD; this is an internal working artifact) and the consultant's working medium. A client-facing variant (Word/PDF) is out of scope and would be a later render of the same model (§10); nothing here forecloses it.

### 6.2 Home: beside the manifest pair it renders from

The report inherits **WTK-111 §4.1's content-class rule** — it contains the same bounded record-data excerpts the profile does (value distributions, option lists, top values), so it lives where the pair lives:

| Source path | Home |
|---|---|
| EspoCRM | the audit output directory in the client repo (`programs/audit-YYYYMMDD-HHMMSS/baseline-report.md`), beside `audit-report.json` — same content class as the pair already there; versioned by the client repo's git like every other audit artifact |
| Spreadsheet | the snapshot directory (`…/sources/{ENG}/{slug}/{snapshot}/baseline-report.md`) — record-data excerpts of a held file **never** enter a git-tracked tree or the client repo (WTK-111 §3.5 rule 1); the report gets the snapshot's immutability-convention, retention, and deletion-procedure properties for free |

`--output` overrides for ad-hoc renders; the operator overriding into a git-tracked tree for a spreadsheet source is the same self-inflicted class as profiling an unregistered directory. Writes are atomic (temp-file + rename, the family idiom).

### 6.3 "Deposited via the existing deposit path"

The report is a **document produced by the deposit run, recorded on the deposit event** — no new deposit machinery, no document entity:

- **Default-on render at deposit.** `crmbuilder-v2-deposit-audit` grows a render step after its evidence writes: it builds the render model from the just-deposited graph plus the manifest pair it was invoked with, and writes the report to the §6.2 home. Default **on** (`--no-render-report` to opt out) — the DEC-180 precedent: the phase's identity is that a first run produces its full output without intervention, and Activity 5 is part of the phase.
- **Provenance on the event.** The run includes `baseline_report_path` in the deposit event's `apply_context` — an optional diagnostic key, exactly the additive growth WTK-089 §4.3 designed for ("free to grow without schema or validation changes"). The report's own header (§4.3) carries the inverse pointer (`DEP-NNN`). Walking either direction answers "which document shows this deposit" / "which deposit produced this document".
- **Render failure never taints a successful deposit.** The deposit event is already posted when rendering begins (it is the run's last governance write, before evidence — WTK-090 §5); a render failure is reported loudly with its own exit status, the deposit stands, and the standalone re-render (below) is the repair path. Mirrors the pass-2-non-fatality rule of WTK-096 §2.2.
- **Standalone re-render, no governance record.** `crmbuilder-v2-render-baseline` re-renders from the *current* DB state at any time (after more evidence accrued, after Phase 1 domains were refined, under different thresholds). Like the standalone re-profile (WTK-096 §2.3), it writes **no** deposit event and touches no record; it overwrites the document in place (the EspoCRM home is git-versioned; the spreadsheet home's prior content is deterministically regenerable from inputs that are all retained). Registering reports as `reference_book` versions was considered and deferred (§10): the deposit-event pointer plus the file's own home already answer provenance, and a governance row per render of a regenerable working document is bookkeeping ahead of need.
- **No cell values in any log** (WTK-111 §3.5 rule 2 — store-wide). The *report* carries bounded excerpts by design (it is the rule-4 surface, like the DB evidence); the renderer's **run output and the deposit-event log** carry section names, counts, and paths only. R12 verifies.

---

## 7. Renderer Architecture and Determinism

### 7.1 Module shape

`crmbuilder-v2/src/crmbuilder_v2/render/baseline_report.py` (a new `render` subpackage — rendering is neither transform nor adapter, and both existing packages would mislead):

- `fetch_render_inputs(client, source_label) → RenderInputs` — the §2 reads, through a **GET-only client** (the module never constructs a write-capable client; the read-only invariant made structural, not behavioral).
- `build_report_model(inputs, *, rendered_at) → ReportModel` — pure; all grouping (§3), banding (delegating to `normalize.derive_priority_band` — never reimplemented), gap derivation (§5), ordering, and count reconciliation happen here. Unit-testable with no API, like `plan_deposit`.
- `render_markdown(model) → str` — pure string assembly; no logic beyond formatting.
- CLI `crmbuilder-v2-render-baseline --source-label <label> --engagement <ENG> [--manifest …] [--profile …] [--output …] [--rendered-at …]`, registered in the root `pyproject.toml` beside its siblings; plus the `--render-report`/`--no-render-report` integration inside `audit_deposit.main`, which calls the same three functions.

### 7.2 Determinism

Byte-identical output for identical inputs (the fixture property every family spec holds):

- `rendered_at` is injected (CLI flag or the deposit run's clock), never read from a wall clock inside the pure functions.
- Every metric, flag, and threshold is taken **verbatim** from the inline evidence object (WTK-097 §3.4 determinism extends through print); the renderer recomputes nothing it can read, and the one thing it derives from metrics (bands) goes through the single landed implementation.
- All orderings are total (§4.4, §5.1 tie-breaks included); model assembly iterates sorted keys only.
- Two renders of the same model are byte-identical; two model builds from the same inputs are equal (R8).

---

## 8. Verification Criteria

The fixture is the family's: the WTK-090 T1 manifest plus its T6 profile, deposited into a test DB (the landed transform is the fixture loader), with Phase 1 domain records seeded so grouping is exercised. Model-level checks run offline against `build_report_model`; end-to-end checks render the document and assert on its text. The implementation is correct when:

**R1 — Full render from the known fixture graph.** Every §4.2 section renders; the T1 fixture's known items land in the expected groups, bands, and orders; the document is byte-identical across two runs with the same `rendered_at`.

**R2 — Provenance header completeness.** H carries every §4.3 fact from the fixture deposit (label, instance, `snapshot_at`, `profiled_at`, `DEP-NNN`, thresholds, versions, anomaly PI); the schema-only variant prints `schema-only: true` and no `profiled_at`.

**R3 — Gaps-and-ghosts correctness.** A fixture seeded with one of each: empty entity, dormant-not-empty entity, low-population field, stale field, ghost-option enum (with declared zeros), undeclared-values enum, and a filtered tab whose AST references a nonexistent field — each appears in exactly its category (G1×2 distinctly, G2, G3, G4×2, G5), each with a probe seed; the EspoCRM G6 note renders; an item matching two categories appears under both.

**R4 — Empty and degraded sections.** Zero personas → P's empty state (not omission); zero ghosts → `none found` per category; schema-only run → collapsed band labels (the exact `normalize.py` strings) + §5.2 not-evaluable notes; manifest pair path removed → DB-only render with U's unavailability note and a partial-coverage marker in C; unknown source label → refusal naming known labels.

**R5 — Per-source isolation.** Two sources deposited into one engagement → two reports; no item or metric from one source's evidence appears in the other's report; a name-collided multi-source candidate appears in both, each under its own source's evidence object.

**R6 — Evidence parity.** Every number and flag printed for a candidate equals the value in its `include_evidence=latest` object for that source — asserted by walking the rendered tables against the API payloads (the renderer recomputed nothing).

**R7 — Band parity and ordering.** Printed bands equal `derive_priority_band` over the same objects; §4.4 within-group order and §5.1 within-category order hold on a fixture crafted with deliberate ties.

**R8 — Read-only and write-back absence.** The full R1–R7 suite records every API request: all GET (the WTK-096 P9 tripwire, applied here). After rendering, the DB is row-identical to before; no domain guess, band, or gap exists anywhere but the document.

**R9 — Stock section from the profile.** The fixture's bare native entity (no candidate exists for it — WTK-090 T10) renders in U with its record count and recency; with `include_native_fields` unset, the stock-fields subsection prints its not-audited note.

**R10 — Coverage reconciliation.** C's arithmetic balances on the fixture (manifest items = D + U + named exclusions, remainder zero); deliberately orphaning one manifest item from every rendered set makes the build's reconciliation check fail loudly.

**R11 — Homes and deposit integration.** A deposit run with rendering on writes the report beside the invoked manifest and records `baseline_report_path` in that event's `apply_context`; a spreadsheet-snapshot render lands inside the snapshot directory; a forced render failure leaves the deposit event `success` and exits nonzero on the render alone.

**R12 — Excerpt boundary.** A sentinel cell value seeded through the spreadsheet fixture appears in the report only inside admitted excerpt positions (distributions/option lists), and in no renderer run output and no deposit-event log.

---

## 9. Build Surface (for the implementing Work Tasks)

This spec ships no code. In dependency order:

1. **`crmbuilder_v2/render/baseline_report.py`** (§7.1): `RenderInputs`/`ReportModel` dataclasses, `fetch_render_inputs` (GET-only client), `build_report_model`, `render_markdown`. Bands via `transform.normalize.derive_priority_band`; evidence objects consumed as served (no local re-assembly).
2. **CLI** `crmbuilder-v2-render-baseline` in the root `pyproject.toml`; `--render-report` default-on integration in `transform/audit_deposit.py`'s `main`, including two additive `apply_context` keys — `baseline_report_path` (§6.3) and the specified-but-never-built `audit_manifest_path` (§2.2) — and the render-failure exit-status split (§6.3).
3. **No schema, vocab, or migration changes.** The one forward hook — persona-evidence `detail.member_count` (G6) — is an additive `evidence_detail` key under the WTK-097 §4 rules (additive keys bump nothing) and is written by *future adapters*, not by this build.
4. **Fixtures + tests** per §8 (model-level offline; R5/R6/R8/R11 against the API test harness; R12 over the spreadsheet fixture path).
5. **Out of scope here:** workflow capture (G5 takes it when WTK-090 §3.5's mappings land); role-membership capture (G6's supplier); the client-facing document render; the §10 deferrals.

## 10. Open Questions and Deferred Decisions

- **Smarter domain grouping** (§3): the lexical heuristic is the v1 floor. An LLM- or embedding-assisted guess (e.g., an ADO-style agent pass over the render model) stays render-only under the same never-written-back boundary; adopt if triage practice shows the lexical groups costing real session time.
- **`reference_book` registration of reports** (§6.3): revisit if reports start being cited as governance sources (e.g., a Decision quoting a report version that has since been re-rendered) — version pinning would then matter more than regenerability.
- **Client-facing render** (§6.1): a product-name-neutral variant for stakeholder distribution would need the L1/L2 neutrality pass and a format decision; deliberately not designed until a stakeholder actually needs the report rather than the conversation it feeds.
- **Per-domain triage worksheets:** Phase 3 batches by domain; splitting the report into per-domain working files (or generating a triage checklist per group) is a natural follow-on once a real triage session has run against the single-document form.
- **Report drift vs. the DB:** a rendered report is a snapshot; evidence keeps accruing. `snapshot_count` in the header plus the standalone re-render covers v1; an "is this report stale?" check (compare header `DEP`/`profiled_at` against current latest) could join the desktop UI's monitoring surface later.

## 11. Cross-References

- `specifications/master-crmbuilder-PRD.md` v0.2 — §7 Phase 1.5 (Activity 5, anchoring discipline, render-language rule, output, completion criteria), §8 Phase 3 (evidence-led conduct, batch-by-domain, the probes §5 seeds), §5 Phase 1 capture table (the domain vocabulary §2.3 reads)
- `utilization-evidence-inline-on-candidates.md` (WTK-097) — §3 the inline object (this report's metric vocabulary), §6 the `include_evidence` projection (§2.1's read path), A3 (the unprofiled/empty distinction §4.4 and §5.2 print), A7/A8
- `catalog-normalizer-type-mapping-and-partition.md` (WTK-102) — §4.5 (standard signal travels through this report), §5 bands/ordering (§4.4, §4.6, §5 consume; `transform/normalize.py` is the landed implementation)
- `audit-report-to-candidate-deposit-transform.md` (WTK-090) — §2.1 manifest, §3.1/§3.2 the exclusion rules §4.7 names, §3.5 (future workflow mappings → G5), §4.3/§4.4 apply_context and placeholder domain, §5 write ordering (§6.3's render-after-event), T1/T6/T10 fixtures
- `espocrm-data-profiling-pass.md` (WTK-096) — §2.1 (bare-native profiling for §4.6), §2.3 (the standalone-no-governance-record precedent §6.3 mirrors), §5 flags/thresholds, P9 (the GET-only tripwire R8 reuses)
- `spreadsheet-source-store-and-profiling-output-persistence.md` (WTK-111) — §3.5 rules 1/2/4 and §4.1 (the content-class home rule §6.2 inherits), §2 snapshot layout
- `governance-schema-specs/deposit-path-provenance-and-schema.md` (WTK-089) — §3.1 `observed_in` (the §2.1 graph definition), §4.3 apply_context additive keys (`baseline_report_path`), I5
- `PRDs/process/interviews/interview-domain-discovery.md` — the Domain Discovery Report sections and working-artifact posture (§4.1's analogy anchor)
- `crmbuilder-v2/src/crmbuilder_v2/transform/normalize.py` — `derive_priority_band`, `PRIORITY_BANDS`, the collapsed-band strings R4 asserts; `transform/audit_deposit.py` — the deposit CLI §6.3 extends; `access/repositories/utilization_evidence.py` / `access/evidence_projection.py` — `inline_evidence_block` / `project_evidence_object` (the served objects §7.2 trusts)
- `espo_impl/core/audit_manager.py` — `RoleAuditResult` (no membership capture — the G6 honesty), `FilteredTabAuditResult.filter` (the G5 ASTs)

---

*End of document.*
