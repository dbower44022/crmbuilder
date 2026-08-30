"""Customer CRM instance provisioning — PI-419 (REQ-522, PRJ-111).

Service-side, Qt-free. Creates a server through a provider API, points DNS at
it, installs and verifies the CRM over SSH (reusing the v1 phases in
``automation.core.deployment.ssh_deploy`` unchanged), and registers the
resulting instance — executed as a *deploy run* by a *deploy worker*.

This package provisions **customers'** servers from an engagement's provider
credentials. Deploying CRMBuilder itself to its production host is human-only
(GVR-240 / DEC-946); the worker refuses that host.
"""
