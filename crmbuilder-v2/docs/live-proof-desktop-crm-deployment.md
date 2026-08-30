# Live proof — admin-driven CRM deployment (PI-419 / REQ-522)

The gate before this feature is trusted or rolled out: two real deploy runs
against a throwaway DigitalOcean droplet, driven from the v2 desktop, with the
service running **locally on your machine** so production is never involved.
Run 1 proves the clean path; run 2 proves the failure-keeps-everything-and-
retry-resumes path (DEC-945). An optional third check proves a restarted
service resumes an interrupted run.

Budget: about 60–90 minutes; one droplet at a time (≈ $24/month, prorated —
under a dollar for the exercise). Everything created is deleted at the end.

---

## 0. What you need before starting

### 0.1 Repository

You will do the whole proof from one terminal window; keep it open until the
end.

1. Open a terminal (Ubuntu: **Ctrl + Alt + T**).
2. Go to the repository. Type the line below and press Enter:

   ```bash
   cd ~/Dropbox/Projects/crmbuilder
   ```
   The prompt now ends in `crmbuilder`. If it says *No such file or
   directory*, the clone is somewhere else — find it and use that path.
3. Make sure you are on the `main` branch:

   ```bash
   git checkout main
   ```
   You should see either `Already on 'main'` or `Switched to branch 'main'`.
   If instead it says local changes would be overwritten, stop and tell me
   before doing anything else — some work is uncommitted on another branch.
4. Fetch the latest commits:

   ```bash
   git pull --ff-only
   ```
   You should see `Already up to date.` or a short list of updated files
   ending in `Fast-forward`. If it says *fatal: Not possible to fast-forward*,
   stop and tell me.
5. Confirm you have the runbook commit or later:

   ```bash
   git log --oneline -1
   ```
   You should see one line beginning with a code such as `552d6e05` followed
   by a message like *v2: live-proof runbook …* (or a newer commit). If the
   message is about something older than the runbook, the pull in step 4 did
   not bring the work in — tell me.
6. Confirm nothing is half-edited:

   ```bash
   git status --short
   ```
   You should see **nothing at all** — an empty line and the prompt. If any
   file names are listed, do not continue; tell me what it lists.
7. Install the exact dependencies:

   ```bash
   uv sync
   ```
   You should see lines like `Resolved 210 packages` and `Audited …`, and the
   prompt returns without the word *error*. This can take a minute the first
   time.

Leave this terminal open — section 1 continues in it.

### 0.2 DigitalOcean token (CRMBuilder's account)

1. Log in at <https://cloud.digitalocean.com> as the CRMBuilder account.
2. Left sidebar → **API** (under *Manage*) → **Tokens** tab → **Generate New Token**.
3. Token name: `crmbuilder-deploy-proof`. Expiration: **30 days**.
4. Scopes: choose **Full Access** (the run needs to read the catalog, create a
   droplet, register an SSH key and read the droplet back; *Read* alone is not
   enough). → **Generate Token**.
5. The token (`dop_v1_…`) is shown **once**. Copy it into the password manager
   as `CRMBuilder DO — deploy proof`. You will paste it into the desktop in
   section 2 and never need it again.

Also confirm the account has **payment method on file** and no droplet-limit
warning (Settings → Billing); a fresh account can be capped at a low droplet
count.

### 0.3 A Cloudflare zone you can experiment on

The zone is the domain whose DNS the run will write to. It must be:

- managed by Cloudflare (nameservers already pointed at Cloudflare and the
  zone showing **Active** on the Cloudflare dashboard home), and
- **not** `crmbuilder.ai` or `crmbuilder.com` — the run refuses those as the
  production host.

Use a personal domain you already have on Cloudflare. If you have none:
Cloudflare dashboard → **Add a domain** → enter a domain you own at your
registrar → Free plan → follow the nameserver change at the registrar → wait
for *Active* (minutes to a few hours). Do this before the day of the proof.

Note the zone name exactly (e.g. `dougbower.com`); the wizard lists zones the
token can see and you will pick it from that list.

### 0.3a Adding an already-registered domain to Cloudflare

