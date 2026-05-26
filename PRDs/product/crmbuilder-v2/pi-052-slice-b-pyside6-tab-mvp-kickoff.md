# Kickoff: PI-052 Slice B — PySide6 chat tab MVP, one tool wired, streaming on, in-memory only

> **V2 governance anchor:** WT-055 addresses PI-052 and points at this file via `work_ticket_file_path`. The file is canonical when this body and WT-055's `work_ticket_description` drift (per DEC-262, the hybrid-kickoff pattern).

**Status:** Ready. Second implementation slice of PI-052 per the slicing plan settled in DEC-261 (SES-080). Slice A shipped under SES-087 (commit `b519df0` — `crmbuilder-v2/scripts/chat_spike.py`) and Doug confirmed the loop works end-to-end against the live Anthropic API.

**Session type:** Implementation. Build-execution working mode. Output is the PySide6 chat-tab MVP code under `crmbuilder-v2/src/crmbuilder_v2/ui/chat/` + `panels/chat.py` + a sidebar entry, plus a build-closure conversation that closes WT-055.

**Anticipated session at close:** SES-091 or later (verify with `list_recent_sessions` at conversation open per the parallel-sandbox-collision discipline — heads at session author time were SES-090 / CONV-060 / DEC-300 / WT-054).

---

## Why this slice exists

Slice A validated the foundational architecture in 131 LOC of terminal Python: `anthropic.Anthropic` + native `tools=[...]` + blocking `httpx` against `127.0.0.1:8765` compose into a working chat loop. The next risk is the Qt-bridging architecture itself — `QThread` + a private asyncio event loop + `AsyncAnthropic.messages.stream()` driving incremental UI updates via Qt signals. If that composition has problems (event-loop cross-talk, signal latency, mid-stream cancellation glitches), they show up here, on the simplest possible tab, before all 44 tools and persistence and caching pile on top in Slice C.

Slice B is intentionally a slice, not a half-built v1. **One tool**, **no persistence**, **mode toggle and model picker present but read-only**, no usage display, no sidebar conversation list. The deliverable is a tab Doug can launch, click into, ask "What's the current status?", and watch Claude's response stream into a bubble with an expandable tool-call disclosure.

---

## Read first

### Tier 1 — design-doc anchor (the spec for this slice)

1. `PRDs/product/crmbuilder-v2/pi-052-chat-ui-design.md` — sections most relevant to Slice B:
   - §1 (Architecture overview),
   - §2.1–§2.7 (Component breakdown — `ChatPanel`, `ChatController`, `ChatWorker`, `ui/chat/tools.py` dispatcher, `ChatSession` dataclass, persistence skeleton, transcript widgets),
   - §3 (Data flow — Send → controller → worker → stream → signals → panel),
   - §5 (Auth model — bootstrap flow Doug needs to wire),
   - §7 (Tool execution loop architecture — threading model, stream events, cancellation),
   - §9 (UI layout and visible state — the mockup; v0.6 styling tokens),
   - §10 Slice B paragraph (the acceptance bullets),
   - §12 (Error recovery matrix — Slice B implements only the bootstrap-401 + Ctrl-app-close paths; the rest land in Slice D).

### Tier 2 — Slice A reference

2. `crmbuilder-v2/scripts/chat_spike.py` — Slice A's blocking loop. Useful for: the tool-dispatch shape (`dispatch(name, args, http)`), the `_unwrap` envelope helper, the `get_current_status` tool definition, the `messages.create` (blocking) parameters that map directly to `messages.stream` (async). Slice B's worker rewrites this in async + streaming form but the tool-call contract is identical. *Slice A is throwaway — do not import from it; copy the patterns you want and let Slice B's code stand on its own.*

### Tier 3 — existing PySide6 surface

