# CLAUDE-CODE-PROMPT: Step 2 of the phase-specific governance plan — corpus cleanup and the first two phase profiles (PI-486, PI-487)

Operating mode: DETAIL. Read `CLAUDE.md` at the repository root first, then `PRDs/product/crmbuilder-v2/phase-governance-plan.md` in full. The plan's Parts 5 and 8 are the specification for this prompt; do not re-derive them.

## Purpose

After this prompt, a session that resolves the Requirements Interviewer profile receives the interview rules and conduct skills and nothing from the delivery pipeline, and a session that resolves the Release Operator profile receives the deployment rules and configuration checks and nothing else. The delivery-pipeline rules are bound explicitly to the pipeline's own profiles so they can no longer reach a client session by audience alone, and the duplicated tool skills are collapsed to one per verb.

**Net Effect (expected; Part A confirms the counts before anything is written):**
- 2 new agent profiles, system scope: Requirements Interviewer; Release Operator
- 4 new instruction skills, system scope: the conduct charter, the kickoff guide, the question library (each from `PRDs/process/conduct/`), and a Phase 13 verification checklist drawn from the Master CRMBuilder PRD
- Bindings on the Requirements Interviewer: the seven requirements rules (GVR-194, GVR-195, GVR-198, GVR-200, GVR-201, GVR-202, GVR-206), the three conduct skills, and the requirement-authoring gate (SKL-102)
- Bindings on the Release Operator: the deployment rules (GVR-240, GVR-173, GVR-170, GVR-162, GVR-163, GVR-161, GVR-171, GVR-172, GVR-209, GVR-210, GVR-182), the three configuration-check skills (SKL-099, SKL-100, SKL-101), and the verification checklist
- Explicit bindings of every active delivery-pipeline rule (audience `ado_agent`) to the pipeline profiles that lack one
- Tool skills collapsed: one skill per distinct verb and callable, bound to every profile that held a copy; the copies retired, not deleted
- 2 planning items moved to In Progress at start and Complete at end: PI-486, PI-487
- No code change is expected. If Part A finds one is needed, the requirement-first rule applies: a confirmed requirement and an implementing planning item exist before any code, authored through the readability gate (SKL-102). Do not edit a status field to get there.

Every record write goes through the API in real time (the governance-recording rule). Nothing is batched into a close-out payload.

---

## Pre-flight

```bash
cd ~/Dropbox/Projects/CRMBuilder && pwd
git status
git pull --rebase origin main
curl -s http://127.0.0.1:8765/health -H "X-Engagement: CRMBUILDER"
curl -s "http://127.0.0.1:8765/sessions/next-identifier" -H "X-Engagement: CRMBUILDER"; echo
# Expected: SES-407 or later. If SES-406 is still the next identifier, the close-out has not been applied — stop and say so.
curl -s "http://127.0.0.1:8765/planning-items/PI-486" -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(d['identifier'], d['status'], d['title'][:60])"
curl -s "http://127.0.0.1:8765/planning-items/PI-487" -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(d['identifier'], d['status'], d['title'][:60])"
```

Open the session record now (session medium `claude_code`, anchored on PI-487, belonging to PRJ-023) and one conversation for this work, before any other write.

---

## Part A — inventory and one decision, then stop

Read-only. Produce the numbers, then put the one question below to the product owner and wait.

1. **Rules.** List active governance rules with audience `ado_agent`. For each, find whether an `agent_profile_governed_by_rule` reference or a registry binding already ties it to at least one agent profile. Report: total, already bound, unbound.
2. **Tool skills.** Group active tool skills by `(name, backing_callable)`. Report each group with more than one member, the member identifiers, and which profile each member is bound to. Expected: the claim, update-status and release verbs on work tasks, and the read-planning-item and read-prior-area-outputs reads.
3. **The seven requirements rules and the eleven deployment rules.** Confirm each identifier above still exists, is active, and its body matches the plan's description. Report any that differ.
4. **The profile tier.** Read `AgentProfileRow` in `crmbuilder-v2/src/crmbuilder_v2/access/models.py` and `AGENT_PROFILE_TIERS` in `access/vocab.py`. Report whether `tier` is constrained only in Python or also by a database CHECK, and whether the contract resolver or any binding logic branches on tier.

