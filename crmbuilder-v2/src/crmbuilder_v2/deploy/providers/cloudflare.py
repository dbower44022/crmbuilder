"""Cloudflare API v4 client — PI-419 (REQ-522).

Zone listing for the wizard and A-record upsert for the runner. Records are
created **DNS-only** (``proxied: false``): a proxied record breaks both the
Let's Encrypt challenge the installer runs and direct SSH to the server
(GVR-182). The upsert is idempotent — an existing record for the name is
updated rather than duplicated — so a resumed run does not create a second one.
"""

from __future__ import annotations

from typing import Any

import requests

from crmbuilder_v2.deploy.providers._http import JsonApi

PROVIDER = "cloudflare"
BASE_URL = "https://api.cloudflare.com/client/v4"
#: Short TTL so a re-provisioned server is reachable quickly.
DEFAULT_TTL = 60


class CloudflareClient:
    """Bearer-token client over :data:`BASE_URL` (an API token, not a global key).

    :param token: An API token with ``Zone.Zone:Read`` + ``Zone.DNS:Edit``.
    :param session: Injectable ``requests.Session`` for tests.
    """

    def __init__(
        self,
        token: str,
        *,
        session: requests.Session | None = None,
        base_url: str = BASE_URL,
        timeout: int = 30,
    ) -> None:
        self._api = JsonApi(PROVIDER, base_url, token, session=session, timeout=timeout)

    def verify_token(self) -> dict[str, Any]:
        """``GET /user/tokens/verify`` — proves the token is active."""
        return self._api.request("GET", "/user/tokens/verify").get("result", {})

    def list_zones(self) -> list[dict[str, Any]]:
        """Zones the token can see, as ``{id, name}``."""
        body = self._api.request(
            "GET", "/zones", params={"per_page": 50, "status": "active"}
        )
        return [{"id": z["id"], "name": z["name"]} for z in body.get("result", [])]

    def get_zone(self, zone_id: str) -> dict[str, Any]:
        """``GET /zones/{id}`` as ``{id, name}``."""
        z = self._api.request("GET", f"/zones/{zone_id}").get("result", {})
        return {"id": z.get("id"), "name": z.get("name")}

    def find_a_record(self, zone_id: str, name: str) -> dict[str, Any] | None:
        """The A record for ``name`` in the zone, or ``None``."""
        body = self._api.request(
            "GET",
            f"/zones/{zone_id}/dns_records",
            params={"type": "A", "name": name, "per_page": 10},
        )
        records = body.get("result", [])
        return _summarize(records[0]) if records else None

    def upsert_a_record(
        self,
        zone_id: str,
        *,
        name: str,
        ip: str,
        ttl: int = DEFAULT_TTL,
        proxied: bool = False,
    ) -> dict[str, Any]:
        """Create or update the A record ``name -> ip``; returns its summary.

        ``proxied`` defaults to ``False`` and callers provisioning a CRM must
        leave it there (GVR-182).
        """
        payload = {"type": "A", "name": name, "content": ip, "ttl": ttl, "proxied": proxied}
        existing = self.find_a_record(zone_id, name)
        if existing is None:
            body = self._api.request(
                "POST", f"/zones/{zone_id}/dns_records", json=payload
            )
            return _summarize(body.get("result", {}))
        if (
            existing["content"] == ip
            and existing["proxied"] == proxied
            and existing.get("ttl") == ttl
        ):
            return existing
        body = self._api.request(
            "PATCH", f"/zones/{zone_id}/dns_records/{existing['id']}", json=payload
        )
        return _summarize(body.get("result", {}))


def _summarize(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("id"),
        "name": record.get("name"),
        "type": record.get("type"),
        "content": record.get("content"),
        "ttl": record.get("ttl"),
        "proxied": bool(record.get("proxied", False)),
    }
