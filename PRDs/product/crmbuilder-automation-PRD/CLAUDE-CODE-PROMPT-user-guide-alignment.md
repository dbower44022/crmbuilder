# Claude Code Prompt: User Guide Alignment Changes

## Context

A review of the CRM Builder User Guide (v1.1) against the L2 PRD and the implemented UI identified naming mismatches and gaps. This prompt covers the mechanical renaming changes that can be applied without design decisions.

## Repository

`dbower44022/crmbuilder`

## Task 1: Rename "Dashboard" → "Requirements Dashboard" in L2 PRD

The L2 PRD (`PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`) uses "Dashboard" and "Project Dashboard" throughout Section 14. The correct user-facing name is **Requirements Dashboard**.

Changes required in the L2 PRD document:

- Section 14.1: The sidebar entry labeled "Dashboard" must be renamed to "Requirements Dashboard"
- Section 14.2: The heading "Project Dashboard" must be renamed to "Requirements Dashboard". All references to "Project Dashboard" and "dashboard" (when referring to this specific view) should use "Requirements Dashboard"
- Section 14.2.5: The breadcrumb example "Dashboard > {Work Item Name}" should become "Requirements Dashboard > {Work Item Name}" or just "Dashboard > {Work Item Name}" if the breadcrumb uses a shortened form — confirm with Doug
- Any other references to "Project Dashboard" or "the dashboard" in Sections 14.3–14.10 that refer to this specific sidebar view should be updated
- Update the document version number and Last Updated timestamp (format: MM-DD-YY HH:MM)

**Do not rename** generic uses of the word "dashboard" that are not referring to this specific sidebar view.

## Task 2: Rename "Run Import" → "Import Results" in Implementation

The implemented UI has a button labeled "Run Import" that should be labeled **"Import Results"** to match the L2 PRD (Section 14.3.3).

Search the codebase under `automation/ui/` for:
- Any button label, action name, or menu text containing "Run Import"
- Replace with "Import Results"
- Check for related tooltip text, status bar messages, or test assertions that reference the old name

## Task 3: Rename "Dashboard" → "Requirements Dashboard" in Implementation

Search the codebase under `automation/ui/` for:
- Sidebar entry labels, window titles, breadcrumb text, or navigation labels that display "Dashboard" as the name of this view
- Replace the user-facing label with "Requirements Dashboard"
- Internal variable names and class names do NOT need to change unless they would cause confusion (e.g., a class named `DashboardView` is fine; a user-facing string `"Dashboard"` displayed in the sidebar is not)

## Verification

After making changes:
- Run the full test suite (`pytest`) and confirm all tests pass
- Run `ruff check` and confirm no lint issues
- Grep for any remaining instances of "Run Import" or "Project Dashboard" that should have been renamed

## Out of Scope — Design Items (Separate Session Required)

The following gaps were identified during the User Guide review but require design decisions before they can be addressed. These should be worked through one at a time with Doug in a separate conversation:

1. **Client Creation UI** — Section 14 needs a "Create Client" flow in Requirements mode (name, project folder path, database initialization). This is the application entry point and is currently undefined in the L2 PRD.

2. **Deployment Mode UI** — The User Guide references a "Deploy panel" and "Deploy Wizard" but the L2 PRD Section 14 focuses on Requirements mode. Deployment mode UI design may be incomplete.

3. **Instance-to-Client Association** — The L2 PRD Section 14.1 mentions a client selector that "optionally auto-links to a CRM instance," but the workflow for creating that association (which phase, which UI action) is not explicitly designed.

4. **Deploy Wizard Scope** — The User Guide specifies "domain configuration and SSL certificate issuance" which assumes self-hosted deployment. The L2 PRD should define Deploy Wizard behavior across deployment scenarios (cloud-hosted vs. self-hosted).
