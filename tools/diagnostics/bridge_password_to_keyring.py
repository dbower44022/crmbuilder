"""Bridge a MariaDB root password from a password manager into the local
OS keyring, producing a reference string suitable for the
InstanceDeployConfig.db_root_password_ref column.

Workflow:
  1. Generates a fresh UUID4
  2. Prompts the operator for the password (hidden input via getpass)
  3. Writes the password into the OS keyring under
     service='crmbuilder', username=<uuid>
  4. Prints the resulting reference string 'crmbuilder:<uuid>'
  5. Does not echo, log, or persist the password anywhere except
     the keyring itself

Use case: an EspoCRM instance was deployed outside the CRM Builder
application's wizard (so the password was never written to the local
keyring) and is now being backfilled into InstanceDeployConfig. The
password lives in the operator's password manager (e.g. Proton Pass)
but the application schema requires a keyring reference. This script
bridges the gap.

After running, the password lives in two places:
  - The operator's password manager (system of record)
  - Local OS keyring under 'crmbuilder:<uuid>' (machine cache that
    the CRM Builder application uses for automated retrieval)

To verify the keyring entry afterward:
  uv run python -c "import keyring; \
      print('OK' if keyring.get_password('crmbuilder', '<uuid>') \
      else 'NOT FOUND')"

To remove the keyring entry later if needed:
  uv run python -c "import keyring; \
      keyring.delete_password('crmbuilder', '<uuid>')"

Run via:
  uv run python tools/diagnostics/bridge_password_to_keyring.py
"""

from __future__ import annotations

import getpass
import sys
import uuid

try:
    import keyring
except ImportError:
    print(
        "ERROR: 'keyring' library not available in this Python.",
        file=sys.stderr,
    )
    print(
        "Run via 'uv run python tools/diagnostics/"
        "bridge_password_to_keyring.py' from the crmbuilder repo.",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    print("Bridge a password from your password manager to the OS keyring.")
    print()
    print("You will be prompted for the password twice. The input is hidden.")
    print("The script does not echo, log, or persist the password anywhere")
    print("except the OS keyring itself.")
    print()

    password = getpass.getpass("Paste the password (hidden): ")
    if not password.strip():
        print(
            "ERROR: empty password; aborting without writing to keyring.",
            file=sys.stderr,
        )
        sys.exit(1)

    confirm = getpass.getpass("Paste it again to confirm (hidden): ")
    if password != confirm:
        print(
            "ERROR: passwords don't match; "
            "aborting without writing to keyring.",
            file=sys.stderr,
        )
        sys.exit(1)

    new_uuid = str(uuid.uuid4())
    service_name = "crmbuilder"

    try:
        keyring.set_password(service_name, new_uuid, password)
    except Exception as exc:
        print(f"ERROR: keyring write failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # Verify by reading it back
    try:
        readback = keyring.get_password(service_name, new_uuid)
    except Exception as exc:
        print(f"ERROR: keyring readback failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if readback != password:
        print(
            "ERROR: keyring readback did not match input.",
            file=sys.stderr,
        )
        print(
            "The password may not have been stored correctly.",
            file=sys.stderr,
        )
        sys.exit(1)

    reference = f"{service_name}:{new_uuid}"

    # Discard locals that contain the password
    del password, confirm, readback

    print()
    print("=" * 68)
    print("SUCCESS")
    print("=" * 68)
    print()
    print("Keyring reference (use this as db_root_password_ref):")
    print()
    print(f"  {reference}")
    print()
    print("Copy that exact string. You will paste it into the backfill")
    print("dialog (or wherever the InstanceDeployConfig row is being")
    print("written) as the value of db_root_password_ref.")
    print()


if __name__ == "__main__":
    main()
