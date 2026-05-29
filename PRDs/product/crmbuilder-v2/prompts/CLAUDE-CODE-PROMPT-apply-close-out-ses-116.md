# Apply prompt — SES-116 close-out (WS-012 orchestrator track, PI-076–083)

**Payload:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_116.json`
**Authored:** 2026-05-29, in the `pi-076-area-field` worktree off `origin/main` (b13707c).
**What it records:** SES-116 / CNV-018 / DEC-331; ingests the seven PI-076–083 commits via `commits[]`; resolves PI-076/077/078/079/082; addresses PI-081/083; attaches the session to WS-012.

---

## ⚠️ Read first — this close-out was authored alongside active parallel sessions

The identifiers (SES-116, CNV-018, DEC-331) were the next-available heads at authoring time and the close-out validator confirmed no collision then. **Parallel sessions (e.g. the SES-115/PI-073 effort and the chat-UI orchestrator) are active and may claim these identifiers before you apply.** Re-verify and re-key if needed (step 1).

Caveats carried from SES-115 (see memory `project-v2-closeout-broken-on-main`):
- `executive_summary` is **required** on decision and session creates — this payload already carries `session_executive_summary` (774 chars) and the DEC-331 `executive_summary` (within 200–800). Don't strip them.
- **In-memory vocab drift:** the long-running API enforces the reference-kind vocab as of its start. This payload uses only `session_belongs_to_workstream`, `conversation_belongs_to_session`, and `decided_in` (DEC→CNV) — all proven to apply in ses_113/ses_115. If a kind 422s, mirror the latest *applied* payload's edges.
- **Run from the main repo working tree** (`~/Dropbox/Projects/crmbuilder`), where the live API exports `db-export/` and the baseline is current with the live DB — so the apply's snapshot diff is just the new records. The seven code commits live on the `pi-076-area-field` worktree branch and are ingested by SHA via `commits[]` (they need not be merged for the apply, but the SHAs must be reachable in the shared `.git`).

---

## 1. Pre-flight — re-verify heads and re-key if claimed

```bash
# API up?
curl -s http://127.0.0.1:8765/health

# Current heads — confirm SES-116 / CNV-018 / DEC-331 are still free.
curl -s http://127.0.0.1:8765/sessions      | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('SES max:',sorted([r['session_identifier'] for r in d])[-3:])"
curl -s http://127.0.0.1:8765/conversations | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('CNV max:',sorted([r['conversation_identifier'] for r in d if str(r['conversation_identifier']).startswith('CNV')])[-3:])"
curl -s http://127.0.0.1:8765/decisions     | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('DEC max:',sorted([r['identifier'] for r in d])[-3:])"

# PI-076..083 should still be Open (PI-080 already Resolved).
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print({p['identifier']:p['status'] for p in d if p['identifier'] in {f'PI-0{n}' for n in range(76,84)}})"
```

If any of SES-116 / CNV-018 / DEC-331 is now taken, re-key the payload to the next free values (find-replace the three identifiers consistently across `ses_116.json`, including every `source_id`/`target_id` and the `label`). Then re-run the validator.

## 2. Validate the payload

```bash
cd crmbuilder-v2
uv run python - <<'PY'
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("cv", "scripts/closeout_validator.py")
m = importlib.util.module_from_spec(spec); sys.modules["cv"]=m; spec.loader.exec_module(m)
p = json.load(open("../PRDs/product/crmbuilder-v2/close-out-payloads/ses_116.json"))
print("issues:", m.validate_payload(p, api_base="http://127.0.0.1:8765"))
PY
```

Expect `issues: []`.

## 3. Apply

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_116.json
```

Expect exit 0. The apply atomically writes SES-116, CNV-018, DEC-331, the seven `commit` records, the references, flips PI-076/077/078/079/082 → Resolved (via `resolves_planning_items`), records the `addresses` edges for PI-081/083, and lazy-creates the `close_out_payload` + `deposit_event` (DEP-NNN), teeing the log to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log`.

## 4. Post-apply verification

```bash
# Resolved PIs
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print({p['identifier']:p['status'] for p in d if p['identifier'] in {'PI-076','PI-077','PI-078','PI-079','PI-081','PI-082','PI-083'}})"
# Expect 076/077/078/079/082 Resolved; 081/083 still Open (addressed, not resolved).

# Session + deposit event landed
curl -s http://127.0.0.1:8765/sessions/SES-116 | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['session_status'])"
```

## 5. Commit

From the main repo working tree, commit the regenerated `db-export/*.json` snapshots + the new `deposit-event-logs/dep_NNN.log` + `ses_116.json` + this apply prompt in one commit:

```
v2: SES-116 close-out applied — WS-012 orchestrator track (PI-076–083), DEC-331
```

Note incidental db-export records the re-export may sweep in (parallel-session pending records), per the SES-115 precedent. The seven PI-076–083 code commits remain on `pi-076-area-field`; merge/land them per your branch plan (they're referenced by SHA in `commits[]`).
