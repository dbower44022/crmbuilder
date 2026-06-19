# Reviewer Persona — Approval Capability (ui facet)

**Status:** design, 2026-06-18. Specifies the **UI-surface** design of the
reviewer persona's capability to approve candidate requirements from the
Requirements Review panel (REQ-251): the two affordances the reviewer reaches
for — the **right-click Approve action** and the **upper-right Approve button** —
the selection model behind them, the reviewer-identity modal, and how each
requirement's outcome is surfaced back in the panel. This is the **ui** facet of
design workstream WSK-154 (PI-231), the sibling of the product, process, access,
and storage facets below. Read those and
`requirements-provenance-and-review-anchor.md` first — they establish *who* the
reviewer is, *why* approval must be a governed event, the *process contract* the
panel must honor, and the *access operation* the panel calls. This document does
not restate the persona, the "why", or the gate chain; it pins the **surface**
that lets the reviewer complete the review *in the panel* — and only the surface.

The sibling facets carry the rest of the same capability and are referenced, not
duplicated, here:

- **methodology-product** (`reviewer-persona-approval-capability.md`, WTK-170 of
  the prior round) — the persona and the product-level capability.
- **methodology-process** (`approve-requirement-process-contract.md`, WTK-172 /
  WTK-184) — the `approve_requirement` actor/affordance/effect/postcondition
  contract this surface must honor.
- **access** (`reviewer-persona-approval-capability-access.md`, WTK-182) — the
  `approve_requirements` operation and the `approve` permission the affordances
  invoke.
- **storage** (`pi-231-review-state-post-approval-semantics-wtk183.md`,
  WTK-183) — `requirement.review_state` returns to `current` on approval
  (REQ-249), surfaced in the panel as the cleared NEEDS REVIEW flag.

A *UI surface*, for this capability, is the pair of **affordances** that invoke
the access operation over a **selection**, plus the **rendering** of the
per-requirement outcomes the operation returns. This facet specifies that
surface and nothing below it: the panel is a thin front door onto
`approve_requirements`; it adds no second route to confirmation.

---

## Where the capability lives in the UI

The capability lives on the **Requirements Review panel** (`ReviewPanel`,
`crmbuilder_v2/ui/panels/review.py`, Governance sidebar), on its **Approval
tab** — the queue that already lists the candidate requirements awaiting
activation and, per row, *what each still needs* (`has_provenance`, `has_topic`).
That tab is the natural home because it already answers the question the reviewer
asks immediately before approving — *"what does each of these still need?"* — so
the decision to approve and the act of approving sit in one surface.

The Approval tab is built by `_build_approval_tab`. Its surface is a header row
(an explanatory label on the left, the Approve button upper-right) above the
`_approval_tree` — a `QTreeWidget` with columns *Identifier · Name · Origin · Has
provenance · Has topic*, populated by `_fill_approval` from the
`review_approval_queue` read.

---

## The two affordances (one handler, one contract)

The capability is offered **two equivalent ways** so it meets the reviewer
wherever their hands already are. Both affordances invoke the **same** handler
(`_on_approve_selected`) over the **same** selection — there is exactly one
approval path through the panel:

- **The upper-right Approve button.** `_approve_button` is a `QPushButton`
  labelled *"Approve selected…"* (`objectName="approve_selected_button"`),
  pinned to the right of the Approval tab's header row via an `addStretch`-fronted
  `QHBoxLayout`, with its `clicked` wired to `_on_approve_selected`. The
  upper-right placement is REQ-251's named location; the stable `objectName` lets
  the verification test find it (`findChild(QPushButton, "approve_selected_button")`)
  without depending on label text.

