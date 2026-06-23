# Agent skills & guardrails — design

**Status:** in-progress design (planning session SES-243 / conversation CNV-169, 06-22-26),
continuing the SES-216 architecture walk. The hardening requirements (REQ-265…281, 283)
are **confirmed**; this doc records the design that operationalizes them — the cross-cutting
agent contract, the per-area expert cards, and (pending) the build order. **The DB
decision records are authoritative**; this doc points to them.
**Origin:** the REL-005 forensics (`REL-005-forensic-agent-trace.md`).

---

## 1. Cross-cutting decisions (settled this session)

| # | Decision | What it means in plain terms |
|---|----------|------------------------------|
| **DEC-624** | Coding agents do a bounded touched-files self-check; the runtime owns the test verdict | An agent commits first, then runs only the tests for the files it touched, time-boxed. The *system* runs the real affected-tests gate and decides pass/fail. An agent can't hang the pipeline on a verdict it doesn't own. (Operationalizes REQ-269/270/271.) |
| **DEC-625** | A work task's done-condition is **paired** | The planning agent emits, per task/batch, a plain-English acceptance criterion (the human-judgeable target) **and** the named test(s) that prove it. Done = criterion met **and** named test green. (Operationalizes REQ-278 + the architect test-spec.) |
| **DEC-626** | UI splits by technology at **build, not design** | One shared UI Architect designs the experience + acceptance criteria once; separate desktop (Qt/PySide6) and web developers/testers build and prove it. Cards keyed (area × technology × tier); technology unset at Architect, set at Developer/Tester. (Operationalizes REQ-281.) |
| **DEC-628** | **Integration is an area; each CRM engine is a technology variant** | Shared Integration Architect owns the engine-neutral→engine adapter contract; per-engine Developers/Testers (EspoCRM, HubSpot, …) build each adapter. Same shape as UI. The v1 `espo` area folds in as the EspoCRM technology. New engine later = one technology + one builder card. Chosen over a parent "Integration Agent with subagents" (the coordinating role is the existing PM/Lead). |

---

## 2. The worker (area-specialist) contract — universal skeleton

The contract every spawned `claude -p` worker receives. The **system owns the skeleton**;
each **area card owns section D2 + the identity tech-fill**; the **architect owns section E**.

- **A. Identity** — `(area × technology × tier)`; the routing key (REQ-273/281).
- **B. Role & scope** — does its one area's work; MUST NOT re-scope, re-architect, or cross areas (confirmed REQ-018).
- **C. Step 0 — validate before building** — input sanity + **already-done check → no-op exit** (REQ-267/279). If the work already exists, record that with evidence and exit; never manufacture filler.
- **D. Hard guidelines** — **D1 universal** (fixed) + **D2 area/technology constraints** (per-area card; REQ-280).
- **E. Deliverable & done-condition** — the **paired** acceptance criterion + named test, emitted by the architect (DEC-625). Under the area-phase batch model (REQ-283) this is a **set**.
- **F. Operating sequence** — validate → implement → **commit FIRST** → **bounded, synchronous, touched-files** self-check (DEC-624, REQ-269/270/271) → report → exit.
- **G. Halt / escalate** — set the workstream `needs_attention` flag + reason; never produce filler to force completion (REQ-272).
- **H. Reporting** — outcome class / files / done-condition result / commit SHA / halt reason — the durable record feeding observability (REQ-277/278).

---

## 3. The area roster

| Area | Full card now? | Technologies | Tiers |
|------|----------------|--------------|-------|
| storage | ✅ approved §4 | — | Architect · Developer · Tester |
| access | ✅ draft §4 | — | A · D · T |
| api | ✅ draft §4 | — | A · D · T |
| mcp | ✅ draft §4 | — | A · D · T |
| ui | ✅ draft §4 | **desktop · web** | Architect (shared) · Dev/Test ×2 |
| integration | ✅ draft §4 | **espocrm · hubspot · …** | Architect (shared) · Dev/Test per engine |
| automation / infrastructure / programs / methodology-* | stub until needed | — | — |

---

## 4. Area cards

### storage — APPROVED (06-22)

The database / models / migrations layer.

1. **Where it works:** SQLAlchemy models in `models.py`; pick the right scoping mixin (engagement-scoped vs system/shared) — wrong choice = rows with no engagement or the wrong one.
2. **Never change the schema without a migration — and prove it applies.** Every model change needs a paired Alembic migration. *This is the rule PI-249 violated, taking the live Releases surface down with a 500 this very session.* Done ≠ "model looks right"; done = migration written **and** runs clean on a real schema chain.
3. **Two databases, one schema.** Runs on SQLite (default) **and** Postgres. Use the dialect-neutral building blocks already in the code; never hand-write SQLite-only SQL.
4. **Some changes ripple.** A new *record type* isn't just a new table — also update the shared `change_log` and `references` validation lists, or unit tests pass while the live DB rejects writes.
5. **Prove it with a migration test, not just a unit test.** The unit tests use a create-everything-fresh shortcut that hides migration bugs. Done for a schema change = a test that stamps the old schema, runs the new migration, and round-trips a record.

