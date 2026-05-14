"""CRUD and slot enforcement for ExtensionLicense / ExtensionInstall.

Reads and writes extension licenses and per-instance install records
from the per-client SQLite database. License keys round-trip through
the OS keyring so plaintext keys never live in the DB. Slot
enforcement counts current installs against the vendor's
per-environment caps (e.g., Advanced Pack: 1 prod + 2 non-prod)
and tells callers whether a given install would fit.

Re-installs on the same (instance, extension) pair do not consume a
fresh slot — the existing row is updated, and the slot it already
occupies stays counted but stays attributed to the same instance.

Companion to ``deploy_config_repo.py``; see _client_v13 in
``automation/db/migrations.py`` for the schema.
"""

from __future__ import annotations

import dataclasses
import logging
import sqlite3
from datetime import UTC, datetime

from automation.core import secrets

logger = logging.getLogger(__name__)


# ── Dataclasses ────────────────────────────────────────────────────────


@dataclasses.dataclass
class ExtensionLicense:
    """Hydrated license row with the key resolved from keyring.

    ``_license_key_ref`` preserves the keyring reference so updates
    can replace the key without touching other fields.
    """

    extension_name: str
    license_key: str
    purchaser_label: str | None = None
    max_production: int = 1
    max_nonproduction: int = 2
    notes: str | None = None
    id: int | None = None
    _license_key_ref: str | None = None


@dataclasses.dataclass
class ExtensionInstall:
    """One install record per (instance, extension)."""

    instance_id: int
    extension_name: str
    extension_version: str
    installed_at: str
    license_id: int | None = None
    last_verified_at: str | None = None
    source_zip_path: str | None = None
    id: int | None = None


@dataclasses.dataclass
class InstanceSlot:
    """Reference to an instance currently holding a license slot."""

    instance_id: int
    instance_code: str
    environment: str   # 'production' | 'staging' | 'test'
    extension_version: str


@dataclasses.dataclass
class SlotUsage:
    """Current slot usage for one license.

    ``production_installs`` and ``nonproduction_installs`` enumerate
    the instances currently consuming each pool. ``max_production`` and
    ``max_nonproduction`` mirror the vendor caps stored on the license.
    """

    license_id: int
    extension_name: str
    max_production: int
    max_nonproduction: int
    production_installs: list[InstanceSlot] = dataclasses.field(default_factory=list)
    nonproduction_installs: list[InstanceSlot] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class SlotCheckResult:
    """Result of checking whether installing on a target instance fits.

    When ``allowed`` is False, ``reason`` carries the message to show
    the operator. When ``is_reinstall`` is True the call does not
    consume a new slot regardless of cap state.
    """

    allowed: bool
    is_reinstall: bool
    reason: str | None
    usage: SlotUsage


# ── License CRUD ───────────────────────────────────────────────────────


def _license_row_to_obj(
    row: tuple, key_ref: str | None = None,
) -> ExtensionLicense:
    """Build an ExtensionLicense from a SELECT * row, resolving the key."""
    (
        id_,
        extension_name,
        license_key_ref,
        purchaser_label,
        max_production,
        max_nonproduction,
        notes,
        _created_at,
        _updated_at,
    ) = row
    ref = key_ref or license_key_ref
    return ExtensionLicense(
        id=id_,
        extension_name=extension_name,
        license_key=secrets.get_secret(ref),
        purchaser_label=purchaser_label,
        max_production=max_production,
        max_nonproduction=max_nonproduction,
        notes=notes,
        _license_key_ref=ref,
    )


_LICENSE_COLS = (
    "id, extension_name, license_key_ref, purchaser_label, "
    "max_production, max_nonproduction, notes, created_at, updated_at"
)


