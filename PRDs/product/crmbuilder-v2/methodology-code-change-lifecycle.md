# Code Change Lifecycle — Methodology

**Last Updated:** 05-23-26 21:00
**Status:** Draft v1.0
**Workstream:** Code Change Lifecycle (established in SES-057)
**Produced by:** SES-061 (PI-027 methodology drafting conversation)
**Resolves the design questions for:** PI-028 commit schema, PI-029 access layer and API, PI-030 close-out payload and apply, PI-031 UI, PI-032 methodology rollout, PI-033 back-fill

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-23-26 21:00 | Doug Bower / Claude (SES-061) | Initial draft. Settles eight design decisions (DEC-183 through DEC-190) deferred by the SES-057 workstream-establishing conversation: commit identifier strategy, granularity of resolves edges, commit ingestion trigger, commit record fields, multi-repo and multi-engagement scoping, typed `addresses` relationship_kind, work_ticket authoring rule scope, and the direction/name of the `blocks` relationship_kind (now `blocked_by`). Names PI-028 through PI-033 as the downstream planning items that consume this methodology. PI-027 itself stays Open at this conversation's close — the `resolves_planning_items` payload section this methodology specifies does not yet ship, so this methodology's own planning item will be resolved retroactively by PI-033. |

---

## Change Log

