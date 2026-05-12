# CLAUDE-CODE-PROMPT-v2-ui-v0.4-C-entities-panel

**Last Updated:** 05-12-26 10:30
**Series:** v2-ui-v0.4
**Slice:** C (3 of 6)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.4-implementation-plan.md`
**Companion schema spec:** `PRDs/product/crmbuilder-v2/methodology-schema-specs/entity.md`
**Predecessor slice:** v2-ui-v0.4-B (Domains panel — live `domain` records exist as the affiliation target for `entity_scopes_to_domain` references)

## Purpose

This is the third of six slices in v0.4. This prompt builds slice **C — Entities panel end-to-end**.

Slice C implements the `entity` entity type fully per `entity.md` — schema migration, access-layer methods, REST endpoints, desktop panel with master and detail views, CRUD dialogs, and tests covering all 16 acceptance criteria from `entity.md` section 3.7.

The shape parallels slice B (Domains panel) with three slice-specific additions worth highlighting:

1. **`entity_scopes_to_domain` exercised end-to-end.** Slice A registered the vocab kind. Slice C is the first slice to produce real reference rows of this kind through the UI. The cascading vocab dialog (`ReferenceCreateDialog` from v0.3 per DEC-033) admits the kind automatically via `RELATIONSHIP_RULES`; this slice verifies the end-to-end UI flow.

2. **Detail-pane `ReferencesSection` widget renders outgoing affiliations.** First methodology-entity panel where the widget shows outgoing edges (Domains in slice B was inbound-only).

3. **Create-then-attach flow per DEC-067.** The New Entity dialog does NOT include a multi-select for domain affiliations. After the entity is created, the user attaches affiliations from the detail pane's "Add reference" affordance using the existing v0.3 cascading dialog.

## Project context

Slice B brought the first methodology entity (`domain`) to the desktop UI. Slice C extends the Methodology sidebar group with its second entry (`entity`) and exercises the cross-entity references infrastructure for the first time in the workstream.

The spec is authoritative. This prompt cites the spec's section numbers rather than restating content.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean.
3. Confirm git identity:
   - `git config user.name` → `Doug Bower`
   - `git config user.email` → `dbower44022@users.noreply.github.com`
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice B is at HEAD or recently committed.
6. API health: `curl -sf http://127.0.0.1:8765/health` returns 200; start via `uv run crmbuilder-v2-api &` if not.
7. Confirm slice A and B tests pass: `uv run pytest tests/crmbuilder_v2/ -v`.

## Reading order

Before producing any code, read:

1. `crmbuilder/CLAUDE.md` — universal entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md` section 4.4 (Entities panel) and section 4.7 (coordinated create-then-attach flow).
3. `PRDs/product/crmbuilder-v2/ui-v0.4-implementation-plan.md` section 4 Step C.
4. `PRDs/product/crmbuilder-v2/methodology-schema-specs/entity.md` — authoritative for this slice. All 16 acceptance criteria in section 3.7 are the gate.
5. `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` — needed because `entity_scopes_to_domain` references target `domain` records. Pay particular attention to section 3.3.2 (inbound relationships) which anticipated this kind.
6. Slice B's domain panel implementation at `crmbuilder-v2/src/crmbuilder_v2/ui/panels/domains.py` and supporting code — slice C mirrors the pattern with entity-specific adjustments.
7. v0.3's `ReferenceCreateDialog` at `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/reference_create.py` (or wherever it lives) — the dialog that opens from "Add reference" and creates `entity_scopes_to_domain` references. No modifications needed; just understand how it consumes `RELATIONSHIP_RULES`.

## Step 1 — Alembic migration: create the `entities` table

Create a revision named like `0NNN_v0_4_create_entities_table.py`. The migration creates the `entities` table per `entity.md` section 3.2:

| Column | Type | Constraints |
|--------|------|-------------|
| `entity_identifier` | TEXT | PRIMARY KEY, format `^ENT-\d{3}$` (CHECK), unique |
| `entity_name` | TEXT | NOT NULL; case-insensitive uniqueness enforced at access layer |
| `entity_status` | TEXT | NOT NULL, default `'candidate'`, CHECK in `('candidate', 'confirmed', 'deferred')` |
| `entity_description` | TEXT | NOT NULL |
| `entity_notes` | TEXT | NULL allowed |
| `entity_created_at` | DATETIME | NOT NULL, default current_timestamp |
| `entity_updated_at` | DATETIME | NOT NULL, default current_timestamp |
| `entity_deleted_at` | DATETIME | NULL allowed |

No FK column to `domain` on the `entities` table — domain affiliations live in the `refs` table via the references entity. Mirror slice B's table-migration patterns for soft-delete, defaults, and CHECK constraints.

Forward and backward reversible.

## Step 2 — Access-layer repository: `access/entity.py`

Create the repository with the eight standard methods. Mirror slice B's `access/domain.py` pattern with entity-specific adjustments:

- Identifier format: `^ENT-\d{3}$`
- Status enum: `{candidate, confirmed, deferred}`
- Status-transition validation: same propose-verify gate as `domain` (one-way out of `candidate`; free movement between `confirmed` and `deferred`)
- Name uniqueness: case-insensitive, engagement-global (no domain-scoping)
- Soft-delete: standard pattern; outbound `entity_scopes_to_domain` references are NOT cascade-deleted per spec 3.4.6

Critical: **`entity_status` is independent of any affiliated domains' statuses per spec 3.4.3.** The access layer does NOT consult the affiliated domains when validating entity-status changes. Status changes on a domain do NOT cascade to entities scoped to that domain.

JSON-export hook regenerates `db-export/entities.json` after any DB-changing operation.

## Step 3 — REST API router: `api/routers/entities.py`

Eight standard endpoints per `entity.md` section 3.5.1. Mirror slice B's `domains.py` router with entity-specific path and validation.

**Decomposed reference handling per spec 3.5.4.** No `/entities/{id}/scopes` shortcut endpoint, no inline-affiliation field in POST/PUT/PATCH bodies. Affiliations attach via the existing `POST /references` route with:

```json
{
  "source_type": "entity",
  "source_id": "ENT-NNN",
  "target_type": "domain",
  "target_id": "DOM-NNN",
  "relationship_kind": "entity_scopes_to_domain"
}
```

The cascading vocab dialog and references router from v0.3 handle this — no changes needed beyond what slice A already provisioned via the vocab additions.

## Step 4 — Desktop UI panel: `ui/panels/entities.py`

Create the panel mirroring slice B's Domains panel pattern with entity-specific adjustments.

### 4.1 Sidebar registration

Methodology sidebar group, position #2 (after Domains).

### 4.2 Master pane

Columns: Identifier / Name / Status / Updated. **No Domains column in v0.4** per spec section 3.6.2 and PI-009 deferral — the column would render bare `DOM-NNN` identifiers without `domain.short_code` (PI-007) and isn't useful at v0.4 entity counts. Defer to v0.5+ paired with PI-007.

Sort: Identifier ascending. Context menu: New / Edit / Delete / Restore.

### 4.3 Detail pane

Vertical layout per spec section 3.6.3:

1. `entity_identifier` — read-only label
2. `entity_name` — single-line text editor
3. `entity_description` — multi-line text editor, placeholder "Brief description of what kind of thing this entity represents"
4. `entity_notes` — multi-line text editor under collapsible "Internal notes" section header, collapsed by default
5. `entity_status` — combo box with three enum values; restrict to valid successors
6. `ReferencesSection` widget — renders outgoing `entity_scopes_to_domain` affiliations plus any inbound references (none in v0.4 from source-side specs; widget always present for v0.5+ future kinds)

The `ReferencesSection` widget's existing v0.3 implementation handles outgoing edges; no widget modifications needed.

### 4.4 CRUD dialogs

Create `ui/dialogs/entity_crud.py` (or split into separate files matching v0.3 patterns).

**Create dialog (per DEC-067 create-then-attach flow):** fields match the detail pane MINUS the `ReferencesSection`. The dialog creates the entity record only. No multi-select for domain affiliations; the user attaches affiliations from the detail pane after creation via the existing "Add reference" affordance.

**Edit dialog:** same shape as create; identifier read-only; status combo restricted to valid successors.

**Delete dialog:** standard edge-text confirmation (user types `ENT-NNN` to enable Delete). Soft-deletes the record; outbound `entity_scopes_to_domain` references persist per spec 3.4.6.

### 4.5 File-watch wiring

Connect to the `entities_changed` signal slice A wired in `ui/refresh.py`.

## Step 5 — Storage client extensions

Add eight methods for entities in `ui/client.py` mirroring slice B's domain methods.

## Step 6 — Tests

Three test modules covering all 16 acceptance criteria from `entity.md` section 3.7.

### 6.1 `tests/crmbuilder_v2/access/test_entity.py`

Cover criteria 1–8 mirroring slice B's domain access tests adapted for entity.

Additional entity-specific assertions:
- Soft-deleting an entity does NOT cascade-delete `entity_scopes_to_domain` references. The references persist in the `refs` table; appear in `?include_deleted=true` views on either side.
- `entity_status` changes do not consult affiliated domains' statuses (no cascade).

### 6.2 `tests/crmbuilder_v2/api/test_entities_api.py`

Cover REST endpoints (criterion 6) and identifier auto-assignment (criterion 7). Standard pattern from slice B.

### 6.3 `tests/crmbuilder_v2/ui/test_entities_panel.py`

Cover criteria 9–16. Critical slice-specific tests:

**Criterion 14: vocab registration + constraint enforcement (end-to-end).**

- POST `/references` with `{source_type: "entity", source_id: "ENT-001", target_type: "domain", target_id: "DOM-001", relationship_kind: "entity_scopes_to_domain"}` succeeds and creates a row in `refs`.
- POST `/references` with `(entity, domain)` and an unsupported kind (e.g., `relationship_kind: "covers"`) returns HTTP 422.
- Direct DB insert into `refs` with an unknown `relationship_kind` value rejected by the CHECK constraint extended in slice A.
- The cascading `ReferenceCreateDialog` opened from an Entities-panel "Add reference" affordance correctly enumerates `entity_scopes_to_domain` in the kind combo when source=`entity` and target=`domain` are selected.

**Criterion 15: bidirectional reference round-trip.**

- Create an entity (`ENT-001`) and a domain (`DOM-001`) via REST.
- Create an `entity_scopes_to_domain` reference from `ENT-001` to `DOM-001` via REST.
- Open the entity detail pane: confirm the reference appears under outgoing references in the `ReferencesSection`.
- Open the domain detail pane (from slice B): confirm the reference appears under inbound references in the `ReferencesSection`.
- Soft-delete the entity: confirm the reference persists in `refs` (visible under `?include_deleted=true`). Soft-delete the domain instead: same behavior. Restore either side: reference remains live.

**Criterion 16: sample CBM-redo Phase 1 records.**

- Programmatically author ~10 entity records (e.g., Contact, Account, Engagement, Session, Mentor, Mentor Application, Client, Dues, Contribution, Fundraising Campaign).
- For each, attach 1–3 `entity_scopes_to_domain` references to authored `domain` records.
- Transition statuses from `candidate` to `confirmed`.
- Simulate app restart by reloading from REST.
- Confirm records and references persist correctly.

## Acceptance verification

1. **Slice C tests pass.** `uv run pytest tests/crmbuilder_v2/access/test_entity.py tests/crmbuilder_v2/api/test_entities_api.py tests/crmbuilder_v2/ui/test_entities_panel.py -v` — all 16 acceptance criteria green.
2. **Slice A and B tests still pass.** `uv run pytest tests/crmbuilder_v2/access/test_vocab_v0_4.py tests/crmbuilder_v2/api/test_next_identifier_retrofit.py tests/crmbuilder_v2/access/test_domain.py tests/crmbuilder_v2/api/test_domains_api.py tests/crmbuilder_v2/ui/test_domains_panel.py -v` green.
3. **Full test suite green.** `uv run pytest tests/crmbuilder_v2/ -v`.
4. **Migration applies forward and backward.**
5. **Manual smoke.** Open the desktop app; create an entity through the New dialog; open detail pane; click "Add reference" and create an `entity_scopes_to_domain` reference to a live domain. Open the Domains panel; navigate to the affiliated domain; confirm the reference appears under inbound.

If any step fails, stop and report.

## Commit

```bash
git add crmbuilder-v2/migrations/0NNN_v0_4_create_entities_table.py \
        crmbuilder-v2/src/crmbuilder_v2/access/entity.py \
        crmbuilder-v2/src/crmbuilder_v2/api/routers/entities.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/panels/entities.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/entity_crud.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/app.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/client.py \
        tests/crmbuilder_v2/access/test_entity.py \
        tests/crmbuilder_v2/api/test_entities_api.py \
        tests/crmbuilder_v2/ui/test_entities_panel.py
git commit -m "v2: v0.4 slice C — Entities panel end-to-end + entity_scopes_to_domain exercised"
```

Doug pushes. Do NOT push.

## What NOT to do

- Do NOT include a multi-select for domain affiliations in the New Entity dialog. The create-then-attach flow per DEC-067 attaches affiliations from the detail pane.
- Do NOT add a master-pane Domains column. Deferred to v0.5+ paired with PI-007 / PI-009.
- Do NOT add an FK column on the `entities` table referencing `domain`. Affiliations live in the `refs` table.
- Do NOT introduce variant relationships (Mentor Contact / Client Contact pattern). Deferred to v0.5+ per PI-010.
- Do NOT cascade `entity_status` changes when an affiliated `domain_status` changes, or vice versa. The two lifecycles are independent per spec 3.4.3.
- Do NOT modify the v0.3 `ReferenceCreateDialog`. It handles the new vocab kind automatically via slice A's `vocab.py` extensions.
- Do NOT write SES-016 or any DEC-NNN records.
- Do NOT bump `__version__` or update the README.

---

*End of prompt.*
