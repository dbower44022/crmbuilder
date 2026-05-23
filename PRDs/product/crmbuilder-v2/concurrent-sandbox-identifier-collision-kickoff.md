# Concurrent Sandbox Identifier Allocation — Kickoff for CLC Refinement Discussion

**Document type:** Kickoff prompt (single-session scoping conversation)
**Repository:** `crmbuilder`
**Path:** `PRDs/product/crmbuilder-v2/concurrent-sandbox-identifier-collision-kickoff.md`
**Last Updated:** 05-23-26 04:15
**Operating mode:** ARCHITECTURE
**Estimated duration:** Short — one session, scoping only
**Engagement:** CRMBUILDER

---

## 1. Topic

When the next-available-identifier check runs against the engagement's `db-export/` snapshot, it sees the snapshot's state at allocation time. If two Claude.ai sandboxes are running concurrently and both look at the snapshot before either has pushed, both allocate the same next identifier. The collision is only detected at push time, when `git pull --rebase` brings down the other sandbox's commit.

The check is necessary but not sufficient when more than one sandbox is producing governance records against the same engagement.

## 2. Concrete instance from 2026-05-23

The audit-v1.2 planning resolution conversation (final identifier: SES-060) and the PI-024 prior-workstreams backfill conversation (final identifier: SES-059) both observed the CRMBUILDER engagement's snapshot with SES-057 as head and SES-058's payload pending apply. Both allocated SES-059 independently.

PI-024 pushed its close-out commit first (commit `44182d1` at 15:32 UTC), taking SES-059 with DEC-175..177. The audit-v1.2 conversation's pull-rebase brought `44182d1` down and silently overwrote its own in-flight `ses_059.json` with PI-024's version. The audit-v1.2 content was reconstructed verbatim from chat history at `ses_060.json` with identifier shifts only (DEC-175..179 → DEC-178..182), and the planning doc was bumped to v1.3 to fix one stale §10 reference (`SES-059 (DEC-175 through DEC-179)` → `SES-060 (DEC-178 through DEC-182)`).

The recovery was clean specifically because the displaced content was still intact in chat history. Another concurrent-allocation case might find the displaced content harder to recover (longer conversation, more files, summarized chat context).

## 3. Why this might belong in the CLC workstream

The Code Change Lifecycle workstream (SES-057, PI-027..PI-033) is being built to make `planning_item`-to-commit-SHA traceability queryable via a single SQL join. It introduces a first-class commit entity and tracks `deposit_event` apply records. The concurrent-allocation issue is structurally about coordinating identifier claims across sandboxes that haven't yet committed to git — adjacent in concept to the commit-and-deposit-event tracking CLC already covers.

Three reads worth weighing:

- **(a) In scope, no new PI needed.** One of PI-027..PI-033 already covers this; the existing CLC scope absorbs it. Requires reading the SES-057 close-out to confirm none of the existing PIs already names allocation coordination.
- **(b) In scope, new PI.** A refinement within CLC's existing identity but not covered by the existing PI set. Author as the next-available PI (currently PI-045 after PI-044 from SES-058's audit-v1.2 series; verify against the engagement snapshot at session start).
- **(c) Adjacent but separate.** Close enough to CLC to be confused with it but structurally a different workstream (apply-time coordination versus retrospective traceability). Would warrant its own micro-workstream or be deferred.

## 4. Possible directions to consider

If the conversation lands on read (b) — in-scope, new PI — two directions are worth weighing:

**Direction 1 — Detection-only refinement.** Sandboxes register their allocation in a lightweight register on a known git-tracked path (one short file per in-flight claim under `PRDs/product/crmbuilder-v2/in-flight-identifiers/` or similar). On push success the claim file is removed in the same commit. The pre-allocation step reads the snapshot AND scans the claim directory, taking the max of both. Pull-rebase remains the safety net for any race between two sandboxes that both write claim files before either pushes. Cheap; no API, DB, or cross-sandbox latency-sensitive coordination.

**Direction 2 — Allocation-time registry check.** Apply prompts (or earlier — the close-out authoring step) query a "claimed but not yet applied" registry that's authoritative across sandboxes. The registry has to be durable cross-sandbox and queryable at allocation time. Probably requires API extension and is structurally more aligned with CLC's first-class commit-and-deposit-event design.

Direction 1 is the minimum viable improvement. Direction 2 is structurally more CLC-native but a larger commitment. The session should weigh whether the failure mode (silent overwrite on pull-rebase, recoverable only from chat history) is rare enough that Direction 1 is sufficient.

## 5. What the session should produce

Three things, in order:

1. **A read on §3** (in-scope-no-new-PI, in-scope-new-PI, or adjacent-but-separate) with a one-paragraph rationale.
2. **If in-scope-new-PI:** a `planning_item` draft with concrete title, description, acceptance criteria, and parent workstream WS reference. The draft is the session's primary deliverable.
3. **If adjacent-but-separate:** a brief recommendation for where the work should live (its own workstream? a deferred planning item under a yet-to-be-established workstream?) and what evidence would justify spinning it up.

If the session lands on §5.2 (new PI), the close-out payload contains the PI and a `decided_in` reference. If it lands on §5.1 or §5.3, the close-out captures the decision but adds no new PI.

## 6. Read-this-first orientation

- `PRDs/product/crmbuilder-v2/code-change-lifecycle-workstream-establishing-kickoff.md` — the SES-057 workstream-establishment kickoff (defines the CLC workstream's identity and scope)
- `PRDs/product/crmbuilder-v2/close-out-payloads/ses_057.json` — for the actual PI-027..PI-033 scope and the existing decisions
- `PRDs/product/crmbuilder-v2/close-out-payloads/ses_059.json` — Doug's PI-024 backfill close-out (one side of the collision)
- `PRDs/product/crmbuilder-v2/close-out-payloads/ses_060.json` — the audit-v1.2 resolution close-out (the other side; `topics_covered` §8 and §11 narrate the collision and the rebase; `conversation_reference` has the timeline)
- `git log --oneline 789a7dc..ce4d00b` — the git evidence of the collision-and-rebase sequence (`44182d1` was Doug's PI-024 SES-059 commit; `ce4d00b` is the audit-v1.2 SES-060 rebased commit landed on top)

## 7. Scope guard — what this session is NOT

This session does NOT:

- Implement any of the directions in §4. The session produces a planning-item draft at most, not code.
- Re-litigate the SES-057 CLC workstream's existing scope. PI-027..PI-033 stand as authored.
- Decide whether the audit-v1.2 series should pause at Prompt E for a deploy-side validation milestone (§8.5 of `audit-v1.2-planning.md`) — that's a workflow choice for Doug at audit-v1.2 execution time, unrelated to this topic.
- Backfill the PI-024 / audit-v1.2 collision into the governance record as a historical event. The collision narrative already lives in SES-060's `topics_covered` and `conversation_reference`; that's sufficient for retrospective reference.

End of kickoff.
