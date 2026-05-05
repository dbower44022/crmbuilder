"""Task 2 — attempt to create admin-defined primary filters via metadata API.

Tries a series of payload shapes and HTTP method variants. Logs every
attempt to ``task2-attempts.jsonl`` and prints a summary. Does not stop
on the first rejection — the spike's value is in mapping the rejection
surface.
"""

from __future__ import annotations

from pathlib import Path

from _common import (
    SPIKE_DIR,
    Attempt,
    BOOL_FILTER_NAMES,
    ENUM_VALUES,
    PRIMARY_FILTER_NAMES,
    append_attempt,
    make_client,
    print_attempt,
    save_json,
)

ATTEMPT_LOG = SPIKE_DIR / "task2-attempts.jsonl"


def primary_filter_block_array_any_of() -> dict:
    """Build the selectDefs.Account.filterDefs payload for multiEnum.

    Uses ``arrayAnyOf`` because cAccountType is multiEnum — scalar
    ``equals`` would return zero rows when matching list-valued fields.
    """
    block = {}
    for name, value in zip(PRIMARY_FILTER_NAMES, ENUM_VALUES):
        block[name] = {
            "where": [
                {
                    "type": "arrayAnyOf",
                    "attribute": "cAccountType",
                    "value": [value],
                }
            ]
        }
    return block


def primary_filter_block_equals() -> dict:
    """Same shape but with ``equals`` — kept for failure-mode evidence.

    cAccountType is multiEnum so this should match nothing functionally,
    but the schema may still accept the structure.
    """
    block = {}
    for name, value in zip(PRIMARY_FILTER_NAMES, ENUM_VALUES):
        block[name] = {
            "where": [
                {
                    "type": "equals",
                    "attribute": "cAccountType",
                    "value": value,
                }
            ]
        }
    return block


def filter_list_payload() -> list[dict]:
    """clientDefs.Account.filterList augmented with the spike filters.

    Preserves the existing ``recentlyCreated`` entry.
    """
    return [{"name": "recentlyCreated"}] + [
        {"name": n} for n in PRIMARY_FILTER_NAMES
    ]


def attempt_request(
    client, label, method, url, payload=None,
):
    """Run one request and append to the attempt log."""
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


def main() -> None:
    if ATTEMPT_LOG.exists():
        ATTEMPT_LOG.unlink()

    client = make_client()
    api = client.profile.api_url
    print(f"Connected to: {client.profile.url}")
    print()

    primary_block = primary_filter_block_array_any_of()
    primary_block_equals = primary_filter_block_equals()
    flist = filter_list_payload()

    # ----- Shape 1: nested under top-level Metadata PUT -----
    nested_full = {
        "selectDefs": {"Account": {"filterDefs": primary_block}},
        "clientDefs": {"Account": {"filterList": flist}},
    }
    attempt_request(
        client, "shape1-PUT-/Metadata-nested",
        "PUT", f"{api}/Metadata", nested_full,
    )

    # ----- Shape 2: same payload but POST -----
    attempt_request(
        client, "shape2-POST-/Metadata-nested",
        "POST", f"{api}/Metadata", nested_full,
    )

    # ----- Shape 3: same payload but PATCH -----
    attempt_request(
        client, "shape3-PATCH-/Metadata-nested",
        "PATCH", f"{api}/Metadata", nested_full,
    )

    # ----- Shape 4: PUT scoped via ?key=selectDefs.Account -----
    attempt_request(
        client, "shape4-PUT-/Metadata?key=selectDefs.Account",
        "PUT",
        f"{api}/Metadata?key=selectDefs.Account",
        {"filterDefs": primary_block},
    )

    # ----- Shape 5: PUT directly to /Metadata/selectDefs/Account -----
    attempt_request(
        client, "shape5-PUT-/Metadata/selectDefs/Account",
        "PUT",
        f"{api}/Metadata/selectDefs/Account",
        {"filterDefs": primary_block},
    )

    # ----- Shape 6: equals variant (multiEnum on scalar equals) -----
    nested_equals = {
        "selectDefs": {"Account": {"filterDefs": primary_block_equals}},
        "clientDefs": {"Account": {"filterList": flist}},
    }
    attempt_request(
        client, "shape6-PUT-/Metadata-nested-equals",
        "PUT", f"{api}/Metadata", nested_equals,
    )

    # ----- Shape 7: try the older Admin/metadata endpoint -----
    attempt_request(
        client, "shape7-PUT-/Admin/metadata-nested",
        "PUT", f"{api}/Admin/metadata", nested_full,
    )

    # ----- Shape 8: try Admin/metadata with POST -----
    attempt_request(
        client, "shape8-POST-/Admin/metadata-nested",
        "POST", f"{api}/Admin/metadata", nested_full,
    )

    # Save final state.
    print()
    print("Re-fetching selectDefs.Account post-attempts...")
    status, body = client._request("GET", f"{api}/Metadata?key=selectDefs.Account")
    save_json(
        SPIKE_DIR / "task2-post-selectDefs-Account.json",
        {"status": status, "body": body},
    )
    print(f"  status={status}, body type={type(body).__name__}")
    if isinstance(body, dict):
        print(f"  has filterDefs: {bool(body.get('filterDefs'))}")
        if body.get("filterDefs"):
            print(f"  filterDefs keys: {list(body['filterDefs'].keys())}")

    print("Re-fetching clientDefs.Account.filterList...")
    status, body = client._request(
        "GET", f"{api}/Metadata?key=clientDefs.Account.filterList"
    )
    save_json(
        SPIKE_DIR / "task2-post-clientDefs-filterList.json",
        {"status": status, "body": body},
    )
    print(f"  status={status}, body={body}")


if __name__ == "__main__":
    main()
