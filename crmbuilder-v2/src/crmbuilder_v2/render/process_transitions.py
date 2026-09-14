"""The transitions section of a rendered process document (PI-471, REQ-584).

A process's status lifecycle is stated once, as transition records, and this
module turns those records into the section of the process document that shows
them: one row per transition, in the process's order, giving the values moved
from, the value moved to, who may make the move and on what occasion, what must
be recorded before it, what happens automatically after it, what a person does
by hand afterwards, and the decisions that settled it.

The three-part split follows ``render/entity_prd.py``:
:func:`fetch_transition_inputs` does the reads (impure),
:func:`build_transitions_model` is pure and deterministic, and
:func:`render_transitions_markdown` is pure string assembly. The reads go
through the access layer rather than the design client, because the section
needs the names behind half a dozen record types — the persona who acts, the
fields a move requires, the view, automation, message template or process a
consequence names — and a document that printed bare identifiers would send its
reader to another record to learn what each row means.

Two deliberate differences from a hand-written table. Where a hand-written row
says "any pre-Active status", the section lists the values that rule actually
covers, because the store holds the membership explicitly (DEC-1065) and a
reader should see what is stored. And what a person does by hand has its own
column rather than being folded into the automatic consequences, because only
the automatic ones are what an application would build (DEC-1067).
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access.models import (
    Automation,
    Decision,
    Field,
    MessageTemplate,
    Persona,
    Process,
    Reference,
    Transition,
    View,
)
from crmbuilder_v2.access.repositories import transition as transition_repo

#: The column headings of the rendered section, in order.
COLUMNS = (
    "From",
    "To",
    "Who",
    "Must be recorded before the move",
    "Happens automatically after the move",
    "Done by hand afterwards",
    "Settling decisions",
)

#: What the From cell says when the move brings the record into being.
NO_RECORD = "(no record)"

_EMPTY = "—"


@dataclass
class TransitionInputs:
    """The records the section renders, and the names behind them."""

    process_identifier: str
    process_name: str
    status_field_names: dict[str, str] = dataclass_field(default_factory=dict)
    transitions: list[dict] = dataclass_field(default_factory=list)
    field_names: dict[str, str] = dataclass_field(default_factory=dict)
    persona_names: dict[str, str] = dataclass_field(default_factory=dict)
    consequence_labels: dict[str, str] = dataclass_field(default_factory=dict)
    settling_decisions: dict[str, list[tuple[str, str]]] = dataclass_field(
        default_factory=dict
    )


@dataclass(frozen=True)
class TransitionRow:
    """One rendered row — the seven cells of :data:`COLUMNS`."""

    from_cell: str
    to_cell: str
    who_cell: str
    before_cell: str
    after_cell: str
    by_hand_cell: str
    decisions_cell: str
    incomplete: bool

    def cells(self) -> tuple[str, ...]:
        return (
            self.from_cell,
            self.to_cell,
            self.who_cell,
            self.before_cell,
            self.after_cell,
            self.by_hand_cell,
            self.decisions_cell,
        )


@dataclass(frozen=True)
class TransitionsModel:
    """The section as data — the heading line, the rows, and the footnote."""

    process_identifier: str
    process_name: str
    status_field_label: str
    rows: list[TransitionRow]

    @property
    def incomplete_count(self) -> int:
        return sum(1 for row in self.rows if row.incomplete)


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def _name_map(session: Session, model, id_column: str, name_column: str) -> dict:
    rows = session.scalars(select(model)).all()
    return {
        getattr(row, id_column): getattr(row, name_column) for row in rows
    }


def _settling_decisions(
    session: Session, identifiers: list[str]
) -> dict[str, list[tuple[str, str]]]:
    """Return, per transition, the decisions recorded as being about it.

    A decision settles a transition through the generic ``is_about`` edge, the
    way it settles any other governed record.
    """
    if not identifiers:
        return {}
    edges = session.scalars(
        select(Reference).where(
            Reference.target_type == "transition",
            Reference.target_id.in_(identifiers),
            Reference.source_type == "decision",
            Reference.relationship_kind == "is_about",
        )
    ).all()
    titles = _name_map(session, Decision, "identifier", "title")
    out: dict[str, list[tuple[str, str]]] = {}
    for edge in edges:
        out.setdefault(edge.target_id, []).append(
            (edge.source_id, titles.get(edge.source_id, ""))
        )
    for pairs in out.values():
        pairs.sort()
    return out


def fetch_transition_inputs(
    session: Session, process_identifier: str
) -> TransitionInputs:
    """Read one process's transitions and every name the section needs."""
    process_row = session.scalar(
        select(Process).where(
            Process.process_identifier == process_identifier
        )
    )
    transitions = transition_repo.list_transitions(
        session, process=process_identifier
    )
    field_names = _name_map(session, Field, "field_identifier", "field_name")
    labels: dict[str, str] = {}
    for identifier, name in _name_map(
        session, View, "view_identifier", "view_name"
    ).items():
        labels[identifier] = f"the {name} view ({identifier})"
    for identifier, name in _name_map(
        session, Automation, "automation_identifier", "automation_name"
    ).items():
        labels[identifier] = f"the {name} routine ({identifier})"
    for identifier, name in _name_map(
        session,
        MessageTemplate,
        "message_template_identifier",
        "message_template_name",
    ).items():
        labels[identifier] = f"the {name} message ({identifier})"
    for identifier, name in _name_map(
        session, Process, "process_identifier", "process_name"
    ).items():
        labels[identifier] = f"hand-off to the {name} process ({identifier})"
    for row in session.scalars(select(Transition)).all():
        labels[row.transition_identifier] = (
            "the move to "
            f"{row.transition_to_value} ({row.transition_identifier})"
        )

    return TransitionInputs(
        process_identifier=process_identifier,
        process_name=(
            process_row.process_name if process_row is not None else ""
        ),
        transitions=transitions,
        field_names=field_names,
        persona_names=_name_map(
            session, Persona, "persona_identifier", "persona_name"
        ),
        consequence_labels=labels,
        settling_decisions=_settling_decisions(
            session, [t["transition_identifier"] for t in transitions]
        ),
    )


