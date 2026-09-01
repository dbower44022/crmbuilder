# V1 → V2 audit parity — gap matrix

**Status:** COMPLETE (2026-08-30). Every gap this matrix identified was built (PI-420..426, PI-429, PI-430 under PRJ-112), verified live, and deployed; see `v1-audit-parity-live-diff.md` for the closing evidence. Retained as the learn-phase inventory that scoped the work. Publish-side layouts remain tracked as PI-427.
**Date:** 2026-08-29
**Evidence basis:** full read of `espo_impl/core/audit_manager.py` (2,646 lines), `audit_db.py`, `audit_utils.py`, `data_profiler.py`, `espo_impl/workers/audit_worker.py`, `automation/ui/deployment/audit_entry.py`, the ten `tests/test_audit_*.py` files; and of `crmbuilder-v2/src/crmbuilder_v2/introspect/*`, `api/routers/instances.py`, `ui/dialogs/audit_progress_dialog.py`, `access/repositories/instance_membership.py`, `transform/audit_deposit.py`, `adapters/espocrm/{adapter,model}.py`, the V2 audit design docs and `tests/crmbuilder_v2/{introspect,transform}/`.

Abbreviations: `AM` = `espo_impl/core/audit_manager.py`; `AU` = `espo_impl/core/audit_utils.py`; `ADB` = `espo_impl/core/audit_db.py`; `DP` = `espo_impl/core/data_profiler.py`; `AC` = `espo_impl/core/api_client.py`; `LT` = `espo_impl/core/layout_types.py`; `RC` = `crmbuilder-v2/src/crmbuilder_v2/introspect/reconcile.py`; `EC` = `crmbuilder-v2/src/crmbuilder_v2/introspect/espo_client.py`; `INST` = `crmbuilder-v2/src/crmbuilder_v2/api/routers/instances.py`; `VOC` = `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`; `DEP` = `crmbuilder-v2/src/crmbuilder_v2/transform/audit_deposit.py`; `MOD` = `crmbuilder-v2/src/crmbuilder_v2/adapters/espocrm/model.py`.

Status vocabulary: **covered** (V2 does it natively), **partial** (V2 does part of it), **gap** (V1 only), **superseded** (replaced by a V2 design decision — no parity needed).

---

## 1. Headline

The parity review's four audit gaps **all hold**, and the inventory found **three more** it missed plus one it mis-scored:

