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
