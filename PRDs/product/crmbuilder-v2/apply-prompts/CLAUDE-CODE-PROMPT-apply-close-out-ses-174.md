# CLAUDE-CODE-PROMPT: Apply Close-Out SES-174

## Purpose

Apply the SES-174 governance close-out payload to the CRMBUILDER engagement database.

**Net Effect:**
- 1 session record: SES-174 (Source Instance Mapping Model — Design Session)
- 1 conversation record: CNV-088
- 6 decision records: DEC-451 through DEC-456
- 2 planning item records: PI-202, PI-203
- 8 reference records

---

## Pre-flight

```bash
# 1. Working directory check
cd ~/Dropbox/Projects/CRMBuilder
pwd

# 2. Clean status check
git status

# 3. Git identity
git config user.name
git config user.email

# 4. Pull rebase
git pull --rebase origin main

# 5. Payload exists
ls PRDs/product/crmbuilder-v2/close-out-payloads/ses_174.json

# 6. API health check
curl -s http://127.0.0.1:8765/health -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d)"

# 7. Pre-apply identifier heads
curl -s "http://127.0.0.1:8765/sessions?sort=session_identifier&order=desc&limit=1" \
  -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; d=json.load(sys.stdin); print('Last SES:', d['data'][0]['session_identifier'])"

curl -s "http://127.0.0.1:8765/decisions?sort=identifier&order=desc&limit=1" \
  -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; d=json.load(sys.stdin); print('Last DEC:', d['data'][0]['identifier'])"

curl -s "http://127.0.0.1:8765/planning-items?sort=identifier&order=desc&limit=1" \
  -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; d=json.load(sys.stdin); print('Last PI:', d['data'][0]['planning_item_identifier'])"
```

---

## Apply

```bash
python3 apply_close_out.py \
  PRDs/product/crmbuilder-v2/close-out-payloads/ses_174.json \
  --engagement CRMBUILDER
```

**Expected OK record counts:** 1 session, 1 conversation, 6 decisions, 2 planning items, 8 references.

---

## Post-apply verification

```bash
# Identifier heads advanced
curl -s "http://127.0.0.1:8765/sessions/SES-174" -H "X-Engagement: CRMBUILDER" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['session_title'])"

curl -s "http://127.0.0.1:8765/decisions/DEC-456" -H "X-Engagement: CRMBUILDER" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['title'])"

curl -s "http://127.0.0.1:8765/planning-items/PI-203" -H "X-Engagement: CRMBUILDER" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['title'])"

# Reference count delta (should show refs referencing SES-174)
curl -s "http://127.0.0.1:8765/references?source_type=session&source_id=SES-174" \
  -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; d=json.load(sys.stdin); print('refs:', len([r for r in d['data'] if r['source_id']=='SES-174']))"
```

---

## Commit snapshots

The `_refresh_snapshot` hook auto-regenerates db-export snapshots on every API write. Commit them:

```bash
git add PRDs/methodology-records/db-export/
git commit -m "v2: governance snapshot — SES-174 apply (DEC-451..456, PI-202..203)"
```

Do NOT push. Doug pushes.

---

## Done

Reply with:
- Heads before and after (SES, DEC, PI)
- Record counts applied
- Snapshot commit SHA
- Next conversation kickoff: source mapping model implementation design session
