#!/usr/bin/env python3
"""Write SES-011 governance records — methodology-schema-design workstream kickoff.

Six decisions (DEC-038 through DEC-043), one PI update (PI-001's fourth deferral),
four new planning items (PI-002 through PI-005), and six references linking each
new decision to SES-011 via ``decided_in``.

The session record SES-011 itself is **not** written by this script — Doug writes
it through the v0.3 desktop New Session dialog at the actual close of the planning
conversation, per the session-record-at-close pattern. This script runs *after*
SES-011 has been written through the dialog, so the ``decided_in`` references
linking DEC-038..DEC-043 to SES-011 can succeed.

Idempotent on re-run: each POST treats HTTP 409 conflict as already-present and
continues. PATCH for PI-001 is also safe to re-run (the body matches the desired
final state regardless of how many times PATCH fires).

Usage:
    cd crmbuilder-v2
    uv run python scripts/apply_ses_011_planning_records.py

The script reports each operation with its HTTP status and continues past 409s.
Exit code 0 on full success; non-zero only if a non-409 error is encountered.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8765"
DECISION_DATE = "05-11-26"
SESSION_ID = "SES-011"

# ---------------------------------------------------------------------------
# Decisions (DEC-038 through DEC-043)
# ---------------------------------------------------------------------------

DECISIONS = [
    {
        "identifier": "DEC-038",
        "title": "v0.4 redirect — methodology entity schema design as primary frame",
        "context": (
            "The committed v0.4 kickoff at ui-v0.4-planning-prompt.md framed v0.4 "
            "as 'deliberately open' and named four candidate buckets: PI-001 styling "
            "discharge (forcing function), v0.3 deferral polish (reference filtering, "
            "JSON diff, global search, keyboard shortcuts, exports, bulk ops), forward "
            "expansion (methodology entity schema design), and reimplementation "
            "workstreams (saved views / duplicate-check rules / workflow managers, "
            "blocked on EspoCRM's lack of public REST write paths). The kickoff also "
            "flagged production-use friction as the highest-weight signal for choosing "
            "among candidates and advised 'consider running v0.4 planning after some "
            "weeks of v0.3 production use.' The planning conversation that opened "
            "against this kickoff (SES-011) found production-use signal effectively "
            "empty: v0.3 closeout was complete only days earlier and SES-010 had captured "
            "closeout-and-kickoff-prep work itself rather than substantive governance use. "
            "Doug surfaced that the natural next step was preparing for a real-world test "
            "by redoing the CBM design — and CBM redo on v2 as system of record for both "
            "governance and methodology content requires v2 to have entity types for "
            "methodology content, which v0.3 does not have."
        ),
        "decision": (
            "v0.4's primary frame is **methodology entity schema design**. "
            "Bucket B (v0.3 deferral polish) is out except where it directly serves "
            "schema design. Bucket D (reimplementation) is out (constraint unchanged). "
            "PI-001 (styling) defers a fourth time per DEC-042. The path under (b) is "
            "**(b-α)**: this planning conversation pivots from 'producing the v0.4 PRD' "
            "to 'kicking off the methodology-schema-design workstream' because the "
            "original kickoff explicitly forbids designing schemas inline in a planning "
            "conversation. The schemas are designed in separate per-entity conversations; "
            "a later v0.4-build-planning conversation produces the v0.4 PRD, "
            "implementation plan, and slice build prompts from those specs. Scope "
            "philosophy is **minimum viable** — design schemas only for what CBM redo's "
            "evolved-methodology Phase 1 needs as content. CBM redo uses the **evolved "
            "methodology** (5-phase iteration-oriented restructure at "
            "PRDs/process/research/evolved-methodology/) rather than the original "
            "13-phase methodology — the evolved methodology is research-stage and needs "
            "real-world validation, the CBM live engagement is currently mid-stream under "
            "the original methodology making 'redo' under it semantically awkward, and the "
            "evolved Phase 1 interview guide v0.2 was already simulator-tested 04-30-26."
        ),
        "rationale": (
            "Routing v0.4 through methodology entity schema design lets the real-world "
            "CBM redo test exercise v2 on substantive content work rather than another "
            "iteration of polish on speculation about what features matter. (b-α) honors "
            "the original kickoff's discipline (don't rush schema design inside a planning "
            "conversation) while producing a useful deliverable now (the workstream "
            "kickoff). Minimum viable scope means the workstream is sized to ship enough "
            "v0.4 to enable CBM redo Phase 1, not sized to anticipate everything CBM redo "
            "might eventually need — Phase 2/3+ entity types get added in v0.5+ as real "
            "use validates each addition. Evolved methodology is the natural choice "
            "because the workstream and the methodology adoption pilot reinforce each "
            "other: the redo tests v2 as content store *and* tests whether evolved Phase 1 "
            "actually works on a real client."
        ),
        "alternatives_considered": (
            "**Stay with original kickoff frame (open-bucket).** Considered. Rejected "
            "because production-use signal was empty and choosing among buckets on "
            "speculation would build v0.4 against guesses about what mattered. "
            "**(a) CBM redo on v1 markdown methodology with v2 only for governance.** "
            "Considered. Rejected because it sidesteps the v2-as-methodology-content "
            "test, which is the load-bearing reason to do CBM redo now rather than "
            "wait. **(b-β) Placeholder v0.4 PRD with schema-spec slots filled later.** "
            "Considered. Rejected because the PRD would be a skeleton with too many "
            "TBDs to be useful as guidance. **(b-γ) Scope-only inline schema design "
            "in this conversation.** Considered. Rejected because it violates the "
            "original kickoff's 'does not execute schema design inline' constraint and "
            "because half-designed schemas commit to shapes that later phases want to "
            "revisit. **Big-design-up-front (all 8-10 methodology entity types).** "
            "Considered. Rejected because it commits 8-10 schema designs ahead of any "
            "real use validating any of them and pushes v0.4 ship out far enough that "
            "CBM redo starts much later — defeating the real-world-test-soon goal. "
            "**Original 13-phase methodology for CBM redo.** Considered. Rejected "
            "because CBM is currently mid-execution under the original methodology, "
            "making 'redo' under it confusing in practice, and because original Phase 1 "
            "(Master PRD) produces a different inventory (candidate entities and candidate "
            "personas as formal Phase 1 outputs) than evolved Phase 1."
        ),
        "consequences": (
            "v0.4 ships methodology entity types instead of UI polish. The workstream "
            "produces four schema-design conversations (one per entity type, sequential), "
            "followed by a single v0.4-build-planning conversation that integrates them "
            "into a v0.4 PRD plus implementation plan plus slice prompts, followed by "
            "Claude Code execution of those prompts. CBM redo Phase 1 starts after v0.4 "
            "ships and exercises evolved methodology against real CBM material. Real-world "
            "friction surfaced during the redo informs v0.5 scope. If the redo surfaces "
            "evidence that the evolved methodology doesn't work on this client, adoption "
            "is reconsidered."
        ),
    },
    {
        "identifier": "DEC-039",
        "title": "Minimum entity inventory and multi-tenancy posture",
        "context": (
            "DEC-038 committed v0.4 to methodology entity schema design under minimum-"
            "viable scope. The concrete inventory question — which entity types — and "
            "the multi-tenancy posture — does one v2 instance host multiple engagements "
            "or one per engagement — both needed settling before the workstream could "
            "scope its per-entity-type conversations. Evolved Phase 1 produces four "
            "outputs (Mission Statement, Domain Inventory, Prioritized Backbone, Initial "
            "CRM Candidate Set) of which Mission Statement maps to the existing Charter "
            "entity (versioned-replace + Make Current pattern); the others need new entity "
            "types. Entity (the CRM-modeled noun like Contact / Account / Session) is not "
            "a formal Phase 1 output but the evolved Phase 1 interview guide v0.2 explicitly "
            "states (line 62) that 'Phase 1 may surface entity names as nouns the client "
            "uses but does not produce Entity PRDs.' Persona is not a Phase 1 output and "
            "the guide explicitly excludes persona elicitation from Phase 1."
        ),
        "decision": (
            "v0.4 ships **four new entity types**: ``domain``, ``entity``, ``process``, "
            "``crm_candidate``. **Persona deferred to v0.5+** per PI-003. **Field, "
            "requirement, manual-config item, test spec deferred to v0.5+** per PI-004. "
            "**Full process schema growth deferred to v0.5+** per PI-005. CBM's Mission "
            "Statement uses the existing Charter entity in CBM's v2 instance — no new "
            "entity type for Mission Statement. **Multi-tenancy posture: one v2 instance "
            "per engagement.** The original v0.4 kickoff's 'no fundamental storage "
            "architecture changes' rule puts multi-tenant v2 out of scope for v0.4. "
            "CBM gets its own v2 instance (separate SQLite, separate API port); v0.4 "
            "ships entity types into v2's codebase and both instances pick them up."
        ),
        "rationale": (
            "Entity is included in the inventory despite not being a formal Phase 1 output "
            "because real Phase 1 conversations naturally surface entity vocabulary (per "
            "the interview guide's line 62) and if v2 has no entity type those names land "
            "as loose nouns in session notes or process descriptions, forcing retrofit at "
            "the Phase 3 boundary — exactly the kind of friction that nudges practitioners "
            "back to markdown. A thin entity schema (name, description, status) in v0.4 "
            "captures Phase 1 surfacing; Phase 3 grows the schema in v0.5+ to add fields, "
            "relationships, full PRD content. Persona is *not* analogously included because "
            "the Phase 1 interview guide explicitly excludes persona elicitation in Phase 1 "
            "— persona context comes from pre-engagement reading of operational role "
            "definitions, used as consultant background rather than captured as records. "
            "Including persona in v0.4 would mean v2 has a feature Phase 1 work doesn't "
            "exercise, defeating real-world-test feedback. Per-engagement v2 instances "
            "(rather than multi-tenancy) respect the kickoff's storage-architecture "
            "constraint and match v2's already-implicit single-engagement scope. Charter "
            "hosting CBM's Mission Statement (rather than a new mission_statement entity) "
            "reuses existing versioned-replace + Make Current semantics that fit the "
            "'drafted by CRM Builder, verified by client' Phase 1 pattern exactly."
        ),
        "alternatives_considered": (
            "**Big-design inventory (8-10 entity types in v0.4).** Considered. Rejected "
            "per DEC-038's minimum-viable scope philosophy. **Three entity types (domain, "
            "process, crm_candidate), entity in v0.5.** Considered. Rejected on Doug's "
            "observation that picking CRM candidates without entity vocabulary in v0.4 "
            "creates internal incoherence — and the Phase 1 guide's line 62 confirms entity "
            "names surface naturally in Phase 1 conversation. **Persona included.** "
            "Considered. Rejected because Phase 1 guide explicitly excludes persona "
            "elicitation; including persona would deliver a feature that Phase 1 work does "
            "not exercise. **Multi-tenant v2 with a client/engagement entity scoping all "
            "data.** Considered. Rejected because it crosses the kickoff's no-architecture-"
            "changes line and adds complexity not earned by current need (CBM is the only "
            "second engagement on the horizon). **Mission Statement as new entity type.** "
            "Considered. Rejected because Charter's versioned-replace + Make Current "
            "pattern fits the Mission Statement lifecycle exactly and per-engagement "
            "instances make 'whose Charter' unambiguous."
        ),
        "consequences": (
            "The schema-design workstream covers four entity types: domain, entity, "
            "process, crm_candidate. Persona, field, requirement, manual-config, "
            "test-spec, and full process schema growth are tracked as planning items "
            "for v0.5+. CBM gets its own v2 instance pointing at a separate SQLite and "
            "API port; spin-up procedure for the second instance is part of v0.4 build "
            "planning. Mission Statement work in CBM uses Charter; CBM's Charter is "
            "different content from the CRM Builder project's Charter but the same "
            "entity type. No multi-tenant complexity; no client/engagement scoping FK."
        ),
    },
    {
        "identifier": "DEC-040",
        "title": "Schema-design workstream structure",
        "context": (
            "DEC-038 and DEC-039 committed v0.4 to a methodology entity schema design "
            "workstream covering four entity types under (b-α) path. The workstream's "
            "structure — what each schema-design conversation produces, in what order, "
            "and how the four specs feed v0.4 build — needed settling before the per-"
            "entity kickoff prompts could be authored."
        ),
        "decision": (
            "Each per-entity schema-design conversation produces **design only**: a "
            "schema specification document at "
            "``PRDs/product/crmbuilder-v2/methodology-schema-specs/{entity_type}.md`` "
            "conforming to the template in ``methodology-entity-schema-spec-guide.md``, "
            "plus the DEC-NNN decisions made during the conversation, plus a SES-NNN "
            "session record written at conversation close. **No build prompts in "
            "schema-design conversations.** Build prompts are authored in a single "
            "**v0.4-build-planning conversation** that takes all four schema specs as "
            "input and produces the v0.4 PRD, implementation plan, and slice build "
            "prompts. **Conversation order: domain → entity → process → crm_candidate, "
            "sequential, no parallelism.** A **schema-spec methodology guide** at "
            "``methodology-entity-schema-spec-guide.md`` defines the template every "
            "schema spec follows; this conversation produces the guide alongside the "
            "four per-entity kickoff prompts and the workstream plan. UI considerations "
            "in section 3.6 of the spec template use the **template-with-deviation-by-"
            "justification** pattern: a default panel layout is given, and a schema may "
            "diverge with explicit rationale."
        ),
        "rationale": (
            "Design-only conversations stay focused on schema design rather than "
            "compromising on the design side to ship a build prompt. Separating build "
            "planning into its own conversation lets cross-cutting v0.4 concerns "
            "(migration sequencing, sidebar ordering, About bump, README, test target, "
            "closeout) be designed with all four schemas visible at once rather than "
            "scattered across four conversations. The chosen order respects dependencies: "
            "domain is foundational (entity and process reference it); entity is "
            "independent of process and gets a clean design pass before process complicates "
            "the picture; process is the most relational (touches both domain and entity) "
            "so designing it third means both referents already exist; crm_candidate is "
            "fully independent and acts as a coda. A schema-spec methodology guide "
            "produces structural consistency across the four specs — without it, the "
            "first schema-design conversation would invent conventions the next three "
            "would have to retrofit. Template-with-deviation for UI considerations "
            "produces visual consistency across the four new panels and makes the v0.4 "
            "build slice prompts simpler, while still allowing per-schema deviation where "
            "justified."
        ),
        "alternatives_considered": (
            "**Design + build prompt per schema-design conversation (option 2).** "
            "Considered. Rejected because cross-cutting v0.4 concerns benefit from being "
            "designed once with all four schemas visible, and because design quality "
            "tends to compromise when build delivery is on the table. **Design + "
            "integration analysis but no build prompts (option 3).** Considered. "
            "Rejected as a middle-ground that adds the integration analysis burden to "
            "schema-design conversations without gaining the design-focus benefit of "
            "option 1. **Order: crm_candidate first as warmup.** Considered. Rejected "
            "because warmup-first delays testing the spec methodology against relational "
            "complexity — methodology gaps wouldn't surface until conversation 2 and would "
            "retroactively affect the warmup. **No schema-spec methodology guide; each "
            "conversation invents its own structure.** Considered. Rejected because "
            "inconsistent spec shapes would force the v0.4-build-planning conversation "
            "to translate between formats. **No UI template; each schema designs from "
            "scratch.** Considered. Rejected because consistent panel patterns are "
            "themselves a usability feature, and divergent layouts mean four bespoke build "
            "slices instead of four uniform ones."
        ),
        "consequences": (
            "Six future conversations follow this one: four schema-design conversations "
            "(domain, entity, process, crm_candidate) plus a v0.4-build-planning "
            "conversation plus a v0.4-build closeout conversation when the slices ship. "
            "Each schema-design conversation reads the workstream plan, the spec "
            "methodology guide, prior schema specs in the same workstream, and its own "
            "per-entity kickoff prompt before opening its first architectural question. "
            "The v0.4-build-planning conversation's first task is the cross-spec "
            "consistency check defined in section 7.2 of the spec methodology guide."
        ),
    },
    {
        "identifier": "DEC-041",
        "title": "Existing v0.4 kickoff supersession — in-place marking",
        "context": (
            "The committed v0.4 kickoff at ``PRDs/product/crmbuilder-v2/ui-v0.4-planning-"
            "prompt.md`` (Last Updated 05-10-26 00:30) describes a v0.4 frame that this "
            "planning conversation redirected. The kickoff is cited by name in SES-010's "
            "``artifacts_produced``. The redirection needed an explicit supersession "
            "treatment so future readers don't get confused about which document drives "
            "the work."
        ),
        "decision": (
            "**Mark in place.** A supersession header is added at the top of the existing "
            "kickoff: 'SUPERSEDED 05-11-26 by methodology-schema-workstream-plan.md — "
            "this kickoff described a v0.4 frame that was redirected during planning. "
            "See workstream plan for the new direction. Retained for history.' The file "
            "stays at its original path; SES-010's reference remains valid."
        ),
        "rationale": (
            "In-place marking keeps SES-010's ``artifacts_produced`` reference valid "
            "without manual stitching. Future archaeology of 'how did v0.4 actually "
            "evolve?' lands at the original kickoff, sees the supersession header, "
            "follows the link to the workstream plan — clean breadcrumb. v2 governance "
            "uses this pattern elsewhere (supplemental decisions reference predecessors "
            "in place rather than moving them)."
        ),
        "alternatives_considered": (
            "**Delete the file.** Rejected — invalidates SES-010's reference, breaks "
            "any other inbound paths. **Archive to PRDs/product/crmbuilder-v2/"
            "superseded/.** Rejected — preserves the file but still breaks paths; the "
            "compromise gains nothing over in-place marking. **No supersession; let the "
            "workstream plan implicitly replace it.** Rejected — future readers would "
            "hit the kickoff and not know it's stale."
        ),
        "consequences": (
            "Existing kickoff carries a supersession header pointing to the workstream "
            "plan. SES-010's ``artifacts_produced`` reference continues to resolve. "
            "Future planning conversations that hit the kickoff are routed to the "
            "workstream plan via the header note."
        ),
    },
    {
        "identifier": "DEC-042",
        "title": "PI-001 fourth deferral with CBM-redo-friction trigger",
        "context": (
            "PI-001 (full styling design pass) has been deferred three times — DEC-024 "
            "(v0.1→v0.2), DEC-026 (v0.2→v0.3), DEC-037 (v0.3→future). The original v0.4 "
            "kickoff treated PI-001 as a forcing function: v0.4 must engage it explicitly "
            "either by adopting it as primary frame, including partial styling, or making "
            "a fourth deferral explicit with a new tracking mechanism plus rationale. "
            "With schema design as v0.4's primary frame (DEC-038) and minimum-viable "
            "scope precluding partial styling carve-ins (DEC-039), the only option left "
            "is fourth deferral — and the kickoff requires that deferral to come with a "
            "new tracking mechanism."
        ),
        "decision": (
            "**PI-001 defers a fourth time with a CBM-redo-friction trigger mechanism.** "
            "Rationale: methodology entity schema design takes the v0.4 slot; styling "
            "continues to be lower-priority than enabling CBM redo to run on v2 as "
            "content system of record. **Trigger mechanism:** if CBM redo Phase 1 "
            "(running against the four new methodology entity panels delivered in v0.4) "
            "surfaces visual friction on any of those panels, PI-001 gets pulled to v0.5 "
            "ahead of any other v0.5 candidate, regardless of v0.5 planning's other "
            "priorities. 'Visual friction' is intentionally fuzzy — Doug's judgment as "
            "the consultant running the redo determines whether something he sees while "
            "working bugs him enough to count. PI-001's record is updated to reflect "
            "deferral #4 and cite this decision."
        ),
        "rationale": (
            "Tying PI-001's priority to actual real-world evidence aligns with the "
            "kickoff's own surfaced principle (production-use friction is the highest-"
            "weight signal). The trigger is observable (Doug working in v0.4 panels) "
            "rather than calendar-based, so future planning conversations have a concrete "
            "signal to act on rather than asking 'did anything important happen with "
            "styling lately?' A simple deferral with no trigger (option α) is honest but "
            "passive. A hard backstop (option γ, 'must ship by v0.5 or v0.6') assumes we "
            "know now that styling will land within two more releases — we don't. "
            "Fuzzy-trigger sidesteps the precision problem; Doug's judgment is the right "
            "calibration tool because he's the consumer of the friction."
        ),
        "alternatives_considered": (
            "**(α) Simple tracking — DEC-038 records deferral, PI-001 status updated, "
            "v0.5 planning's first architectural question must be PI-001 disposition.** "
            "Rejected — passive; doesn't tie styling priority to evidence. **(γ) Hard "
            "backstop — PI-001 must ship in v0.5 or v0.6.** Rejected — imposes a "
            "calendar cap that may not match what real use actually wants. **Discharge "
            "PI-001 in v0.4 as primary frame.** Rejected per DEC-038. **Discharge "
            "PI-001 in v0.4 as partial work alongside schema design.** Rejected per "
            "DEC-039's minimum-viable scope philosophy."
        ),
        "consequences": (
            "PI-001's record is patched to reflect fourth deferral and cite DEC-042. "
            "Future v0.5 planning includes PI-001 disposition as an explicit candidate. "
            "If CBM redo Phase 1 generates visual friction on the new methodology panels, "
            "Doug's signal pulls PI-001 to v0.5. If CBM redo runs smoothly visually, "
            "PI-001 may continue to defer — and that's evidence too."
        ),
    },
    {
        "identifier": "DEC-043",
        "title": "SES-010 identifier-asymmetry resolution",
        "context": (
            "SES-010 documented a friction: v2's desktop dialogs auto-assign identifiers "
            "via compute_next_*_identifier helpers, hiding identifier computation from "
            "the user, but ``POST /<entity>`` requires the identifier in the request "
            "body, so direct-API consumers (curl, MCP, scripts) hit "
            "``request_validation_error: body.identifier — Field required`` if they don't "
            "compute and supply it. The original v0.4 kickoff named three resolution "
            "options: (A) document only (already in place via post-SES-010 CLAUDE.md "
            "updates), (B) add ``GET /<entity>/next-identifier`` helper endpoints, "
            "(C) make ``identifier`` optional in POST bodies with server-side auto-"
            "assignment on omission. v0.4 adds four new prefixed-identifier entity types "
            "(domain, entity, process, crm_candidate), each inheriting the asymmetry "
            "unless resolved."
        ),
        "decision": (
            "v0.4 build engages option **(B) for all twelve prefixed-identifier entity "
            "types** — the four new ones (DOM, ENT, PROC, CRM working assumptions) plus "
            "retroactive helpers on the existing prefixed entity types (decision SES, "
            "risk, planning-item, topic, reference, charter version, status version). "
            "**Option (C) is tracked as PI-002** — making ``identifier`` optional in "
            "POST bodies — as a future ergonomic improvement that needs more design "
            "(default-vs-required ambiguity for clients that want to specify identifier). "
            "Helper endpoints follow the path convention ``GET /<plural>/next-identifier`` "
            "and return the next available identifier for that entity type computed via "
            "the existing access-layer pattern."
        ),
        "rationale": (
            "Option (B) fits the kickoff's 'additive endpoints required by new write "
            "surfaces' exception cleanly — new endpoints, no changes to existing endpoint "
            "contracts. Retrofitting existing entities matters because inconsistency is "
            "its own friction: a consultant who learns ``GET /domains/next-identifier`` "
            "works will reasonably expect ``GET /decisions/next-identifier`` to work too, "
            "and a 404 is worse UX than no helpers anywhere. Retrofit cost is small "
            "(~10 lines per endpoint), small fraction of v0.4 build scope. Option (C) is "
            "the cleaner end state but crosses into changing existing endpoint contracts "
            "(POST body schema changes), which is gray-area under the kickoff's 'doesn't "
            "alter v0.3's storage shape' rule and deserves its own design pass — hence "
            "the PI rather than inclusion in v0.4."
        ),
        "alternatives_considered": (
            "**(1) Defer entirely — v0.4 ships no helpers, new four inherit documented "
            "asymmetry.** Rejected — multiplies the friction by four exactly when CBM "
            "redo's direct-API and MCP patterns will hit it most. **(2) (B) for new four "
            "only, existing eight remain documented-only.** Rejected — creates "
            "inconsistent API surface; consultant expectation breaks. **(C) inline in "
            "v0.4 (POST body schema change).** Rejected — gray-area under kickoff "
            "constraints, deserves dedicated design pass, tracked as PI-002 instead."
        ),
        "consequences": (
            "v0.4 build includes ``GET /<plural>/next-identifier`` endpoints for all 12 "
            "prefixed entity types (4 new, 8 retrofitted). Helper-endpoint test coverage "
            "is part of v0.4's test target. CLAUDE.md's post-SES-010 documentation of "
            "the asymmetry gets updated to reflect resolution after v0.4 ships. PI-002 "
            "carries forward option (C) for future design."
        ),
    },
]

# ---------------------------------------------------------------------------
# Planning items — one update (PI-001) and four new (PI-002..PI-005)
# ---------------------------------------------------------------------------

PI_001_PATCH = {
    "description": (
        "Full styling design pass per DEC-024, deferred FOUR TIMES: v0.1→v0.2 (DEC-024), "
        "v0.2→v0.3 (DEC-026), v0.3→future (DEC-037), v0.4→v0.5+ with CBM-redo-friction "
        "trigger (DEC-042). The pass establishes a coherent visual language for the v2 "
        "desktop application: typography hierarchy, accent colors beyond the navy stub "
        "(#1F3864), error/warning/info states, button hierarchy, dialog framing, table "
        "row spacing, and accessibility considerations. **Trigger mechanism (per "
        "DEC-042):** if CBM redo Phase 1 — running against the four new methodology "
        "entity panels delivered in v0.4 (domain, entity, process, crm_candidate) — "
        "surfaces visual friction on any of those panels, PI-001 gets pulled to v0.5 "
        "ahead of any other v0.5 candidate, regardless of v0.5 planning's other "
        "priorities. 'Visual friction' is intentionally fuzzy: Doug's judgment as the "
        "consultant running the redo determines whether something he sees while working "
        "bugs him enough to count. If CBM redo runs smoothly visually, PI-001 may "
        "continue to defer — that's evidence too."
    ),
}

NEW_PIS = [
    {
        "identifier": "PI-002",
        "title": "Make `identifier` optional in POST bodies (SES-010 option C)",
        "item_type": "pending_work",
        "status": "Open",
        "description": (
            "DEC-043 resolved the SES-010 identifier-asymmetry friction via option (B) — "
            "``GET /<entity>/next-identifier`` helpers for all twelve prefixed entity "
            "types. Option (C) — making ``identifier`` optional in POST bodies with "
            "server-side auto-assignment on omission — is the cleaner end state but was "
            "deferred from v0.4 because it changes existing endpoint contracts (gray-area "
            "under the kickoff's 'doesn't alter v0.3's storage shape' rule) and deserves "
            "its own design pass. Open design questions: (1) how to disambiguate "
            "client-omitted identifier (auto-assign) from client-specified-empty-string "
            "identifier (validation error)? (2) does this apply to versioned entity types "
            "like charter and status, whose identifiers are version numbers? (3) does the "
            "MCP server need any change beyond what the API change implies? Target "
            "release: v0.5 or later, depending on scope competition."
        ),
    },
    {
        "identifier": "PI-003",
        "title": "Persona entity type for v0.5+ (deferred from v0.4 minimum-viable inventory)",
        "item_type": "pending_work",
        "status": "Open",
        "description": (
            "DEC-039 deferred persona from v0.4's minimum-viable inventory because evolved "
            "Phase 1's interview guide v0.2 explicitly excludes persona elicitation in "
            "Phase 1 — persona context comes from pre-engagement reading of operational "
            "role definitions, used as consultant background rather than captured as "
            "records. Phase 2 or 3 of the evolved methodology may surface persona records "
            "(actors performing processes, role-based access boundaries). The persona "
            "entity type design should follow the workstream pattern (one Claude.ai "
            "conversation produces the schema spec, design-only, separate from build). "
            "Target release: v0.5+, conditional on CBM redo Phase 2 or 3 surfacing need."
        ),
    },
    {
        "identifier": "PI-004",
        "title": "Additional methodology entity types for v0.5+: field, requirement, manual_config, test_spec",
        "item_type": "pending_work",
        "status": "Open",
        "description": (
            "DEC-039 deferred fields, requirements, manual-config items, and test specs "
            "from v0.4's minimum-viable inventory. These are Phase 3+ entity types in "
            "the evolved methodology (Iteration Build and Deploy through Engagement "
            "Closure and Adoption). Each will need its own schema-design conversation "
            "following the workstream pattern established in v0.4. Field is the most "
            "urgent of the four because entity (shipped thin in v0.4) gains real utility "
            "only when fields can attach. Likely v0.5 ships field; later releases ship "
            "the rest. Target release: v0.5+ for field; v0.6+ for the rest, conditional "
            "on CBM redo progression and v2 patterns established in earlier releases."
        ),
    },
    {
        "identifier": "PI-005",
        "title": "Process schema growth beyond Phase 1 thin shape (full process definition)",
        "item_type": "pending_work",
        "status": "Open",
        "description": (
            "DEC-039 ships process in v0.4 with a thin Phase-1-only schema: identifier, "
            "name, brief description, priority classification, domain reference, "
            "process-to-process connections. Phase 3 of the evolved methodology (Iteration "
            "Build and Deploy) produces full Process Documents with steps, actors "
            "(personas), entity-field touches, triggers, outcomes, edge cases. Growing "
            "process's schema to host this content is v0.5+ work that depends on field "
            "(PI-004) and persona (PI-003) existing as records. Likely a migration story "
            "rather than re-design (thin schema designed with growth in mind), but the "
            "migration scope is non-trivial. Target release: v0.5+ after persona and "
            "field land, conditional on CBM redo reaching Phase 3."
        ),
    },
]


# ---------------------------------------------------------------------------
# References — link each new decision to SES-011 via ``decided_in``
# ---------------------------------------------------------------------------

# SES-011 must exist (Doug wrote it through the New Session dialog at conversation
# close) before these references can be authored.
REFERENCES = [
    {
        "source_entity_type": "decision",
        "source_identifier": dec["identifier"],
        "target_entity_type": "session",
        "target_identifier": SESSION_ID,
        "relationship_kind": "decided_in",
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

    # Pre-flight: check SES-011 exists. The references step fails badly otherwise.
    status, payload = _request("GET", f"/sessions/{SESSION_ID}")
    if status != 200:
        print(
            f"\n✗ Pre-flight failed: {SESSION_ID} not found (HTTP {status}).\n"
            f"  Write the session record through the v0.3 desktop New Session dialog\n"
            f"  before running this script. See methodology-schema-workstream-plan.md\n"
            f"  section 8.3 for the session-record-at-close pattern.\n",
            file=sys.stderr,
        )
        return 2
    print(f"✓ Pre-flight: {SESSION_ID} exists in the database.\n")

    print(f"=== Writing {len(DECISIONS)} decisions ===")
    for dec in DECISIONS:
        body = {**dec, "decision_date": DECISION_DATE, "status": "Active"}
        status, payload = _request("POST", "/decisions", body)
        ok &= _log(f"POST /decisions  {dec['identifier']}", status, payload)

    print(f"\n=== Patching PI-001 (fourth deferral) ===")
    status, payload = _request("PATCH", "/planning-items/PI-001", PI_001_PATCH)
    ok &= _log("PATCH /planning-items/PI-001", status, payload)

    print(f"\n=== Writing {len(NEW_PIS)} new planning items ===")
    for pi in NEW_PIS:
        status, payload = _request("POST", "/planning-items", pi)
        ok &= _log(f"POST /planning-items  {pi['identifier']}", status, payload)

    print(f"\n=== Writing {len(REFERENCES)} references (decided_in → {SESSION_ID}) ===")
    for ref in REFERENCES:
        status, payload = _request("POST", "/references", ref)
        ok &= _log(
            f"POST /references  {ref['source_identifier']} decided_in {SESSION_ID}",
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
