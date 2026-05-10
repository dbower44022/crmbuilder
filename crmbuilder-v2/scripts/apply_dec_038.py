#!/usr/bin/env python3
"""Apply DEC-038 — derived fields first-class in methodology schema.

HISTORICAL — DO NOT RE-RUN. This script was executed once on 05-10-26
and DEC-038 was successfully created (HTTP 201). It is preserved as
the original record of the apply.

A second run will return HTTP 409 (DEC-038 already exists), which the
script handles as a skip — but there is no reason to invoke it again.
"""
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8765"


def _request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw": body}
        return e.code, payload


DEC_038 = {
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


def main() -> int:
    print("=" * 70)
    print("POST /decisions for DEC-038")
    print("=" * 70)
    code, payload = _request("POST", "/decisions", DEC_038)
    if code == 201:
        identifier = payload.get("data", {}).get("identifier", "DEC-038")
        print(f"OK — created {identifier}")
        return 0
    if code == 409:
        print("SKIP — DEC-038 already exists (HTTP 409)")
        return 0
    print(f"FAILED: HTTP {code}")
    print(json.dumps(payload, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
