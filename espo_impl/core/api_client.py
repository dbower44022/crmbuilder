"""EspoCRM Admin REST API client for field management."""

import base64
import hashlib
import hmac
import json
import logging
from typing import Any
from urllib.parse import urlencode, urlparse

import requests

from espo_impl.core.models import InstanceProfile

logger = logging.getLogger(__name__)


_RAW_TEXT_TRUNCATION = 2000
_DETAIL_TRUNCATION = 200


def _format_error_detail(body: Any) -> str:
    """Format a response body (possibly a sentinel) as a human-readable error detail.

    :param body: The body returned by ``EspoAdminClient._request``. May be
        ``None``, a regular response dict, a sentinel dict carrying
        ``_parse_failed`` / ``_request_failed``, or a non-dict value (list
        or scalar) returned by endpoints that respond with JSON arrays.
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


def _where_query_params(where: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Encode EspoCRM where-items as flat query parameters.

    Produces the ``where[i][type]`` / ``where[i][attribute]`` /
    ``where[i][value]`` triples the record list endpoint expects (the
    same idiom :meth:`EspoAdminClient.search_by_email` hand-writes).
    List values are emitted as repeated ``where[i][value][]`` entries
    (the shape ``arrayAnyOf`` takes).

    :param where: List of where-item dicts, each with a ``type`` key
        and optional ``attribute`` / ``value`` keys.
    :returns: Ordered (key, value) pairs ready for ``urlencode``.
    """
    params: list[tuple[str, str]] = []
    for i, item in enumerate(where):
        params.append((f"where[{i}][type]", str(item["type"])))
        if "attribute" in item:
            params.append((f"where[{i}][attribute]", str(item["attribute"])))
        if "value" in item:
            value = item["value"]
            if isinstance(value, (list, tuple)):
                for element in value:
                    params.append((f"where[{i}][value][]", str(element)))
            else:
                params.append((f"where[{i}][value]", str(value)))
    return params


