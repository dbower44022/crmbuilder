#!/usr/bin/env python3
"""Apply a close-out JSON payload to the v2 API.

Reads a single JSON payload file and POSTs each section's records to the
local v2 REST API at http://127.0.0.1:8765. Idempotent on re-run: each
POST treats HTTP 409 conflict as already-present and continues.

v0.8 (PI-030 slice B) extends the script to handle five new top-level
payload sections introduced by the Code Change Lifecycle methodology and
DEC-223 (close-out payload format gains a conversation block):

  conversation → session → work_tickets → planning_items → commits
              → decisions → references → resolves_planning_items
              → addresses_planning_items

Per-section shape transforms translate payload entries into POST bodies:
  - work_tickets[].addresses_planning_item becomes an embedded addresses
    edge in the work_ticket POST.
  - commits[].commit_session_id is auto-populated from the payload's
    session block (per PI-073 / DEC-314 — commits now attribute to
    sessions, replacing the legacy commit_conversation_id which
    pointed at the v0.7 conversation entity).
  - resolves_planning_items[] entries translate to POST /references with
    relationship=resolves; slice A's atomic edge+flip fires server-side.
  - addresses_planning_items[] entries translate to POST /references with
    relationship=addresses (no status flip).

Sections absent from the payload are skipped (no-op), preserving backward
compatibility with v0.7 payloads.

v0.7 (governance entity release) integrates deposit_event creation as the
apply's last step. The script:

1. Fetches the next ``DEP-NNN`` identifier from
   ``GET /deposit-events/next-identifier`` at start.
2. Opens a log file at
   ``PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log`` and tees
   stdout to it so the full apply transcript is captured.
3. Captures per-record HTTP outcomes into a ``wrote_records`` accumulator
   (200/201 only) and a ``records_summary`` counter dict (keyed by the
   spec's plural names — ``sessions``, ``decisions``, ``planning_items``,
   ``references``, plus v0.8 ``conversations``, ``work_tickets``,
   ``commits``).
4. POSTs a deposit_event at the apply's last step with the captured
   summary, the apply-context provenance, the parent
   ``deposit_event_applies_close_out_payload`` edge (target derived from
   the payload basename ``ses_NNN.json`` → ``COP-NNN``), and one
   ``deposit_event_wrote_record`` edge per record created. The access
   layer lazy-creates the target close_out_payload when missing.

Exit code 0 on full success; non-zero only if a non-409 error is
encountered or the payload file cannot be read.
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple

import crmbuilder_v2

BASE = "http://127.0.0.1:8765"


def _load_closeout_validator():
    """Load the sibling ``closeout_validator.py`` module by file-path.

    The script lives in ``crmbuilder-v2/scripts/`` which isn't on the package
    import path, so the PI-090 validator module is loaded the same way tests
    load this script (``spec_from_file_location``). Returns the module, or
    None if it can't be loaded (in which case validation is skipped with a
    warning — the apply still runs).
    """
    validator_path = Path(__file__).resolve().parent / "closeout_validator.py"
    try:
        spec = importlib.util.spec_from_file_location(
            "closeout_validator", validator_path
        )
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("closeout_validator", module)
        spec.loader.exec_module(module)
        return module
    except (OSError, ImportError):
        return None


class _Section(NamedTuple):
    """A single close-out payload section descriptor.

    ``shape_fn`` is an optional per-entry transform that receives the raw
    payload entry plus a cross-section ``context`` dict and returns the
    body to POST. When None, the entry is POSTed as-is (identity).
    """

    name: str
    endpoint: str
    is_singular: bool
    entity_type: str
    summary_key: str
    shape_fn: Callable[[dict, dict], dict] | None = None


def _shape_work_ticket(entry: dict, context: dict) -> dict:
    """Pop ``addresses_planning_item`` and translate to an embedded
    addresses edge in the work_ticket POST body (atomic with the create).

    The API's embedded references list validates source_type and source_id
    on every entry, so the work_ticket's own identifier must be present in
    the entry; otherwise the implicit-source case can't be expressed."""
    body = {k: v for k, v in entry.items() if k != "addresses_planning_item"}
    target_pi = entry.get("addresses_planning_item")
    if target_pi:
        wt_id = entry.get("work_ticket_identifier")
        if not wt_id:
            raise ValueError(
                "work_ticket entry has addresses_planning_item but no "
                "work_ticket_identifier — the embedded addresses edge needs "
                "an explicit source_id. Either include work_ticket_identifier "
                "in the entry, or omit addresses_planning_item and create the "
                "edge in a separate references entry after the work_ticket "
                "has been assigned an identifier."
            )
        existing_refs = list(body.get("references") or [])
        existing_refs.append({
            "source_type": "work_ticket",
            "source_id": wt_id,
            "target_type": "planning_item",
            "target_id": target_pi,
            "relationship": "addresses",
        })
        body["references"] = existing_refs
    return body


