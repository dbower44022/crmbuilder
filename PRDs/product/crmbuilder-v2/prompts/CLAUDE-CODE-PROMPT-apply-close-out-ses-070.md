# CLAUDE-CODE-PROMPT — Apply SES-070 close-out payload

**Last Updated:** 05-24-26 17:30
**Purpose:** Apply the SES-070 close-out payload — the ARCHITECTURE-mode planning conversation that settled PI-030's three stop-the-flow questions (Q0 full scope, Q1 emit-time helper, Q2 conversation block) and authored three Claude Code slice prompts (A: methodology + resolves; B: apply extensions; C: enumerate_commits.py helper). Lands four decisions (DEC-221..224) and five supporting references (four decided_in edges from each DEC to SES-070, one is_about edge from SES-070 to PI-030).
**Identifier rebase note:** This work claims SES-070 / DEC-221..224. The latest applied head at conversation close is SES-068 (per current snapshot); ses_069.json is queued and may apply before this. Either ordering produces SES-070 for this payload via filename-based COP identifier derivation. If a parallel sandbox commit lands first claiming SES-070 or DEC-221..224, rebase by editing this payload's identifiers and the four decided_in references before applying.
**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_070.json`
**Predecessors:** SES-068 (the PI-026 supersession + planning queue) must have landed. ses_069 (PI-023 reconciliation utility planning) may or may not have landed yet — apply order between ses_069 and ses_070 is unconstrained because COP identifiers derive from filename (ses_069.json → COP-069; ses_070.json → COP-070) and DEPs are assigned from the next-identifier helper at apply time.
**Successor:** Once this payload lands, run the three PI-030 slice prompts in dependency order at Doug's terminal via Claude Code:
1. `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-030-A-resolves-flip-and-methodology.md` (must run first; slice B depends on it)
2. `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-030-B-apply-close-out-extensions.md` (depends on slice A)
3. `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-030-C-enumerate-commits-helper.md` (independent; can run any time)

---

## Scope

Apply `close-out-payloads/ses_070.json` using the existing `crmbuilder-v2/scripts/apply_close_out.py` script. The payload contains:

- 1 session record (SES-070)
- 4 decisions (DEC-221, DEC-222, DEC-223, DEC-224)
- 0 planning items
- 5 references:
    * `decision:DEC-221 -[decided_in]-> session:SES-070`
    * `decision:DEC-222 -[decided_in]-> session:SES-070`
    * `decision:DEC-223 -[decided_in]-> session:SES-070`
    * `decision:DEC-224 -[decided_in]-> session:SES-070`
    * `session:SES-070 -[is_about]-> planning_item:PI-030`

The payload is in v0.7 format — no conversation block, no work_tickets, no commits, no resolves_planning_items, no addresses_planning_items. PI-030's slice prompts haven't executed yet, so the new sections haven't been wired into apply_close_out.py at the time this payload applies. The first close-out that USES the new sections will be authored after slice B lands.

The payload is idempotent on re-run; HTTP 409 SKIPs are treated as already-present.

---

## Pre-flight

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

# Clean working tree
git status

# Pull latest commits
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start the API:
#   uv run crmbuilder-v2-api &

# Verify the payload file exists
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_070.json

# Verify the API is routed to the CRMBUILDER engagement
curl -s http://127.0.0.1:8765/sessions \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), 'sessions - latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
# Expect at minimum SES-068 (PI-026 supersession landed). If ses_069's
# apply has also landed, expect SES-069 as the head. Either is fine;
# this apply produces SES-070 regardless.

# Verify SES-068 is present (predecessor)
curl -sf http://127.0.0.1:8765/sessions/SES-068 >/dev/null && echo "SES-068 OK (predecessor)" || echo "SES-068 MISSING — apply ses_068 first"

# Verify PI-030 is present (target of the is_about edge)
curl -sf http://127.0.0.1:8765/planning-items/PI-030 >/dev/null && echo "PI-030 OK (is_about target)" || echo "PI-030 MISSING — check planning queue"

# Confirm there are no existing decision records claiming DEC-221..224
for d in DEC-221 DEC-222 DEC-223 DEC-224; do
  curl -s -o /dev/null -w "$d: HTTP %{http_code}\n" http://127.0.0.1:8765/decisions/$d
done
# Expect: HTTP 404 for each on first run. If any returns 200, a parallel
# sandbox session has claimed the identifier; rebase the payload before
# applying.

# Capture pre-apply heads
echo "=== Pre-apply heads ==="
for endpoint in sessions decisions planning-items; do
  echo "$endpoint:"
  curl -s "http://127.0.0.1:8765/$endpoint" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
done
echo "Close-out payloads:"
curl -s http://127.0.0.1:8765/close-out-payloads | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['close_out_payload_identifier'] for r in d)[-1] if d else 'none')"
echo "Deposit events:"
curl -s http://127.0.0.1:8765/deposit-events | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['deposit_event_identifier'] for r in d)[-1] if d else 'none')"
echo "References (count):"
curl -s 'http://127.0.0.1:8765/references?limit=4000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', len(d))"
```

