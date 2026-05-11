# Methodology Entity Schema Design — `crm_candidate` — Kickoff Prompt

**Last Updated:** 05-11-26 16:00
**Purpose:** Seed prompt for a new Claude.ai conversation that designs the `crm_candidate` entity type schema for v0.4.
**Position in workstream:** **Fourth and final** of four schema-design conversations. Predecessors: `domain`, `entity`, `process` (all must be complete before this conversation opens). Successor: the v0.4-build-planning conversation.
**Workstream master:** `PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md`
**Schema spec template:** `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md`

---

## The task

Design the `crm_candidate` entity type schema for v2's storage layer. A `crm_candidate` is one of the **two or three CRM products** selected at evolved Phase 1 for multi-deploy through the iteration loop — open source vs. commercial, hosting choices, budget, integrations, team-IT capabilities. The set persists across all iterations and is the basis for the final CRM selection in Phase 5.

Drive a structured architectural discussion that produces one deliverable:

**`PRDs/product/crmbuilder-v2/methodology-schema-specs/crm_candidate.md`** — the complete schema specification per the template in `methodology-entity-schema-spec-guide.md`.

This is the last per-entity schema-design conversation. After it closes, the next workstream conversation is **v0.4-build-planning**, which takes all four specs as input and produces the v0.4 PRD, implementation plan, and slice build prompts.

---

## Context — why crm_candidate is the simplest of the four

`crm_candidate` is the simplest schema in the workstream and the most isolated. It does not relate to `domain`, `entity`, or `process` — a CRM candidate is metadata about *where* the iteration deploys, not about *what* the iteration models. There are no references to declare for it (beyond standard references to decisions or sessions, which already exist in v0.3).

The schema is small:

- Per-record: identifier, name (the CRM product, e.g., "EspoCRM", "Salesforce", "HubSpot"), fit reason (one-paragraph rationale for inclusion in the candidate set), status (active / selected / declined / removed)
- Optional metadata: vendor URL, hosting type (cloud / self-hosted / both), license type (open source / commercial / freemium), price tier (free / paid)

The schema-design conversation primarily settles classification fields (status values, hosting-type enum, license-type enum) and the fit-reason field shape. There's little architectural complexity.

This is **the workstream's coda**. Its position last in the sequence is deliberate: by the time this conversation runs, the prior three schemas have established all the cross-spec consistency conventions (identifier prefix style, status casing, relationship-kind naming, UI patterns). `crm_candidate` follows them without renegotiation.

---

## Methodology context

Evolved Phase 1 produces an **Initial CRM Candidate Set** — two or three CRM products selected for multi-deploy based on coarse fit. Selection criteria per the phase outline:

- Open source vs. commercial
- Hosting (cloud / on-premise / both)
- Budget
- Integrations
- Team IT capabilities

Proposed by CRM Builder, verified by client. Final selection (Phase 5: "the client picks the winning CRM from the candidate set, based on lived experience across iterations and the cumulative Comparison Artifact") happens later. So the schema must support:

- Carrying records across all iterations of the engagement
- A lifecycle that includes "winning" (one record transitions to `selected` at Phase 5) and "losing" (others transition to `declined`)
- A clean way to record decommissioning of non-selected instances at Phase 5

What `crm_candidate` does *not* yet need in v0.4:

- **Per-iteration deployment logs.** Phase 3 territory (Deployment Logs are a separate Phase 3 output, not metadata on the candidate).
- **Per-candidate Comparison Artifact entries.** Phase 4 territory (Comparison Artifact is a separate artifact, not embedded in candidate records).
- **Cost tracking, license tracking, contract management.** Operational territory; not methodology content.

---

