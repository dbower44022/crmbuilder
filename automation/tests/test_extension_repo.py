"""Tests for ExtensionLicense / ExtensionInstall CRUD and slot enforcement."""

from __future__ import annotations

import os
import sqlite3
import tempfile

import pytest

# Force in-memory keyring before importing the module under test.
os.environ["CRMBUILDER_KEYRING_DISABLE"] = "1"

from automation.core import secrets  # noqa: E402
from automation.core.deployment.extension_repo import (  # noqa: E402
    ExtensionLicense,
    check_slot_availability,
    find_license,
    get_slot_usage,
    list_installs_for_instance,
    list_installs_for_license,
    list_licenses,
    load_install,
    load_license,
    record_install,
    save_license,
    update_verification,
)
from automation.db.migrations import run_client_migrations  # noqa: E402


@pytest.fixture
def conn():
    """Fresh client DB with all migrations applied."""
    secrets._reset_in_memory_store_for_tests()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    c = run_client_migrations(db_path)
    yield c
    c.close()
    os.unlink(db_path)


def _make_instance(c: sqlite3.Connection, code: str, env: str) -> int:
    c.execute(
        "INSERT INTO Instance (name, code, environment) VALUES (?, ?, ?)",
        (code, code, env),
    )
    c.commit()
    return c.execute(
        "SELECT id FROM Instance WHERE code = ?", (code,),
    ).fetchone()[0]


# ── License CRUD ───────────────────────────────────────────────────────


class TestLicenseCrud:
    def test_save_insert_then_load(self, conn):
        lic = save_license(conn, ExtensionLicense(
            extension_name="advanced-pack",
            license_key="SECRET-KEY-123",
            purchaser_label="CBM",
        ))
        assert lic.id is not None
        assert lic._license_key_ref is not None

        loaded = load_license(conn, lic.id)
        assert loaded is not None
        assert loaded.license_key == "SECRET-KEY-123"
        assert loaded.extension_name == "advanced-pack"
        assert loaded.purchaser_label == "CBM"
        assert loaded.max_production == 1
        assert loaded.max_nonproduction == 2

    def test_save_update_metadata_only(self, conn):
        lic = save_license(conn, ExtensionLicense(
            extension_name="advanced-pack",
            license_key="KEY-A",
        ))
        original_ref = lic._license_key_ref

        lic.notes = "Renewed 2026-05"
        lic.max_nonproduction = 3
        save_license(conn, lic)

        # Same key, same ref — keyring not rotated
        assert lic._license_key_ref == original_ref
        assert secrets.get_secret(original_ref) == "KEY-A"

        loaded = load_license(conn, lic.id)
        assert loaded.notes == "Renewed 2026-05"
        assert loaded.max_nonproduction == 3

    def test_save_update_rotates_key(self, conn):
        lic = save_license(conn, ExtensionLicense(
            extension_name="advanced-pack",
            license_key="OLD-KEY",
        ))
        old_ref = lic._license_key_ref

        lic.license_key = "NEW-KEY"
        save_license(conn, lic)

        assert lic._license_key_ref != old_ref
        loaded = load_license(conn, lic.id)
        assert loaded.license_key == "NEW-KEY"

        # Old keyring entry removed
        with pytest.raises(KeyError):
            secrets.get_secret(old_ref)

    def test_find_license_by_name(self, conn):
        save_license(conn, ExtensionLicense(
            extension_name="advanced-pack", license_key="K1",
            purchaser_label="Client A",
        ))
        save_license(conn, ExtensionLicense(
            extension_name="advanced-pack", license_key="K2",
            purchaser_label="Client B",
        ))

        a = find_license(conn, "advanced-pack", "Client A")
        b = find_license(conn, "advanced-pack", "Client B")
        assert a is not None and a.license_key == "K1"
        assert b is not None and b.license_key == "K2"
        assert find_license(conn, "no-such-ext") is None

    def test_list_licenses(self, conn):
        save_license(conn, ExtensionLicense(
            extension_name="advanced-pack", license_key="K1",
        ))
        save_license(conn, ExtensionLicense(
            extension_name="other-pack", license_key="K2",
        ))
        names = [l.extension_name for l in list_licenses(conn)]
        assert names == ["advanced-pack", "other-pack"]

    def test_unique_constraint(self, conn):
        save_license(conn, ExtensionLicense(
            extension_name="advanced-pack", license_key="K1",
            purchaser_label="CBM",
        ))
        with pytest.raises(sqlite3.IntegrityError):
            save_license(conn, ExtensionLicense(
                extension_name="advanced-pack", license_key="K2",
                purchaser_label="CBM",
            ))


