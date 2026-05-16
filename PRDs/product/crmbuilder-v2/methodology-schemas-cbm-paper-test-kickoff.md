# Methodology Schemas — CBM Content Paper-Test Kickoff

> ## Status: Deferred (as of 05-16-26 14:00)
>
> **This kickoff does not run next.** It runs after v0.5 (engagement management) ships and a CBM engagement has been created in v2.
>
> **Why deferred.** This kickoff was authored on 05-15-26 11:00 against the assumption that there was one v2 instance available to test against. v0.4 closeout subsequently surfaced that running the paper-test against the v2-build dogfood instance would mix CBM domain content into the same SQLite file that hosts the v2-build's own governance — exactly the kind of co-mingling that loses lineage. The v0.5-orientation conversation (05-16-26) committed v2 to building proper multi-engagement support (a new `engagement` entity type plus routing infrastructure) before any CBM content lands. See `PRDs/product/crmbuilder-v2/v0.5-engagement-management-workstream-plan.md`.
>
> **Predecessor work required before this kickoff runs.**
>
> 1. v0.5 ships. (Engagement management + multi-engagement routing.)
> 2. A CBM engagement record is created in v2 against the freshly-shipped `engagement` entity type, with its own SQLite database file.
> 3. This kickoff is lightly edited at run time to reflect that v0.5 has shipped and the paper-test runs against the CBM engagement specifically (not against the v2-build dogfood instance).
>
> **Scope and method are unchanged.** Everything below the rule remains the paper-test's intended frame; only the timing changes.

---

**Last Updated:** 05-15-26 11:00
**Purpose:** Seed prompt for a new Claude.ai conversation that validates the four MVS methodology entity schemas (`domain`, `entity`, `process`, `crm_candidate` — shipped in v0.4) against existing Cleveland Business Mentoring (CBM) domain content, producing a findings report and a single decision about whether CBM redo Phase 1 ships on v0.4 as-is or whether schema amendments are required first.
**Predecessor:** v0.4 ship — SES-024 (slice F closeout) + SES-025 (slice G records authoring, if numbered after this kickoff). See `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md` for what's in production; see `PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md` for the workstream context.

---

## The task

Drive a structured validation conversation that produces two deliverables:

1. **`PRDs/product/crmbuilder-v2/methodology-schemas-cbm-paper-test-findings.md`** — a findings report categorizing every relevant piece of CBM domain content against the four v0.4 schemas. Same length and shape as the schema-spec working notes: ~200–400 lines, prose-with-headings, no formal acceptance criteria section (the decision rubric in §6 below is the gate).
2. **A single, named decision at the end of the conversation** — either "Ship CBM redo Phase 1 on v0.4 as-is" or "Amend N specific schemas before CBM redo Phase 1 starts, in this order." If amendments are required, the conversation also names which deferred Planning Items (PI-003 persona, PI-004 field/requirement/manual_config/test_spec, PI-005 process_step growth, PI-013 Cross-Domain Service, PI-014 Catalog FK, PI-015 renderers, PI-016 router-vocab) the findings argue should open first.

Cadence per Doug's preferences:
- ARCHITECTURE mode default. One finding presented at a time. Doug confirms or pushes back before the next finding lands.
- Plain text discussion. Brief headings, no bullet overload. Terse approvals are sufficient.
- The findings report is drafted incrementally as findings are confirmed, not all at once at the end.
- The conversation's session record is captured at close per DEC-025 conventions.

---

## What "paper-test" means

This conversation does no code, no schema changes, no migrations, no PRD amendments, no database writes, no CBM repo edits. It reads CBM domain content with v0.4's schemas in mind and writes prose findings about fit.

Schema amendments — if findings demand them — become a separate follow-up workstream (a v0.5+ planning conversation). This conversation produces the case for or against that workstream; it doesn't open it.

The output is a report and a decision. That's all.

---

## Context — what's shipped (v0.4) and what's available (CBM content)

**v0.4 storage surface (shipped 05-15-26 per SES-024):**