**Version 1.0 (05-23-26 21:00):** Initial creation. Defines the seven-stage code-change-lifecycle chain that connects a planning item, through the work that addresses it, through the commits that deliver it, to the resolution declaration. Introduces three new relationship_kinds (`resolves`, `addresses`, `blocked_by`), one renamed kind (`blocks` → `blocked_by`), and one new governance entity type (`commit` with identifier prefix `CM-NNNN`). Specifies four new close-out payload sections (`commits`, `work_tickets`, `resolves_planning_items`, `addresses_planning_items`). States the broad work_ticket authoring rule (every single-use seed document committed to a repo is a work_ticket record, classified by the four-value kind enum). Specifies the apply-time payload-declared, helper-enumerated commit ingestion model. Specifies the conversation-scoped commits model (commits live in their conversation's engagement database regardless of physical repo; `repository` column distinguishes). Specifies the audit query patterns the chain supports. Documents the back-fill posture for pre-methodology records (PI-033 scope: ~220 historical work_tickets, several hundred historical commits, retroactive `resolves` for previously-Resolved planning items, `is_about` → `addresses` migration on v0.7 work_ticket edges, two `blocks` → `blocked_by` row migrations). Names known gaps: until PI-030 ships, the close-out payload format does not yet support the four new sections, so this methodology is normative-but-not-yet-implemented at v1.0 authoring time.

---

## 1. Purpose and Scope

The **Code Change Lifecycle** methodology defines the seven-stage chain that connects a planning item, through the work that addresses it, through the commits that deliver it, to the resolution declaration. Each stage is implemented as governance data in V2's per-engagement SQLite databases. Every transition is recorded; every record is queryable; the full chain is a single SQL join.

The methodology exists because the diagnostic in SES-057 surfaced that only one of 26 `planning_items` in the CRMBUILDER engagement database showed status `Resolved`, and that one was achieved via a manual status flip with no companion governance edge. The audit chain from a planning item through its planning conversation, work tickets, execution conversation, commits, and resolution was not machine-readable. This methodology specifies the model that closes the gap.

**In scope:**
- Authoring rules for `work_ticket`, `conversation`, `commit`, `resolves`, and `addresses` records and edges.
- Close-out payload format extensions for the new entities and edges.
- Vocabulary additions: relationship_kinds `resolves`, `addresses`; the renamed kind `blocked_by`; the new entity type `commit`; identifier convention `CM-NNNN`.
- Audit query patterns that walk the full chain.
- Back-fill posture for pre-methodology records.

**Out of scope:**
- The Document Production Process methodology that governs client-facing CRM implementation work (separate, methodology-agnostic body of process).
- Workstreams that produce no commits (purely planning or diagnostic conversations — they participate in the chain through their decisions and references, just not through commits).
- Cross-engagement commit queries beyond the per-engagement boundary established in section 3 (decision DEC-187, conversation-scoped commits).

---

## 2. The Seven-Stage Lifecycle

Every workstream traverses some or all of these stages. Small workstreams collapse stages (e.g., the planning conversation and execution conversation are the same conversation). Most workstreams span multiple conversations through stages 2 through 4.

### Stage 1 — Planning item motivates the work

A `planning_item` record (PI-NNN, status `Open`) declares a unit of work to be done. It carries a title, a description, and zero or more `blocked_by` edges to prerequisite planning items. The planning item is the durable representation of intent — what work needs to happen.

Planning items are authored by prior conversations or by workstream-establishing kickoffs. They live in the engagement database where the work happens.

### Stage 2 — Planning conversation produces decisions and work_tickets

A Claude.ai conversation opens against a kickoff document (which is itself a work_ticket — see Stage 3). The conversation produces:

- One or more `decision` records (DEC-NNN) capturing design choices.
- Zero or more `planning_item` records authoring downstream work.
- Zero or more `work_ticket` records authoring single-use seed documents that future conversations will consume.
- One `session` record (SES-NNN) summarizing the conversation.

The conversation's close-out payload records all of the above. After apply, the new work_tickets are status `ready` (queued for consumption).

### Stage 3 — Execution conversation opens against a work_ticket

A subsequent Claude.ai or Claude Code conversation opens against a `ready` work_ticket. The act of opening creates an inbound `conversation_opens_against_work_ticket` edge (declared from the conversation side per the v0.7 conversation schema) and atomically transitions the work_ticket's status to `consumed`. Each work_ticket can be consumed at most once, per the work_ticket spec's terminal-state-with-edge rule.

### Stage 4 — Execution conversation produces commits

The conversation makes one or more git commits in one or more repositories. Commits exist in git first; their governance records are created at Stage 5 (close-out).

The conversation's authoring activity in this stage is normal development work: edit files, commit, push (in the sandbox; commit, leave-for-Doug-to-push in Claude Code per the working conventions in repo `CLAUDE.md`). No special bookkeeping yet.

### Stage 5 — Close-out payload records resolves edges, work_ticket consumptions, and commits

At session close, the conversation produces its close-out payload. Four new top-level sections this methodology adds:

- **`commits`** — enumerated by the helper (`tools/governance/enumerate_commits.py` or an inline `git log` snippet) at close-out authoring time. One entry per commit in the range `<last-ingested-sha-per-repo>..<current-HEAD-per-repo>` for each repo this conversation touched.
- **`work_tickets`** — entries for any new work_ticket records authored in this conversation (kickoffs, Claude Code prompts, session prompts, update prompts committed in this session). Each entry carries title, description, file path, kind, status, and the planning item it addresses (when known).
- **`resolves_planning_items`** — entries declaring "this conversation resolves PI-NNN." Each entry generates a `conversation → resolves → planning_item` edge at apply time AND flips the planning item's status from `Open` to `Resolved` atomically.
- **`addresses_planning_items`** — entries declaring "this conversation contributed to PI-NNN but did not resolve it." Each entry generates a `conversation → addresses → planning_item` edge. Used for multi-conversation work.

### Stage 6 — Apply transaction lands the records

`apply_close_out.py` POSTs the entries in fixed order, in one logical transaction. The deposit_event row at the end records the apply with its `wrote_record` edges to every record landed. Standard idempotency, error tolerance, and snapshot regeneration per the existing v0.7 apply pattern. The apply script also handles the planning-item status transitions (via the `resolves` edges) and the work_ticket status transitions (via the existing `conversation_opens_against_work_ticket` edges from any newly-opened conversation records).

### Stage 7 — Downstream queries walk the chain

Any future query against the engagement database walks from any node in the chain to any other. Section 6 names the canonical query patterns. The audit chain from "PI-NNN was resolved by which commits in which repo on which date" reduces to one SQL join across `planning_items`, `refs`, `commits`, and (optionally) `conversations`.

---

## 3. Vocabulary Additions

### 3.1 New entity type: `commit`

**Identifier shape:** `CM-NNNN` (four-digit zero-padded sequence). Client-side assignment per the prefixed-identifier convention documented in repo `CLAUDE.md`. Four digits chosen to accommodate the high commit volume the system will accumulate (REF uses four digits for the same reason).

**v0.8 fields:**

| Field | Type | Notes |
|-------|------|-------|
| `commit_identifier` | TEXT | `CM-NNNN`; unique within engagement |
| `commit_sha` | TEXT | full 40-character SHA; UNIQUE INDEX |
| `commit_message_first_line` | TEXT | for compact display in lists and prose |
| `commit_message_full` | TEXT | complete commit message body |
| `commit_author_name` | TEXT | from `git log --format=%an` |
| `commit_author_email` | TEXT | from `%ae` |
| `commit_committed_at` | TIMESTAMP | from `%cI` (committer date — chronological order in the repo) |
| `commit_repository` | TEXT | e.g., `crmbuilder`, `ClevelandBusinessMentoring`; no enum constraint |
| `commit_branch` | TEXT | branch observed at ingestion time; almost always `main` |
| `commit_parent_shas` | JSON | array of 0/1/2 parent SHAs (0 for initial commit, 1 for normal, 2 for merge) |
| `commit_files_changed_count` | INTEGER | from `git diff-tree --no-commit-id --name-only -r <sha> \| wc -l` |
| `commit_conversation_id` | TEXT | FK to `conversation.conversation_identifier`; the conversation that produced this commit |
| `commit_created_at` | TIMESTAMP | governance standard |
| `commit_updated_at` | TIMESTAMP | governance standard |
| `commit_deleted_at` | TIMESTAMP | nullable; soft-delete per V2 base behavior |

**Deferred to v0.9 or later, pending real-use signal:**
- `commit_files_changed_paths` — separate table when needed; `git show <sha>` provides on demand.
- `commit_signed_by` — Doug's commits aren't currently signed.
- `commit_committer_name`, `commit_committer_email` — practically identical to author in this workflow.
- `commit_message_trailers` — parsed `Co-authored-by`, `Signed-off-by`, etc.; not currently used.

**REST endpoints (per the v0.7 governance pattern):**
- `GET /commits` — list with filtering, pagination, sort
- `GET /commits/{identifier}` — by `CM-NNNN`
- `GET /commits/by-sha/{sha}` — by full or prefix SHA; prefix matches against the index; ambiguity returns HTTP 409 with the candidate list
- `POST /commits` — create (client-side identifier expected in body)
- `DELETE /commits/{identifier}` — soft delete

**UI:** a Commits panel under the Governance sidebar group in the V2 desktop UI, with master/detail layout following the existing v0.7 governance panels (PI-031 scope).

### 3.2 New relationship_kind: `resolves`

**Admissible pair:** `(conversation, planning_item)`.

**Semantics:** declares "this conversation completed the work authored by the planning item." Triggers the planning item's status transition `Open` → `Resolved` at apply time, in the same atomic transaction as the edge insertion.

**Cardinality:** unique on `(target_type, target_id)` filtered by `relationship_kind='resolves'`. A planning item can be resolved by at most one conversation. (If a regression ever requires re-resolving a planning item, lift the unique constraint then.)

### 3.3 New relationship_kind: `addresses`

**Admissible pairs:**
- `(work_ticket, planning_item)` — declares "this work_ticket is a unit of work created to address this planning item." Authored at work_ticket creation time.
- `(conversation, planning_item)` — declares "this conversation contributed to this planning item but did not resolve it." Used for multi-conversation work where a non-terminal conversation does some of the work.

**Cardinality:** many-to-many on both sides. A work_ticket can address multiple planning items (cross-cutting tickets). A planning item can be addressed by multiple work_tickets (decomposed work). A conversation can address multiple planning items. A planning item can be addressed by multiple non-terminal conversations.

### 3.4 Renamed kind: `blocks` → `blocked_by`

**Admissible pair:** `(planning_item, planning_item)`.

**Semantics:** source planning item cannot proceed until target planning item reaches `Resolved` status. Reads naturally in English: "`PI-Y` is blocked_by `PI-X`" — `PI-Y` is the dependent, `PI-X` is the prerequisite.

**Migration:** the existing two `blocks` rows (`REF-0357` and `REF-0358`) keep their source/target endpoints unchanged. Only the `relationship_kind` value migrates from `'blocks'` to `'blocked_by'`. Folded into PI-029's Alembic migration.

### 3.5 Identifier conventions reminder

All new entity types follow the existing prefixed-identifier convention documented in repo `CLAUDE.md`: client-side assignment via list-and-increment; apply scripts compute identifiers before POSTing; API does not auto-assign for prefixed-identifier entity types. The commit entity adds `CM-NNNN` to the prefix namespace.

---

## 4. Close-out Payload Format Extension

The v0.7 close-out payload structure (one session record, decisions array, planning_items array, references array) extends with four new top-level array sections. The apply script processes the sections in fixed order to honor dependency constraints:

```
session → work_tickets → planning_items → commits → decisions
       → references → resolves_planning_items → addresses_planning_items
```

Rationale for the order: work_tickets must exist before they can be referenced from is_about/addresses/opens-against edges; commits must exist before resolves/addresses edges can be authored against the conversation that produced them; resolves edges flip planning_item status, so the planning item record must exist first.

### 4.1 `commits` section

```json
"commits": [
  {
    "commit_sha": "a1b2c3d4e5f6...",
    "commit_message_first_line": "v2: add commit entity schema spec",
    "commit_message_full": "v2: add commit entity schema spec\n\nFollows the seven-section governance schema spec format. Resolves the design questions deferred by the SES-061 methodology conversation. Foundation for the v0.8 commit ingestion workstream.",
    "commit_author_name": "Doug Bower",
    "commit_author_email": "doug@dougbower.com",
    "commit_committed_at": "2026-05-23T20:45:12-04:00",
    "commit_repository": "crmbuilder",
    "commit_branch": "main",
    "commit_parent_shas": ["f9e8d7c6..."],
    "commit_files_changed_count": 1
  }
]
```

Each entry generates one `commit` record. `CM-NNNN` is assigned client-side at apply time by the apply script (incrementing the engagement's commit identifier head). The commit's `commit_conversation_id` is set to the close-out's owning conversation; no explicit field needed in the payload entry.

### 4.2 `work_tickets` section

```json
"work_tickets": [
  {
    "work_ticket_title": "Commit entity schema specification",
    "work_ticket_description": "Kickoff for the PI-028 conversation that produces the commit entity schema spec in the standard seven-section governance schema spec format.",
    "work_ticket_file_path": "PRDs/product/crmbuilder-v2/schema-design-kickoff-commit.md",
    "work_ticket_kind": "kickoff_prompt",
    "work_ticket_status": "ready",
    "addresses_planning_item": "PI-028"
  }
]
```

Each entry generates one `work_ticket` record plus the `addresses` edge to the named planning item.

### 4.3 `resolves_planning_items` section

```json
"resolves_planning_items": [
  {
    "planning_item_identifier": "PI-027"
  }
]
```

Each entry generates one `conversation → resolves → planning_item` edge AND flips the planning item's status from `Open` to `Resolved` in the same atomic transaction. The conversation is implicit (the close-out's owning session/conversation). No `resolution_reference` field is needed — the edge itself is the reference.

### 4.4 `addresses_planning_items` section

```json
"addresses_planning_items": [
  {
    "planning_item_identifier": "PI-028"
  }
]
```

For non-terminal contribution. Generates `conversation → addresses → planning_item` edges. No status flip.

### 4.5 Idempotency rules

- **Re-applying the same payload:** the second apply rejects on each unique-constraint violation (e.g., `commit_sha` already exists) and reports the conflict in the deposit_event's `error_info`. Per-record error tolerance allows the apply to continue for non-conflicting records.
- **A commit already ingested by a previous close-out:** unique on `commit_sha` rejects with HTTP 409; the conversation that previously ingested the commit retains ownership. The current close-out's commits section should not have included it — usually indicates a bug in the helper's "since SHA" calculation.
- **A planning item already resolved:** unique on `(target_type, target_id)` for `resolves` rejects the duplicate edge with HTTP 409. The planning item's status remains `Resolved` (it cannot be resolved twice).

---

## 5. Authoring Rules

### 5.1 When is a work_ticket born?

Every single-use seed document committed to either repo is born as a `work_ticket` record in the same close-out payload that produces the commit. Classification by filename pattern:

| Pattern | `work_ticket_kind` |
|---------|---------------------|
| `CLAUDE-CODE-PROMPT-*.md` | `claude_code_prompt` |
| `*-kickoff*.md`, `*-planning-prompt*.md` | `kickoff_prompt` |
| `SESSION-PROMPT-*`, `UPDATE-PROMPT-*` | `ad_hoc_prompt` |
| (other one-conversation seed) | `other` |

The work_ticket's `addresses_planning_item` (when known) names the planning item the conversation will address. For kickoffs that establish a workstream (no specific PI yet), the addresses edge is omitted; the relationship is captured later when the workstream's planning items are authored.

### 5.2 When is a work_ticket consumed?

When a conversation opens against the work_ticket — i.e., when the seed file is the kickoff of a new Claude.ai or Claude Code conversation. The conversation's close-out payload declares the consumption via the existing `conversation_opens_against_work_ticket` edge (in the conversation's section of the payload), and the work_ticket's status transitions to `consumed` atomically in the apply transaction.