def save_license(
    conn: sqlite3.Connection, license_obj: ExtensionLicense,
) -> ExtensionLicense:
    """Insert or update a license. Persists the key to the keyring.

    On update, replaces the old keyring entry only when the
    ``license_key`` field actually changed. ``id`` may be None on
    insert; set on the returned object.

    :param conn: Per-client database connection.
    :param license_obj: License to save. Mutated in place to record
        the keyring reference and (on insert) the new row id.
    :returns: The same license object with refs and id populated.
    """
    if license_obj.id is not None:
        existing = load_license(conn, license_obj.id)
        if existing is None:
            raise ValueError(
                f"License id={license_obj.id} not found for update"
            )
        old_ref = existing._license_key_ref
        if license_obj.license_key != existing.license_key:
            new_ref = secrets.put_secret(license_obj.license_key)
            license_obj._license_key_ref = new_ref
        else:
            license_obj._license_key_ref = old_ref
            new_ref = old_ref

        conn.execute(
            "UPDATE ExtensionLicense SET "
            "    extension_name = ?, license_key_ref = ?, "
            "    purchaser_label = ?, max_production = ?, "
            "    max_nonproduction = ?, notes = ?, "
            "    updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (
                license_obj.extension_name,
                new_ref,
                license_obj.purchaser_label,
                license_obj.max_production,
                license_obj.max_nonproduction,
                license_obj.notes,
                license_obj.id,
            ),
        )
        conn.commit()
        if old_ref and old_ref != new_ref:
            secrets.delete_secret(old_ref)
        return license_obj

    ref = secrets.put_secret(license_obj.license_key)
    license_obj._license_key_ref = ref
    cursor = conn.execute(
        "INSERT INTO ExtensionLicense ("
        "    extension_name, license_key_ref, purchaser_label, "
        "    max_production, max_nonproduction, notes"
        ") VALUES (?, ?, ?, ?, ?, ?)",
        (
            license_obj.extension_name,
            ref,
            license_obj.purchaser_label,
            license_obj.max_production,
            license_obj.max_nonproduction,
            license_obj.notes,
        ),
    )
    conn.commit()
    license_obj.id = cursor.lastrowid
    return license_obj


def load_license(
    conn: sqlite3.Connection, license_id: int,
) -> ExtensionLicense | None:
    """Load a license by id, resolving its key from the keyring."""
    row = conn.execute(
        f"SELECT {_LICENSE_COLS} FROM ExtensionLicense WHERE id = ?",
        (license_id,),
    ).fetchone()
    if row is None:
        return None
    return _license_row_to_obj(row)


def find_license(
    conn: sqlite3.Connection,
    extension_name: str,
    purchaser_label: str | None = None,
) -> ExtensionLicense | None:
    """Look up a license by extension name and optional purchaser label.

    Convenience for the install flow, where the caller knows which
    extension is being installed but not the license id.
    """
    if purchaser_label is None:
        row = conn.execute(
            f"SELECT {_LICENSE_COLS} FROM ExtensionLicense "
            "WHERE extension_name = ? AND purchaser_label IS NULL",
            (extension_name,),
        ).fetchone()
    else:
        row = conn.execute(
            f"SELECT {_LICENSE_COLS} FROM ExtensionLicense "
            "WHERE extension_name = ? AND purchaser_label = ?",
            (extension_name, purchaser_label),
        ).fetchone()
    if row is None:
        return None
    return _license_row_to_obj(row)


def list_licenses(conn: sqlite3.Connection) -> list[ExtensionLicense]:
    """Return every license in insertion order."""
    rows = conn.execute(
        f"SELECT {_LICENSE_COLS} FROM ExtensionLicense ORDER BY id"
    ).fetchall()
    return [_license_row_to_obj(r) for r in rows]


# ── Install CRUD ───────────────────────────────────────────────────────


_INSTALL_COLS = (
    "id, instance_id, extension_name, extension_version, license_id, "
    "installed_at, last_verified_at, source_zip_path"
)


