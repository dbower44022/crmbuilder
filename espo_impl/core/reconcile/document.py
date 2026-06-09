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

import io
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

    # -- line / block geometry -------------------------------------------

    def _line_text(self, line_idx: int) -> str:
        """The full source of line ``line_idx`` (including its newline if any)."""
        start = self._line_starts[line_idx]
        if line_idx + 1 < len(self._line_starts):
            return self._text[start : self._line_starts[line_idx + 1]]
        return self._text[start:]

    def _indent_of(self, line_idx: int) -> int | None:
        """Leading-space count of a line, or ``None`` if blank/whitespace-only."""
        line = self._line_text(line_idx)
        stripped = line.lstrip(" ")
        if stripped in ("", "\n"):
            return None
        return len(line) - len(stripped)

    def _block_last_content_line(self, key_line: int, key_indent: int) -> int:
        """Last line (inclusive) belonging to a block whose key sits at
        ``key_indent`` on ``key_line``.

        The block's body is the following run of lines that are blank or indented
        deeper than the key; the body ends at the first line indented at or below
        the key (a sibling/dedent) or EOF. Trailing blank lines are excluded.
        """
        n = len(self._line_starts)
        last = key_line
        i = key_line + 1
        while i < n:
            indent = self._indent_of(i)
            if indent is None:  # blank: provisionally inside the block
                i += 1
                continue
            if indent <= key_indent:  # dedent -> block ended
                break
            last = i  # a non-blank deeper line belongs to the block
            i += 1
        return last

    def _marker_col_of_sequence(self, key_line: int) -> int:
        """Column of the ``-`` marker of the first item under a sequence key."""
        n = len(self._line_starts)
        i = key_line + 1
        while i < n:
            indent = self._indent_of(i)
            if indent is not None:
                return indent
            i += 1
        # Empty sequence (no items yet): indent one level under the key.
        return self._indent_of(key_line) or 0

    def _render_sequence_item(
        self, mapping: dict, marker_col: int, *, blank_line_before: bool
    ) -> str:
        """Render ``mapping`` as a block-sequence item indented at ``marker_col``.

        The mapping is emitted with ruamel (a fresh, comment-free block — there is
        nothing to preserve for new content) and each line is shifted right: the
        first key gets the ``- `` marker, the rest align under it. A leading blank
        line matches the common one-blank-between-items file style.
        """
        buf = io.StringIO()
        self._yaml.dump(dict(mapping), buf)
        lines = buf.getvalue().rstrip("\n").split("\n")
        pad = " " * marker_col
        out = []
        for idx, line in enumerate(lines):
            prefix = f"{pad}- " if idx == 0 else f"{pad}  "
            out.append(prefix + line if line else prefix.rstrip())
        block = "\n".join(out) + "\n"
        return ("\n" + block) if blank_line_before else block

    def insert_sequence_item(
        self, owner, seq_key: str, mapping: dict, *, blank_line_before: bool = True
    ) -> None:
        """Append ``mapping`` as a new item to the block sequence ``owner[seq_key]``.

        Splices the rendered item after the sequence's last content line; existing
        items, comments, and following siblings are untouched.
        """
        key_line, key_col = owner.lc.key(seq_key)
        marker_col = self._marker_col_of_sequence(key_line)
        item_text = self._render_sequence_item(
            mapping, marker_col, blank_line_before=blank_line_before
        )
        last = self._block_last_content_line(key_line, key_col)
        insert_at = (
            self._line_starts[last + 1]
            if last + 1 < len(self._line_starts)
            else len(self._text)
        )
        # Guarantee a newline boundary before the inserted block at EOF.
        if insert_at > 0 and self._text[insert_at - 1] != "\n":
            item_text = "\n" + item_text
        self._edits.append(_Edit(insert_at, insert_at, item_text))

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
