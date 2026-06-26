# CRMBuilder v2 — Documentation Index

A curated map of the V2 design, architecture, and user docs in this directory.
It is **not exhaustive** — the directory also holds many per-session kickoff
prompts, per‑PI design/verification notes, and schema‑design prompts that are
historical records (see [Historical records](#historical-records)).

**Authoritative sources of current state:**
- The repo‑root **`CLAUDE.md`** is the living description of V2's current state and
  conventions — read it first; where any doc here disagrees, CLAUDE.md wins.
- The **V2 database** is the source of truth for governance (charter, status,
  decisions, sessions, requirements, planning items). Read it live via the REST
  API / MCP, not from committed files.

---

## Feature guides

User‑facing how‑tos for shipped capabilities.

- **[Three-Way Reconciliation — User Guide](three-way-reconciliation-user-guide.md)** —
  compare the canonical design against two live instances and reconcile the
  differences (desktop **Governance → Reconcile**). Plan/design:
  [three-way-reconciliation-release-plan.md](three-way-reconciliation-release-plan.md).

## Foundational PRDs & plans

- [Storage System PRD](storage-system-PRD-v0.1.md) · [implementation plan](storage-system-implementation-plan.md)
- [User Interface PRD](ui-PRD-v0.6.md) (latest; v0.1–v0.5 retained for history) · UI implementation plans `ui-v0.*-implementation-plan.md`
- [Governance Entity PRD](governance-entity-PRD-v0.1.md) · [implementation plan](governance-entity-implementation-plan.md)
- [Catalog Ingestion PRD](catalog-ingestion-PRD-v0.1.md) · [implementation plan](catalog-ingestion-implementation-plan.md)

## Architecture (current model)

- [Governance & Delivery Redesign — Target Data Model](governance-redesign-target-model.md) — the current Project / Workstream / Work Task model (supersedes earlier descriptions)
- [Production Multi-Tenant API — Architecture](production-multitenant-api-architecture.md) — the PRJ‑019 program
  - [PI-123 — Unified Multi-Engagement DB](pi-123-unified-db-architecture.md)
  - [PI-α — Postgres Foundation](pi-alpha-postgres-foundation-architecture.md) · [migration runbook](pi-alpha-postgres-migration-runbook.md)
  - [PI-β — De-file + kill snapshots](pi-beta-defile-architecture.md)
  - [PI-γ — Identity, Auth & RBAC](pi-gamma-rbac-architecture.md)
- [Engine-Neutral CRM Design Model & Pluggable Adapters](engine-neutral-design-model-and-adapters.md)
- [Multi-Engagement Architecture (v0.5)](multi-engagement-architecture.md)
- [Migration drift safety + bootstrap-db](pi-308-migration-drift-safety-approach.md)

## Multi-instance audit, publish & reconcile

- [PRJ-027 — Multi-Instance CRM Connection, Audit & Inventory](prj-027-multi-instance-audit-inventory-architecture.md)
- [Source Instance Mapping — Design Model](source-mapping-design.md)
- [Three-Way Reconciliation — Release Plan](three-way-reconciliation-release-plan.md) (engine, capture-back, transaction log, rollback)

## Requirements provenance & review

- [Process Anchor](requirements-provenance-and-review-anchor.md) · [Build Translation](requirements-provenance-build-translation.md) · [Phase 7 — Prove on itself](requirements-provenance-phase7-prove-on-itself.md)
- [`approve_requirement` process contract](approve-requirement-process-contract.md)

## Methodology & schema specs

- [Methodology Entity Schema — Spec Guide](methodology-entity-schema-spec-guide.md)
- [Governance Entity Schema — Spec Guide](governance-entity-schema-spec-guide.md)
- [Code Change Lifecycle — Methodology](methodology-code-change-lifecycle.md)
- Per-entity schema specs: `governance-schema-specs/`, `methodology-schema-specs/`

## Notable execution plans / releases

- [Outstanding-Work Release Plan](release-plan-outstanding-work.md) (release-scoped project model)
- [PI-073 — Session/Conversation redesign](pi-073-execution-plan.md)
- [PI-112 — Governance & Delivery Model Migration](pi-112-execution-plan.md)

## Subdirectories

- `governance-schema-specs/`, `methodology-schema-specs/` — per-entity schema specifications
- `close-out-payloads/`, `apply-prompts/`, `deposit-event-logs/` — the governance close-out trail (sandbox path + git-tracked deposit logs)
- `prompts/` — Claude Code apply-close-out prompts
- `pi-cleanup/`, `styling-screenshots/` — supporting artifacts

## Historical records

Many files here are **point-in-time session records**, not living specs:
`*-kickoff.md` (per-session kickoff prompts), `pi-NNN-*` (per-PI design,
execution, verification, and runbook notes), and `schema-design-kickoff-*.md`
(per-entity schema-design prompts). They document how a piece of work was framed
and executed; for current state, defer to `CLAUDE.md` and the live V2 DB.
