# Session: Audit CBM dev (test) vs production — relationship/link divergence + root cause

## Goal
Systematically diff the CBM **test/dev** EspoCRM instance against **production**, with
primary focus on **relationships (links)**: links missing on prod, links present on both
but with **mismatched/invalid link types** (or mismatched foreign entity / foreign-side
name / relationName), and extra links on prod. Then **determine WHY** prod diverged from
test, and produce an ordered remediation plan. This is a **read-only audit + root-cause
analysis** session — do NOT modify production unless Doug explicitly approves a specific fix.

## Context (what this is)
- CBM = Cleveland Business Mentors, engagement **ENG-002** in the V2 governance DB.
- This is NOT a fresh problem: a prior session already fixed (so don't re-flag these):
  - Contact + CMentorProfile **detail layouts** (form fields).
  - Entity collection-settings round-trip (orderBy/textFilterFields/fullTextSearch) — **PI-300**.
  - The **c-prefix engine bug** that mangled custom-entity field/link names whose real name
    starts with `c`+Uppercase (e.g. `cBMValueProvided` -> `bMValueProvided`) — **fixed in
    PI-307, merged to `main` as `d2d65a14`**. So the *engine* no longer corrupts names.
  - Two already-reconciled prod records: `CPartnerProfile.cBMValueProvided` (multiEnum field)
    and `CSponsorProfile.cBMSponsorManager` (belongsTo link -> CMentorProfile).
  - **Known still-missing (start here):** `CSponsorProfile` is missing the `sponsorSessions`
    hasMany link to `CSession` that test has. Doug reports **more** links like this.

## Connection (both instances live in one SQLite DB)
- DB: `/home/doug/Dropbox/Projects/ClevelandBusinessMentors/.crmbuilder/CBM.db`
  (the desktop app's DB; **`sqlite3` CLI is NOT installed — use Python `sqlite3`**, read-only:
  `sqlite3.connect("file:<path>?mode=ro", uri=True)`).
- Table `Instance`: **id=1 = CBMTEST/dev** (`https://crm-test.clevelandbusinessmentors.org/`),
  **id=2 = CBM Production** (`https://crm.clevelandbusinessmentors.org`). Both user
  `admin@cbmentors.org`, plaintext `password` column.
- Auth = HTTP Basic: headers `Authorization: Basic b64(user:pass)` **and**
  `Espo-Authorization: b64(user:pass)`. API base `{url}/api/v1/`.
- **CRITICAL gotcha — verify auth FIRST:** `GET /api/v1/App/user` must return **200**. If it
  returns **401**, the stored creds are stale and **every Metadata call returns an empty
  string `""`** — which looks like "entities/fields are missing" but is just 401 noise. The
  prod admin password was rotated mid-session once already. On 401, stop and ask Doug for
  fresh creds rather than trusting any "missing" reading.

## Where relationships live + how to read them
- Links: `GET /api/v1/Metadata?key=entityDefs.{Entity}.links` -> dict of
  `{linkName: {type, entity, foreign, relationName?, isCustom?, audited?}}`.
  - `type` values: `belongsTo` (the many->one / manyToOne near side), `hasMany`
    (one->many near side), `hasOne`, `belongsToParent`, `hasChildren`, `manyMany`.
  - `entity` = the foreign entity; `foreign` = the link name on the foreign entity's side;
    `relationName` = the join-table name (matters for `manyMany` — a relationName mismatch
    means two instances use different join tables and the data won't line up).
- A relationship has **TWO sides** (near link on entity A + foreign link on entity B). Compare
  **both** sides and the **type on each side**. An "invalid link type" = same logical
  relationship present on both but with a different `type` (e.g. test `hasMany` vs prod
  `belongsTo`), different foreign `entity`, different `foreign` name, or different
  `relationName`.
- Scopes / entity list: `GET /api/v1/Metadata?key=scopes` (filter `entity==true`;
  `isCustom==true` = custom entities; also include extended natives Account, Contact).
- Fields (diff these too, more mis-named/missing may exist):
  `GET /api/v1/Metadata?key=entityDefs.{Entity}.fields`.
- Labels: `GET /api/v1/I18n?scope={Entity}`. Layouts:
  `GET /api/v1/Layout/action/getOriginal?scope={E}&name={detail|list|...}`.

## Methodology
1. Auth-verify both instances (`App/user` -> 200).
2. Enumerate scopes; build the set of custom + extended-native entities on each.
3. For every entity, pull `.links` on both instances. Normalize each relationship to a
   canonical tuple `(near_entity, near_link, type, foreign_entity, foreign_link,
   relationName)` and **de-dupe each relationship to one row** (it appears on both sides).
4. Produce a per-entity / per-relationship diff with four buckets:
   - **Missing on prod** (in test, not prod)
   - **Extra on prod** (in prod, not test)
   - **Type/shape mismatch** (present both, but type / foreign entity / foreign name /
     relationName differs) — these are the "invalid link types"
   - **Match** (ignore)
5. Do the same for fields (catch any remaining mis-named/missing fields).
6. **Root-cause each discrepancy.** Cross-reference the CBM YAML program files in the CBM
   repo (`~/Dropbox/Projects/ClevelandBusinessMentors/.../programs/`, top-level
   `relationships:` blocks) — does the YAML declare the relationship, and correctly? This
   distinguishes "prod never received it" from "prod received it wrong."

## Root-cause hypotheses to test (don't assume — verify each against the data)
- **(a) Non-topological deploy ordering.** The V1 engine deploys YAML files in *alphabetical*
  order, not dependency order, so a relationship to a not-yet-created custom entity hits
  HTTP 500 and is silently skipped (documented in the crmbuilder `CLAUDE.md` "Engine-bug
  backlog"). Look for missing links whose target entity sorts later alphabetically.
- **(b) Link-type downgrade.** `oneToOne` was rejected by the validator before YAML schema
  **v1.3.1**; true 1:1 links were authored as `manyToOne` as a workaround. Look for
  test=oneToOne/manyToOne mismatches.
- **(c) c-prefix name corruption (now engine-fixed in PI-307).** May have left orphaned or
  half-created links from earlier deploys. The two known ones were reconciled; look for more.
- **(d) Partial / multi-step / time-skewed deploys.** Prod was deployed at a different time
  or from a different YAML revision than test; some relationships were added to test later.
- **(e) Swallowed createLink failures** (409 Conflict from dual-declared `type: link` fields,
  or 500s) during the original prod build.

## Deliverable
A markdown report at `~/Dropbox/Projects/ClevelandBusinessMentors/audit-dev-vs-prod-links.md`:
- A per-entity relationship diff table (the four buckets above) + a field diff section.
- For each discrepancy, the **assigned root cause** (with evidence: YAML state, alphabetical
  position, type history, etc.).
- An **ordered remediation plan** for prod, grouped by cause. For link fixes, note:
  EspoCRM can't rename a link in place -> recreate-then-remove; when the foreign-side name
  collides, `removeLink` BEFORE `createLink`. createLink payload shape is in
  `espo_impl/core/relationship_manager.py::_build_payload` (`entity`, `entityForeign`,
  `link`, `linkForeign`, `label`, `labelForeign`, `linkType` in
  {manyToOne, oneToMany, manyToMany, oneToOne, ...}, `relationName` for manyMany);
  removeLink = `POST EntityManager/action/removeLink {entity, link}`; `Admin/rebuild` after
  each change. **Do not execute remediation in this session** — present the plan for Doug's
  approval.

## Guardrails & governance
- **Read-only by default.** Both instances are live (test is a shared sandbox; prod is real
  CBM). No writes to prod without Doug's explicit per-fix/batch approval.
- Re-verify auth before trusting any "missing" finding (401 -> empty `""` noise).
- This is ENG-002 work: record the audit session + findings as an ENG-002 session/conversation/
  decision (governance recording rules live in the V2 DB under topic TOP-013). If the audit
  uncovers a *tool/engine* defect (e.g. the alphabetical-deploy-ordering bug), that fix is
  **requirement-first** — author a requirement + implementing PI before any engine code; the
  prod data remediation itself is operational ENG-002 work.
- Optional tooling: the V1 audit (`espo_impl` audit_manager) can capture each instance's
  relationships to YAML for a file-level diff; the V2 desktop "Audit now" reconciles a live
  instance into the V2 DB. A direct API link-diff script (as above) is the most surgical and
  is recommended for the diagnosis pass.

---
*Governance (ENG-002, release-scoped): release **REL-003** "CBM dev->prod parity
reconciliation" -> project **PRJ-004** "Dev->prod relationship reconciliation" ->
**PI-007** (this audit) <- **WT-001** (this kickoff; this file is its
work_ticket_file_path). Remediation PIs the audit produces are born in PRJ-004 too.
Open against PI-007.*
