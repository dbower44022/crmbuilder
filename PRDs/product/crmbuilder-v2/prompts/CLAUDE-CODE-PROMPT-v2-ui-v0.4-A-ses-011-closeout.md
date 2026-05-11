# CLAUDE-CODE-PROMPT v2-ui-v0.4-A — SES-011 closeout

**Last Updated:** 05-11-26 16:30
**Purpose:** Close out the v0.4 planning conversation (SES-011) by writing the session record directly via the v2 storage API and then executing the apply script that writes the six decisions, patches PI-001, creates PI-002 through PI-005, and writes the six `decided_in` references linking the decisions to SES-011.
**Predecessor conversation:** Claude.ai planning conversation on 05-11-26 that redirected v0.4 from a UI-polish release to a methodology-entity-schema-design workstream. Produced `PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md`, `methodology-entity-schema-spec-guide.md`, four `schema-design-kickoff-*.md` files, and `scripts/apply_ses_011_planning_records.py`. All eight files are already on `origin/main` at commit `ff07d38` or later.

---

## Scope and ordering

This prompt does two things, in order:

1. **POST SES-011 to `http://127.0.0.1:8765/sessions`** with the verbatim body in Appendix A. Idempotent: if SES-011 already exists (HTTP 409), continue.
2. **Run `uv run python scripts/apply_ses_011_planning_records.py`** from `crmbuilder-v2/`. The script's pre-flight checks that SES-011 exists (which step 1 just ensured), then writes the six decisions, patches PI-001, creates the four new planning items, and writes the six references.

Step 1 deviates from the session-record-at-close dogfood pattern (which prescribes writing the session record through the v0.3 desktop New Session dialog). The deviation is an acceptable one-time loss accepted by Doug for the closeout-automation gain — subsequent workstream session records will return to the dialog pattern.

---

## Pre-flight

Before step 1:

```bash
# Working directory
cd ~/Dropbox/Projects/CRM\ Builder/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2
# (Use whichever path matches Doug's clone; the script below references the
# parent dir via Path(__file__).resolve().parents[2] regardless.)

# API health
curl -sf http://127.0.0.1:8765/health
# Expect: {"data":{"ok":true},"meta":{},"errors":null}

# Storage path sanity
ls -la data/storage.db && echo "OK"

# Optional: confirm SES-011 does NOT already exist
curl -sf http://127.0.0.1:8765/sessions/SES-011 && echo "SES-011 already exists" || echo "SES-011 not yet present (expected)"
```

If `curl` against `/health` fails, start the API per `crmbuilder-v2/USER-GUIDE.md` before continuing.

---

## Step 1 — POST SES-011

Send the request below. Use Python (`urllib.request`) rather than shell `curl` so the verbatim body survives without escaping pain. Run this from `crmbuilder-v2/` so the working directory matches the apply script.

```python
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8765"

SES_011_BODY = {
    "identifier": "SES-011",
    "title": "v0.4 planning — methodology entity schema-design workstream kickoff",
    "session_date": "05-11-26",
    "status": "Complete",
    "conversation_reference": (
        "Claude.ai planning conversation on 05-11-26 that redirected v0.4 from a "
        "UI-polish release to a methodology-entity-schema-design workstream. Produced "
        "methodology-schema-workstream-plan.md, methodology-entity-schema-spec-guide.md, "
        "four schema-design-kickoff-*.md files under PRDs/product/crmbuilder-v2/, and "
        "scripts/apply_ses_011_planning_records.py. No transcript preserved per DEC-025. "
        "Session record written via direct API (one-time deviation from session-record-"
        "at-close dialog pattern, accepted by Doug for closeout-automation gain)."
    ),
    "topics_covered": SES_011_TOPICS_COVERED,
    "summary": SES_011_SUMMARY,
    "artifacts_produced": SES_011_ARTIFACTS,
    "in_flight_at_end": SES_011_IN_FLIGHT,
}


def post_session(body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}/sessions",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


status, payload = post_session(SES_011_BODY)
if status in (200, 201):
    print(f"✓ SES-011 created (HTTP {status})")
elif status == 409:
    print(f"· SES-011 already exists (HTTP 409) — continuing")
else:
    print(f"✗ SES-011 POST failed (HTTP {status}): {payload}")
    raise SystemExit(1)
```

The four string constants `SES_011_TOPICS_COVERED`, `SES_011_SUMMARY`, `SES_011_ARTIFACTS`, and `SES_011_IN_FLIGHT` are the verbatim strings from Appendix A below. Inline them as Python triple-quoted strings; do not paraphrase, reformat, or strip them.

