# CLAUDE-CODE-PROMPT — Apply SES-069 close-out payload

**Last Updated:** 05-24-26 15:30
**Purpose:** Apply the SES-069 close-out payload — the PI-023 workstream-state reconciliation utility planning conversation. Lands DEC-216 (Phase 1 references-orphan formally acknowledged), DEC-217 (invariant scope Classes 1+2+3), DEC-218 (allowlist mechanism: YAML config file), DEC-219 (read mechanism: snapshots only), DEC-220 (output format: structured plain text with exit 0/1/2), PI-048 (ses_056.json stale blocks-vocabulary migration), and 8 supporting references (six decided_in edges from each new DEC/PI to SES-069, plus two SES-069 is_about edges to PI-023 and PI-048).
**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_069.json`
**Predecessors:** SES-068's apply must have landed (heads SES-068 / DEC-215 / PI-047 / COP-068 / DEP-046; references count 817). If pre-flight identifier-head verification finds an unexpected head advanced past these (e.g., a parallel-sandbox session has committed an unrelated apply during the SES-069 authoring window), halt and surface the drift before proceeding — DEC-216..220 and PI-048 may need to be rebased.
**Successor (sequential, run AFTER this apply):** PI-023 Claude Code prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-023-workstream-state-reconciliation-utility.md`. The Claude Code prompt authors `crmbuilder-v2/scripts/reconcile.py` and `PRDs/product/crmbuilder-v2/reconciliation-allowlist.yaml`, runs the first reconciliation (expecting 7 findings all allowlisted, exit 0), and transitions PI-022 from Open to Resolved. Run that prompt second; this apply prompt does NOT transition PI-022.

---

## Scope

Apply `close-out-payloads/ses_069.json` using the existing `crmbuilder-v2/scripts/apply_close_out.py` script. The payload contains:

- 1 session record (SES-069)
- 5 decisions:
    * DEC-216 — Phase 1 references-orphan formally acknowledged (embedded follow-on from DEC-218's allowlist mechanism)
    * DEC-217 — PI-023 invariant scope: Classes 1+2+3 (file vs record presence; record-claims-vs-record-presence; decision-vs-records consistency with supersedes traversal); Classes 4 and 5 deferred
    * DEC-218 — PI-023 allowlist mechanism: YAML config file at `PRDs/product/crmbuilder-v2/reconciliation-allowlist.yaml`; each entry carries decided_in (DEC-NNN) or planning_item (PI-NNN)
    * DEC-219 — PI-023 read mechanism: db-export JSON snapshots only, no V2 REST API dependency (overrides the kickoff's proposed REST-API default)
    * DEC-220 — PI-023 output format: structured plain text on stdout, severity-prefixed, exit 0/1/2
- 1 planning item (PI-048 — Migrate stale 'blocks' relationship references in ses_056.json to the v0.8-renamed 'blocked_by' kind, or formally accept stale-vocab in historical payloads)
- 8 references:
    * `decision:DEC-216 -[decided_in]-> session:SES-069`
    * `decision:DEC-217 -[decided_in]-> session:SES-069`
    * `decision:DEC-218 -[decided_in]-> session:SES-069`
    * `decision:DEC-219 -[decided_in]-> session:SES-069`
    * `decision:DEC-220 -[decided_in]-> session:SES-069`
    * `planning_item:PI-048 -[decided_in]-> session:SES-069`
    * `session:SES-069 -[is_about]-> planning_item:PI-023`
    * `session:SES-069 -[is_about]-> planning_item:PI-048`

The payload is idempotent on re-run; HTTP 409 SKIPs are treated as already-present.

No supersedes edges in this payload (DEC-216 acknowledges a historical pattern; it does not supersede a prior decision).

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
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_069.json

# Verify the API is routed to the CRMBUILDER engagement
curl -s http://127.0.0.1:8765/sessions \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), 'sessions - latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"

# Verify SES-068 has landed (the predecessor)
curl -sf http://127.0.0.1:8765/sessions/SES-068 >/dev/null && echo "SES-068 OK (predecessor present)" || echo "SES-068 MISSING — apply SES-068 first"

# Verify DEC-215 has landed (most recent DEC head before this apply)
curl -sf http://127.0.0.1:8765/decisions/DEC-215 >/dev/null && echo "DEC-215 OK" || echo "DEC-215 MISSING — apply SES-068 first"

# Confirm DEC-216..220 are not yet present (first-run sanity)
for d in DEC-216 DEC-217 DEC-218 DEC-219 DEC-220; do
  curl -s -o /dev/null -w "$d: %{http_code}\n" "http://127.0.0.1:8765/decisions/$d"
done
# Expect five 404s on first run.

# Confirm PI-048 is not yet present
curl -s -o /dev/null -w "PI-048: %{http_code}\n" "http://127.0.0.1:8765/planning-items/PI-048"
# Expect 404 on first run.

# Capture pre-apply heads
echo "=== Pre-apply heads ==="
echo "Sessions (expect SES-068):"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Decisions (expect DEC-215):"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Planning items (expect PI-047):"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Close-out payloads (expect COP-068):"
curl -s http://127.0.0.1:8765/close-out-payloads | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['close_out_payload_identifier'] for r in d)[-1] if d else 'none')"
echo "Deposit events (expect DEP-046):"
curl -s http://127.0.0.1:8765/deposit-events | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['deposit_event_identifier'] for r in d)[-1] if d else 'none')"
echo "References count (expect 817):"
curl -s 'http://127.0.0.1:8765/references?limit=4000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', len(d))"
```

Expected pre-apply state:

| Resource | Head |
|---|---|
| Sessions | SES-068 |
| Decisions | DEC-215 |
| Planning items | PI-047 |
| Close-out payloads | COP-068 |
| Deposit events | DEP-046 |
| References | 817 |

If any head is advanced past the expected value, a parallel sandbox session has committed during the SES-069 authoring window. Halt and rebase DEC-216..220 / PI-048 to the next-available identifiers; update `close-out-payloads/ses_069.json` accordingly before retrying the apply.

---

## Apply

Run the apply script against the payload:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_069.json
```

Expected output structure:

- 1 session OK (SES-069)
- 5 decisions OK (DEC-216, DEC-217, DEC-218, DEC-219, DEC-220)
- 1 planning item OK (PI-048)
- 8 references OK (6 decided_in, 2 is_about)
- 1 close_out_payload lazy-created (COP-069 — derived from filename `ses_069.json`)
- 1 deposit_event written at apply close (lazy-created — DEP-047, head + 1)

If any record returns 409 SKIP on first run, halt and investigate — first run should have zero SKIPs. On re-run, every record should SKIP idempotently.

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Sessions (expect SES-069):"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Decisions (expect DEC-220):"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Planning items (expect PI-048):"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Close-out payloads (expect COP-069 lazy-created):"
curl -s http://127.0.0.1:8765/close-out-payloads | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['close_out_payload_identifier'] for r in d)[-1])"
echo "Deposit events (expect DEP-047 lazy-created):"
curl -s http://127.0.0.1:8765/deposit-events | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['deposit_event_identifier'] for r in d)[-1])"

# Spot-check each new DEC
echo ""
echo "=== Decisions DEC-216..220 ==="
for d in DEC-216 DEC-217 DEC-218 DEC-219 DEC-220; do
  echo "$d:"
  curl -s "http://127.0.0.1:8765/decisions/$d" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80] + ('...' if len(d['title']) > 80 else '')); print('  status:', d['status'])"
done

# Spot-check PI-048
echo ""
echo "=== PI-048 ==="
curl -s "http://127.0.0.1:8765/planning-items/PI-048" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:100] + ('...' if len(d['title']) > 100 else '')); print('  status:', d['status'])"

# Confirm decided_in edges landed (6 expected: from DEC-216..220 and PI-048 to SES-069)
echo ""
echo "=== decided_in edges to SES-069 (expect 6 + DEC-215's from SES-068's apply = 7 + DEC-215 + ...) ==="
curl -s 'http://127.0.0.1:8765/references?target_type=session&target_id=SES-069' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(' ', r['source_type'], r['source_id'], '->', r['target_id'], '[', r['relationship_kind'], ']') for r in d]"
# Expect 6 rows: 5 from DEC-216..220 and 1 from PI-048, all decided_in.

# Confirm is_about edges from SES-069 landed (2 expected)
echo ""
echo "=== is_about edges from SES-069 (expect 2: -> PI-023, -> PI-048) ==="
curl -s 'http://127.0.0.1:8765/references?source_type=session&source_id=SES-069' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(' ', r['source_id'], '->', r['target_type'], r['target_id'], '[', r['relationship_kind'], ']') for r in d]"

# Reference total delta
echo ""
echo "Reference total after apply:"
curl -s 'http://127.0.0.1:8765/references?limit=4000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
# Expected delta from pre-apply (817): +16 or +17
#   8 from payload (6 decided_in, 2 is_about)
#   7 wrote_record edges from the apply script's lazy-created DEP (1 session + 5 decisions + 1 PI)
#   1 deposit_event_applies_close_out_payload from the lazy DEP to the lazy COP-069
#   (possibly 1 close_out_payload_produced_by_conversation edge for the lazy COP-069)
#   Total: 16 or 17.