# ---------------------------------------------------------------------------
# Build (pure)
# ---------------------------------------------------------------------------


def _from_cell(row: dict) -> str:
    if row["transition_from_kind"] == "record_creation":
        return NO_RECORD
    return ", ".join(row["transition_from_values"])


def _who_cell(row: dict, persona_names: dict[str, str]) -> str:
    if row["transition_actor_kind"] == "system":
        who = "System"
    else:
        identifier = row["transition_actor_persona"]
        who = persona_names.get(identifier, identifier)
    occasion = row.get("transition_actor_occasion")
    return f"{who}, {occasion}" if occasion else who


def _before_cell(row: dict, field_names: dict[str, str]) -> str:
    parts = []
    required = [
        field_names.get(identifier, identifier)
        for identifier in row["transition_required_fields"]
    ]
    if required:
        parts.append(", ".join(required))
    condition = row.get("transition_precondition")
    if condition:
        parts.append(condition)
    return ". ".join(parts) if parts else "Nothing."


def _after_cell(row: dict, labels: dict[str, str]) -> tuple[str, bool]:
    parts = [
        labels.get(identifier, identifier)
        for identifier in row["transition_consequences"]
    ]
    words = row.get("transition_consequence_notes")
    incomplete = bool(words)
    if words:
        parts.append(f"{words} (no record for this yet)")
    return ("; ".join(parts) if parts else "None.", incomplete)


def _decisions_cell(pairs: list[tuple[str, str]]) -> str:
    if not pairs:
        return _EMPTY
    return "; ".join(
        f"{title} ({identifier})" if title else identifier
        for identifier, title in pairs
    )


def build_transitions_model(inputs: TransitionInputs) -> TransitionsModel:
    """Turn the read records into the rows the section renders."""
    rows: list[TransitionRow] = []
    status_fields: list[str] = []
    for record in inputs.transitions:
        field_identifier = record["transition_field"]
        label = inputs.field_names.get(field_identifier, field_identifier)
        if label not in status_fields:
            status_fields.append(label)
        after_cell, incomplete = _after_cell(record, inputs.consequence_labels)
        rows.append(
            TransitionRow(
                from_cell=_from_cell(record),
                to_cell=record["transition_to_value"],
                who_cell=_who_cell(record, inputs.persona_names),
                before_cell=_before_cell(record, inputs.field_names),
                after_cell=after_cell,
                by_hand_cell=record.get("transition_manual_follow_up")
                or _EMPTY,
                decisions_cell=_decisions_cell(
                    inputs.settling_decisions.get(
                        record["transition_identifier"], []
                    )
                ),
                incomplete=incomplete,
            )
        )
    return TransitionsModel(
        process_identifier=inputs.process_identifier,
        process_name=inputs.process_name,
        status_field_label=", ".join(status_fields),
        rows=rows,
    )


# ---------------------------------------------------------------------------
# Render (pure)
# ---------------------------------------------------------------------------


def _escape(cell: str) -> str:
    return cell.replace("|", "\\|").replace("\n", " ")


def render_transitions_markdown(
    model: TransitionsModel, *, heading: str = "## Status transitions"
) -> str:
    """Render the section as Markdown: a preamble, the table, and a footnote."""
    lines = [heading, ""]
    if not model.rows:
        lines.append(
            f"The {model.process_name} process has no transitions recorded."
        )
        return "\n".join(lines) + "\n"

    lines.append(
        f"One row per allowed move of {model.status_field_label} within the "
        f"{model.process_name} process, in the order the process holds them. "
        "Where a move is allowed from several values, every value is listed, "
        "because the rule is stored by its members rather than as a phrase."
    )
    lines.append("")
    lines.append("| " + " | ".join(COLUMNS) + " |")
    lines.append("|" + "---|" * len(COLUMNS))
    for row in model.rows:
        lines.append(
            "| " + " | ".join(_escape(cell) for cell in row.cells()) + " |"
        )
    lines.append("")
    if model.incomplete_count:
        lines.append(
            f"{model.incomplete_count} of these moves still describe an "
            "automatic action in words rather than naming a record for it. "
            "Until those records exist, a builder reading the description "
            "makes a choice the definition did not make."
        )
    else:
        lines.append(
            "Every automatic action above names a record; nothing is left to "
            "a builder's reading."
        )
    return "\n".join(lines) + "\n"


def render_process_transitions(
    session: Session, process_identifier: str, *, heading: str = "## Status transitions"
) -> str:
    """Read, build and render in one call — the section for one process."""
    inputs = fetch_transition_inputs(session, process_identifier)
    return render_transitions_markdown(
        build_transitions_model(inputs), heading=heading
    )
