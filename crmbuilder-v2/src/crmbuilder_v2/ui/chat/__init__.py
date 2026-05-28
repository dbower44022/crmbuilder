"""Chat UI subpackage (PI-052).

Slice B (WT-055) builds the MVP chat tab: one tool wired, streaming on,
in-memory only. The package is organized per the design doc
``pi-052-chat-ui-design.md`` §2:

* :mod:`session` — the in-memory ``ChatSession`` dataclass.
* :mod:`tools` — the tool dispatcher (one tool in Slice B).
* :mod:`worker` — ``ChatWorker``, a ``QThread`` hosting a private
  asyncio loop that drives ``AsyncAnthropic.messages.stream()``.
* :mod:`controller` — ``ChatController``, the main-thread bridge that
  owns the session and the worker.
* :mod:`widgets` — transcript bubble / tool-disclosure widgets.
* :mod:`auth` — API-key bootstrap (env → keyring → modal dialog).

Persistence, the full 44-tool surface, prompt caching, the
multi-conversation sidebar, and the mode/model picker logic all land in
Slice C.
"""

from __future__ import annotations
