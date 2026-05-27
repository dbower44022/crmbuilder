# CLAUDE-CODE-PROMPT — apply close-out SES-099 (PI-073 close-out — Session/Conversation entity redesign complete; resolves PI-073)

**Last Updated:** 05-27-26
**Operating mode:** DETAIL
**Series:** PI-073 redesign workstream — Phase G (final close-out)
**Slice:** Rebase pi-073-redesign onto main, resolve conflicts, merge, run the data migration on main's DB, apply this close-out, push.
**Status:** **NOT YET RUNNABLE.** The pi-073-redesign branch's commits are local; this prompt cannot run until the branch is rebased, merged, the schema migrations apply, and the data migration script runs on main's DB. The order of operations matters — see the apply pipeline below.

> **Why this session record exists:** Phase G closes the eight-phase PI-073 redesign workstream. The session captures the audit + documentation-propagation conversation conducted on the pi-073-redesign branch; the resolves_planning_items section flips PI-073 status Open → Resolved. The eight phase commits (init + A through F) are recorded in the payload's commits[] section so the new model has full provenance in the governance graph.
>
> **Identifier head capture** (per DEC-300, against main's live DB at branch-cut snapshot time): SES-099, CONV-069 (pre-migration), DEC-319, PI-094, WT-056. Because the migration retires the CONV-NNN-as-conversation semantic, the next conversation identifier post-merge is CNV-001 (the new prefix per conversation-v2.md §3.1). DEC-314 (active since SES-095 on the original main) remains the architectural authority — no new DEC is authored in Phase G.

---

## Net Effect (after the full apply pipeline below completes)

This close-out applied via apply_close_out.py creates:

- SES-099 (session, status=Complete) — Phase G audit + documentation propagation. medium=chat, medium_metadata={"chat_platform": "claude_code"}.
- CNV-001 (conversation, status=complete) — first conversation under the new CNV-NNN prefix on main; belongs to SES-099 via `conversation_belongs_to_session` edge.
- 8 commit rows recording the PI-073 phase commits (d8b2d37 init, 6cd62ca Phase A, bdce21d Phase B.1, 63562d8 Phase B.2, 313b8e0 Phase C, 9898870 Phase D, 5b46e92 Phase E, f5dfda5 Phase F). Each row's `commit_session_id` is auto-populated to SES-099 by the apply script's `_shape_commit` per the Phase C update.
- 1 session_belongs_to_workstream edge (SES-099 → WS-011)
- 1 conversation_belongs_to_session edge (CNV-001 → SES-099)
- 1 `resolves` edge (CNV-001 → PI-073) auto-generated from `resolves_planning_items` — flips PI-073 Open → Resolved atomically.
- close_out_payload COP-099 + deposit_event DEP-NNN (lazy-created).

No decisions, planning items, work tickets, or other reference edges authored here.

---

## Apply pipeline (multi-step; do these in order)

### Step 1 — Rebase pi-073-redesign onto current main

```bash
cd ~/Dropbox/Projects/crmbuilder
git fetch origin
git checkout pi-073-redesign
git rebase main
```

**Expected conflicts** (three, documented at the bottom of every phase commit message):

1. **Migration filename collision.** My branch has `crmbuilder-v2/migrations/versions/0020_pi_073_session_conversation_redesign.py`; main has `0020_pi_074_executive_summary.py` and possibly later 0021_* / 0022_* migrations from PI-091/092/093. **Resolution:** Rename my migration file to the next available number revising main's head (likely `0023_pi_073_*` depending on what's on main). Update the file's `revision` constant + `down_revision` constant. Verify with `alembic heads` and `alembic history` post-rename.

2. **Session model class missing `session_executive_summary`.** Main's PI-074 commit `6ae82c3` added an `executive_summary` TEXT column to the legacy sessions table. The Phase A migration in my branch renames that table to `legacy_sessions`, carrying the column. The new sessions table in my branch's Phase A migration does NOT include a parallel column. **Resolution:** add a `session_executive_summary: Mapped[str | None] = mapped_column(Text, nullable=True)` field to the new `Session` ORM class (Phase B.1 commit) AND extend Phase A's migration to add the column to the new sessions table. Same treatment for the new `Conversation` class (call it `conversation_executive_summary`). Update SessionCreateIn / SessionPatchIn / SessionReplaceIn schemas. Update apply_close_out.py if it touches the field. Update the Phase F data migration script's INSERT statement to preserve the legacy executive_summary value during the conv→session migration.

3. **Desktop UI conflicts on `panels/sessions.py` and possibly `dialogs/session_create.py`.** Main's PI-091/092/093 commits (SES-098, etc.) added executive_summary editing UI to the legacy sessions panel. My Phase E rewrites the panel entirely. **Resolution:** Apply Phase E's rewrite as the new structure, then ADD the executive_summary field to the new SessionsPanel detail view + the SessionEditDialog / SessionCreateDialog field schemas. The new model carries `session_executive_summary` (per resolution 2 above); the UI surfaces it as an editable text field.

