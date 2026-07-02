# REL-039 / PI-356 — DB Structures for Instructions, Preferences, Lessons, Reference Pointers

**Requirement:** REQ-415 — *Design database structures for instructions, preferences, lessons, and reference pointers.*
**Acceptance:** a design names the target structure for each class with its reuse-or-new decision justified, and any new structure has a schema and a migration plan.
**Status:** DRAFT for Doug's review (contains open decisions §7). Produced 2026-07-02 (Claude Code, ENG-001).
**Input:** the PI-355 classification work-list — `PRDs/product/crmbuilder-v2/rel-039-pi-355-knowledge-inventory-classification.md`.
**Downstream:** PI-357 (migrate) → PI-358 (bootstrap read) → PI-359 (reduce files) → PI-360 (SSoT rule). This design is produced before any migration code, per REQ-415.

---

## 1. The four knowledge classes and the decision at a glance

| Class | Source in files | Volume (PI-355) | Decision | Target structure |
|---|---|---|---|---|
| **Instructions** (binding governance rules) | `CLAUDE.md` Working-conventions + `feedback_*` binding rules | ~9 rule groups + 9 memory files | **REUSE** | `governance_rule` (`GVR-`) |
| **Preferences** (interaction / working style) | `feedback_*` style items | 7 files | **NEW** | `preference` (`PRF-`) |
| **Lessons** (operational gotchas / how-tos) | hybrid `project_*` splits + `reference_*` gotchas | ~40 items | **NEW** | `lesson` (`LSN-`) |
| **Reference pointers** (servers, dashboards, docs, tickets, repo paths, credential locations) | `reference_*` + `MIGRATE-PTR` notes | ~8 items | **NEW** | `reference_pointer` (`RFP-`) |

The two reuse-or-new axes that drove every call: **(a)** does an existing entity already carry this class's semantics without distortion, and **(b)** does reuse pollute the existing entity's own consumers (the enforcement gate, the agent-contract resolver)?

All four structures share the **system|engagement scope pattern** already proven by `governance_rule`, `learning`, and the registry entities: a **nullable `engagement_id`** where `NULL` = a system-wide row and a set value = an engagement overlay, on a plain `Base` model (not `EngagementScopedMixin`) so system rows stay globally visible and the read path merges `WHERE engagement_id IS NULL OR engagement_id = :active`.

---

## 2. Instructions → REUSE `governance_rule` (`GVR-`)

**Decision: reuse, no schema change.**

The binding rules in `CLAUDE.md`'s *Working conventions* and the binding `feedback_*` items (Governed-By trailer, terminology governance, requirement-first, real-time governance recording, project-complete terminality, agent naming, commit-with-pathspec, commit-under-parallel-orchestrators, approval-request structure) are **governance rules**, and `governance_rules` already models exactly this:

```
governance_rules(identifier GVR-, engagement_id?, rule_type?, enforcement,
                 severity?, body, predicate?, version, status, created/updated)
```

- `enforcement ∈ {advisory, enforced, enforced_with_override}` (existing `RULE_ENFORCEMENT_MODES`) — matches the advisory/binding split of these rules.
- `body` holds the rule text; `predicate` holds a machine-checkable form for the enforced ones (e.g. the Governed-By gate already has code behind it).
- Most of these already conceptually live under **TOP-013** ("Governance Recording Method"). Migration (PI-357) creates the missing ones as `GVR-` rows and links each to its TOP-013 child topic and source decision via the existing `references` edges.

**Justification:** exact semantic match; `governance_rule` is already the enforcement home (the Governed-By gate reads it), and the TOP-013 corpus is already the recording target per the "specs live in the DB" principle. Adding a parallel structure would fork the rule corpus.

**Considered and rejected:** the `rule` entity (`RUL-`) — that is a methodology rule bound to a Process/Domain, not a project-operating rule. Wrong domain.

---

## 3. Preferences → NEW `preference` (`PRF-`)

**Decision: new entity.** 7 items: execute-autonomously/no-confirmation, no-grayed-buttons, button-styling, one-issue-at-a-time, one-step-at-a-time, full-file-paths, operator-control-over-multi-step-ops.

**Considered and rejected — overload `governance_rule` with `rule_type='preference'`:** these are *advisory interaction style*, not governance. Folding them into `governance_rules` would (a) inject style rows into the TOP-013 governance corpus and the Governed-By enforcement gate's read set, and (b) misuse `enforcement`/`severity`/`predicate`, which have no meaning for "use warm-orange secondary buttons." A preference is never *enforced* and never has a predicate.

### Schema

```sql
CREATE TABLE preferences (
    identifier      VARCHAR(32) PRIMARY KEY,          -- PRF-NNN
    engagement_id   VARCHAR    NULL REFERENCES engagements(engagement_identifier) ON DELETE CASCADE,
    category        VARCHAR(32) NOT NULL,             -- 'interaction' | 'ui' | 'workflow'
    title           VARCHAR(255) NOT NULL,
    body            TEXT        NOT NULL,             -- the preference statement
    applies_to      VARCHAR(32) NOT NULL DEFAULT 'all', -- 'all' | 'claude_code' | 'sandbox' | 'ui'
    status          VARCHAR(16) NOT NULL DEFAULT 'active',  -- 'active' | 'retired'
    created_at      TIMESTAMPTZ NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL,
    CHECK (identifier ~ '^PRF-[0-9]{3,}$'),           -- dialect-rendered, per _IdentifierFormatCheck
    CHECK (category IN ('interaction','ui','workflow')),
    CHECK (applies_to IN ('all','claude_code','sandbox','ui')),
    CHECK (status IN ('active','retired'))
);
```

