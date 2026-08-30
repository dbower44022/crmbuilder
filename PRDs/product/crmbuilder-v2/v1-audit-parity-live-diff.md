# V1 vs V2 audit — live parity verification (PI-428)

**Instance:** CBM test EspoCRM (`crm-test.clevelandbusinessmentors.org`, RFP-007), audited read-only on 2026-08-30.
**Method:** the same instance audited by V1 (`AuditManager`, every option on) and by every V2 audit area in order (`_AUDIT_AREAS`, into a scratch store), then V1's YAML diffed against V2's records with the harness in the session scratchpad (`parity_diff.py`, `utilization_diff.py`). The harness is deliberately not committed: it carries instance credentials by file path and is a one-off proof, not a product feature.
**Stack under test:** PI-423, PI-424, PI-422, PI-420, PI-421, PI-425, PI-426 plus the layout fix this run produced.

## Result in one line

Every difference between the two audits is either **fixed in this stack**, **superseded by a deliberate V2 design decision**, or **recorded below as a remaining gap with a planning item**. No unexplained difference remains.

## Counts

| Area | V1 | V2 | Verdict |
|---|---|---|---|
| Entities | 29 YAMLs | 21 records | 21 shared; 8 V1-only — see gap G1 |
| Fields | 315 | 300 custom + 147 built-in | 15 V1-only are link-typed — superseded (DEC-932 / REQ-505: links are relationships); 147 built-in fields are V2-only by design (REQ-523) |
| Relationships | 134 | 70 associations (87 seen) | links whose other end is not a canonical entity are not recorded — gap G1 |
| Layouts | 257 blocks | 179 records | per-entity type sets identical for shared entities after the fix below; the total gap is the 8 G1 entities |
| Roles | 12 | 12 | equal |
| Teams | 9 | 9 | equal |
| Filtered tabs | 0 | 1 | V2 records the entity's report filter (`Engagement / Pending Clients`); V1 only emits a tab when a navigation tab scope points at it — superseded (DEC-437 defines the V2 record as the report filter) |
| Email templates | 0 | 0 | instance holds none; parity proven at unit level (`test_email_template_parity.py`) |
| Formula scripts | 2 entities | 2 entities | same hook keys |
| Field dynamic logic | 0 | 0 | instance holds none; parity proven at unit level (`test_field_rules_parity.py`) |
| Entity settings | — | — | 0 differences across the 10 compared keys (sort, icon, colour, status field, kanban, count, OCC, multi-assign, FTS) |
| V1 warnings | 48 | — | all 48 are role scope-access values V1 cannot represent (booleans); V2 stores the raw matrix, so nothing is lost |

## Defect found and fixed by this run

**Empty layout bodies.** The first run stored 378 V2 layout records; 200 of them were EspoCRM's `false` / empty answer for a type the entity has no stored layout for. V1 skips those; V2 did not. Fixed (`_layout_body_present`, both the layouts area and the single-entity refresh), with a regression test; the rerun stores 179, and per-entity layout type sets now match V1's for every shared entity.

## Remaining gaps (tracked)

- **G1 — uncustomised built-in entities.** V1 writes an entity YAML for any built-in entity that has layouts (Call, Campaign, Case, Lead, Meeting, Opportunity, TargetList, Task here); V2 creates an entity record only when a built-in entity has a custom field (PI-192), so those entities' layouts and the relationships that end on them are not inventoried. A customised *layout* on a built-in entity with no custom field is therefore invisible. Recommendation: treat a built-in entity with any stored layout as canonical. Recorded as Draft planning item PI-429.
- **G2 — qualifying properties dropped at field creation.** The field audit derives holds/display/values/supplied-by from the live field but the create path writes only type, required, format and numeric scale, so a discovered multi-value pick-list is stored (and would publish) as a single enum. Surfaced by the utilization comparison as ten populated-count mismatches, all on multiEnum/array fields. Recorded as Draft planning item PI-430 (REQ-501).
- **Relationship sides in utilization** (PI-426): V1 profiles link-shaped relationship sides; V2 profiles only design fields that describe a link, because an association is not an admitted evidence subject. 175 V1-only field targets in the comparison are these. Noted in the PI-426 commit.

## Utilization (PI-426)

V1's `utilization-profile.json` versus V2's `utilization_evidence` rows for the same instance (V2 run: 21 entities, 447 fields, 468 evidence rows, one deposit event).

| Measure | Result |
|---|---|
| Entities profiled | V1 29 / V2 21 — the 8 V1-only are G1 |
| Entity record counts | 20 of 21 shared entities equal; `Email` differed (V1 wrote `-2`, V2 first wrote `0`) — root cause below, fixed |
| Field populated counts | 300 shared targets; 290 equal; 10 differ, all multi-value pick-lists — G2 |

**Defects found and fixed by this run (PI-426).** EspoCRM answers `total: -1` for an entity whose counting is disabled (`countDisabled`, a setting the audit now captures). V1 wrote that through unchecked; V2's evidence repository rightly refuses a negative count, which failed the first run on `Email`. The profiler now recognises the answer, skips the per-field count queries (each would answer -1), takes the record count from the newest-first scan — exact when the scan completes, a flagged lower bound at the cap — and derives every field metric from the scan; and it still counts by an id-only scan when the entity has no inspectable design field.
