# Methodology Entity Schema Design — `entity` — Kickoff Prompt

**Last Updated:** 05-11-26 16:00
**Purpose:** Seed prompt for a new Claude.ai conversation that designs the `entity` entity type schema for v0.4.
**Position in workstream:** **Second of four** schema-design conversations. Predecessor: `domain` (must be complete before this conversation opens). Successors: `process`, then `crm_candidate`.
**Workstream master:** `PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md`
**Schema spec template:** `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md`

---

## The task

Design the `entity` entity type schema for v2's storage layer. The "entity" here is the **CRM-modeled noun** — Contact, Account, Session, Engagement, Dues — the things the eventual CRM stores records about. Not to be confused with v2's storage-layer entity types (decisions, sessions, charter, etc., which are governance constructs); when this conversation says "entity" it means the methodology-content concept.

Drive a structured architectural discussion that produces one deliverable:

**`PRDs/product/crmbuilder-v2/methodology-schema-specs/entity.md`** — the complete schema specification per the template in `methodology-entity-schema-spec-guide.md`.

Cadence matches SES-011, the `domain` schema-design conversation, and the v0.1/v0.2/v0.3 planning conversations: structured architectural discussion one decision at a time, building toward the spec section by section.

At conversation close: decisions written via direct API as DEC-NNN records; deferred items written as PI-NNN records; one session record written by Doug through the v0.3 desktop New Session dialog per the session-record-at-close pattern.

---

## Context — why entity is delicate

The `entity` schema is the most provisional of the four in v0.4. Evolved Phase 1's interview guide explicitly states (line 62): *"Phase 1 may surface entity names as nouns the client uses, but does not produce Entity PRDs."* And line 477: *"The Domain Inventory... does not include candidate entities or candidate personas; those are drafted in Phase 3 for in-scope domains."*

So evolved Phase 1 surfaces entity *names* but does not define entities. The decision to include `entity` in v0.4's minimum-viable inventory (per DEC-039) was made on the argument that real Phase 1 conversations naturally surface entity vocabulary, and if v2 has no entity type, those names end up as loose nouns inside session notes or process descriptions, requiring retrofit at the Phase 3 boundary.

The implication for the schema: **`entity` ships thin in v0.4** — name, brief description, status — and grows in v0.5+ as Phase 3 demands attach fields, relationships, and full PRD content. The v0.4 schema must be designed with that growth path in mind, not as a final shape.

---

## Methodology context

Phase 1 work surfaces entities like this (extracted from the Phase 1 interview guide structure):

- The consultant talks the client through the Prioritized Backbone processes.
- As processes are discussed, the client uses nouns naturally: "we track each *mentor* alongside the *clients* they work with"; "the *organization* has *funders* and *fundees*"; etc.
- The consultant records the nouns as candidate entities — but does *not* drill down into fields, validations, or relationships. That's Phase 3 work.

What `entity` in v0.4 needs to host:

- Per-record: name, brief description, lifecycle status (candidate is the typical Phase 1 starter; confirmed comes in Phase 3+)
- Domain affiliation — though many entities span domains (Contact is shared across MN/MR/FU in CBM). So entity-to-domain is many-to-many, not containment.
- The domain affiliation likely uses the existing `reference` infrastructure with a new `relationship_kind` (e.g., `entity_scopes_to_domain`), not a direct FK column on `entity` — because direct FK would imply single-domain, which the methodology contradicts.

What `entity` does *not* yet need in v0.4:

- **Fields.** Entity fields are a Phase 3 deliverable; in v0.4 there's no `field` entity type and no field-list on entity records. Tracked as PI-004.
- **Validation rules, defaults, types.** Same — Phase 3.
- **Inter-entity relationships** (e.g., Contact belongs to Account). Phase 3 territory.
- **Visibility/security per role.** Way later — Phase 4+.

---

