"""The declarative base, the engagement-scope mixins, and the dialect-aware
CHECK helpers every table module builds on (PI-508 / REQ-591, DEC-1079).

Extracted from ``access/models.py`` so segment packages can define their
tables on the one ``Base`` without importing the shared models module. The
shared module re-exports every name here, so existing import paths keep
working.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql.expression import ColumnElement

# --- PI-alpha (D1): dialect-aware identifier-format CHECK constraints ---
#
# The identifier-format CHECKs were hand-written as SQLite ``GLOB`` predicates
# (e.g. ``session_identifier GLOB 'SES-[0-9][0-9][0-9]'``). ``GLOB`` is a
# SQLite-only operator — Postgres has no GLOB, so ``create_all`` against PG
# fails. These two custom constructs render the **byte-identical GLOB form on
# SQLite** (so create_all on SQLite is unchanged and existing SQLite DBs, whose
# CHECK text is already baked in, are untouched) and the equivalent **POSIX
# regex (``~``) form on Postgres**.


class _IdentifierFormatCheck(ColumnElement):
    """An identifier-format CHECK predicate, dialect-rendered.

    ``prefixes`` are OR'd together (the session/conversation rows admit two);
    ``digits`` is the trailing digit count (3 for most, 4 for ``CM-``/``REF-``).

    ``at_least`` makes ``digits`` a floor rather than an exact count, for a
    series that outgrows its width. ``REF-`` did: the four-digit CHECK
    rejected REF-10000 and every reference write in the store failed until
    the constraint was widened (shared_core_0003). A series whose rows are
    written by the machine rather than named by a person will reach its
    ceiling eventually, so the floor is the safer shape for those.
    """

    inherit_cache = True
    type = Boolean()

    #: SQLite has no bounded-repetition GLOB, so an open-ended check is
    #: rendered there as an OR over widths up to this many digits.
    _SQLITE_MAX_DIGITS = 8

    def __init__(
        self,
        column_name: str,
        prefixes,
        digits: int = 3,
        allow_null: bool = False,
        at_least: bool = False,
    ) -> None:
        self.column_name = column_name
        self.prefixes = tuple(prefixes)
        self.digits = digits
        self.at_least = at_least
        # ``allow_null`` prepends ``<col> IS NULL OR`` (e.g. server-assigned
        # REF-NNNN, NULL before assignment). Folded into the rendered predicate
        # — rather than wrapping the element in ``sql.or_`` — because nesting a
        # boolean custom element inside ``and_``/``or_`` makes SQLAlchemy's
        # SQLite compiler append a spurious ``= 1`` boolean coercion.
        self.allow_null = allow_null


@compiles(_IdentifierFormatCheck, "sqlite")
def _render_ident_sqlite(element, compiler, **kw) -> str:
    widths = (
        range(element.digits, element._SQLITE_MAX_DIGITS + 1)
        if element.at_least
        else (element.digits,)
    )
    pred = " OR ".join(
        f"{element.column_name} GLOB '{p}-{'[0-9]' * n}'"
        for p in element.prefixes
        for n in widths
    )
    if element.allow_null:
        pred = f"{element.column_name} IS NULL OR {pred}"
    return pred


@compiles(_IdentifierFormatCheck)
def _render_ident_default(element, compiler, **kw) -> str:
    # POSIX regex (Postgres ``~``): anchored, exact trailing digit count,
    # or a floor when ``at_least`` is set.
    count = f"{element.digits}," if element.at_least else str(element.digits)
    pred = " OR ".join(
        f"{element.column_name} ~ '^{p}-[0-9]{{{count}}}$'" for p in element.prefixes
    )
    if element.allow_null:
        pred = f"{element.column_name} IS NULL OR {pred}"
    return pred


class _LowerHexCheck(ColumnElement):
    """A "value is all lowercase hex (or empty)" CHECK, dialect-rendered.

    The git-commit-SHA guard: SQLite ``col NOT GLOB '*[^0-9a-f]*'`` (no char
    outside ``0-9a-f``) ⇔ Postgres ``col ~ '^[0-9a-f]*$'``. ``length`` prepends
    an exact-length predicate (``LENGTH`` is portable across both dialects).
    """

    inherit_cache = True
    type = Boolean()

    def __init__(self, column_name: str, length: int | None = None) -> None:
        self.column_name = column_name
        self.length = length


@compiles(_LowerHexCheck, "sqlite")
def _render_hex_sqlite(element, compiler, **kw) -> str:
    pred = f"{element.column_name} NOT GLOB '*[^0-9a-f]*'"
    if element.length is not None:
        pred = f"LENGTH({element.column_name}) = {element.length} AND {pred}"
    return pred


@compiles(_LowerHexCheck)
def _render_hex_default(element, compiler, **kw) -> str:
    pred = f"{element.column_name} ~ '^[0-9a-f]*$'"
    if element.length is not None:
        pred = f"LENGTH({element.column_name}) = {element.length} AND {pred}"
    return pred


class _NonEmptyJsonArrayCheck(ColumnElement):
    """A "column is NULL or a non-empty JSON array" CHECK, dialect-rendered.

    SQLite uses ``json_valid``/``json_type``/``json_array_length``; Postgres
    JSONB uses ``jsonb_typeof``/``jsonb_array_length`` (and is always valid
    JSON, so no validity guard is needed).
    """

    inherit_cache = True
    type = Boolean()

    def __init__(self, column_name: str) -> None:
        self.column_name = column_name


@compiles(_NonEmptyJsonArrayCheck, "sqlite")
def _render_jsonarr_sqlite(element, compiler, **kw) -> str:
    c = element.column_name
    return (
        f"{c} IS NULL OR (json_valid({c}) AND json_type({c}) = 'array' "
        f"AND json_array_length({c}) >= 1)"
    )


@compiles(_NonEmptyJsonArrayCheck)
def _render_jsonarr_default(element, compiler, **kw) -> str:
    c = element.column_name
    return (
        f"{c} IS NULL OR (jsonb_typeof({c}) = 'array' "
        f"AND jsonb_array_length({c}) >= 1)"
    )


class _BooleanDomainCheck(ColumnElement):
    """A boolean-domain CHECK, dialect-rendered.

    SQLite stores Boolean as the integers ``0``/``1`` (``IN (0, 1)``); Postgres
    has a native boolean type, so the literals are ``true``/``false``. NULL
    satisfies the CHECK on both (``NULL IN (...)`` is unknown ⇒ passes).
    """

    inherit_cache = True
    type = Boolean()

    def __init__(self, column_name: str) -> None:
        self.column_name = column_name


@compiles(_BooleanDomainCheck, "sqlite")
def _render_booldomain_sqlite(element, compiler, **kw) -> str:
    return f"{element.column_name} IN (0, 1)"


@compiles(_BooleanDomainCheck)
def _render_booldomain_default(element, compiler, **kw) -> str:
    return f"{element.column_name} IN (true, false)"



def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class EngagementScopedMixin:
    """Row-level tenant discriminator for the unified multi-engagement DB.

    PI-123 Slice 2 (DEC-375 / D2, D5). ``engagement_id`` holds the owning
    engagement's **stable identifier** (``engagements.engagement_identifier``,
    ``ENG-NNN``) — the durable key (never renamed, unlike ``engagement_code``),
    so no separate integer surrogate is needed and the discriminator stays
    consistent with v2's identifier-keyed model (refs, etc.).

    **Strict (cutover) schema** — PI-123 Stage 2. ``engagement_id`` is now
    ``NOT NULL`` with a FK to ``engagements.engagement_identifier``. Every
    scoped row belongs to exactly one engagement. Identifier uniqueness is
    composite ``(engagement_id, <identifier>)`` per the three constraint classes
    in ``pi-123-slice3-enforce-plan.md`` §1: identifier-as-PK tables (Class A)
    make ``engagement_id`` a PK member (redeclared per-class with
    ``primary_key=True``); surrogate-PK tables (Class B) swap
    ``UNIQUE(identifier)`` for ``UNIQUE(engagement_id, identifier)``; the two
    un-keyed tables (Class C) take only NOT NULL + FK + an index.

    This is the *target* schema that ``Base.metadata.create_all`` materialises
    for the unified DB (D9 builds fresh + copies rows in). The central
    read-filter (``do_orm_execute`` → ``with_loader_criteria``) and the
    write-stamp (``before_flush``) in ``engagement_scope.py`` key on this column
    and are activated at the cutover (and in the test fixtures, which seed an
    engagement and set it active so the stamp fills every insert).
    """

    engagement_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("engagements.engagement_identifier"),
        nullable=False,
    )


class EngagementScopedPKMixin(EngagementScopedMixin):
    """Class A scoping: ``engagement_id`` is also part of the composite PK.

    The 19 identifier-as-PK governance/methodology tables (plus
    ``engagement_areas``, whose PK is a name) make ``engagement_id`` the leading
    member of a composite primary key ``(engagement_id, <entity>_identifier)``,
    so the same prefixed identifier can coexist across engagements while an
    intra-engagement duplicate is still rejected (DEC-375 / D3). Subclasses keep
    their existing ``<entity>_identifier`` / name column with
    ``primary_key=True``; this override supplies the second PK column.
    ``isinstance(obj, EngagementScopedMixin)`` still holds, so the central
    read-filter / write-stamp cover these tables unchanged.
    """

    engagement_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("engagements.engagement_identifier"),
        primary_key=True,
        nullable=False,
    )


# PI-alpha (D1): JSON columns use JSONB on Postgres and plain JSON everywhere
# else (the still-SQLite meta DB, legacy SQLite installs, and the unified-DB
# migration source). A single shared ``TypeEngine`` instance per variant is
# safe — SQLAlchemy type objects are immutable descriptors reused across
# columns. ``none_as_null`` is load-bearing on the work-area-labels column (a
# Python ``None`` must persist as SQL NULL, not the JSON text ``'null'``); it is
# preserved on both sides of the variant.
JSONColumn = JSON().with_variant(JSONB(), "postgresql")
JSONColumnNoneAsNull = JSON(none_as_null=True).with_variant(
    JSONB(none_as_null=True), "postgresql"
)
