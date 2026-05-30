# Kickoff — PI-110: Harden the v2 API lifecycle (rotating logs + UI auto-restart)

> **Anchored after the fact (2026-05-30).** PI-110 was picked up reactively from
> a bug report (a Work Tickets panel failed to display, console showed
> `[Errno 111] Connection refused`) and implemented in the same Claude Code
> session that authored this kickoff. This document is the kickoff record so the
> work has the standard `planning_item` → `work_ticket` (kickoff_prompt) →
> session trail. Work shipped in commit `9f8ec27` (PR #3, merged `07b9313`),
> resolved by SES-125 / CNV-027. Work ticket: **WT-061**, `addresses` PI-110.

## Planning item

**PI-110 — Harden the v2 API process lifecycle so an API outage is both
diagnosable and self-healing.**

The trigger: an externally-launched, detached `crmbuilder-v2-api` (reparented to
`systemd --user`) died with **no captured logs**, and the desktop UI — which
only crash-monitors API subprocesses it spawns itself — discovered the death
only reactively, when a panel click issued an HTTP request and got
`Connection refused`. Two structural gaps: (1) no persistent API logs, so the
cause of death was unrecoverable; (2) no automatic recovery — the UI sat
disabled behind a generic banner until a manual Reconnect click.

## Goal

Make an API drop **diagnosable** (durable rotating logs) and **self-resolving**
(the UI auto-restarts the API), with informative operator-facing reporting.

## Scope delivered

1. **Rotating API logs** at `crmbuilder-v2/data/logs/api.log` (`config.api_log_path()`,
   gitignored). `cli._build_api_log_config()` deep-copies uvicorn's
   `LOGGING_CONFIG`, adds a `RotatingFileHandler` (2 MB × 5) on the root and
   `uvicorn`/`uvicorn.access` loggers, and passes it as `uvicorn.run(..., log_config=...)`.
   Built just before `uvicorn.run`, so `--check-only` / fail-loud stay
   side-effect-free. Captures app logs, startup tracebacks, and access logs for
   both standalone and UI-spawned launches.
2. **UI auto-restart** in `MainWindow`: a panel `connection_lost` or an owned
   subprocess `crashed` drives `ServerLifecycle.start()` up to
   `_MAX_RECONNECT_ATTEMPTS` (3), then falls back to a manual-Reconnect banner.
   Banners are specific (URL, attempt count, log path, standalone-launch hint);
   overlapping triggers dedupe; a runtime spawn failure (post first-ready, gated
   on `had_first_ready()`) routes to the in-window banner via `app.py` instead
   of the fatal startup dialog, so a failed reconnect never kills a live session.
3. **Tests** — `tests/crmbuilder_v2/ui/test_auto_reconnect.py` (7 cases: retry
   bound, dedupe, exhaustion, manual reset, crash path, `had_first_ready` gate).

## Acceptance

- A real API run writes startup + access + shutdown lines to `data/logs/api.log`;
  `--check-only` creates no log file. The UI recovers from an API drop without a
  manual click and shows actionable messaging on failure. Full v2 UI + CLI
  suites green (818 pass); changed files lint clean.

## Resolution

Implemented in commit `9f8ec27` (merged via PR #3 as `07b9313`); resolved by
**SES-125 / CNV-027** (close-out `ses_125.json`).

## Deferred follow-on

**PI-111** — optional periodic `/health` heartbeat so the UI proactively detects
an *external* API's death (between requests) and auto-relaunches before the next
click fails. Surfaced and deferred during this session's scope decision
(DEC-333, option not chosen).
