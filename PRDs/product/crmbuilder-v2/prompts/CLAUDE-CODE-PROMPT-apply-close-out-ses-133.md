# Apply close-out — SES-133 / CNV-035 (YAML schema v1.3 Section 12 / RBAC Parts A–E)

Run from Claude Code at the repo root with the v2 API up. Identifiers are provisional and re-verify at apply; re-key on collision.

## Net effect

Lands in the **CRMBUILDER** engagement:

- 1 session — **SES-133** (status `complete`)
- 1 conversation — **CNV-035** (status `complete`), belongs to SES-133 and to Project WS-015
- 1 **new Project — WS-015** "YAML Schema v1.3 — Role-Based Access Control" (created in the pre-step, not by the payload)
- 3 decisions — **DEC-345** (Section 12 placement: new top-level section), **DEC-346** (no file-type discriminator; `roles:` and `teams:` are optional top-level keys), **DEC-347** (deploy ordering: loader-level content-based discovery) — each `decided_in` CNV-035
- 0 planning items
- 0 work tickets
- 1 commit — **`06c36054d585ff59dc72fca0eb23cd55a6279745`** ("yaml-schema v1.3: add Section 12 — Role-Based Access Control (Category 6 Parts A–E)"; already on origin/main as an ancestor of HEAD; net diff +657 / -8 lines on `PRDs/product/app-yaml-schema.md`)
- 6 references total (1 `session_belongs_to_workstream`, 1 `conversation_belongs_to_session`, 1 `conversation_belongs_to_workstream`, 3 `decided_in`)

**Not changed by this apply:** No PI status moves. The implementation prompt series for v1.3 (loader extensions, validator extensions, two new deploy managers `role_manager.py` + `team_manager.py`, API client extensions for `/api/v1/Role` and `/api/v1/Team`, condition_expression.py role-clause support, tests matching the v1.1 archived series pattern at `PRDs/_archive/yaml-schema-prompts/`) is the next conversation's work, not in this close-out.

## Pre-flight

```bash
cd crmbuilder-v2
curl -s http://127.0.0.1:8765/health
# Re-verify heads haven't advanced in parallel; re-key the payload + this prompt on collision.
for ep in sessions conversations decisions planning-items work-tickets workstreams; do
  curl -s "http://127.0.0.1:8765/$ep/next-identifier"; echo; done
# Expect: SES-133, CNV-035, DEC-345, PI-113, WT-064, WS-015 — assuming SES-132 has already applied.
# If SES-132 has not applied yet, apply ses_132.json first.

# Confirm the payload is present:
ls -1 ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_133.json
```

**Pre-step — create the new Project WS-015 out-of-band** (mirrors the SES-079/SES-132 pattern; a Project/`workstream` is not created by the close-out payload). Verify the field names against the live `/workstreams` POST schema before running:

```bash
# VERIFY FIELD NAMES against the current workstreams schema, then:
curl -s -X POST http://127.0.0.1:8765/workstreams \
  -H 'Content-Type: application/json' \
  -d '{"workstream_identifier":"WS-015","workstream_title":"YAML Schema v1.3 — Role-Based Access Control","workstream_description":"Deliver the v1.2-scope half of Category 6 (Role-Based Access Control) from yaml-schema-gap-analysis-MR-pilot.md Section 6, as amended 05-20-26. Spans the schema-spec drafting (this session, complete at commit 06c3605), the implementation prompt series for Claude Code (loader extensions for the new top-level keys roles: and teams:, validator extensions enforcing whitelist semantics and Q5 coverage and the operator-restriction and context-restriction on role: leaf clauses, two new deploy managers role_manager.py and team_manager.py wired ahead of fields and relationships per Section 12.6, API client extensions for /api/v1/Role and /api/v1/Team, condition_expression.py role-clause support, and test coverage matching the v1.1 archived series pattern at PRDs/_archive/yaml-schema-prompts/), and the eventual deployment artifacts. Field-level permissions and named permission presets (gap-analysis Section 6 Deferred to v1.3) remain queued behind this Project as a separate future bump. Opened at SES-133.","workstream_status":"in_flight"}'
# Re-key to the next free WS- identifier if WS-015 is taken; update the two CNV-035->WS-015 references in the payload and the session->WS-015 reference to match.
```

## Apply

```bash
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_133.json
# Expect OK: 1 session, 1 conversation, 3 decisions, 0 planning_items, 0 work_tickets, 1 commit, 6 references.
```

## Post-apply verification

```bash
curl -s http://127.0.0.1:8765/sessions/SES-133 | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['session_status'])"     # complete
curl -s http://127.0.0.1:8765/conversations/CNV-035 | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['conversation_status'])"  # complete
curl -s "http://127.0.0.1:8765/references/from/decision/DEC-345" | python3 -c "import sys,json;[print(r['relationship'],r['target_type'],r['target_id']) for r in json.load(sys.stdin)['data']]"   # decided_in conversation CNV-035
curl -s "http://127.0.0.1:8765/references/from/conversation/CNV-035" | python3 -c "import sys,json;[print(r['relationship'],r['target_id']) for r in json.load(sys.stdin)['data']]"               # belongs_to_session SES-133, belongs_to_workstream WS-015
curl -s "http://127.0.0.1:8765/references/from/session/SES-133" | python3 -c "import sys,json;[print(r['relationship'],r['target_id']) for r in json.load(sys.stdin)['data']]"                    # session_belongs_to_workstream WS-015
curl -s http://127.0.0.1:8765/commits/06c36054d585ff59dc72fca0eb23cd55a6279745 | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['commit_message_first_line'])"  # yaml-schema v1.3 …
```

## Commit snapshot

After verification passes, commit the regenerated db-export JSON snapshots:

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git status   # confirm only db-export/ files changed
git diff --stat PRDs/product/crmbuilder-v2/db-export/
git commit -m "v2: apply SES-133 — YAML schema v1.3 Section 12 (RBAC Parts A–E) drafted

Lands 1 session (SES-133), 1 conversation (CNV-035), 3 decisions
(DEC-345 section placement, DEC-346 no file-type discriminator,
DEC-347 content-based deploy ordering), 0 planning items, 0 work
tickets, 1 commit (06c3605 — yaml-schema v1.3), 6 references.

Opens new Project WS-015 (YAML Schema v1.3 — Role-Based Access
Control) carrying the schema-spec drafting through implementation
and deployment.

Substantive artifact already on origin/main as ancestor of HEAD:
- PRDs/product/app-yaml-schema.md v1.3 at 06c3605 (header bump
  v1.2.4 → v1.3, revision-history entry, Section 3.1 extension for
  roles: and teams: top-level keys, Section 7.1 layout-variant
  alternative, Section 10 new validation block, Section 11
  leaf-clause split, full new Section 12)

Next: v1.3 Category 6 implementation prompt series for Claude Code
covering loader extensions for roles:/teams:/scope_access:/system_
permissions: parsing, validator extensions enforcing the new
Section 10 rules, two new deploy managers (role_manager.py,
team_manager.py) wired ahead of fields/relationships per Section
12.6, API client extensions for /api/v1/Role and /api/v1/Team,
condition_expression.py role-clause support with context-flag
plumbing, and test coverage matching the v1.1 archived series
pattern at PRDs/_archive/yaml-schema-prompts/."
git push origin main
```
