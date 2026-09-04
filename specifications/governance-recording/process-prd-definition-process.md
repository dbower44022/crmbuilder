# Process PRD Definition Process — Process PRD

| Field | Value |
|-------|-------|
| Version | 0.3 |
| Last Updated | 09-04-26 01:20 |
| Status | DISCUSSION DRAFT — render of process record PROC-011 (supporting, domain DOM-012) as of 09-04-26 |
| Audience | Anyone about to author a Process PRD for any domain in any engagement; the Engagement Lead as approver |
| Governs | Nothing on its own. The process record PROC-011 and its links in the V2 store are the source (DEC-393, DEC-394, DEC-1021); this file is a render and goes stale between renders |

## Purpose

This document renders the Process PRD Definition Process as recorded in the V2 store: the meta process DEC-311 asked for, describing how a Process PRD is authored, written from the practice that produced PROC-010 (PI-087) and used earlier for the domain (PI-085) and the personas (PI-086). Each step cites the record the PI-087 run actually produced. It exists so a reader of the repository can review the process without opening the store. When this file and the store disagree, the store is right and this file needs re-rendering. Produced under PI-088 (REQ-411) per DEC-311; rulings DEC-1039 to DEC-1041 applied. Engagement ENG-001, project PRJ-023.

## 1. Process metadata

| Field | Value |
|---|---|
| Name | Process PRD Definition Process |
| Domain | DOM-012 Governance Recording. PI-088 floated a "methodology-authoring" domain; the confirmed nine-domain model (DEC-1003) has none, every step here is a recording act, and the process runs in any domain of any engagement, so it is cross-cutting the way DOM-012 is. |
| Owner persona | Engagement Lead (PER-013): rules every open question, approves the write, pushes |
| Performing personas | Claude Code Agent (PER-014); Claude.ai Sandbox Agent (PER-015) by payload |
| Classification | `supporting` (DEC-1040). If this process stopped, Process PRDs would still be produced, unevenly, and the store would still be the source of truth, because PROC-010 (mission_critical) is what keeps every session on the record; what would be lost is consistency of shape and precedent. The first non-mission_critical process record; the gate is one-way only out of `unclassified` (process spec §3.4), so it can be raised if the meta process proves load-bearing. |
| Version | 0.2 |

## 2. Trigger

A new process within an existing domain is identified and needs a Process PRD: named as a candidate in a Domain Overview (PROC-010 was item 1 of the DOM-012 overview §5), raised by a decision (DEC-311 named PI-087 and PI-088), or surfaced as cross-session work (PROC-010 step 8). The trigger is complete only when a confirmed requirement and an implementing planning item exist; GVR-230 applies to a Process PRD as to code.
*Evidence: DEC-311; REQ-410 confirmed, PI-087 in PRJ-023; REQ-411, PI-088.*

## 3. Inputs

The Domain Overview (for DOM-012, `specifications/governance-recording/domain-overview.md` v0.4, a render of DOM-012); the persona records the domain names (PER-013..015); the rules corpus the process must encode (TOP-013 and children, effective governance rules, lessons on demand); prior Process PRDs as precedent (PROC-002..010; PROC-010 the fullest); the POST /processes schema (`ProcessCreateIn` in `/openapi.json`: name, domain, purpose required; classification, rationale, notes, steps, triggers, outcomes, edge cases, frequency, duration optional) and the reference vocabulary (`access/vocab.py`); the observed practice, that is, the sessions and decisions in which the process already ran informally.
*Evidence: DEC-1021; DOM-012; PROC-010; TOP-013.*

## 4. Steps

**Agent** = Claude Code Agent or, by payload, Claude.ai Sandbox Agent. **Lead** = Engagement Lead. Times are UTC, 2026-09-04.

