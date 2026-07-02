# Kickoff — Finish REL-039 (Database as Single Source of Truth)

**Paste this into a fresh Claude Code session rooted at `~/Dropbox/Projects/crmbuilder`.**

You are finishing **REL-039 — "Database as Single Source of Truth"** (project **PRJ-076**): move durable knowledge out of files into the V2 database, make the DB authoritative for the classes it owns, and shrink `CLAUDE.md` + the file-based memory to a minimal bootstrap.

Two of six PIs are already done — **PI-355** (inventory & classification) and **PI-356** (the DB-structures design). Your job is the remaining four, **in dependency order**:

```
PI-357 (migrate content in)  →  PI-358 (bootstrap + read protocol)
                             →  PI-359 (reduce files)  →  PI-360 (SSoT rule + enforcement)
```

When all four are Resolved, walk REL-039 to a terminal state.

---

## 0. Read these first (in order)

1. **`CLAUDE.md`** (auto-loads) — especially "Governance is a precondition", the Branch-work protocol (Model A), session lifecycle, and the v2 governance-recording rules (TOP-013).
2. **The design you are implementing:** `PRDs/product/crmbuilder-v2/rel-039-pi-356-knowledge-structures-design.md`. This is authoritative — PI-357 implements its schema and migration plan literally. Do not re-litigate the reuse-or-new decisions; they were approved by Doug (DEC-891) and PI-356 is Resolved.
3. **The migration work-list:** `PRDs/product/crmbuilder-v2/rel-039-pi-355-knowledge-inventory-classification.md` — the per-item destination table (what to migrate, what to delete, what stays). This is your checklist for PI-357 and PI-359.

## 1. Environment & source of truth (critical)

- **The live V2 store is cloud Postgres, and the cloud is the single source of truth.** Local docker PG (`:55432`) is a stale snapshot — do **not** record governance against it. See the memory `project_cloud_deployment_v2`.
- **The cloud API** (`https://api.crmbuilder.ai`) has **auth ON** — you don't have a bearer token in this session. To read/write governance against the live DB, SSH to the droplet and use the access layer directly (RBAC is enforced at the API layer, not the repositories):
  ```
  ssh -i ~/.ssh/id_ed25519 root@138.197.72.15
  cd /opt/crmbuilder && QT_QPA_PLATFORM=offscreen .venv/bin/python3 -   # pipe a script over stdin
  ```
  Wrap writes in `with active_engagement("ENG-001"): with session_scope() as s:` and `change_log.set_actor("user")`. Table columns are prefixed for some entities (`project_*`, `release_*`, `requirement_*`) and unprefixed for others (`planning_items`, `decisions`, `refs` use `identifier`/`status`); `to_dict` returns raw column names. Use the repository functions in `crmbuilder_v2/access/repositories/` (they enforce the invariants the API does).
- **Governance is recorded real-time via direct writes** (DEC-383), not batched close-out JSON. Resolve a PI by creating a build-closure conversation + a `resolves` edge (`(conversation → planning_item)`), which atomically flips it to `Resolved`. Session/conversation lifecycle is `planned → in_flight → complete` (no direct `planned→complete`); decision status is `Active`; session medium is `chat`; executive summaries are 200–800 chars.

## 2. Governance preconditions — already satisfied (do not skip the check, but expect it to pass)

All four requirements are **confirmed** and each PI **implements** its requirement, so the authorization to build exists:

| PI | Requirement (confirmed) | What it demands |
|---|---|---|
| **PI-357** | REQ-416 | Every migration-tagged item exists as a DB record; every duplicate-tagged item removed from files; spot-check confirms no content lost. |
| **PI-358** | REQ-417 | A documented session-start protocol; a cold session following only the residual bootstrap loads the governing rules from the DB; residual minimized. |
| **PI-359** | REQ-418 | Files contain only bootstrap + repo-side reference + no-DB-home items; each removed item confirmed in the DB *first*; the reduction recorded. |
| **PI-360** | REQ-419 | A governance rule record states the SSoT principle + no-duplication constraint; the bootstrap references it; new sessions follow it. |

`REL-039` is **not frozen** and `PRJ-076` is `planned`. The release-scoped dev gate (`assert_developable`) defaults **OFF** and the Governed-By gate defaults to **warn**, so building is not blocked — but you must still follow Model A and requirement-first. REL-039's prior PIs were delivered off-pipeline (manual); finish this one the same way (walk the release to `delivered_off_pipeline` at the end — that transition is valid from `preliminary_planning`).

## 3. The work, PI by PI

### PI-357 — Migrate content into the DB (the big one; slice it)

Implements the PI-356 design. This is **schema + data**, and it is large enough to decompose into slices (address the PI with each slice; resolve it on the final build-closure).

**3a. Schema (code, on a `pi-357-*` branch, Model A):**
- Add three new entities per the design: **`preference` (`PRF-`)**, **`lesson` (`LSN-`)**, **`reference_pointer` (`RFP-`)** — models in `access/models.py` (plain `Base`, nullable `engagement_id`, dialect-rendered CHECKs via `_IdentifierFormatCheck` etc.), repositories under `access/repositories/`, REST endpoints, and client methods. Follow how `governance_rule`/`learning` are wired as the template.
- **Vocab:** add the three entity types to `vocab.ENTITY_TYPES`, the three prefixes to the identifier registry, and the new relationship kinds `lesson_derived_from` / `lesson_supersedes` / `lesson_promoted_to_learning` to `REFERENCE_RELATIONSHIPS` **and** `_kinds_for_pair` (source/target constraints).
- **Migrations — dual head, both required:** one migration on the SQLite chain (`migrations/`) and one on the Postgres chain (`migrations/pg/`). Never replay the SQLite chain on PG. **Each migration MUST rebuild the `change_log.entity_type` CHECK and the `refs.source_type`/`target_type`/`relationship_kind` CHECKs** to admit the new types/kinds — this is the gotcha that `create_all`-based tests miss and that 500s the live PG DB if skipped (memory `project_v2_changelog_check_migration_gotcha`).
- **Tests on Postgres** via `CRMBUILDER_V2_TEST_PG_URL` (docker-compose.dev.yml / the PG CI workflow), not just SQLite.

