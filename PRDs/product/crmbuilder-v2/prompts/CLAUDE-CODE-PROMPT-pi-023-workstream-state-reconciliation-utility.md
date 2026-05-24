# CLAUDE-CODE-PROMPT — PI-023 workstream-state reconciliation utility

**Last Updated:** 05-24-26 15:35
**Purpose:** PI-023 build phase. Author `crmbuilder-v2/scripts/reconcile.py` (the workstream-state reconciliation utility — read-only, snapshot-driven, allowlist-aware, plain-text-output drift detector for the v2 governance graph) and `PRDs/product/crmbuilder-v2/reconciliation-allowlist.yaml` (the v1 allowlist with 6 entries covering 7 known data-quality artifacts). Run the first reconciliation against the current db-export snapshots and verify it produces 7 findings, all allowlisted, exit code 0. Then transition PI-022's planning item from Open to Resolved via the V2 API, closing the PI-022 governance-backfill program. Discharges PI-023 per the kickoff at `PRDs/product/crmbuilder-v2/pi-023-workstream-state-reconciliation-utility-kickoff.md` and per DEC-216..220 settled in SES-069.
**Script files:**
- `crmbuilder-v2/scripts/reconcile.py` (this prompt authors it from the embedded source below, then runs it)
- `PRDs/product/crmbuilder-v2/reconciliation-allowlist.yaml` (this prompt authors it from the embedded source below)
**Predecessor:** The SES-069 close-out apply at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-069.md` **must be applied before this prompt runs**. The SES-069 apply lands DEC-216..220 and PI-048; the allowlist YAML references DEC-216, DEC-215, DEC-210, PI-047, and PI-048 — every entry must resolve in the snapshots or reconcile.py exits 2 with a configuration error at startup. Apply order: SES-069 close-out → this PI-023 build prompt. The pre-flight section verifies SES-069 has landed.

---

## Net effect

Files that exist on disk after this prompt runs:

- **`crmbuilder-v2/scripts/reconcile.py`** — the reconciliation utility, ~890 lines of Python. Standalone script, no internal package imports. Single external dependency: PyYAML. Auto-detects the repository root by walking up until a `.git` directory is found. Default paths: `--db-export PRDs/product/crmbuilder-v2/db-export/`, `--payloads-dir PRDs/product/crmbuilder-v2/close-out-payloads/`, `--allowlist PRDs/product/crmbuilder-v2/reconciliation-allowlist.yaml`. Exit codes: 0 (no unallowlisted drift), 1 (unallowlisted drift), 2 (configuration error — allowlist references unknown records, snapshot file missing, etc.).

- **`PRDs/product/crmbuilder-v2/reconciliation-allowlist.yaml`** — the v1 allowlist, 106 lines, 6 entries. Each entry carries a `decided_in` (DEC-NNN) or `planning_item` (PI-NNN) field as the required canonical-record reference and a `drift_pattern` field describing what it matches. Schema-level documentation lives in the file's top comment.

Database state changes from this prompt:

- **PI-022's planning_item transitions from `Open` to `Resolved`** via PATCH to `http://127.0.0.1:8765/planning-items/PI-022`. The status change is the formal close of the PI-022 governance-backfill program (Phases 1–4 plus the PI-023 reconciliation utility's first successful run together constitute the program's completion). The PI-022 record's title and description are unchanged; only the status field flips.

No new sessions, decisions, references, COPs, or DEPs are created by this prompt. The PI-022 PATCH does trigger the `_refresh_snapshot` hook on `crmbuilder-v2/src/crmbuilder_v2/access/engagement.py`, which regenerates `PRDs/product/crmbuilder-v2/db-export/planning_items.json` and appends an audit row to `PRDs/product/crmbuilder-v2/db-export/change_log.json`.

---

## Pre-flight

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

# Clean working tree
git status

# Pull latest commits
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start the API:
#   uv run crmbuilder-v2-api &

# Verify the SES-069 apply has landed (predecessor check)
for d in DEC-216 DEC-217 DEC-218 DEC-219 DEC-220; do
  curl -sf "http://127.0.0.1:8765/decisions/$d" >/dev/null && echo "$d OK" || { echo "$d MISSING — apply SES-069 close-out first"; exit 1; }
done
curl -sf "http://127.0.0.1:8765/planning-items/PI-048" >/dev/null && echo "PI-048 OK" || { echo "PI-048 MISSING — apply SES-069 close-out first"; exit 1; }

# Verify PI-022 exists and is currently at status=Open
curl -s http://127.0.0.1:8765/planning-items/PI-022 | python3 -c "
import sys, json
d = json.load(sys.stdin)['data']
print(f'PI-022 status: {d[\"status\"]}')
assert d['status'] == 'Open', f'PI-022 unexpectedly at status={d[\"status\"]} (expected Open) — halt'
"

# Verify the script and allowlist files do NOT yet exist (first-run sanity)
[ -e crmbuilder-v2/scripts/reconcile.py ] && { echo "reconcile.py already exists — this prompt is for first authoring; halt and investigate"; exit 1; } || echo "reconcile.py absent (expected)"
[ -e ../PRDs/product/crmbuilder-v2/reconciliation-allowlist.yaml ] && { echo "reconciliation-allowlist.yaml already exists — this prompt is for first authoring; halt and investigate"; exit 1; } || echo "reconciliation-allowlist.yaml absent (expected)"

# Verify PyYAML is available (reconcile.py imports yaml)
uv run python -c "import yaml; print(f'PyYAML {yaml.__version__} available')" || {
  echo "PyYAML missing — add via: uv add pyyaml"
  exit 1
}

