"""Spreadsheet source adapter (WTK-110 design spec).

The second Phase 1.5 source adapter: profiles a **source** — one
workbook, on disk a directory of CSV files (one per sheet) or a single
CSV file — and emits the normalized-inventory manifest pair the
EspoCRM adapter emits: ``audit-report.json`` plus
``utilization-profile.json``, ready for the landed ``plan_deposit``
consumer (``crmbuilder_v2/transform/audit_deposit.py``).

Unlike the EspoCRM source, a spreadsheet declares no schema — the
adapter *infers* one. That changes the character of the output, not
its shape: every structural fact in the manifest is an inference
carrying evidence and a confidence grade in the profile's ``detail``
blocks (the WTK-096 verbatim passthrough into ``evidence_detail``),
where the EspoCRM adapter's facts were declarations read from
metadata. The run is mechanical per Master CRMBuilder PRD §7: no
keep/drop judgment — oddities become anomalies and evidence, never
silent corrections.

Five pure stages over the file bytes (spec §4):

* **A** — decode (BOM sniff -> strict UTF-8 -> cp1252 fallback with a
  warning), dialect sniff, parse, header detection and normalization;
* **B** — column type inference by recognizer vote (most specific
  recognizer with match rate >= ``inference_threshold`` wins);
* **B′** — enum / multi_enum / auto_number post-passes;
* **C** — candidate-entity proposal (one sheet -> one entity,
  mechanically; structure oddities recorded as evidence only);
* **D** — cross-sheet reference detection by distinct-value
  containment against other sheets' candidate key columns;
* **E** — exact utilization metrics (the spreadsheet *is* its own
  data — no sampling, no request budget).

In v1 the adapter emits no manifest ``relationships`` entries (spec
§6.4): a fired reference is a plain field of native type ``reference``
carrying full utilization metrics plus its ``reference_inference``
evidence block. Roles and teams are structurally empty. The stage-1
type table for the closed inferred-type vocabulary is registered in
``transform/normalize.py`` under the ``"spreadsheet"`` slug (delta
D3); every item partitions ``custom`` (delta D4).
"""

from __future__ import annotations

import argparse
import codecs
import csv
import io
import json
import math
import re
import sys
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime
from pathlib import Path

from crmbuilder_v2 import __version__ as _ADAPTER_VERSION

MANIFEST_VERSION = 1
SOURCE_SYSTEM = "spreadsheet"

MANIFEST_FILENAME = "audit-report.json"
PROFILE_FILENAME = "utilization-profile.json"

# The closed inferred-type vocabulary (spec §6.3) — the adapter's
# native `field_type` values. The stage-1 table `_SPREADSHEET_TYPES`
# in transform/normalize.py must be total over exactly this set
# (conformance criterion C3).
INFERRED_TYPES: frozenset[str] = frozenset(
    {
        "text",
        "long_text",
        "integer",
        "decimal",
        "currency",
        "percent",
        "boolean",
        "date",
        "datetime",
        "time",
        "email",
        "phone",
        "url",
        "enum",
        "multi_enum",
        "reference",
        "auto_number",
        "empty",
    }
)

# Recognizer specificity order (spec §4.2) — the inferred type is the
# first recognizer in this order whose match rate >= the threshold.
# `long_text`/`text` are the fallback refinement, not voted recognizers.
_SPECIFICITY: tuple[str, ...] = (
    "boolean",
    "integer",
    "decimal",
    "currency",
    "percent",
    "date",
    "datetime",
    "time",
    "email",
    "url",
    "phone",
)

_BOOLEAN_PAIRS: tuple[frozenset[str], ...] = (
    frozenset({"true", "false"}),
    frozenset({"yes", "no"}),
    frozenset({"y", "n"}),
)

_CURRENCY_SYMBOLS = "$€£"
_RUNNER_UP_FLOOR = 0.30
_LONG_TEXT_NEWLINE_FRACTION = 0.05
_LONG_TEXT_P95_LENGTH = 200
_AUTO_NUMBER_DENSITY = 1.5
_MULTI_VALUE_SPLIT_FRACTION = 0.20
_COMMA_TOKEN_CAP = 12
_REFERENCE_MIN_MATCHED = 10
_KEY_POPULATION_FLOOR = 0.95
_DISTINCT_CAP = 1_000
_TOP_VALUES_MAX_DISTINCT = 100
_TOP_VALUES_COUNT = 10
_SAMPLE_VALUES_COUNT = 5
_SIMILAR_SHEETS_FRACTION = 0.80
_HEADER_DIVERGENCE_FRACTION = 0.60
_SNIFF_SAMPLE_BYTES = 64 * 1024
# Types whose sample values are PII — `sample_values` is omitted; the
# recognizer name is evidence enough (spec §5.1).
_REDACTED_SAMPLE_TYPES = frozenset({"email", "phone"})

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip

_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_SLASH_DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$")
_DASH_DATE_RE = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})$")
_DAY_MON_RE = re.compile(r"^(\d{1,2})-([A-Za-z]{3,9})-(\d{4})$")
_MON_DAY_RE = re.compile(r"^([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})$")
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?$", re.IGNORECASE)
_DATETIME_SUFFIX_RE = re.compile(
    r"[ T](\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)(Z|[+-]\d{2}:?\d{2})?$",
    re.IGNORECASE,
)
_PHONE_STRIP_RE = re.compile(r"[\s().\-]")
_PHONE_RE = re.compile(r"^\+?\d{7,15}$")
_ID_SUFFIX_RE = re.compile(r"(?:^|[^a-z])id$")


