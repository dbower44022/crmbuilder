# REL-016 / PI-062 — Cross-Engagement Reference Store Architecture

**Requirement:** REQ-397 — *Cross-engagement reference store architecture.*
**Acceptance:** a documented architecture exists for storing and resolving shared reference content across engagements, with engagement-scoped data still isolated.
**Produced:** 2026-07-01 (Claude Code, ENG-001). This document is the architecture gate for REL-016; PI-063–067 build against it.

**Decisions recorded here (with Doug, 2026-07-01):**
1. **Reuse the existing cross-engagement store** — do not build a new one.
2. **Naming** of the three content kinds: **Domain Knowledge**, **Organization Structure**, **Inventory Items**.
3. **One entity distinguished by a `kind` field** (combined mechanism, distinct kinds) — not three separate tables.

**Naming LOCKED (DEC-887, 2026-07-01):** umbrella entity **Reference Entry** (table `reference_entries`, identifier prefix **`RFE-NNN`**); `kind` tokens **`domain_knowledge`** / **`organization_structure`** / **`inventory_items`** (display: Domain Knowledge / Organization Structure / Inventory Items). PI-063 is unblocked. See §7.

---

## 1. The problem, and why the store is already built

REQ-397 asks for a place to hold knowledge that is the same across **every** engagement (glossary terms, domain knowledge, organization structures, inventories) while keeping each engagement's private data isolated.

That storage mechanism **already exists**, delivered by the Agent Profile Registry (PI-122) on the unified multi-engagement database (PI-123). The pattern:

- A record carries a **nullable `engagement_id`**. `NULL` = a **system** row shared by all engagements; a set value = a row **private** to that engagement.
- Reads apply the **scope merge**: a row is in scope iff `engagement_id IS NULL` **OR** `engagement_id = <active engagement>`. System rows are the inheritable baseline; an engagement row can add to (or, by convention, override) them. This is exactly the merge `registry_resolver.py` performs today and `agent_profiles.search_agents(...)` applies with its `engagement_id` parameter.

This pattern is **live on six record types** — `agent_profile`, `skill`, `governance_rule`, `learning`, and (the glossary) **`term`** — with the desktop registry UI (PI-330) already authoring the system-vs-engagement scope on each.

**Consequence:** PI-062 does **not** design a new store. It **adopts the existing `system | engagement` pattern** for REL-016's new content. Building a second cross-engagement mechanism would duplicate solved, proven infrastructure.

### Already-built pieces of REL-016

- **Cross-engagement store (REQ-397):** the `system | engagement` pattern above. **Done — reuse.**
- **Glossary (named in PI-062 as TERM-NNN):** the `terms` entity exists with this exact scope model (`usage_scope` deliberately named to avoid colliding with the scope discriminator, DEC-404); **29 system terms are live in ENG-001.** The glossary holds CRMBuilder's own framework vocabulary. **Done — no new work in REL-016; it is the worked precedent.**

---

## 2. Naming and the `skill` collision

REL-016's REQ-398 called its content a "skills library." The word **`skill` is already taken** — the `skills` table (SKL-NNN) holds **ADO agent capabilities** (`kind` = instruction/tool, `io_contract`, `backing_callable`): operating tools like "read prior-phase outputs" or "claim a Work Task." The glossary itself already defines `TERM-008 "Agent Skill"` as an agent capability. REL-016's content is a different concept: **knowledge about a client's industry, loaded during discovery interviews.**

To avoid the collision, the three REL-016 content kinds are named (Doug, 2026-07-01):

| REL-016 concept (old name) | Locked name | What it holds |
|---|---|---|
| domain-knowledge "skill" (REQ-398) | **Domain Knowledge** | Prose knowledge about how an organization type operates (e.g. how nonprofit mentoring works). |
| "pattern" (REQ-399) | **Organization Structure** | The typical structural shape of an org type — its typical entities and their relationships. |
| "inventory" (REQ-400) | **Inventory Items** | A discovery checklist — the typical entities, personas, and processes of an org type. |

