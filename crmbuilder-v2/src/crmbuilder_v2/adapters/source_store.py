"""Source store intake for client-supplied spreadsheet files (WTK-111).

The spreadsheet path is the first time CRMBuilder holds client record
data at rest (spec §3.5): a registered workbook is the only copy
CRMBuilder has and — per the WTK-104 compile contract — the only thing
a future migration can extract records from. This module owns the
intake side of that store:

* **Layout** (§3.1–§3.2): ``config.sources_dir()`` / ``{ENGAGEMENT}``
  / ``{source-slug}`` / ``{YYYYMMDDTHHMMSSZ}``. One slug directory =
  one source = one workbook; one snapshot = one immutable
  registration. CSVs land at the snapshot root (the adapter's input
  glob), everything else under ``originals/``.
* **Content identity** (§3.2): every snapshot carries a
  ``source-manifest.json`` recording names, byte counts, and SHA-256
  per file — what the provenance chain terminates in and what the
  migration pre-flight re-verifies.
* **Size limits** (§3.4): 100 MiB per file / 500 MiB per snapshot,
  enforced before anything is copied; ``allow_oversize`` overrides
  both and the manifest records the exception forever.
* **Sensitive-data posture** (§3.5): the store root is gitignored;
  this module logs names, byte counts, and hashes — never cell
  values.

Registration is atomic: files are staged into a hidden sibling
directory and the finished snapshot appears under its final name in
one rename. Intake never writes into an existing snapshot — a
corrected or refreshed upload is a *new* snapshot beside the old one
(§3.2), and snapshots are retained for the life of the engagement
(§3.6).
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import re
import shutil
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from crmbuilder_v2 import config

SOURCE_MANIFEST_FILENAME = "source-manifest.json"
SOURCE_MANIFEST_VERSION = 1

# §3.4 — protecting the intake copy and the synced disk, not profiler
# correctness (the adapter bounds its own memory). A genuine outlier
# passes with ``allow_oversize`` and a manifest flag visible forever.
PER_FILE_LIMIT_BYTES = 100 * 2**20
SNAPSHOT_LIMIT_BYTES = 500 * 2**20

# §3.2 — the runtime-log timestamp idiom names the snapshot directory.
_SNAPSHOT_STAMP_FORMAT = "%Y%m%dT%H%M%SZ"

_SLUG_RE = re.compile(r"[^a-z0-9]+")


class SourceRegistrationError(ValueError):
    """Intake refusal carrying a stable machine-readable ``code``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def slugify_source_name(name: str) -> str:
    """Kebab-case path slug (§3.1) — the adapter's header slugify
    family (WTK-110 §4.1) with ``-`` as the separator for path use."""
    return _SLUG_RE.sub("-", name.lower()).strip("-")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_files(paths: Sequence[str | Path]) -> list[Path]:
    """Expand the operator's file-or-dir arguments into a flat file
    list: a directory contributes its sorted, non-hidden, immediate
    files (intake registers exports, it does not crawl trees)."""
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(
                child
                for child in sorted(path.iterdir())
                if child.is_file() and not child.name.startswith(".")
            )
        elif path.is_file():
            files.append(path)
        else:
            raise SourceRegistrationError(
                "source_file_missing", f"no such file: {path}"
            )
    if not files:
        raise SourceRegistrationError(
            "no_source_files", "nothing to register: no files supplied"
        )
    return files


def _enforce_limits(files: Sequence[Path], allow_oversize: bool) -> None:
    """§3.4, checked before any copy so a refusal leaves no residue."""
    if allow_oversize:
        return
    total = 0
    for path in files:
        size = path.stat().st_size
        total += size
        if size > PER_FILE_LIMIT_BYTES:
            raise SourceRegistrationError(
                "source_file_too_large",
                f"{path.name} is {size} bytes; the per-file limit is "
                f"{PER_FILE_LIMIT_BYTES} bytes (override with "
                f"--allow-oversize)",
            )
    if total > SNAPSHOT_LIMIT_BYTES:
        raise SourceRegistrationError(
            "snapshot_too_large",
            f"snapshot totals {total} bytes across {len(files)} file(s); "
            f"the per-snapshot limit is {SNAPSHOT_LIMIT_BYTES} bytes "
            f"(override with --allow-oversize)",
        )


def _default_registered_by() -> str | None:
    try:
        return getpass.getuser()
    except (KeyError, OSError):
        return None


