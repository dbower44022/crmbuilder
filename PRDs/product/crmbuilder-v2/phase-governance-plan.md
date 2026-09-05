# Phase-Specific Governance Plan — rules and skills selected by the work in front of the session

> **DISCUSSION DRAFT — NOT YET APPROVED.** Produced in a claude.ai session on 09-05-26 against the CRMBUILDER engagement. The two decisions in Part 2 were ruled by Doug in conversation and are not yet decision records in the store; nothing in this plan has been written to the store. The plan becomes binding when the close-out that carries those decisions is applied.

| Field | Value |
|-------|-------|
| Version | 0.1 (draft) |
| Last Updated | 09-05-26 01:05 |
| Engagement | CRMBUILDER (dogfood first; Cleveland Business Mentors validates second) |
| Governs | Nothing yet — a reviewable plan |
| Companion | `specifications/master-crmbuilder-PRD.md` (the phase definitions); `specifications/governance-recording/domain-overview.md` (the recording rules that apply in every phase) |

## 1. What this plan changes

Today every session loads the same rules whatever it is doing. A requirements interview loads the commit-hygiene rules and nothing about interviewing; a deployment loads the writing standards and nothing about the deploy runbook. After this plan, a session opens by asking the user what they want to do, works out from the plain-language answer which kind of work that is, and loads only the rules and skills for the phase the work is in — changing them as the work moves from one phase to the next inside the same sitting.

The cost is stated once here and not repeated: five phase profiles and a catalogue of kinds of work have to be authored and kept current, and a first version will misread some requests. The guard against misreading is that the system always says back, in plain words, what it thinks the user asked for before it loads anything.

## 2. Decisions ruled in this session

**The session names a profile, and the system does the naming.** Rules and skills are selected by the kind of work a session is doing, not by a phase stamped on the engagement. An engagement is in several phases at once (a client can be maintaining one application, gathering requirements for the next domain, and deploying a CRM in the same week), so a phase on the engagement record would be wrong within days. The selector is an agent profile, which the existing contract resolver already knows how to expand into rules, skills, engagement overrides, and learnings. The user never picks a profile; the opening prompt's answer is classified into one.

**The opening answer maps to a kind of work, not a phase.** "Add a field to an existing screen" is a short requirements step, a design change, a build, a sandbox check, and a release, all in one sitting. Mapping that answer to a single phase would load the wrong rules for most of the session. So the answer maps to a named kind of work from a curated catalogue, and each kind of work is a sequence of phase segments. The phase profiles hold the rules and skills; the kind of work holds the sequence. A rule is written once for a phase and every kind of work passing through that phase inherits it.

## 3. What was found in the current architecture (verified against source and store, 09-05-26)

A governance rule carries an audience (everyone, Claude Code, the sandbox, the desktop, or the delivery-pipeline agent) and a moment (always, at commit, at deploy, when recording governance, at release). An engagement can override a system rule of the same type. The session-start hook loads every active rule addressed to Claude Code or to everyone. The agent profile contract resolver assembles a profile's bound skills and rules, applies the engagement overlay, and adds learnings by area and tier. No part of that path knows what phase the work is in, and the engagement record has only a status (active, paused, archived).

Of 247 rules (85 active), 228 are addressed to the delivery-pipeline agent, 15 to Claude Code, 4 to everyone. The rules that govern requirements work — inferences need positive support, one output per conversation, phases run in strict sequence, no product names in requirement documents, unique identifiers on every requirement, documents are renders of the store — all exist but are addressed to the delivery-pipeline agent, so a Claude Code or claude.ai session running an interview never loads them. No design-phase rules exist; the Master PRD marks those phases as placeholders and a candidate requirement set for them is drafted but not written to the store. Deployment rules are engine mechanics. No maintenance rules exist.

Of 124 skills, 98 are tool skills and nearly all are delivery-pipeline work-task plumbing, heavily duplicated ("claim a Work Task" appears thirteen times, once per area profile). The 26 instruction skills are three EspoCRM configuration checks, one requirement-authoring gate, generic coding standards, thirteen custom web application standards that came out of the CBM mentoring app, and one engagement repository pointer. No skill covers interviewing, designing, a deployment runbook, or maintenance.

