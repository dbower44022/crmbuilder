#!/usr/bin/env python3
"""Pre-flight validator for v2 close-out payloads (PI-090).

This module is the *executable form* of the governance recording rules in
``specifications/governance-recording-rules.md``: it checks a close-out
payload against the rules BEFORE ``apply_close_out.py`` POSTs any record to
the V2 API, so violations surface as one clear report instead of a partial
apply that leaves orphan records behind.

**Post-PI-073 / DEC-314 adaptation.** The PI-090 body's check list predated
the session/conversation redesign. The checks here are reconciled against the
*current* schema specs (``session-v2.md``, ``conversation-v2.md``):

  - Decisions are ``decided_in`` a CONVERSATION (CNV-NNN), not a session.
  - Conversation parentage is ``conversation_belongs_to_session`` — the
    retired ``conversation_belongs_to_workstream`` / ``conversation_records_session``
    kinds are NOT validated for.
  - Sessions have no ``session_date`` field; that PI-body check is dropped.

**Architecture.** ``validate_payload(payload, api_base=None)`` is the public
entry point. The pure-shape checks (1-9) run WITHOUT an API. Only the
identifier-head check (10) needs the API; it is skipped when ``api_base`` is
None (offline mode for unit tests) or can be driven by a caller-supplied
``head_fetcher`` callable for testability without a live server. The module
uses ``urllib`` only — no access-layer imports — mirroring
``apply_close_out.py``'s dependency-light style so the two can sit side by
side as sibling scripts.

The vocab values (``SESSION_MEDIUMS``, ``DECISION_STATUSES``) are imported
live from ``crmbuilder_v2.access.vocab`` rather than hardcoded, so the
validator never drifts from the access layer's own enums.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

# When this file is loaded by ``importlib.util.spec_from_file_location`` (the
# pattern used by tests and by PI-090's verification snippet), the module is
# not registered in ``sys.modules`` by default. The ``@dataclass`` decorator
# below resolves field types against ``sys.modules[cls.__module__].__dict__``;
# without registration that lookup returns None and the decorator raises an
# AttributeError. Self-register a module object whose namespace is this exact
# globals dict so the dataclass works under any loader.
if sys.modules.get(__name__) is None:  # pragma: no cover - loader-dependent
    import types as _types

    _self_module = _types.ModuleType(__name__)
    _self_module.__dict__.update(globals())
    sys.modules[__name__] = _self_module

# Import the live vocab so the validator's accepted values track the access
# layer's CHECK constraints exactly. If the package import path is not set up
# (the validator is sometimes loaded by file-path in tests), fall back to the
# values captured at authoring time — a deliberate, documented duplicate kept
# in lock-step with vocab.py.
try:
    from crmbuilder_v2.access.vocab import DECISION_STATUSES, SESSION_MEDIUMS
except Exception:  # pragma: no cover - exercised only when package isn't importable
    SESSION_MEDIUMS = frozenset(
        {"chat", "email", "phone", "zoom", "in_person", "slack", "other"}
    )
    DECISION_STATUSES = frozenset({"Active", "Superseded", "Withdrawn", "Deleted"})


# ---------------------------------------------------------------------------
# Violation model
# ---------------------------------------------------------------------------

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"


@dataclass(frozen=True)
class Violation:
    """A single rule violation found in a payload.

    ``severity`` is ``"error"`` (hard reject — blocks the apply) or
    ``"warning"`` (printed but the apply proceeds). ``check_name`` is the
    short name of the check that produced it (so the report and the rules
    document stay synchronized). ``message`` is the actionable detail.
    """

    severity: str
    check_name: str
    message: str


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

# The ten payload sections per the v0.8 close-out shape (CLAUDE.md §
# "v2 session lifecycle — closing a session"). Empty arrays/objects are
# acceptable; a MISSING key is an error.
REQUIRED_SECTIONS: tuple[str, ...] = (
    "label",
    "session",
    "conversation",
    "work_tickets",
    "planning_items",
    "commits",
    "decisions",
    "references",
    "resolves_planning_items",
    "addresses_planning_items",
)

# Decision status enum. ``Final`` is explicitly NOT here — see check 4.
# (Imported live as DECISION_STATUSES; this tuple is just for the message.)
_VALID_DECISION_STATUSES = tuple(sorted(DECISION_STATUSES))

# executive_summary length bounds — mirrors PI-074's validate_optional_length
# (crmbuilder-v2/src/crmbuilder_v2/access/_helpers.py). Present non-empty
# values must be 200-800 chars inclusive; absent/empty/whitespace passes.
_EXEC_SUMMARY_MIN = 200
_EXEC_SUMMARY_MAX = 800

_SES_RE = re.compile(r"^SES-\d{3}$")
_CNV_RE = re.compile(r"^CNV-\d{3}$")

# Map an identifier prefix to its head endpoint and a regex it must match for
# the head-conflict comparison. Commits are deliberately omitted: real
# payloads identify commits by ``commit_sha`` (40-hex), not a sequential
# ``CM-NNNN`` identifier, so there is no per-payload identifier to compare
# against the head. The API's 409 still catches a true SHA collision.
_HEAD_ENDPOINTS: dict[str, str] = {
    "SES": "/sessions/next-identifier",
    "CNV": "/conversations/next-identifier",
    "DEC": "/decisions/next-identifier",
    "PI": "/planning-items/next-identifier",
    "WT": "/work-tickets/next-identifier",
}


# ---------------------------------------------------------------------------
# Individual checks (each returns a list[Violation])
# ---------------------------------------------------------------------------


def check_required_sections(payload: dict) -> list[Violation]:
    """Check 1 (HARD): every required top-level section key is present.

    Empty arrays / objects are fine; a *missing* key is an error.
    """
    out: list[Violation] = []
    for key in REQUIRED_SECTIONS:
        if key not in payload:
            out.append(
                Violation(
                    SEVERITY_ERROR,
                    "required_sections",
                    f"payload is missing required section '{key}'. "
                    f"All ten sections must be present (empty arrays/objects "
                    f"are OK): {', '.join(REQUIRED_SECTIONS)}.",
                )
            )
    return out


def check_session_block(payload: dict) -> list[Violation]:
    """Check 2 (HARD): session block shape + session_medium vocab.

    The session block must carry session_identifier (SES-NNN), session_title,
    session_description, session_medium, session_status — and session_medium
    must be in SESSION_MEDIUMS.

    This is the check that would have caught SES-101's
    ``session_medium="claude_code"`` failure (``claude_code`` is a
    chat-platform value belonging in ``session_medium_metadata.chat_platform``,
    not in the ``session_medium`` enum, which is one of
    chat/email/phone/zoom/in_person/slack/other).
    """
    out: list[Violation] = []
    block = payload.get("session")
    if not isinstance(block, dict):
        return [
            Violation(
                SEVERITY_ERROR,
                "session_block",
                "session block is missing or not an object.",
            )
        ]

    ident = block.get("session_identifier")
    if not isinstance(ident, str) or not _SES_RE.match(ident):
        out.append(
            Violation(
                SEVERITY_ERROR,
                "session_block",
                f"session.session_identifier must match SES-NNN; got {ident!r}.",
            )
        )
    for field in ("session_title", "session_description", "session_status"):
        val = block.get(field)
        if not isinstance(val, str) or not val.strip():
            out.append(
                Violation(
                    SEVERITY_ERROR,
                    "session_block",
                    f"session.{field} is required and must be a non-empty string.",
                )
            )

    medium = block.get("session_medium")
    if medium not in SESSION_MEDIUMS:
        out.append(
            Violation(
                SEVERITY_ERROR,
                "session_block",
                f"session.session_medium={medium!r} is not in SESSION_MEDIUMS "
                f"{sorted(SESSION_MEDIUMS)}. (This is the SES-101 case — "
                f"'claude_code' is a chat-platform value for "
                f"session_medium_metadata.chat_platform, not a session_medium.)",
            )
        )
    return out


def _collect_references(payload: dict) -> list[dict]:
    """Return all reference edges visible to the validator.

    Edges may appear in the top-level ``references[]`` section OR inline in
    the singular ``session`` / ``conversation`` blocks' own ``references``
    arrays (the apply script hoists membership edges into those blocks).
    Both placements are valid, so the validator unions them.
    """
    refs: list[dict] = []
    top = payload.get("references")
    if isinstance(top, list):
        refs.extend(r for r in top if isinstance(r, dict))
    for block_name in ("session", "conversation"):
        block = payload.get(block_name)
        if isinstance(block, dict):
            inline = block.get("references")
            if isinstance(inline, list):
                refs.extend(r for r in inline if isinstance(r, dict))
    return refs


def check_conversation_block(payload: dict) -> list[Violation]:
    """Check 3 (HARD): conversation block shape + parentage edge.

    The conversation block must carry conversation_identifier (CNV-NNN),
    conversation_title, conversation_status. It must also have a
    ``conversation_belongs_to_session`` edge (in the block's inline
    references OR the top-level references[]) from this CNV to the payload's
    SES — that edge is what makes the post-PI-073
    ``complete_session_requires_conversation`` rule satisfiable at apply time
    (the session create-validation looks for the inbound edge).
    """
    out: list[Violation] = []
    block = payload.get("conversation")
    if not isinstance(block, dict):
        return [
            Violation(
                SEVERITY_ERROR,
                "conversation_block",
                "conversation block is missing or not an object.",
            )
        ]

    conv_id = block.get("conversation_identifier")
    if not isinstance(conv_id, str) or not _CNV_RE.match(conv_id):
        out.append(
            Violation(
                SEVERITY_ERROR,
                "conversation_block",
                f"conversation.conversation_identifier must match CNV-NNN; "
                f"got {conv_id!r}.",
            )
        )
    for field in ("conversation_title", "conversation_status"):
        val = block.get(field)
        if not isinstance(val, str) or not val.strip():
            out.append(
                Violation(
                    SEVERITY_ERROR,
                    "conversation_block",
                    f"conversation.{field} is required and must be a "
                    f"non-empty string.",
                )
            )

    # Parentage edge: conversation_belongs_to_session from this CNV to the SES.
    ses_block = payload.get("session")
    ses_id = ses_block.get("session_identifier") if isinstance(ses_block, dict) else None
    refs = _collect_references(payload)
    has_edge = any(
        r.get("relationship") == "conversation_belongs_to_session"
        and r.get("source_type") == "conversation"
        and (conv_id is None or r.get("source_id") == conv_id)
        and (ses_id is None or r.get("target_id") == ses_id)
        for r in refs
    )
    if not has_edge:
        out.append(
            Violation(
                SEVERITY_ERROR,
                "conversation_block",
                f"missing a conversation_belongs_to_session edge from "
                f"{conv_id or '<this conversation>'} to "
                f"{ses_id or '<the session>'} (in the conversation block's "
                f"inline references or the top-level references[]). Without "
                f"it the apply trips complete_session_requires_conversation.",
            )
        )
    return out


def check_decision_status(payload: dict) -> list[Violation]:
    """Check 4 (HARD): every DEC.status is in the decision-status enum.

    ``Final`` is explicitly rejected — it is the highest-frequency historical
    mistake (SES-067 precedent), and the DB CHECK accepts only
    {Active, Deleted, Superseded, Withdrawn}.
    """
    out: list[Violation] = []
    for dec in payload.get("decisions") or []:
        if not isinstance(dec, dict):
            continue
        ident = dec.get("identifier", "<unidentified decision>")
        status = dec.get("status")
        if status == "Final":
            out.append(
                Violation(
                    SEVERITY_ERROR,
                    "decision_status",
                    f"{ident} has status='Final', which fails apply. The DB "
                    f"CHECK accepts only {_VALID_DECISION_STATUSES}. Use "
                    f"'Active' for an in-force decision (SES-067 precedent — "
                    f"the highest-frequency status mistake).",
                )
            )
        elif status not in DECISION_STATUSES:
            out.append(
                Violation(
                    SEVERITY_ERROR,
                    "decision_status",
                    f"{ident} has status={status!r}, not in "
                    f"{_VALID_DECISION_STATUSES}.",
                )
            )
    return out


def check_decision_back_reference(payload: dict) -> list[Violation]:
    """Check 5 (HARD, post-PI-073): every DEC has a decided_in → CONVERSATION.

    Under PI-073 / DEC-314, decisions are decided_in a CONVERSATION (CNV-NNN),
    NOT the session. Every decision in ``decisions[]`` must have a matching
    ``decided_in`` reference (source=this DEC, target_type=conversation,
    target_id=the payload's CNV) in the references[] array (or the inline
    block references).
    """
    out: list[Violation] = []
    decisions = payload.get("decisions") or []
    if not decisions:
        return out

    conv_block = payload.get("conversation")
    conv_id = (
        conv_block.get("conversation_identifier")
        if isinstance(conv_block, dict)
        else None
    )
    refs = _collect_references(payload)

    for dec in decisions:
        if not isinstance(dec, dict):
            continue
        ident = dec.get("identifier")
        match = any(
            r.get("relationship") == "decided_in"
            and r.get("source_type") == "decision"
            and r.get("source_id") == ident
            and r.get("target_type") == "conversation"
            for r in refs
        )
        if not match:
            target_hint = conv_id or "<the payload's conversation>"
            out.append(
                Violation(
                    SEVERITY_ERROR,
                    "decision_back_reference",
                    f"{ident or '<unidentified decision>'} has no decided_in "
                    f"reference to a conversation. Post-PI-073, every "
                    f"decision is decided_in a CONVERSATION (e.g. "
                    f"{target_hint}), not the session. Add a references[] "
                    f"entry: source_type=decision, source_id={ident}, "
                    f"target_type=conversation, relationship=decided_in.",
                )
            )
    return out


def check_planning_item_type(payload: dict) -> list[Violation]:
    """Check 6 (HARD): every PI carries item_type == 'pending_work'.

    The CRMBUILDER engagement requires ``item_type: "pending_work"`` on every
    PI in a close-out payload; without it the apply 422s (SES-069 / PI-048).
    """
    out: list[Violation] = []
    for pi in payload.get("planning_items") or []:
        if not isinstance(pi, dict):
            continue
        ident = pi.get("identifier", "<unidentified PI>")
        item_type = pi.get("item_type")
        if item_type != "pending_work":
            out.append(
                Violation(
                    SEVERITY_ERROR,
                    "planning_item_type",
                    f"{ident} has item_type={item_type!r}; the CRMBUILDER "
                    f"target requires item_type='pending_work' on every PI "
                    f"in a close-out payload (SES-069 / PI-048 precedent — "
                    f"apply 422s without it).",
                )
            )
    return out


def check_work_ticket_file_path(payload: dict) -> list[Violation]:
    """Check 7 (HARD): every work_ticket has a non-empty work_ticket_file_path.

    Required for every WT regardless of work_ticket_kind, including 'other'
    (PI-025 backfill rejected six wt_kind='other' rows that omitted it). Use a
    placeholder like 'n/a' if there is genuinely no file — never omit the key.
    """
    out: list[Violation] = []
    for wt in payload.get("work_tickets") or []:
        if not isinstance(wt, dict):
            continue
        ident = wt.get("work_ticket_identifier", "<unidentified WT>")
        path = wt.get("work_ticket_file_path")
        if not isinstance(path, str) or not path.strip():
            out.append(
                Violation(
                    SEVERITY_ERROR,
                    "work_ticket_file_path",
                    f"{ident} has a missing/empty work_ticket_file_path. It is "
                    f"required for every work_ticket regardless of "
                    f"work_ticket_kind (PI-025 backfill precedent). Use a "
                    f"placeholder path like 'n/a' if there is no file.",
                )
            )
    return out


def check_reference_field_key(payload: dict) -> list[Violation]:
    """Check 8 (HARD): reference / resolves / addresses entries use the right keys.

    references[] entries use the API key ``relationship`` (NOT the
    DB-column-style ``relationship_kind`` — the SES-051 / SES-052 mismatch
    class that 422'd on apply). resolves_planning_items[] /
    addresses_planning_items[] entries use ``planning_item_identifier``.
    """
    out: list[Violation] = []

    for r in payload.get("references") or []:
        if not isinstance(r, dict):
            continue
        if "relationship" not in r and "relationship_kind" in r:
            out.append(
                Violation(
                    SEVERITY_ERROR,
                    "reference_field_key",
                    f"a references[] entry uses 'relationship_kind' (the DB "
                    f"column name) instead of 'relationship' (the API key). "
                    f"The apply POSTs to /references which expects "
                    f"'relationship' (SES-051 / SES-052 precedent). Entry: "
                    f"{json.dumps(r)[:200]}.",
                )
            )
        elif "relationship" not in r:
            out.append(
                Violation(
                    SEVERITY_ERROR,
                    "reference_field_key",
                    f"a references[] entry is missing the 'relationship' key. "
                    f"Entry: {json.dumps(r)[:200]}.",
                )
            )

    for section in ("resolves_planning_items", "addresses_planning_items"):
        for entry in payload.get(section) or []:
            if not isinstance(entry, dict):
                continue
            if "planning_item_identifier" not in entry:
                out.append(
                    Violation(
                        SEVERITY_ERROR,
                        "reference_field_key",
                        f"a {section}[] entry is missing the "
                        f"'planning_item_identifier' key. Entry: "
                        f"{json.dumps(entry)[:200]}.",
                    )
                )
    return out


def _check_one_exec_summary(
    value: object, where: str, out: list[Violation]
) -> None:
    """Apply the 200-800 length rule to one executive_summary value.

    Mirrors validate_optional_length: None / empty / whitespace-only passes
    (treated as absent); a present non-empty value must be 200-800 chars
    inclusive (length measured on the full string, not the trimmed one).
    """
    if value is None:
        return
    if not isinstance(value, str):
        out.append(
            Violation(
                SEVERITY_ERROR,
                "executive_summary_length",
                f"{where} executive_summary must be a string or null; "
                f"got {type(value).__name__}.",
            )
        )
        return
    if value.strip() == "":
        return
    n = len(value)
    if n < _EXEC_SUMMARY_MIN or n > _EXEC_SUMMARY_MAX:
        out.append(
            Violation(
                SEVERITY_ERROR,
                "executive_summary_length",
                f"{where} executive_summary must be "
                f"{_EXEC_SUMMARY_MIN}-{_EXEC_SUMMARY_MAX} characters "
                f"(got {n}). Mirrors PI-074's validate_optional_length.",
            )
        )


def check_executive_summary_length(payload: dict) -> list[Violation]:
    """Check 9 (HARD): any present executive_summary is 200-800 chars.

    Applies to the session block's ``session_executive_summary`` and to each
    planning_item's / decision's ``executive_summary``. Absent / null passes.
    """
    out: list[Violation] = []
    block = payload.get("session")
    if isinstance(block, dict):
        _check_one_exec_summary(
            block.get("session_executive_summary"),
            f"session {block.get('session_identifier', '')}".strip(),
            out,
        )
    for section, label in (("planning_items", "PI"), ("decisions", "DEC")):
        for rec in payload.get(section) or []:
            if not isinstance(rec, dict):
                continue
            ident = rec.get("identifier", f"<unidentified {label}>")
            _check_one_exec_summary(rec.get("executive_summary"), str(ident), out)
    return out


# ---------------------------------------------------------------------------
# Check 10: identifier-head conflicts (WARNING; needs the API)
# ---------------------------------------------------------------------------


def _default_head_fetcher(api_base: str) -> Callable[[str], str | None]:
    """Build a head-fetcher that reads ``GET {api_base}{endpoint}`` via urllib.

    Returns a callable mapping an endpoint path to the ``data.next`` string,
    or None on any failure (network, parse, missing field). Failures degrade
    to "no warning" — the head check is best-effort, never blocking.
    """

    def fetch(endpoint: str) -> str | None:
        url = f"{api_base}{endpoint}"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read())
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError):
            return None
        data = body.get("data") if isinstance(body, dict) else None
        nxt = data.get("next") if isinstance(data, dict) else None
        return nxt if isinstance(nxt, str) else None

    return fetch


def _collect_payload_identifiers(payload: dict) -> list[str]:
    """Gather every prefixed identifier the payload declares.

    Sessions (SES), conversations (CNV), decisions (DEC), planning items (PI),
    work tickets (WT). Commits are excluded — they have no per-payload
    sequential identifier (keyed by commit_sha).
    """
    idents: list[str] = []
    block = payload.get("session")
    if isinstance(block, dict):
        si = block.get("session_identifier") or block.get("identifier")
        if isinstance(si, str):
            idents.append(si)
    block = payload.get("conversation")
    if isinstance(block, dict):
        ci = block.get("conversation_identifier")
        if isinstance(ci, str):
            idents.append(ci)
    for dec in payload.get("decisions") or []:
        if isinstance(dec, dict) and isinstance(dec.get("identifier"), str):
            idents.append(dec["identifier"])
    for pi in payload.get("planning_items") or []:
        if isinstance(pi, dict) and isinstance(pi.get("identifier"), str):
            idents.append(pi["identifier"])
    for wt in payload.get("work_tickets") or []:
        if isinstance(wt, dict) and isinstance(
            wt.get("work_ticket_identifier"), str
        ):
            idents.append(wt["work_ticket_identifier"])
    return idents


def check_identifier_heads(
    payload: dict,
    *,
    api_base: str | None = None,
    head_fetcher: Callable[[str], str | None] | None = None,
) -> list[Violation]:
    """Check 10 (WARNING): identifiers at-or-below the live API head.

    For each prefixed identifier in the payload (SES/CNV/DEC/PI/WT), compare
    its number against the live API's current head for that record type. If
    the payload identifier is at-or-below the head, WARN — because a
    legitimate idempotent re-apply reuses identifiers that already exist (the
    head has advanced past them). A true collision is caught by the API's 409
    on apply, so this is a warning, NOT a hard reject — making it a reject
    would block every re-apply.

    Skipped entirely when ``api_base`` is None and no ``head_fetcher`` is
    supplied (offline mode). When the API is unreachable, individual head
    lookups degrade to no-warning rather than blocking.
    """
    if head_fetcher is None:
        if api_base is None:
            return []
        head_fetcher = _default_head_fetcher(api_base)

    # Cache head numbers per prefix so we hit each endpoint at most once.
    head_cache: dict[str, int | None] = {}

    def head_number(prefix: str) -> int | None:
        if prefix in head_cache:
            return head_cache[prefix]
        endpoint = _HEAD_ENDPOINTS.get(prefix)
        result: int | None = None
        if endpoint is not None:
            nxt = head_fetcher(endpoint)
            if isinstance(nxt, str):
                tail = nxt.rsplit("-", 1)[-1]
                if tail.isdigit():
                    result = int(tail)
        head_cache[prefix] = result
        return result

    out: list[Violation] = []
    for ident in _collect_payload_identifiers(payload):
        if "-" not in ident:
            continue
        prefix, _, tail = ident.rpartition("-")
        if not tail.isdigit() or prefix not in _HEAD_ENDPOINTS:
            continue
        head = head_number(prefix)
        if head is None:
            continue
        # next-identifier returns the NEXT free slot. An identifier whose
        # number is < head already exists (re-apply); == head would collide
        # with the next-to-be-assigned slot. Both warrant a (non-blocking)
        # heads-advanced warning.
        if int(tail) < head:
            out.append(
                Violation(
                    SEVERITY_WARNING,
                    "identifier_heads",
                    f"{ident} is at-or-below the live head ({prefix} head's "
                    f"next free slot is {prefix}-{head:03d}). This is expected "
                    f"for an idempotent re-apply (the record already exists); "
                    f"a genuine collision is caught by the API's 409 on apply.",
                )
            )
    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

# The hard-reject (shape) checks, in report order. Each is a plain function
# taking the payload and returning list[Violation]. Listing them here makes
# the rule set self-documenting and keeps the rules document and the
# validator synchronized — a rule added without a check here is a known gap.
_SHAPE_CHECKS: tuple[Callable[[dict], list[Violation]], ...] = (
    check_required_sections,
    check_session_block,
    check_conversation_block,
    check_decision_status,
    check_decision_back_reference,
    check_planning_item_type,
    check_work_ticket_file_path,
    check_reference_field_key,
    check_executive_summary_length,
)


def validate_payload(
    payload: dict,
    *,
    api_base: str | None = None,
    head_fetcher: Callable[[str], str | None] | None = None,
) -> list[Violation]:
    """Validate a close-out payload against the governance recording rules.

    Runs the nine pure-shape checks unconditionally (no API needed), then the
    identifier-head check only when an API is reachable (``api_base`` set, or a
    ``head_fetcher`` supplied for tests). Returns a flat list of
    :class:`Violation`. Callers decide what to do with each by severity:
    ``error`` blocks the apply, ``warning`` prints but proceeds.

    :param payload: the parsed close-out payload dict.
    :param api_base: base URL of the V2 API (e.g. ``http://127.0.0.1:8765``).
        When None and no ``head_fetcher`` is given, the head check (10) is
        skipped — offline mode for unit tests of the shape checks.
    :param head_fetcher: optional callable ``endpoint -> next-identifier
        string`` used in place of live urllib calls, for testability.
    :returns: list of violations (possibly empty).
    """
    violations: list[Violation] = []
    for check in _SHAPE_CHECKS:
        violations.extend(check(payload))
    violations.extend(
        check_identifier_heads(
            payload, api_base=api_base, head_fetcher=head_fetcher
        )
    )
    return violations


def format_report(violations: list[Violation]) -> str:
    """Render violations as a human-readable report grouped by severity.

    Errors first, then warnings; each line is
    ``[ERROR] <check_name>: <message>`` / ``[WARN] ...``. Returns a single
    string (no trailing newline) suitable for printing.
    """
    errors = [v for v in violations if v.severity == SEVERITY_ERROR]
    warnings = [v for v in violations if v.severity == SEVERITY_WARNING]
    lines: list[str] = []
    lines.append(
        f"Close-out payload validation: "
        f"{len(errors)} error(s), {len(warnings)} warning(s)."
    )
    for v in errors:
        lines.append(f"  [ERROR] {v.check_name}: {v.message}")
    for v in warnings:
        lines.append(f"  [WARN]  {v.check_name}: {v.message}")
    return "\n".join(lines)
