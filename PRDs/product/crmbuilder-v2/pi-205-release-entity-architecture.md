# PI-205 — Release Entity & Staged Pipeline: Architecture

**Wave 0 / keystone of the multi-agent release pipeline build** (build plan §19).
Architecture-phase deliverable for **PI-205** — "Build the Release entity and staged pipeline
with the planned-completely gate." Produced 2026-06-16 (session **SES-197**, conversation
**CNV-112**), addressing PI-205 (does not resolve it — resolution lands at the Development/Test
close-out).

Governing design: `multi-agent-release-pipeline-architecture.md` §5.0 (Release entity), §16.6
(intrinsic shape), §16.2 (composition), §9A/§16.7 (freeze interplay). Requirements implemented:
**REQ-189, REQ-190, REQ-197, REQ-209, REQ-210, REQ-211, REQ-212, REQ-213** (all confirmed).

This is an **Architecture** artifact: an implementation-ready schema + lifecycle + access/API
design and a work-task breakdown. It is not the code (that is the Develop work-step).

---

## 1. Scope & boundaries

**PI-205 builds:** the `releases` table; the pipeline-stage lifecycle + its transition state
machine; the three gated transitions (**freeze**, **planned-completely**, **single-occupancy**);
lane entry by explicit order + `blocked_by`; the composition edge that makes a Project
release-scoped; the REST + repository + access surface; the migrations (SQLite + PG); the new
vocab.

**PI-205 does NOT build (owned by siblings, all `blocked_by` PI-205):**
- The **enforcement of frozen-ness on other records** (rejecting ungoverned edits to in-scope
  requirements/process-versions, derived frozen-ness) — that is **PI-216** (§9A). PI-205 owns the
  freeze *transition* and the `release_frozen_at` stamp; PI-216 reads the release status to gate
  edits elsewhere.
- **Lane single-occupancy *across releases* as the coordination invariant** and single-owner-per-
  area — **PI-204** (REQ-188/191). PI-205 owns the per-release lane-state transitions and the
  occupancy check at lane entry; PI-204 owns the broader coordination enforcement and area
  ownership. *(The occupancy check belongs to PI-205 because it is a precondition of the Release's
  own `→ development` transition; PI-204 layers area-ownership and claims on top.)*
- **Versioning of model/process definitions tied to the release** — **PI-208** (it reads
  `release_status == shipped` for the live rule; §16.4).
- **Reconciliation / freeze-temperature / planning org** — PI-215 / PI-207 / PI-209.

---

## 2. The `releases` table

New entity type **`release`**, identifier prefix **`REL-`**, `EngagementScopedPKMixin + Base`
(row-scoped by `engagement_id`, same as `Project`/`Workstream`). Conventions mirror `Project`
(`models.py:2684`) and `Workstream` (`models.py:2750`).

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `release_identifier` | `String(32)` PK | no | — | `REL-NNN`; server-assigned on POST (PI-002 pattern) |
| `release_title` | `String(255)` | no | — | human label |
| `release_status` | `String(24)` | no | `preliminary_planning` | the pipeline stage (see §3); `String(24)` because `architecture_planning` is 21 chars |
| `release_description` | `Text` | no | — | |
| `release_notes` | `Text` | yes | — | |
| `release_lane_order` | `Integer` | yes | — | the human-set lane-entry sequence (REQ-210); NULL until ordered |
| `release_frozen_at` | `DateTime(tz)` | yes | — | the freeze stamp (§16.7); also the boundary marking post-freeze versions as frozen drafts (read by PI-208) |
| `release_planned_completely_at` | `DateTime(tz)` | yes | — | stamp of the planned-completely gate (→ `ready`) |
| `release_shipped_at` | `DateTime(tz)` | yes | — | terminal-success stamp |
| `release_created_at` | `DateTime(tz)` | no | `_utcnow` | |
| `release_updated_at` | `DateTime(tz)` | no | `_utcnow` / `onupdate` | |
| `release_deleted_at` | `DateTime(tz)` | yes | — | soft-delete |
| `release_cancelled_at` | `DateTime(tz)` | yes | — | terminal |
| `release_superseded_at` | `DateTime(tz)` | yes | — | terminal |