# ── Install CRUD ───────────────────────────────────────────────────────


class TestInstallCrud:
    def test_record_install_insert(self, conn):
        inst = _make_instance(conn, "PROD", "production")
        install = record_install(
            conn,
            instance_id=inst,
            extension_name="advanced-pack",
            extension_version="3.12.1",
            source_zip_path="/tmp/x.zip",
        )
        assert install.id is not None
        assert install.installed_at is not None

        loaded = load_install(conn, inst, "advanced-pack")
        assert loaded is not None
        assert loaded.extension_version == "3.12.1"
        assert loaded.source_zip_path == "/tmp/x.zip"
        assert loaded.last_verified_at is None

    def test_record_install_reinstall_updates(self, conn):
        inst = _make_instance(conn, "PROD", "production")
        first = record_install(
            conn, instance_id=inst, extension_name="advanced-pack",
            extension_version="3.12.0",
        )
        second = record_install(
            conn, instance_id=inst, extension_name="advanced-pack",
            extension_version="3.12.1",
        )
        assert first.id == second.id
        loaded = load_install(conn, inst, "advanced-pack")
        assert loaded.extension_version == "3.12.1"

        rows = conn.execute(
            "SELECT COUNT(*) FROM ExtensionInstall"
        ).fetchone()
        assert rows[0] == 1

    def test_update_verification(self, conn):
        inst = _make_instance(conn, "PROD", "production")
        record_install(
            conn, instance_id=inst, extension_name="advanced-pack",
            extension_version="3.12.1",
        )
        install = load_install(conn, inst, "advanced-pack")
        update_verification(conn, install.id, when="2026-05-13T10:00:00+00:00")
        reloaded = load_install(conn, inst, "advanced-pack")
        assert reloaded.last_verified_at == "2026-05-13T10:00:00+00:00"

    def test_list_by_instance_and_license(self, conn):
        prod = _make_instance(conn, "PROD", "production")
        stage = _make_instance(conn, "STAGE", "staging")
        lic = save_license(conn, ExtensionLicense(
            extension_name="advanced-pack", license_key="K",
        ))
        record_install(
            conn, instance_id=prod, extension_name="advanced-pack",
            extension_version="3.12.1", license_id=lic.id,
        )
        record_install(
            conn, instance_id=stage, extension_name="advanced-pack",
            extension_version="3.12.1", license_id=lic.id,
        )
        record_install(
            conn, instance_id=prod, extension_name="google-integration",
            extension_version="1.8.4",
        )

        prod_installs = list_installs_for_instance(conn, prod)
        assert {i.extension_name for i in prod_installs} == {
            "advanced-pack", "google-integration",
        }

        lic_installs = list_installs_for_license(conn, lic.id)
        assert len(lic_installs) == 2
        assert {i.instance_id for i in lic_installs} == {prod, stage}


# ── Slot enforcement ───────────────────────────────────────────────────


