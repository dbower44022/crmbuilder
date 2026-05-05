"""Task 1 — capture baseline metadata for Account.

Saves selectDefs and clientDefs for the Account entity to disk as a
reference and rollback target for the rest of the spike.
"""

from __future__ import annotations

from pathlib import Path

from _common import SPIKE_DIR, make_client, save_json


def main() -> None:
    client = make_client()
    profile = client.profile
    print(f"Connected to: {profile.url}")

    targets = [
        ("selectDefs.Account", "baseline-selectDefs-Account.json"),
        ("clientDefs.Account", "baseline-clientDefs-Account.json"),
    ]
    for key, filename in targets:
        url = f"{profile.api_url}/Metadata?key={key}"
        status, body = client._request("GET", url)
        out_path: Path = SPIKE_DIR / filename
        save_json(out_path, {"key": key, "status": status, "body": body})
        size = len(body) if isinstance(body, dict) else "n/a"
        print(f"  {key} -> HTTP {status}, top-level keys: {size}")
        print(f"  saved to: {out_path}")


if __name__ == "__main__":
    main()