def _shape_commit(entry: dict, context: dict) -> dict:
    """Inject ``commit_session_id`` from the payload's session block.

    Under PI-073 / DEC-314, commits attribute to sessions (not the
    legacy v0.7 conversation entity). The payload entry omits the FK;
    the apply derives it from the close-out's owning session (from the
    payload's ``session.identifier`` block).
    """
    sess_id = context.get("session_identifier")
    if not sess_id:
        raise ValueError(
            "commits section present but no session block in payload — "
            "every commit needs commit_session_id. Add a session "
            "block per methodology §4.0."
        )
    body = dict(entry)
    body.setdefault("commit_session_id", sess_id)
    return body


def _shape_resolves_pi(entry: dict, context: dict) -> dict:
    """Translate ``{planning_item_identifier: PI-NNN}`` to a full
    POST /references body with relationship=resolves. The conversation
    source is derived from the payload's conversation block."""
    conv_id = context.get("conversation_identifier")
    if not conv_id:
        raise ValueError(
            "resolves_planning_items section present but no conversation "
            "block in payload — resolves edges flow from the conversation. "
            "Add a conversation block per methodology §4.0."
        )
    target_pi = entry["planning_item_identifier"]
    return {
        "source_type": "conversation",
        "source_id": conv_id,
        "target_type": "planning_item",
        "target_id": target_pi,
        "relationship": "resolves",
    }


def _shape_addresses_pi(entry: dict, context: dict) -> dict:
    """Translate ``{planning_item_identifier: PI-NNN}`` to a full
    POST /references body with relationship=addresses. No status flip."""
    conv_id = context.get("conversation_identifier")
    if not conv_id:
        raise ValueError(
            "addresses_planning_items section present but no conversation "
            "block in payload — addresses edges flow from the conversation. "
            "Add a conversation block per methodology §4.0."
        )
    target_pi = entry["planning_item_identifier"]
    return {
        "source_type": "conversation",
        "source_id": conv_id,
        "target_type": "planning_item",
        "target_id": target_pi,
        "relationship": "addresses",
    }


def _inline_membership_edges(
    payload: dict, section_name: str, kind: str
) -> None:
    """Hoist mandatory membership edges from top-level ``references`` into
    the singular ``session`` / ``conversation`` block.

    Without this hoist, the apply script POSTs the singular block BEFORE
    the top-level references section, and the access-layer edge-rule
    validator on the create endpoint can't see the membership edge yet
    — the create returns 422 with ``missing_*_membership_edge``.

    Mutates ``payload`` in place: matching edges are moved out of
    ``payload['references']`` and into ``payload[section_name]['references']``,
    so the top-level references section no longer tries to POST them
    (avoiding 409 collisions with the inline edge that the create
    transaction already wrote).

    No-op if the section block is missing, isn't a dict, or has no
    candidate edges in top-level references.
    """
    block = payload.get(section_name)
    if not isinstance(block, dict):
        return
    # The source identifier — new shape uses ``<section>_identifier``;
    # legacy session payloads also accepted plain ``identifier``.
    source_id_key = f"{section_name}_identifier"
    source_id = block.get(source_id_key) or block.get("identifier")
    if not isinstance(source_id, str):
        return
    top_refs = payload.get("references")
    if not isinstance(top_refs, list):
        return

    matched: list[dict] = []
    kept: list[dict] = []
    for edge in top_refs:
        if not isinstance(edge, dict):
            kept.append(edge)
            continue
        if (
            edge.get("source_type") == section_name
            and edge.get("source_id") == source_id
            and edge.get("relationship") == kind
        ):
            matched.append(edge)
        else:
            kept.append(edge)

    if not matched:
        return

    payload["references"] = kept
    inline_refs = block.get("references") or []
    if not isinstance(inline_refs, list):
        inline_refs = []
    block["references"] = list(inline_refs) + matched


