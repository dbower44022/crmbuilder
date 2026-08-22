# Triage-All-Open-Releases — new-session handoff prompt (TRIAGE ONLY)

**Purpose:** triage every open V2 release and surface a single consolidated list
of **only what needs Doug** (requirement approvals + decisions), plus the set of
releases that are **ready to build** once approved. **Build nothing, ship
nothing, freeze nothing.** The actual building is a separate batch Doug kicks off
after he's approved the requirements this triage surfaces. Authored 2026-06-28
(SES-246 lineage). Engagement `ENG-001` (`X-Engagement: CRMBUILDER`), API
`127.0.0.1:8765`.

---

## 0. The one hard rule

You **cannot** approve requirements or build anything — both are gated on Doug.
This pass is **read + draft-candidate-requirements + report**, nothing else. In
particular: do **not** freeze a release, do **not** transition any release toward
the lane, do **not** decompose/claim/resolve any PI, do **not** cancel anything.
The only writes you make are **drafting candidate requirements** (the items Doug
will approve) and recording your session/decisions. Drafting a candidate is
surfacing work for approval — it does not build or confirm anything.

Don't touch actively-parallel-worked projects' records beyond reading (check the
live "hot edge" — most-recently-updated PIs — at start).

---

## 1. Method: classify every open release, draft what's missing, report

**Enumerate:** `GET /releases?limit=200`, keep `release_status NOT IN
(shipped, cancelled, superseded)`. For each: `GET /releases/{id}/freeze-readiness`
and walk `project_belongs_to_release → planning_item_belongs_to_project` for the
open PIs (`Draft/Ready/In Progress/In Review`); per PI, read its
`planning_item_implements_requirement → requirement` status.

**Classify into buckets and act per the table — actions are report-only except bucket C:**

| Bucket | Test | Triage action |
|---|---|---|
| **A. Ready** | all open PIs have a **confirmed** requirement | **List under "Ready to build"** (no writes). It will be built in the post-approval batch. |
| **B. Requirement-less** | any open PI with **no** requirement | **Draft a candidate requirement** per such PI (the only writes), add to the **Approval list**. |
| **C. Empty** | no open PIs | **List under "Recommend cancel"** (don't cancel — just recommend), unless its project is a deliberate parked/blocked container (PRJ-028 upstream-blocked) → "Leave parked". |
| **D. Blocked-artifact** | freeze-readiness blocked by a **Cancelled/terminal** PI (e.g. REL-013 ← cancelled PI-161 / deferred REQ-120) | **List under "Recommend cleanup"** with the specific fix (remove the terminal PI's `belongs_to_project` edge), and triage the release *behind* it (its real backlog is usually bucket B → draft those requirements). |

## 2. Drafting candidate requirements (bucket B — the only writes)

For each requirement-less open PI:
1. Draft a **candidate** requirement with full provenance — `requirement_belongs_to_topic` (reuse the PI's topic or the nearest fit) + `requirement_defined_in_conversation` (a new `CNV` under your session). Statement must pass the readability gate: **≤75 words, ≤4 sentences, NO embedded `PI-/DEC-/REQ-` identifiers** (push detail to `requirement_notes`); acceptance summary required. Origin `ai_derived`.
2. Add the `planning_item_implements_requirement` edge PI→REQ.
3. Add it to the **Approval list** with a one-line "why".

Do **not** freeze the release afterward — a frozen scope is closed (REQ-226) and
would trap any still-unapproved PI. Freezing happens in the build batch, after
approval.

## 3. Governance
Open one session (`chat`, belongs to a project) at start; record a decision
capturing the triage outcome. Never edit a requirement's status to confirm it —
that's Doug's Review-panel gate.

## 4. End-state: the report (this is the whole deliverable)

A single markdown report with four sections:
1. **Ready to build** — bucket-A releases (already frozen-ready or forming-ready), each with its PIs. These need no input; they go to the build batch.
2. **Requirements to approve** — every candidate you drafted (bucket B/D), grouped by release, each one line. Approving these unblocks their builds.
3. **Recommended cleanups** — empties to cancel (bucket C), blocked-artifacts to clear (bucket D), with the exact action. (Recommend; don't execute.)
4. **Decisions needed** — genuine scope/design forks you couldn't resolve.

Nothing is built, shipped, frozen, or cancelled. Doug reviews the report,
approves requirements + cleanups, and *then* the build batch runs.

---

## Starting state (2026-06-28 handoff)

- **Ready to build (bucket A), already frozen:** REL-007, REL-010, REL-011, REL-014, REL-021, REL-022, REL-031, REL-034 — 15 confirmed-req PIs. *(One of these is being built locally first as a process check — re-derive live; if one is already `shipped`, drop it.)*
- **Requirement-less (bucket B):** REL-016 (PI-062..067, Skills/Patterns/Inventories libraries), REL-017 (PI-020), REL-012 (1 of 3 PIs).
- **Blocked-artifact (bucket D):** REL-013 (cancelled PI-161 / deferred REQ-120; behind it PRJ-023's ~11-PI methodology backlog → bucket B).
- **Empty (bucket C):** re-derive live.
- Phase-E enforcement flag is OFF (flips after this backlog clears, Doug's call).
