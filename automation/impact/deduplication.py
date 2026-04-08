"""Batch deduplication for Impact Analysis.

Implements L2 PRD Section 12.4.3 — when multiple ChangeLog entries in
the same batch surface the same (affected_table, affected_record_id)
pair, merges them into one CandidateImpact.

Deduplication rules:
- Each unique affected record appears once in results.
- change_log_id references the FIRST ChangeLog entry that surfaced it.
- impact_description aggregates all relevant changes.
- requires_review = True if ANY contributing impact had requires_review=True.
"""

from __future__ import annotations

from automation.impact.changeimpact import CandidateImpact


def deduplicate(candidates: list[CandidateImpact]) -> list[CandidateImpact]:
    """Deduplicate candidate impacts by (affected_table, affected_record_id).

    :param candidates: All candidate impacts from a batch, before dedup.
    :returns: Deduplicated list with merged descriptions.
    """
    if not candidates:
        return []

    # Group by (affected_table, affected_record_id)
    groups: dict[tuple[str, int], list[CandidateImpact]] = {}
    for c in candidates:
        key = (c.affected_table, c.affected_record_id)
        groups.setdefault(key, []).append(c)

    merged: list[CandidateImpact] = []
    for (table, rid), group in groups.items():
        if len(group) == 1:
            merged.append(group[0])
            continue

        # Merge: first change_log_id, combined descriptions, OR of requires_review
        first = group[0]
        descriptions = []
        seen_descs: set[str] = set()
        requires_review = False
        for c in group:
            if c.impact_description not in seen_descs:
                descriptions.append(c.impact_description)
                seen_descs.add(c.impact_description)
            if c.requires_review:
                requires_review = True

        combined_desc = " | ".join(descriptions)

        merged.append(
            CandidateImpact(
                change_log_id=first.change_log_id,
                affected_table=table,
                affected_record_id=rid,
                impact_description=combined_desc,
                requires_review=requires_review,
            )
        )

    return merged
