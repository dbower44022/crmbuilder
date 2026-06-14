"""Instance endpoints — PI-186 entity (PRJ-027).

Standard eight-endpoint set delegating to
:mod:`crmbuilder_v2.access.repositories.instances`. This router owns the
secret boundary (REQ-157): the write-only plaintext ``secret`` / ``secret_key``
inputs are stored in the OS keyring via :mod:`crmbuilder_v2.secrets` and only
the opaque references reach the data layer; plaintext is never persisted and
never echoed back. Request bodies may also carry an inline ``references`` array
and, on a backfill create, a ``timestamps`` dict. All responses use the
``{data, meta, errors}`` envelope.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2 import secrets
from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import instances
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    InstanceCreateIn,
    InstancePatchIn,
    InstanceReplaceIn,
)

router = APIRouter(prefix="/instances", tags=["instances"])
_FIELD_PREFIX = "instance_"


def _edges(body) -> list[dict] | None:
    return [e.model_dump() for e in body.references] if body.references else None


def _store(value: str | None) -> str | None:
    """Store a plaintext secret in the keyring, returning its opaque reference.

    :param value: A plaintext secret, or ``None``/empty for no secret.
    :returns: The keyring reference, or ``None`` when no secret was supplied.
    """
    return secrets.put_secret(value) if value else None


@router.get("")
def list_all(
    include_deleted: bool = False,
    status: str | None = None,
    role: str | None = None,
):
    with readonly_session() as s:
        return ok(
            instances.list_instances(
                s, include_deleted=include_deleted, status=status, role=role
            )
        )


@router.get("/next-identifier")
def next_identifier():
    with readonly_session() as s:
        return ok({"next": instances.next_instance_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = instances.get_instance(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("instance", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: InstanceCreateIn):
    with writable_session() as s:
        return ok(
            instances.create_instance(
                s,
                name=body.instance_name,
                url=body.instance_url,
                vendor=body.instance_vendor or "espocrm",
                role=body.instance_role or "both",
                auth_method=body.instance_auth_method or "api_key",
                secret_ref=_store(body.secret),
                secret_key_ref=_store(body.secret_key),
                status=body.instance_status or "active",
                notes=body.instance_notes,
                identifier=body.instance_identifier,
                references=_edges(body),
                timestamps=body.timestamps,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: InstanceReplaceIn):
    with writable_session() as s:
        current = instances.get_instance(s, identifier, include_deleted=True)
        if current is None:
            raise NotFoundError("instance", identifier)
        # PUT preserves the existing secret unless a new plaintext is supplied.
        if body.secret is not None:
            secret_ref = _store(body.secret)
            secrets.delete_secret(current.get("instance_secret_ref"))
        else:
            secret_ref = current.get("instance_secret_ref")
        if body.secret_key is not None:
            secret_key_ref = _store(body.secret_key)
            secrets.delete_secret(current.get("instance_secret_key_ref"))
        else:
            secret_key_ref = current.get("instance_secret_key_ref")
        return ok(
            instances.update_instance(
                s,
                identifier,
                instance_identifier=body.instance_identifier,
                name=body.instance_name,
                url=body.instance_url,
                vendor=body.instance_vendor or "espocrm",
                role=body.instance_role or "both",
                auth_method=body.instance_auth_method or "api_key",
                secret_ref=secret_ref,
                secret_key_ref=secret_key_ref,
                status=body.instance_status or "active",
                notes=body.instance_notes,
                references=_edges(body),
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: InstancePatchIn):
    provided = body.model_dump(exclude_unset=True)
    references = provided.pop("references", None)
    has_secret = "secret" in provided
    has_secret_key = "secret_key" in provided
    secret = provided.pop("secret", None)
    secret_key = provided.pop("secret_key", None)
    fields = {key[len(_FIELD_PREFIX):]: value for key, value in provided.items()}
    with writable_session() as s:
        current = instances.get_instance(s, identifier, include_deleted=True)
        if current is None:
            raise NotFoundError("instance", identifier)
        if has_secret:
            secrets.delete_secret(current.get("instance_secret_ref"))
            fields["secret_ref"] = _store(secret)
        if has_secret_key:
            secrets.delete_secret(current.get("instance_secret_key_ref"))
            fields["secret_key_ref"] = _store(secret_key)
        return ok(
            instances.patch_instance(s, identifier, references=references, **fields)
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(instances.delete_instance(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(instances.restore_instance(s, identifier))
