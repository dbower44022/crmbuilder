# PI-051 — RBAC Deploy Support: Design / Architecture Pass (Kickoff)

**Planning item:** PI-051 (Draft) — *"audit-v1.4 — Section 12.5 role-aware visibility deploy implementation alongside Section 12.7 field-level permissions"*
**Project:** PRJ-017 — *YAML Schema v1.3 — Role-Based Access Control*
**Session type:** Design / Architecture pass. **No build, no stakeholder interview.** The output is a *decision + a reviewable requirement + a design doc*, not code.
**Why this session exists:** PI-051 is real, undone work, but it is **not** an ADO-buildable task today. It is currently a *research menu* — four mutually-exclusive candidate approaches with open EspoCRM wire-format questions and a hard "the API-only engine can't write files" blocker. ADO cannot build a decision that has not been made. This session makes that decision and produces the spec + requirement so PI-051 can later be decomposed and built.

---

## 1. Orientation — read these first

**Tier 1 (always):**
- `CLAUDE.md` — esp. the **"Three features have no public REST API write path"** rule (savedViews / duplicateChecks / workflows → `NOT_SUPPORTED` short-circuit) and the **"Error handling architecture"** section. RBAC deploy is the next candidate for that same treatment — the precedent governs the design.

**Tier 2 (v2 governance — read live from the API, never from files):**
Start the API if needed (`crmbuilder-v2-api &`), send the `X-Engagement: CRMBUILDER` header on every call, unwrap the `{data, meta, errors}` envelope.
- `GET /planning-items/PI-051` — the full candidate-approach menu (the four options) lives in its description.
- `GET /decisions/DEC-243` — **the governing prior decision.** §12.5 (both 12.5.1 role-leaf-clauses and 12.5.2 forRoles layout variants) was ruled `NOT_SUPPORTED` on EspoCRM 9.x because (a) Dynamic Logic supports only **record-field** conditions — EspoCRM 8.1+ added `current-user` and `current-user-teams` conditions but **not** `current-user-role`; and (b) Layout Sets bind to **Teams, not Roles**. The loader still validates §12.5 intent and audit round-trips the deployable parts.
- `GET /decisions/DEC-180`, `/DEC-181`, `/DEC-182` — the v1.2 audit roles/teams/security-capture decisions (audit already emits `security/security.yaml`).

**Tier 2 (spec + code — these are v1 product artifacts, read from disk):**
- `PRDs/product/app-yaml-schema.md` **§12 Security and RBAC** (lines ~2326–2831): §12.1 Roles, §12.2 Teams, §12.3 Scope-Level Entity Access, §12.4 System Permissions, **§12.5 Role-Aware Visibility** (incl. the "Deploy Support" sub-section DEC-243 added), §12.6 Deploy Ordering, **§12.7 Deferred — Field-Level Permissions and Permission Presets**.
- `PRDs/product/features/feat-audit.md` **§12.5** — role-aware visibility is `NOT_AUDITABLE` in v1.3; schema accepts the structure for v1.4 when a real deploy mechanism lands.
- `espo_impl/core/role_manager.py` — existing v1.2 roles/teams scaffolding.
- The `NOT_SUPPORTED` short-circuit precedents: `espo_impl/core/saved_view_manager.py`, `duplicate_check_manager.py`, `workflow_manager.py` (the `TODO(error-handling-D)` pattern).

---

## 2. The core tension you are resolving

The CRMBuilder Configure engine is **API-only by design** — it deploys via the EspoCRM REST API and does **not** SSH in or write files to the instance. Several RBAC surfaces appear to need exactly what the engine refuses to do:

| Surface | Apparent deploy mechanic | API-only compatible? |
|---|---|---|
| §12.1 Roles | Role entity CRUD via REST | **Likely yes** |
| §12.2 Teams | Team entity CRUD via REST | **Likely yes** |
| §12.3 Scope-level entity access | Role `data` permissions via REST | **Likely yes — verify** |
| §12.4 System permissions | Role permission fields via REST | **Likely yes — verify** |
| §12.5.1 role-aware leaf clauses | Dynamic Logic — but no `current-user-role` condition exists | **No (DEC-243)** — needs a workaround or stays NOT_SUPPORTED |
| §12.5.2 forRoles layout variants | Layout Sets — but they bind to Teams not Roles | **No (DEC-243)** — needs Teams-as-proxy or stays NOT_SUPPORTED |
| §12.5 via Dynamic Handler JS | Generate `client/custom/src/views/<entity>/record/detail.js` | **No** — filesystem write, outside the engine |
| §12.7 field-level permissions | Role `fieldData` / `fieldOverridesPermission` via REST | **Unknown — primary research question** |

**The decision is not "how do we build all of §12.5/§12.7" — it is "what is honestly deployable via the API-only engine, and what stays NOT_SUPPORTED, and is the API-deployable subset worth shipping on its own?"**

