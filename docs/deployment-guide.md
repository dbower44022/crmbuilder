# EspoCRM Implementation Tool — Deployment Guide

**Version:** 1.0  
**Last Updated:** March 2026  
**Changelog:** See end of document.

**Audience:** Technical team members deploying a CRM configuration to an
EspoCRM instance for the first time, or promoting a tested configuration
to production.

**Scope:** Operational steps — setting up the tool, deploying YAML program
files to a test instance, verifying the result, and promoting to production.

**Prerequisites:** Before following this guide, your YAML program files
must be authored and validated. See the
[Process Guide](process.md) for instructions on requirements capture,
YAML authoring, and the complete design-to-maintenance lifecycle.

---

## 1. Overview

Deployment follows a two-instance model:

```
YAML Program Files
       ↓
  Deploy to Test     ← validate everything works
       ↓
  Verify on Test     ← confirm clean state
       ↓
  UAT (manual)       ← user acceptance testing in EspoCRM
       ↓
  Deploy to Prod     ← same YAML, different instance
       ↓
  Verify on Prod     ← confirm production matches spec
       ↓
  Generate Docs      ← update reference manual
       ↓
  Commit & Push      ← lock the deployment in version control
```

Because the tool is idempotent, deploying to production after a successful
test deployment is simply selecting a different instance and clicking Run.

---

## 2. Tool Setup

### 2.1 Install the Tool

```bash
git clone https://github.com/dbower44022/espo-implementation-tool.git
cd espo-implementation-tool
uv sync
```

Requires Python 3.12+, uv, and Node.js.

### 2.2 Launch

```bash
uv run espo-impl
```

### 2.3 Add the Test Instance

1. Click **+ Add** in the Instance panel
2. Fill in:
   - **Name** — e.g., `CBM Test`
   - **URL** — EspoCRM instance URL
   - **Auth Method** — Use **Basic** for EspoCRM Cloud
   - **Username / Password** — Admin credentials
   - **Project Folder** — Click **Browse** and select the client repo folder
     (e.g., `~/Projects/ClevelandBusinessMentoring`)
3. Click **Save**

The tool creates `programs/`, `reports/`, and `Implementation Docs/`
subdirectories inside the project folder if they don't exist.

### 2.4 Add Program Files

Place your YAML program files in the `programs/` subdirectory of the
project folder. They appear in the Program File panel automatically when
the instance is selected.

---

## 3. Pre-Deployment Checklist

Before running any files, complete this checklist:

- [ ] All YAML files are in the `programs/` directory
- [ ] Each file has been validated (no structural errors)
- [ ] `content_version` is set on all files
- [ ] Any pre-deployment manual steps are completed (see Section 7)
- [ ] Test instance is reachable (try Validate on any file)
- [ ] Test instance has no live data that would be affected by delete operations

---

## 4. Test Instance Deployment

### 4.1 Recommended File Order

Deploy in this order to ensure entities exist before relationships are created:

**Step 1 — Custom entities (fields + layouts)**
```
cbm_engagement_fields.yaml
cbm_session_fields.yaml
cbm_nps_survey_fields.yaml
cbm_workshop_fields.yaml
cbm_workshop_attendance_fields.yaml
cbm_dues_fields.yaml
cbm_partner_agreement_fields.yaml
cbm_client_partner_association_fields.yaml
cbm_partner_activity_fields.yaml
```

**Step 2 — Native entity extensions**
```
cbm_contact_fields.yaml
cbm_account_fields.yaml
cbm_partner_account_fields.yaml
cbm_partner_contact_fields.yaml
```

**Step 3 — Relationships**
```
cbm_relationships.yaml
cbm_partner_relationships.yaml
```

Alternatively, use `cbm_full_rebuild.yaml` for Steps 1 and 2 combined
(deploys all custom entities in one run).

### 4.2 Running Each File

For each file:

1. Select the instance in the Instance panel
2. Select the program file in the Program File panel
3. Click **Validate** — wait for the preview to complete
4. Review the planned changes summary
5. Click **Run**
6. If a confirmation dialog appears, choose **Skip deletes** for a test
   instance with existing data, or **Proceed with deletes** for a clean
   test instance
7. Watch the output panel — green lines are success, red lines are errors
8. When the run completes, click **Verify** to confirm the deployment

### 4.3 What Clean Output Looks Like

**Validate:**
```
[VALIDATE] OK — 1 entities, 42 fields found
[VALIDATE] Checking instance for planned changes ...
===========================================
PLANNED CHANGES
===========================================
  To create : 42
  To update : 0
  No change : 0
===========================================
```

**Run (first deployment):**
```
=== ENTITY CREATION ===
[CREATE]  CEngagement ... OK
[REBUILD] Cache rebuild complete

=== FIELD OPERATIONS ===
[CHECK]   Engagement.status ... NOT FOUND
[CREATE]  Engagement.status ... OK
[VERIFY]  Engagement.status ... VERIFIED
...

=== LAYOUT OPERATIONS ===
[LAYOUT]  Engagement.detail ... UPDATING
[LAYOUT]  Engagement.detail ... UPDATED OK
[LAYOUT]  Engagement.detail ... VERIFIED

===========================================
RUN SUMMARY
===========================================
Total fields processed : 11
  Created              : 11
  Updated              : 0
  Skipped (no change)  : 0
  Verification failed  : 0
  Errors               : 0
===========================================
```

**Verify (after run):**
```
[VERIFY]  Engagement.status ... VERIFIED
[VERIFY]  Engagement.meetingCadence ... VERIFIED
...
===========================================
RUN SUMMARY
===========================================
Total fields processed : 11
  Verification failed  : 0
  Errors               : 0
===========================================
```