Do this only if the domain you want to use is not yet on Cloudflare. The
domain stays registered where it is; Cloudflare only takes over DNS. Nothing
on the domain changes until the final step, and even then any existing DNS
records are carried across first.

**Part 1 — add the zone in Cloudflare**

1. Sign in at <https://dash.cloudflare.com>. On the home page click
   **+ Add a domain** (top right; older layouts say *Add a site*).
2. Type the bare domain, e.g. `dougbower.com` (no `www`, no `https://`).
   Leave *Quick scan for DNS records* selected → **Continue**.
3. Choose the **Free** plan → **Continue**.
4. Cloudflare shows the DNS records it found (*Review your DNS records*).
   Check that anything the domain already does — a website (`A` or `CNAME`
   for `@` and `www`), email (`MX` records) — is listed. If a record you know
   about is missing, add it now with **+ Add record** so the switch does not
   break it. → **Continue to activation**.
5. Cloudflare now shows **two nameservers**, e.g. `ada.ns.cloudflare.com` and
   `rick.ns.cloudflare.com` (yours will differ). Keep this page open; copy
   both names exactly.

**Part 2 — point the registrar at Cloudflare**

The steps below are for Porkbun, the registrar in use for this project. Other
registrars have the same setting under *Nameservers* / *DNS management*; see
the note after the steps.

6. In a new tab sign in at <https://porkbun.com> → **Account → Domain
   Management** (or the domain list on the home page).
7. Click the domain. In its details panel find **Nameservers** (Porkbun shows
   the current ones, usually four `*.porkbun.com` entries) → click **Edit**
   (pencil icon).
8. Delete every existing nameserver line. Enter the two Cloudflare
   nameservers from step 5, one per line, exactly as shown. → **Submit**.
   Porkbun confirms *Nameservers updated*.
9. If Porkbun shows a **DNSSEC** section with records present, delete them
   (Cloudflare will re-establish DNSSEC later if you want it). Leaving old
   DNSSEC records in place makes the domain fail to resolve after the switch.

*Other registrars:* Namecheap — Domain List → **Manage** → *Nameservers* →
choose **Custom DNS** → enter the two names. GoDaddy — My Products → domain →
**DNS** → *Nameservers* → **Change** → *I'll use my own nameservers*.

**Part 3 — wait for activation**

10. Back in the Cloudflare tab click **Continue** / **Check nameservers**. The
    zone shows *Pending nameserver update*. Cloudflare re-checks
    automatically and emails you when the zone is **Active**; usually within
    an hour, occasionally up to 24. You can click *Check nameservers* again at
    any time.
11. When the dashboard home lists the domain with a green **Active** badge,
    the zone is ready for the proof. Confirm with:
    ```bash
    dig +short NS dougbower.com
    ```
    (use your domain). You should see the two Cloudflare nameservers. If the
    old registrar nameservers still appear, wait longer — nothing is wrong yet.

If the domain hosts a live website or email, check both still work after
activation; a missing record from step 4 is the only thing that could have
changed.

### 0.4 Cloudflare token A — full (Zone Read + DNS Edit)

1. Cloudflare dashboard → click the profile icon (top right) → **My Profile**
   → **API Tokens** → **Create Token**.
2. Scroll to *Custom token* → **Get started**.
3. Token name: `crmbuilder-proof-A-full`.
4. Permissions — add two rows:
   - **Zone · Zone · Read**
   - **Zone · DNS · Edit**
5. Zone Resources: **Include → Specific zone → your zone**.
6. Leave Client IP filtering and TTL blank → **Continue to summary** →
   **Create Token**.
7. Copy the token (shown once) into the password manager as
   `Cloudflare — proof A (full)`. The page offers a *test this token* curl
   command; running it returns `"status":"active"` — optional.

### 0.5 Cloudflare token B — read-only (makes run 2 fail after the server exists)

Repeat 0.4 with:

- Token name: `crmbuilder-proof-B-readonly`
- Permissions: **Zone · Zone · Read** only (do **not** add DNS Edit)
- Same specific zone.

