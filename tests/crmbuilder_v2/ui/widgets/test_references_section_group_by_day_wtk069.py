"""WTK-069 independent verification — 'Created (by day)' grouping.

These tests are the verifier's own evidence for PI-117 acceptance criteria
AC-5 and AC-7 on the one group-by path WTK-068's own suite left untested:
the *Created (by day)* bucket (design §3.5 — bucket on the ``YYYY-MM-DD``
date prefix) and the group-ordering rule (§3.7-2 — groups ordered by key,
the ``(none)`` bucket always last). They reuse the fixture conventions in
``test_references_section_sort_group.py``.
"""

from __future__ import annotations

from crmbuilder_v2.ui.widgets.references_section import ReferencesSection

# Group-by combo option indices (mirror _GROUP_OPTIONS).
_GROUP_CREATED_BY_DAY = 5


def _row(source_id, created):
    return {
        "source_type": "session",
        "source_id": source_id,
        "target_type": "decision",
        "target_id": "DEC-001",
        "relationship": "decided_in",
        "other_summary": {
            "identifier": source_id,
            "entity_type": "session",
            "title": f"{source_id} title",
            "status": "complete",
            "created_at": created,
            "updated_at": created,
        },
    }


def _payload_with_missing():
    # Two rows share a calendar day (different times); one is a different
    # day; one has a missing created_at → the "(none)" bucket.
    return {
        "as_target": [
            _row("SES-001", "2026-01-10T09:00:00+00:00"),
            _row("SES-002", "2026-01-10T22:30:00+00:00"),
            _row("SES-003", "2026-03-05T10:00:00+00:00"),
            _row("SES-004", None),
        ],
        "as_source": [],
    }


def _group_labels(section):
    gm = section._group_model
    return [gm.group_label(g) for g in range(gm.group_count())]


def test_created_buckets_by_day_not_timestamp(qapp, qtbot):
    """Two rows on the same calendar day collapse into one day bucket."""
    section = ReferencesSection("decision", "DEC-001", _payload_with_missing())
    qtbot.addWidget(section)
    section._group_combo.setCurrentIndex(_GROUP_CREATED_BY_DAY)
    labels = _group_labels(section)
    # 2026-01-10 carries both SES-001 and SES-002 despite differing times.
    assert "2026-01-10 (2)" in labels
    assert "2026-03-05 (1)" in labels


def test_created_by_day_groups_ordered_with_none_last(qapp, qtbot):
    """Day buckets sort chronologically; the missing-date bucket is last."""
    section = ReferencesSection("decision", "DEC-001", _payload_with_missing())
    qtbot.addWidget(section)
    section._group_combo.setCurrentIndex(_GROUP_CREATED_BY_DAY)
    labels = _group_labels(section)
    # YYYY-MM-DD string order == chronological order (§3.7-2); "(none)" last.
    assert labels == ["2026-01-10 (2)", "2026-03-05 (1)", "(none) (1)"]
