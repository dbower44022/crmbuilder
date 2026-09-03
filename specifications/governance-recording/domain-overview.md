# Governance Recording — Domain Overview

| Field | Value |
|-------|-------|
| Version | 0.3 |
| Last Updated | 09-03-26 19:30 |
| Status | DISCUSSION DRAFT — render of domain record DOM-012 (candidate) as of 09-03-26 |
| Audience | Anyone working in or on the CRMBuilder methodology's ninth domain; PI-086, PI-087 and PI-088 authors |
| Governs | Nothing on its own. The domain record DOM-012 and its links in the V2 store are the source (DEC-393, DEC-394, DEC-1021); this file is a render and goes stale between renders |

## Purpose

This document renders the Governance Recording domain as recorded in the V2 store: its name and identity, the question the CRMBuilder mission forces it to answer, its scope, and the personas, processes, entities and rules it involves. It exists so a reader of the repository can review the domain without opening the store. When this file and the store disagree, the store is right and this file needs re-rendering. Produced under PI-085 (REQ-408) per DEC-1003. Engagement ENG-001, project PRJ-023.

## 1. Domain name and identity

**Name:** Governance Recording (established term; DEC-1003).

**Purpose:** Record every session, decision, and unit of work against the engagement's store at the moment it happens, so the store — not memory, files, or transcripts — is the single source of truth for what was decided, what work exists, and who did what.

**Identity:** Governance Recording is a cross-cutting Domain, not a lifecycle stage. It does not sit before, after, or between the eight confirmed domains; it runs inside all of them — Project Definition through Feedback and Upgrades in a client engagement, and Software Delivery in CRMBuilder's own work — because every session in any of them is opened, conducted, and closed under this Domain's rules. It is the ninth Domain.
*Evidence: DEC-1003; DOM-004..DOM-011.*

## 2. The big question

CRMBuilder's mission is to hold the complete definition of a product in a structured store and generate everything else from it. That promise fails the moment the store is an incomplete reflection of what happened — a decision made in conversation but never recorded, work implied in a consequences paragraph but never filed, a commit that names no governing item. The question this Domain must answer is: **how does an engagement prove, from its records alone and at any later moment, what was decided, why, what work followed, and who did it — when the people and agents doing the work are the same ones who must record it, and the store stays true only if they record faithfully, in real time, without exception?**
*Evidence: DEC-310 context; GVR-238.*

## 3. Scope

**In:** *that* governance events are recorded (sessions, conversations, decisions, planning items, projects, references, commits, work tickets, fallback close-out artifacts — no off-the-record sessions); *how* (API/MCP-only authoring, real-time recording in Claude Code, the close-out payload fallback for the sandbox, identifier discipline, wire-format constraints, minimum edges per record); *when* (at the moment of decision, at the moment work surfaces, at a topic boundary, at session open and close — never batched where the store is reachable); *by whom* (the same rules bind AI and human agents equally; every record targets one named engagement). Also the rulebook itself, the enforced mechanical checks, per-engagement rule overrides, the durable knowledge records sessions load at start, and compliance verification.

**The requirement-approval boundary:** the Domain owns the *record* of a requirement approval — that an approving decision exists, that the requirement's status changes only through it, and that a planning item implements it before any build — but not the *process* of approving. Eliciting, specifying, and approving requirements are the work of Requirements Capture and Specification and Approval. REQ-248 stays under TOP-076, read as a recording rule.
*Evidence: DEC-1011; GVR-230; REQ-248.*

**Out:** the content of any decision, requirement, or planning item — what is decided belongs to the domain in which it is decided; that it is recorded belongs here. Planning, building, and shipping software (DOM-011, including ADO rules GVR-001..220). Deploying, operating, or configuring a CRM instance or the cloud service (TOP-116).
*Evidence: REQ-064..067, REQ-085, REQ-088..089, REQ-095..098; DEC-310; DEC-383; DEC-1012.*

## 4. Personas involved

**Existing records — all participate:**

- PER-003 Project Manager (customer) — the customer-side approver whose rulings become recorded decisions in a client engagement.
- PER-005 Consultant (optional) — a human facilitating a client session records under these rules.
- PER-006 Scheduler, PER-007 Reconciliation Agent, PER-008 Architect Agent, PER-009 Project Manager Agent, PER-010 PI Lead Agent, PER-011 Developer Agent, PER-012 Tester Agent — every pipeline agent writes to the store under this Domain's rules: release runs, demand-sets, build plans and work tasks, planning-item dispatch and phase transitions, commits carrying their governing item, findings and verification results.
*Evidence: DEC-1015; GVR-229; TERM-042 (`ado_agent` audience).*

