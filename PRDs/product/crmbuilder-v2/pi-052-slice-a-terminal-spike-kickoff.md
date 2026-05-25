# Kickoff: PI-052 Slice A — terminal proof-of-concept Python script for the Anthropic-API chat loop with native tool definitions

> **V2 governance anchor:** WT-048 addresses PI-052 and points at this file via `work_ticket_file_path`. The file is canonical when this body and WT-048's `work_ticket_description` drift (per DEC-262, the hybrid-kickoff pattern).

**Status:** Ready. This is the first implementation slice of PI-052 per the slicing plan settled in DEC-261 (SES-080).

**Session type:** Implementation. Build-execution working mode. Output is the `chat_spike.py` script and a build-closure conversation that closes WT-048.

**Anticipated session at close:** SES-081 (verify with `list_recent_sessions` at conversation open per the parallel-sandbox-collision discipline).

---

## Why this slice exists

The PI-052 design session (SES-080) settled the chat-UI architecture as a PySide6 tab inside the v2 desktop app (DEC-252), with all 44 tools registered (DEC-253), streaming on (DEC-257), and a four-slice build plan (DEC-261). Before any UI code lands, Slice A validates the foundational architecture — that the Anthropic SDK + native `tools=[...]` definitions + `httpx` against the REST API at 127.0.0.1:8765 actually compose into a working chat loop. The lesson from DEC-244 (verify the integration end-to-end before building infrastructure on top of it) is the framing: if the loop doesn't work in 80 LOC of pure Python, it isn't going to work better with a PySide6 wrapper on top.

Slice A is intentionally minimal. Three tools, no streaming, no caching, no persistence, terminal `input()` loop. It is a throwaway script — committed to the repo as a reference but not maintained going forward. Slice B is the first slice with production code.

---

## Read first

### Tier 1 — design-doc anchor

1. `PRDs/product/crmbuilder-v2/pi-052-chat-ui-design.md` — the canonical PI-052 design document. Sections most relevant to Slice A: §1 (Architecture overview), §4 (Tool surface scope — the read tools the spike uses), §7 (Tool execution loop — Slice A is the blocking simplification of this), §10 (Slicing plan, Slice A acceptance criteria), §12 (Error recovery matrix — the spike implements only 401 + Ctrl+C).
2. `PRDs/product/crmbuilder-v2/close-out-payloads/ses_080.json` — the SES-080 close-out payload containing DEC-252 through DEC-262.

### Tier 2 — code surface to reuse

3. `crmbuilder-v2/src/crmbuilder_v2/mcp_server/tools.py` — read the three tools the spike implements: `get_current_status` (line 57), `get_current_charter` (line 34), `list_recent_sessions` (line 171). Note the docstring + signature pattern; the spike re-defines them inline rather than refactoring (Slice C does the refactor per design doc Appendix A).
4. `crmbuilder-v2/src/crmbuilder_v2/api/main.py` and `crmbuilder-v2/src/crmbuilder_v2/api/routers/` — the FastAPI surface the tools call. The spike uses `httpx.AsyncClient(base_url="http://127.0.0.1:8765", timeout=30.0)`.

### Tier 3 — Anthropic SDK reference

5. The `anthropic` Python SDK's `messages.create` (blocking variant — Slice A doesn't use streaming) and the `tools=[...]` parameter format. The spike imports `anthropic` and `httpx` and nothing else from the crmbuilder codebase.

### Tier 4 — methodology references

6. `crmbuilder/CLAUDE.md` v2 section — for the v2 governance state and push convention.
7. The `/claude-api` skill — for Anthropic SDK patterns. **NOTE:** prompt caching is normally required by the skill but is explicitly deferred to Slice C in DEC-261 — the spike intentionally skips it. The Slice-C build-execution session will revisit caching.

---

## Goal

A standalone Python script at `crmbuilder-v2/scripts/chat_spike.py` that:

1. Reads `ANTHROPIC_API_KEY` from the environment; fails loud with a clear error if missing.
2. Constructs an `anthropic.Anthropic()` client.
3. Constructs an `httpx.Client(base_url="http://127.0.0.1:8765", timeout=30.0)` (blocking, not async).
4. Defines three tools inline as a `tools = [...]` list with name, description, and a hand-written JSON Schema for the input. Tools are:
   - `get_current_status` — no parameters, returns current status singleton.
   - `get_current_charter` — no parameters, returns current charter singleton.
   - `list_recent_sessions` — one optional integer parameter `limit` (default 3).
5. Implements three Python functions matching the tool names, each calling `httpx` and unwrapping the `{data, meta, errors}` envelope.
6. Runs a terminal `input()` loop:
   - Read user input. Ctrl+C exits cleanly.
   - Append to message history.
   - Call `client.messages.create(model="claude-opus-4-7", system="...", tools=tools, messages=messages, max_tokens=8192)` (no streaming).
   - For each `tool_use` block in the response, dispatch to the matching local function, build a `tool_result` content block, append to messages, and call `messages.create` again.
   - Loop until response `stop_reason != "tool_use"`.
   - Print the final assistant text to stdout. Tool calls echo to stderr (one line per call: `→ tool_name(args)`).
7. ~80 LOC including imports and the three tool functions. No tests in this slice.

A minimal system prompt is OK — one paragraph identifying Claude as an assistant with v2 governance tool access. The full system prompt design happens in Slice C.

---

## Non-goals