- Four methodology entity tables: `domains`, `entities`, `processes`, `crm_candidates`. Schemas at `PRDs/product/crmbuilder-v2/methodology-schema-specs/{domain,entity,process,crm_candidate}.md`.
- Each is the MVS thin shape: identifier + name + description + status (or classification for process) + audit columns + soft-delete (for the soft-delete-eligible types). No field-level entity definitions. No process steps. No personas. No sub-domains. No cross-domain services. No catalog FK integration on methodology entities.
- Two reference kinds in production: `entity_scopes_to_domain` (entity → domain affiliation), `process_hands_off_to_process` (process → process bidirectional). Other reference kinds across methodology types are not in v0.4 vocab.
- v0.3 governance entity types (`decision`, `session`, `risk`, `planning_item`, `topic`, `reference`, `charter`, `status`) remain available alongside the new methodology types.

**Deferred to v0.5+ (tracked PIs):**

- **PI-003** — `persona` entity type. Every CBM domain has personas; v0.4 has no place to record them as data.
- **PI-004** — `field`, `requirement`, `manual_configuration_item`, `test_specification` entity types. The thin v0.4 `entity` shape carries no field-level definitions; CBM's Entity PRDs (Contact v1.5, Account v1.5, etc.) have detailed field tables that have no home in v0.4.
- **PI-005** — `process_step` entity type and richer process content. v0.4 `process` is thin (name + classification + handoffs); CBM's process docs have multi-step swimlanes.
- **PI-013** — Cross-Domain Service representation. The original methodology named Notes, Email, Calendar, Surveys as cross-domain entities. v0.4 has no representation.
- **PI-014** — Catalog FK integration. v0.4 methodology entities don't carry FKs into the catalog tables shipped in v2-C.
- **PI-015** — Methodology entity renderers (.docx, YAML, JSON exports per DEC-008). v0.4 ships zero renderer work.
- **PI-016** — Router-level per-pair vocab enforcement on `/references`. Theoretical until external clients hit the endpoint.

**Also explicitly deferred** (no PI as of this writing):

- Sub-domains. v0.4 `domain` is flat. The `domain.md` schema spec notes a self-FK migration path for sub-domain support in v0.5+; not authored yet.
- Master PRD as a methodology entity. v0.4 has no `master_prd` table.

**CBM repository state (as of the 04-30-26 user-memory snapshot):**

- **MN (Mentoring)** — five process docs plus Domain PRD complete. Six entity PRDs in scope (Contact v1.5, Account v1.5, Engagement v1.2, Session v1.1, Dues v1.1, MN-INTAKE v2.4). Personas, processes, and cross-domain service references are present in the docs.
- **MR (Mentor Recruiting)** — five process docs (Recruit, Apply, Onboard, Manage, Depart) plus Domain PRD.
- **CR (Client Recruiting)** — Domain Overview v1.2. **Has sub-domains**: Partner (complete), Marketing (complete), Events (complete), Reactivation (Sub-Domain Overview done; Outreach process pending). CR Reconciliation not yet done.
- **FU (Fundraising)** — not yet started.
- **Other** — Dues and SME Request need PRDs. Six entity PRDs deferred (Marketing Campaign, Campaign Group, Campaign Engagement, Segment, Event, Event Registration).
- **Pattern library** — `PRDs/methodology-extension/` carries a pattern library specification v0.1 and a nonprofit-mentoring pattern entry v0.1 from the methodology-extension work.
- **Methodology-extension docs** — phase 1 interview guide v0.2 and CBM redo ground rules v0.3 committed 04-30-26.

This is the content the paper-test reads against the four v0.4 schemas.

---

## Read this first

Before producing any finding, read the following in order:

1. **`crmbuilder/CLAUDE.md`** — universal entry. Check both repos' conventions are loaded.
2. **The four MVS schema specs** at `PRDs/product/crmbuilder-v2/methodology-schema-specs/{domain,entity,process,crm_candidate}.md`. End-to-end. Pay particular attention to each spec's §3 (schema specification, including the columns and the explicit deviations) and §3.7 (acceptance criteria — the contract v0.4 ships against).
3. **`PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md`** end-to-end. §2 Out of Scope is the canonical list of what v0.4 deliberately doesn't cover.
4. **`PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md`** — read the Phase 1 outputs definition. The MVS schemas were designed for Phase 1 outputs specifically; understanding Phase 1's scope sets the bar for what counts as "blocking" vs "v0.5+ gap."
5. **`PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md`** — the methodology guide. Section 6 (cross-spec conventions) and section 7 (consistency requirements).
6. **CBM repository content** (clone `dbower44022/ClevelandBusinessMentoring` separately, sparse). Suggested sparse checkout: `git sparse-checkout set --skip-checks CLAUDE.md PRDs/`. Read in this order:
   - `PRDs/MN/` — start here; this is the most complete domain
   - `PRDs/MR/` — second-most complete
   - `PRDs/CR/` — read carefully because of sub-domains (Partner, Marketing, Events, Reactivation)
   - `PRDs/services/` — even if mostly placeholder, it signals the Cross-Domain Service shape CBM expects
   - `PRDs/entities/` (if it exists) — at least one Entity PRD to anchor what "entity content" looks like in CBM's full-detail form
   - `PRDs/methodology-extension/` — the pattern library and phase-1 interview guide for the evolved methodology context

---

## The walk

The paper-test runs in two passes, in order. Both pass through CBM content; the difference is what they're looking for.

### Pass 1 — Phase 1 fitness check

For each CBM domain (MN, MR, CR, FU even if not started — FU is "ship a domain record with status: not started" not "no record"):

- **Domain check.** Does the domain map to a v0.4 `domain` record? Are name, description, and status (`active` / `archived` / etc. per the schema) sufficient? Are there fields CBM is trying to record at domain-level that have no v0.4 column?
- **Surfaced entity names check.** What entity names does Phase 1 surface for this domain? Do they map to v0.4 `entity` records (thin: identifier + name + description + status + domain affiliation)? Are there entities CBM treats as cross-domain that the `entity_scopes_to_domain` reference can't carry (because they scope to multiple domains)?
- **Prioritized Backbone check.** What processes does Phase 1 prioritize for this domain? Do they map to v0.4 `process` records (identifier + name + description + classification + domain FK)? Are the handoffs between processes captured by `process_hands_off_to_process` references, or are some handoffs cross-domain in a way the reference kind doesn't admit?
- **CRM Candidate Set check.** If CBM has named any CRM candidates yet (likely not, per the user memory — Engine pluggability for Attio first, then HubSpot, is tracked separately), do they map to `crm_candidate` records? If candidates are named at the project level (not per-domain), where do they live? (Note: per DEC-039, v2 is one-instance-per-engagement, so project-level is implicit.)

**Special checks Pass 1 should explicitly resolve, because each one is known a priori to be a candidate finding:**

- **Sub-domains in CR.** The CR domain has Partner / Marketing / Events / Reactivation sub-domains. v0.4 `domain` is flat. Options: (a) record CR alone as a v0.4 domain and treat sub-domains as descriptive text in the description field; (b) record four flat domains (CR-Partner, CR-Marketing, CR-Events, CR-Reactivation) with CR itself unused; (c) declare sub-domain support v0.4-blocking and require schema amendment before CBM redo Phase 1 starts. Pass 1 produces a recommendation.
- **Personas.** Every CBM domain has personas (mentors, clients, partner contacts, client administrators, etc.). v0.4 has no `persona` entity type. Options: (a) record personas as v0.4 `entity` rows with a convention-based identifier prefix (ENT-PERSONA-NNN or similar) and a description that flags "this is a persona"; (b) skip personas in v0.4 and accept Phase 1 outputs without persona data; (c) declare persona support v0.4-blocking. Pass 1 produces a recommendation.
- **Cross-Domain Services.** The original methodology names Notes / Email / Calendar / Surveys. PI-013 tracks the design question (is CDS a distinct entity type, subsumed into `process` with a future `process_kind`, or dropped?). Pass 1 names which CBM domains actually USE which CDS in Phase-1-relevant ways, and asks: does v0.4 need a representation, or can CBM redo Phase 1 produce usable output without CDS data?

