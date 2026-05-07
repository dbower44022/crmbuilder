"""Liveness probe.

Pure liveness check — no database access, no readonly_session. The UI's
detect-then-launch lifecycle (per DEC-023) probes this endpoint to decide
whether to spawn its own ``crmbuilder-v2-api`` subprocess.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.api.envelope import ok

router = APIRouter(prefix="/health", tags=["meta"])


@router.get("")
def get_health():
    return ok({"ok": True})