### 5.3 When is a work_ticket superseded?

When a kickoff is rewritten enough to warrant a new ticket with its own identifier — the prior ticket is marked `superseded` and points at the successor via the existing `supersedes` reference kind. Standard per the work_ticket spec.

### 5.4 When is a planning_item resolved?

When a conversation's `resolves_planning_items` section names it. Apply script generates the edge AND flips status in one transaction. **Manual status flips outside this mechanism are forbidden** — they leave the `resolves` edge missing and break the audit chain. The diagnostic script can flag any planning item in `Resolved` status without a corresponding `resolves` edge as a data-integrity violation.

### 5.5 When does a commit get ingested?

At close-out authoring time. The helper enumerates commits in the range `<last-ingested-sha-per-repo>..<current-HEAD-per-repo>` for each repo the conversation touched. The "last-ingested SHA" is derived per repo by querying the most recent `commit` record's `commit_sha` for that repository (`GET /commits?commit_repository=<name>&sort=commit_committed_at:desc&limit=1`). The conversation's close-out payload includes the resulting `commits` section. Apply POSTs each commit.

### 5.6 Attribution

Every commit in the enumerated range is attributed to the close-out's conversation, regardless of who authored it physically. Manual commits Doug made between the previous close-out and this one are rolled into this conversation's set. The simplification is acceptable for the audit-trail use case; if attribution discipline becomes a problem, a future v0.9 adds a `commit_author_kind` field (`claude_ai` / `claude_code` / `manual`).

