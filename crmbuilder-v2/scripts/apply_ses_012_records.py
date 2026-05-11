#!/usr/bin/env python3
"""Write SES-012 governance records — domain schema-design conversation.

Six decisions (DEC-044 through DEC-049), two new planning items (PI-006 and
PI-007), and six references linking each new decision to SES-012 via
``decided_in``.

The session record SES-012 itself is **not** written by this script — Doug
writes it through the v0.3 desktop New Session dialog at the actual close of
the conversation, per the session-record-at-close pattern. This script runs
*after* SES-012 has been written through the dialog, so the ``decided_in``
references linking DEC-044..DEC-049 to SES-012 can succeed.

Idempotent on re-run: each POST treats HTTP 409 conflict as already-present
and continues. Safe to re-run if a partial failure occurs.

Usage:
    cd crmbuilder-v2
    uv run python scripts/apply_ses_012_records.py

The script reports each operation with its HTTP status and continues past
409s. Exit code 0 on full success; non-zero only if a non-409 error is
encountered or the SES-012 pre-flight check fails.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8765"
DECISION_DATE = "05-11-26"
SESSION_ID = "SES-012"

# ---------------------------------------------------------------------------
# Decisions (DEC-044 through DEC-049)
# ---------------------------------------------------------------------------

DECISIONS = [
    {
        "identifier": "DEC-044",
        "title": "domain identifier prefix and format",
        "context": (
            "The domain methodology entity needs an identifier prefix. The spec "
            "guide allows 3-5 uppercase letters; existing v2 governance entities "
            "use 3 letters consistently (DEC, SES, RSK, TOP, REF, CHR, STA; PI is "
            "the lone 2-letter outlier predating the convention). domain is the "
            "first methodology entity to land in the methodology-entity-schema-"
            "design workstream, so its prefix choice carries implicit weight for "
            "the downstream three specs (entity, process, crm_candidate)."
        ),
        "decision": (
            "Adopt DOM as the identifier prefix for the domain methodology "
            "entity. Format DOM-NNN, zero-padded to 3 digits, server-assigned "
            "on POST omission via the GET /domains/next-identifier helper (per "
            "DEC-043 / SES-010 resolution). Affirm the v2 norm of 3-letter "
            "prefixes without locking it as a strict requirement for downstream "
            "methodology entities; the spec guide section 6 range of 3-5 letters "
            "remains open for downstream entities (process, crm_candidate) where "
            "3 letters introduces ambiguity (e.g., PROC over PRC for clarity; "
            "CRMC over CRM to avoid product-name collision)."
        ),
        "rationale": (
            "DOM is three letters, unambiguous, has no collision risk with any "
            "existing prefix, reads naturally as 'domain', and matches the "
            "existing v2 pattern visually. The soft-3-letter posture preserves "
            "downstream flexibility — locking 3 strict would force PRC over PROC "
            "or CRM over CRMC even where the 4-letter form is clearer."
        ),
        "alternatives_considered": (
            "DOMAIN (6 letters, verbose, breaks rhythm with existing prefixes). "
            "D (too short, ambiguous). DM (2 letters, breaks 3-5 convention, "
            "collision-risk with future entities). Strict 3-letter convention "
            "for all methodology entities (rejected as preemptively constraining "
            "process and crm_candidate before their conversations open)."
        ),
        "consequences": (
            "domain.md uses DOM-NNN throughout. Downstream entity, process, "
            "crm_candidate specs choose their own prefixes with soft-3-letter "
            "posture as guidance; each justifies its choice in its own section "
            "3.1. Cross-spec consistency check at v0.4-build planning verifies "
            "no prefix collisions across the four methodology entity types."
        ),
    },
    {
        "identifier": "DEC-045",
        "title": "domain field inventory and validation under minimum-viable v0.4 scope",
        "context": (
            "The Phase 1 evolved methodology interview guide (section 7.2) "
            "produces a Domain Inventory with one paragraph per domain "
            "containing name (in client's language), structural code, one-"
            "sentence purpose, and brief description of work covered. The "
            "domain schema in v0.4 needs to host this output under minimum-"
            "viable scope while leaving room for v0.5+ growth as Phase 3+ "
            "iteration work demands."
        ),
        "decision": (
            "Adopt seven explicit fields plus inherited timestamps for the "
            "domain entity in v0.4: domain_identifier (DOM-NNN, server-"
            "assigned), domain_name (client's language, case-insensitive "
            "unique within engagement), domain_purpose (required, one-"
            "sentence, plain text), domain_description (required, brief "
            "paragraph, plain text), domain_notes (optional, plain text "
            "consultant scratchpad not part of client-facing Domain Inventory "
            "render), domain_status (see DEC-047), plus inherited "
            "domain_created_at, domain_updated_at, domain_deleted_at. No "
            "storage-level length caps in v0.4; UI placeholder text provides "
            "soft guidance. Markdown rendering on description and purpose "
            "deferred to CBM-redo signal."
        ),
        "rationale": (
            "Splitting purpose and description (rather than collapsing to one "
            "description field) preserves the Phase 1 output shape 1:1 with "
            "no data loss on the way in, separates the why (purpose, priority-"
            "test artifact) from the what (description, work content), and "
            "enables differentiated UI rendering. Optional notes captures "
            "consultant rationale (pattern-library reasoning, push-back "
            "trails) without conflating with client-facing content. No length "
            "caps because caps are easy to add via migration later and hard "
            "to relax once imposed; CBM redo will surface whether pathological "
            "inputs justify them. Case-insensitive name uniqueness within "
            "engagement prevents duplicate-domain confusion in v2's one-"
            "instance-per-engagement model."
        ),
        "alternatives_considered": (
            "Collapse purpose into description as the lead sentence (simpler "
            "but loses the field-level distinction Phase 1 produces). Make "
            "notes structured journal pattern with timestamped entries (ahead-"
            "of-need for v0.4; v0.5 candidate). Impose storage-level length "
            "caps now (premature constraint without real-use signal). Add "
            "mnemonic short_code field for 2-letter domain codes like MN/MR/"
            "CR/FU (tracked as PI-007 deferred to v0.5+)."
        ),
        "consequences": (
            "domain.md section 3.2 defines these seven fields with the "
            "validation rules above. Phase 1 Domain Inventory content flows "
            "into v2 with no field-mapping translation. CBM-redo authoring "
            "workflow uses the New Domain dialog to populate purpose and "
            "description as distinct fields. PI-007 captures short_code as "
            "future work."
        ),
    },
    {
        "identifier": "DEC-046",
        "title": "Parent-prefix field-naming convention for methodology entities (cross-spec rule)",
        "context": (
            "Generic field names like status, name, description appearing on "
            "multiple entity types create reference ambiguity when fields are "
            "discussed across entities (which status? which name?). The spec "
            "guide section 6 currently mandates bare status as the cross-spec "
            "convention, mirroring existing v2 governance entities (DEC, SES, "
            "RSK, PI, TOP, REF, CHR, STA). The domain schema-design "
            "conversation surfaced this as a friction point when establishing "
            "conventions that the next three methodology specs (entity, "
            "process, crm_candidate) will inherit."
        ),
        "decision": (
            "Adopt parent-prefix field naming for all four methodology "
            "entities in this workstream: all non-identifier and non-timestamp "
            "fields are prefixed with the parent entity name. For domain, this "
            "produces domain_name, domain_purpose, domain_description, "
            "domain_notes, domain_status. Identifier and timestamps also adopt "
            "the prefix for full convention consistency: domain_identifier, "
            "domain_created_at, domain_updated_at, domain_deleted_at. "
            "Convention scope: applies to common-or-could-be-common fields; "
            "fields that are genuinely entity-specific in nature would stay "
            "bare, though for domain v0.4 every field is common-or-could-be-"
            "common so all fields are prefixed. The convention is forward-"
            "only for the methodology workstream; governance-entity retrofit "
            "is tracked as PI-006."
        ),
        "rationale": (
            "The prefix disambiguates field references in cross-spec "
            "discussions (entity_status vs process_status vs domain_status is "
            "unambiguous; bare status requires context). The convention costs "
            "little for new entities — naming is a sunk cost paid once at "
            "design — and the value compounds as the entity count grows. "
            "Forward-only posture for methodology is safe because methodology "
            "entities are new in v0.4; retrofitting governance entities is a "
            "substantial migration that needs its own scoping (PI-006)."
        ),
        "alternatives_considered": (
            "Keep bare status, name, description per spec guide section 6 "
            "(preserves existing v2 norm but accepts the ambiguity as the "
            "entity count grows). Apply prefix only to enum/classification "
            "fields like status, leaving name/description bare (rejected as "
            "inconsistent — partial coverage invites reinterpretation). Apply "
            "prefix to all fields uniformly including those entity-specific "
            "by nature (rejected as overreaching when entity-specific fields "
            "are unambiguous on their own)."
        ),
        "consequences": (
            "All four methodology workstream specs (domain.md, entity.md, "
            "process.md, crm_candidate.md) use parent-prefix field naming. "
            "The spec guide section 6 needs amendment to reflect the new "
            "convention — flagged for the v0.4-build-planning conversation. "
            "Governance-entity retrofit (PI-006) becomes a v0.4-build-planning "
            "sizing question (pull into v0.4 scope or defer to v0.5+). The "
            "methodology/governance field-naming split signals 'this is "
            "methodology, this is governance' as a useful structural tell "
            "until PI-006 closes the gap."
        ),
    },
    {
        "identifier": "DEC-047",
        "title": "domain status lifecycle, propose-verify gate, and rejection-via-soft-delete posture",
        "context": (
            "Phase 1 of the evolved methodology has CRM Builder proposing "
            "domains and the client verifying them (Principle 4 — CRM Builder "
            "proposes, client verifies). The domain entity needs a status "
            "lifecycle that captures this engagement-scope flow without "
            "conflating engagement-scope state with deliberation state or "
            "with record-existence state."
        ),
        "decision": (
            "Adopt three status values for domain: candidate (default "
            "starter; CRM Builder proposed, awaiting client verification), "
            "confirmed (client-verified, in scope for the engagement), "
            "deferred (client-acknowledged real domain but out of current "
            "engagement scope). Implement a one-way propose-verify gate: "
            "candidate transitions to confirmed or deferred but not back to "
            "candidate from either; confirmed and deferred transition between "
            "each other freely. Rejection handled via soft-delete (DELETE "
            "sets domain_deleted_at; restorable via POST /restore) rather "
            "than a rejected status value. No archived status — soft-delete "
            "already covers retained-for-record-not-in-scope."
        ),
        "rationale": (
            "Three values cover the propose-verify happy path plus the "
            "acknowledged-but-not-now case without inventing values that "
            "duplicate soft-delete. The one-way gate makes propose-verify a "
            "meaningful engagement moment — if a consultant wants to "
            "fundamentally rethink a verified domain, the right action is "
            "editing content, not regressing status. The principle 'status "
            "tracks engagement-scope lifecycle; soft-delete tracks existence-"
            "in-the-record' is cross-spec applicable and downstream "
            "methodology specs adopt it unless they have substantive reason "
            "to deviate. The default-candidate starter affirms the spec "
            "guide section 6 'typical for evolving methodology entities' "
            "note."
        ),
        "alternatives_considered": (
            "Add rejected status value (rejected; duplicates soft-delete "
            "which already supports the show-deleted toggle and restore "
            "endpoint). Add archived status value (rejected; same "
            "duplication concern). Allow backflow to candidate (rejected; "
            "conflates engagement-scope state with deliberation state). "
            "Two-value lifecycle candidate/confirmed only (rejected; loses "
            "the deferred-but-real-domain distinction that Phase 1 needs at "
            "domain granularity, mirroring the process-level deferred-list "
            "pattern)."
        ),
        "consequences": (
            "domain.md section 3.4 specifies the three values, the "
            "transition matrix, and the soft-delete-handles-rejection "
            "posture. Server-side transition validation returns HTTP 422 on "
            "invalid transitions with an invalid_status_transition error "
            "body. Cross-spec consequence: downstream methodology specs "
            "adopt the candidate starter and the rejection-via-soft-delete "
            "posture unless they document a substantive deviation. CBM redo "
            "will surface whether the one-way gate creates friction; if so, "
            "v0.5 transition-map amendment opens regression paths."
        ),
    },
    {
        "identifier": "DEC-048",
        "title": (
            "domain relationship posture and {source}_{verb}_{target} "
            "relationship-kind naming convention"
        ),
        "context": (
            "domain is the foundational methodology entity that entity and "
            "process will reference. The domain schema-design conversation "
            "needs to settle (a) what relationships domain itself declares "
            "versus what its inbound targets declare, (b) what mechanism "
            "(direct FK vs references-entity edge vs hierarchy) those "
            "inbound relationships use, and (c) what naming convention "
            "applies to relationship-kind vocabulary entries involving "
            "methodology entities."
        ),
        "decision": (
            "domain has no outgoing relationships in v0.4: no FK fields to "
            "other entity types, no self-referential hierarchy, no source-"
            "side use of the references entity. Inbound relationships from "
            "entity and process are declared in those specs (source-side "
            "declaration, not target-side). Anticipated inbound kinds are "
            "listed informationally in domain.md section 3.3.2 "
            "(entity_scopes_to_domain via references-entity edge for many-"
            "to-many; process_belongs_to_domain via direct FK for many-to-"
            "one) but actual vocab.py registration and mechanism choice "
            "belong to entity.md and process.md. Cross-spec naming "
            "convention established here: relationship-kind values "
            "involving methodology entities use {source}_{verb}_{target} "
            "pattern (source entity name, verb phrase, target entity name) "
            "— e.g., entity_scopes_to_domain, process_belongs_to_domain. "
            "Forward-only for methodology vocab; governance vocabulary "
            "(cites, supersedes, etc.) retains its existing verb-phrase-"
            "only pattern."
        ),
        "rationale": (
            "Source-side declaration matches normal RDBMS modeling (the "
            "edge lives where the source is) and the verb_phrase reads "
            "source-first anyway (entity_scopes_to_domain — entity is the "
            "subject). The methodology workstream has multiple entities "
            "with similar verbs (entity_belongs_to_domain could collide "
            "with process_belongs_to_domain without source-prefixing), so "
            "prefixing the source disambiguates direction at read time and "
            "prevents collisions. No outgoing relationships in v0.4 "
            "reflects the explicit out-of-scope items in the workstream "
            "plan section 3.1 (no sub-domain hierarchy, no Cross-Domain "
            "Service distinction) and keeps the v0.4 schema thin."
        ),
        "alternatives_considered": (
            "Target-side declaration in domain.md (rejected; puts "
            "downstream-dependency declarations in upstream specs, inverts "
            "source-side ownership). domain.md commits authoritative "
            "mechanism choice for inbound edges (rejected; the choice "
            "belongs to source-side specs, and the cross-spec consistency "
            "check at v0.4-build planning is the appropriate gate). "
            "verb_phrase-only relationship-kind naming with no source "
            "prefix (rejected for methodology vocab because of collision "
            "risk; retained for governance vocab as forward-only posture)."
        ),
        "consequences": (
            "domain.md section 3.3 is target-side-observer-only. entity.md "
            "and process.md make the authoritative mechanism choices for "
            "entity_scopes_to_domain and process_belongs_to_domain "
            "respectively. The v0.4-build-planning conversation's cross-"
            "spec consistency check validates that the source-side "
            "mechanism choices align. Spec guide section 6 needs amendment "
            "to reflect the {source}_{verb}_{target} naming pattern for "
            "methodology vocab — flagged with the field-naming convention "
            "amendment under coordination with PI-006 at v0.4-build-"
            "planning. Existing governance vocab vocab.py entries (cites, "
            "supersedes) unchanged."
        ),
    },
    {
        "identifier": "DEC-049",
        "title": "domain API surface, UI defaults, and acceptance criteria for v0.4",
        "context": (
            "With identifier, fields, relationships, and lifecycle settled, "
            "the remaining v0.4 specifications for domain are the REST "
            "endpoint set, server-side validation behaviors, the desktop UI "
            "layout, and the testable acceptance criteria for build "
            "planning."
        ),
        "decision": (
            "Adopt the cross-spec default REST endpoint set with no "
            "deviations: GET /domains, GET /domains/{id}, POST /domains, "
            "PUT /domains/{id}, PATCH /domains/{id}, DELETE /domains/{id}, "
            "POST /domains/{id}/restore, GET /domains/next-identifier. "
            "Status-transition validation enforced server-side at the "
            "access layer returning HTTP 422 with invalid_status_transition "
            "error body on illegal transitions. List endpoint supports only "
            "?include_deleted=true in v0.4; additional filters deferred to "
            "CBM-redo signal. Adopt the spec guide default ListDetailPanel "
            "UI layout with no architectural deviations: new 'Methodology' "
            "sidebar group below 'Governance' (with domain first, entity/"
            "process/crm_candidate following in workstream order, all "
            "shipping together in v0.4); master pane columns Identifier/"
            "Name/Status/Updated sorted ascending by identifier; right-"
            "click context menu New/Edit/Delete/Restore per DEC-035 and "
            "DEC-036; detail pane fields in section 3.2 order with "
            "domain_notes under a collapsible 'Internal notes' header "
            "collapsed by default; CRUD dialogs via EntityCrudDialog "
            "subclasses. Acceptance criteria captured as 14 numbered "
            "testable statements covering schema migration, access-layer "
            "methods, REST endpoints, identifier auto-assignment "
            "concurrency, soft-delete/restore round-trip, UI structural "
            "elements, CRUD round-trip, file-watch refresh, and end-to-end "
            "CBM-redo Phase 1 authoring through the dialog."
        ),
        "rationale": (
            "No-deviation default endpoints minimize cross-spec complexity "
            "and reuse existing v2 patterns. Server-side transition "
            "validation prevents UI-only enforcement bugs from corrupting "
            "the engagement-scope state. Single ?include_deleted flag is "
            "the minimum that lets the show-deleted UI toggle work; "
            "further filters are speculative without real-use signal. "
            "Default UI layout fits domain's small-record-count, scalar-"
            "field, no-outgoing-relationship shape exactly — designing a "
            "custom layout would invent complexity without benefit. "
            "domain_notes collapsed-by-default reinforces field semantics "
            "(internal scratchpad, not client-facing) through UI "
            "affordance. Fourteen acceptance criteria covers the spec "
            "guide's ten typical categories with appropriate depth without "
            "over-fragmenting."
        ),
        "alternatives_considered": (
            "Add server-side ?domain_status=... filter to the list "
            "endpoint (rejected for v0.4; client-side filtering over 3-8 "
            "records is sufficient). Render domain_notes always-visible in "
            "the detail pane (rejected; collapsed-by-default's visual cue "
            "is cheap and reinforces 'internal' semantics). Different "
            "sidebar group label such as 'Implementation Content' or "
            "'Client Content' (rejected; 'Methodology' is already "
            "established in workstream documents and is the cleanest "
            "distinction from 'Governance'). Fewer than 10 acceptance "
            "criteria (rejected; spec guide section 7.1 requires at least "
            "10)."
        ),
        "consequences": (
            "domain.md sections 3.5 (API), 3.6 (UI), 3.7 (acceptance "
            "criteria) lock these specifications. v0.4 build planning "
            "translates the 14 acceptance criteria into specific test "
            "cases. The Methodology sidebar group is introduced as a "
            "single shipping unit in v0.4 containing all four methodology "
            "entity panels."
        ),
    },
]


# ---------------------------------------------------------------------------
# New planning items (PI-006, PI-007)
# ---------------------------------------------------------------------------

NEW_PIS = [
    {
        "identifier": "PI-006",
        "title": "Retrofit governance entities to parent-prefix field-naming convention",
        "item_type": "pending_work",
        "status": "Open",
        "description": (
            "DEC-046 establishes the parent-prefix field-naming convention "
            "for methodology entities forward-only; governance entities "
            "(DEC, SES, RSK, PI, TOP, REF, CHR, STA) retain bare field "
            "names (status, title, name, description, etc.) until this "
            "retrofit lands. Retrofit scope: Alembic migrations renaming "
            "columns on eight existing tables; access-layer method updates "
            "across crmbuilder-v2/src/crmbuilder_v2/access/; REST API "
            "serialization updates; MCP tool input/output updates; UI "
            "dialog updates (every QLineEdit, QComboBox, and table model "
            "column bound to a renamed field); DB-export JSON snapshot "
            "regeneration with rewriting of committed snapshots in git "
            "history; backward-compat considerations for any external "
            "scripts hitting the REST API or MCP. Substantial migration. "
            "The v0.4-build-planning conversation decides whether to pull "
            "this retrofit into v0.4 scope (significant additional work) "
            "or defer to v0.5+. The methodology workstream's specs ship "
            "with the new convention regardless of when this retrofit "
            "lands."
        ),
    },
    {
        "identifier": "PI-007",
        "title": (
            "domain.short_code field for mnemonic references and "
            "downstream identifier prefixes"
        ),
        "item_type": "pending_work",
        "status": "Open",
        "description": (
            "The existing CBM methodology uses 2-letter domain codes (MN "
            "for Mentoring, MR for Mentor Recruitment, CR for Client "
            "Recruiting, FU for Fundraising) as prefixes for process and "
            "entity identifiers (MN-INTAKE, MR-RECRUIT, etc.). The Phase 1 "
            "evolved-methodology interview guide section 7.2 says the "
            "Domain Inventory includes 'name in client's language and a "
            "structural code' but does not specify whether downstream "
            "process/entity codes continue to use mnemonic prefixes in "
            "the evolved methodology. DEC-045 defers domain_short_code "
            "from the v0.4 minimum-viable shape pending CBM-redo signal. "
            "If real-engagement Phase 3 work confirms that mnemonic "
            "prefixes still pull weight for human-readable process/entity "
            "identifier construction, a v0.5 schema migration adds "
            "domain_short_code (str, 2-4 uppercase letters, unique within "
            "engagement); the process and entity schemas adopt it for "
            "human-readable identifier prefixes alongside their numeric "
            "identifiers. If the evolved methodology converges on "
            "sequential identifiers without mnemonic prefixes, this PI "
            "closes as not-needed."
        ),
    },
]


# ---------------------------------------------------------------------------
# References — link each new decision to SES-012 via ``decided_in``
# ---------------------------------------------------------------------------

# SES-012 must exist (Doug wrote it through the New Session dialog at
# conversation close) before these references can be authored.
#
# Field-name convention: API uses the short forms (source_type, source_id,
# target_type, target_id, relationship); DB uses the long forms. Always use
# the short API-canonical forms in POST bodies. Matches the pattern in
# apply_ses_011_planning_records.py.
REFERENCES = [
    {
        "source_type": "decision",
        "source_id": dec["identifier"],
        "target_type": "session",
        "target_id": SESSION_ID,
        "relationship": "decided_in",
    }
    for dec in DECISIONS
]


# ---------------------------------------------------------------------------
# HTTP and helpers
# ---------------------------------------------------------------------------

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
        body_bytes = e.read().decode()
        try:
            payload = json.loads(body_bytes)
        except json.JSONDecodeError:
            payload = {"raw": body_bytes}
        return e.code, payload


def _log(label: str, status: int, payload: dict) -> bool:
    """Print result; return True on success-or-409, False on real error."""
    if status in (200, 201, 204):
        print(f"  ✓ {label} (HTTP {status})")
        return True
    if status == 409:
        print(f"  · {label} already present (HTTP 409) — skipping")
        return True
    errors = payload.get("errors") or payload.get("detail") or payload
    print(f"  ✗ {label} FAILED (HTTP {status}): {errors}", file=sys.stderr)
    return False


def main() -> int:
    ok = True

    # Pre-flight: check SES-012 exists. The references step fails badly otherwise.
    status, payload = _request("GET", f"/sessions/{SESSION_ID}")
    if status != 200:
        print(
            f"\n✗ Pre-flight failed: {SESSION_ID} not found (HTTP {status}).\n"
            f"  Write the session record through the v0.3 desktop New Session\n"
            f"  dialog before running this script. The session content is in\n"
            f"  the Claude.ai conversation that produced domain.md.\n",
            file=sys.stderr,
        )
        return 2
    print(f"✓ Pre-flight: {SESSION_ID} exists in the database.\n")

    print(f"=== Writing {len(DECISIONS)} decisions ===")
    for dec in DECISIONS:
        body = {**dec, "decision_date": DECISION_DATE, "status": "Active"}
        status, payload = _request("POST", "/decisions", body)
        ok &= _log(f"POST /decisions  {dec['identifier']}", status, payload)

    print(f"\n=== Writing {len(NEW_PIS)} new planning items ===")
    for pi in NEW_PIS:
        status, payload = _request("POST", "/planning-items", pi)
        ok &= _log(f"POST /planning-items  {pi['identifier']}", status, payload)

    print(f"\n=== Writing {len(REFERENCES)} references (decided_in → {SESSION_ID}) ===")
    for ref in REFERENCES:
        status, payload = _request("POST", "/references", ref)
        ok &= _log(
            f"POST /references  {ref['source_id']} decided_in {SESSION_ID}",
            status,
            payload,
        )

    print()
    if ok:
        print("✓ All operations complete.")
        return 0
    print("✗ One or more operations failed. See stderr for details.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