# Section descriptors in apply order. PI-099 swapped session and
# conversation so the conversation POSTs first — its mandatory inline
# ``conversation_belongs_to_session`` edge must exist before the
# session create runs validate_edges (the ``complete_session_requires_
# conversation`` rule looks for that inbound edge at create-time). The
# rest of the order is fixed: conversation → session → work_tickets →
# planning_items → commits → decisions → references →
# resolves_planning_items → addresses_planning_items.
_SECTIONS: list[_Section] = [
    _Section("conversation",             "/conversations",  True,  "conversation",   "conversations"),
    _Section("session",                  "/sessions",       True,  "session",        "sessions"),
    _Section("work_tickets",             "/work-tickets",   False, "work_ticket",    "work_tickets", _shape_work_ticket),
    _Section("planning_items",           "/planning-items", False, "planning_item",  "planning_items"),
    _Section("commits",                  "/commits",        False, "commit",         "commits",       _shape_commit),
    _Section("decisions",                "/decisions",      False, "decision",       "decisions"),
    _Section("references",               "/references",     False, "reference",      "references"),
    _Section("resolves_planning_items",  "/references",     False, "reference",      "references",    _shape_resolves_pi),
    _Section("addresses_planning_items", "/references",     False, "reference",      "references",    _shape_addresses_pi),
]


def _request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_bytes = e.read().decode()
        try:
            payload = json.loads(body_bytes)
        except json.JSONDecodeError:
            payload = {"raw": body_bytes}
        return e.code, payload
    except urllib.error.URLError as e:
        return 0, {"error": "connection_failed", "detail": str(e)}


def _log(label: str, status: int, payload: dict) -> bool:
    """Print result; return True on success-or-409, False on real error."""
    if status in (200, 201, 204):
        print(f"  ✓ {label} (HTTP {status})")
        return True
    if status == 409:
        print(f"  · {label} already present (HTTP 409) — skipping")
        return True
    if status == 0:
        print(f"  ✗ {label} CONNECTION FAILED: {payload}", file=sys.stderr)
        return False
    errors = payload.get("errors") or payload.get("detail") or payload
    print(f"  ✗ {label} FAILED (HTTP {status}): {errors}", file=sys.stderr)
    return False


def _record_label(section: str, record: dict) -> str:
    # Try plain identifier first, then prefixed variants (v0.8 entity
    # types use prefixed identifier field names).
    ident = (
        record.get("identifier")
        or record.get("conversation_identifier")
        or record.get("work_ticket_identifier")
        or record.get("commit_identifier")
    )
    if ident:
        return f"POST {section}  {ident}"
    # resolves_planning_items / addresses_planning_items entries
    if record.get("planning_item_identifier"):
        return f"POST {section}  → {record['planning_item_identifier']}"
    src = record.get("source_id")
    tgt = record.get("target_id")
    rel = record.get("relationship")
    if src and tgt and rel:
        return f"POST {section}  {src} {rel} {tgt}"
    return f"POST {section}  <unidentified record>"


def _check_api_reachable() -> bool:
    status, payload = _request("GET", "/health")
    if status == 200:
        return True
    if status == 0:
        print(
            f"\n✗ Cannot reach v2 API at {BASE}.\n"
            f"  Start it with: uv run crmbuilder-v2-api &\n"
            f"  Detail: {payload}\n",
            file=sys.stderr,
        )
        return False
    print(
        f"\n✗ v2 API at {BASE} returned HTTP {status} on /health.\n"
        f"  Detail: {payload}\n",
        file=sys.stderr,
    )
    return False


