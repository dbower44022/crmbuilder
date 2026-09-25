"""Operate request schemas (PI-513 / REQ-591): the instance, its deployment
configuration, the deploy run and the provider credential.

The shared ``api.schemas`` module re-exports these names for the import
paths that predate the package.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from crmbuilder_v2.api.schema_base import GovernanceEdgeIn, _Base


# --- Instance (CRM connection, PI-186 / PRJ-027) ---------------------------
# ``secret`` / ``secret_key`` are write-only plaintext inputs: the router
# stores them in the OS keyring and persists only the opaque reference
# (REQ-157). They are never echoed back. The keyring references are exposed on
# read responses as ``instance_secret_ref`` / ``instance_secret_key_ref`` (opaque).
class InstanceCreateIn(_Base):
    instance_name: str
    instance_url: str
    instance_vendor: str | None = None
    instance_role: str | None = None
    instance_auth_method: str | None = None
    secret: str | None = None
    secret_key: str | None = None
    instance_status: str | None = None
    instance_notes: str | None = None
    # PI-444 (REQ-546): the stored feature selection — design-entity
    # identifiers (ENT-NNN) active for this instance; null = full design.
    instance_feature_selection: list[str] | None = None
    instance_identifier: str | None = None
    references: list[GovernanceEdgeIn] | None = None
    timestamps: dict[str, Any] | None = None


class InstanceReplaceIn(_Base):
    instance_identifier: str | None = None
    instance_name: str
    instance_url: str
    instance_vendor: str | None = None
    instance_role: str | None = None
    instance_auth_method: str | None = None
    secret: str | None = None
    secret_key: str | None = None
    instance_status: str | None = None
    instance_notes: str | None = None
    instance_feature_selection: list[str] | None = None
    references: list[GovernanceEdgeIn] | None = None


class InstancePatchIn(_Base):
    instance_name: str | None = None
    instance_url: str | None = None
    instance_vendor: str | None = None
    instance_role: str | None = None
    instance_auth_method: str | None = None
    secret: str | None = None
    secret_key: str | None = None
    instance_status: str | None = None
    instance_notes: str | None = None
    instance_feature_selection: list[str] | None = None
    references: list[GovernanceEdgeIn] | None = None


# --- Instance deploy config (PI-201 / REQ-172) -----------------------------
# PUT body for /instances/{id}/deploy-config. Write-only plaintext secrets
# (``ssh_credential`` for password auth, ``db_root_password``) cross the REQ-157
# keyring boundary at the router and are never echoed back; for key auth
# ``ssh_credential`` is the key file path (stored inline, paths not sensitive).
# ``model_fields_set`` distinguishes an omitted key (leave unchanged) from an
# explicit null (clear), so partial updates work.
class InstanceDeployConfigIn(_Base):
    scenario: str | None = None
    ssh_host: str | None = None
    ssh_port: int | None = None
    ssh_username: str | None = None
    ssh_auth_type: str | None = None
    ssh_credential: str | None = None
    domain: str | None = None
    letsencrypt_email: str | None = None
    db_root_password: str | None = None
    admin_email: str | None = None
    current_espocrm_version: str | None = None
    latest_espocrm_version: str | None = None
    last_upgrade_at: str | None = None
    cert_expiry_date: str | None = None
    last_backup_paths: str | None = None
    backups_enabled: bool | None = None
    last_record_version: str | None = None
    domain_registrar: str | None = None
    dns_provider: str | None = None
    droplet_id: str | None = None
    # PI-419 (REQ-522): written by a deploy run; ``db_password`` /
    # ``admin_password`` are write-only plaintext like ``db_root_password``.
    db_password: str | None = None
    admin_username: str | None = None
    admin_password: str | None = None
    droplet_ip: str | None = None
    droplet_region: str | None = None
    droplet_size: str | None = None
    dns_record_id: str | None = None
    last_deploy_run_identifier: str | None = None
    # PI-442 (REQ-544): server-management facts — non-secret, operator-editable
    # (the runner writes what it knows at instance registration).
    hosting_provider: str | None = None
    hosting_account: str | None = None
    hosting_console_url: str | None = None
    dns_console_url: str | None = None
    ssh_key_public: str | None = None
    ssh_key_fingerprint: str | None = None
    ssh_key_name: str | None = None
    ssh_key_provider_id: str | None = None
    server_image: str | None = None
    provisioned_at: datetime | None = None
    last_verified_at: datetime | None = None
    backup_schedule: str | None = None
    backup_retention: str | None = None
    backup_destination: str | None = None
    monthly_cost_usd: float | None = None
    billing_note: str | None = None
    notes: str | None = None


# --- Deploy runs (PI-419 / REQ-522) ------------------------------------------
# POST body for /deploy-runs: the non-secret spec plus the three write-only
# passwords (DB passwords auto-generate when omitted). Validated by
# ``crmbuilder_v2.deploy.spec.validate_spec`` so the API and runner agree.
class DeployRunCreateIn(_Base):
    instance_name: str
    region: str
    size: str
    image: str
    ssh_key_ids: list[int | str] | None = None
    # PI-566 (REQ-642): ``cloudflare`` needs zone_id + zone_name + subdomain;
    # ``manual`` (manual DNS) needs the full address in ``domain`` instead.
    dns_mode: str = "cloudflare"
    zone_id: str | None = None
    zone_name: str | None = None
    subdomain: str | None = None
    domain: str | None = None
    letsencrypt_email: str
    admin_username: str = "admin"
    admin_email: str
    admin_password: str
    db_password: str | None = None
    db_root_password: str | None = None
    # PI-576 (REQ-653): the deployment this run builds. When set, the run
    # uses that deployment's credentials (falling back to the application's)
    # and attaches the instance it registers to it. Optional until the
    # deploy wizard creates the deployment first (PI-580).
    deployment_identifier: str | None = None


# POST body for /deploy-runs/{id}/retry (PI-571 / REQ-650): an optional
# corrected web address. Manual DNS sends ``domain``; Cloudflare mode sends
# ``subdomain`` (and may move to another zone with ``zone_id`` + ``zone_name``).
# An empty body retries unchanged.
class DeployRunRetryIn(_Base):
    domain: str | None = None
    subdomain: str | None = None
    zone_id: str | None = None
    zone_name: str | None = None


# --- Provider credentials (PI-419 / REQ-522) --------------------------------
# PUT body for /provider-credentials/{provider}: the write-only plaintext token
# crosses the secret boundary and only its opaque reference is stored.
class ProviderCredentialIn(_Base):
    token: str
    label: str | None = None


# --- Deployment (PI-576 / REQ-653, DEC-1155) ---------------------------------
# A deployment names its client, its application (the engagement identifier,
# defaulting to the active engagement) and its hosting provider, and holds an
# instance either by naming an existing one (``instance_identifier``) or by
# describing a new one (``instance``), created under the application in the
# same request. The instance's ``secret`` / ``secret_key`` are write-only
# plaintext that the router stores behind the secret boundary (REQ-157).
# ``deploy_config`` carries the non-secret configuration fields of
# ``PUT /instances/{id}/deploy-config``; the secret-bearing ones still go
# through that route.
class DeploymentInstanceIn(_Base):
    instance_name: str
    instance_url: str
    instance_vendor: str | None = None
    instance_role: str | None = None
    instance_auth_method: str | None = None
    secret: str | None = None
    secret_key: str | None = None
    instance_status: str | None = None
    instance_notes: str | None = None
    instance_feature_selection: list[str] | None = None


class DeploymentCreateIn(_Base):
    deployment_client: str
    deployment_name: str
    deployment_application: str | None = None
    deployment_hosting_provider: str | None = None
    deployment_status: str | None = None
    deployment_notes: str | None = None
    deployment_identifier: str | None = None
    instance_identifier: str | None = None
    instance: DeploymentInstanceIn | None = None
    deploy_config: dict[str, Any] | None = None


class DeploymentPatchIn(_Base):
    deployment_name: str | None = None
    deployment_status: str | None = None
    deployment_notes: str | None = None
    deployment_hosting_provider: str | None = None
    deployment_client: str | None = None