def _install_row_to_obj(row: tuple) -> ExtensionInstall:
    (
        id_,
        instance_id,
        extension_name,
        extension_version,
        license_id,
        installed_at,
        last_verified_at,
        source_zip_path,
    ) = row
    return ExtensionInstall(
        id=id_,
        instance_id=instance_id,
        extension_name=extension_name,
        extension_version=extension_version,
        license_id=license_id,
        installed_at=installed_at,
        last_verified_at=last_verified_at,
        source_zip_path=source_zip_path,
    )


def record_install(
    conn: sqlite3.Connection,
    *,
    instance_id: int,
    extension_name: str,
    extension_version: str,
    license_id: int | None = None,
    source_zip_path: str | None = None,
    installed_at: str | None = None,
) -> ExtensionInstall:
    """Upsert an install record for (instance, extension).

    Re-installs update the existing row in place, refreshing the
    version, license link, source path, and installed_at timestamp.
    """
    when = installed_at or datetime.now(UTC).isoformat()
    existing = load_install(conn, instance_id, extension_name)
    if existing is None:
        cursor = conn.execute(
            "INSERT INTO ExtensionInstall ("
            "    instance_id, extension_name, extension_version, "
            "    license_id, installed_at, source_zip_path"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (
                instance_id, extension_name, extension_version,
                license_id, when, source_zip_path,
            ),
        )
        conn.commit()
        return ExtensionInstall(
            id=cursor.lastrowid,
            instance_id=instance_id,
            extension_name=extension_name,
            extension_version=extension_version,
            license_id=license_id,
            installed_at=when,
            last_verified_at=None,
            source_zip_path=source_zip_path,
        )

    conn.execute(
        "UPDATE ExtensionInstall SET "
        "    extension_version = ?, license_id = ?, installed_at = ?, "
        "    source_zip_path = ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (extension_version, license_id, when, source_zip_path, existing.id),
    )
    conn.commit()
    existing.extension_version = extension_version
    existing.license_id = license_id
    existing.installed_at = when
    existing.source_zip_path = source_zip_path
    return existing


def update_verification(
    conn: sqlite3.Connection, install_id: int,
    *, when: str | None = None,
) -> None:
    """Stamp ``last_verified_at`` on an install record."""
    ts = when or datetime.now(UTC).isoformat()
    conn.execute(
        "UPDATE ExtensionInstall SET "
        "    last_verified_at = ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (ts, install_id),
    )
    conn.commit()


def load_install(
    conn: sqlite3.Connection,
    instance_id: int,
    extension_name: str,
) -> ExtensionInstall | None:
    """Load the install row for a specific (instance, extension) pair."""
    row = conn.execute(
        f"SELECT {_INSTALL_COLS} FROM ExtensionInstall "
        "WHERE instance_id = ? AND extension_name = ?",
        (instance_id, extension_name),
    ).fetchone()
    if row is None:
        return None
    return _install_row_to_obj(row)


def list_installs_for_instance(
    conn: sqlite3.Connection, instance_id: int,
) -> list[ExtensionInstall]:
    """Every extension installed on a given instance."""
    rows = conn.execute(
        f"SELECT {_INSTALL_COLS} FROM ExtensionInstall "
        "WHERE instance_id = ? ORDER BY extension_name",
        (instance_id,),
    ).fetchall()
    return [_install_row_to_obj(r) for r in rows]


def list_installs_for_license(
    conn: sqlite3.Connection, license_id: int,
) -> list[ExtensionInstall]:
    """Every install record currently bound to a given license."""
    rows = conn.execute(
        f"SELECT {_INSTALL_COLS} FROM ExtensionInstall "
        "WHERE license_id = ? ORDER BY instance_id",
        (license_id,),
    ).fetchall()
    return [_install_row_to_obj(r) for r in rows]


# ── Slot enforcement ───────────────────────────────────────────────────


# Production is its own pool; staging and test share the non-prod pool.
_NONPRODUCTION_ENVS = ("staging", "test")
_PRODUCTION_ENV = "production"


