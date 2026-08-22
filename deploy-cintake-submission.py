#!/usr/bin/env python3
"""One-shot headless deploy of the CIntakeSubmission entity to an EspoCRM instance.

Creates the custom entity `CIntakeSubmission` and its five custom fields, with
the mandatory rebuilds, replicating exactly what the v1 CRM Builder ("Run"
button) does — but without the Qt GUI. Idempotent: it skips the entity if it
already exists and treats a duplicate-field 409 as "already there".

It reads the EspoCRM **admin** connection from a v1 instance-profile JSON (the
same file the desktop tool uses), so no secret is typed or printed here. The
create-only ESPO_API_KEY used by the cbm-client-intake app will NOT work for
this — entity/field/rebuild endpoints require an admin-scoped credential.

Usage:
    python3 deploy-cintake-submission.py [path/to/instance-profile.json]

Default profile path is the migrated CBMTEST profile. Override by passing a
path, or set CBM_INSTANCE_PROFILE. The script aborts before any write if the
credential is not admin-scoped.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import time

try:
    import requests
except ImportError:
    sys.exit("This script needs `requests` (pip install requests, or run from the crmbuilder venv).")

DEFAULT_PROFILE = "/home/doug/Dropbox/Projects/crmbuilder/data/instances/cbm_test_instance.json.migrated"

ENTITY_NATURAL = "IntakeSubmission"   # EspoCRM prepends "C" -> CIntakeSubmission
ENTITY = "CIntakeSubmission"
LABEL_SINGULAR = "Intake Submission"
LABEL_PLURAL = "Intake Submissions"

FIELDS = [
    {"name": "form", "type": "enum", "label": "Form",
     "options": ["client-intake", "volunteer", "info-request"]},
    {"name": "reason", "type": "enum", "label": "Reason",
     "options": ["Honeypot", "OrchestratorError"]},
    {"name": "submitterEmail", "type": "email", "label": "Submitter Email"},
    {"name": "status", "type": "enum", "label": "Status",
     "options": ["New", "Approved", "Rejected", "Processed"], "default": "New"},
    {"name": "description", "type": "text", "label": "Description"},
]


def load_profile(path: str) -> dict:
    with open(path) as f:
        p = json.load(f)
    if not p.get("url"):
        sys.exit(f"Profile {path} has no 'url'.")
    return p


def auth_headers(profile: dict, method: str, uri: str) -> dict:
    """Mirror espo_impl EspoAdminClient header construction."""
    am = (profile.get("auth_method") or "api_key").lower()
    api_key = profile.get("api_key") or ""
    secret = profile.get("secret_key") or ""
    if am == "api_key":
        return {"X-Api-Key": api_key}
    if am == "basic":
        tok = base64.b64encode(f"{api_key}:{secret}".encode()).decode()
        return {"Authorization": f"Basic {tok}", "Espo-Authorization": tok}
    if am == "hmac":
        msg = f"{method} /{uri}".encode()
        mac = hmac.new(secret.encode(), msg, hashlib.sha256).digest()
        return {"X-Hmac-Authorization": base64.b64encode(api_key.encode() + b":" + mac).decode()}
    sys.exit(f"Unknown auth_method: {am!r}")


def main() -> None:
    path = (len(sys.argv) > 1 and sys.argv[1]) or os.environ.get("CBM_INSTANCE_PROFILE") or DEFAULT_PROFILE
    profile = load_profile(path)
    base = profile["url"].rstrip("/") + "/api/v1"
    print(f"Target: {base}  (auth_method={profile.get('auth_method', 'api_key')}, profile={path})")

    s = requests.Session()

    def call(method: str, uri: str, body: dict | None = None):
        headers = {"Content-Type": "application/json", **auth_headers(profile, method, uri)}
        r = s.request(method, f"{base}/{uri}", headers=headers,
                      data=json.dumps(body) if body is not None else None, timeout=30)
        snippet = (r.text or "")[:200].replace("\n", " ")
        print(f"  {method} {uri} -> {r.status_code} {snippet}")
        return r

    # 0. Admin sanity gate — must be 200. 401 = bad credential, 403 = not admin.
    print("\n[0] admin auth check")
    r = call("GET", "Metadata?key=app.adminPanel")
    if r.status_code != 200:
        sys.exit(f"\nABORT: credential is not admin-scoped (HTTP {r.status_code}). "
                 "Use the admin profile, not the create-only intake API key. No writes made.")

    # 1. Create entity unless it already exists.
    print("\n[1] entity")
    r = call("GET", f"Metadata?key=scopes.{ENTITY}")
    if r.status_code == 200 and r.json():
        print(f"  {ENTITY} already exists — skipping create.")
    else:
        r = call("POST", "EntityManager/action/createEntity", {
            "name": ENTITY_NATURAL, "type": "Base",
            "labelSingular": LABEL_SINGULAR, "labelPlural": LABEL_PLURAL,
            "stream": True, "disabled": False})
        if r.status_code >= 400:
            sys.exit(f"\nABORT: createEntity failed (HTTP {r.status_code}).")

    # 2. Rebuild and wait for entityDefs to materialize (async on the server).
    print("\n[2] rebuild + wait for entity to materialize")
    call("POST", "Admin/rebuild")
    for _ in range(20):
        r = s.get(f"{base}/Metadata?key=entityDefs.{ENTITY}",
                  headers=auth_headers(profile, "GET", f"Metadata?key=entityDefs.{ENTITY}"), timeout=30)
        if r.status_code == 200 and r.json():
            print("  entity is live.")
            break
        time.sleep(1.5)
    else:
        sys.exit("\nABORT: entity did not materialize after rebuild.")

    # 3. Fields (409 = already present; harmless on re-run).
    print("\n[3] fields")
    for f in FIELDS:
        r = call("POST", f"Admin/fieldManager/{ENTITY}", {**f, "isCustom": True})
        if r.status_code >= 400 and r.status_code != 409:
            print(f"  WARNING: field {f['name']} returned {r.status_code}")

    # 4. Final rebuild so the new columns/cache settle.
    print("\n[4] final rebuild")
    call("POST", "Admin/rebuild")

    # 5. Verify.
    print("\n[5] verify field names landed un-prefixed")
    r = call("GET", f"Metadata?key=entityDefs.{ENTITY}.fields")
    if r.status_code == 200:
        got = set(r.json().keys())
        want = {f["name"] for f in FIELDS}
        missing = want - got
        prefixed = {n for n in want if f"c{n[0].upper()}{n[1:]}" in got}
        print(f"  fields present: {sorted(got & want)}")
        if missing:
            print(f"  MISSING: {sorted(missing)}")
        if prefixed:
            print(f"  NOTE: these came back c-prefixed, update the app: {sorted(prefixed)}")
        if not missing and not prefixed:
            print("  OK — all five fields present with the expected api-names.")
    print("\nDone.")


if __name__ == "__main__":
    main()
