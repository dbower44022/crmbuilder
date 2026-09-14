"""The session-open and segment-advance operations (PI-488, Step 3 of the
phase-specific governance plan).

A session opens with one question — *What do you want to do today?* — and
the user's verbatim reply is the **opening answer** (TERM-060). The answer is
classified against the **catalogue of kinds of work** (TERM-058): process
records whose ``process_steps`` field carries the ordered **phase segments**
(TERM-059), each naming a lifecycle domain and a **phase profile** (TERM-057),
and whose ``process_triggers`` field carries the recognition phrases
(DEC-1060). Classification is deterministic phrase matching on the server;
no language model is called (DEC-1061). Below the confidence threshold the
operation returns one follow-up question, which the calling surface asks in
the user's words, and records the miss as a planning item so the catalogue
grows from use (REQ-572).

Every contract the two operations return is the segment's resolved profile
contract merged with the **cross-cutting** contract — the one named set of
rules that loads whatever the phase, held by the system-scope agent profile
whose area is ``cross-cutting`` (REQ-574). A session opened without an answer,
or without a confident match, receives the cross-cutting contract only and a
first line saying that no kind of work was chosen (REQ-571).

Requirements: REQ-569 (catalogue shape), REQ-570 (session-open), REQ-571
(no answer), REQ-572 (unrecognised answer), REQ-573 (segment-advance),
REQ-574 (cross-cutting set). Decisions: DEC-1060..1063.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from sqlalchemy.orm import Session as DbSession

from crmbuilder_v2.access.exceptions import (
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import (
    agent_profiles,
    planning_items,
    projects,
    registry_resolver,
    sessions,
)
from crmbuilder_v2.access.repositories import (
    domain as domain_repo,
)
from crmbuilder_v2.access.repositories import (
    process as process_repo,
)

#: The opening question every surface asks (plan Part 4).
OPENING_QUESTION = "What do you want to do today?"
#: Catalogue version written on every entry's steps block (plan Part 6).
CATALOGUE_VERSION = "0.1"
#: The reserved area of the system-scope profile that holds the cross-cutting
#: rules (REQ-574). Found by area, never by identifier, so a re-created profile
#: needs no code change.
CROSS_CUTTING_AREA = "cross-cutting"
#: Below this confidence the operation returns "no confident match" (DEC-1061).
MATCH_THRESHOLD = 0.6
#: Two entries this close in score are ambiguous — treated as no confident match.
AMBIGUITY_MARGIN = 0.15
#: The one follow-up question for an unrecognised answer (REQ-572). It never
#: asks for a phase or a role.
FOLLOW_UP_QUESTION = (
    "I could not match that to a kind of work I know. In one sentence, what "
    "would you like to have changed, built, fixed or answered by the end of "
    "this session?"
)
NO_KIND_OF_WORK_LINE = (
    "No kind of work was chosen for this session; only the cross-cutting rules "
    "are loaded."
)

# REQ-595 / PI-500 (DEC-1080): when an opening loads a kind of work, the rules
# returned tell the model to begin its first reply with the confirmation line,
# word for word, so the user sees what the session understood on every surface
# that opens a session — Claude Code, the connector, the desktop. The line is
# carried inside the instruction, so a surface that shows the model only the
# rules still has the exact words. An opening with no kind of work carries no
# such instruction: there is no classification for the user to check.
FIRST_REPLY_INSTRUCTION = (
    "Begin your first reply to the user with this confirmation line, word for "
    "word, on its own line, so they can correct the kind of work if it is "
    "wrong: \"{line}\""
)


def first_reply_instruction(confirmation_line: str | None) -> str | None:
    """The instruction to restate the confirmation line, or ``None`` without one."""
    if not confirmation_line:
        return None
    return FIRST_REPLY_INSTRUCTION.format(line=confirmation_line)


def _with_first_reply_instruction(contract: dict, confirmation_line: str | None) -> dict:
    """Return the contract carrying the restatement instruction (REQ-595).

    The instruction is placed both as its own key, for a surface that reads the
    contract as data, and at the head of the system prompt, for one that hands
    the model the prompt text alone.
    """
    instruction = first_reply_instruction(confirmation_line)
    if instruction is None:
        return contract
    out = dict(contract)
    out["first_reply_instruction"] = instruction
    prompt = out.get("system_prompt") or ""
    out["system_prompt"] = f"{instruction}\n\n{prompt}" if prompt else instruction
    return out
#: Catalogue entries offered as examples with the opening question (three or
#: four, plan Part 4), by entry name; the first four that exist are used.
EXAMPLE_NAMES = (
    "Define new business processes",
    "Add or change a field or screen in an existing application",
    "Upgrade the platform to the latest version",
    "Ask a question about the system or its records",
)
SEGMENT_STATUSES = frozenset({"active", "pending"})
_SEGMENT_KEYS = ("position", "domain", "profile", "area", "label", "status")
_STOPWORDS = frozenset(
    "a an the to of in on for with and or i we my our you your it its is are "
    "be want need would like please let us me some this that these those".split()
)
_WORD_RE = re.compile(r"[a-z0-9]+")


# --- catalogue ---------------------------------------------------------------


def _tokens(text: str) -> list[str]:
    return [w for w in _WORD_RE.findall((text or "").lower()) if w not in _STOPWORDS]


def parse_catalogue_entry(record: dict) -> dict | None:
    """The catalogue view of a process record, or ``None`` when the record is
    not a catalogue entry (its steps field is not a phase-segment block)."""
    raw_steps = record.get("process_steps")
    if not raw_steps:
        return None
    try:
        block = json.loads(raw_steps)
    except (TypeError, ValueError):
        return None
    if not isinstance(block, dict) or "phase_segments" not in block:
        return None
    segments = block.get("phase_segments")
    if not isinstance(segments, list):
        return None
    phrases: list[str] = []
    raw_triggers = record.get("process_triggers")
    if raw_triggers:
        try:
            loaded = json.loads(raw_triggers)
            if isinstance(loaded, list):
                phrases = [str(p) for p in loaded if str(p).strip()]
        except (TypeError, ValueError):
            phrases = [p.strip() for p in str(raw_triggers).splitlines() if p.strip()]
    return {
        "process_identifier": record["process_identifier"],
        "name": record["process_name"],
        "purpose": record.get("process_purpose"),
        "domain": record["process_domain_identifier"],
        "catalogue_version": block.get("catalogue_version"),
        "segments": [
            {k: seg.get(k) for k in _SEGMENT_KEYS} for seg in segments if isinstance(seg, dict)
        ],
        "trigger_phrases": phrases,
    }


def list_catalogue(session: DbSession) -> list[dict]:
    """Every kind of work in the store, in identifier order (REQ-569)."""
    entries = []
    for record in process_repo.list_processes(session):
        entry = parse_catalogue_entry(record)
        if entry is not None:
            entries.append(entry)
    return entries


def catalogue_steps_block(segments: list[dict]) -> str:
    """Render segments as the steps-field block a catalogue entry carries."""
    return json.dumps(
        {"catalogue_version": CATALOGUE_VERSION, "phase_segments": segments},
        indent=2,
    )


def validate_segments(session: DbSession, segments: list[dict]) -> list[str]:
    """Problems with a segment list, as plain strings (empty when valid)."""
    problems = []
    for i, seg in enumerate(segments, start=1):
        if seg.get("status") not in SEGMENT_STATUSES:
            problems.append(f"segment {i}: status must be active or pending")
        if domain_repo.get_domain(session, str(seg.get("domain") or "")) is None:
            problems.append(f"segment {i}: domain {seg.get('domain')!r} does not exist")
        if seg.get("status") == "active":
            profile = seg.get("profile")
            try:
                rec = agent_profiles.get(session, str(profile or ""))
            except NotFoundError:
                rec = None
            if rec is None or rec.get("status") != "active":
                problems.append(f"segment {i}: profile {profile!r} is not an active agent profile")
        elif not seg.get("area"):
            problems.append(f"segment {i}: a pending segment names the planned profile area")
    return problems


# --- classification (DEC-1061) ------------------------------------------------


def _phrase_score(answer_tokens: list[str], answer_text: str, phrase: str) -> float:
    phrase_norm = " ".join(_WORD_RE.findall(phrase.lower()))
    if phrase_norm and phrase_norm in answer_text:
        return 1.0
    ptoks = _tokens(phrase)
    if not ptoks:
        return 0.0
    aset = set(answer_tokens)
    hit = sum(1 for t in ptoks if t in aset)
    return hit / len(ptoks)


def classify(answer: str, entries: list[dict]) -> dict:
    """Score ``answer`` against every entry's trigger phrases.

    Returns ``{"entry": entry | None, "confidence": float, "ranked": [...]}``.
    ``entry`` is the best match only when its score clears the threshold and
    beats the runner-up by the ambiguity margin; otherwise ``None`` (no
    confident match). Deterministic: the same answer always ranks the same.
    """
    answer_text = " ".join(_WORD_RE.findall((answer or "").lower()))
    answer_tokens = _tokens(answer)
    ranked = []
    for entry in entries:
        best = 0.0
        for phrase in entry.get("trigger_phrases") or []:
            best = max(best, _phrase_score(answer_tokens, answer_text, phrase))
        ranked.append((round(best, 4), entry["process_identifier"], entry))
    ranked.sort(key=lambda t: (-t[0], t[1]))
    if not ranked or not answer_tokens:
        return {"entry": None, "confidence": 0.0, "ranked": []}
    top_score = ranked[0][0]
    second = ranked[1][0] if len(ranked) > 1 else 0.0
    confident = top_score >= MATCH_THRESHOLD and (
        second < MATCH_THRESHOLD or top_score - second >= AMBIGUITY_MARGIN
    )
    return {
        "entry": ranked[0][2] if confident else None,
        "confidence": top_score,
        "ranked": [
            {"process_identifier": pid, "name": e["name"], "score": s}
            for s, pid, e in ranked[:5]
        ],
    }


# --- contracts ----------------------------------------------------------------


def _empty_contract() -> dict:
    return {
        "profile_id": None,
        "area": None,
        "tier": None,
        "scope": None,
        "engagement_id": None,
        "system_prompt": "",
        "tools": [],
        "advisory_rules": [],
        "enforced_ruleset": [],
        "active_learnings": [],
        "version_stamp": "",
    }


def cross_cutting_profile(session: DbSession) -> dict | None:
    """The active system-scope profile whose area is ``cross-cutting``."""
    rows = agent_profiles.list_all(
        session, area=CROSS_CUTTING_AREA, status="active", scope="system"
    )
    return rows[0] if rows else None


def cross_cutting_contract(session: DbSession, engagement_id: str | None) -> dict:
    """The cross-cutting contract (REQ-574); an empty contract when no
    cross-cutting profile exists, so a session is never blocked."""
    profile = cross_cutting_profile(session)
    if profile is None:
        contract = _empty_contract()
        contract["engagement_id"] = engagement_id
        contract["missing_cross_cutting_profile"] = True
        return contract
    return registry_resolver.resolve_contract(
        session, profile["identifier"], engagement_id=engagement_id
    )


def _merge_unique(first: list[dict], second: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out = []
    for item in list(first) + list(second):
        key = item.get("identifier") or json.dumps(item, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def merge_contracts(segment_contract: dict | None, cross: dict) -> dict:
    """The segment's contract with the cross-cutting rules merged in.

    Rules, tools and learnings are unioned by identifier (the segment's first);
    the system prompt is the segment's followed by the cross-cutting text. With
    no segment contract the result is the cross-cutting contract itself.
    """
    if segment_contract is None:
        merged = dict(cross)
        merged["cross_cutting_profile_id"] = cross.get("profile_id")
        merged["segment_profile_id"] = None
        return merged
    merged = dict(segment_contract)
    merged["segment_profile_id"] = segment_contract.get("profile_id")
    merged["cross_cutting_profile_id"] = cross.get("profile_id")
    for key in ("advisory_rules", "enforced_ruleset", "tools", "active_learnings"):
        merged[key] = _merge_unique(segment_contract.get(key) or [], cross.get(key) or [])
    parts = [segment_contract.get("system_prompt") or ""]
    if cross.get("system_prompt"):
        parts.append("CROSS-CUTTING RULES — these apply in every phase segment.\n\n" + cross["system_prompt"])
    merged["system_prompt"] = "\n\n".join(p for p in parts if p)
    merged["version_stamp"] = f"{segment_contract.get('version_stamp', '')}+{cross.get('version_stamp', '')}"
    return merged


def _segment_contract(session: DbSession, segment: dict, engagement_id: str | None) -> tuple[dict | None, str | None]:
    """``(contract, note)`` for entering a segment: the profile's contract when
    the segment is active, else ``None`` and a line saying the profile is pending."""
    if segment.get("status") == "active" and segment.get("profile"):
        try:
            return registry_resolver.resolve_contract(
                session, segment["profile"], engagement_id=engagement_id
            ), None
        except NotFoundError:
            pass
    label = segment.get("label") or segment.get("area") or "this phase"
    return None, (
        f"The {label} profile is not yet available, so only the cross-cutting "
        "rules are loaded for this segment."
    )


# --- the opening (no write) ---------------------------------------------------


def preview(answer: str, entries: list[dict]) -> dict:
    """What the session-open operation would say back for ``answer``, without
    a write: the kind of work, the confidence, the confirmation line or the
    follow-up question. Lets a surface show the line before it creates the
    session (REQ-576) while the server still does every classification."""
    answer = " ".join((answer or "").split())
    result = classify(answer, entries) if answer else {"entry": None, "confidence": 0.0, "ranked": []}
    entry = result["entry"]
    if entry is not None:
        line = confirmation_line_for(entry)
        return {
            "opening_answer": answer,
            "kind_of_work": entry["process_identifier"],
            "kind_of_work_name": entry["name"],
            "confidence": result["confidence"],
            "confirmation_line": line,
            "first_line": line,
            "follow_up_question": None,
            "segments": entry["segments"],
        }
    return {
        "opening_answer": answer,
        "kind_of_work": None,
        "kind_of_work_name": None,
        "confidence": result["confidence"],
        "confirmation_line": None,
        "first_line": NO_KIND_OF_WORK_LINE if not answer else f"{NO_KIND_OF_WORK_LINE} {FOLLOW_UP_QUESTION}",
        "follow_up_question": FOLLOW_UP_QUESTION if answer else None,
        "segments": [],
    }


def opening(session: DbSession, engagement_id: str | None, *, answer: str | None = None) -> dict:
    """The opening question, its examples, the catalogue and the cross-cutting
    contract — everything a surface needs before the user answers. With
    ``answer`` the result also carries ``preview``: what the operation would
    say back, without a write."""
    entries = list_catalogue(session)
    by_name = {e["name"]: e for e in entries}
    examples = [n for n in EXAMPLE_NAMES if n in by_name][:4]
    if len(examples) < 3:
        examples = [e["name"] for e in entries[:4]]
    return {
        "question": OPENING_QUESTION,
        "examples": examples,
        "catalogue": [
            {
                "process_identifier": e["process_identifier"],
                "name": e["name"],
                "domain": e["domain"],
                "segments": e["segments"],
            }
            for e in entries
        ],
        "cross_cutting": cross_cutting_contract(session, engagement_id),
        "preview": preview(answer, entries) if answer is not None else None,
    }


# --- the session-open operation (REQ-570..572) --------------------------------


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _default_project(session: DbSession) -> str:
    """The project that holds a session opened without a named project: the
    latest project in flight, else the latest planned one."""
    for status in ("in_flight", "planned"):
        rows = projects.list_projects(session, status=status)
        if rows:
            return rows[-1]["project_identifier"]
    raise UnprocessableError(
        [
            FieldError(
                "project_identifier",
                "no_project",
                "no project in flight or planned to hold the session; pass "
                "project_identifier",
            )
        ]
    )


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text


def confirmation_line_for(entry: dict) -> str:
    """The one-sentence confirmation in the user's own terms (plan Part 4)."""
    name = _lower_first(entry["name"])
    segments = entry.get("segments") or []
    if not segments:
        return (
            f"It sounds like you want to {name}; no phase profile applies, so only "
            "the cross-cutting rules are loaded."
        )
    first = segments[0]
    label = first.get("label") or first.get("area") or "the first phase"
    if first.get("status") == "active":
        return f"It sounds like you want to {name}; I will start with the {label}."
    return (
        f"It sounds like you want to {name}; I will start with the {label}, whose "
        "profile is not yet available, so only the cross-cutting rules load for now."
    )


def _executive_summary(answer: str, entry: dict | None, line: str) -> str:
    if entry is not None:
        text = (
            f"A session opened with the answer \"{answer}\", classified as the kind of "
            f"work \"{entry['name']}\". {line} The session record carries the answer "
            "as given, the kind of work, the confirmation line and the phase "
            "segments run, each with the profile it loaded and the moments it was "
            "entered and left, so the work done here can be read back later."
        )
    elif answer:
        text = (
            f"A session opened with the answer \"{answer}\", which matched no kind of "
            "work in the catalogue with confidence. Only the cross-cutting rules were "
            "loaded and the miss was recorded as a planning item so the catalogue "
            "grows from real use. The session record carries the answer as given "
            "and no kind of work or phase segments."
        )
    else:
        text = (
            "A session opened without an opening answer — a scheduled run, a resumed "
            "session or a hook that could not ask — so only the cross-cutting rules "
            "were loaded and the first line said so. The session record carries an "
            "empty answer, no kind of work and no phase segments, which is the "
            "visible fallback the plan requires instead of a silent guess at a phase."
        )
    return text[:800]


def _record_miss(session: DbSession, answer: str, session_identifier: str) -> dict:
    """The planning item that records an unrecognised opening answer (REQ-572)."""
    short = " ".join(answer.split())[:120]
    return planning_items.create(
        session,
        title=f"Catalogue miss: {short}",
        item_type="pending_work",
        status="Draft",
        description=(
            f"The opening answer \"{answer}\" given in session {session_identifier} "
            "matched no kind of work in the catalogue with confidence. Decide whether "
            "an existing catalogue entry needs a new trigger phrase or a new kind of "
            "work is needed, then update the process record."
        ),
        executive_summary=(
            f"A session opened with the answer \"{short}\" and the catalogue of kinds "
            "of work did not recognise it. This item asks for the catalogue to grow: "
            "either an existing entry gains the phrase that would have matched, or a "
            "new kind of work is written as a process record with its phase segments "
            "and trigger phrases. Until then the same answer will keep loading only "
            "the cross-cutting rules and asking its follow-up question."
        )[:800],
        execution_mode="interactive",
    )


def open_session(
    session: DbSession,
    *,
    engagement_id: str | None,
    opening_answer: str | None,
    medium: str = "claude_code",
    project_identifier: str | None = None,
    title: str | None = None,
    participants: list | None = None,
    medium_metadata: dict | None = None,
    description: str | None = None,
    executive_summary: str | None = None,
    notes: str | None = None,
) -> dict:
    """Classify the opening answer, create the session record and return the
    first segment's contract merged with the cross-cutting rules.

    ``title``, ``description``, ``executive_summary`` and ``notes`` are
    generated from the answer when not supplied; a surface with a form (the
    desktop dialog) passes what the user typed.

    Returns ``{session, kind_of_work, confidence, ranked, confirmation_line,
    first_line, follow_up_question, segment, contract, planning_item}``.
    """
    answer = " ".join((opening_answer or "").split())
    entries = list_catalogue(session)
    result = classify(answer, entries) if answer else {"entry": None, "confidence": 0.0, "ranked": []}
    entry = result["entry"]
    cross = cross_cutting_contract(session, engagement_id)

    segments: list[dict] = []
    segment_contract: dict | None = None
    note: str | None = None
    if entry is not None:
        for i, seg in enumerate(entry["segments"], start=1):
            segments.append({**seg, "position": i, "entered_at": None, "left_at": None})
        confirmation = confirmation_line_for(entry)
        if segments:
            segments[0]["entered_at"] = _now()
            segment_contract, note = _segment_contract(session, segments[0], engagement_id)
        first_line = confirmation if note is None else f"{confirmation} {note}"
        follow_up = None
    else:
        confirmation = None
        follow_up = FOLLOW_UP_QUESTION if answer else None
        first_line = NO_KIND_OF_WORK_LINE if not answer else (
            f"{NO_KIND_OF_WORK_LINE} {FOLLOW_UP_QUESTION}"
        )

    project = project_identifier or _default_project(session)
    identifier = sessions.next_session_identifier(session)
    # The identifier keeps the title unique when several sessions open at once.
    session_title = title or (
        f"{identifier} — {answer[:70] or 'opened without an opening answer'}"
    )
    metadata = dict(medium_metadata or {})
    metadata["opened_by_operation"] = "session-open"
    if result.get("ranked"):
        metadata["classification"] = {
            "confidence": result["confidence"],
            "ranked": result["ranked"][:3],
        }
    record = sessions.create_session(
        session,
        identifier=identifier,
        title=session_title,
        description=description or (
            f"Opened through the session-open operation with the opening answer "
            f"\"{answer}\"." if answer else
            "Opened through the session-open operation without an opening answer."
        ),
        medium=medium,
        status="in_flight",
        notes=notes,
        participants=participants,
        medium_metadata=metadata,
        executive_summary=executive_summary or _executive_summary(answer, entry, confirmation or first_line),
        opening_answer=answer or None,
        kind_of_work=entry["process_identifier"] if entry else None,
        confirmation_line=confirmation,
        phase_segments=segments,
        references=[
            {
                "source_type": "session",
                "source_id": identifier,
                "target_type": "project",
                "target_id": project,
                "relationship": "session_belongs_to_project",
            }
        ],
    )

    planning_item = None
    if entry is None and answer:
        planning_item = _record_miss(session, answer, record["session_identifier"])
        metadata["catalogue_miss_planning_item"] = planning_item["identifier"]
        record = sessions.patch_session(
            session, record["session_identifier"], medium_metadata=metadata
        )

    return {
        "session": record,
        "kind_of_work": entry["process_identifier"] if entry else None,
        "kind_of_work_name": entry["name"] if entry else None,
        "confidence": result["confidence"],
        "ranked": result.get("ranked", []),
        "confirmation_line": confirmation,
        "first_line": first_line,
        "follow_up_question": follow_up,
        "segment": segments[0] if segments else None,
        "contract": _with_first_reply_instruction(
            merge_contracts(segment_contract, cross), confirmation
        ),
        "planning_item": planning_item,
    }


# --- the segment-advance operation (REQ-573) ----------------------------------


def advance_segment(
    session: DbSession, identifier: str, *, engagement_id: str | None
) -> dict:
    """Close the current phase segment, open the next, return its contract.

    After the last segment the session's segments are complete: the result
    carries ``completed: True`` and no contract.
    """
    record = sessions.get_session(session, identifier)
    if record is None:
        raise NotFoundError("session", identifier)
    segments = [dict(s) for s in (record.get("session_phase_segments") or [])]
    if not segments:
        raise UnprocessableError(
            [
                FieldError(
                    "session_phase_segments",
                    "no_segments",
                    "the session has no phase segments to advance",
                )
            ]
        )
    now = _now()
    current = next((s for s in segments if s.get("entered_at") and not s.get("left_at")), None)
    if current is None:
        if all(s.get("left_at") for s in segments):
            return {
                "session": record,
                "completed": True,
                "segment": None,
                "contract": None,
                "first_line": "Every phase segment of this session is complete.",
            }
        # Nothing entered yet: enter the first segment.
        nxt = segments[0]
    else:
        current["left_at"] = now
        idx = segments.index(current)
        nxt = segments[idx + 1] if idx + 1 < len(segments) else None

    if nxt is None:
        updated = sessions.patch_session(session, identifier, phase_segments=segments)
        return {
            "session": updated,
            "completed": True,
            "segment": None,
            "contract": None,
            "first_line": "Every phase segment of this session is complete.",
        }

    nxt["entered_at"] = now
    updated = sessions.patch_session(session, identifier, phase_segments=segments)
    segment_contract, note = _segment_contract(session, nxt, engagement_id)
    cross = cross_cutting_contract(session, engagement_id)
    label = nxt.get("label") or nxt.get("area") or "the next phase"
    line = f"Entering the {label} segment." if note is None else f"Entering the {label} segment. {note}"
    return {
        "session": updated,
        "completed": False,
        "segment": nxt,
        "contract": merge_contracts(segment_contract, cross),
        "first_line": line,
    }