def get_slot_usage(
    conn: sqlite3.Connection, license_id: int,
) -> SlotUsage:
    """Compute current production / non-production slot consumption.

    Joins ExtensionInstall against Instance and groups by environment.
    """
    lic = load_license(conn, license_id)
    if lic is None:
        raise ValueError(f"License id={license_id} not found")

    rows = conn.execute(
        "SELECT i.id, i.code, i.environment, x.extension_version "
        "FROM ExtensionInstall x "
        "JOIN Instance i ON i.id = x.instance_id "
        "WHERE x.license_id = ? "
        "ORDER BY i.environment, i.code",
        (license_id,),
    ).fetchall()

    prod: list[InstanceSlot] = []
    nonprod: list[InstanceSlot] = []
    for instance_id, code, env, version in rows:
        slot = InstanceSlot(
            instance_id=instance_id,
            instance_code=code,
            environment=env,
            extension_version=version,
        )
        if env == _PRODUCTION_ENV:
            prod.append(slot)
        elif env in _NONPRODUCTION_ENVS:
            nonprod.append(slot)
        else:
            logger.warning(
                "Install %s on instance %s has unrecognized environment %r",
                lic.extension_name, code, env,
            )

    return SlotUsage(
        license_id=license_id,
        extension_name=lic.extension_name,
        max_production=lic.max_production,
        max_nonproduction=lic.max_nonproduction,
        production_installs=prod,
        nonproduction_installs=nonprod,
    )


def check_slot_availability(
    conn: sqlite3.Connection,
    license_id: int,
    target_instance_id: int,
) -> SlotCheckResult:
    """Determine whether installing on a target instance fits the license.

    Re-installs on an instance that already holds a slot are always
    allowed (the slot is already counted and stays attributed to the
    same instance). A first-time install on an instance must fit the
    cap for its environment pool.
    """
    usage = get_slot_usage(conn, license_id)
    lic = load_license(conn, license_id)
    if lic is None:
        raise ValueError(f"License id={license_id} not found")

    row = conn.execute(
        "SELECT code, environment FROM Instance WHERE id = ?",
        (target_instance_id,),
    ).fetchone()
    if row is None:
        raise ValueError(
            f"Target instance id={target_instance_id} not found"
        )
    target_code, target_env = row

    existing = load_install(conn, target_instance_id, lic.extension_name)
    is_reinstall = existing is not None and existing.license_id == license_id

    if is_reinstall:
        return SlotCheckResult(
            allowed=True, is_reinstall=True, reason=None, usage=usage,
        )

    if target_env == _PRODUCTION_ENV:
        if len(usage.production_installs) >= usage.max_production:
            occupant = ", ".join(
                s.instance_code for s in usage.production_installs
            )
            return SlotCheckResult(
                allowed=False, is_reinstall=False,
                reason=(
                    f"Production slot full ({len(usage.production_installs)}"
                    f"/{usage.max_production}): occupied by {occupant}. "
                    "Free a slot before installing on another production "
                    "instance."
                ),
                usage=usage,
            )
        return SlotCheckResult(
            allowed=True, is_reinstall=False, reason=None, usage=usage,
        )

    if target_env in _NONPRODUCTION_ENVS:
        if len(usage.nonproduction_installs) >= usage.max_nonproduction:
            occupant = ", ".join(
                s.instance_code for s in usage.nonproduction_installs
            )
            return SlotCheckResult(
                allowed=False, is_reinstall=False,
                reason=(
                    f"Non-production slots full "
                    f"({len(usage.nonproduction_installs)}"
                    f"/{usage.max_nonproduction}): occupied by {occupant}. "
                    "Free a slot before installing on another non-production "
                    "instance."
                ),
                usage=usage,
            )
        return SlotCheckResult(
            allowed=True, is_reinstall=False, reason=None, usage=usage,
        )

    return SlotCheckResult(
        allowed=False, is_reinstall=False,
        reason=(
            f"Instance {target_code!r} has unrecognized environment "
            f"{target_env!r}; expected one of "
            f"{_PRODUCTION_ENV}, {', '.join(_NONPRODUCTION_ENVS)}"
        ),
        usage=usage,
    )
