# CLAUDE-CODE-PROMPT — Apply SES-078 close-out payload

**Last Updated:** 05-25-26 (drafted at PI-002 build close)
**Purpose:** Apply the SES-078 close-out payload — PI-002's build closure. Lands SES-078, CONV-048, one commit record (`48a91e358936ae1acfc70d69cf44b60e75bd9cd3` for the PI-002 retrofit, assigned CM-NNNN at apply time), zero new decisions, zero new planning items, three `is_about` payload references (SES-078 → PI-002, SES-078 → DEC-043, SES-078 → SES-010), and one `resolves_planning_items` entry that atomically flips PI-002 to Resolved via slice A's server-side atomic edge+flip.

**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_078.json`

**Predecessors:**
- SES-077 must have landed (commit `<SES-077 apply commit on origin/main>`, applied per its apply prompt).
- The PI-002 commit must be on `origin/main` — the build was executed in worktree `/home/doug/Dropbox/Projects/crmbuilder-pi002` on branch `pi-002-optional-identifier` branched from `723bc284`; Doug commits and merges/pushes that branch to main before this apply runs.
- A workstream pre-step (below) creates WS-011 "V2 storage API refinements" before the close-out apply. No existing workstream covers PI-002's lineage; per DEC-237's precedent, the apply-prompt pre-step creates a new workstream so the conversation's required `conversation_belongs_to_workstream` edge resolves.

**Successor:** None planned. Future ergonomic refinements to the v2 storage API join WS-011 as new planning items.

---

## Pre-publication TODOs (Doug fills these in before running the apply)

Before running this prompt, the following placeholders in the payload (`ses_078.json`) and in this prompt need to be filled in with concrete values:

1. **`48a91e358936ae1acfc70d69cf44b60e75bd9cd3`** — the SHA of the PI-002 commit on `origin/main`. Replace in:
   - `close-out-payloads/ses_078.json` → `commits[0].commit_sha`
   - This prompt's Scope section and the Pre-flight block
2. **`<COMMIT_DATE_TBD>`** — the ISO 8601 commit timestamp (`git log -1 --format=%cI <SHA>`). Replace in:
   - `close-out-payloads/ses_078.json` → `commits[0].commit_committed_at`
3. **`commits[0].commit_parent_shas`** — confirm `723bc284c477a6b6c7922295dcad218fb2de1766` is still the parent SHA. If Doug merged via a `--no-ff` merge commit or rebased the branch, update accordingly via `git log -1 --format='%P' <SHA>`.
4. **`commits[0].commit_files_changed_count`** — currently set to 16 (matching the diff stat at draft time: 6 source/schema files + 6 modified test files + 2 added artifact files + CLAUDE.md + 1 more from any post-draft change). Confirm with `git diff --stat 723bc284..<SHA> | tail -1`. If commits other than the PI-002 commit land on `main` between draft and apply (parallel-workstream interleaving — see DEC-233), the commits array stays exactly as authored (explicit-list curation, not range-based enumeration).

After filling in, the placeholders should be gone — search `grep -n 'TBD' PRDs/product/crmbuilder-v2/close-out-payloads/ses_078.json PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-078.md` to verify.

---

## Scope

Apply `close-out-payloads/ses_078.json` using `crmbuilder-v2/scripts/apply_close_out.py`. The payload contains the v0.8 nine sections:

- **1 session** (SES-078)
- **1 conversation** (CONV-048, status `complete`, embeds the two required edges atomically: `conversation_belongs_to_workstream` to WS-011, `conversation_records_session` to SES-078)
- **1 commit** (`48a91e358936ae1acfc70d69cf44b60e75bd9cd3` — the PI-002 retrofit — assigned CM-NNNN at apply time with `commit_conversation_id = CONV-048`)
- **0 work_tickets**
- **0 decisions**
- **0 planning_items**
- **3 references** (three `is_about` from SES-078 to PI-002, DEC-043, and SES-010 — surfacing the genealogy of the work for future audit queries)
- **1 resolves_planning_item** (PI-002 — server-side atomic edge+flip via slice A; PI-002 status flips Open → Resolved in the same transaction)
- **0 addresses_planning_items**

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

# Verify the payload file exists and has no TBD placeholders
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_078.json
grep -n 'TBD' ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_078.json || echo "OK: no TBD placeholders remain"

# Confirm the PI-002 commit is on local main
git cat-file -e 48a91e358936ae1acfc70d69cf44b60e75bd9cd3 2>/dev/null \
  && echo "FOUND: 48a91e358936ae1acfc70d69cf44b60e75bd9cd3 — $(git log -1 --format=%s 48a91e358936ae1acfc70d69cf44b60e75bd9cd3)" \
  || { echo "MISSING: 48a91e358936ae1acfc70d69cf44b60e75bd9cd3 — HALT (commit + push the PI-002 branch first)"; exit 1; }

# Confirm WS-011 absence (will be created by the pre-step below)
curl -sf http://127.0.0.1:8765/workstreams/WS-011 >/dev/null 2>&1 \
  && echo "WARN: WS-011 already exists; the pre-step below is a no-op on re-run" \
  || echo "OK: WS-011 absent (pre-step will create it)"

# Confirm PI-002 still Open (target of resolves edge — flip happens in this apply)
curl -s http://127.0.0.1:8765/planning-items/PI-002 \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('PI-002 status:', d['status'])"
# Expect: Open. If Resolved, a parallel apply has already landed this closure — halt and investigate.

# Capture pre-apply heads
echo "=== Pre-apply heads ==="
for endpoint in sessions decisions planning-items; do
  echo "$endpoint:"
  curl -s "http://127.0.0.1:8765/$endpoint?limit=2000" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
done
echo "Conversations:"
curl -s 'http://127.0.0.1:8765/conversations?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['conversation_identifier'] for r in d)[-1] if d else 'none')"
echo "Workstreams:"
curl -s http://127.0.0.1:8765/workstreams | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['workstream_identifier'] for r in d)[-1] if d else 'none')"
echo "Commits:"
curl -s 'http://127.0.0.1:8765/commits?limit=2000' 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', (sorted(r['commit_identifier'] for r in d)[-1] if d else 'none'))"
echo "Close-out payloads:"
curl -s 'http://127.0.0.1:8765/close-out-payloads?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['close_out_payload_identifier'] for r in d)[-1] if d else 'none')"
echo "Deposit events:"
curl -s 'http://127.0.0.1:8765/deposit-events?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['deposit_event_identifier'] for r in d)[-1] if d else 'none')"
echo "References (count):"
curl -s 'http://127.0.0.1:8765/references?limit=5000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', len(d))"
```

