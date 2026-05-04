# Claude Code Prompt — Phase 9 YAML Generation, All Domains, Unattended

**Repository:** `dbower44022/ClevelandBusinessMentoring` (working tree
at `~/Dropbox/Projects/ClevelandBusinessMentors/`)
**Branch:** `main` — commit per domain
**Type:** Multi-domain Phase 9 YAML Generation, designed for
unattended execution
**Companion repo (read-only):** `dbower44022/crmbuilder` for the
authoritative guide and schema

---

## 1. Goal

Produce complete, deployable YAML for **all four CBM domains** in a
single unattended run, so the user can return to a YAML set ready to
deploy and validate against the CRM Builder application's Configure
flow. The user is **not available** during the run. Every decision
that would normally pause for human input is instead recorded in
EXCEPTIONS.md with Claude Code's best-effort choice and rationale so
the user can review and reverse on return.

## 2. Scope

Four domains, processed in this order:

1. **MN** (Mentee / Mentoring) — full Phase 9 YAML generation. No
   prior YAML exists. Two MN-owned custom entities (Engagement,
   Session) plus MN's contributions to native Contact.
2. **MR** (Mentor Recruitment) — refresh existing YAML. Two files
   exist (`MR-Contact.yaml`, `MR-Dues.yaml`) but predate current
   Contact v1.7 and Dues v1.1 PRDs. Diff against current PRDs and
   apply drift corrections; do not regenerate from scratch.
3. **CR** (Client Recruitment) — full Phase 9 YAML generation. No
   prior YAML exists. Seven CR-owned custom entities (Partnership
   Agreement, Event, Event Registration, Marketing Campaign,
   Campaign Group, Campaign Engagement, Segment) plus CR's
   contributions to native Contact and Account.
4. **FU** (Fundraising) — verify-only. YAML already complete from
   Phase 9 done 05-01-26. Read it, diff against current FU Domain
   PRD v1.0 and Entity PRDs, append any drift findings to a top-
   level summary; do not regenerate or modify the FU YAML.

## 3. Authoritative inputs (read-only, do not modify)

These live in the **`crmbuilder` repo**, not the CBM repo. Sparse-
checkout that repo if needed.

- **`crmbuilder/PRDs/process/interviews/guide-yaml-generation.md`**
  v1.1 — the authoritative guide for the generation work. **Read
  this in full before generating anything.** It defines defaults,
  conventions, exception categories, manual-config categories, and
  the Stop-and-Ask criteria. The instructions below extend the
  guide for unattended operation; they do not replace it.
- **`crmbuilder/PRDs/product/app-yaml-schema.md`** v1.2.3 — the
  authoritative YAML schema. **Read this before generating
  anything.** Schema features available in v1.1+ are in scope.
  Anything not in v1.1+ goes to MANUAL-CONFIG.md per the guide.

The CBM repo has the **PRDs** that drive the generation:

- Domain PRDs: `PRDs/MN/CBM-Domain-PRD-Mentoring.docx`,
  `PRDs/MR/CBM-Domain-PRD-MentorRecruitment.docx`,
  `PRDs/CR/CBM-Domain-PRD-ClientRecruiting.docx`,
  `PRDs/FU/CBM-Domain-PRD-Fundraising.docx`.
- Process documents per domain — see `PRDs/{DOMAIN}/` and CR sub-
  folders `PRDs/CR/{PARTNER,MARKETING,EVENTS,REACTIVATE}/`.
- Entity PRDs: `PRDs/entities/*.docx` — current state per CBM
  CLAUDE.md is Contact v1.7, Account v1.8, Engagement v1.2,
  Session v1.1, Dues v1.1, Contribution v1.0, Fundraising
  Campaign v1.0, plus seven CR Phase 2b Entity PRDs at v1.0.
- Existing reference YAMLs to mirror structure and conventions:
  `programs/FU/FU-*.yaml` (the most recent and most complete
  reference set).

## 4. Operating principles for unattended execution

These are mandatory and override the standard "ask the user" pattern
in `guide-yaml-generation.md` Section "When to Stop and Ask the
User":

### 4.1 Defer, do not block

Every condition that would normally trigger a Stop-and-Ask in the
guide instead becomes an entry in the per-domain `EXCEPTIONS.md`.
Format the entry as:

```markdown
### {DOMAIN}-Y9-EXC-{NNN}: {short title}

**Trigger:** {what about the input forced this exception}
**Best-effort decision:** {what Claude Code chose to put in the YAML}
**Rationale:** {why this choice was the safest default given the
inputs available}
**Reversal cost:** {how hard it would be to change after deploy —
e.g. "low: enum value addition only", "medium: field type change",
"high: relationship cardinality change"}
**Open question for user:** {the question Claude Code would have
asked if interactive}
```

The user reviews these on return and either accepts each decision
or asks for a targeted regenerate of the affected entity.