### access — the business-logic / repository layer (DRAFT)

`access/repositories/` (one module per entity) + `access/` (vocab, scoping, validation).

1. **Thin API, fat access.** All business logic and governance invariants live here, not in the routers. A repository returns plain dicts and raises typed exceptions (`NotFoundError`, `UnprocessableError`, `ConflictError`, `FieldError`) — it never knows HTTP or the `{data, meta, errors}` envelope.
2. **Reference vocab is law.** Valid relationship kinds and their (source, target) rules live in `vocab.py` (`REFERENCE_RELATIONSHIPS` + `RELATIONSHIP_RULES`). Adding a kind means updating **both** the vocab and the CHECK-constraint migration — and the UI's relationship dialog reads the rules directly, so compliance is strict end to end.
3. **Engagement scoping is automatic but unforgiving.** Scoped writes are stamped from the active-engagement contextvar by a flush hook; with no active engagement the stamp is null and the insert fails (this session's release-runtime bug). Any path that writes scoped rows outside an API request must set the active engagement itself.
4. **Atomic or nothing.** Multi-step writes (edge + status flip, per-item batches) use nested savepoints so one failure rolls back cleanly. Follow the existing `begin_nested` pattern; don't hand-roll partial writes.
5. **Identifiers are server-assigned.** Prefixed identifiers auto-assign via a SAVEPOINT-retry helper safe under concurrent writers; don't accept a client-supplied identifier on create for these types.
6. **Done = an access-layer test** against the real session, not just an API round-trip — this is where the invariant must hold.

### api — the REST surface (DRAFT)

`api/routers/` (one router per entity) + `api/schemas.py` + `api/envelope.py`.

1. **Routers stay thin.** Parse → call access → wrap. No business logic in the router. Every success returns the `{data, meta, errors}` envelope via `ok()`; lists put a list in `data`, single records a dict.
2. **Schemas mirror the access contract.** Pydantic `*CreateIn`/`*UpdateIn` in `schemas.py`. For prefixed-identifier entities the create body **rejects** an `identifier`. Inline `references` are allowed only where the access create accepts them (sessions/conversations yes; decisions no — a real gotcha this session).
3. **Errors don't always wear the envelope.** Some handlers (`errors.py`) return FastAPI's standard error shape. Anything reading a response that might 4xx/5xx must read the body before unwrapping `.data`.
4. **Scope comes from the header.** Every request names its engagement via `X-Engagement`; the scope middleware resolves it. Use the `writable_session`/`readonly_session` deps; don't open sessions by hand.
5. **Known quirk:** list endpoints currently ignore `limit`/`offset` (return everything) — don't build a client around pagination that isn't there.
6. **Done = a TestClient round-trip** asserting the envelope shape and the status code.

### mcp — the AI tool surface (DRAFT)

`mcp_server` (the tools that expose the API to Claude Desktop / native tool definitions).

1. **Tools wrap, they don't reimplement.** Each tool calls the REST/access surface; `mcp_server.tools` is reusable as native Anthropic tool definitions. Keep tool defs in sync with the API they front — a drifted tool is worse than a missing one.
2. **Always scope.** Every tool call sends `X-Engagement`; an unscoped tool silently hits the wrong engagement.
3. **stdio is the live transport** (Claude Desktop); the HTTP transport is shelved but wired — don't break it.
4. **Thin area, light card:** no business logic here; done = the tool is callable and returns the documented shape.

### ui-desktop — the PySide6 / Qt front-end (DRAFT)

`ui/panels/` (extend `ListDetailPanel`) + `ui/widgets/` + `ui/workers.py`.

1. **Never block the UI thread.** Every blocking call goes through a `run_in_thread` QThread worker; keep the worker alive until `finished` or it GCs mid-flight. Transient modal sub-dialogs need `deleteLater()` or you get worker/widget GC crashes.
2. **House style is guard-enforced.** Use `CopyableMessageBox`, never raw `QMessageBox` (a test greps the `ui/` tree and fails the build). Buttons are **never disabled** — let the user click and explain. Secondary buttons are warm orange (`#FFA726`), not gray.
3. **All data via `StorageClient`** (it unwraps `.data` and carries the engagement header). Panels refresh on selection / lifecycle-ready / manual Refresh.
4. **The Qt suite is slow and flaky by nature.** `pytest-qt` + `qtbot`, `QT_QPA_PLATFORM=offscreen`; a known intermittent SIGSEGV is handled by a global teardown hook in `conftest.py` — **don't remove it**. Mind async worker → UI races (status set then clobbered by a refresh — the `_pending_status` pattern).
5. **Done = a `qtbot` panel test** driving the real widget, scoped to the touched panel's test file (DEC-624).

### ui-web — the web front-end (DRAFT — stack pending)

No web codebase yet; this card fills when the stack is chosen. Until then:

1. **Shared design, own build** (DEC-626): consumes the **same** API and engine-neutral design the desktop app does, and must match the desktop app's behavior + acceptance criteria — the UI Architect's design is the single source.
2. **D2 (framework, component library, styling, test idioms) = TBD** — filled when the web stack is selected; do not invent it before the stack is real.

### integration — engine adapters (DRAFT — shared architect + per-engine builders)

The engine-neutral design lives in the V2 DB; each engine technology derives its own config.

**Integration Architect (shared):**
1. **Derive, don't store.** The DB holds the engine-neutral CRM design; engine-specific config is **derived** by the adapter at generate time, with scoped overrides — never stored as engine-specific rows (the PRJ-025 principle). The architect owns the adapter interface every engine plug-in satisfies.
2. **One contract, many engines.** A new engine is a new implementation of the same adapter contract, not a new shape. Keep the contract engine-agnostic.

**EspoCRM technology** (folds in the v1 `espo` engine — `espo_impl/`):
3. **Config is API-only and declarative.** Deploy via the EspoCRM REST API from YAML program files using the CHECK→ACT manager pattern (field/layout/relationship/entity). Custom fields/entities take the internal `c`-prefix; native ones don't.
4. **Known platform limits are not failures.** `savedViews`/`duplicateChecks`/`workflows` have no REST write path → surface as `NOT_SUPPORTED` (manual config), not errors. Link relationships go only in the `relationships:` block, never as `type: link` fields (`validate_program` hard-rejects).
5. **Done = the generated config deploys/validates against a real instance** (the audit round-trip), not just "the YAML looks right."

**HubSpot technology:** TBD — fills when HubSpot work is real; inherits the architect's adapter contract.

---

## 5. Open items (next)

- ~~Remaining area cards~~ — DRAFTED (§4); storage approved, the rest await Doug's review. `ui-web` and HubSpot are forward-looking stubs (fill when the stack/engine is real).
- ~~The planning agents' contracts~~ — SETTLED (DEC-635): cautious, **flag-by-default**; resolve only **verifiable** duplicates (provably already-done) themselves, everything uncertain stops + escalates; prompts rewritten to match actual behavior (drop the over-claimed conflict-resolution authority). Feed the architect one PI not the whole release (REQ-266), validate inputs (REQ-279), emit paired done-conditions (DEC-625), size discipline (REQ-276).
- **Propagate the release-gate pattern** (fail-closed floor + grounded judgment + structured findings — the one good model, AGP-005) down to the phase gate and worker verification.
- **Build order — SETTLED (§7).** Three waves; Wave 1 planning items created.

## 6. Planning-agent posture (DEC-635)

Both LLM planning agents (reconciliation AGP-003, architect AGP-004) are **cautious /
fail-closed**: any genuine judgment call → stop + `needs_attention` + escalate. The **only**
self-resolved case is a **verifiable duplicate** (the implementing item is complete, or the
exact change already exists) → skip + record, don't flag. "Obvious" = checkable-as-fact, never
a judgment. Prompts rewritten to describe only what they do (translate / decompose / flag),
not the conflict-resolution authority the conductor + human actually hold.

## 7. Build order (settled 06-22)

Three waves. **Wave 1 stops the bleeding cheaply and makes the pipeline safe to re-run**;
Wave 2 fills the registry with the rich per-area contracts; Wave 3 adds observability.

### Wave 1 — stop the bleeding (planning items created under PRJ-039, `interactive`)

| PI | Title | Implements | Code locus |
|----|-------|-----------|------------|
| **PI-278** | Scope the planning seams to live, single-item work | REQ-265, REQ-266 | `release_runtime.py` (`_confirmed_requirements`, `_plan` delta-set slice) |
| **PI-279** | Validate and clear release decompositions | REQ-274, REQ-275 | `release_orchestration.py`, release cancel path |
| **PI-280** | Worker stop-conditions: skip-when-done and halt-to-escalate | REQ-267, REQ-272 | worker contract + `coordinating_runtime.py` |
| **PI-281** | Worker verification: commit-first, bounded, time-budgeted | REQ-269, REQ-270, REQ-271 | `coordinating_runtime.py` + worker contract (DEC-624) |

All four are `execution_mode = interactive` and PRJ-039 is set `interactive` — the broken
ADO runtime must not build its own fix; Wave 1 is built directly.

### Wave 2 — the real contracts (the depth)
Per-area expert cards + strict contracts become registry entries; rewrite the two
planning-agent prompts (DEC-635); area-batch build unit; area-matched profiles;
proportionate fan-out. REQ-273, 278, 280, 281, 283, 276, 279, 268. *(PIs TBD.)*

### Wave 3 — observability
Durable progress / agent-activity log. REQ-277, under PRJ-040. *(PIs TBD.)*
