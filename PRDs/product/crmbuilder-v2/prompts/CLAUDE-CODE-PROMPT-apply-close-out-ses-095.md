# CLAUDE-CODE-PROMPT — apply close-out SES-095 (governance-recording-rules.md v0.1 + CLAUDE.md wiring + DEC-299 conceptual alignment)

**Last Updated:** 05-27-26
**Operating mode:** DETAIL
**Series:** Standalone governance session (kickoff: `PRDs/product/crmbuilder-v2/conversation-logging-rules-kickoff.md`)
**Slice:** Apply the SES-095 close-out payload to the V2 governance DB
**Status:** Ready to execute with caveats noted below. Requires: live `crmbuilder-v2-api` at 127.0.0.1:8765. No migration. Three commits already on origin/main (`5a2b6a4`, `c28b363`, `b8a6df1`). Payload is governance-only (no work tickets; one new PI; four DECs; eight references).

> **Why this session record exists.** SES-095 followed the framing pivot in the predecessor session (which itself reversed SES-093's reframe of PI-084). The work produced is what PI-084 originally called for: a canonical rules document for governance-record authoring, stored at `specifications/governance-recording-rules.md`. The session also wired the document into the repository-level `CLAUDE.md` and codified the document's own kickoff pre-flight requirements within §1. A subsequent gap-finding turn from Doug surfaced two omissions (Mandatory Logging and stop-and-log discipline) and one prior-error (§9 documented an outdated four-section payload schema instead of the actual v0.8 ten-element schema); the document was rewritten against DEC-299's post-redesign conceptual model and the corrected schema. PI-090 captures the apply-pipeline validator as the highest-leverage missing enforcement layer.

> **Identifier-head capture per DEC-300.** Heads captured at session start were SES-094, CONV-064, DEC-313, PI-089, WT-055. The sandbox did not have direct API access to re-verify mid-session. Pre-flight below MUST re-verify before apply.

---

## Net Effect

Apply `PRDs/product/crmbuilder-v2/close-out-payloads/ses_095.json` to the V2 governance DB via the standard apply script. Creates:

- **SES-095** — session record for governance-recording-rules.md v0.1 authoring
- **CONV-065** — conversation record (status=`complete`) with two embedded reference edges (`conversation_belongs_to_workstream` → WS-011; `conversation_records_session` → SES-095)
- **DEC-314** — Rules document lives at `specifications/governance-recording-rules.md`, not under `PRDs/process/conduct/`
- **DEC-315** — Workstreams covered as first-class section; all record creation via API or MCP, never via desktop UI
- **DEC-316** — Adopts DEC-299 conceptual model for Session/Conversation; codifies Mandatory Logging as a core principle
- **DEC-317** — Multi-conversation Claude.ai chats handled via PI-073 schema evolution (Option B), not via one-V2-session-per-conversation (Option A)
- **PI-090** — Apply-pipeline validator script for governance-recording-rules conformance (status=Open)
- **8 reference rows:**
  - `decided_in` DEC-314 → SES-095
  - `decided_in` DEC-315 → SES-095
  - `decided_in` DEC-316 → SES-095
  - `decided_in` DEC-317 → SES-095
  - `is_about` DEC-316 → DEC-299 (DEC-316 adopts DEC-299's conceptual model)
  - `is_about` DEC-317 → PI-073 (DEC-317 picks Option B which PI-073 enables)
  - `addresses` PI-090 → DEC-310 (validator delivers the enforcement layer DEC-310's mandate implies)
  - `decided_in` PI-090 → SES-095 (PI created in this session)
- **3 commit rows** already on origin/main:
  - `5a2b6a4` — initial v0.1 draft of governance-recording-rules.md
  - `c28b363` — CLAUDE.md wiring + kickoff pre-flight requirements
  - `b8a6df1` — DEC-299 conceptual alignment + Mandatory Logging + stop-and-log
- close_out_payload COP-NNN + deposit_event DEP-NNN (lazy-created)

No work tickets opened or consumed. `resolves_planning_items[]` and `addresses_planning_items[]` are both **empty** — see "Open question before apply" below.

---

## Open question before apply — PI linkage

This session's content output (governance-recording-rules.md v0.1) matches PI-084's title exactly ("Create the canonical governance-recording rules document at specifications/governance-recording-rules.md"). However:

- SES-093's reframe (DEC-311) superseded PI-084 with PI-085 (Domain Overview).
- The predecessor session (live SES-094, not in repo snapshot) reversed that reframe via a framing-pivot DEC and may have created a new PI to capture the corrected scope, somewhere in the PI-085..PI-089 range.

The sandbox could not see PI-085 through PI-089 (snapshot lags two sessions / three decisions). Before running apply, Doug must:

1. Query the live API for PI-084 through PI-089 status and titles:
   ```bash
   for n in 084 085 086 087 088 089; do
     curl -sf "http://127.0.0.1:8765/planning-items/PI-$n" | python3 -c "import sys,json; p=json.load(sys.stdin); print(f\"PI-{p.get('identifier','???').split('-')[-1]}: status={p.get('status')}  title={p.get('title','')[:100]}\")"
   done
   ```
2. Identify which PI this session resolves (if any). Candidates: PI-084 if the framing pivot un-superseded it; or a successor PI in PI-085..PI-089.
3. If a resolving PI is identified, edit `PRDs/product/crmbuilder-v2/close-out-payloads/ses_095.json` and add the identifier to `resolves_planning_items[]` (and remove from any wrong slot) **before** running apply. Equivalently, add to `addresses_planning_items[]` if the work advances but does not fully resolve.

If no resolving PI is identified, leave both arrays empty and document the orphan-content situation in `session.in_flight_at_end` via an UPDATE-PROMPT after apply.

---

## Pre-flight

1. `pwd` → repo clone root (`~/Dropbox/Projects/crmbuilder`). Stop if unexpected.

2. Clean working tree:
   ```bash
   git status --porcelain
   ```
   Stop if non-empty. The expected state is the close-out payload and this apply prompt already on disk and committed (this same commit will also include the post-apply snapshot regen).

3. Git identity:
   ```bash
   git config user.email   # expect doug@dougbower.com
   git config user.name    # expect Doug Bower
   ```

4. Pull latest:
   ```bash
   git pull --rebase origin main
   ```

5. Payload exists:
   ```bash
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_095.json
   ```

6. API health:
   ```bash
   curl -sf http://127.0.0.1:8765/health || curl -sf http://127.0.0.1:8765/sessions | head -c 200
   ```
   Expect 200 OK on either; stop if neither responds.

7. **Pre-apply identifier-head capture per DEC-300** (re-verify against live API; sandbox heads were captured at session start hours earlier and may have drifted):
   ```bash
   curl -sf http://127.0.0.1:8765/sessions       | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(s['identifier'] for s in d); print('SES head:', ids[-1])"
   curl -sf http://127.0.0.1:8765/conversations  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(c['conversation_identifier'] for c in d); print('CONV head:', ids[-1])"
   curl -sf http://127.0.0.1:8765/decisions      | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(dc['identifier'] for dc in d); print('DEC head:', ids[-1])"
   curl -sf http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(p['identifier'] for p in d); print('PI head:', ids[-1])"
   curl -sf http://127.0.0.1:8765/work-tickets   | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(w['work_ticket_identifier'] for w in d); print('WT head:', ids[-1])"
   ```
   Expected heads (sandbox-captured at session start): SES-094, CONV-064, DEC-313, PI-089, WT-055. If any head is now ≥ the identifier this payload reserves (SES-095, CONV-065, DEC-314..317, PI-090), the payload must be **renumbered** before apply — see Renumbering below.

8. Resolve the PI-linkage question above (see "Open question before apply").

---

## Renumbering (if heads have advanced)

If pre-flight step 7 reveals any head equal to or greater than this payload's reserved identifier slot:

1. Compute the new head for each affected record type: `new_head = live_head + 1`.
2. Edit `ses_095.json` and update **every** internal reference: session.identifier, conversation.conversation_identifier, decisions[].identifier, planning_items[].identifier, references[].source_id and target_id, the conversation's embedded references, and the apply prompt filename (this file).
3. Rename this file to `CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md` matching the new SES identifier.
4. Rename the payload to `ses_NNN.json` matching the new SES identifier.
5. Repeat pre-flight step 7 to confirm the new identifiers are higher than current heads.
6. Proceed to Apply.

---

## Apply

Run the standard close-out apply script:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_095.json
```

Expected OK counts on success:
- 1 session created (SES-095)
- 1 conversation created (CONV-065)
- 4 decisions created (DEC-314..317)
- 1 planning_item created (PI-090)
- 8 top-level references created
- 2 embedded conversation references created (conversation_belongs_to_workstream, conversation_records_session)
- 3 commit records ingested (5a2b6a4, c28b363, b8a6df1)
- 0 work_tickets
- 0 resolves_planning_items (subject to the PI-linkage question)
- 0 addresses_planning_items (subject to the PI-linkage question)
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
   Expect SES head = SES-095, CONV head = CONV-065, DEC head = DEC-317, PI head = PI-090 (or higher if heads advanced before apply and the payload was renumbered).

2. Reference count delta — expect +10 reference rows total (8 top-level + 2 embedded):
   ```bash
   curl -sf "http://127.0.0.1:8765/references?source_id=SES-095" | python3 -c "import sys,json; print('refs targeting SES-095:', len(json.load(sys.stdin)['data']))"
   curl -sf "http://127.0.0.1:8765/references?target_id=SES-095" | python3 -c "import sys,json; print('refs targeting SES-095 (target):', len(json.load(sys.stdin)['data']))"
   ```

3. Spot-check SES-095 and one decision:
   ```bash
   curl -sf http://127.0.0.1:8765/sessions/SES-095 | python3 -m json.tool | head -30
   curl -sf http://127.0.0.1:8765/decisions/DEC-316 | python3 -m json.tool | head -30
   ```
   Expect SES-095.title and DEC-316.title to match the payload.

4. Spot-check a `decided_in` reference resolution:
   ```bash
   curl -sf "http://127.0.0.1:8765/references?source_id=DEC-316&relationship=decided_in" | python3 -m json.tool
   ```
   Expect one row, target_type=session, target_id=SES-095.

5. Confirm PI-090 is Open and has `item_type: pending_work`:
   ```bash
   curl -sf http://127.0.0.1:8765/planning-items/PI-090 | python3 -c "import sys,json; p=json.load(sys.stdin); print('PI-090:', p.get('status'), p.get('item_type'))"
   ```

---

## Commit snapshot regeneration

The apply script's `_refresh_snapshot` hook regenerates `PRDs/product/crmbuilder-v2/db-export/` JSON snapshots transactionally on every write. After apply completes, commit all snapshot updates plus the payload, apply prompt, and any deposit-event-log file together in **one** commit:

```bash
cd ~/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/db-export/
git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_095.json
git add PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-095.md
git add PRDs/product/crmbuilder-v2/deposit-event-logs/ 2>/dev/null || true
git status --short
git commit -m "v2: SES-095 close-out applied — governance-recording-rules.md v0.1 + CLAUDE.md wiring + DEC-299 conceptual alignment

Applied close-out payload for SES-095:

- 1 session (SES-095): governance-recording-rules.md v0.1 authoring,
  CLAUDE.md wiring, DEC-299 conceptual alignment, stop-and-log discipline.
- 1 conversation (CONV-065).
- 4 decisions (DEC-314 location/filename; DEC-315 workstreams as
  first-class plus API/MCP-only creation; DEC-316 DEC-299 conceptual
  alignment plus Mandatory Logging; DEC-317 Option B for
  multi-conversation chats via PI-073 schema evolution).
- 1 planning item (PI-090): apply-pipeline validator script.
- 8 top-level references plus 2 embedded conversation references.
- 3 commit records ingested.

Snapshots regenerated and committed in this commit."
git log --oneline -1
```

Doug pushes after review (per Claude Code workflow — this differs from sandbox commit-and-push).

---

## Done block

When this script completes, reply with:

- Heads-before and heads-after for SES, CONV, DEC, PI, WT
- Record counts created (sessions, conversations, decisions, planning_items, references, commits, close_out_payload, deposit_event)
- The snapshot-commit SHA
- The next-conversation kickoff path (TBD — no follow-on kickoff was authored in SES-095; PI-090's validator-build session and any rules-document trim-pass session are candidates Doug to schedule)

---

## Known caveats and follow-on items surfaced by SES-095

These do not block apply; they are surfaced here for Doug's later attention:

1. **Word budget overage.** Rules document is 4022 words against the original ~2150 v0.1 budget. Trim pass (especially §10's eleven failure modes) deferred — Doug to decide whether to trim before or after PI-073 lands.

2. **`conversation_belongs_to_session` reference vocabulary.** Introduced in §4 of the rules document for the post-PI-073 1:N schema. Not verified to be registered in `vocab.py`. If unregistered, requires a vocab-registration step before any payload uses this kind. (Note: this payload uses `conversation_records_session` per the SES-093 precedent, not `conversation_belongs_to_session`. The vocabulary question applies to future payloads under the new model.)

3. **Workstream linkage assignment.** Conversation CONV-065 belongs to WS-011 (V2 storage API refinements) per pragmatic choice — closest existing workstream match. A dedicated "Governance recording enforcement" workstream (provisionally WS-013) is referenced in PI-090's description as future scope. Doug may want to retro-assign CONV-065 to a new workstream once created.

4. **PI-073 open design questions touch the rules document.** Medium-classifier metadata (§3) and planned-but-not-started conversation handling (§4) are flagged as pending PI-073 resolution. The rules document will need amendment when PI-073 lands.

5. **§9 transitional v0.8 handling for multi-conversation sessions.** Sandbox documented a direct-API-POST-with-references workaround as the bridge until PI-073 lands. Doug may prefer a cleaner transitional rule (e.g., "during transition, multi-conversation sessions aren't allowed — close out and start new").