# Capture pre-step heads (no records created, but capture for the done report)
echo "=== Pre-step state ==="
echo "Sessions head:"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1])"
echo "Decisions head:"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1])"
echo "Planning items head:"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1])"
```

Expected pre-step state:

| Resource | Value |
|---|---|
| Sessions head | SES-069 |
| Decisions head | DEC-220 |
| Planning items head | PI-048 |
| PI-022 status | Open |
| reconcile.py | absent |
| reconciliation-allowlist.yaml | absent |

If any of these do not match, halt and investigate before proceeding.

---

## Step 1 — Author reconcile.py and reconciliation-allowlist.yaml

Create the two files from the embedded source below.

### File 1 of 2: `crmbuilder-v2/scripts/reconcile.py`

```python
#!/usr/bin/env python3
"""PI-023 workstream-state reconciliation utility.

Read-only utility that detects git-vs-database state drift in the v2
governance graph. Invoked at the pre-flight of close-out conversations
to confirm the close-out payload JSON files on disk and the db-export
snapshots agree on what the governance graph contains.

Reads exclusively from the ``PRDs/product/crmbuilder-v2/db-export/``
JSON snapshots (per DEC-219 in SES-069) — no V2 REST API dependency, so
the utility runs in any sandbox or local terminal.

Drift classes checked in v1 (per DEC-217 in SES-069):

- Class 1 (file vs record presence): every close-out payload JSON file
  has a corresponding COP record, every COP record's file_path resolves
  to an extant file.
- Class 2 (record-claims-vs-record-presence): every record a payload
  JSON claims it created (session, decisions, planning_items,
  references) exists in the database with the claimed identifier.
- Class 3 (decision-vs-records consistency, allowlist-driven): every
  allowlist entry whose drift_pattern matches a record set is reported
  as EXPECTED; supersedes edges are traversed so that allowlist entries
  referencing decisions which are themselves the target of a supersedes
  edge are flagged as stale.

Allowlist mechanism (per DEC-218 in SES-069): YAML file at
``PRDs/product/crmbuilder-v2/reconciliation-allowlist.yaml``. Each
entry references a governing decision (``decided_in``) or planning
item (``planning_item``) plus a ``drift_pattern`` describing the
records the entry covers.

Output format (per DEC-220 in SES-069): structured plain text on
stdout. Findings are severity-prefixed (``EXPECTED`` / ``DRIFT``);
exit code is 0 when every finding is allowlisted, 1 when any
unallowlisted drift exists, 2 when the allowlist or snapshots are
malformed.

Usage::

    uv run python scripts/reconcile.py
    uv run python scripts/reconcile.py --allowlist PATH
    uv run python scripts/reconcile.py --db-export PATH --payloads-dir PATH
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    print(
        "reconcile.py: PyYAML is required. Install via `uv add pyyaml` "
        "or `pip install pyyaml`.",
        file=sys.stderr,
    )
    sys.exit(2)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _find_repo_root(start: Path) -> Path:
    """Walk up from ``start`` until a directory containing ``.git`` is found."""
    cur = start.resolve()
    while cur != cur.parent:
        if (cur / ".git").exists():
            return cur
        cur = cur.parent
    raise RuntimeError(
        f"reconcile.py: could not find repository root from {start}; "
        "no .git directory encountered while walking upward."
    )


DEFAULT_DB_EXPORT_REL = Path("PRDs/product/crmbuilder-v2/db-export")
DEFAULT_PAYLOADS_REL = Path("PRDs/product/crmbuilder-v2/close-out-payloads")
DEFAULT_ALLOWLIST_REL = Path(
    "PRDs/product/crmbuilder-v2/reconciliation-allowlist.yaml"
)


# ---------------------------------------------------------------------------
# Finding model
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    drift_class: int  # 1, 2, or 3
    severity: str  # "EXPECTED" or "DRIFT"
    allowlist_key: str | None  # entry name for EXPECTED; None for DRIFT
    canonical_record: str | None  # DEC-NNN / PI-NNN for EXPECTED; None for DRIFT
    summary: str

    def format(self) -> str:
        prefix = self.severity.ljust(8)
        if self.severity == "EXPECTED":
            assert self.allowlist_key is not None
            assert self.canonical_record is not None
            return (
                f"  {prefix}  {self.allowlist_key} ({self.canonical_record}): "
                f"{self.summary}"
            )
        return f"  {prefix}  {self.summary}"


@dataclass
class Report:
    class_1: list[Finding] = field(default_factory=list)
    class_2: list[Finding] = field(default_factory=list)
    class_3: list[Finding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def all_findings(self) -> Iterable[Finding]:
        yield from self.class_1
        yield from self.class_2
        yield from self.class_3

    @property
    def expected_count(self) -> int:
        return sum(1 for f in self.all_findings if f.severity == "EXPECTED")

    @property
    def drift_count(self) -> int:
        return sum(1 for f in self.all_findings if f.severity == "DRIFT")


# ---------------------------------------------------------------------------
# Snapshot + payload loading
# ---------------------------------------------------------------------------

REQUIRED_SNAPSHOT_FILES = [
    "sessions.json",
    "decisions.json",
    "planning_items.json",
    "references.json",
    "close_out_payloads.json",
    "deposit_events.json",
]


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_snapshots(db_export: Path) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for name in REQUIRED_SNAPSHOT_FILES:
        path = db_export / name
        if not path.exists():
            raise FileNotFoundError(
                f"reconcile.py: required snapshot file missing: {path}"
            )
        data = _load_json(path)
        # Snapshots are bare JSON arrays in current shape; accept dict wrappers
        # defensively in case the export format ever changes.
        if isinstance(data, dict):
            data = data.get("data", data.get(name.split(".")[0], []))
        if not isinstance(data, list):
            raise ValueError(
                f"reconcile.py: snapshot file {path} did not parse as a list "
                f"(got {type(data).__name__})."
            )
        out[name.split(".")[0]] = data
    return out


def load_payloads(payloads_dir: Path) -> dict[str, dict[str, Any]]:
    """Return a dict keyed by filename (stem.json) → payload contents."""
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(payloads_dir.glob("ses_*.json")):
        out[path.name] = _load_json(path)
    return out


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------

@dataclass
class AllowlistEntry:
    name: str
    description: str
    decided_in: str | None  # DEC-NNN
    planning_item: str | None  # PI-NNN
    drift_pattern: dict[str, Any]

    @property
    def canonical_record(self) -> str:
        # decided_in takes precedence for display when both are set
        return self.decided_in or self.planning_item or "<unknown>"


def load_allowlist(path: Path) -> list[AllowlistEntry]:
    if not path.exists():
        # Missing allowlist is non-fatal — treat as empty allowlist.
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        raise ValueError(
            f"reconcile.py: allowlist {path} did not parse as a list "
            f"(got {type(raw).__name__})."
        )
    entries: list[AllowlistEntry] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(
                f"reconcile.py: allowlist entry #{idx + 1} is not a mapping."
            )
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(
                f"reconcile.py: allowlist entry #{idx + 1} missing `name`."
            )
        decided_in = item.get("decided_in")
        planning_item = item.get("planning_item")
        if not (decided_in or planning_item):
            raise ValueError(
                f"reconcile.py: allowlist entry `{name}` must carry "
                "either `decided_in` (DEC-NNN) or `planning_item` (PI-NNN)."
            )
        drift_pattern = item.get("drift_pattern") or {}
        if not isinstance(drift_pattern, dict):
            raise ValueError(
                f"reconcile.py: allowlist entry `{name}` has invalid "
                "`drift_pattern` (must be a mapping)."
            )
        entries.append(
            AllowlistEntry(
                name=name,
                description=item.get("description", ""),
                decided_in=decided_in,
                planning_item=planning_item,
                drift_pattern=drift_pattern,
            )
        )
    return entries


def validate_allowlist(
    entries: list[AllowlistEntry], snapshots: dict[str, list[dict[str, Any]]]
) -> list[str]:
    """Return a list of allowlist-config errors. Empty list means valid."""
    errors: list[str] = []
    dec_ids = {d["identifier"] for d in snapshots["decisions"]}
    pi_ids = {p["identifier"] for p in snapshots["planning_items"]}
    for e in entries:
        if e.decided_in and e.decided_in not in dec_ids:
            errors.append(
                f"allowlist entry `{e.name}` references {e.decided_in} which "
                "is not in the decisions snapshot."
            )
        if e.planning_item and e.planning_item not in pi_ids:
            errors.append(
                f"allowlist entry `{e.name}` references {e.planning_item} "
                "which is not in the planning_items snapshot."
            )
        pat_type = e.drift_pattern.get("type")
        valid_types = {
            "records_summary_field",
            "unresolved_payload_references",
            "payload_files_without_cop",
        }
        if pat_type and pat_type not in valid_types:
            errors.append(
                f"allowlist entry `{e.name}` has unknown drift_pattern.type "
                f"`{pat_type}`; valid: {sorted(valid_types)}."
            )
    return errors


# ---------------------------------------------------------------------------
# Identifier helpers
# ---------------------------------------------------------------------------

def _identifier_in_range(identifier: str, lo: str, hi: str) -> bool:
    """``DEP-020`` is in range ``DEP-020..DEP-043`` etc. Prefix must match."""
    pfx_id, _, num_id = identifier.partition("-")
    pfx_lo, _, num_lo = lo.partition("-")
    pfx_hi, _, num_hi = hi.partition("-")
    if pfx_id != pfx_lo or pfx_id != pfx_hi:
        return False
    try:
        return int(num_lo) <= int(num_id) <= int(num_hi)
    except ValueError:
        return False


def _parse_range(spec: str) -> tuple[str, str]:
    """``DEP-020..DEP-043`` → (``DEP-020``, ``DEP-043``)."""
    if ".." not in spec:
        raise ValueError(
            f"reconcile.py: identifier range `{spec}` missing `..` separator."
        )
    lo, hi = spec.split("..", 1)
    return lo.strip(), hi.strip()


# ---------------------------------------------------------------------------
# Class 1 — file vs record presence
# ---------------------------------------------------------------------------

def check_class_1(
    snapshots: dict[str, list[dict[str, Any]]],
    payloads: dict[str, dict[str, Any]],
    payloads_dir: Path,
    repo_root: Path,
    allowlist: list[AllowlistEntry],
) -> list[Finding]:
    findings: list[Finding] = []

    # Pre-index payload_files_without_cop allowlist entries by filename.
    files_without_cop_allowed: dict[str, AllowlistEntry] = {}
    for entry in allowlist:
        if entry.drift_pattern.get("type") == "payload_files_without_cop":
            for f in entry.drift_pattern.get("payload_files", []) or []:
                files_without_cop_allowed[f] = entry

    # File → COP record direction.
    cop_file_paths = {
        c.get("close_out_payload_file_path"): c["close_out_payload_identifier"]
        for c in snapshots["close_out_payloads"]
        if c.get("close_out_payload_file_path")
    }
    # Normalise to repo-relative paths for comparison.
    payloads_rel = payloads_dir.relative_to(repo_root)
    for filename in payloads:
        rel = str(payloads_rel / filename)
        if rel not in cop_file_paths:
            entry = files_without_cop_allowed.get(filename)
            if entry is not None:
                findings.append(
                    Finding(
                        drift_class=1,
                        severity="EXPECTED",
                        allowlist_key=entry.name,
                        canonical_record=entry.canonical_record,
                        summary=(
                            f"payload file {filename} has no close_out_payload "
                            "record (orphan-session file)."
                        ),
                    )
                )
            else:
                findings.append(
                    Finding(
                        drift_class=1,
                        severity="DRIFT",
                        allowlist_key=None,
                        canonical_record=None,
                        summary=(
                            f"payload file {filename} has no corresponding "
                            f"close_out_payload record (looked for file_path "
                            f"`{rel}`)."
                        ),
                    )
                )

    # COP record → file direction.
    for cop in snapshots["close_out_payloads"]:
        fp = cop.get("close_out_payload_file_path")
        identifier = cop["close_out_payload_identifier"]
        if not fp:
            findings.append(
                Finding(
                    drift_class=1,
                    severity="DRIFT",
                    allowlist_key=None,
                    canonical_record=None,
                    summary=(
                        f"{identifier} carries no close_out_payload_file_path."
                    ),
                )
            )
            continue
        on_disk = repo_root / fp
        if not on_disk.exists():
            findings.append(
                Finding(
                    drift_class=1,
                    severity="DRIFT",
                    allowlist_key=None,
                    canonical_record=None,
                    summary=(
                        f"{identifier}'s file_path `{fp}` does not exist on disk."
                    ),
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Class 2 — record-claims-vs-record-presence
# ---------------------------------------------------------------------------

def check_class_2(
    snapshots: dict[str, list[dict[str, Any]]],
    payloads: dict[str, dict[str, Any]],
    allowlist: list[AllowlistEntry],
) -> list[Finding]:
    findings: list[Finding] = []

    session_ids = {s["identifier"] for s in snapshots["sessions"]}
    decision_ids = {d["identifier"] for d in snapshots["decisions"]}
    pi_ids = {p["identifier"] for p in snapshots["planning_items"]}

    # Build a reference-set keyed by the payload's reference shape (no
    # reference_identifier; just the 5-tuple). The snapshot's column is
    # ``relationship_kind``, but the payload key is ``relationship`` —
    # mismatch documented in v2 close-out emission conventions; we match
    # against the snapshot's ``relationship_kind`` field.
    ref_set: set[tuple[str, str, str, str, str]] = {
        (
            r["source_type"],
            r["source_id"],
            r["target_type"],
            r["target_id"],
            r["relationship_kind"],
        )
        for r in snapshots["references"]
    }

    # Index allowlist entries that cover unresolved-payload-references patterns.
    unresolved_ref_entries: list[tuple[AllowlistEntry, dict[str, Any]]] = []
    for entry in allowlist:
        pat = entry.drift_pattern
        if pat.get("type") == "unresolved_payload_references":
            unresolved_ref_entries.append((entry, pat))

    for filename, payload in payloads.items():
        # Session claim.
        sess = payload.get("session", {}) or {}
        sess_id = sess.get("identifier")
        if sess_id and sess_id not in session_ids:
            findings.append(
                Finding(
                    drift_class=2,
                    severity="DRIFT",
                    allowlist_key=None,
                    canonical_record=None,
                    summary=(
                        f"{filename} claims session {sess_id}, which is not "
                        "in the sessions snapshot."
                    ),
                )
            )

        # Decision claims.
        for d in payload.get("decisions", []) or []:
            d_id = d.get("identifier")
            if d_id and d_id not in decision_ids:
                findings.append(
                    Finding(
                        drift_class=2,
                        severity="DRIFT",
                        allowlist_key=None,
                        canonical_record=None,
                        summary=(
                            f"{filename} claims decision {d_id}, which is not "
                            "in the decisions snapshot."
                        ),
                    )
                )

        # Planning item claims.
        for pi in payload.get("planning_items", []) or []:
            pi_id = pi.get("identifier")
            if pi_id and pi_id not in pi_ids:
                findings.append(
                    Finding(
                        drift_class=2,
                        severity="DRIFT",
                        allowlist_key=None,
                        canonical_record=None,
                        summary=(
                            f"{filename} claims planning item {pi_id}, which "
                            "is not in the planning_items snapshot."
                        ),
                    )
                )

        # Reference claims. Payload uses field key ``relationship`` even
        # though the snapshot column is ``relationship_kind``.
        unresolved = []
        for r in payload.get("references", []) or []:
            key = (
                r.get("source_type"),
                r.get("source_id"),
                r.get("target_type"),
                r.get("target_id"),
                r.get("relationship"),
            )
            if key not in ref_set:
                unresolved.append(r)

        if unresolved:
            # Try to match an allowlist entry. The pattern matches on
            # ``payload_file`` and ``expected_unresolved_count``.
            matched_entry: AllowlistEntry | None = None
            for entry, pat in unresolved_ref_entries:
                if pat.get("payload_file") != filename:
                    continue
                expected = pat.get("expected_unresolved_count")
                if expected is not None and expected != len(unresolved):
                    continue
                matched_entry = entry
                break

            if matched_entry is not None:
                findings.append(
                    Finding(
                        drift_class=2,
                        severity="EXPECTED",
                        allowlist_key=matched_entry.name,
                        canonical_record=matched_entry.canonical_record,
                        summary=(
                            f"{filename} claims {len(unresolved)} references "
                            "that do not resolve in the references snapshot."
                        ),
                    )
                )
            else:
                findings.append(
                    Finding(
                        drift_class=2,
                        severity="DRIFT",
                        allowlist_key=None,
                        canonical_record=None,
                        summary=(
                            f"{filename} claims {len(unresolved)} references "
                            "that do not resolve in the references snapshot "
                            f"(first: {unresolved[0]})."
                        ),
                    )
                )

    return findings


# ---------------------------------------------------------------------------
# Class 3 — decision-vs-records (allowlist-driven; supersedes-aware)
# ---------------------------------------------------------------------------

def _build_supersedes_index(
    references: list[dict[str, Any]],
) -> dict[str, set[str]]:
    """Return ``superseded_by``: target_id → set of source_ids that supersede it.

    A decision DEC-X is "superseded" iff there exists a reference with
    source_type=decision, target_type=decision, target_id=DEC-X,
    relationship_kind=supersedes.
    """
    out: dict[str, set[str]] = {}
    for r in references:
        if (
            r.get("source_type") == "decision"
            and r.get("target_type") == "decision"
            and r.get("relationship_kind") == "supersedes"
        ):
            target = r.get("target_id")
            source = r.get("source_id")
            if target and source:
                out.setdefault(target, set()).add(source)
    return out


def check_class_3(
    snapshots: dict[str, list[dict[str, Any]]],
    allowlist: list[AllowlistEntry],
) -> list[Finding]:
    findings: list[Finding] = []

    deps_by_id = {
        d["deposit_event_identifier"]: d for d in snapshots["deposit_events"]
    }
    decisions_by_id = {d["identifier"]: d for d in snapshots["decisions"]}
    pis_by_id = {p["identifier"]: p for p in snapshots["planning_items"]}

    superseded_by = _build_supersedes_index(snapshots["references"])

    for entry in allowlist:
        pat = entry.drift_pattern
        pat_type = pat.get("type")
        if pat_type != "records_summary_field":
            # Class 3 only handles records_summary_field patterns; the
            # unresolved_payload_references type is consumed by Class 2.
            continue

        # Validate canonical record is still active in some sense.
        if entry.decided_in:
            dec = decisions_by_id.get(entry.decided_in)
            if dec is None:
                # Validation should have caught this; emit as DRIFT to be safe.
                findings.append(
                    Finding(
                        drift_class=3,
                        severity="DRIFT",
                        allowlist_key=None,
                        canonical_record=None,
                        summary=(
                            f"allowlist entry `{entry.name}` references "
                            f"{entry.decided_in} which is not in the decisions "
                            "snapshot."
                        ),
                    )
                )
                continue
            # Supersedes check: if entry's DEC is superseded, the entry is stale.
            if entry.decided_in in superseded_by:
                supersedors = sorted(superseded_by[entry.decided_in])
                findings.append(
                    Finding(
                        drift_class=3,
                        severity="DRIFT",
                        allowlist_key=None,
                        canonical_record=None,
                        summary=(
                            f"allowlist entry `{entry.name}` references "
                            f"{entry.decided_in}, which is superseded by "
                            f"{', '.join(supersedors)}; update the entry to "
                            "cite the superseding decision."
                        ),
                    )
                )
                continue

        if entry.planning_item:
            pi = pis_by_id.get(entry.planning_item)
            if pi is None:
                findings.append(
                    Finding(
                        drift_class=3,
                        severity="DRIFT",
                        allowlist_key=None,
                        canonical_record=None,
                        summary=(
                            f"allowlist entry `{entry.name}` references "
                            f"{entry.planning_item} which is not in the "
                            "planning_items snapshot."
                        ),
                    )
                )
                continue

        # Apply the pattern: records_summary_field matches DEP records in
        # an identifier range whose records_summary[field] equals expected_value.
        rec_type = pat.get("record_type")
        if rec_type != "deposit_event":
            findings.append(
                Finding(
                    drift_class=3,
                    severity="DRIFT",
                    allowlist_key=None,
                    canonical_record=None,
                    summary=(
                        f"allowlist entry `{entry.name}` records_summary_field "
                        f"pattern targets unsupported record_type "
                        f"`{rec_type}` (only `deposit_event` supported in v1)."
                    ),
                )
            )
            continue

        range_spec = pat.get("identifier_range", "")
        try:
            lo, hi = _parse_range(range_spec)
        except ValueError as exc:
            findings.append(
                Finding(
                    drift_class=3,
                    severity="DRIFT",
                    allowlist_key=None,
                    canonical_record=None,
                    summary=(
                        f"allowlist entry `{entry.name}`: {exc}"
                    ),
                )
            )
            continue

        # ``field`` is dotted, e.g. records_summary.references → access
        # deposit_event_records_summary["references"].
        field_path = pat.get("field", "")
        if not field_path.startswith("records_summary."):
            findings.append(
                Finding(
                    drift_class=3,
                    severity="DRIFT",
                    allowlist_key=None,
                    canonical_record=None,
                    summary=(
                        f"allowlist entry `{entry.name}` field `{field_path}` "
                        "must start with `records_summary.`."
                    ),
                )
            )
            continue
        sub_key = field_path[len("records_summary."):]
        expected = pat.get("expected_value")

        matched_ids: list[str] = []
        mismatched_ids: list[tuple[str, Any]] = []
        for dep_id, dep in deps_by_id.items():
            if not _identifier_in_range(dep_id, lo, hi):
                continue
            rs = dep.get("deposit_event_records_summary") or {}
            actual = rs.get(sub_key)
            if actual == expected:
                matched_ids.append(dep_id)
            else:
                mismatched_ids.append((dep_id, actual))

        if not matched_ids and not mismatched_ids:
            findings.append(
                Finding(
                    drift_class=3,
                    severity="DRIFT",
                    allowlist_key=None,
                    canonical_record=None,
                    summary=(
                        f"allowlist entry `{entry.name}` matches no records "
                        f"in range {range_spec} (stale entry?)."
                    ),
                )
            )
            continue

        # Emit the EXPECTED finding for matched DEPs.
        findings.append(
            Finding(
                drift_class=3,
                severity="EXPECTED",
                allowlist_key=entry.name,
                canonical_record=entry.canonical_record,
                summary=(
                    f"{lo}..{hi} {field_path}={expected!r} "
                    f"({len(matched_ids)} of {len(matched_ids) + len(mismatched_ids)} "
                    "records in range)."
                ),
            )
        )
        # And DRIFT for any DEPs in range that DON'T match the expected value.
        if mismatched_ids:
            sample = mismatched_ids[0]
            findings.append(
                Finding(
                    drift_class=3,
                    severity="DRIFT",
                    allowlist_key=None,
                    canonical_record=None,
                    summary=(
                        f"{len(mismatched_ids)} records in range "
                        f"{range_spec} do NOT match allowlist entry "
                        f"`{entry.name}` (first: {sample[0]} has "
                        f"{field_path}={sample[1]!r}, expected "
                        f"{expected!r})."
                    ),
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------

CLASS_DESCRIPTIONS = {
    1: "file vs record presence",
    2: "record-claims-vs-presence",
    3: "decision-vs-records",
}


def render(report: Report, snapshots_loaded: int, payloads_loaded: int,
           allowlist_loaded: int) -> str:
    lines: list[str] = []
    lines.append("reconcile.py — workstream-state reconciliation utility")
    lines.append(f"Reading db-export/ snapshots ({snapshots_loaded} files): OK")
    lines.append(
        f"Reading close-out-payloads/ ({payloads_loaded} files): OK"
    )
    lines.append(f"Reading allowlist ({allowlist_loaded} entries): OK")
    lines.append("")

    for cls in (1, 2, 3):
        bucket = getattr(report, f"class_{cls}")
        header = f"Class {cls} ({CLASS_DESCRIPTIONS[cls]}):"
        lines.append(f"{header:<42}{len(bucket)} findings")
        for f in bucket:
            lines.append(f.format())

    lines.append("")
    total = report.expected_count + report.drift_count
    summary = (
        f"Summary: {total} findings "
        f"({report.expected_count} allowlisted, "
        f"{report.drift_count} unallowlisted drift)."
    )
    lines.append(summary)
    if report.drift_count == 0:
        lines.append("No unallowlisted drift.")
    else:
        lines.append("Unallowlisted drift present; investigate before proceeding.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "PI-023 workstream-state reconciliation utility — detect git-vs-"
            "database drift in the v2 governance graph."
        ),
    )
    parser.add_argument("--allowlist", type=Path, default=None)
    parser.add_argument("--db-export", type=Path, default=None)
    parser.add_argument("--payloads-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        repo_root = _find_repo_root(Path(__file__).resolve().parent)
    except RuntimeError as exc:
        print(f"reconcile.py: {exc}", file=sys.stderr)
        return 2

    db_export = (args.db_export or (repo_root / DEFAULT_DB_EXPORT_REL)).resolve()
    payloads_dir = (
        args.payloads_dir or (repo_root / DEFAULT_PAYLOADS_REL)
    ).resolve()
    allowlist_path = (
        args.allowlist or (repo_root / DEFAULT_ALLOWLIST_REL)
    ).resolve()

    try:
        snapshots = load_snapshots(db_export)
    except (FileNotFoundError, ValueError) as exc:
        print(f"reconcile.py: {exc}", file=sys.stderr)
        return 2

    if not payloads_dir.exists():
        print(
            f"reconcile.py: payloads directory missing: {payloads_dir}",
            file=sys.stderr,
        )
        return 2
    payloads = load_payloads(payloads_dir)

    try:
        allowlist = load_allowlist(allowlist_path)
    except (ValueError, yaml.YAMLError) as exc:
        print(f"reconcile.py: allowlist load failed: {exc}", file=sys.stderr)
        return 2

    config_errors = validate_allowlist(allowlist, snapshots)
    if config_errors:
        for e in config_errors:
            print(f"reconcile.py: {e}", file=sys.stderr)
        return 2

    report = Report()
    report.class_1 = check_class_1(
        snapshots, payloads, payloads_dir, repo_root, allowlist
    )
    report.class_2 = check_class_2(snapshots, payloads, allowlist)
    report.class_3 = check_class_3(snapshots, allowlist)

    print(
        render(
            report,
            snapshots_loaded=len(REQUIRED_SNAPSHOT_FILES),
            payloads_loaded=len(payloads),
            allowlist_loaded=len(allowlist),
        )
    )
    return 0 if report.drift_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

### File 2 of 2: `PRDs/product/crmbuilder-v2/reconciliation-allowlist.yaml`

```yaml
# PI-023 reconciliation allowlist — known data-quality artifacts that the
# governance graph has formally acknowledged. Each entry references either
# a governing decision (decided_in: DEC-NNN) or planning item
# (planning_item: PI-NNN); the canonical reasoning lives in that record.
#
# Schema (v1, per DEC-218 in SES-069):
#
#   - name: short slug, unique
#     description: one-line human summary
#     decided_in: DEC-NNN          # required if planning_item absent
#     planning_item: PI-NNN        # required if decided_in absent
#     drift_pattern:
#       type: records_summary_field | unresolved_payload_references | payload_files_without_cop
#       # records_summary_field shape:
#       record_type: deposit_event
#       identifier_range: DEP-LO..DEP-HI
#       field: records_summary.<subfield>
#       expected_value: <literal>
#       # unresolved_payload_references shape:
#       payload_file: ses_NNN.json
#       expected_unresolved_count: <int>
#       # payload_files_without_cop shape:
#       payload_files: [ses_NNN.json, ses_MMM.json, ...]
#
# Class 4 entries (DEC-197 orphan sessions list) are NOT included — Class 4
# is out of scope for v1 per DEC-217. Add them when scope expands.

- name: phase-1-references-orphan
  description: >
    Phase 1 backfill (DEP-001..DEP-008) deliberately skipped reference
    wrote_record edges. Mirrors the same pattern later adopted under
    Option I for PI-026.
  decided_in: DEC-216
  drift_pattern:
    type: records_summary_field
    record_type: deposit_event
    identifier_range: DEP-001..DEP-008
    field: records_summary.references
    expected_value: 0

- name: option-i-references-orphan
  description: >
    PI-026 historical-applies backfill (DEP-020..DEP-043) skipped reference
    wrote_record edges after the apply-time discovery of the vocab.py
    schema-vs-spec contradiction (PI-046). DEC-215 supersedes DEC-206.
  decided_in: DEC-215
  drift_pattern:
    type: records_summary_field
    record_type: deposit_event
    identifier_range: DEP-020..DEP-043
    field: records_summary.references
    expected_value: 0

- name: orphan-session-payload-files-without-cop
  description: >
    SES-001 and SES-046 are orphan sessions per DEC-197 (no parent CONV
    record). PI-026's historical-applies backfill explicitly excluded
    them per DEC-210 since no CONV exists to attach a close_out_payload
    to. The session JSON files exist on disk for archival continuity but
    have no corresponding COP record.
  decided_in: DEC-210
  drift_pattern:
    type: payload_files_without_cop
    payload_files:
      - ses_001.json
      - ses_046.json

- name: ses-001-orphan-unresolved-references
  description: >
    ses_001.json claims three decided_in references from DEC-001..003 to
    SES-001 that do not resolve in the references snapshot. As an
    orphan-session file per DEC-197/DEC-210, its references were never
    imported into the governance graph.
  decided_in: DEC-210
  drift_pattern:
    type: unresolved_payload_references
    payload_file: ses_001.json
    expected_unresolved_count: 3

- name: pi-047-ses-030-unresolved-references
  description: >
    ses_030.json claims four references (decided_in edges from
    DEC-105/106/107 plus an is_about edge from SES-030 to PI-001) that
    do not resolve in the references snapshot. The decided_in edges
    actually point at SES-036, an apparent duplicate-session artifact.
    Resolution deferred to PI-047.
  planning_item: PI-047
  drift_pattern:
    type: unresolved_payload_references
    payload_file: ses_030.json
    expected_unresolved_count: 4

- name: pi-048-ses-056-stale-blocks-vocabulary
  description: >
    ses_056.json claims two references with relationship="blocks"
    (PI-025 blocks PI-024, PI-026 blocks PI-025). The v0.8 methodology
    rename dropped "blocks" in favor of the directionally-renamed
    "blocked_by". The corresponding "blocked_by" edges exist in the
    references snapshot; the payload's claims are stale relative to
    the rename. PI-048 tracks migration of the payload (or formal
    acceptance of stale-vocab in historical payloads).
  planning_item: PI-048
  drift_pattern:
    type: unresolved_payload_references
    payload_file: ses_056.json
    expected_unresolved_count: 2
```

---

## Step 1 commit — script and allowlist

```bash
cd ~/Dropbox/Projects/crmbuilder

# Stage both files
git add crmbuilder-v2/scripts/reconcile.py
git add PRDs/product/crmbuilder-v2/reconciliation-allowlist.yaml

# Commit
git commit -m "Author PI-023 reconciliation utility — reconcile.py + reconciliation-allowlist.yaml

Per DEC-216..220 settled in SES-069.

crmbuilder-v2/scripts/reconcile.py:
- Standalone script, ~890 lines, no internal package imports
- Reads db-export JSON snapshots only; no V2 REST API dependency
  (DEC-219; the kickoff's proposed REST-API default was overridden
  because the Claude.ai sandbox cannot reach 127.0.0.1:8765 — the
  utility must run in any environment with the cloned repo on disk)
- Implements drift Classes 1, 2, and 3 (DEC-217):
  * Class 1: file vs close_out_payload-record presence both directions
  * Class 2: payload's record claims (session, decisions, planning_
    items, references) resolve in the snapshots
  * Class 3: allowlist-driven decision-vs-records consistency with
    supersedes-edge traversal (entries citing superseded decisions
    are flagged as stale)
- Allowlist mechanism is YAML config file at
  PRDs/product/crmbuilder-v2/reconciliation-allowlist.yaml (DEC-218);
  reconcile.py validates every entry's decided_in/planning_item
  resolves in the snapshots at startup
- Output format: structured plain text on stdout, severity-prefixed
  (EXPECTED / DRIFT), grouped by drift class, with summary line;
  exit 0 (no drift) / 1 (unallowlisted drift) / 2 (configuration
  error) (DEC-220)
- Single external dependency: PyYAML

PRDs/product/crmbuilder-v2/reconciliation-allowlist.yaml:
- 6 entries covering 7 known data-quality artifacts:
  * phase-1-references-orphan -> DEC-216 (DEP-001..008 records_
    summary.references=0)
  * option-i-references-orphan -> DEC-215 (DEP-020..043 records_
    summary.references=0)
  * orphan-session-payload-files-without-cop -> DEC-210 (ses_001.
    json, ses_046.json files exist without COP records)
  * ses-001-orphan-unresolved-references -> DEC-210 (ses_001.json
    claims 3 references that do not resolve)
  * pi-047-ses-030-unresolved-references -> PI-047 (ses_030.json
    claims 4 references that do not resolve)
  * pi-048-ses-056-stale-blocks-vocabulary -> PI-048 (ses_056.json
    claims 2 references with stale 'blocks' relationship)

Next: Step 2 runs the first reconciliation and verifies exit 0;
Step 3 transitions PI-022 to Resolved."

# Per the 'you commit, I push' convention in Claude Code context, do NOT push here.
```

---

## Step 2 — Run the first reconciliation

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2

# Run reconcile.py against the current snapshots
uv run python scripts/reconcile.py
EXIT_CODE=$?

echo ""
echo "=== Exit code: $EXIT_CODE ==="

# Expected: exit 0 with 7 findings, all allowlisted.
# If exit code is 1, unallowlisted drift was found — halt and surface
# to a Claude.ai conversation to either expand the allowlist or surface
# new planning items. Do NOT proceed to Step 3.
# If exit code is 2, the allowlist or snapshots are malformed — halt
# and read the stderr output.

if [ "$EXIT_CODE" -ne 0 ]; then
  echo "HALT: reconcile.py exit code $EXIT_CODE — do not proceed to PI-022 transition."
  exit 1
fi
```

Expected output:

```
reconcile.py — workstream-state reconciliation utility
Reading db-export/ snapshots (6 files): OK
Reading close-out-payloads/ (47 files): OK
Reading allowlist (6 entries): OK

Class 1 (file vs record presence):        2 findings
  EXPECTED  orphan-session-payload-files-without-cop (DEC-210): payload file ses_001.json has no close_out_payload record (orphan-session file).
  EXPECTED  orphan-session-payload-files-without-cop (DEC-210): payload file ses_046.json has no close_out_payload record (orphan-session file).
Class 2 (record-claims-vs-presence):      3 findings
  EXPECTED  ses-001-orphan-unresolved-references (DEC-210): ses_001.json claims 3 references that do not resolve in the references snapshot.
  EXPECTED  pi-047-ses-030-unresolved-references (PI-047): ses_030.json claims 4 references that do not resolve in the references snapshot.
  EXPECTED  pi-048-ses-056-stale-blocks-vocabulary (PI-048): ses_056.json claims 2 references that do not resolve in the references snapshot.
Class 3 (decision-vs-records):            2 findings
  EXPECTED  phase-1-references-orphan (DEC-216): DEP-001..DEP-008 records_summary.references=0 (8 of 8 records in range).
  EXPECTED  option-i-references-orphan (DEC-215): DEP-020..DEP-043 records_summary.references=0 (24 of 24 records in range).

Summary: 7 findings (7 allowlisted, 0 unallowlisted drift).
No unallowlisted drift.
```

Exit code: 0.

The file counts may differ if any new ses_*.json files have been added since this prompt was authored (47 was the count at the SES-069 apply close). The finding counts and allowlist counts are stable so long as no new drift has been introduced.

---

## Step 3 — Transition PI-022 to Resolved

The PI-022 governance-backfill program closes when reconcile.py's first invocation succeeds. PATCH PI-022's status from Open to Resolved.

```bash
# PATCH PI-022 to Resolved status
curl -s -X PATCH http://127.0.0.1:8765/planning-items/PI-022 \
  -H "Content-Type: application/json" \
  -d '{"status": "Resolved"}' \
  | python3 -m json.tool

# Verify the transition landed
curl -s http://127.0.0.1:8765/planning-items/PI-022 | python3 -c "
import sys, json
d = json.load(sys.stdin)['data']
print(f'PI-022 status after PATCH: {d[\"status\"]}')
assert d['status'] == 'Resolved', f'PATCH failed — status is {d[\"status\"]}'
print('PI-022 transitioned Open -> Resolved')
"
```

The PATCH triggers the `_refresh_snapshot` hook, which regenerates `PRDs/product/crmbuilder-v2/db-export/planning_items.json` (PI-022's status field updates) and appends an audit row to `PRDs/product/crmbuilder-v2/db-export/change_log.json` capturing the before/after payloads.

---

## Step 3 commit — PI-022 transition and snapshot regeneration

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect changed snapshot files
git status PRDs/product/crmbuilder-v2/db-export/

# Expected:
#   modified: PRDs/product/crmbuilder-v2/db-export/planning_items.json
#   modified: PRDs/product/crmbuilder-v2/db-export/change_log.json

# Stage and commit
git add PRDs/product/crmbuilder-v2/db-export/
git commit -m "PI-022 governance-backfill program closed — PI-022 status Open -> Resolved

PI-022 was the top-level program covering the v2 governance-graph
backfill work: Phase 1 (DEP-001..008 records-level wrote_record
edges), Phase 2 deferred to the future, Phase 3 deferred to the
future, Phase 4 (PI-026 historical-applies backfill DEP-020..043),
and the PI-023 reconciliation utility as the program's terminal
verification capability.

PI-022's closure was gated on PI-023's reconcile.py producing a
clean first-run report: 7 findings, all allowlisted, exit 0. That
condition was met by the first reconcile.py invocation immediately
preceding this commit.

The transition is recorded in change_log.json as an audit row with
the before (status=Open) and after (status=Resolved) payloads. The
planning_items.json snapshot is regenerated to reflect the new
status.

Three governance-data-quality planning items remain Open as
eligible-for-future-workstream-lane:
- PI-046 (vocab.py schema-vs-spec contradiction for reference targets
  in deposit_event_wrote_record edges)
- PI-047 (ses_030 / ses_036 duplicate-session artifact and the 4
  unresolvable references ses_030's payload claims)
- PI-048 (ses_056.json stale 'blocks' relationship references vs
  v0.8-renamed 'blocked_by')

Each of these is covered by an allowlist entry in
PRDs/product/crmbuilder-v2/reconciliation-allowlist.yaml so reconcile.
py emits them as EXPECTED rather than DRIFT. When any of the three is
resolved, the corresponding allowlist entry should be removed and
reconcile.py re-run to confirm zero findings in the affected class."

# Per the 'you commit, I push' convention in Claude Code context, do NOT push here.
```

---

## Done

Reply with:

- Pre-step heads: SES-069, DEC-220, PI-048, PI-022 status=Open
- Step 1 commit SHA (reconcile.py + reconciliation-allowlist.yaml authored)
- Step 2 outcome: reconcile.py exit code 0; 7 findings, all allowlisted (2 Class 1 EXPECTED, 3 Class 2 EXPECTED, 2 Class 3 EXPECTED, 0 DRIFT)
- Step 3 outcome: PI-022 PATCH succeeded; PI-022 status=Resolved confirmed
- Step 3 commit SHA (snapshot regeneration captures PI-022 transition + change_log audit row)
- Next: PI-022 governance-backfill program is closed. Three governance-data-quality planning items (PI-046, PI-047, PI-048) remain Open and eligible for a future workstream lane. The next conversation is at Doug's discretion; no successor kickoff was authored at PI-023's close.
