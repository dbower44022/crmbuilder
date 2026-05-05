"""Task 3 — attempt to create admin-defined boolean filters via metadata API.

Same approach as Task 2 but targets ``selectDefs.Account.boolFilters``
plus ``clientDefs.Account.boolFilterList``.
"""

from __future__ import annotations

from _common import (
    SPIKE_DIR,
    Attempt,
    BOOL_FILTER_NAMES,
    ENUM_VALUES,
    append_attempt,
    make_client,
    print_attempt,
    save_json,
)


ATTEMPT_LOG = SPIKE_DIR / "task3-attempts.jsonl"


def bool_filter_block() -> dict:
    """Build the selectDefs.Account.boolFilters payload."""
    block = {}
    for name, value in zip(BOOL_FILTER_NAMES, ENUM_VALUES):
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


def main() -> None:
    if ATTEMPT_LOG.exists():
        ATTEMPT_LOG.unlink()

    client = make_client()
    api = client.profile.api_url
    print(f"Connected to: {client.profile.url}")
    print()

    bool_block = bool_filter_block()
    bool_list = ["onlyMy"] + BOOL_FILTER_NAMES

    nested_full = {
        "selectDefs": {"Account": {"boolFilters": bool_block}},
        "clientDefs": {"Account": {"boolFilterList": bool_list}},
    }

    # Same shape matrix as task 2.
    attempt_request(client, "shape1-PUT-/Metadata-nested-bool",
                    "PUT", f"{api}/Metadata", nested_full)
    attempt_request(client, "shape2-POST-/Metadata-nested-bool",
                    "POST", f"{api}/Metadata", nested_full)
    attempt_request(client, "shape3-PATCH-/Metadata-nested-bool",
                    "PATCH", f"{api}/Metadata", nested_full)
    attempt_request(
        client,
        "shape4-PUT-/Metadata?key=selectDefs.Account.boolFilters",
        "PUT",
        f"{api}/Metadata?key=selectDefs.Account.boolFilters",
        bool_block,
    )
    attempt_request(
        client, "shape5-PUT-/Metadata/selectDefs/Account/boolFilters",
        "PUT", f"{api}/Metadata/selectDefs/Account/boolFilters", bool_block,
    )
    # Try a few extra "admin-ish" routes that some EspoCRM forks expose.
    attempt_request(client, "shape6-POST-/Admin/Action/clearCache",
                    "POST", f"{api}/Admin/Action/clearCache", None)

    # Save final state.
    print()
    print("Re-fetching selectDefs.Account post-attempts...")
    status, body = client._request("GET", f"{api}/Metadata?key=selectDefs.Account")
    save_json(
        SPIKE_DIR / "task3-post-selectDefs-Account.json",
        {"status": status, "body": body},
    )
    print(f"  status={status}, body type={type(body).__name__}")
    print("Re-fetching clientDefs.Account.boolFilterList...")
    status, body = client._request(
        "GET", f"{api}/Metadata?key=clientDefs.Account.boolFilterList"
    )
    save_json(
        SPIKE_DIR / "task3-post-clientDefs-boolFilterList.json",
        {"status": status, "body": body},
    )
    print(f"  status={status}, body={body}")


if __name__ == "__main__":
    main()