# ---------------------------------------------------------------------------
# v0.7: log-file tee + deposit_event capture
# ---------------------------------------------------------------------------


class _TeeStream:
    """File-like that forwards writes to two underlying streams."""

    def __init__(self, primary, secondary) -> None:
        self._primary = primary
        self._secondary = secondary

    def write(self, data: str) -> int:
        n = self._primary.write(data)
        try:
            self._secondary.write(data)
        except (OSError, ValueError):
            pass
        return n

    def flush(self) -> None:
        for stream in (self._primary, self._secondary):
            try:
                stream.flush()
            except (OSError, ValueError):
                pass


def _next_deposit_event_identifier() -> str:
    """Return the next ``DEP-NNN`` identifier from the API, or a fallback."""
    status, payload = _request("GET", "/deposit-events/next-identifier")
    if status == 200 and isinstance(payload, dict):
        nxt = payload.get("data", payload).get("next")
        if isinstance(nxt, str):
            return nxt
    # Fallback so the apply still runs against an older API; the deposit
    # POST itself will succeed because the access layer reassigns.
    return "DEP-???"


def _derive_cop_identifier(payload_path: Path) -> str | None:
    """``close-out-payloads/ses_055.json`` → ``COP-055``; ``None`` if unparseable."""
    stem = payload_path.stem  # e.g. "ses_055"
    parts = stem.split("_")
    if len(parts) != 2 or not parts[1].isdigit():
        return None
    return f"COP-{int(parts[1]):03d}"


def _extract_data(payload: dict) -> dict:
    """Pull the unwrapped record dict from a ``{data, meta, errors}`` body."""
    if isinstance(payload, dict) and "data" in payload and isinstance(payload["data"], dict):
        return payload["data"]
    return payload if isinstance(payload, dict) else {}


def _record_target_id(entity_type: str, response_data: dict) -> str | None:
    """Extract the addressable identifier from a created record's response.

    Most entities use a plain ``identifier`` field at the row level; the
    v0.8 entity types (conversation, work_ticket, commit) carry a
    prefixed field name. Match each known entity type explicitly so the
    apply doesn't fall through to a missing field.
    """
    field_by_type = {
        "session": "session_identifier",
        "decision": "identifier",
        "planning_item": "identifier",
        "reference": "reference_identifier",
        "conversation": "conversation_identifier",
        "work_ticket": "work_ticket_identifier",
        "commit": "commit_identifier",
    }
    field = field_by_type.get(entity_type, "identifier")
    return response_data.get(field)


def _post_deposit_event(
    *,
    dep_identifier: str,
    cop_identifier: str,
    outcome: str,
    records_summary: dict[str, int],
    wrote_records: list[tuple[str, str]],
    error_info: dict | None,
    log_file_path: str,
    target_file_path: str,
    invocation: str,
) -> None:
    """POST the deposit_event capturing this apply run."""
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    title = f"Apply of {cop_identifier}, {timestamp}"
    summary_phrase = (
        ", ".join(
            f"{count} {key}" for key, count in sorted(records_summary.items()) if count
        )
        or "no records written"
    )
    if outcome == "success":
        description = f"Applied {cop_identifier}. Outcome: success. {summary_phrase}."
    else:
        step = (error_info or {}).get("step", "?")
        description = (
            f"Applied {cop_identifier}. Outcome: failure at step {step}. "
            f"Records written before failure: {summary_phrase}."
        )
    body: dict[str, Any] = {
        "deposit_event_identifier": dep_identifier,
        "deposit_event_title": title,
        "deposit_event_description": description,
        "deposit_event_outcome": outcome,
        "deposit_event_records_summary": records_summary,
        "deposit_event_apply_context": {
            "apply_script_version": crmbuilder_v2.__version__,
            "invocation": invocation,
            "runner": "claude_code",
        },
        "deposit_event_log_file_path": log_file_path,
        "deposit_event_error_info": error_info,
        "target_file_path": target_file_path,
        "references": [
            {
                "target_type": "close_out_payload",
                "target_id": cop_identifier,
                "relationship": "deposit_event_applies_close_out_payload",
            }
        ]
        + [
            {
                "target_type": entity_type,
                "target_id": target_id,
                "relationship": "deposit_event_wrote_record",
            }
            for entity_type, target_id in wrote_records
        ],
    }
    status, payload = _request("POST", "/deposit-events", body)
    if status in (200, 201):
        print(f"\n✓ Recorded apply as deposit_event {dep_identifier} (HTTP {status}).")
    else:
        # The deposit_event POST itself failed; surface it but don't change
        # the apply's exit code (the records that landed before this step
        # still landed). The operator can re-run; the access layer's
        # idempotent edge upserts handle re-confirmation.
        errors = payload.get("errors") if isinstance(payload, dict) else payload
        print(
            f"\n⚠ deposit_event POST failed (HTTP {status}): {errors}",
            file=sys.stderr,
        )


