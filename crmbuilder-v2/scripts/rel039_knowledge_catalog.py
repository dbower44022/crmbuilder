"""REL-039 / PI-357 knowledge-migration catalog (REQ-416, DEC-891).

The authored content moved out of the instruction files (``CLAUDE.md`` +
the file-based memory) into the DB, per the PI-355 classification table and the
PI-356 design. Consumed by ``ingest_rel039_knowledge.py`` (idempotent, dry-run
capable). Data only — no side effects on import.

Four record classes, each a list of dicts:

* ``GOVERNANCE_RULES`` — binding operating rules (→ ``governance_rule`` / GVR-).
* ``PREFERENCES``      — advisory interaction/UI style (→ ``preference`` / PRF-).
* ``LESSONS``          — operational gotchas/how-tos (→ ``lesson`` / LSN-), each
                          optionally carrying ``derived_from`` provenance edges
                          to the decision / planning_item / commit it was welded
                          to (the lossless hybrid split).
* ``REFERENCE_POINTERS`` — external servers/dashboards/docs/credential locations
                          (→ ``reference_pointer`` / RFP-). CBM pointers are
                          scoped to ``ENG-002``. ``access_note`` records *where* a
                          secret lives — NEVER the secret value.

``scope`` is ``"system"`` (a CRMBuilder-wide default, ``engagement_id=NULL``) or
an engagement identifier (``ENG-002`` = CBM). Each record's ``title`` is its
idempotency key within (entity_type, scope): re-ingest skips an existing title.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Instructions → governance_rule (GVR-). The binding feedback_* rules. Each
# links (is_about) to a TOP-013 child topic and/or its source decision where one
# exists. Enforcement: 'enforced'/'enforced_with_override' only where a machine
# check backs it; otherwise 'advisory' (binding-by-discipline).
# ---------------------------------------------------------------------------

GOVERNANCE_RULES: list[dict] = [
    {
        "title": "Every code commit carries a Governed-By trailer",
        "enforcement": "enforced_with_override",
        "severity": "high",
        "rule_type": "commit_governance",
        "body": (
            "Every git commit touching code must carry a Git trailer "
            "'Governed-By: PI-NNN' naming the implementing planning item while it "
            "is still in an executable state (Draft/Decomposed/Ready/In Progress/"
            "In Review — never a Resolved PI), or 'Governed-By: trivial' plus a "
            "non-empty 'Exemption-Reason: <why>' for a genuinely trivial change. "
            "Doc/data-only commits (PRDs/, *.md, crmbuilder-v2/data/, .claude/) are "
            "auto-exempt; a commit touching both code and exempt files is governed. "
            "Enforced by the governance-gate git hook (REQ-320/PI-286/287), mode "
            "CRMBUILDER_GOVERNANCE_GATE=off|warn|enforce (default warn)."
        ),
        "edges": [("decision", "DEC-538"), ("topic", "TOP-076")],
    },
    {
        "title": "Requirement-first is a precondition, not a postscript",
        "enforcement": "enforced_with_override",
        "severity": "high",
        "rule_type": "requirement_first",
        "body": (
            "Before any V2 code/schema/migration on any branch — even a one-line "
            "change — there must already exist, in order: (1) a requirement with "
            "provenance (defined-in-conversation, belongs-to-topic); (2) that "
            "requirement confirmed via an approving decision "
            "(requirement_approved_by_decision → activate_by_decision; NEVER a "
            "status edit); (3) a planning_item that implements it "
            "(planning_item_implements_requirement), inside a project. Code comes "
            "last. The Model A build-closure defers only the bookkeeping "
            "(session/decision/deposit-log to main after merge) — never the "
            "requirement, its approval, or the implementing PI. This is REQ-248 / "
            "DEC-538, ENG-001's founding rule."
        ),
        "edges": [("decision", "DEC-538"), ("topic", "TOP-076")],
    },
    {
        "title": "Record V2 governance in real time via direct API writes",
        "enforcement": "advisory",
        "severity": "high",
        "rule_type": "governance_recording",
        "body": (
            "In Claude Code (live API reachable), record every V2 governance record "
            "— decision, planning item, session, conversation, reference — by direct "
            "API POST at the moment it occurs, not batched into a close-out JSON "
            "payload. The close-out-payload + apply_close_out.py path is the "
            "claude.ai-sandbox fallback (no API access); in Claude Code it retains "
            "only the residual role of producing the git-tracked deposit-event log "
            "under Model A. DEC-310 mandates moment-of-decision authoring; DEC-383 "
            "makes direct POST the Claude Code default. Sessions/conversations are "
            "in_flight, decisions Active, session medium chat, executive summaries "
            "200–800 chars, PIs use the six-state lifecycle (no 'Open')."
        ),
        "edges": [("decision", "DEC-383"), ("topic", "TOP-085")],
    },
    {
        "title": "Every term is defined in the glossary; no new term without approval",
        "enforcement": "advisory",
        "severity": "high",
        "rule_type": "terminology",
        "body": (
            "Terminology governance (binding, Doug 2026-06-20): (1) every term used "
            "in code or documentation has a glossary entry; (2) no new term may be "
            "coined, renamed, or introduced — in code OR docs — until Doug approves "
            "it; surface the proposed term and wait; (3) poor original names are not "
            "permanent — descriptive names win, plan to rename rather than "
            "perpetuate a bad one. When Doug asks a question, answer it — do not make "
            "changes unless he asks for changes."
        ),
        "edges": [("topic", "TOP-077")],
    },
    {
        "title": "A completed project is terminal — never reopen it",
        "enforcement": "advisory",
        "severity": "high",
        "rule_type": "project_lifecycle",
        "body": (
            "A V2 project marked 'complete' cannot be reopened via the API "
            "(PROJECT_STATUS_TRANSITIONS makes 'complete' terminal). Doug's rule: you "
            "cannot reopen a completed project — create a NEW project and move the "
            "unfinished PI(s) there. Before closing any project, re-enumerate its "
            "planning items at the live moment and confirm EVERY one is Resolved — "
            "GET /references?target_id=PRJ-NNN then filter "
            "relationship=='planning_item_belongs_to_project' in Python (the "
            "&relationship= URL param under-returns). Re-verify immediately before "
            "any irreversible governance action, especially under concurrent writes."
        ),
        "edges": [("topic", "TOP-078")],
    },
    {
        "title": "Every agent display name ends in 'Agent'; non-Agent means not an agent",
        "enforcement": "advisory",
        "severity": "medium",
        "rule_type": "naming",
        "body": (
            "In the agent-system / ADO / release-pipeline docs, every agent's display "
            "name ends in the word 'Agent' (Project Manager Agent, PI Lead Agent, "
            "Architect/Developer/Tester Agent, Release Lead Agent). The rule cuts both "
            "ways: a name NOT ending in 'Agent' is NOT an agent — so the "
            "scheduler/conductor and substrate repositories carry no suffix. "
            "Display-name only: do not rename code (tier enums stay "
            "lowercase/unsuffixed; module names pm.py/lead.py unchanged). Boundary: all "
            "four ADO tiers are AI agents; humans plan+approve+compose+freeze, agents "
            "execute from the freeze onward, a human is pulled back only on a "
            "needs_attention flag."
        ),
        "edges": [("topic", "TOP-077")],
    },
    {
        "title": "Always commit with an explicit pathspec, never a bare commit",
        "enforcement": "advisory",
        "severity": "high",
        "rule_type": "commit_hygiene",
        "body": (
            "Always use 'git commit -- <file> [<file>...]' (pathspec-scoped), never a "
            "bare 'git commit' or 'git add <x> && git commit'. Parallel ADO "
            "orchestrators run live on main and stage their in-flight files; a bare "
            "commit sweeps the whole index under your message. Stage nothing first; "
            "pass files directly. Before committing, confirm the branch with "
            "'git rev-parse --abbrev-ref HEAD' (a parallel agent may have moved HEAD); "
            "to land on main, explicitly 'git checkout main' first or use a worktree."
        ),
        "edges": [("topic", "TOP-077")],
    },
    {
        "title": "Commit code immediately when parallel orchestrators are running",
        "enforcement": "advisory",
        "severity": "high",
        "rule_type": "commit_hygiene",
        "body": (
            "When a parallel session/orchestrator runs concurrently in this repo, "
            "commit code changes immediately rather than holding them in the working "
            "tree — the orchestrator's git reset/stash cycles silently discard "
            "uncommitted changes, and it can even sweep your files into an 'abandoned "
            "commit' and switch branches under you. If work looks reverted, check "
            "'git reflog' first (it reveals the reset mechanism) before theorizing "
            "about a race. Destructive git ops (branch -D / force-push) act on the "
            "live ref, not the SHA you validated — a TOCTOU hole on shared branches; "
            "prefer a dedicated git worktree off origin/main for substantial "
            "independent work. This applies to ordinary code fixes, not the "
            "governance-record discipline."
        ),
        "edges": [("topic", "TOP-077")],
    },
    {
        "title": "Structure approval requests as one gate per semantic decision",
        "enforcement": "advisory",
        "severity": "medium",
        "rule_type": "communication",
        "body": (
            "When asking Doug to approve edits (especially propagating one decision "
            "across documents): (1) one approval gate per semantic decision, not per "
            "document or edit; (2) inline the before/after content — never cite an "
            "identifier without inlining what it says, so Doug can approve from the "
            "request alone; (3) separate mechanical (version bumps, timestamps, "
            "cross-ID sync — applied automatically after approval) from semantic; "
            "(4) verify before asking — no conditional plans; (5) then execute and "
            "report once. Governs in-conversation approval requests from Claude Code "
            "too, not just session prompts."
        ),
        "edges": [("topic", "TOP-085")],
    },
]

# ---------------------------------------------------------------------------
# Preferences → preference (PRF-). Advisory interaction/UI/workflow style.
# ---------------------------------------------------------------------------

PREFERENCES: list[dict] = [
    {
        "title": "Execute autonomously — don't ask permission to proceed",
        "category": "interaction",
        "applies_to": "all",
        "body": (
            "Do not ask 'shall I proceed?' or 'would you like me to continue?' — just "
            "do the work. Execute a task fully without pausing to ask permission "
            "between steps. Only stop if genuinely blocked or if a "
            "destructive/irreversible action needs confirmation per the safety rules."
        ),
    },
    {
        "title": "Bring one issue at a time in planning/design discussions",
        "category": "interaction",
        "applies_to": "all",
        "body": (
            "In planning and design discussions, bring issues one at a time, discuss "
            "each to resolution, then move to the next — never batch multiple "
            "decisions into one AskUserQuestion block or message. Present one "
            "decision, give a recommendation with reasoning, and engage until "
            "settled. Refines 'execute autonomously' (still act on non-decision work)."
        ),
    },
    {
        "title": "One command per turn for terminal walkthroughs",
        "category": "interaction",
        "applies_to": "claude_code",
        "body": (
            "For operational walkthroughs where Doug runs commands at his terminal "
            "(UI clicks, curl verifications, deploy phases), send exactly one command "
            "or one action per turn and wait for the output before sending the next. "
            "Do not bundle multiple steps with expected-response tables. Does NOT "
            "apply to code I write/edit, parallel tool calls I make myself, or "
            "research findings I report — only to Doug's executable steps."
        ),
    },
    {
        "title": "Always give full absolute file paths",
        "category": "interaction",
        "applies_to": "all",
        "body": (
            "When referencing any file, give the full absolute path (e.g. "
            "/home/doug/Dropbox/Projects/crmbuilder/...), never a bare filename — the "
            "repo has thousands of files and full paths are clickable in the "
            "terminal. Applies to new files created, files edited, and files cited "
            "for reading."
        ),
    },
    {
        "title": "Prefer operator-controlled stepping over auto-looping",
        "category": "workflow",
        "applies_to": "all",
        "body": (
            "For multi-step external operations (EspoCRM upgrades, migrations applied "
            "one at a time, multi-stage cutovers), don't auto-loop to the latest — "
            "apply one step per invocation and let the operator decide when to run "
            "again. Operators sometimes intentionally lag the absolute latest (letting "
            "a fresh release bake). Surface 'more available' signals rather than "
            "silently continuing."
        ),
    },
    {
        "title": "Never gray out buttons — show an explanatory message instead",
        "category": "ui",
        "applies_to": "ui",
        "body": (
            "Do not disable (gray out) buttons. Keep them enabled and add guard logic "
            "in the click handler that shows an informative message when "
            "preconditions aren't met, so the user understands what to fix. A "
            "grayed-out button is confusing — the user can't tell why it's "
            "unavailable."
        ),
    },
    {
        "title": "Secondary buttons use warm orange, not gray",
        "category": "ui",
        "applies_to": "ui",
        "body": (
            "Secondary/utility buttons (e.g. Recovery & Reset) use warm orange "
            "(#FFA726, hover #FFB74D) to look visually subordinate to primary actions "
            "while still clearly active. Do not use gray (#9E9E9E) — it reads as "
            "disabled."
        ),
    },
]

# ---------------------------------------------------------------------------
# Lessons → lesson (LSN-). Operational gotchas/how-tos split from the hybrid
# memories. ``derived_from`` = provenance edges to the DB record the memory was
# welded to (decision / planning_item / commit) — the lossless split.
# category ∈ {engineering, operations, process, deployment};
# signal ∈ {guidance, hazard, howto}.
# ---------------------------------------------------------------------------

LESSONS: list[dict] = [
    # --- schema / migrations engineering ---
    {
        "title": "Adding a V2 entity type must rebuild the change_log CHECK too",
        "category": "engineering",
        "signal": "hazard",
        "body": (
            "Adding a new entity type to vocab.ENTITY_TYPES must also rebuild the "
            "change_log.entity_type CHECK (which unions ENTITY_TYPES) and the refs "
            "source_type/target_type CHECKs — not just the refs. create_all-based "
            "tests miss this because create_all always builds the current CHECK, but "
            "the live PG DB 500s on the first change_log insert for the new type if "
            "the migration skips the rebuild. Migrations after 0036 guard this."
        ),
        "derived_from": [("planning_item", "PI-046")],
    },
    {
        "title": "Never hand-patch the live V2 schema — migrate via Alembic only",
        "category": "deployment",
        "signal": "hazard",
        "body": (
            "Never hand-patch the live V2 DB schema. Apply schema changes through the "
            "Alembic chain (crmbuilder-v2-bootstrap-db / alembic upgrade), verified on "
            "a copy first. The PI-308 migration-drift gate refuses to start the API if "
            "the DB version != schema head. Safe live path: verify schema == head, "
            "then 'alembic stamp head' if a create_all DB is unstamped."
        ),
        "derived_from": [("planning_item", "PI-308")],
    },
    {
        "title": "Live V2 store is Postgres with a dual-head Alembic chain",
        "category": "deployment",
        "signal": "guidance",
        "body": (
            "The live V2 store is Postgres (cloud Managed PG; a local docker PG on "
            ":55432 is a stale snapshot). Alembic is dual-head: the SQLite batch chain "
            "(migrations/) is NOT replayed on PG — Postgres has its own tree at "
            "migrations/pg/ (alembic.ini there). Never 'alembic upgrade head' a "
            "Postgres DB through the SQLite chain. Every schema change ships a "
            "migration on BOTH heads."
        ),
        "derived_from": [("planning_item", "PI-123")],
    },
    {
        "title": "PG serial sequences are not reset after a SQLite→PG load",
        "category": "deployment",
        "signal": "hazard",
        "body": (
            "After a SQLite→Postgres data load, integer serial-id sequences are left "
            "behind max(id), so the next insert collides. Repair with setval on each "
            "sequence. sqlite_to_postgres.py still doesn't reset sequences — a "
            "requirement-first fix is pending. Symptom: duplicate-key IntegrityError "
            "on a fresh insert into a table that was just bulk-loaded."
        ),
        "derived_from": [("planning_item", "PI-123")],
    },
    {
        "title": "Per-prefix advisory lock serializes identifier auto-assign under concurrency",
        "category": "engineering",
        "signal": "guidance",
        "body": (
            "Server-assigned prefixed identifiers (SES-, DEC-, GVR-, …) use a "
            "read-max-then-insert-and-retry loop that races under concurrent writers "
            "on Postgres. The fix (PI-384) is a per-prefix advisory lock "
            "(serialize_identifier_assignment) — a PG advisory lock, SQLite no-op — "
            "called before compute_next_identifier in every repository's "
            "_insert_with_autoassign. references had no retry loop (hard 500 on "
            "collision) until the same fix landed."
        ),
        "derived_from": [("planning_item", "PI-384")],
    },
    {
        "title": "Scheduler side-band writers must stamp engagement identifier, not code",
        "category": "engineering",
        "signal": "hazard",
        "body": (
            "The scheduler's side-band DB writers (event_capture/cost_capture) that "
            "bypass HTTP must stamp the engagement IDENTIFIER (ENG-NNN), not the "
            "engagement CODE, or pipeline_events hits a foreign-key violation and "
            "observability is silently lost (non-fatal). A requirement-first fix is "
            "pending."
        ),
        "derived_from": [],
    },
    {
        "title": "The catalog-seed data is gitignored — validate schema via create_all",
        "category": "engineering",
        "signal": "howto",
        "body": (
            "The base-entity-catalog YAML the 0004 seed migration needs is "
            "gitignored/absent from a clone, so you cannot run the SQLite Alembic "
            "chain from base. Validate a schema change via Base.metadata.create_all "
            "(models) or against a copy of the live DB — not a from-scratch chain "
            "walk. The PI-308 bootstrap create_all+stamp path exists for exactly this."
        ),
        "derived_from": [],
    },
    # --- runtime / concurrency ---
    {
        "title": "V2 desktop SQLite needs WAL to avoid reader/writer freezes",
        "category": "engineering",
        "signal": "hazard",
        "body": (
            "On a shared SQLite store the default delete-journal makes a writer block "
            "all readers, freezing the desktop UI. Enable WAL mode (plus busy_timeout) "
            "via the db.py _enable_sqlite_pragmas hook. Durable fix is REQ-296/PI-253."
        ),
        "derived_from": [("planning_item", "PI-253")],
    },
    {
        "title": "Don't remove the gc/DeferredDelete teardown in Qt tests",
        "category": "engineering",
        "signal": "hazard",
        "body": (
            "Intermittent v2-test SIGSEGVs (Qt multi_sort_header paintSection during "
            "teardown) were fixed by a gc + DeferredDelete teardown in "
            "tests/crmbuilder_v2/conftest.py. Do not remove it. Symptom of the flake: "
            "the suite exits 0 with no summary after a Qt teardown SIGSEGV; re-run the "
            "UI suite alone to confirm a real pass."
        ),
        "derived_from": [("commit", "b1682d38")],
    },
    {
        "title": "Transient modal sub-dialogs from EntityCrudDialog need deleteLater()",
        "category": "engineering",
        "signal": "hazard",
        "body": (
            "In the v2 UI, transient modal sub-dialogs opened from an EntityCrudDialog "
            "must be explicitly deleteLater()'d, or a worker-thread GC hazard crashes "
            "the app when the parent dialog closes while a worker still references the "
            "child."
        ),
        "derived_from": [],
    },
    # --- API / access behaviour ---
    {
        "title": "V2 list endpoints ignore offset — page with a single large limit",
        "category": "engineering",
        "signal": "hazard",
        "body": (
            "V2 list endpoints ignore the offset parameter (return the same first "
            "page). To read a large collection, request a single large limit rather "
            "than paginating with offset. Surfaced during the Phase 1.5 CBM run "
            "(246 candidates)."
        ),
        "derived_from": [],
    },
    {
        "title": "The X-Engagement header names the engagement for every request",
        "category": "engineering",
        "signal": "guidance",
        "body": (
            "Post PI-β there is one unified DB; the active engagement is named "
            "per-request by the X-Engagement header (ENG-NNN or code), resolved by "
            "the scope middleware and applied as the row-level filter/stamp. There is "
            "no current_engagement.json marker and no per-engagement DB file. Direct "
            "access-layer use wraps writes in 'with active_engagement(\"ENG-NNN\"):'."
        ),
        "derived_from": [("planning_item", "PI-126")],
    },
    {
        "title": "V2 API responses use a {data, meta, errors} envelope",
        "category": "engineering",
        "signal": "guidance",
        "body": (
            "Every V2 endpoint returns {data, meta, errors}: list endpoints have "
            "data:[...], single-record data:{...}, errors:null on success. Any inline "
            "Python/jq/shell reading the API must unwrap .data first. Some exception "
            "handlers (api/errors.py) bypass the envelope and return FastAPI's "
            "standard error shape — read the body before unwrapping if a request "
            "might 4xx/5xx."
        ),
        "derived_from": [],
    },
    {
        "title": "specs live in the DB as topic/requirement/decision records, not .md",
        "category": "process",
        "signal": "guidance",
        "body": (
            "V2 specs and governance rules live in the DB as topic/requirement/"
            "decision records, not markdown files (DEC-393/394). Read the relevant "
            "topic (e.g. TOP-013 for governance recording) before authoring records. "
            "A conversation's 'resolves' edge to a planning_item atomically flips it "
            "to Resolved; /requirements POST rejects a client-supplied identifier."
        ),
        "derived_from": [("decision", "DEC-393")],
    },
    # --- close-out / governance wire-format ---
    {
        "title": "Close-out payload wire-format gotchas",
        "category": "process",
        "signal": "hazard",
        "body": (
            "Close-out payloads (the sandbox fallback path): commits need "
            "commit_committed_at + commit_parent_shas; session_medium has no "
            "'claude_code' value (use 'chat'); planning items use the six-state "
            "lifecycle (no 'Open'); every session/decision/PI needs an "
            "executive_summary (200–800 chars). apply_close_out.py posts the session "
            "block verbatim — author it in the PI-073 shape."
        ),
        "derived_from": [],
    },
    {
        "title": "Closing a pre-created (planned) session: PATCH to complete after apply",
        "category": "process",
        "signal": "howto",
        "body": (
            "When closing a session that was pre-created in 'planned' status, the "
            "close-out's session block 409s on apply (the row already exists). PATCH "
            "the session planned→complete separately after the apply, rather than "
            "including it in the payload's session-create block."
        ),
        "derived_from": [],
    },
    {
        "title": "Check the target before a bulk live write — a founding assumption can be stale",
        "category": "process",
        "signal": "hazard",
        "body": (
            "Before a bulk live write driven from a document/spec, verify the target "
            "state first — a founding assumption can be stale. The REL-013/PI-095 "
            "candidate-inventory ingest was built and dry-run-validated, then HALTED "
            "at the live write because the confirmed methodology model (an 8-domain "
            "taxonomy) superseded the stale 14-domain candidates the script drove "
            "from. Mechanism-correct is not content-correct."
        ),
        "derived_from": [("planning_item", "PI-095")],
    },
    # --- release / delivery model ---
    {
        "title": "All V2 dev is release-scoped; a project belongs to exactly one release",
        "category": "process",
        "signal": "guidance",
        "body": (
            "The delivery model is release-scoped: all development flows through a "
            "release, a Project belongs to exactly one release (REQ-211), and there "
            "are no long-lived containers. The release-scoped dev gate "
            "(assert_developable) can require a PI be in a frozen release before "
            "In Progress/Resolved, but the flag defaults OFF (REQ-323/324)."
        ),
        "derived_from": [("planning_item", "PI-288")],
    },
    {
        "title": "Manual-release ship auto-completes only in_flight projects",
        "category": "process",
        "signal": "guidance",
        "body": (
            "Manual-mode releases (execution_mode='manual') skip decomposition + "
            "qa/test and auto-ship when all in-scope PIs are Resolved. On ship, the "
            "auto-complete only completes in_flight projects (REQ-385) — it won't "
            "force a project out of another state. Manual mode still needs real human "
            "reconciliation + architecture sign-offs (not fabricated); bootstrap-db "
            "is manual."
        ),
        "derived_from": [("planning_item", "PI-295")],
    },
    {
        "title": "Grab-the-lane: a persistent monitor beats a notify-only wait",
        "category": "operations",
        "signal": "howto",
        "body": (
            "To claim the single-occupancy dev lane the instant it frees (vs losing "
            "the race to automated schedulers), run a persistent monitor whose poll "
            "loop itself POSTs the ready→development transition when no release is in "
            "a lane state. A notify-only wait loses the race. REL-037 sat at 'ready' "
            "for hours behind another release holding the lane."
        ),
        "derived_from": [("planning_item", "PI-350")],
    },
    {
        "title": "Cleaning up a failed release run retires it, never deletes it",
        "category": "process",
        "signal": "guidance",
        "body": (
            "Cleaning up a failed/abandoned release means retiring it, not erasing it "
            "(REQ-264 / GVR-122). The only sanctioned cleanup path for a release that "
            "entered a lane is releases.abandon() (POST /releases/{id}/abandon), which "
            "writes a born-terminal release_run outcome (RUN-) and preserves the "
            "scope edges + phase workstreams as evidence. A plain lane→cancelled is "
            "refused."
        ),
        "derived_from": [],
    },
    # --- edges / model discipline ---
    {
        "title": "Legacy provenance backfill: cluster by decision, never fuzzy-match names",
        "category": "process",
        "signal": "howto",
        "body": (
            "When backfilling provenance edges for a legacy corpus, cluster "
            "requirements by the design decision each traces to and map that cluster "
            "to the Resolved PI(s) that built it (planning_item_implements_requirement) "
            "— never fuzzy-match requirement names to PI titles (the two sets are "
            "disjoint domains; that fabricates provenance). Recovered ENG-001's "
            "coverage from 101 'unbuilt' to 6 this way."
        ),
        "derived_from": [],
    },
    {
        "title": "The ADO driver won't adopt a phase left In Progress — complete then relaunch",
        "category": "operations",
        "signal": "guidance",
        "body": (
            "The ADO orchestration driver (PI-143, the PI-level scheduler in "
            "runtime/ado_runtime.py) won't adopt a phase workstream left In Progress by "
            "a prior run — complete-phase it, then relaunch. It verifies work by result, "
            "not by agent exit code (DEC-396)."
        ),
        "derived_from": [("planning_item", "PI-143")],
    },
    {
        "title": "A worktree agent must spawn from current main HEAD or it builds on stale code",
        "category": "operations",
        "signal": "hazard",
        "body": (
            "An ADO agent's git worktree must be spawned from current main HEAD, or it "
            "builds on stale code. The parallel-agent fleet runs in per-agent "
            "worktrees; spawning from an old base silently reintroduces already-fixed "
            "bugs."
        ),
        "derived_from": [],
    },
    # --- CRM engine / deploy ---
    {
        "title": "Raw audit YAML is not directly deployable",
        "category": "deployment",
        "signal": "hazard",
        "body": (
            "Audit-captured YAML from a live EspoCRM instance is NOT directly "
            "re-deployable — it needs transformation (c-prefix handling, "
            "relationship-block extraction, deferred options, layout adjustments) "
            "before the Configure pipeline accepts it. The CBM full-structure deploy "
            "confirmed this."
        ),
        "derived_from": [],
    },
    {
        "title": "EspoCRM audit matches entities by internal/neutral name, not label",
        "category": "deployment",
        "signal": "hazard",
        "body": (
            "The EspoCRM audit matches entities/fields by internal (neutral) name with "
            "the c-prefix stripped, NOT by display label. An earlier audit that "
            "captured labels as names created duplicate canonical entities. Labels "
            "live in i18n (Global.scopeNames / <Entity>.fields), not entityDefs/scope "
            "meta; sync them as a separate label column, never as the match key."
        ),
        "derived_from": [("planning_item", "PI-322")],
    },
    {
        "title": "EspoCRM blank enum option breaks reconcile capture — re-audit to clear stale",
        "category": "deployment",
        "signal": "hazard",
        "body": (
            "A blank ('') enum/multi_enum option value on an EspoCRM field breaks "
            "reconcile option-value capture. Re-audit the instance to clear the stale "
            "captured option set after fixing it. Surfaced in REL-056 enum-option "
            "reconcile."
        ),
        "derived_from": [("planning_item", "PI-381")],
    },
    {
        "title": "Deploy-wizard leaves custom/Espo/Custom/Resources root-owned, blocking createEntity",
        "category": "deployment",
        "signal": "hazard",
        "body": (
            "The V1 deploy wizard's Docker install leaves custom/Espo/Custom/Resources "
            "root-owned (COPY ran as root), which blocks the API's createEntity "
            "(runs as www-data). chown -R www-data:www-data the custom resources dir "
            "before deploying custom entities (DEC-002, CBM pipeline proof)."
        ),
        "derived_from": [("decision", "DEC-002")],
    },
    {
        "title": "The foreign field kind: re-audit to reclassify after the vocab lands",
        "category": "deployment",
        "signal": "guidance",
        "body": (
            "After the 'foreign' field-kind vocab + CHECK landed (PI-374, migrations "
            "0103/0060), re-audit a live instance to reclassify existing foreign "
            "fields — the audit only tags the kind on a fresh read. The deploy + "
            "result-type slices are separate follow-ons; the audit-side token is "
            "'foreign'."
        ),
        "derived_from": [("planning_item", "PI-374")],
    },
    {
        "title": "Verify entity panels by rendering, not by metadata",
        "category": "engineering",
        "signal": "howto",
        "body": (
            "When adding EspoCRM entity side-panels (Activities/History/Tasks), verify "
            "they actually RENDER for the entity — via clientDefs.{Entity}.sidePanels."
            "detail + the link definitions — not merely that the metadata exists. "
            "Metadata present is not the same as the panel showing."
        ),
        "derived_from": [("planning_item", "PI-344")],
    },
    {
        "title": "Manual-mode releases still need real human reconciliation + architecture sign-offs",
        "category": "process",
        "signal": "guidance",
        "body": (
            "Even a manual-execution-mode release must record genuine human "
            "reconciliation and architecture sign-offs — do not fabricate them to "
            "walk the release to shipped. The ship approval auto-records only once "
            "all in-scope PIs are actually Resolved."
        ),
        "derived_from": [],
    },
    {
        "title": "YAML-out is CLI-only today; the Generate-YAML/Publish UI is a gap",
        "category": "engineering",
        "signal": "guidance",
        "body": (
            "The engine-neutral design → EspoCRM YAML export (PRJ-025) is CLI-only "
            "(crmbuilder-v2-export-espocrm); there is no Generate-YAML / Publish UI "
            "yet. Publish source is the DB design, not YAML files."
        ),
        "derived_from": [("planning_item", "PI-189")],
    },
    # --- infra / MCP ---
    {
        "title": "claude.ai-web MCP connector is blocked upstream — use Claude Code/Desktop",
        "category": "operations",
        "signal": "guidance",
        "body": (
            "The V2 MCP server is reachable at mcp.crmbuilder.ai via a self-hosted "
            "OAuth AS, but claude.ai-web connector registration is blocked by an "
            "upstream Anthropic token-exchange bug (the silent ofid_* pattern, GitHub "
            "issue #271). Use Claude Code or Claude Desktop (stdio MCP) instead; the "
            "web path immediately works when Anthropic ships the connector fix."
        ),
        "derived_from": [],
    },
    {
        "title": "engagement_export_dir need not exist at create/update",
        "category": "engineering",
        "signal": "guidance",
        "body": (
            "A v2 engagement's engagement_export_dir need not exist at create/update "
            "time; existence is enforced only at the write-time export gate (and the "
            "exporter itself was removed in PI-β — the column is vestigial)."
        ),
        "derived_from": [],
    },
    {
        "title": "Restart the API after a schema/code deploy so it serves the new surface",
        "category": "deployment",
        "signal": "howto",
        "body": (
            "After shipping new code/endpoints to the droplet, restart the API "
            "(systemctl restart crmbuilder-v2-api) so it serves the new surface; the "
            "startup drift gate enforces migrate-before-serve. A newly-merged endpoint "
            "isn't live until the process restarts."
        ),
        "derived_from": [],
    },
    # --- process / provenance gate ---
    {
        "title": "Requirement descriptions pass a blocking readability gate at approval",
        "category": "process",
        "signal": "guidance",
        "body": (
            "A V2 requirement_description must pass a blocking readability gate at "
            "approval: ≤75 words, ≤4 sentences, NO embedded identifiers, acceptance "
            "criteria required. Put detail/identifiers in requirement_notes, not the "
            "description. The gate (access/readability.py) rejects unreadable "
            "statements at confirm time."
        ),
        "derived_from": [],
    },
    {
        "title": "Local-only ADO salvage branches are not in the DB — track their tips",
        "category": "operations",
        "signal": "guidance",
        "body": (
            "Some ADO/RBAC salvage work lives on local-only branches whose tips are "
            "not represented in the governance DB (e.g. the PI-051 role-aware "
            "field-level security branches ado/wtk-197..203). Their existence + tip "
            "SHAs are durable knowledge that would otherwise be lost when the memory "
            "file is trimmed."
        ),
        "derived_from": [("planning_item", "PI-051")],
    },
]

# ---------------------------------------------------------------------------
# Reference pointers → reference_pointer (RFP-). External targets. CBM pointers
# are engagement-scoped to ENG-002. ``access_note`` records WHERE a secret lives
# (keyring ref, env var name, key path), NEVER the secret value.
# ---------------------------------------------------------------------------

REFERENCE_POINTERS: list[dict] = [
    # --- CRMBuilder V2 cloud infrastructure (system scope) ---
    {
        "title": "V2 production API",
        "kind": "service",
        "scope": "system",
        "target": "https://api.crmbuilder.ai",
        "access_note": (
            "Auth ON (bearer token). Backed by the DO NYC3 droplet at 138.197.72.15 "
            "(SSH root + ~/.ssh/id_ed25519) behind Caddy TLS. Config incl. "
            "CRMBUILDER_V2_DATABASE_URL is read from "
            "/opt/crmbuilder/crmbuilder-v2/data/crmbuilder.env; systemd unit "
            "crmbuilder-v2-api. To read/write governance directly, SSH in and use the "
            "access layer (RBAC is enforced at the API layer, not the repositories)."
        ),
        "body": (
            "The live V2 backend and single source of truth. Managed Postgres is the "
            "store; the local docker PG on :55432 is a stale snapshot."
        ),
    },
    {
        "title": "V2 production droplet",
        "kind": "server",
        "scope": "system",
        "target": "root@138.197.72.15 (DigitalOcean NYC3)",
        "access_note": (
            "SSH as root with the key at ~/.ssh/id_ed25519 (path only — never the "
            "key material). App at /opt/crmbuilder (deployed copy, not a git repo). "
            "Run the access layer with: cd /opt/crmbuilder && QT_QPA_PLATFORM="
            "offscreen .venv/bin/python3 -"
        ),
        "body": "Hosts the V2 API + Caddy; Managed PG is separate.",
    },
    {
        "title": "V2 MCP server",
        "kind": "service",
        "scope": "system",
        "target": "https://mcp.crmbuilder.ai",
        "access_note": (
            "Self-hosted Google-OAuth authorization server (systemd + cloudflared). "
            "claude.ai-web connector registration is blocked upstream — use Claude "
            "Code or Claude Desktop (stdio MCP)."
        ),
        "body": "Remote MCP transport for the V2 store.",
    },
    {
        "title": "ANTHROPIC_API_KEY location for the ADO agents",
        "kind": "credential_location",
        "scope": "system",
        "target": "crmbuilder-v2/data/crmbuilder.env (env var ANTHROPIC_API_KEY)",
        "access_note": (
            "The release-pipeline / ADO agents read ANTHROPIC_API_KEY from the "
            "gitignored crmbuilder.env (or the keyring after the PI-321 migration: "
            "crmbuilder-v2-migrate-agent-secrets). This pointer records the location "
            "only — never the key value."
        ),
        "body": "Where the agent runtime's Anthropic credential lives.",
    },
    {
        "title": "Agent-system PRD documents",
        "kind": "doc",
        "scope": "system",
        "target": (
            "PRDs/product/NEW-Master PRDs/Agent PRDs/Archive/ (see its README.md "
            "manifest)"
        ),
        "access_note": None,
        "body": (
            "The ADO / orchestrator / release-pipeline / agent-profile-registry "
            "design + build docs (~57 files). Agent-System-Overview.md and "
            "...-Technical-Reference.md are the built canonical docs; "
            "Agent-System-Target-Model.md is the target (rest not built)."
        ),
    },
    # --- CBM client engagement (ENG-002) ---
    {
        "title": "CBM production EspoCRM",
        "kind": "server",
        "scope": "ENG-002",
        "target": "https://crm.clevelandbusinessmentors.org (droplet 147.182.135.50)",
        "access_note": (
            "SSH root@147.182.135.50 with ~/.ssh/id_ed25519 (path only). API speaks "
            "basic auth as admin@cbmentors.org; the admin password + the "
            "db_root_password_ref (keyring 'crmbuilder:<uuid>') live on the live GUI "
            "DB ~/Dropbox/Projects/ClevelandBusinessMentors/.crmbuilder/CBM.db "
            "(Instance id=2, InstanceDeployConfig id=2). Resolve keyring refs via "
            "automation.core.secrets.get_secret(ref). V2 instance INST-002 must be "
            "auth_method=basic. Never store the password value here."
        ),
        "body": "The live CBM production CRM. DNS-only (grey cloud) in Cloudflare.",
    },
    {
        "title": "CBM test EspoCRM instance",
        "kind": "server",
        "scope": "ENG-002",
        "target": "https://crm-test.clevelandbusinessmentors.org",
        "access_note": (
            "Basic auth; username is the admin email admin@cbmentors.org (NOT "
            "'admin', which 401s). Spike scripts read automation/data/cbm-client.db "
            "(old schema v7); the running GUI app uses "
            "<client_repo>/.crmbuilder/CBM.db (schema v16). Inspect SQLite via "
            "'uv run python' + stdlib sqlite3 — the sqlite3 CLI is not installed. "
            "V2 instance INST-001."
        ),
        "body": "CBM_Hosted_Test (V1 Instance id=1). The espocloud instance is gone (404).",
    },
    {
        "title": "CBM documentation / training (BookStack)",
        "kind": "dashboard",
        "scope": "ENG-002",
        "target": "https://docs.clevelandbusinessmentors.org (droplet 192.34.63.167)",
        "access_note": "BookStack at /opt/bookstack (docker compose) on its own droplet.",
        "body": "Docs/training site shared by the CBM sandbox + prod CRM. Shelf→Book→Chapter→Page.",
    },
    {
        "title": "CBM BookStack REST API",
        "kind": "credential_location",
        "scope": "ENG-002",
        "target": "https://docs.clevelandbusinessmentors.org/api",
        "access_note": (
            "API token stored at ~/.config/bookstack/credentials (chmod 600) — path "
            "only, never the token. Pages accept markdown or html."
        ),
        "body": "Edit CBM docs programmatically via the BookStack REST API.",
    },
    {
        "title": "CBM client repository (name ↔ local path)",
        "kind": "repo",
        "scope": "ENG-002",
        "target": "github: dbower44022/ClevelandBusinessMentoring",
        "access_note": None,
        "body": (
            "The GitHub repo is 'ClevelandBusinessMentoring' (long form); Doug's local "
            "clone is ~/Dropbox/Projects/ClevelandBusinessMentors/ (short form, ending "
            "'Mentors'). Use the short local path in session prompts, the long name "
            "for the GitHub repo/PR links. Client YAML + generated docs live here, "
            "not in the crmbuilder repo."
        ),
    },
    {
        "title": "CBM client intake project",
        "kind": "repo",
        "scope": "ENG-002",
        "target": "~/Dropbox/Projects/cbm-client-intake",
        "access_note": None,
        "body": (
            "The CBM 'client intake form' is a separate project with its own repo + "
            "CLAUDE.md — read that repo's CLAUDE.md first when working on it."
        ),
    },
]