| # | Step | Persona | Condition | Recorded | Evidence, PI-087 run |
|---|---|---|---|---|---|
| 1 | **Anchor and gather context.** Confirm the requirement is confirmed and its implementing planning item exists inside a project; open or continue the session and a conversation that `addresses` the item; read the §3 inputs. | Agent | Always | Conversation, `addresses` edge | REQ-410 confirmed; PI-087 in PRJ-023 (REF-6093); CNV-360 `addresses` PI-087 (REF-9039) |
| 2 | **Draft v0.1 with open questions and a store payload.** Usually a subagent of the orchestrating session, writing to scratch only: the eleven sections of this template, every step with persona, condition, record and evidence; each unsettled point as an open question with labelled options, costs and a recommendation; a payload with the POST body and every edge, each kind checked against `vocab.py` for its pair, plus any entity records the process needs that do not yet exist; unapproved terms flagged. No store write, no repository change. | Agent | Always | Nothing | PI-087 v0.1, 09-03, five open questions (render change log); the orchestrator's recommendation on Q5 quoted in DEC-1038; this draft's Q1 became DEC-1039 |
| 3 | **Render and present.** Put the draft to the Lead as a page, open questions and payload visible; the Lead reads before any question is asked. | Agent; Lead reads | Always | Nothing | DEC-1034..1038 each open "PI-087 open question N", the draft's numbering |
| 4 | **Rule one question at a time, after the parallel-ruling check.** Immediately before each question, re-read decisions `is_about` the planning item recorded since the draft was read and look for a live peer session on it; a ruling already recorded is answered. Then one question per message: labelled options, costs, recommendation. | Agent asks; Lead rules | Each open question | Nothing yet | Five rulings, one at a time: 04:20, 04:23, 04:25, 04:26, 04:28. The failure guarded against: DEC-1024 superseding DEC-1018/1020 (LSN-074). This draft: DEC-1039, DEC-1040, DEC-1041 |
| 5 | **Record each ruling at that moment.** Decision in the eight-element template, Active, executive summary; `decided_in` → session; `is_about` → planning item and each affected record. A ruling that becomes code: record the requirement, approve it by this decision, file the implementing planning item, before the next question. A candidate not ruled is named in consequences, not filed. | Agent | Each ruling | Decision; edges; Requirement and Planning Item when code follows | DEC-1034 `decided_in` SES-388 (REF-9289), `is_about` PI-087, REQ-087, REQ-092; REQ-560 defined in CNV-360, approved by DEC-1034 at 04:20:51, PI-462 implements; DEC-1035 → REQ-561, PI-462 second slice; DEC-1036 names a candidate, files nothing |
| 6 | **Revise to v0.2 applying the rulings.** Close every open question in a "rulings applied" section; update the affected steps, edge cases, acceptance criteria and the payload. | Agent | After the last ruling | Nothing | PROC-010 notes "Rulings applied in v0.2: DEC-1034 .. DEC-1038"; render change log 0.2; this v0.2 |
| 7 | **One approval gate for the write.** The record inlined field by field, the edge list and any entity records in the batch, mechanical items (timestamps, manifest row) separated from semantic; no conditional plan. | Agent asks; Lead approves | Before any POST | Nothing | PI-087 resolution_reference "written 2026-09-04 on Doug approval"; GVR-237 |
| 8 | **Write and verify.** POST any entity records the batch carries, then POST /processes; assert each identifier matches `^[A-Z]{2,4}-[0-9]+$` before any edge; POST each edge; `is_about` from each ruling to the new record; GET it back and count edges against the payload. | Agent | After approval | Process; Entity records when needed; References | PROC-010 04:40:58; REF-9313..9336 by 04:41:04; REQ-410 `requirement_realized_by_process` (REF-9333); DEC-1037/1038 `is_about` PROC-010 (REF-9338/9339). Entity records in the batch: ENT-045..058 with DOM-012 (DEC-1013); Process, Domain, Persona with this record (DEC-1039) |
| 9 | **Render and commit.** A dated render headed as a render of the record (DEC-1021); a row in `specifications/README.md`; commit with a pathspec and `Governed-By` (`trivial` plus `Exemption-Reason` for a render-only commit). No push. | Agent commits; Lead pushes | After the write | Commit row only when code is touched | 6cc02c3e, 04:41:58: render v0.3 and manifest row, `Governed-By: trivial` with reason |
| 10 | **Resolve after the push.** Verify with `git merge-base --is-ancestor <sha> origin/main`; then the delivering conversation gets `resolves` → planning item, resolution_reference naming record, rulings and render. The rule is uniform: the push that carried the item's last commit, render or code, gates the resolve (DEC-1041). If the session ends first, hand the resolve forward (PROC-010 steps 17–18). | Agent, after the Lead's push | Push verified | `resolves` edge | DEC-1041; LSN-077. CNV-360 `resolves` PI-087 (REF-9337) at 04:41:25, before the render commit and before any push, recorded as out of order in §11 |
| 11 | **Close under PROC-010.** Close-out completeness audit, conclude the conversation, complete or hand forward the session. | Agent | Always | Per PROC-010 | PROC-010 §9; SES-388 and CNV-360 still `in_flight`, the run being one lane of a longer session |
| 12 | **Observe and improve this meta process.** Compare the run with these steps. A hazard or how-to becomes a lesson (`lesson_derived_from`); a changed step is a decision `is_about` this process, applied to the record and re-rendered; a new rule is its own decision (REQ-543). | Agent proposes; Lead approves | After each run | Lesson; Decision; re-render | LSN-074 filed from DEC-1024; LSN-077 filed from DEC-1041 and the PI-087 run; this record itself, drawn from PI-087's practice as DEC-311 required |