### 4.2 Defaults over invention

When a PRD is silent on a YAML detail, use defaults in this order:

1. The default specified in `guide-yaml-generation.md` v1.1 if any.
2. The pattern in the most recent existing CBM YAML if any
   (FU YAMLs are the most recent and most complete; mirror their
   patterns for `settings:`, `savedViews:`, `requiredWhen:`,
   `visibleWhen:`, `formula:`, layout `tabs:`, etc.).
3. The schema's stated default if the schema specifies one.
4. The most conservative interpretation that the deploy will accept
   (e.g. optional rather than required, no rather than yes,
   omitted rather than included). Record the choice as an
   EXCEPTION.

### 4.3 Schema gaps go to MANUAL-CONFIG.md

When a PRD requirement cannot be expressed in v1.1+ schema
(common categories per FU's MANUAL-CONFIG: cross-entity setField
actions, mutually-exclusive-field constraints, cross-entity union
saved views, role-based field visibility, deferred-master-list
option lists), the entry goes to `MANUAL-CONFIG.md` per the guide,
not to EXCEPTIONS.md. Use FU's MANUAL-CONFIG.md as the format
reference.

### 4.4 Single commit per domain

After each domain's outputs are written and validated, commit them
with the message format:

```
phase 9 yaml: {DOMAIN} — {N} files committed

{brief summary of what's in the commit:
 - YAML files generated/refreshed
 - count of fields, entities, relationships
 - count of EXCEPTIONS recorded
 - count of MANUAL-CONFIG entries}
```

Then push immediately. If the run fails partway, prior domains'
work is durable.

### 4.5 No interactive prompts

The standard guide instructs "ask the user." For this run, treat
every such instruction as: "make the best-effort decision, record
the deferral in EXCEPTIONS.md, proceed."

### 4.6 Schema validation on every YAML before commit

After writing each YAML, parse it as YAML to confirm structural
validity. If parsing fails, fix the structural error before
proceeding — do not commit broken YAML. (Semantic validation
against the deploy engine happens during the user's deployment
pass; that is out of scope here.)

### 4.7 No deployment, no Configure runs

This prompt produces YAML only. It does not invoke the CRM Builder
application's Configure flow, does not connect to any EspoCRM
instance, does not modify any database state. All deployment
testing is the user's task on return.

## 5. Per-domain workflow

### 5.1 MN domain — full generation

**Inputs to read first:**

- `PRDs/MN/CBM-Domain-PRD-Mentoring.docx`
- All MN process docs in `PRDs/MN/`: MN-INTAKE, MN-MATCH,
  MN-ENGAGE, MN-CLOSE, MN-INACTIVE
- Entity PRDs: `PRDs/entities/Contact-Entity-PRD.docx` (v1.7),
  `PRDs/entities/Engagement-Entity-PRD.docx` (v1.2),
  `PRDs/entities/Session-Entity-PRD.docx` (v1.1)
- Reference: existing `programs/FU/FU-Contact.yaml` for the native-
  entity-extension pattern; existing `programs/MR/MR-Dues.yaml`
  for the custom-entity pattern

**Outputs (write to `programs/MN/`):**

- `MN-Contact.yaml` — MN's mentee-specific custom field additions
  to native Contact (e.g. mentee status, intake fields, match
  fields, engagement ownership). Mirror FU-Contact.yaml structure.
- `MN-Engagement.yaml` — full custom entity definition.
- `MN-Session.yaml` — full custom entity definition.
- `EXCEPTIONS.md` — per-domain exception list (see 4.1).
- `MANUAL-CONFIG.md` — per-domain manual configuration list (see
  4.3).

**Commit and push.**

### 5.2 MR domain — refresh existing YAML

**Inputs to read first:**

- Existing `programs/MR/MR-Contact.yaml` and
  `programs/MR/MR-Dues.yaml`, plus the existing
  `programs/MR/EXCEPTIONS.md` and `programs/MR/MANUAL-CONFIG.md`.
- `PRDs/MR/CBM-Domain-PRD-MentorRecruitment.docx`
- All MR process docs: MR-RECRUIT, MR-APPLY, MR-ONBOARD,
  MR-MANAGE, MR-DEPART
- Entity PRDs: Contact v1.7, Dues v1.1

**Diff strategy:**

1. Re-derive what the MR YAML *should* be from the current PRDs
   using the same generation logic as a fresh run.
2. Compare to what is in the repo.
3. For every drift, decide: applies-and-update vs.
   was-deliberate-keep. Update where the PRD has clearly
   superseded the YAML. When in doubt, prefer the PRD and record
   an EXCEPTION.
4. If existing EXCEPTIONS.md / MANUAL-CONFIG.md entries from
   prior MR work are still applicable, retain them; append any
   new ones surfaced by this refresh.

