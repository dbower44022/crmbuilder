# Candidate-Requirements Triage — 2026-07-20

**Scope:** the 18 `candidate` requirements in the ENG-001 store as of 2026-07-20
(REQ-453, 455–459, 461–462, 466–471, 473–475, 477). All decisions here are
recommendations only — confirmation/rejection is Doug's, recorded as decisions
in the store per the approval gate.

**Context:** every candidate except REQ-455 and REQ-477 traces to the ENG-004
mentor-app dev-lane pilot (2026-07-04..07): ~$300 of largely-uncaptured spend,
five PIs built before any human-verifiable demonstration (now GVR-239), a
scheduler crash on the first multi-engagement launch, and the 2026-07-07
corpus-mutation incident (59 confirmed requirements regressed by an
unattributable automated actor). The candidates are the systematic fixes.

---

## Tier 1 — Unblock first: the deploy procedure (needs Doug input, not build effort)

| Req | Priority | Recommendation |
|---|---|---|
| **REQ-477** Checked-in production deploy procedure | must | **Confirm — but blocked on Doug.** DEC-907: build is blocked until Doug approves AND supplies the actual rsync / alembic / restart / verify steps. The steps "are not recoverable and must not be inferred." Smallest item on the list once the steps exist; also the most consequential gap (production currently has no durable deploy mechanism at all). |

**Doug's action:** approve, and dictate the deploy steps (or walk one deploy
with the session recording it). Nothing can proceed on this item without that.

## Tier 2 — Store integrity (protects the SSoT; do before more autonomous runs)

These close the corpus-mutation incident's attack surface. The store is the
single source of truth (GVR-238); an open regression path on it is the most
dangerous open item after the deploy gap.

| Req | Priority | Recommendation |
|---|---|---|
| **REQ-474** Decision-gated requirement status regression | must | **Confirm.** The confirmation side is already decision-gated; the regression side is open — that asymmetry is exactly what the 04:11Z incident exploited. Small, well-bounded store change. |
| **REQ-475** Per-write actor attribution | must | **Confirm.** Companion to REQ-474: the incident's actor is unattributable beyond the shared engagement token. Sub-actor identity on writes makes the audit trail answer *who*. |
| **REQ-453** Side-band writes reach the concurrency-safe store | should | **Confirm.** Scheduler side-band writes (run events, cost, identity) can still land in a corruptible local file when the DB isn't configured. Fail closed instead. Pairs naturally with REQ-469 (cost events are one of the side-band paths). |

## Tier 3 — Cost control (Doug's 07-05 directives; prerequisite to any further metered pipeline run)

| Req | Priority | Recommendation |
|---|---|---|
| **REQ-469** Complete cost capture across all agent paths | must | **Confirm, first of this tier.** The pilot spent ~$300 that telemetry recorded as $12.81, so the approved $200 ceiling never fired. Budget gates are decorative until capture is complete. |
| **REQ-467** Interactive subscription-billed execution mode | must | **Confirm.** Doug's explicit directive: tune the process interactively on subscription billing; graduate deliberately to metered autonomous runs. This is the mode the next process-tuning rounds should run in. |
| **REQ-470** Model tiering + prompt caching | should | **Confirm, build after 469/467.** 288k tokens all on the top-tier model with zero cache utilization. Pure configuration-and-plumbing savings; verification depends on cost telemetry (REQ-469) existing. |

## Tier 4 — Review gates (mechanize GVR-239 so it isn't advisory-only)

| Req | Priority | Recommendation |
|---|---|---|
| **REQ-466** Demonstrable-increment gate in the pipeline | must | **Confirm.** GVR-239 is currently an enforced *rule* with no mechanical teeth in the scheduler. This is the enforcement: no In Review without an executed journey artifact; no PI N+1 while PI N awaits demonstration. |
| **REQ-473** Acceptance-summary-driven verification gates | must | **Confirm.** FND-909: PI-010 passed 1364 machine tests and failed on first human render. Experiential requirements need rendered-output verification, not code-property gates. Overlaps REQ-466 — recommend designing them together (one gate family). |
| **REQ-468** Early UI prototype gate in the methodology | must | **Confirm.** Cheap prototype review between requirements confirmation and freeze. Methodology change more than code change; feeds the Master CRMBuilder PRD (REL-013) as a defined phase. |

## Tier 5 — Pipeline correctness batch (confirm now, build as one release before the next pipeline run)

All discovered in the same ENG-004 planning/dev runs; individually small-to-medium.

| Req | Priority | Recommendation |
|---|---|---|
| **REQ-456** Engagement-scoped release resolution | must | **Confirm.** Straight crash (MultipleResultsFound) on the first multi-engagement launch. Smallest fix in the batch. |
| **REQ-459** Provider output validated at the agent boundary | must | **Confirm.** Invariant violations should re-prompt/pause, never abort the scheduler loop. |
| **REQ-457** Demand authoring past the output ceiling | must | **Confirm.** Chunk + merge oversized demand sets; detect truncation; no identical-retry loops; record failed-call spend. |
| **REQ-458** Canonical artifact naming in demand authoring | must | **Confirm.** Case-variant/synonym artifact duplicates (Session/session, HomeScreen/HomePanel) silently split concepts. |
| **REQ-462** Design-phase store-side output path | must | **Confirm.** Design-phase code-lane tasks are boxed in (no-MD standard + branch-commit gate + no store path). Prerequisite for honest Design phases. |
| **REQ-471** Correction-release delta planning path | should | **Confirm.** Correction releases currently have no route from delta requirements into existing workstreams; SES-004's bespoke driver is the workaround being institutionalized. |
| **REQ-461** Work-task list API filters + workstream linkage | should | **Confirm.** Small API ergonomics fix; also makes monitoring the Tier 3/4 work observable per-PI. |

## Tier 6 — Larger platform feature (scope separately)

| Req | Priority | Recommendation |
|---|---|---|
| **REQ-455** Module & Platform Documentation Log | should | **Confirm the direction, but scope as its own release** (new entity family + versioning + a centralized UI panel). It underpins the ENG-004 "NO MD" coding standard (CS-9), so it will block that standard's full adoption until built — worth planning, not worth jumping the queue. |

---

## Suggested release shapes (if the tiers are approved)

1. **REQ-477** alone — tiny, human-gated, immediately valuable. Needs Doug's steps.
2. **Store-integrity release:** REQ-474 + 475 + 453.
3. **Cost-control release:** REQ-469 + 467 + 470 — before any further metered pipeline run.
4. **Review-gates release:** REQ-466 + 473 (one gate family), REQ-468 as the methodology piece feeding REL-013.
5. **Pipeline-correctness release:** REQ-456 + 457 + 458 + 459 + 461 + 462 + 471 — before the next ENG-004 pipeline attempt.
6. **REQ-455** planned as its own later release.

Tiers 2 and 3 are both "before more autonomous runs"; if only one goes first,
integrity (Tier 2) protects the store even while nothing is running, so it edges
out cost control.