**`__table_args__`:**
- `CheckConstraint(_IdentifierFormatCheck("release_identifier", ["REL"]), name="ck_release_identifier_format")`
- `CheckConstraint(_check_in("release_status", RELEASE_STATUSES), name="ck_release_status")`
- `Index("ix_releases_release_status", "release_status")`
- `Index("ix_releases_release_deleted_at", "release_deleted_at")`
- **Partial unique index enforcing single-occupancy** (see §4.3):
  `Index("uq_releases_one_in_lane", "engagement_id", unique=True, sqlite_where=text("release_status IN ('development','qa','testing','deployment') AND release_deleted_at IS NULL"))`
  with a dialect-conditional Postgres partial-unique equivalent. This is the *structural* backstop
  under the access-layer occupancy check — a belt-and-suspenders mirror of how the file-lock uses a
  unique constraint (§7.3, FL-4).

Composition (Projects, lane order) is in `refs`, **not** FK columns — same discipline as every
other governance entity.

---

## 3. The pipeline-stage lifecycle

`RELEASE_STATUSES` (new in `vocab.py`), 13 values:

```
preliminary_planning → development_planning → reconciliation → architecture_planning
  → ready → development → qa → testing → deployment → shipped
                                              (+ cancelled, superseded)
```

**Allowed transitions** (enforced in the access layer, mirroring how `planning_items` /
`workstreams` enforce their lifecycles):

| From | To | Gate |
|---|---|---|
| `preliminary_planning` | `development_planning` | none (scope still forming, REQ-209) |
| `development_planning` | `reconciliation` | **FREEZE gate** (§4.1) |
| `reconciliation` | `architecture_planning` | none (governed-amend window open, §9A) |
| `architecture_planning` | `ready` | **PLANNED-COMPLETELY gate** (§4.2) |
| `ready` | `development` | **SINGLE-OCCUPANCY gate** + lane-order/blocked_by (§4.3) |
| `development` | `qa` | none |
| `qa` | `testing` | none |
| `testing` | `deployment` | none |
| `deployment` | `shipped` | none (sets `release_shipped_at`; frees the lane) |
| `qa` / `testing` / `deployment` | `development` | **rework bounce-back** (D-07; lane stays held) |
| any non-terminal | `cancelled` / `superseded` | terminal; frees the lane if held |

- `shipped`, `cancelled`, `superseded` are **terminal** (no outgoing transitions).
- Rework bounce-backs (`qa/testing/deployment → development`) are explicit and legal — the lane is
  not freed (D-07, §6). They are distinct from a frozen-area reopen (§14, PRJ-034).
- Every transition is a guarded write; an illegal `from→to` raises a `ConflictError`
  ("release REL-NNN cannot move {from} → {to}").

---

## 4. The three gated transitions

### 4.1 Freeze gate — `development_planning → reconciliation` (REQ-197, REQ-209)

Entry conditions (per §16.7 D-42):
1. the release has a **settled, non-empty scope** — at least one Project is attached via
   `project_belongs_to_release`, and every in-scope **requirement** (reachable release → Project →
   PI → requirement) is `confirmed`;
2. the actor is a **deliberate human/PM act** (carried as an `X-Actor`/principal; recorded).

Effect: set `release_status = reconciliation`, stamp `release_frozen_at = now`. After this, edits
to in-scope demands are gated by **PI-216** (PI-205 only stamps the boundary).

*PI-205 deliverable:* the transition + the confirmed-scope precondition query + the stamp. The
"reject ungoverned edits elsewhere" half is PI-216.

### 4.2 Planned-completely gate — `architecture_planning → ready` (REQ-190)

Entry conditions (all three, §5.2):
1. **frozen** — `release_frozen_at IS NOT NULL` (implied by being past `reconciliation`);
2. **every requirement decomposed to work tasks** — each in-scope PI has phase workstreams whose
   work tasks cover it (queried through the PI → workstream → work_task graph);
3. **every work task sequenced** — the work-task `blocked_by` graph is acyclic and complete (no
   work task without its declared prerequisites present).

Effect: `release_status = ready`, stamp `release_planned_completely_at`. A `ready` release is
eligible for lane entry.

*PI-205 deliverable:* the gate predicate (a read over the existing PI/workstream/work_task graph)
+ the transition. Condition 2/3 reuse the landed ADO graph; PI-205 only *checks* it.

### 4.3 Single-occupancy gate — `ready → development` (REQ-189, REQ-210)

Entry conditions:
1. **no other release is in a lane state** (`development|qa|testing|deployment`) for this
   engagement — the occupancy check;
2. **lane order / blocked_by satisfied** — among `ready` releases, this one is next by
   `release_lane_order`, and every release it is `blocked_by` (release→release edge) is `shipped`
   (REQ-210).