**Relationships run:**
```
[RELATIONSHIP]  Session → Engagement (sessionEngagement) ... SKIP (manual)
[RELATIONSHIP]  NpsSurveyResponse → Engagement (engagement) ... CREATING
[RELATIONSHIP]  NpsSurveyResponse → Engagement (engagement) ... CREATED OK
[RELATIONSHIP]  NpsSurveyResponse → Engagement (engagement) ... VERIFIED
...
===========================================
RELATIONSHIP SUMMARY
===========================================
Total relationships processed : 11
  Created              : 5
  Skipped (manual)     : 6
  Failed               : 0
===========================================
```

### 4.4 Handling Errors During Run

**TYPE CONFLICT** — a field exists with a different type than specified:
1. Note the field name
2. Delete it manually in EspoCRM: Administration → Entity Manager →
   {Entity} → Fields → find the field → Remove Field
3. Re-run the file — the tool will recreate it with the correct type

**HTTP 409 on a relationship** — name conflict with an existing link:
1. Check what links exist:
   `https://{instance}/api/v1/Metadata?key=entityDefs.{Entity}.links`
2. Identify the conflict
3. Update the `link` name in the YAML and bump `content_version`
4. Re-run the relationships file

**HTTP 403 on all operations** — authentication issue:
- Switch to **Basic** auth with admin username/password

**Any other errors** — check the run report:
1. Click **View Report**
2. Find the ERROR lines
3. The report includes the HTTP status code and response body

---

## 5. Verifying the Test Deployment

After all files have been deployed, do a final verification pass across
all files:

1. Select each program file in turn
2. Click **Verify**
3. Confirm all fields show VERIFIED with 0 errors

A clean verify across all files means the test instance exactly matches
the YAML specification.

### 5.1 Second Run Test (Idempotency Check)

Re-run one or two files after verifying. All fields should show
NO CHANGES NEEDED with 0 created and 0 updated. This confirms the tool
is truly idempotent and safe to run repeatedly.

---

## 6. Generate Docs and Commit

After the test deployment is verified:

1. Click **Generate Docs** in the tool
2. Review `Implementation Docs/CBM-CRM-Reference.docx` — confirm it
   accurately reflects the deployed configuration
3. Commit everything to the client repository:

```bash
cd ~/Projects/ClevelandBusinessMentoring
git add programs/
git add "Implementation Docs/"
git commit -m "deploy: CBM test instance deployment complete — all fields and relationships verified"
git push
```

---

## 7. Production Promotion

### 7.1 Add the Production Instance

1. Click **+ Add** in the Instance panel
2. Fill in:
   - **Name** — e.g., `CBM Production`
   - **URL** — production EspoCRM URL
   - **Auth Method** — Basic
   - **Project Folder** — same project folder as the test instance
     (`~/Projects/ClevelandBusinessMentoring`)
3. Click **Save**

Both instances share the same project folder and YAML files. Switching
instances automatically switches context — the Program File panel shows
the same files for both.

### 7.2 Pre-Production Manual Steps

Complete any manual steps required before deploying to production.
See Section 8 for CBM-specific notes.

### 7.3 Deploy to Production

Follow the same sequence as the test deployment (Section 4) with the
production instance selected.

**Key differences for production:**
- Always choose **Skip deletes** in the confirmation dialog — never
  delete entities on a production instance with live data
- Run files one at a time and verify each before proceeding
- Have a rollback plan — know which fields can be safely deleted if
  a type conflict is discovered

### 7.4 Verify Production

After all files have run, do a full verify pass across all files on
the production instance. Confirm 0 errors before proceeding.

### 7.5 Post-Deployment

1. Click **Generate Docs** with the production instance selected
2. Commit and push the updated docs
3. Tag the deployment in git:

```bash
git tag -a "deploy-prod-v1.0" -m "CBM Production initial deployment"
git push --tags
```

---

## 8. CBM-Specific Pre-Deployment Steps

The following manual steps are required before running the tool against
the CBM Production instance. These are one-time fixes for items
configured manually before the tool was built.

### 8.1 Account — Time in Operation Field

The `cTimeInOperation` field was created manually as `varchar` but the
YAML defines it as `enum`.

**Action before running `cbm_account_fields.yaml` on production:**
1. Export any existing values from `cTimeInOperation` across all Account
   records (Administration → Import/Export or a list view export)
2. Go to Administration → Entity Manager → Account → Fields
3. Find `Time in Operation` and click **Remove Field**
4. Run `cbm_account_fields.yaml` — the tool recreates it as `enum`
5. Re-import the exported values if needed

### 8.2 PartnerActivity — Description Field

No action required. The YAML uses `activityDescription` instead of
`description` (which is a reserved native field name on Base entities).
The tool creates `cActivityDescription` automatically.

---

## 9. Next Steps After Deployment

With the deployment complete, the following ongoing processes apply.
See the [Process Guide](process.md) for full details:

- **Adding new fields** — update YAML, run the affected file, verify, regenerate docs
- **Changing enum values** — update options in YAML, run the file
- **Adding new entities or modules** — write PRD first, then YAML, then deploy
- **Handling PRD changes** — update YAML files, bump content_version, run and verify
- **Keeping docs current** — regenerate and commit docs after every YAML change

The test → production promotion process described in this guide applies
to every subsequent change: validate on test first, verify clean, then
promote to production.
---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 1.0 | March 2026 | Initial release |
