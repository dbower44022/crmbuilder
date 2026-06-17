# PI-208 — Versioned, Release-Tied Change Spine: Architecture

**Wave 1 of the multi-agent release pipeline build** (build plan §19; `blocked_by`
PI-205). Architecture-phase deliverable for **PI-208** — "Build the versioned,
release-tied process and model change spine." Stacked on the `pi-205-release-entity`
branch (it reads the Release's shipped status for the live rule).

Governing design: `multi-agent-release-pipeline-architecture.md` §9 + §16.4
(DEC-481/482, REQ-214/215/216). Requirements implemented: **REQ-196, REQ-214,
REQ-215, REQ-216**.

## 1. Scope

PI-208 builds the **versioning store + the live-rule query**: full-definition
snapshots, per-artifact monotonic numbering, each version tied to the release
that introduced it, and `live = the latest version whose release has shipped`.
It does **not** author snapshots (that is architecture planning, PI-209, which
calls `snapshot(...)` with the reconciled definition) and does **not** version
requirements (they stay lifecycle-governed, REQ-216).

## 2. Key decision — one generic `artifact_versions` table (DEC-503)

§16.4 sketched "a per-artifact `*_versions` child table." This Architecture pass
**refines that to a single generic `artifact_versions` table** holding a JSON
full-definition snapshot keyed by `(artifact_type, artifact_identifier,
version_number)`.

- **Options:** (a) one `*_versions` child table per versioned type
  (`entity_versions`, `field_versions`, `persona_versions`, `process_versions`,
  `association_versions`) — five+ near-identical tables and migrations; (b) one
  generic table with a typed discriminator + a JSON snapshot.
- **Chosen:** (b). **Why:** "full-definition snapshot" is naturally a JSON blob,
  so a typed column-per-artifact schema buys nothing; one table is far less
  schema/migration surface and keeps the monotonic-numbering + live-rule logic in
  one place; it still delivers every REQ-214/215/216 property (per-artifact
  monotonic numbering, release tie, live=latest-shipped, scope = model+process).

## 3. The `artifact_versions` table

`EngagementScopedMixin + Base`, surrogate `id` PK (the satellite-table
convention, cf. `reference_book_versions`). Does **not** participate in `refs`
and does **not** emit `change_log` (the version rows are themselves the audit
trail).

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `Integer` PK autoincrement | no | surrogate |
| `engagement_id` | `String(32)` FK | no | tenant discriminator |
| `artifact_type` | `String(32)` | no | in `VERSIONED_ARTIFACT_TYPES` |
| `artifact_identifier` | `String(32)` | no | e.g. `ENT-001` |
| `version_number` | `Integer` | no | per-artifact monotonic, ≥1 |
| `release_identifier` | `String(32)` | no | the release that introduced it |
| `snapshot` | `JSONColumn` | no | the complete definition at this version |
| `created_at` | `DateTime(tz)` | no | |

Constraints:
- `UNIQUE(engagement_id, artifact_type, artifact_identifier, version_number)` —
  the monotonic numbering guard.
- `CHECK artifact_type IN VERSIONED_ARTIFACT_TYPES`.
- `CHECK version_number >= 1`.
- `ForeignKeyConstraint((engagement_id, release_identifier) → releases)` — the
  release tie (cf. the `reference_book_versions` composite FK).
- Index on `(engagement_id, artifact_type, artifact_identifier)`.

`VERSIONED_ARTIFACT_TYPES` (new vocab): `{entity, field, persona, process,
association}` — the model definitions (entity, field, persona, relation=
association) plus processes (REQ-215). Requirements are excluded by design
(REQ-216).

## 4. Access layer — `repositories/artifact_versions.py`

- `snapshot(session, *, artifact_type, artifact_identifier, release_identifier,
  snapshot) -> dict` — append vN+1: `version_number = max(existing) + 1` for that
  artifact (1 if none), insert. Concurrency-safe via the unique constraint +
  SAVEPOINT retry (the PI-002 allocator pattern).
- `live(session, artifact_type, artifact_identifier) -> dict | None` — the
  snapshot of the **highest `version_number` whose `release_identifier` has
  `release_status == 'shipped'`**; `None` if no shipped version yet (REQ-215).
  Versions in an in-flight release are frozen drafts and never returned here.
- `list_versions(session, artifact_type, artifact_identifier) -> list[dict]` —
  all versions, ascending.
- `get_version(session, artifact_type, artifact_identifier, version_number)`.
- `versions_for_release(session, release_identifier)` — every snapshot a release
  introduced (the provenance read).

## 5. API surface — `routers/artifact_versions.py`

- `POST /artifact-versions` — `snapshot(...)` (called by architecture planning).
- `GET /artifact-versions?artifact_type=&artifact_identifier=` — list.
- `GET /artifact-versions/live?artifact_type=&artifact_identifier=` — the live def.
- `GET /artifact-versions/{id}` — one version row.
- `GET /releases/{id}/versions` — `versions_for_release` (provenance).

## 6. Migrations

- SQLite `0064` (head `0063`): `create_table("artifact_versions", …)`. No refs /
  change_log CHECK rebuilds (the table is outside the refs/change_log discipline).
- PG `0021` (head `0020`): mirror.

## 7. Tests

- monotonic numbering (v1→v2→v3 per artifact, independent across artifacts);
  unique-constraint collision;
- live-rule: returns nothing until the introducing release ships; returns the
  latest *shipped* version; an in-flight (frozen-draft) higher version is **not**
  live until its release ships;
- artifact_type CHECK rejects an unversioned type (e.g. `requirement`);
- release-FK enforced; `versions_for_release` provenance; SQLite + PG.

## 8. Requirement traceability

| REQ | Where |
|---|---|
| REQ-214 full-definition snapshots, per-artifact monotonic | §3 (JSON `snapshot`, UNIQUE numbering) |
| REQ-215 release-tied; live = latest shipped | §3 (`release_identifier` FK), §4 (`live()`) |
| REQ-216 scope = model + processes; requirements lifecycle-governed | §3 (`VERSIONED_ARTIFACT_TYPES` excludes `requirement`) |
| REQ-196 versioned, release-tied change chain | the whole spine |
