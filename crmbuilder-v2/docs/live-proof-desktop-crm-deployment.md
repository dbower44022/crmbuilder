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

| Item | Detail |
|---|---|
| Repository | `main` at or after `959a7f20`, clean tree, `uv sync` done. |
| DigitalOcean token | On **CRMBuilder's** account, *Personal access token*, scopes: **read + write** (full). You will paste it once into the desktop; note it in the password manager under `CRMBuilder DO — deploy proof`. |
| Cloudflare zone | A zone **you own and can experiment on** — not `crmbuilder.ai` / `crmbuilder.com` (the run refuses those, by design). A personal domain is ideal. |
| Cloudflare token **A** (full) | *Create Custom Token* → permissions **Zone · Zone · Read** and **Zone · DNS · Edit**, zone resources: *Include → Specific zone → your zone*. |
| Cloudflare token **B** (read-only) | Same, but **Zone · Zone · Read only** (no DNS Edit). This is what forces run 2 to fail *after* the server exists. |
| Names | `proof-1.<your-zone>` for run 1, `proof-2.<your-zone>` for run 2. Neither may exist as a DNS record yet. |
| Emails | A Let's Encrypt contact address and a CRM administrator address (can be the same). |

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