| # | Item | Verdict |
|---|---|---|
| 1 | Email templates (REQ-124) | **Gap confirmed** |
| 2 | Field dynamic logic `requiredWhen`/`visibleWhen` (REQ-123) | **Gap confirmed** |
| 3 | Entity formula scripts (REQ-122 / DEC-420) | **Gap confirmed** |
| 4 | Data utilization profile | **Gap confirmed** (V2 has no native producer; `audit_deposit.py` only copies V1's `utilization-profile.json`) |
| 5 | Layouts — the review scored this *covered*; it is **partial**. V2 reads 6 of V1's 18 audited layout types (`edit` is the most consequential omission). | **Seed wrong → partial** |
| 6 | Entity settings — review scored *covered*; it is **partial**. Collection settings yes; icon / color / kanbanViewMode / statusField / optimisticConcurrencyControl / countDisabled / multipleAssignedUsers no (clientDefs never read). | **Seed wrong → partial** |
| 7 | Native fields (V1 `include_native_fields`) and native-entity *entity* records without custom fields | **Gap the seed missed** |
| 8 | Panel-level `dynamicLogicVisible` inside detail layouts | **Gap the seed missed** (only matters once `edit`/panel layouts are captured with structure; V2 stores layouts verbatim so this arrives for free with #5) |
| 9 | Audit → YAML files on disk | **Superseded** (DEC-008), **but** with a live consequence: `crmbuilder-v2-export-espocrm` renders none of `layouts:` / `teams:` / `filteredTabs:` / `formulaScript:`, so the Phase 4 like-for-like diff cannot compare those areas via YAML — a diff harness that reads V2 records directly is needed (§5). |

Everything else V1 audits (entities, custom fields incl. foreign, relationships, roles + system permissions, field permissions, teams, filtered tabs, i18n labels, collection settings, record export) is covered.

---

## 2. The matrix

### 2.1 Entities and entity-level settings

| V1 captures | V1 source | EspoCRM read | V2 status | V2 location | Notes |
|---|---|---|---|---|---|
| Scope discovery + classification (custom / native / system) | `AM:772-839`, `AU:267-291` | `GET /Metadata?key=scopes` | covered | `RC:484-638`, `crmbuilder-v2/…/introspect/audit_utils.py:292-316` | Same catalogs ported (PI-187). |
| Entity singular/plural labels | `AM:813-816` (i18n `Global.scopeNames[Plural]`) | `GET /I18n?language=en_US` | covered | `RC:544-551, 622-631` (REQ-364) | |
| `type` (Base / BasePlus / Person / Company / Event) | `AM:809-826` | `scopes.<E>.type` | **partial** | `RC:386` stores only `entity_tracks_activities` (BasePlus) | The base template of a custom entity (Person vs Base etc.) is not on the V2 entity record; `get_base_type` is used only to classify native fields. Publish-side emits `type` from `entity_kind` (`MOD`), so the audited value may not round-trip. |
| `stream` | `AM:809-826` | `scopes.<E>.stream` | covered | `RC:385` (`entity_track_activity`) | |
| Collection settings: `orderBy`, `order`, `textFilterFields`, `fullTextSearch`, `fullTextSearchMinLength` | `AM:862-877` (DEC-696) | `entityDefs.<E>.collection` | covered | `EC:353-367`, `RC:583-586, 724-727` (REQ-340/375) | Seed check "V2 reads `entityDefs.<E>.collection`" — **holds**. |
| `countDisabled`, `optimisticConcurrencyControl`, derived `multipleAssignedUsers` | `AM:877-889` | `entityDefs.<E>` | **gap** | — | Not in `_audited_entity_attrs` (`RC:365-401`). |
| `iconClass`, `color`, `kanbanViewMode`, `statusField` | `AM:891-904` | `clientDefs.<E>` | **gap** | — | `EC:426-437 get_client_defs` exists but no reconciler calls it. Seed check "confirm V2 reads the entity options (icon, color, kanban, statusField…)" — **does not hold**. |
| Native entity *record* when it has no custom fields | (V1 writes the entity if any layout/tab/template/formula exists, `AM:2318-2325`) | — | **gap (by design, needs confirming)** | `RC:421-437, 571-576` creates a native entity only when it has ≥1 custom field | Consequence: a native entity with customised layouts but no custom fields gets no `entity` record, so its layouts / filtered tabs are not inventoried either. |

### 2.2 Fields

| V1 captures | V1 source | EspoCRM read | V2 status | V2 location | Notes |
|---|---|---|---|---|---|
| Custom fields on custom entities | `AM:910-1048` | `entityDefs.<E>.fields` | covered | `RC:917-1189` | |
| Custom fields on native entities, c-prefix stripped (REQ-342) | `AU:203-229`; flag `include_native_custom_fields` `AM:125` | same | covered | `RC:1060, 1095-1097`; `audit_utils.py:230-254` | V2 has no opt-out flag; always on. Seed row "separate flags for custom-entity / native-entity-custom / native fields" — V1's `include_custom_fields` is a **dead flag** (never read, `AM:124`), so the real V1 switches are two: native-custom (on) and native (off). |
| **Native (non-custom) fields** (`include_native_fields`, default **False**) | `AM:136, 936-937` | same | **gap** | — | V2 reconciles only `CUSTOM`-classified fields (`RC:1024-1029`). V1 defaults this off, so the parity question is whether V2 needs the *option*. Recommend: out of scope for parity unless a reconcile use case (e.g. drift on native `required`) is confirmed. |
| Field type mapping | `AM:952` (verbatim Espo type) | — | covered (better) | `RC:804-811`, `adapters/espocrm/field_types.py:51-132` | V2 maps to the neutral vocabulary; unmapped types are *reported* (`unrecognized_field_types`, `RC:1107-1118`) not stored. Confirm this reporting is surfaced in the audit UI summary — `audit_progress_dialog.py:42-48` prints only seen/created/present/drifted/absent. |
| Field label (i18n) | `AM:529-561` | `/I18n` | covered | `RC:976-987, 1162-1165` | |
| `required`, `readOnly`, `default`, `min`, `max`, `maxLength` | `AM:965-1034` | `entityDefs.<E>.fields` | **partial** | `RC:788-793, 814-850` | Compared for drift, but on *create* only `type`/`required`/`format`/`numeric_scale` are written (`RC:1140-1148`); `default/min/max/maxLength/readOnly` are not persisted on a newly discovered field. |
| `audited`, `copyToClipboard` | `AM:965-1034` | same | **gap** | — | Minor. |
| Enum/multiEnum `options`, `translatedOptions`, `style`, `isSorted`, `displayAsLabel` | `AM:978-1000` | same | **partial** | `RC:848-882, 910-913` (REQ-442/445) | Options + labels covered; `style`, `isSorted`, `displayAsLabel` not captured. |
| Foreign field `link` + `field` | `AM:1013-1031` (REQ-121) | same | covered | `RC:1171-1177, 176-208` | V2 additionally resolves the mirrored result type. |
| **Field dynamic logic `requiredWhen` / `visibleWhen`** (REQ-123) | `AM:1369-1418`; operator map `AM:57-67`; reversal `AM:1455-1530`; unmapped type → warning + whole field's logic dropped `AM:1497-1503` | `clientDefs.<E>.dynamicLogic.fields.<f>.{required,visible}.conditionGroup` | **gap** | — | Seed **holds**. V2 has the target record type (`rule`, rendered on publish as `requiredWhen`/`visibleWhen`, `MOD:880-883`) so this is audit-IN only. V1's `readOnly` logic kind is skipped (`AM:1380-1381`) — same scope for V2. |
| **Entity formula scripts** (REQ-122 / DEC-420) | `AM:2265-2300`; filter `_`-prefixed keys + empty bodies `AM:2287-2291` | `GET /Metadata?key=formula.<E>` | **gap** | — | Seed **holds**. Capture-only by DEC-420. V2 has **no record type** for an entity-level script (the `derived` field kind is per-field). Needs a decision: new attribute on `entity`, or a new entity type. Publish side does not emit `formulaScript:` either (`MOD` grep = 0), consistent with capture-only. |

### 2.3 Relationships

| V1 captures | V1 source | EspoCRM read | V2 status | V2 location | Notes |
|---|---|---|---|---|---|
| Links → `relationships.yaml` with linkType, both link names, labels, `relationName`, `audited`, `auditedForeign` | `AM:1532-1661` | `entityDefs.<E>.links` | covered | `RC:1423-1760` | V2 also handles `belongsToParent` as `many_to_one` + `target_kinds` (REQ-506), which V1 skips (`AM:1570-1581`). `audited`/`auditedForeign` flags: not captured in V2 — minor. |

### 2.4 Layouts

V1 fetches 18 layout types (`AM:1053-1080`): `detail, edit, detailSmall, detailConvert, list, listSmall, kanban, filters, massUpdate, relationships` + 8 panel-map types (`sidePanelsDetail/Edit/DetailSmall/EditSmall`, `bottomPanelsDetail/Edit/DetailSmall/EditSmall`). Portal variants are defined (`LT:62-70`) but **never fetched by V1 either**, so the seed's "24 types" is the type catalog, not the audited set.

| Layout type | V1 | V2 (`VOC:1004-1006`, `RC:1763-1770, 1839`) | Status |
|---|---|---|---|
| `detail`, `list`, `detailSmall`, `listSmall`, `kanban`, `massUpdate` | yes | yes (verbatim body; drift = whole-body `!=`) | covered |
| `edit` | yes | **no** | **gap** — operators customise edit separately from detail; this is the one that bites first |
| `detailConvert` | yes | no | gap (Lead conversion only) |
| `filters` (search filters) | yes | no | gap |
| `relationships` (bottom-panel ordering) | yes | no | gap |
| 8 panel-map types (`sidePanels*`, `bottomPanels*`) | yes | no | gap |
| Portal variants (`detailPortal` …) | catalogued, not fetched | no | superseded / n-a (PI-418 already scopes portal- and role-bound variants as "captured, not compared") |
| Panel-level `dynamicLogicVisible` | reversed to shorthand `AM:1339-1367` | arrives verbatim inside the stored body | covered once the type is fetched |

Seed check "layout coverage may be narrower" — **holds**; 6 of 18. Fix shape: extend `LAYOUT_TYPES` + `_LAYOUT_TYPE_TO_ESPO` (vocab CHECK migration on `layout.layout_type` if constrained — verify in Phase 3) — no new entity type needed.

### 2.5 Security

| V1 captures | V1 source | EspoCRM read | V2 status | V2 location | Notes |
|---|---|---|---|---|---|
| Teams (name, description) | `AM:1945-1983` | `GET /Team?maxSize=200` | covered | `RC:2175-2232` | Neither side captures membership or pages past 200. |
| Roles: `scope_access` reversed (create as bool, read/edit/delete/stream as level) | `AM:2041-2085` | `GET /Role?maxSize=200` | covered (raw) | `RC:1911-1914` stores `data` verbatim as `scope_access` | V2 keeps Espo's raw matrix rather than V1's reversed shape — fine for inventory; the publish path (`MOD:1293-1297`) reads the raw form. |
| Roles: `system_permissions` (5 named perms) | `AM:2087-2122` | same | covered (broader) | `RC:1914` keeps every `*Permission` key | |
| Field-level permissions (`fieldData`) | not in V1 audit (deploy-only, PI-051) | — | covered | `RC:1962-2172` (DEC-707) | V2 exceeds V1. |
| §12.5 role-aware visibility | NOT_AUDITABLE advisory `AM:659-683` | — | superseded / deferred | PI-310 Deferred | Same platform block on both sides. |

### 2.6 Filtered tabs, email templates, other blocks

| V1 captures | V1 source | EspoCRM read | V2 status | V2 location | Notes |
|---|---|---|---|---|---|
| Filtered tabs: scope, label, acl, `where` reversed to condition AST; 404 = no Advanced Pack | `AM:1663-1943` | `scopes` (tab scopes), `clientDefs.<Tab>`, `GET /ReportFilter?…entityType=E` | covered (raw) | `RC:2234-2314` (DEC-437) | V2 stores the ReportFilter `where` verbatim rather than reversing it; `acl` and `navOrder` not captured. V1's tab-scope discovery (`clientDefs.<TabScope>.defaultFilter`) is not used — V2 matches on `(entity, label)`. Acceptable for inventory; the reversal lives in the publish adapter. |
| **Email templates**: name, subject, body sidecar, merge fields, slug ids | `AM:2127-2264` (REQ-124) | `GET /EmailTemplate?where[…entityType=E]&maxSize=200` | **gap** | — | Seed **holds**. `EmailTemplate` is in V2's `_SYSTEM_SCOPES` exclusion (`audit_utils.py:203`) and no reconciler reads it. Target record type exists (`message_template`, emitted on publish `MOD:2014`), so audit-IN only. |
| Saved views, duplicate checks | not audited by V1 | — | n-a | — | Saved views are excluded by decision; duplicate checks flagged "future" in `compared-set-declaration.md:191-192` — not a V1 parity item. |
| Workflows | not audited by V1 | — | n-a for parity (open V2 item) | PI-413 Draft (REQ-499 / DEC-926) | Not a V1 gap; listed because it will become the ninth audit area and shares the pattern. |

### 2.7 Data utilization profile

| V1 captures | V1 source | EspoCRM read | V2 status | V2 location | Notes |
|---|---|---|---|---|---|
| Per-entity record count, last-created, dormancy; per-field populated count / rate / last populated / distinct values / option usage (ghost + undeclared options), top values; newest-first scan capped at 10,000 with retry policy; anomalies to warnings | `DP:641-1141`; flag `include_data_profile` `AM:142` (no UI checkbox) | `GET /{E}?maxSize=0` (count), `GET /{E}?select=…&orderBy=createdAt&maxSize=1`, per-field `where[isNotNull/arrayIsNotEmpty/isLinked/isTrue]` counts, paged `GET /{E}?maxSize=200&offset=…` | **gap** | `DEP:402-414, 620-634, 759-777` consumes V1's `utilization-profile.json`; `EC:502 get_records` feeds record export only | Seed **holds**. V2 already has the *sink* (`utilization_evidence`, one row per subject, `DEP:1270-1295`) and the deposit provenance rule (REQ-339). What is missing is a native producer: an audit area `utilization` that runs the DP algorithm against `EspoIntrospectionClient` and writes `utilization_evidence` rows directly (not via a manifest). This is the largest build item (~1,100 lines of V1 logic, no V1 unit tests beyond stubs — `tests/test_audit_manager.py:1172-1254`). |

### 2.8 Output, persistence, orchestration

| V1 | V1 source | V2 status | V2 location | Notes |
|---|---|---|---|---|
| YAML files in `programs/audit-<ts>/` + `relationships.yaml` + `security/security.yaml` + `templates/<E>/<id>.html` sidecars | `AM:2302-2645` | superseded (DEC-008: renders, not authored copies) | `crmbuilder-v2-export-espocrm` (`adapter.py:172-183`, `MOD:2023-2182`) | **Caveat:** the render emits entities/fields/relationships/rules/savedViews/workflows/duplicateChecks/emailTemplates/fieldPermissions but **not** `layouts:` / `teams:` / `filteredTabs:` / `formulaScript:` (PI-417 covers roles/teams/filtered-tab publish; layouts have no PI). Nothing downstream in V2 needs V1's *files* — `audit_deposit.py` is the only consumer and it becomes obsolete once the gaps above are native. |
| `audit-report.json` manifest | `AM:346-390` | superseded | consumed only by `DEP:99-109` | Retire with `audit_deposit.py` after parity. |
| `utilization-profile.json` | `DP:47` | superseded as a file; content is the §2.7 gap | | |
| Per-client SQLite rows (Entity, Field, FieldOption, Relationship, LayoutPanel, LayoutRow, ListColumn, Team, Role, FilteredTab, ConfigurationRun) | `ADB` | superseded | V2 canonical records + `instance_membership` | V1's DB is the retired per-client store. |
| Entity picker, overwrite guard | `AE:284-495` | superseded / partial | area-scoped audit + single-entity re-audit (`entity_audit.py`); no multi-entity subset picker | PI-315 (targeted single-entity audit) Deferred — not a parity blocker. |
| Progress / cancel / per-area log | single worker | covered (better) | `audit_progress_dialog.py:117-202` reads areas from `GET /instances/audit/areas` dynamically | Seed check "dialog picks up new areas from the endpoint" — **holds**; new areas need no dialog change. Summary line omits `candidates` / `unrecognized_field_types` / `links_not_yet_described` counts (`:42-48`) — worth surfacing. |
| Connection test before run | `AW:54` | covered | `EC:311-328` | |

---

## 3. Seed findings — verdicts in one place

| Seed | Holds? |
|---|---|
| Email templates not a V2 audit area | **Yes** |
| Field dynamic logic not audited | **Yes** (V1 operator map documented above; poison behaviour = whole-field drop with warning) |
| Entity formula scripts not audited | **Yes**; V2 also lacks a place to put them |
| Utilization profile is V1-dependent | **Yes**; V2 has the sink, not the producer |
| Layout coverage narrower | **Yes** — 6 of 18 fetched types; `edit` is the notable miss. The "24 types / 4 classes" figure includes 6 portal variants V1 never fetches. |
| Entity/collection settings | **Half** — collection settings covered; clientDefs entity options (icon/color/kanban/statusField) and `countDisabled`/`optimisticConcurrencyControl`/`multipleAssignedUsers` are gaps |
| Native-entity custom fields vs native fields | Native-custom covered; native fields (V1 default off) is a gap only if the option is wanted; V1's third flag is dead code |
| Records-not-files superseded | **Yes**, nothing downstream needs the files; but the like-for-like Phase 4 diff needs a record-side harness for layouts/teams/filtered tabs/formula |

---

## 4. Proposed Phase 2 shape (for discussion, not yet recorded)

Existing confirmed requirements cover most gaps, so most items are **PIs against existing REQs**, not new requirements:

| Gap | Governing requirement | Proposed PI | Needs new record type / migration? |
|---|---|---|---|
| Email templates audit-IN | REQ-124 (confirmed) | new PI, "audit-IN half of REQ-124 in V2" | No — `message_template` exists; add `message_template` to `INSTANCE_MEMBERSHIP_MEMBER_TYPES` (`VOC:914`) → CHECK migration on `instance_membership.member_type` |
| Field dynamic logic audit-IN | REQ-123 (confirmed) | new PI | No new type — `rule` records; membership member_type `rule` addition (migration) |
| Entity formula scripts | REQ-122 (confirmed), DEC-420 | new PI | **Decision needed**: attribute on `entity` (`entity_formula_script` JSON) vs new `formula_script` entity type. Recommend attribute — capture-only, no separate lifecycle. |
| Layout types 6 → 18 | REQ-158/160 (inventory completeness) | new PI | Extend `LAYOUT_TYPES`; CHECK migration if the column is constrained |
| Entity options (clientDefs) + `countDisabled`/OCC/`multipleAssignedUsers` | DEC-696 says "V2 deferred" — **candidate requirement needed** (ai_derived) | new PI | Attributes on `entity` → migration |
| Utilization profile native producer | REQ-339 (provenance) + **candidate requirement needed** for "audit produces utilization evidence natively" | new PI (largest) | No — `utilization_evidence` exists |
| Native fields option | **Decide first** whether wanted; if yes, candidate requirement | — | — |
| Phase 4 diff harness (record-side) | none needed — test tooling | part of the verification PI | No |

Out of scope per the prompt and confirmed by this matrix: emitting `layouts:`/`teams:`/`filteredTabs:` on publish (PI-417 covers two of three; **layouts publish has no PI** — recommend recording one), workflows detection (PI-413, already drafted), V1 code deletion.

---

## 5. What Doug must decide next

1. **Native fields** — parity on the *option* (V1 default off), or drop it? (Recommend drop unless a reconcile use case exists.)
2. **Formula script home** — attribute on `entity` vs new entity type. (Recommend attribute.)
3. **Entity-options capture** (icon/color/kanban/statusField/OCC/countDisabled) — DEC-696 deferred it for V2; confirm it is in scope now so a candidate requirement can be drafted.
4. **Utilization profile** — confirm building the native producer is in this parity workstream (it is the largest item and has the weakest V1 test oracle), or split it into its own PI series.
5. **Layouts publish PI** — record one now (out of build scope here) so the layouts gap is not orphaned.

After these five answers, Phase 2 drafts the candidate requirements and PIs in the store and presents them for approval; no code before that.
