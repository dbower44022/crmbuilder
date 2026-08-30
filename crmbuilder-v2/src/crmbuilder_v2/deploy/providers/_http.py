"""Shared JSON-over-HTTPS plumbing for the provider clients — PI-419."""

from __future__ import annotations

from typing import Any

import requests

from crmbuilder_v2.deploy.errors import ProviderError


class JsonApi:
    """A bearer-authenticated JSON API at ``base_url``.

    :param provider: The provider name used in every raised error.
    :param base_url: API root, without a trailing slash.
    :param token: The bearer token. Never logged, never echoed.
    :param session: An injectable ``requests.Session`` (tests pass a fake).
    :param timeout: Per-request timeout in seconds.
    """

    def __init__(
        self,
        provider: str,
        base_url: str,
        token: str,
        *,
        session: requests.Session | None = None,
        timeout: int = 30,
    ) -> None:
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Issue one request and return the decoded JSON body.

        Non-2xx statuses, transport failures and non-JSON bodies all raise
        :class:`ProviderError` with the provider's own message when available.
        """
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(
                method, url, params=params, json=json, timeout=self.timeout
            )
        except requests.exceptions.RequestException as exc:
            raise ProviderError(self.provider, f"{method} {path}: {exc}") from exc
        if response.status_code == 204 or not response.content:
            body: dict[str, Any] = {}
        else:
            try:
                body = response.json()
            except ValueError as exc:
                raise ProviderError(
                    self.provider,
                    f"{method} {path}: non-JSON response",
                    status=response.status_code,
                ) from exc
        if not 200 <= response.status_code < 300:
            raise ProviderError(
                self.provider,
                f"{method} {path}: {_error_message(body)}",
                status=response.status_code,
            )
        return body if isinstance(body, dict) else {"data": body}


def _error_message(body: Any) -> str:
    """Pull the human message out of a DigitalOcean or Cloudflare error body."""
    if isinstance(body, dict):
        # DigitalOcean: {"id": "...", "message": "..."}
        if isinstance(body.get("message"), str):
            return body["message"]
        # Cloudflare: {"success": false, "errors": [{"code": ..., "message": ...}]}
        errors = body.get("errors")
        if isinstance(errors, list) and errors:
            parts = []
            for err in errors:
                if isinstance(err, dict) and err.get("message"):
                    code = err.get("code")
                    parts.append(f"{err['message']}" + (f" [{code}]" if code else ""))
            if parts:
                return "; ".join(parts)
    return "request failed"