**Expected pre-apply state** (CRMBUILDER engagement, post SES-077 apply): sessions head **at least SES-077**, decisions head **at least DEC-245**, planning-items head **at least PI-052**, conversations head CONV-047, workstreams head WS-010 (WS-011 created in the pre-step). The "at least" hedges accommodate any parallel-sandbox claims between this prompt's authoring and Doug actually running it; identifier-collision contingency handled by re-keying the payload before apply (see "Re-key if any identifier in this payload is already taken" below).

---

## Pre-step: create WS-011 workstream

The CRMBUILDER engagement has no workstream covering PI-002's lineage. Per DEC-237's precedent for SES-074, the apply prompt POSTs `/workstreams` to create the workstream as a pre-step before invoking `apply_close_out.py`:

```bash
# Create WS-011 'V2 storage API refinements'
curl -s -X POST http://127.0.0.1:8765/workstreams \
  -H 'Content-Type: application/json' \
  -d '{
    "workstream_identifier": "WS-011",
    "workstream_name": "V2 storage API refinements",
    "workstream_purpose": "Bring the v2 storage REST API to ergonomic parity across all entity types and absorb post-launch refinement work that emerges from real usage.",
    "workstream_description": "Hosts planning items that refine the v2 storage REST API after its initial v0.7 governance build and v0.4+ methodology builds. Initial member: PI-002 (server-side identifier auto-assignment retrofit for the five remaining prefixed entity types, completing DEC-043 option C). Future members: any ergonomic refinements that surface from CBM usage or other engagements — batch-write helpers, identifier-as-path-segment uniformity audits, pagination consistency, etc. Status stays in_flight until the workstream'\''s open planning items resolve.",
    "workstream_status": "in_flight"
  }' | python3 -m json.tool

# Confirm WS-011 exists and status is in_flight
curl -s http://127.0.0.1:8765/workstreams/WS-011 \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('WS-011 status:', d['workstream_status'])"
```