Plain `Base` (nullable-`engagement_id` scope), mirroring `governance_rules`. No `predicate`/`enforcement`/`severity` — preferences are advisory by construction. `applies_to` lets a preference be surface-scoped (a UI preference need not load into a headless agent).

---

## 4. Lessons → NEW `lesson` (`LSN-`)

**Decision: new entity.** ~40 operational gotchas/how-tos split from the hybrid `project_*` memories (e.g. add-entity-type→rebuild-change_log-CHECK, never-hand-patch-live-schema, WAL-concurrency-fix, PG-sequences-setval, Qt gc/deleteLater hazards, close-out wire-format, check-target-before-bulk-write, grab-the-lane monitor, layout-API how-to, "raw audit YAML not directly deployable", list-endpoints-ignore-offset).

**Considered and rejected — reuse `learning` (`LRN-`):** superficially close ("accumulated operational knowledge"), but `learnings` is hard-coupled to the **agent (area × tier) contract model**: `area` and `tier` are `NOT NULL`, and the registry resolver *attaches learnings to a spawned agent by area+tier match* with an evidence/confidence promotion lifecycle. Our lessons are for **humans and Claude-Code sessions generally**, not a specific agent cell. Forcing them in would require fabricating `area`/`tier` values and would **pollute agent contract resolution** (every agent in that area would inherit unrelated dev gotchas). The clean relationship is the reverse: a lesson may later be *promoted into* a `learning` for a specific agent area — modeled as an optional edge, not a merge.

### Schema

```sql
CREATE TABLE lessons (
    identifier      VARCHAR(32) PRIMARY KEY,          -- LSN-NNN
    engagement_id   VARCHAR    NULL REFERENCES engagements(engagement_identifier) ON DELETE CASCADE,
    category        VARCHAR(32) NOT NULL,             -- 'engineering' | 'operations' | 'process' | 'deployment'
    title           VARCHAR(255) NOT NULL,
    body            TEXT        NOT NULL,             -- the gotcha / how-to
    signal          VARCHAR(16) NOT NULL DEFAULT 'guidance', -- 'guidance' | 'hazard' (don't-do-X) | 'howto'
    status          VARCHAR(16) NOT NULL DEFAULT 'active',   -- 'active' | 'superseded' | 'retired'
    created_at      TIMESTAMPTZ NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL,
    CHECK (identifier ~ '^LSN-[0-9]{3,}$'),
    CHECK (category IN ('engineering','operations','process','deployment')),
    CHECK (signal IN ('guidance','hazard','howto')),
    CHECK (status IN ('active','superseded','retired'))
);
```

**Provenance edges (new relationship kinds in the `refs` vocab):**
- `lesson_derived_from` — `(lesson → decision | planning_item | commit)`: the DB record the hybrid memory was welded to. This is what makes the PI-357 hybrid split lossless: DELETE-DUP the build-status half (DB already owns the DEC/PI/CM), keep the lesson half, and record *where it came from*.
- `lesson_supersedes` — `(lesson → lesson)`: a corrected/replaced lesson.
- `lesson_promoted_to_learning` — `(lesson → learning)`: the optional bridge to the agent-contract world (future; the `learning` target is admitted now but need not be exercised in this release).

---

## 5. Reference pointers → NEW `reference_pointer` (`RFP-`)

**Decision: new entity.** ~8 external pointers: CBM prod/test servers, CBM BookStack + its API/token location, the CBM repo name↔local-path mapping, the cbm-client-intake project pointer, the agent-PRD doc-location pointer, ANTHROPIC_API_KEY-in-env location.

**Considered and rejected — reuse `reference_book` (`RB-`):** `reference_book` is a **long-lived versioned document** (title/description/kind + a `reference_book_versions` child table). A pointer is a single addressable target with connection metadata and *no version history*; the versioning machinery is dead weight and the semantics ("a document you read" vs "a place/thing you connect to") differ.

**Considered and noted — REL-016's Reference Entry (PI-062, in flight):** that structure is for **client-domain knowledge** (Domain Knowledge / Organization Structure / Inventory Items) captured for discovery — different content and purpose from ops/infra pointers. Keep separate; if REL-016 lands a generic `reference` entity first, PI-357 should re-evaluate folding pointers into it (flagged as an open dependency, §7).

### Schema

