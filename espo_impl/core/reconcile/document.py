"""Position-aware, comment-preserving YAML editing.

:class:`YamlDocument` loads a program file with ruamel purely to obtain the
line/column of each node, then applies edits by splicing replacement text into
the *original* source string. The document is never re-serialized whole, so any
content we did not explicitly edit — comments, key order, quote styles, and
hand-authored column alignment inside inline flow maps — survives byte-for-byte.

Phase 1 supports replacing a single-line scalar value (``set_scalar``), which
covers the common field-property drift case (label, required, default, ...).
Multi-line scalars (folded/literal blocks), key insertion, and node insertion
are deferred to later phases.
"""
from __future__ import annotations

from dataclasses import dataclass

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import (
    DoubleQuotedScalarString,
    SingleQuotedScalarString,
)


@dataclass
class _Edit:
    """A pending byte-range replacement in the source text."""

    start: int
    end: int
    new_text: str


class YamlDocument:
    """A program YAML file opened for surgical edits.

    :param text: the file's full source text.
    """

    def __init__(self, text: str) -> None:
        self._text = text
        self._line_starts = self._compute_line_starts(text)
        yaml = YAML()  # round-trip mode: tracks line/col and preserves structure
        yaml.preserve_quotes = True
        self._yaml = yaml
        #: The loaded ruamel document (CommentedMap). Navigate this to find the
        #: node to edit, then pass it to :meth:`set_scalar`.
        self.data = yaml.load(text)
        self._edits: list[_Edit] = []

    # -- position helpers -------------------------------------------------

    @staticmethod
    def _compute_line_starts(text: str) -> list[int]:
        """Absolute offset of the first character of each line."""
        starts = [0]
        for i, ch in enumerate(text):
            if ch == "\n":
                starts.append(i + 1)
        return starts

    def _offset(self, line: int, col: int) -> int:
        """Absolute offset for a 0-based (line, col) position."""
        return self._line_starts[line] + col

    # -- literal rendering ------------------------------------------------

    @staticmethod
    def _render_literal(value, *, double_quoted: bool, single_quoted: bool) -> str:
        """Render ``value`` as the YAML source literal it should occupy.

        Quote style is explicit so a replacement inherits the original token's
        style. Booleans and ``None`` render in YAML's lowercase form to match
        how the files are authored.
        """
        if double_quoted:
            return '"' + str(value) + '"'
        if single_quoted:
            return "'" + str(value).replace("'", "''") + "'"
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        return str(value)

    # -- editing ----------------------------------------------------------

    def set_scalar(self, owner, key, new_value, *, quote: str | None = "keep") -> None:
        """Replace the scalar value of ``owner[key]`` in place.

        :param owner: the ruamel ``CommentedMap`` that holds ``key``.
        :param key: the mapping key whose value is being replaced.
        :param new_value: the new Python value (str/bool/int/None).
        :param quote: ``"keep"`` (default) inherits the existing quote style;
            ``'"'``/``"'"`` force double/single quoting; ``None`` forces plain.

        Only the value token's exact source span is replaced, so any trailing
        comment and the line's leading alignment are preserved. Raises
        :class:`ValueError` if the located token does not match the parsed value
        (e.g. an unsupported multi-line or escaped scalar) — failing loud rather
        than corrupting the file.
        """
        line, col = owner.lc.value(key)
        old = owner[key]
        old_dq = isinstance(old, DoubleQuotedScalarString)
        old_sq = isinstance(old, SingleQuotedScalarString)
        old_literal = self._render_literal(
            old, double_quoted=old_dq, single_quoted=old_sq
        )

        start = self._offset(line, col)
        found = self._text[start : start + len(old_literal)]
        if found != old_literal:
            raise ValueError(
                f"value token mismatch at line {line + 1}, col {col + 1}: "
                f"expected {old_literal!r} but source has {found!r}. "
                "Multi-line or escaped scalars are not yet supported."
            )

        if quote == "keep":
            new_dq, new_sq = old_dq, old_sq
        else:
            new_dq, new_sq = (quote == '"'), (quote == "'")
        new_literal = self._render_literal(
            new_value, double_quoted=new_dq, single_quoted=new_sq
        )
        self._edits.append(_Edit(start, start + len(old_literal), new_literal))

    @property
    def dirty(self) -> bool:
        """Whether any edits are pending."""
        return bool(self._edits)

    def render(self) -> str:
        """Return the edited source text. Idempotent; does not mutate state."""
        if not self._edits:
            return self._text
        # Apply highest-offset edits first so earlier offsets stay valid.
        edits = sorted(self._edits, key=lambda e: e.start, reverse=True)
        text = self._text
        prev_start: int | None = None
        for edit in edits:
            if prev_start is not None and edit.end > prev_start:
                raise ValueError("overlapping edits are not supported")
            text = text[: edit.start] + edit.new_text + text[edit.end :]
            prev_start = edit.start
        return text
