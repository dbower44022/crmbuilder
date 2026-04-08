"""Tests for automation.docgen.templates.formatting — shared constants."""

from automation.docgen.templates.formatting import (
    ALT_ROW_BG,
    BODY_SIZE,
    BORDER_COLOR,
    CONTENT_WIDTH,
    DRAFT_HEADER_TEXT,
    FIELD_COL_HEADERS,
    FIELD_COL_WIDTHS,
    FONT_NAME,
    GRAY_TEXT,
    H1_SIZE,
    H2_SIZE,
    H3_SIZE,
    HEADER_BG,
    HEADER_TEXT,
    MARGIN_BOTTOM,
    MARGIN_LEFT,
    MARGIN_RIGHT,
    MARGIN_TOP,
    META_COL_WIDTHS_ENTITY,
    META_COL_WIDTHS_PROCESS,
    NATIVE_FIELD_COL_WIDTHS,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    REL_COL_WIDTHS,
    REQ_COL_WIDTHS,
    SMALL_SIZE,
    TABLE_WIDTH_DXA,
    TITLE_COLOR,
    TWO_COL_WIDTHS,
    XS_SIZE,
)


class TestFormattingConstants:

    def test_colors_defined(self):
        assert HEADER_BG == "1F3864"
        assert HEADER_TEXT == "FFFFFF"
        assert TITLE_COLOR == "1F3864"
        assert ALT_ROW_BG == "F2F7FB"
        assert BORDER_COLOR == "AAAAAA"
        assert GRAY_TEXT == "888888"

    def test_font(self):
        assert FONT_NAME == "Arial"

    def test_font_sizes(self):
        # Body 11pt, small 10pt, xs 8pt
        assert BODY_SIZE.pt == 11
        assert SMALL_SIZE.pt == 10
        assert XS_SIZE.pt == 8
        assert H1_SIZE.pt == 16
        assert H2_SIZE.pt == 14
        assert H3_SIZE.pt == 12

    def test_page_dimensions(self):
        # US Letter
        assert PAGE_WIDTH.inches == 8.5
        assert PAGE_HEIGHT.inches == 11
        assert MARGIN_TOP.inches == 1
        assert MARGIN_BOTTOM.inches == 1
        assert MARGIN_LEFT.inches == 1
        assert MARGIN_RIGHT.inches == 1
        assert CONTENT_WIDTH.inches == 6.5

    def test_field_table_widths(self):
        assert FIELD_COL_WIDTHS == [2200, 1100, 800, 2400, 1000, 1860]
        assert sum(FIELD_COL_WIDTHS) == TABLE_WIDTH_DXA
        assert len(FIELD_COL_HEADERS) == len(FIELD_COL_WIDTHS)

    def test_table_width(self):
        assert TABLE_WIDTH_DXA == 9360

    def test_req_col_widths(self):
        assert sum(REQ_COL_WIDTHS) == TABLE_WIDTH_DXA

    def test_native_field_col_widths(self):
        assert sum(NATIVE_FIELD_COL_WIDTHS) == TABLE_WIDTH_DXA

    def test_rel_col_widths(self):
        assert sum(REL_COL_WIDTHS) == TABLE_WIDTH_DXA

    def test_two_col_widths(self):
        assert sum(TWO_COL_WIDTHS) == TABLE_WIDTH_DXA

    def test_meta_col_widths(self):
        assert sum(META_COL_WIDTHS_PROCESS) == TABLE_WIDTH_DXA
        assert sum(META_COL_WIDTHS_ENTITY) == TABLE_WIDTH_DXA

    def test_draft_header_text(self):
        assert "DRAFT" in DRAFT_HEADER_TEXT