@dataclass(frozen=True)
class AdapterOptions:
    """Every inference parameter (spec §6.2), pinned into the profile's
    ``options`` block so evidence is re-derivable, plus the operator
    designations (``--no-header``, ``--created-column``) that change
    the output's basis and are recorded where they apply."""

    inference_threshold: float = 0.95
    enum_min_support: int = 10
    enum_max_options: int = 24
    multi_value_delimiters: tuple[str, ...] = (";", "|", ",")
    reference_containment_threshold: float = 0.95
    decimal_comma: bool = False
    dormancy_window_days: int = 365
    low_population_threshold: float = 0.05
    no_header_sheets: frozenset[str] = frozenset()
    created_columns: Mapping[str, str] = dataclass_field(default_factory=dict)

    def profile_options(self) -> dict:
        """The §6.2 profile ``options`` block — inference parameters
        only; per-sheet designations surface as `*_basis` evidence."""
        return {
            "inference_threshold": self.inference_threshold,
            "enum_min_support": self.enum_min_support,
            "enum_max_options": self.enum_max_options,
            "multi_value_delimiters": list(self.multi_value_delimiters),
            "reference_containment_threshold": (
                self.reference_containment_threshold
            ),
            "decimal_comma": self.decimal_comma,
            "dormancy_window_days": self.dormancy_window_days,
            "low_population_threshold": self.low_population_threshold,
        }


# ---------------------------------------------------------------------------
# Recognizers (spec §4.2) — each takes one trimmed cell value
# ---------------------------------------------------------------------------


def _number_patterns(decimal_comma: bool) -> tuple[re.Pattern, re.Pattern]:
    """Integer and decimal grammars; ``--decimal-comma`` swaps the
    ``.``/``,`` roles for European exports. Decimal is a superset of
    integer (the optional fraction); specificity order keeps an
    all-integer column ``integer``."""
    group, point = (".", ",") if decimal_comma else (",", ".")
    integer = re.compile(
        rf"^[+-]?(?:\d{{1,3}}(?:{re.escape(group)}\d{{3}})+|\d+)$"
    )
    decimal = re.compile(
        rf"^[+-]?(?:\d{{1,3}}(?:{re.escape(group)}\d{{3}})+|\d+)"
        rf"(?:{re.escape(point)}\d+)?$"
    )
    return integer, decimal


def _valid_date_parts(year: int, month: int, day: int) -> bool:
    try:
        datetime(year, month, day)
    except ValueError:
        return False
    return True


def _pivot_year(raw: str) -> int:
    """Two-digit years in the slash family pivot at 1970 (spec §4.2)."""
    year = int(raw)
    if len(raw) == 2:
        return 1900 + year if year >= 70 else 2000 + year
    return year


def _parse_named_month(name: str) -> int | None:
    return _MONTHS.get(name[:3].lower())


def _date_parse(value: str) -> datetime | None:
    """Parse one date cell through the pinned format list, trying each
    in order; slash-family values valid under either component order
    parse M/D (the US default) — the per-column order resolution is
    evidence, not a parse concern."""
    m = _ISO_DATE_RE.match(value)
    if m:
        year, month, day = (int(g) for g in m.groups())
        if _valid_date_parts(year, month, day):
            return datetime(year, month, day, tzinfo=UTC)
        return None
    m = _SLASH_DATE_RE.match(value)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        year = _pivot_year(m.group(3))
        if _valid_date_parts(year, a, b):
            return datetime(year, a, b, tzinfo=UTC)
        if _valid_date_parts(year, b, a):
            return datetime(year, b, a, tzinfo=UTC)
        return None
    m = _DASH_DATE_RE.match(value)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if _valid_date_parts(year, month, day):
            return datetime(year, month, day, tzinfo=UTC)
        return None
    m = _DAY_MON_RE.match(value)
    if m:
        month = _parse_named_month(m.group(2))
        if month and _valid_date_parts(int(m.group(3)), month, int(m.group(1))):
            return datetime(int(m.group(3)), month, int(m.group(1)), tzinfo=UTC)
        return None
    m = _MON_DAY_RE.match(value)
    if m:
        month = _parse_named_month(m.group(1))
        if month and _valid_date_parts(int(m.group(3)), month, int(m.group(2))):
            return datetime(int(m.group(3)), month, int(m.group(2)), tzinfo=UTC)
    return None


class _Recognizers:
    """The recognizer set, compiled once per run from the options."""

    def __init__(self, options: AdapterOptions) -> None:
        self._integer, self._decimal = _number_patterns(options.decimal_comma)

    def integer(self, value: str) -> bool:
        return bool(self._integer.match(value))

    def decimal(self, value: str) -> bool:
        return bool(self._decimal.match(value))

    def currency(self, value: str) -> bool:
        rest = value
        sign = ""
        if rest[:1] in "+-":
            sign, rest = rest[:1], rest[1:].strip()
        parenthesized = rest.startswith("(") and rest.endswith(")")
        if parenthesized:
            rest = rest[1:-1].strip()
        symbol = False
        if rest[:1] in _CURRENCY_SYMBOLS:
            symbol, rest = True, rest[1:].strip()
        elif rest[-1:] in _CURRENCY_SYMBOLS:
            symbol, rest = True, rest[:-1].strip()
        if not (symbol or parenthesized):
            return False
        return bool(rest) and self.decimal(sign + rest)

    def percent(self, value: str) -> bool:
        return value.endswith("%") and self.decimal(value[:-1].strip())

    def date(self, value: str) -> bool:
        return _date_parse(value) is not None

    def datetime(self, value: str) -> bool:
        m = _DATETIME_SUFFIX_RE.search(value)
        return bool(m) and self.date(value[: m.start()].strip())

    def time(self, value: str) -> bool:
        return bool(_TIME_RE.match(value))

    def email(self, value: str) -> bool:
        if value.count("@") != 1 or " " in value:
            return False
        local, _, domain = value.partition("@")
        return bool(local) and "." in domain.strip(".")

    def url(self, value: str) -> bool:
        lowered = value.lower()
        return lowered.startswith(("http://", "https://", "www."))

    def phone(self, value: str) -> bool:
        return bool(_PHONE_RE.match(_PHONE_STRIP_RE.sub("", value)))

    def matches(self, name: str, value: str) -> bool:
        """One non-boolean recognizer by name (boolean is pair-based
        per column, handled by the vote)."""
        return getattr(self, name)(value)


