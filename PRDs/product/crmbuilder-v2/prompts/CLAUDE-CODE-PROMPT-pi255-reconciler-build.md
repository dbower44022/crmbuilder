# CLAUDE-CODE-PROMPT-pi255-reconciler-build.md

## Operating mode: DETAIL

## Purpose

Build **PI-255's final delivering slice**: the source-mapping **reconciler
candidate-gating** plus the **association mapping extension**. This implements
**REQ-300** (and **REQ-319** for associations) and, on close-out, **resolves
PI-255**. Slices 1 (schema/access) and 2a (REST) are already on `main`.

---

## Step 0 — Governance preconditions (verify FIRST — binding, do not skip)

Per CLAUDE.md "Governance is a precondition": confirm out loud, before any code:

1. `GET /requirements/REQ-300` → `status == confirmed`. REQ-300 authorizes the
   **reconciler core** (Slices A + B below).
2. `GET /requirements/REQ-319` → **must be `confirmed`** before any **association**
   code (Slice C). REQ-319 is human-approved by Doug in the desktop Requirements
   Review panel. **If REQ-319 is not yet confirmed: build Slices A + B only, and
   STOP before Slice C** — do not write association code on an unconfirmed
   requirement. Re-check at build time.
3. `GET /references?source_id=PI-255` shows `planning_item_implements_requirement`
   to both REQ-300 and REQ-319 (already wired).

If REQ-300 is somehow not confirmed, stop and surface it — do not proceed.

---

## Step 1 — Read the authoritative design

The design is recorded in the governance DB (authoritative) and mirrored in the
design doc:

- `PRDs/product/crmbuilder-v2/source-mapping-design.md` — **§12** (reconciler
  design pass), **§8.8** (`association_mapping`), §1–9 (the model), §10/§11.
- Decisions **DEC-648…654** (`GET /decisions/DEC-648` … `DEC-654`), recorded in
  session **SES-247**. These govern; where §10 differs, §12 governs.

### The seven locked decisions (summary)

- **DEC-648 — role is the switch.** Candidate-gating runs only on a `source`- or
  `both`-role instance audit (`both` → treated as source). A `target`-role audit
  keeps today's `present`/`drifted`/`absent` drift reconcile **unchanged**.
- **DEC-649 — no auto-promotion on source audits.** Never auto-create canonical
  objects, never auto-mark `present` by name. Every discovered object → a
  `mapping_candidate`; name/type similarity is a **suggestion only**. On re-audit,
  matching is driven by the resolved `source_mapping` (the human decision).
- **DEC-650 — membership stays canonical-only.** `instance_membership` keeps
  `present`/`drifted`/`absent`. **Remove `candidate_pending` + `mapping_stale`**
  from the vocab. Candidacy → `mapping_candidate`; staleness → the mapping's
  `status`.
- **DEC-651 — fractal multi-pass surfacing.** Entity candidate immediately; a
  **field** candidate only once its parent entity is mapped; an **association**
  candidate only once **both** endpoint entities are mapped; a **value** candidate
  only once its interpreted enum field is mapped. Rejected/unmapped dependency →
  dependents stay deferred. Multi-pass over re-audits.
- **DEC-652 — staleness on the mapping.** Source-side staleness (re-audit finds a
  mapped source object renamed/retyped/gone) → mapping `status=stale,
  source_changed` + a fresh suggestion-candidate — **build this now**. Design-side
  staleness → a **separate follow-on** (needs canonical-edit hooks).
- **DEC-653 — scope.** Source audits candidate-gate **entity / field / value /
  association** only. Layouts/roles/teams/filtered-tabs are **not** reconciled on
  a source audit. Target audits unchanged.
- **DEC-654 — associations first-class.** New `association_mapping` (`AMP-`,
  table `association_mappings`), parallel to `field_mapping`, decision types
  `direct`/`referential`/`rejected` (no decomposition); `candidate_type` gains
  `association`; surfaces once both endpoints are mapped. Terms already approved.

---

## Step 2 — Build (slices)

Build off a fresh git worktree from **current `origin/main` HEAD** (not stale
code). Model A: a `pi-NNN` branch carries only code/schema/migration commits.

### Slice A — drop the two membership states (migration)

- `vocab.py`: `INSTANCE_MEMBERSHIP_STATES` → `{present, drifted, absent}` (remove
  `candidate_pending`, `mapping_stale`).
- New migration (SQLite chain head + 1; **check the live head, numbers drift** —
  see the 0079→0081 lesson; chain off whatever the current head is) that rebuilds
  the `instance_memberships` `ck_instance_membership_state` CHECK back to the three
  states. PG companion. No rows use the dropped states, so it's a clean rebuild.