The pre-step is idempotent: re-running after WS-011 already exists returns HTTP 409 and the script continues. The `conversation_belongs_to_workstream` edge inside the payload's conversation block resolves against this workstream at apply time.

---

## Apply

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_078.json
```

Expected output: nine sections processed in order (session → conversation → work_tickets [empty] → planning_items [empty] → commits → decisions [empty] → references → resolves_planning_items → addresses_planning_items [empty]) followed by the deposit_event POST. Section processing emits one `[CREATED]` or `[SKIP]` line per record (and `[NO-WORK]` for empty sections). The atomic resolves edge fires inside the references machinery and flips PI-002 to Resolved in the same transaction.

The script tees stdout to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` (git-tracked per DEC-164). The final `[DEPOSIT_EVENT]` line names the COP and DEP identifiers assigned at apply time.

---

## Post-apply verification

```bash
# PI-002 should be Resolved
curl -s http://127.0.0.1:8765/planning-items/PI-002 \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('PI-002 status:', d['status'])"
# Expect: Resolved

# Session, conversation, workstream linkages
curl -s http://127.0.0.1:8765/sessions/SES-078 \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('SES-078 title:', d['title'][:80])"

curl -s http://127.0.0.1:8765/conversations/CONV-048 \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('CONV-048 status:', d['conversation_status'])"

# Verify the conversation's two required edges exist
curl -s 'http://127.0.0.1:8765/references?source_type=conversation&source_id=CONV-048' \
  | python3 -c "import sys,json; refs=json.load(sys.stdin)['data']; print('CONV-048 outbound edges:'); [print(' ', r['relationship_kind'], '->', r['target_type'], r['target_id']) for r in refs]"
# Expect: conversation_belongs_to_workstream -> workstream WS-011
#         conversation_records_session -> session SES-078

# Verify the commit landed and is attributed to CONV-048
curl -s 'http://127.0.0.1:8765/commits?limit=2000' \
  | python3 -c "
import sys,json
rows = json.load(sys.stdin)['data']
pi002 = [r for r in rows if r['commit_sha'].startswith('48a91e358936ae1acfc70d69cf44b60e75bd9cd3'[:8])]
if pi002:
    r = pi002[0]
    print('Commit:', r['commit_identifier'], 'conversation:', r.get('commit_conversation_id'))
else:
    print('NOT FOUND')
"

# Verify the resolves edge exists
curl -s 'http://127.0.0.1:8765/references?source_type=conversation&source_id=CONV-048&target_type=planning_item&target_id=PI-002' \
  | python3 -c "import sys,json; refs=json.load(sys.stdin)['data']; print('CONV-048 -> PI-002 edges:'); [print(' ', r['relationship_kind']) for r in refs]"
# Expect: resolves

# Snapshot regeneration: regenerate db-export so the file-fallback Tier 2 reflects the apply
cd .. && uv run python crmbuilder-v2/scripts/regenerate_snapshots.py && cd crmbuilder-v2
```

The snapshot regeneration commit should be made and pushed alongside this apply per the standard close-out convention (Doug commits + pushes; see `CLAUDE.md` push convention).

---

## Idempotency

Re-running this prompt is safe:
- WS-011 POST returns 409 (already exists)
- `apply_close_out.py` translates HTTP 409 to `[SKIP]` for every record
- The `resolves` edge POST returns 409 (already exists); PI-002 stays Resolved
- A second deposit_event is emitted for the re-run (deposit_events are append-only)

---

## Re-key if any identifier in this payload is already taken

If `SES-078`, `CONV-048`, `WS-011`, or `CM-NNNN` is claimed by a parallel sandbox conversation between draft and apply:

1. Identify the next available identifier (`curl -s http://127.0.0.1:8765/<entity>/next-identifier`).
2. Re-key throughout `ses_078.json` and this prompt — the affected entity identifier, plus any internal references in the payload (`source_id` / `target_id` / `commit_conversation_id`).
3. Rename `ses_078.json` and this prompt file to match if SES re-keyed.
4. Re-run pre-flight.

The build-closure kickoff pattern (SES-074's apply prompt names this contingency explicitly) covers the re-key mechanic.