### 5.7 Multi-conversation work

When work on a planning item spans multiple conversations and only the final conversation declares resolution:

- Each non-terminal conversation declares `addresses_planning_items` for that planning item — non-resolving contribution.
- The final conversation declares `resolves_planning_items` — terminal contribution; status flips.

Audit query "every commit that contributed to PI-NNN" walks both `resolves` and `addresses` edges from `conversation → planning_item`, then joins to `commits` via `commit_conversation_id`.

---

## 6. Audit Query Patterns

### 6.1 Given a planning item, list every commit that contributed to its resolution

```sql
SELECT c.commit_identifier, c.commit_sha, c.commit_message_first_line,
       c.commit_repository, c.commit_committed_at
FROM commits c
JOIN refs r ON r.source_id = c.commit_conversation_id
            AND r.source_type = 'conversation'
WHERE r.target_id = 'PI-027'
  AND r.target_type = 'planning_item'
  AND r.relationship_kind IN ('resolves', 'addresses')
ORDER BY c.commit_committed_at ASC;
```

### 6.2 Given a commit SHA, list every planning_item it relates to plus the planning conversation that motivated each

```sql
WITH commit_row AS (
  SELECT * FROM commits WHERE commit_sha LIKE 'a1b2c3d4%' LIMIT 1
),
related AS (
  SELECT r.target_id AS pi_id, r.relationship_kind
  FROM refs r, commit_row c
  WHERE r.source_id = c.commit_conversation_id
    AND r.source_type = 'conversation'
    AND r.target_type = 'planning_item'
    AND r.relationship_kind IN ('resolves', 'addresses')
)
SELECT related.pi_id,
       related.relationship_kind,
       pi.planning_item_title,
       authored_in.source_id AS authored_in_session
FROM related
JOIN planning_items pi ON pi.planning_item_identifier = related.pi_id
LEFT JOIN refs authored_in
  ON authored_in.target_id = related.pi_id
  AND authored_in.target_type = 'planning_item'
  AND authored_in.source_type = 'session'
  AND authored_in.relationship_kind = 'is_about';
```