## Read this first

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. `PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md` — workstream master plan.
3. `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — schema spec template.
4. `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` — the **predecessor schema**. Read for conventions established in the first conversation (identifier-prefix style, status-value casing, relationship-kind verb-tense). Deviations from those conventions require justification.
5. `PRDs/process/research/evolved-methodology/phase-1-interview-guide.md` v0.2 — especially line 62 (entity definition section) and the surrounding context on how entity names surface.
6. `PRDs/product/crmbuilder-v2/db-export/sessions.json` — read SES-011 (workstream planning) and the `domain` schema-design conversation's session record.
7. `PRDs/product/crmbuilder-v2/db-export/decisions.json` — read decisions from the `domain` conversation.

---

## Architectural questions likely to arise

The conversation will surface these in some order. The list is illustrative, not exhaustive.

- **Identifier prefix.** Working assumption: `ENT`. Alternatives: `E` (too short), `MENT` for "methodology entity" (clearer but verbose), `ENTITY` (verbose). Note: must not collide with existing prefixes.
- **Field inventory.** Working minimum: `identifier`, `name`, `description`, `status`. Phase 1 surfaces these naturally. Anything else for v0.4?
- **Domain affiliation mechanism.** Many-to-many via references (working assumption) vs. direct FK with multi-value support (less standard in v2). The references approach is consistent with v2's existing patterns and the methodology's "Contact is shared across domains" reality.
- **Status lifecycle.** Working assumption: same as `domain` — `candidate` → `confirmed` → `deferred` (+ archived?). Phase 1 entities start as `candidate`; Phase 3 Entity PRD work moves them to `confirmed`.
- **Description field shape.** Plain text suffices for Phase 1 nouns. Anticipate markdown for Phase 3 when descriptions get richer?
- **Relationship vocabulary additions.** Working set: `entity_scopes_to_domain` (entity-to-domain m:m). Anticipated for v0.5+: `entity_referenced_by_process`, but that gets declared in `process`'s spec.
- **UI considerations.** Default panel layout fits. Worth checking: does the master pane benefit from showing domain affiliation as a column? May be worth it for usability with a moderate-sized entity list.
- **Acceptance criteria.** Translate the schema into testable statements per spec guide section 3.7. Critically: a sample CBM Phase 1 record (e.g., "Contact" scoping to MN, MR, FU domains via three references) should round-trip through the UI.

---

## Working style

Per Doug's preferences:

- Discuss one architectural decision at a time. Wait for explicit approval before moving to the next.
- Plain text discussion. Bold section headings acceptable. Avoid bullet-point overload.
- Terse approvals sufficient.
- Propose outlines; user approves before drafting begins. Once architectural questions are settled and outline is approved, execute the spec drafting end-to-end without per-step confirmation.

For repo work: sparse checkout, set git identity, `git pull --rebase origin main` before pushing.

---

## Pre-flight checks

Before the first architectural question:

1. `curl -sf http://127.0.0.1:8765/health` — API up.
2. `uv run pytest tests/crmbuilder_v2/ -v` — test suite green.
3. `git pull --rebase origin main` — clone current.
4. Read items 1–7 in "Read this first."

---

## Governance — at conversation close

Per DEC-013, one Claude.ai conversation produces one session record. This conversation's session record is written **at the actual close of the conversation**, by Doug, through the v0.3 desktop New Session dialog.

Record contents follow the SES-011 and `domain`-conversation pattern:

- `identifier`: next available SES-NNN at conversation close
- `conversation_reference`: e.g., `"Claude.ai schema-design conversation that produced methodology-schema-specs/entity.md. No transcript preserved per DEC-025."`
- `topics_covered`: seed prompt verbatim, then structured architectural-question summary
- `artifacts_produced`: `methodology-schema-specs/entity.md`, plus DEC-NNNs authored, plus PI-NNNs authored
- `in_flight_at_end`: `"Next workstream conversation: process schema design. Kickoff at schema-design-kickoff-process.md."`

---

## What this conversation does NOT do

- Build code.
- Modify v2's storage architecture beyond additive extensions for `entity`.
- Plan beyond `entity`.
- Define entity **fields**. Fields are Phase 3 work and tracked as PI-004. The `entity` v0.4 schema is intentionally fields-less.
- Address inter-entity relationships (Contact-to-Account, etc.). Phase 3 work.

---

End of kickoff prompt.
