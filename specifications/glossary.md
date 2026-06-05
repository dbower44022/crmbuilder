# CRMBuilder Glossary — retired (now in V2)

| Field | Value |
|-------|-------|
| Status | **Retired.** Term definitions now live in V2 as `term` records. |
| Retired | 06-04-26 by PI-061 |
| Canonical source | The V2 `term` entity — the **Glossary** panel in the V2 desktop app (Methodology group), or the `/terms` REST API. |

---

This file is no longer the source of truth for term definitions. PI-061 brought the
glossary into V2 as a first-class entity (`term`, identifiers `TERM-NNN`), so definitions
are queryable records with a desktop editing surface, shared across engagements by default.

**To read or edit terms:**

- **Desktop app:** open the **Glossary** entry under the Methodology group in the V2
  desktop app.
- **API:** `GET /terms` (list), `GET /terms/{TERM-NNN}` (one term), `POST`/`PATCH`/`DELETE`
  for writes, under the `{data, meta, errors}` envelope. Send the `X-Engagement` header.

The five terms this file previously held — Engagement (`TERM-001`), Skill (`TERM-002`),
Pattern (`TERM-003`), Inventory (`TERM-004`), Client (`TERM-005`) — were migrated into V2
verbatim, alongside the agent-system terms (Area, Agent, Agent Skill, Rule, Registry,
Contract, Engagement Admin, Pass, Finding, and the role names Project Manager, PI Lead,
Architect, Developer, Tester).

Schema and design: `PRDs/product/crmbuilder-v2/methodology-schema-specs/term.md`. The
governing decisions are DEC-403 (term data structure) and DEC-404 (build choices).

> **Note on "Skill" vs "Agent Skill" (DEC-389):** `Skill` (`TERM-002`) keeps its
> methodology meaning — a domain-knowledge file for the requirements process. The agent
> concept is a separate term, `Agent Skill` (`TERM-008`).
