"""Ingest the CRMBuilder Phase-2 Candidate Inventory MD into V2 records.

REL-013 / PI-095 (REQ-413). Reads the durable Markdown inventory at
``PRDs/product/crmbuilder-v2/CRMBuilder-Phase-2-Candidate-Inventory.md``
(the source of truth captured by SES-098, DEC-319) and writes first-class
methodology **candidate** records + edges to the V2 store via the REST
API, so the captured domains / entities / personas become queryable and
reconcilable rather than living only as prose.

Mechanism (b) of PI-095: a standalone ingestion script (own parsing,
validation, ordering) that POSTs through the existing ``/domains``,
``/entities``, ``/personas`` and ``/references`` endpoints. Chosen over a
v0.9 close-out payload-schema extension (more invasive) or an MCP batch
tool (aimed at live sessions, not backfill).

What it writes (candidate status throughout):
  * 14 Domain records (§1).
  * The first-class bulleted Entity records (§2), deduped by
    case-insensitive name across domains; entities annotated
    "not a first-class entity" are skipped.
  * ``entity_scopes_to_domain`` edges — each entity to every domain it is
    listed under (a duplicate-named entity links to all of them).
  * 9 Persona records (§3).

Deliberately NOT written (stated, not silent):
  * Persona backing / persona-to-domain edges — §3 marks all backings
    "TBD pending PI-091" and gives no clean per-persona primary domain,
    so guessing edges into the live store would be worse than omitting
    them. Persona backing is Phase-3 / PI-091 (now PI-094 participant)
    work.
  * Speculative / "Entities TBD" prose candidates (Domains 1, 8, 10, 11)
    that are not bulleted first-class entities.

Idempotent: existing records (by case-insensitive name) and existing
edges (409) are skipped, so re-running is safe.

Usage::

    # parse + print the plan, write nothing
    uv run python scripts/ingest_phase2_candidate_inventory.py --dry-run

    # execute against the configured API (reads creds from crmbuilder.env)
    uv run python scripts/ingest_phase2_candidate_inventory.py
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_INVENTORY = (
    _REPO_ROOT
    / "PRDs/product/crmbuilder-v2/CRMBuilder-Phase-2-Candidate-Inventory.md"
)
_ENV = _REPO_ROOT / "crmbuilder-v2/data/crmbuilder.env"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _section(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _field(block: str, label: str) -> str | None:
    """Return the paragraph text following ``**<label>.**`` in ``block``."""
    m = re.search(rf"\*\*{re.escape(label)}\.\*\*\s*(.+)", block)
    return m.group(1).strip() if m else None


def parse_domains(text: str) -> list[dict]:
    sec = _section(text, "## 1. Candidate Domain List", "## 2.")
    domains = []
    blocks = re.split(r"^### Candidate Domain \d+ — ", sec, flags=re.M)[1:]
    for block in blocks:
        name = block.splitlines()[0].strip()
        description = _field(block, "Description") or name
        purpose = _field(block, "Mission tie-in") or description
        domains.append(
            {"name": name, "purpose": purpose, "description": description}
        )
    return domains


def parse_entities(text: str) -> list[dict]:
    """Return unique entities with the set of domains each belongs to.

    Deduped by case-insensitive name; description taken from the first
    occurrence. Bullets annotated "not a first-class entity" are skipped.
    """
    sec = _section(text, "## 2. Candidate Entity Inventory", "## 3.")
    by_key: dict[str, dict] = {}
    blocks = re.split(r"^### Domain \d+ — ", sec, flags=re.M)[1:]
    for block in blocks:
        domain_name = block.splitlines()[0].strip()
        for line in block.splitlines():
            m = re.match(r"^- \*\*(.+?)\*\*(.*)$", line.strip())
            if not m:
                continue
            name = m.group(1).strip()
            tail = m.group(2).strip()
            if "not a first-class entity" in tail.lower():
                continue
            # Description = the parenthetical/trailing annotation, or a
            # synthesized fallback naming the source domain.
            desc = tail.lstrip(" .")
            desc = desc.strip("()").strip() if desc else ""
            if not desc:
                desc = (
                    f"Candidate entity surfaced under the {domain_name} "
                    "domain in Phase 2 discovery."
                )
            key = name.lower()
            if key in by_key:
                by_key[key]["domains"].add(domain_name)
            else:
                by_key[key] = {
                    "name": name,
                    "description": desc,
                    "domains": {domain_name},
                }
    return list(by_key.values())


def parse_personas(text: str) -> list[dict]:
    sec = _section(text, "## 3. Candidate Persona Inventory", "## 4.")
    personas = []
    blocks = re.split(r"^### Candidate Persona \d+ — ", sec, flags=re.M)[1:]
    for block in blocks:
        name = block.splitlines()[0].strip()
        # Drop a parenthetical qualifier like "(questionable inclusion)".
        name = re.sub(r"\s*\(.*\)$", "", name).strip()
        role_summary = _field(block, "Description") or name
        personas.append({"name": name, "role_summary": role_summary})
    return personas


# ---------------------------------------------------------------------------
# API client (curl + envelope unwrap)
# ---------------------------------------------------------------------------


class Api:
    def __init__(self) -> None:
        env = _ENV.read_text()
        self.base = _env_value(env, "CRMBUILDER_V2_API_BASE_URL")
        token = _env_value(env, "CRMBUILDER_V2_API_TOKEN")
        self.headers = [
            "-H",
            f"Authorization: Bearer {token}",
            "-H",
            "X-Engagement: ENG-001",
            "-H",
            "Content-Type: application/json",
        ]

    def _call(self, method: str, path: str, body: dict | None = None):
        args = ["curl", "-s", "-X", method, *self.headers, self.base + path]
        if body is not None:
            args += ["-d", json.dumps(body)]
        out = subprocess.check_output(args).decode()
        return json.loads(out)

    def list_names(self, endpoint: str, name_key: str) -> set[str]:
        res = self._call("GET", f"/{endpoint}")
        data = res.get("data") or []
        return {r[name_key].lower() for r in data if r.get(name_key)}

    def post(self, endpoint: str, body: dict) -> dict:
        return self._call("POST", f"/{endpoint}", body)


def _env_value(env: str, key: str) -> str:
    m = re.search(rf"^{re.escape(key)}=(.*)$", env, flags=re.M)
    if not m:
        raise SystemExit(f"{key} not found in {_ENV}")
    return m.group(1).strip()


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


def run(*, dry_run: bool) -> int:
    text = _INVENTORY.read_text()
    domains = parse_domains(text)
    entities = parse_entities(text)
    personas = parse_personas(text)

    print(f"Parsed: {len(domains)} domains, {len(entities)} entities, "
          f"{len(personas)} personas")
    edge_count = sum(len(e["domains"]) for e in entities)
    print(f"        {edge_count} entity_scopes_to_domain edges")

    if dry_run:
        print("\n--- DOMAINS ---")
        for d in domains:
            print(f"  {d['name']}")
        print("\n--- ENTITIES (name → domains) ---")
        for e in sorted(entities, key=lambda x: x["name"].lower()):
            print(f"  {e['name']}  ←  {sorted(e['domains'])}")
        print("\n--- PERSONAS ---")
        for p in personas:
            print(f"  {p['name']}")
        print("\n(dry run — nothing written)")
        return 0

    api = Api()
    # Existing names for idempotency.
    have_domains = api.list_names("domains", "domain_name")
    have_entities = api.list_names("entities", "entity_name")
    have_personas = api.list_names("personas", "persona_name")

    # Resolve domain/entity name → identifier for edge creation.
    domain_id: dict[str, str] = {}
    entity_id: dict[str, str] = {}

    # Domains.
    created_d = 0
    for d in domains:
        if d["name"].lower() in have_domains:
            existing = _find_identifier(api, "domains", "domain_name",
                                        "domain_identifier", d["name"])
            domain_id[d["name"]] = existing
            print(f"  domain exists: {d['name']} ({existing})")
            continue
        res = api.post("domains", {
            "domain_name": d["name"],
            "domain_purpose": d["purpose"],
            "domain_description": d["description"],
        })
        if res.get("errors"):
            print(f"  DOMAIN ERROR {d['name']}: {res['errors']}")
            continue
        ident = res["data"]["domain_identifier"]
        domain_id[d["name"]] = ident
        created_d += 1
        print(f"  + domain {ident}: {d['name']}")

    # Entities.
    created_e = 0
    for e in entities:
        if e["name"].lower() in have_entities:
            existing = _find_identifier(api, "entities", "entity_name",
                                        "entity_identifier", e["name"])
            entity_id[e["name"]] = existing
            print(f"  entity exists: {e['name']} ({existing})")
            continue
        res = api.post("entities", {
            "entity_name": e["name"],
            "entity_description": e["description"],
        })
        if res.get("errors"):
            print(f"  ENTITY ERROR {e['name']}: {res['errors']}")
            continue
        ident = res["data"]["entity_identifier"]
        entity_id[e["name"]] = ident
        created_e += 1
        print(f"  + entity {ident}: {e['name']}")

    # entity_scopes_to_domain edges.
    created_edges = 0
    for e in entities:
        eid = entity_id.get(e["name"])
        if not eid:
            continue
        for dname in sorted(e["domains"]):
            did = domain_id.get(dname)
            if not did:
                continue
            res = api.post("references", {
                "source_type": "entity", "source_id": eid,
                "target_type": "domain", "target_id": did,
                "relationship": "entity_scopes_to_domain",
            })
            if res.get("errors"):
                # 409 duplicate is expected on re-run; report others.
                msg = str(res["errors"])
                if "already exists" not in msg:
                    print(f"  EDGE ERROR {eid}->{did}: {msg}")
                continue
            created_edges += 1

    # Personas.
    created_p = 0
    for p in personas:
        if p["name"].lower() in have_personas:
            print(f"  persona exists: {p['name']}")
            continue
        res = api.post("personas", {
            "persona_name": p["name"],
            "persona_role_summary": p["role_summary"],
        })
        if res.get("errors"):
            print(f"  PERSONA ERROR {p['name']}: {res['errors']}")
            continue
        created_p += 1
        print(f"  + persona {res['data']['persona_identifier']}: {p['name']}")

    print(f"\nCreated: {created_d} domains, {created_e} entities, "
          f"{created_edges} edges, {created_p} personas")
    return 0


def _find_identifier(api: Api, endpoint: str, name_key: str,
                     id_key: str, name: str) -> str | None:
    res = api._call("GET", f"/{endpoint}")
    for r in res.get("data") or []:
        if (r.get(name_key) or "").lower() == name.lower():
            return r[id_key]
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="parse and print the plan without writing")
    args = ap.parse_args()
    if not _INVENTORY.exists():
        print(f"inventory not found: {_INVENTORY}", file=sys.stderr)
        return 1
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