# ---------------------------------------------------------------------------
# Stage A — parse and header detection (spec §3.1/§4.1)
# ---------------------------------------------------------------------------

_BOMS: tuple[tuple[bytes, str], ...] = (
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)


def _decode_bytes(raw: bytes, sheet: str) -> tuple[str, list[str]]:
    """BOM sniff -> strict UTF-8 -> cp1252 fallback with a warning
    (the fallback never fails, so it must be visible)."""
    for bom, encoding in _BOMS:
        if raw.startswith(bom):
            return raw.decode(encoding), []
    try:
        return raw.decode("utf-8"), []
    except UnicodeDecodeError:
        return raw.decode("cp1252"), [
            f"sheet {sheet}: not valid UTF-8; decoded as cp1252 "
            "(encoding fallback)"
        ]


def _sniff_delimiter(text: str, sheet: str) -> tuple[str, str | None]:
    try:
        dialect = csv.Sniffer().sniff(text[:_SNIFF_SAMPLE_BYTES], ",;\t|")
    except csv.Error:
        return ",", (
            f"sheet {sheet}: delimiter sniff failed; assuming comma"
        )
    return dialect.delimiter, None


_SLUG_RE = re.compile(r"[^a-z0-9]+")
_WHITESPACE_RUN_RE = re.compile(r"\s+")


def _slugify(text: str) -> str:
    return _SLUG_RE.sub("_", text.lower()).strip("_")


@dataclass
class _Column:
    api_name: str
    yaml_name: str
    cells: list[str]


@dataclass
class _Sheet:
    name: str
    columns: list[_Column]
    record_count: int
    blank_row_count: int
    ragged_row_count: int
    header_assumed: bool
    source_file: str
    source_file_modified_at: str
    anomalies: list[dict]
    warnings: list[str]


def _populated(cells: list[str]) -> list[str]:
    """The WTK-096 §3.1 predicate: populated iff non-empty after
    trimming whitespace; values are compared trimmed throughout."""
    return [cell.strip() for cell in cells if cell.strip()]


def _base_vote(
    cells: list[str], recognizers: _Recognizers
) -> dict[str, float]:
    """Match rate per recognizer over the populated cells. Boolean is
    pair-based: one pair per column, the best pair's rate."""
    total = len(cells)
    rates: dict[str, float] = {}
    lowered = [cell.lower() for cell in cells]
    rates["boolean"] = max(
        sum(1 for cell in lowered if cell in pair) / total
        for pair in _BOOLEAN_PAIRS
    )
    for name in _SPECIFICITY[1:]:
        rates[name] = (
            sum(1 for cell in cells if recognizers.matches(name, cell)) / total
        )
    return rates


def _header_accepted(
    header_row: list[str],
    body_columns: list[list[str]],
    recognizers: _Recognizers,
    options: AdapterOptions,
) -> bool:
    """The §4.1 acceptance test for row 1 as header."""
    typed: list[tuple[int, str]] = []
    all_text = True
    for index, cells in enumerate(body_columns):
        populated = _populated(cells)
        if populated and not header_row[index].strip():
            return False
        if not populated:
            continue
        rates = _base_vote(populated, recognizers)
        winner = next(
            (
                name
                for name in _SPECIFICITY
                if rates[name] >= options.inference_threshold
            ),
            None,
        )
        if winner is not None:
            all_text = False
            typed.append((index, winner))
    if typed:
        failing = sum(
            1
            for index, name in typed
            if not _cell_matches(header_row[index].strip(), name, recognizers)
        )
        return failing / len(typed) >= _HEADER_DIVERGENCE_FRACTION
    if all_text:
        populated_header = [c.strip() for c in header_row if c.strip()]
        return len(set(populated_header)) == len(populated_header)
    return False


def _cell_matches(value: str, name: str, recognizers: _Recognizers) -> bool:
    if not value:
        return False
    if name == "boolean":
        return any(value.lower() in pair for pair in _BOOLEAN_PAIRS)
    return recognizers.matches(name, value)


