# CLAUDE-CODE-PROMPT — apply close-out SES-098 (UI gap discovery + PI-091/092/093 authoring)

**Last Updated:** 05-27-26
**Operating mode:** DETAIL
**Series:** WS-012 (Parallel agent orchestrator and executive summary) — follow-on PI discovery
**Slice:** Apply the SES-098 close-out payload to the V2 governance DB
**Status:** Ready to execute. No migration; no code commits. Pure governance authoring: one session, one conversation, three planning items, two embedded conversation references.

> **Why this session record exists.** PI-074 (resolved in SES-097) added the `executive_summary` column to the planning_items, decisions, and sessions tables but did not scope the desktop UI work that surfaces the field in the create/edit dialogs and master panes. SES-098 is the discovery session that filed the gap as three area-disjoint PIs (PI-091 planning_items UI, PI-092 decisions UI, PI-093 sessions UI), one per entity type so the orchestrator (PI-081) can dispatch them in parallel to agents working on disjoint file sets.

> **Identifier-head capture per DEC-300.** Heads captured at session start (live API): SES-097, CONV-067, DEC-318, PI-090. This payload reserves SES-098, CONV-068, no DECs, PI-091/092/093. Pre-flight below MUST re-verify before apply.

---

## Net Effect

Apply `PRDs/product/crmbuilder-v2/close-out-payloads/ses_098.json` to the V2 governance DB via the standard apply script. Creates:

- **SES-098** — UI gap discovery session, executive_summary populated (561 chars)
- **CONV-068** — single conversation, status complete, member of WS-012, records SES-098
- **PI-091** — Surface executive_summary in planning_items UI (status Open, executive_summary 422 chars)
- **PI-092** — Surface executive_summary in decisions UI (status Open, executive_summary 412 chars)
- **PI-093** — Surface executive_summary in sessions UI — no edit dialog per DEC-013 (status Open, executive_summary 455 chars)
- close_out_payload COP-NNN + deposit_event DEP-NNN (lazy-created)

No new decisions, no work tickets, no commits, no resolves edges. `addresses_planning_items[]` is empty.

---

## Pre-flight

1. `pwd` → repo clone root (`~/Dropbox/Projects/crmbuilder`). Stop if unexpected.

2. Clean working tree:
   ```bash
   git status --porcelain
   ```
   Expected: only the payload and this apply prompt staged for commit (they land in one commit before apply).

3. Payload exists:
   ```bash
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_098.json
   ```

4. API health:
   ```bash
   curl -sf http://127.0.0.1:8765/health
   ```

5. **Pre-apply identifier-head capture per DEC-300** (re-verify against live API):
   ```bash
   curl -sf http://127.0.0.1:8765/sessions       | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(s['identifier'] for s in d); print('SES head:', ids[-1])"
   curl -sf http://127.0.0.1:8765/conversations  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(c['conversation_identifier'] for c in d); print('CONV head:', ids[-1])"
   curl -sf http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(p['identifier'] for p in d); print('PI head:', ids[-1])"
   ```
   Expected: SES head = SES-097, CONV head = CONV-067, PI head = PI-090. If any head is ≥ the identifiers this payload reserves (SES-098, CONV-068, PI-091/092/093), the payload must be renumbered before apply — see Renumbering below.

---

## Renumbering (if heads have advanced)

If pre-flight step 5 reveals any head equal to or greater than this payload's reserved slot:

1. Compute new heads: `new_head = live_head + 1`.
2. Edit `ses_098.json` and update every internal reference: session.identifier, conversation.conversation_identifier, the two embedded `conversation.references[]` source_ids, each planning_items[].identifier, and any mention of these identifiers in description text.
3. Rename the payload to `ses_NNN.json` matching the new SES identifier.
4. Rename this apply prompt to `CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md`.
5. Repeat pre-flight step 5.
6. Proceed to Apply.

---

## Apply

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_098.json
```

Expected OK counts on success:

- 1 session created (SES-098, with executive_summary populated)
- 1 conversation created (CONV-068)
- 0 work_tickets, 0 commits, 0 decisions
- 3 planning_items created (PI-091, PI-092, PI-093)
- 0 top-level references created
- 2 embedded conversation references created (conversation_belongs_to_workstream → WS-012, conversation_records_session → SES-098)
- 0 resolves edges, 0 addresses edges
- 1 close_out_payload lazy-created (COP-NNN)
- 1 deposit_event lazy-created (DEP-NNN)

Any 4xx response halts the apply — read the error and either correct the payload or surface to Doug.

---

## Post-apply verification

1. Identifier-head advancement:
   ```bash
   curl -sf http://127.0.0.1:8765/sessions       | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(s['identifier'] for s in d); print('SES head after:', ids[-1])"
   curl -sf http://127.0.0.1:8765/conversations  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(c['conversation_identifier'] for c in d); print('CONV head after:', ids[-1])"
   curl -sf http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(p['identifier'] for p in d); print('PI head after:', ids[-1])"
   ```
   Expect SES-098, CONV-068, PI-093.

2. Each new PI is Open:
   ```bash
   for n in 091 092 093; do
     curl -sf http://127.0.0.1:8765/planning-items/PI-$n | python3 -c "import sys,json; p=json.load(sys.stdin)['data']; print(f\"PI-{p['identifier'].split('-')[-1]}: {p['status']} | exec_summary len={len(p.get('executive_summary') or '')}\")"
   done
   ```
   Expect three rows of `Open | exec_summary len=4xx`.

3. SES-098.executive_summary round-trips:
   ```bash
   curl -sf http://127.0.0.1:8765/sessions/SES-098 | python3 -c "import sys,json; s=json.load(sys.stdin)['data']; print('SES-098.executive_summary len:', len(s.get('executive_summary') or ''))"
   ```
   Expect `561`.

4. CONV-068 membership + records edges:
   ```bash
   curl -sf "http://127.0.0.1:8765/references?source_id=CONV-068" | python3 -m json.tool
   ```
   Expect two rows: conversation_belongs_to_workstream → WS-012 and conversation_records_session → SES-098.

---

## Commit snapshot regeneration

After apply, commit the regenerated snapshots and deposit-event log together in one commit on main:

```bash
cd ~/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/db-export/
git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_098.json
git add PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-098.md
git add PRDs/product/crmbuilder-v2/deposit-event-logs/ 2>/dev/null || true
git commit -m "v2: SES-098 close-out applied — UI gap discovery + PI-091/092/093 authoring (executive_summary desktop UI for planning_items, decisions, sessions)"
```