3. `crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py` — main window construction, sidebar wiring, panel instantiation pattern.
4. `crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py` — `SIDEBAR_GROUPS` table. Slice B adds a **new** group `"AI"` *above* the existing `"Engagements"` group with one entry `"Chat"`. (Position chosen so it's the first thing in the sidebar — chat is the front-and-center surface Doug will reach for most often. Conventional placement; can be re-sorted in Slice D if it feels wrong.)
5. `crmbuilder-v2/src/crmbuilder_v2/ui/panels/status.py` (216 LOC) — the simplest existing panel; use it as the structural template for `panels/chat.py`. *Do not copy its data-fetching pattern (the chat panel is async/streaming; status is synchronous request/refresh).* Use it for: panel-class shape, refresh-service registration, layout token usage, design-token references.
6. `crmbuilder-v2/src/crmbuilder_v2/ui/refresh.py` — only if the chat panel needs to react to cross-tab events. Likely no for Slice B (deferred to Slice D per design §10 *Sidebar staleness indicator integration*).

### Tier 4 — SDK + methodology references

7. The `anthropic` Python SDK's `AsyncAnthropic.messages.stream()`. Returns an async context manager that yields events (`MessageStartEvent`, `ContentBlockStartEvent`, `ContentBlockDeltaEvent`, `ContentBlockStopEvent`, `MessageDeltaEvent`, `MessageStopEvent`). Design doc §7 (Stream events) is authoritative for which to handle in Slice B.
8. The `/claude-api` skill — for Anthropic SDK patterns generally. **NOTE:** prompt caching is normally required by the skill but is explicitly deferred to Slice C in DEC-261 — Slice B intentionally skips it. The Slice C build session will revisit and wire all three caching tiers.
9. `crmbuilder/CLAUDE.md` v2 section — for the v2 governance state and push convention.

---

## Goal

A PySide6 chat tab that meets every bullet in design doc §10 *Slice B*. Concretely:

### New files to author

```
crmbuilder-v2/src/crmbuilder_v2/ui/
  panels/
    chat.py                       # ChatPanel — top-level QWidget for the tab
  chat/
    __init__.py
    controller.py                 # ChatController(QObject) — main-thread bridge
    worker.py                     # ChatWorker(QThread) — async loop owner
    session.py                    # ChatSession dataclass (in-memory only in Slice B)
    tools.py                      # tool dispatcher — one tool in Slice B (the get_current_status definition is hardcoded here, NOT extracted from mcp_server.tools; Slice C does the refactor per design Appendix A)
    widgets.py                    # UserMessageItem, AssistantMessageItem, ToolUseItem, ToolResultItem
    auth.py                       # API-key bootstrap (env → keyring → modal dialog)
```

### Existing files to touch

- `ui/sidebar.py` — add `("AI", ("Chat",))` to `SIDEBAR_GROUPS` (the position decision is in the *Read first* section above).
- `ui/main_window.py` — register the chat panel in the panel dispatch.
- `pyproject.toml` — add `keyring` as a runtime dependency (the auth bootstrap needs it per design §5).

### Behavioral contract

1. **App launches normally.** No `import keyring` at startup that blocks if the keyring backend is unavailable — make all keyring access lazy (only when the chat panel is first activated).
2. **Click "Chat" in the sidebar.** Panel becomes visible. On first activation:
   - Check `os.environ["ANTHROPIC_API_KEY"]`. If set → use it, panel ready.
   - Else check `keyring.get_password("crmbuilder-v2-chat", "default")`. If set → use it, panel ready.
   - Else → render an empty state inside the panel with a "Configure API key" button. Clicking opens a modal dialog with a single text field, paste-from-clipboard button, save-to-keyring checkbox (default on), Save/Cancel. On Save the key is held in memory for the app run and written to the keyring if checked.
3. **Type "What's the current status?" → Send.** The transcript shows:
   - A user bubble with the typed text.
   - An assistant bubble that fills incrementally as text streams in.
   - When Claude calls `get_current_status`, a `ToolUseItem` widget appears showing `🔧 get_current_status({})` collapsed by default; clicking expands.
   - When the tool returns, a `ToolResultItem` widget appears showing a one-line synthesized summary collapsed by default; clicking expands to the full JSON.
   - After the tool round-trip, the assistant bubble continues streaming with the synthesized status summary.
   - On `stop_reason != "tool_use"`, streaming stops and the assistant bubble is final.
4. **Stop button.** Visible only when a turn is in flight; clicking cancels via `worker.stop()` per design §7 *Stop / cancel*. Partial text stays in the transcript; the assistant message closes off cleanly with a `(cancelled)` marker appended.
5. **Close and re-launch the app.** Chat history is empty. **Expected** — Slice C wires persistence.
6. **Mode toggle and model picker** are visible in the header. Both are `QComboBox` widgets populated with the correct options (Mode: Full/Read-only/Ask before write; Model: Opus 4.7/Sonnet 4.6/Haiku 4.5). Both have `setEnabled(False)` for Slice B with a tooltip "Configured in Slice C". *Visible but inert* — this is intentional so the layout is correct now and Slice C just removes two `setEnabled(False)` calls and wires the logic.

### Tool surface

Exactly one tool: `get_current_status`. Hardcoded schema in `chat/tools.py`:

```python
TOOL_DEFINITIONS = [
    {
        "name": "get_current_status",
        "description": "Return the current crmbuilder v2 governance project status singleton.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]
```

The dispatcher's `invoke(name, args)` method calls `httpx.AsyncClient.get("/status")` and returns the unwrapped `data` field. One function in the dispatcher. No partition machinery (read/write split lands in Slice C when there are 44 tools to partition).

### Threading + streaming

Per design doc §2.3 + §7. Vanilla `QThread.run()` containing `asyncio.run(self._loop_main())`. No `qasync` dependency. `AsyncAnthropic` client + `httpx.AsyncClient` live inside the worker thread. All cross-thread communication is via Qt signals (queued connections — Qt handles the marshalling automatically when the receiver lives in a different thread).

Single in-flight turn at a time in Slice B. The controller refuses to call `worker.start_turn()` if the previous turn isn't finished — the input area's Send button is disabled while a turn is in flight (just like the Stop button is only visible during).

### Styling

Reuse the existing v0.6 design tokens (`color.neutral.0`, `color.neutral.100`, `color.neutral.300`, `font.body`, `font.mono`) per design §9 *Transcript*. The layout mockup in §9 is the visual target. Sidebar (240px) is **not** rendered in Slice B — that's Slice C's multi-conversation work. The chat tab in Slice B is just header + transcript + input.

---

## Non-goals

- No persistence. `ChatSession` lives in `ChatController` memory; lost on app close. `chat/session.py` defines the dataclass and `messages_for_api()`, but no `chat/persistence.py` in Slice B.
- No prompt caching. Skipped per DEC-261. Slice C wires all three tiers.
- No more than one tool. `mcp_server.tools` is **not** refactored in Slice B — leave the closure pattern alone. The shared `tool_definitions()` helper from design doc Appendix A is Slice C's deliverable.
- No conversation sidebar. The header has no `+ New` button and no sidebar conversation list. The session is implicit and singular.
- No usage display. The header has no `↑in ↓out (cache N) $X.XX` line. Token accounting starts in Slice C alongside caching.
- No mode-toggle / model-picker functionality. Widgets are inert per the *Behavioral contract*.
- No export, no rename, no delete — those are multi-conversation operations that don't apply when there's one implicit session. Slice D.
- No system prompt design. Slice B uses a one-paragraph placeholder system prompt similar to Slice A's. The substantive design happens in Slice C per design §13.
- No tests in Slice B. The MVP is validated by manual run per the acceptance criteria below. Slice D adds the test suite.
- No new REST endpoints. The chat tab consumes the existing FastAPI surface per design §2.8.

---

## Working pattern

Standard Claude Code build-execution conversation: implement, test manually by launching the app, iterate, commit when working. Final deliverable is one commit on `main` per the commit convention below.

The work breaks naturally into phases — author each in order, test the app between phases:

1. **Skeleton.** Add `keyring` to `pyproject.toml`. Author `chat/session.py` + empty `chat/__init__.py`. Sidebar entry + main_window dispatch + empty `ChatPanel` that renders a label "Chat tab — Slice B MVP" with the model + mode pickers inert in the header. **Test:** launch app, click "Chat", see the empty panel; no errors.
2. **Auth bootstrap.** Author `chat/auth.py` (env → keyring → modal dialog). Wire it into `ChatPanel.first_show()`. **Test:** launch with `ANTHROPIC_API_KEY` set → panel ready; launch without → "Configure API key" empty state.
3. **Worker + controller skeleton.** Author `chat/worker.py` + `chat/controller.py`. Wire input area + Send button; on Send, controller emits `message_added(user, text)` (no API call yet) and worker echoes back a stub `loop_finished("end_turn")`. **Test:** type, click Send, see user bubble appear, see stub assistant bubble.
4. **Live streaming.** Wire `AsyncAnthropic.messages.stream()` in worker; emit `streaming_delta(idx, text)` per text-delta event; panel appends to live assistant bubble. **Test:** type a question with no tool use needed ("hello"), see response stream in word-by-word.
5. **Tool dispatch.** Author `chat/tools.py`; wire tool-use blocks in worker; emit `tool_call_started` / `tool_call_completed`; panel inserts `ToolUseItem` / `ToolResultItem` widgets. **Test:** type "What's the current status?", see the full tool round-trip.
6. **Cancellation.** Wire Stop button per design §7 *Stop / cancel*. **Test:** start a long turn (e.g., ask for a multi-tool sequence), click Stop, see the partial bubble close cleanly with `(cancelled)`.

Each phase is a natural checkpoint. If a phase reveals a design surprise (the SDK behaves unexpectedly, Qt signals don't marshal cleanly across the asyncio boundary, the keyring backend has a quirk on Linux Mint), pause and surface — Slice B's value increases if the conversation pivots to investigation.

---

## Acceptance criteria

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python -m crmbuilder_v2.ui.app
```

(Or however the app is launched today — check `crmbuilder-v2/pyproject.toml` `[project.scripts]` if there's a console-script entry.)

Manual gate checklist:

- [ ] App launches normally with no chat-related errors in stderr (even with no `ANTHROPIC_API_KEY` set).
- [ ] Sidebar shows a new "AI" group with one entry "Chat".
- [ ] Clicking "Chat" with `ANTHROPIC_API_KEY` set → empty transcript + functional input area.
- [ ] Clicking "Chat" without `ANTHROPIC_API_KEY` set and no keyring entry → empty state with "Configure API key" button → modal dialog → entering a valid key → transcript usable.
- [ ] Typing "What's the current status?" + Send → user bubble, then streamed assistant bubble, then `🔧 get_current_status({})` collapsed disclosure, then `↩︎ ...` result disclosure, then streamed synthesized status summary, then turn ends cleanly.
- [ ] Multi-turn works: ask "and what does that mean?" as a follow-up, get a response that references the prior turn's tool result (proves message history is being threaded into `messages_for_api()`).
- [ ] Stop button cancels a long turn cleanly; transcript shows `(cancelled)`; the next turn works normally.
- [ ] Mode picker and Model picker are visible, populated with the right options, and disabled with a tooltip "Configured in Slice C".
- [ ] Close + re-launch the app → "Chat" still in sidebar; transcript empty (expected — Slice C adds persistence).
- [ ] No Qt warnings in stderr about cross-thread signal/slot connections or zombie QThreads at app close.
- [ ] No unexpected text in the transcript (no debug prints, no raw event repr strings).

---

## Deliverable shape

Single commit on `main` of the `crmbuilder` repo. Commit-message convention:

```
v2: PI-052 Slice B — PySide6 chat tab MVP (one tool wired, streaming on, in-memory only)

WT-055. Per DEC-261 (slicing plan) and DEC-257 (streaming on; QThread +
private asyncio loop, no qasync). Second slice of PI-052: PySide6 chat
tab MVP with one tool (`get_current_status`), live streaming via
`AsyncAnthropic.messages.stream()`, API-key bootstrap (env → keyring →
modal), and cancel-button support. No persistence, no prompt caching,
no mode-toggle/model-picker functionality, no usage display, no
multi-conversation sidebar — all four lift in Slice C / D per the
design doc §10 plan.

New files: <list>
Touched: <list>
pyproject.toml gains keyring runtime dep.

<implementation notes>

<smoke-test summary>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

After the commit lands, the build-closure conversation authors a close-out payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_<next>.json` carrying:

- 1 session (the Slice B build session)
- 1 conversation
- 1 commit (lazy, from the SHA above)
- 0 new work_tickets (Slice C kickoff is authored at Slice C kickoff-authoring time, same as Slice B was)
- 0 new planning items (none expected; surface any genuine surprises as DECs or PIs)
- 0–N decisions (per the kickoff: if Slice B composes as the design predicted, no DECs; if the Qt+asyncio bridging surfaces architectural revisions, record them with an explicit `supersedes` edge against DEC-257)
- 1 `is_about` reference (SES-<next> → PI-052)
- 1 `addresses` edge (CONV-<next> → PI-052) — PI-052 stays Open through Slice C, resolves on Slice D
- WT-055 transitions ready → consumed via the conversation's `conversation_opens_against_work_ticket` edge, then PATCHed to `consumed` after apply (apply_close_out.py does not auto-transition; pattern matches SES-080 and SES-087 close-out applies)

---

## What comes next

Slice C's kickoff is authored after Slice B lands successfully. The kickoff body lives at `pi-052-slice-c-full-surface-persistence-caching-kickoff.md` (to be authored). Anticipated WT-<next-free-at-the-time> per the parallel-sandbox-collision discipline.

Slice C is the substantive build: refactor `mcp_server.tools.register_tools` into a `tool_definitions()` helper per design doc Appendix A; wire all 44 tools through the dispatcher; add JSON-file persistence + the multi-conversation sidebar; apply prompt caching at all three tiers; draft the system prompt per design §13; wire the usage display; activate the mode toggle and model picker. Slice D is polish, exports, error recovery, and the test suite.

If Slice B surfaces a blocker (the Qt+asyncio bridging doesn't compose as expected, the streaming events don't shape-fit the controller signals cleanly, the keyring backend on Linux Mint has a quirk that makes the bootstrap dialog needed even with a key in env), Slice C's kickoff is the place to record the architectural revision — issue any necessary `supersedes` edges against DEC-257 / DEC-258 / DEC-254 in Slice B's close-out and reflect the revision in Slice C's scope.

---

## Identifier note

Anticipates WT-055 consumed and SES-091 / CONV-061 / DEC-301+ created (heads at kickoff author time: SES-090 / CONV-060 / DEC-300 / WT-054). Verify identifier heads with `list_recent_sessions` / `curl /work-tickets/WT-055` at conversation open. Parallel-sandbox identifier collisions are the rule, not the exception in this engagement — SES-080 saw three rebases, SES-087 saw multiple, and the SES-085 / SES-087 / SES-089 architecture-review re-key chain that followed Slice A's close-out is fresh in memory. Same discipline applies here.

---

## One open question for the implementer

Design doc §2.4 specifies the dispatcher as a module that "at import time, the module reads `crmbuilder_v2.mcp_server.tools.register_tools` indirectly by re-defining the same 44 functions". Slice B sidesteps this entirely — only one tool is wired, defined inline. But the question for Slice B's implementer is whether the *shape* of the Slice B dispatcher is forward-compatible with Slice C's refactor. Concretely: does Slice B's `chat/tools.py` use a `TOOL_DEFINITIONS: list[dict]` constant that Slice C can grow, or does it hardcode the schema inside the `invoke()` function?

The right answer is the former — a list of dicts that Slice C replaces with the output of `tool_definitions()`. That way Slice C's change to `chat/tools.py` is a single replacement: `TOOL_DEFINITIONS = tool_definitions()`. If the implementer chooses otherwise (e.g., for clarity reasons), note it in the build-closure narrative so Slice C knows what it's working against.
