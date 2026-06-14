"""SES-166 — backfill the four dogfood cross-domain services (PI-161).

The first dogfood run (SES-166) had nowhere to put cross-domain services:
the four were captured as a single line in the charter's scope markdown
("**Cross-domain services:** document storage, notifications, user accounts,
AI agent orchestration") because the ``service`` entity type did not yet
exist (PI-161). Now that the type ships (WTK-138), this script materialises
the four as proper ``service`` records per service.md §6.

Run on ``main`` against the live API once the ``/services`` endpoint is
deployed (the API surface is a sibling Work Task — this is a governance data
apply under the Model A branch protocol, not part of the storage branch):

    uv run python scripts/backfill_ses_166_services.py \
        --api-base http://127.0.0.1:8765 --engagement CRMBUILDER

Each service POSTs directly at ``confirmed`` — administrator-confirmed live
in SES-166 (service.md §3.2.3) — with ``service_notes`` recording provenance.
No edges are attached at backfill (§6 steps 2–3): the dogfood's processes
have not had Phase 3 dependency elicitation, and no entity records exist in
ENG-001 yet, so ``process_consumes_service`` and ``service_owns_entity``
edges attach when those passes run. The script is idempotent: a service whose
``service_name`` already exists in the engagement is left untouched.

The accompanying provenance Decision and the charter-supersession edit
(§6 steps 4–5) are authored separately at PI-161 build-closure; this script
only writes the four records.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

# The four SES-166 services, drafted from charter scope context (service.md
# §6). ``service_purpose`` wording is the spec's draft; the backfill session
# confirms it with the stakeholder. Identifiers are server-assigned on POST
# omission (PI-002) — the SVC-001..004 column in the spec table is expected,
# not asserted here.
_SERVICES: list[dict[str, str]] = [
    {
        "service_name": "Document Storage",
        "service_purpose": (
            "Store, version, and attach documents across all domains' "
            "records — requirements artifacts, specifications, deliverables."
        ),
    },
    {
        "service_name": "Notifications",
        "service_purpose": (
            "Notify users of events and state changes across domains — "
            "approvals due, gates reached, feedback received."
        ),
    },
    {
        "service_name": "User Accounts",
        "service_purpose": (
            "Account, identity, and access for every persona across the "
            "system; the cross-domain substrate role-based access builds on."
        ),
    },
    {
        "service_name": "AI Agent Orchestration",
        "service_purpose": (
            "Coordinate the AI agents that execute methodology work across "
            "domains — the delivery organization's runtime substrate."
        ),
    },
]

_PROVENANCE = (
    "Captured in SES-166 charter scope text; backfilled per PI-161 "
    "(WTK-138 storage build). Ownership intent and consuming-process edges "
    "attach when Phase 2/3 surfaces them."
)


def _api(
    method: str,
    base: str,
    path: str,
    *,
    engagement: str,
    body: dict | None = None,
) -> object:
    """Call the V2 API and unwrap the ``{data, meta, errors}`` envelope."""
    headers = {"Content-Type": "application/json", "X-Engagement": engagement}
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base.rstrip("/") + path, data=data, method=method, headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        raise SystemExit(
            f"API {method} {path} failed ({e.code}): {detail}"
        ) from e
    if payload.get("errors"):
        raise SystemExit(
            f"API {method} {path} returned errors: {payload['errors']}"
        )
    return payload.get("data")


def _existing_names(base: str, engagement: str) -> set[str]:
    rows = _api("GET", base, "/services", engagement=engagement) or []
    return {
        (r.get("service_name") or "").strip().lower()
        for r in rows
        if isinstance(r, dict)
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="SES-166 cross-domain service backfill")
    p.add_argument("--api-base", default="http://127.0.0.1:8765")
    p.add_argument("--engagement", default="CRMBUILDER")
    args = p.parse_args(argv)

    existing = _existing_names(args.api_base, args.engagement)
    created = skipped = 0
    for svc in _SERVICES:
        if svc["service_name"].strip().lower() in existing:
            print(f"  SKIP {svc['service_name']}: already present")
            skipped += 1
            continue
        data = _api(
            "POST",
            args.api_base,
            "/services",
            engagement=args.engagement,
            body={
                "service_name": svc["service_name"],
                "service_purpose": svc["service_purpose"],
                "service_status": "confirmed",
                "service_notes": _PROVENANCE,
            },
        )
        ident = data.get("service_identifier") if isinstance(data, dict) else "?"
        print(f"  OK   {ident}: {svc['service_name']}")
        created += 1
    print(f"created {created}, skipped {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
