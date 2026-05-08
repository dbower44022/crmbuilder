"""Shared form widgets for the decision create/edit dialogs.

Wired in slice G. Builds the eleven-field form per PRD §4.7 with
paired inline error labels under each input. The two dialogs differ
only in whether the identifier is editable and how Save is wired —
the form itself is identical.

Returns a dataclass of references to the widgets so the dialog can
read values, set inline errors, and clear errors on edit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.access.vocab import DECISION_STATUSES

_LONG_TEXT_MIN_HEIGHT = 80
_INLINE_ERROR_STYLE = "color: #B22222;"
_DEFAULT_STATUS = "Active"

# Client-side format validators. These run before the API call to catch
# common typos. They are permissive (do not validate calendar correctness
# of the date) — server-side validation remains the authoritative gate.
IDENTIFIER_RE = re.compile(r"^DEC-\d{3,}$")
DECISION_DATE_RE = re.compile(r"^\d{2}-\d{2}-\d{2}$")
SUPERSEDES_RE = IDENTIFIER_RE  # supersedes / superseded_by share the format

IDENTIFIER_HINT = "Identifier must be in the format DEC-NNN (e.g., DEC-018)."
DECISION_DATE_HINT = "Decision Date must be in the format MM-DD-YY (e.g., 05-09-26)."
SUPERSEDES_HINT = (
    "Must be in the format DEC-NNN (e.g., DEC-005), or empty to clear."
)

# Order of fields per PRD §4.7. Pairs of (api_key, label_text).
LONG_TEXT_FIELDS: tuple[tuple[str, str], ...] = (
    ("context", "Context"),
    ("decision", "Decision"),
    ("rationale", "Rationale"),
    ("alternatives_considered", "Alternatives Considered"),
    ("consequences", "Consequences"),
)


@dataclass
class DecisionFormWidgets:
    """Bag of widgets built by ``build_decision_form``."""

    identifier: QLineEdit
    title: QLineEdit
    decision_date: QLineEdit
    status: QComboBox
    context: QPlainTextEdit
    decision: QPlainTextEdit
    rationale: QPlainTextEdit
    alternatives_considered: QPlainTextEdit
    consequences: QPlainTextEdit
    supersedes: QLineEdit
    superseded_by: QLineEdit
    error_labels: dict[str, QLabel]

    def widget_for(self, field: str) -> QWidget | None:
        return getattr(self, field, None) if hasattr(self, field) else None

    def value_for(self, field: str) -> str:
        """Return the current value of a form field as a string.

        For ``status`` returns the current dropdown text. For
        ``QLineEdit`` and ``QPlainTextEdit`` widgets returns the text/
        plain-text content.
        """
        widget = self.widget_for(field)
        if widget is None:
            return ""
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, QLineEdit):
            return widget.text()
        if isinstance(widget, QPlainTextEdit):
            return widget.toPlainText()
        return ""

    def set_value(self, field: str, value: str) -> None:
        widget = self.widget_for(field)
        if widget is None:
            return
        if isinstance(widget, QComboBox):
            idx = widget.findText(value)
            if idx >= 0:
                widget.setCurrentIndex(idx)
            else:
                widget.setEditText(value)
            return
        if isinstance(widget, QLineEdit):
            widget.setText(value)
            return
        if isinstance(widget, QPlainTextEdit):
            widget.setPlainText(value)

    def show_error(self, field: str, message: str) -> None:
        label = self.error_labels.get(field)
        if label is None:
            return
        label.setText(message)
        label.setVisible(True)

    def clear_error(self, field: str) -> None:
        label = self.error_labels.get(field)
        if label is None:
            return
        label.setText("")
        label.setVisible(False)

    def clear_all_errors(self) -> None:
        for field in self.error_labels:
            self.clear_error(field)


def _make_inline_error() -> QLabel:
    label = QLabel("")
    label.setStyleSheet(_INLINE_ERROR_STYLE)
    label.setWordWrap(True)
    label.setVisible(False)
    return label


def _row_widget(input_widget: QWidget, error_label: QLabel) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    layout.addWidget(input_widget)
    layout.addWidget(error_label)
    return container


def build_decision_form(parent: QWidget) -> tuple[QFormLayout, DecisionFormWidgets]:
    """Build the eleven-field decision form. Returns (layout, widgets)."""
    form = QFormLayout()
    form.setLabelAlignment(form.labelAlignment())
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

    identifier = QLineEdit(parent)
    identifier.setPlaceholderText("DEC-NNN")

    title = QLineEdit(parent)

    decision_date = QLineEdit(parent)
    decision_date.setPlaceholderText("MM-DD-YY")

    status = QComboBox(parent)
    for value in sorted(DECISION_STATUSES):
        status.addItem(value)
    if _DEFAULT_STATUS in DECISION_STATUSES:
        idx = status.findText(_DEFAULT_STATUS)
        if idx >= 0:
            status.setCurrentIndex(idx)

    context = QPlainTextEdit(parent)
    context.setMinimumHeight(_LONG_TEXT_MIN_HEIGHT)

    decision = QPlainTextEdit(parent)
    decision.setMinimumHeight(_LONG_TEXT_MIN_HEIGHT)

    rationale = QPlainTextEdit(parent)
    rationale.setMinimumHeight(_LONG_TEXT_MIN_HEIGHT)

    alternatives_considered = QPlainTextEdit(parent)
    alternatives_considered.setMinimumHeight(_LONG_TEXT_MIN_HEIGHT)

    consequences = QPlainTextEdit(parent)
    consequences.setMinimumHeight(_LONG_TEXT_MIN_HEIGHT)

    supersedes = QLineEdit(parent)
    supersedes.setPlaceholderText("DEC-NNN or empty")

    superseded_by = QLineEdit(parent)
    superseded_by.setPlaceholderText("DEC-NNN or empty")

    error_labels = {
        "identifier": _make_inline_error(),
        "title": _make_inline_error(),
        "decision_date": _make_inline_error(),
        "status": _make_inline_error(),
        "context": _make_inline_error(),
        "decision": _make_inline_error(),
        "rationale": _make_inline_error(),
        "alternatives_considered": _make_inline_error(),
        "consequences": _make_inline_error(),
        "supersedes": _make_inline_error(),
        "superseded_by": _make_inline_error(),
    }

    form.addRow("Identifier", _row_widget(identifier, error_labels["identifier"]))
    form.addRow("Title", _row_widget(title, error_labels["title"]))
    form.addRow(
        "Decision Date", _row_widget(decision_date, error_labels["decision_date"])
    )
    form.addRow("Status", _row_widget(status, error_labels["status"]))
    form.addRow("Context", _row_widget(context, error_labels["context"]))
    form.addRow("Decision", _row_widget(decision, error_labels["decision"]))
    form.addRow("Rationale", _row_widget(rationale, error_labels["rationale"]))
    form.addRow(
        "Alternatives Considered",
        _row_widget(
            alternatives_considered, error_labels["alternatives_considered"]
        ),
    )
    form.addRow(
        "Consequences", _row_widget(consequences, error_labels["consequences"])
    )
    form.addRow("Supersedes", _row_widget(supersedes, error_labels["supersedes"]))
    form.addRow(
        "Superseded By",
        _row_widget(superseded_by, error_labels["superseded_by"]),
    )

    widgets = DecisionFormWidgets(
        identifier=identifier,
        title=title,
        decision_date=decision_date,
        status=status,
        context=context,
        decision=decision,
        rationale=rationale,
        alternatives_considered=alternatives_considered,
        consequences=consequences,
        supersedes=supersedes,
        superseded_by=superseded_by,
        error_labels=error_labels,
    )

    # Wire change-clears-error: when the user starts editing a field
    # whose inline error is showing, clear it so the visual reflects
    # the in-flight fix.
    def _bind_clear(field: str) -> None:
        widget = widgets.widget_for(field)
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(lambda _t, f=field: widgets.clear_error(f))
        elif isinstance(widget, QPlainTextEdit):
            widget.textChanged.connect(lambda f=field: widgets.clear_error(f))
        elif isinstance(widget, QComboBox):
            widget.currentTextChanged.connect(
                lambda _t, f=field: widgets.clear_error(f)
            )

    for fname in error_labels:
        _bind_clear(fname)

    return form, widgets