**3b. Data migration (populate + delete-dup):** drive from the PI-355 classification table.
- **Instructions → `governance_rule` (GVR-)**: the ~9 binding rule groups + binding `feedback_*` items; link each to its TOP-013 child topic + source decision.
- **Preferences → `preference` (PRF-)**: the 7 interaction/UI style items.
- **Lessons → `lesson` (LSN-)**: the ~40 gotchas/how-tos split out of the hybrid `project_*` memories; for each, add a `lesson_derived_from` edge to the DEC/PI/commit it was welded to (lossless split).
- **Reference pointers → `reference_pointer` (RFP-)**: the ~8 pointers. **CBM-scoped rows go to `engagement_id='ENG-002'`** (approved). **Never store a secret value** — `access_note` records *where* a credential lives, not the secret.
- Prefer a repeatable, idempotent ingest script (`crmbuilder-v2/scripts/`) with `--dry-run`, mirroring `ingest_phase2_candidate_inventory.py`. **Check the target before bulk-writing** (memory `project_rel013_pi095_ingest_halted` — a founding assumption can be stale).
- **Acceptance:** every migration-tagged item is a DB record; a spot-check confirms nothing lost. (The file *deletions* are PI-359's job — keep migration and reduction separate so you can confirm-before-delete.)

### PI-358 — Bootstrap + session-start read protocol
- Author the minimal residual that stays in `CLAUDE.md`: *how to reach the DB* (API base + auth hint) + *which records to read at session start* (TOP-013 rules, active `governance_rule`s, `preference`s, and the pointer index), **with graceful degradation when the DB is unreachable at cold start** (auth-gated — see design §6.3).
- Consider a single cheap read (e.g. a `GET /knowledge/bootstrap` endpoint or a documented set of `status='active'` scoped queries).
- **Acceptance:** a cold session following only the residual reliably loads the governing rules from the DB; residual minimized.

### PI-359 — Reduce the files
- Using the PI-355 table, trim `CLAUDE.md` to STAYS-REPO + STAYS-BOOT only, and reduce the file-based memory (harness dir `/home/doug/.claude/projects/-home-doug-Dropbox-Projects-crmbuilder/memory/`) to the minimum.
- **Confirm each item is present in its DB destination *before* removing it from the file.** Record the reduction.
- Note the meta-irony: this step trims the very memory files a session relies on — keep the bootstrap + any no-DB-home item (e.g. the global `~/.claude/CLAUDE.md` rule, which is **out of scope** and stays a file).

### PI-360 — SSoT rule + enforcement
- Create a `governance_rule` (GVR-) stating the DB is the single source of truth for governance/project knowledge and the file-memory must not store any fact the DB owns; binds humans and agents.
- Wire the bootstrap (PI-358 residual) to reference it. **Acceptance:** the rule record exists, the bootstrap references it, new sessions follow it.

## 4. Build & delivery mechanics

- **Model A branch protocol:** code/schema/migration commits go on a `pi-357-*` (etc.) branch; **verify you're on the intended branch before every commit** (`git branch --show-current`) — this repo runs a fleet of parallel agent worktrees and the checkout can move under you; commit code fixes immediately so a parallel reset can't discard them (memory `feedback_commit_during_multi_session_work`). Governance *applies* on `main`; in Claude Code, record governance **real-time via the droplet access layer** as you go.
- **Every code commit needs a `Governed-By: PI-357` (etc.) trailer** (or `Governed-By: trivial` + `Exemption-Reason:` for genuinely trivial). Docs/data-only commits are auto-exempt.
- **Commit with explicit pathspec** (`git commit -m ... -- <files>`); Claude commits, **Doug pushes**.
- **Applying the migration to the live cloud DB** (after merge to main): ship code to the droplet, `uv sync`, `alembic -c crmbuilder-v2/migrations/pg/alembic.ini upgrade head`, `systemctl restart crmbuilder-v2-api` (the startup drift gate enforces migrate-before-serve). **Never hand-patch the live schema** (memory `project_v2_live_db_migrate_via_alembic_only`). Take a DB snapshot/backup before the live migration.

## 5. Definition of done for REL-039

1. PI-357, PI-358, PI-359, PI-360 each **Resolved** (via `resolves` edges from their build-closure conversations), with governance recorded real-time (sessions/conversations/decisions in the cloud DB).
2. The three new tables exist on **both** Alembic heads and are **applied to the live cloud PG**; migrated records verified present; file dups removed and reduction recorded.
3. Cold-start bootstrap proven to load the governing rules from the DB.
4. **PRJ-076 → `complete`** and **REL-039 → `delivered_off_pipeline`** (both from their current states; both irreversible — confirm all PIs Resolved first).
5. Update the memory `project_rel039_pi355_knowledge_inventory` to reflect completion.

## 6. Where to pause for Doug

Bring these to Doug rather than deciding solo (one issue at a time — memory `feedback_one_issue_at_a_time_discuss`):
- The **shape/size of the PI-358 bootstrap residual** (how much stays in `CLAUDE.md`) — it's a judgment call about the cold-start guarantee.
- **Before deleting** any batch of memory files / `CLAUDE.md` sections in PI-359 (confirm-in-DB evidence, then get the go-ahead).
- **Before applying the migration to the live cloud DB** and before the irreversible **PRJ-076 complete / REL-039 terminal** transitions.