## Read this first

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. `PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md` — workstream master plan.
3. `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — schema spec template.
4. `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` — for conventions established by the first schema.
5. `PRDs/product/crmbuilder-v2/methodology-schema-specs/entity.md` — for conventions established by the second.
6. `PRDs/product/crmbuilder-v2/methodology-schema-specs/process.md` — for conventions established by the third.
7. `PRDs/process/research/evolved-methodology/evolved-methodology-phase-outline.md` — sections 3 (Phase 1's "Initial CRM Candidate Set" output, Phase 3's "Deployed instances" output, Phase 5's "CRM Selection Decision" output).
8. `PRDs/product/crmbuilder-v2/db-export/sessions.json` — read SES-011 and the three predecessor schema-design conversations' session records.
9. `PRDs/product/crmbuilder-v2/db-export/decisions.json` — read decisions from the three predecessor conversations.

---

## Architectural questions likely to arise

The conversation will surface these in some order; the list is illustrative.

- **Identifier prefix.** Working assumption: `CRM`. The methodology context is unambiguous so the prefix doubles cleanly as a meaning ("a CRM candidate"). Alternatives: `CC` (collision risk), `CAND` (generic). Confirm `CRM`.
- **Field inventory.** Working minimum: `identifier`, `name`, `fit_reason`, `status`. Optional but probably-useful: `vendor_url`, `hosting_type`, `license_type`. Decide which optional fields make the v0.4 cut.
- **Status lifecycle.** This is the most distinctive feature of `crm_candidate`. Working values: `active` → `selected` → `declined` → `removed`. Transitions:
  - `active` → `selected` (Phase 5: this CRM wins)
  - `active` → `declined` (Phase 5: this CRM doesn't win)
  - `active` → `removed` (mid-engagement: this CRM dropped from the set before Phase 5)
  - There can only be one `selected` record per engagement (Phase 5 picks one winner). Schema-level constraint or access-layer validation? Working assumption: access-layer validation (consistent with v2's existing soft-FK pattern).
- **`fit_reason` field shape.** Plain text or markdown? Working assumption: plain text in v0.4; markdown is overkill for a one-paragraph rationale. Phase 5 may want richer content (a final-selection rationale paragraph); revisit then.
- **`hosting_type` and `license_type` enums.** If included, what values? Working set for hosting: `cloud`, `self_hosted`, `both`. License: `open_source`, `commercial`, `freemium`.
- **No relationships to declare.** `crm_candidate` doesn't relate to `domain`, `entity`, or `process`. It relates only to standard governance entities (decisions and sessions cite it, but those references go *from* decisions and sessions *to* crm_candidate via the existing references infrastructure — no new vocabulary needed beyond a `references` value for source entity type).
  - **However:** references vocabulary needs to be able to *target* `crm_candidate` from existing entities. Check that `RELATIONSHIP_RULES` admits `crm_candidate` as a target entity type for relationship_kinds like `cited_by_decision`, `discussed_in_session`. If not, those vocabulary additions are this conversation's responsibility.
- **UI considerations.** Default panel layout fits well — 2–3 records is the typical engagement count. Master pane columns: identifier, name, status. Detail pane: identifier (read-only), name, fit_reason, status, optional metadata fields. No deviations expected.
- **Acceptance criteria.** Round-trip a sample CBM candidate set (e.g., three CRM candidates: EspoCRM active, SuiteCRM active, Salesforce active) through the UI.

---

## Working style

Per Doug's preferences:

- Discuss one architectural decision at a time. Wait for explicit approval before moving to the next.
- Plain text. Bold section headings OK. Avoid bullet-point overload.
- Terse approvals sufficient.
- Propose outlines; user approves before drafting begins. Once architectural questions are settled, execute the spec drafting end-to-end.

For repo work: sparse checkout, set git identity, `git pull --rebase origin main` before pushing.

---

## Pre-flight checks

1. `curl -sf http://127.0.0.1:8765/health` — API up.
2. `uv run pytest tests/crmbuilder_v2/ -v` — test suite green.
3. `git pull --rebase origin main` — clone current.
4. Read items 1–9 in "Read this first."

---

## Governance — at conversation close

This is the **final per-entity schema-design conversation**. Beyond the standard session-record-at-close pattern, this conversation's `in_flight_at_end` is distinct: it names the upcoming **v0.4-build-planning conversation** rather than another schema-design conversation.

The conversation also authors a small additional artifact: a **v0.4-build-planning kickoff prompt** at `PRDs/product/crmbuilder-v2/ui-PRD-v0.4-build-planning-kickoff.md` (or similar). The kickoff identifies the four schema specs as inputs and defines the v0.4-build-planning conversation's deliverables (the v0.4 PRD, implementation plan, slice build prompts, plus the cross-spec consistency check defined in section 7.2 of the schema-spec methodology guide).

The build-planning kickoff is authored at the close of this conversation because by then all four schemas exist and the kickoff can name them concretely.

Standard session record contents:

- `identifier`: next available SES-NNN
- `conversation_reference`: e.g., `"Claude.ai schema-design conversation that produced methodology-schema-specs/crm_candidate.md and the v0.4-build-planning kickoff. No transcript preserved per DEC-025."`
- `topics_covered`: seed prompt verbatim, then structured architectural-question summary
- `artifacts_produced`: `methodology-schema-specs/crm_candidate.md`, `ui-PRD-v0.4-build-planning-kickoff.md`, plus DEC-NNNs and PI-NNNs authored
- `in_flight_at_end`: `"Workstream's four schema-design conversations are complete. Next: v0.4-build-planning conversation against ui-PRD-v0.4-build-planning-kickoff.md, which produces the v0.4 PRD, implementation plan, and slice build prompts."`

---

## What this conversation does NOT do

- Build code.
- Modify v2's storage architecture beyond additive extensions for `crm_candidate`.
- Plan v0.4 build slices. That's the v0.4-build-planning conversation's job.
- Address deployment-log structure, comparison-artifact structure, or selection-decision capture. Those are Phase 3, 4, and 5 territory respectively, and they all live in `decision` records or future entity types — not in `crm_candidate` itself.

---

End of kickoff prompt.
