"""Task 8 — verify no metadata mutated during the spike.

Every write attempt in tasks 2 and 3 returned 404/405. Nothing reached a
handler that could have mutated state. This script re-fetches the
baseline keys and compares structurally against the saved baseline. If
they match, the instance is in its original state and no cleanup is
required. If they differ, halts with a non-zero exit code so the
operator can investigate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from _common import SPIKE_DIR, load_json, make_client


def main() -> int:
    client = make_client()
    api = client.profile.api_url
    print(f"Connected to: {client.profile.url}")

    targets = [
        ("selectDefs.Account", "baseline-selectDefs-Account.json"),
        ("clientDefs.Account", "baseline-clientDefs-Account.json"),
    ]
    drift = False
    for key, filename in targets:
        baseline = load_json(SPIKE_DIR / filename)
        url = f"{api}/Metadata?key={key}"
        status, body = client._request("GET", url)
        baseline_body = baseline.get("body")
        if json.dumps(body, sort_keys=True) == json.dumps(
            baseline_body, sort_keys=True
        ):
            print(f"  {key}: identical to baseline (HTTP {status})")
        else:
            drift = True
            print(f"  {key}: DRIFT FROM BASELINE (HTTP {status})")
            print(f"    baseline: {json.dumps(baseline_body)[:160]}")
            print(f"    current:  {json.dumps(body)[:160]}")

    if drift:
        print()
        print("DRIFT detected — manual investigation required.")
        return 1
    print()
    print("Baseline restored. No residual test artifacts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