### Pass 2 — v0.5+ gap inventory

After Pass 1 produces its blocking-vs-non-blocking findings, Pass 2 catalogs the gaps beyond Phase 1 — content CBM has detailed in its existing PRDs that would need v0.5+ capabilities to record properly. This pass is advisory; it doesn't affect the v0.4 ship/no-ship decision, but it produces the prioritization signal for which v0.5+ PI to open first.

For each of the deferred PIs, name which CBM content surfaces the need, and rate the severity (1 = nice-to-have for v0.6+, 3 = real friction for CBM redo Phase 2, 5 = blocking work that's already on the runway):

- **PI-003 persona** — already partially examined in Pass 1; Pass 2 captures the full scope.
- **PI-004 field/requirement/manual_config/test_spec** — every CBM Entity PRD (Contact v1.5, Account v1.5, etc.) has a detailed field table with names, types, required flags, defaults, validation rules. None of that fits in v0.4. Severity rating per Entity PRD.
- **PI-005 process_step growth** — every CBM process doc has a multi-step swimlane. v0.4 `process` is thin. Severity rating per process doc.
- **PI-013 Cross-Domain Service** — already partially examined in Pass 1.
- **PI-014 Catalog FK integration** — does any CBM Entity PRD claim correspondence to a base-entity-catalog entity (Account / Contact / Activity etc.)? If yes, severity rating.
- **PI-015 renderers** — does CBM currently maintain hand-authored .docx versions of Phase 1 outputs? (Almost certainly yes per current workflow.) Severity rating based on the operational cost of maintaining hand-authored outputs vs renders.
- **PI-016 router-vocab** — does any CBM workflow involve external scripts hitting `/references` directly? If no, this stays theoretical and a low priority.

---

## Findings categorization

Every finding lands in one of four buckets:

- **CLEAN.** Maps to a v0.4 record without interpretive stretch. The shape fits.
- **STRETCH.** Maps with mild interpretive stretch. The shape fits but only because the consultant adopts a convention not enforced by the schema. Worth documenting; not blocking.
- **NO HOME.** Concept doesn't exist in v0.4. Maps to a v0.5+ PI. Pass 2 work.
- **BLOCKING.** Concept is required for CBM redo Phase 1 to produce usable output, and v0.4 doesn't admit it. The paper-test recommends amending the schema before Phase 1 starts.

Most findings will be CLEAN or NO HOME. BLOCKING findings are the ones that matter for the v0.4 ship/no-ship decision. The threshold for BLOCKING is high: the gap must materially impair Phase 1 outputs (Domain Inventory, surfaced entity names, Prioritized Backbone, Initial CRM Candidate Set), not Phase 2+ work.

---

## The decision rubric

At the end of the conversation:

- **Zero BLOCKING findings** → recommend "Ship CBM redo Phase 1 on v0.4 as-is." The findings report names every STRETCH finding so consultants know which conventions to adopt, and every NO HOME finding so the v0.5+ PI prioritization signal is captured. The next workstream after this decision is the first CBM redo Phase 1 conversation (or a v0.5+ planning conversation for whichever PI rates highest in Pass 2 severity, depending on what's more urgent).
- **One or more BLOCKING findings** → recommend "Amend N schemas before CBM redo Phase 1 starts, in this order." Name each amendment, name the PI it likely fits under, and propose a sequence (which amendment opens first as a v0.5+ planning conversation). The next workstream is that first v0.5+ planning conversation; CBM redo Phase 1 waits.

The rubric leans toward "ship as-is" — STRETCH findings are not BLOCKING by definition, and v0.4 was designed against the MVS principle that real CBM-redo signal should drive v0.5+ work rather than speculative pre-redo amendments.

---

## Working style

Per Doug's preferences:

- ARCHITECTURE mode. The two-part test applies: a finding triggers a pause-and-present only when (1) the finding has real downstream impact AND (2) at least two viable categorizations are defensible. Routine CLEAN findings are noted and moved past; STRETCH findings get one-line documentation; NO HOME findings get a Pass 2 entry; BLOCKING candidates always pause for explicit discussion.
- Discuss one finding at a time. Wait for explicit approval or pushback before moving to the next.
- Plain text discussion. Bold section headings acceptable. Avoid bullet-point overload.
- Terse approvals ("yes", "confirm", "next") are sufficient — do not re-summarize or re-confirm.
- The findings report is drafted incrementally as findings are confirmed, not all at once at the end. By the time the last finding is confirmed, the report is ~90% complete; the final pass adds the §6 decision and the closing recommendation.
- Once the report is complete, do a full review at the end rather than per-section review during drafting.

The two-part test for what stops the flow applies: real downstream impact AND two viable options producing meaningfully different outcomes. BLOCKING findings pass both tests (impact = v0.4 ship/no-ship; options = ship-as-is vs amend-first). STRETCH findings rarely pass both tests (impact is small or rhetorical; options collapse).

---

## Governance — at conversation close

Per DEC-025 conventions, the paper-test conversation produces a session record at close.

- `identifier`: the next available SES-NNN after SES-024 (likely SES-025 if no other sessions land in the interim).
- `title`: "Methodology schemas — CBM content paper-test"
- `session_date`: the date the conversation closes (today's date for the closing turn).
- `status`: Complete.
- `conversation_reference`: descriptive text per DEC-025, identifying the conversation by its deliverable (`"Claude.ai paper-test conversation that produced methodology-schemas-cbm-paper-test-findings.md and the ship-as-is-vs-amend-first decision for CBM redo Phase 1. No transcript preserved per DEC-025."`).
- `topics_covered`: opens with `Seed prompt: contents of PRDs/product/crmbuilder-v2/methodology-schemas-cbm-paper-test-kickoff.md` (the conversation's seed is this file). Followed by a structured topic summary: domains tested, blocking findings (with count), stretch findings (count), NO HOME findings (count by PI), the final decision.
- `summary`: a paragraph narrating the paper-test pass-by-pass.
- `artifacts_produced`: the findings report path; any commits.
- `in_flight_at_end`: either "CBM redo Phase 1 unblocked; first Phase 1 conversation opens next" or "PI-NNN amendment workstream recommended as next conversation."

The session record can be authored at conversation close via the desktop dialog, or — if the paper-test is followed immediately by a Claude Code session that picks up the next workstream — via a Claude Code prompt that batches the records (the v0.4 closeout records authoring prompt is the precedent).

---

## Pre-flight

Before the first finding is discussed:

1. v0.4 closeout records all written. `sqlite3 v2.db "SELECT COUNT(*) FROM sessions WHERE identifier BETWEEN 'SES-017' AND 'SES-024'"` returns 8. Same check for DEC-068 through DEC-074 (returns 7). Same for PI-013 through PI-016 (returns 4). Status entity at phase `"v0.4 complete"`.
2. v2.db at Alembic head with all v0.4 migrations applied (0006 through 0010 at minimum). Full v2 suite green.
3. Both repos clean and at origin:
   - `crmbuilder`: `git status` clean, on `main`, `git pull --rebase origin main` returns no new commits.
   - `ClevelandBusinessMentoring`: same.
4. Read items 1–6 in the "Read this first" section above.

---

## What this conversation does NOT do

- **No code.** Pure reading + analysis + reporting.
- **No schema migrations.** Even if Pass 1 finds BLOCKING findings, the amendments are sketched in prose only — the actual migration work happens in a follow-up v0.5+ planning conversation and its Claude Code prompts.
- **No PRD amendments.** The four schema specs at `methodology-schema-specs/` are read-only inputs. Amendments to them — if recommended — are deferred to the follow-up workstream.
- **No CBM repo edits.** The CBM repo is read-only input.
- **No v2 database writes.** Including no session records or findings stored as v2 entity rows during the conversation. Records land at close per the governance section above.
- **No decision to open v0.5+ workstreams.** The paper-test produces a recommendation (ship-as-is or amend-first); opening any follow-up workstream is a separate conversation Doug initiates.
- **No findings about v0.3 governance entity types.** Out of scope. The paper-test is methodology-schema-validation only.

---

End of paper-test kickoff prompt.
