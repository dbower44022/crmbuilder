# CLAUDE-CODE-PROMPT — Apply SES-081 close-out payload

**Last Updated:** 05-25-26
**Purpose:** Apply the SES-081 close-out payload — the orchestrated design phase for PI-003 (persona), PI-004 (the field/requirement/manual_config/test_spec cohort), and PI-005 (process schema growth). Lands SES-081, CONV-051, six `kickoff_prompt` work_tickets (WT-049..054), zero new decisions, zero new planning items, five `is_about` references from SES-081 (to PI-003, PI-004, PI-005, DEC-039, WS-003), and three `addresses_planning_items` edges from SES-081 to PI-003, PI-004, PI-005. **No `resolves_planning_items` — PI-003, PI-004, PI-005 remain `Open`.** Each of the six build prompts (one per WT) instructs a future Claude Code session to execute its entity end-to-end and atomically resolve its target PI in that session's own close-out.

**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_081.json`

**Predecessors:**
- This payload is the third of three close-out payloads currently staged-but-unapplied in git. The other two are `ses_079.json` (the WS-012 orchestrator-architecture establishing conversation) and `ses_080.json` (the PI-052 chat-UI design conversation). All three were authored against non-conflicting identifier sets — applying any one does not block applying the others. **Apply order does not matter** for correctness, but applying in numeric order (SES-079 → SES-080 → SES-081) is cleaner for log readability.
- WS-003 "Methodology entity schema design" must exist (it does — it was created in v0.4 and is status `complete`; this apply references it via the conversation's `conversation_belongs_to_workstream` edge, which is valid against any-status workstreams).

**Successors:** Six future Claude Code sessions, one per WT-049..054, each executing its build prompt at the path named in `work_ticket_file_path`. Recommended order: persona (PI-003) and field (PI-004 portion) first (independent foundational entities), then requirement / manual_config / test_spec in any order (the LAST of those four to ship is the PI-004 build-closure session), then process-v2 (PI-005, depends on persona + field for full coverage but safe to run earlier).

---

## Pre-publication TODOs

None. The payload was authored against a clean snapshot of the live API state. No placeholders (`TBD`, `XXX`, etc.) appear in the payload — confirm with:

```bash
grep -n -E 'TBD|XXX|<.*_TBD>' PRDs/product/crmbuilder-v2/close-out-payloads/ses_081.json && echo "FAIL: placeholders remain" || echo "OK: no placeholders"
```

---

## Scope

Apply `close-out-payloads/ses_081.json` using `crmbuilder-v2/scripts/apply_close_out.py`. The payload contains the v0.8 nine sections:

- **1 session** (SES-081)
- **1 conversation** (CONV-051, status `complete`, embeds two required edges: `conversation_belongs_to_workstream` → WS-003, `conversation_records_session` → SES-081)
- **0 commits** (design phase produced documentation only; no code)
- **6 work_tickets** (WT-049..054, all kind=`kickoff_prompt`, status=`ready`, each with `addresses_planning_item` pointing at its target PI: WT-049→PI-003, WT-050..053→PI-004, WT-054→PI-005)
- **0 decisions** (per-spec design decisions are captured inline in each spec's section 3.9.1 as DEC-XXX placeholders; each build session's close-out authors its spec's decisions with definitive DEC-NNN numbers)
- **0 planning_items** (no new PIs surfaced from the design phase; each spec's section 3.8 enumerates spec-deferred questions that become PIs in the respective build sessions)
- **5 references** (SES-081 `is_about` → PI-003, PI-004, PI-005, DEC-039, WS-003 — capturing the work's genealogy for future audit queries)
- **0 resolves_planning_items**
- **3 addresses_planning_items** (PI-003, PI-004, PI-005 — this session advances each PI by producing its schema spec and build prompt but does NOT resolve any)

The payload is idempotent on re-run; HTTP 409 SKIPs are treated as already-present.

---

## Pre-flight

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

# Clean working tree (acknowledge unrelated unstaged work — proceed regardless)
git status

# Pull latest commits
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# Git identity
git config user.email
# Expect: doug@dougbower.com

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start the API:
#   uv run crmbuilder-v2-api &

# Verify the payload file exists and has no placeholders
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_081.json
grep -n -E 'TBD|XXX|<.*_TBD>' ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_081.json && { echo "FAIL: placeholders remain"; exit 1; } || echo "OK: no placeholders"

# Verify the six build-prompt files exist (each WT's work_ticket_file_path)
for f in \
  CLAUDE-CODE-PROMPT-build-persona.md \
  CLAUDE-CODE-PROMPT-build-field.md \
  CLAUDE-CODE-PROMPT-build-requirement.md \
  CLAUDE-CODE-PROMPT-build-manual_config.md \
  CLAUDE-CODE-PROMPT-build-test_spec.md \
  CLAUDE-CODE-PROMPT-build-process-v2.md \
; do
  ls -la "../PRDs/product/crmbuilder-v2/prompts/$f" || { echo "MISSING: $f"; exit 1; }
done

# Verify the six schema-spec files exist (each WT cites them in its description)
for f in persona.md field.md requirement.md manual_config.md test_spec.md process-v2.md; do
  ls -la "../PRDs/product/crmbuilder-v2/methodology-schema-specs/$f" || { echo "MISSING: $f"; exit 1; }
done

# Confirm WS-003 exists and is the target of the conversation_belongs_to_workstream edge
curl -s http://127.0.0.1:8765/workstreams/WS-003 \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('WS-003 status:', d['workstream_status'])"
# Expect: complete (the workstream still accepts new belongs_to edges regardless of status)

# Confirm PI-003, PI-004, PI-005 still Open (targets of addresses edges — no flip happens here)
for pi in PI-003 PI-004 PI-005; do
  curl -s "http://127.0.0.1:8765/planning-items/$pi" \
    | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('$pi status:', d['status'])"
done
# Expect: Open / Open / Open. If any are Resolved, halt and investigate — a parallel sandbox may have already shipped them.

# Capture pre-apply heads (live API state)
echo "=== Pre-apply heads ==="
for endpoint in sessions decisions planning-items; do
  echo "$endpoint:"
  curl -s "http://127.0.0.1:8765/$endpoint?limit=2000" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
done
echo "Conversations:"
curl -s 'http://127.0.0.1:8765/conversations?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['conversation_identifier'] for r in d)[-1] if d else 'none')"
echo "Work tickets:"
curl -s 'http://127.0.0.1:8765/work-tickets?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['work_ticket_identifier'] for r in d)[-1] if d else 'none')"
echo "Close-out payloads:"
curl -s 'http://127.0.0.1:8765/close-out-payloads?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['close_out_payload_identifier'] for r in d)[-1] if d else 'none')"
echo "Deposit events:"
curl -s 'http://127.0.0.1:8765/deposit-events?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['deposit_event_identifier'] for r in d)[-1] if d else 'none')"
echo "References (count):"
curl -s 'http://127.0.0.1:8765/references?limit=5000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', len(d))"
```

