# Domain Sub-Domain Hierarchy Amendment — Planning Conversation Kickoff

**Last Updated:** 05-20-26
**Status:** Ready to run — open as a fresh Claude.ai conversation
**Operating mode:** ARCHITECTURE (design work; eight-element consequential decision template for each architectural choice)
**Companion inputs:** `methodology-schemas-cbm-paper-test-findings.md` (Finding 2 — the BLOCKING finding this workstream discharges) and `methodology-schema-specs/domain.md` (the spec being amended).

---

## Purpose

Produce the design, slice plan, and Claude Code prompts for amending the v0.4 `domain` schema with a nullable `domain_parent_identifier` self-FK so that a domain can declare a parent domain (sub-domain hierarchy). This is the single Pass-1-BLOCKING gap the methodology-schemas CBM-content paper-test identified: CBM's Client Recruiting (CR) domain is "organized into four sub-domains" (Partner, Marketing, Events, Reactivation), and v0.4's flat `domain` schema cannot represent that structure. CBM redo Phase 1 is gated on this amendment shipping.

The decision to make this amendment is already settled — it does not get re-litigated here. What this conversation decides is *how* to build it: the release vehicle, the handful of genuine schema/UI design forks, the slice breakdown, and the per-slice build prompts.

The output of this conversation is:

1. A new planning item **PI-022 in the CRMBUILDER engagement** scoping the workstream (the dogfood is where v2 product governance lives — see "Engagement routing" below).
2. A slice plan committed as a Markdown document at `PRDs/product/crmbuilder-v2/domain-subdomain-hierarchy-slice-plan.md`.
3. One `CLAUDE-CODE-PROMPT-*` file per slice committed to `PRDs/product/crmbuilder-v2/prompts/`.
4. A session record (SES-046 in CRMBUILDER) plus the decisions captured at close-out via the standard `apply_close_out.py` pattern.

The build conversations that execute the slices open separately, after this planning conversation closes and its close-out applies.

---

## Origin and engagement routing — read carefully

This workstream was surfaced *by* the CBM paper-test, whose governance records live in the **CBM engagement** database:

- **CBM `SES-001`** — "Methodology schemas — CBM content paper-test" (the paper-test session).
- **CBM `DEC-001`** — "Paper-test single decision: amend `domain` with `domain_parent_identifier` self-FK for sub-domain hierarchy before CBM redo Phase 1 opens." This is the settled decision; do not re-open it.
- **CBM `PI-001`** — "`domain_parent_identifier` self-FK on `domain` for sub-domain hierarchy." This is the motivating planning item. Its description already sketches the amendment scope, acceptance criteria, and a probable 2–3 slice shape — treat it as the requirements brief for this conversation, not as a record to mutate.

