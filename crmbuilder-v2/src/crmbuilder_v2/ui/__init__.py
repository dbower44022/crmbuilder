"""CRMBuilder v2 desktop UI.

A standalone PySide6 application that consumes the v2 storage system
through its REST API. See `ui-PRD-v0.1.md` for requirements and
`ui-implementation-plan.md` for the slice breakdown.

DEC-018 — UI is a standalone application, not embedded in the v1 PySide6 app.
DEC-019 — UI consumes the REST API over HTTP, not the access layer directly.
DEC-020 — v0.1 scope: read-only across all entities, full CRUD for decisions only.
DEC-021 — Sidebar navigation with master/detail panes.
DEC-022 — File-watch on db-export/ for live refresh, manual Refresh button as fallback.
DEC-023 — Detect-then-launch API subprocess management.
DEC-024 — Native Qt look for v0.1; styling pass deferred.
"""