---

## Step 2 — Run the apply script

Once SES-011 is in the database:

```bash
cd crmbuilder-v2  # if not already there
uv run python scripts/apply_ses_011_planning_records.py
```

Expected output (paraphrased — the script's own messages are verbose but show structure):

```
✓ Pre-flight: SES-011 exists in the database.

=== Writing 6 decisions ===
  ✓ POST /decisions  DEC-038 (HTTP 201)
  ✓ POST /decisions  DEC-039 (HTTP 201)
  ✓ POST /decisions  DEC-040 (HTTP 201)
  ✓ POST /decisions  DEC-041 (HTTP 201)
  ✓ POST /decisions  DEC-042 (HTTP 201)
  ✓ POST /decisions  DEC-043 (HTTP 201)

=== Patching PI-001 (fourth deferral) ===
  ✓ PATCH /planning-items/PI-001 (HTTP 200)

=== Writing 4 new planning items ===
  ✓ POST /planning-items  PI-002 (HTTP 201)
  ✓ POST /planning-items  PI-003 (HTTP 201)
  ✓ POST /planning-items  PI-004 (HTTP 201)
  ✓ POST /planning-items  PI-005 (HTTP 201)

=== Writing 6 references (decided_in → SES-011) ===
  ✓ POST /references  DEC-038 decided_in SES-011 (HTTP 201)
  ✓ POST /references  DEC-039 decided_in SES-011 (HTTP 201)
  ✓ POST /references  DEC-040 decided_in SES-011 (HTTP 201)
  ✓ POST /references  DEC-041 decided_in SES-011 (HTTP 201)
  ✓ POST /references  DEC-042 decided_in SES-011 (HTTP 201)
  ✓ POST /references  DEC-043 decided_in SES-011 (HTTP 201)

✓ All operations complete.
```

Exit code 0 on full success. Re-running is safe — every operation treats HTTP 409 as already-present.

---

## Verification

After both steps complete, verify the state via curl:

```bash
# 10 sessions before this prompt; should be 11 now
curl -sf http://127.0.0.1:8765/sessions | python3 -c "import sys, json; print(len(json.load(sys.stdin)['data']))"
# Expect: 11

# 37 decisions before this prompt; should be 43 now
curl -sf http://127.0.0.1:8765/decisions | python3 -c "import sys, json; print(len(json.load(sys.stdin)['data']))"
# Expect: 43

# 1 planning item before this prompt; should be 5 now
curl -sf http://127.0.0.1:8765/planning-items | python3 -c "import sys, json; print(len(json.load(sys.stdin)['data']))"
# Expect: 5

# Check PI-001 reflects fourth deferral
curl -sf http://127.0.0.1:8765/planning-items/PI-001 | python3 -c "import sys, json; d=json.load(sys.stdin)['data']; print('Fourth deferral mentioned:', 'DEFERRED FOUR TIMES' in d['description'])"
# Expect: True

# Check references exist
curl -sf "http://127.0.0.1:8765/references?source_identifier=DEC-038" | python3 -c "import sys, json; print('DEC-038 references:', len(json.load(sys.stdin)['data']))"
# Expect: 1 (decided_in → SES-011)
```

If any verification fails, surface the actual response payload so Doug can diagnose. Do not attempt corrective writes — every operation in the apply script and the SES-011 POST is meant to be a single attempt, and rerunning is safe.

---

## What this prompt does NOT do

- Update `db-export/` JSON snapshots in the repo. Those are regenerated by a separate process (or manually if needed). This prompt only touches the live SQLite database via the API.
- Commit anything. Database changes don't go into git; only the source-of-truth document files (workstream plan, spec guide, four kickoffs, apply script, this prompt) are versioned, and they're already on `main` at commit `ff07d38` or later.
- Open the next schema-design conversation. After this prompt completes, Doug starts a fresh Claude.ai conversation and uploads `PRDs/product/crmbuilder-v2/schema-design-kickoff-domain.md` to begin the workstream's first schema-design conversation.

---

## Appendix A — SES-011 verbatim body strings

The four strings below are the verbatim values for `topics_covered`, `summary`, `artifacts_produced`, and `in_flight_at_end` on the SES-011 record. Inline them as Python triple-quoted strings in step 1's script. **Do not paraphrase or reformat.**

### A.1 `SES_011_TOPICS_COVERED`

```
Seed prompt: "Plan v0.4 of the v2 desktop UI for the CRM Builder project. Drive a structured architectural discussion that produces three deliverables: ui-PRD-v0.4.md (intent, scope, acceptance criteria, error handling matrix, open questions, same shape as v0.1/v0.2/v0.3), ui-v0.4-implementation-plan.md (slice breakdown with deliverables and acceptance gates per slice), and execution prompts under PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.4-{A..*}-*.md (one per implementation slice, structure matching the v0.1/v0.2/v0.3 prompts). Cadence matches v0.1/v0.2/v0.3: structured architectural discussion driven one decision at a time, building toward the PRD first, then the implementation plan, then the execution prompts."

Twelve architectural questions discussed and resolved:

Q1 (frame): v0.4's primary frame. Doug surfaced that the natural next step was preparing for a real-world test by redoing the CBM design, and CBM redo on v2 as system of record for both governance and methodology content requires v2 to have entity types for methodology content. Path chosen: (b) — CBM redo runs on v2 as system of record for both governance AND methodology content; v0.4's primary frame becomes methodology entity schema design (Bucket C from the original kickoff). Captured in DEC-038.

Q1.5 (path under b): the original kickoff explicitly forbids designing schemas inline in a planning conversation. Three paths under (b) considered: (b-α) two-stage — planning conversation pivots to workstream kickoff; (b-β) placeholder v0.4 PRD with TBD schema slots; (b-γ) scope-only inline schema design (violates kickoff constraint). Chose (b-α). Captured in DEC-038.

Q2 (scope philosophy): three options — big design up front (8-10 entity types), minimum viable (only what evolved Phase 1 needs), hybrid (Phase 1 plus buffer). Chose minimum viable. Captured in DEC-038.

Q3 (methodology choice for CBM redo): two options — original 13-phase methodology (live, currently mid-execution on CBM) or evolved methodology (research-stage at PRDs/process/research/evolved-methodology/, simulator-tested against CBM on 04-30-26). Chose evolved methodology — adoption pilot doubles as v2 real-world test. Captured in DEC-038.

Q4 (multi-tenancy): kickoff forbids fundamental storage architecture changes, putting multi-tenant v2 out of scope. Finding (not a decision): one v2 instance per engagement. CBM gets its own v2 instance; CBM's Mission Statement uses the existing Charter entity (versioned-replace + Make Current pattern) — no new entity type for Mission Statement. Captured in DEC-039.

Q5 (entity inventory): Phase 1 produces Mission Statement (→ Charter), Domain Inventory, Prioritized Backbone, Initial CRM Candidate Set. Initial proposal: three entity types — domain, process, crm_candidate. Doug pushed back that excluding entity while including crm_candidate was strange. Phase 1 interview guide v0.2 line 62 confirms: 'Phase 1 may surface entity names as nouns the client uses, but does not produce Entity PRDs.' Revised: four entity types — domain, entity (thin), process (thin), crm_candidate. Persona deferred (Phase 1 guide explicitly excludes persona elicitation). Captured in DEC-039.

Q6 (per-conversation product): what does each schema-design conversation produce? Three options — (1) design only, (2) design plus build prompt, (3) design plus integration analysis. Chose (1): each schema-design conversation produces a schema spec, the DEC-NNN decisions made during it, and a session record; build prompts come from a separate v0.4-build-planning conversation that takes all four specs as input. Captured in DEC-040.

Q7 (conversation order): domain → entity → process → crm_candidate. Reasoning: domain is foundational; entity is independent of process; process is most relational; crm_candidate is independent coda. Alternative (crm_candidate first as warmup) rejected because warmup-first delays testing the spec methodology against relational complexity. Captured in DEC-040.

Q8 (schema-spec methodology doc outline): nine sections — Identity, Fields, Relationships, Lifecycle, API surface, UI considerations, Acceptance criteria, Open questions, Cross-references. Confirmed.

Q9 (UI considerations section pattern): template-with-deviation-by-justification — default panel layout given, schema may diverge with explicit rationale. Captured in DEC-040.

Q10 (existing v0.4 kickoff supersession): three options — (X) mark in place, (Y) delete, (Z) archive. Chose (X) — supersession header at the top of the existing kickoff; SES-010's artifacts_produced reference remains valid. Captured in DEC-041.

Q11 (PI-001 fourth deferral mechanics): kickoff requires fourth deferral to have new tracking mechanism plus rationale. Three options — (α) simple tracking, (β) CBM-redo-friction trigger, (γ) hard backstop. Chose (β) — if CBM redo Phase 1 surfaces visual friction on any of the four new methodology panels, PI-001 gets pulled to v0.5 ahead of any other v0.5 candidate. Captured in DEC-042.

Q12 (SES-010 identifier-asymmetry resolution): three options — defer entirely, GET helpers for new four only, GET helpers for all 12 prefixed entity types (with PI-002 tracking option C for future). Chose option (3): all 12. Captured in DEC-043.

Final synthesis: deliverables of this conversation confirmed as the workstream plan, schema-spec methodology guide, four per-entity kickoff prompts, supersession edit, six consolidated decisions, one PI patch, four new planning items.
```

### A.2 `SES_011_SUMMARY`

```
Planning conversation that redirected v0.4 from a UI-polish release to a methodology-entity-schema-design workstream. Twelve architectural questions resolved into six decisions (DEC-038 through DEC-043). Produced a workstream master plan, a schema-spec methodology guide, and four per-entity kickoff prompts at PRDs/product/crmbuilder-v2/, plus a supersession header on the original v0.4 kickoff and a Python apply script for the governance records. The four schema-design conversations (domain, entity, process, crm_candidate) run sequentially after this conversation closes, followed by a single v0.4-build-planning conversation that takes the four specs as input and produces the v0.4 PRD, implementation plan, and slice build prompts.
```

### A.3 `SES_011_ARTIFACTS`

```
PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md (master workstream plan)
PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md (schema-spec template for the four schema-design conversations)
PRDs/product/crmbuilder-v2/schema-design-kickoff-domain.md (first schema-design conversation kickoff)
PRDs/product/crmbuilder-v2/schema-design-kickoff-entity.md (second schema-design conversation kickoff)
PRDs/product/crmbuilder-v2/schema-design-kickoff-process.md (third schema-design conversation kickoff)
PRDs/product/crmbuilder-v2/schema-design-kickoff-crm_candidate.md (fourth schema-design conversation kickoff)
PRDs/product/crmbuilder-v2/ui-v0.4-planning-prompt.md (existing v0.4 kickoff with supersession header added per DEC-041)
crmbuilder-v2/scripts/apply_ses_011_planning_records.py (idempotent script that writes DEC-038..DEC-043, patches PI-001, creates PI-002..PI-005, and writes six decided_in references to SES-011)
PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.4-A-ses-011-closeout.md (this prompt — writes SES-011 then runs the apply script)
DEC-038 (v0.4 redirect — methodology entity schema design as primary frame)
DEC-039 (minimum entity inventory plus multi-tenancy finding)
DEC-040 (schema-design workstream structure)
DEC-041 (existing v0.4 kickoff supersession — in-place marking)
DEC-042 (PI-001 fourth deferral with CBM-redo-friction trigger)
DEC-043 (SES-010 resolution — GET /<entity>/next-identifier helpers for all 12 prefixed entity types)
PI-001 patch (fourth deferral language; cites DEC-042)
PI-002 (make identifier optional in POST bodies — SES-010 option C, future ergonomic work)
PI-003 (persona entity type for v0.5+)
PI-004 (additional methodology entity types — field, requirement, manual_config, test_spec — for v0.5+)
PI-005 (process schema growth beyond Phase 1 thin shape)
Six decided_in references linking each of DEC-038..DEC-043 to SES-011.
```

### A.4 `SES_011_IN_FLIGHT`

```
Four schema-design conversations queued in workstream order (domain first):
1. domain — kickoff at PRDs/product/crmbuilder-v2/schema-design-kickoff-domain.md
2. entity — kickoff at PRDs/product/crmbuilder-v2/schema-design-kickoff-entity.md
3. process — kickoff at PRDs/product/crmbuilder-v2/schema-design-kickoff-process.md
4. crm_candidate — kickoff at PRDs/product/crmbuilder-v2/schema-design-kickoff-crm_candidate.md

After all four complete, a single v0.4-build-planning conversation opens against an as-yet-unwritten kickoff (authored at the close of the fourth schema-design conversation). That conversation takes all four schema specs as input and produces ui-PRD-v0.4.md, ui-v0.4-implementation-plan.md, and slice build prompts under PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.4-{A..*}-*.md. Build then runs via Claude Code execution of the slice prompts.

PI-001 (full styling design pass) deferred a fourth time per DEC-042 with CBM-redo-friction trigger mechanism — pulled to v0.5 ahead of any other v0.5 candidate if CBM redo Phase 1 surfaces visual friction on any of the four new methodology entity panels in v0.4. PI-002 (SES-010 option C) tracked for future ergonomic work. PI-003, PI-004, PI-005 track methodology entity types and process schema growth deferred from v0.4.

Subsequent workstream session records return to the session-record-at-close dialog pattern (the SES-011 direct-API write is a one-time deviation accepted for closeout-automation gain).
```

---

End of prompt.
