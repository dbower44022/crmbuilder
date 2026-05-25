# Kickoff: PI-052 — Chat UI add-on to the V2 PySide6 desktop app

**Status:** Ready. This kickoff is the architectural design conversation for the chat-UI work surfaced by DEC-245 (architectural pivot away from claude.ai-web after the upstream connector bug discovered in DEC-244).

**Session type:** Design + planning. ARCHITECTURE working mode throughout. No code is written in this conversation — the output is a design document, slicing plan, and architectural decisions.

**Anticipated session at close:** SES-078 (subject to identifier rebasing per the recent parallel-sandbox pattern; verify with `list_recent_sessions` at conversation open).

---

## Why this session exists

PI-052 was surfaced by SES-077 (the conversation that observed the upstream claude.ai connector bug end-to-end and pivoted away from remote-MCP integration). The original goal — *"a chat UI with access to v2 governance tools"* — remains valid and is now delivered via a different architecture: an integrated chat surface in the existing CRMBuilder v2 PySide6 desktop application, built on the Anthropic SDK with native `tools=[...]` definitions calling the REST API at `127.0.0.1:8765` directly. No MCP HTTP transport hop, no remote-access infrastructure, no third-party-bug dependency.

This session designs that add-on. The output is the design document and the slicing plan; a follow-up session (or sequence of sessions) implements the slices.

---

## Read first

### Tier 1 — universal v2 orientation

1. `crmbuilder/CLAUDE.md` — particularly the v2 Methodology Rearchitecture section (the new "v2 AI surface integration" paragraph captures the immediate context).
2. `get_current_status()` — current v2 governance state.
3. `get_current_charter()` — current v2 charter version.

### Tier 2 — strategic context for this PI