class EspoAdminClient:
    """EspoCRM Admin API client for field management.

    Supports API Key, HMAC, and Basic authentication methods.

    :param profile: Instance connection profile.
    :param timeout: Request timeout in seconds.
    """

    def __init__(self, profile: InstanceProfile, timeout: int = 30) -> None:
        self.profile = profile
        self.timeout = timeout
        # Headers of the most recent response, for callers that need
        # e.g. Retry-After on a 429. Empty after a transport failure.
        self.last_response_headers: dict[str, str] = {}
        # Whether this server accepts maxSize=0 count queries. None
        # until the first count_records call probes it (per WTK-096
        # §4.1 — detected once per run and remembered).
        self._count_max_size_zero_ok: bool | None = None
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
        })

        if profile.auth_method == "api_key":
            self.session.headers["X-Api-Key"] = profile.api_key
        elif profile.auth_method == "basic":
            credentials = f"{profile.api_key}:{profile.secret_key}"
            encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
            self.session.headers["Authorization"] = f"Basic {encoded}"
            self.session.headers["Espo-Authorization"] = encoded

    @property
    def _base_url(self) -> str:
        """Admin fieldManager base URL."""
        return f"{self.profile.api_url}/Admin/fieldManager"

    def _hmac_header(self, method: str, url: str) -> dict[str, str]:
        """Build the HMAC authorization header for a request.

        :param method: HTTP method (GET, POST, PUT).
        :param url: Full request URL.
        :returns: Dict with the X-Hmac-Authorization header.
        """
        if self.profile.auth_method != "hmac":
            return {}

        # EspoCRM expects the URI portion after /api/v1/
        parsed = urlparse(url)
        full_path = parsed.path.lstrip("/")
        # Strip the api/v1 prefix to get the resource path
        api_prefix = "api/v1/"
        if full_path.startswith(api_prefix):
            uri = full_path[len(api_prefix):]
        else:
            uri = full_path
        if parsed.query:
            uri = f"{uri}?{parsed.query}"

        string_to_sign = f"{method} /{uri}"
        hmac_hash = hmac.new(
            self.profile.secret_key.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        auth_string = f"{self.profile.api_key}:{hmac_hash}"
        encoded = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")

        return {"X-Hmac-Authorization": encoded}

    def _request(
        self, method: str, url: str, **kwargs: Any
    ) -> tuple[int, Any]:
        """Execute an HTTP request with appropriate auth.

        Catches all reasonable failure modes — connection drops, timeouts,
        SSL failures, non-JSON response bodies — and returns a sentinel
        body dict carrying diagnostic detail rather than propagating the
        exception. Use :func:`_format_error_detail` to render the body
        for user-facing output.

        :param method: HTTP method.
        :param url: Full request URL.
        :returns: Tuple of (status_code, body). ``status_code`` is ``-1``
            for transport-level failures. ``body`` is ``None`` only when
            the server returned an empty response. ``body`` may be a
            list when the endpoint returns a JSON array (e.g., layout
            endpoints).
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
                method, url, type(exc).__name__, exc,
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
                method, url, resp.status_code, truncated, exc,
            )
            return resp.status_code, {
                "_parse_failed": True,
                "_raw_text": truncated,
                "_status_code": resp.status_code,
            }

        return resp.status_code, body

    def get_field(
        self, entity: str, field_name: str
    ) -> tuple[int, dict[str, Any] | None]:
        """Fetch a field definition via the Metadata API.

        Uses ``Metadata?key=entityDefs.{entity}.fields.{fieldName}`` which
        reliably returns field definitions for both system and custom fields.
        Falls back to the Admin/fieldManager endpoint if metadata returns
        an empty result.

        :param entity: Entity name (e.g., "Contact").
        :param field_name: Field name (e.g., "contactType" or "cContactType").
        :returns: Tuple of (status_code, response_json or None).
        """
        # Primary: use the Metadata API
        url = (
            f"{self.profile.api_url}/Metadata"
            f"?key=entityDefs.{entity}.fields.{field_name}"
        )
        status_code, body = self._request("GET", url)

        if status_code == 200 and isinstance(body, dict) and body:
            return 200, body

        # Metadata returned empty or error — try Admin/fieldManager
        fm_url = f"{self._base_url}/{entity}/{field_name}"
        return self._request("GET", fm_url)

    def create_field(
        self, entity: str, payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        """Create a new field on the instance.

        Automatically injects ``isCustom: true`` into the payload.

        :param entity: Entity name.
        :param payload: Field definition payload.
        :returns: Tuple of (status_code, response_json or None).
        """
        url = f"{self._base_url}/{entity}"
        payload = {**payload, "isCustom": True}
        return self._request("POST", url, json=payload)

    def update_field(
        self, entity: str, field_name: str, payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        """Update an existing field on the instance.

        :param entity: Entity name.
        :param field_name: Field name.
        :param payload: Updated field definition payload.
        :returns: Tuple of (status_code, response_json or None).
        """
        url = f"{self._base_url}/{entity}/{field_name}"
        return self._request("PUT", url, json=payload)

    # --- Entity Manager endpoints ---

    def create_entity(
        self, payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        """Create a custom entity type.

        :param payload: Entity definition (name, type, labelSingular, etc.).
        :returns: Tuple of (status_code, response_json or None).
        """
        url = f"{self.profile.api_url}/EntityManager/action/createEntity"
        return self._request("POST", url, json=payload)

    def remove_entity(self, name: str) -> tuple[int, dict[str, Any] | None]:
        """Remove a custom entity type.

        Uses the EspoCRM internal name (C-prefixed).

        :param name: EspoCRM internal entity name (e.g., "CEngagement").
        :returns: Tuple of (status_code, response_json or None).
        """
        url = f"{self.profile.api_url}/EntityManager/action/removeEntity"
        return self._request("POST", url, json={"name": name})

    def check_entity_exists(self, name: str) -> tuple[int, bool]:
        """Check whether an entity type exists via the Metadata API.

        :param name: Entity name to check (e.g., "CEngagement").
        :returns: Tuple of (status_code, exists).
        """
        url = f"{self.profile.api_url}/Metadata?key=scopes.{name}"
        status_code, body = self._request("GET", url)
        if status_code == 200 and isinstance(body, dict) and body:
            return status_code, True
        return status_code, False

    def rebuild(self) -> tuple[int, dict[str, Any] | None]:
        """Trigger a cache rebuild on the instance.

        :returns: Tuple of (status_code, response_json or None).
        """
        url = f"{self.profile.api_url}/Admin/rebuild"
        return self._request("POST", url)

    def update_entity(
        self, payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        """Update an existing entity's settings (stream, disabled, labels).

        :param payload: Entity update payload (must include ``name``).
        :returns: Tuple of (status_code, response_json or None).
        """
        url = f"{self.profile.api_url}/EntityManager/action/updateEntity"
        return self._request("POST", url, json=payload)

    def get_client_defs(
        self, entity: str
    ) -> tuple[int, dict[str, Any] | None]:
        """Fetch clientDefs metadata for an entity.

        Contains duplicate-check configuration among other things.

        :param entity: EspoCRM entity name.
        :returns: Tuple of (status_code, clientDefs dict or None).
        """
        url = f"{self.profile.api_url}/Metadata?key=clientDefs.{entity}"
        return self._request("GET", url)

    def put_metadata(
        self, payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        """Write arbitrary metadata via the Metadata API.

        :param payload: Metadata payload (nested dict matching Metadata structure).
        :returns: Tuple of (status_code, response_json or None).
        """
        url = f"{self.profile.api_url}/Metadata"
        return self._request("PUT", url, json=payload)

    # --- Report Filter endpoints (Advanced Pack) ---
    #
    # Report Filters are a record entity contributed by the Advanced Pack
    # extension. On instances without Advanced Pack, GET/POST against
    # /ReportFilter returns HTTP 404; callers should treat that as
    # "feature unavailable" rather than a transport error.

    def list_report_filters(
        self, entity_type: str,
    ) -> tuple[int, dict[str, Any] | None]:
        """List Report Filters that target a given entity type.

        :param entity_type: EspoCRM entity name (e.g., "Account", "CEngagement").
        :returns: Tuple of (status_code, response_json or None). The
            standard EspoCRM list response shape ``{total, list}`` is
            returned on success; HTTP 404 means Advanced Pack is not
            installed on this instance.
        """
        url = (
            f"{self.profile.api_url}/ReportFilter"
            f"?where[0][type]=equals"
            f"&where[0][attribute]=entityType"
            f"&where[0][value]={entity_type}"
        )
        return self._request("GET", url)

    def create_report_filter(
        self, payload: dict[str, Any],
    ) -> tuple[int, dict[str, Any] | None]:
        """Create a Report Filter record.

        Expected payload shape::

            {
                "name": "My Engagements",
                "entityType": "CEngagement",
                "data": {"where": [<EspoCRM where-item dicts>]},
            }

        :param payload: Report Filter creation payload.
        :returns: Tuple of (status_code, response_json or None).
        """
        url = f"{self.profile.api_url}/ReportFilter"
        return self._request("POST", url, json=payload)

    def delete_report_filter(
        self, filter_id: str,
    ) -> tuple[int, dict[str, Any] | None]:
        """Delete a Report Filter record.

        :param filter_id: Report Filter record id.
        :returns: Tuple of (status_code, response_json or None).
        """
        url = f"{self.profile.api_url}/ReportFilter/{filter_id}"
        return self._request("DELETE", url)

    # --- Metadata discovery endpoints (audit) ---

    def get_all_scopes(self) -> tuple[int, dict[str, dict] | None]:
        """Fetch all entity scopes from metadata.

        :returns: Tuple of (status_code, {scopeName: {entity, isCustom, ...}} or None).
        """
        url = f"{self.profile.api_url}/Metadata?key=scopes"
        return self._request("GET", url)

    def get_entity_full_metadata(
        self, entity: str
    ) -> tuple[int, dict[str, Any] | None]:
        """Fetch complete entityDefs for an entity.

        :param entity: EspoCRM entity name (e.g., "Contact", "CEngagement").
        :returns: Tuple of (status_code, full entityDefs dict or None).
        """
        url = f"{self.profile.api_url}/Metadata?key=entityDefs.{entity}"
        return self._request("GET", url)

    def get_all_links(
        self, entity: str
    ) -> tuple[int, dict[str, dict] | None]:
        """Fetch all link definitions for an entity.

        :param entity: EspoCRM entity name.
        :returns: Tuple of (status_code, {linkName: {type, entity, foreign, ...}} or None).
        """
        url = f"{self.profile.api_url}/Metadata?key=entityDefs.{entity}.links"
        return self._request("GET", url)

    def get_metadata(self, key: str) -> tuple[int, Any]:
        """Fetch an arbitrary metadata value by dotted key.

        The Metadata API returns the value at ``key`` (e.g.
        ``entityDefs.Meeting.fields.parent.entityList``). A key that does not
        resolve yields an empty body; callers should treat that as "absent".

        :param key: Dotted metadata key.
        :returns: Tuple of (status_code, value) — ``value`` is the parsed JSON
            (dict/list/scalar) or ``None`` for an empty body.
        """
        url = f"{self.profile.api_url}/Metadata?key={key}"
        return self._request("GET", url)

    def get_language_translations(
        self, entity: str, language: str = "en_US"
    ) -> tuple[int, dict[str, Any] | None]:
        """Fetch translated labels for an entity's fields and links.

        :param entity: EspoCRM entity name.
        :param language: Language code (default: "en_US").
        :returns: Tuple of (status_code, translation dict or None).
        """
        url = (
            f"{self.profile.api_url}/Metadata"
            f"?key=i18n.{language}.{entity}"
        )
        status, body = self._request("GET", url)
        if status == 200 and body:
            return status, body
        # Fallback: try the I18n endpoint
        url = f"{self.profile.api_url}/I18n?language={language}"
        return self._request("GET", url)

    def get_i18n(
        self, language: str = "en_US"
    ) -> tuple[int, dict[str, Any]]:
        """Fetch the full merged i18n payload for the given language.

        EspoCRM stores display labels (``labelSingular``/``labelPlural`` on
        entities, plus field and link labels) in i18n resources, not in
        ``entityDefs.{Entity}``. The ``/I18n`` endpoint returns the merged
        tree:

        - ``{"Global": {"scopeNames": {...}, "scopeNamesPlural": {...},
          "fields": {...}, "links": {...}, ...}}``
        - ``{"<Entity>": {"fields": {...}, "links": {...}, ...}}`` per
          entity, with entity-specific overrides of Global defaults.

        Probing ``/Metadata?key=i18n.<lang>.<path>`` for nested keys
        returns ``null`` on this server, so callers must fetch the whole
        tree and traverse it client-side.

        :param language: Language code (default: ``"en_US"``).
        :returns: Tuple of (status_code, i18n tree). Empty dict on any
            non-200 or shape mismatch so callers can ``.get()`` safely.
        """
        url = f"{self.profile.api_url}/I18n?language={language}"
        status, body = self._request("GET", url)
        if status != 200 or not isinstance(body, dict):
            return status, {}
        return status, body

    # --- Relationship Manager endpoints ---

    def get_link(
        self, entity: str, link: str
    ) -> tuple[int, Any]:
        """Fetch link metadata for a relationship.

        :param entity: EspoCRM entity name (C-prefixed for custom).
        :param link: Link name on the entity.
        :returns: Tuple of (status_code, response_json).
        """
        url = (
            f"{self.profile.api_url}/Metadata"
            f"?key=entityDefs.{entity}.links.{link}"
        )
        return self._request("GET", url)

    def create_link(
        self, payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        """Create a relationship link between entities.

        :param payload: Full link payload.
        :returns: Tuple of (status_code, response_json or None).
        """
        url = f"{self.profile.api_url}/EntityManager/action/createLink"
        return self._request("POST", url, json=payload)

    # --- Layout Manager endpoints ---

    def get_layout(
        self, entity: str, layout_type: str
    ) -> tuple[int, Any]:
        """Fetch the current layout for an entity.

        :param entity: EspoCRM entity name (C-prefixed for custom).
        :param layout_type: Layout type (e.g., "detail", "list").
        :returns: Tuple of (status_code, response_json).
        """
        url = (
            f"{self.profile.api_url}/Layout/action/getOriginal"
            f"?scope={entity}&name={layout_type}"
        )
        return self._request("GET", url)

    def save_layout(
        self, entity: str, layout_type: str, payload: Any
    ) -> tuple[int, Any]:
        """Save a layout for an entity.

        :param entity: EspoCRM entity name (C-prefixed for custom).
        :param layout_type: Layout type (e.g., "detail", "list").
        :param payload: Full layout payload (list of panels or columns).
        :returns: Tuple of (status_code, response_json).
        """
        url = f"{self.profile.api_url}/{entity}/layout/{layout_type}"
        return self._request("PUT", url, json=payload)

    # --- Data-level endpoints ---

    def get_entity_field_list(
        self, entity: str
    ) -> tuple[int, dict[str, dict] | None]:
        """Fetch all field definitions for an entity.

        :param entity: Entity name (e.g., "Contact").
        :returns: Tuple of (status_code, {fieldName: {label, type, ...}} or None).
        """
        url = (
            f"{self.profile.api_url}/Metadata"
            f"?key=entityDefs.{entity}.fields"
        )
        return self._request("GET", url)

    def list_records(
        self,
        entity: str,
        select: list[str] | None = None,
        where: list[dict[str, Any]] | None = None,
        order_by: str | None = None,
        order: str | None = None,
        offset: int = 0,
        max_size: int = 200,
    ) -> tuple[int, dict[str, Any] | None]:
        """Query the record list endpoint with arbitrary search parameters.

        Generic surface over ``GET /{Entity}`` returning the standard
        EspoCRM list shape ``{"total": N, "list": [...]}``. The query
        string is built into the URL (not passed as ``params``) so the
        HMAC signature covers it, matching ``search_by_email``.

        :param entity: EspoCRM entity name (C-prefixed for custom).
        :param select: Attribute names to return per record; ``None``
            lets the server choose its default attribute set.
        :param where: Where-item dicts (see :func:`_where_query_params`).
        :param order_by: Attribute to sort by (e.g., ``createdAt``).
        :param order: Sort direction, ``"asc"`` or ``"desc"``.
        :param offset: Pagination offset.
        :param max_size: Page size; the server may clamp it lower.
        :returns: Tuple of (status_code, response_json or None).
        """
        params: list[tuple[str, str]] = [
            ("maxSize", str(max_size)),
            ("offset", str(offset)),
        ]
        if select:
            params.append(("select", ",".join(select)))
        if order_by:
            params.append(("orderBy", order_by))
        if order:
            params.append(("order", order))
        if where:
            params.extend(_where_query_params(where))
        url = f"{self.profile.api_url}/{entity}?{urlencode(params)}"
        return self._request("GET", url)

    def count_records(
        self,
        entity: str,
        where: list[dict[str, Any]] | None = None,
    ) -> tuple[int, int | None]:
        """Count records matching the given where-items.

        Uses the ``maxSize=0`` count idiom (the server returns ``total``
        with an empty list, so no record payload crosses the wire). A
        server build that rejects ``maxSize=0`` is detected on the first
        count query of the client's lifetime and remembered — subsequent
        counts use the ``maxSize=1&select=id`` fallback (WTK-096 §4.1).

        :param entity: EspoCRM entity name (C-prefixed for custom).
        :param where: Optional where-item dicts restricting the count.
        :returns: Tuple of (status_code, total or None). ``total`` is
            None on any non-200 or shape mismatch.
        """
        def _count(max_size: int, select: list[str] | None) -> tuple[int, int | None]:
            status, body = self.list_records(
                entity, select=select, where=where, max_size=max_size
            )
            if status == 200 and isinstance(body, dict):
                total = body.get("total")
                return status, total if isinstance(total, int) else None
            return status, None

        if self._count_max_size_zero_ok is False:
            return _count(1, ["id"])

        status, total = _count(0, None)
        if status == 200:
            self._count_max_size_zero_ok = True
            return status, total

        if status == 400 and self._count_max_size_zero_ok is None:
            # Ambiguous 400: maxSize=0 unsupported, or the where-item
            # itself rejected. Probe once with the fallback shape; if it
            # succeeds the server doesn't take maxSize=0, otherwise the
            # where was the problem and maxSize=0 stands as supported.
            fb_status, fb_total = _count(1, ["id"])
            if fb_status == 200:
                self._count_max_size_zero_ok = False
                return fb_status, fb_total
            self._count_max_size_zero_ok = True
            return fb_status, fb_total

        return status, total

    def search_by_email(
        self, entity: str, email: str
    ) -> tuple[int, list[dict] | None]:
        """Search for records matching an email address.

        :param entity: Entity name (e.g., "Contact").
        :param email: Email address to search for.
        :returns: Tuple of (status_code, list of matching records or None).
        """
        url = (
            f"{self.profile.api_url}/{entity}"
            f"?where[0][type]=equals"
            f"&where[0][attribute]=emailAddress"
            f"&where[0][value]={email}"
            f"&maxSize=2"
        )
        status, body = self._request("GET", url)
        if status == 200 and isinstance(body, dict):
            return status, body.get("list", [])
        return status, [] if status == 200 else None

    def get_record(
        self, entity: str, record_id: str
    ) -> tuple[int, dict[str, Any] | None]:
        """Fetch a single record by ID.

        :param entity: Entity name.
        :param record_id: EspoCRM record ID.
        :returns: Tuple of (status_code, record dict or None).
        """
        url = f"{self.profile.api_url}/{entity}/{record_id}"
        return self._request("GET", url)

    def create_record(
        self, entity: str, payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        """Create a new record.

        :param entity: Entity name.
        :param payload: Field values to set.
        :returns: Tuple of (status_code, created record or None).
        """
        url = f"{self.profile.api_url}/{entity}"
        return self._request("POST", url, json=payload)

    def patch_record(
        self, entity: str, record_id: str, payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        """Patch specific fields on an existing record.

        Only the fields included in payload are updated.
        Fields not in payload are left unchanged.

        :param entity: Entity name.
        :param record_id: EspoCRM record ID.
        :param payload: Partial field values to update.
        :returns: Tuple of (status_code, response or None).
        """
        url = f"{self.profile.api_url}/{entity}/{record_id}"
        return self._request("PATCH", url, json=payload)

    # --- Team management ---

    def get_email_templates(
        self, entity_espo_name: str,
    ) -> tuple[int, dict[str, Any] | None]:
        """List EmailTemplate records bound to an entity type.

        Used by the audit to reverse-engineer the ``emailTemplates:``
        block. Filters server-side by ``entityType`` and bulk-fetches
        up to 200 templates in a single GET (sufficient for the
        dogfood and pilot-client use cases; more would require
        pagination, which is not implemented here). The query mirrors
        the deploy-side
        :meth:`espo_impl.core.email_template_manager.EmailTemplateManager._get_existing_templates`.

        :param entity_espo_name: EspoCRM wire-name of the entity
            (e.g. ``Contact``, ``CEngagement``).
        :returns: Tuple of (status_code, response_json or None) with
            the standard ``{"total": N, "list": [...]}`` shape on
            success.
        """
        url = (
            f"{self.profile.api_url}/EmailTemplate"
            f"?where[0][type]=equals"
            f"&where[0][attribute]=entityType"
            f"&where[0][value]={entity_espo_name}"
            f"&maxSize=200"
        )
        return self._request("GET", url)

    def get_entity_formula(
        self, entity: str
    ) -> tuple[int, dict[str, Any] | None]:
        """Fetch an entity's formula metadata (REQ-122 audit capture).

        Returns the ``formula.{Entity}`` metadata block, which holds the
        entity-level formula scripts (``beforeSaveCustomScript``,
        ``beforeSaveApiScript``, …). Entities without a formula return an
        empty / parse-failure body, which the audit treats as "no formula".

        :param entity: EspoCRM entity name (e.g. ``CMentorProfile``).
        :returns: Tuple of (status_code, formula dict or None).
        """
        url = f"{self.profile.api_url}/Metadata?key=formula.{entity}"
        return self._request("GET", url)

    def get_teams(
        self,
    ) -> tuple[int, dict[str, Any] | None]:
        """List all Team records on the target instance.

        Bulk-fetches up to 200 teams in a single GET. This is
        sufficient for the dogfood and pilot-client use cases; an
        instance with more than 200 teams would require pagination,
        which is not implemented in this workstream.

        :returns: Tuple of (status_code, response_json or None).
            The standard EspoCRM list response shape
            ``{"total": N, "list": [...]}`` is returned on success.
        """
        url = f"{self.profile.api_url}/Team?maxSize=200"
        return self._request("GET", url)

    def create_team(
        self, name: str, description: str | None = None,
    ) -> tuple[int, dict[str, Any] | None]:
        """Create a new Team record.

        :param name: Team name (operator-chosen identifier).
        :param description: Optional description text.
        :returns: Tuple of (status_code, created record or None).
        """
        payload: dict[str, Any] = {"name": name}
        if description is not None:
            payload["description"] = description
        return self.create_record("Team", payload)

    def update_team(
        self, team_id: str, description: str | None = None,
    ) -> tuple[int, dict[str, Any] | None]:
        """Update an existing Team record's description.

        Name is the team-identity key from YAML's perspective; this
        method intentionally does not accept a ``name`` parameter
        so the manager cannot accidentally trigger a server-side
        rename. The description is the only mutable field this
        workstream manages.

        :param team_id: Server-assigned Team record ID.
        :param description: New description text (or None to clear).
        :returns: Tuple of (status_code, response or None).
        """
        payload: dict[str, Any] = {"description": description}
        return self.patch_record("Team", team_id, payload)

    # --- Role management ---

    def get_roles(
        self,
    ) -> tuple[int, dict[str, Any] | None]:
        """List all Role records on the target instance.

        Bulk-fetches up to 200 roles in a single GET. Pagination
        beyond this is not implemented; documented as a future
        scaling concern matching ``get_teams``.

        :returns: Tuple of (status_code, response_json or None).
            Standard EspoCRM list shape ``{"total": N, "list": [...]}``
            on success.
        """
        url = f"{self.profile.api_url}/Role?maxSize=200"
        return self._request("GET", url)

    def create_role(
        self, payload: dict[str, Any],
    ) -> tuple[int, dict[str, Any] | None]:
        """Create a new Role record.

        Unlike ``create_team``, the payload is variable-shape (it
        carries the ``data`` JSON blob and the five system-permission
        columns), so this method takes the full payload dict directly
        rather than named parameters.

        :param payload: Full Role creation payload. Required keys
            depend on EspoCRM 9.x's Role record schema; the manager
            layer is responsible for constructing a valid payload.
        :returns: Tuple of (status_code, created record or None).
        """
        return self.create_record("Role", payload)

    def update_role(
        self, role_id: str, payload: dict[str, Any],
    ) -> tuple[int, dict[str, Any] | None]:
        """PATCH an existing Role record.

        Only the fields present in ``payload`` are updated; other
        fields are preserved. This is the semantic that lets the
        manager omit EspoCRM-only permissions (DEC-2) from the
        update path.

        :param role_id: Server-assigned Role record ID.
        :param payload: Partial Role update payload.
        :returns: Tuple of (status_code, response or None).
        """
        return self.patch_record("Role", role_id, payload)

    # --- Connection test ---

    def test_connection(self) -> tuple[bool, str]:
        """Test API connectivity by fetching metadata.

        :returns: Tuple of (success, message).
        """
        url = f"{self.profile.api_url}/Metadata?key=app.adminPanel"
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
