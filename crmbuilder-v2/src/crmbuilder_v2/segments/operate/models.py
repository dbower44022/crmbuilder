"""Operate tables (PI-513 / REQ-591): the instance, its deployment
configuration, the provider credential and the deploy run.

Built on the one ``Base`` from ``access.base``; the shared ``access.models``
module re-exports these names and loads this module through the segment
registry so the tables register on ``Base.metadata`` for Alembic and
``create_all``. This module never imports ``access.models``. The instance
membership table stays in the shared module: it belongs to Build.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from crmbuilder_v2.access.base import (
    Base,
    EngagementScopedMixin,
    EngagementScopedPKMixin,
    JSONColumnNoneAsNull,
    _IdentifierFormatCheck,
    _utcnow,
)
from crmbuilder_v2.access.vocab import _check_in
from crmbuilder_v2.segments.operate.vocab import (
    DEPLOY_CONFIG_SCENARIOS,
    DEPLOY_CONFIG_SSH_AUTH_TYPES,
    DEPLOY_RUN_PHASES,
    DEPLOY_RUN_STATUSES,
    INSTANCE_AUTH_METHODS,
    INSTANCE_ROLES,
    INSTANCE_STATUSES,
    INSTANCE_VENDORS,
    PROVIDER_CREDENTIAL_PROVIDERS,
)

__all__ = [
    "DeployRun",
    "Instance",
    "InstanceDeployConfig",
    "ProviderCredential",
]


class Instance(EngagementScopedPKMixin, Base):
    """PI-186 entity (PRJ-027) — one engagement-scoped connection to a live CRM.

    An engagement defines one or more instances (identifier ``INST-NNN``), each
    pointing at a real CRM system. Audit (pull) reverse-engineers a source
    instance's structure into the canonical engine-neutral inventory; publish
    (push, PRJ-025) writes design to a target instance. See
    ``prj-027-multi-instance-audit-inventory-architecture.md`` §3.

    Parent-prefix field naming (DEC-046); the prefixed-string identifier is the
    primary key (no integer surrogate), matching the methodology/governance
    entity precedent. ``instance_vendor`` selects the introspection/adapter
    driver. ``instance_role`` mirrors the V1 ``InstanceRole``: a ``source`` to
    read from, a ``target`` to write to, or ``both``.

    **Secrets are never stored on this row** (REQ-157). The two ``*_secret_ref``
    columns hold only opaque ``crmbuilder:{uuid}`` keyring references resolved at
    connection time via :mod:`crmbuilder_v2.secrets`; the plaintext values live
    in the OS keyring. ``instance_secret_ref`` carries the API key or password;
    ``instance_secret_key_ref`` carries the HMAC secret key when
    ``instance_auth_method`` is ``hmac``.
    """

    __tablename__ = "instances"

    instance_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    instance_name: Mapped[str] = mapped_column(String(255), nullable=False)
    instance_vendor: Mapped[str] = mapped_column(
        String(16), nullable=False, default="espocrm"
    )
    instance_url: Mapped[str] = mapped_column(Text, nullable=False)
    instance_role: Mapped[str] = mapped_column(
        String(16), nullable=False, default="both"
    )
    instance_auth_method: Mapped[str] = mapped_column(
        String(16), nullable=False, default="api_key"
    )
    instance_secret_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    instance_secret_key_ref: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    instance_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )
    instance_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # PI-444 (REQ-546 / DEC-977) — the chapter's stored feature selection: the
    # entity identifiers (``ENT-NNN``) of the canonical design that are active
    # for this instance. NULL means no selection (publish the full design —
    # today's behaviour). Entity identifiers, not generated program filenames,
    # so a design-entity rename cannot silently detach the selection; publish
    # resolves identifiers to filenames at run time.
    instance_feature_selection: Mapped[list | None] = mapped_column(
        JSONColumnNoneAsNull, nullable=True
    )
    # PI-412 / REQ-498 — the design-version stamp as last READ from the
    # instance's carrier record by the audit (REQ-495's stamp is what the
    # instance holds; these columns are the fleet view's queryable copy of
    # that reading, never a substitute for it). A failed read leaves them
    # untouched; ``instance_stamp_read_at`` says how old the reading is.
    instance_standard_version: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    instance_plan_fingerprint: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    instance_stamp_read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    instance_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    instance_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    instance_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^INST-\d{3}$`` expressed as a SQLite GLOB / PG regex pattern.
        CheckConstraint(
            _IdentifierFormatCheck("instance_identifier", ["INST"]),
            name="ck_instance_identifier_format",
        ),
        CheckConstraint(
            _check_in("instance_vendor", INSTANCE_VENDORS),
            name="ck_instance_vendor",
        ),
        CheckConstraint(
            _check_in("instance_role", INSTANCE_ROLES),
            name="ck_instance_role",
        ),
        CheckConstraint(
            _check_in("instance_auth_method", INSTANCE_AUTH_METHODS),
            name="ck_instance_auth_method",
        ),
        CheckConstraint(
            _check_in("instance_status", INSTANCE_STATUSES),
            name="ck_instance_status",
        ),
        Index("ix_instances_instance_status", "instance_status"),
        Index("ix_instances_instance_deleted_at", "instance_deleted_at"),
    )




class InstanceDeployConfig(EngagementScopedMixin, Base):
    """PI-201 (REQ-172, PRJ-027) — an instance's deploy/provisioning config.

    A lightweight engagement-scoped child of ``instance`` (1:1, ``UNIQUE`` on the
    instance), **not** a prefixed-identifier governance entity (no change_log /
    refs participation) — mirroring ``InstanceMembership``. Carries the SSH
    connection, hosting/DNS metadata, version tracking, and backup state for a
    self-hosted instance (REQ-172), ported from the V1 ``InstanceDeployConfig``.
    Secrets live in the OS keyring: ``ssh_credential_ref`` holds a keyring
    reference for a password auth (or the key file path inline for key auth,
    paths not being sensitive the same way), ``db_root_password_ref`` a keyring
    reference — the same REQ-157 pattern as the instance API credential.
    """

    __tablename__ = "instance_deploy_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instance_identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    scenario: Mapped[str] = mapped_column(
        String(16), nullable=False, default="self_hosted"
    )
    ssh_host: Mapped[str | None] = mapped_column(Text, nullable=True)
    ssh_port: Mapped[int | None] = mapped_column(Integer, nullable=True, default=22)
    ssh_username: Mapped[str | None] = mapped_column(Text, nullable=True)
    ssh_auth_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ssh_credential_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    letsencrypt_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    db_root_password_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_espocrm_version: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    latest_espocrm_version: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    last_upgrade_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cert_expiry_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_backup_paths: Mapped[str | None] = mapped_column(Text, nullable=True)
    backups_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_record_version: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    domain_registrar: Mapped[str | None] = mapped_column(Text, nullable=True)
    dns_provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    droplet_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # PI-419 (REQ-522) — facts a deploy run writes when it provisions the
    # server itself: the CRM admin login (secret ref + username; the same
    # password backs the instance's basic-auth credential), the application
    # DB password ref (the installer needs both DB passwords), the droplet's
    # public IP / region / size, the DNS record it created, and the run that
    # last provisioned or re-provisioned this instance.
    db_password_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_username: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_password_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    droplet_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    droplet_region: Mapped[str | None] = mapped_column(String(32), nullable=True)
    droplet_size: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dns_record_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_deploy_run_identifier: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    # PI-442 (REQ-544) — the server-management facts a human admin or an AI
    # agent needs without hunting through provider consoles: who hosts the
    # server and under which account, where its consoles are, the identity of
    # the SSH key that grants access (the private half stays a secret ref in
    # ``ssh_credential_ref``), the OS image, and when it was provisioned and
    # last verified reachable. The runner writes what it knows at instance
    # registration; the rest — backup policy, cost, billing and free-form
    # notes — are operator-editable via the deploy-config endpoint. All
    # nullable, never backfilled (DEC-971).
    hosting_provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    hosting_account: Mapped[str | None] = mapped_column(Text, nullable=True)
    hosting_console_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    dns_console_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ssh_key_public: Mapped[str | None] = mapped_column(Text, nullable=True)
    ssh_key_fingerprint: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    ssh_key_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    ssh_key_provider_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    server_image: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provisioned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # PI-571 (REQ-650, REQ-651): what is still outstanding on the instance
    # after its deploy — typically the DNS record and the certificate. A list
    # of objects, each with a key, a title, what was found, what to do, who
    # acts, how to confirm, and whether it is open. Written by the deploy run
    # and by Check DNS now; NULL on rows that predate the column.
    open_items: Mapped[list | None] = mapped_column(
        JSONColumnNoneAsNull, nullable=True
    )
    backup_schedule: Mapped[str | None] = mapped_column(Text, nullable=True)
    backup_retention: Mapped[str | None] = mapped_column(Text, nullable=True)
    backup_destination: Mapped[str | None] = mapped_column(Text, nullable=True)
    monthly_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    billing_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["engagement_id", "instance_identifier"],
            ["instances.engagement_id", "instances.instance_identifier"],
            ondelete="CASCADE",
            name="fk_instance_deploy_configs_instance",
        ),
        UniqueConstraint(
            "engagement_id",
            "instance_identifier",
            name="uq_instance_deploy_config",
        ),
        CheckConstraint(
            _check_in("scenario", DEPLOY_CONFIG_SCENARIOS),
            name="ck_instance_deploy_config_scenario",
        ),
        CheckConstraint(
            _check_in("ssh_auth_type", DEPLOY_CONFIG_SSH_AUTH_TYPES),
            name="ck_instance_deploy_config_ssh_auth_type",
        ),
    )




class DeployRun(EngagementScopedMixin, Base):
    """PI-419 (REQ-522, PRJ-111) — one recorded execution of a provisioning job.

    A lean engagement-scoped operational log (integer PK plus a friendly
    ``DEP-NNN`` identifier; **not** a prefixed-identifier governance entity — no
    ``change_log`` / ``refs`` participation, mirroring ``PublishRun``). Unlike a
    publish run it is *not* born terminal: it is created ``queued``, a deploy
    worker claims it (``deploy_run_worker_id`` + heartbeat) and drives it through
    the ordered deploy phases, and a terminal status lands at the end. The
    ``state`` JSON is the resume checkpoint — what has already been created
    (droplet id / IP, DNS record, SSH key), per-phase outcomes, verification
    results, and the cancel flag — so a run abandoned by a restarted service is
    reclaimed and resumed at the phase that did not complete. ``spec`` holds the
    non-secret request; ``secret_refs`` only opaque secret references (REQ-157);
    ``log`` a capped list of ``[timestamp, level, message]`` lines, already
    masked. ``instance_identifier`` is null until the run registers the instance.
    """

    __tablename__ = "deploy_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deploy_run_identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    instance_identifier: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    deploy_run_status: Mapped[str] = mapped_column(String(24), nullable=False)
    deploy_run_phase: Mapped[str | None] = mapped_column(String(32), nullable=True)
    deploy_run_spec: Mapped[dict | None] = mapped_column(
        JSONColumnNoneAsNull, nullable=True
    )
    deploy_run_secret_refs: Mapped[dict | None] = mapped_column(
        JSONColumnNoneAsNull, nullable=True
    )
    deploy_run_state: Mapped[dict | None] = mapped_column(
        JSONColumnNoneAsNull, nullable=True
    )
    deploy_run_log: Mapped[list | None] = mapped_column(
        JSONColumnNoneAsNull, nullable=True
    )
    deploy_run_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # PI-442 (REQ-544) — which hosting provider this run provisioned against,
    # stamped at creation so the history row is self-describing. Free text
    # (no CHECK): the run's provider is the service's choice today
    # (``digitalocean``) but the history must be able to name any provider a
    # future runner uses. NULL on rows that predate the column.
    deploy_run_provider: Mapped[str | None] = mapped_column(
        String(24), nullable=True
    )
    deploy_run_requested_by: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    deploy_run_worker_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    deploy_run_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deploy_run_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deploy_run_ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("deploy_run_identifier", ["DEP"]),
            name="ck_deploy_run_identifier_format",
        ),
        CheckConstraint(
            _check_in("deploy_run_status", DEPLOY_RUN_STATUSES),
            name="ck_deploy_run_status",
        ),
        CheckConstraint(
            _check_in("deploy_run_phase", DEPLOY_RUN_PHASES),
            name="ck_deploy_run_phase",
        ),
        UniqueConstraint(
            "engagement_id",
            "deploy_run_identifier",
            name="uq_deploy_run_identifier",
        ),
        Index("ix_deploy_runs_status", "engagement_id", "deploy_run_status"),
        Index("ix_deploy_runs_instance", "engagement_id", "instance_identifier"),
    )




class ProviderCredential(EngagementScopedMixin, Base):
    """PI-419 (REQ-522, PRJ-111) — an engagement's infrastructure-provider token.

    One row per (engagement, provider) — DigitalOcean or Cloudflare — holding
    only an opaque secret reference (REQ-157; the ciphertext lives in
    ``secret_values``) plus a human label. A lightweight engagement-scoped
    child (no change_log / refs participation), like ``InstanceDeployConfig``.
    CRMBuilder's own accounts are entered as an engagement's credentials by
    default; a customer may replace them with its own (DEC-945).
    """

    __tablename__ = "provider_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(24), nullable=False)
    token_ref: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            _check_in("provider", PROVIDER_CREDENTIAL_PROVIDERS),
            name="ck_provider_credential_provider",
        ),
        UniqueConstraint(
            "engagement_id", "provider", name="uq_provider_credential_provider"
        ),
    )


