"""GET-only design client for the EspoCRM adapter (design §10).

Mirrors the established renderer shape
(``render/baseline_report.py::RestRenderClient``): a read-only client
protocol the impure fetch path drives, plus a REST implementation that
sends the ``X-Engagement`` header (PI-β) and unwraps the
``{data, meta, errors}`` envelope. The client never constructs a
write-capable surface — the read-only invariant is structural.

The three reads are exactly the design-record inputs the adapter
consumes: ``/entities`` (with intrinsic neutral attributes),
``/fields`` (with embedded ``field_options``, each annotated with its
``parent_entity_identifier`` resolved from the
``field_belongs_to_entity`` edge), and ``/engine-overrides`` (the sparse
per-engine override layer).
"""

from __future__ import annotations

import json
from urllib import error as urllib_error
from urllib import request as urllib_request


class DesignClient:
    """GET-only client protocol the adapter's fetch path drives.

    Defines no mutating method — the read-only invariant is structural.
    :class:`RestDesignClient` is the production implementation; tests
    supply an access-layer-backed fake.
    """

    def list_entities(self) -> list[dict]:
        raise NotImplementedError

    def list_fields(self) -> list[dict]:
        """Field records each carrying ``field_options`` (embedded) and
        ``parent_entity_identifier`` (from the parent edge)."""
        raise NotImplementedError

    def list_engine_overrides(self) -> list[dict]:
        raise NotImplementedError

    def list_associations(self) -> list[dict]:
        """Association records — the ``relationships:`` block source."""
        raise NotImplementedError

    def list_rules(self) -> list[dict]:
        """Field/entity rule records carrying a neutral condition AST."""
        raise NotImplementedError


class RestDesignClient(DesignClient):
    """REST client of the live V2 API — GET requests only.

    Every request sends the ``X-Engagement`` header and unwraps the
    ``{data, meta, errors}`` envelope; a non-2xx body (which may bypass
    the envelope, see ``api/errors.py``) is surfaced verbatim in the
    raised error.
    """

    def __init__(
        self, base_url: str = "http://127.0.0.1:8765", engagement: str | None = None
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.engagement = engagement

    def _get(self, path: str):
        url = f"{self.base_url}{path}"
        req = urllib_request.Request(url, method="GET")
        if self.engagement:
            req.add_header("X-Engagement", self.engagement)
        try:
            with urllib_request.urlopen(req) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            raise RuntimeError(
                f"GET {path} -> HTTP {exc.code}: "
                f"{exc.read().decode('utf-8', errors='replace')}"
            ) from exc
        if payload.get("errors"):
            raise RuntimeError(f"GET {path} -> errors: {payload['errors']}")
        return payload["data"]

    def list_entities(self) -> list[dict]:
        return self._get("/entities")

    def list_fields(self) -> list[dict]:
        fields = self._get("/fields")
        refs = self._get(
            "/references?source_type=field"
            "&relationship_kind=field_belongs_to_entity"
        )
        parent_by_field = {
            r["source_id"]: r["target_id"]
            for r in refs
            if r.get("relationship_kind") == "field_belongs_to_entity"
        }
        for row in fields:
            row["parent_entity_identifier"] = parent_by_field.get(
                row["field_identifier"]
            )
        return fields

    def list_engine_overrides(self) -> list[dict]:
        return self._get("/engine-overrides")

    def list_associations(self) -> list[dict]:
        return self._get("/associations")

    def list_rules(self) -> list[dict]:
        return self._get("/rules")
