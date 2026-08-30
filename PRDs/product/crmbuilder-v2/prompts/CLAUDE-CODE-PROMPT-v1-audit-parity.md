# CLAUDE CODE PROMPT — V1 audit parity in V2

**Mission.** Make CRMBuilder V2 able to do everything the V1 Audit feature does, so V1's audit code can be retired. Learn first, get the requirements approved, then build.

**Context you are inheriting.** A parity review on 2026-08-29 (https://claude.ai/code/artifact/bda883a3-2bd7-471e-82fe-06b3a27cee19) found V2's native audit (`crmbuilder-v2/src/crmbuilder_v2/introspect/`) covers entities, fields, associations, layouts, roles, field permissions, teams and filtered tabs, but that four V1 audit passes have no V2 equivalent. Treat those findings as a **seed to verify**, not as settled fact.

A **parallel session is working on Server Management** (SSH deploy / upgrade / recovery / extensions) at the same time. Coordination rules are in §4.

---

## 1. Bootstrap (do this before anything else)

1. Read `CLAUDE.md` → "Session bootstrap". The V2 database is the source of truth. Read TOP-013 + children, active governance rules, active preferences, reference pointers, and `GET /lessons?category=process`.
2. Announce which governance rules bind this session: requirement-first (confirmed requirement + implementing PI before any code), `Governed-By: PI-NNN` trailer on every commit, real-time governance recording, commit-with-pathspec on `main` (Model A), no new terminology without Doug's approval, and the commit-under-parallel-orchestrators rule.
3. Read these store records before forming any opinion: **REQ-121, REQ-122, REQ-123, REQ-124, REQ-125, REQ-126, REQ-127, REQ-128, REQ-129, REQ-158, REQ-159, REQ-160, REQ-339, REQ-364, REQ-392, REQ-393, REQ-394, REQ-395, REQ-499, DEC-420, DEC-434, DEC-437, DEC-648, DEC-649, DEC-653, DEC-696, DEC-707, DEC-851, DEC-862.** Record any others you find relevant in your session notes.

---

## 2. Phase 1 — Learn (read-only; no code changes)

Build a complete, evidence-backed inventory of what V1 audit captures and what V2 audit captures. Cite file paths and line numbers.

**V1 audit surface**

- `espo_impl/core/audit_manager.py` (2,646 lines — read it all, it is the reference), `audit_db.py`, `audit_utils.py`, `data_profiler.py`, `espo_impl/workers/audit_worker.py`, `automation/ui/deployment/audit_entry.py`
- Every `AuditOptions` flag and what each one reads from EspoCRM
- Every reverse-mapper (layouts by structure class, dynamic-logic operator map, where-item reversal, `scope_access` / `system_permissions` reversal, i18n label resolution, email-template merge-field extraction and body sidecars, `formulaScript` capture)
- Output shape: per-entity YAML, `security/security.yaml`, `manifest.json`, `utilization-profile.json`, the per-client SQLite rows `audit_db.py` writes
- `tests/test_audit_*.py` — these are your parity oracle

**V2 audit surface**

- `crmbuilder-v2/src/crmbuilder_v2/introspect/` (`espo_client.py`, `reconcile.py`, `entity_audit.py`, `record_export.py`), `api/routers/instances.py` (`_AUDIT_AREAS`, `_SOURCE_AUDIT_AREAS`), `ui/dialogs/audit_progress_dialog.py`, `access/repositories/instance_membership.py`, `transform/audit_deposit.py`
- Design docs in `PRDs/product/crmbuilder-v2/*audit*` and `compared-set-declaration.md`
- `tests/crmbuilder_v2/introspect/` and `tests/crmbuilder_v2/transform/`

**Deliverable: a gap matrix** at `PRDs/product/crmbuilder-v2/v1-audit-parity-gap-matrix.md`. One row per thing V1 captures; columns: V1 source, EspoCRM endpoint/metadata key read, V2 status (covered / partial / gap / superseded), V2 location, notes. Verify each of these seed findings explicitly and say whether they hold:

| Seed finding | What to check |
|---|---|
| Email templates (REQ-124) are not a V2 audit area | `MessageTemplate` is authored only; no `reconcile_*` reads `EmailTemplate` records |
| Field dynamic logic (REQ-123) is not audited in V2 | V1 reverses `requiredWhen`/`visibleWhen` from `clientDefs` dynamic logic with a documented operator map and poisons unmapped types with a warning |
| Entity formula scripts (REQ-122, DEC-420) are not audited in V2 | V1 captures verbatim `formulaScript:` — capture-only by decision |
| Data utilization profile is V1-dependent | V2's `transform/audit_deposit.py` consumes V1's `AuditReport` manifest; no native V2 pass produces `utilization_evidence` |
| Layout coverage may be narrower | V1 audits 24 layout types across four structure classes incl. portal variants and panel-map layouts; confirm which `reconcile_layouts` reads |
| Entity-settings / collection-settings capture (DEC-696) | Confirm V2 reads `entityDefs.<E>.collection` and the entity options (icon, color, kanban, statusField, …) |
| Native-entity custom fields and native-field audit | V1 has separate flags for custom-entity fields, native-entity custom fields, and native fields |
| Audit output as files | V1 writes YAML to `programs/audit-*/`; V2 writes records. Treat "records, not files" as superseded **unless** something downstream still needs the files (check `crmbuilder-v2-export-espocrm` covers it) |

Also list anything V1 audits that the seed missed. Present the matrix to Doug and **stop for review** before Phase 2.

---

## 3. Phase 2 — Governance (before any code)

For each confirmed gap, draft a candidate requirement in the store (origin `ai_derived`, status candidate) following the decision/requirement templates under TOP-013, then propose PIs that implement them. Where a confirmed requirement already exists (REQ-122/123/124 are confirmed; REQ-121–129 were approved together under DEC-419) do **not** create a duplicate — propose the PI against the existing requirement and record which half (audit-IN) it delivers. Present the requirement + PI set to Doug for approval. **No code until approval.**

---

## 4. Phase 3 — Build

Follow the existing V2 audit pattern exactly — that is the whole point of parity, not a redesign:

- One `reconcile_<area>()` in `introspect/reconcile.py` per new area (or `entity_audit.py` for per-entity slices), registered in `_AUDIT_AREAS` in run order, backed by `EspoIntrospectionClient` methods, writing canonical records + `instance_membership` rows through the repositories. Respect source-vs-target candidate gating (DEC-648/649/653) and the "successful-but-empty read drives present→absent" rule (DEC-851).
- New design entity types (if an area needs one) require the model + both repositories + REST router + dual-head Alembic migrations (`migrations/versions/` and `migrations/pg/versions/`) + the `refs`/`change_log` CHECK extensions — see the add-entity-type lesson in `GET /lessons`.
- The audit progress dialog picks new areas up from `/instances/{id}/audit/areas`; verify it does.
- Tests: port the relevant V1 `tests/test_audit_*.py` cases to `tests/crmbuilder_v2/introspect/` as the parity proof. Run `QT_QPA_PLATFORM=offscreen uv run pytest tests/crmbuilder_v2/ -q` before every commit.

**Coordination with the parallel Server Management session:**

- Before editing `crmbuilder-v2/src/crmbuilder_v2/access/models.py`, `api/routers/instances.py`, `ui/panels/instances.py`, or adding an Alembic revision, run `git fetch && git log origin/main --oneline -20` and rebase; those files and the Alembic heads are shared with the other session. Never create a migration without first checking both heads (`alembic heads` for each tree). Resolve a dual-head collision by linearizing onto `main`'s head (DEC-430 precedent).
- Keep your commits scoped with an explicit pathspec; never `git add -A`. Do not touch `automation/core/deployment/`, `instance_deploy_configs`, or anything SSH-related — that is the other session's area.
- Record every PI start/finish in the store in real time so the other session (and Doug) can see what is claimed.

---

## 5. Phase 4 — Verify parity

The acceptance test is a live comparison: audit the same EspoCRM instance with V1 (`uv run crmbuilder` → Deployment → Audit, all options on) and with V2 (Instances → Audit now), then diff V1's YAML output against V2's records (render V2 with `crmbuilder-v2-export-espocrm` to compare like with like). Audit is read-only, so the shared test instance is safe. Every difference must be either fixed, explained as superseded-by-design, or recorded as a remaining gap with a PI. Commit the diff summary as the PI resolution evidence.

---

## 6. Out of scope

Server management (parallel session); emitting `layouts:`/`teams:`/`filteredTabs:` on the **publish** side (a separate parity item — record a PI if audit work exposes a need but do not build it here); deleting V1 code (retirement is a later phase once all parity items close).

## 7. Report at the end of each phase

Plain summary: what was verified, what was built, test counts, PIs and requirements touched with identifiers, remaining gaps, and what Doug must decide next. Report failures as failures.
