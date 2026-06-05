# Entity Schema Spec — `term`

**Last Updated:** 06-04-26
**Status:** v1.0 — produced by PI-061 Design step (WSK-036 / WTK-053, conversation CNV-063, session SES-161)
**Governing decisions:** DEC-403 (term data structure), DEC-404 (build choices), DEC-390 (the glossary is a V2 entity), DEC-298 (glossary.md is the current canonical term store), DEC-389 ("Skill" keeps its methodology meaning)
**Migrates from:** `specifications/glossary.md`

---

## 1. Purpose

A `term` is one definition in the CRMBuilder glossary: a word or phrase used across the
methodology, governance, and process documentation, with a stable identifier so documents
can cite it. Before this entity exists, term definitions live only in the flat markdown
file `specifications/glossary.md`. PI-061 brings them into V2 as records, gives each a
desktop editing surface, and retires the markdown file to a pointer.

Definitions live **only** in this entity. Other documents reference a term by its
identifier (`TERM-NNN`) rather than restating the definition.

## 2. Scope model — shared by default, extensible per engagement

A term is **shared across all engagements by default**. This is done with a nullable
`engagement_id` column, the same system-or-engagement scope mechanism the Agent Profile
Registry already uses (PI-122):

- `engagement_id` **empty (NULL)** → a **system** term, visible to every engagement.
- `engagement_id` **set** → an **engagement overlay**, a term added by and visible only to
  that one engagement.

The table is a plain row (not engagement-scoped-by-construction): reads merge the system
terms with the asking engagement's own additions. The public `scope` field on every term
record reflects this — `"system"` when `engagement_id` is empty, otherwise the engagement
identifier. New terms default to system scope.

## 3. Fields

| Column | Type | Null? | Notes |
|--------|------|-------|-------|
| `identifier` | text PK | no | `TERM-NNN`, three digits, server-assigned when omitted |
| `engagement_id` | text FK → engagements | yes | empty = system term; set = engagement overlay |
| `name` | varchar(255) | no | the term itself, e.g. "Engagement" |
| `definition` | text | no | one or two plain-English sentences |
| `usage_scope` | text | yes | where the term applies (which documents, which contexts) |
| `examples` | text | yes | one or two concrete uses, free-form |
| `distinguishing_notes` | text | yes | what the term is NOT to be confused with |
| `related_terms` | text | yes | names of related terms (plain text, mirrors the markdown) |
| `version` | integer | no | starts at 1 |
| `status` | varchar(16) | no | `active`, `draft`, or `retired`; defaults to `active` |
| `created_at` | timestamp | no | set on insert |
| `updated_at` | timestamp | no | set on insert, refreshed on edit |

**Naming note (DEC-404):** the glossary's "Scope" field is stored as `usage_scope` so it
does not collide with the system-or-engagement `scope` discriminator.

**`related_terms` (DEC-404):** stored as plain text (the names of related terms), mirroring
how `glossary.md` lists them, rather than as formal reference edges between term records.

## 4. Identifier and registration

- Identifier format `^TERM-\d{3}$`, enforced by a CHECK constraint and auto-assigned by the
  standard SAVEPOINT-retry helper (`next_prefixed_identifier`).
- `term` is added to `ENTITY_TYPES`, which rebuilds the `change_log` and `refs` entity-type
  CHECK constraints on fresh/test databases (via `create_all`). The **live unified database
  needs those two CHECK constraints rebuilt directly** (the known live-DB gotcha), because
  every term create writes a `change_log` row of `entity_type = "term"`.
- No new relationship-kind vocabulary is required: `related_terms` is a field, not edges.

## 5. API surface — `/terms`

Standard CRUD under the `{data, meta, errors}` envelope:

- `GET /terms` — list, with optional `status` and `scope` filters.
- `GET /terms/next-identifier` — next available `TERM-NNN`.
- `GET /terms/{identifier}` — one term.
- `POST /terms` — create (identifier optional; `scope` optional, defaults to system).
- `PATCH /terms/{identifier}` — update fields and/or scope.
- `DELETE /terms/{identifier}` — delete.

The MCP tool surface for terms is **deferred** to a later task (DEC-404).

## 6. Desktop panel — "Glossary"

A read/edit panel under the sidebar listing terms (master pane) with a detail/edit form.
Mirrors the existing governance/methodology panels (list + detail + create/edit dialog).

## 7. Migration and seed

1. Import the five existing terms from `glossary.md`: TERM-001 Engagement, TERM-002 Skill,
   TERM-003 Pattern, TERM-004 Inventory, TERM-005 Client. "Skill" keeps its methodology
   meaning (DEC-389).
2. Seed the agent-system terms: Area, Agent, Agent Skill, Rule, Registry, Contract,
   Engagement Admin, Pass, Finding, and the role names (Project Manager, PI Lead, Architect,
   Developer, Tester). "Agent Skill" is the agent concept, distinct from "Skill".
3. Replace the body of `specifications/glossary.md` with a short pointer to the V2 glossary
   as the canonical source (DEC-404).

## 8. Acceptance

- A term can be created, read, updated, listed, and deleted through `/terms`.
- A system term (no engagement) is visible to every engagement; an engagement overlay is
  visible only to that engagement.
- Creating a term writes a `change_log` row without a CHECK violation on the live database.
- The five existing terms and the agent-system terms exist as records.
- `glossary.md` points to the V2 glossary.
