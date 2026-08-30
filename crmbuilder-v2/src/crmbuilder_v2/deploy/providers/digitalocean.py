"""DigitalOcean API v2 client — PI-419 (REQ-522).

Only the calls the deploy runner and the wizard need: catalog reads for the
wizard (regions, sizes, images, account SSH keys), droplet create / read /
find-by-tag, and account-key registration for the run's generated SSH key.
Droplets are tagged with the deploy run identifier so a crashed run can find
the server it already created instead of creating a second one.
"""

from __future__ import annotations

from typing import Any

import requests

from crmbuilder_v2.deploy.errors import ProviderError
from crmbuilder_v2.deploy.providers._http import JsonApi

PROVIDER = "digitalocean"
BASE_URL = "https://api.digitalocean.com/v2"
#: Every droplet CRMBuilder creates carries this tag as well as its run tag.
CRMBUILDER_TAG = "crmbuilder"


class DigitalOceanClient:
    """Bearer-token client over :data:`BASE_URL`.

    :param token: A personal access token with read + write scope.
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

    # -- account / catalog ----------------------------------------------------

    def verify_token(self) -> dict[str, Any]:
        """``GET /account`` — proves the token works; returns the account block."""
        return self._api.request("GET", "/account").get("account", {})

    def list_regions(self) -> list[dict[str, Any]]:
        """Available regions as ``{slug, name}``."""
        body = self._api.request("GET", "/regions", params={"per_page": 200})
        return [
            {"slug": r["slug"], "name": r.get("name", r["slug"])}
            for r in body.get("regions", [])
            if r.get("available", True)
        ]

    def list_sizes(self) -> list[dict[str, Any]]:
        """Available sizes as ``{slug, description, memory, vcpus, disk, price_monthly, regions}``."""
        body = self._api.request("GET", "/sizes", params={"per_page": 200})
        return [
            {
                "slug": s["slug"],
                "description": s.get("description", s["slug"]),
                "memory": s.get("memory"),
                "vcpus": s.get("vcpus"),
                "disk": s.get("disk"),
                "price_monthly": s.get("price_monthly"),
                "regions": s.get("regions", []),
            }
            for s in body.get("sizes", [])
            if s.get("available", True)
        ]

    def list_images(self, *, distribution: str = "Ubuntu") -> list[dict[str, Any]]:
        """Public distribution images as ``{slug, name, distribution}``.

        Filtered to one distribution by default: the EspoCRM installer script
        targets Ubuntu, and the v1 server-prep phase adds Docker's apt repo the
        Ubuntu way.
        """
        body = self._api.request(
            "GET", "/images", params={"type": "distribution", "per_page": 200}
        )
        return [
            {
                "slug": i.get("slug"),
                "name": i.get("name"),
                "distribution": i.get("distribution"),
            }
            for i in body.get("images", [])
            if i.get("slug")
            and (distribution is None or i.get("distribution") == distribution)
        ]

    def list_ssh_keys(self) -> list[dict[str, Any]]:
        """Account SSH keys as ``{id, name, fingerprint}``."""
        body = self._api.request("GET", "/account/keys", params={"per_page": 200})
        return [
            {"id": k["id"], "name": k.get("name"), "fingerprint": k.get("fingerprint")}
            for k in body.get("ssh_keys", [])
        ]

    def add_ssh_key(self, *, name: str, public_key: str) -> dict[str, Any]:
        """Register a public key on the account; returns ``{id, name, fingerprint}``.

        DigitalOcean rejects a duplicate key with 422; in that case the existing
        key with the same fingerprint is looked up and returned, so re-running a
        ``validate`` phase is idempotent.
        """
        try:
            body = self._api.request(
                "POST", "/account/keys", json={"name": name, "public_key": public_key}
            )
        except ProviderError as exc:
            if exc.status != 422:
                raise
            for key in self.list_ssh_keys():
                if key.get("name") == name:
                    return key
            raise
        key = body.get("ssh_key", {})
        return {"id": key.get("id"), "name": key.get("name"), "fingerprint": key.get("fingerprint")}

    # -- droplets --------------------------------------------------------------

    def find_droplets_by_tag(self, tag: str) -> list[dict[str, Any]]:
        """Droplets carrying ``tag`` (the idempotency lookup for a run)."""
        body = self._api.request(
            "GET", "/droplets", params={"tag_name": tag, "per_page": 200}
        )
        return [_summarize(d) for d in body.get("droplets", [])]

    def create_droplet(
        self,
        *,
        name: str,
        region: str,
        size: str,
        image: str,
        ssh_key_ids: list[int | str],
        tags: list[str],
    ) -> dict[str, Any]:
        """``POST /droplets``; returns the new droplet summary (status ``new``).

        The public IP is not assigned yet — poll :meth:`get_droplet` until
        ``status == "active"`` and ``ip`` is set.
        """
        payload = {
            "name": name,
            "region": region,
            "size": size,
            "image": image,
            "ssh_keys": list(ssh_key_ids),
            "tags": sorted({CRMBUILDER_TAG, *tags}),
            "backups": False,
            "ipv6": False,
            "monitoring": True,
        }
        body = self._api.request("POST", "/droplets", json=payload)
        return _summarize(body.get("droplet", {}))

    def get_droplet(self, droplet_id: int | str) -> dict[str, Any]:
        """``GET /droplets/{id}`` as a summary ``{id, name, status, ip, region, size}``."""
        body = self._api.request("GET", f"/droplets/{droplet_id}")
        return _summarize(body.get("droplet", {}))


def _public_ipv4(droplet: dict[str, Any]) -> str | None:
    for entry in (droplet.get("networks") or {}).get("v4", []) or []:
        if entry.get("type") == "public" and entry.get("ip_address"):
            return entry["ip_address"]
    return None


def _summarize(droplet: dict[str, Any]) -> dict[str, Any]:
    region = droplet.get("region") or {}
    size = droplet.get("size") or {}
    return {
        "id": droplet.get("id"),
        "name": droplet.get("name"),
        "status": droplet.get("status"),
        "ip": _public_ipv4(droplet),
        "region": region.get("slug") if isinstance(region, dict) else region,
        "size": size.get("slug") if isinstance(size, dict) else droplet.get("size_slug"),
        "tags": droplet.get("tags", []),
    }
