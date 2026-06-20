# The multi-agent release pipeline — annotated whole-picture map

**Document type:** Architecture orientation / synthesis (the running pipeline, end to end, with every gap + decision marked).
**Status:** Working map from the SES-216 architecture walk (PRJ-039 / TOP-099; observability PRJ-040 / TOP-100). **DB requirement/decision records are authoritative; everything here points to them.** Requirements are candidate / needs_review — nothing built from this walk yet.
**Last updated:** 06-20-26 (SES-216)

---

## How to read this

The pipeline is **two org models stacked**. A release flows top to bottom. At each
step an agent (LLM) or substrate (deterministic code) acts, then a gate decides
whether to advance. The columns below: **what acts**, **what it's told**, **what
checks its output**, and **the gap** (with the governing requirement).

Legend: 🟢 well-designed · 🟡 weak/advisory · 🔴 missing/broken · ⚙️ deterministic substrate · 🤖 LLM agent

---

## The flow, top to bottom

```
HUMAN assembles scope (projects → PIs → confirmed requirements) and FREEZES the release
   │   (freeze gate: development_planning → reconciliation — the human/conductor handoff)
   ▼
LAYER A — THE CONDUCTOR  ⚙️  (runtime/release_runtime.py)
   │   status-driven step machine; one frozen release; position = release_status (12 states)
   │   re-reads live DB each tick; picks the ONE next step
   ▼
LAYER B — PLANNING AGENTS (fixed seams, called by pipeline position, NOT queue-dispatched)
   │
   ├─ 1. RECONCILIATION / DEMANDS  🤖 AGP-003 (model/architect)
   │      in : confirmed in-scope requirements  ← 🔴 no already-delivered filter (REQ-265)
   │      out: the demand-set (the change-list)
   │      check: format/schema + a contradiction-catcher (open conflict → conductor HALTS for a human)
   │      🔴 no content check: not vs requirements, not for completeness, not for already-built
   │      🟡 prompt over-claims authority (says it resolves conflicts / re-runs — conductor + human do) (REQ-278)
   │
   ├─ 2. ARCHITECT / DECOMPOSITION  🤖 AGP-004 (planning/architect)
   │      in : the reconciled change-list  ← 🔴 told to TRUST it, never validate (REQ-279)
   │             🔴 fed the WHOLE release's deltas for every PI (REL-005 over-production, REQ-266)
   │      out: (a) the blueprint (vN+1 designs) + (b) the build plan (workstreams + work tasks)
   │      check: 🟡 create-time well-formedness (REQ-258, confirmed) — but 🔴 NOT re-validated before
   │             execution, so a stale/malformed graph from a prior run is inherited (REL-005 deadlock, REQ-274)
   │      🔴 emits NO per-task acceptance criteria / done-condition (REQ-278)
   │      🔴 no size→task-count discipline (16 tasks for 2 trivial reqs, REQ-276)
   │
   ▼   ── architect "finalizes" → plan is FROZEN → dev lane opens. All judgment is meant to be over. ──
   │
LAYER C — ADO DEV-ORG (mostly ⚙️ substrate; only the workers are 🤖)
   │   PM ⚙️ → PI Lead ⚙️ → Phase Specialist ⚙️ → AREA SPECIALIST 🤖 (the workers)
   │
   ├─ 3. WORKERS — AREA SPECIALISTS  🤖  (one per area × phase; spawned `claude -p` in a worktree)
   │      THE WEAKEST + MOST NUMEROUS LEVEL — most failure modes live here.
   │      contract = registry card + operating protocol, stacked.
   │      🔴 only ONE worker profile exists (AGP-002 storage/developer); every area gets it with
   │         `{AREA}` string-substituted — no per-area dev/tester cards, no enforced area rules (REQ-273)
   │      🟡 only ONE enforced rule (self-verify tests); everything else advisory (REQ-278)
   │      🔴 no "step 0: already done? / inputs sane?" → manufactures filler (REQ-267, REQ-279)
   │      🔴 no done-condition beyond "tests green" (REQ-278)
   │      🔴 commit is step 3 AFTER the work → a kill loses everything (WTK-176, REQ-270)
   │      🔴 self-verify has no time budget, no "run synchronously" → 13-min spin to SIGKILL (REQ-269/271)
   │      🔴 no halt/escalate exit → detects duplicate work but must finish anyway (REQ-272)
   │      🔴 wrong build unit: one process PER WORK TASK per PI, not one per area-phase batch (REQ-283)
   │
   ▼
   ├─ VERIFY + MERGE (per area)  ⚙️  — verify by RESULT (task Complete + branch has commits),
   │      run affected tests, merge the branch. 🟢 commit-before-verify fixed for the runtime side;
   │      🟡 "Complete" is a soft signal (no acceptance criterion behind it).
   │
   ├─ PHASE GATE (PI Lead `complete_phase`)  ⚙️  — advances a phase when ALL tasks Complete.
   │      🔴 the confirmed CROSS-AREA COHERENCE CHECK (REQ-027/031) is UNBUILT — the `finding`
   │         substrate (PI-134) exists but is not wired; phase advances on "all Complete" alone.
   │         (REQ-027/031 amended to RELEASE scope, DEC-556; gate-wiring is a build gap.)
   │
   ▼
LAYER A again — RELEASE-LEVEL GATES  (the conductor, via the Release Lead)
   │
   ├─ 4. QA GATE + TEST GATE  🤖 AGP-005 (release/pi_lead) via runtime/release_gate.py
   │      🟢 THE MODEL TO COPY: deterministic FAIL-CLOSED FLOOR (no confirmed reqs / no designs →
   │         cannot pass, no LLM) + grounded LLM judgment over the REAL records + structured findings.
   │      QA = design COVERS every requirement, no cross-area contradiction.
   │      Test = key processes hold END-TO-END across areas ("a green per-area unit is NOT a process").
   │      🟡 AGP-005 enforced_ruleset empty (3 advisory rules); 🟡 prompt over-claims like AGP-003 (REQ-278)
   │      ⚠️ currently the ONLY place cross-area coherence is checked (because the phase gate isn't) —
   │         so a mismatch is caught at the finish line, after all build cost is spent.
   │
   ▼
   deployment → shipped
```

