"""Response-envelope helpers.

Every endpoint returns ``{"data": ..., "meta": ..., "errors": ...}``.
"""

from __future__ import annotations

from typing import Any


def ok(data: Any, **meta) -> dict:
    return {"data": data, "meta": meta, "errors": None}


def err(errors: list[dict], **meta) -> dict:
    return {"data": None, "meta": meta, "errors": errors}
