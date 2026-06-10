"""content_version bump tests."""
from __future__ import annotations

from espo_impl.core.reconcile.document import YamlDocument


def _doc(version_line):
    return YamlDocument(f'version: "1.0"\n{version_line}\nentities: {{}}\n')


def test_minor_bump_resets_patch():
    doc = _doc('content_version: "1.2.3"')
    assert doc.bump_content_version() == ("1.2.3", "1.3.0")
    assert 'content_version: "1.3.0"' in doc.render()


def test_major_and_patch_bumps():
    doc = _doc('content_version: "1.2.3"')
    assert doc.bump_content_version("major") == ("1.2.3", "2.0.0")

    doc2 = _doc('content_version: "1.2.3"')
    assert doc2.bump_content_version("patch") == ("1.2.3", "1.2.4")


def test_absent_version_returns_none():
    doc = YamlDocument('version: "1.0"\nentities: {}\n')
    assert doc.bump_content_version() is None


def test_quote_style_preserved():
    doc = _doc('content_version: "1.0.0"')
    doc.bump_content_version()
    assert 'content_version: "1.1.0"' in doc.render()  # stays double-quoted
