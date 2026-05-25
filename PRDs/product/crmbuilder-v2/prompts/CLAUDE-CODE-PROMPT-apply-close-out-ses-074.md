# CLAUDE-CODE-PROMPT — Apply SES-074 close-out payload

**Last Updated:** 05-25-26 16:00
**Re-key note:** Originally drafted as SES-073 close-out at 05-25-26 13:30; re-keyed to SES-074 / DEC-232..DEC-237 / PI-050 at 05-25-26 16:00 after a parallel-sandbox PI-045 step-5 OAuth-rerouting session claimed SES-073, DEC-226, and PI-049 via direct-API writes (commits `bfa7053`, `7495a40`). CONV-046, CM-0001..CM-0003, and WS-009 remain as originally written. Identifier-collision contingency anticipated by the build-closure kickoff.
**Purpose:** Apply the SES-074 close-out payload — the first close-out to use the full nine-section v0.8 payload format, and the functional acceptance test for PI-030's machinery (slice A's POST /references atomic edge+flip, slice B's apply_close_out.py extension for the five new sections, slice C's enumerate_commits.py helper). Lands SES-074 plus CONV-046, three commit records (CM-0001/0002/0003 for slices A/B/C), six decisions (DEC-232–DEC-237), one new planning item (PI-050), seven payload references (six `decided_in` plus one `is_about` to PI-050), one resolves edge that atomically flips PI-030 to Resolved, and one addresses edge to PI-032.

**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_073.json`
**Predecessors:**
- SES-072 must have landed (commit `63f13a4`, applied per its apply prompt).
- The parallel-sandbox PI-045 step-5 OAuth-rerouting work that claimed SES-073/DEC-226/PI-049 (commits `bfa7053` direct-API writes and `7495a40` audit-chain backfill) has landed on `origin/main`; the SES-074 payload was re-keyed from an originally-drafted SES-073 in response, per the identifier-collision contingency named in the build-closure kickoff.
- All three PI-030 slice commits (`70d88e6`, `2b5557d`, `c6ff67a`) must be on `origin/main`.
- A workstream pre-step (below) creates WS-009 "Code Change Lifecycle workstream" before the close-out apply. The CRMBUILDER engagement has no workstream covering PI-030's lineage today, and `conversations.py` access layer requires every live conversation to carry exactly one `conversation_belongs_to_workstream` edge per DEC-237.
**Successor:** Methodology rollout (PI-032) and historical backfill (PI-033) consume the build-closure pattern established here. The commits panel UI (PI-031) reads from the commit records this apply creates.

---

## Scope

Apply `close-out-payloads/ses_073.json` using `crmbuilder-v2/scripts/apply_close_out.py`. The payload contains all nine v0.8 sections:

- **1 session** (SES-074)
- **1 conversation** (CONV-046, status `complete`, embeds the two required edges atomically: `conversation_belongs_to_workstream` to WS-009, `conversation_records_session` to SES-074)
- **3 commits** (slice A `70d88e6`, slice B `2b5557d`, slice C `c6ff67a` — assigned CM-0001, CM-0002, CM-0003 chronologically with `commit_conversation_id = CONV-046`)
- **0 work_tickets**
- **6 decisions** (DEC-232 build-closure pattern, DEC-233 commits scoping + PI-050 surfacing, DEC-234 resolves attribution discipline, DEC-235 executor-improvisation governance posture, DEC-236 conversation_purpose convention, DEC-237 WS-009 promotion + §4.0 example fix)
- **1 planning_item** (PI-050 helper evolution, status Open)
- **7 references** (six `decided_in` for DEC-232..DEC-237 → SES-074, one `is_about` for SES-074 → PI-050)
- **1 resolves_planning_item** (PI-030 — server-side atomic edge+flip via slice A; PI-030 status flips Open → Resolved in same transaction)
- **1 addresses_planning_item** (PI-032 — methodology rollout partially advanced by this closure's §10 amendment but not resolved)

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

# Verify the payload file exists
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_073.json

# Confirm slice SHAs on local main (commits ingested by this close-out)
for sha in 70d88e6 2b5557d c6ff67a; do
  git cat-file -e $sha 2>/dev/null && echo "FOUND: $sha — $(git log -1 --format=%s $sha)" || echo "MISSING: $sha — HALT"
done

# Confirm no commits.json snapshot yet (bootstrap case for the commits section)
ls ../PRDs/product/crmbuilder-v2/db-export/commits.json 2>/dev/null && echo "WARN: commits.json already exists; this is no longer the bootstrap case" || echo "OK: commits.json absent (bootstrap)"

# Confirm WS-009 absence (will be created by the pre-step below)
curl -sf http://127.0.0.1:8765/workstreams/WS-009 >/dev/null 2>&1 \
  && echo "WARN: WS-009 already exists; the pre-step below is a no-op on re-run" \
  || echo "OK: WS-009 absent (pre-step will create it)"

# Confirm PI-030 still Open (target of resolves edge — flip happens in this apply)
curl -s http://127.0.0.1:8765/planning-items/PI-030 \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('PI-030 status:', d['status'])"
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

Expected pre-apply state (CRMBUILDER engagement, post the parallel-sandbox direct-API writes that claimed SES-073/DEC-226/PI-049 and the subsequent audit-chain backfill that lazy-created COP-073/DEP-052): sessions head **at least SES-073**, decisions head **at least DEC-226**, planning-items head **at least PI-049**, conversations head CONV-045, workstreams head WS-008 (WS-009 will be created in the pre-step), commits head `none` (bootstrap still — direct-API parallel writes did not ingest any commit records), COP head **at least COP-073**, DEP head **at least DEP-052**, references ≈ 866 (or higher if additional parallel applies have landed). The "at least" hedges accommodate further parallel sandbox claims between this apply prompt's authoring and Doug actually running it; the +6 DEC-block buffer and +1 SES/PI/COP/DEP offsets in this payload's identifier mapping (DEC-226..DEC-231 → DEC-232..DEC-237, SES-073 → SES-074, PI-049 → PI-050) leave room for that.

---

## WS-009 pre-step — create the Code Change Lifecycle workstream

Per DEC-237: the close-out payload schema has no `workstreams` section, so WS-009 must be created out-of-band before the close-out apply. Single direct POST to `/workstreams`:

```bash
# Capture WS-009 absence one more time (idempotency guard)
if curl -sf http://127.0.0.1:8765/workstreams/WS-009 >/dev/null 2>&1; then
  echo "WS-009 already exists; skipping creation step (idempotent re-run)"