These are distinct from **Agent Skill** (an agent's operating capability) and from **Glossary Term** (a framework definition).

---

## 3. Data model — one entity, distinguished by `kind`

REQ-399 asks whether the three are "cleanly distinguished or deliberately combined." The answer is **both**: **distinct by `kind`, combined in mechanism** — one record family mirroring the existing `skill` entity's "one table + `kind` discriminator + JSON payload" shape.

### 3.1 The `Reference Entry` entity *(name LOCKED — DEC-887, §7)*

Table `reference_entries`, identifier prefix **`RFE-NNN`**, engagement-scoped by the shared pattern:

| Column | Type | Notes |
|---|---|---|
| `identifier` | str PK | `RFE-NNN`, server-assignable |
| `engagement_id` | str **NULL** FK → engagements | **The scope discriminator.** NULL = system (shared by all engagements); set = private to that engagement. Reused pattern. |
| `name` | str, required | e.g. "Nonprofit Mentoring Organization" |
| `kind` | str, required | CHECK ∈ `{domain_knowledge, organization_structure, inventory_items}` (display names per the table above) |
| `applies_to` | str, nullable | the org-type/domain this describes, e.g. "nonprofit mentoring" — the matchable subject |
| `trigger_keywords` | JSON, nullable | list of terms the loader (§4) matches a client's defining statements against |
| `content` | JSON, required | the **per-kind** payload (§3.2) |
| `status` | str | reuse `REGISTRY_STATUSES` (active/…), default active |
| `version` | int | reuse the registry versioning convention |
| `created_at` / `updated_at` | ts | standard |

The shared envelope (`name`, `kind`, `applies_to`, `trigger_keywords`, scope, status) is identical across kinds; only `content` varies. This is the same design as `skill` (`kind` + `io_contract` JSON).

### 3.2 Per-kind `content` payloads

The DB stores `content` as JSON; the **access layer validates its shape per `kind`** (exactly as it validates `skill.io_contract` today — the DB does not enforce inner shape):

- **domain_knowledge** → `{ "body": "<prose / markdown>" }`
- **organization_structure** → `{ "typical_entities": [...], "typical_relationships": [...] }`
- **inventory_items** → `{ "entities": [...], "personas": [...], "processes": [...] }`

**Why JSON, not relational columns / links:** these are reference **templates and knowledge**, not live records. An inventory's "typical personas: Donor, Volunteer, Board Member" is descriptive text used as a discovery starting point, **not** links to real `PER-NNN` rows. If a future requirement wanted an inventory to reference *actual* engagement records, that would argue for relational structure — but REL-016 does not describe that, and adding it later is non-breaking (a new kind or a linked child table).

### 3.3 What reusing the store buys, mechanically

- **Scope:** `Reference Entry` gets the `NULL = system` isolation for free; a system entry ("Nonprofit Mentoring") is visible to every engagement, an engagement can add or override its own.
- **Resolution:** the same scope-merge predicate (`engagement_id IS NULL OR = active`) applies; no new resolver.
- **Uniformity:** one migration (create the table + rebuild the `refs`/`change_log` CHECKs for the new entity type, per the standard add-entity-type pattern), one repository, one router.

---

## 4. Contextual loading (REQ-401 / PI-066)

REQ-401 wants the AI to recognize a client's defining statements and auto-load the matching content, with **one mechanism for all three kinds**. The combined entity makes this a single index:

- A `search_reference_entries(session, *, statements|keywords, kind=None, engagement_id)` primitive, modeled directly on `agent_profiles.search_agents` — a **deterministic pre-filter** that:
  - matches the client's defining statements/keywords against each entry's `trigger_keywords` + `applies_to` + `name`, ranked by overlap count (the `search_agents` ordering-by-overlap pattern);
  - applies the `system ∪ engagement` scope merge via the `engagement_id` parameter;
  - optionally narrows by `kind` (load only Domain Knowledge, only Inventory Items, etc.).
- Because all three kinds share one table and one keyword index, "the same mechanism loads patterns and inventories" (REQ-401's explicit ask) is satisfied by construction — no per-kind loader.
- The recognition step (turning a client's free-text defining statements into match keywords) is the LLM-facing surface; the deterministic keyword pre-filter is the safety backstop beneath it, mirroring the `search_agents` split (LLM picks, deterministic filter bounds).

---

## 5. Authoring tooling (REQ-402 / PI-067)

REQ-402 wants a desktop surface to author/manage the content. Reuse the registry UI pattern (PI-330):

- A `ReferenceEntriesPanel` subclassing **`RegistryCrudPanel`** (`ui/panels/_registry_panel_base.py`) — the same base the Skills/Rules/Learnings panels use.
- Every row shows its **scope** (system vs engagement); the create/edit dialog builds the scope combo from the live engagement list (author a system default or an engagement overlay) — identical to the existing registry panels.
- A **`kind` selector** switches the content editor: a markdown/prose editor for Domain Knowledge, structured list editors for Organization Structure and Inventory Items. `trigger_keywords` edits as a keyword list.
- Glossary Terms already have their surface (the `terms` panel); Reference Entries add one new panel, not four.

---

## 6. How the pieces relate (the disambiguation, for the glossary)

Three cross-engagement content families now coexist, cleanly separated:

| Family | Entity | Holds | Consumer |
|---|---|---|---|
| **Glossary Term** | `term` (built) | CRMBuilder's own framework vocabulary | humans/AI reading definitions |
| **Agent Skill** | `skill` (built) | an ADO agent's operating capability | the delivery pipeline / agents |
| **Reference Entry** | `reference_entries` (new) | client-industry knowledge (Domain Knowledge / Organization Structure / Inventory Items) | the AI during discovery interviews |

All three use the same `system | engagement` store; each is a distinct entity with a clear consumer. New glossary terms should be added for **Domain Knowledge**, **Organization Structure**, **Inventory Items**, and **Reference Entry** once the umbrella name is locked (§7).

---

## 7. Naming — LOCKED (DEC-887, 2026-07-01)

Doug locked the naming so PI-063 can build:

1. **Umbrella entity: `Reference Entry`** — table `reference_entries`, identifier prefix **`RFE-NNN`**.
2. **`kind` tokens:** `domain_knowledge` / `organization_structure` / `inventory_items` (display: Domain Knowledge / Organization Structure / Inventory Items).

**PI-063 is unblocked** — everything (reuse the store, one-entity-by-kind, keyword loader, RegistryCrudPanel UI, names) is decided.

### 7.1 Glossary reconciliation (follow-up to the lock)

The glossary already carries these three concepts under **old names**, each noting the distinction was "still being refined":

| Glossary term (old) | → Locked name | Action |
|---|---|---|
| `TERM-002 "Skill"` (methodology domain-knowledge) | **Domain Knowledge** | rename + resolve the "still being refined" note (now a `kind` of Reference Entry) |
| `TERM-003 "Pattern"` | **Organization Structure** | rename + resolve |
| `TERM-004 "Inventory"` | **Inventory Items** | rename + resolve |
| `TERM-008 "Agent Skill"` | *(unchanged)* | update its `related_terms` to point at Domain Knowledge |
| *(new)* | **Reference Entry** | add the umbrella term |

This reconciliation aligns the vocabulary SSoT with the locked names; it is content-only (no code) and can land alongside PI-063.

---

## 8. Decomposition — what each downstream PI builds against this

| PI / Req | Builds |
|---|---|
| **PI-063 / REQ-398** Domain Knowledge | The `reference_entries` entity + migration (table + CHECK rebuilds) + repository + `/reference-entries` router; seed initial **Domain Knowledge** entries (nonprofit mentoring, charitable foundation, social marketing). *The entity itself lands here (first of the content PIs).* |
| **PI-064 / REQ-399** Organization Structure | The `organization_structure` kind's `content` validation + authored entries. (No new table — reuses PI-063's entity.) |
| **PI-065 / REQ-400** Inventory Items | The `inventory_items` kind's `content` validation + authored entries. (No new table.) |
| **PI-066 / REQ-401** Loader | `search_reference_entries` (keyword pre-filter, `search_agents` pattern) + the recognize-defining-statements → load flow. |
| **PI-067 / REQ-402** Authoring UI | `ReferenceEntriesPanel` (RegistryCrudPanel subclass) with kind-specific content editors + scope authoring. |

A consequence of the combined design: **PI-063 builds the entity once**; PI-064/065 add only per-kind content + validation, not new tables/panels — less surface than three separate libraries would have required.
