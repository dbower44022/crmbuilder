# CLAUDE-CODE-PROMPT-apply-DEC-038

**Last Updated:** 05-10-26 04:50
**Series:** apply-DEC
**Status:** Ready to execute
**Companion conversation:** Discussion with Doug on 05-10-26 establishing how Foreign-style fields should be modeled in CRMBuilder v2's methodology entity schema.

## Purpose

Apply **DEC-038** to the CRMBuilder v2 governance database: a settled position on how foreign-style fields (EspoCRM's `Foreign` field type, lookup fields in other CRMs) are modeled in the methodology entity schema. The decision needs to be in the database before the methodology entity schema design (Step 0 follow-on) picks up so it has a settled requirement to build from.

This is a one-shot apply prompt. After it runs successfully and is committed, mark the resulting `apply_dec_038.py` script with the historical preamble (matching the `apply_dec_025.py` convention) so it is not re-run.

## Project context

Per DEC-004, the v2 database is the source of truth for all v2 artifacts; per DEC-008, downstream JSON snapshots are renders, not authored copies. Decisions are inserted via the v2 access layer (HTTP POST to `/decisions`), which transactionally regenerates the JSON snapshots under `PRDs/product/crmbuilder-v2/db-export/`.

The current v2 status (see `db-export/status.json`) lists 37 decisions (DEC-001 through DEC-037). DEC-038 is the next identifier.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. If there are uncommitted changes, stop and report to Doug before proceeding.
3. Confirm git identity is set:
   - `git config user.name` should return `Doug`
   - `git config user.email` should return `doug@dougbower.com`
   - If not set, configure: `git config user.name "Doug"` and `git config user.email "doug@dougbower.com"`.
4. Pull latest from origin: `git pull --rebase origin main`.
5. Confirm DEC-038 does not already exist:
   - `grep -c '"identifier": "DEC-038"' PRDs/product/crmbuilder-v2/db-export/decisions.json` should return `0`. If `1`, stop — DEC-038 is already applied; this prompt should not be re-run.
6. Confirm the v2 API is running:
   - `curl -sf http://127.0.0.1:8765/decisions >/dev/null` should return success.
   - If not running, ask Doug to start it (`crmbuilder-v2-api &`) before proceeding.

## Workflow

### Step 1 — Write the apply script

Create `crmbuilder-v2/scripts/apply_dec_038.py` modeled on the existing `apply_dec_025.py` pattern: urllib-based POST to `http://127.0.0.1:8765/decisions`, with handling for `201 Created` (success), `409 Conflict` (already applied — exit 0 with skip message), and other statuses (exit 1 with diagnostic).

Use **the exact DEC-038 content in the appendix at the bottom of this prompt** as the payload. Do not paraphrase or shorten.

### Step 2 — Run the apply script

```bash
python crmbuilder-v2/scripts/apply_dec_038.py
```

Expected output: `OK — created DEC-038`. If the response is anything else, stop and report.

### Step 3 — Verify

- `curl http://127.0.0.1:8765/decisions/DEC-038` returns the decision body matching the payload.
- `grep -c '"identifier": "DEC-038"' PRDs/product/crmbuilder-v2/db-export/decisions.json` returns `1`.
- The same grep against `change_log.json` should also return at least `1` (the access layer's audit log records the insert).

If either snapshot was not regenerated, the export hook may have failed. Stop and report rather than committing partial state.

### Step 4 — Add the historical preamble to the apply script

Once the script has been successfully run, edit it to add a "HISTORICAL — DO NOT RE-RUN" preamble matching the `apply_dec_025.py` convention. The preamble should record the run date, confirm the apply succeeded, and instruct future readers not to re-run it.

### Step 5 — Commit and push

Single commit covering:

- `crmbuilder-v2/scripts/apply_dec_038.py` (new file, with the post-run historical preamble)
- `PRDs/product/crmbuilder-v2/db-export/decisions.json` (regenerated)
- `PRDs/product/crmbuilder-v2/db-export/change_log.json` (regenerated)

Commit message:

```
v2: Apply DEC-038 — derived fields first-class in methodology schema

Settles the modeling question for foreign-style fields ahead of the
methodology entity schema design (Step 0 follow-on). Derived fields
are first-class methodology entities with explicit FK references to
the traversed relationship and source field; cross-entity dependency
is tracked via the universal references table (DEC-006) using two
new vocabulary entries (derives_from_relationship, derives_from_field).

A v1-side workstream is opened separately to bump app-yaml-schema.md
to v1.3 and add `type: foreign` to the deployment engine; tracked as
a follow-on planning item, not blocking V2.

Originating conversation: Claude.ai discussion 05-10-26.
```

Push to origin/main. Authentication via the established token-in-remote-URL pattern; reset remote URL after push.

### Step 6 — Report

In the final response to Doug, report:

- Confirmation that DEC-038 was created (status code, identifier, decision_date).
- The two regenerated snapshot file paths and a one-line confirmation each contains DEC-038.
- The commit SHA and the result of `git log --oneline -1`.
- The push result (`origin/main` tip).
- Any deviations from the prompt or anomalies encountered.

## Constraints

- **One decision only.** This prompt applies DEC-038 and nothing else. Do not edit other governance records, propose new decisions, modify methodology guides, or touch v1 code.
- **No paraphrasing the payload.** The DEC-038 content in the appendix is the agreed text; reproduce it verbatim in the apply script.
- **Stop on any anomaly.** If the API is unreachable, the snapshot doesn't regenerate, the JSON shape differs from expected, or any pre-flight check fails, stop and report rather than working around it.
- **No CBM content involvement.** This is a v2 governance change. The CBM repo is not touched by this prompt.

---

## Appendix — DEC-038 payload (verbatim)

```json
{
  "identifier": "DEC-038",
  "title": "Derived fields — first-class methodology entities with explicit references to traversed relationship and source field",
  "decision_date": "05-10-26",
  "status": "Active",
  "context": "EspoCRM's Foreign field type — and analogous concepts in other CRM platforms (lookup fields, formula fields, rollup fields) — provides a way to display data from a linked entity inline on the host entity, avoiding clicks-through and enabling list views, filters, and reports to surface related-entity information without joins. This is a core configuration capability used heavily in practice (mentor email on Engagement, mentee company industry on Engagement, cohort on SurveyAnswer, etc.). The current CRMBuilder v1 YAML schema (Section 6.2 of app-yaml-schema.md) does not support Foreign as a field type; foreign-style fields are invisible to the deployment engine and accumulate as manual-config items. The V2 storage system v0.1 covers project-management entities only; the methodology entity schema (entities, fields, relationships, etc.) is Step 0 follow-on work (per the current status entry) and has not been designed yet. This decision settles the modeling question for derived fields before that design work begins, so the methodology schema work, when it picks up, has a settled position to build from.",
  "decision": "Foreign-style fields are modeled as a first-class concept in the V2 methodology entity schema under the platform-agnostic name 'derived fields', with `derivation_kind=linked_value` as the initial form. Each derived field carries explicit foreign-key references to (a) the relationship on the host entity that the field traverses, and (b) the source field on the linked entity whose value is mirrored. The cross-entity dependency is tracked via the universal references mechanism (DEC-006) using two new relationship-vocabulary entries: `derives_from_relationship` and `derives_from_field`. Validation enforces the dependency at write time: link must exist on the host entity, source field must exist on the linked entity, source field type must be in the supported set (varchar, int, float, date, datetime, bool, text, enum), and link cardinality must be Many-to-One or One-to-One. Renderers (Entity PRDs, Domain PRDs, deployment YAML, Verification Spec) treat derived fields distinctly from stored fields. Deployment YAML support is delivered separately via a v1.3 bump to app-yaml-schema.md adding `type: foreign` with `link` and `sourceField` properties — separate v1-side workstream, not blocking V2 design and tracked as a planning item.",
  "rationale": "Treating derived fields as first-class with explicit dependency references makes the cross-entity relationship between a derived field and its source machine-readable, which enables impact-analysis queries ('if I rename Contact.emailAddress, which derived fields break?', 'which derived fields disappear if I delete the assignedMentor link?') that are impossible today. Routing derivation references through the universal references table (DEC-006) avoids inventing a parallel mechanism and means the same cross-cutting query infrastructure that handles decisions, sessions, and topics naturally extends to derived fields. Validating at write time shifts left — currently these errors surface only at deployment, or never, since v1 doesn't deploy derived fields at all. Calling the concept 'derived fields' rather than 'foreign fields' keeps the methodology layer platform-agnostic; the platform-mapping layer translates `derivation_kind=linked_value` to EspoCRM's `type: foreign` (or equivalent in another CRM). Separating the v1.3 YAML schema bump from this decision keeps the methodology design clean and unblocks deployment automation today, before V2's renderers exist.",
  "alternatives_considered": "- Treat foreign fields as a regular field with `field_type='foreign'` and no explicit references. Rejected — dependencies remain invisible to queries; V2 cannot answer impact-analysis questions; defeats the cross-entity reference machinery V2 already has.\n- Use EspoCRM-specific naming ('foreign field') in the methodology schema. Rejected — couples the methodology layer to a specific CRM platform; other CRMs use different terminology; V2 is meant to be platform-agnostic at the methodology layer.\n- Defer the design until the methodology entity schema is otherwise underway. Rejected — derived fields are common enough in practice that letting the schema land without a settled treatment risks retrofitting later, when the references model is harder to extend cleanly.\n- Skip explicit FK references; store link_name and source_field as plain strings on the field row. Rejected — loses referential integrity and makes impact analysis a string-search exercise rather than a graph traversal through the references table.\n- Bundle the v1-side YAML schema bump into this decision. Rejected — bundles two distinct workstreams (methodology design vs. v1 deployment engine extension) under one decision and obscures their independent timing.\n- Solve only the v1-side gap (extend v1 YAML schema for `type: foreign`) and defer V2 modeling. Rejected — solves today's deployment gap but doesn't address the methodology-schema design question this decision is meant to settle.",
  "consequences": "- The methodology entity schema design (Step 0 follow-on after V2 storage v0.1, currently in the status pending list) inherits this treatment as a settled requirement: the `fields` table includes a `derivation_kind` discriminator, and a structure (sub-table or columns) carries the link + source-field FKs for fields where `derivation_kind` is set.\n- Two new relationship-vocabulary entries are added to the universal references controlled vocabulary (DEC-006) when the methodology entity schema lands: `derives_from_relationship` (source_type=field, target_type=relationship) and `derives_from_field` (source_type=field, target_type=field).\n- Renderer specs (Word, YAML, Verification) need to handle derived fields distinctly. This is downstream work, after the methodology schema and renderers are scoped.\n- A separate v1-side workstream is opened: bump `app-yaml-schema.md` to v1.3 adding `type: foreign` with `link` and `sourceField` properties, and extend the v1 deployment engine's field manager to handle the new type. Tracked as a planning item, not blocking V2.\n- Foreign-style fields currently treated as manual-config items in CBM YAML files become candidates for automation once the v1.3 schema bump and engine support land. Existing manual-config entries for foreign fields can be migrated.\n- This decision opens the door to unified treatment of related derivation kinds (aggregate, arithmetic, concat — already in v1's formula schema as `formula:` blocks) under a single `derivation_kind` discriminator in the future methodology schema, but those are out of scope for this decision."
}
```
