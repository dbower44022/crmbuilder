"""Operate vocabulary (PI-513 / REQ-591): the instance connection sets, the
deploy-configuration sets, the deploy-run lifecycle and phases, and the
provider set.

The four tables' CHECK constraints are built from these sets in the package
models module. ``access.vocab`` re-exports every name for the import paths
that predate the package; two Postgres revisions (0031, 0080) import them
through that path, so the re-export outlives the one-release shims
(segment-package-design.md, question 4).
"""

from __future__ import annotations

INSTANCE_VENDORS: frozenset[str] = frozenset({"espocrm"})

INSTANCE_ROLES: frozenset[str] = frozenset({"source", "target", "both"})

INSTANCE_AUTH_METHODS: frozenset[str] = frozenset({"api_key", "basic", "hmac"})

# PI-201 (REQ-172) — instance deploy/provisioning config. v1 supports only
# self-hosted (cloud-hosted / bring-your-own cannot be SSHed into); SSH auth is
# a key (path stored inline) or a password (keyring ref).
DEPLOY_CONFIG_SCENARIOS: frozenset[str] = frozenset({"self_hosted"})

DEPLOY_CONFIG_SSH_AUTH_TYPES: frozenset[str] = frozenset({"key", "password"})

INSTANCE_STATUSES: frozenset[str] = frozenset({"active", "disabled"})

# ---------------------------------------------------------------------------
# deploy_run (PI-419 — PRJ-111, REQ-522). One recorded execution of a
# provisioning job that creates a server, sets its DNS record, installs and
# verifies the CRM over SSH, and registers the resulting instance. Unlike a
# publish_run it is NOT born terminal: a deploy worker claims a ``queued`` run,
# holds it ``running`` with a heartbeat, and lands a terminal status —
# succeeded, succeeded_with_issues (verification found gaps), failed (a phase
# raised; everything built is kept and reported — DEC-945), or cancelled.
# ---------------------------------------------------------------------------
DEPLOY_RUN_STATUSES: frozenset[str] = frozenset(
    {
        "queued",
        "running",
        "succeeded",
        "succeeded_with_issues",
        "failed",
        "cancelled",
    }
)
DEPLOY_RUN_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"succeeded", "succeeded_with_issues", "failed", "cancelled"}
)
# The ordered deploy phases (each idempotent so an interrupted run resumes at
# the phase that did not complete). The tuple is the execution order; the
# frozenset backs the CHECK.
DEPLOY_RUN_PHASE_ORDER: tuple[str, ...] = (
    "validate",
    "create_droplet",
    "wait_droplet",
    "create_dns",
    "wait_dns",
    "server_prep",
    "install_espocrm",
    "post_install",
    "verify",
    "create_instance",
)
DEPLOY_RUN_PHASES: frozenset[str] = frozenset(DEPLOY_RUN_PHASE_ORDER)

# provider_credential (PI-419): an engagement-scoped API token for an
# infrastructure provider, stored as an opaque secret ref (REQ-157).
PROVIDER_CREDENTIAL_PROVIDERS: frozenset[str] = frozenset(
    {"digitalocean", "cloudflare"}
)
