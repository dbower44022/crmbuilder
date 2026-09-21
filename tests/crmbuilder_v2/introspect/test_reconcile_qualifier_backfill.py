"""An audit fills a qualifying property the design never carried — REQ-627.

The two cases here are the two CBMTEST refused on 2026-09-19, written from
what the instance actually holds rather than from what the code expects:
``Resource.URL`` is a web address there and ``Contribution.Notes`` is a
rich-text box, while both design records carry nothing. The publish rendered
each as the plain kind and the additive-only fence refused it as a type change
on a field nobody had touched.

The create path has recorded these properties since PI-414 and PI-430. Nothing
ever filled one in on a record created before that, because the deviation check
compares under forward asymmetry: a canonical ``None`` never produces a
difference, so it never produced a correction either.
"""

from __future__ import annotations

from typing import Any

from crmbuilder_v2.introspect.reconcile import (
    _audited_field_attrs,
    _backfill_qualifiers,
    _field_override,
)


class FakeFieldRepo:
    """Records the patches an audit would write."""

    def __init__(self) -> None:
        self.patches: list[tuple[str, dict[str, Any]]] = []

    def patch_field(self, session: Any, identifier: str, **fields: Any) -> dict:
        self.patches.append((identifier, dict(fields)))
        return {"field_identifier": identifier, **fields}


def _canonical(identifier: str = "FLD-203", **carried: Any) -> dict[str, Any]:
    """A design field record as a June 2026 audit left it — every qualifying
    property empty, because nothing read them then."""
    row: dict[str, Any] = {
        "field_identifier": identifier,
        "field_type": "text",
        "field_format": None,
        "field_numeric_scale": None,
        "field_display": None,
        "field_values": None,
        "field_holds": None,
        "field_supplied_by": None,
    }
    row.update(carried)
    return row


# --- the two real cases -----------------------------------------------------


def test_a_web_address_field_gains_its_format() -> None:
    """Resource.URL on CBMTEST: the instance holds a web address, the design
    said plain text, and a publish proposed replacing one with the other."""
    repo = FakeFieldRepo()
    filled = _backfill_qualifiers(
        None, repo, _canonical(), _audited_field_attrs({"type": "url"})
    )
    assert filled == ["field_format"]
    assert repo.patches == [("FLD-203", {"format": "url"})]


def test_a_rich_text_field_gains_its_display() -> None:
    """Contribution.Notes on CBMTEST: the instance holds a rich-text box."""
    repo = FakeFieldRepo()
    canonical = _canonical("FLD-135", field_type="long_text")
    filled = _backfill_qualifiers(
        None, repo, canonical, _audited_field_attrs({"type": "wysiwyg"})
    )
    assert filled == ["field_display"]
    assert repo.patches == [("FLD-135", {"display": "rich_text"})]


def test_the_backfill_closes_the_refusal_it_was_written_for() -> None:
    """The point of the whole thing: once filled, the design and the instance
    no longer disagree, so there is nothing left for the fence to refuse."""
    audited = _audited_field_attrs({"type": "url"})
    canonical = _canonical()
    _backfill_qualifiers(None, FakeFieldRepo(), canonical, audited)
    # The backfill patches the store, so mirror it onto the row the way a
    # re-read would, then ask the deviation check what is left.
    canonical["field_format"] = audited["field_format"]
    assert _field_override(canonical, audited) == {}


# --- what it must not do ----------------------------------------------------


def test_a_property_the_design_carries_is_left_alone() -> None:
    """Disagreement is drift, and drift is reported for a person to judge. A
    backfill that overwrote it would silently make the design agree with
    whatever the instance happened to say."""
    repo = FakeFieldRepo()
    canonical = _canonical(field_format="email")
    filled = _backfill_qualifiers(
        None, repo, canonical, _audited_field_attrs({"type": "url"})
    )
    assert filled == []
    assert repo.patches == []


def test_drift_is_still_reported_after_the_backfill_runs() -> None:
    """The same case, from the other side: the deviation survives."""
    audited = _audited_field_attrs({"type": "url"})
    canonical = _canonical(field_format="email")
    _backfill_qualifiers(None, FakeFieldRepo(), canonical, audited)
    assert _field_override(canonical, audited)["field_format"] == "url"


def test_a_plain_field_is_not_given_a_property_it_does_not_have() -> None:
    """A varchar carries no format. Writing one would invent a refinement the
    instance never had, which is the mirror of the defect being fixed."""
    repo = FakeFieldRepo()
    filled = _backfill_qualifiers(
        None, repo, _canonical(), _audited_field_attrs({"type": "varchar"})
    )
    assert filled == []
    assert repo.patches == []


def test_a_field_already_fully_described_is_a_no_op() -> None:
    """A re-audit of a field created since the create path recorded these
    writes nothing, so re-auditing is not a stream of pointless patches."""
    audited = _audited_field_attrs({"type": "urlMultiple"})
    canonical = _canonical(**{k: audited[k] for k in audited if k.startswith("field_")})
    repo = FakeFieldRepo()
    assert _backfill_qualifiers(None, repo, canonical, audited) == []
    assert repo.patches == []


def test_every_qualifying_property_is_covered_not_only_the_two_that_bit() -> None:
    """``urlMultiple`` carries a format and a holds. Fixing only the properties
    CBMTEST happened to surface would leave the next instance to find the rest
    the same expensive way."""
    repo = FakeFieldRepo()
    filled = _backfill_qualifiers(
        None, repo, _canonical(), _audited_field_attrs({"type": "urlMultiple"})
    )
    assert filled == ["field_format", "field_holds"]
    assert dict(p for _, patch in repo.patches for p in patch.items()) == {
        "format": "url",
        "holds": "several",
    }


# --- the audit says what it wrote (REQ-627 / PI-541) ------------------------


def test_the_backfill_reports_what_it_filled_so_a_summary_can_count_it() -> None:
    """The backfill writes to design records nobody has watched it write. It
    returns what it filled so the fields area can say so, rather than leaving
    an operator to discover the writes afterwards — which is the shape of
    defect this path has already been corrected for three times."""
    repo = FakeFieldRepo()
    filled = _backfill_qualifiers(
        None, repo, _canonical(), _audited_field_attrs({"type": "urlMultiple"})
    )
    assert len(filled) == len(repo.patches)