---

## The cross-cutting truths (what the whole map says)

1. **LLM judgment lives in only 4 places** — demands (AGP-003), decomposition (AGP-004),
   the workers (AGP-002 only), the gates (AGP-005). Everything else is ⚙️ substrate. So
   "fix the agents" = fix 4 contracts + the substrate guardrails around them.

2. **Almost nothing checks CONTENT.** Format checks + a contradiction-catcher + "all tasks
   Complete" are the only gates until the very end. Agents are told to TRUST inputs. The
   one real content judgment (the release gate) is excellent — and isolated at the finish.
   → REQ-279 (validate handoffs both sides), REQ-027/031 (wire the earlier coherence gate).

3. **The registry shelf is built but nearly empty.** 5 profiles; 1 worker card for all
   areas; all rules advisory. The mechanism for strict, enforced, per-(area×tech×tier)
   contracts exists and is unused. → REQ-278, 280, 281, 273.

4. **Prompts don't match behavior.** AGP-003 and AGP-005 both describe agency the
   deterministic conductor actually owns. → REQ-278 ("must match what the agent does").

5. **The good pattern already exists — propagate it.** The release gate's *fail-closed
   floor + grounded judgment + structured findings* is the template to lift the worker
   contracts and the phase gate toward. Don't invent; propagate.

6. **Observability is fragmented.** Durable position in DB statuses; ephemeral stdout
   (conductor `ReleaseRunReport`, runtime `self.log` → `print`); rich agent reasoning in
   scattered `~/.claude` transcripts. No single durable progress/agent-activity log.
   → REQ-277 (PRJ-040 / TOP-100).

---

## Where each governing requirement lands on the map

| Level | Gap | Requirement(s) | State |
|---|---|---|---|
| Reconciliation input | dispatched already-delivered work | REQ-265 | candidate (orig 12) |
| Architect input | fed whole release, not one PI | REQ-266 | candidate (orig 12) |
| Architect output | no re-validation before execution | REQ-274 (narrowed) | candidate · refines REQ-258 |
| Architect output | task count disproportionate | REQ-276 | candidate (orig 12) |
| Architect output | no per-task acceptance criteria | REQ-278 | candidate · refines REQ-021 |
| Worker | no already-done / no-op exit | REQ-267 | candidate (orig 12) |
| Worker | design re-documents shipped work | REQ-268 | candidate (orig 12) |
| Worker | commit after work (kill loses it) | REQ-270 | candidate (orig 12) |
| Worker | unbounded self-verify spin | REQ-269, REQ-271 | candidate (orig 12) |
| Worker | no halt/escalate | REQ-272 | candidate (orig 12) |
| Worker | wrong-area card | REQ-273 | candidate · refines REQ-252 |
| Worker | validate inputs before starting | REQ-279 (narrowed) | candidate · refines REQ-057 |
| Worker | strict contract w/ deliverables + reporting | REQ-278 | candidate · refines REQ-021 |
| Worker | hard tech/design constraints | REQ-280 | candidate · refines REQ-021 |
| Worker | technology variants of one area | REQ-281 | candidate · refines REQ-018 |
| Worker | build unit = area-phase batch | REQ-283 | candidate · refines REQ-061 (DEC-554) |
| Phase gate | coherence check unbuilt + per-PI scope | REQ-027, REQ-031 | needs_review, release scope (DEC-556); UNBUILT |
| Plan layout | per-PI granularity superseded | REQ-024 | needs_review (DEC-555) |
| Whole pipeline | progress/activity not durable/queryable | REQ-277 | candidate (TOP-100) |
| (rejected) | catalog of defaults — already confirmed | REQ-282 | REJECTED dup (DEC-553) |

**Already CONFIRMED in TOP-005 (the baseline this builds on):** system-default agent
team (REQ-004/044), per-engagement customization (REQ-045/046/047/006), per-area experts
with own skills/rules (REQ-017/021), one-task-one-area (REQ-018), plan splits by area
(REQ-024), design→develop→test passes with per-area specs (REQ-026/028/029), coherence
check exists (REQ-027/031), scheduler verifies result before advancing (REQ-057),
single-train-of-thought per area in design (REQ-208), standing area expert across the
release (REQ-061, deferred), well-formed decomposition (REQ-258), build-area profiles
resolvable (REQ-252).

---

## The one-line redesign thesis

**Propagate the release gate's proven pattern (fail-closed floor + grounded judgment +
structured findings) down to every level that lacks it; fill the empty registry with
strict, enforced, per-(area×technology×tier) contracts that carry checkable
done-conditions and match what the agent actually does; verify every handoff instead of
trusting it; and make the whole thing durably observable.**

The genuinely-new requirements after dedup: **REQ-277, 278, 280, 281, 283** + the
**279 / 274** slivers. Everything else refines or amends confirmed TOP-005 requirements.
