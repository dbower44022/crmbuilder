"""Task 9 — verify the Preferences.presetFilters write path.

After tasks 2/3 confirmed the metadata API is read-only, Doug found
that the admin UI saves filters by PUTing the user's Preferences record.
This script:

  1. Captures baseline ``GET /Preferences/{userId}`` for admin.
  2. Adds three preset filters for ``cAccountType`` to the existing
     ``presetFilters.Account`` list.
  3. PUTs the modified preferences back.
  4. GETs again to verify the new filters round-trip.
  5. Restores the baseline so no test artifacts remain.

The Preferences record is **per-user**, so this only proves that the
admin user's saved-search list can be programmatically extended. It does
not prove anything about admin-defined system filters (which is what
selectDefs/clientDefs would have controlled). The findings report is
the place where that distinction is made explicit.
"""

from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

from _common import (
    SPIKE_DIR,
    Attempt,
    ENUM_VALUES,
    PRIMARY_FILTER_NAMES,
    append_attempt,
    load_json,
    make_client,
    print_attempt,
    save_json,
)


ADMIN_USER_ID = "69f8a18e429456e87"
ATTEMPT_LOG = SPIKE_DIR / "task9-attempts.jsonl"
BASELINE_FILE = SPIKE_DIR / "task9-baseline-preferences.json"


def _short_id() -> str:
    """Generate a 7-char hex id matching the UI's filter-id pattern."""
    return secrets.token_hex(4)[:7]


def build_account_type_filter(filter_id: str, label: str, value: str) -> dict:
    """Build one preset-filter entry for cAccountType (multiEnum field).

    The shape mirrors what the EspoCRM search panel emits for a multiEnum
    field selection in the list view. Outer ``data.cAccountType`` is the
    search-form view shape; inner ``data`` is the where-builder hint.
    """
    return {
        "id": filter_id,
        "name": filter_id,
        "label": label,
        "data": {
            "cAccountType": {
                "type": "anyOf",
                "value": [value],
                "data": {
                    "type": "anyOf",
                    "valueList": [value],
                },
            },
        },
        "primary": None,
    }


def attempt_request(client, label, method, url, payload=None):
    if payload is not None:
        status, body = client._request(method, url, json=payload)
    else:
        status, body = client._request(method, url)
    a = Attempt(
        label=label, method=method, url=url,
        payload=payload, status=status, body=body,
    )
    append_attempt(ATTEMPT_LOG, a)
    print_attempt(a)
    return a


def main() -> int:
    if ATTEMPT_LOG.exists():
        ATTEMPT_LOG.unlink()

    client = make_client()
    api = client.profile.api_url
    print(f"Connected to: {client.profile.url}")
    print()

    # 1. Capture baseline.
    a = attempt_request(
        client, "baseline-GET-/Preferences/{adminId}",
        "GET", f"{api}/Preferences/{ADMIN_USER_ID}",
    )
    if a.status != 200 or not isinstance(a.body, dict):
        print("FATAL: could not fetch baseline preferences")
        return 1
    baseline_prefs = a.body
    save_json(BASELINE_FILE, baseline_prefs)

    # 2. Build extended presetFilters.Account.
    existing_account = (
        baseline_prefs.get("presetFilters", {}) or {}
    ).get("Account", [])
    print(f"Existing Account preset filters: {len(existing_account)}")

    new_entries = []
    spike_ids = []
    labels = ["Spike: Client", "Spike: Partner", "Spike: Donor/Sponsor"]
    for label, value in zip(labels, ENUM_VALUES):
        fid = _short_id()
        spike_ids.append(fid)
        new_entries.append(build_account_type_filter(fid, label, value))

    extended_account = existing_account + new_entries
    extended_preset_filters = {
        **(baseline_prefs.get("presetFilters") or {}),
        "Account": extended_account,
    }

    # PUT only the changed sub-tree to keep the payload focused.
    put_payload = {"presetFilters": extended_preset_filters}

    print()
    print(f"Adding {len(new_entries)} preset filters with ids: {spike_ids}")
    a = attempt_request(
        client, "PUT-/Preferences/{adminId}-with-3-new-presetFilters",
        "PUT", f"{api}/Preferences/{ADMIN_USER_ID}", put_payload,
    )
    if a.status != 200:
        print("FAILED: PUT did not return 200; aborting before any cleanup.")
        return 1

    # 3. Round-trip verify.
    print()
    print("Round-trip verifying...")
    a = attempt_request(
        client, "verify-GET-/Preferences/{adminId}",
        "GET", f"{api}/Preferences/{ADMIN_USER_ID}",
    )
    after_account = (
        a.body.get("presetFilters", {}) or {}
    ).get("Account", []) if isinstance(a.body, dict) else []
    after_ids = {f.get("id") for f in after_account}
    expected_ids = set(spike_ids) | {f.get("id") for f in existing_account}
    print(f"  expected ids: {sorted(expected_ids)}")
    print(f"  observed ids: {sorted(after_ids)}")
    if not set(spike_ids).issubset(after_ids):
        print("FAILED: spike filter ids did not persist")
        return 1
    print("  -> all three spike filters persisted")
    save_json(SPIKE_DIR / "task9-after-put-preferences.json", a.body)

    # 4. Functional test — does the search API accept presetName= or
    #    primaryFilter= against a preset-filter id? (Hypothesis: NO — preset
    #    filters are client-side state. Worth verifying so we know.)
    print()
    print("Functional check: can the search API consume a preset id?")
    spike_id = spike_ids[0]
    func_url = (
        f"{api}/Account?primaryFilter={spike_id}&maxSize=1"
    )
    attempt_request(
        client, "func-primaryFilter-with-presetId",
        "GET", func_url,
    )
    func_url2 = (
        f"{api}/Account?presetName={spike_id}&maxSize=1"
    )
    attempt_request(
        client, "func-presetName-with-presetId",
        "GET", func_url2,
    )
    # Compare a direct arrayAnyOf query for the Client value as the
    # ground-truth baseline of what the filter *would* match.
    direct_url = (
        f"{api}/Account"
        f"?where[0][type]=arrayAnyOf"
        f"&where[0][attribute]=cAccountType"
        f"&where[0][value][]=Client"
        f"&maxSize=1"
    )
    attempt_request(
        client, "func-direct-arrayAnyOf-cAccountType-Client",
        "GET", direct_url,
    )

    # 5. Restore baseline.
    print()
    print("Restoring baseline preferences...")
    restore_payload = {
        "presetFilters": baseline_prefs.get("presetFilters") or {}
    }
    a = attempt_request(
        client, "restore-PUT-/Preferences/{adminId}",
        "PUT", f"{api}/Preferences/{ADMIN_USER_ID}", restore_payload,
    )
    if a.status != 200:
        print(
            "WARNING: restore PUT returned {}. Manual cleanup may be required.".format(
                a.status
            )
        )
        return 1

    # Final verify.
    a = attempt_request(
        client, "final-GET-/Preferences/{adminId}",
        "GET", f"{api}/Preferences/{ADMIN_USER_ID}",
    )
    final_account = (
        a.body.get("presetFilters", {}) or {}
    ).get("Account", []) if isinstance(a.body, dict) else []
    final_ids = {f.get("id") for f in final_account}
    if any(sid in final_ids for sid in spike_ids):
        print("WARNING: spike ids still present after restore")
        return 1
    print("  -> baseline restored, no spike ids remain")
    return 0


if __name__ == "__main__":
    sys.exit(main())
