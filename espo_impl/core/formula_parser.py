"""Recursive-descent parser for arithmetic expressions in formula blocks.

Parses expressions like ``fieldA + fieldB * 2`` into an AST of
:class:`NumberLiteral`, :class:`FieldRef`, and :class:`BinaryOp` nodes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# AST nodes
# ---------------------------------------------------------------------------

@dataclass
class NumberLiteral:
    """A numeric constant (int or float)."""

    value: int | float


@dataclass
class FieldRef:
    """A reference to a field on the entity."""

    name: str


@dataclass
class BinaryOp:
    """A binary arithmetic operation."""

    left: ArithNode
    op: str  # '+', '-', '*', '/'
    right: ArithNode


ArithNode = NumberLiteral | FieldRef | BinaryOp


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

# Token types
_TOKEN_NUMBER = "NUMBER"
_TOKEN_FIELD = "FIELD"
_TOKEN_OP = "OP"
_TOKEN_LPAREN = "LPAREN"
_TOKEN_RPAREN = "RPAREN"

_TOKEN_PATTERN = re.compile(
    r"""
    \s*                          # skip leading whitespace
    (?:
        (\d+(?:\.\d+)?)          # group 1: numeric literal (int or float)
      | ([a-zA-Z_][a-zA-Z0-9_]*) # group 2: field name
      | ([+\-*/])               # group 3: operator
      | (\()                    # group 4: left paren
      | (\))                    # group 5: right paren
    )
    """,
    re.VERBOSE,
)


def _tokenize(expression: str) -> list[tuple[str, str, int]]:
    """Tokenize an arithmetic expression.

    :param expression: Raw expression string.
    :returns: List of (token_type, value, position) tuples.
    :raises ValueError: On unexpected characters.
    """
    tokens: list[tuple[str, str, int]] = []
    pos = 0
    while pos < len(expression):
        # Skip whitespace
        while pos < len(expression) and expression[pos].isspace():
            pos += 1
        if pos >= len(expression):
            break

        m = _TOKEN_PATTERN.match(expression, pos)
        if not m or m.start() != pos:
            raise ValueError(
                f"Unexpected character '{expression[pos]}' at position {pos}"
            )

        if m.group(1) is not None:
            tokens.append((_TOKEN_NUMBER, m.group(1), pos))
        elif m.group(2) is not None:
            tokens.append((_TOKEN_FIELD, m.group(2), pos))
        elif m.group(3) is not None:
            tokens.append((_TOKEN_OP, m.group(3), pos))
        elif m.group(4) is not None:
            tokens.append((_TOKEN_LPAREN, "(", pos))
        elif m.group(5) is not None:
            tokens.append((_TOKEN_RPAREN, ")", pos))

        pos = m.end()

    return tokens


# ---------------------------------------------------------------------------
# Parser — recursive descent
# Grammar:
#   expr   → term (('+' | '-') term)*
#   term   → factor (('*' | '/') factor)*
#   factor → '(' expr ')' | NUMBER | FIELD_REF
# ---------------------------------------------------------------------------

class _Parser:
    """Internal recursive-descent parser state."""

    def __init__(self, tokens: list[tuple[str, str, int]], expression: str) -> None:
        self.tokens = tokens
        self.expression = expression
        self.pos = 0

    def _peek(self) -> tuple[str, str, int] | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _advance(self) -> tuple[str, str, int]:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _expect(self, token_type: str, value: str | None = None) -> tuple[str, str, int]:
        tok = self._peek()
        if tok is None:
            raise ValueError(
                f"Unexpected end of expression at position "
                f"{len(self.expression)}"
            )
        if tok[0] != token_type or (value is not None and tok[1] != value):
            raise ValueError(
                f"Expected {value or token_type} at position {tok[2]}, "
                f"got '{tok[1]}'"
            )
        return self._advance()

    def parse_expr(self) -> ArithNode:
        """Parse: expr → term (('+' | '-') term)*"""
        left = self.parse_term()
        while True:
            tok = self._peek()
            if tok is None or tok[0] != _TOKEN_OP or tok[1] not in ("+", "-"):
                break
            op_tok = self._advance()
            right = self.parse_term()
            left = BinaryOp(left=left, op=op_tok[1], right=right)
        return left

    def parse_term(self) -> ArithNode:
        """Parse: term → factor (('*' | '/') factor)*"""
        left = self.parse_factor()
        while True:
            tok = self._peek()
            if tok is None or tok[0] != _TOKEN_OP or tok[1] not in ("*", "/"):
                break
            op_tok = self._advance()
            right = self.parse_factor()
            left = BinaryOp(left=left, op=op_tok[1], right=right)
        return left

    def parse_factor(self) -> ArithNode:
        """Parse: factor → '(' expr ')' | NUMBER | FIELD_REF"""
        tok = self._peek()
        if tok is None:
            raise ValueError(
                f"Unexpected end of expression at position "
                f"{len(self.expression)}"
            )

        if tok[0] == _TOKEN_LPAREN:
            self._advance()
            node = self.parse_expr()
            self._expect(_TOKEN_RPAREN, ")")
            return node

        if tok[0] == _TOKEN_NUMBER:
            self._advance()
            val_str = tok[1]
            if "." in val_str:
                return NumberLiteral(value=float(val_str))
            return NumberLiteral(value=int(val_str))

        if tok[0] == _TOKEN_FIELD:
            self._advance()
            return FieldRef(name=tok[1])

        raise ValueError(
            f"Unexpected token '{tok[1]}' at position {tok[2]}"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_arithmetic(expression: str) -> ArithNode:
    """Parse an arithmetic expression string into an AST.

    :param expression: Arithmetic expression (e.g. ``"fieldA + fieldB * 2"``).
    :returns: Root AST node.
    :raises ValueError: On malformed input.
    """
    if not expression or not expression.strip():
        raise ValueError("Arithmetic expression must not be empty")

    tokens = _tokenize(expression)
    if not tokens:
        raise ValueError("Arithmetic expression must not be empty")

    parser = _Parser(tokens, expression)
    result = parser.parse_expr()

    # Ensure all tokens were consumed
    remaining = parser._peek()
    if remaining is not None:
        raise ValueError(
            f"Unexpected token '{remaining[1]}' at position {remaining[2]}"
        )

    return result


def extract_field_refs(node: ArithNode) -> set[str]:
    """Extract all field references from an arithmetic AST.

    :param node: Root AST node.
    :returns: Set of field name strings.
    """
    refs: set[str] = set()
    _collect_refs(node, refs)
    return refs


def _collect_refs(node: ArithNode, refs: set[str]) -> None:
    """Recursively collect field references."""
    if isinstance(node, FieldRef):
        refs.add(node.name)
    elif isinstance(node, BinaryOp):
        _collect_refs(node.left, refs)
        _collect_refs(node.right, refs)
    # NumberLiteral — nothing to collect


def render_arithmetic(node: ArithNode) -> str:
    """Render an arithmetic AST back to a string expression.

    :param node: Root AST node.
    :returns: String representation of the expression.
    """
    if isinstance(node, NumberLiteral):
        return str(node.value)
    if isinstance(node, FieldRef):
        return node.name
    if isinstance(node, BinaryOp):
        left_str = render_arithmetic(node.left)
        right_str = render_arithmetic(node.right)
        # Add parens around sub-expressions when needed for precedence
        if isinstance(node.left, BinaryOp) and _needs_parens(node.left, node, is_left=True):
            left_str = f"({left_str})"
        if isinstance(node.right, BinaryOp) and _needs_parens(node.right, node, is_left=False):
            right_str = f"({right_str})"
        return f"{left_str} {node.op} {right_str}"
    raise TypeError(f"Unexpected node type: {type(node)}")  # pragma: no cover


def _precedence(op: str) -> int:
    """Return operator precedence (higher = binds tighter)."""
    if op in ("+", "-"):
        return 1
    if op in ("*", "/"):
        return 2
    return 0  # pragma: no cover


def _needs_parens(child: BinaryOp, parent: BinaryOp, *, is_left: bool) -> bool:
    """Determine if a child BinaryOp needs parentheses in its parent context."""
    child_prec = _precedence(child.op)
    parent_prec = _precedence(parent.op)
    if child_prec < parent_prec:
        return True
    # Right-associativity edge case: a - (b - c) needs parens on the right
    if not is_left and child_prec == parent_prec and parent.op in ("-", "/"):
        return True
    return False
