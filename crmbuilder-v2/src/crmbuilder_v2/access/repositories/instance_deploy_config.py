"""Instance deploy-config repository — PI-201 (REQ-172, PRJ-027).

A lightweight engagement-scoped 1:1 child of ``instance`` (no change_log / refs
participation), mirroring ``instance_membership.py``: engagement scoping is
applied by the session, so this repo just resolves, upserts, and deletes the
single config row per instance. Secret values are stored as opaque keyring
references in the ``*_ref`` columns; translation of plaintext secrets to refs is
the router's job (the REQ-157 boundary, as in ``instances``).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.exceptions import FieldError, UnprocessableError
from crmbuilder_v2.access.models import InstanceDeployConfig
from crmbuilder_v2.access.repositories import _governance as gov

# Columns an upsert may set (everything except the keys / timestamps).
_FIELDS: frozenset[str] = frozenset({
    "scenario", "ssh_host", "ssh_port", "ssh_username", "ssh_auth_type",
    "ssh_credential_ref", "domain", "letsencrypt_email", "db_root_password_ref",
    "admin_email", "current_espocrm_version", "latest_espocrm_version",
    "last_upgrade_at", "cert_expiry_date", "last_backup_paths", "backups_enabled",
    "last_record_version", "domain_registrar", "dns_provider", "droplet_id",
})


def _find(session: Session, instance_identifier: str) -> InstanceDeployConfig | None:
    return session.scalars(
        select(InstanceDeployConfig).where(
            InstanceDeployConfig.instance_identifier == instance_identifier
        )
    ).first()


def get_deploy_config(
    session: Session, instance_identifier: str
) -> dict | None:
    """Return the instance's deploy config, or ``None`` if it has none."""
    row = _find(session, instance_identifier)
    return to_dict(row) if row is not None else None


def upsert_deploy_config(
    session: Session, instance_identifier: str, **fields
) -> dict:
    """Create or replace the instance's single deploy-config row.

    Keyed on the instance within the active engagement. Supplied fields are set
    wholesale (an explicit ``None`` clears a column); omitted fields are left
    unchanged on an existing row. ``scenario`` defaults to ``self_hosted``.
    """
    instance_identifier = gov.require_nonempty(
        instance_identifier, field="instance_identifier"
    )
    unknown = set(fields) - _FIELDS
    if unknown:
        raise UnprocessableError(
            [FieldError("fields", "unknown_field",
                        f"unknown deploy-config fields: {sorted(unknown)}")]
        )
    if "scenario" in fields:
        gov.require_in(
            fields["scenario"], {"self_hosted"}, field="scenario"
        )
    if fields.get("ssh_auth_type") is not None:
        gov.require_in(
            fields["ssh_auth_type"], {"key", "password"}, field="ssh_auth_type"
        )

    row = _find(session, instance_identifier)
    if row is None:
        row = InstanceDeployConfig(
            instance_identifier=instance_identifier,
            scenario=fields.get("scenario") or "self_hosted",
        )
        session.add(row)
    for key, value in fields.items():
        setattr(row, key, value)
    session.flush()
    return to_dict(row)


def delete_deploy_config(session: Session, instance_identifier: str) -> None:
    """Hard-delete the instance's deploy config (child row, no soft-delete)."""
    row = _find(session, instance_identifier)
    if row is not None:
        session.delete(row)
        session.flush()


def backfill_from_notes(
    session: Session, instance_identifier: str, notes_json: str | None
) -> tuple[dict | None, str | None]:
    """Promote a ``deploy_config`` object stashed in an instance's notes JSON.

    Before PI-201, deploy/provisioning config was stashed as a JSON object under a
    ``deploy_config`` key inside ``instance_notes``. This parses it out, upserts a
    real config row, and returns ``(created_config_or_None, remaining_notes)`` —
    the remaining notes with the ``deploy_config`` key stripped (``None`` when
    nothing else remains), for the caller to write back. A safe no-op when the
    notes are absent, not JSON, or carry no recognised deploy fields.
    """
    import json

    if not notes_json:
        return None, notes_json
    try:
        data = json.loads(notes_json)
    except (ValueError, TypeError):
        return None, notes_json
    if not isinstance(data, dict) or not isinstance(
        data.get("deploy_config"), dict
    ):
        return None, notes_json
    fields = {k: v for k, v in data["deploy_config"].items() if k in _FIELDS}
    if not fields:
        return None, notes_json
    cfg = upsert_deploy_config(session, instance_identifier, **fields)
    remaining = {k: v for k, v in data.items() if k != "deploy_config"}
    return cfg, (json.dumps(remaining) if remaining else None)