Expected pre-apply state depends on whether ses_069 has been applied:

| State | Sessions head | Decisions head | PI head | COP head | DEP head |
|---|---|---|---|---|---|
| ses_069 NOT yet applied | SES-068 | DEC-215 | PI-047 | COP-068 | DEP-043 or DEP-044 |
| ses_069 applied | SES-069 | DEC-220 | PI-048 | COP-069 | DEP-044 or DEP-045 |

Either is acceptable; this apply produces SES-070 / DEC-224 / PI head unchanged either way.

---

## Apply

Run the apply script against the payload:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_070.json
```

Expected output structure:

- 1 session OK (SES-070)
- 4 decisions OK (DEC-221, DEC-222, DEC-223, DEC-224)
- 0 planning items
- 5 references OK (4 decided_in, 1 is_about)
- 1 close_out_payload lazy-created (COP-070 — derived from filename `ses_070.json`)
- 1 deposit_event written at apply close (lazy-created — DEP identifier depends on current head)

If any record returns 409 SKIP on first run, halt and investigate — first run should have zero SKIPs. On re-run, every record should SKIP idempotently.

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Sessions (expect SES-070):"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Decisions (expect DEC-224):"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Planning items (unchanged from pre-apply):"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Close-out payloads (expect COP-070 lazy-created):"
curl -s http://127.0.0.1:8765/close-out-payloads | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['close_out_payload_identifier'] for r in d)[-1])"
echo "Deposit events (expect DEP head + 1 lazy-created):"
curl -s http://127.0.0.1:8765/deposit-events | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['deposit_event_identifier'] for r in d)[-1])"

# Spot-check DEC-221..224
for dec in DEC-221 DEC-222 DEC-223 DEC-224; do
  echo ""
  echo "$dec:"
  curl -s "http://127.0.0.1:8765/decisions/$dec" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80]); print('  status:', d['status'])"
done

# Confirm the four decided_in edges landed
echo ""
echo "decided_in edges from new decisions to SES-070:"
curl -s 'http://127.0.0.1:8765/references?source_type=decision&target_id=SES-070' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(' ', r['source_id'], '->', r['target_id'], '[', r['relationship_kind'], ']') for r in d if r['source_id'].startswith('DEC-22')]"
# Expect 4 lines: DEC-221, DEC-222, DEC-223, DEC-224 -> SES-070 [decided_in]

# Confirm the is_about edge to PI-030 landed
echo ""
echo "is_about edge from SES-070 to PI-030:"
curl -s 'http://127.0.0.1:8765/references?source_id=SES-070&target_id=PI-030' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(' ', r['source_id'], '->', r['target_id'], '[', r['relationship_kind'], ']') for r in d]"
# Expect 1 line: SES-070 -> PI-030 [is_about]

# Reference total delta
echo ""
echo "Reference total after apply:"
curl -s 'http://127.0.0.1:8765/references?limit=4000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
# Expected delta from pre-apply: +11 or +12
#   5 from payload (4 decided_in + 1 is_about)
#   5 wrote_record edges from the apply script's lazy-created DEP
#     (1 session + 4 decisions; 0 planning_items; references skipped per DEC-215)
#   1 deposit_event_applies_close_out_payload from the lazy DEP to lazy COP-070
#   (possibly 1 close_out_payload_produced_by_conversation edge for lazy COP-070)
```

Expected post-apply heads: SES-070, DEC-224, planning-items head unchanged, COP-070 (lazy), DEP head + 1 (lazy). Reference total +11 or +12.

---

## Commit snapshot regeneration

The apply script triggers automatic snapshot regeneration via the `_refresh_snapshot` hook in `crmbuilder-v2/src/crmbuilder_v2/access/engagement.py`. The db-export snapshot and change_log.json should both reflect the new records after the apply completes.

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect changed snapshot files
git status PRDs/product/crmbuilder-v2/db-export/
git status PRDs/product/crmbuilder-v2/deposit-event-logs/