Those three records are CBM-engagement records and stay there. **The amendment itself is v2 product infrastructure — it changes the `domain` schema that every engagement shares — so its workstream governance (PI-022, SES-046, DEC-117…) is authored in the CRMBUILDER dogfood engagement**, exactly as the multi-tenancy routing fix did (PI-018 / SES-044 / DEC-108+ in CRMBUILDER). Because cross-engagement references are not supported (per the multi-tenancy investigation's "what I did not do"), the CRMBUILDER PI-022 record cites the CBM `PI-001` / `DEC-001` / `SES-001` **textually by identifier-and-engagement** in its description — not via a refs-table edge.

---

## Read first

1. `crmbuilder/CLAUDE.md` — v2 build governance, commit conventions, the `{data, meta, errors}` envelope, prefixed-identifier client-side computation. Confirm with Doug which CLAUDE.md files to load at conversation open (default: crmbuilder root; CBM root is not needed for product schema work).
2. `PRDs/product/crmbuilder-v2/methodology-schemas-cbm-paper-test-findings.md` — **Finding 2** (§2) is the BLOCKING finding; §4 "The single decision" states the amendment shape and the sequence. The amendment paragraph in Finding 2 and the PI-001 description are the requirements.
3. `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` end-to-end, with attention to:
   - **§3.3.4 Hierarchy** — the deferral being reversed (current text: "`domain` does not use the self-referential parent-child hierarchy pattern in v0.4 … the v0.5 schema migration adds a `domain_parent_identifier` self-FK following the existing `topic.parent_topic` pattern"). The amendment makes this real.
   - **§3.2 Fields**, **§3.5 API Surface**, **§3.6 UI Considerations**, **§3.7 Acceptance Criteria** — the sections the amendment touches and the acceptance-criteria pattern to follow.
4. **The `topic.parent_topic` pattern** — this is the existing, shipped implementation the amendment mirrors. Read it so the design copies a proven shape rather than inventing one:
   - Migration precedent + domain table: `crmbuilder-v2/migrations/versions/0007_v0_4_create_domains_table.py` (the table to alter); latest migration is `0010_v0_4_create_crm_candidates_table.py`, so the new migration is `0011_*`.
   - Model: `crmbuilder-v2/src/crmbuilder_v2/access/models.py` (topic's `parent_topic` field is the template; domain model lives here too).
   - Access/repository validation: `crmbuilder-v2/src/crmbuilder_v2/access/repositories/topics.py` (parent-existence + no-self-loop validation) vs the file to edit, `crmbuilder-v2/src/crmbuilder_v2/access/repositories/domain.py`.
   - API: `crmbuilder-v2/src/crmbuilder_v2/api/routers/topics.py` and `api/schemas.py` (note the write-key `parent_topic` vs read-key `parent_topic_identifier` asymmetry) vs the domains router to edit.
   - UI: `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/_topic_schema.py`, `topic_create.py`, `topic_edit.py`, `ui/widgets/hierarchical_picker.py`, `ui/panels/topics.py` vs the domain equivalents `ui/dialogs/_domain_schema.py`, `ui/dialogs/domain_crud.py`, `ui/panels/domains.py`.

---

## Pre-flight

1. **Active engagement is CRMBUILDER.** This is v2 product work; governance records go in the dogfood, not CBM. Verify via `curl -s http://127.0.0.1:8765/admin/connection` → `data.engagement_code == "CRMBUILDER"`. If it shows CBM, switch via the desktop UI's Engagements panel before starting. (The multi-tenancy fix's `/admin/connection` endpoint, DEC-116, exists specifically to make this check trivial.)
2. **API is running and routed to CRMBUILDER.db.** Verify: `curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), '- latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"` → expect `44 - latest: SES-045`. If the API is down, ask Doug to start it (recovery sequence in `CLAUDE-CODE-PROMPT-apply-close-out-ses-044.md` step 6a); do not start it yourself.
3. **Working trees clean in both repos.** This conversation produces design documents and Claude Code prompts only — no source code changes — so the gate is mostly so close-out commits land cleanly.
4. **`v2.db` / engagement DBs at Alembic head**, full v2 suite green. Confirm 0006–0010 applied so the new `0011` migration has a clean base.

---

## The task

This planning conversation runs in two phases.

### Phase 1 — Architectural decisions

Each question below passes the two-part test (real downstream impact + multiple viable options) and warrants the eight-element consequential decision template. Surface each as an explicit decision; do not silently default. Decisions where the answer collapses to "follows from a prior decision" fold into a single record at close-out.

**Decision 1 — Release vehicle and naming.** PI-001 / DEC-001 leave this open: ship as a standalone **v0.4.1** mini-workstream, or **absorb into the first slice of v0.5**? Consider: v0.4 is shipped and stable; CBM redo Phase 1 is the thing waiting; whether any other v0.5 work wants to ride along. This decision sets the slice-plan framing and the schema-spec version bump in §3.3.4.

**Decision 2 — Hierarchy depth.** CBM needs exactly one level (CR parent → four sub-domains). Options: (a) enforce **max depth 1** — a domain that is itself a child cannot be a parent (validation rejects assigning a parent to a domain that already has children, and vice versa); (b) allow **arbitrary nesting** like `topic.parent_topic`. Depth-1 is simpler to render and matches the only known requirement; arbitrary nesting matches the topic precedent and avoids a future migration. Name the tradeoff explicitly.

**Decision 3 — List-endpoint hierarchy access.** PI-001 says "decides which": **hierarchy-aware default ordering** (parents followed by their children, indented), a **`?parent=DOM-NNN` filter** (flat, caller assembles the tree), or **both**. The detail-pane children list needs the filter regardless; the question is whether the default list ordering also becomes hierarchy-aware.

**Decision 4 — Master-pane (Domains panel) treatment.** How sub-domains render in `ui/panels/domains.py`: (a) an **indented tree** mirroring the Topics panel's `parent_topic_id` nesting; (b) **flat list with a Parent column**; (c) flat for now, tree deferred. This interacts with **PI-007 (`domain.short_code`)** — Finding 6 flagged identifier legibility (`PROC-007` vs `MN-INTAKE`) as a STRETCH, and sub-domain display is where short codes would most help. Decide whether to **pull PI-007 short_code into this workstream** or explicitly keep it out of scope.

**Decision 5 — Parent soft-delete / orphan semantics.** PI-001 states soft-deleting a parent does **not** cascade to children. The open question is what the UI does: (a) **block** soft-deleting a parent that still has live children (force the operator to reparent or delete children first); (b) **allow** it and surface the now-orphaned children (parent FK dangles to a soft-deleted record); (c) **null-out** children's `domain_parent_identifier` on parent delete. Pick the one that keeps the data model honest without surprising the operator.

**Decision 6 — Validation surface and error shape.** Confirm the access-layer validation set (matches `^DOM-\d{3}$` when non-null; refers to a *live* `domain` record; not equal to the row's own identifier; respects the Decision 2 depth rule) and that it returns through the standard error path so the API emits a clean `{data:null, …, errors:[…]}` envelope rather than a 500. Mirror `repositories/topics.py`.

### Phase 2 — Slice plan and Claude Code prompt authoring

Once Phase 1's decisions are settled, produce:

**A. The slice plan document** at `PRDs/product/crmbuilder-v2/domain-subdomain-hierarchy-slice-plan.md`. Standard slice-plan structure (per the v0.5 / v0.6 / multi-tenancy precedents): per-slice scope, acceptance criteria, `file:line` touch points, test plan, dependency chain. PI-001's sketch is the starting point — expect roughly:
   - **Slice A** — schema migration (`0011_*`), model field, access-layer validation, API router + schema (read/write key asymmetry), tests.
   - **Slice B** — UI: Parent combo in create/edit dialogs (backed by live `domain` records, sorted by identifier asc), detail-pane parent render + inline children list, master-pane treatment per Decision 4.
   - **Slice C (optional)** — `domain.md` §3.3.4 amendment + schema-spec version bump, README / status-entity touches, and any PI-007 short_code work if Decision 4 pulled it in.

   Adjust the count to the Phase 1 outcomes (e.g., depth-1 vs arbitrary nesting changes Slice A's validation; pulling PI-007 in may justify splitting Slice C).

**B. The per-slice Claude Code prompts** following the existing pattern: `CLAUDE-CODE-PROMPT-domain-subdomain-hierarchy-{A,B,C}-{descriptor}.md` in `PRDs/product/crmbuilder-v2/prompts/`. Each is DETAIL-mode and pure-execution — pre-flight, workflow steps, post-conditions, test invocation, commit-message scaffold (`v2:` subject prefix). The build conversations execute these one at a time.

**C. The planning item record** PI-022 in CRMBUILDER, opened at close-out via the standard `apply_close_out.py` pattern. Title: "`domain_parent_identifier` self-FK amendment — sub-domain hierarchy build." Description: link to this kickoff, the findings doc Finding 2, the slice plan, and cite CBM `PI-001` / `DEC-001` / `SES-001` textually as the origin. Status: Open.

---

## Close-out

Per the v0.4-closeout precedent and DEC-025. The close-out produces a single `close-out-payloads/ses_046.json` payload and a `CLAUDE-CODE-PROMPT-apply-close-out-ses-046.md` apply prompt, both committed in the crmbuilder repo. Remember the API envelope: any verification snippet must unwrap `.data`, and the close-out writes to CRMBUILDER.db (confirm routing first per Pre-flight 1).

**Session record.** SES-046 (next in CRMBUILDER after SES-045). Title: "Domain sub-domain hierarchy amendment — planning." `session_date`: the date the conversation closes. `topics_covered`: open with the seed-prompt reference (this file), then a structured summary of the Phase 1 decisions and Phase 2 outputs. `artifacts_produced`: the slice plan path, the per-slice prompt paths, this kickoff.

**Decisions.** One per settled Phase 1 question (DEC-117, DEC-118, … — next in CRMBUILDER after DEC-116). Standard decision shape (`identifier`, `title`, `context`, `decision`, `rationale`, `alternatives_considered`, `consequences`, `decision_date`, `status: Active`). Fold collapsing questions into a single record.

**Planning item.** PI-022 per above (next in CRMBUILDER after PI-021).

**References.** One `decided_in` reference per decision (decision → SES-046). Plus an `is_about` reference from PI-022 to SES-046. All references are intra-CRMBUILDER; do not attempt a reference to any CBM record.

**Commit.** One commit in the crmbuilder repo containing: the slice plan, the Claude Code prompts, the payload JSON, the apply prompt. Doug pushes; the apply runs in a separate Claude Code session after push.

---

## What this conversation does NOT do

- Does not modify any source code. Source changes happen in the build conversations that execute the slice prompts.
- Does not re-decide *whether* to make the amendment — DEC-001 settled that. It decides *how*.
- Does not run the API, post to it, or trigger DB writes outside the standard close-out apply.
- Does not write to the CBM engagement. CBM `PI-001` / `DEC-001` / `SES-001` are read-only origin records cited textually.
- Does not apply the slice prompts or open the build conversations — those follow after the close-out lands and Doug picks up Slice A.
- Does not amend `domain.md` itself — that edit is Slice C build work, not planning work. The planning conversation only specifies the amendment.
- Does not start CBM redo Phase 1. That opens only after the amendment ships and `domain.md` §3.3.4 is updated.

---

*End of kickoff.*