After conflict resolution, verify the branch builds clean:

```bash
cd crmbuilder-v2
uv run python -c "from crmbuilder_v2.api.main import create_app; create_app(); print('App constructs OK')"
uv run alembic heads   # should show one head, your renumbered PI-073 migration
```

### Step 2 — Merge pi-073-redesign into main

```bash
cd ~/Dropbox/Projects/crmbuilder
git checkout main
git pull origin main
git merge --no-ff pi-073-redesign
```

Use `--no-ff` so the branch's history is preserved as a logical unit in main's history.

### Step 3 — Apply the schema migration to main's CRMBUILDER.db

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
# Stop any running API server first so it doesn't hold connections
# (the API server reading from main's DB will fail mid-migration otherwise)
pkill -f crmbuilder-v2-api 2>/dev/null || true
sleep 2

# Apply alembic
CRMBUILDER_V2_DB_PATH=$(realpath data/engagements/CRMBUILDER.db) uv run alembic upgrade head
```

Expect:
- Renamed conversations → legacy_conversations (preserves all live conversation rows including any added post-branch-cut)
- Renamed sessions → legacy_sessions (preserves all live session rows)
- Created new sessions + conversations tables
- Renamed commits.commit_conversation_id → commit_session_id
- Extended refs.relationship_kind CHECK

### Step 4 — Run the Phase F data migration on main's CRMBUILDER.db

```bash
CRMBUILDER_V2_DB_PATH=$(realpath data/engagements/CRMBUILDER.db) uv run python scripts/migrate_pi_073_data.py
```

Expect:
- N legacy_conversations migrated to sessions (N = however many were on main at apply time, ≥66 since branch-cut)
- M legacy_sessions migrated to conversations (M ≥ 95)
- Reference edges retargeted; conversation_records_session reversed to conversation_belongs_to_session
- Audit report written to `PRDs/product/crmbuilder-v2/pi-073-migration-audit.md` (overwrites the branch DB's audit; this run is authoritative)

### Step 5 — Restart the API server against main's DB

```bash
cd ~/Dropbox/Projects/crmbuilder
nohup uv run crmbuilder-v2-api > /tmp/crmbuilder-v2-api.log 2>&1 &
sleep 3
curl -sf http://127.0.0.1:8765/health
```

### Step 6 — Apply this close-out

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_099.json
```

Expect:

```
=== session (1 record) ===
  ✓ POST session  SES-099 (HTTP 201)
=== conversation (1 record) ===
  ✓ POST conversation  CNV-001 (HTTP 201)
=== commits (8 records) ===
  ✓ POST commits  CM-NNNN (HTTP 201)   ×8
=== references (1 record) ===
  ✓ POST references  SES-099 session_belongs_to_workstream WS-011 (HTTP 201)
=== resolves_planning_items (1 record) ===
  ✓ POST resolves_planning_items  → PI-073 (HTTP 201)
✓ All 11 operations complete.
✓ Recorded apply as deposit_event DEP-NNN (HTTP 201).
```

---

## Pre-flight checks (before Step 6)

```bash
# 1. API reachable
curl -sf http://127.0.0.1:8765/health || echo "API not running"

# 2. New schema is in place
curl -sf http://127.0.0.1:8765/sessions?limit=1 | python3 -c "import sys,json; d=json.load(sys.stdin)['data'][0]; print('Latest session shape:', list(d.keys())[:5])"

# 3. The new identifiers are available (SES-099, CNV-001 should not yet exist)
echo "SES-099 (expect 404):"
curl -o /dev/null -s -w "  HTTP %{http_code}\n" http://127.0.0.1:8765/sessions/SES-099
echo "CNV-001 (expect 404):"
curl -o /dev/null -s -w "  HTTP %{http_code}\n" http://127.0.0.1:8765/conversations/CNV-001

# 4. PI-073 is still Open
curl -sf http://127.0.0.1:8765/planning-items/PI-073 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('PI-073 status:', d['status'])"

# 5. WS-011 still in_flight
curl -sf http://127.0.0.1:8765/workstreams/WS-011 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['workstream_identifier'], d['workstream_status'])"
```

**Collision handling.** If any of the identifiers (SES-099, CNV-001) is already claimed at apply time (e.g., another session landed between branch cut and apply), re-key the payload:

```bash
# Get current heads
curl -sf http://127.0.0.1:8765/sessions/next-identifier
curl -sf http://127.0.0.1:8765/conversations/next-identifier
# Edit ses_099.json to use the returned identifiers throughout (session_identifier,
# conversation_identifier, all internal references); rename the file accordingly.
```