```sql
CREATE TABLE reference_pointers (
    identifier      VARCHAR(32) PRIMARY KEY,          -- RFP-NNN
    engagement_id   VARCHAR    NULL REFERENCES engagements(engagement_identifier) ON DELETE CASCADE,
    kind            VARCHAR(32) NOT NULL,             -- 'server' | 'dashboard' | 'doc' | 'ticket' | 'repo' | 'credential_location' | 'service'
    title           VARCHAR(255) NOT NULL,
    target          TEXT        NOT NULL,             -- URL / host / path / repo slug
    access_note     TEXT        NULL,                 -- how to reach it (SSH user+key path, auth scheme) — NEVER the secret itself
    body            TEXT        NULL,                 -- free-form detail
    status          VARCHAR(16) NOT NULL DEFAULT 'active',  -- 'active' | 'retired'
    created_at      TIMESTAMPTZ NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL,
    CHECK (identifier ~ '^RFP-[0-9]{3,}$'),
    CHECK (kind IN ('server','dashboard','doc','ticket','repo','credential_location','service')),
    CHECK (status IN ('active','retired'))
);
```

**Secret-safety invariant (binding on the migration):** `access_note` records *where* a credential lives (keyring entry, `crmbuilder.env` var name, `~/.ssh/` key path) and the auth scheme — **never a secret value**. This mirrors the existing keyring-ref discipline and keeps the shared multi-tenant DB free of plaintext secrets.

---

## 6. Cross-cutting: scope, migration, and the bootstrap contract

### 6.1 Scope resolution
All three new tables reuse the `governance_rule`/`learning` pattern: plain `Base`, nullable `engagement_id`, read-path merge `WHERE engagement_id IS NULL OR engagement_id = :active`. System rows (NULL) are the CRMBuilder-wide defaults; CBM-specific pointers/lessons are `engagement_id = 'ENG-002'` overlays (pending §7).

### 6.2 Migration plan (PI-357 executes; this design specifies it)
One migration on **each** Alembic head (the dual-head rule — SQLite batch chain `migrations/` and the Postgres chain `migrations/pg/`; never replay the SQLite chain on PG):

1. `CREATE TABLE preferences | lessons | reference_pointers` with the dialect-rendered CHECKs (`_IdentifierFormatCheck` etc. — byte-identical SQLite, `~`-regex on PG).
2. **Rebuild the `change_log.entity_type` CHECK and the `refs.source_type`/`target_type` CHECKs** to admit `preference`, `lesson`, `reference_pointer` — *this is the change_log-CHECK gotcha that create_all-based tests miss and that 500s live if skipped* (the migration must include it explicitly).
3. **Rebuild the `refs.relationship_kind` CHECK** to admit `lesson_derived_from`, `lesson_supersedes`, `lesson_promoted_to_learning`.
4. Add the three entity types to `vocab.ENTITY_TYPES`, the three prefixes to the identifier registry, and the three relationship kinds to `REFERENCE_RELATIONSHIPS` + `_kinds_for_pair` (source/target constraints).

Prefixes `PRF` / `LSN` / `RFP` are unused today (verified against the live prefix set; `LRN`/`REF`/`RFE`/`RB` are taken and distinct).

### 6.3 What the structures owe PI-358 (the bootstrap read)
The cold-start problem is real: the cloud DB is **auth-gated and may be unreachable at session start**. This design does not build the bootstrap, but it constrains the structures so PI-358 *can*:
- Every class has a stable **`status='active'`** filter and a **`scope` merge**, so "the active knowledge for ENG-001" is one cheap indexed query per table (candidate single endpoint `GET /knowledge/bootstrap`).
- The minimal unavoidable **STAYS-BOOT residual** (per PI-355 finding 3) is: *how to reach the DB* (the API base URL + auth hint) plus *the instruction to read TOP-013 + preferences + pointers on connect*, with graceful degradation when the read fails. That residual is itself a `reference_pointer` (kind `service`) once migrated, but a bootstrapped copy must stay in the file because you can't read the pointer table before you can reach it.

---

## 7. Open decisions for Doug (not decided here)

1. **CBM-scoped rows — ENG-001 or ENG-002?** The 7 `*_cbm_*` pointers/memories are CBM-client knowledge. Home them as `engagement_id='ENG-002'` overlays (my recommendation — they're CBM's), or keep on ENG-001 as the dogfood operator's working notes?
2. **Global `~/.claude/CLAUDE.md`.** The one cross-project rule ("respect each repo's process") has no crmbuilder-DB home. Leave it as a global bootstrap file (out of REL-039 scope), or stand up a future global store? Recommend: out of scope, stays a file.
3. **REL-016 dependency.** If REL-016's generic Reference Entry entity lands before PI-357 runs, re-evaluate whether pointers fold into it. Recommend: proceed independently; `reference_pointer` (infra) and Reference Entry (client-domain) are genuinely different classes.
4. **Preference enforceability.** Confirm preferences stay purely advisory (no enforcement column). Recommend: yes — the moment a "preference" needs enforcing it should be a `governance_rule`.

---

## 8. Acceptance check (REQ-415)

- ✅ Every class named with its target structure and a justified reuse-or-new decision (§2–§5).
- ✅ Each **new** structure (`preference`, `lesson`, `reference_pointer`) has a schema (§3–§5) and a migration plan (§6.2).
- ✅ Produced before any migration code.

Resolution of PI-356 is held pending Doug's sign-off on §7.