else
  echo "Creating WS-009..."
  curl -sf -X POST http://127.0.0.1:8765/workstreams \
    -H "Content-Type: application/json" \
    -d '{
      "workstream_identifier": "WS-009",
      "workstream_name": "Code Change Lifecycle workstream",
      "workstream_purpose": "Bring code-change lifecycle into V2 governance: methodology document, commit entity, payload-section extensions, UI surface, methodology rollout, and historical backfill.",
      "workstream_description": "The workstream established at SES-057 to close the planning_items resolution gap diagnosed by the v0.7 schema-design close-out (PI-022 was the only Resolved planning item and had no resolves edge). Comprises planning items PI-027 (methodology document), PI-028 (commit entity schema spec), PI-029 (commits access layer + REST), PI-030 (close-out payload extension + apply integration + enumerate_commits.py helper), PI-031 (commits panel UI), PI-032 (methodology rollout — close-out template + work_ticket authoring rule in repo CLAUDE.md), and PI-033 (historical backfill of work_tickets, commits, retroactive resolves edges, and the blocks → blocked_by + is_about → addresses kind migrations). PI-050 (extend enumerate_commits.py with explicit-list mode) joins on surface from SES-074. Status remains in_flight until PI-031, PI-032, and PI-033 all resolve.",
      "workstream_status": "in_flight"
    }' \
    | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('Created:', d['workstream_identifier'], '-', d['workstream_status'])"
