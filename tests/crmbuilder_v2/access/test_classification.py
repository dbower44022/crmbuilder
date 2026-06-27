"""PI-202 / REQ-185 (WTK-217) — content-vs-software Planning Item classification.

Content iff every area is a methodology-* area (and there is at least one);
anything else — empty, mixed, or any software/engagement area — is software.
A pure function of the PI's areas, so these tests need no runtime.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.classification import (
    CONTENT,
    METHODOLOGY_AREAS,
    SOFTWARE,
    classify_areas,
    classify_planning_item,
    is_content_planning_item,
)


def test_methodology_areas_are_the_four_system_areas():
    assert METHODOLOGY_AREAS == {
        "methodology-process",
        "methodology-product",
        "methodology-interviews",
        "methodology-templates",
    }


@pytest.mark.parametrize(
    "areas, expected",
    [
        # all-methodology → content
        (["methodology-process"], CONTENT),
        (["methodology-process", "methodology-product"], CONTENT),
        (list(METHODOLOGY_AREAS), CONTENT),
        # any software area → software
        (["access"], SOFTWARE),
        (["ui", "api"], SOFTWARE),
        # mixed content + software → software (deferred split, design §6)
        (["methodology-process", "access"], SOFTWARE),
        # engagement-defined (non-methodology) area → software
        (["cbm-intake"], SOFTWARE),
        (["methodology-process", "cbm-intake"], SOFTWARE),
        # empty / None → software (default runtime path)
        ([], SOFTWARE),
        (None, SOFTWARE),
        # falsy entries are ignored, not treated as content
        (["", None], SOFTWARE),
        (["methodology-process", ""], CONTENT),
        # order/duplication-insensitive
        (["methodology-product", "methodology-product"], CONTENT),
    ],
)
def test_classify_areas(areas, expected):
    assert classify_areas(areas) == expected


def test_classify_planning_item_reads_area_list():
    assert classify_planning_item({"area": ["methodology-templates"]}) == CONTENT
    assert classify_planning_item({"area": ["storage"]}) == SOFTWARE
    # a PI with no area key / None area is software, not an error
    assert classify_planning_item({}) == SOFTWARE
    assert classify_planning_item({"area": None}) == SOFTWARE


def test_is_content_planning_item():
    assert is_content_planning_item({"area": ["methodology-interviews"]}) is True
    assert is_content_planning_item({"area": ["methodology-process", "ui"]}) is False
    assert is_content_planning_item({"area": []}) is False
