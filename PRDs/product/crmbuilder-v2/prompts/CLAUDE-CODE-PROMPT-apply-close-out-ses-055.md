# CLAUDE-CODE-PROMPT — Apply SES-055 close-out payload

**Last Updated:** 05-22-26 17:30
**Purpose:** Apply the SES-055 close-out payload — the build-planning conversation that closes the governance entity schema-design workstream and plans the v0.7 release.
**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_055.json`
**Predecessor session:** SES-054 (deposit_event schema-design conversation). The SES-054 payload exists at `close-out-payloads/ses_054.json` and should be applied before this one. If SES-054 has not yet been applied at the time this prompt runs, apply it first using the canonical apply-close-out pattern, then return to this prompt.

---

## Scope

Apply `close-out-payloads/ses_055.json` using the existing `crmbuilder-v2/scripts/apply_close_out.py` script. The payload contains:

- 1 session record (SES-055)
- 6 decisions (DEC-161 through DEC-166)
- 0 planning items (PI-022 refinement is recorded in DEC-166 rather than as a new PI; follow-on planning items PI-023, PI-024, PI-025 are authored at the v0.7 build closeout, not here)
- 13 references (6 `decided_in` linking each decision to SES-055; 1 `is_about` from SES-055 to PI-022; 1 cross-conversation `references` to SES-054; 2 `references` from DEC-165 to DEC-158 and from DEC-166 to PI-022; 3 `references` from DEC-161/162/163 to foundation decisions DEC-122/121/117)

The payload is idempotent on re-run; HTTP 409 SKIPs treated as already-present.

---

## Pre-flight

Before running the apply script:

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start the API:
#   uv run crmbuilder-v2-api &

# Pull latest commits from origin/main (SES-055 payload was pushed from the build-planning sandbox)
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# Verify the payload file exists
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_055.json

# Verify SES-054 has been applied (the predecessor); if not, apply it first
curl -sf http://127.0.0.1:8765/sessions/SES-054 | head -5
# If this returns 404, SES-054 has not yet been applied. Apply it via its own
# Claude Code prompt before continuing:
#   PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-054.md
# Open that prompt in Claude Code, let it execute, then return to this prompt.
```

---

## Apply

Run the apply script against the payload:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_055.json
```

Expected output: one session created (HTTP 201), six decisions created (HTTP 201 each), thirteen references created (HTTP 201 each). Total 20 operations. Exit code 0.

If any operation fails with a non-409 error (HTTP 422 for validation errors, HTTP 500 for server errors, connection failure), capture the script's stderr and stop — investigate before re-running.

If the script reports HTTP 409 SKIPs for any record (already present), continue — the apply is idempotent.

---

## Post-apply verification

```bash
# Verify the session record exists
curl -s http://127.0.0.1:8765/sessions/SES-055 | python3 -c "import sys, json; d = json.load(sys.stdin); print(d['data']['identifier'], d['data']['title'])"

# Verify the six decisions exist
for id in DEC-161 DEC-162 DEC-163 DEC-164 DEC-165 DEC-166; do
  curl -s http://127.0.0.1:8765/decisions/$id | python3 -c "import sys, json; d = json.load(sys.stdin); print(d['data']['identifier'], d['data']['title'])"
done

# Verify the references are in place
curl -s "http://127.0.0.1:8765/references?target_id=SES-055&target_type=session" | python3 -c "import sys, json; d = json.load(sys.stdin); print(f'{len(d[\"data\"])} references target SES-055')"
```

Expected: SES-055 session present; six decisions present (DEC-161 through DEC-166); at least six `decided_in` references targeting SES-055 (plus any other references targeting SES-055 from other entity types if present).

---

## Identifier note

The payload assumes:

- Next available session identifier is SES-055 (verified against the database snapshot at this conversation's authoring time, which showed SES-053 as the latest applied; SES-054 payload was queued but not yet applied).
- Next available decision identifiers are DEC-161 through DEC-166 (SES-054 reserves DEC-155 through DEC-160).

If the database state has shifted by the time this prompt runs (e.g., another conversation closed between SES-054 and this apply), the identifiers in the payload may need re-assignment. The apply script will reject duplicate identifiers with HTTP 409; if that happens, investigate the actual next-available values via `GET /sessions/next-identifier` and `GET /decisions/next-identifier`, edit the payload file in place to use the actual values, and re-run the apply.

---

## After this apply lands

The governance entity schema-design workstream is fully closed at the planning-and-design phase. Build execution begins with Slice A of v0.7:

- **Next action:** Run Slice A's Claude Code prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-A-schema-and-access.md`.

The release ships after all six slices (A through F) complete and the v0.7 build closeout session lands.