### 6.3 Given a workstream, list every commit it produced

Walk: workstream → conversations (via `conversation_belongs_to_workstream`) → commits (via `commit_conversation_id`).

```sql
SELECT c.commit_identifier, c.commit_sha, c.commit_message_first_line,
       c.commit_repository, conv.conversation_identifier
FROM commits c
JOIN conversations conv ON conv.conversation_identifier = c.commit_conversation_id
JOIN refs r ON r.source_id = conv.conversation_identifier
            AND r.source_type = 'conversation'
            AND r.relationship_kind = 'conversation_belongs_to_workstream'
WHERE r.target_id = 'WS-002'
ORDER BY c.commit_committed_at ASC;
```

### 6.4 Find planning_items in indeterminate state

Resolved-status without a `resolves` edge (data integrity violation):
```sql
SELECT pi.planning_item_identifier, pi.planning_item_title
FROM planning_items pi
LEFT JOIN refs r ON r.target_id = pi.planning_item_identifier
                 AND r.target_type = 'planning_item'
                 AND r.relationship_kind = 'resolves'
WHERE pi.planning_item_status = 'Resolved' AND r.id IS NULL;
```

Open-status with `addresses` edges (work in progress, decomposed):
```sql
SELECT pi.planning_item_identifier,
       pi.planning_item_title,
       COUNT(r.id) AS contributing_conversations
FROM planning_items pi
JOIN refs r ON r.target_id = pi.planning_item_identifier
            AND r.target_type = 'planning_item'
            AND r.relationship_kind = 'addresses'
            AND r.source_type = 'conversation'
WHERE pi.planning_item_status = 'Open'
GROUP BY pi.planning_item_identifier, pi.planning_item_title;
```

