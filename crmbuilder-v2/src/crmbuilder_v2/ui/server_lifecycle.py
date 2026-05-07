"""Detect-then-launch lifecycle for the storage API subprocess.

Wired in slice B. Per DEC-023, on startup the UI probes
``GET /health``; if no response, spawns ``crmbuilder-v2-api`` via
``QProcess`` and waits for readiness. Tracks ownership ("external" /
"owned") so it terminates only subprocesses it spawned itself.
"""