---

## Post-apply verification

```bash
echo "SES-099:"
curl -sf http://127.0.0.1:8765/sessions/SES-099 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['session_title'][:80]); print('  status:', d['session_status']); print('  medium:', d['session_medium'])"

echo "CNV-001:"
curl -sf http://127.0.0.1:8765/conversations/CNV-001 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['conversation_title'][:80]); print('  status:', d['conversation_status'])"

echo "PI-073 status (expect Resolved):"
curl -sf http://127.0.0.1:8765/planning-items/PI-073 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  status:', d['status'])"

echo "8 commits attributed to SES-099 (expect 8 rows):"
curl -sf 'http://127.0.0.1:8765/sessions/SES-099/commits' | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
print('  Count:', len(data))
for c in sorted(data, key=lambda c: c['commit_committed_at']):
    print(' ', c['commit_identifier'], c['commit_sha'][:8], '|', c['commit_message_first_line'][:70])
"

echo "CNV-001 belongs to SES-099 (expect 1 edge):"
curl -sf 'http://127.0.0.1:8765/sessions/SES-099/conversations' | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
print('  Count:', len(data))
for cv in data:
    print(' ', cv['conversation_identifier'], '|', cv['conversation_title'][:70])
"

echo "Latest deposit_event:"
curl -sf 'http://127.0.0.1:8765/deposit-events' | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
latest = sorted(data, key=lambda x: x['deposit_event_identifier'])[-1]
print(' ', latest['deposit_event_identifier'], '/', latest['deposit_event_outcome'])
"
```

---

## Commit the apply outputs

```bash
cd ~/Dropbox/Projects/crmbuilder

git add \
  PRDs/product/crmbuilder-v2/close-out-payloads/ses_099.json \
  PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-099.md \
  PRDs/product/crmbuilder-v2/pi-073-migration-audit.md \
  PRDs/product/crmbuilder-v2/db-export/ \
  PRDs/product/crmbuilder-v2/deposit-event-logs/

git commit -m "$(cat <<'EOF'
v2: SES-099 close-out applied — PI-073 redesign complete; resolves PI-073

Applies the SES-099 close-out payload via apply_close_out.py against
main's now-migrated CRMBUILDER.db. Closes the eight-phase PI-073
Session/Conversation entity redesign workstream.

Creates:
- SES-099 (session, medium=chat) — Phase G audit + documentation
  propagation conversation conducted in Claude Code.
- CNV-001 (conversation, status=complete) — first conversation under
  the new CNV-NNN prefix on main; belongs to SES-099.
- 8 commit rows (init + A + B.1 + B.2 + C + D + E + F), each
  attributed to SES-099 via commit_session_id.
- session_belongs_to_workstream edge SES-099 → WS-011.
- conversation_belongs_to_session edge CNV-001 → SES-099.
- resolves edge CNV-001 → PI-073 — flips PI-073 Open → Resolved
  atomically.
- close_out_payload COP-099 + deposit_event DEP-NNN.

PI-073 redesign summary (now Resolved):
- session is medium-agnostic communication container; conversation
  is topical sub-unit; 1:N relationship; six-status lifecycle on
  both; DEC-013 fully superseded by DEC-314; identifier-prefix
  asymmetry accepted (CONV-NNN now sessions, SES-NNN now
  conversations, new conversations use CNV-NNN).
- Migration of 66+ conversations and 95+ sessions to new shape
  via scripts/migrate_pi_073_data.py with full reference-edge
  retargeting; audit report at pi-073-migration-audit.md.
- The seven previously-blocked PIs (PI-085, PI-086, PI-087, PI-088,
  PI-024, PI-025, PI-026) now unblocked per the blocked_by edges
  authored in SES-095's close-out (they remain in refs as
  historical references but no longer represent active blockage).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Doug pushes after review.

---

## Done

After commit succeeds:
- PI-073 status flipped Open → Resolved
- DEC-314 (active since SES-095) remains the architectural authority
- The new session/conversation model is the live production model on main
- The seven previously-blocked downstream PIs (PI-085–088, PI-024–026) unblock
- `legacy_sessions` and `legacy_conversations` tables remain in main's DB as a safety net; a future cleanup PI may drop them after a holding period

Next-step considerations (out of scope for this close-out):
- Author a follow-on PI to drop legacy_* tables once everyone is comfortable the new shape is stable
- Revisit the `close_out_payload_produced_by_conversation` kind naming — under the new model the kind name reads slightly off (it now points at a session not a conversation); semantic rename to `close_out_payload_produced_by_session` is a cosmetic follow-up
- Re-engage PI-085 (Domain Overview) now that the structural prerequisite has landed
