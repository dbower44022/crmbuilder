# Apply close-out — SES-115 / CNV-017 (Parallel agent orchestrator and executive summary / WS-012)

## 1. Purpose

Apply the close-out payload at
`PRDs/product/crmbuilder-v2/close-out-payloads/ses_115.json` to the CRMBUILDER
engagement's v2 governance database, recording the PI-102 work — reconciling
the `executive_summary` column nullability between the SQLAlchemy models (and
the access / API-schema / MCP-tool / UI layers built on them) and the live
database, which has enforced NOT NULL + a 200-800 char CHECK since migration
0023 (PI-075).

**Net effect (records that will land):**

| Section | Count | Identifiers |
|---|---|---|
| session | 1 | SES-115 |
| conversation | 1 | CNV-017 |
| work_tickets | 0 | — |
| planning_items | 0 | — |
| commits | 1 | 73e4f08 (branch `pi-102-exec-summary-nullability`, pending push/merge) |
| decisions | 1 | DEC-330 (Active) |
| references | 5 | session_belongs_to_workstream (SES-115→WS-012); conversation_belongs_to_session (CNV-017→SES-115); decided_in (DEC-330→CNV-017); is_about (DEC-330→PI-102); conversation_belongs_to_workstream (CNV-017→WS-012) |
| resolves_planning_items | 1 | PI-102 → Resolved (atomic flip) |
| addresses_planning_items | 0 | — |
| deposit_event | 1 | DEP-NNN (auto), → COP-115 |

No supersession, so no manual post-apply PATCH (unlike ses-112).

**Repo note.** The PI-102 *code* deliverable (commit `73e4f08`) lives on branch
`pi-102-exec-summary-nullability` in an isolated worktree based on the clean
`b13707c` (not main's "abandoned commit"). This *governance* close-out is
applied from the main repo working tree because the live API exports
`db-export/` there and that baseline is current with the live DB — so the
db-export diff is exactly the PI-102 records. The two commits (code on the
worktree branch, governance here) are linked by the commit SHA in the payload
and reconcile when Doug merges the worktree branch.

## 2. Pre-flight

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
pwd                                   # expect repo root
git status --short                    # Doug's chat WIP (pi-106) is expected dirty; db-export/ should be clean
git rev-parse --abbrev-ref HEAD       # pi-106-chat-slice-d-followups (governance commit stages ONLY governance paths)
curl -s -m5 http://127.0.0.1:8765/health   # expect 200
test -f PRDs/product/crmbuilder-v2/close-out-payloads/ses_115.json && echo "payload present"
# Identifier-head re-capture (re-key the payload if any collide before applying):
for ep in sessions conversations decisions; do
  echo -n "$ep next: "; curl -s -m5 "http://127.0.0.1:8765/$ep/next-identifier"; echo
done
curl -s -m5 http://127.0.0.1:8765/planning-items/PI-102 | python3 -c "import sys,json;print('PI-102 status (expect Open):',json.load(sys.stdin)['data']['status'])"
```

Expected free at draft time: SES-115, CNV-017, DEC-330. **If any are now taken,
re-key the payload (and this prompt) to the next free slots before applying** —
a collision is silently skipped as HTTP 409, not loudly failed.

## 3. Apply

```bash
cd /home/doug/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_115.json
```

Expect ✓ on: 1 conversation, 1 session, 1 commit, 1 decision, the reference
edges, the PI-102 resolves edge (atomic Open→Resolved flip), and a
deposit_event POST. Exit code 0. (The duplicate conversation_belongs_to_session
edge — embedded in the conversation block and repeated in references — 409-skips
harmlessly on the second POST.)

## 4. Post-apply verification

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
curl -s -m5 http://127.0.0.1:8765/sessions/SES-115 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('SES-115',d['session_status'])"
curl -s -m5 http://127.0.0.1:8765/conversations/CNV-017 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('CNV-017',d['conversation_status'])"
curl -s -m5 http://127.0.0.1:8765/decisions/DEC-330 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('DEC-330',d['status'])"
curl -s -m5 http://127.0.0.1:8765/planning-items/PI-102 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('PI-102',d['status'],'(expect Resolved)')"
curl -s -m5 "http://127.0.0.1:8765/references?source_id=DEC-330" | python3 -c "import sys,json;print('DEC-330 edges:',[(r['relationship'],r['target_id']) for r in json.load(sys.stdin)['data']])"
```

## 5. Commit snapshot regeneration

The apply transactionally regenerated `db-export/*.json` and wrote
`deposit-event-logs/dep_NNN.log`. Commit them with the payload and this apply
prompt — **stage only governance paths so Doug's in-flight chat WIP stays
unstaged**:

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/ \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_115.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-115.md
git commit -m "v2: SES-115 close-out applied — DEC-330 (executive_summary nullability reconciled to live schema) + PI-102 resolved"
```

## 6. Done block

Reply with: heads before/after, record counts from the apply, the deposit-event
identifier + log path, and the snapshot-commit SHA. Note that the code commit
`73e4f08` (branch `pi-102-exec-summary-nullability`) and this governance commit
both still need `git push`, and the worktree branch needs merging.
