"""The Operate methods of the desktop storage client (PI-513 / REQ-591).
``ui.client.StorageClient`` is composed from every segment's mixin plus the
transport base, so these methods keep their names and callers see no change.
The mixin relies on the base's ``_request``. The audit, publish and
membership calls on an instance stay in the base: they are Build's.
"""

from __future__ import annotations

from typing import Any

from crmbuilder_v2.ui.exceptions import ServerError


class OperateMethods:
    """Instance, deploy-configuration, provider-credential and deploy-run
    calls; mixed into ``StorageClient``."""

    _request: Any  # supplied by the transport base

    # ------------------------------------------------------------------
    # Instances (CRM connections; PI-186 / PRJ-027)
    # ------------------------------------------------------------------

    def list_instances(
        self, *, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """Return all instances as a list of dicts.

        Shape matches ``crmbuilder_v2/api/routers/instances.py``. With
        ``include_deleted=True`` soft-deleted records are included.
        """
        path = "/instances"
        if include_deleted:
            path = "/instances?include_deleted=true"
        result = self._request("GET", path)
        if not isinstance(result, list):
            return []
        return result

    def get_instance(self, identifier: str) -> dict[str, Any]:
        """Return a single instance by identifier (e.g. ``"INST-001"``)."""
        result = self._request("GET", f"/instances/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for get_instance",
            )
        return result

    def create_instance(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /instances. Returns the created record dict.

        The body uses the parent-prefixed field names plus the write-only
        plaintext ``secret`` / ``secret_key`` inputs (stored in the keyring
        server-side, never echoed). ``instance_identifier`` is server-assigned
        when omitted.
        """
        result = self._request("POST", "/instances", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for create_instance",
            )
        return result

    def update_instance(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PUT /instances/{identifier} — full record replace.

        An omitted ``secret`` preserves the existing one (the router reads the
        current record); supplying a new plaintext rotates it.
        """
        result = self._request(
            "PUT", f"/instances/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for update_instance",
            )
        return result

    def patch_instance(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH /instances/{identifier} — partial update.

        Body should contain only changed fields. A ``secret`` / ``secret_key``
        present in the body rotates that keyring reference.
        """
        result = self._request(
            "PATCH", f"/instances/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for patch_instance",
            )
        return result

    def delete_instance(self, identifier: str) -> Any:
        """DELETE /instances/{identifier}. Soft-deletes; idempotent."""
        return self._request("DELETE", f"/instances/{identifier}")

    def restore_instance(self, identifier: str) -> dict[str, Any]:
        """POST /instances/{identifier}/restore. Clears the soft-delete."""
        result = self._request("POST", f"/instances/{identifier}/restore")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for restore_instance",
            )
        return result

    def next_instance_identifier(self) -> str:
        """GET /instances/next-identifier. Returns the next ``INST-NNN``."""
        result = self._request("GET", "/instances/next-identifier")
        if isinstance(result, dict) and isinstance(result.get("next"), str):
            return result["next"]
        raise ServerError(
            status_code=200,
            errors=[],
            message="Expected {'next': str} body for next_instance_identifier",
        )

    # --- deploy config (PI-201 / REQ-172) ------------------------------------

    def get_deploy_config(self, identifier: str) -> dict[str, Any] | None:
        """GET /instances/{id}/deploy-config — the config, or ``None`` if unset."""
        result = self._request("GET", f"/instances/{identifier}/deploy-config")
        return result if isinstance(result, dict) else None

    def put_deploy_config(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PUT /instances/{id}/deploy-config. Write-only plaintext secrets
        (``ssh_credential``, ``db_root_password``) cross the keyring boundary."""
        result = self._request(
            "PUT", f"/instances/{identifier}/deploy-config", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200, errors=[],
                message="Expected dict body for put_deploy_config",
            )
        return result

    def export_instance_records(
        self,
        identifier: str,
        entities: list[str],
        *,
        max_size: int | None = None,
    ) -> dict[str, Any]:
        """POST /instances/{id}/export-records (PI-234) — export selected seed/
        reference records into an import-ready artifact. Returns ``{artifact, log}``."""
        body: dict[str, Any] = {"entities": entities}
        if max_size is not None:
            body["max_size"] = max_size
        result = self._request(
            "POST", f"/instances/{identifier}/export-records", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200, errors=[],
                message="Expected dict body for export_instance_records",
            )
        return result

    # --- provider credentials (PI-419 / REQ-522) ------------------------------

    def list_provider_credentials(self) -> list[dict[str, Any]]:
        """GET /provider-credentials — configured flags per provider, never tokens."""
        result = self._request("GET", "/provider-credentials")
        return result if isinstance(result, list) else []

    def put_provider_credential(
        self, provider: str, token: str, label: str | None = None
    ) -> dict[str, Any]:
        """PUT /provider-credentials/{provider}. The plaintext token crosses the
        secret boundary once and is stored as an opaque reference."""
        body: dict[str, Any] = {"token": token}
        if label:
            body["label"] = label
        result = self._request(
            "PUT", f"/provider-credentials/{provider}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200, errors=[],
                message="Expected dict body for put_provider_credential",
            )
        return result

    def delete_provider_credential(self, provider: str) -> None:
        """DELETE /provider-credentials/{provider}."""
        self._request("DELETE", f"/provider-credentials/{provider}")

    def get_digitalocean_options(self) -> dict[str, Any]:
        """GET /provider-credentials/digitalocean/options — live catalog."""
        result = self._request("GET", "/provider-credentials/digitalocean/options")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200, errors=[],
                message="Expected dict body for get_digitalocean_options",
            )
        return result

    def list_cloudflare_zones(self) -> list[dict[str, Any]]:
        """GET /provider-credentials/cloudflare/zones."""
        result = self._request("GET", "/provider-credentials/cloudflare/zones")
        return result if isinstance(result, list) else []

    # --- deployments (PI-576 / REQ-653) ---------------------------------------

    def list_deployments(
        self,
        *,
        application: str | None = None,
        client: str | None = None,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        """GET /deployments — every deployment the principal may see, each
        composed with the instance, deploy configuration and credential
        flags it holds; narrowed to one application and/or client."""
        query: list[str] = []
        if application:
            query.append(f"application={application}")
        if client:
            query.append(f"client={client}")
        if include_deleted:
            query.append("include_deleted=true")
        path = "/deployments" + (f"?{'&'.join(query)}" if query else "")
        result = self._request("GET", path)
        return result if isinstance(result, list) else []

    def get_deployment(self, identifier: str) -> dict[str, Any]:
        """GET /deployments/{identifier}."""
        result = self._request("GET", f"/deployments/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200, errors=[],
                message="Expected dict body for get_deployment",
            )
        return result

    def create_deployment(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /deployments — create a deployment, optionally with its
        instance, in one request (201)."""
        result = self._request("POST", "/deployments", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200, errors=[],
                message="Expected dict body for create_deployment",
            )
        return result

    def patch_deployment(
        self, identifier: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH /deployments/{identifier}."""
        result = self._request(
            "PATCH", f"/deployments/{identifier}", json_body=fields
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200, errors=[],
                message="Expected dict body for patch_deployment",
            )
        return result

    def delete_deployment(self, identifier: str) -> None:
        """DELETE /deployments/{identifier} (soft delete)."""
        self._request("DELETE", f"/deployments/{identifier}")

    def restore_deployment(self, identifier: str) -> dict[str, Any]:
        """POST /deployments/{identifier}/restore."""
        result = self._request("POST", f"/deployments/{identifier}/restore")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200, errors=[],
                message="Expected dict body for restore_deployment",
            )
        return result

    def list_deployment_provider_credentials(
        self, identifier: str
    ) -> list[dict[str, Any]]:
        """GET /deployments/{identifier}/provider-credentials — the
        credentials that apply, each with its scope; never tokens."""
        result = self._request(
            "GET", f"/deployments/{identifier}/provider-credentials"
        )
        return result if isinstance(result, list) else []

    def put_deployment_provider_credential(
        self, identifier: str, provider: str, token: str, label: str | None = None
    ) -> list[dict[str, Any]]:
        """PUT /deployments/{identifier}/provider-credentials/{provider}."""
        body: dict[str, Any] = {"token": token}
        if label:
            body["label"] = label
        result = self._request(
            "PUT",
            f"/deployments/{identifier}/provider-credentials/{provider}",
            json_body=body,
        )
        return result if isinstance(result, list) else []

    def delete_deployment_provider_credential(
        self, identifier: str, provider: str
    ) -> None:
        """DELETE /deployments/{identifier}/provider-credentials/{provider}."""
        self._request(
            "DELETE", f"/deployments/{identifier}/provider-credentials/{provider}"
        )

    # --- deploy runs (PI-419 / REQ-522) ---------------------------------------

    def create_deploy_run(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /deploy-runs — queue a provisioning run (202)."""
        result = self._request("POST", "/deploy-runs", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200, errors=[],
                message="Expected dict body for create_deploy_run",
            )
        return result

    def list_deploy_runs(
        self,
        *,
        instance: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """GET /deploy-runs (newest first, log omitted)."""
        params = [f"{k}={v}" for k, v in (
            ("instance", instance), ("status", status), ("limit", limit)
        ) if v is not None]
        path = "/deploy-runs" + (f"?{'&'.join(params)}" if params else "")
        result = self._request("GET", path)
        return result if isinstance(result, list) else []

    def get_deploy_run(
        self, identifier: str, *, log_after: int | None = None
    ) -> dict[str, Any]:
        """GET /deploy-runs/{id}; ``log_after`` returns only new log lines."""
        path = f"/deploy-runs/{identifier}"
        if log_after is not None:
            path = f"{path}?log_after={log_after}"
        result = self._request("GET", path)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200, errors=[],
                message="Expected dict body for get_deploy_run",
            )
        return result

    def cancel_deploy_run(self, identifier: str) -> dict[str, Any]:
        """POST /deploy-runs/{id}/cancel."""
        result = self._request("POST", f"/deploy-runs/{identifier}/cancel")
        return result if isinstance(result, dict) else {}

    def retry_deploy_run(
        self, identifier: str, corrections: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """POST /deploy-runs/{id}/retry — Try again, optionally with a
        corrected web address (PI-571 / REQ-650)."""
        result = self._request(
            "POST", f"/deploy-runs/{identifier}/retry", json_body=corrections or None
        )
        return result if isinstance(result, dict) else {}

    def lookup_deploy_address(self, domain: str) -> dict[str, Any]:
        """GET /deploy-runs/dns-lookup — who hosts DNS for ``domain`` and what
        records it already has (PI-571 / REQ-648)."""
        from urllib.parse import quote

        result = self._request(
            "GET", f"/deploy-runs/dns-lookup?domain={quote(domain)}", timeout=60
        )
        return result if isinstance(result, dict) else {}

    def check_instance_dns(self, identifier: str) -> dict[str, Any]:
        """POST /instances/{id}/check-dns — Check DNS now (PI-571 / REQ-651)."""
        # DNS questions and an SSH login: allow longer than an ordinary call.
        result = self._request("POST", f"/instances/{identifier}/check-dns", timeout=120)
        return result if isinstance(result, dict) else {}

    def get_deploy_worker_status(self) -> dict[str, Any]:
        """GET /deploy-runs/worker."""
        result = self._request("GET", "/deploy-runs/worker")
        return result if isinstance(result, dict) else {}

    def _publish_request(
        self,
        path: str,
        scope: list[str] | None = None,
        *,
        allow_no_backup: bool = False,
        expected_plan_fingerprint: str | None = None,
        confirm_access_removal: bool = False,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if scope:
            body["scope"] = scope
        if allow_no_backup:
            body["allow_no_backup"] = True
        if expected_plan_fingerprint is not None:
            body["expected_plan_fingerprint"] = expected_plan_fingerprint
        if confirm_access_removal:
            body["confirm_access_removal"] = True
        result = self._request(
            "POST", path, json_body=body or None
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200, errors=[],
                message=f"Expected dict body for {path}",
            )
        return result


MIXIN = OperateMethods