**Expected pre-apply state** (assuming SES-079 and SES-080 have been applied first): sessions head **SES-080**, conversations head **CONV-050**, work_tickets head **WT-048**. If those two payloads have NOT been applied first, sessions head will be SES-078, conversations head CONV-048, work_tickets head WT-047 — this apply still succeeds independently because the SES-081 / CONV-051 / WT-049..054 identifiers do not collide with any of the parallel-sandbox identifiers (ses_079.json claims SES-079/CONV-049/PI-053..062/DEC-246..251; ses_080.json claims SES-080/CONV-050/WT-048/DEC-252..262 — all disjoint from this payload).

---

## Pre-step

**None.** WS-003 already exists (it shipped in v0.4 and is referenced by the conversation block). No new workstream, no new entity types, no new vocabulary kinds — this is a pure governance close-out for the design phase.

---

## Apply

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_081.json
```

Expected output: nine sections processed in order (session → conversation → work_tickets → planning_items [empty] → commits [empty] → decisions [empty] → references → resolves_planning_items [empty] → addresses_planning_items) followed by the deposit_event POST. Section processing emits one `[CREATED]` or `[SKIP]` line per record (and `[NO-WORK]` for empty sections). The three `addresses` edges fire inside the references machinery; no status flips occur on PI-003/004/005 (their `Open` status is preserved).

The script tees stdout to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` (git-tracked per DEC-164). The final `[DEPOSIT_EVENT]` line names the COP and DEP identifiers assigned at apply time.

