# Methodology Entity Schema Design — `domain` — Kickoff Prompt

**Last Updated:** 05-11-26 16:00
**Purpose:** Seed prompt for a new Claude.ai conversation that designs the `domain` entity type schema for v0.4.
**Position in workstream:** **First of four** schema-design conversations. Predecessors: SES-011 (workstream planning). Successors: `entity`, then `process`, then `crm_candidate`.
**Workstream master:** `PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md`
**Schema spec template:** `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md`

---

## The task

Design the `domain` entity type schema for v2's storage layer. Drive a structured architectural discussion that produces one deliverable:

**`PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md`** — the complete schema specification per the template in `methodology-entity-schema-spec-guide.md`. The directory does not yet exist; this conversation creates it.

Cadence matches SES-011 and the v0.1/v0.2/v0.3 planning conversations: structured architectural discussion driven one decision at a time, building toward the spec section by section.

At conversation close: decisions written via direct API as DEC-NNN records; any deferred items written as PI-NNN records; one session record written by Doug through the v0.3 desktop New Session dialog per the session-record-at-close pattern.

---

## Context — why domain first

`domain` is foundational. Both `entity` and `process` reference it (entity can scope to or span domains; process belongs to a domain). Designing `domain` first means the downstream schemas use it as a settled referent rather than placeholder.

As the workstream's first schema-design conversation, this conversation also **establishes the cross-spec consistency conventions** the subsequent three schemas will follow. The spec guide names categories (identifier-prefix style, status-value casing, relationship-kind verb-tense) but does not pre-decide values; the first decision a downstream conversation faces is "does the convention `domain` chose still fit my entity?" — so `domain`'s choices carry implicit downstream weight.

---

## Methodology context

CBM redo uses the **evolved methodology**. Evolved Phase 1 (Mission and Backbone Identification) produces a **Domain Inventory** — a short list of domains with one-paragraph descriptions, proposed by CRM Builder and verified by client. The Domain Inventory is intentionally lighter than the current 13-phase Domain Discovery Report — it does not include candidate entities or candidate personas; those surface in Phase 3 work.

So the `domain` schema needs to host:

- A short list of records (a typical engagement has 3–8 domains)
- Per-domain: name, one-paragraph description, lifecycle status (candidate → confirmed → deferred, or similar)
- Relationship-readiness for `entity` and `process` to reference it later in the workstream

What `domain` does *not* yet need:

- Full domain documentation (Domain Overview-style content); that's Phase 4 of the original methodology and lives in Phase 3 iteration outputs in the evolved methodology
- Domain-to-domain relationships (sub-domains, parent domains); the evolved methodology doesn't formalize sub-domain hierarchy at Phase 1
- Cross-Domain Service distinction; services are structurally parallel to domains in the original methodology, but the evolved methodology doesn't address this at Phase 1 — keep services out of scope for `domain`'s v0.4 shape

---

## Read this first

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. `PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md` — workstream master plan.
3. `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — schema spec template.
4. `PRDs/process/research/evolved-methodology/evolved-methodology-phase-outline.md` — sections 1–3, especially Phase 1's outputs.
5. `PRDs/process/research/evolved-methodology/phase-1-interview-guide.md` v0.2 — search for "Domain Inventory" to see how the interview elicits domains.
6. `PRDs/product/crmbuilder-v2/db-export/sessions.json` — read SES-011 to see what this workstream conversation set up and why.
7. `PRDs/product/crmbuilder-v2/db-export/decisions.json` — read DEC-038 through DEC-043 (the six decisions from SES-011).

---

## Architectural questions likely to arise

The conversation will surface these in some order. The list is illustrative, not exhaustive — let the conversation flow.

- **Identifier prefix.** Working assumption: `DOM`. Alternatives: `DOMAIN` (verbose), `D` (too short), `DM` (collision risk with future entities). Decision.
- **Field inventory.** Working minimum: `identifier`, `name`, `description`, `status`. Anything else for v0.4? Notes/rationale field? Mission-alignment statement?
- **Status lifecycle.** Working assumption: `candidate` → `confirmed` → `deferred` (+ `archived`?). What transitions are valid? Default starter status?
- **Description field shape.** Plain text vs. markdown vs. JSON-structured? The methodology says "one paragraph" — keep it plain text for now, or anticipate markdown for Phase 3?
- **Relationship vocabulary additions.** What `relationship_kind` values do we need to declare for use by `entity` and `process` later? Working set: `entity_scopes_to_domain`, `process_belongs_to_domain` — but these get declared in the entity and process specs, not in domain's. Should domain's spec list them as anticipated additions for downstream specs?
- **UI deviations.** The default panel layout from the spec guide fits well for a small list of 3–8 records. Likely no deviation needed.
- **Acceptance criteria.** Translate the schema into testable statements per spec guide section 3.7.

---

## Working style

Per Doug's preferences:

- Discuss one architectural decision at a time. Wait for explicit approval before moving to the next.
- Plain text discussion. Bold section headings acceptable. Avoid bullet-point overload.
- Terse approvals ("yes", "confirm", "a", "1 good") are sufficient — do not re-summarize.
- Propose document structures and outlines; the user approves before drafting begins.
- Once architectural questions are settled and outline is approved, execute the spec drafting end-to-end without per-step confirmation. Full review at the end.

For repo work: sparse checkout (`git clone --filter=blob:none --sparse` then `git sparse-checkout set --skip-checks CLAUDE.md PRDs/ crmbuilder-v2/`). Set git identity before first commit (`git config user.email "doug@dougbower.com"`, `git config user.name "Doug"`). Always `git pull --rebase origin main` before pushing.

---

## Pre-flight checks

Before the first architectural question:

1. `curl -sf http://127.0.0.1:8765/health` — API up.
2. `uv run pytest tests/crmbuilder_v2/ -v` — test suite green.
3. `git pull --rebase origin main` — clone current.
4. Read items 1–7 in "Read this first."

---

## Governance — at conversation close

Per DEC-013, one Claude.ai conversation produces one session record. This conversation's session record is written **at the actual close of the conversation, not during drafting**.

Doug writes the session record through the v0.3 desktop New Session dialog. The record captures:

- `identifier`: next available SES-NNN at conversation close (compute via `client.list_sessions()` or check `db-export/sessions.json`).
- `conversation_reference`: descriptive text identifying the conversation by its deliverable. Example template: `"Claude.ai schema-design conversation that produced methodology-schema-specs/domain.md. No transcript preserved per DEC-025."`
- `topics_covered`: opens with the verbatim seed prompt rendered as `Seed prompt: "<the task statement at the top of this document>"`, followed by a structured summary of architectural questions discussed.
- `artifacts_produced`: `methodology-schema-specs/domain.md`, plus DEC-NNNs authored, plus PI-NNNs authored.
- `in_flight_at_end`: `"Next workstream conversation: entity schema design. Kickoff at schema-design-kickoff-entity.md."`

---

## What this conversation does NOT do

- Build any code. The build happens later — first when the schema spec feeds the v0.4-build-planning conversation, then when that conversation's slice prompts run in Claude Code.
- Modify v2's storage architecture beyond what the new entity type additively requires. New table, new endpoints, new access-layer methods — yes. Modify existing entity types' tables, endpoints, behaviors — no.
- Plan beyond `domain`. The next three schemas have their own conversations.
- Design `entity` or `process` inline because they reference `domain`. They have their own kickoffs.

---

End of kickoff prompt.