# Confirm new records appear in the snapshot
grep -c '"identifier": "DEC-22[1-4]"' PRDs/product/crmbuilder-v2/db-export/decisions.json
# Expect: 4

grep -c '"identifier": "SES-070"' PRDs/product/crmbuilder-v2/db-export/sessions.json
# Expect: 1

# Verify change_log.json got new audit rows for the apply
python3 -c "
import json
log = json.load(open('PRDs/product/crmbuilder-v2/db-export/change_log.json'))
recent = [r for r in log if r.get('entity_identifier', '').startswith(('SES-070', 'DEC-22', 'COP-070'))]
print(f'New audit rows for SES-070/DEC-221..224/COP-070: {len(recent)}')
"
# Expect at minimum: 1 session insert + 4 decision inserts + 1 COP insert + 1 DEP insert + 5 ref inserts = 12 audit rows (more if wrote_record edges are logged separately)

# Commit
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "Apply SES-070 close-out: PI-030 architecture planning — full scope, emit-time helper, conversation block, resolves extension

Records landed via apply_close_out.py against the CRMBUILDER engagement:
- 1 session (SES-070)
- 4 decisions:
  * DEC-221 — PI-030 scope is the full four-section close-out payload
    extension per methodology §8 (commits + work_tickets +
    resolves_planning_items + addresses_planning_items), not commits-
    only. The kickoff's narrowing was editorial drift; settling full
    scope in one architecture conversation lets us answer apply-
    ordering once.
  * DEC-222 — Commit-metadata helper runs emit-time, sandbox-side, at
    crmbuilder-v2/scripts/enumerate_commits.py with full records in
    the payload per methodology §4.1 example. apply_close_out.py stays
    a dumb POSTer with no git subprocess dependency.
  * DEC-223 — Close-out payload format gains a conversation block;
    methodology §4 amended to add §4.0. Closes the FK gap where
    SES-061+ sessions had no associated conversation records,
    blocking commits' commit_conversation_id FK enforcement.
  * DEC-224 — POST /references extended to atomically flip target
    planning_item status to Resolved when relationship_kind ==
    'resolves'. Single endpoint handles both write paths; no
    dedicated /resolves endpoint needed.
- 0 planning items (PI-030 stays Open until the three slice prompts
  execute and complete the build work)
- 5 payload references:
  * decision:DEC-221 -[decided_in]-> session:SES-070
  * decision:DEC-222 -[decided_in]-> session:SES-070
  * decision:DEC-223 -[decided_in]-> session:SES-070
  * decision:DEC-224 -[decided_in]-> session:SES-070
  * session:SES-070 -[is_about]-> planning_item:PI-030
- 1 close_out_payload lazy-created (COP-070)
- 1 deposit_event lazy-created (DEP head + 1)

Three Claude Code slice prompts produced by this conversation are
queued for execution at Doug's terminal:

  1. CLAUDE-CODE-PROMPT-pi-030-A-resolves-flip-and-methodology.md
  2. CLAUDE-CODE-PROMPT-pi-030-B-apply-close-out-extensions.md
  3. CLAUDE-CODE-PROMPT-pi-030-C-enumerate-commits-helper.md

Dependency order: A must run before B (B's apply extensions depend on
A's extended POST /references for the resolves kind). C is independent
and can run at any time.

After all three slices land, the next sandbox conversation can produce
a close-out using the full nine-section format and the
enumerate_commits.py helper for the commits array."

# Per the 'you commit, I push' convention in Claude Code context,
# do NOT push here. Doug reviews and pushes manually:
#   git pull --rebase origin main
#   git push
```

---

## Done

Reply with:

- Pre-apply heads: actual (depends on ses_069 apply state), references = N
- Post-apply heads: SES-070, DEC-224, PI head unchanged, COP-070 (lazy), DEP head + 1 (lazy), references = N + 11 or N + 12
- Record counts: 1 session OK, 4 decisions OK, 0 planning items, 5 references OK, 0 SKIPs, 1 lazy COP-070, 1 lazy DEP
- The four decided_in edges confirmed via `curl -s 'http://127.0.0.1:8765/references?source_type=decision&target_id=SES-070'`
- The is_about edge to PI-030 confirmed
- Snapshot commit SHA
- Next: run the three PI-030 slice prompts in dependency order — A first (must complete before B), then B, then C (independent; any order relative to the others)