Save it as `Cloudflare — proof B (read-only)`. With this token the run can
verify the zone (so it gets past *Checking credentials* and creates the
server) but cannot create the A record — exactly the failure run 2 needs.

### 0.6 Check the names `proof-1` and `proof-2` are free

1. Open <https://dash.cloudflare.com> and click **acmeconstruction.us** in the
   list.
2. In the left menu click **DNS**, then **Records**.
3. In the *Search DNS Records* box type `proof` and press Enter.
4. You should see **no matching records** — the names are free. If a record
   named `proof-1` or `proof-2` is listed, click its **Delete** link on the
   right and confirm.

### 0.7 Keep to hand

| | |
|---|---|
| DO token | password manager — pasted once in section 2 |
| CF token A | password manager — pasted in section 2, and again in section 4 step 3 |
| CF token B | password manager — pasted in section 4 step 1 |
| Zone name | e.g. `dougbower.com` |
| Two labels | `proof-1`, `proof-2` |
| A place to write the generated admin passwords | password manager entries `Proof 1 admin`, `Proof 2 admin` |

Nothing here touches the cloud service, the production droplet, or the CBM
instances.

---

## 1. Start the service and desktop locally

1. Generate a one-off encryption key for the proof (the local service needs
   one to store tokens; this key lives only in your shell):

   ```bash
   cd ~/Dropbox/Projects/crmbuilder
   export CRMBUILDER_V2_SECRET_KEY="$(uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
   ```
   Nothing is printed; the key is held in the variable for this terminal only
   (to confirm, `echo $CRMBUILDER_V2_SECRET_KEY` shows a 44-character string).

2. Point this shell at a local, throwaway store and allow the desktop to use
   it (these override `crmbuilder-v2/data/crmbuilder.env`, which targets the
   cloud):

   ```bash
   export CRMBUILDER_V2_API_BASE_URL="http://127.0.0.1:8765"
   export CRMBUILDER_V2_API_TOKEN=""
   export CRMBUILDER_V2_API_REMOTE=false
   export CRMBUILDER_V2_ALLOW_LOCAL=true
   export CRMBUILDER_V2_DATABASE_URL=""
   export CRMBUILDER_V2_DB_PATH="$PWD/crmbuilder-v2/data/live-proof.db"
   uv run crmbuilder-v2-bootstrap-db        # prints "Schema initialised."
   ```

3. Launch the desktop; it spawns and supervises the local API, and the API
   starts the deploy worker inside itself:

   ```bash
   ./start-v2.sh
   ```

4. In the desktop, if the engagement picker is empty, create one
   (**Engagements → New**), e.g. *Live proof*, and select it.

**Check:** the API log (`crmbuilder-v2/data/logs/api.log`) contains
`deploy worker api:<host>:<pid> started`.

---

## 2. Store the provider credentials

You do this once, in the CRMBuilder desktop window that section 1 opened.
Have the password manager open with the two tokens from 0.2 and 0.4.

1. In the desktop's left sidebar, under **Governance**, click **Instances**.
2. At the top of the Instances panel click the **Deploy new…** button. A
   window titled *Deploy a new CRM instance* opens on *Step 1 of 5 —
   Providers*. Both lines read **Not set**.
3. Click **Set credentials…**. A second window, *Provider credentials*,
   opens with two boxes: **DigitalOcean** on top, **Cloudflare** below. Each
   box has a *Token* field, a *Label* field, a **Remove** button and a
   **Save token** button.
4. In the **DigitalOcean** box:
   - click in *Token* and paste the DigitalOcean token (`dop_v1_…`);
   - click in *Label* and type `CRMBuilder DO`;
   - click **Save token**.
   The line above the fields changes to green **✓ Configured — CRMBuilder
   DO** and the *Token* field empties itself. If an error window appears
   instead, read its message and tell me.
5. In the **Cloudflare** box:
   - click in *Token* and paste Cloudflare **token A** (the full one);
   - click in *Label* and type `Zone A – full`;
   - click **Save token**.
   The line changes to green **✓ Configured — Zone A – full**.