# Verify the snapshot regenerated automatically via _refresh_snapshot hook
echo ""
echo "=== Snapshot regeneration check ==="
cd ..
git diff --stat PRDs/product/crmbuilder-v2/db-export/
# Expect updates to sessions.json, decisions.json, planning_items.json,
# references.json, close_out_payloads.json, deposit_events.json,
# and change_log.json (the audit row for this apply).
```

Expected post-apply heads: SES-069, DEC-220, PI-048, COP-069 (lazy), DEP-047 (lazy). References total +16 or +17 from the pre-apply 817.

---

## Commit snapshot regeneration

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect changed snapshot files
git status PRDs/product/crmbuilder-v2/db-export/
git status PRDs/product/crmbuilder-v2/deposit-event-logs/

# Commit
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "Apply SES-069 close-out: PI-023 reconciliation utility planning — DEC-216..220 and PI-048

Records landed via apply_close_out.py against the CRMBUILDER engagement:
- 1 session (SES-069)
- 5 decisions:
  * DEC-216 — Phase 1 references-orphan formally acknowledged
    (embedded follow-on so the reconciliation allowlist entry has a
    canonical database record to cite; Phase 1's only prior
    acknowledgement was an inline script comment in
    backfill_governance_phase_1.py)
  * DEC-217 — PI-023 invariant scope: Classes 1+2+3 (file vs record
    presence; record-claims-vs-record-presence; decision-vs-records
    consistency with supersedes-edge traversal); Classes 4 and 5
    deferred
  * DEC-218 — PI-023 allowlist mechanism: YAML config file at
    PRDs/product/crmbuilder-v2/reconciliation-allowlist.yaml; each
    entry carries decided_in (DEC-NNN) or planning_item (PI-NNN) as
    required canonical-record reference
  * DEC-219 — PI-023 read mechanism: db-export JSON snapshots only,
    no V2 REST API dependency (overrides the kickoff's proposed
    REST-API default because the Claude.ai sandbox cannot reach the
    local 127.0.0.1:8765 API)
  * DEC-220 — PI-023 output format: structured plain text on stdout,
    severity-prefixed, exit 0 (no drift) / 1 (unallowlisted drift) /
    2 (configuration error)
- 1 planning item:
  * PI-048 — Migrate stale 'blocks' relationship references in
    ses_056.json to the v0.8-renamed 'blocked_by' kind, or formally
    accept stale-vocab in historical payloads as an immutable
    archival convention; surfaced during PI-023's planning while
    testing reconcile.py against the current snapshot
- 8 payload references:
  * 5x decision:DEC-21X -[decided_in]-> session:SES-069
  * 1x planning_item:PI-048 -[decided_in]-> session:SES-069
  * 1x session:SES-069 -[is_about]-> planning_item:PI-023
  * 1x session:SES-069 -[is_about]-> planning_item:PI-048
- 1 close_out_payload lazy-created (COP-069)
- 1 deposit_event lazy-created (DEP-047)

PI-022's planning item status remains at Open after this apply. The
PI-022 transition Open->Resolved is performed by the PI-023 Claude
Code prompt at
PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-023-
workstream-state-reconciliation-utility.md, gated on reconcile.py's
first invocation producing 7 findings all allowlisted with exit 0.

Next: run the PI-023 Claude Code prompt to author reconcile.py and
the allowlist, run the first reconciliation, and transition PI-022."

# Per the 'you commit, I push' convention in Claude Code context, do NOT push here.
# Doug reviews and pushes manually:
#   git pull --rebase origin main
#   git push
```

---

## Done

Reply with:

- Pre-apply heads: SES-068, DEC-215, PI-047, COP-068, DEP-046, references = 817 (expected)
- Post-apply heads: SES-069, DEC-220, PI-048, COP-069 (lazy), DEP-047 (lazy), references = 833 or 834
- Record counts: 1 session OK, 5 decisions OK, 1 planning item OK, 8 references OK, 0 SKIPs, 1 lazy COP-069, 1 lazy DEP-047
- Spot-check confirmation that DEC-216..220 and PI-048 are present at status="Active" (decisions) / status="Open" (PI-048)
- decided_in edges to SES-069 confirmed (6 rows expected: 5 from DEC-216..220, 1 from PI-048)
- is_about edges from SES-069 confirmed (2 rows expected: SES-069 -> PI-023, SES-069 -> PI-048)
- Snapshot commit SHA
- Next: run the PI-023 Claude Code prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-023-workstream-state-reconciliation-utility.md` to author reconcile.py + reconciliation-allowlist.yaml, run the first reconciliation, and transition PI-022 from Open to Resolved.