---

## Post-apply verification

```bash
# PI-003, PI-004, PI-005 should remain Open (this session does not resolve them)
for pi in PI-003 PI-004 PI-005; do
  curl -s "http://127.0.0.1:8765/planning-items/$pi" \
    | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('$pi status:', d['status'])"
done
# Expect: Open / Open / Open

# Session, conversation, workstream linkages
curl -s http://127.0.0.1:8765/sessions/SES-081 \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('SES-081 title:', d['title'][:80])"

curl -s http://127.0.0.1:8765/conversations/CONV-051 \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('CONV-051 status:', d['conversation_status'])"

# Verify the conversation's two required edges exist
curl -s 'http://127.0.0.1:8765/references?source_type=conversation&source_id=CONV-051' \
  | python3 -c "import sys,json; refs=json.load(sys.stdin)['data']; print('CONV-051 outbound edges:'); [print(' ', r['relationship_kind'], '->', r['target_type'], r['target_id']) for r in refs]"
# Expect: conversation_belongs_to_workstream -> workstream WS-003
#         conversation_records_session -> session SES-081

# Verify the six work_tickets landed and each addresses its target PI
for wt in WT-049 WT-050 WT-051 WT-052 WT-053 WT-054; do
  curl -s "http://127.0.0.1:8765/work-tickets/$wt" \
    | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('$wt status:', d['work_ticket_status'], '| file:', d.get('work_ticket_file_path', '(none)'))"
done

# Verify each WT's addresses edge to its target PI
for wt in WT-049 WT-050 WT-051 WT-052 WT-053 WT-054; do
  curl -s "http://127.0.0.1:8765/references?source_type=work_ticket&source_id=$wt" \
    | python3 -c "import sys,json; refs=json.load(sys.stdin)['data']; [print('$wt addresses', r['target_id']) for r in refs if r['relationship_kind']=='addresses']"
done
# Expect: WT-049 addresses PI-003; WT-050..053 addresses PI-004; WT-054 addresses PI-005

# Verify the three SES-081 addresses_planning_items edges exist
for pi in PI-003 PI-004 PI-005; do
  curl -s "http://127.0.0.1:8765/references?source_type=session&source_id=SES-081&target_type=planning_item&target_id=$pi" \
    | python3 -c "import sys,json; refs=json.load(sys.stdin)['data']; [print('SES-081', r['relationship_kind'], '->', '$pi') for r in refs]"
done
# Expect: SES-081 addresses -> PI-003, SES-081 addresses -> PI-004, SES-081 addresses -> PI-005
# (Plus an is_about edge per the references section — that's separate)

# Snapshot regeneration: regenerate db-export so the file-fallback Tier 2 reflects the apply
cd .. && uv run python crmbuilder-v2/scripts/regenerate_snapshots.py && cd crmbuilder-v2
```

The snapshot regeneration commit should be made and pushed alongside this apply per the standard close-out convention (Doug commits + pushes; see `CLAUDE.md` push convention).

---

## Idempotency

Re-running this prompt is safe:
- `apply_close_out.py` translates HTTP 409 to `[SKIP]` for every record
- The three `addresses` edges return 409 on re-run (already exists); PI-003/004/005 stay `Open`
- A second deposit_event is emitted for the re-run (deposit_events are append-only)

---

## Re-key if any identifier in this payload is already taken

If any of `SES-081`, `CONV-051`, `WT-049..054` is claimed by a parallel sandbox conversation between draft and apply:

1. Identify the next available identifier (`curl -s http://127.0.0.1:8765/<entity>/next-identifier`).
2. Re-key throughout `ses_081.json` and this prompt — the affected entity identifier plus any internal references in the payload (`source_id` / `target_id`).
3. Rename `ses_081.json` and this prompt file to match if SES re-keyed.
4. Re-run pre-flight.

The SES-077 re-key precedent (originally drafted as SES-076; consumed by parallel work; re-keyed at close-out) documents the mechanic. This payload was already re-keyed once during authoring: originally drafted as SES-079, re-keyed to SES-081 after discovering ses_079.json (orchestrator architecture) and ses_080.json (PI-052 chat-UI) staged-but-unapplied in git.