### 6.5 Find planning_items addressed by a work_ticket

```sql
SELECT pi.planning_item_identifier, pi.planning_item_title, pi.planning_item_status
FROM planning_items pi
JOIN refs r ON r.target_id = pi.planning_item_identifier
            AND r.target_type = 'planning_item'
            AND r.relationship_kind = 'addresses'
            AND r.source_type = 'work_ticket'
WHERE r.source_id = 'WT-012';
```

---

## 7. Migration and Back-fill Posture

### 7.1 What PI-033 will retroactively author

**Historical work_tickets** — one per existing seed file in both repos. Filename pattern classifies by kind. Approximately:
- ~168 `claude_code_prompt`-kind (every `CLAUDE-CODE-PROMPT-*.md` under `PRDs/`)
- ~27 `kickoff_prompt`-kind (every `*-kickoff*.md` and `*-planning-prompt*.md`)
- ~26 `ad_hoc_prompt`-kind (`SESSION-PROMPT-*`, `UPDATE-PROMPT-*`)
- ~221 records total

Each linked to its consuming conversation via `conversation_opens_against_work_ticket` where derivable from filename conventions; some require per-record judgment.

**Historical commits** — every commit in both repos from the start of the repository through the back-fill date. Each attributed to a historical conversation (most can be derived from commit message prefix conventions, e.g. `v2:` for v2 work; cross-checked against close-out apply commit dates). Approximately several hundred commits across the two repos.

**Historical `resolves` edges** — for planning items already in `Resolved` status (today: PI-022 only, achieved via manual flip), retroactively author the `resolves` edge to the resolving conversation. From this point forward, manual flips are forbidden.

