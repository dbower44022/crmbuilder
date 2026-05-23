# CLAUDE-CODE-PROMPT — Apply SES-063 close-out payload

**Last Updated:** 05-23-26 22:30
**Purpose:** Apply the SES-063 close-out payload — the PI-028 schema-design conversation that authored `governance-schema-specs/commit.md` v1.0, settled three governing decisions (DEC-198 status-free documentary lifecycle refining DEC-137; DEC-199 FK-over-references-edge deviation from DEC-124 with frequency-justified-denormalization rationale; DEC-200 four new cross-spec precedents elevated), and authored the PI-029 Prompt A that will land the storage foundation for the commit entity.

**Net Effect block (records that will land):**
- 1 session record (SES-063) — the commit schema-design conversation
- 3 decision records (DEC-198, DEC-199, DEC-200) — status-free lifecycle, FK deviation, four new cross-spec precedents
- 0 planning items (PI-028 stays Open per methodology §9; PI-033 resolves it retroactively)
- 4 references — 3 `decided_in` (DEC-198/192/193 → SES-063) + 1 `is_about` (SES-063 → PI-028)
- 1 deposit_event written at apply close + edges per the v0.7 apply pattern

**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_063.json`

**Predecessor sessions:** SES-060 (audit-v1.2 planning), SES-061 (Code Change Lifecycle methodology drafting), and SES-062 (PI-025 prior-conversations backfill planning). All three should already be applied per their own apply prompts before this one runs. If `curl -sf http://127.0.0.1:8765/sessions/SES-062` returns 404, apply SES-062's close-out first (and SES-060/SES-061 before that if they return 404 too), then return here.

**Successor:** PI-029 Prompt A at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-029-A-commits-table-and-vocab.md`. Run after this apply lands so the DEC-198/192/193 records exist as context for the Prompt A's commit messages and apply-script references.

---

## Pre-flight

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

# Confirm clean working tree
git status

# Confirm git identity
git config user.name "Doug Bower"
git config user.email "doug@dougbower.com"

# Pull latest commits from origin/main (SES-063 payload, the commit spec, and the
# PI-029 Prompt A were pushed from the planning sandbox)
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start the API:
#   uv run crmbuilder-v2-api &

# Verify the payload file exists
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_063.json

# Verify the commit spec and PI-029 Prompt A also exist (same sandbox push)
ls -la ../PRDs/product/crmbuilder-v2/governance-schema-specs/commit.md
ls -la ../PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-029-A-commits-table-and-vocab.md

# Verify the API is routed to the CRMBUILDER engagement (the dogfood DB, not CBM)
curl -s http://127.0.0.1:8765/sessions \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), 'sessions - latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"

# Verify the three predecessor sessions are applied
curl -sf http://127.0.0.1:8765/sessions/SES-060 > /dev/null && echo "SES-060 applied: yes" || echo "SES-060 applied: NO — apply it first"
curl -sf http://127.0.0.1:8765/sessions/SES-061 > /dev/null && echo "SES-061 applied: yes" || echo "SES-061 applied: NO — apply it first"
curl -sf http://127.0.0.1:8765/sessions/SES-062 > /dev/null && echo "SES-062 applied: yes" || echo "SES-062 applied: NO — apply it first"
# If any prints "NO", apply the missing close-out(s) first via the corresponding
# CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md prompt, then return here.

# Capture pre-apply identifier heads for post-apply verification
echo "=== Pre-apply heads ==="
echo "Sessions:"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Decisions:"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Planning items:"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "References (count for delta verification):"
curl -s 'http://127.0.0.1:8765/references?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
```

Expected pre-apply heads (after SES-060, SES-061, and SES-062 have applied): SES-062, DEC-197, PI-044. Reference count varies; capture for delta verification.

**If the SES head is not SES-062** (i.e., another close-out has been applied since the SES-063 payload was authored), stop and report. The SES-063 payload's session identifier is hard-coded; an unexpected head means either (a) a parallel close-out was applied that bumped the head past SES-063 (which would have collided on POST), (b) the payload was authored against a stale snapshot and now collides with the live state, or (c) one of SES-060/SES-061/SES-062 has not yet applied. Diagnose before proceeding.

---

## Apply

