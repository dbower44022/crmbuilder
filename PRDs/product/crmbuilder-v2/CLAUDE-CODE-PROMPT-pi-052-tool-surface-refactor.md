# Claude Code Prompt — PI-052 Slice C early: extract tool surface, rewire chat spike

**Created:** 05-30-26 05:40
**Repo:** `dbower44022/crmbuilder`
**Operating mode for execution:** DETAIL. Surgical edits, behavior preservation, tests must stay green.

**Anchors:**
- In-app chat assistant work item (PI-052)
- The claude.ai connector bug (DEC-244)
- The architectural pivot away from the connector (DEC-245)
- The PySide6 tab on the Anthropic SDK (DEC-252)
- All tools registered out of the gate, no MVP subset (DEC-253)
- The four-slice build plan (DEC-261); this prompt pulls forward the Slice C tool-surface refactor specified in Appendix A of the design document

---

## 1. Context and net effect

The CRMBuilder Integrated AI (the in-app chat assistant tracked under PI-052) is currently the Slice A terminal spike at `crmbuilder-v2/scripts/chat_spike.py`. The spike hand-wires three read tools (current status, current charter, recent sessions) and is correctly labeled throwaway scaffolding. The user needs the spike to expose the full read tool surface today, but extending the spike with more hand-wired tools is throwaway work the eventual chat tab discards.

The PI-052 design document (`PRDs/product/crmbuilder-v2/pi-052-chat-ui-design.md`, §6.4 and Appendix A) already specifies a load-bearing refactor: extract the closure-pattern tool surface in `crmbuilder-v2/src/crmbuilder_v2/mcp_server/tools.py` into a shared registry that both the MCP server and the chat dispatcher consume. That refactor is scheduled for Slice C. This prompt pulls it forward so the Slice A spike gains the full read tool surface immediately, and Slice B / Slice C reuse the same registry instead of re-implementing it later.

**Net effect after this prompt runs:**

- New module `crmbuilder_v2.mcp_server.tool_definitions` exposing a `ToolDefinition` dataclass and a `tool_definitions(http)` factory.
- New module `crmbuilder_v2.mcp_server.tool_schemas` exposing `schema_from_signature(callable) -> dict` for generating Anthropic-API `input_schema` blocks.
- `crmbuilder_v2.mcp_server.tools.register_tools` becomes a thin loop over the new factory; no externally observable behavior change for the MCP stdio server.
- `crmbuilder-v2/scripts/chat_spike.py` rewritten async, building its `tools=[...]` block from the new factory filtered to read tools only, dispatching by name lookup.
- The existing MCP test suite passes unchanged. New tests cover the factory partition and the schema generator.

---

## 2. Stop-and-ask gate (run before any edits)

Verify each premise against the live repo. If any check fails, **stop and report** rather than editing.

1. **Tool surface file.** `crmbuilder-v2/src/crmbuilder_v2/mcp_server/tools.py` defines `register_tools(server: FastMCP, http: httpx.AsyncClient) -> None` and contains a sequence of nested `async def` tool functions each decorated with `@server.tool()` (closure-style). Confirm the structure matches; **report the exact tool count**.
2. **MCP tests in place.** All three of these test files exist:
   - `tests/crmbuilder_v2/mcp_server/test_smoke.py`
   - `tests/crmbuilder_v2/mcp_server/test_catalog_tools.py`
   - `tests/crmbuilder_v2/mcp_server/test_transport_dispatch.py`
   Run `pytest tests/crmbuilder_v2/mcp_server/ -v` and **report the count of passing tests** as a baseline. Stop if anything is red pre-refactor.
3. **Spike present and shape correct.** `crmbuilder-v2/scripts/chat_spike.py` exists, uses synchronous `anthropic.Anthropic` + `httpx.Client`, and has a hand-coded `dispatch()` switch over three tools (current status, current charter, recent sessions). Confirm.
4. **Design anchor.** `PRDs/product/crmbuilder-v2/pi-052-chat-ui-design.md` Appendix A specifies the `ToolDefinition` shape and the `tool_definitions(http)` factory pattern. Confirm by quoting one line from Appendix A's "After" code block.

If all four check out, proceed to step 3. Otherwise stop and report which premise broke.

---

## 3. New module — `crmbuilder-v2/src/crmbuilder_v2/mcp_server/tool_definitions.py`

Create the file with the structure below. The skeleton shows the dataclass, the helpers, and the first two tool definitions; **populate the rest by copying every nested `async def` from the current `register_tools` in `mcp_server/tools.py` in the same source order**, then building the `ToolDefinition` list in the same order. Preserve docstrings verbatim.