**Engagement Lead — exists as a glossary term (TERM-012), defined as a persona in PI-086:** the person who runs the engagement; approves requirements and governance rules; reviews each demonstrable increment and each PI report before the next item launches; reviews Claude Code's local commits and pushes them; alone deploys to production; the human point of contact when an agent or phase needs attention. Decision authority: final on every ruling this Domain records.
*Evidence: DEC-1009; DEC-1010; TERM-012; LSN-045; GVR-239; GVR-240 / DEC-907; GVR-232.*

**Named here, defined as persona records in PI-086 (DEC-1022):**

- **Claude Code Agent** (TERM-046): reaches the live store; records each governance record by direct API write as it occurs; commits with a `Governed-By` trailer, does not push. Authority: none over content; stops at a topic boundary and surfaces rulings rather than making them.
  *Evidence: REQ-095; GVR-229; GVR-231; LSN-045; REQ-081.*
- **Claude.ai Sandbox Agent** (TERM-047): cannot reach the store; authors the close-out payload and apply prompt; commits and pushes in the same turn. Authority: as above. Not the sandbox of the Development and Sandbox domain, which is a test copy of a client CRM.
  *Evidence: REQ-096..098; LSN-042; LSN-045.*

The rules bind "Doug or anyone else operating against the V2 governance database"; whether any human other than the Engagement Lead and the Consultant needs a persona is for PI-086 to decide.
*Evidence: REQ-066; DEC-310.*

## 5. Processes within the Domain

No process record exists for any of these (PROC-002..009 belong to other domains). All are candidates; the first is PI-087's.

1. **Session/Conversation governance Process** (PI-087) — one session in any medium: pre-flight open, stop-and-log at topic boundaries, decisions at the moment of decision paired with planning items, references as relationships form, audited close. Carries the rules content originally planned for PI-084.
   *Evidence: REQ-077..084, REQ-105, REQ-085..092; Master PRD §11.*
2. **Session open / kickoff pre-flight** — read CLAUDE.md and TOP-013, load rules and preferences (now hook-automated), capture identifier heads live, identify the project, health-check the API, anchor on the planning item and kickoff work ticket. May be a step of (1).
   *Evidence: REQ-068, REQ-071..072; LSN-040; PI-437 / REQ-540.*
3. **Scheduled session handoff** — pre-create the next session as `planned` with the kickoff in its description; the receiver opens it `planned → in_flight`.
   *Evidence: REQ-079; LSN-041; LSN-016.*
4. **Triple-artifact close-out (sandbox fallback)** — deliverable, close-out payload, apply prompt; apply writes the records and lazy-creates the payload and deposit event; the deposit log is committed with the deliverables.
   *Evidence: REQ-096..098; LSN-042; LSN-015.*
5. **Model A build-closure** — branches carry only code; requirement, approval, and implementing item exist before the branch; bookkeeping lands on `main` after merge, re-keyed to current heads.
   *Evidence: LSN-038..039; DEC-232; GVR-230.*
6. **Planning-item resolution after push** — advance with `addresses`; resolve only by the final conversation's `resolves` edge, and only after the Engagement Lead has pushed.
   *Evidence: REQ-090; LSN-043; LSN-047; LSN-066.*
7. **Project open and close** — create when multi-session work is recognized; membership edges on every session and conversation; scope changes are decisions; complete is terminal.
   *Evidence: REQ-073..076; GVR-233.*
8. **Governance-rule authoring, change, and override** — a new rule names its source decision; a change declares wording or meaning; an engagement rule shadows by type with a `supersedes` edge; command-time overrides record their reason.
   *Evidence: REQ-543; LSN-063; DEC-955; GVR-241; PI-439 / REQ-542.*
9. **Release close-out** — user-review checkpoint before the next item; genuine sign-offs in manual mode; failed runs retired, never deleted.
   *Evidence: GVR-239; LSN-019; LSN-021; LSN-031.*
10. **Terminology governance** — every term has a glossary entry; no new term without the Engagement Lead's approval.
    *Evidence: GVR-232.*
11. **Knowledge capture** — lessons, preferences, and reference pointers go to the store, not files.
    *Evidence: GVR-238; REL-039.*
