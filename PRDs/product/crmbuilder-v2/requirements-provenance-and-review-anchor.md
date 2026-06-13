# Requirements Provenance and Review — Process Anchor

**Status:** founding draft, 2026-06-13. This is the governing document for how
requirements are captured, organized, and verified. Nothing else in the
requirements process proceeds until the enforcement described here is live.

This document is written to be read by a human project manager. If any part of
it is hard to read, that is a defect in this document, because readability is
the point.

---

## The problem

A capability was built — engagement-scoped agent rules — with no requirement
behind it. It entered the system as a decision plus a build ticket and skipped
the requirement step entirely. The project manager had no way to find it, read
it, or confirm it matched intent.

Worse: when an AI claimed "the UI is read-only per a requirement," the PM could
not open that requirement, trace it back to the conversation that started it,
and check for misinterpretation or drift. The trace did not exist.

The capture machinery is not the weak point. The missing piece is a human
review loop — a way for the person who defines what gets built to find, read,
and validate what the system actually recorded.

---

## The principle

The human project manager defines what is to be built.

Everything that exists must trace to one of two origins:

- something the human defined, or
- an AI interpretation the human approved.

The conversation and the decision are the source of truth. Requirements,
specifications, plans, and code are projections of that truth. They must
reconcile back to it, and can be re-checked against it at any time.

---

## The model

**Hierarchy.** Requirements form a tree. The top is one broad statement a human
can read. Each level adds detail. The lowest leaves may be too technical for a
human to review — and that is fine, because a human validates a leaf by *where
it hangs*, not by reading it. You navigate up, never forced to read down.

**Provenance.** Every requirement links to the conversation, session, and
decision where it was defined — or inherits that link through its parent. No
requirement is an orphan. Every requirement, however deep, is transitively
rooted in a real conversation.

**Origin.** Every requirement records how it came to be: human-defined, or
AI-derived-and-human-approved. Approval is a recorded event — a person, a time,
and the exact text approved.

**Topics organize conversations and features.** A topic is the home for every
conversation about one area of functionality, and the organizing map of the
system's features — its table of contents. Topics are themselves hierarchical:
high-level topics hold high-level features, lower-level topics hold lower-level
features.

One conversation addresses exactly one topic. A session that spans topics is
split into one conversation per topic. A topic therefore aggregates everything
about one capability — its conversations, decisions, requirements, and plans —
in one place.

**A requirement lives in two structures at once.** It has a parent *requirement*
— the decomposition tree, which carries provenance — and it links to a *topic*
at its level — the organizational tree, which carries navigation. A high-level
feature links to a high-level topic. As it decomposes, lower-level features link
to lower-level topics where those exist, while remaining children of their
parent feature. The topic tree is how you *find* things; the requirement tree is
how they were *derived and rooted*.

**The spine.** Six stages, traceable in both directions:

`defined → decided → specified → planned → developed → verified`

- **defined** — the conversation, by or approved by the human.
- **decided** — the decision.
- **specified** — the requirement.
- **planned** — the planning item.
- **developed** — the code / commit.
- **verified** — a test or check that proves the build satisfies the requirement.

---

## The enforcement

These are rules the system refuses to break. They are not conventions someone
has to remember.

**No orphan requirement.** Every requirement must be rooted in a human
conversation — directly, or through its ancestors.

- A **top-level** requirement has no parent, so it must carry its own provenance
  (conversation, session, decision). This is required, not precluded — the top
  requirement is the one that most needs a direct human root.
- A **child** requirement inherits provenance through its parent, so it needs
  none of its own.
- The only forbidden state is a requirement with **no parent and no provenance**
  — one rooted to nothing.

**No orphan capability.** This runs the other direction, and it is the rule the
agent-rules failure broke. Nothing gets built — no planning item, no commit —
without a requirement above it. And nothing the human stated in a conversation
silently dies: it becomes a requirement, or it is explicitly declined, on the
record.

**Saved vs. active.** A requirement can be *saved* with a conversation and
session alone — a human stated it. It becomes *active*, a commitment to deliver,
only when a decision resolves it. Until then it is a proposal on the record, not
work to be built.

**A decision resolves a requirement, three ways:**

- **Deliver** — the requirement becomes active and proceeds down the spine.
- **Decline** — the requirement will not be delivered. It is recorded as
  declined by that decision — not deleted, not silently dropped. This is how
  "nothing the human said silently dies" is honored: a feature decided against
  is a recorded outcome, not a gap.
- **Change** — the requirement must change. The current version is superseded;
  the revised requirement re-enters approval.

**Approval is judgment, not a rubber stamp.** For an AI-derived requirement, the
resolving decision shows the human the source conversation beside the derived
requirement, so the human approves against the actual intent.

**Living drift.** When a requirement, decision, or piece of code changes, its
descendants and its downstream stages are flagged for re-review, and an
AI-derived child re-opens for approval. The tree is kept true over time, not
just at birth.

**One topic per conversation.** A conversation cannot bind a second topic.

**Reviewed, not reviewable.** Validation is a recorded event: the PM reviewed a
topic's requirement set on a date and attested it matches intent. The system
tracks what has been validated and what has not.

---

## Where this lives

Enforcement lives in the **API / access layer**, so no client can bypass it. The
desktop app, an AI agent, and a direct API call are all held to the same rules.

The human review surface is delivered **two ways**:

- an **interactive panel** in the desktop app — navigate the tree, open a
  requirement, trace it to its conversation; and
- a **generated read-back document** — the same content as a plain, readable
  page a human can review top to bottom, away from the app.

---

## Readability is load-bearing

If what is presented is too hard to read, the human approves it anyway. A rubber
stamp is worse than no gate — it manufactures false confidence and negates the
entire process. The approval gate is only as strong as the clarity of what it
presents.

So readability is enforced, not hoped for:

- A requirement statement is one declarative idea with an acceptance criterion.
- A linter rejects multi-idea, jargon-heavy, or unreadable statements *before*
  any human is asked to approve them.
- Build history and superseded approaches never appear in a requirement
  statement. History lives in a separate place, always.

The failure case to never repeat: an agent-system description that packed live
capability and the shelved batch orchestrator into one 90-word paragraph. No
human scans that and validates it.

---

## Keeping focus

This is the one gating item. Nothing else in the requirements process proceeds
until the enforcement above is live.

We prove it by running it on itself. The founding requirement — *"requirements
must be captured, organized, and verified this way"* — becomes the first record
created under the new process: a top-level, human-defined requirement, rooted in
the conversation that produced this document. If the process cannot cleanly hold
its own founding requirement, it is not done.

---

## Not yet decided

These are open design questions, called out honestly so they are not lost:

- **Cross-cutting requirements.** How a concern like "all UI green" attaches
  without being duplicated across every topic it touches. *Deferred.*
- **Decomposition depth.** How depth is governed so the tree does not become a
  new "sea." Working rule for now: a human approves the *shape* — the immediate
  children of a node — at each level, and decomposition stops when a leaf is
  testable. *Still open.*