6. Click **Close**. You are back on *Step 1 of 5 — Providers*; both lines
   now read **✓ Configured**. A moment later the wizard fetches the
   DigitalOcean catalog in the background — nothing visible happens on this
   step, but Step 2's region list will already be filled when you get there.

Leave the wizard open; section 3 continues in it.

**What you have proved:** the desktop can save a token without ever showing
it again — the fields are blank, the lines only say *Configured*, and the
token is stored encrypted by the service.

---

## 3. Run 1 — the clean path

Wizard, in order:

| Step | Enter |
|---|---|
| 2 Server | Instance name `Proof 1`; region **nyc3** (or the one nearest you); size **s-2vcpu-4gb**; image **Ubuntu 24.04 LTS**; tick your laptop's SSH key if it is listed (optional). |
| 3 Domain | Zone: **acmeconstruction.us**; subdomain `proof-1` — the address line shows `proof-1.acmeconstruction.us`; in *Let's Encrypt email* type `doug@dougbower.com` (the certificate service sends expiry notices there). |
| 4 Accounts | Username `admin`; in *Administrator email* type `doug@dougbower.com`; **Generate** a password and **write it down now** (it is never shown again); leave *Generate database passwords automatically* ticked. |
| 5 Review | Read it back; **Deploy**. |

The progress window opens on `DEP-001`. Expected timeline:

| Phase | Typical duration | What you should see |
|---|---|---|
| Checking credentials | seconds | `DigitalOcean token ok`, `Cloudflare token ok`, `Registered SSH key crmbuilder-DEP-001` |
| Creating server / Waiting for server | 1–2 min | `Created server <id>`, `Server active at <ip>` |
| Setting DNS | seconds | `DNS A record proof-1.<zone> → <ip> (DNS-only)` |
| Waiting for DNS | 0–10 min | polls every 30 s until the name resolves |
| Preparing server | 2–4 min | apt, Docker, swap, firewall output streaming |
| Installing CRM | 5–10 min | the EspoCRM installer's output; secrets appear as `[secret]` |
| Post-install checks | seconds | containers, custom-tree ownership, certificate expiry |
| Verifying | up to 1 min per check | HTTP→HTTPS, HTTPS, certificate, login page, cron, database |
| Registering instance | seconds | `Registered instance INST-001 at https://proof-1.<zone>` |

**Checks while it runs**
- Close the progress window mid-install, then **Deploy History → select DEP-001 → Open progress…** — it reattaches and the log continues.
- DigitalOcean console → Droplets: `proof-1.<zone>` tagged `crmbuilder` and `DEP-001`.
- Cloudflare → DNS: `proof-1` A record, **grey cloud** (DNS only).

