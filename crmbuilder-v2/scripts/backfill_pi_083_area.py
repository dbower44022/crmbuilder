"""PI-083 — backfill the ``area`` field on currently-open planning items.

Two-phase, Doug-in-the-loop tooling (PI-083 requires a spot-check before
bulk-applying and mutates live governance data, so inference and
application are deliberately separate):

    # 1. Propose — fetch every Open planning item with a null area,
    #    infer area set(s) from title + description, write an editable
    #    proposal file. Mutates nothing.
    uv run python scripts/backfill_pi_083_area.py propose \
        --api-base http://127.0.0.1:8765 --out /tmp/pi083-proposal.json

    # 2. (Doug spot-checks / edits /tmp/pi083-proposal.json.)

    # 3. Apply — PATCH each item's area from the (reviewed) proposal.
    uv run python scripts/backfill_pi_083_area.py apply \
        --api-base http://127.0.0.1:8765 --from /tmp/pi083-proposal.json

``infer_areas`` is a deterministic keyword/path heuristic — a *starting
point* for Doug's review, not an oracle. Items it cannot classify are
emitted with an empty ``area`` and ``needs_review: true`` so they stand
out in the proposal. After every Open item carries an area, the NOT NULL
tightening migration (authored under
``crmbuilder-v2/migrations/deferred/``) is moved into ``versions/`` and
applied — that step is gated on this backfill completing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# vocab.AREAS is the source of truth; import it so the heuristic can never
# propose an unregistered area (and so adding an area to the vocab is the
# only edit needed to make it proposable).
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
from crmbuilder_v2.access.vocab import AREAS  # noqa: E402

# Ordered (compiled-pattern, area) rules. A planning item is matched
# against the union of its title + description; every area whose pattern
# fires is added (multi-valued per DEC-247). Order only affects the
# output order of the proposed list, not membership.
_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bmcp\b|claude\.ai|stdio|streamable", re.I), "v2-mcp"),
    (re.compile(r"\bui\b|panel|dialog|desktop|pyside|qt\b|qwidget|sidebar|widget", re.I), "v2-ui"),
    (re.compile(r"\bapi\b|endpoint|router|fastapi|pydantic|\brest\b|envelope", re.I), "v2-api"),
    (re.compile(r"access[- ]layer|repositor|validator|\bvocab\b|relationship_kind", re.I), "v2-access"),
    (re.compile(r"migration|alembic|schema|\bcolumn\b|\btable\b|sqlite|\bdatabase\b|check constraint", re.I), "v2-storage"),
    (re.compile(r"methodology.*interview|interview.*guide|conduct|question[- ]library|kickoff", re.I), "methodology-interviews"),
    (re.compile(r"\bphase\b|process[- ]definition|13-phase|5-phase|domain discovery|reconciliation", re.I), "methodology-process"),
    (re.compile(r"\btemplate\b|verification spec", re.I), "methodology-templates"),
    (re.compile(r"master prd|product requirements|domain prd|entity prd", re.I), "methodology-product"),
    (re.compile(r"cloudflare|oauth|tunnel|systemd|digitalocean|droplet|deploy(?!ment engine)|\bdns\b|nginx|certbot", re.I), "infrastructure"),
    (re.compile(r"espocrm|espo_impl|c-prefix", re.I), "v1-espo"),
    (re.compile(r"automation/|setup wizard|upgrade|recovery|ssh", re.I), "v1-automation"),
    (re.compile(r"programs/|yaml program|\bFU-|\bMR-|\bCR-|\bMN-", re.I), "v1-programs"),
    (re.compile(r"\bcbm\b|cleveland", re.I), "cbm-services"),
]


def infer_areas(title: str, description: str) -> list[str]:
    """Best-guess area set for a planning item from its title + description.

    Deterministic keyword/path heuristic. Returns areas in :data:`AREAS`
    order, de-duplicated; an empty list means "no signal — needs manual
    review". Never returns an unregistered area.
    """
    haystack = f"{title}\n{description}"
    hits: set[str] = set()
    for pattern, area in _RULES:
        if area in AREAS and pattern.search(haystack):
            hits.add(area)
    # Stable output order: follow the canonical AREAS ordering.
    ordered = [a for a in _area_order() if a in hits]
    return ordered


def _area_order() -> list[str]:
    # AREAS is a frozenset; pin a deterministic order for output.
    return [
        "v2-storage", "v2-access", "v2-api", "v2-mcp", "v2-ui",
        "cbm-mn", "cbm-mr", "cbm-cr", "cbm-fu", "cbm-services",
        "methodology-interviews", "methodology-process",
        "methodology-templates", "methodology-product",
        "infrastructure", "v1-automation", "v1-espo", "v1-programs",
    ]


def _unwrap(resp_json: dict) -> object:
    """Unwrap the {data, meta, errors} envelope."""
    return resp_json["data"]


def _open_unassigned(api_base: str) -> list[dict]:
    import requests

    r = requests.get(f"{api_base.rstrip('/')}/planning-items", timeout=30)
    r.raise_for_status()
    items = _unwrap(r.json())
    return [
        pi
        for pi in items
        if pi.get("status") == "Open" and not pi.get("area")
    ]


def cmd_propose(args: argparse.Namespace) -> int:
    items = _open_unassigned(args.api_base)
    proposal = []
    for pi in items:
        areas = infer_areas(pi.get("title", ""), pi.get("description", ""))
        proposal.append(
            {
                "identifier": pi["identifier"],
                "title": pi.get("title", ""),
                "area": areas,
                "needs_review": not areas,
            }
        )
    out = Path(args.out)
    out.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    needs = sum(1 for p in proposal if p["needs_review"])
    print(f"proposed areas for {len(proposal)} open planning items -> {out}")
    print(f"  {needs} need manual review (no heuristic signal)")
    print("Review/edit the file, then run the 'apply' subcommand.")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    import requests

    proposal = json.loads(Path(args.proposal_path).read_text(encoding="utf-8"))
    base = args.api_base.rstrip("/")
    applied = skipped = 0
    for entry in proposal:
        ident, areas = entry["identifier"], entry.get("area") or []
        if not areas:
            print(f"  SKIP {ident}: empty area (still needs review)")
            skipped += 1
            continue
        r = requests.patch(f"{base}/planning-items/{ident}", json={"area": areas}, timeout=30)
        if r.status_code != 200:
            print(f"  FAIL {ident}: HTTP {r.status_code} {r.text}")
            skipped += 1
            continue
        print(f"  OK   {ident}: {areas}")
        applied += 1
    print(f"applied {applied}, skipped {skipped}")
    print(
        "Once every Open planning item carries an area, move "
        "migrations/deferred/0027_pi_083_planning_item_area_not_null.py "
        "into migrations/versions/ and run `alembic upgrade head`."
    )
    return 0 if skipped == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="PI-083 area backfill tooling")
    sub = p.add_subparsers(dest="command", required=True)

    pr = sub.add_parser("propose", help="write an editable area proposal")
    pr.add_argument("--api-base", default="http://127.0.0.1:8765")
    pr.add_argument("--out", required=True, help="proposal JSON output path")
    pr.set_defaults(func=cmd_propose)

    ap = sub.add_parser("apply", help="PATCH areas from a reviewed proposal")
    ap.add_argument("--api-base", default="http://127.0.0.1:8765")
    ap.add_argument("--from", dest="proposal_path", required=True, help="proposal JSON path")
    ap.set_defaults(func=cmd_apply)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
