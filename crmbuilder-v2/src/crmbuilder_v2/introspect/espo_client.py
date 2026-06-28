"""Standalone EspoCRM introspection REST client.

Ported from V1 ``espo_impl.core.api_client.EspoAdminClient`` for PI-187,
reduced to the connection/auth basics plus the discovery and security
read methods. All Qt/UI coupling and the V1 ``InstanceProfile`` model
dependency have been removed: connection configuration is supplied via
:class:`EspoConnectionConfig` (or plain constructor params), and the
client is a pure ``requests.Session``-based wrapper.

The discovery/security method names are kept identical to their V1
counterparts (``test_connection``, ``get_all_scopes``,
``get_entity_field_list``, ``get_all_links``, ``get_layout``,
``get_i18n``, ``get_client_defs``, ``list_report_filters``,
``get_teams``, ``get_roles``) so downstream reconcile code (PI-185)
can call them without translation.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

_RAW_TEXT_TRUNCATION = 2000
_DETAIL_TRUNCATION = 200

#: Supported authentication methods.
_VALID_AUTH_METHODS = frozenset({"api_key", "basic", "hmac"})


def format_error_detail(body: Any) -> str:
    """Format a response body (possibly a sentinel) as a readable error.

    :param body: The body returned by
        :meth:`EspoIntrospectionClient._request`. May be ``None``, a
        regular response dict, a sentinel dict carrying ``_parse_failed``
        / ``_request_failed``, or a non-dict value (list or scalar)
        returned by endpoints that respond with JSON arrays.
    :returns: A one-line error description suitable for end-user output.
    """
    if body is None:
        return "(no response body)"
    if not isinstance(body, dict):
        return repr(body)[:_DETAIL_TRUNCATION]
    if body.get("_request_failed"):
        return (
            f"request failed: "
            f"{body.get('_exception_type', 'Exception')}: "
            f"{body.get('_error', '')}"
        )
    if body.get("_parse_failed"):
        snippet = (body.get("_raw_text") or "")[:_DETAIL_TRUNCATION]
        return f"non-JSON response: {snippet}"
    msg = body.get("messageTranslation") or body.get("message")
    if msg:
        return str(msg)
    return repr(body)[:_DETAIL_TRUNCATION]


@dataclass(frozen=True)
class EspoConnectionConfig:
    """Connection configuration for :class:`EspoIntrospectionClient`.

    A standalone replacement for V1's ``InstanceProfile`` carrying only
    the fields the introspection client needs.

    :param base_url: EspoCRM instance URL. Either the site root
        (``https://crm.example.org``) or the API base
        (``https://crm.example.org/api/v1``); the ``/api/v1`` suffix is
        appended automatically when absent.
    :param api_key: API key (api_key/hmac auth) or username (basic auth).
    :param secret_key: Secret key for HMAC auth, or password for basic
        auth. Unused for api_key auth.
    :param auth_method: One of ``"api_key"``, ``"basic"``, ``"hmac"``.
    :param timeout: Per-request timeout in seconds.
    """

    base_url: str
    api_key: str
    secret_key: str | None = None
    auth_method: str = "api_key"
    timeout: int = 30

    @property
    def api_url(self) -> str:
        """Full API base URL with a single ``/api/v1`` suffix."""
        root = self.base_url.rstrip("/")
        if root.endswith("/api/v1"):
            return root
        return f"{root}/api/v1"


class EspoIntrospectionClient:
    """Read-only EspoCRM REST client for instance introspection.

    Supports API Key, HMAC, and Basic authentication methods. Exposes
    the connection test plus the metadata-discovery and security read
    endpoints needed to reverse-engineer a live instance.

    :param base_url: EspoCRM instance URL (site root or ``/api/v1``
        base). Ignored when ``config`` is supplied.
    :param api_key: API key or basic-auth username. Ignored when
        ``config`` is supplied.
    :param secret_key: HMAC secret or basic-auth password. Ignored when
        ``config`` is supplied.
    :param auth_method: ``"api_key"`` (default), ``"basic"``, or
        ``"hmac"``. Ignored when ``config`` is supplied.
    :param timeout: Request timeout in seconds. Ignored when ``config``
        is supplied.
    :param config: A prebuilt :class:`EspoConnectionConfig`. When given,
        it takes precedence over the individual params.
    :raises ValueError: If ``auth_method`` is not recognised.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        secret_key: str | None = None,
        auth_method: str = "api_key",
        timeout: int = 30,
        *,
        config: EspoConnectionConfig | None = None,
    ) -> None:
        if config is None:
            if base_url is None or api_key is None:
                raise ValueError(
                    "base_url and api_key are required when no config is "
                    "supplied"
                )
            config = EspoConnectionConfig(
                base_url=base_url,
                api_key=api_key,
                secret_key=secret_key,
                auth_method=auth_method,
                timeout=timeout,
            )

        if config.auth_method not in _VALID_AUTH_METHODS:
            raise ValueError(
                f"Unsupported auth_method {config.auth_method!r}; "
                f"expected one of {sorted(_VALID_AUTH_METHODS)}"
            )

        self.config = config
        self.timeout = config.timeout
        #: Headers of the most recent response, for callers that need
        #: e.g. ``Retry-After`` on a 429. Empty after a transport failure.
        self.last_response_headers: dict[str, str] = {}

        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

        if config.auth_method == "api_key":
            self.session.headers["X-Api-Key"] = config.api_key
        elif config.auth_method == "basic":
            credentials = f"{config.api_key}:{config.secret_key}"
            encoded = base64.b64encode(
                credentials.encode("utf-8")
            ).decode("utf-8")
            self.session.headers["Authorization"] = f"Basic {encoded}"
            self.session.headers["Espo-Authorization"] = encoded

    @classmethod
    def from_config(
        cls, config: EspoConnectionConfig
    ) -> EspoIntrospectionClient:
        """Construct a client from a :class:`EspoConnectionConfig`.

        :param config: The connection configuration.
        :returns: A configured client.
        """
        return cls(config=config)

    @property
    def api_url(self) -> str:
        """Full API base URL (``{base_url}/api/v1``)."""
        return self.config.api_url

    def _hmac_header(self, method: str, url: str) -> dict[str, str]:
        """Build the HMAC authorization header for a request.

        :param method: HTTP method (GET, POST, PUT).
        :param url: Full request URL.
        :returns: Dict with the ``X-Hmac-Authorization`` header, or an
            empty dict when not using HMAC auth.
        """
        if self.config.auth_method != "hmac":
            return {}

        # EspoCRM expects the URI portion after /api/v1/.
        parsed = urlparse(url)
        full_path = parsed.path.lstrip("/")
        api_prefix = "api/v1/"
        if full_path.startswith(api_prefix):
            uri = full_path[len(api_prefix):]
        else:
            uri = full_path
        if parsed.query:
            uri = f"{uri}?{parsed.query}"

        string_to_sign = f"{method} /{uri}"
        hmac_hash = hmac.new(
            (self.config.secret_key or "").encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        auth_string = f"{self.config.api_key}:{hmac_hash}"
        encoded = base64.b64encode(
            auth_string.encode("utf-8")
        ).decode("utf-8")

        return {"X-Hmac-Authorization": encoded}

    def _request(
        self, method: str, url: str, **kwargs: Any
    ) -> tuple[int, Any]:
        """Execute an HTTP request with the appropriate auth.

        Catches all reasonable failure modes — connection drops,
        timeouts, SSL failures, non-JSON response bodies — and returns a
        sentinel body dict carrying diagnostic detail rather than
        propagating the exception. Use :func:`format_error_detail` to
        render the body for user-facing output.

        :param method: HTTP method.
        :param url: Full request URL.
        :returns: Tuple of ``(status_code, body)``. ``status_code`` is
            ``-1`` for transport-level failures. ``body`` is ``None``
            only when the server returned an empty response. ``body``
            may be a list when the endpoint returns a JSON array (e.g.,
            layout endpoints).
        """
        headers = kwargs.pop("headers", {})
        headers.update(self._hmac_header(method, url))

        self.last_response_headers = {}
        try:
            resp = self.session.request(
                method, url, headers=headers, timeout=self.timeout, **kwargs
            )
        except requests.exceptions.ConnectionError as exc:
            logger.error("Connection error: %s %s: %s", method, url, exc)
            return -1, {
                "_request_failed": True,
                "_error": str(exc),
                "_exception_type": type(exc).__name__,
            }
        except requests.exceptions.Timeout as exc:
            logger.error("Request timeout: %s %s: %s", method, url, exc)
            return -1, {
                "_request_failed": True,
                "_error": str(exc),
                "_exception_type": type(exc).__name__,
            }
        except requests.exceptions.RequestException as exc:
            logger.error(
                "Request failed: %s %s: %s: %s",
                method,
                url,
                type(exc).__name__,
                exc,
            )
            return -1, {
                "_request_failed": True,
                "_error": str(exc),
                "_exception_type": type(exc).__name__,
            }

        try:
            self.last_response_headers = dict(resp.headers or {})
        except (TypeError, ValueError):
            self.last_response_headers = {}

        if not resp.content:
            return resp.status_code, None

        try:
            body = resp.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raw = resp.content.decode("utf-8", errors="replace")
            truncated = raw[:_RAW_TEXT_TRUNCATION]
            logger.warning(
                "Non-JSON response from %s %s: status=%d, body=%r, "
                "parse_error=%s",
                method,
                url,
                resp.status_code,
                truncated,
                exc,
            )
            return resp.status_code, {
                "_parse_failed": True,
                "_raw_text": truncated,
                "_status_code": resp.status_code,
            }

        return resp.status_code, body

    # --- Connection test ---

    def test_connection(self) -> tuple[bool, str]:
        """Test API connectivity by fetching metadata.

        :returns: Tuple of ``(success, message)``.
        """
        url = f"{self.api_url}/Metadata?key=app.adminPanel"
        status_code, _ = self._request("GET", url)

        if status_code == 200:
            return True, "Connection successful"
        elif status_code == 401:
            return False, "Authentication failed — check API key"
        elif status_code == 403:
            return False, "Access forbidden — API user needs admin role"
        elif status_code == -1:
            return False, "Connection failed — check URL"
        else:
            return False, f"Unexpected response: HTTP {status_code}"

    # --- Metadata discovery endpoints ---

    def get_all_scopes(self) -> tuple[int, dict[str, dict] | None]:
        """Fetch all entity scopes from metadata.

        :returns: Tuple of ``(status_code, {scopeName: {entity,
            isCustom, ...}} or None)``.
        """
        url = f"{self.api_url}/Metadata?key=scopes"
        return self._request("GET", url)

    def get_entity_field_list(
        self, entity: str
    ) -> tuple[int, dict[str, dict] | None]:
        """Fetch all field definitions for an entity.

        :param entity: Entity name (e.g., "Contact").
        :returns: Tuple of ``(status_code, {fieldName: {label, type,
            ...}} or None)``.
        """
        url = f"{self.api_url}/Metadata?key=entityDefs.{entity}.fields"
        return self._request("GET", url)

    def get_collection(
        self, entity: str
    ) -> tuple[int, dict[str, Any] | None]:
        """Fetch the collection-search settings for an entity (REQ-340).

        The ``entityDefs.{Entity}.collection`` block carries the neutral
        collection settings: ``orderBy``, ``order``, ``textFilterFields``,
        ``fullTextSearch``, ``fullTextSearchMinLength``.

        :param entity: EspoCRM entity name (e.g. "Contact").
        :returns: Tuple of ``(status_code, {orderBy, order,
            textFilterFields, fullTextSearch, ...} or None)``.
        """
        url = f"{self.api_url}/Metadata?key=entityDefs.{entity}.collection"
        return self._request("GET", url)

    def get_all_links(
        self, entity: str
    ) -> tuple[int, dict[str, dict] | None]:
        """Fetch all link definitions for an entity.

        :param entity: EspoCRM entity name.
        :returns: Tuple of ``(status_code, {linkName: {type, entity,
            foreign, ...}} or None)``.
        """
        url = f"{self.api_url}/Metadata?key=entityDefs.{entity}.links"
        return self._request("GET", url)

    def get_layout(
        self, entity: str, layout_type: str
    ) -> tuple[int, Any]:
        """Fetch the current layout for an entity.

        :param entity: EspoCRM entity name (C-prefixed for custom).
        :param layout_type: Layout type (e.g., "detail", "list").
        :returns: Tuple of ``(status_code, response_json)``.
        """
        url = (
            f"{self.api_url}/Layout/action/getOriginal"
            f"?scope={entity}&name={layout_type}"
        )
        return self._request("GET", url)

    def get_i18n(
        self, language: str = "en_US"
    ) -> tuple[int, dict[str, Any]]:
        """Fetch the full merged i18n payload for the given language.

        EspoCRM stores display labels (``labelSingular``/``labelPlural``
        on entities, plus field and link labels) in i18n resources, not
        in ``entityDefs.{Entity}``. The ``/I18n`` endpoint returns the
        merged tree:

        - ``{"Global": {"scopeNames": {...}, "scopeNamesPlural": {...},
          "fields": {...}, "links": {...}, ...}}``
        - ``{"<Entity>": {"fields": {...}, "links": {...}, ...}}`` per
          entity, with entity-specific overrides of Global defaults.

        Probing ``/Metadata?key=i18n.<lang>.<path>`` for nested keys
        returns ``null`` on this server, so callers must fetch the whole
        tree and traverse it client-side.

        :param language: Language code (default: ``"en_US"``).
        :returns: Tuple of ``(status_code, i18n tree)``. Empty dict on
            any non-200 or shape mismatch so callers can ``.get()``
            safely.
        """
        url = f"{self.api_url}/I18n?language={language}"
        status, body = self._request("GET", url)
        if status != 200 or not isinstance(body, dict):
            return status, {}
        return status, body

    def get_client_defs(
        self, entity: str
    ) -> tuple[int, dict[str, Any] | None]:
        """Fetch clientDefs metadata for an entity.

        Contains duplicate-check configuration among other things.

        :param entity: EspoCRM entity name.
        :returns: Tuple of ``(status_code, clientDefs dict or None)``.
        """
        url = f"{self.api_url}/Metadata?key=clientDefs.{entity}"
        return self._request("GET", url)

    # --- Report Filter endpoints (Advanced Pack) ---

    def list_report_filters(
        self,
        entity_type: str,
    ) -> tuple[int, dict[str, Any] | None]:
        """List Report Filters that target a given entity type.

        Report Filters are a record entity contributed by the Advanced
        Pack extension. On instances without Advanced Pack, GET against
        ``/ReportFilter`` returns HTTP 404; callers should treat that as
        "feature unavailable" rather than a transport error.

        :param entity_type: EspoCRM entity name (e.g., "Account",
            "CEngagement").
        :returns: Tuple of ``(status_code, response_json or None)``. The
            standard EspoCRM list response shape ``{total, list}`` is
            returned on success; HTTP 404 means Advanced Pack is not
            installed on this instance.
        """
        url = (
            f"{self.api_url}/ReportFilter"
            f"?where[0][type]=equals"
            f"&where[0][attribute]=entityType"
            f"&where[0][value]={entity_type}"
        )
        return self._request("GET", url)

    # --- Team management (read) ---

    def get_teams(self) -> tuple[int, dict[str, Any] | None]:
        """List all Team records on the target instance.

        Bulk-fetches up to 200 teams in a single GET. This is sufficient
        for the dogfood and pilot-client use cases; an instance with more
        than 200 teams would require pagination, which is not implemented
        here.

        :returns: Tuple of ``(status_code, response_json or None)``. The
            standard EspoCRM list response shape ``{"total": N, "list":
            [...]}`` is returned on success.
        """
        url = f"{self.api_url}/Team?maxSize=200"
        return self._request("GET", url)

    # --- Role management (read) ---

    def get_roles(self) -> tuple[int, dict[str, Any] | None]:
        """List all Role records on the target instance.

        Bulk-fetches up to 200 roles in a single GET. Pagination beyond
        this is not implemented; documented as a future scaling concern
        matching :meth:`get_teams`.

        :returns: Tuple of ``(status_code, response_json or None)``.
            Standard EspoCRM list shape ``{"total": N, "list": [...]}``
            on success.
        """
        url = f"{self.api_url}/Role?maxSize=200"
        return self._request("GET", url)

    # --- Record data (read) — PI-234 / REQ-130 ---

    def get_records(
        self, entity: str, *, max_size: int = 200, offset: int = 0
    ) -> tuple[int, dict[str, Any] | None]:
        """List records of an entity for seed/reference export (PI-234).

        Bulk-fetches up to ``max_size`` records in one GET, ordered by EspoCRM's
        default. ``offset`` supports simple paging; deeper pagination is the same
        documented scaling concern as :meth:`get_teams`.

        :returns: ``(status_code, response_json or None)`` — the standard EspoCRM
            list shape ``{"total": N, "list": [...]}`` on success.
        """
        url = f"{self.api_url}/{entity}?maxSize={max_size}&offset={offset}"
        return self._request("GET", url)