Effect: `release_status = development`. The lane is now held until `shipped`/`cancelled`/
`superseded` (D-07).

Enforced **twice**: the access-layer check (clear error, the primary path) **and** the partial
unique index (§2) as a concurrency-safe structural backstop under `BEGIN IMMEDIATE`.

---

## 5. Composition & vocabulary (REQ-211/212/213)

New reference relationship kinds (add to `REFERENCE_RELATIONSHIPS` **and** `_kinds_for_pair` in
`vocab.py`, plus the `refs.relationship_kind` CHECK migration — per CLAUDE.md vocab rule):

| Kind | Source → Target | Meaning |
|---|---|---|
| `project_belongs_to_release` | project → release | a Project is release-scoped — belongs to exactly **one** release (REQ-211). Access layer enforces single-membership (mirrors `session_belongs_to_project`). |
| `release_blocked_by` *(use existing `blocked_by` on `(release, release)`)* | release → release | lane ordering (REQ-210); a release can't enter the lane until its blocker ships. **Extend `_kinds_for_pair` to admit `blocked_by` for the `(release, release)` pair** (as already done for `(workstream,workstream)`/`(work_task,work_task)`). |
| `release_planned_in_reference_book` | release → reference_book | optional: tie a release to its planning doc (parallels `project_planned_in_reference_book`). |

**Two-home requirements (REQ-212):** unchanged data model — a requirement keeps its
`requirement_belongs_to_topic` (timeless) and gains a *delivery overlay* by virtue of its PI's
`planning_item_belongs_to_project` where that Project `project_belongs_to_release`. No new edge on
the requirement itself; the overlay is derived through the graph. **No requirement is moved out
from under its Topic.**

**Work larger than one project (REQ-213):** `blocked_by`-sequenced release-scoped Projects sharing
a Topic — no parent-project field. Already supported by the existing `(project, project)`
`blocked_by`.

---

## 6. Access layer

New `access/repositories/releases.py` (mirror `projects.py`):
- `create_release(session, *, title, description, status="preliminary_planning", notes=None, identifier=None) -> dict` — server-assigns `REL-NNN` via the SAVEPOINT-retry helper (PI-002).
- `get(session, identifier) -> dict` / `list_releases(session, *, status=None, …)`.
- `update_release(...)` — non-status fields; status changes go through `transition`.
- `transition(session, identifier, to_status, *, actor=None) -> dict` — the **single guarded
  mutator** for `release_status`. Validates `(from,to)` against the transition table (§3), runs the
  gate predicate for freeze / planned-completely / single-occupancy (§4), stamps the matching
  lifecycle timestamp, and writes. Raises `ConflictError` on illegal transition or unmet gate.
- `set_lane_order(session, identifier, order)` / lane helpers.
- Gate predicates as private helpers: `_scope_confirmed`, `_planned_completely`, `_lane_free`,
  `_lane_next`.

`BEGIN IMMEDIATE` (already global on SQLite) + the partial unique index make the occupancy gate
concurrency-safe.

---

## 7. API surface

New `api/routers/releases.py` (mirror `projects` router), all under the `{data, meta, errors}`
envelope and the `X-Engagement` scope middleware:
- `POST /releases` — create (identifier optional).
- `GET /releases` / `GET /releases/{id}` — list / fetch.
- `PATCH /releases/{id}` — non-status fields.
- `POST /releases/{id}/transition` `{to_status}` — the guarded lifecycle move (returns 409 with a
  specific message on illegal/ungated transitions).
- `POST /releases/{id}/lane-order` `{order}` — set the lane sequence.
- `GET /releases/{id}/composition` — the release's Projects (+ their PIs), derived; convenience for
  the freeze/planned-completely surfaces.

Register the router in `api/routers/__init__.py` / `main.py`.

---

## 8. Migrations

**SQLite — `0063_pi_205_release_entity.py`** (head is `0062`; batch-mode per the chain):
1. `create_table("releases", …)` with all columns + checks + indexes (§2), incl. the partial
   unique `uq_releases_one_in_lane`.
2. **Rebuild the `refs.relationship_kind` CHECK** to admit the new kinds (§5) — batch recreate.
3. **Rebuild the `refs` entity-type CHECK** (source/target type) to admit `release`.
4. **Rebuild the `change_log` entity-type CHECK** to admit `release` — *required*, or live writes
   500 (the known gotcha: `project_v2_changelog_check_migration_gotcha`).
5. Guard for mid-stream chain entry (stamp test) per the >0036 rule; expression indexes survive
   batch recreate (the 08280ed1 fix).

