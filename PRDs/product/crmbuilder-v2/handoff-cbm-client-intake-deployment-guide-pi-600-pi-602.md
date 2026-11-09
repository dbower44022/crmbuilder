# Handoff — update the chapter deployment guide for CRMBuilder's new deploy wizard (PI-600, PI-602)

| Field | Value |
|---|---|
| Title | Handoff — update the chapter deployment guide for CRMBuilder's new deploy wizard (PI-600, PI-602) |
| Last Updated | 11-09-26 12:16 |
| Revision | 1.0 |
| Status | Ready once PI-602 is rolled out to production. Paste into a Claude Code session started in `~/Dropbox/Projects/cbm-client-intake`. |
| Governs | One documentation session in `cbm-client-intake`: guide steps 5.8, 9.2 and 9.3, the methods file's step 5.8, and `OPEN-ITEMS.md` item 73. |
| Source | CRMBuilder SES-459 on 11-09-26: PI-600 (DEC-1205, REQ-668..REQ-670) accepted in CNV-426; PI-602 (DEC-1206, REQ-671, REQ-672). |

Paste everything below the line into a new Claude Code session started in `~/Dropbox/Projects/cbm-client-intake`. That session follows this repository's `CLAUDE.md`; its operating mode there is DETAIL.

---

Operating mode: DETAIL. Stopping points: (1) after the proposed wording for each step is shown, before any file is changed; (2) after the files are changed, before the commit.

## What changed in CRMBuilder

CRMBuilder's deploy wizard changed on 11-09-26 (PI-600, and PI-602 once rolled out). The chapter deployment guide still describes the old wizard. The old labels "Instances", "Deploy new…", "Step 1 of 5 — Providers" and "Deploy a new CRM instance" no longer exist. Guide step 5.8 also tells the operator to create a separate engagement for the chapter to hold its tokens; that is no longer how tokens are held.

What is true now:

- A chapter is a **client** of the application ENG-002 (Cleveland Business Mentoring), holding a **deployment grant**. It is not a new engagement.
- A chapter's tokens belong to its **deployment**, and they are entered inside the deploy wizard. Entering them is no longer a separate step done before the wizard.
- A deployment for a client that only holds a deployment grant **never** uses the application's tokens (DEC-1206). The wizard refuses to leave step 1 until the deployment has its own DigitalOcean token. CRMBuilder can create the DNS record only with the deployment's own Cloudflare token; without one, manual DNS is the only choice.
- Pressing **Set credentials…** or leaving step 1 records the deployment. A wizard cancelled after that leaves the deployment in the Deployments panel marked **active — not yet run**, which **Remove** deletes together with its tokens. The tokens stay in the chapter's vault and are entered again in a fresh wizard.
- Enter in a wizard text box no longer closes the wizard. In the web address box it checks the address.

## Exact screens and labels

**Recording the chapter as a client** (once per chapter)
- Side bar group Operate CRMBuilder, entry **Clients**, button **New Client**. The window is titled **New client**, with the fields Name, Notes and Status, and a **Save** button.
- Select the client. In the section **Deployment grants**, choose **ENG-002 — Cleveland Business Mentoring (adds a deployment grant)** in the list, then click **Add application**. The section then lists "ENG-002 — Cleveland Business Mentoring (CBM) — defined by CLI-001".

**Opening the wizard**
- In the strip across the top, choose **Cleveland Business Mentoring (CBM)**.
- Tab **11 · CRM Deployment**, side bar entry **Deployments**, button **New deployment…**. The window is titled **Deploy a new CRM**. Its pages are titled "Step N of 6 — …": Before you start, Web address, DNS, Server, Administrator, Review.

**Step 1 — Before you start**
- Under **Who is this deployment for?** are three fields:
  - **Client**: the chapter, shown as "<chapter name> — holds a deployment grant".
  - **Purpose**: **Client's own**.
  - **What should CRMBuilder call this deployment?**: for example "<chapter short name> CRM".