Then stop and ask exactly this, in this shape, and nothing after it:

> **Which tier value do the phase profiles carry?** The registry allows architect, developer, tester, orchestrator and pi_lead, all of which describe a seat in the delivery pipeline. Option 1: carry `orchestrator` for now — no code change, but the value is a loose fit and every reader of the registry will wonder why an interviewer is an orchestrator. Option 2: add a `phase` tier — an honest value, at the cost of a vocabulary change (and a migration if the CHECK is in the database), which under the requirement-first rule needs a confirmed requirement and an implementing planning item before the code moves. Recommendation: Option 1 now, with a planning item raised for Option 2, so Step 2 lands today and the vocabulary is corrected under its own requirement. Please choose.

Do not proceed to Part B until the product owner has answered.

---

## Part B — execute, without further confirmation

Move PI-486 and PI-487 to In Progress.

**B1. Skills.** Create the four instruction skills. The description of each conduct skill is the document's own text, unedited, with a one-line header naming its source path and the date it was copied; the verification checklist is drawn from the Master CRMBuilder PRD's Phase 13 section and says so. System scope, kind `instruction`, version 1.

**B2. Profiles.** Create the two agent profiles, system scope, with the tier the product owner chose. `area` values: `requirements-capture` and `release-to-production` (the lifecycle domain names as slugs; the plan's Decision 3 makes the domain records the phase vocabulary). The `description` is the system-role prompt for the profile, written in plain language for a reader who has not read the store: what the profile is for, which phase it serves, what it must never do (an interviewer never records an inference as fact without the stakeholder's confirmation; a release operator never executes a production deploy). `capability_description` carries `summary`, `specialties`, `builds`, `constraints`.

**B3. Bindings.** Bind rules and skills to each profile through `POST /agent-profiles/{identifier}/bindings` (system scope, mode `bind`). Do not change any rule's `applies_to`; the audience filter is replaced by the contract in Step 3 of the plan, not here.

**B4. Pipeline rules.** For every active `ado_agent` rule Part A found unbound, bind it to the pipeline profiles for its area (the rule's `rule_type` prefix names the area: `storage_`, `access_`, `api_`, `mcp_`, `ui_`, `automation_`, `infra_`, `espo_`, `programs_`; the unprefixed planning and release rules bind to the planning, model and release profiles). Report any rule whose area cannot be read from its type rather than guessing.

**B5. Tool skills.** For each duplicate group from Part A: keep the lowest identifier, bind it to every profile that held a copy, and set each copy's status to `retired`. Retain, never delete.

**B6. Verify.** For each of the two new profiles, call `GET /agent-profiles/{identifier}/contract` and check: the rules are exactly the bound set; no rule of audience `ado_agent` outside that set appears; the instruction skills appear in the system prompt; the enforced ruleset contains the human-only production deploy rule for the Release Operator and nothing enforced for the Requirements Interviewer. Then resolve one pipeline profile (the storage developer) and confirm its contract is unchanged in rule count except for any newly bound rules from B4.

**B7. Close.** Record one decision if the product owner chose Option 2 in Part A (the tier vocabulary change) or if any body in B2 required a judgment the plan does not settle; otherwise no decision. If Option 1 was chosen, raise a planning item for the `phase` tier. Move PI-486 and PI-487 to Complete with the verification output as the resolution note. Close the conversation and the session with executive summaries in the 200-to-800-character range. If any code changed, commit with an explicit pathspec and a `Governed-By: PI-487` trailer and push.

---

## Done

Reply with the review list and nothing else: profiles created (identifiers), skills created (identifiers), binding counts per profile, pipeline rules bound in B4, tool skills retired in B5, the two contract checks from B6 in one line each, the session and conversation identifiers, and any commit SHA. Then **What next**: Step 3 of the plan (PI-488, the session-open and segment-advance operations and the catalogue), with the note that it is the first step that changes code and needs its requirements authored first.