**Postgres — `0020_pi_205_release_entity.py`** (head `0019`): the same as a native
`create_table` + `ALTER`/`DROP-CREATE` of the regenerated CHECKs (PG uses `~` regex / native
partial index). The dual-head rule holds — **never** run the SQLite chain on PG.

`vocab.py` is the source of truth for the regenerated CHECKs; rebuild them from the current vocab
(guarded), as PI-α/0043-0044 did.

---

## 9. Tests

- **Lifecycle:** every legal transition succeeds + stamps; every illegal `from→to` raises.
- **Freeze gate:** rejects when scope empty or any in-scope requirement non-confirmed; succeeds +
  stamps `release_frozen_at` when all confirmed.
- **Planned-completely gate:** rejects on undecomposed/unsequenced; succeeds + stamps.
- **Single-occupancy:** second release `→ development` rejected while one holds the lane (both the
  access check and, via a forced concurrent path, the unique index); freed on `shipped`/`cancelled`.
- **Lane order / blocked_by:** a release `blocked_by` an unshipped release cannot enter; order
  respected.
- **Composition:** a Project may belong to only one release; two-home requirement derivation.
- **Identifier:** `REL-NNN` format check; server-assignment + collision (409).
- Run on both SQLite and the `CRMBUILDER_V2_TEST_PG_URL` PG path (the `v2_env` fixture).

---

## 10. Work-task breakdown (the decomposition)

PI-205 is `execution_mode=interactive`, so the ADO structural decomposer is intentionally
inapplicable (DEC-425 — it refuses interactive PIs). This is the **human decomposition**, grouped
by the ADO work-steps (Design → Develop → Test) and the layer areas (`storage` → `access` → `api`).

**Design (this doc) — complete.**

**Develop** (serial by layer; `storage` before `access` before `api`):
- `WT/storage-1` — `Release` model in `models.py` + `RELEASE_STATUSES` + new vocab kinds in
  `vocab.py` (`REFERENCE_RELATIONSHIPS` + `_kinds_for_pair`).
- `WT/storage-2` — SQLite migration `0063` (table + the three CHECK rebuilds + partial unique).
- `WT/storage-3` — PG migration `0020` (mirror).
- `WT/access-1` — `repositories/releases.py`: CRUD + server-assign.
- `WT/access-2` — `transition()` + the four gate predicates (freeze, planned-completely,
  lane-free, lane-next) + lifecycle stamps.
- `WT/access-3` — `project_belongs_to_release` single-membership enforcement + `(release,release)`
  `blocked_by` admission.
- `WT/api-1` — `routers/releases.py` (CRUD + `/transition` + `/lane-order` + `/composition`) +
  registration + schemas.

**Test** (one work-step):
- `WT/test-1` — the §9 suite (lifecycle, three gates, occupancy/concurrency, composition,
  identifier) on SQLite + PG.

Sequencing: `storage-1 → {storage-2, storage-3} → access-1 → access-2/3 → api-1 → test-1`. The
`storage`/`access`/`api` serial chain falls out of the layer ranks (no intra-step parallel fan-out,
so the file-lock backstop is not exercised here).

**Note on build mechanism (decision for the Development hand-off):** because PI-205 is
`execution_mode=interactive`, the Development work-step is built either (a) by a human/this
assistant directly, or (b) by flipping PI-205 to `execution_mode=ado` and handing it to the ADO
runtime — which would make it autonomously dispatchable. (b) is a deliberate, separately-authorized
step (the background runtime can spawn build agents on a flip). PI-205 stays `interactive` until
that is chosen.

---

## 11. Requirement traceability

| REQ | Where satisfied |
|---|---|
| REQ-209 born-early forming container | §2 (`default preliminary_planning`), §3 |
| REQ-210 lane entry = explicit order + blocked_by | §2 (`release_lane_order`), §4.3, §5 |
| REQ-211 Project is release-scoped (one release) | §5 (`project_belongs_to_release`, single-membership) |
| REQ-212 requirement two homes | §5 (derived overlay; Topic home untouched) |
| REQ-213 larger work = blocked_by-sequenced, Topic-grouped projects | §5 |
| REQ-197 release freeze is a deliberate gate | §4.1 (PI-205 transition + stamp; enforcement = PI-216) |
| REQ-190 enter lane only when planned completely | §4.2 |
| REQ-189 lane locked until shipped / one in lane | §3 (lane held to `shipped`), §4.3 (occupancy) |