**Checks when it finishes (status *succeeded*)**
1. The Instances panel selects `INST-001`; its *Deploy config* block shows Droplet id, Droplet IP, region/size, DNS provider `cloudflare`, CRM admin username, *set* for the three passwords, and `Last deploy run DEP-001`.
2. Browser: `https://proof-1.<zone>` shows the EspoCRM login with a valid certificate; log in as `admin` with the password you wrote down.
3. Instances → **Audit now** on `INST-001` completes (proves the stored admin credential works as the instance's login).
4. Deploy History → DEP-001 shows every phase `done`, all verification checks ✓, certificate expiry date populated.

If verification lands *succeeded (issues)* instead, note which check failed (it is listed) — that is a finding, not a blocker for continuing.

---

## 4. Run 2 — a failure keeps everything, Retry resumes

### 4a. In the desktop app — prove the stored login works (last check of run 1)

This check proves the admin password the run stored is usable as the
instance's login without you ever typing it.

1. In the CRMBuilder desktop window, left sidebar under **Governance**, click
   **Instances**. You should see *Proof 1* in the list. If the list is empty,
   stop and tell me exactly what the panel shows.
2. Click the row **Proof 1**. The right-hand pane shows its details with a row
   of buttons at the top: *Edit*, *Audit now*, *Publish…*, *Delete*.
3. Click **Audit now**. A window titled *Audit progress — Proof 1* opens with a
   progress bar and a running log; it finishes within about a minute with the
   status line **Audit complete.** If instead a red ✗ line appears, stop and
   tell me exactly what the log's last lines say.
4. Click **Close**.

### 4b. In the desktop app — switch Cloudflare to token B

Saving the read-only token is what makes run 2 fail after the server exists —
that failure is the point of run 2.

1. In the Instances panel (top of the list), click **Deploy new…**. The window
   *Deploy a new CRM instance* opens on *Step 1 of 5 — Providers*; both
   provider lines read **✓ Configured**.
2. Click **Set credentials…**. The *Provider credentials* window opens with a
   **DigitalOcean** box on top and a **Cloudflare** box below.
3. In the **Cloudflare** box, click in the *Token* field and paste **token B**
   (the read-only Cloudflare token, saved in the password manager as
   `Cloudflare — proof B (read-only)`).
4. In the same **Cloudflare** box, click in the *Label* field, clear it, and
   type `Zone B – read only`.
5. In the same **Cloudflare** box, click **Save token**. The line above the
   fields turns green: **✓ Configured — Zone B – read only**, and the *Token*
   field empties itself. If an error window appears, stop and tell me exactly
   what it says.
6. Click **Close** at the bottom of the *Provider credentials* window. You are
   back on *Step 1 of 5 — Providers*.

### 4c. In the deploy wizard — request Proof 2

Same request as run 1 except the name and subdomain, so the failure is
attributable to the token alone.

1. On *Step 1 of 5 — Providers*, click **Next**. You should land on *Step 2 of
   5 — Server* with the Region list already filled. If the Region list is
   empty, stop and tell me what the yellow notice line says.
2. On *Step 2 of 5 — Server*: click in *Instance name* and type `Proof 2`;
   Region **New York 3 (nyc3)**; Size **s-2vcpu-4gb**; Image **Ubuntu 24.04
   LTS**. Click **Next**.
3. On *Step 3 of 5 — Domain*: Zone **acmeconstruction.us**; click in
   *Subdomain* and type `proof-2` — the *Instance address* line shows
   `proof-2.acmeconstruction.us`; click in *Let's Encrypt email* and type
   `doug@dougbower.com`. Click **Next**.
4. On *Step 4 of 5 — Accounts*: *Administrator username* stays `admin`; click
   in *Administrator email* and type `doug@dougbower.com`; click **Generate**
   next to *Administrator password* and record the shown value in the password
   manager as `Proof 2 admin` — it is never shown again; leave *Generate
   database passwords automatically* ticked. Click **Next**.
5. On *Step 5 of 5 — Review*: the summary should read address
   `https://proof-2.acmeconstruction.us`, server `s-2vcpu-4gb in nyc3`.
   Click **Deploy**. The wizard closes and the progress window *Deploy run
   DEP-002* opens.

### 4d. In the progress window — watch it fail as designed

The run should create the server, then stop at DNS because token B cannot
write records.

1. Watch the log in the *Deploy run DEP-002* window. Within about three
   minutes you should see, in order: `Created server <a number>`,
   `Server active at <an address>`, then a red line
   `✗ create_dns: cloudflare (HTTP 403) … Authentication error [10000]`
   (verified: this is the exact error token B produced on DEP-001), and an
   orange line `Kept (not destroyed): server <number> at <address>. Retry the
   run to resume…`. The status line reads **Deployment failed — everything
   built was kept.** and a **Retry** button appears.
   If the run instead reaches *Preparing server*, stop and tell me — that
   would mean token B can edit DNS and the token is wrong.
2. Leave the *Deploy run DEP-002* window open.
3. In the web browser, open <https://cloud.digitalocean.com> → **Droplets**.
   You should see exactly one droplet named `proof-2.acmeconstruction.us`.
   If you see two, stop and tell me.
4. In the web browser, open <https://dash.cloudflare.com> →
   **acmeconstruction.us** → **DNS** → **Records**, type `proof-2` in the
   *Search DNS Records* box and press Enter. You should see **no matching
   records**. If a `proof-2` record exists, stop and tell me.

### 4e. In the desktop app — fix the token and Retry

Retry must resume at the failed step without creating a second server.

1. In the Instances panel, click **Deploy new…**, then **Set credentials…**.
2. In the **Cloudflare** box, click in the *Token* field and paste **token A**
   (the full Cloudflare token, saved as `Cloudflare — proof A (full)`).
3. In the same box, click in the *Label* field, clear it, and type
   `Zone A – full`; click **Save token**. The line turns green:
   **✓ Configured — Zone A – full**.
4. Click **Close**, then click **Cancel** at the bottom of the deploy wizard —
   do not start a new run.
5. In the *Deploy run DEP-002* window, click **Retry**. The log should show
   `Resuming deploy run DEP-002`, then `↷ create_droplet: already complete,
   skipping`, then `DNS A record proof-2.acmeconstruction.us → <address>
   (DNS-only)`, then `resolves to <address> on public resolvers` within about
   a minute, and continue through *Preparing server* and *Installing CRM* to
   **Deployment complete.** with `Registered instance INST-002`. Total: about
   10–15 minutes. If any red ✗ line appears, stop and paste the last 20 log
   lines.
6. In the web browser, reload the DigitalOcean **Droplets** page. You should
   still see exactly **one** droplet named `proof-2.acmeconstruction.us`.
7. In the web browser, open `https://proof-2.acmeconstruction.us`. You should
   see the EspoCRM login page with no certificate warning.

Then tell me the outcome of 4d step 1, 4e step 5, 4e step 6 and 4e step 7, and
we move to section 5 (optional restart check) or straight to section 6
(clean-up).

---

## 5. Run 3 — a restarted service resumes an interrupted install

### 5a. In the deploy wizard — request Proof 3

A third throwaway server, so the interruption cannot disturb the two proven
runs.

1. In the CRMBuilder desktop window, left sidebar under **Governance**, click
   **Instances**, then click **Deploy new…** at the top of the panel. The
   window *Deploy a new CRM instance* opens on *Step 1 of 5 — Providers*;
   both lines read **✓ Configured**. Click **Next**.
2. On *Step 2 of 5 — Server*: click in *Instance name* and type `Proof 3`;
   Region **New York 3 (nyc3)**; Size **s-2vcpu-4gb**; Image **Ubuntu 24.04
   LTS**; leave every box in *Extra SSH keys* unticked. Click **Next**.
3. On *Step 3 of 5 — Domain*: Zone **acmeconstruction.us**; click in
   *Subdomain* and type `proof-3` — the *Instance address* line shows
   `proof-3.acmeconstruction.us`; click in *Let's Encrypt email* and type
   `doug@dougbower.com`. Click **Next**.
4. On *Step 4 of 5 — Accounts*: *Administrator username* stays `admin`; click
   in *Administrator email* and type `doug@dougbower.com`; click **Generate**
   next to *Administrator password* and record the shown value in the
   password manager as `Proof 3 admin`; leave *Generate database passwords
   automatically* ticked. Click **Next**.
5. On *Step 5 of 5 — Review*: the summary should read address
   `https://proof-3.acmeconstruction.us`. Click **Deploy**. The progress
   window *Deploy run DEP-003* opens.

### 5b. In the progress window — interrupt during the install

The interruption must land while the installer is streaming, after the server
and DNS exist — that is the exact moment the plan flagged as untested.

1. Watch the *Deploy run DEP-003* log through *Creating server*, *Setting
   DNS* and *Preparing server* (about 6–8 minutes; the resolver line
   `proof-3.acmeconstruction.us resolves to <an address> on public resolvers`
   should appear within a minute of *Waiting for DNS*). Do nothing yet.
2. When the status line reads **Running — Installing CRM** and installer
   output is streaming (lines mentioning `install.sh`, image pulls, or
   certificates), close the CRMBuilder desktop window. The window and the
   progress window disappear; the local service dies with them, mid-install.
   If the status has already reached *Post-install checks*, too late — tell
   me and we simply let the run finish instead.

### 5c. In the terminal — wait, then relaunch

The service must be down long enough for its claim on the run to go stale
(three minutes).

1. In the terminal whose prompt ends in `crmbuilder-proof`, wait about 30
   seconds after the window closes, then type the line below and press Enter:
   ```bash
   ./start-v2.sh
   ```
   You should see `Launching v2 desktop UI (it will spawn and supervise the
   API)...` and one desktop window open. If a Python error appears, stop and
   paste it.

### 5d. In the desktop app — watch the run be reclaimed and resume

Within about three minutes of the relaunch, the new service notices the
abandoned run and takes it over.

1. In the left sidebar under **Governance**, click **Deploy History**. You
   should see *DEP-003* with status **▶ running**, phase *Installing CRM* —
   the run is still marked running even though nothing is executing yet; that
   is the stale claim.
2. Click the row **DEP-003**, then click **Open progress…** at the top of the
   right-hand pane. The progress window opens showing the old log.
3. Wait up to four minutes without clicking anything. A new log line
   `Resuming deploy run DEP-003` should appear, then `↷ create_droplet:
   already complete, skipping`, then the installer re-runs on the same
   server. If nothing new appears after five minutes, stop and tell me.
4. Watch to the end: **Deployment complete.** (or **Deployment complete with
   verification gaps** — either is a pass for this test) with `Registered
   instance INST-003`, roughly 10–15 minutes from the resume. If a red ✗
   appears during *Installing CRM*, paste the last 30 log lines — that is
   precisely the finding this run exists to capture (the installer refusing
   to re-run on a half-installed server).

### 5e. In the web browser — confirm the result

1. Open `https://proof-3.acmeconstruction.us`. You should see the EspoCRM
   login page with no certificate warning.
2. Open <https://cloud.digitalocean.com> → **Droplets**. You should see
   exactly three droplets, one per proof name — none duplicated.

Then report the outcome of 5d step 3, 5d step 4, 5e step 1 and 5e step 2, and
we move to section 6 (clean-up of all three servers).

---

## 6. Clean up

In this order, so nothing is left billing:

1. DigitalOcean → Droplets: destroy the `proof-1`, `proof-2` and `proof-3` droplets.
2. DigitalOcean → Settings → Security: delete SSH keys `crmbuilder-DEP-001`, `crmbuilder-DEP-002` (and `-003` if you ran step 5 separately).
3. Cloudflare → DNS: delete the `proof-1` and `proof-2` A records.
4. Revoke Cloudflare token B (and A, if it was created only for this).
5. Quit the desktop; delete the throwaway store:
   `rm crmbuilder-v2/data/live-proof.db*`. The exported variables die with the shell.

---

## 7. Report back

Send the outcome of each numbered check above as pass / fail, plus:

- run durations (from Deploy History's Started/Finished),
- the verification list for each run,
- anything the installer printed on the resume path (step 5),
- any log line that looked wrong or leaked something it should not have.

With that in hand PI-419 is resolved and a decision records the proof; the
production rollout (`scripts/deploy-production.sh`, your step) follows.

---

## If something goes wrong

| Symptom | Meaning / action |
|---|---|
| Wizard Step 1 says *Not set* after saving | The save failed — an error dialog will have said why. Most likely the local service has no `CRMBUILDER_V2_SECRET_KEY`; re-export it and relaunch. |
| *no digitalocean credential configured* on Deploy | Credentials are per engagement — you saved them under a different engagement than the one selected. |
| Progress stays *Queued* | No worker. Check `api.log` for `deploy worker … started`; the desktop must have been launched from the shell with `CRMBUILDER_V2_DEPLOY_WORKER_INPROCESS` unset (default on). |
| Fails at *Checking credentials* with a Cloudflare error | Token A lacks Zone Read, or the zone chosen in the wizard is not the one the token covers. |
| *Waiting for DNS* runs the full 10 minutes and fails | The record exists but your resolver has not caught up; **Retry** — nothing is recreated. |
| Fails at *Installing CRM* | Read the installer's last lines in the log; retry re-runs the installer on the same server. |
| A run refuses `…crmbuilder.ai` | Intended: the production host is protected (DEC-946). Use your own zone. |