- **The right-click Approve action.** The `_approval_tree` runs with
  `CustomContextMenu` policy; `customContextMenuRequested` is wired to
  `_on_approval_context_menu`, which builds the menu via
  `_build_approval_context_menu` and exec's it at the click position. The menu is
  **built and returned** (not exec'd) by `_build_approval_context_menu` so the
  action wiring is unit-testable in isolation, mirroring the other governance
  panels' `_build_context_menu` convention. It carries a single action,
  *"Approve selected…"*, whose `triggered` connects to the same
  `_on_approve_selected`. **With nothing selected the menu is not built**
  (`_build_approval_context_menu` returns `None`) so a right-click on empty space
  is a clean no-op.

That both affordances funnel into one handler over one selection is the
load-bearing UI property: there is no way for the button and the menu to drift
into two different approval behaviours.

---

## The selection model

The `_approval_tree` is configured for `ExtendedSelection` so the reviewer can
pick **one or many** candidates (Ctrl/Shift-click, Select-All) and approve them
in a single action — the product capability's "one action, many requirements".

`_selected_approval_ids` reads the selection into an **order-preserving,
de-duplicated** list of identifiers, taken from **column 0** (the Identifier
column) of each selected row. Order-preservation matters because the access
operation returns one result *per input identifier, order-preserving*; reading
from a fixed column keeps the identifier extraction independent of any column
reordering.

---

## The reviewer-identity modal (`_ApproveDialog`)

Before any approval is submitted, `_on_approve_selected` opens the modal
`_ApproveDialog` over the selected identifiers. The modal captures the two things
the panel must supply that the queue does not already know:

- **Reviewer** (`QLineEdit`, required) — *who, on the record, is approving*. The
  access facet validates a non-empty reviewer server-side; the modal validates it
  **on accept** and nudges inline (it rewrites the window title to "A reviewer is
  required") rather than round-tripping a 422.
- **Note** (`QPlainTextEdit`, optional) — a rationale folded into each governed
  decision's context.

The modal states plainly what approving does — that it records a governed
approving decision per requirement and confirms those that pass the readability,
provenance, and topic gates, while any that fail stay candidates with their
reason shown — so the reviewer sees the contract before committing. Its title
counts the selection ("Approve N requirement(s)"). Per the house rule below, the
Approve button is **never disabled**; the modal validates on accept.

On accept, `_on_approve_selected` reads `(reviewer, note)` from `values()` and
calls `_submit_approvals(ids, reviewer, note)`.

---

## Submitting and surfacing the per-requirement outcome

`_submit_approvals` stamps the current date as `decision_date` and calls the
access operation through the storage client off the shared worker thread:

```python
self._client.approve_requirements(
    ids, reviewer=reviewer, decision_date=decision_date, note=note
)
```

It returns the access facet's **order-preserving per-requirement result list**,
each row carrying an `outcome` of `confirmed`, `already_confirmed`, or `failed`
(with a `reason`). The panel renders that list — it does **not** re-derive
confirmation; the access operation is the single source of truth:

- **A truthful status summary.** `_on_done` partitions the results and writes a
  one-line summary to the status label — e.g. *"Approvals: 2 approved, 1 already
  confirmed, 1 failed."* The counts come straight from the result outcomes, so a
  mixed batch reports each part honestly.
- **Failures teach, in a copyable box.** When any requirement failed, the panel
  raises a `CopyableMessageBox.warning` listing each failed identifier with the
  **gate's own reason string** ("what to fix"), under a heading that says those
  requirements *remain candidates*. Failures are surfaced, never silently
  dropped.
- **The queue settles by re-fetch.** `_on_done` triggers `refresh`, which
  re-reads the approval queue: confirmed (and already-confirmed) rows leave the
  queue, failed rows remain. Because the refresh is asynchronous and would
  otherwise overwrite the summary with the default *"N topics"* status, the
  summary is parked in `_pending_status` and the next overview refresh lands on
  it — so the reviewer's result survives the reload.

The panel never edits a requirement's status field and never confirms a
requirement by any path other than the governed `approve_requirements` operation.

---

## The reopen / re-approval interaction (REQ-249, surfaced in the panel)

The storage facet returns `review_state` to `current` on approval and clears a
reopened-for-change NEEDS REVIEW flag (REQ-249). The panel **surfaces** that
lifecycle, it does not own it:

- A requirement flagged `needs_review` shows a **NEEDS REVIEW** badge/flag in the
  requirement tree (`_flags_text`, `_render_req_detail`) and appears in the Drift
  tab.
- After a governed change-decision reopens a confirmed requirement (back to
  `candidate` / `needs_review`), it reappears in the Approval queue. A second
  approval through the same panel affordance reconfirms it and the NEEDS REVIEW
  flag **clears** on the next refresh — no lingering flag. This end-to-end
  lifecycle through the panel is pinned by
  `test_post_reopen_approval_returns_review_state_to_current`.

The panel requires no special re-approval affordance: a reopened requirement is
just a candidate in the queue again, approved by the same one action.

---

## House rules this surface must honor

These are codebase-wide UI conventions the affordances follow; they are
constraints on *how* the surface is built, not part of the capability contract:

- **Buttons are never disabled.** The Approve button and the modal's Approve
  button stay enabled; validation (empty selection, empty reviewer) is handled by
  showing an explanatory message — a status-label nudge for an empty selection,
  an inline title nudge for a missing reviewer — never by graying out the
  control.
- **Copyable message surfaces, not raw `QMessageBox`.** The failure box uses the
  shared `CopyableMessageBox` (WTK-143…146) so the reviewer can copy a gate
  reason. New code in `crmbuilder_v2/ui` must not introduce a raw `QMessageBox`
  here (the PI-124 guard greps `ui/`).
- **Transient sub-dialogs are `deleteLater`-d.** `_ApproveDialog` (like the
  panel's other modals) is appended to `self._dialogs` and `deleteLater`-d in a
  `finally` after `exec`, to avoid the worker-thread GC crash
  (`project_qt_worker_widget_gc_hazard`).
- **Fetches run off the worker thread.** `approve_requirements` is called via the
  panel's `_run` helper (the shared `run_in_thread`), with the worker tracked in
  `_in_flight_workers` so teardown drains it; the UI thread is never blocked on
  the round-trip.

---

## Surface boundaries (what this facet is not)

- **The access operation** (`approve_requirements`, its savepoint isolation, the
  `approve` permission gate) is the **access** facet (WTK-182). This surface
  *calls* it; it does not define authorization or per-requirement atomicity.
- **The gates themselves** (readability, provenance, topic) are the anchor's
  enforcement in `activate_by_decision`. The panel surfaces their *reasons*; it
  does not define, evaluate, or relax them.
- **The `review_state` transition** to `current` is the **storage** facet
  (WTK-183 / REQ-249). The panel *renders* the resulting NEEDS REVIEW flag state;
  it does not own the transition.
- **The process contract** (the actor/affordance/effect/postcondition a verifier
  holds the behaviour against) is the **methodology-process** facet (WTK-172 /
  WTK-184).
- **Decline and change** are the other two reviewer decision outcomes from the
  anchor. This surface offers **approve** only; declining or sending a
  requirement back for change is a separate action, not part of these
  affordances.
- **Authoring or editing a requirement statement** is not on this surface. The
  reviewer approves what is presented; an unreadable statement is refused by the
  readability gate and surfaced as a `failed` outcome — the recourse is to send
  it back, not to rewrite it in the approve action.

---

## Acceptance shape (ui level)

The ui facet is satisfied when, on the Requirements Review panel's Approval tab:

1. The approval queue supports **`ExtendedSelection`** so the reviewer can select
   one **or more** candidates, and `_selected_approval_ids` yields an
   **order-preserving, de-duplicated** identifier list from column 0.
2. **Both affordances are present and equivalent** — the upper-right
   *"Approve selected…"* button (stable `objectName="approve_selected_button"`)
   and the right-click *"Approve selected…"* context-menu action — and **both
   invoke the same `_on_approve_selected` handler** over the same selection.
3. A **right-click with no selection builds no menu** (a clean no-op).
4. Invoking Approve opens a modal that captures the **reviewer** (required,
   validated inline) and an **optional note**, then calls the access operation
   `approve_requirements` with those values and the current `decision_date`.
5. The panel renders the operation's **per-requirement outcomes**: a truthful
   status summary (counts of confirmed / already-confirmed / failed) and a
   **copyable failure box** listing each failed identifier with its **gate
   reason**, stating those requirements remain candidates.
6. After approval the queue **re-fetches** (confirmed rows leave, failed rows
   stay) and the result summary **survives the async refresh** via
   `_pending_status`.
7. A requirement that was reopened-for-change reappears in the queue, is
   reconfirmed by the same one action, and its **NEEDS REVIEW flag clears** on
   refresh (REQ-249, surfaced).
8. No path on this surface confirms a requirement by editing its status field —
   confirmation is only ever via the governed `approve_requirements` operation.

These map directly to REQ-251's acceptance summary. The implemented behaviour is
`crmbuilder_v2/ui/panels/review.py` (`ReviewPanel._build_approval_tab`,
`_selected_approval_ids`, `_build_approval_context_menu`,
`_on_approval_context_menu`, `_on_approve_selected`, `_submit_approvals`, and the
`_ApproveDialog` modal), and is pinned end-to-end by
`tests/crmbuilder_v2/ui/test_review_approve_panel.py`.

---

## Provenance

- **Requirement:** REQ-251 — *"Reviewers can approve requirements from the
  Requirements Review panel."* (human_defined, confirmed.)
- **Postcondition requirement:** REQ-249 — review_state returns to `current` on
  approval, surfaced in the panel as the cleared NEEDS REVIEW flag (storage
  facet).
- **Planning item / workstream:** PI-231, Design workstream WSK-154.
- **Work task:** WTK-185 (ui).
- **Sibling facets (WSK-154):** WTK-182 (access, the operation + permission),
  WTK-183 (storage, review_state → `current`), WTK-184 (methodology-process, the
  process contract). Prior-round product facet:
  `reviewer-persona-approval-capability.md`; prior-round implementation:
  WTK-176 (the affordances this facet pins).
- **Implementation anchored:** `crmbuilder_v2/ui/panels/review.py`
  (`ReviewPanel`, `_ApproveDialog`); tests
  `tests/crmbuilder_v2/ui/test_review_approve_panel.py`.
- **Anchor:** `requirements-provenance-and-review-anchor.md` — the principle, the
  gates, and the "readability is only worth enforcing if the human approves where
  the readable content is" rule this surface serves.