**Outputs (in `programs/MR/`):**

- Updated `MR-Contact.yaml` and/or `MR-Dues.yaml` (only files
  with actual changes).
- Updated `EXCEPTIONS.md` and `MANUAL-CONFIG.md` if changes
  occurred.

If the diff yields no changes, leave files untouched and add a
log line to the run summary noting that MR was already current.

**Commit and push** (skip if zero changes).

### 5.3 CR domain — full generation

**Inputs to read first:**

- `PRDs/CR/CBM-Domain-PRD-ClientRecruiting.docx` (v1.2 Phase 8
  Approved)
- `PRDs/CR/CBM-Domain-Overview-ClientRecruiting.docx`
- All four CR sub-domain folders:
  - `PRDs/CR/PARTNER/`: SubDomain Overview, CR-PARTNER-PROSPECT,
    CR-PARTNER-MANAGE
  - `PRDs/CR/MARKETING/`: SubDomain Overview,
    CR-MARKETING-CONTACTS, CR-MARKETING-CAMPAIGNS
  - `PRDs/CR/EVENTS/`: SubDomain Overview, CR-EVENTS-MANAGE,
    CR-EVENTS-CONVERT
  - `PRDs/CR/REACTIVATE/`: SubDomain Overview,
    CR-REACTIVATE-OUTREACH
- Entity PRDs (all v1.0): Partnership Agreement, Event, Event
  Registration, Marketing Campaign, Campaign Group, Campaign
  Engagement, Segment. Plus Contact v1.7 and Account v1.8 for
  CR's contributions to those native entities.

**Outputs (write to `programs/CR/`):**

One YAML per entity. Suggested files (final names follow the
established `{DOMAIN}-{Entity}.yaml` convention):

- `CR-Contact.yaml` — CR's contributions to native Contact (the
  multi-typed contactType fields per CR Domain PRD v1.2 Section
  4, including the howDidYouHearAboutCbm 8-value enum and any
  Partner/Client/Donor type-conditional Contact fields owned by
  CR — distinct from MN-, MR-, and FU-domain Contact additions).
- `CR-Account.yaml` — CR's contributions to native Account
  (geographicServiceArea is FU-domain per ACT-DEC-014; CR-domain
  fields are the Partner-specific and Client-organization
  additions per Section 4 of the CR Domain PRD).
- `CR-PartnershipAgreement.yaml` — full custom entity.
- `CR-Event.yaml` — full custom entity.
- `CR-EventRegistration.yaml` — full custom entity.
- `CR-MarketingCampaign.yaml` — full custom entity. Note channel
  enum value `Reactivation` per Section 4 design.
- `CR-CampaignGroup.yaml` — full custom entity.
- `CR-CampaignEngagement.yaml` — full custom entity.
- `CR-Segment.yaml` — full custom entity. Note segmentType
  discriminator drives conditional field requirements per
  Entity PRD.
- `EXCEPTIONS.md` — per-domain exception list.
- `MANUAL-CONFIG.md` — per-domain manual configuration list.

**Expected complexity:** CBM CLAUDE.md notes CR is "substantially
more output than FU." Expect more EXCEPTIONS than MN; expect the
schema-gap MANUAL-CONFIG entries to overlap heavily with FU's
list (cross-entity setField, mutual exclusivity, cross-entity
union saved views, role-based field visibility).

**Commit and push.**

### 5.4 FU domain — verify only

**Inputs to read first:**

- Existing four YAMLs in `programs/FU/`, plus `EXCEPTIONS.md`
  and `MANUAL-CONFIG.md`.
- `PRDs/FU/CBM-Domain-PRD-Fundraising.docx` (v1.0 Phase 8
  Approved)
- All four FU process docs.
- Entity PRDs: Contribution v1.0, Fundraising Campaign v1.0,
  Contact v1.7, Account v1.8.

**Verify-only check:** parse each FU YAML, sanity-check field
counts and structural integrity against the Entity PRDs. Do not
regenerate. Do not commit changes to FU YAML. Record any drift
found in the top-level summary (Section 6) under an "FU
verification findings" subsection. If no drift, the summary
entry is "FU verification: clean."

## 6. End-of-run summary

After all four domains have been processed, produce one final
top-level document at `programs/PHASE-9-RUN-SUMMARY.md`:

```markdown
# Phase 9 YAML Generation — Multi-Domain Unattended Run Summary

**Run date:** {ISO date}
**Run trigger:** Single Claude Code prompt, unattended
**Source prompt:**
crmbuilder/PRDs/product/crmbuilder-automation-PRD/CLAUDE-CODE-PROMPT-multi-domain-yaml-generation-unattended.md

## Domain results

| Domain | Action | Files | EXCEPTIONS | MANUAL-CONFIG | Commit |
|---|---|---|---|---|---|
| MN | Generated | {count} | {count} | {count} | {hash} |
| MR | Refreshed | {changed/untouched} | {count delta} | {count delta} | {hash or "no commit"} |
| CR | Generated | {count} | {count} | {count} | {hash} |
| FU | Verified | (no changes) | — | — | — |

## EXCEPTIONS deferral roll-up

A consolidated list of every Stop-and-Ask deferral across all
domains, in the order the user should review them. For each:
domain, exception ID, short title, best-effort decision summary,
reversal cost.

{enumerate every entry from each domain's EXCEPTIONS.md}

## MANUAL-CONFIG roll-up by category

Group by category — Role-Based Field Visibility, Advanced
Automation, Cross-Entity Union Views, Deferred Master Lists,
etc. — across all four domains.

## FU verification findings

{populated only if drift found}

## Schema v1.2 candidates

If during generation the same schema gap surfaced as MANUAL-CONFIG
in multiple domains, list it here as a candidate for promotion to
schema v1.2. Mirror the FU Phase 9 candidate list as a starting
point.
```

Commit and push the summary as a final commit:

```
phase 9 yaml: multi-domain run summary

End-of-run summary covering MN (generated), MR (refreshed), CR
(generated), FU (verified). {N} EXCEPTIONS deferred for user
review; {M} MANUAL-CONFIG entries surfaced.
```

## 7. Out of scope

- Do NOT modify any PRD documents. PRDs are the source of truth;
  any drift detected becomes an EXCEPTION or a finding in the
  summary.
- Do NOT touch the L1 or L2 PRD in `crmbuilder/PRDs/product/`.
- Do NOT touch the YAML schema or any code in `crmbuilder/`.
- Do NOT call CRM Builder's `Configure` action against the test
  instance.
- Do NOT issue any Recovery & Reset operation against any
  EspoCRM instance.
- Do NOT regenerate FU YAML.
- Do NOT delete archived YAML in `programs/Archive/`.

## 8. Manual reset instructions for the user (post-run)

When the user returns and wants to validate the generated YAML
against a clean EspoCRM instance, the steps are **manual** and
**not** part of this prompt's unattended run. They are documented
here for the user's reference. Append this section verbatim into
`programs/PHASE-9-RUN-SUMMARY.md` under a final "## Next steps"
heading so the user sees it immediately on return.

```markdown
## Next steps for the user

### Reset the EspoCRM test instance to a clean state

1. Open the CRM Builder application.
2. Navigate to the **Deployment** tab.
3. Click the **Recovery & Reset** button to open the modal dialog.
4. In the **Full Database Reset** section, type `DELETE ALL DATA`
   in the confirmation field exactly (it is case-sensitive).
5. Click **Run Full Reset** and wait for the operation to finish.
   This tears down all containers, wipes all volumes, and re-runs
   the EspoCRM installer from scratch. The instance will be
   restored to a fresh out-of-the-box state.

### Deploy and validate, one YAML at a time

For each domain in dependency order — MN → MR → CR → FU —
deploy each YAML in the domain's `programs/{DOMAIN}/` folder
through the **Deployment → Configure** entry. After each
deployment:

1. Read the run log for warnings, errors, and unexpected
   `NOT_SUPPORTED` lines.
2. Open EspoCRM and exercise each entity touched by the YAML —
   create a record, edit it, view list and detail.
3. Capture findings (engine bugs vs. YAML-shape bugs vs.
   schema/PRD divergences) in a per-deployment notes file.

When everything passes, the deployment-engine validation pass
is complete.

### Review EXCEPTIONS

Open `programs/PHASE-9-RUN-SUMMARY.md` and walk the EXCEPTIONS
roll-up. For each entry, accept the best-effort decision or
request a targeted regenerate of the affected entity.
```

## 9. Verification before exit

Before declaring the run complete, Claude Code verifies:

- Every YAML file written parses as valid YAML (`yaml.safe_load`
  succeeds).
- Every domain has either a commit on `main` (with push
  succeeding) or an explicit "no commit needed" log line.
- `programs/PHASE-9-RUN-SUMMARY.md` exists and lists every
  domain.
- `git status` is clean (no uncommitted changes left behind).
- `git log origin/main..HEAD` is empty (everything pushed).

## 10. Commit-message template

Per domain (Section 4.4 already specifies the format). Final
summary commit (Section 6 already specifies). All commits go to
`main` directly, signed with the user's git identity per the
local clone's existing config.

## 11. If anything blocks

If a hard blocker is hit that prevents proceeding (e.g. a PRD
file is missing, a schema document is missing, the repo state is
unexpected), record the blocker in
`programs/PHASE-9-RUN-BLOCKED.md` with full context, push the
file, and exit. The user will see this on return and resume
diagnosis manually. Do not attempt to invent inputs or proceed
past genuine blockers.

---

**End of prompt. Begin Phase 9 multi-domain run.**
