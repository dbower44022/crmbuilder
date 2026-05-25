# PI-052 — Chat UI on Anthropic API: Architecture and Slicing Plan

**Status:** Draft from SES-080 (design + planning session, ARCHITECTURE working mode).
**Anchors:** PI-052, DEC-245 (architectural pivot), DEC-244 (claude.ai connector bug), WT-047 (kickoff body), WS-010 (v2 AI Surface Integration workstream).
**Successor decisions:** DEC-252 through DEC-262 (settled in SES-080; see §11).

This document is the canonical architecture for the chat-UI add-on. It supersedes the deferred-choice language in DEC-245 ("UI surface deferred to a Phase 1 spike") and replaces it with a settled plan that the Slice-A through Slice-D implementation sessions execute against.

---

## 1. Architecture overview

The chat UI is a new tab inside the existing `crmbuilder-v2` PySide6 desktop application. It uses the Anthropic Python SDK (`anthropic.Anthropic`) with `messages.create(tools=...)` to drive a chat loop. Tool definitions are generated at startup from the 44 functions in `crmbuilder_v2.mcp_server.tools` — the same module the stdio MCP server registers with FastMCP. Tool execution dispatches through an `httpx.AsyncClient` against the existing FastAPI REST API at `127.0.0.1:8765`. No MCP HTTP transport, no Cloudflare Tunnel, no claude.ai connector.

```
+----------------------------------------------------------+
| QApplication (crmbuilder-v2-ui)                         |
|                                                          |
|  MainWindow                                              |
|   +-- Sidebar  (new entry: "Chat" in a new "AI" group)   |
|   +-- QStackedWidget                                     |
|        +-- ChartersPanel ...                             |
|        +-- ChatPanel    (new, this PI)                   |
|             +-- ChatHeader  (model picker, mode toggle,  |
|             |               session total tokens/$)       |
|             +-- ConversationSidebar  (list of saved      |
|             |    chats from ~/.crmbuilder-v2/chats/)     |
|             +-- TranscriptView  (QListWidget, custom     |
|             |    item delegates per message type)        |
|             +-- InputArea  (multi-line QPlainTextEdit +  |
|                  Send button + Stop button)              |
|                                                          |
|        ChatController (QObject)                          |
|         +-- ChatWorker (QThread hosting asyncio loop)    |
|              +-- anthropic.AsyncAnthropic client          |
|              +-- httpx.AsyncClient(base_url="...:8765")  |
|              +-- tool_dispatcher (signatures from        |
|                   mcp_server.tools → JSONSchema)         |
+----------------------------------------------------------+
```

The chat loop runs entirely in a worker thread. The Qt main thread renders streamed tokens via signals; tool execution is blocking inside the worker (it awaits httpx) but does not block the UI. Stop / cancel are honored at the loop boundary.

---

## 2. Component breakdown

### 2.1 `ui/panels/chat.py` — `ChatPanel`

Top-level `QWidget` subclass that the main window registers under sidebar entry `Chat` in a new `AI` group. Composed of header, optional conversation-sidebar, transcript, and input. Sizing follows the existing v0.6 design tokens (sidebar 220px, header 48px, etc.). Owns one `ChatController`.

### 2.2 `ui/chat/controller.py` — `ChatController(QObject)`

The main-thread bridge. Holds:

- the active `ChatSession` object (current transcript + metadata),
- a `ChatWorker` instance running the inference loop in a worker thread,
- signals fanned out to the panel:
  - `message_added(role, content_block)`
  - `streaming_delta(message_index, text_delta)`
  - `tool_call_started(message_index, tool_name, args_json)`
  - `tool_call_completed(message_index, tool_name, result_json, ms)`
  - `tool_call_failed(message_index, tool_name, error)`
  - `usage_updated(input_tokens, output_tokens, cache_read, cache_create)`
  - `loop_finished(stop_reason)`
  - `loop_failed(error)`

Owns persistence: on every assistant turn completion, the controller writes the current `ChatSession` to `~/.crmbuilder-v2/chats/<chat_id>.jsonl` (one JSON object per line, append-only inside a single turn; rewritten atomically on turn close).

### 2.3 `ui/chat/worker.py` — `ChatWorker(QThread)`

Hosts a private asyncio event loop. Public entry points are slot-callable from the main thread (`start_turn(user_text)`, `stop()`, `set_mode(...)`). Internal loop:

```python
async def _run_turn(self, user_text: str) -> None:
    session.append_user(user_text)
    while True:
        async with self._anthropic.messages.stream(
            model=session.model,
            system=self._cached_system_block(),
            tools=self._cached_tools_block(),
            messages=session.messages_for_api(),
            max_tokens=8192,
        ) as stream:
            async for event in stream:
                self._dispatch_stream_event(event)
            final = await stream.get_final_message()
        session.append_assistant(final)
        if final.stop_reason != "tool_use":
            break
        tool_results = await self._execute_tool_calls(final)
        session.append_user_tool_results(tool_results)
```

`_execute_tool_calls` runs tool calls concurrently when there are multiple `tool_use` blocks in a single assistant message (gather), serial otherwise. Each call is dispatched through `tool_dispatcher.invoke(name, args)`.

### 2.4 `ui/chat/tools.py` — tool dispatcher

At import time, the module reads `crmbuilder_v2.mcp_server.tools.register_tools` indirectly by re-defining the same 44 functions (extracted from the closure pattern by re-organizing `tools.py` into a pair of registration helpers — see §6.4 *Refactor: extract tool surface* below). At controller startup the dispatcher:

1. Builds an Anthropic-API-compatible `tools=[...]` block (each entry: `{name, description, input_schema}`). Schema generation uses `inspect.signature` + the docstring as `description`; required-vs-optional inferred from default values; types mapped to JSONSchema via a small table (`str→string`, `int→integer`, `dict→object`, `str|None→string with default null`).
2. Partitions tool names into `read_tools` (`get_*`, `list_*`, `catalog_*`, `*_for_*`) and `write_tools` (`create_*`, `update_*`, `delete_*`, `add_*`, `replace_*`).
3. Exposes `invoke(name, args) -> dict` that wraps the function with the controller's `httpx.AsyncClient`.

The dispatcher is the single source of truth for what tools exist. The MCP stdio server continues to register the same surface via `register_tools(server, http)` — both surfaces stay in sync because they both read from the same registration helper.

### 2.5 `ui/chat/session.py` — `ChatSession` dataclass

```python
@dataclass
class ChatSession:
    chat_id: str             # uuid7 — sortable by creation time
    title: str               # auto-set from first user turn, editable
    model: str               # "claude-opus-4-7" default
    created_at: datetime
    updated_at: datetime
    mode: Literal["full", "read_only", "ask_before_write"]
    messages: list[dict]     # Anthropic API message format
    usage: UsageRollup       # cumulative tokens + cost estimate
```

`messages_for_api()` returns the list in the format the SDK expects. Tool-result blocks are stored as native Anthropic `user` messages with `tool_result` content blocks.

### 2.6 `ui/chat/persistence.py`

Single file per chat at `~/.crmbuilder-v2/chats/<chat_id>.json` (single JSON document, not JSONL — kept simple for v1; revisit if files get large). Atomic write via tmp-and-rename. The conversation sidebar reads the directory on panel open and on file-watch events. Each chat file is self-contained — no DB dependency.

### 2.7 `ui/chat/widgets.py` — transcript rendering

Custom item widgets for:

- `UserMessageItem` (right-aligned bubble, neutral.100 background per design tokens),
- `AssistantMessageItem` (left-aligned, neutral.0 background, hairline border),
- `ToolUseItem` (collapsed by default — shows `🔧 create_decision({…})` with click-to-expand args; expanded shows pretty-printed JSON),
- `ToolResultItem` (collapsed by default — shows `↩︎ created DEC-253` synthesized line; click-to-expand to see full JSON result),
- `ErrorItem` (warning callout reusing the v0.6 slice E `WarningCallout` for retryable errors, `ErrorDialog` for fatal).

Tool name + args are always visible (transparency about what Claude is doing); tool result is collapsed by default (avoid cluttering transcript with large JSON dumps). One-click expand on either.

### 2.8 No new REST endpoints

The chat UI consumes the existing FastAPI surface. It does not add new endpoints. This is a deliberate constraint: it keeps the chat tab side-loadable (could be removed entirely without touching the storage system) and lets the same tool surface flow through Claude Desktop's stdio MCP path unchanged.

---

## 3. Data flow

User types in `InputArea` → Send → `ChatController.start_turn(text)` → emits `message_added(user, text)` → `ChatWorker.start_turn(text)`.