## 5. Entities touched

| Entity | Read | Created | Updated |
|---|---|---|---|
| Process (candidate entity record created with this process, DEC-1039) | prior processes (1) | the process record (8) | classification later, if raised |
| Domain; Persona (candidate entity records created with this process, DEC-1039; no domain scope edge, they are methodology objects) | 1 | — | — |
| Decision ENT-047 | 4 | 5 | — |
| Requirement (table-style ENT-013 only); Planning Item ENT-040 | 1 | 5, when a ruling becomes code | approved by decision (5); resolved by edge (10) |
| Reference ENT-050 | 4 | 1, 5, 8, 10, 12 | — |
| Session ENT-045; Conversation ENT-046 | 1 | 1 | 11 |
| Commit ENT-051 | — | 9, code only | — |
| Governance Rule ENT-055; Preference ENT-056; Lesson ENT-057; Reference Pointer ENT-058 | 1 | Lesson (12) | — |

## 6. Personas involved

Engagement Lead PER-013: owner; reads at 3, rules at 4, approves at 7, pushes before 10, approves at 12. Claude Code Agent PER-014: steps 1–12 with the live store. Claude.ai Sandbox Agent PER-015: the same, decisions authored in the working material and the write carried by the close-out payload the Lead applies (PROC-010 step 20). In a client engagement the customer persona who owns the domain rules alongside the Lead; the agent still records.
*Evidence: PER-013..015; DEC-1009, DEC-1022.*

## 7. Exception handling

- **A parallel session already ruled.** The ruling is answered; revise to it without asking. Two rulings: the earlier stands, the later is superseded by decision. *LSN-074, DEC-1024.*
- **A term is needed.** Flag `[TERM NEEDS APPROVAL]`, use it descriptively, put it to the Lead as its own question; the glossary entry follows approval. *GVR-232; DEC-1022, DEC-1023.*
- **A ruling becomes code.** Requirement-first inside step 5; the Process PRD says what stands until the code lands. *GVR-230; DEC-1034 → REQ-560 / PI-462; DEC-1035 → REQ-561.*
- **An entity the process touches has no record.** Create the candidate record in the confirmed style in the same write batch and edge it; a scope edge only where the object belongs to a domain. *DEC-1013, DEC-1039.*
- **An unacceptable draft.** The objection is a decision `is_about` the planning item stating what changes; back to step 2 at the next minor version; nothing written. *REQ-085, GVR-237.*
- **A create that fails.** 200 with `errors`; the identifier assertion stops the edge loop; read the body, fix, audit for dangling edges. *LSN-056.*
- **A ruling against the recommendation.** Record the ruling and the rejected recommendation in alternatives_considered; follow the ruling. *DEC-1038.*
- **Push not landed at session end.** Hand the resolve forward; the next session verifies and fires it; a render commit counts. *DEC-1036, DEC-1041, LSN-077.*

## 8. Anti-patterns

