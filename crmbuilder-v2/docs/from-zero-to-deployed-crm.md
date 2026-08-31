# From Zero to a Working CRM

The complete operator's path from **no infrastructure at all** — no domain, no
server, no accounts — to a client's CRM deployed, configured from its design,
verified, and in its users' hands. Written for whoever drives the CRMBuilder
desktop for an engagement; every step says where you are, what to do, what you
should see, and what to do if you don't.

This guide is the concrete companion to the Master CRMBuilder PRD's delivery
phases (Part V, Phases 11–13): the PRD defines the process engine-agnostically;
this guide names the actual products (EspoCRM, DigitalOcean, Cloudflare) and
the actual buttons. Third-party console labels drift — where a menu is not
where this guide says, the target named in the step is what matters; tell the
session you're working with what you see.

**What you need before anything:** a credit card for two accounts (the domain
registrar and DigitalOcean — server cost from ~$24/month prorated), a password
manager, and the engagement's approved design in V2 (for the configuration
part; deployment alone needs no design). Time: about an hour of clicks plus
waits, most of it DNS and installer time.

---

## 1. Register a domain

The CRM lives at a name like `crm.clientdomain.com`. If the client already owns
a domain, skip to section 2. Registrar consoles differ; steps below are the
common shape.

1. In the web browser, open a registrar (Porkbun and GoDaddy are the ones used
   on this project; any registrar works). Create or sign in to an account.
2. In the registrar's search box, type the domain you want (the bare name, e.g.
   `clientdomain.com`) and press Enter. You should see whether it is available
   and its yearly price.
3. Add the available domain to the cart and complete the purchase. Decline the
   add-ons (hosting, email, site builders) — none are needed. You should end
   on a confirmation page and receive a receipt email.
4. In the registrar's domain list, the new domain appears, typically marked
   active within minutes. If it hasn't appeared after 15 minutes, contact the
   registrar's support before proceeding.

## 2. Put the domain's DNS on Cloudflare

Cloudflare will hold the domain's DNS so CRMBuilder can create the CRM's
record automatically. The domain stays registered where it is; only DNS moves.

1. In the web browser, open <https://dash.cloudflare.com>. Create or sign in
   to the account that will manage this client's DNS.
2. On the dashboard home, click **+ Add a domain** (older layouts: *Add a
   site*). Type the bare domain (no `www`, no `https://`) → **Continue**.
3. Choose the **Free** plan → **Continue**.
4. On *Review your DNS records*: for a brand-new domain the list is empty or
   holds only registrar parking records — nothing to change. For a domain
   already in use, confirm every record the domain relies on (website `A` /
   `CNAME`, email `MX`) is listed and add anything missing with **+ Add
   record** — a record missed here is the only thing this switch can break.
   → **Continue to activation**.
5. Cloudflare shows **two nameservers** (e.g. `grant.ns.cloudflare.com` and
   `luciane.ns.cloudflare.com`; yours will differ). Keep this page open and
   copy both exactly.
6. In a new tab, sign in at the registrar → open the domain → find the
   **Nameservers** setting (sometimes under *DNS management*; on GoDaddy: the
   domain → **DNS** → *Nameservers* → **Change** → *I'll use my own
   nameservers*). Delete every existing nameserver line, enter the two
   Cloudflare names one per line, and save. The registrar confirms the update.
7. Still at the registrar, if a **DNSSEC** section shows records, delete them
   — stale DNSSEC records make the domain stop resolving after the switch.
8. Back in the Cloudflare tab, click **Check nameservers**. The zone shows
   *Pending nameserver update*; Cloudflare emails when it flips to **Active**
   — usually under an hour, occasionally up to 24. Do not continue to section
   5 until the dashboard shows the green **Active** badge.

## 3. Create the DigitalOcean account and its token

DigitalOcean hosts the CRM's server. One account can serve many engagements,
or the client can own theirs — the token is stored per engagement either way.

1. In the web browser, open <https://cloud.digitalocean.com> and create or
   sign in to the account that will own (and pay for) the client's server.
   Confirm a payment method is on file (**Settings → Billing**).
2. Left sidebar → **API** (under *Manage*) → **Tokens** tab → **Generate New
   Token**.
3. Name it for the engagement (e.g. `crmbuilder-<client>`), set an expiration
   you're comfortable renewing, and give it **Full Access** (the deploy
   creates a server and registers a key; read-only is not enough). Click
   **Generate Token**.
4. The token (`dop_v1_…`) is shown **once**. Copy it into the password manager
   under a name like `<Client> DigitalOcean token`. You paste it into
   CRMBuilder once, in section 5.

## 4. Create the Cloudflare API token

This token lets the deploy create the CRM's DNS record — scoped to the one
zone, nothing else.

1. In the Cloudflare dashboard, click the profile icon (top right) → **My
   Profile** → **API Tokens** → **Create Token** → under *Custom token* click
   **Get started**.
2. Name it for the engagement (e.g. `crmbuilder-<client>-dns`).
3. Under *Permissions*, add two rows: **Zone · Zone · Read** and **Zone · DNS
   · Edit**.
4. Under *Zone Resources*: **Include → Specific zone → the client's zone**.
5. **Continue to summary** → **Create Token**. Copy the token (shown once)
   into the password manager as `<Client> Cloudflare token`.

## 5. In the CRMBuilder desktop — store the engagement's provider credentials

Done once per engagement; every deploy after this skips straight to the wizard.
You must be an administrator, and the engagement must be selected in the
desktop's engagement picker.

1. Open the CRMBuilder desktop. In the left sidebar under **Governance**,
   click **Instances**.
