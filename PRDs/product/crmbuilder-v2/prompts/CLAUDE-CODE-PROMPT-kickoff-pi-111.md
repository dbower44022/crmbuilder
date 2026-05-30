# Kickoff — PI-111: /health heartbeat for proactive API-death detection

> **Anchored after the fact (2026-05-30).** PI-111 was filed in the SES-125
> close-out as the deferred follow-on to PI-110 / DEC-333 (the scope option not
> chosen at the time), then implemented in a later Claude Code session that
> authored this kickoff. This document is the kickoff record so the work has the
> standard `planning_item` → `work_ticket` (kickoff_prompt) → session trail.
> Work shipped in commit `01c948d`, resolved by SES-130 / CNV-032. Work ticket:
> **WT-062**, `addresses` PI-111.

## Planning item

**PI-111 — Optional `/health` heartbeat so the UI proactively detects an
external API's death.**

PI-110 made an API drop self-healing *reactively*: the UI auto-restarts on a
panel `connection_lost`. The remaining gap is an API the UI does not own (an
externally-launched `crmbuilder-v2-api`) that dies while the user is idle — the
UI doesn't notice until the next request fails. This PI closes that window.

## Goal

Detect an external API's death between user actions and auto-restart before the
next click fails, reusing the PI-110 recovery path.

## Scope delivered

1. `StorageClient.health()` — `GET /health`, returns the payload on success and
   raises `StorageConnectionError` when unreachable (the heartbeat's signal).
2. `MainWindow` heartbeat: a `QTimer` (`_HEARTBEAT_INTERVAL_MS = 15000`) that,
   while ready, probes `/health` off the GUI thread (`run_in_thread`). On a
   `StorageConnectionError` it calls `_begin_auto_reconnect` (the PI-110 bounded
   probe-then-spawn path). The timer starts on first ready, pauses during a
   reconnect cycle, and resumes on the next ready; a single probe is in flight at
   a time; non-connection errors are ignored (not a death signal).
3. Tests — 6 cases added to `tests/crmbuilder_v2/ui/test_auto_reconnect.py`
   (timer lifecycle, connection-failure restart, non-connection ignore,
   ignore-while-reconnecting, ok-clears-in-flight, tick guards).

## Acceptance

- An external API dying while the UI is idle is detected within the heartbeat
  interval and auto-restarted via the existing recovery path; non-connection
  errors don't trigger a restart; one probe at a time. Full v2 UI suite green.

## Resolution

Implemented in commit `01c948d`; resolved by **SES-130 / CNV-032** (close-out
`ses_130.json`). Completes the API-resilience arc started by PI-110 / DEC-333.