Run the apply script against the payload:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_063.json
```

Expected output structure:

- 1 session OK (SES-063)
- 3 decisions OK (DEC-198, DEC-199, DEC-200)
- 0 planning items
- 4 references OK (3 `decided_in` + 1 `is_about` SES-063 → PI-028)
- 1 deposit_event written at apply close

If any record returns 409 SKIP on first run, halt and investigate — first run should have zero SKIPs. On re-run, every record should SKIP idempotently.

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Sessions (expect SES-063):"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Decisions (expect DEC-200):"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Planning items (expect PI-044 — unchanged):"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"

# Spot check SES-063
curl -s http://127.0.0.1:8765/sessions/SES-063 | python3 -m json.tool | head -25

# Spot check DEC-198 (status-free documentary lifecycle, refines DEC-137)
curl -s http://127.0.0.1:8765/decisions/DEC-198 | python3 -m json.tool | head -25

# Spot check DEC-199 (FK-over-references-edge deviation from DEC-124)
curl -s http://127.0.0.1:8765/decisions/DEC-199 | python3 -m json.tool | head -25

# Spot check DEC-200 (four new cross-spec precedents)
curl -s http://127.0.0.1:8765/decisions/DEC-200 | python3 -m json.tool | head -25

# Spot check a decided_in reference: find DEC-198's edge and confirm it resolves
curl -s 'http://127.0.0.1:8765/references?source_type=decision&source_id=DEC-198' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(r['source_id'], '->', r['target_id'], '[', r['relationship_kind'], ']') for r in d]"
# Expect at minimum: DEC-198 -> SES-063 [ decided_in ]

# Spot check the is_about edge SES-063 → PI-028
curl -s 'http://127.0.0.1:8765/references?source_type=session&source_id=SES-063&target_type=planning_item' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(r['source_id'], '->', r['target_id'], '[', r['relationship_kind'], ']') for r in d]"
# Expect: SES-063 -> PI-028 [ is_about ]

# Confirm reference total delta is +9 from pre-apply
# (4 payload refs + 4 wrote_record edges from deposit_event POST + 1 applies_close_out_payload edge to lazy-created COP-062)
echo "Reference total after apply:"
curl -s 'http://127.0.0.1:8765/references?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
```

Expected: sessions head SES-063, decisions head DEC-200, planning_items head PI-044 (unchanged), reference total +9 from pre-apply (4 payload refs + 4 wrote_record edges from the apply script's deposit_event POST [one per record landed: 1 session + 3 decisions = 4] + 1 applies_close_out_payload edge to the lazy-created COP-062).

Confirm PI-028 status remains `Open`:

```bash
curl -s http://127.0.0.1:8765/planning-items/PI-028 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('PI-028 status:', d['planning_item_status'])"
# Expect: PI-028 status: Open
```

PI-028 stays Open per methodology §9 — the `resolves_planning_items` payload section the methodology specifies does not yet ship. PI-033 resolves PI-028 retroactively once PI-030 lands the new payload sections.

---

## Commit snapshot regeneration

The apply script transactionally regenerates the engagement's db-export JSON snapshots on every API write via the `_refresh_snapshot` hook in `crmbuilder-v2/src/crmbuilder_v2/access/engagement.py`. The `change_log.json` file also gets one audit row per write with before/after payloads. After a successful apply, commit the regenerated snapshots together with the deposit-event log:

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect what changed (should be sessions.json, decisions.json, references.json,
# close_out_payloads.json, deposit_events.json, change_log.json, plus the
# deposit-event log)
git status PRDs/product/crmbuilder-v2/db-export/
git status PRDs/product/crmbuilder-v2/deposit-event-logs/

# Commit the snapshot regeneration in a single commit
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "Apply SES-063 close-out: commit entity schema spec landed

Records landed via apply_close_out.py against CRMBUILDER engagement:
- 1 session (SES-063 — PI-028 schema-design conversation)
- 3 decisions (DEC-198 status-free documentary lifecycle refining DEC-137;
  DEC-199 FK-over-references-edge deviation from DEC-124 with
  frequency-justified-denormalization rationale; DEC-200 four new cross-spec
  precedents elevated)
- 0 planning items (PI-028 stays Open per methodology §9; PI-033 resolves
  retroactively)
- 4 references (3 decided_in DEC-198/192/193 -> SES-063, 1 is_about
  SES-063 -> PI-028)
- 1 deposit_event

The commit entity schema spec itself lives at
PRDs/product/crmbuilder-v2/governance-schema-specs/commit.md v1.0. PI-029
Prompt A queued at PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-
pi-029-A-commits-table-and-vocab.md for next Claude Code execution."

git pull --rebase origin main
git push
```

---

## Done

Reply with:

- Pre-apply heads: SES-062, DEC-197, PI-044, references = N (captured)
- Post-apply heads: SES-063, DEC-200, PI-044 (unchanged), references = N + 9
- Record counts (expect 1 session OK, 3 decisions OK, 0 planning items, 4 references OK, 0 SKIPs on first run)
- PI-028 status (expect: Open — stays Open per methodology §9)
- Snapshot commit SHA from the commit-snapshot-regeneration step
- Next prompt to run: `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-029-A-commits-table-and-vocab.md` — lands the commits table, the refs CHECK extensions for the new entity type and the three new/renamed relationship kinds, the `blocks` → `blocked_by` data migration, and the vocab.py update