| Anti-pattern | Recorded by |
|---|---|
| Asking a draft's question without re-reading the store for rulings on the item | LSN-074 |
| Several questions in one message, or options without costs and a recommendation | PRF-002, PRF-009, GVR-237 |
| Edges from an unchecked create response | LSN-056 |
| A name coined in the draft without a flag | GVR-232 |
| A ruling that becomes code, with no requirement and planning item before the next question | GVR-230 |
| An approval request citing the record by identifier, or bundling semantic decisions in one gate | GVR-237 |
| Resolving before the push, or by status edit; treating a render-only commit as outside the rule | LSN-047, LSN-066, DEC-1036, DEC-1041, LSN-077 |
| Patching the markdown as if it were the source | DEC-1021, GVR-238 |
| Holding rulings in the transcript until close-out with the store reachable | GVR-231, DEC-310 |

## 9. Acceptance criteria

From the store and repository alone, the run produced a Process PRD that PROC-010's close-out completeness audit can validate:

1. The process record exists with every `ProcessCreateIn` field populated; notes name the rulings and the render path.
2. Edges: `process_performed_by_persona` to each performing persona; `process_touches_entity` to each entity record read or created, including any created in the batch; `requirement_realized_by_process` from the requirement; `references` to the decisions and processes it rests on; `is_about` from each ruling.
3. Each open question is a decision with `decided_in` → session and `is_about` → planning item, created at the moment of ruling (separate timestamps, not a batch).
4. Each ruling that becomes code has a requirement approved by that decision and an implementing planning item.
5. A dated render is committed with a manifest row and a `Governed-By` trailer.
6. The planning item is resolved by `resolves` from the delivering conversation after the push that carried the render, with a resolution_reference naming the record (DEC-1041).
7. Every term is in the glossary or flagged; no reference has a malformed identifier.

## 10. Outputs

The process record and its edges (the Process PRD); candidate entity records where the process touched an object with no record; a decision per ruling; requirements and planning items for rulings that become code; the committed render and manifest row; the resolved planning item; a lesson or amending decision from step 12.

## 11. Rulings applied

1. **DEC-1039** (Q1, option A): candidate entity records Process, Domain and Persona are created in the confirmed style in the same write batch as this process and edged from it with `process_touches_entity`; no domain scope edge, they are methodology objects, not governance objects. The payload carries the three records and their edges unconditionally.
2. **DEC-1040** (Q2, option A): classification `supporting`, the first non-mission_critical process record; raisable later if the meta process proves load-bearing.
3. **DEC-1041** (Q3, option A): resolve-after-push is uniform; every planning item resolves only after the push that carried its last commit, render or code, since a committed render is part of what delivered means under DEC-1021. Step 10 stands as drafted; PROC-010 audit item 8 needs no carve-out.

**Finding, recorded.** The PI-087 run fired `resolves` (REF-9337, 04:41:25) before the render commit (6cc02c3e, 04:41:58) and before any push. Under DEC-1041 that order was wrong; the edge stands and the order is recorded as out of order, not re-ordered (PROC-010 step 15). LSN-077, the lesson derived from DEC-1041 and the PI-087 run (`lesson_derived_from` DEC-1041): verify the write, commit the render, wait for the push, then fire `resolves`.

**Not open.** No positive evidence for a domain other than DOM-012; PI-088's "methodology-authoring" candidate is not raised.

**[TERM NEEDS APPROVAL]:** "Process PRD" is used from DEC-311 onward and names two committed renders but has no glossary entry; a TERM record is proposed, not a coinage. "Meta process" is PI-088's phrase, used descriptively, not proposed as a term.

## Change log

| Version | Date | Change |
|---|---|---|
| 0.1 | 09-04-26 | Drafted from the PI-087 run (SES-388 / CNV-360, DEC-1034..1038, PROC-010) under PI-088 / REQ-411 per DEC-311; three open questions. |
| 0.2 | 09-04-26 | Rulings DEC-1039 (entity records Process, Domain, Persona), DEC-1040 (supporting) and DEC-1041 (resolve-after-push uniform, LSN-077) applied. |
| 0.3 | 09-04-26 01:20 | First committed render. Process record PROC-011, entity records ENT-059 to ENT-061 and twenty-four links written to the store on Doug's approval (SES-388 / CNV-360). PI-088 resolves after this render is pushed (DEC-1041). |
