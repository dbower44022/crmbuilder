# Governance Entity Schema Design — `commit` — Kickoff Prompt

**Last Updated:** 05-23-26 21:00
**Work ticket kind:** kickoff_prompt
**Status:** ready
**Workstream:** Code Change Lifecycle (established in SES-057)
**Planning item this conversation resolves:** PI-028
**Predecessor conversation:** SES-061 (methodology drafting conversation; settled the eight design decisions this kickoff inherits)
**Schema spec template:** `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md`
**Methodology authority for this spec:** `PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md` v1.0

> **Note on the work_ticket status.** This kickoff is structurally a `work_ticket` record (kind: `kickoff_prompt`, status: `ready`). It is authored in SES-061's close-out payload as part of the broad work_ticket authoring rule (per DEC-189 in `methodology-code-change-lifecycle.md` §5.1).

---

## Goal

Author `PRDs/product/crmbuilder-v2/governance-schema-specs/commit.md` — the complete `commit` entity type schema specification per the seven-section format in `governance-entity-schema-spec-guide.md`. The conversation is heavily pre-decided by the methodology document (most architectural questions are already settled there); the spec primarily renders those decisions into the standard schema-spec shape and surfaces the remaining open questions for resolution in passing.

The motivating context, the seven-stage lifecycle, the audit query patterns, and the eight foundation decisions (DEC-183 through DEC-190) are documented in `methodology-code-change-lifecycle.md`. **Read that document first.** It is the authoritative source for everything this spec must implement; this kickoff names only what is specific to the schema-spec rendering.

---

## Pre-decided by the methodology (do not re-litigate)

The following are already decided by `methodology-code-change-lifecycle.md` §3.1 and the eight foundation decisions. The schema spec records them; it does not revisit them:

- **Entity type name (storage):** `commit`
- **Display name (singular / plural):** "Commit" / "Commits"
- **Identifier prefix:** `CM`
- **Identifier format:** `CM-NNNN` (four digits, zero-padded)
- **Identifier assignment:** client-side, per the prefixed-identifier convention (CLAUDE.md line 62)
- **v0.8 fields** (the list in methodology §3.1 — fourteen columns including the three governance-standard timestamps)
- **Deferred fields:** `files_changed_paths`, `signed_by`, `committer_*`, `message_trailers` — defer to v0.9
- **REST endpoints:** standard set plus `GET /commits/by-sha/{sha}` (full or prefix SHA; ambiguity → 409 with candidate list)
- **UI:** Commits panel under the Governance sidebar group (panel details deferred to PI-031 build prompts)
- **Soft-delete posture:** default V2 soft-delete with restore
- **Lifecycle:** documentary-shaped (per DEC-137 cross-spec precedent in `work_ticket.md` §3.4) — base timestamps only; no per-status lifecycle timestamps. A commit either exists or doesn't; there is no workflow on a commit itself.

---

## Design questions for the schema-design conversation to settle

These are the open questions specific to rendering the methodology into the schema spec format. Settle them in the conversation; record each as a decision in the close-out.

### Question 1 — Lifecycle posture: documentary or workflow?

The methodology §3.1 implies a documentary-shaped lifecycle (no statuses, no transitions, commits just exist once ingested). The pattern matches `reference_book.md` v1.0's documentary posture per DEC-137 precedent (SES-050).

But: a commit might plausibly have a lifecycle if revertedness, supersededness, or branch-deletedness are tracked. None of these are currently in scope per the v0.8 field set. Confirm the documentary posture in the schema spec, OR surface an unanticipated workflow consideration.

Recommended posture: documentary. Confirm in passing.

### Question 2 — Cross-spec precedent contribution

Per `governance-entity-schema-spec-guide.md` §7, every schema spec is invited to contribute cross-spec precedents that successor specs may inherit. The commit spec is the seventh governance entity type and the first under v0.8; what (if anything) does it establish that the next governance entity type should inherit?

Candidate precedents the commit spec may establish:
- **The `<entity>_by-natural-key/{value}` lookup endpoint pattern** — `/commits/by-sha/{sha}` is the first such endpoint on a governance entity. Future entities with a strong natural key (e.g., a future `file_artifact` entity with a content-hash natural key) inherit the pattern.
- **The JSON array column for variable-cardinality scalar lists** — `parent_shas` is the first JSON array column on a governance entity table. Future schemas needing a 0-to-N list of scalars (without needing a separate normalized table) inherit the pattern.
- **The conversation-scoped accounting unit principle** (per DEC-187) — every record produced by a conversation belongs to that conversation's engagement DB, regardless of which physical artifact (repo, file, external system) the record describes. Future entities representing artifacts that physically live outside the engagement DB inherit the principle.