12. **Compliance verification** — the close-out completeness audit (PI-087), the payload validator (PI-090), the pre-action rule check.
    *Evidence: DEC-310; TOP-057; PI-439.*

## 6. Entities the Domain operates on

The Domain points at methodology-level entity records — the governance objects as the methodology understands them, in the style of the confirmed Software Delivery entities — not at the storage-table inventory (ENT-003..ENT-038), which stays separate as a description of the database. One record already exists in that style and is reused; the other fourteen were created as candidates on 2026-09-03 (ENT-045 to ENT-058).
*Evidence: DEC-1013; ENT-040 / ENT-041 as the model.*

| Governance object | Entity record | The Domain's relationship to it |
|---|---|---|
| Planning Item | ENT-040 (confirmed; reused) | Filed for any work that crosses a session; advanced by `addresses`, resolved only by a `resolves` edge after the push. |
| Session | ENT-045 (candidate) | Opened at start and transitioned at close; one per unit of communication in any medium; never off the record. |
| Conversation | ENT-046 (candidate) | One per topic within a session; carries the edge that advances or resolves a planning item. |
| Decision | ENT-047 (candidate) | Authored at the moment of decision in the eight-element template; dispositions paired with references. |
| Project | ENT-048 (candidate) | The long-running container every session and conversation belongs to; terminal when complete. |
| Engagement | ENT-049 (candidate) | The workspace every record targets; named on every request. |
| Reference | ENT-050 (candidate) | The typed edge tying every record to its session, project, topic, or predecessor. |
| Commit | ENT-051 (candidate) | A git commit as a governance record; carries `Governed-By`. |
| Work Ticket | ENT-052 (candidate) | The kickoff seed anchoring a session; file path always required. |
| Close-out Payload | ENT-053 (candidate) | The fallback-path package; lazy-created on apply. |
| Deposit Event | ENT-054 (candidate) | The durable record of an apply; its log is committed with the deliverables. |
| Governance Rule | ENT-055 (candidate) | The binding rules and mechanical checks; loaded by audience and moment; overridable per engagement. |
| Preference | ENT-056 (candidate) | Working-style records loaded at session start. |
| Lesson | ENT-057 (candidate) | Distilled operational knowledge, read on demand. |
| Reference Pointer | ENT-058 (candidate) | The index sessions consult instead of files. |

*Evidence: REQ-067; REQ-073..098; GVR-238; GVR-241.*

## 7. Cross-domain relationships

Every other domain invokes this one by opening a session. A Project Goal Interview (DOM-004), an SME interview (DOM-005), a specification review (DOM-006), a solution analysis (DOM-007), a sandbox review (DOM-008), a release (DOM-009), a feedback session (DOM-010), and a pipeline run or build session in Software Delivery (DOM-011) are each one or more sessions, and each is recorded under this Domain's rules: opened against a project and planning item, decisions authored as made, work filed, close audited. The medium does not matter, and neither does the engagement — CRMBuilder's own work and every client engagement alike, with per-engagement overrides where a client's practice differs. Nothing flows the other way: this Domain never decides what those sessions conclude.
*Evidence: DEC-1003; REQ-066; REQ-077; GVR-241; Master PRD §11.*

## 8. Rules corpus

**Rulebook:** TOP-013 Governance Recording Method and its children; the requirement records under each are the rules (all confirmed):

| Topic | Area | Requirement records |
|---|---|---|
| TOP-076 | Core Recording Principles | 6 (REQ-064..067, REQ-248, REQ-320) |
| TOP-077 | Identifier Discipline | 5 (REQ-068..072) |
| TOP-078 | Project Records | 4 (REQ-073..076) |
| TOP-079 | Session Records | 3 (REQ-077..079) |
| TOP-080 | Conversation Records | 6 (REQ-080..084, REQ-105) |
| TOP-081 | Decision Records | 3 (REQ-085..087) |
| TOP-082 | Planning Item Records | 3 (REQ-088..090) |
| TOP-083 | Reference Records | 2 (REQ-091..092) |
| TOP-084 | Work Ticket Records | 2 (REQ-093..094) |
| TOP-085 | Recording Mechanism | 4 (REQ-095..098) |
| TOP-086 | Wire-Format Constraints | 6 (REQ-099..104) |
| TOP-013 directly | — | 1 (REQ-444) |