2. Click **Deploy new…** at the top of the panel. The window *Deploy a new CRM
   instance* opens on *Step 1 of 5 — Providers*; both lines read **Not set**.
3. Click **Set credentials…**. The *Provider credentials* window opens with a
   **DigitalOcean** box and a **Cloudflare** box.
4. In the **DigitalOcean** box: click in *Token*, paste the DigitalOcean token
   from section 3; click in *Label*, type whose account it is (e.g.
   `CRMBuilder account` or `<Client>'s account`); click **Save token**. The
   line above turns green **✓ Configured** and the token field empties — the
   token is stored encrypted and never shown again. If an error window
   appears, stop and report exactly what it says.
5. In the **Cloudflare** box: paste the Cloudflare token from section 4, label
   it, click **Save token**. The line turns green **✓ Configured**.
6. Click **Close**. Back on *Step 1 of 5*, both lines read **✓ Configured**
   and the server catalog loads in the background.

## 6. In the deploy wizard — deploy the CRM

The service does the work as a *deploy run*; you can close the desktop at any
point and the run continues. Requires the zone from section 2 to be **Active**.

1. On *Step 1 of 5 — Providers*, click **Next**. *Step 2 of 5 — Server* shows
   the Region list already filled from DigitalOcean's live catalog. If it is
   empty, click **Next** anyway and read the notice line — it names what is
   missing.
2. On *Step 2 of 5 — Server*: type the *Instance name* (how it appears in
   CRMBuilder, e.g. the client's name); pick the Region nearest the client;
   Size **s-2vcpu-4gb** is the proven baseline; Image **Ubuntu 24.04 LTS**;
   leave *Extra SSH keys* unticked unless a named person needs shell access.
   Click **Next**.
3. On *Step 3 of 5 — Domain*: pick the client's zone; type the *Subdomain*
   (`crm` is conventional) — the *Instance address* line shows the full name;
   type the *Let's Encrypt email* (the certificate service's contact — expiry
   notices go there). Click **Next**.
4. On *Step 4 of 5 — Accounts*: leave *Administrator username* as `admin`;
   type the administrator email; click **Generate** and **record the password
   in the password manager now** — it is stored encrypted for the deployment
   and used as the instance's credential, but never shown again. Leave
   *Generate database passwords automatically* ticked. Click **Next**.
5. On *Step 5 of 5 — Review*: read the summary back. Click **Deploy**. The
   progress window opens on the new run (`DEP-NNN`).
6. Watch or walk away. The phases, in order, with usual timings: checking
   credentials (seconds) → creating server (1–2 min) → setting DNS (seconds)
   → waiting for DNS (under a minute — the check asks public resolvers) →
   preparing server (2–4 min) → installing CRM (5–10 min) → post-install
   checks → verifying (seven checks) → registering instance. The finish line
   is **Deployment complete.** with `Registered instance INST-NNN`.
7. If the run fails: nothing is destroyed. The log names the failed phase and
   what still exists (server id and address). Fix the cause — it is almost
   always a token permission — then click **Retry** in the progress window or
   from **Deploy History**; the run resumes where it stopped and will not
   create a second server. If the cause isn't obvious from the log, report
   the last 20 log lines.
8. Confirm for yourself: open `https://<subdomain>.<zone>` in the browser —
   the CRM login page, with a valid certificate; log in as `admin` with the
   recorded password. In the desktop, the Instances panel now shows the new
   instance; **Audit now** on it should complete — that proves the stored
   credential works end to end.

## 7. In the desktop — configure the CRM from the design

This is Phase 12 of the process: the engagement's approved design is pushed to
the instance; nothing is configured by hand that the pipeline can write.
Requires an approved design in the engagement's store.

1. In the Instances panel, select the new instance and click **Publish…**. The
   publish window validates the design against the engine schema *and* the
   live instance, and lists every generated program with its status.
2. Review the validation; use **Preview** for the change set. Click
   **Publish**. The run captures a pre-publish backup, applies the design, and
   verifies every published object; the outcome (and any **manual
   configuration required** items) is shown and recorded under **Publish
   History**.
3. Work the manual-config list: items the engine accepts no API write for
   (saved views, duplicate rules, workflows) are performed in the CRM's own
   admin pages and marked done on their `MCF-` records in the desktop.
4. In the **Reconcile** panel, run the design-vs-instance comparison. Every
   row should read as agreement; disposition anything else deliberately
   (publish it, capture it, or accept it with a reason) and repeat until
   clean.

## 8. Verify and hand over

Phase 13: prove it, then give it to the client.

1. Three mechanical checks must be green: the deploy run's verification
   (section 6, already recorded), the publish verification (section 7 step 2),
   and a clean reconcile (section 7 step 4).
2. Run the acceptance pass: stakeholders exercise their real processes against
   the CRM — guided by the engagement's test specifications where they exist.
   Capture every problem as a finding; fix through the design and republish,
   never by hand-editing the instance.
3. Onboard the users: create the client's users and roles in the CRM's admin
   pages (role publishing is manual-config at present); confirm each can log
   in.
4. Hand over: give the client's owner the administrator credential from the
   password manager, show them where the manual-config records live, and
   record the acceptance as a decision in the engagement.

The client now has a CRM that did not exist at step 1 — and V2 holds the
complete account of how it came to be: the deploy run, the publish history
with backups, the reconcile verdicts, and the acceptance decision.

---

*Companion documents:* the Master CRMBuilder PRD Part V (the engine-agnostic
process these steps implement); `crmbuilder-v2/USER-GUIDE.md` § "Deploying a
new CRM instance" (the deployment feature reference);
`crmbuilder-v2/docs/live-proof-desktop-crm-deployment.md` (the four-run live
proof this guide's claims rest on, with results).
