# CLAUDE-CODE-PROMPT — Apply close-out SES-137

**Last Updated:** 05-31-26 00:05

**Operating mode:** DETAIL. Run the steps in order. Stop and report on any unexpected result.

**Repo:** `dbower44022/crmbuilder`. **Target engagement:** CRMBUILDER. **CLAUDE.md:** root.

---

## Purpose

Apply the SES-137 close-out payload to the CRMBUILDER V2 governance database. This records the Model A branch-governance decision and its work.

### Net Effect (records that will land)

| Record | Identifier | Notes |
|---|---|---|
| Session | SES-137 | Branch strategy review + PI-112 fork diagnosis + Model A guard. medium `chat`, status `complete`. |
| Conversation | CNV-039 | Belongs to SES-137. |
| Decision | DEC-356 | Model A — governance applies + snapshot commits only on main; status `Active`. |
| Planning Item | PI-114 | Created `Draft`, **resolved** in this same payload → `Resolved`. |
| Work Ticket | WT-064 | The guard Claude Code prompt; kind `claude_code_prompt`, status `ready`. |
| Commits | b7e4a17d, 3a2f4324 | Prompt authoring + guard implementation, both already on `main`. |
| References | 6 explicit | session→PRJ-014, conv→SES-137, conv→PRJ-014, DEC-356 `decided_in` CNV-039, SES-137 `session_follows_from` SES-136, WT-064 `addresses` PI-114. Plus apply-generated deposit-event edges. |

This is a governance apply, so per Model A (the very decision being recorded) it **must run on `main`** — the guard added in commit `3a2f4324` now enforces this; running off `main` will exit 2.

---

## Pre-flight

```bash
cd ~/Dropbox/Projects/crmbuilder
git rev-parse --abbrev-ref HEAD          # MUST be: main  (apply guard requires it)
git status --porcelain                   # clean
git config user.email "doug@dougbower.com"
git config user.name  "Doug Bower"
git pull --rebase origin main
test -f PRDs/product/crmbuilder-v2/close-out-payloads/ses_137.json && echo "payload present"

# API health (start if needed — UI-owned API preferred)
curl -fsS http://127.0.0.1:8765/health >/dev/null && echo "API up" || echo "API DOWN — start it first"
```

### Pre-apply identifier-head capture (CRMBUILDER)

```bash
for e in sessions decisions planning_items conversations work_tickets; do
  pre=$(echo "$e" | sed -E 's/sessions/SES/;s/decisions/DEC/;s/planning_items/PI/;s/conversations/CNV/;s/work_tickets/WT/')
  echo "$e: $(curl -fsS "http://127.0.0.1:8765/$(echo $e | tr _ -)?limit=1000" | python3 -c "import json,sys;d=json.load(sys.stdin)['data'];import re;ids=[r.get('identifier') or r.get(list(r)[0]) for r in d];print(sorted([i for i in ids if isinstance(i,str) and i.startswith('$pre-')], key=lambda x:int(x.split('-')[1]))[-1] if ids else 'none')")"
done
```

Expected heads at apply time: **SES-136, DEC-355, PI-113, CNV-038, WT-063** (and DEP-131).

### Re-key contingency (SES-077 pattern)

If any of SES-137 / DEC-356 / PI-114 / CNV-039 / WT-064 has already been claimed by a parallel agent (head higher than above), **stop**. Re-key the payload to the next free identifiers, updating every internal cross-reference (the `references`, `resolves_planning_items`, `decided_in`, `addresses`, `session_follows_from` edges, the filename `ses_NNN.json`, and this prompt's Net Effect), then re-run pre-flight. Do not apply over a collision.

---

## Apply

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_137.json
```

Expected OK record counts: **1 session, 1 conversation, 1 work_ticket, 1 planning_item, 2 commits, 1 decision, 6 references, 1 planning-item resolution.** The script lazy-creates the `close_out_payload` + `deposit_event` (DEP-132) and tees its log to `deposit-event-logs/dep_132.log`.

---

## Post-apply verification

```bash
cd ~/Dropbox/Projects/crmbuilder
# 1. Heads advanced by exactly one each
#    SES-136→137, DEC-355→356, PI-113→114, CNV-038→039, WT-063→064  (re-run the head-capture loop)

# 2. Decision landed Active (not Final)
curl -fsS http://127.0.0.1:8765/decisions/DEC-356 | python3 -c "import json,sys;d=json.load(sys.stdin)['data'];print(d['identifier'], d['status'], '—', d['title'][:60])"
#    EXPECT: DEC-356 Active — Model A ...

# 3. PI-114 resolved
curl -fsS http://127.0.0.1:8765/planning-items/PI-114 | python3 -c "import json,sys;d=json.load(sys.stdin)['data'];print(d['identifier'], d['status'])"
#    EXPECT: PI-114 Resolved

# 4. decided_in resolves to the conversation
curl -fsS "http://127.0.0.1:8765/references?source_id=DEC-356" | python3 -c "import json,sys;[print(r['source_id'],r['relationship'],r['target_id']) for r in json.load(sys.stdin)['data']]"
#    EXPECT a row: DEC-356 decided_in CNV-039

# 5. Session spot-check
curl -fsS http://127.0.0.1:8765/sessions/SES-137 | python3 -c "import json,sys;d=json.load(sys.stdin)['data'];print(d['identifier'], d['session_status'])"
#    EXPECT: SES-137 complete
```

All five must pass. If the decision shows any status other than `Active`, or PI-114 is not `Resolved`, stop and report before committing.

---

## Commit snapshot regeneration

The apply script transactionally regenerated `db-export/*.json` + `change_log.json` via the `_refresh_snapshot` hook and wrote `deposit-event-logs/dep_132.log`. No standalone exporter is invoked. We are on `main`, so the pre-commit guard allows the snapshot commit.

```bash
cd ~/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/dep_132.log
git commit -m "v2: apply SES-137 close-out — Model A branch-governance guard (DEC-356); resolve PI-114

Records DEC-356 (governance applies + snapshot commits occur only on main,
enforced mechanically), WT-064 (guard prompt), commits b7e4a17d + 3a2f4324,
and resolves PI-114. Belongs to Project PRJ-014."
git push origin main
```

---

## Done block — reply with

1. Heads before → after for SES / DEC / PI / CNV / WT (and DEP).
2. Record counts the apply reported.
3. Results of verification checks 2–5.
4. The snapshot-commit SHA.
5. Confirmation there is no next-conversation kickoff queued from this close-out (this session is self-contained; PI-114 is resolved).
