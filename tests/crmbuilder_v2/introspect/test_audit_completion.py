"""Truthful audit-completion classifier — REQ-395 / PI-354 / DEC-862.

A successful audit that populated no inventory must report that plainly, not
read as a successful complete audit (the 06-26 CBM failure mode). Read failures
never reach the classifier — they raise ReconcileError (a 422) upstream.
"""

from __future__ import annotations

from crmbuilder_v2.introspect.reconcile import classify_audit_completion


def test_populated_audit_is_complete():
    result = classify_audit_completion(
        {
            "entities": {"seen": 2, "created": 0, "present": 2, "drifted": 0,
                         "absent": 0},
            "fields": {"seen": 5, "created": 0, "present": 5, "drifted": 0,
                       "absent": 0},
        }
    )
    assert result["status"] == "complete"
    assert result["areas_ran"] == 2
    assert result["totals"]["present"] == 7


def test_successful_but_empty_audit_is_empty_not_complete():
    # Every area read successfully (it is here, not raising) but found nothing.
    result = classify_audit_completion(
        {
            "entities": {"seen": 0, "created": 0, "present": 0, "drifted": 0,
                         "absent": 0},
            "fields": {"seen": 0, "created": 0, "present": 0, "drifted": 0,
                       "absent": 0},
        }
    )
    assert result["status"] == "empty"
    assert "no inventory" in result["message"].lower()
    assert "not a successful" in result["message"].lower()


def test_candidates_only_audit_is_distinct():
    result = classify_audit_completion(
        {
            "entities": {"seen": 0, "created": 0, "present": 0, "drifted": 0,
                         "absent": 0, "candidates": 3},
        }
    )
    assert result["status"] == "candidates_only"
    assert "3 unresolved" in result["message"]


def test_absent_only_run_still_counts_as_complete():
    # A run that only swept previously-present objects to absent did real work —
    # it is not an empty result (REQ-394/REQ-395 interplay).
    result = classify_audit_completion(
        {"entities": {"seen": 0, "created": 0, "present": 0, "drifted": 0,
                      "absent": 4}}
    )
    assert result["status"] == "complete"


def test_all_skipped_areas_report_no_areas():
    result = classify_audit_completion(
        {
            "roles": {"skipped": True, "reason": "source audit"},
            "teams": {"skipped": True, "reason": "source audit"},
        }
    )
    assert result["status"] == "no_areas"
    assert result["areas_ran"] == 0


def test_skipped_areas_are_excluded_but_real_areas_classified():
    result = classify_audit_completion(
        {
            "entities": {"seen": 1, "present": 1, "created": 0, "drifted": 0,
                         "absent": 0},
            "roles": {"skipped": True},
        }
    )
    assert result["status"] == "complete"
    assert result["areas_ran"] == 1