Worker: appends user message; calls `messages.stream(tools=[...])`; per delta event emits `streaming_delta(idx, text)` back to controller via Qt signal (thread-safe). On `tool_use` content blocks at stream end: emits `tool_call_started`, executes via `httpx.AsyncClient → http://127.0.0.1:8765/...`, emits `tool_call_completed` (or `_failed`). Appends `tool_result` content block to messages and re-enters the loop. When `stop_reason != "tool_use"`, emits `loop_finished` and returns.

Controller: on every emitted signal it updates the in-memory `ChatSession` and queues a persistence write at turn boundaries (debounced 250ms). The panel's transcript widgets subscribe to the controller signals and redraw incrementally.

---

## 4. Tool surface scope

**Decision (DEC-253):** All 44 tools registered out of the gate. No MVP subset.

Rationale: the 44 tools already exist as a complete, tested surface (the MCP stdio server has been using them for months). Cherry-picking a subset would add code, force a partition decision Doug doesn't need today, and miss out on Claude's ability to chain tools (e.g., "look up the related decisions" → `list_references_to(decision, DEC-244)` → `get_decision("DEC-226")`). The chat is most useful when it has the full surface.

Read/write partition (used by read-only mode and the per-session confirm toggle):

| Bucket  | Tools (44 total)                                                                                                                                                                                                                                |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Read    | get_current_charter, get_charter_version, list_charter_versions, get_current_status, get_status_version, list_status_versions, get_decision, list_decisions, get_session, list_sessions, list_recent_sessions, list_decisions_for_session, get_risk, list_risks, get_planning_item, list_planning_items, get_topic, list_topics, list_references, list_references_from, list_references_to, list_references_touching, catalog_search, catalog_get_entity, catalog_get_cross_system_map, catalog_gap_check |
| Write   | replace_charter, replace_status, create_decision, update_decision, delete_decision, create_session, delete_session, create_risk, update_risk, delete_risk, create_planning_item, update_planning_item, delete_planning_item, create_topic, update_topic, delete_topic, add_reference, delete_reference |

(Partitioning is by name-prefix at registration time; the tool dispatcher exposes `read_names: set[str]` and `write_names: set[str]` for the controller to consult.)

---

## 5. Auth model

**Decision (DEC-254):** API key from `ANTHROPIC_API_KEY` environment variable, primary. Fallback to a key stored in the system keyring under service `crmbuilder-v2-chat`, user `default`. Never stored in `settings.json` (avoids accidental commit).

### Bootstrap