def _normalize_headers(
    raw_header: list[str], sheet: str
) -> tuple[list[str], list[str], list[dict]]:
    """Trim + collapse whitespace runs (-> ``api_name``/``label``),
    slugify to snake_case (-> ``yaml_name``); empty headers become
    ``column_{i}`` and duplicates take ``_2``/``_3`` suffixes on both
    forms, each with an anomaly (spec §4.1)."""
    anomalies: list[dict] = []
    api_names: list[str] = []
    for index, raw in enumerate(raw_header, start=1):
        api = _WHITESPACE_RUN_RE.sub(" ", raw.strip())
        if not api:
            api = f"column_{index}"
            anomalies.append(
                {
                    "scope": "entity",
                    "entity": sheet,
                    "field": api,
                    "note": (
                        f"empty header in position {index}; "
                        f"named {api!r}"
                    ),
                }
            )
        api_names.append(api)
    seen: dict[str, int] = {}
    deduped: list[str] = []
    for api in api_names:
        count = seen.get(api, 0) + 1
        seen[api] = count
        if count > 1:
            suffixed = f"{api}_{count}"
            anomalies.append(
                {
                    "scope": "entity",
                    "entity": sheet,
                    "field": suffixed,
                    "note": (
                        f"duplicate header {api!r}; "
                        f"renamed {suffixed!r}"
                    ),
                }
            )
            api = suffixed
        deduped.append(api)
    yaml_names: list[str] = []
    yaml_seen: dict[str, int] = {}
    for api in deduped:
        slug = _slugify(api) or api.lower()
        count = yaml_seen.get(slug, 0) + 1
        yaml_seen[slug] = count
        if count > 1:
            slug = f"{slug}_{count}"
        yaml_names.append(slug)
    return deduped, yaml_names, anomalies


