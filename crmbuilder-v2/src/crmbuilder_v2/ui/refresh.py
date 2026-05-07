"""File-watch refresh service.

Wired in slice F. Per DEC-022, a ``QFileSystemWatcher`` watches the
``CRMBUILDER_V2_EXPORT_DIR`` directory and emits a per-entity-type
``data_changed`` signal when a snapshot file changes. Manual Refresh
buttons on every panel act as a fallback.
"""