fi
```

Expected output: `Created: WS-009 - in_flight` on first run; `WS-009 already exists; skipping creation step (idempotent re-run)` on re-run.

---

## Apply

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_073.json
```

Expected output structure (methodology §4 order: session → conversation → work_tickets → planning_items → commits → decisions → references → resolves_planning_items → addresses_planning_items):

- **`=== session ===`** — 1 OK (SES-074)
- **`=== conversation ===`** — 1 OK (CONV-046 with two embedded edges committed atomically: `conversation_belongs_to_workstream` to WS-009, `conversation_records_session` to SES-074)
- **`=== work_tickets ===`** — 0 (section empty)
- **`=== planning_items ===`** — 1 OK (PI-050 status Open)
- **`=== commits ===`** — 3 OK (CM-0001 = `70d88e6`, CM-0002 = `2b5557d`, CM-0003 = `c6ff67a`; all with `commit_conversation_id = CONV-046` injected by the apply script per slice B)
- **`=== decisions ===`** — 6 OK (DEC-232 through DEC-237)
- **`=== references ===`** — 7 OK (six `decided_in` + one `is_about`)
- **`=== resolves_planning_items ===`** — 1 OK (CONV-046 → resolves → PI-030; PI-030 status flips Open → Resolved server-side per slice A)
- **`=== addresses_planning_items ===`** — 1 OK (CONV-046 → addresses → PI-032)
- 1 close_out_payload lazy-created (COP-074)
- 1 deposit_event written at apply close (lazy-created; DEP identifier depends on current head, expect DEP-053 if no further parallel applies have intervened beyond the SES-073 backfill at DEP-052)

If any record returns 409 SKIP on first run, halt and investigate — first run should have zero SKIPs. On re-run, every record should SKIP idempotently (including the resolves edge: PI-030's status flip is a no-op once it's already Resolved per slice A's idempotency guard).

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Sessions (expect SES-074):"
curl -s 'http://127.0.0.1:8765/sessions?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Decisions (expect DEC-237):"
curl -s 'http://127.0.0.1:8765/decisions?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Planning items (expect PI-050):"
curl -s 'http://127.0.0.1:8765/planning-items?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Conversations (expect CONV-046):"
curl -s 'http://127.0.0.1:8765/conversations?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['conversation_identifier'] for r in d)[-1])"
echo "Workstreams (expect WS-009 — created in pre-step):"
curl -s http://127.0.0.1:8765/workstreams | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['workstream_identifier'] for r in d)[-1])"
echo "Commits (expect CM-0003 — first-ever ingestion):"
curl -s 'http://127.0.0.1:8765/commits?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['commit_identifier'] for r in d)[-1] if d else 'none')"
echo "Close-out payloads (expect COP-074 lazy-created — COP-073 was lazy-created by the parallel-sandbox audit-chain backfill commit 7495a40):"
curl -s 'http://127.0.0.1:8765/close-out-payloads?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['close_out_payload_identifier'] for r in d)[-1])"
echo "Deposit events (expect DEP head + 1):"
curl -s 'http://127.0.0.1:8765/deposit-events?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['deposit_event_identifier'] for r in d)[-1])"

# Spot-check SES-074
curl -s http://127.0.0.1:8765/sessions/SES-074 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:100]); print('  status:', d['status'])"

# Spot-check CONV-046 and its two atomic edges
curl -s http://127.0.0.1:8765/conversations/CONV-046 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  CONV-046 status:', d['conversation_status']); print('  CONV-046 purpose opens:', d['conversation_purpose'][:80])"
curl -s 'http://127.0.0.1:8765/references?source_id=CONV-046' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(' ', r['source_id'], '->', r['target_id'], '[', r['relationship'], ']') for r in d]"
# Expect at minimum:
#   CONV-046 -> WS-009 [ conversation_belongs_to_workstream ]
#   CONV-046 -> SES-074 [ conversation_records_session ]
#   CONV-046 -> PI-030 [ resolves ]
#   CONV-046 -> PI-032 [ addresses ]

