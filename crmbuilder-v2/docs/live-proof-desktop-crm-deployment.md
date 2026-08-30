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

### 0.6 Check two names are free, and decide one email address

**Part 1 — check the names `proof-1` and `proof-2` are not already in use**

1. Open <https://dash.cloudflare.com> and click **acmeconstruction.us** in the
   list.
2. In the left menu click **DNS**, then **Records**.
3. In the *Search DNS Records* box type `proof` and press Enter.
4. You should see **no matching records**. That means the names are free —
   move on to Part 2. If a record named `proof-1` or `proof-2` is listed,
   click its **Delete** link on the right, confirm, and it is free.

**Part 2 — decide the email address**

Later, the deploy wizard has two boxes that ask for an email address. Decide
now what you will type; nothing is set up, sent, or encrypted at this stage.

- Box labelled **Let's Encrypt email** → type `doug@dougbower.com`.
  *(Let's Encrypt is the name of the free service that issues the website's
  HTTPS certificate; it emails this address before the certificate expires.)*
- Box labelled **Administrator email** → type `doug@dougbower.com` again.
  *(This becomes the email on the admin user inside the new CRM.)*

That is all for 0.6.

### 0.7 Keep to hand

| | |
|---|---|
| DO token | password manager — pasted once in section 2 |
| CF token A | password manager — pasted in section 2, and again in section 4 step 3 |
| CF token B | password manager — pasted in section 4 step 1 |
| Zone name | e.g. `dougbower.com` |
| Two labels | `proof-1`, `proof-2` |
| One email address | `doug@dougbower.com` — typed into both email boxes of the wizard |
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

1. Sidebar **Instances → Deploy new…**. Step 1 shows both providers as *Not set*.
2. **Set credentials…** — paste the DigitalOcean token (label `CRMBuilder DO`)
   → **Save token**; paste Cloudflare **token A** (label `Zone A – full`) →
   **Save token**. Both rows turn green *✓ Configured*. **Close**.
3. Back in the wizard, both providers now read *✓ Configured* and the server
   catalog loads (Step 2's region list fills in).

**Check:** the token fields are empty again and nothing on screen shows the
token — only "configured".

---

## 3. Run 1 — the clean path

Wizard, in order:

| Step | Enter |
|---|---|
| 2 Server | Instance name `Proof 1`; region **nyc3** (or the one nearest you); size **s-2vcpu-4gb**; image **Ubuntu 24.04 LTS**; tick your laptop's SSH key if it is listed (optional). |
| 3 Domain | Zone: your zone; subdomain `proof-1` — the address line shows `proof-1.<zone>`; Let's Encrypt email. |
| 4 Accounts | Username `admin`; administrator email; **Generate** a password and **write it down now** (it is never shown again); leave *Generate database passwords automatically* ticked. |
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

## 4. Run 2 — failure keeps everything, retry resumes

1. **Instances → Deploy new… → Set credentials…**: replace the Cloudflare
   token with **token B** (read-only), label `Zone B – read only`. **Close**.
2. Wizard as in run 1 but instance name `Proof 2`, subdomain `proof-2`.
   **Deploy** → `DEP-002`.

Expected: credentials check passes (the zone is readable), the server is
created and becomes active, then **Setting DNS fails** with a Cloudflare
authentication/permission error. Status: **failed**. The log ends with
`Kept (not destroyed): server <id> at <ip>. Retry the run to resume…` and the
progress window shows **Retry**.

**Checks**
- Deploy History → DEP-002 is orange: *Still exists (not destroyed): server <id> at <ip>* with **Copy server id**; phases show `create_droplet done`, `create_dns failed`.
- DigitalOcean console: the `proof-2` droplet exists (one, not two).
- Cloudflare: **no** `proof-2` record.

3. Fix the cause: **Set credentials…** → Cloudflare back to **token A**.
4. In the progress window (or Deploy History), **Retry**.

Expected: log says `Resuming deploy run DEP-002`, `create_droplet: already
complete, skipping`, then DNS is set and the run continues to *succeeded*,
registering `INST-002`.

**Checks**
- DigitalOcean still shows exactly **one** `proof-2` droplet, and one SSH key `crmbuilder-DEP-002`.
- `https://proof-2.<zone>` serves the CRM login.

---

## 5. Optional — a restarted service resumes a run

Do this during run 2's retry (or a third run) while **Installing CRM** is
streaming:

1. Quit the desktop (it takes the local API and its worker down with it).
2. Wait ~30 s, relaunch `./start-v2.sh` in the same shell (same exported variables).
3. Deploy History → the run shows *running* with the old phase; within about
   three minutes (the stale-heartbeat threshold) the log gains
   `Resuming deploy run …` and the run continues from *Installing CRM*.

Expected: the run finishes *succeeded* or *succeeded (issues)* — the installer
is re-run on the same server, which it tolerates. If it does **not** tolerate
it (install fails on resume), record exactly what the installer printed; that
is the one open risk named in the plan.

---

## 6. Clean up

In this order, so nothing is left billing:

1. DigitalOcean → Droplets: destroy `proof-1.<zone>` and `proof-2.<zone>`.
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
