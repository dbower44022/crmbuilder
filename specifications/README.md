# CRMBuilder Specifications — Directory Manifest

| Field | Value |
|-------|-------|
| Version | 0.2 |
| Last Updated | 09-04-26 00:45 |
| Status | Manifest — three canonical documents plus the first domain-overview render and the first persona render |
| Audience | Anyone trying to find the definitive document for a CRMBuilder topic |
| Governs | Navigation of the `specifications/` directory |

## Purpose

This directory holds the canonical specifications for CRMBuilder — the process, the normative governance discipline, and the shared vocabulary. When the question is "where is the definitive document for X?", read this manifest first; it names what is here today, in what order to read it, and where the historical material that is being superseded still lives until consolidation completes.

The directory exists because CRMBuilder documentation was previously federated across many locations under `PRDs/`. The consolidation captured by `specifications/master-crmbuilder-PRD.md` is in progress and is being authored iteratively against CRMBuilder's own dogfood engagement. Documents here are the future source of truth as their topics are folded in.

## Current Canonical Documents

The files below are the current contents of this directory. Each is the canonical specification for its scope as of the date noted on its frontmatter.

| File | Purpose | Version / Status |
|------|---------|------------------|
| `master-crmbuilder-PRD.md` | Process-definition document for using V2 to capture the complete definition of a product, from first interview through deployed application. Internal L3 specification — names V2 specifically. Currently being authored against CRMBuilder dogfood; phase content drafted iteratively. | 0.1 (draft) — DISCUSSION DRAFT, NOT YET APPROVED |
| `governance-recording-rules.md` | Normative rules for authoring governance records in V2 — workstreams, sessions, conversations, decisions, planning items, references, work tickets, close-out payloads. Applies equally to AI and human agents per DEC-310. | 0.1 — DISCUSSION DRAFT |
| `governance-recording/domain-overview.md` | Domain Overview for Governance Recording, the methodology's ninth, cross-cutting domain (DEC-1003): identity, big question, scope, personas, processes, entities, rules corpus. A dated render of domain record DOM-012 in the V2 store, which is the source (DEC-1021). | 0.4 — DISCUSSION DRAFT, render of a candidate domain record |
| `governance-recording/session-conversation-governance-process.md` | Process PRD for the Session/Conversation Governance Process, the first concrete process of the Governance Recording domain: one process in four variants (Claude Code, sandbox, human-only, pipeline), twenty steps from open to close, edge cases, anti-patterns and the close-out completeness audit as acceptance criteria. A dated render of process record PROC-010 in the V2 store, which is the source (DEC-1021). | 0.3 — DISCUSSION DRAFT, render of a mission_critical process record |
| `personas/governance-recording-personas.md` | Persona records the Governance Recording domain involves and no earlier domain defined: PER-013 Engagement Lead, PER-014 Claude Code Agent, PER-015 Claude.ai Sandbox Agent — role, responsibilities, Governance Recording duties, decision authority, lifecycle, participant backing. Personas are first-class and cross-domain, so the render lives under `personas/`, not in a domain folder. A dated render of the persona records in the V2 store, which is the source (DEC-1021). | 0.1 — DISCUSSION DRAFT, render of candidate persona records |
| `glossary.md` | Canonical definitions of terms used across CRMBuilder methodology, governance, and process documentation. Terms carry stable `TERM-NNN` identifiers; alphabetical order is rendering-only. | 0.2 — In progress, terms added as discussed |

## Recommended Reading Order

A new contributor or returning operator should read in this order:

1. **`governance-recording-rules.md`** — every session and conversation operating against any V2-tracked engagement follows this document. It is normative and applies regardless of which methodology a session executes. Read it first because compliance starts at the first record you author.
2. **`master-crmbuilder-PRD.md`** — the process itself. What V2 is for, how the phases sequence, what artifacts each phase produces. Read second because the rules above govern any work you do under this process.
3. **`glossary.md`** — terminology reference. Read on demand; consult whenever a term needs grounding.

## Document Tier Vocabulary (L1 / L2 / L3)

The terms L1, L2, and L3 appear in CRMBuilder documents but are not yet formally defined in a standalone reference. The in-use distinction, drawn from `master-crmbuilder-PRD.md` §1 and the existing automation PRDs:

- **L1 / L2** documents are intended to be product-name-neutral; client-facing artifacts generated from V2 records follow the L1/L2 rule (no mention of EspoCRM, WordPress, etc.).
- **L3** documents are internal and may name specific products, surfaces, and implementation details (SQLite, REST API, MCP, PySide6).

A formal definition belongs in `master-crmbuilder-PRD.md` or `glossary.md` as the consolidation continues. Until then, this section is the working summary.

## Supersession History

This directory does not maintain its own supersession ledger. The authoritative list of documents being consolidated into `master-crmbuilder-PRD.md` lives in the repo root `CLAUDE.md` under the "Current direction: Master CRMBuilder PRD consolidation" section. That list currently names:

- The 13-phase Document Production Process (`PRDs/process/CRM-Builder-Document-Production-Process.docx`)
- The interview and guide documents (`PRDs/process/interviews/`)
- The three conduct documents (`PRDs/process/conduct/`)
- The V2 user process guide (`PRDs/process/v2-user-process-guide.md`)
- The L1/L2 automation PRDs (`PRDs/product/crmbuilder-automation-PRD/`)
- Other V1/V2 product PRDs as their content is folded in

Each superseded document carries a transitional status header pointing at `master-crmbuilder-PRD.md` as the future source of truth. Until the Master CRMBuilder PRD covers a given topic, the corresponding existing document remains the operative reference for that topic.

## How to Add a New Document

When a new specification belongs here:

1. Place the file in `specifications/` (or a topical subdirectory if the document set has grown enough to warrant one).
2. Add an entry to the **Current Canonical Documents** table above — filename, one-line purpose, current version/status.
3. Give the file a frontmatter block at the top (a Markdown table with Version, Last Updated, Status, Audience, Governs) matching the style of the existing three files.
4. Include a Purpose paragraph immediately after the frontmatter.
5. If the new document supersedes a document elsewhere in the repo, update the CLAUDE.md "Documents being consolidated and superseded" list and add a transitional status header to the superseded document.

Do not delete superseded documents; let them remain available as historical reference until the consolidation is fully validated.

## Cross-References

- `CLAUDE.md` (repo root) — orientation, current direction, and the supersession ledger.
- `PRDs/product/crmbuilder-v2/` — V2 architecture, component PRDs, execution history, close-out payloads, deposit-event logs.
- `PRDs/process/` — legacy methodology documents being consolidated into `master-crmbuilder-PRD.md`. Still operative for any topic the Master CRMBuilder PRD has not yet covered.
- `PRDs/product/` — V1 product PRDs and the federated automation PRDs.

## Change log

| Version | Date | Change |
|---|---|---|
| 0.1 | 09-03-26 19:30 | Manifest created with the three canonical documents and the first domain-overview render (SES-392 / CNV-364). |
| 0.2 | 09-03-26 23:05 | Added the first persona render, `personas/governance-recording-personas.md` v0.1; domain-overview row bumped to v0.4; change log added (SES-395 / CNV-367, PI-086). |
| 0.3 | 09-04-26 00:45 | Added the first process render, `governance-recording/session-conversation-governance-process.md` v0.3 (SES-388 / CNV-360, PI-087). |
