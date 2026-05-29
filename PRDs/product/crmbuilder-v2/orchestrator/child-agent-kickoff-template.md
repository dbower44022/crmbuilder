# Child-agent kickoff — {{session_identifier}} / {{conversation_identifier}}

<!--
PI-082 child-agent kickoff template (WS-012 parallel-agent orchestrator).

This file is a TEMPLATE. The orchestrator driver (PI-081) renders a
concrete copy at dispatch time by substituting every {{placeholder}}
below, then writes the rendered file into the working directory of the
spawned Claude Code subagent. The subagent reads its rendered copy as
its sole kickoff.

Placeholder contract (the driver MUST substitute all of these):
  {{operating_mode}}                 e.g. DETAIL
  {{engagement_code}}                e.g. CRMBUILDER
  {{workstream_identifier}}          e.g. WS-012
  {{workstream_title}}               human-readable workstream name
  {{orchestrator_conversation_identifier}}  the supervising CONV-NNN
  {{session_identifier}}             pre-allocated SES-NNN for this agent
  {{conversation_identifier}}        pre-allocated CONV-NNN for this agent
  {{reserved_identifiers}}           any additional reserved IDs (DEC/PI/…)
  {{branch_name}}                    the child branch already created for the agent
  {{base_branch}}                    branch the child was cut from (e.g. origin/main)
  {{commit_prefix}}                  commit-subject prefix (e.g. "v2:")
  {{areas_claimed}}                  comma-separated area labels this agent owns
  {{areas_claimed_list}}             bulleted list form of the same areas
  {{planning_items}}                 rendered full descriptions of each PI in scope
                                     (identifier, title, executive_summary, area,
                                     full description) from the ready-batches response
  {{planning_item_identifiers}}      comma-separated PI-NNN list (the scope)
  {{close_out_payloads_dir}}         engagement close-out-payloads directory
  {{close_out_payload_path}}         where this agent writes its ses_NNN.json
  {{apply_prompt_path}}              where this agent writes its apply prompt
  {{api_base_url}}                   e.g. http://127.0.0.1:8765
-->

**Operating mode:** {{operating_mode}} (DETAIL is the default for code work — make concrete file-level changes, run tests, commit; do not stay at the architecture level).
**Engagement:** {{engagement_code}}
**Workstream:** {{workstream_identifier}} — {{workstream_title}}
**Dispatched by orchestrator conversation:** {{orchestrator_conversation_identifier}}
**Your branch:** `{{branch_name}}` (already created off `{{base_branch}}` — work only here; do not switch branches).

---

## 1. Who you are in this run

You are one child agent in a parallel orchestrator run. The orchestrator has partitioned the open backlog by **area** so that no two agents touch the same files at once. You own the areas listed in §4 and the planning items in §3. Other agents are running concurrently against other areas on their own branches — **stay inside your claimed areas** (§4) so the run stays conflict-free.

You have been pre-allocated the governance identifiers in §2. Use exactly those — do **not** compute next-available identifiers yourself (other agents may be writing records at the same time; the orchestrator reserved yours to avoid collisions).

## 2. Pre-allocated identifiers

| Purpose | Identifier |
|---|---|
| Your session | `{{session_identifier}}` |
| Your conversation | `{{conversation_identifier}}` |
| Additional reserved | {{reserved_identifiers}} |

Write your close-out under these identifiers. If you need an identifier you were not allocated (a new DEC, PI, etc.), reserve it via `POST {{api_base_url}}/identifiers/reserve` with `{entity_type, count}` before using it — never grab next-available directly.

## 3. Planning items in scope

Resolve (or, where the work only advances them, address) the following planning items. Full descriptions are inlined so you do not need to re-fetch them:

{{planning_items}}

Scope identifiers: {{planning_item_identifiers}}

A planning item **resolves** only when your close-out payload lists it in `resolves_planning_items`. If your work advances but does not finish an item, list it under `addresses_planning_items` instead.

## 4. Areas you have claimed — and the conflict rule

You own these areas for this run:

{{areas_claimed_list}}

**Conflict rule (hard):** edit only files that belong to your claimed areas ({{areas_claimed}}). If completing your planning items appears to require touching a file outside your areas, **stop and report it in your close-out** rather than editing it — another agent may own that file in this same wave. Cross-area work is the orchestrator's to sequence, not yours to grab.

## 5. Orientation reads (do these first)

- `crmbuilder/CLAUDE.md` — the operative engagement context. Confirm at session open before any work.
- `specifications/governance-recording-rules.md` — the authoritative governance recording rules. Read before authoring any governance record. Record creation goes through the API or `apply_close_out.py`, **not** the desktop UI.
- The planning items in §3 cite their own design docs; read the ones relevant to your scope.

## 6. How to work

1. Confirm the API is up: `GET {{api_base_url}}/health`.
2. Implement each planning item in §3 on branch `{{branch_name}}`, in DETAIL mode: concrete edits, tests, and a commit per logical unit.
3. Run the test suite for the areas you touched before committing. Do not mark a planning item done with failing tests.
4. Keep every change inside your claimed areas (§4).

## 7. Close-out (required)

Produce the standard triple-artifact close-out — this is how your work becomes durable and how the orchestrator records your run:

1. **Content deliverable** — your commits on `{{branch_name}}`, each subject prefixed `{{commit_prefix}}`.
2. **Close-out payload** at `{{close_out_payload_path}}` — a nine-section JSON (`session`, `conversation`, `work_tickets`, `planning_items`, `commits`, `decisions`, `references`, `resolves_planning_items`, `addresses_planning_items`; list empty sections too). Use your pre-allocated `{{session_identifier}}` / `{{conversation_identifier}}`. List the planning items you finished under `resolves_planning_items` and any you only advanced under `addresses_planning_items`. Record your commits in the `commits` section.
3. **Apply prompt** at `{{apply_prompt_path}}` — documenting pre-flight checks, the apply command, and post-apply verification.

Apply your own payload with:

```
uv run python scripts/apply_close_out.py {{close_out_payload_path}}
```

then commit the regenerated `db-export/*.json` snapshots + the new `deposit-event-logs/dep_NNN.log` + your content deliverable + payload + apply prompt in one commit.

Do **not** create the `conversation_orchestrates_conversation` edge from the orchestrator to your conversation — the orchestrator owns that edge and writes it when it ingests your close-out.

## 8. If you get stuck

Halt and write what blocked you into your close-out (or, if you cannot reach close-out, leave a short note in the working directory). Do **not**: switch branches, touch files outside your claimed areas, grab unreserved identifiers, or force any git operation. The orchestrator leaves your planning-item claims in place on failure for forensic review; a human will pick it up.