class TestSlotEnforcement:
    def test_empty_license_allows_first_install(self, conn):
        prod = _make_instance(conn, "PROD", "production")
        lic = save_license(conn, ExtensionLicense(
            extension_name="advanced-pack", license_key="K",
        ))
        result = check_slot_availability(conn, lic.id, prod)
        assert result.allowed is True
        assert result.is_reinstall is False
        assert result.reason is None
        assert len(result.usage.production_installs) == 0

    def test_production_cap_blocks_second_prod(self, conn):
        prod_a = _make_instance(conn, "PRODA", "production")
        prod_b = _make_instance(conn, "PRODB", "production")
        lic = save_license(conn, ExtensionLicense(
            extension_name="advanced-pack", license_key="K",
        ))
        record_install(
            conn, instance_id=prod_a, extension_name="advanced-pack",
            extension_version="3.12.1", license_id=lic.id,
        )
        result = check_slot_availability(conn, lic.id, prod_b)
        assert result.allowed is False
        assert "Production slot full" in result.reason
        assert "PRODA" in result.reason

    def test_nonprod_cap_blocks_third_nonprod(self, conn):
        stage = _make_instance(conn, "STAGE", "staging")
        test = _make_instance(conn, "TEST", "test")
        dev = _make_instance(conn, "DEV", "test")
        lic = save_license(conn, ExtensionLicense(
            extension_name="advanced-pack", license_key="K",
        ))
        record_install(
            conn, instance_id=stage, extension_name="advanced-pack",
            extension_version="3.12.1", license_id=lic.id,
        )
        record_install(
            conn, instance_id=test, extension_name="advanced-pack",
            extension_version="3.12.1", license_id=lic.id,
        )
        result = check_slot_availability(conn, lic.id, dev)
        assert result.allowed is False
        assert "Non-production slots full" in result.reason
        assert "STAGE" in result.reason
        assert "TEST" in result.reason

    def test_reinstall_always_allowed(self, conn):
        prod = _make_instance(conn, "PROD", "production")
        lic = save_license(conn, ExtensionLicense(
            extension_name="advanced-pack", license_key="K",
        ))
        record_install(
            conn, instance_id=prod, extension_name="advanced-pack",
            extension_version="3.12.0", license_id=lic.id,
        )
        result = check_slot_availability(conn, lic.id, prod)
        assert result.allowed is True
        assert result.is_reinstall is True

    def test_reinstall_when_full_still_allowed(self, conn):
        """Full cap should still permit re-installing on an existing slot."""
        prod = _make_instance(conn, "PROD", "production")
        lic = save_license(conn, ExtensionLicense(
            extension_name="advanced-pack", license_key="K",
        ))
        record_install(
            conn, instance_id=prod, extension_name="advanced-pack",
            extension_version="3.12.0", license_id=lic.id,
        )
        result = check_slot_availability(conn, lic.id, prod)
        assert result.allowed is True
        assert result.is_reinstall is True

    def test_get_slot_usage_breakdown(self, conn):
        prod = _make_instance(conn, "PROD", "production")
        stage = _make_instance(conn, "STAGE", "staging")
        lic = save_license(conn, ExtensionLicense(
            extension_name="advanced-pack", license_key="K",
        ))
        record_install(
            conn, instance_id=prod, extension_name="advanced-pack",
            extension_version="3.12.1", license_id=lic.id,
        )
        record_install(
            conn, instance_id=stage, extension_name="advanced-pack",
            extension_version="3.12.0", license_id=lic.id,
        )
        usage = get_slot_usage(conn, lic.id)
        assert len(usage.production_installs) == 1
        assert usage.production_installs[0].instance_code == "PROD"
        assert usage.production_installs[0].extension_version == "3.12.1"
        assert len(usage.nonproduction_installs) == 1
        assert usage.nonproduction_installs[0].instance_code == "STAGE"

    def test_install_on_unlicensed_extension_does_not_consume_slot(self, conn):
        """An install with license_id=None has no slot impact."""
        prod = _make_instance(conn, "PROD", "production")
        lic = save_license(conn, ExtensionLicense(
            extension_name="advanced-pack", license_key="K",
        ))
        record_install(
            conn, instance_id=prod, extension_name="google-integration",
            extension_version="1.8.4", license_id=None,
        )
        usage = get_slot_usage(conn, lic.id)
        assert len(usage.production_installs) == 0
        assert len(usage.nonproduction_installs) == 0