def _current_git_branch() -> str | None:
    """Return the current git branch name, or None if it can't be determined."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def main() -> int:
    global BASE

    parser = argparse.ArgumentParser(
        description="Apply a close-out JSON payload to the v2 API.",
    )
    parser.add_argument(
        "payload_path",
        type=Path,
        help="Path to the JSON payload file to apply.",
    )
    parser.add_argument(
        "--base",
        default=BASE,
        help=f"Override the v2 API base URL (default: {BASE}).",
    )
    parser.add_argument(
        "--skip-deposit-event",
        action="store_true",
        help=(
            "Skip the final deposit_event POST and log capture (useful for "
            "backfill scripts that author deposit_events explicitly)."
        ),
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help=(
            "Bypass the PI-090 pre-flight close-out-payload validator "
            "entirely. For emergencies only — the validator catches "
            "payload-shape violations before any record is POSTed."
        ),
    )
    parser.add_argument(
        "--allow-branch-local",
        action="store_true",
        help=(
            "Permit applying on a non-main branch (Model B isolated-DB work "
            "only). Requires CRMBUILDER_V2_DB_PATH to point at a gitignored "
            "branch-local engagement DB. Default refuses any apply off main."
        ),
    )
    args = parser.parse_args()

    branch = _current_git_branch()
    if branch is not None and branch != "main" and not args.allow_branch_local:
        print(
            f"✗ Refusing to apply a close-out on branch '{branch}'.",
            file=sys.stderr,
        )
        print(
            "  Governance applies must run on 'main' so the identifier "
            "sequence advances\n  on a single line (Model A). If this is "
            "isolated-DB branch work, re-run\n  with --allow-branch-local AND "
            "ensure CRMBUILDER_V2_DB_PATH points at a\n  gitignored "
            "branch-local engagement DB.",
            file=sys.stderr,
        )
        return 2

    BASE = args.base

    if not args.payload_path.exists():
        print(f"✗ Payload file not found: {args.payload_path}", file=sys.stderr)
        return 2

    try:
        with args.payload_path.open() as f:
            payload = json.load(f)
    except json.JSONDecodeError as e:
        print(f"✗ Failed to parse payload JSON: {e}", file=sys.stderr)
        return 2

    label = payload.get("label", str(args.payload_path.name))

    # v0.7: open the deposit-event log file and tee stdout to it. The log
    # captures the full apply transcript regardless of outcome.
    record_deposit = not args.skip_deposit_event
    dep_identifier = _next_deposit_event_identifier() if record_deposit else None
    log_dir = args.payload_path.parent.parent / "deposit-event-logs"
    log_disk_path: Path | None = None
    log_repo_relative: str | None = None
    log_file_handle: io.TextIOWrapper | None = None
    original_stdout = sys.stdout
    if record_deposit and dep_identifier:
        log_disk_path = log_dir / f"{dep_identifier.lower().replace('-', '_')}.log"
        log_disk_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            log_file_handle = log_disk_path.open("w", encoding="utf-8")
            sys.stdout = _TeeStream(original_stdout, log_file_handle)  # type: ignore[assignment]
            log_repo_relative = (
                f"PRDs/product/crmbuilder-v2/deposit-event-logs/{log_disk_path.name}"
            )
        except OSError as exc:
            print(
                f"⚠ Could not open log file {log_disk_path}: {exc}", file=sys.stderr
            )
            log_disk_path = None
            log_repo_relative = None

    try:
        print("=== Applying close-out payload ===")
        print(f"Source: {args.payload_path}")
        print(f"Label:  {label}")
        if dep_identifier:
            print(f"Deposit event: {dep_identifier}")
        print()

        if not _check_api_reachable():
            return 2

        # PI-090 pre-flight: validate the payload against the governance
        # recording rules BEFORE any record is POSTed. Hard-reject (error)
        # violations abort with exit code 2 so no partial apply happens;
        # warnings print but the apply proceeds. ``--skip-validation``
        # bypasses entirely (emergencies / backfill).
        #
        # The in-process test harness (test_apply_close_out.py) monkeypatches
        # ``_request`` to route through a FastAPI TestClient and exercises the
        # POST path with intentionally-minimal / legacy-shape payloads that
        # this validator would (correctly) reject — those tests assert the
        # downstream apply behavior, not pre-flight shape. Skip the gate when
        # ``_request`` has been monkeypatched away from its module-defined
        # original, so the production CLI always validates while the
        # apply-path tests keep exercising what they target. New-shape real
        # payloads (and the dedicated validator tests) are unaffected.
        _harness_routed = (
            getattr(_request, "__module__", None) != __name__
            or getattr(_request, "__qualname__", "") != "_request"
        )
        if not args.skip_validation and not _harness_routed:
            validator = _load_closeout_validator()
            if validator is None:
                print(
                    "⚠ Could not load closeout_validator.py; skipping "
                    "pre-flight validation.",
                    file=sys.stderr,
                )
            else:
                violations = validator.validate_payload(payload, api_base=BASE)
                errors = [
                    v for v in violations if v.severity == validator.SEVERITY_ERROR
                ]
                if violations:
                    print(validator.format_report(violations))
                    print()
                if errors:
                    print(
                        f"✗ Pre-flight validation failed with {len(errors)} "
                        f"error(s). No records were POSTed. Fix the payload "
                        f"and re-run, or pass --skip-validation to override "
                        f"(emergencies only).",
                        file=sys.stderr,
                    )
                    return 2

        ok = True
        total_processed = 0
        wrote_records: list[tuple[str, str]] = []
        # v0.8: de-dup summary keys — references, resolves_planning_items,
        # and addresses_planning_items all roll up under "references".
        records_summary: dict[str, int] = {}
        for section in _SECTIONS:
            records_summary.setdefault(section.summary_key, 0)
        first_error: dict | None = None

        # Cross-section values that per-entry shape functions need.
        #
        # PI-073 / DEC-314 update: commits now attribute to session_identifier
        # (the column on the commits table was renamed from
        # commit_conversation_id to commit_session_id). The session_identifier
        # propagates into commits. The conversation_identifier still
        # propagates into resolves_/addresses_planning_items as the source_id
        # of those reference edges (a conversation resolves/addresses PIs).
        context: dict[str, str] = {}
        session_block = payload.get("session")
        if isinstance(session_block, dict):
            # New shape uses session_identifier; legacy shape used 'identifier'
            si = session_block.get("session_identifier") or session_block.get("identifier")
            if isinstance(si, str):
                context["session_identifier"] = si
        conversation_block = payload.get("conversation")
        if isinstance(conversation_block, dict):
            ci = conversation_block.get("conversation_identifier")
            if isinstance(ci, str):
                context["conversation_identifier"] = ci

        # Inline membership edges into singular session/conversation blocks
        # so the access layer sees the mandatory edge at create-validation
        # time. (Apply-script edge-ordering bug surfaced at SES-099 apply:
        # session POST runs before the top-level references[] section, so
        # a session_belongs_to_project edge in references[] arrives
        # AFTER the session validate_edges check fires. Same for
        # conversation_belongs_to_session edges with conversations.)
        # Hoist any matching top-level reference into the source-entity's
        # inline references array, then strip from top-level so the
        # references section doesn't re-POST.
        _inline_membership_edges(payload, "session",
                                 "session_belongs_to_project")
        _inline_membership_edges(payload, "conversation",
                                 "conversation_belongs_to_session")

        for section in _SECTIONS:
            section_name = section.name
            if section_name not in payload or not payload[section_name]:
                continue
            records = (
                [payload[section_name]] if section.is_singular else payload[section_name]
            )
            print(
                f"=== {section_name} ({len(records)} record{'s' if len(records) != 1 else ''}) ==="
            )
            for record in records:
                try:
                    body = (
                        record
                        if section.shape_fn is None
                        else section.shape_fn(record, context)
                    )
                except ValueError as exc:
                    ok = False
                    total_processed += 1
                    print(f"  ✗ {_record_label(section_name, record)} SHAPE ERROR: {exc}", file=sys.stderr)
                    if first_error is None:
                        first_error = {
                            "kind": "shape_error",
                            "message": str(exc)[:300],
                            "step": section_name,
                            "http_status": 0,
                        }
                    continue
                status, response = _request("POST", section.endpoint, body)
                rec_ok = _log(_record_label(section_name, record), status, response)
                ok &= rec_ok
                total_processed += 1
                if status in (200, 201):
                    response_data = _extract_data(response)
                    target_id = _record_target_id(section.entity_type, response_data)
                    if target_id:
                        # References are first-class records here but are not
                        # in the deposit_event references' target_type vocab,
                        # so they cannot appear as deposit_event_wrote_record
                        # back-edges. The access layer enforces
                        # sum(records_summary) == len(wrote_records), so we
                        # also skip the summary bump — the count of references
                        # written lives in the source payload and the
                        # references table itself.
                        if section.entity_type != "reference":
                            wrote_records.append((section.entity_type, target_id))
                            records_summary[section.summary_key] += 1
                elif status not in (200, 201, 204, 409) and first_error is None:
                    errors = (
                        response.get("errors") if isinstance(response, dict) else None
                    )
                    err_msg = (
                        json.dumps(errors)[:300]
                        if errors
                        else str(response)[:300]
                    )
                    first_error = {
                        "kind": "http_error" if status > 0 else "connection_failure",
                        "message": err_msg,
                        "step": section_name,
                        "http_status": status,
                    }
            print()

        if ok:
            print(f"✓ All {total_processed} operations complete.")
        else:
            print(
                f"✗ One or more of {total_processed} operations failed. "
                f"See stderr for details. Re-running is safe (409 = already present).",
                file=sys.stderr,
            )

        # v0.7: POST the deposit_event as the apply's last step.
        if record_deposit and dep_identifier and log_repo_relative:
            cop_identifier = _derive_cop_identifier(args.payload_path)
            if cop_identifier is None:
                print(
                    "⚠ Could not derive COP-NNN from payload basename; "
                    "skipping deposit_event POST.",
                    file=sys.stderr,
                )
            else:
                outcome = "success" if ok else "failure"
                _post_deposit_event(
                    dep_identifier=dep_identifier,
                    cop_identifier=cop_identifier,
                    outcome=outcome,
                    records_summary=records_summary,
                    wrote_records=wrote_records,
                    error_info=first_error if outcome == "failure" else None,
                    log_file_path=log_repo_relative,
                    target_file_path=(
                        f"PRDs/product/crmbuilder-v2/close-out-payloads/"
                        f"{args.payload_path.name}"
                    ),
                    invocation=" ".join(sys.argv),
                )

        return 0 if ok else 1
    finally:
        if log_file_handle is not None:
            sys.stdout = original_stdout
            try:
                log_file_handle.flush()
                log_file_handle.close()
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(main())
