"""Cross-cutting startup-and-routing concerns for crmbuilder_v2.

The ``runtime`` package captures engagement-routing logic that does not
belong in ``access/``, ``api/``, or ``migration/``: resolving the active
engagement marker, routing ``Settings`` to a per-engagement DB and
export directory, and the export-write gate. Modules import directly
(no package-level re-exports).
"""
