# CLAUDE-CODE-PROMPT — Apply SES-068 close-out payload

**Last Updated:** 05-24-26 00:15
**Purpose:** Apply the SES-068 close-out payload — the tight follow-up ARCHITECTURE-mode conversation (continuation within the same Claude.ai session as SES-066) that closed the governance gap from PI-026's Option-I apply-time deviation. Lands DEC-215 (Option I supersedes DEC-206 after the vocab.py schema-vs-spec contradiction was discovered at apply time), PI-046 (vocab.py contradiction enters the planning queue), PI-047 (ses_030 / ses_036 duplicate-session artifact enters the planning queue), and four supporting references (the DEC-215 supersedes DEC-206 edge, DEC-215's decided_in to SES-068, and two SES-068 is_about edges to PI-046 and PI-047).
**Identifier rebase note:** This work was initially drafted as SES-067 / DEC-211. A parallel sandbox session committed c0b898e during the authoring window (PI-029 slice B build planning, claiming SES-067 / DEC-211..214). Rebased to SES-068 / DEC-215 to avoid collision. Planning items PI-046 / PI-047 were not claimed by PI-029 slice B.
**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_068.json`
**Predecessors:** PI-026 backfill must have landed (heads SES-066 / DEC-210 / PI-045 / COP-066 / DEP-043). PI-029 slice B's apply (SES-067 close-out at `CLAUDE-CODE-PROMPT-apply-close-out-ses-067.md`) may or may not have landed yet — apply order between SES-067 and SES-068 is unconstrained. The COP identifiers derive from filename (ses_067.json → COP-067; ses_068.json → COP-068) so no collision; DEPs are assigned in apply order from the next-identifier helper.
**Successor:** PI-023 (workstream-state reconciliation utility) kickoff is to be authored next at `PRDs/product/crmbuilder-v2/pi-023-workstream-state-reconciliation-utility-kickoff.md` as a Claude.ai deliverable.

---

## Scope

Apply `close-out-payloads/ses_068.json` using the existing `crmbuilder-v2/scripts/apply_close_out.py` script. The payload contains:

- 1 session record (SES-068)
- 1 decision (DEC-215)
- 2 planning items (PI-046, PI-047)
- 4 references:
    * `decision:DEC-215 -[supersedes]-> decision:DEC-206`
    * `decision:DEC-215 -[decided_in]-> session:SES-068`
    * `session:SES-068 -[is_about]-> planning_item:PI-046`
    * `session:SES-068 -[is_about]-> planning_item:PI-047`

The supersedes edge is the canonical mechanism for marking DEC-206 as overridden by DEC-215. DEC-206 itself remains at status="Active" in the decisions table — downstream consumers respect supersession via the graph edge, not via a status enum value.

This is the first decision-supersedes-decision edge in the database. Both source and target types are "decision" so the vocab admits the kind via `_kinds_for_pair`'s same-type supersession clause.

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
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_068.json

# Verify the API is routed to the CRMBUILDER engagement
curl -s http://127.0.0.1:8765/sessions \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), 'sessions - latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
# Expect at minimum SES-066 (PI-026 backfill landed). If PI-029 slice B's SES-067 apply has also landed,
# expect SES-067 as the head. Either is fine; this apply produces SES-068 regardless.

# Verify the PI-026 backfill has landed (DEP-043)
curl -sf http://127.0.0.1:8765/deposit-events/DEP-043 >/dev/null && echo "DEP-043 OK (PI-026 backfill landed)" || echo "DEP-043 MISSING — run the PI-026 backfill prompt first"

# Verify DEC-206 is present (the target of the supersedes edge)
curl -sf http://127.0.0.1:8765/decisions/DEC-206 >/dev/null && echo "DEC-206 OK (target of supersedes edge)" || echo "DEC-206 MISSING — apply SES-066 first"

# Confirm there are no existing supersedes edges from DEC-215 (first run should have none)
curl -s 'http://127.0.0.1:8765/references?source_id=DEC-215' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(f'  Existing DEC-215 outbound refs: {len(d)} (expect 0 on first run)')"

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

Expected pre-apply state depends on whether PI-029 slice B's SES-067 has been applied:

| State | Sessions head | Decisions head | COP head | DEP head |
|---|---|---|---|---|
| PI-029 slice B NOT yet applied | SES-066 | DEC-210 | COP-066 | DEP-043 |
| PI-029 slice B applied | SES-067 | DEC-214 | COP-067 | DEP-044 |

Either is acceptable; this apply produces SES-068 / DEC-215 either way.

---

## Apply

Run the apply script against the payload:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_068.json
```

Expected output structure:

- 1 session OK (SES-068)
- 1 decision OK (DEC-215)
- 2 planning items OK (PI-046, PI-047)
- 4 references OK (1 supersedes, 1 decided_in, 2 is_about)
- 1 close_out_payload lazy-created (COP-068 — derived from filename `ses_068.json`)
- 1 deposit_event written at apply close (lazy-created — DEP identifier depends on current head; expect DEP-044 if PI-029 slice B unapplied, DEP-045 if applied)

If any record returns 409 SKIP on first run, halt and investigate — first run should have zero SKIPs. On re-run, every record should SKIP idempotently.