def _format_utc(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_sheet(
    path: Path, options: AdapterOptions, recognizers: _Recognizers
) -> _Sheet:
    sheet = path.stem
    raw = path.read_bytes()
    text, warnings = _decode_bytes(raw, sheet)
    delimiter, sniff_warning = _sniff_delimiter(text, sheet)
    if sniff_warning:
        warnings.append(sniff_warning)
    rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))

    blank_row_count = 0
    data_rows: list[list[str]] = []
    for row in rows:
        if not row or all(not cell.strip() for cell in row):
            blank_row_count += 1
            continue
        data_rows.append(row)

    anomalies: list[dict] = []
    header_assumed = False
    if sheet in options.no_header_sheets:
        width = max((len(row) for row in data_rows), default=0)
        api_names = [f"column_{i}" for i in range(1, width + 1)]
        yaml_names = list(api_names)
        body = data_rows
    else:
        raw_header = data_rows[0] if data_rows else []
        body = data_rows[1:]
        width = len(raw_header)
        body_columns = [
            [row[i] if i < len(row) else "" for row in body]
            for i in range(width)
        ]
        if not _header_accepted(raw_header, body_columns, recognizers, options):
            # Ambiguous -> assume header (the overwhelmingly common
            # case for exported sheets) and surface the guess.
            header_assumed = True
            anomalies.append(
                {
                    "scope": "entity",
                    "entity": sheet,
                    "field": None,
                    "note": (
                        "header assumed: row 1 did not pass the header "
                        "acceptance test; column names are guesses"
                    ),
                }
            )
            warnings.append(f"sheet {sheet}: header assumed from row 1")
        api_names, yaml_names, header_anomalies = _normalize_headers(
            raw_header, sheet
        )
        anomalies.extend(header_anomalies)

    ragged_row_count = 0
    normalized: list[list[str]] = []
    for row in body:
        if len(row) != width:
            ragged_row_count += 1
            row = row[:width] + [""] * (width - len(row))
        normalized.append(row)
    if ragged_row_count:
        anomalies.append(
            {
                "scope": "entity",
                "entity": sheet,
                "field": None,
                "note": (
                    f"{ragged_row_count} ragged row(s) normalized to the "
                    f"header width of {width}"
                ),
            }
        )
        warnings.append(
            f"sheet {sheet}: {ragged_row_count} ragged row(s) normalized "
            "to header width"
        )

    columns = [
        _Column(
            api_name=api_names[i],
            yaml_name=yaml_names[i],
            cells=[row[i] for row in normalized],
        )
        for i in range(width)
    ]
    return _Sheet(
        name=sheet,
        columns=columns,
        record_count=len(normalized),
        blank_row_count=blank_row_count,
        ragged_row_count=ragged_row_count,
        header_assumed=header_assumed,
        source_file=path.name,
        source_file_modified_at=_format_utc(
            datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        ),
        anomalies=anomalies,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Stages B/B′ — type inference and post-passes (spec §4.2/§4.3)
# ---------------------------------------------------------------------------


@dataclass
class _Inference:
    """One column's inference outcome — everything the §5.1
    ``type_inference`` block and the manifest emission need."""

    inferred_type: str
    base_type: str
    match_rate: float | None
    non_empty_count: int
    recognizer: str | None
    runner_up: str | None
    runner_up_rate: float | None
    confidence: str
    date_order_assumed: bool
    sample_values: list[str] | None
    options: list[str] | None = None
    value_distribution: dict[str, int] | None = None
    reference: dict | None = None


def _grade(match_rate: float, non_empty: int, threshold: float) -> str:
    """The §5.2 type-inference confidence grades."""
    if match_rate >= 0.99 and non_empty >= 50:
        return "high"
    if match_rate >= threshold and non_empty >= 10:
        return "medium"
    return "low"


def _enum_eligible(
    support: int, distinct: int, options: AdapterOptions
) -> bool:
    return (
        support >= options.enum_min_support
        and 2 <= distinct < support
        and distinct
        <= min(options.enum_max_options, max(6, math.ceil(0.5 * support)))
    )


def _ordered_options(counts: Counter) -> list[str]:
    """Observed option list, descending count then alphabetical
    (deterministic, spec §6.1)."""
    return [
        value
        for value, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def _tokenize(cells: list[str], delimiter: str) -> list[str]:
    return [
        token
        for cell in cells
        for token in (part.strip() for part in cell.split(delimiter))
        if token
    ]


def _multi_enum_pass(
    cells: list[str], options: AdapterOptions
) -> tuple[Counter, str] | None:
    for delimiter in options.multi_value_delimiters:
        split_cells = sum(
            1
            for cell in cells
            if len([p for p in (t.strip() for t in cell.split(delimiter)) if p])
            > 1
        )
        if split_cells / len(cells) < _MULTI_VALUE_SPLIT_FRACTION:
            continue
        tokens = _tokenize(cells, delimiter)
        token_counts = Counter(tokens)
        if not _enum_eligible(len(tokens), len(token_counts), options):
            continue
        # Comma is admitted only under the tighter token cap — commas
        # inside prose otherwise flood it (spec §4.3).
        if delimiter == "," and len(token_counts) > _COMMA_TOKEN_CAP:
            continue
        return token_counts, delimiter
    return None


def _auto_number_pass(cells: list[str], decimal_comma: bool) -> bool:
    group = "." if decimal_comma else ","
    values = [int(cell.replace(group, "").lstrip("+")) for cell in cells]
    distinct = set(values)
    if len(distinct) != len(values):
        return False
    span = max(values) - min(values) + 1
    return span / len(values) <= _AUTO_NUMBER_DENSITY


def _date_order(cells: list[str]) -> bool:
    """The §4.2 per-column slash-family day/month resolution: True when
    the column carries slash-family values and neither order is fixed
    by an out-of-range component (the M/D US-default assumption)."""
    saw_slash = False
    for cell in cells:
        m = _SLASH_DATE_RE.match(cell)
        if not m:
            continue
        saw_slash = True
        if int(m.group(1)) > 12 or int(m.group(2)) > 12:
            return False
    return saw_slash


def _sample_values(cells: list[str], inferred_type: str) -> list[str] | None:
    if inferred_type in _REDACTED_SAMPLE_TYPES:
        return None
    samples: list[str] = []
    seen: set[str] = set()
    for cell in cells:
        if cell not in seen:
            seen.add(cell)
            samples.append(cell)
        if len(samples) == _SAMPLE_VALUES_COUNT:
            break
    return samples or None


def _infer_column(
    cells: list[str], options: AdapterOptions, recognizers: _Recognizers
) -> _Inference:
    """Stages B and B′ for one column's populated (trimmed) cells."""
    n = len(cells)
    if n == 0:
        return _Inference(
            inferred_type="empty",
            base_type="empty",
            match_rate=None,
            non_empty_count=0,
            recognizer=None,
            runner_up=None,
            runner_up_rate=None,
            confidence="none",
            date_order_assumed=False,
            sample_values=None,
        )

    rates = _base_vote(cells, recognizers)
    winner = next(
        (
            name
            for name in _SPECIFICITY
            if rates[name] >= options.inference_threshold
        ),
        None,
    )
    if winner is None:
        newline_fraction = sum(1 for c in cells if "\n" in c) / n
        lengths = sorted(len(c) for c in cells)
        p95 = lengths[max(0, math.ceil(0.95 * n) - 1)]
        base = (
            "long_text"
            if newline_fraction >= _LONG_TEXT_NEWLINE_FRACTION
            or p95 > _LONG_TEXT_P95_LENGTH
            else "text"
        )
        match_rate = 1.0  # text is the universal fallback
        # Near-miss pool: every voted recognizer is a loser here.
        losers = [name for name in _SPECIFICITY if rates[name] < 1.0]
    else:
        base = winner
        match_rate = rates[winner]
        # Recognizers that also cleared the threshold but lost on
        # specificity are grammar supersets, not near-misses.
        losers = [
            name
            for name in _SPECIFICITY
            if name != winner and rates[name] < options.inference_threshold
        ]

    runner_up = None
    runner_up_rate = None
    eligible = [name for name in losers if rates[name] >= _RUNNER_UP_FLOOR]
    if eligible:
        runner_up = max(
            eligible, key=lambda name: (rates[name], -_SPECIFICITY.index(name))
        )
        runner_up_rate = round(rates[runner_up], 3)

    inferred = base
    recognizer: str | None = base
    counts = Counter(cells)
    option_list: list[str] | None = None
    distribution: dict[str, int] | None = None

    if base == "text":
        multi = _multi_enum_pass(cells, options)
        if multi is not None:
            token_counts, _delimiter = multi
            inferred = "multi_enum"
            recognizer = "multi_enum_post_pass"
            option_list = _ordered_options(token_counts)
            distribution = dict(token_counts)
        elif _enum_eligible(n, len(counts), options):
            inferred = "enum"
            recognizer = "enum_post_pass"
            option_list = _ordered_options(counts)
            distribution = dict(counts)
    elif base == "integer" and _auto_number_pass(cells, options.decimal_comma):
        inferred = "auto_number"
        recognizer = "auto_number_post_pass"

    date_order_assumed = (
        base in ("date", "datetime") and _date_order(cells)
    )
    return _Inference(
        inferred_type=inferred,
        base_type=base,
        match_rate=round(match_rate, 3),
        non_empty_count=n,
        recognizer=recognizer,
        runner_up=runner_up,
        runner_up_rate=runner_up_rate,
        confidence=_grade(match_rate, n, options.inference_threshold),
        date_order_assumed=date_order_assumed,
        sample_values=_sample_values(cells, inferred),
        options=option_list,
        value_distribution=distribution,
    )


# ---------------------------------------------------------------------------
# Stage C — structure evidence (spec §4.4)
# ---------------------------------------------------------------------------

_DIGIT_RUN_RE = re.compile(r"\d+")


def _repeated_groups(api_names: list[str]) -> list[dict]:
    """Repeated column groups — headers equal up to a single trailing
    or embedded index, across >= 2 index values: the de-normalized
    child-entity signature."""
    by_index: dict[int, set[str]] = {}
    for name in api_names:
        runs = _DIGIT_RUN_RE.findall(name)
        if len(runs) != 1:
            continue
        by_index.setdefault(int(runs[0]), set()).add(
            _DIGIT_RUN_RE.sub("#", name)
        )
    by_templates: dict[frozenset[str], list[int]] = {}
    for index, templates in by_index.items():
        by_templates.setdefault(frozenset(templates), []).append(index)
    return [
        {"templates": sorted(templates), "indices": sorted(indices)}
        for templates, indices in sorted(
            by_templates.items(), key=lambda kv: sorted(kv[0])
        )
        if len(indices) >= 2
    ]


def _similar_sheets(sheets: list[_Sheet]) -> dict[str, list[dict]]:
    """Near-duplicate sheets: >= 80% of normalized headers shared,
    measured against the larger header set; recorded on both."""
    out: dict[str, list[dict]] = {sheet.name: [] for sheet in sheets}
    slugs = {
        sheet.name: {column.yaml_name for column in sheet.columns}
        for sheet in sheets
    }
    for i, first in enumerate(sheets):
        for second in sheets[i + 1 :]:
            a, b = slugs[first.name], slugs[second.name]
            if not a or not b:
                continue
            fraction = len(a & b) / max(len(a), len(b))
            if fraction >= _SIMILAR_SHEETS_FRACTION:
                entry = round(fraction, 3)
                out[first.name].append(
                    {"sheet": second.name, "shared_header_fraction": entry}
                )
                out[second.name].append(
                    {"sheet": first.name, "shared_header_fraction": entry}
                )
    return out


# ---------------------------------------------------------------------------
# Stage D — cross-sheet reference detection (spec §4.5)
# ---------------------------------------------------------------------------


def _candidate_keys(
    sheets: list[_Sheet],
) -> list[tuple[str, str, frozenset[str]]]:
    """Candidate key columns: >= 95% populated with all-unique values."""
    keys: list[tuple[str, str, frozenset[str]]] = []
    for sheet in sheets:
        if sheet.record_count == 0:
            continue
        for column in sheet.columns:
            populated = _populated(column.cells)
            if not populated:
                continue
            if len(populated) / sheet.record_count < _KEY_POPULATION_FLOOR:
                continue
            if len(set(populated)) != len(populated):
                continue
            keys.append((sheet.name, column.api_name, frozenset(populated)))
    return keys


def _detect_references(
    sheets: list[_Sheet],
    inferences: dict[tuple[str, str], _Inference],
    options: AdapterOptions,
) -> None:
    """Re-type containment matches to ``reference`` in place. The base
    inference is preserved as ``base_type`` evidence; header hints
    raise confidence but are never sufficient alone (spec §4.5)."""
    keys = _candidate_keys(sheets)
    for sheet in sheets:
        for column in sheet.columns:
            inference = inferences[(sheet.name, column.api_name)]
            if inference.inferred_type == "empty":
                continue
            distinct = set(_populated(column.cells))
            if not distinct:
                continue
            best: tuple[float, int, str, str] | None = None
            for target_sheet, target_column, key_values in keys:
                if target_sheet == sheet.name:
                    continue
                matched = len(distinct & key_values)
                if matched < _REFERENCE_MIN_MATCHED:
                    continue
                containment = matched / len(distinct)
                if containment < options.reference_containment_threshold:
                    continue
                candidate = (containment, matched, target_sheet, target_column)
                # Highest containment, then most matched values; name
                # order breaks the remaining ties deterministically.
                if (
                    best is None
                    or candidate[:2] > best[:2]
                    or (candidate[:2] == best[:2] and candidate[2:] < best[2:])
                ):
                    best = candidate
            if best is None:
                continue
            containment, matched, target_sheet, target_column = best
            lowered = column.api_name.lower()
            header_hint = bool(_ID_SUFFIX_RE.search(lowered)) or (
                target_sheet.lower() in lowered
            )
            grade = (
                "high"
                if containment >= 0.99 and matched >= 25
                else "medium"
            )
            if header_hint and grade == "medium":
                grade = "high"  # a hint promotes one grade (spec §5.2)
            inference.inferred_type = "reference"
            inference.recognizer = "reference_containment"
            inference.confidence = grade
            inference.options = None
            inference.value_distribution = None
            inference.reference = {
                "target_sheet": target_sheet,
                "target_column": target_column,
                "containment": round(containment, 3),
                "matched_distinct": matched,
                "header_hint": header_hint,
            }


# ---------------------------------------------------------------------------
# Stage E + emission (spec §4.6/§5/§6)
# ---------------------------------------------------------------------------


def _parse_created_values(cells: list[str]) -> list[datetime | None]:
    """Per-row timestamps from an operator-designated created column:
    date or datetime grammar, None where unparseable/blank."""
    out: list[datetime | None] = []
    for cell in cells:
        value = cell.strip()
        if not value:
            out.append(None)
            continue
        m = _DATETIME_SUFFIX_RE.search(value)
        parsed = _date_parse(value[: m.start()].strip()) if m else None
        if parsed is not None and m is not None:
            time_text = m.group(1).strip().upper()
            time_m = re.match(
                r"^(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?$", time_text
            )
            if time_m:
                hour = int(time_m.group(1))
                meridiem = time_m.group(4)
                if meridiem == "PM" and hour < 12:
                    hour += 12
                if meridiem == "AM" and hour == 12:
                    hour = 0
                if hour <= 23:
                    parsed = parsed.replace(
                        hour=hour,
                        minute=int(time_m.group(2)),
                        second=int(time_m.group(3) or 0),
                    )
        if parsed is None:
            parsed = _date_parse(value)
        out.append(parsed)
    return out


def _type_inference_block(inference: _Inference) -> dict:
    block: dict = {
        "inferred_type": inference.inferred_type,
        "base_type": inference.base_type,
        "match_rate": inference.match_rate,
        "non_empty_count": inference.non_empty_count,
        "recognizer": inference.recognizer,
        "runner_up": inference.runner_up,
        "runner_up_rate": inference.runner_up_rate,
        "confidence": inference.confidence,
        "date_order_assumed": inference.date_order_assumed,
    }
    if inference.sample_values is not None:
        block["sample_values"] = inference.sample_values
    return block


def _field_profile(
    column: _Column,
    inference: _Inference,
    record_count: int,
    created_values: list[datetime | None] | None,
    created_column: str | None,
    options: AdapterOptions,
) -> dict:
    populated = _populated(column.cells)
    populated_count = len(populated)
    empty_string_count = sum(
        1 for cell in column.cells if cell and not cell.strip()
    )
    counts = Counter(populated)
    distinct = len(counts)

    out: dict = {"populated_count": populated_count}
    rate: float | None = None
    if record_count > 0:
        # Unlike a CRM bool column, a spreadsheet boolean cell can be
        # genuinely blank — the rate is computed normally (spec §4.6).
        rate = round(populated_count / record_count, 3)
        out["population_rate"] = rate
    out["distinct_value_count"] = min(distinct, _DISTINCT_CAP)

    detail: dict = {"type_inference": _type_inference_block(inference)}
    if inference.reference is not None:
        detail["reference_inference"] = inference.reference

    last_populated: datetime | None = None
    if created_values is not None and populated_count:
        stamps = [
            created
            for cell, created in zip(column.cells, created_values, strict=True)
            if cell.strip() and created is not None
        ]
        if stamps:
            last_populated = max(stamps)
            out["last_populated_at"] = _format_utc(last_populated)
            detail["last_populated_at_basis"] = {"column": created_column}

    if inference.options is not None:
        # A spreadsheet declares nothing, so the option set IS the
        # observed set: declared == used by construction and the
        # ghost-option signal is structurally zero (spec §4.6).
        out["declared_option_count"] = len(inference.options)
        out["used_option_count"] = len(inference.options)
        detail["value_distribution"] = inference.value_distribution
    elif (
        inference.inferred_type != "empty"
        and distinct <= _TOP_VALUES_MAX_DISTINCT
    ):
        detail["top_values"] = dict(counts.most_common(_TOP_VALUES_COUNT))

    if distinct > _DISTINCT_CAP:
        detail["distinct_overflow"] = True
    if empty_string_count:
        detail["empty_string_count"] = empty_string_count
    if rate is not None and rate < options.low_population_threshold:
        detail["low_population"] = True

    out["detail"] = detail
    return out


def _entity_profile(
    sheet: _Sheet,
    inferences: dict[tuple[str, str], _Inference],
    structure: dict,
    options: AdapterOptions,
) -> dict:
    created_column = options.created_columns.get(sheet.name)
    created_values: list[datetime | None] | None = None
    if created_column is not None:
        column = next(
            (c for c in sheet.columns if c.api_name == created_column), None
        )
        if column is not None:
            created_values = _parse_created_values(column.cells)

    detail: dict = {
        "source_file": sheet.source_file,
        "source_file_modified_at": sheet.source_file_modified_at,
        "blank_row_count": sheet.blank_row_count,
        "ragged_row_count": sheet.ragged_row_count,
        "empty": sheet.record_count == 0,
    }
    detail.update(structure)

    out: dict = {"record_count": sheet.record_count}
    if created_values is not None:
        stamps = [created for created in created_values if created is not None]
        if stamps:
            last_created = max(stamps)
            out["last_record_created_at"] = _format_utc(last_created)
            detail["last_record_created_at_basis"] = {"column": created_column}
            # Entity dormancy is derivable only under designation
            # (spec §4.6); `empty` always.
            detail["dormant"] = False

    out["detail"] = detail
    out["fields"] = {
        column.api_name: _field_profile(
            column,
            inferences[(sheet.name, column.api_name)],
            sheet.record_count,
            created_values,
            created_column,
            options,
        )
        for column in sheet.columns
    }
    return out


def _entity_manifest(
    sheet: _Sheet, inferences: dict[tuple[str, str], _Inference]
) -> dict:
    fields = []
    for column in sheet.columns:
        inference = inferences[(sheet.name, column.api_name)]
        properties: dict = {"required": False}
        if inference.options is not None:
            properties["options"] = inference.options
        fields.append(
            {
                "yaml_name": column.yaml_name,
                "api_name": column.api_name,
                "label": column.api_name,
                "field_type": inference.inferred_type,
                "field_class": "custom",
                "properties": properties,
            }
        )
    return {
        "yaml_name": _slugify(sheet.name) or sheet.name.lower(),
        "espo_name": sheet.name,
        "label_singular": sheet.name.strip(),
        "entity_type": None,
        "entity_class": "custom",
        "stream": False,
        "layouts": [],
        "filtered_tabs": [],
        "fields": fields,
    }


def profile_source(
    path: str | Path,
    options: AdapterOptions | None = None,
    *,
    source_name: str | None = None,
    now: datetime | None = None,
) -> tuple[dict, dict]:
    """Profile one source and return ``(manifest, profile)``.

    A pure function of the files given pinned ``options`` and ``now``
    (criterion C6): same bytes, same options, same clock -> the same
    pair. ``path`` is the source directory of per-sheet CSV files or a
    single CSV file (spec §3.3); unreadable files become manifest
    ``errors`` and the run continues over the remaining sheets.
    """
    options = options or AdapterOptions()
    source = Path(path)
    if source.is_dir():
        csv_paths = sorted(
            p for p in source.iterdir() if p.suffix.lower() == ".csv"
        )
    else:
        csv_paths = [source]
    if not csv_paths:
        raise ValueError(f"no CSV files found in {source}")
    stamp = _format_utc(now or datetime.now(tz=UTC))
    recognizers = _Recognizers(options)

    errors: list[str] = []
    warnings: list[str] = []
    sheets: list[_Sheet] = []
    for csv_path in csv_paths:
        try:
            sheet = _parse_sheet(csv_path, options, recognizers)
        except OSError as exc:
            errors.append(f"sheet {csv_path.stem}: {exc}")
            continue
        warnings.extend(sheet.warnings)
        sheets.append(sheet)

    inferences: dict[tuple[str, str], _Inference] = {
        (sheet.name, column.api_name): _infer_column(
            _populated(column.cells), options, recognizers
        )
        for sheet in sheets
        for column in sheet.columns
    }
    _detect_references(sheets, inferences, options)
    similar = _similar_sheets(sheets)

    anomalies: list[dict] = []
    entities: list[dict] = []
    profile_entities: dict[str, dict] = {}
    for sheet in sheets:
        anomalies.extend(sheet.anomalies)
        structure: dict = {}
        groups = _repeated_groups([c.api_name for c in sheet.columns])
        if groups:
            structure["repeated_group"] = groups
        if similar.get(sheet.name):
            structure["similar_sheets"] = similar[sheet.name]
        entities.append(_entity_manifest(sheet, inferences))
        profile_entities[sheet.name] = _entity_profile(
            sheet, inferences, structure, options
        )

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "source_system": SOURCE_SYSTEM,
        "timestamp": stamp,
        "source_url": source.resolve().as_uri(),
        "source_name": source_name or source.name,
        "errors": errors,
        "warnings": warnings,
        "entities": entities,
        "relationships": [],
        "roles": [],
        "teams": [],
    }
    profile = {
        "manifest_version": MANIFEST_VERSION,
        "profiled_at": stamp,
        "profiler_version": _ADAPTER_VERSION,
        "options": options.profile_options(),
        "anomalies": anomalies,
        "entities": profile_entities,
    }
    return manifest, profile


def write_outputs(
    manifest: dict, profile: dict, output_dir: str | Path
) -> tuple[Path, Path]:
    """Atomic dual-file writer: both payloads land via tmp-file rename,
    written beside the inputs by default (spec §3.4)."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    staged: list[tuple[Path, Path]] = []
    for filename, payload in (
        (MANIFEST_FILENAME, manifest),
        (PROFILE_FILENAME, profile),
    ):
        target = directory / filename
        tmp = directory / f".{filename}.tmp"
        tmp.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        staged.append((tmp, target))
    for tmp, target in staged:
        tmp.replace(target)
    return staged[0][1], staged[1][1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-spreadsheet-profile",
        description=(
            "Profile a spreadsheet source (a directory of per-sheet CSV "
            "files, or one CSV) into the Phase 1.5 manifest pair "
            "(WTK-110), ready for crmbuilder-v2-deposit-audit."
        ),
    )
    parser.add_argument(
        "source", help="source directory of CSV sheets, or a single CSV file"
    )
    parser.add_argument(
        "--source-name",
        default=None,
        help="manifest source_name (default: the source basename)",
    )
    parser.add_argument(
        "--no-header",
        action="append",
        default=[],
        metavar="SHEET",
        help="treat SHEET's row 1 as data; columns become column_1..n",
    )
    parser.add_argument(
        "--created-column",
        action="append",
        default=[],
        metavar="SHEET=COLUMN",
        help=(
            "designate COLUMN as SHEET's record-creation date, enabling "
            "last_record_created_at / last_populated_at"
        ),
    )
    parser.add_argument(
        "--decimal-comma",
        action="store_true",
        help="swap the . and , roles in numbers (European exports)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="where to write the manifest pair (default: beside the input)",
    )
    args = parser.parse_args(argv)

    created_columns: dict[str, str] = {}
    for spec in args.created_column:
        sheet, sep, column = spec.partition("=")
        if not sep or not sheet or not column:
            parser.error(f"--created-column expects SHEET=COLUMN, got {spec!r}")
        created_columns[sheet] = column
    options = AdapterOptions(
        decimal_comma=args.decimal_comma,
        no_header_sheets=frozenset(args.no_header),
        created_columns=created_columns,
    )

    source = Path(args.source)
    manifest, profile = profile_source(
        source, options, source_name=args.source_name
    )
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = source if source.is_dir() else source.parent
    manifest_path, profile_path = write_outputs(manifest, profile, output_dir)

    field_count = sum(len(e["fields"]) for e in manifest["entities"])
    print(
        f"Profiled {len(manifest['entities'])} sheet(s), "
        f"{field_count} column(s); "
        f"{len(profile['anomalies'])} anomaly(ies), "
        f"{len(manifest['warnings'])} warning(s), "
        f"{len(manifest['errors'])} error(s)."
    )
    print(f"Manifest written: {manifest_path}")
    print(f"Profile written: {profile_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