**`is_about` → `addresses` migration** — the v0.7 back-fill's eight `work_ticket → planning_item` `is_about` edges migrate kind value to `addresses`. Endpoints unchanged.

**`blocks` → `blocked_by` rename** — the two existing `blocks` rows (`REF-0357`, `REF-0358`) migrate kind value. Endpoints unchanged. Folded into the same Alembic migration as the relationship_kind CHECK constraint update.

### 7.2 What stays as historical noise

- Pre-methodology session prompts and kickoffs whose consuming conversation can no longer be unambiguously identified: authored as work_tickets in status `consumed` with a best-guess conversation link, or status `cancelled` if no consumer is identifiable.
- Commits that pre-date the methodology and made before any explicit close-out: rolled into the chronologically-nearest applied conversation, even if the commit was a hand-typed fix Doug made between conversations. The simplification is accepted for back-fill scope.

### 7.3 PI-029's consolidated Alembic migration

PI-029's schema work delivers a single Alembic migration that:
1. Adds the `commits` table with the v0.8 fields above.
2. Drops the existing `refs.relationship_kind` CHECK constraint; adds `'resolves'`, `'addresses'`, `'blocked_by'` to the allowed set; removes `'blocks'` from the allowed set; re-adds the constraint.
3. `UPDATE refs SET relationship_kind='blocked_by' WHERE relationship_kind='blocks'` — migrates the two existing rows.
4. Updates `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`: adds the kinds to `REFERENCE_RELATIONSHIPS`; updates `_kinds_for_pair` for `(conversation, planning_item)`, `(work_ticket, planning_item)`, and `(planning_item, planning_item)`.
5. Adds entity-type registration for `commit` in `ENTITY_TYPES` (per CLAUDE.md line 58).

---

## 8. Known Gaps and Downstream Dependencies

This methodology specifies a model that the current schema does not yet implement. The downstream planning items close the gaps:

| Planning item | Delivers |
|---------------|----------|
| PI-028 | Commit entity schema spec in the standard seven-section governance schema spec format |
| PI-029 | Schema migration: new `commits` table; vocab.py updates; Alembic migration adding kinds; renaming `blocks` to `blocked_by` |
| PI-030 | Close-out payload schema extensions for the four new sections; `apply_close_out.py` updates; `enumerate_commits.py` helper |
| PI-031 | UI updates: Commits panel under Governance sidebar; planning_item detail view shows `resolves` and `addresses` edges |
| PI-032 | Methodology rollout: updated close-out template; work_ticket authoring rule documented in repo CLAUDE.md; methodology document linked |
| PI-033 | Back-fill of historical work_tickets, historical commits, retroactive `resolves` edges, `is_about` → `addresses` migration, and `blocks` → `blocked_by` rename |

Until PI-030 ships, this methodology document is **normative-but-not-yet-implemented**. Close-out payloads in the interim continue using the v0.7 format. The four new sections (`commits`, `work_tickets`, `resolves_planning_items`, `addresses_planning_items`) are not yet recognized by the apply script and will cause apply failures if included in a payload before PI-030 lands.

---

## 9. PI-027 Resolution Posture

The kickoff for this conversation flagged that PI-027 (this methodology document) cannot be properly resolved in its own close-out — the `resolves_planning_items` payload section the methodology specifies does not yet exist, so the methodology's own planning item cannot use it. Two options were named: (a) defer (leave PI-027 Open and let PI-033 resolve it retroactively), or (b) hand-flip PI-027's status to `Resolved` via direct API after this close-out applies.

**This methodology adopts option (a).** PI-027 stays `Open` at the end of this conversation's close-out. PI-033's back-fill resolves it once the `resolves_planning_items` payload section ships in PI-030. The honesty of "the methodology specifies a model the schema does not yet support" matters more than the visual neatness of a flipped status. Future readers walking the chain will see PI-027 transition to `Resolved` chronologically alongside every other historical planning item PI-033 retroactively resolves.

The diagnostic that motivated this workstream — "PI-022 is the only Resolved planning item, and it has no `resolves` edge" — would have been impossible to detect under option (b) for PI-027. Adopting (a) keeps the same diagnostic signal usable through this conversation's tail.