- No PySide6 code. The spike is terminal-only.
- No streaming. The spike uses the blocking `messages.create()` API.
- No prompt caching. Skipped per DEC-261 — Slice C revisits.
- No persistence. Conversation history lives in a local list variable; lost on exit.
- No write tools. Only reads. (Writes land in Slice B alongside the mode toggle from DEC-255.)
- No refactor of `mcp_server.tools`. The three tool functions are duplicated inline; the shared `tool_definitions()` helper from design doc Appendix A is Slice C.
- No tests. The spike is throwaway code validated by manual run.
- No keyring integration. Env var only — Slice B adds the keyring path per DEC-254.

---

## Working pattern

Standard Claude Code build-execution conversation: implement, test manually, iterate, commit when working. The script lives at `crmbuilder-v2/scripts/chat_spike.py`. Commit message follows the v2 convention (subject line then body referring to WT-048 + DEC-261).

The spike should run end-to-end in one session — the implementation is small enough that a single conversation can author, test, and commit. If something material doesn't work (the loop hangs, tool calls error out, the SDK behaves unexpectedly), the session pivots to investigation and the spike's value increases — the architecture decision in DEC-257 (streaming on, QThread + asyncio) is downstream of "the basic loop works"; Slice A is where we'd discover otherwise.

---

## Acceptance criteria

Run from terminal:

```bash
cd ~/Dropbox/Projects/crmbuilder
uv run python crmbuilder-v2/scripts/chat_spike.py
> What's the current status?
```

Expected behavior:

1. Script starts, no errors.
2. Reads `ANTHROPIC_API_KEY` from env. If not set, prints `ANTHROPIC_API_KEY not set` and exits with code 1.
3. Prompts `> ` (or similar).
4. Doug types the question.
5. Stderr shows `→ get_current_status()`.
6. Stdout shows a coherent paragraph synthesizing the current status (v0.6 shipped, etc.) from the tool result.
7. Prompt returns. Doug can ask follow-ups.
8. Ctrl+C exits cleanly.

Additional checks the implementer should run before claiming Slice A complete:

- `list_recent_sessions` works when the user asks "what were the last three sessions?".
- `get_current_charter` works when the user asks "show me the charter governance principles".
- Multi-tool turn works: ask "what's the status and what were the last three sessions?" — Claude should call both tools in one assistant message; the spike should dispatch both and feed both results back.

---

## Deliverable shape

Single commit on the `main` branch of the crmbuilder repo:

- `crmbuilder-v2/scripts/chat_spike.py` (new file, ~80 LOC).

Commit message convention:

```
v2: PI-052 Slice A — terminal proof-of-concept for Anthropic-API chat loop with three read-only governance tools

WT-048. Per DEC-261 (slicing plan) and DEC-257 (streaming on for the
production UI — explicitly deferred for this spike), this is the
foundational architecture validation: ~80 LOC Python script that runs
a blocking chat loop with three hand-defined tools (get_current_status,
get_current_charter, list_recent_sessions), validating that the
Anthropic SDK + native tools=[...] + httpx against the local REST API
compose into a working chat loop before any PySide6 code lands.

No PySide6, no streaming, no caching, no persistence. Slice B is the
first slice with production code. The script is throwaway —
committed as a reference but not maintained.
```

No close-out payload for Slice A — it's a small implementation slice, not a methodology session. The build-closure conversation that lands the commit also lands a SES-081 session record with `is_about PI-052` + `consumed WT-048`, but without DECs (no architectural decisions in Slice A — DEC-261 already settled the slicing plan; Slice A is execution against it).

If Slice A surprises us (e.g., the SDK API surface differs from what the design doc assumed), the build-closure conversation can issue follow-up DECs to record the variance, but the expected path is no new decisions.

---

## What comes next

Slice B's kickoff is authored after Slice A lands successfully. The kickoff body is at `pi-052-slice-b-pyside6-tab-mvp-kickoff.md` (to be authored) and the WT identifier is WT-049 (anticipated; verify at the time).

Slice B's scope: the full PySide6 tab structure, one tool wired through the dispatcher, streaming on, no persistence, mode toggle and model picker present but read-only. Slice C is where the substantive build lands (full tool surface, persistence, caching, system prompt).

If Slice A surfaces a blocker (the architecture doesn't compose as expected), Slice B's kickoff is the place to record the architectural revision. The PI-052 design document is canonical and gets updated in place; any DEC issued during Slice A's build-closure that contradicts a DEC-252–DEC-262 decision issues an explicit supersedes edge.

---

## Identifier note

Anticipates SES-081 and WT-048 consumed. Verify identifier heads with `list_recent_sessions` / `curl /work-tickets/WT-048` at conversation open. Parallel-sandbox identifier collisions remain possible — SES-080 (the design session) saw the rebasing pattern twice (kickoff anticipated SES-078, displaced by the parallel PI-002 build closure to SES-079, then displaced again by the parallel orchestrator session to SES-080). Same discipline applies here for SES-081.

---

## One open question for the implementer

The Anthropic SDK exposes `messages.create()` blocking and `messages.stream()` async. Slice A uses blocking. The DEC-257 streaming design says "vanilla QThread + asyncio.run() for the production worker" — Slice A doesn't have a worker, so it uses the blocking path. If the implementer finds the blocking API surprisingly cumbersome (e.g., it doesn't expose tool-use results in a clean shape), that's a Slice A surprise worth recording in the build-closure SES-081 narrative — it doesn't invalidate DEC-257 (which is about the production threading model, not the spike), but it informs Slice B's design.
