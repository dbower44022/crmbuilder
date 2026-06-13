# Claude Code Prompt — Requirements-Provenance Phase 6b: the Review Qt Panel

## What this is

The requirements-provenance rebuild (anchor:
`PRDs/product/crmbuilder-v2/requirements-provenance-and-review-anchor.md`; build
plan: `requirements-provenance-build-translation.md`) is built through Phase 6a —
the review-surface **data layer** — plus the sign-off record. The only thing
left in Phase 6 is the **Qt desktop panel** that renders all of it. This prompt
is that task. It was split out because a Qt panel can't be auto-verified in a
headless agent run — it needs the desktop app launched and looked at, which you
(in a session where Doug can run the app) can do.

**Read first:**
1. The anchor, especially **§"How a review works"** — the panel is a direct
   rendering of that process (topic-first → read tree top-down → trace to the
   defining conversation → read the spine → sign off; plus three queues).
2. `crmbuilder-v2/src/crmbuilder_v2/ui/panels/workstreams.py` — the canonical
   **read-only** monitoring panel. Mirror its structure (master/detail, a
   refresh worker, `read_only_line`/`read_only_text` helpers, no create/edit/
   delete affordances except the one sign-off action below).
3. `crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py` — the `build_panel()`
   factory and the sidebar-group registration. Adding a panel is: one sidebar
   entry, one import, the factory mapping, and the panel class file.

## Branch + working rules

- Work on branch **`requirements-provenance-process`** (the rest of this feature
  lives there; PR #4). **Before every commit, run `git branch --show-current`
  and re-assert the branch if needed** — a background ADO runtime has a history
  of hijacking this shared working tree to `main` (it is currently paused; see
  the `feedback_ado_paused` memory — do not relaunch it).
- v2 UI Qt hazard: transient modal sub-dialogs opened from a panel need
  `deleteLater()` to avoid worker-thread GC crashes (see the
  `project_qt_worker_widget_gc_hazard` memory).
- The desktop UI is a **conforming API client** — it reads and (for sign-off)
  writes through the REST API at `127.0.0.1:8765`, same as any client. No direct
  DB access from the panel.

## The API the panel consumes (all built, all on this branch)

- `GET /topics` — the topic tree (the navigable map / table of contents). Each
  topic has `identifier` (e.g. `TOP-013`), `name`, `parent_topic_identifier`.
- `GET /review/topics/{topic_identifier}` → `{topic, requirements: [node...]}`.
  Each node: `identifier`, `name`, `status`, `review_state`
  (`current`/`needs_review`), `origin` (`human_defined`/`ai_derived`/null),
  `priority`, `acceptance_summary`, `defined_in_conversations: [CNV-…]`,
  `planned` (bool), `verified` (bool), `children: [node...]`. Descent already
  stops where a descendant re-links to a sub-topic.
- `GET /review/topics/{topic_identifier}/document` → `{topic, document}` — a
  plain-language markdown read-back of the tree.
- `GET /review/approval-queue` → candidates awaiting activation, each with
  `identifier`, `name`, `origin`, `has_provenance`, `has_topic` (what it still
  needs before it can be approved).
- `GET /review/drift-queue` → requirements flagged `needs_review`.
- `GET /coverage/capabilities` → `{orphan_planning_items, unbuilt_requirements,
  conversations_without_requirement, summary}` (the coverage-gaps queue).
- `POST /review/signoffs` `{signoff_topic_identifier, signoff_reviewer,
  signoff_attestation}` → records an attestation (server snapshots the topic's
  current requirement set). `GET /review/signoffs?topic=TOP-NNN` lists them.
- Tracing provenance: a node's `defined_in_conversations` are `CNV-NNN`/`SES-NNN`
  ids; fetch a conversation via `GET /conversations/{id}` to show/jump to the
  defining conversation. (All requests send the `X-Engagement` header like the
  other panels.)

## What to build — a "Requirements Review" panel

Register it under the **Governance** sidebar group (a read-only review/monitoring
surface). Layout, top to bottom / left to right:

1. **Topic picker** — a combo or tree populated from `GET /topics`. Selecting a
   topic drives everything below.
2. **Requirement tree** (`QTreeWidget`) from `GET /review/topics/{id}` — top-down,
   one row per requirement: `identifier` · `name` · a `[status]` chip · a
   **NEEDS REVIEW** badge when `review_state == needs_review` · small flags for
   `unbuilt` (confirmed but not `planned`) and `unverified` (confirmed but not
   `verified`). Broad top-level rows are the human-readable layer; the human
   validates a leaf by where it hangs, so make the hierarchy the visual spine.
3. **Detail pane** for the selected requirement — `acceptance_summary`, `origin`,
   `priority`, and its **provenance**: the `defined_in_conversations`, each a
   button/link that fetches the conversation and shows it (the "trace to the
   conversation that defined it" step). Show the six-stage spine state
   (defined→decided→specified→planned→developed→verified) from the flags you have
   (`planned`, `verified`) — mark the rest as present/unknown for now.
4. **Read-back document tab** — render `GET …/document` (plain text/markdown) so
   the PM can read the whole topic top to bottom in one place.
5. **Sign-off** — a button that opens a small modal (reviewer + attestation),
   POSTs to `/review/signoffs`, and a list of prior sign-offs for the topic from
   `GET /review/signoffs?topic=`. This is the one *write* the panel does; it is a
   conforming API write, fully allowed.
6. **Queues** — three tabs or a side list: **Approval** (`/review/approval-queue`,
   showing has_provenance / has_topic so the PM sees what blocks each),
   **Drift** (`/review/drift-queue`), **Coverage gaps** (`/coverage/capabilities`).

Keep it read-only except the sign-off action — record creation is otherwise the
API/MCP's job; this panel is for review.

## Done when

- The panel is registered and opens from the Governance sidebar group.
- With the API running on a populated engagement, you can: pick a topic, see its
  requirement tree, open a requirement and reach its defining conversation, read
  the read-back document, see the three queues, and record a sign-off that then
  appears in the topic's sign-off list.
- `uv run ruff check` clean on the new/changed files; the app launches
  (`uv run crmbuilder-v2-ui`) and the panel renders without Qt GC crashes.
- Commit on `requirements-provenance-process` (re-assert the branch first); push
  to update PR #4.

## After this

Only **Phase 7 (prove-on-itself)** remains: capture this whole effort's founding
requirement ("requirements must be captured, organized, and verified this way")
under the new process — a top-level human-defined requirement rooted in the
conversation that produced the anchor — as the first real exercise of the engine.