The 38 agent profiles are organised by code layer and tier — the organisation chart for building CRMBuilder itself. None corresponds to running a client engagement phase.

Two phase vocabularies exist and this plan adds no third. The Master PRD's thirteen numbered phases are the steps. The seven lifecycle domain records are the phases: Project Definition, Requirements Capture, Specification and Approval, Solution Analysis, Development and Sandbox, Release to Production, Feedback and Upgrades. Software Delivery is CRMBuilder building itself; Governance Recording is cross-cutting.

## 4. Target architecture

The session opens with one question: *What do you want to do today?* with three or four examples drawn from the catalogue. The answer is stored verbatim on the session record, the way close-out payloads already carry the seed prompt.

The answer is classified against the catalogue of kinds of work. The system replies with a one-sentence confirmation in the user's own terms — "It sounds like you want to change a screen on the mentoring app; I will start by confirming what the new field is for." If no catalogue entry matches with confidence, the system asks exactly one follow-up question in plain words. It never asks the user to name a phase or a role.

The kind of work resolves to an ordered list of phase segments. Each segment names a phase profile. Entering a segment calls the existing contract resolver for that profile against the active engagement, which returns the rules, skills, engagement overrides, and learnings to load. Leaving a segment is a natural governance moment: the decision or planning item that the segment produced is written then, before the next segment's rules load.

Five phase profiles hold the rules and skills. A sixth set — the cross-cutting rules — loads in every segment: governance recording, the four writing standards, terminology governance, and commit hygiene where a commit happens.

## 5. The five phase profiles

Each profile below names what it loads and where that content comes from today. "Re-address" means an existing rule whose audience changes; "author" means a rule or skill that does not exist.

**Requirements Interviewer** (Project Definition, Requirements Capture; Master PRD Phases 1 through 3). Loads the conduct charter, kickoff variants, and question library as instruction skills; the seven requirements rules re-addressed from the delivery-pipeline agent; the requirement-authoring readability gate skill. Personas: Engagement Lead and the client's subject-matter experts. Everything here exists; the work is re-addressing and binding.

**Solution Designer** (Specification and Approval, Solution Analysis; Phases 4 through 8 and 10). Loads rules authored from the drafted design-phase candidate requirements once they are ruled on: derive the design from the confirmed inventory, every field traces to a need, defaults are marked as defaulted, coherence and completeness gates before approval, approval recorded as a versioned design. Product names stay out until Solution Analysis chooses a platform. Nearly all of this is to author, and it is gated on the Part C decisions in the design-phase candidate document.

**Application Developer** (Development and Sandbox). Loads the delivery-pipeline discipline that transfers to any build — implement what the design decided, minimal change in your own area, self-verify before complete, blind verification, test observable behaviour, never build on unfrozen ground — plus the thirteen custom web application standards and the coding standards as instruction skills, and the user-review checkpoint rule. The delivery-pipeline rules that are specific to CRMBuilder's own code layers stay with the Software Delivery profiles and are not loaded here.

**Release Operator** (Release to Production; Phases 11 through 13). Loads the deploy rules: production deploy is human-only, every YAML load is validated, links go only in the relationships block, never re-run the clean installer to upgrade, deferred options carry a manual-configuration note, raw audit YAML is not deployable, DNS records are not proxied. Loads the three EspoCRM configuration checks as skills. To author: a deployment runbook skill per platform and a verification checklist skill matching Phase 13.

**Maintainer** (Feedback and Upgrades). Nothing exists. To author: change-request intake (what the user wants, why, who is affected), impact check against the approved design version before any change, the rule that a change re-enters the design as a new version rather than being patched in place, regression before release, and the release cadence. Most client requests after go-live enter through this profile and hand off to the others, so it is authored first among the new content.

## 6. The catalogue of kinds of work, version 0.1

Each entry is the plain-language name a user would recognise, followed by its phase segments. The catalogue lives in the store as process records in the domain each belongs to, so it is governed and rendered like everything else, not hard-coded in a prompt.