# Spot-check the atomic resolves flip — PI-030 status MUST be Resolved post-apply
curl -s http://127.0.0.1:8765/planning-items/PI-030 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  PI-030 status (expect Resolved):', d['status'])"

# Spot-check the new commit records and their FK propagation
echo ""
echo "Commits ingested under CONV-046:"
curl -s 'http://127.0.0.1:8765/commits?limit=2000' | python3 -c "
import sys, json
d = json.load(sys.stdin)['data']
for c in d:
    print(' ', c['commit_identifier'], c['commit_sha'][:8], '->', c.get('commit_conversation_id'), c.get('commit_message_first_line','')[:80])
"
# Expect three rows: CM-0001 / CM-0002 / CM-0003, all with commit_conversation_id = CONV-046.

# Spot-check one decision
curl -s http://127.0.0.1:8765/decisions/DEC-232 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  DEC-232 title:', d['title'][:100]); print('  status:', d['status'])"

# Confirm DEC-232's decided_in reference resolves to SES-074
curl -s 'http://127.0.0.1:8765/references?source_id=DEC-232' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(' ', r['source_id'], '->', r['target_id'], '[', r['relationship'], ']') for r in d]"

# Reference total delta
echo ""
echo "Reference total after apply:"
curl -s 'http://127.0.0.1:8765/references?limit=5000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
# Expected delta from pre-apply: +25 to +28 references, breakdown:
#   + 7 payload references (6 decided_in + 1 is_about)
#   + 2 conversation block embedded edges (workstream membership + records_session)
#   + 1 resolves edge (CONV-046 -> PI-030)
#   + 1 addresses edge (CONV-046 -> PI-032)
#   +12 wrote_record edges from the lazy deposit_event (1 session + 1 conversation + 3 commits + 6 decisions + 1 planning_item = 12 records the apply created)
#   + 1 close_out_payload_applied_by_deposit_event (DEP-053 -> COP-074)
#   + 1 close_out_payload_produced_by_conversation (CONV-046 -> COP-074) — if the lazy-create wires this
#   ≈ 25 + a couple depending on lazy-create edge wiring
```

Expected post-apply state: sessions head SES-074, decisions head DEC-237, planning-items head PI-050, conversations head CONV-046, workstreams head WS-009, commits head CM-0003 (first ingestion), COP head COP-074 (lazy), DEP head DEP-053 or higher (lazy). PI-030 status `Resolved`. Reference total ≈ pre + 25 (give or take depending on lazy-create edges).

---

## Commit snapshot regeneration

The apply script's `_refresh_snapshot` hook regenerates db-export JSON snapshots transactionally on every API write. The snapshots produced by this apply include:

- `db-export/sessions.json` (SES-074 added)
- `db-export/conversations.json` (CONV-046 added)
- `db-export/decisions.json` (DEC-232..DEC-237 added)
- `db-export/planning_items.json` (PI-050 added; PI-030 status updated to Resolved)
- `db-export/commits.json` (NEW file — CM-0001, CM-0002, CM-0003 ingested; first appearance of this snapshot)
- `db-export/workstreams.json` (WS-009 added from the pre-step)
- `db-export/close_out_payloads.json` (COP-074 lazy)
- `db-export/deposit_events.json` (DEP-053 or higher lazy)
- `db-export/references.json` (+25 give or take)
- `db-export/change_log.json` (audit rows for every write)
- `deposit-event-logs/dep_NNN.log` (apply stdout tee, where NNN is the new DEP identifier)

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect changed snapshot files
git status PRDs/product/crmbuilder-v2/db-export/
git status PRDs/product/crmbuilder-v2/deposit-event-logs/

# Confirm commits.json now exists
ls -la PRDs/product/crmbuilder-v2/db-export/commits.json

# Commit
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "Apply SES-074 close-out: PI-030 build closure — first nine-section v0.8 payload

Records landed via apply_close_out.py against the CRMBUILDER engagement:
- 1 session (SES-074 — PI-030 build closure, first nine-section payload
  acceptance test; methodology §10/§5.5/§4.0/§5.3/§5.7 amendments
  committed alongside in a separate commit)
- 1 conversation (CONV-046 — first build-closure conversation per DEC-232;
  member of WS-009; records SES-074; purpose opens with 'Build closure for
  SES-070 — ' per DEC-236's convention)
- 3 commits (CM-0001 = 70d88e6 slice A, CM-0002 = 2b5557d slice B,
  CM-0003 = c6ff67a slice C — first-ever commit-record ingestion in the
  CRMBUILDER engagement; commit_conversation_id = CONV-046 on all three)
- 0 work_tickets
- 6 decisions:
  * DEC-232 — Build closure conversation type recognized
  * DEC-233 — Commit-array scoping for parallel-workstream closures; PI-050
    surfaced for helper evolution
  * DEC-234 — Resolves attribution discipline preserved; only PI-030 flipped
  * DEC-235 — Executor-improvisation fixes get no governance record
  * DEC-236 — Build closure conversation_purpose convention 'Build closure
    for SES-NNN — '
  * DEC-237 — WS-009 promotion + methodology §4.0 example fix
- 1 planning item (PI-050 — extend enumerate_commits.py with explicit-list
  mode; status Open, may be subsumed by PI-033)
- 7 payload references (6 decided_in for DEC-232..DEC-237 -> SES-074 plus
  1 is_about for SES-074 -> PI-050)
- 1 resolves edge: CONV-046 -[resolves]-> PI-030 — server-side atomic flip
  by slice A on the resolves_planning_items section transitions PI-030
  Open -> Resolved
- 1 addresses edge: CONV-046 -[addresses]-> PI-032 — methodology rollout
  partially advanced by this closure's §10/§5.5/§4.0 amendments but
  not resolved
- 1 close_out_payload lazy-created (COP-074)
- 1 deposit_event lazy-created (DEP head + 1)
- 1 workstream pre-created (WS-009 — Code Change Lifecycle workstream
  status in_flight) via apply-prompt /workstreams POST per DEC-237

PI-030 status: Open -> Resolved (atomic flip). PI-027, PI-028, PI-029,
PI-032 remain Open by deliberate attribution discipline per DEC-234;
PI-033's Phase 3 backfill resolves them.

First end-to-end use of all five v0.8 sections (conversation, commits,
work_tickets [empty], resolves_planning_items, addresses_planning_items).
The PI-030 build's functional acceptance test passes."

git pull --rebase origin main
git push
```