def register_source(
    files: Sequence[str | Path],
    engagement: str,
    source_name: str,
    *,
    sheet_names: Mapping[str, str] | None = None,
    allow_oversize: bool = False,
    registered_by: str | None = None,
    now: datetime | None = None,
) -> Path:
    """Register operator-supplied files as a new immutable snapshot.

    Copies CSVs to the snapshot root and everything else (the
    as-received workbook artifacts) to ``originals/``, computes byte
    counts and SHA-256 per copied file, enforces the §3.4 limits,
    writes ``source-manifest.json``, and returns the snapshot path —
    the input to ``crmbuilder-v2-spreadsheet-profile``. ``sheet_names``
    maps a CSV basename to its workbook sheet name when the operator
    knows it. The whole registration is one staged-directory rename;
    an existing snapshot is never written into.
    """
    engagement = engagement.strip()
    if not engagement:
        raise SourceRegistrationError(
            "engagement_required", "engagement code must be non-empty"
        )
    slug = slugify_source_name(source_name)
    if not slug:
        raise SourceRegistrationError(
            "source_name_required",
            f"source name {source_name!r} yields an empty slug",
        )

    inputs = _collect_files(files)
    seen: set[str] = set()
    for path in inputs:
        if path.name in seen:
            raise SourceRegistrationError(
                "duplicate_file_name",
                f"two supplied files share the name {path.name!r}; "
                "snapshot file names must be unique",
            )
        seen.add(path.name)
    _enforce_limits(inputs, allow_oversize)

    registered_at = now or datetime.now(tz=UTC)
    stamp = registered_at.strftime(_SNAPSHOT_STAMP_FORMAT)
    source_dir = config.sources_dir() / engagement / slug
    snapshot_dir = source_dir / stamp
    if snapshot_dir.exists():
        raise SourceRegistrationError(
            "snapshot_exists",
            f"snapshot {snapshot_dir} already exists; snapshots are "
            "immutable — register again for a new snapshot",
        )

    staging = source_dir / f".staging-{stamp}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        csvs: list[Path] = []
        originals: list[Path] = []
        for path in inputs:
            if path.suffix.lower() == ".csv":
                target = staging / path.name
                csvs.append(target)
            else:
                (staging / "originals").mkdir(exist_ok=True)
                target = staging / "originals" / path.name
                originals.append(target)
            shutil.copy2(path, target)

        # Original attribution (§3.2): operator- or filename-derived,
        # nullable. With exactly one original every sheet came from it;
        # with several (or none) the link is unknown in v1.
        sole_original = originals[0].name if len(originals) == 1 else None
        names = sheet_names or {}
        manifest = {
            "source_manifest_version": SOURCE_MANIFEST_VERSION,
            "engagement": engagement,
            "source_name": source_name,
            "source_slug": slug,
            "registered_at": registered_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "registered_by": registered_by or _default_registered_by(),
            "originals": [
                {
                    "name": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
                for path in originals
            ],
            "sheets": [
                {
                    "file": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                    "original": sole_original,
                    "sheet_name": names.get(path.name),
                }
                for path in csvs
            ],
            "oversize_allowed": allow_oversize,
            "notes": None,
        }
        tmp = staging / f".{SOURCE_MANIFEST_FILENAME}.tmp"
        tmp.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp.replace(staging / SOURCE_MANIFEST_FILENAME)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    staging.replace(snapshot_dir)
    return snapshot_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-register-source",
        description=(
            "Register client-supplied spreadsheet files (per-sheet CSVs "
            "plus the as-received originals) as a new immutable source-"
            "store snapshot (WTK-111), ready for "
            "crmbuilder-v2-spreadsheet-profile."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        metavar="file-or-dir",
        help="files to register; a directory contributes its files",
    )
    parser.add_argument(
        "--engagement",
        required=True,
        help="engagement code the source belongs to (e.g. CRMBUILDER)",
    )
    parser.add_argument(
        "--source-name",
        required=True,
        help="human name of the source workbook; slugified for the path",
    )
    parser.add_argument(
        "--sheet-name",
        action="append",
        default=[],
        metavar="FILE=NAME",
        help="record which workbook sheet a CSV came from",
    )
    parser.add_argument(
        "--allow-oversize",
        action="store_true",
        help="override the size limits; recorded in the manifest",
    )
    args = parser.parse_args(argv)

    sheet_names: dict[str, str] = {}
    for spec in args.sheet_name:
        file, sep, name = spec.partition("=")
        if not sep or not file or not name:
            parser.error(f"--sheet-name expects FILE=NAME, got {spec!r}")
        sheet_names[file] = name

    try:
        snapshot = register_source(
            args.paths,
            args.engagement,
            args.source_name,
            sheet_names=sheet_names,
            allow_oversize=args.allow_oversize,
        )
    except SourceRegistrationError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 1

    # §3.5 rule 2: names, byte counts, and hashes only — never content.
    manifest = json.loads(
        (snapshot / SOURCE_MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    print(
        f"Registered {len(manifest['sheets'])} sheet CSV(s) and "
        f"{len(manifest['originals'])} original(s) for source "
        f"{manifest['source_name']!r} ({manifest['source_slug']})."
    )
    print(f"Snapshot: {snapshot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
