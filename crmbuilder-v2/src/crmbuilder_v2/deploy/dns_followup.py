"""Check DNS now — PI-571 (REQ-651).

After a deploy that ended with open items, an operator presses Check DNS now
on the instance. This module does what that button promises:

* runs the DNS diagnostic (:func:`dns_check.diagnose`) for the instance's
  web address and server;
* reads the self-healing certificate job's status from the server over SSH;
* when DNS is correct and the certificate is not yet in place, starts the job
  at once, in the background, so the request returns quickly;
* rewrites the instance's open items — closing the ones that are resolved —
  and records the certificate's expiry once it exists.

It never changes DNS and never reinstalls anything itself; the job on the
server does the certificate work, so the rule that nothing stops the CRM
before a test certificate has passed is kept in one place.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from crmbuilder_v2 import secrets
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import FieldError, UnprocessableError
from crmbuilder_v2.access.repositories import instance_deploy_config, instances
from crmbuilder_v2.deploy import certificate_job, dns_check
from crmbuilder_v2.deploy.keys import private_key_file

_log = logging.getLogger("crmbuilder_v2.deploy.dns_followup")

#: Job states that need a person, and the ones that finish by themselves.
_JOB_NEEDS_ACTION = frozenset({"test_failed", "failed_restored", "gave_up"})


def _connect(cfg: dict[str, Any], key: str, ssh_module) -> Any:
    """Open SSH to the instance's server with its recorded key.

    ``key`` is the private key itself (a deploy run stores it as a secret) or,
    for a configuration entered by hand, the path of a key file.
    """
    config = ssh_module.SelfHostedConfig(
        ssh_host=cfg.get("ssh_host") or cfg.get("droplet_ip"),
        ssh_port=int(cfg.get("ssh_port") or 22),
        ssh_username=cfg.get("ssh_username") or "root",
        ssh_credential="",
        ssh_auth_type="key",
        domain=cfg.get("domain") or "",
        letsencrypt_email=cfg.get("letsencrypt_email") or "",
        db_password="",
        db_root_password="",
        admin_username="",
        admin_password="",
        admin_email="",
    )
    if "PRIVATE KEY" not in key:
        config.ssh_credential = key
        return ssh_module.connect_ssh(config)
    with private_key_file(key) as key_path:
        config.ssh_credential = key_path
        return ssh_module.connect_ssh(config)


def _certificate_item(state: str, title: str, found: str, action: str, who: str,
                      domain: str) -> dict[str, Any]:
    return {
        "key": "certificate",
        "step": "certificate",
        "state": state,
        "title": title,
        "found": found,
        "meaning": "The CRM must not be used until it has its certificate.",
        "action": action,
        "who": who,
        "verify": f"open https://{domain} in a browser; it should show a padlock.",
        "code": "certificate",
        "opened_at": datetime.now(UTC).isoformat(),
    }


def check_instance_dns(
    instance_identifier: str,
    *,
    lookup: dns_check.DnsLookup | None = None,
    ssh_module: Any = None,
    cert_job: Any = None,
    resolve_secret: Callable[[str], str] = secrets.get_secret,
) -> dict[str, Any]:
    """Diagnose DNS, advance the certificate, and update the open items."""
    if ssh_module is None:
        from crmbuilder_v2.deploy import ssh as ssh_module
    cert_job = cert_job or certificate_job
    with session_scope() as s:
        if instances.get_instance(s, instance_identifier) is None:
            raise UnprocessableError(
                [FieldError("instance", "not_found", f"{instance_identifier} does not exist")]
            )
        cfg = instance_deploy_config.get_deploy_config(s, instance_identifier)
    ip = (cfg or {}).get("droplet_ip") or (cfg or {}).get("ssh_host")
    if not cfg or not cfg.get("domain") or not ip:
        raise UnprocessableError(
            [FieldError("instance", "no_deploy_config",
                        f"{instance_identifier} has no recorded web address and server "
                        "address, so there is nothing to check")]
        )
    domain = cfg["domain"]
    diag = dns_check.diagnose(
        domain, ip, lookup=lookup,
        automatic_host="cloudflare" if cfg.get("dns_provider") == "cloudflare" else None,
    )

    job_status: dict[str, Any] | None = None
    expiry: str | None = None
    job_started = False
    ssh_error: str | None = None
    key_ref = cfg.get("ssh_credential_ref")
    if key_ref and (cfg.get("ssh_auth_type") or "key") == "key":
        try:
            key = resolve_secret(key_ref) if secrets.is_ref(key_ref) else key_ref
            client = _connect(cfg, key, ssh_module)
            try:
                expiry = cert_job.read_certificate_expiry(client, domain)
                job_status = cert_job.read_status(client)
                if (
                    expiry is None
                    and diag.is_correct
                    and (job_status or {}).get("state") not in ("installing", "gave_up")
                    and cert_job.job_installed(client)
                ):
                    cert_job.run_job_now(client, background=True)
                    job_started = True
            finally:
                client.close()
        except Exception as exc:  # the server may be down; the DNS answer still stands
            _log.warning("check-dns %s: SSH failed: %s", instance_identifier, exc)
            ssh_error = f"Could not reach the server over SSH: {exc}"

    items = {i["key"]: i for i in (cfg.get("open_items") or []) if isinstance(i, dict) and i.get("key")}
    if diag.is_correct:
        items.pop("dns", None)
    else:
        items["dns"] = {
            "key": "dns",
            "step": "check_dns",
            "state": "needs_action" if diag.state == dns_check.NEEDS_ACTION else "waiting",
            "title": diag.title,
            "found": diag.found,
            "meaning": diag.meaning,
            "action": diag.action,
            "who": diag.who,
            "verify": diag.verify,
            "code": diag.code,
            "opened_at": (items.get("dns") or {}).get("opened_at") or datetime.now(UTC).isoformat(),
        }
    if expiry:
        items.pop("certificate", None)
    elif job_started:
        items["certificate"] = _certificate_item(
            "waiting", "The certificate is being installed",
            "DNS is correct, so the certificate job was started just now.",
            "Nothing. Press Check DNS now again in a few minutes.",
            dns_check.WHO_NOBODY, domain,
        )
    elif job_status:
        state = job_status.get("state", "")
        text = certificate_job.STATE_TEXT.get(state, state)
        needs = state in _JOB_NEEDS_ACTION
        items["certificate"] = _certificate_item(
            "needs_action" if needs else "waiting",
            "The certificate could not be installed yet" if needs
            else "The certificate is waiting",
            f"{text} {job_status.get('detail') or ''}".strip(),
            "Fix the cause the detail names (often a firewall blocking port 80), then "
            "press Check DNS now." if needs else "Nothing, once DNS is correct.",
            dns_check.WHO_OPERATOR if needs else dns_check.WHO_NOBODY, domain,
        )

    fields: dict[str, Any] = {"open_items": list(items.values())}
    if expiry:
        fields["cert_expiry_date"] = expiry
    with session_scope() as s:
        instance_deploy_config.upsert_deploy_config(s, instance_identifier, **fields)

    return {
        "instance_identifier": instance_identifier,
        "domain": domain,
        "server_ip": ip,
        "dns": diag.to_dict(),
        "certificate_expiry": expiry,
        "certificate_job": job_status,
        "certificate_job_started": job_started,
        "ssh_error": ssh_error,
        "open_items": list(items.values()),
        "checked_at": datetime.now(UTC).isoformat(),
    }
