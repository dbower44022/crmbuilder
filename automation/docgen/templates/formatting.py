"""Shared formatting constants for Document Generator templates.

Implements L2 PRD Section 13.4 — all colors, fonts, sizes, page dimensions,
table column widths, and style constants used across Word document templates.
A change to any constant here propagates to all templates on the next generation.

Constants match the reference implementations in:
  - PRDs/process/templates/generate-process-doc-template.js
  - PRDs/process/templates/generate-entity-prd-template.js
"""

from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: F401 — re-exported for templates
from docx.shared import Inches, Pt, RGBColor

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------

HEADER_BG = "1F3864"
HEADER_TEXT = "FFFFFF"
TITLE_COLOR = "1F3864"
ALT_ROW_BG = "F2F7FB"
BORDER_COLOR = "AAAAAA"
GRAY_TEXT = "888888"
META_KEY_BG = "E8E8E8"

# As RGBColor objects for python-docx
HEADER_BG_RGB = RGBColor(0x1F, 0x38, 0x64)
HEADER_TEXT_RGB = RGBColor(0xFF, 0xFF, 0xFF)
TITLE_COLOR_RGB = RGBColor(0x1F, 0x38, 0x64)
ALT_ROW_BG_RGB = RGBColor(0xF2, 0xF7, 0xFB)
BORDER_COLOR_RGB = RGBColor(0xAA, 0xAA, 0xAA)
GRAY_TEXT_RGB = RGBColor(0x88, 0x88, 0x88)

# ---------------------------------------------------------------------------
# Font
# ---------------------------------------------------------------------------

FONT_NAME = "Arial"

# ---------------------------------------------------------------------------
# Font sizes (in half-points for python-docx, matching JS template SZ values)
# JS template uses half-points: body=22, small=20, xs=16, h1=32, h2=28, h3=24
# python-docx Pt() takes points, so divide by 2
# ---------------------------------------------------------------------------

BODY_SIZE = Pt(11)       # 22 half-points
SMALL_SIZE = Pt(10)      # 20 half-points
XS_SIZE = Pt(8)          # 16 half-points
H1_SIZE = Pt(16)         # 32 half-points
H2_SIZE = Pt(14)         # 28 half-points
H3_SIZE = Pt(12)         # 24 half-points
META_SIZE = Pt(10)       # 20 half-points
TITLE_SIZE = Pt(18)      # 36 half-points
SUBTITLE_SIZE = Pt(14)   # 28 half-points
HEADER_FONT_SIZE = Pt(9) # 18 half-points

# ---------------------------------------------------------------------------
# Page dimensions — US Letter with 1" margins
# ---------------------------------------------------------------------------

PAGE_WIDTH = Inches(8.5)
PAGE_HEIGHT = Inches(11)
MARGIN_TOP = Inches(1)
MARGIN_BOTTOM = Inches(1)
MARGIN_LEFT = Inches(1)
MARGIN_RIGHT = Inches(1)
CONTENT_WIDTH = Inches(6.5)  # 8.5 - 2 * 1

# ---------------------------------------------------------------------------
# Table widths (in DXA = twentieths of a point, matching JS templates)
# US Letter with 1" margins = 9360 DXA content width
# ---------------------------------------------------------------------------

TABLE_WIDTH_DXA = 9360

# Field table column widths: 2200+1100+800+2400+1000+1860 = 9360
FIELD_COL_WIDTHS = [2200, 1100, 800, 2400, 1000, 1860]
FIELD_COL_HEADERS = ["Field Name", "Type", "Required", "Values", "Default", "ID"]

# Requirement table column widths
REQ_COL_WIDTHS = [2000, 7360]

# Native field table column widths (Entity PRD)
NATIVE_FIELD_COL_WIDTHS = [2200, 1400, 3000, 2760]
NATIVE_FIELD_COL_HEADERS = ["Native Field", "Type", "PRD Name(s) / Mapping", "Referenced By"]

# Relationship table column widths (Entity PRD)
REL_COL_WIDTHS = [2600, 1800, 1400, 1700, 1860]
REL_COL_HEADERS = ["Relationship", "Related Entity", "Link Type", "PRD Reference", "Domain(s)"]

# Two-column table (issues, decisions) column widths (Entity PRD)
TWO_COL_WIDTHS = [1500, 7860]

# Metadata table column widths (Process Doc title page)
META_COL_WIDTHS_PROCESS = [2400, 6960]

# Metadata table column widths (Entity PRD)
META_COL_WIDTHS_ENTITY = [2800, 6560]

# ---------------------------------------------------------------------------
# Cell margins (in DXA, matching JS templates)
# ---------------------------------------------------------------------------

CELL_MARGIN_TOP = 60
CELL_MARGIN_BOTTOM = 60
CELL_MARGIN_LEFT = 100
CELL_MARGIN_RIGHT = 100

DESC_MARGIN_TOP = 40
DESC_MARGIN_BOTTOM = 80

# ---------------------------------------------------------------------------
# Spacing (in twips, matching JS templates)
# ---------------------------------------------------------------------------

PARAGRAPH_AFTER = 120
BULLET_AFTER = 60
NUMBERED_AFTER = 80

H1_BEFORE = 360
H1_AFTER = 120
H2_BEFORE = 240
H2_AFTER = 120
H3_BEFORE = 200
H3_AFTER = 100

# ---------------------------------------------------------------------------
# Workflow diagram
# ---------------------------------------------------------------------------

DIAGRAM_WIDTH = Inches(6.5)  # Content width for embedded diagrams

# ---------------------------------------------------------------------------
# Draft watermark text
# ---------------------------------------------------------------------------

DRAFT_HEADER_TEXT = "DRAFT — FOR PREVIEW ONLY"