Start working with a new organisation — Requirements Interviewer only (Phase 0 and Phase 1).
Define new business processes — Requirements Interviewer, then Solution Designer.
Describe a system you already use — Requirements Interviewer (Phase 1.5 baseline).
Add or change a field or screen in an existing application — Maintainer, Requirements Interviewer (short), Solution Designer, Application Developer, Release Operator.
Build a new application or module from approved requirements — Solution Designer, Application Developer, Release Operator.
Upgrade the platform to the latest version — Release Operator only.
Fix something that is not working — Maintainer, then Application Developer or Release Operator depending on what the intake finds.
Review what has been delivered — Solution Designer (stakeholder review segment) or Maintainer, depending on whether the thing reviewed is a design or a running system.
Ask a question about the system or its records — no phase profile; cross-cutting rules only.

The catalogue is expected to miss requests in its first version. A miss is answered with one follow-up question, and the missed request is recorded as a planning item so the catalogue grows from real use.

## 7. Mechanics across the three surfaces

One implementation serves all surfaces. A session-open operation on the API takes the engagement and the opening answer, classifies it, creates the session record with the answer and the kind of work, and returns the first segment's contract. Segment transitions are a second operation that advances the session and returns the next contract. The Claude Code session hook calls the first operation instead of the flat audience query it runs today, and the pre-command check keeps working unchanged because the contract carries the enforced rules. The claude.ai connector exposes both operations as tools. The desktop application asks the opening question in a dialog and calls the same operations.

A session that opens without an answer — a scheduled run, a resumed session, a hook failure — loads the cross-cutting rules only and says so in its first line. That is the fallback: safe, visible, and never a silent guess at a phase.

## 8. Cleaning up the existing corpus

Three cleanups make the profiles honest and are done before any new content is authored. The seven requirements rules are re-addressed so they load for interviews. The 228 delivery-pipeline rules are bound to the Software Delivery profiles explicitly so they cannot leak into a client session by audience alone. The thirteen-fold tool skills are collapsed to one skill per verb, bound to many profiles, which is what the binding mechanism was built for.

## 9. Work sequence

Step 1, record the decisions. The two rulings in Part 2 become decision records; this plan's steps become planning items; the plan is committed as a discussion draft. Exit: the close-out is applied and the identifiers resolve.

Step 2, cleanup and the two profiles that already have content. Create the Requirements Interviewer and Release Operator profiles from existing rules and skills, re-addressing and binding as in Part 8. Exit: resolving either profile's contract returns the expected rules and nothing from the delivery pipeline.

Step 3, the session-open and segment-advance operations, the catalogue as process records, and the session-record fields (opening answer, kind of work, segments run). Exit: a Claude Code session opened with "define new business processes" loads the Requirements Interviewer contract and records the answer.

Step 4, dogfood on the CRMBUILDER engagement. Run the next three real sessions through the opening prompt. Exit: three session records showing the answer, the classification, the confirmation line, and the segments run, with misses recorded as planning items.

Step 5, author the Maintainer profile and the catalogue's maintenance entries, then the Application Developer profile from the transferable delivery-pipeline rules and the custom web application standards. Exit: "add a field to the intake screen" runs end to end on the CBM mentoring app under changing profiles.

Step 6, the Solution Designer profile, gated on the design-phase decisions. Exit: a design-phase session loads design rules and none from elsewhere.

Step 7, validate on the Cleveland Business Mentors engagement with a real stakeholder session. Exit: the stakeholder never sees a phase name and the session record shows the correct profile loaded.

## 10. Open items, not yet decisions

Whether Project Definition gets its own profile or stays inside Requirements Interviewer; the first version keeps it inside. How the claude.ai sandbox declares its opening answer when the store is unreachable — the close-out payload is the likely carrier. Whether the confirmation line is a rule on the opening step or a fixed part of the operation; the first version makes it part of the operation so it cannot be skipped.

## Revision control

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 0.1 | 09-05-26 01:05 | Claude (claude.ai session with Doug) | First draft from the 09-05-26 architecture review and the two rulings recorded in Part 2. |
