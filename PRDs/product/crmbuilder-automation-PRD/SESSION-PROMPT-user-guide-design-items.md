# Session Prompt: User Guide Review — Design Items

## Context

A review of the CRM Builder User Guide (v1.1) against the L2 PRD identified four design gaps that require decisions before they can be added to the L2 PRD and the implementation. These items were documented as out-of-scope in `CLAUDE-CODE-PROMPT-user-guide-alignment.md` and deferred for a dedicated design session.

This session works through those four items one at a time, with each design decision confirmed before moving to the next, following Doug's standard working style.

## Repository

`dbower44022/crmbuilder`

## Required Reading at Start of Session

1. `CLAUDE.md` (root)
2. `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx` — particularly Section 14 (User Interface) in full, and Section 9 (Workflow Engine) and Section 10 (Prompt Generator) for context on phase definitions
3. `docs/CRM-Builder-User-Guide.docx` — the user guide that surfaced these gaps, particularly Sections 4.2 (Setting Up a Project) and 4.8 (Deploying and Configuring the CRM)
4. `CLAUDE-CODE-PROMPT-user-guide-alignment.md` — for context on what was already addressed and the out-of-scope items being picked up here

## Working Approach

- Address design items in the order listed below
- For each item, present the gap, propose options with tradeoffs, wait for Doug's selection, then document the decision
- Do not make any document or code changes until all design decisions are made — capture decisions in working notes during the conversation
- Once all four items are decided, draft the L2 PRD updates as a single coordinated change
- Keep track of decisions as DEC-### entries (continuing from DEC-053, the most recent decision in the L2 PRD)
- Open issues should be tracked as ISS-### entries (continuing from ISS-015)

## Design Item 1: Client Creation UI

**Gap:** Section 14 of the L2 PRD has no defined flow for creating a new client. The User Guide describes opening Requirements mode, clicking "Create Client," providing a name and project folder, and the application initializing the project database and folder structure. No corresponding UI is specified in the L2 PRD.

**Questions to resolve:**
- Where in the UI does Create Client live? (Sidebar action? Splash screen on app launch when no client exists? Dropdown in the client selector?)
- What fields are captured at creation time? (Just name and project folder? Or additional metadata like organization type, contact, target CRM platform?)
- What validation is applied? (Project folder must exist? Must be empty? Must be a git repo? Should the application offer to initialize git?)
- What does the application do after creation? (Auto-navigate to the Requirements Dashboard? Open Phase 1 Master PRD work item directly?)
- What happens to existing clients — is there a client management view (list, edit, delete, archive)?

## Design Item 2: Deployment Mode UI

**Gap:** Section 14 of the L2 PRD focuses entirely on Requirements mode. The User Guide references a "Deploy panel" and "Deploy Wizard" as part of Phase 10 (CRM Deployment), but no UI is defined for Deployment mode in the L2 PRD.

**Questions to resolve:**
- What is the overall structure of Deployment mode? (Same sidebar pattern as Requirements mode with different entries? A wizard-style linear flow? A single panel?)
- What sidebar entries (or equivalent navigation) does Deployment mode contain?
- How does the implementor switch between Requirements mode and Deployment mode? (Mode toggle in the main window? Separate workflows triggered from the Requirements Dashboard?)
- Is Deployment mode tied to a specific work item (CRM Deployment), or is it a separate global view?
- Does Deployment mode share the breadcrumb/drill-down stack pattern from Requirements mode?

## Design Item 3: Instance-to-Client Association

**Gap:** Section 14.1 of the L2 PRD mentions a client selector that "optionally auto-links to a CRM instance when the association exists," but the L2 PRD does not define when or how that association is created.

**Questions to resolve:**
- At what phase is an instance first associated with a client? (Phase 10 — CRM Deployment, since that is when the instance first comes into existence?)
- Does an instance belong to exactly one client, or can a single instance serve multiple clients? (CBM has Test and Production — are those two instances both associated with the same client?)
- Can a client have multiple instances? If yes, how does the auto-link behavior in the client selector work — does it pick a default, prompt the user, or show all?
- Does the association store URL and credentials, or just a reference to a separately-managed instance record?
- What happens if the instance is deleted or its credentials change?

## Design Item 4: Deploy Wizard Scope

**Gap:** The User Guide currently states the Deploy Wizard handles "domain configuration and SSL certificate issuance." This assumes self-hosted deployment. The L2 PRD must define Deploy Wizard behavior across deployment scenarios.

**Questions to resolve:**
- What deployment scenarios must be supported? (Self-hosted on Doug's own server? Cloud-hosted by the CRM vendor? Both?)
- For self-hosted: what does the Deploy Wizard automate? (Server provisioning, OS setup, web server config, database setup, CRM installation, domain DNS, SSL certificates, admin account creation?)
- For cloud-hosted: what does the Deploy Wizard do? (Just capture credentials for an externally-provisioned instance? Drive a vendor API to provision?)
- How does the wizard branch based on scenario? (Selection at start? Driven by CRM Selection output from Phase 9?)
- What is out of scope for the wizard and considered manual? (DNS records, payment methods, account creation with the vendor?)
- Per Doug's standard, no specific product or vendor names should appear in the L2 PRD — the wizard description must be expressed in generic terms

## Output

After all four design decisions are made:

1. Draft L2 PRD updates (new and modified subsections in Section 14, new decisions DEC-054+, any new open issues)
2. Apply updates to `crmbuilder-automation-l2-PRD.docx` using the standard unpack/edit/repack workflow
3. Increment the L2 PRD version number and update Last Updated (format: MM-DD-YY HH:MM)
4. Commit and push to `dbower44022/crmbuilder`
5. After L2 PRD changes are committed, identify any User Guide updates needed and apply them in a separate commit