```python
"""Shared tool surface.

The MCP server (:mod:`crmbuilder_v2.mcp_server.tools`) and the in-app
chat dispatcher (``scripts/chat_spike.py`` today; ``ui/chat/tools.py``
in Slice B/C) both consume the same ``tool_definitions(http)`` factory
so the tool surface never diverges between transports. Per PI-052
Appendix A.

Each tool is a coroutine closure over the supplied
:class:`httpx.AsyncClient` and wraps a single REST endpoint. The MCP
layer holds no business logic; validation, vocabulary checks, and
state lookups all happen in the access layer behind the REST API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import httpx


@dataclass(frozen=True)
class ToolDefinition:
    """One callable governance tool plus the metadata transports need."""

    name: str
    callable: Callable[..., Any]
    description: str
    is_write: bool


_WRITE_PREFIXES: tuple[str, ...] = (
    "create_",
    "update_",
    "delete_",
    "add_",
    "replace_",
)


def _is_write(name: str) -> bool:
    return any(name.startswith(p) for p in _WRITE_PREFIXES)


async def _unwrap(response: httpx.Response) -> Any:
    """Pull the envelope's ``data`` field, or raise on error envelopes."""
    response.raise_for_status()
    body = response.json()
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body.get("data")


def _description(callable_: Callable[..., Any]) -> str:
    """First-paragraph docstring, stripped; empty string if no docstring."""
    doc = (callable_.__doc__ or "").strip()
    return doc.split("\n\n", 1)[0].strip()


def tool_definitions(http: httpx.AsyncClient) -> list[ToolDefinition]:
    """Return every governance tool bound to the given async HTTP client.

    Each callable is an async closure over ``http``. The list ordering
    is stable and matches the original ``tools.py`` registration order,
    so tests that key off ordering keep working.
    """

    # ---------- Charter ----------

    async def get_current_charter() -> Any:
        """Return the current charter document (singleton, latest version)."""
        return await _unwrap(await http.get("/charter"))

    async def get_charter_version(version: int) -> Any:
        """Return a specific historical charter version."""
        return await _unwrap(await http.get(f"/charter/versions/{version}"))

    # ... [copy every remaining nested async def from the current
    #     register_tools(), in source order, verbatim — including its
    #     docstring. Do not change body logic.] ...

    return [
        ToolDefinition(
            name="get_current_charter",
            callable=get_current_charter,
            description=_description(get_current_charter),
            is_write=_is_write("get_current_charter"),
        ),
        ToolDefinition(
            name="get_charter_version",
            callable=get_charter_version,
            description=_description(get_charter_version),
            is_write=_is_write("get_charter_version"),
        ),
        # ... [one ToolDefinition entry per copied function, same order
        #     as the function definitions above] ...
    ]
```

**Filling in the body — explicit instructions:**

- Open `mcp_server/tools.py` and copy every nested `async def` inside `register_tools` into `tool_definitions` in the same order they appear today.
- Remove the `@server.tool()` decorator from each (the decorator is applied later, in `tools.py`).
- Preserve every docstring verbatim.
- After all function definitions, build the returned list with one `ToolDefinition` per function, **in the same order**, populating `name` (string literal matching the function name), `callable` (the function reference), `description` (via `_description(...)`), and `is_write` (via `_is_write("<name>")`).
- Move the `_unwrap` helper from `tools.py` into this module (the version above). Remove it from `tools.py`.
- Do **not** add new logic, new tools, or change any URL path. This is a mechanical move.

---

## 4. New module — `crmbuilder-v2/src/crmbuilder_v2/mcp_server/tool_schemas.py`

```python
"""JSONSchema generator for Anthropic-API ``tools=[...]`` blocks.

Given a coroutine callable from :mod:`tool_definitions`, return the
``{name, description, input_schema}`` dict the Anthropic Messages API
expects. Per PI-052 design §2.4.

Best-effort schema generation tuned for the read-tool signatures
the Slice A spike consumes (zero-arg, single typed identifier, single
optional with default). The write-tool surface uses richer payload
shapes; richer generation lands with Slice B when those tools start
flowing through the dispatcher.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, get_args, get_origin

_JSON_TYPE: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    dict: "object",
    list: "array",
}


def _python_type_to_json(annotation: Any) -> tuple[str, bool]:
    """Map a Python annotation to ``(json_type, nullable)``.

    Handles ``str | None`` style unions and bare types. Unknown
    annotations fall back to ``"string"`` so generation never fails;
    correctness here is best-effort and will be tightened with Slice B.
    """
    if annotation is inspect.Parameter.empty:
        return "string", False
    origin = get_origin(annotation)
    if origin is None:
        return _JSON_TYPE.get(annotation, "string"), False
    args = get_args(annotation)
    nullable = type(None) in args
    non_none = [a for a in args if a is not type(None)]
    if len(non_none) == 1:
        return _JSON_TYPE.get(non_none[0], "string"), nullable
    return "string", nullable


def schema_from_signature(callable_: Callable[..., Any]) -> dict[str, Any]:
    """Return the Anthropic-API ``input_schema`` dict for ``callable_``."""
    sig = inspect.signature(callable_)
    properties: dict[str, dict[str, Any]] = {}
    required: list[str] = []
    for name, param in sig.parameters.items():
        json_type, nullable = _python_type_to_json(param.annotation)
        prop: dict[str, Any] = {"type": json_type}
        if nullable:
            prop["type"] = [json_type, "null"]
        if param.default is inspect.Parameter.empty:
            required.append(name)
        else:
            prop["default"] = param.default
        properties[name] = prop
    return {"type": "object", "properties": properties, "required": required}
```