Settle which (if any) to elevate to cross-spec precedent status. Recommended: all three are worth recording. The third is the most consequential — it generalizes the engagement-as-accounting-unit principle to any future entity type representing external artifacts.

### Question 3 — Field naming convention for `commit_*` fields

Per DEC-046 (parent-prefix field naming, inherited from methodology workstream), fields are named with the parent entity's prefix when they belong to that entity. The methodology document §3.1 already uses this convention (`commit_sha`, `commit_message_first_line`, etc.). Confirm and apply uniformly through the spec.

One name worth checking: `commit_conversation_id` vs `commit_conversation_identifier`. Existing V2 patterns use `_id` for FK fields whose target is identified by a string identifier (e.g., `parent_close_out_payload_id` on a deposit_event row holds a `COP-NNN` string). Apply that pattern: `commit_conversation_id` holds the parent conversation's `conversation_identifier` value (e.g., `CONV-NNN`).

Settle the naming uniformly and call out the FK-via-identifier-string pattern in the spec's section 3.2.4.

### Question 4 — Validation rules for the natural-key columns

Two natural-key columns:
- `commit_sha` — 40-character hex, UNIQUE within engagement.
- `commit_repository` — non-empty TEXT, no enum constraint (new repos added as encountered).

For `commit_sha`, validation: length exactly 40, character set `[0-9a-f]`, lowercase enforced. Specify in section 3.2 validation column.

For `commit_repository`, validation: non-empty, trimmed, no whitespace or path separators in the value (repository name only, not a path). Specify likewise.

Confirm the rules; the conversation may strengthen them based on observed CBM-side or crmbuilder-side edge cases.

### Question 5 — Relationship rendering for `commit_conversation_id`

The methodology specifies `commit.commit_conversation_id` as the FK that ties a commit to its producing conversation. Per `governance-entity-schema-spec-guide.md` §3.3, foreign-key fields are mechanism (1) and live in section 3.2.4 (Relationship fields), not as a relationship_kind entry.

But: the commit-to-conversation relationship is also walkable via the `refs` table in some queries (the audit chain in methodology §6 walks `refs` to find the resolves/addresses edges, then joins to commits via `commit_conversation_id` — the join goes through the FK, not through a `refs` edge).

Question: does any query benefit from a typed `commit_belongs_to_conversation` relationship_kind in addition to the FK? Reasoning: most likely no — the FK is sufficient for the join, and adding a redundant edge doubles write cost on every commit ingestion. Decision per the DEC-133 frequency-justified deferral test: don't add the typed kind unless a query pattern needs it.

Confirm: FK only; no typed `refs` kind for the commit-to-conversation relationship.

### Question 6 — Acceptance criteria specific to commit

Every schema spec carries acceptance criteria in its section 7. For the commit spec, candidate criteria:

- An apply that POSTs a `commits` array entry creates a `commit` row whose every field matches the entry.
- A POST with a duplicate `commit_sha` returns HTTP 409 and does not create a row.
- A POST with a `commit_sha` of incorrect length or character set returns HTTP 422.
- `GET /commits/by-sha/<sha>` returns the single matching row for a full SHA; returns the single matching row for an unambiguous prefix SHA; returns HTTP 409 with candidate list for an ambiguous prefix SHA; returns HTTP 404 for a SHA with no matches.
- A DELETE soft-deletes the row; subsequent GET returns 404; GET with `?include_deleted=true` returns the row with `commit_deleted_at` populated.
- The conversation's `GET /conversations/<id>/commits` derived endpoint (if added — see Question 7) returns all commits whose `commit_conversation_id` matches.

Surface any missing criteria; the conversation may add coverage gaps the commit-specific scenarios reveal.

### Question 7 — Derived endpoints

Beyond the standard set, are any derived endpoints worth recommending in section 5 of the spec?

Candidate: `GET /conversations/{conversation_identifier}/commits` — list all commits for a conversation. Useful for the audit chain queries in methodology §6. Could be done as `GET /commits?commit_conversation_id=<id>` against the standard list endpoint; the derived endpoint just provides a more discoverable URL.

Recommended: leave to PI-029 build prompts. The schema spec names the capability; the build conversation decides the URL shape.

---

## Deliverable

One file:

**`PRDs/product/crmbuilder-v2/governance-schema-specs/commit.md`** — the complete schema specification per the seven-section format in `governance-entity-schema-spec-guide.md`. Sections:

1. **Identity** — entity type name, display names, identifier prefix and format, identifier assignment.
2. **Fields** — the fourteen v0.8 fields plus the three governance-standard timestamps, organized by category (identity, content, classification, relationship, timestamp). Includes the explicit "deferred to v0.9" list per the methodology.
3. **Relationships** — `commit_conversation_id` as foreign-key (mechanism 1); no new typed relationship_kind vocabulary; cross-references to the three new kinds (`resolves`, `addresses`, `blocked_by`) that the build-planning work (PI-029) consolidates.
4. **Lifecycle** — documentary posture; no statuses; soft-delete with restore.
5. **REST endpoints** — standard set plus `GET /commits/by-sha/{sha}`.
6. **UI** — Commits panel sketch (master/detail; one Repository filter combo; sortable Committed-At column). Final layout details deferred to PI-031.
7. **Acceptance criteria** — per Question 6 above.

---

## Read list (required before drafting)

1. **`PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md`** v1.0 — the authoritative source for what this spec implements. Read first.
2. **`PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md`** v1.0 — the schema-spec template.
3. **`PRDs/product/crmbuilder-v2/governance-schema-specs/work_ticket.md`** v1.0 — closest existing precedent (closed-enum classification, documentary cross-references, similar audit-grain role).
4. **`PRDs/product/crmbuilder-v2/governance-schema-specs/reference_book.md`** v1.0 — documentary-shaped lifecycle precedent (DEC-137 source).
5. **`crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`** — the existing `REFERENCE_RELATIONSHIPS`, `ENTITY_TYPES`, and `_kinds_for_pair`. The commit spec adds `commit` to `ENTITY_TYPES`; the methodology's three new kinds are added by PI-029, not this conversation.

Optional but useful:

6. **`PRDs/product/crmbuilder-v2/close-out-payloads/ses_061.json`** — the SES-061 close-out payload that authors this kickoff (the predecessor conversation's record).
7. **The five other governance-schema-specs/*.md** — for cross-spec precedent context.

---

## Close-out expectations for the PI-028 conversation

The close-out payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_061.json` (subject to availability check at apply time) should contain:

- **1 session record** (SES-061 or next available) — the commit schema-design conversation.
- **Decisions** — one per question in this kickoff that was genuinely consequential. Estimate: 3–6 decisions (Questions 1, 2, possibly 3, 5, 7). Question 4 is straightforward and likely doesn't warrant a decision record; Question 6 emerges as the acceptance-criteria block in the spec itself, not as a separate decision.
- **Planning items** — possibly one if a downstream gap surfaces; otherwise zero.
- **References** — one `decided_in` per decision; `is_about` from SES-061 to PI-028; `is_about` from the spec file (as a reference_book record, authored separately by PI-033 in its reference_book back-fill, NOT in this conversation) to the methodology document.
- **Artifacts produced** — `governance-schema-specs/commit.md` (the spec).
- **In flight at end** — PI-029 schema migration conversation queued, opening against the methodology document and the commit spec together.

Per `methodology-code-change-lifecycle.md` §9, PI-028 itself cannot be resolved in this close-out — the `resolves_planning_items` payload section does not yet ship. PI-028 stays `Open` and is resolved retroactively by PI-033.

---

## What is explicitly NOT in scope for this conversation

- The Alembic migration that adds the `commits` table (PI-029).
- The vocab.py update that adds the three new relationship_kinds (PI-029).
- The close-out payload schema extension and apply script update (PI-030).
- The commit ingestion helper (PI-030).
- The Commits panel UI build (PI-031).
- Back-fill of historical commits (PI-033).

The schema spec names what these downstream planning items must produce; it does not produce them. If a schema-level question arises that this conversation cannot answer abstractly, name it as a follow-on decision for PI-029 (build planning) rather than over-reaching here.

---

## Additional deliverable at close

This conversation produces only the schema spec. The next conversation in the workstream is PI-029's schema migration work, which is structurally a Claude Code execution rather than a Claude.ai conversation. Its kickoff is a `CLAUDE-CODE-PROMPT-*.md` file authored by the conversation closer of *this* conversation (PI-028) as part of its close-out — specifically:

**`PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-029-A-commits-table-and-vocab.md`** — the first prompt in a multi-prompt PI-029 series. Subsequent prompts (B, C, ...) emerge from the build-planning approach taken in PI-028's close-out.

If the PI-028 conversation does not have time-and-context budget to author the PI-029 Prompt A in the same session, defer it to a fresh planning conversation. The choice is the conversation's; record it in passing.
