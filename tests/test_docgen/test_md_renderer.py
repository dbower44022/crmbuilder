"""Tests for the Markdown renderer."""

from tools.docgen.models import DocDocument, DocParagraph, DocSection, DocTable
from tools.docgen.renderers.md_renderer import render


def _make_doc(sections=None) -> DocDocument:
    return DocDocument(
        title="Test",
        subtitle="Sub",
        version="1.0",
        timestamp="2026-03-23",
        sections=sections or [],
    )


def test_heading_levels():
    doc = _make_doc([
        DocSection(title="Level 1", level=1, content=[
            DocSection(title="Level 2", level=2, content=[
                DocSection(title="Level 3", level=3),
            ]),
        ]),
    ])
    md = render(doc)
    assert "# Level 1" in md
    assert "## Level 2" in md
    assert "### Level 3" in md


def test_table_renders_as_pipe_table():
    doc = _make_doc([
        DocSection(title="Test", level=1, content=[
            DocTable(
                headers=["Name", "Value"],
                rows=[["foo", "bar"], ["baz", "qux"]],
            ),
        ]),
    ])
    md = render(doc)
    assert "| Name | Value |" in md
    assert "| --- | --- |" in md
    assert "| foo | bar |" in md


def test_status_paragraph_renders_as_blockquote():
    doc = _make_doc([
        DocSection(title="Test", level=1, content=[
            DocParagraph(text="Not Yet Implemented", style="status"),
        ]),
    ])
    md = render(doc)
    assert "> \u26a0\ufe0f **Not Yet Implemented**" in md


def test_note_paragraph():
    doc = _make_doc([
        DocSection(title="Test", level=1, content=[
            DocParagraph(text="Important info", style="note"),
        ]),
    ])
    md = render(doc)
    assert "> **Note:** Important info" in md


def test_normal_paragraph():
    doc = _make_doc([
        DocSection(title="Test", level=1, content=[
            DocParagraph(text="Just a paragraph"),
        ]),
    ])
    md = render(doc)
    assert "Just a paragraph" in md