---

## 5. Rewrite — `crmbuilder-v2/src/crmbuilder_v2/mcp_server/tools.py`

After the refactor, this file is the small loop below. Replace the **entire** existing file contents with:

```python
"""MCP tool registration.

Thin loop over the shared tool surface defined in
:mod:`crmbuilder_v2.mcp_server.tool_definitions`. The actual tool
bodies, docstrings, and ``is_write`` partition live there; this file
exists only to bind the surface to a FastMCP server instance.
"""

from __future__ import annotations

import httpx
from mcp.server.fastmcp import FastMCP

from crmbuilder_v2.mcp_server.tool_definitions import tool_definitions


def register_tools(server: FastMCP, http: httpx.AsyncClient) -> None:
    """Register every tool from :func:`tool_definitions` on ``server``."""
    for td in tool_definitions(http):
        server.tool(name=td.name, description=td.description)(td.callable)
```

That is the whole file. Everything else moved to `tool_definitions.py`.

---

## 6. Rewrite — `crmbuilder-v2/scripts/chat_spike.py`

Replace the entire spike with the async version below. It consumes the shared registry, filters to read tools, and dispatches by name lookup.

```python
"""PI-052 Slice A terminal proof-of-concept (now consuming the shared
tool surface from :mod:`crmbuilder_v2.mcp_server.tool_definitions` —
PI-052 Appendix A refactor pulled forward).

Async blocking chat loop against the Anthropic API with the full
read-only governance tool surface dispatched against the local REST
API at 127.0.0.1:8765. Still throwaway scaffolding; Slice B is the
first slice with production UI code.
"""

from __future__ import annotations

import asyncio
import os
import sys

import anthropic
import httpx

from crmbuilder_v2.mcp_server.tool_definitions import tool_definitions
from crmbuilder_v2.mcp_server.tool_schemas import schema_from_signature

API_BASE = "http://127.0.0.1:8765"
MODEL = "claude-opus-4-7"
SYSTEM = (
    "You are an assistant with read-only access to the crmbuilder v2 "
    "governance database via tools that wrap the REST API. Call them "
    "when the user asks about project state, decisions, sessions, "
    "planning items, references, the charter, risks, topics, or the "
    "catalog. Answer concisely from tool results. Cite identifiers "
    "with the human-readable name first followed by the code in "
    "parentheses (for example, 'Client Intake (MN-INTAKE)')."
)


async def _read_line(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


async def _run() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1
    client = anthropic.AsyncAnthropic()
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as http:
        defs = {
            td.name: td
            for td in tool_definitions(http)
            if not td.is_write
        }
        tools_block = [
            {
                "name": td.name,
                "description": td.description,
                "input_schema": schema_from_signature(td.callable),
            }
            for td in defs.values()
        ]
        messages: list[dict] = []
        while True:
            try:
                user = (await _read_line("> ")).strip()
            except EOFError:
                print()
                return 0
            if not user:
                continue
            messages.append({"role": "user", "content": user})
            while True:
                response = await client.messages.create(
                    model=MODEL,
                    system=SYSTEM,
                    tools=tools_block,
                    messages=messages,
                    max_tokens=8192,
                )
                messages.append(
                    {"role": "assistant", "content": response.content}
                )
                if response.stop_reason != "tool_use":
                    text = "".join(
                        b.text
                        for b in response.content
                        if b.type == "text"
                    )
                    print(text)
                    break
                tool_results: list[dict] = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    print(
                        f"→ {block.name}({dict(block.input)})",
                        file=sys.stderr,
                    )
                    try:
                        td = defs[block.name]
                        result = await td.callable(**dict(block.input))
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": repr(result),
                            }
                        )
                    except KeyError:
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": f"unknown tool: {block.name}",
                                "is_error": True,
                            }
                        )
                    except Exception as exc:  # noqa: BLE001
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": f"error: {exc}",
                                "is_error": True,
                            }
                        )
                messages.append({"role": "user", "content": tool_results})


def main() -> int:
    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

The spike now requires the package to be importable; run it from the repo root with the project installed editable (`pip install -e .`).

---

## 7. Tests

### 7.1 Keep the existing MCP suite green

Before any edits, capture the baseline:

```
pytest tests/crmbuilder_v2/mcp_server/ -v
```

After every edit step, re-run it. All tests must still pass with no behavior change. If any test asserts the internal closure structure of `register_tools` directly (rather than externally observable behavior such as registered tool names), update that test minimally to assert against `tool_definitions` output — but only if it actually fails; do not pre-emptively edit passing tests.

### 7.2 New file — `tests/crmbuilder_v2/mcp_server/test_tool_definitions.py`

Cover:

- Calling `tool_definitions(http)` with a stub `httpx.AsyncClient` returns a non-empty `list[ToolDefinition]`.
- Every entry has a non-empty `name`, a callable `callable`, and a non-empty `description`.
- No two definitions share a name.
- The list length equals the tool count reported in step 2 of the stop-and-ask gate. (Use that count as the expected value; do not hardcode a lower estimate.)
- The read/write partition matches the name-prefix rule for a representative subset. Assert each of the following expectations explicitly:
  - `get_current_status` → `is_write=False`
  - `list_decisions` → `is_write=False`
  - `list_references_touching` → `is_write=False`
  - `catalog_search` → `is_write=False`
  - `create_decision` → `is_write=True`
  - `update_session` → `is_write=True`
  - `delete_topic` → `is_write=True`
  - `add_reference` → `is_write=True`
  - `replace_status` → `is_write=True`

A reasonable stub for the `httpx.AsyncClient` parameter is `httpx.AsyncClient(base_url="http://test")` — the factory only closes over the client; it does not make calls at definition time.

### 7.3 New file — `tests/crmbuilder_v2/mcp_server/test_tool_schemas.py`

Cover `schema_from_signature` against three representative hand-defined callables inside the test module:

- **Zero-arg.** `async def f() -> typing.Any: ...` → returns `{"type": "object", "properties": {}, "required": []}`.
- **Required string.** `async def f(identifier: str) -> typing.Any: ...` → `properties["identifier"]["type"] == "string"` and `required == ["identifier"]`.
- **Optional int with default.** `async def f(limit: int = 3) -> typing.Any: ...` → `properties["limit"]["type"] == "integer"`, `properties["limit"]["default"] == 3`, `required == []`.

---

## 8. Verification (after tests are green)

Run these manual checks; capture the output for the done block.

1. Start the REST API in one terminal: `crmbuilder-v2-api`.
2. Start the MCP stdio server in another: `crmbuilder-v2-mcp`. Confirm it boots without error and serves the same tool list as before the refactor.
3. **Parity check.** Compare:
   - the count and names returned by `tool_definitions(http)`
   - the count and names the stdio MCP server advertises (use the FastMCP introspection path or a stdio probe)
   These must match exactly.
4. **Spike smoke.** With `ANTHROPIC_API_KEY` set and the API running, run `python crmbuilder-v2/scripts/chat_spike.py`. At the prompt, ask: `What does PI-027 say?`. Confirm the stderr shows a `→ get_planning_item({...})` line and that the assistant returns a coherent answer based on the tool result. Exit with Ctrl-D.

If any step fails, stop and report. Do not commit.

---

## 9. Commit

Single commit covering all of the above. Message:

```
v2: PI-052 Slice C early — extract tool surface to mcp_server.tool_definitions; rewire chat_spike to use the shared registry
```

Do **not** push. Per repo working conventions, the user pushes from their local clone.

---

## 10. Done block — reply with

- **Files added** (paths).
- **Files modified** (paths).
- **Pre-refactor MCP test count** (from step 2 of the gate) and **post-refactor MCP test count** (after rerun) — both must match, both green.
- **New test count** (`test_tool_definitions.py` + `test_tool_schemas.py`).
- **Total test run** at repo level: `pytest -q` summary line.
- **Tool count parity**: integer reported by `len(tool_definitions(stub_http))` vs. integer advertised by the stdio MCP server. They must match.
- **Spike run transcript** — one-line transcript showing the spike calling `get_planning_item("PI-027")` successfully against the live API.
- **Next action** — the user opens a Claude.ai planning conversation against `PRDs/product/crmbuilder-v2/pi-052-slice-b-pyside6-tab-mvp-kickoff.md` to begin Slice B (the PySide6 chat-tab MVP) on top of the now-extracted tool surface.