### Slice B — reconciler candidate-gating (REQ-300)

In `crmbuilder-v2/src/crmbuilder_v2/introspect/reconcile.py` + the audit router:

- **Role switch.** The audit entrypoint (`POST /instances/{id}/audit[/{area}]`)
  branches on the instance's role: `source`/`both` → the candidate-gated path;
  `target` → the existing drift reconcile, unchanged.
- **`reconcile_entities`** (source path): for each discovered source entity, look
  up its **resolved `source_mapping`** for `(instance, source_entity_name)`. If a
  resolved mapping exists → reconcile `present`/`drifted` membership against its
  target canonical entity. If a **rejected** mapping exists → skip (decided). If
  no mapping → **create a `mapping_candidate(entity)`** (idempotent — don't
  duplicate an existing unresolved candidate); attach a name-match **suggestion**
  if a canonical name matches; **do not auto-create, do not write membership**.
- **`reconcile_fields`** (source path): reconcile fields **only** for entities that
  are mapped to canonical (resolved `source_mapping`). For such an entity, an
  unmatched field → a `mapping_candidate(field)` (with `source_entity_name` +
  `source_field_name`); a matched field → present/drifted membership. **Defer**
  (skip) fields of entities that are still candidates.
- **Source-side staleness.** When re-audit no longer finds a previously-mapped
  source object, flip its `source_mapping`/`field_mapping` to `status=stale,
  stale_reason=source_changed` and surface the changed/new object as a fresh
  candidate.
- Summary: add a `candidates` count; keep the existing keys for backward-compat.
- **Update the affected existing tests** in
  `tests/crmbuilder_v2/access/test_instance_membership.py` (and the audit API
  test) to the new candidate-gated behavior — they currently assert auto-promotion.

### Slice C — association extension (REQ-319 — only if confirmed)

Mirror the `field_mapping` build end-to-end:

- `vocab.py`: `candidate_type` set gains `association`; add
  `ASSOCIATION_MAPPING_DECISION_TYPES = {direct, referential, rejected}`; add
  `association_mapping` to `ENTITY_TYPES`.
- `models.py`: `AssociationMapping` (table `association_mappings`,
  `EngagementScopedPKMixin`, identifier-as-PK `AMP-`, columns per design §8.8,
  same `status`/`stale_*` CHECKs as `FieldMapping`). Register in
  `entity_summary.py`.
- Migration (chain off current head) creating `association_mappings` + rebuilding
  `change_log`/`refs` CHECKs for the new entity type; PG companion; add the table
  to the `0038` scoped-tables guard (`test_0038_engagement_id_discriminator.py`).
- `access/repositories/association_mapping.py` (mirror `field_mapping.py`).
- `api/routers/association_mappings.py` + schemas in `api/schemas.py` + register in
  `api/main.py` (mirror `field_mappings`).
- `reconcile_associations` (source path): an association candidate
  (`candidate_type=association`) surfaces once **both** endpoint entities are
  mapped; resolution writes an `association_mapping` → canonical association.
- Tests for the repo + router + the reconcile association-gating.

---

## Step 3 — Verify

- `uv run ruff check` clean on all changed/new files.
- New + updated tests green; run the full `tests/crmbuilder_v2/access/` and
  `tests/crmbuilder_v2/api/` dirs + the migration round-trip tests.
- `uv run python -m alembic heads` → single head, both chains.

---

## Step 4 — Merge, governance, resolve PI-255

- Rebase onto current `origin/main`; renumber the migration(s) if the head moved
  (the 0079→0081 lesson); ff `main`.
- Record governance **real-time via API on `main`** (DEC-383): the build session,
  any build decisions, and **resolve PI-255** via a `resolves_planning_items`
  close-out edge (`Open/Draft → Resolved`). Read **`TOP-013`** before authoring
  governance records.
- **Live DB:** after merge, migrate the live `v2-unified.db` with
  `crmbuilder-v2/scripts/migrate_live_db_to_0081.py` as the model — i.e. stamp to
  the true schema level then `upgrade head`, **and run `--reconcile-only`** to heal
  any create_all column drift. Back up first; the script does.

---

## Scope boundary (do NOT build here)

- Layouts/roles/teams/filtered-tabs candidate-gating (out of scope, future
  extension).
- The **design-side** staleness trigger (DEC-652 — separate follow-on).
- The candidate-resolution **desktop UI** (separate follow-on under PRJ-027).
- If REQ-319 is unconfirmed at build time: **Slice C is out** — ship A + B only.

---

## Deliverables

- Code + migration(s) + tests merged to `main`.
- Live DB migrated + reconciled.
- Build session governance recorded; **PI-255 resolved**.