---

## Done

Reply with:

- Pre-apply heads: actual (sessions / decisions / planning_items / conversations / workstreams / commits / COP / DEP heads plus reference count)
- WS-009 pre-step outcome: `Created` on first run, `already exists` on re-run
- Apply output record counts: 1 session OK, 1 conversation OK, 0 work_tickets, 1 planning_item OK, 3 commits OK, 6 decisions OK, 7 references OK, 1 resolves OK (PI-030 flipped Open → Resolved), 1 addresses OK, 0 SKIPs on first run
- Post-apply heads: SES-074, DEC-237, PI-050, CONV-046, WS-009, CM-0003, COP-074 (lazy), DEP-053 or higher (lazy), references ≈ pre + 25
- PI-030 status confirmed `Resolved` via `GET /planning-items/PI-030`
- CONV-046's four expected outbound edges all present (`conversation_belongs_to_workstream` to WS-009, `conversation_records_session` to SES-074, `resolves` to PI-030, `addresses` to PI-032) via `GET /references?source_id=CONV-046`
- Three commit records ingested with `commit_conversation_id = CONV-046` via `GET /commits`
- Snapshot commit SHA
- Next: nothing post-apply. The methodology amendments (§10 new section, §5.5 clarification, §4.0 worked-example fix, §5.3/§5.7 cross-refs, change-log row, Last Updated bump) are already on `origin/main` from the same sandbox push that committed this apply prompt and the payload — the `git pull --rebase` in the pre-flight step pulled them down before the apply ran. The only post-apply commit is the snapshot regeneration above. PI-050 sits Open awaiting either a dedicated helper-extension conversation or absorption by PI-033's backfill.