45 in all (44 under the children). REQ-477, REQ-480, and REQ-481 were refiled to TOP-116 Cloud deployment and multi-user operation.
*Evidence: DEC-1012.*

**Mechanical checks:** the thirteen rules whose audience is a Claude Code session, GVR-229..241. Five are enforced: GVR-229 (`Governed-By` trailer), GVR-230 (requirement-first, via the governance-gate hook), GVR-235 (pathspec commit), GVR-240 (production deploy human-only), GVR-241 (rule-scope precedence). Advisory: GVR-231 real-time recording, GVR-232 terminology, GVR-233 project lifecycle, GVR-234 naming, GVR-236 commit under parallel sessions, GVR-237 approval-request structure, GVR-238 single source of truth, GVR-239 user review checkpoint.
*Evidence: `GET /governance-rules?resolution=effective`; PI-439 / REQ-542.*

## 9. Rulings applied, and terms

The seven open questions of v0.1 are closed:

1. DEC-1009 — the human who runs an engagement is one persona, Engagement Lead; TERM-012 renamed from Engagement Admin, definition widened to approval, review, push, and production-deploy authority.
2. DEC-1010 — reviewing increments and commits is an Engagement Lead responsibility, not a Reviewer persona.
3. DEC-1011 — the record of a requirement approval is in scope; the process of approving is not; REQ-248 stays under TOP-076 as a recording rule.
4. DEC-1012 — REQ-477, REQ-480, REQ-481 refiled from TOP-013 to TOP-116; the corpus is 45 records.
5. DEC-1013 — the Domain points at methodology-level entity records for all fourteen governance objects, reusing ENT-040; the storage-table inventory stays separate.
6. DEC-1015 — every pipeline agent persona (PER-006..PER-012) participates, with PER-003 and PER-005.
7. DEC-1021 — the domain record is the source; this file is a committed, dated render at `specifications/governance-recording/domain-overview.md`, its path taken from the domain name because domain codes are optional.

**Recorded detour (DEC-1024).** Two sessions put questions 5 and 6 to the Engagement Lead on the same day without either knowing of the other, and the answers differed. The earlier rulings, DEC-1013 and DEC-1015, stand because they came first and were already written; the later ones, DEC-1018 and DEC-1020, carry status Superseded. Nothing written under the earlier rulings was unwound.

**Terms.** The role names and the established terms this document uses now have glossary entries:

| Term | Record | Established by |
|---|---|---|
| Engagement Lead | TERM-012 (renamed) | DEC-1009 |
| Claude Code Agent | TERM-046 | DEC-1022 |
| Claude.ai Sandbox Agent | TERM-047 | DEC-1022 |
| Governance Recording | TERM-048 | DEC-1023 |
| Session | TERM-049 | DEC-1023 |
| Conversation | TERM-050 | DEC-1023 |
| Planning Item | TERM-051 | DEC-1023 |
| Close-out payload | TERM-052 | DEC-1023 |
| Deposit event | TERM-053 | DEC-1023 |
| Model A | TERM-054 | DEC-1023 |
| Build closure | TERM-055 | DEC-1023 |

No term in this document lacks a glossary entry.

## 10. What comes next

- **PI-086** defines the persona records for the Engagement Lead, the Claude Code Agent and the Claude.ai Sandbox Agent and links them to DOM-012.
- **PI-087** defines the Session/Conversation governance Process, the first process record of this domain.
- **PI-088** defines the meta process by which process PRDs are produced, after PI-087 has been observed.
- DOM-012 and ENT-045 to ENT-058 move from candidate to confirmed together when this overview leaves discussion-draft status.

## Change log

| Version | Date | Change |
|---|---|---|
| 0.1 | 09-03-26 | Discussion draft authored in SES-388 / CNV-360 under PI-085 per DEC-1003, with seven open questions. |
| 0.2 | 09-03-26 | Rulings DEC-1009 to DEC-1013 and DEC-1015 applied; domain DOM-012, ENT-045 to ENT-058 and twenty-four scope links written to the store; PI-085 resolved. |
| 0.3 | 09-03-26 19:30 | First committed render (DEC-1021). Persona names approved (DEC-1022, TERM-046, TERM-047); eight glossary entries added (DEC-1023, TERM-048 to TERM-055); entity identifiers filled in; the parallel-ruling detour recorded (DEC-1024). Authored in SES-392 / CNV-364. |
