# CLAUDE-CODE-PROMPT — apply close-out SES-098 (CRMBuilder dogfood Phase 2 Domain Discovery)

**Last Updated:** 05-27-26
**Operating mode:** DETAIL
**Series:** Standalone dogfood methodology session (kickoff: this session's seed prompt was minimal — "I would like to start a session to define the domains for crmBuilder using the domain capture prd"; methodology guide: `PRDs/process/interviews/interview-domain-discovery.md` v1.1)
**Slice:** Apply the SES-098 close-out payload to the V2 governance DB
**Status:** Ready to execute. Requires: live `crmbuilder-v2-api` at 127.0.0.1:8765. No migration. One substantive commit already on origin/main (`e03688b` — candidate inventory MD). Payload is governance-only (no work tickets; two new PIs; six DECs; ten references). Per DEC-319's Option C.1 framing, no methodology candidate records are written by this apply — they remain in the MD inventory pending PI-092's resolution and the V2 close-out pipeline's methodology ingestion support.

> **Why this session record exists.** SES-098 conducted Phase 2 Domain Discovery for the CRMBUILDER engagement (dogfood). Established 14 candidate domains (all passing Rule 2.1 against a revised mission), ~40 candidate entities, and 9 candidate personas. Surfaced the user/role entity gap (PI-091) and the methodology-records-promotion gap (PI-092). Mid-session pivoted the originally-confirmed Option C session shape to Option C.1 (durable MD inventory plus PI for methodology promotion) after discovering the v0.8 close-out payload schema is governance-only — DEC-319 records the pivot with Doug's explicit additional requirement that the MD-to-DB conversion happens when the close-out pipeline supports it. This session also effectively drafts the new Master CRMBuilder PRD's Phase 2 by execution per §III iterative-drafting framework.

> **Identifier-head capture per DEC-300.** Heads captured at session start (against the GitHub snapshot, NOT the live API — sandbox does not have direct API access): SES-096, CONV-066, DEC-318, PI-090, WT-055, WS-012. The snapshot is known to lag the live API. Pre-flight below MUST re-verify against the live API before apply and renumber if heads have advanced.

---

## Net Effect

Apply `PRDs/product/crmbuilder-v2/close-out-payloads/ses_098.json` to the V2 governance DB via the standard apply script. Creates:

- **SES-098** — session record for CRMBuilder dogfood Phase 2 Domain Discovery
- **CONV-068** — conversation record (status=`complete`) with two embedded reference edges (`conversation_belongs_to_workstream` → WS-011 pragmatic; `conversation_records_session` → SES-098)
- **DEC-319** — Adopt Option C.1 for SES-098 close-out (durable MD inventory + standard governance close-out; methodology promotion deferred to PI-092)
- **DEC-320** — Mission revision to application-framework framing with three-mode platform-or-build option
- **DEC-321** — CRMBUILDER engagement domain set: 14 candidate domains established, all passing Rule 2.1
- **DEC-322** — Symmetric pattern-inventory parallels rejected for #6 and #8 (patterns intrinsic to those operational domains)
- **DEC-323** — Methodology Authoring (#1) is CRMBuilder-internal-only (present in CRMBUILDER engagement; absent from external client engagements)
- **DEC-324** — Entity naming disambiguation (Pattern qualifiers locked in; Render Run standardized across #12 and #13; Generated Artifact / Document stay distinct)
- **PI-091** — Design and implement user/role entity model in V2 for tracking per-engagement participants (status=Open)
- **PI-092** — Promote Phase 2 candidate methodology records into V2 once close-out pipeline supports methodology ingestion (status=Open)
- **10 reference rows:**
  - `decided_in` DEC-319 → SES-098
  - `decided_in` DEC-320 → SES-098
  - `decided_in` DEC-321 → SES-098
  - `decided_in` DEC-322 → SES-098
  - `decided_in` DEC-323 → SES-098
  - `decided_in` DEC-324 → SES-098
  - `decided_in` PI-091 → SES-098
  - `decided_in` PI-092 → SES-098
  - `is_about` PI-092 → DEC-319 (PI-092 carries the deferred work decided in DEC-319)
  - `is_about` PI-091 → DEC-323 (user/role gap surfaced during methodology-authoring scope discussion)
- **1 commit row** already on origin/main:
  - `e03688b` — Phase 2 Domain Discovery candidate inventory MD for CRMBUILDER engagement (SES-098)
- close_out_payload COP-NNN + deposit_event DEP-NNN (lazy-created)

No work tickets opened or consumed. `resolves_planning_items[]` and `addresses_planning_items[]` are both **empty** — this session creates two new PIs but does not resolve or advance any pre-existing PIs.

**No methodology records are written by this apply.** The 14 candidate Domains, 9 candidate Personas, and ~40 candidate Entities surfaced in SES-098 remain in `PRDs/product/crmbuilder-v2/CRMBuilder-Phase-2-Candidate-Inventory.md` pending PI-092 resolution. This is the explicit intent of Option C.1 (DEC-319).

---

## Pre-flight

1. `pwd` → repo clone root (`~/Dropbox/Projects/crmbuilder`). Stop if unexpected.

2. Clean working tree:
   ```bash
   git status --porcelain
   ```
   Stop if non-empty. The expected state is the candidate inventory MD already on disk and committed at `e03688b`, plus the close-out payload and this apply prompt also on disk and committed (sandbox commit-and-push convention — these will already be in origin/main after the pull below).

3. Git identity:
   ```bash
   git config user.email   # expect doug@dougbower.com
   git config user.name    # expect Doug Bower
   ```

4. Pull latest:
   ```bash
   git pull --rebase origin main
   ```
   This should fast-forward to the sandbox commits (candidate inventory MD + payload + apply prompt).

5. Payload and inventory exist:
   ```bash
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_098.json
   ls -la PRDs/product/crmbuilder-v2/CRMBuilder-Phase-2-Candidate-Inventory.md
   git log --oneline -3 PRDs/product/crmbuilder-v2/CRMBuilder-Phase-2-Candidate-Inventory.md
   ```
   Expect the inventory commit `e03688b` to be in the log.

6. API health:
   ```bash
   curl -sf http://127.0.0.1:8765/health || curl -sf http://127.0.0.1:8765/sessions | head -c 200
   ```
   Expect 200 OK on either; stop if neither responds.

7. **Pre-apply identifier-head capture per DEC-300** (re-verify against live API; sandbox heads were captured against the GitHub snapshot which is known to lag):
   ```bash
   curl -sf http://127.0.0.1:8765/sessions       | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(s['identifier'] for s in d); print('SES head:', ids[-1])"
   curl -sf http://127.0.0.1:8765/conversations  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(c['conversation_identifier'] for c in d); print('CONV head:', ids[-1])"
   curl -sf http://127.0.0.1:8765/decisions      | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(dc['identifier'] for dc in d); print('DEC head:', ids[-1])"
   curl -sf http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(p['identifier'] for p in d); print('PI head:', ids[-1])"
   curl -sf http://127.0.0.1:8765/work-tickets   | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(w['work_ticket_identifier'] for w in d); print('WT head:', ids[-1])"
   curl -sf http://127.0.0.1:8765/workstreams    | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(w['workstream_identifier'] for w in d); print('WS head:', ids[-1])"
   ```
   Snapshot-captured heads (sandbox-side): SES-096, CONV-066, DEC-318, PI-090, WT-055, WS-012. If any live head is ≥ the identifier this payload reserves (SES-098, CONV-068, DEC-319..324, PI-091..092), the payload must be **renumbered** before apply — see Renumbering below.

8. Verify WS-011 exists and is the chosen parent workstream:
   ```bash
   curl -sf http://127.0.0.1:8765/workstreams/WS-011 | python3 -c "import sys,json; w=json.load(sys.stdin); print('WS-011:', w.get('workstream_status'), w.get('workstream_name'))"
   ```
   Expect WS-011 to exist (`in_flight`, "V2 storage API refinements"). The conversation references it pragmatically per the SES-096 precedent. A dedicated dogfood-methodology-authoring workstream is mentioned in SES-098's `in_flight_at_end` as future scope.

---

## Renumbering (if heads have advanced)

If pre-flight step 7 reveals any head equal to or greater than this payload's reserved identifier slot:

1. Compute the new head for each affected record type: `new_head = live_head + 1`.
2. Edit `ses_098.json` and update **every** internal reference: `session.identifier`, `conversation.conversation_identifier`, every `decisions[].identifier`, every `planning_items[].identifier`, every `references[].source_id` and `target_id` that touches a renumbered identifier, and the conversation's embedded references.
3. Rename this file to `CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md` matching the new SES identifier.
4. Rename the payload to `ses_NNN.json` matching the new SES identifier.
5. Update the candidate inventory MD's session-identifier references (search for "SES-098" — appears in front-matter, transcript, decision summaries, and PI descriptions) and commit the update on top of `e03688b`.
6. Repeat pre-flight step 7 to confirm the new identifiers are higher than current heads.
7. Proceed to Apply.

---

## Apply

Run the standard close-out apply script:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_098.json
```

Expected OK counts on success:
- 1 session created (SES-098)
- 1 conversation created (CONV-068)
- 6 decisions created (DEC-319, DEC-320, DEC-321, DEC-322, DEC-323, DEC-324)
- 2 planning_items created (PI-091, PI-092)
- 10 top-level references created
- 2 embedded conversation references created (`conversation_belongs_to_workstream`, `conversation_records_session`)
- 1 commit record ingested (`e03688b`)
- 0 work_tickets
- 0 resolves_planning_items
- 0 addresses_planning_items
- 1 close_out_payload lazy-created (COP-NNN)
- 1 deposit_event lazy-created (DEP-NNN)

Any 4xx response halts the apply — read the error and either correct the payload or surface to Doug.

---

## Post-apply verification

1. Identifier-head advancement:
   ```bash
   curl -sf http://127.0.0.1:8765/sessions       | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(s['identifier'] for s in d); print('SES head after:', ids[-1])"
   curl -sf http://127.0.0.1:8765/conversations  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(c['conversation_identifier'] for c in d); print('CONV head after:', ids[-1])"
   curl -sf http://127.0.0.1:8765/decisions      | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(dc['identifier'] for dc in d); print('DEC head after:', ids[-1])"
   curl -sf http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(p['identifier'] for p in d); print('PI head after:', ids[-1])"
   ```
   Expect SES head = SES-098, CONV head = CONV-068, DEC head = DEC-324, PI head = PI-092 (or higher if heads advanced before apply and the payload was renumbered).

2. Reference count delta — expect +12 reference rows total (10 top-level + 2 embedded):
   ```bash
   curl -sf "http://127.0.0.1:8765/references?target_id=SES-098" | python3 -c "import sys,json; print('refs targeting SES-098:', len(json.load(sys.stdin)['data']))"
   ```
   Expect 9 (six DECs + two PIs + one CONV record-session edge — the conversation_records_session ref).

3. Spot-check SES-098 and one decision:
   ```bash
   curl -sf http://127.0.0.1:8765/sessions/SES-098 | python3 -m json.tool | head -30
   curl -sf http://127.0.0.1:8765/decisions/DEC-319 | python3 -m json.tool | head -30
   ```
   Expect SES-098.title and DEC-319.title to match the payload.

4. Spot-check a `decided_in` reference resolution:
   ```bash
   curl -sf "http://127.0.0.1:8765/references?source_id=DEC-321&relationship=decided_in" | python3 -m json.tool
   ```
   Expect one row, target_type=session, target_id=SES-098.

5. Confirm PI-091 and PI-092 are Open and have `item_type: pending_work`:
   ```bash
   for id in PI-091 PI-092; do
     curl -sf "http://127.0.0.1:8765/planning-items/$id" | python3 -c "import sys,json; p=json.load(sys.stdin); print('$id:', p.get('status'), p.get('item_type'))"
   done
   ```
   Expect both `Open pending_work`.

6. Confirm CONV-068 belongs to WS-011:
   ```bash
   curl -sf "http://127.0.0.1:8765/references?source_id=CONV-068&relationship=conversation_belongs_to_workstream" | python3 -m json.tool
   ```
   Expect one row with target_type=workstream, target_id=WS-011.

---

## Commit snapshot regeneration

The apply script's `_refresh_snapshot` hook regenerates `PRDs/product/crmbuilder-v2/db-export/` JSON snapshots transactionally on every write. After apply completes, commit all snapshot updates plus the payload, apply prompt, and any deposit-event-log file together in **one** commit:

```bash
cd ~/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/db-export/
git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_098.json
git add PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-098.md
git add PRDs/product/crmbuilder-v2/deposit-event-logs/ 2>/dev/null || true
git status --short
git commit -m "v2: SES-098 close-out applied — CRMBuilder dogfood Phase 2 Domain Discovery

Applied close-out payload for SES-098:

- 1 session (SES-098): Phase 2 Domain Discovery for CRMBUILDER dogfood;
  14 candidate domains established (all passing Rule 2.1), candidate
  inventory captured as durable MD at
  PRDs/product/crmbuilder-v2/CRMBuilder-Phase-2-Candidate-Inventory.md,
  methodology-records promotion deferred to PI-092 per Option C.1.
- 1 conversation (CONV-068), parent WS-011 pragmatic.
- 6 decisions (DEC-319 session shape Option C.1; DEC-320 mission
  revision to application-framework framing with three-mode platform-
  or-build option; DEC-321 14-domain set; DEC-322 symmetric pattern-
  inventory parallels rejected for #6 and #8; DEC-323 Methodology
  Authoring CRMBuilder-internal-only; DEC-324 entity naming
  disambiguation).
- 2 planning items (PI-091 user/role entity model; PI-092 promote
  Phase 2 candidate methodology records to V2 once close-out pipeline
  supports methodology ingestion).
- 10 top-level references plus 2 embedded conversation references.
- 1 commit ingested (e03688b candidate inventory MD).

No methodology records were written this apply — they remain in the
MD inventory pending PI-092 resolution per the explicit intent of
Option C.1 (DEC-319).

Snapshots regenerated and committed in this commit."
git log --oneline -1
```

Doug pushes after review (per Claude Code workflow — this differs from sandbox commit-and-push).

---

## Done block

When this script completes, reply with:

- Heads-before and heads-after for SES, CONV, DEC, PI, WT, WS
- Record counts created (sessions, conversations, decisions, planning_items, references, commits, close_out_payload, deposit_event)
- The snapshot-commit SHA
- The next-conversation kickoff path. **No follow-on kickoff was authored in SES-098.** Three candidate next sessions exist for Doug to schedule:
  1. **Decide the V2 methodology-records ingestion mechanism** (precondition for resolving PI-092). Design decision: payload schema extension, separate apply path, MCP tool surface, or other.
  2. **Resolve PI-091** — design and implement user/role entity model.
  3. **Draft Phase 2 into the new Master CRMBuilder PRD** — capture SES-098's execution into the PRD's Phase 2 specification per §III iterative-drafting framework.

---

## Known caveats and follow-on items surfaced by SES-098

These do not block apply; they are surfaced here for Doug's later attention:

1. **Workstream parentage is pragmatic.** CONV-068 belongs to WS-011 (V2 storage API refinements) per the SES-096 precedent. Substantively, a dedicated "CRMBuilder Dogfood Methodology Authoring" workstream (provisionally WS-013) would be a better parent. Doug may want to author that workstream and retro-assign CONV-068 once created. Note: workstreams are not authored via close-out payloads under current convention — direct API POST or MCP call.

2. **Methodology records not yet in V2.** Per Option C.1 (DEC-319), the 14 candidate Domains, 9 candidate Personas, and ~40 candidate Entities surfaced in SES-098 are in the MD inventory only. PI-092 captures the promotion work. Until PI-092 resolves, the MD is the source-of-truth.

3. **User/role entity gap.** PI-091 captures this — 7 of 9 personas have TBD Rule 2.2 backing because CRMBuilder lacks a first-class user/role entity model. Resolution affects both PI-092's persona promotions (which depend on PI-091 for backings) and external-engagement persona handling.

4. **Methodology Authoring is CRMBuilder-internal-only.** Per DEC-323, external client engagements will have a 13-domain default starting point (everything except #1) plus client-specific adjustments. The new Master CRMBuilder PRD will need to document this scope distinction when Phase 2 is drafted into the PRD.

5. **Phase 3 Inventory Reconciliation has limited applicability.** Single-stakeholder dogfood doesn't reconcile across multiple stakeholders. The new Master CRMBuilder PRD may absorb reconciliation into Phase 1 or define a different next-phase. Worth resolving before non-dogfood Phase 2 sessions for external clients.

6. **This session drafts new-PRD Phase 2 by execution.** Per Master CRMBuilder PRD §III iterative-drafting framework, SES-098's conduct can be lifted into a Phase 2 specification for the PRD. The Master CRMBuilder PRD's Phase 2 placeholder is currently empty; this session's transcript and methodology adaptations (Variant A for dogfood, three-track listening adapted from oral to corpus-walking, the Option C.1 pivot) inform what that PRD Phase 2 should say.
