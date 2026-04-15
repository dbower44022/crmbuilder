"""EspoCRM Admin REST API client for field management."""

import base64
import hashlib
import hmac
import logging
from typing import Any
from urllib.parse import urlparse

import requests

from espo_impl.core.models import InstanceProfile

logger = logging.getLogger(__name__)


class EspoAdminClient:
    """EspoCRM Admin API client for field management.

    Supports API Key, HMAC, and Basic authentication methods.

    :param profile: Instance connection profile.
    :param timeout: Request timeout in seconds.
    """

    def __init__(self, profile: InstanceProfile, timeout: int = 30) -> None:
        self.profile = profile
        self.timeout = timeout
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
    ) -> tuple[int, dict[str, Any] | None]:
        """Execute an HTTP request with appropriate auth.

        :param method: HTTP method.
        :param url: Full request URL.
        :returns: Tuple of (status_code, response_json or None).
        """
        headers = kwargs.pop("headers", {})
        headers.update(self._hmac_header(method, url))

        try:
            resp = self.session.request(
                method, url, headers=headers, timeout=self.timeout, **kwargs
            )
            body = resp.json() if resp.content else None
            return resp.status_code, body
        except requests.exceptions.ConnectionError as exc:
            logger.error("Connection error: %s", exc)
            return -1, None
        except requests.exceptions.Timeout as exc:
            logger.error("Request timeout: %s", exc)
            return -1, None

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