On chat panel first activation (lazy — not on app startup, so users who never open the tab don't see a key prompt):

1. Check `os.environ["ANTHROPIC_API_KEY"]`. If present, use it.
2. Else check `keyring.get_password("crmbuilder-v2-chat", "default")`. If present, use it.
3. Else show a modal API-key configuration dialog with one text field, a "paste from clipboard" button, a "save to keyring" checkbox (default on), and Save/Cancel. On Save, the key is held in memory for this app run and written to the keyring if checked. Cancel disables the chat tab (sidebar entry stays visible but selecting it shows a "no API key configured" empty state with a Configure button).

### Runtime failures

- **401 Unauthorized from Anthropic:** show the configuration dialog again with an "invalid key" warning callout. Clear the in-memory key but leave the keyring entry untouched (let the user decide whether to overwrite).
- **402 Payment Required:** show the error inline in the transcript with a link to the Anthropic Console billing page.
- **Network error reaching api.anthropic.com:** retry once with 2s backoff; if still failing, show error inline; let the user click "Retry".

The key is never logged or written to disk except via `keyring`. The `keyring` library's default backend on Linux Mint is `SecretService` (gnome-keyring); macOS uses Keychain; Windows uses Credential Manager. Add `keyring` to `pyproject.toml`.

---

## 6. Conversation state and persistence

**Decision (DEC-256):** JSON files on disk, NOT a first-class governance entity. Path: `~/.crmbuilder-v2/chats/<chat_id>.json`. Schema: the `ChatSession` dataclass serialized.

### Why not a governance entity (for v1)

A "chat session" in this UI is an ad-hoc, exploratory Q&A surface. It is fundamentally different in kind from a `session` in the v2 governance schema (which models a methodology session that produces decisions, has explicit edges to workstreams and work tickets, and lives inside the audit chain). Modeling chat sessions as governance entities would:

- require ~5 new SQLAlchemy tables (`chat_session`, `chat_message`, `chat_tool_call`, `chat_tool_result`, `chat_session_usage`),
- thread through the REST API + envelope + access layer + MCP tools,
- pull schema versioning + migration into scope,
- and add a confusing namespace overlap with the existing `session` entity.

None of that is needed for v1. JSON files give us: persistence, listability, exportability, restorability, and zero schema impact. If Doug later decides chat sessions deserve first-class governance treatment (e.g., a chat that produces decisions should close out as a methodology session with edges), that becomes its own PI — surfaced here as a candidate but not adopted (see §10 *Future PI candidates*).

### File format

```json
{
  "chat_id": "01H...",
  "schema_version": 1,
  "title": "Audit DEC-244 / 245 chain",
  "model": "claude-opus-4-7",
  "created_at": "2026-05-25T22:30:00Z",
  "updated_at": "2026-05-25T22:34:12Z",
  "mode": "full",
  "messages": [
    {"role": "user", "content": [{"type": "text", "text": "Show me the supersedes chain from DEC-245."}]},
    {"role": "assistant", "content": [
      {"type": "text", "text": "I'll look that up."},
      {"type": "tool_use", "id": "toolu_...", "name": "list_references_from", "input": {"source_type": "decision", "source_id": "DEC-245"}}
    ]},
    {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_...", "content": "[{...}, {...}]"}]},
    {"role": "assistant", "content": [{"type": "text", "text": "DEC-245 supersedes DEC-226..."}]}
  ],
  "usage": {
    "total_input_tokens": 12450,
    "total_output_tokens": 870,
    "total_cache_creation_tokens": 7800,
    "total_cache_read_tokens": 4200,
    "estimated_cost_usd": 0.094
  }
}
```

### Multi-conversation UX

**Decision (DEC-258):** claude.ai-web sidebar pattern, single active chat at a time.

The chat panel splits left-to-right at 240px:

```
[ Conversation list 240px | Active chat ]
```

The list shows one entry per JSON file in the chats directory, ordered by `updated_at` descending. Each entry: title (truncated to 2 lines) + relative timestamp. A "+ New chat" button at the top creates a new session in memory (no file written until the first user turn). Click an entry to switch the active session.

Right-click on a list entry: rename, delete, export-as-markdown.

No tabs, no simultaneously-running chats. If Doug needs two chats in parallel, he opens two instances of the desktop app (the storage system is multi-process-safe; the file-watcher handles cross-instance refresh).

---

## 7. Tool execution loop architecture

**Decision (DEC-257):** Streaming on by default. Worker pattern = `QThread` hosting a private asyncio event loop; main thread bridges via signals.

### Threading model

- **Main thread:** QApplication, all UI widgets, signal handlers. Only Qt code runs here.
- **Worker thread:** `ChatWorker(QThread)` with its own asyncio loop started inside `run()`. Holds the `anthropic.AsyncAnthropic` client and the `httpx.AsyncClient` for tool dispatch. Receives queued `QMetaObject.invokeMethod` calls from the controller as slot invocations.
- **No `qasync` dependency.** `qasync` is nice but adds a dep; for a single worker thread with a single asyncio loop, a vanilla `QThread.run()` containing `asyncio.run(self._loop_main())` is sufficient.

### Stream events

The Anthropic SDK's `messages.stream()` yields events: `MessageStartEvent`, `ContentBlockStartEvent`, `ContentBlockDeltaEvent` (text + input_json deltas), `ContentBlockStopEvent`, `MessageDeltaEvent`, `MessageStopEvent`. The worker dispatches:

- `text_delta` → emit `streaming_delta(message_idx, text)` → panel appends to the live text bubble.
- `input_json_delta` (for tool use) → accumulate; do NOT emit per-chunk (the tool args build up incrementally and aren't useful to render mid-stream).
- `content_block_stop` for a `tool_use` block → emit `tool_call_started(idx, name, accumulated_input)`.
- `message_stop` with `stop_reason == "tool_use"` → execute tools, then loop again.
- `message_stop` with `stop_reason == "end_turn"` → emit `loop_finished("end_turn")`.

### Concurrency for tool calls

Within a single assistant message, Claude can emit multiple `tool_use` blocks. The worker runs them concurrently via `asyncio.gather(*[invoke(...) for ...])` with a hard cap of 8 in-flight (well above any realistic Claude turn; protective). Results are appended in stream order.

### Stop / cancel

The header has a Stop button. Click → controller invokes `worker.stop()` → worker sets a `cancellation_event`; the next `await` in the loop checks it and raises `asyncio.CancelledError`, which the worker catches and emits `loop_finished("cancelled")`. Mid-stream cancellation is graceful: the partial text in the current bubble stays in the transcript, tool calls already dispatched complete normally (their results are appended even if the loop won't continue), and the assistant message is closed off cleanly.

---

## 8. Prompt caching strategy

Per the `/claude-api` skill, prompt caching is required on every Anthropic API call. The chat UI has three caching tiers (top to bottom):

### Tier 1: System block

The system prompt (`system=[{type: "text", text: "...", cache_control: {type: "ephemeral"}}]`) is cached as a single block. Content: the static methodology preamble, tool-surface semantics, output-style guidance. Cached on every call. Reused across every turn in a session; reused across sessions (identical text → cache hit).

### Tier 2: Tools block

Tool definitions (`tools=[{name, description, input_schema, cache_control: {type: "ephemeral"}}]`) — apply `cache_control` to the LAST tool in the array, per the Anthropic caching docs, to cache the cumulative tools block. Tool definitions are stable across turns (the 44 tools don't change), so every turn after the first is a cache hit on this block.

### Tier 3: Conversation history

After every assistant turn, mark the most recent user message (which contains the tool_results from the just-finished turn) with `cache_control: {type: "ephemeral"}`. This caches the rolling conversation prefix. Each subsequent turn rolls the cache point forward.

### Cache savings expectation

For a typical 10-turn chat with 8 tool calls averaging 800-token inputs / 200-token outputs:

- Without caching: ~80k input tokens billed across the conversation.
- With caching: ~12k uncached + ~68k cached-read (90% of cached cost). Savings ≈ 70% on input billing.

The cost display (§9) reports both uncached + cache-read tokens explicitly so the savings are visible.

---

## 9. UI layout and visible state

```
+---- Chat header (48px) ------------------------------------------+
| Model: [Opus 4.7 ▾]  Mode: [Full ▾]  ↑1.2k ↓340 (cache 4.2k) $0.012 [+New] [⏵] |
+-- 240px ------+---- main column ----------------------------------+
|+ New chat     | [user] Show me the supersedes chain from DEC-245. |
| Audit chain… |                                                    |
|  2 min ago    | [Claude] I'll look that up.                       |
|               | 🔧 list_references_from {"source_type":...} ▶    |
| Schema spike  | ↩︎ 4 results ▶                                    |
|  Yesterday    |                                                    |
|               | DEC-245 supersedes DEC-226 (single edge). The…    |
| First chat    |                                                    |
|  3 days ago   |                                                    |
|               |                                                    |
+---------------+----------------------------------------------------+
| Streaming…                                                         |
+--------------------------------------------------------------------+
| Type a message…                                       [Send] [Stop]|
+--------------------------------------------------------------------+
```

### Header elements

- **Model picker:** `QComboBox` with Opus 4.7 (default), Sonnet 4.6, Haiku 4.5. Affects the next turn; in-flight turns finish on the previously-selected model. (DEC-260.)
- **Mode picker:** `Full`, `Read-only`, `Ask before write`. Changes the tool surface presented in the next turn. (DEC-255 + DEC-257.)
- **Usage display:** `↑input ↓output (cache cached)` plus `$total` for the current session. Updates after every turn from `MessageStopEvent.usage`. Cost estimated client-side from a small pricing table per model. (DEC-259.)
- **+ New** button: create a new session, switch to it.
- **▶ Stop** button: visible only when a turn is in flight; cancels it.

### Sidebar conversation list

- Auto-titled from the first user turn (`session.title = first_user_text[:60]`). Editable via right-click → Rename.
- Ordered by `updated_at` descending.
- "Today" / "Yesterday" / relative-date headers when the list crosses a day boundary (claude.ai-web convention).
- Right-click context menu: Rename, Delete, Export as Markdown (writes to a chosen path; format: front-matter + linearized transcript).

### Transcript

- Reuses v0.6 design tokens: `color.neutral.0` for assistant bubbles, `color.neutral.100` for user bubbles, hairline border `color.neutral.300`, `font.body` for content, `font.mono` for tool args and JSON results.
- Tool-call disclosure widgets: collapsed by default, expand on click. Tool name + truncated arg summary always visible.

---

## 10. Slicing plan

**Decision (DEC-261):** Four slices A through D, each independently runnable and reviewable.

### Slice A — Terminal proof of concept

**~80 LOC standalone script at `crmbuilder-v2/scripts/chat_spike.py`.** Validates end-to-end loop with no UI work.

- Reads `ANTHROPIC_API_KEY` from env, fails loud if missing.
- Hardcodes 3 read tools: `get_current_status`, `get_current_charter`, `list_recent_sessions`.
- Manual tool-schema generation (don't refactor `mcp_server.tools` yet — just write the schemas inline).
- Blocking I/O, no streaming, no caching.
- `input()` loop, prints assistant text to stdout, prints tool calls to stderr.
- Exit cleanly on Ctrl+C.

**Acceptance:** Run from terminal, prompt "What's the current status?", Claude calls `get_current_status`, summarizes the response, no errors.

**Implementation session:** 1 hour. Becomes WT-048's body.

### Slice B — PySide6 chat tab MVP

**The full tab structure, one tool wired, streaming on, no persistence.**

- `ui/panels/chat.py` panel scaffold + sidebar entry registration in a new "AI" sidebar group.
- `ui/chat/controller.py`, `ui/chat/worker.py`, `ui/chat/session.py`.
- One tool wired through the dispatcher: `get_current_status`. Hardcoded schema.
- Streaming on. Worker thread + asyncio bridge functional.
- In-memory only — no JSON file persistence, no sidebar conversation list, no usage display.
- API key bootstrap dialog functional (key in env passes through; missing-key state shows a Configure button).
- Mode toggle and model picker present but read-only (no effect — Slice C wires them).
- Existing v0.6 styling tokens applied to bubbles, input, header.

**Acceptance:** Launch the app; click "Chat" in the sidebar; ask Claude "What's the current status?"; see streamed response with tool-use disclosure; close and re-launch — chat history empty (expected).

**Implementation session:** 1 day.

### Slice C — Full tool surface + persistence + caching

**The substantive build.**

- **Refactor `mcp_server.tools.register_tools`** into a pair of helpers: a `tool_definitions() -> list[ToolDefinition]` function that returns the canonical metadata (name, callable, signature, docstring, read/write), and `register_with_fastmcp(server, http, defs)` + `register_with_dispatcher(dispatcher, http, defs)`. Both registration paths reuse the same definitions, so the chat UI and Claude Desktop stay in sync forever.
- Tool dispatcher auto-builds the Anthropic API tools block from the definitions module (no hand-maintained schema list).
- All 44 tools wired.
- Persistence: read/write `~/.crmbuilder-v2/chats/<chat_id>.json`. Conversation sidebar populated.
- Prompt caching applied at all three tiers.
- System prompt drafted in this slice — see §11 *Q6 deferred* below for the structure.
- Cost + token usage display wired.
- Mode picker functional: `Full` exposes all tools, `Read-only` exposes only the 26 read tools, `Ask before write` exposes all tools but the controller intercepts every `tool_use` for a write tool and surfaces a modal "Claude wants to call X(args) — Allow / Deny / Edit" before dispatching.

**Acceptance:** Multi-turn conversation produces governance writes (e.g., "Create DEC-253 with ..."); writes appear in the storage system; chat is persisted across app restarts; cache-read tokens visible on subsequent turns; mode toggle behaves correctly.

**Implementation session:** 2 days.

### Slice D — Polish, exports, error recovery

- Multi-conversation operations: rename, delete, export-as-markdown.
- Error recovery matrix from §12 wired (rate-limit retry, context-window overflow handling, 401 reprompt, 500 inline error).
- Token-usage display refined: per-turn footer + per-session total in header, with cache hit ratio visible.
- Sidebar staleness indicator integration (the existing `RefreshService` already watches `db-export/*.json`; chat tab subscribes for cross-tab "Decisions panel changed" hints so it can flag a session whose `list_decisions` result might be stale — informational only, not a re-call).
- Test coverage: unit tests for tool dispatch + schema generation, end-to-end tests with a recorded Anthropic API mock.

**Acceptance:** Full WCAG-AA palette compliance (regression with the v0.6 build gate); all error cases recoverable without app restart; chat UX feels at parity with a polished v1.

**Implementation session:** 1.5 days.

---

## 11. Decisions issued by SES-080 (this session)

| ID      | Title                                                                                                 | Settles                  |
| ------- | ----------------------------------------------------------------------------------------------------- | ------------------------ |
| DEC-252 | PySide6 chat tab as the production UI surface for the chat UI                                          | DEC-245 Phase 2 deferred |
| DEC-253 | Chat UI tool surface = all 44 read+write tools registered; partitioned by name-prefix for mode toggle | Goal #2                  |
| DEC-254 | Anthropic API key from `ANTHROPIC_API_KEY` env primary, system keyring fallback, never in settings.json | Goal #3                  |
| DEC-255 | Tool-call confirmation policy — auto-execute with inline disclosure + per-session "ask before write" toggle | Q1                       |
| DEC-256 | Chat session persistence = JSON files under `~/.crmbuilder-v2/chats/`; first-class governance treatment deferred | Q3                       |
| DEC-257 | Streaming on by default; `QThread` + private asyncio event loop, no `qasync` dependency                | Q9                       |
| DEC-258 | Multi-conversation UX = claude.ai-web sidebar pattern, single active chat                              | Q8                       |
| DEC-259 | Cost + token visibility = per-turn footer + per-session total in header, three-tier cache-hit display | Q5                       |
| DEC-260 | Model selection = Opus 4.7 default; Sonnet 4.6 + Haiku 4.5 selectable in header                       | Goal #7                  |
| DEC-261 | Slicing plan for PI-052 = four slices A (terminal spike), B (MVP tab), C (full surface + caching), D (polish) | Goal #9                  |
| DEC-262 | Hybrid kickoff pattern (WT inline summary + file pointer + "file is canonical") as the standard for non-trivial kickoff bodies | Methodology Q from kickoff body |

Three open questions from the kickoff are **not** issued as DECs in this session:

- **Q4 (tool-result visibility default)** — follows from DEC-255 + the design pattern in §2.7: collapsed by default, tool name + args visible, expand-on-click. No separate DEC.
- **Q6 (system prompt design)** — substantial prompt-engineering work; outlined in §13 below; full settlement deferred to Slice C and recorded as a DEC at that time.
- **Q7 (conversation export as governance close-out)** — Surfaced as a future PI candidate (see §14). Not adopted in v1.

Read-only mode default is handled as a behavioral aspect of DEC-255 + the mode picker in §9: default mode is `Full`. A separate DEC isn't needed; this design doc is the load-bearing artifact.

---

## 12. Error recovery matrix

| Failure                                       | Behavior                                                                                                                                                                                                                              |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 401 Unauthorized from Anthropic               | Surface the API-key configuration dialog with an "invalid key" warning. Clear in-memory key. Keep the in-flight assistant message truncated where the error fired.                                                                    |
| 402 Payment Required                          | Inline error in transcript with a link to the Anthropic Console. Turn ends.                                                                                                                                                            |
| 429 Rate Limit                                | Auto-retry with exponential backoff: 2s, 4s, 8s, then give up and surface inline error. Show a "Rate limited, retrying in Ns" inline progress bubble during backoff.                                                                  |
| 500 / network error reaching api.anthropic.com | Auto-retry once after 2s. If still failing, surface inline error with Retry button. Partial streamed content is preserved.                                                                                                              |
| Tool call REST API 500 / network error        | Pass the error back as a `tool_result` with `is_error: true` and the error message. Let Claude decide whether to retry, explain, or surface to the user. (Anthropic SDK convention.)                                                  |
| Context window exceeded                       | Surface inline error: "This conversation exceeded the model's context window. Start a new chat or use Trim to drop the oldest N messages." Trim drops the oldest non-system messages until under the limit.                            |
| User clicks Stop mid-stream                   | Loop cancels at next `await`. Partial text stays in the transcript. Any in-flight tool calls complete and their results are recorded but not fed back to Claude (since the loop won't continue).                                       |
| User closes the app mid-stream                | Worker shutdown emits `loop_finished("app_closing")` after the current stream chunk. The session file is written one last time. On next launch, the session reopens in its truncated state.                                            |
| Keyring unavailable (e.g., headless Linux)    | API-key configuration dialog disables the "save to keyring" checkbox with a tooltip. Key is held in memory only for that app run. On next launch, prompt again.                                                                       |

---

## 13. System prompt design (Q6 outline, full settlement in Slice C)

The system prompt has three sections:

1. **Role + scope.** "You are an assistant embedded in the CRMBuilder v2 desktop application. You have read and write access to Doug's v2 governance database via the provided tools. Doug is the sole operator..." Reinforces single-user trust model.

2. **Tool-surface semantics.** Brief paragraph per entity type explaining what `decision`, `session`, `risk`, etc. mean in v2 governance, with pointers to specific tools. Plus: read-vs-write convention, identifier conventions (DEC-NNN, SES-NNN, etc.), edge semantics, the apply / close-out pattern in case Doug asks Claude to help draft a payload.

3. **Output preferences.** "Default to terse responses. Cite identifiers (DEC-NNN, etc.) when answering. When you call multiple tools, batch them in one assistant message rather than serializing. If you're unsure whether to write, ask first when mode is `Full` — Doug doesn't expect you to wait for permission, but a brief 'Going to create DEC-253 with X, Y, Z — sound right?' is welcome on consequential writes."

The full text is drafted in Slice C and issued as DEC-NNN at that time. Length budget: 1500–2500 tokens (justifies the system-block cache tier; the cache savings repay the cost on every turn).

---

## 14. Future PI candidates surfaced (not adopted in v1)

- **PI-053 candidate: Chat session as governance entity + conversation export.** Elevate chat sessions to first-class governance records, with REST + MCP surfaces, and add an "Export this chat as SES-NNN close-out" action. Justification depends on whether chats that produce decisions need the audit-chain treatment. Not authored as a PI here — surfaced for Doug's later judgment after he uses the v1 chat tab for a while.
- **PI-054 candidate: Remote-access surface for the chat UI** (web app, mobile). Out of scope per the kickoff non-goals. Surface only if Doug eventually wants chat-from-his-phone. The current architecture is local-only by design.
- **PI-055 candidate: Tool surface expansion.** New tools as the v2 schema grows (deposit events, workstreams, work tickets, close-out payloads — these have read access via list endpoints today but no dedicated chat-tool wrappers). Add when each entity surfaces real usage demand.

---

## 15. Open implementation questions

Each of these is for an implementation-session author to settle at build time, not a strategic question:

- Exact JSONSchema generation library — `typing.get_type_hints` + manual dispatch, or `pydantic.TypeAdapter`, or `griffe`? Pick when writing Slice C's tool dispatcher.
- Conversation file format versioning strategy when the `ChatSession` dataclass evolves. (`schema_version` field is in the file; migration policy = lazy on read, warn-and-skip on incompatible major bump.)
- Stop button affordance during tool execution (mid-loop, post-stream, pre-next-stream). Probably fine to leave Stop active throughout.
- Whether the conversation sidebar uses the existing `ListDetailPanel` base or a new bespoke widget. Probably bespoke — the existing base assumes a per-row CRUD model that doesn't match chat.

---

## 16. Cross-references and addressed work

- Addresses PI-052.
- References DEC-244 (claude.ai connector bug — the precipitating event), DEC-245 (architectural pivot — the parent decision), DEC-226 (superseded by DEC-245).
- Belongs to WS-010 (v2 AI Surface Integration workstream).
- Opens against WT-047 (the PI-052 kickoff body, which this session consumes).
- Produces WT-048 (Slice-A terminal spike kickoff body — authored alongside this design doc as a separate file).

---

## Appendix A — Refactor diff sketch for `mcp_server/tools.py`

The Slice C refactor extracts the registration pattern. Today:

```python
def register_tools(server: FastMCP, http: httpx.AsyncClient) -> None:
    @server.tool()
    async def get_current_charter() -> Any:
        """..."""
        return await _unwrap(await http.get("/charter"))
    # ... 43 more inline definitions
```

After:

```python
# tool_definitions.py
@dataclass(frozen=True)
class ToolDefinition:
    name: str
    callable: Callable
    description: str
    is_write: bool

def tool_definitions(http: httpx.AsyncClient) -> list[ToolDefinition]:
    async def get_current_charter() -> Any:
        """Return the current charter document (singleton, latest version)."""
        return await _unwrap(await http.get("/charter"))
    # ... 43 more
    return [
        ToolDefinition("get_current_charter", get_current_charter,
                       get_current_charter.__doc__, is_write=False),
        # ...
    ]

# mcp_server/server.py (unchanged in shape):
def register_tools(server: FastMCP, http: httpx.AsyncClient) -> None:
    for td in tool_definitions(http):
        server.tool(name=td.name, description=td.description)(td.callable)

# ui/chat/tools.py (new):
class ChatToolDispatcher:
    def __init__(self, http: httpx.AsyncClient):
        self._defs = {td.name: td for td in tool_definitions(http)}

    def anthropic_tools_block(self) -> list[dict]:
        return [{"name": td.name, "description": td.description,
                 "input_schema": _schema_from_signature(td.callable)}
                for td in self._defs.values()]

    async def invoke(self, name: str, args: dict) -> Any:
        return await self._defs[name].callable(**args)
```

This refactor is mechanical and surfaces no behavior changes for the MCP stdio server. It's the load-bearing change that lets the chat UI reuse the tool surface without re-implementation. Worth pulling into Slice C as an early step rather than at the end.

---

*End of design.*
