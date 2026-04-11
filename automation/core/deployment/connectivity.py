"""CRM connectivity and version checks — Qt-free, unit-testable.

Used by the cloud-hosted and bring-your-own wizard paths (§14.12.5.2)
and the self-hosted connectivity verification step.

L2 PRD v1.16 §14.12.5.2, §14.12.6.
"""

from __future__ import annotations

import dataclasses
import logging

import requests

logger = logging.getLogger(__name__)

# Supported EspoCRM versions — keyed by platform (§14.12.6).
# The wizard's compatibility check verifies the connected instance
# runs a version in this list.
SUPPORTED_VERSIONS: dict[str, list[str]] = {
    "EspoCRM": [
        "7.0", "7.1", "7.2", "7.3", "7.4", "7.5",
        "8.0", "8.1", "8.2", "8.3", "8.4", "8.5",
    ],
}


@dataclasses.dataclass
class ConnectivityResult:
    """Result of a connectivity check."""

    reachable: bool
    authenticated: bool
    platform_match: bool
    version: str | None
    version_supported: bool
    error: str | None


def check_espocrm_connectivity(
    url: str,
    username: str,
    password: str,
) -> ConnectivityResult:
    """Check connectivity to an EspoCRM instance.

    1. Reach the URL (HTTP GET).
    2. Authenticate via the EspoCRM REST API.
    3. Read the platform name and version.
    4. Verify version is in ``SUPPORTED_VERSIONS``.

    :param url: Base URL of the EspoCRM instance.
    :param username: Admin username.
    :param password: Admin password.
    :returns: ConnectivityResult.
    """
    base_url = url.rstrip("/")

    # Step 1: Reachability
    try:
        resp = requests.get(base_url, timeout=15, allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return ConnectivityResult(
            reachable=False, authenticated=False, platform_match=False,
            version=None, version_supported=False,
            error=f"Cannot reach {base_url}: {exc}",
        )

    # Step 2: Authenticated API call — GET /api/v1/App/user
    api_url = f"{base_url}/api/v1/App/user"
    try:
        resp = requests.get(
            api_url,
            auth=(username, password),
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if resp.status_code == 401:
            return ConnectivityResult(
                reachable=True, authenticated=False, platform_match=False,
                version=None, version_supported=False,
                error="Authentication failed — check username and password.",
            )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return ConnectivityResult(
            reachable=True, authenticated=False, platform_match=False,
            version=None, version_supported=False,
            error=f"API call failed: {exc}",
        )

    # Step 3: Read version from /api/v1/App/about
    version: str | None = None
    try:
        about_resp = requests.get(
            f"{base_url}/api/v1/App/about",
            auth=(username, password),
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if about_resp.ok:
            data = about_resp.json()
            version = data.get("version")
    except Exception:
        pass

    # Step 4: Version support check
    version_supported = False
    if version:
        # Match major.minor prefix
        major_minor = ".".join(version.split(".")[:2])
        version_supported = major_minor in SUPPORTED_VERSIONS.get("EspoCRM", [])

    return ConnectivityResult(
        reachable=True,
        authenticated=True,
        platform_match=True,  # If we got here, it responded to EspoCRM API
        version=version,
        version_supported=version_supported if version else True,
        error=None,
    )
