"""The validated request behind a deploy run — PI-419 (REQ-522).

``DeploySpec`` is what the API stores on ``deploy_runs.deploy_run_spec`` (never
a secret) and what the runner reads back. ``validate_spec`` is the single
place request shape is checked, so the API and the runner agree. The
protected-host guard lives here too: provisioning a *customer* server is this
feature's purpose, but the CRMBuilder production host is never a target
(GVR-240 / DEC-946).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from crmbuilder_v2.access.exceptions import FieldError, UnprocessableError

#: Hosts a deploy run must never touch: CRMBuilder's own production system.
PROTECTED_HOSTS: frozenset[str] = frozenset(
    {
        "138.197.72.15",
        "api.crmbuilder.ai",
        "mcp.crmbuilder.ai",
        "crmbuilder.ai",
        "crmbuilder.com",
    }
)

_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class DeploySpec:
    """Non-secret request for one deploy run."""

    instance_name: str
    region: str
    size: str
    image: str
    zone_id: str
    zone_name: str
    subdomain: str
    letsencrypt_email: str
    admin_username: str
    admin_email: str
    ssh_key_ids: list[int | str] = field(default_factory=list)
    domain: str = ""

    def __post_init__(self) -> None:
        if not self.domain:
            self.domain = f"{self.subdomain}.{self.zone_name}".lower()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeploySpec:
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})


def is_protected_host(value: str | None) -> bool:
    """Whether ``value`` (host or domain) is, or sits under, a protected host."""
    if not value:
        return False
    v = value.strip().lower().rstrip(".")
    return any(v == h or v.endswith("." + h) for h in PROTECTED_HOSTS)


def validate_spec(data: dict[str, Any]) -> DeploySpec:
    """Build a :class:`DeploySpec` from a request body, raising 422 on problems."""
    errors: list[FieldError] = []

    def need(key: str) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(FieldError(key, "required", f"{key} is required"))
            return ""
        return value.strip()

    instance_name = need("instance_name")
    region = need("region")
    size = need("size")
    image = need("image")
    zone_id = need("zone_id")
    zone_name = need("zone_name").lower()
    subdomain = need("subdomain").lower()
    letsencrypt_email = need("letsencrypt_email")
    admin_username = need("admin_username")
    admin_email = need("admin_email")
    ssh_key_ids = data.get("ssh_key_ids") or []
    if not isinstance(ssh_key_ids, list):
        errors.append(FieldError("ssh_key_ids", "invalid", "ssh_key_ids must be a list"))
        ssh_key_ids = []

    if subdomain and not all(_LABEL.match(part) for part in subdomain.split(".")):
        errors.append(
            FieldError("subdomain", "invalid", "subdomain must be DNS labels (a-z, 0-9, -)")
        )
    if zone_name and not all(_LABEL.match(part) for part in zone_name.split(".")):
        errors.append(FieldError("zone_name", "invalid", "zone_name is not a valid domain"))
    for key, value in (("letsencrypt_email", letsencrypt_email), ("admin_email", admin_email)):
        if value and not _EMAIL.match(value):
            errors.append(FieldError(key, "invalid", f"{key} is not an email address"))
    domain = f"{subdomain}.{zone_name}" if subdomain and zone_name else ""
    if is_protected_host(domain) or is_protected_host(zone_name):
        errors.append(
            FieldError(
                "subdomain",
                "protected_host",
                f"{domain or zone_name} is CRMBuilder's own production host; a "
                "deploy run never targets it (GVR-240)",
            )
        )
    if errors:
        raise UnprocessableError(errors)
    return DeploySpec(
        instance_name=instance_name,
        region=region,
        size=size,
        image=image,
        zone_id=zone_id,
        zone_name=zone_name,
        subdomain=subdomain,
        letsencrypt_email=letsencrypt_email,
        admin_username=admin_username,
        admin_email=admin_email,
        ssh_key_ids=list(ssh_key_ids),
        domain=domain,
    )