- Under **This deployment's hosting accounts** are two status lines, **DigitalOcean (required)** and **Cloudflare (optional)**, and the **Set credentials…** button.
- Before any token is entered for a chapter, both lines read **Not set — this deployment needs its own token**. Next then explains: "This client deploys into its own accounts, so this deployment needs its own DigitalOcean token: press Set credentials…."
- **Set credentials…** opens a window titled **Hosting credentials for deployment DPL-NNN — <deployment name>**.
  - It has one box for **DigitalOcean** and one for **Cloudflare**. Each box has **Token**, **Label** and **Save token**. **Close** closes the window.
  - After saving, a box reads "✓ Configured — <label> (this deployment)".
- Back on step 1, the lines read "✓ Configured — <label> (this deployment's own)".

**Later pages**
- **Web address**: box **What web address should the CRM use?**, button **Check this address**.
- **DNS**: two choices:
  - **CRMBuilder creates it in Cloudflare**, offered only for a zone in the deployment's own Cloudflare account; its note begins "Available".
  - **It is created by hand at the domain's DNS host (manual DNS)**.
- **Server**:
  - **How large a server?**, with **Show every size**.
  - **Where should the server be?**
  - **Operating system**, which is fixed.
  - **Extra SSH keys (optional)**, read from the chapter's own DigitalOcean account.
  - The deployment name is no longer asked here.
- **Administrator**:
  - **Administrator username**.
  - **Administrator email**.
  - **Administrator password**, with Generate, Copy and Show.
  - **Email for certificate notices**.
  - **Generate database passwords automatically (recommended)**.
- **Review**: the button reads **Deploy**.

**Removing an abandoned deployment**
- In **Deployments**, a deployment that never ran shows Status **active — not yet run**.
- **Remove** asks "Remove DPL-NNN — <name>?" and says that its own DigitalOcean and Cloudflare tokens are deleted. Click **Yes**.
- For a deployment that has run, Remove says "<id> — <name> has run, so it cannot be removed", with only an **OK** button.

## What to change

1. **Guide step 5.8** (`prds/chapter-network/deployment-guide/guide/05-open-the-chapter-s-service-accounts.md`) keeps creating the two tokens and putting them in the vault. Remove its CRMBuilder part: creating the engagement and entering the tokens in a Provider credentials window. Its "Done when" no longer includes "entered in CRMBuilder". Say that the tokens are entered in step 9.3.
2. **Guide step 9.3** (`guide/09-build-the-crm-system.md`) is rewritten from the labels above.
   - It opens with recording the chapter as a client with a deployment grant, if that isn't done.
   - It enters the two tokens inside the wizard on step 1.
   - It runs the wizard in one sitting. A cancelled wizard leaves a deployment to remove, and its tokens must be entered again.
   - Remove its warning that "Any other label means the server would be built in someone else's account". CRMBuilder now enforces that, and the step can say so.
3. **Guide step 9.2's "First:" line** no longer names "the chapter's tokens entered in CRMBuilder (step 5.8)". It names "the chapter's tokens in its vault (step 5.8)".
4. **An SSH key before the first run.** The chapter's DigitalOcean account needs an SSH key before step 9.3, so that **Extra SSH keys (optional)** can tick crm-SHORT-LABEL. The Business Mentors Association's account had none on 11-09-26. Place that in step 5.8 or in a step before 9.3, as fits the guide.
5. **The methods file's step 5.8** (`prds/chapter-network/deployment-guide/9-Methods-Hosting-Website-Policies.md`) gets the same correction as item 1. Its "How you know it worked" becomes the step 1 status lines above.
6. **`OPEN-ITEMS.md` item 73.** Record that the CRMBuilder gap that blocked the Association's first deploy run is closed (PI-600 accepted on 11-09-26; PI-602). Name what is still owed for the Association: an SSH key in its DigitalOcean account, then the first deploy run.

Give every changed file a new revision and change-log row, as that repository's documents already carry.

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 11-09-26 12:16 | Claude (Claude Code) | First version, written in CRMBuilder SES-459 after the PI-600 acceptance (CNV-426) and DEC-1206. |