4. `get_decision("DEC-244")` — the empirical finding that closed off claude.ai-web as the integration surface (claude.ai connector OAuth blocked by upstream Anthropic bug across 7+ IdPs).
5. `get_decision("DEC-245")` — the architectural pivot to chat-UI-on-Anthropic-API with native tool definitions calling the REST API directly. Supersedes DEC-226.
6. `get_planning_item("PI-052")` — this PI's scope as recorded in V2 governance.
7. `get_session("SES-077")` — the SES-077 close-out (today's conversation that produced PI-052). Read `topics_covered`, `summary`, `in_flight_at_end` for the full reasoning chain.

### Tier 3 — code surface to reuse

8. `crmbuilder-v2/src/crmbuilder_v2/mcp_server/tools.py` — the 44 tool functions that are reusable as native Anthropic API tool definitions. Each function already wraps `httpx → REST API at 127.0.0.1:8765`. Per DEC-245's commitment, the chat UI reuses these directly rather than re-implementing.
9. `crmbuilder-v2/src/crmbuilder_v2/api/` — the FastAPI REST surface. Understand the `{data, meta, errors}` envelope (per CLAUDE.md) and the access-layer constraints (supersession-requires-edge, conversation-membership, work-ticket single-use, etc. per the v0.7 governance entities).
10. `crmbuilder-v2/src/crmbuilder_v2/ui/` — the existing PySide6 desktop app structure. The chat tab will be a peer to the existing Governance panels.

### Tier 4 — skills to invoke during the conversation

- `/software-architect` — for the architectural design itself (component layout, data flow, state management).
- `/claude-api` — for the Anthropic SDK integration patterns. **Prompt caching is REQUIRED on all Anthropic API calls per the skill.** The chat UI's tool-definition payload + system prompt + tool call history will easily justify caching.

### Tier 5 — recent v2 methodology context

- Build-closure pattern (DEC-232 through DEC-237 from SES-074) — relevant if PI-052's implementation crosses Claude Code executor sessions. The build-closure conversation type would own the close-out for multi-slice implementation.
- Methodology document at `PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md` (current per SES-074's amendments).

---

## Goals (what the session must produce)

1. **Architecture design** for the chat tab — components, data flow, state model, threading/async, error handling. Should be detailed enough that the implementation session(s) can execute without re-deciding fundamentals.

2. **Tool surface scope decision** — does the chat tab expose all 44 MCP tools as native Anthropic API tools out of the gate, or a curated subset for MVP? If a subset, which tools are MVP-essential? (Hint: read + write surfaces for charter / status / decisions / planning items / sessions are probably the MVP core; references and the v0.7 governance entities are valuable but not strictly required for a useful first version.)

3. **Auth model for the API calls** — Anthropic API key handling. Where it's read from (env var / settings.json / system keyring / dotfile), how the chat tab refuses to run without it, what happens on 401 from Anthropic.

4. **Conversation state model** — in-memory only for v1? Persist to disk (a new SQLite table in `v2.db`? a separate JSON file?)? Are chat sessions themselves first-class governance entities that get a CRM record (parallel to SES / CONV)? **This is a methodology question, not just an implementation choice** — needs an explicit decision.

5. **Tool execution loop architecture** — read user input → `messages.create(tools=...)` → loop on `tool_use` blocks → execute via `httpx → REST API` → format `tool_result` → re-send to Anthropic → continue until no more tool calls or limit reached. Where the loop runs (PySide6 main thread? worker thread? asyncio loop?). How streaming responses (if used) integrate with Qt's event loop.

6. **Prompt caching strategy** — the system prompt + tool definitions + conversation history are all candidates. The `/claude-api` skill requires caching. Decide: what's cached at the system-prompt boundary, what at the tool-definitions boundary, what (if anything) at the conversation-history boundary.

7. **Model selection** — Opus 4.7 default for the chat UI? Sonnet 4.6 for faster turns? User-selectable in the UI? Cost/latency trade-offs.

8. **UI mockup / sketch** — even a paragraph describing the layout is enough at the design level: where the tab sits in the existing app, message list area, input area, model selector, token-usage display, tool-call visualization (show which tools were called and what they returned, or hide that and just show Claude's response text? — has implications for trust and debugging).

9. **Slicing plan** — break the build into testable slices, each end-to-end-runnable. A reasonable starting hypothesis: Slice A (proof-of-concept: ~50 LOC standalone Python script with 2-3 tools, validates the full loop end-to-end), Slice B (integrate as a PySide6 tab with one tool wired and a working chat loop), Slice C (wire all tools / refine UX / add caching), Slice D (conversation persistence if chosen). Confirm or revise this hypothesis.

10. **Open questions and decisions surfaced** — anything that needs explicit settlement before implementation. Record as DEC-NNN candidates in the close-out.

---

## Non-goals (out of scope for this session)

- Writing any of the implementation code. This session designs, the next session(s) implement.
- Re-litigating DEC-244 / DEC-245. The strategic decision is settled; this session is downstream.
- Replicating claude.ai-web feature parity (Artifacts, Projects, voice, mobile, file uploads). Out of scope for the design AND for the v1 build. Future PIs may surface, but not from this session.
- Adding a remote-access surface to the chat UI itself (web app on the existing Cloudflare Tunnel, mobile app, etc.). Out of scope. The chat UI is local-only for v1. If a future PI surfaces remote access, it can build on whatever this design produces.
- Re-enabling the shelved MCP HTTP transport / Cloudflare Managed OAuth. Those stay shelved per DEC-244.

---

## Key open questions for the session to settle

A non-exhaustive list — each likely surfaces a DEC-NNN candidate:

- **Q1.** Tool-call confirmation: does the chat tab execute tool calls (especially write-surface ones like `create_decision`, `update_planning_item`, `delete_*`) automatically, or does the UI prompt the user "Claude wants to call `create_decision` with these arguments — Allow / Deny / Edit"? Trade-off: deterministic safety + UX friction vs. flow + trust. Single-user system reduces the safety pressure, but governance writes have audit-chain implications.

- **Q2.** Read-only mode default: should the chat tab launch in a "read-only" mode where Claude can call `get_*` and `list_*` tools but not `create_*` / `update_*` / `delete_*`, with the user toggling write mode on per session or per turn?

- **Q3.** Chat session as a governance entity: are individual chat sessions first-class records (parallel to CONV)? If yes, what's the schema (`chat_session_*` entity type, persisted to `v2.db`, exposed via REST + MCP)? If no, where does the conversation history live?

- **Q4.** Tool-call results: are tool call results inlined visibly in the chat transcript (verbose but transparent), shown only on hover/expand (clean but opaque), or hidden by default with a toggle (compromise)? Affects trust and debugging.

- **Q5.** Cost visibility: token usage + estimated cost displayed per turn / per session / hidden? Doug runs against Anthropic API which is metered; cost transparency matters for everyday-use confidence.

- **Q6.** System prompt design: what does Claude get told about its role + the v2 governance methodology + the tool surface semantics? This is a substantial piece of prompt engineering and probably justifies invoking `/prompt-engineering`. The system prompt is the right boundary for prompt caching.

- **Q7.** Conversation export: should chat sessions be exportable to the V2 close-out payload pattern (i.e., a chat session that produces decisions could close out as a CONV record with embedded decisions)? Methodology question — Doug should explicitly think about whether the chat UI is a "first-class governance conversation surface" or just "a chat surface that happens to have governance tools."

- **Q8.** Multi-conversation UX: can multiple chat sessions run simultaneously (tabs within the chat tab)? Or single chat at a time, with history visible in a sidebar like Claude.ai-web? Affects UI complexity and conversation-persistence design.

- **Q9.** Streaming vs. blocking: Anthropic API supports streaming. PySide6's event loop integrates with asyncio via `qasync` or similar. Streaming gives "type-as-you-go" UX but adds threading complexity. Worth it for v1, or defer?

- **Q10.** Error recovery: what happens if a tool call fails (REST API returns 500)? If Anthropic rate-limits? If the conversation context window is exceeded? Each needs a defined behavior.

---

## Working pattern

**Mode:** ARCHITECTURE throughout. Use the eight-element consequential-decision template for Q1–Q10 (and any new questions that surface).

**Pacing:** Design conversations don't have the one-step-at-a-time discipline of terminal-execution conversations. Doug and Claude work through the questions in whatever order makes sense, with Claude proposing options + trade-offs and Doug exercising judgment. Aim to settle 4–6 of the open questions in this session; defer others to implementation-time if they're better answered by spike output.

**Surface:** Either Claude.ai-web (no MCP needed for this conversation — pure design), Claude Code at Doug's terminal, or Claude Desktop. Doug picks. Per the push convention, if Claude.ai is used, the close-out payload + apply prompt + any code artifacts get committed and pushed by Claude in the same turn (the parallel-sandbox push pattern); if Claude Code is used, Claude commits and Doug pushes.

**Skill invocation:**
- `/software-architect` early — for the overall architecture
- `/claude-api` mid-conversation — for the SDK integration patterns (and ensures prompt caching is designed in correctly)
- `/prompt-engineering` for Q6 (system prompt design) — invoked if Q6 gets deep enough

---

## Deliverable shape

Triple-artifact close-out per the established SES-046–SES-077 precedent:

1. **Design document** at `PRDs/product/crmbuilder-v2/pi-052-chat-ui-design.md` — comprehensive output of the session. Sections roughly: Architecture overview, Component breakdown, Data flow, Tool surface, State model, Auth + caching, UI layout sketch, Slicing plan, Open issues. This is the readable design artifact future implementation sessions consult.

2. **Close-out payload** at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_078.json` containing the architectural decisions (DEC-NNNs settled), references threading them into the existing audit chain, addresses/resolves edges as appropriate. Likely 4–8 new decisions across Q1–Q10.

3. **Apply prompt** at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-078.md` — for Doug or another sandbox to apply the close-out.

If the slicing plan settles cleanly, **also**:

4. **Work-ticket(s)** for each slice — either inline in the V2 DB (the WT-046 dogfooding pattern) or as markdown files under `PRDs/product/crmbuilder-v2/`. Slice 1's WT should be detailed enough that the first implementation session can run without re-design.

---

## Folding into PI-052

This session does not resolve PI-052 — it scopes and plans it. PI-052 stays Open with `is_about` edges from SES-078 (and the future SES records that own each slice). PI-052 resolves when the chat UI ships as a working v1 — the last slice's build-closure conversation flips PI-052 to Resolved via the standard `resolves_planning_items` mechanism.

The methodology continues to be tested here: this design session is a normal Claude.ai-or-Claude-Code conversation, the implementation sessions are normal Claude Code conversations, and the close-out for each is the build-closure-conversation pattern from SES-074 / DEC-232.

---

## Identifier note

Anticipates SES-078, DEC-246+, and probably PI-053+ for any new planning items surfaced (e.g., conversation-persistence-as-governance-entity if Q3 lands that way). Verify identifier heads with `list_recent_sessions` and the equivalent for decisions / PIs at conversation open. Parallel-sandbox identifier collisions remain possible — the recent SES-077 close-out illustrates rebasing pattern.

---

## Lesson the session should keep in view

DEC-244 surfaced *"Goals get framed as the infrastructure that would deliver them. Verify the integrating client's full auth flow end-to-end before committing to weeks of server-side work that depends on it."* That lesson applies here too: **verify that the Anthropic SDK + native tools approach really works end-to-end with at least one v2 tool before designing the production UI on top of it.** A 30-minute spike (Slice A) BEFORE the design conversation finalizes could prevent a class of design errors that only surface in execution. Optional: run the spike as part of this design session if Doug has the cycles, or as the first action item afterwards.

---

## One open methodology question for the session

The kickoff body could have lived inline in a new WT-047 in the V2 DB rather than as this markdown file (the v0.7 dogfooding pattern WT-046 used). The choice between file-kickoff and WT-inline-kickoff is itself a methodology decision — Doug should consider, and the session might surface this as a DEC-NNN if it warrants explicit settlement. For PI-052 today, this file is the kickoff; future PI-052 slice kickoffs may go either way.