---

## 3. The four candidate approaches (from PI-051 — adjudicate each)

1. **Dynamic Handler JavaScript generation** — generate per-entity `detail.js` with role-aware visibility logic. Requires filesystem writes (no REST path) and a reverse-engineering strategy for audit round-trip, *or* accept this surface is `NOT_AUDITABLE` and write-only. **Tension:** breaks the API-only model; would require a new SSH/file-write engine capability.
2. **Teams-as-proxies-for-Roles** — auto-generate one Team per Role at deploy; bind users to teams as a separate operator step; use EspoCRM 8.1's `current-user-teams` Dynamic Logic condition. **Tension:** conflates Team and Role semantics; operators see auto-generated mirror-teams in the admin UI.
3. **Upstream EspoCRM feature request** — file a Dynamic Logic role-condition feature request and wait. **Not actionable as a build item** — track only.
4. **Layout Sets + Teams (forRoles deploy path)** — layout-level role scoping via Layout Sets bound to auto-generated mirror-Teams, even if leaf-clause role conditions remain `NOT_SUPPORTED`.

These are not all-or-nothing — a hybrid (e.g. ship the REST-deployable Roles/Teams/scope-access + §12.7 field permissions now; adopt approach 2/4 for the layout/visibility surface as an opt-in; keep JS-generation NOT_SUPPORTED) is a legitimate outcome.

---

## 4. Questions this session must answer

1. **§12.7 field-level permissions — is it REST-API-deployable?** This is the highest-value open question. Roles carry field-level permission data (`fieldData` / read/edit per field). Confirm the exact wire format against EspoCRM 9.x and whether `RoleManager`/the Role entity REST endpoint accepts it. If yes, §12.7 may be the cleanest, most shippable piece — independent of the §12.5 mess.
2. **What is the honest deployable subset of §12.5?** Decide per-surface: REST-deployable, Teams-as-proxy (approach 2/4), NOT_SUPPORTED, or NOT_AUDITABLE.
3. **Do we build a filesystem/SSH-write engine capability?** The Server Management layer already SSHes for deploy/upgrade/recovery — is reusing that connection for `custom/` file writes + cache rebuild in scope, or explicitly out of scope (keeping Configure API-only)? **Recommend a default of "out of scope — keep Configure API-only; JS-generation stays NOT_SUPPORTED"** unless the research shows it's small.
4. **Audit / round-trip strategy** — for each deployable surface, can audit reverse-engineer it back to YAML, or is it write-only?
5. **Scope split** — what ships in the next schema version, what's deferred, what's permanently NOT_SUPPORTED. Update the §12.5 "Deploy Support" sub-section and the §12.7 sub-section accordingly.

---

## 5. Deliverables (the triple-artifact close-out)

1. **A design doc** at `PRDs/product/crmbuilder-v2/pi-051-rbac-deploy-design.md`: the per-surface deploy adjudication table (§5 q1–q5 resolved), the chosen approach(es) with rationale, the EspoCRM 9.x wire-format findings (cite sources), the proposed §12.5/§12.7 schema-spec revisions, and a **decomposition recommendation** (which workstreams/work_tasks, area `espo` / `automation`, what each builds).
2. **A governance decision** (`POST /decisions`) recording the chosen approach. It should **reference / build on DEC-243** (DEC-243 deferred §12.5; this decision says *how much of it actually lands and how*). Capture which surfaces are REST-deployable, which use Teams-as-proxy, which stay NOT_SUPPORTED/NOT_AUDITABLE.
3. **A traced, reviewable requirement** (or small set) for the chosen RBAC deploy scope — `POST /requirements` (no `identifier` field in the body; server-assigns), anchored to a topic and a provenance conversation, then surfaced in the **Requirements Review panel** for Doug's sign-off. **This is the gate:** per the requirements-provenance rebuild, the capability cannot be ADO-built until a confirmed requirement traces to it. Note PI-051's current topic anchor `TOP-065` does not resolve — create or attach a valid topic.

**Explicitly out of scope for this session:** writing any deploy code, decomposing PI-051 into workstreams, or flipping its status to Ready / dispatch-approved. Those are the *next* session, after the design + requirement are approved.

---

## 6. After this session

Once the design lands and the requirement is approved in the Review panel, PI-051 becomes ADO-ready via the normal path: **decompose → scope into work_tasks (area `espo`/`automation`) → Ready → dispatch-approve → ADO builds.** Until then PI-051 stays `Draft` in PRJ-017 (`in_flight`) and is correctly *not* dispatchable.

**Prioritization note for Doug:** this is a v1 product-engine feature; the repo's stated active direction is the Master CRMBuilder PRD / v2 dogfood. Confirm this design pass is worth scheduling against that priority before spending the session.