The supersedes edge is the first decision-supersedes-decision edge in the database. If the POST fails with a relationship-validation error, the vocab.py read was wrong and this prompt's pre-flight assumptions need correction — halt and report.

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Sessions (expect SES-068):"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Decisions (expect DEC-215):"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Planning items (expect PI-047):"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Close-out payloads (expect COP-068 lazy-created):"
curl -s http://127.0.0.1:8765/close-out-payloads | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['close_out_payload_identifier'] for r in d)[-1])"
echo "Deposit events (expect DEP-044 or DEP-045 lazy-created):"
curl -s http://127.0.0.1:8765/deposit-events | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['deposit_event_identifier'] for r in d)[-1])"

# Spot-check DEC-215
curl -s http://127.0.0.1:8765/decisions/DEC-215 | python3 -m json.tool | head -10

# Confirm the supersedes edge landed
curl -s 'http://127.0.0.1:8765/references?source_type=decision&source_id=DEC-215' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(r['source_id'], '->', r['target_id'], '[', r['relationship_kind'], ']') for r in d]"
# Expect at minimum:
#   DEC-215 -> DEC-206 [ supersedes ]
#   DEC-215 -> SES-068 [ decided_in ]

# Spot-check PI-046 and PI-047
for pi in PI-046 PI-047; do
  echo ""
  echo "$pi:"
  curl -s "http://127.0.0.1:8765/planning-items/$pi" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title']); print('  status:', d['status'])"
done

# Reference total delta
echo ""
echo "Reference total after apply:"
curl -s 'http://127.0.0.1:8765/references?limit=4000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
# Expected delta: +9 or +10 from pre-apply
#   4 from payload (supersedes, decided_in, 2 is_about)
#   4 wrote_record edges from the apply script's lazy-created DEP (1 session + 1 decision + 2 planning_items)
#   1 deposit_event_applies_close_out_payload from the lazy DEP to the lazy COP-068
#   (possibly 1 close_out_payload_produced_by_conversation edge for the lazy COP-068)
```

Expected post-apply heads: SES-068, DEC-215, PI-047, COP-068 (lazy), DEP-044 or DEP-045 (lazy). Reference total +9 or +10.

---

## Commit snapshot regeneration

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect changed snapshot files
git status PRDs/product/crmbuilder-v2/db-export/
git status PRDs/product/crmbuilder-v2/deposit-event-logs/

# Commit
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "Apply SES-068 close-out: DEC-215 supersedes DEC-206 (PI-026 Option I); PI-046 and PI-047 enter planning queue

Records landed via apply_close_out.py against the CRMBUILDER engagement:
- 1 session (SES-068)
- 1 decision (DEC-215 — Option I skip references as deposit_event_
  wrote_record targets, mirror Phase 1's pattern, supersedes DEC-206
  after apply-time discovery of the vocab.py schema-vs-spec
  contradiction; the parallel sandbox session's commits 384c224 and
  944495e adopted Option I and ran the backfill; this close-out
  records the override in the governance graph)
- 2 planning items:
  * PI-046 — Resolve vocab.py schema-vs-spec contradiction for
    reference targets in deposit_event_wrote_record edges
  * PI-047 — Resolve ses_030 / ses_036 duplicate-session artifact
    and the 4 unresolvable references ses_030's payload claims
- 4 payload references:
  * decision:DEC-215 -[supersedes]-> decision:DEC-206 (first
    decision-supersedes-decision edge in the database)
  * decision:DEC-215 -[decided_in]-> session:SES-068
  * session:SES-068 -[is_about]-> planning_item:PI-046
  * session:SES-068 -[is_about]-> planning_item:PI-047
- 1 close_out_payload lazy-created (COP-068)
- 1 deposit_event lazy-created (DEP head + 1)

Identifier rebase note: this work was initially drafted as SES-067 /
DEC-211. A parallel sandbox session committed c0b898e during the
authoring window (PI-029 slice B build planning, claiming SES-067 /
DEC-211..214). Rebased to SES-068 / DEC-215 to avoid collision.

Closes the governance gap created when PI-026's parallel-sandbox
Option I refactor diverged from DEC-206 without recording the
supersession.

PI-023 (workstream-state reconciliation utility) kickoff is to be
authored next as a Claude.ai deliverable at PRDs/product/crmbuilder-
v2/pi-023-workstream-state-reconciliation-utility-kickoff.md. The
kickoff must call out that DEC-215 supersedes DEC-206 and that the
reconciliation utility's audit logic must respect supersedes edges
when computing 'active decisions honored by records'."

git pull --rebase origin main
git push
```

---

## Done

Reply with:

- Pre-apply heads: actual (depends on PI-029 slice B apply state), references = N
- Post-apply heads: SES-068, DEC-215, PI-047, COP-068 (lazy), DEP head + 1 (lazy), references = N + 9 or 10
- Record counts: 1 session OK, 1 decision OK, 2 planning items OK, 4 references OK, 0 SKIPs, 1 lazy COP-068, 1 lazy DEP
- The supersedes edge confirmed via `curl -s 'http://127.0.0.1:8765/references?source_type=decision&source_id=DEC-215'`
- Snapshot commit SHA
- Next: author PI-023 workstream-state reconciliation utility kickoff at `PRDs/product/crmbuilder-v2/pi-023-workstream-state-reconciliation-utility-kickoff.md` as a Claude.ai deliverable
