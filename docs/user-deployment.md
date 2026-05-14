# CRM Builder — EspoCRM Server Deployment Guide

**Version:** 1.3
**Status:** Current
**Last Updated:** 05-13-26

---

## What This Feature Does

The Deploy feature provisions a fresh EspoCRM instance on a DigitalOcean
Droplet directly from CRM Builder. It automates server preparation,
EspoCRM installation, SSL certificate setup, and verification — all
over SSH.

After deployment, CRM Builder can immediately connect to the new instance
and begin deploying fields, layouts, and relationships from YAML files.

---

## Prerequisites

Complete these steps **before** opening the Setup Wizard:

### 1. DigitalOcean Droplet

Provision a Droplet with:

| Setting | Production | Test / Staging |
|---------|-----------|----------------|
| Image | Ubuntu 22.04 LTS x64 | Ubuntu 22.04 LTS x64 |
| Size | 2 vCPU / 4 GB RAM / 80 GB SSD (~$24/mo) | 1 vCPU / 2 GB RAM / 50 GB SSD (~$12/mo) |
| Authentication | SSH Key | SSH Key |

Do not select a one-click app — the Droplet must be a clean Ubuntu image.

Note the Droplet's public IPv4 address.

### 2. SSH Key

You need an SSH key pair. If you don't have one:

```bash
ssh-keygen -t ed25519 -C "crm-deploy"
```

Add the public key to the Droplet (easiest during Droplet creation in
the DigitalOcean control panel).

Verify you can connect:
```bash
ssh -i ~/.ssh/id_ed25519 root@<droplet-ip>
```

### 3. Domain Name and DNS

A domain name is required (bare IP is not supported). Create a DNS A
record pointing your subdomain to the Droplet IP:

| Field | Value |
|-------|-------|
| Type | `A` |
| Name | `crm` (production) or `crm-test` (staging) |
| Value | Droplet IPv4 address |
| TTL | `300` (5 minutes) |

The deployment tool validates DNS propagation automatically and will
wait up to 10 minutes for propagation before proceeding.

---

## Setup Wizard

Click **Set Up Deployment** in the Deploy panel (visible when an instance
is selected that doesn't yet have deployment configured).

The wizard has seven steps:

### Step 1 — Server Connection

- **Droplet IP** — the IPv4 address from DigitalOcean
- **SSH Key File** — path to your private key (Browse to select)
- **SSH Username** — `root` (default for fresh Droplets)

### Step 2 — Domain

- **Base Domain** — e.g., `mycompany.com`
- **Subdomain** — `crm` (production) or `crm-test` (staging)
- The full domain preview updates live as you type

### Step 3 — Database

- **EspoCRM DB Password** — password for the EspoCRM database
- **MariaDB Root Password** — leave blank to auto-generate a secure password

### Step 4 — EspoCRM Admin

- **Admin Username** — the login you'll use for EspoCRM (default: `admin`)
- **Admin Password** — choose a strong password
- **Admin Email** — for admin account notifications

### Step 5 — SSL / Let's Encrypt

- **Let's Encrypt Email** — used for certificate expiry notifications

### Step 6 — Documentation Inputs

These values feed the Deployment Record document that is produced
automatically when the deploy completes (see "After Deployment —
Deployment Record" below). They are not used by the application
itself; they document where each item is stored or who manages it.

- **Domain Registrar** — the company where the domain is registered
  (e.g., `Porkbun`)
- **DNS Provider** — where DNS records are managed; often the same
  as the registrar
- **Droplet ID** — the numeric ID from the DigitalOcean dashboard
  URL (`cloud.digitalocean.com/droplets/{ID}`); used to populate
  direct links to the Droplet detail page and in-browser Console
- **Backups Enabled** — check if DigitalOcean weekly backups are
  enabled for this Droplet
- **Admin Password — Password Manager Entry** — the exact name of
  the password manager entry where the admin password is stored
  (e.g., `CBM-ESPOCRM-Test Instance Admin`)
- **DB Root Password — Password Manager Entry** — same convention
  for the MariaDB root password entry
- **Hosting Account — Password Manager Entry** — same convention
  for the DigitalOcean account login

The seven Documentation Inputs are persisted with the deploy
configuration so they pre-fill on subsequent regenerations.

### Step 7 — Review & Confirm

Review all values. Passwords are masked by default — click **Show Passwords**
to verify. Click **Save & Deploy** to save the configuration and begin
deployment.

---

## Deployment Phases

After saving the configuration, deployment runs automatically through
four phases:

### Phase 1 — Server Preparation

Updates the system, installs Docker Engine, configures a 2 GB swap file,
and opens firewall ports (22, 80, 443).

### Phase 2 — EspoCRM Installation

Downloads and runs the official EspoCRM installer script. This installs
EspoCRM, MariaDB, and Nginx as Docker containers, issues the Let's
Encrypt SSL certificate, and configures cron for certificate renewal.

DNS is re-validated before this phase to ensure the domain resolves
correctly (required for Let's Encrypt).

### Phase 3 — Post-Install Configuration

Verifies all containers are running, confirms the cron job exists, and
reads the SSL certificate expiry date. After this phase, CRM Builder
updates the instance URL to `https://{your-domain}`.

### Phase 4 — Verification

Runs seven checks:

| Check | What It Verifies |
|-------|-----------------|
| Docker containers | All EspoCRM containers are running |
| HTTP redirect | Port 80 redirects to HTTPS |
| HTTPS response | Port 443 returns HTTP 200 |
| SSL certificate | Certificate is valid |
| EspoCRM login page | The login page loads correctly |
| Cron job | Certificate renewal is scheduled |
| Database connectivity | MariaDB container is healthy |

---

## After Deployment — Logging In

Once all four phases complete successfully, your EspoCRM instance is live.

**URL:** `https://{subdomain}.{base-domain}`
(e.g., `https://crm.mycompany.com` or `https://crm-test.mycompany.com`)

**Login credentials:** The Admin Username and Admin Password you entered
in Step 4 of the Setup Wizard (default username: `admin`).

Open the URL in a browser — you should see the EspoCRM login page. After
logging in, you can begin configuring the instance by deploying YAML
program files from CRM Builder (Validate → Run → Verify).

CRM Builder automatically updates the instance profile URL after a
successful deployment, so the Validate / Run / Verify buttons connect
to the new instance immediately.

---

## After Deployment — Deployment Record

When the deploy completes successfully, CRM Builder automatically
generates a per-instance Deployment Record `.docx` capturing the
as-deployed state. The file lands at:

```
{project_folder}/PRDs/deployment/{INSTANCE_CODE}-Instance-Deployment-Record.docx
```

The Deployment Record contains:

- Droplet identification (region, public IPv4, hostname, Droplet ID,
  direct links to the DigitalOcean detail page and in-browser Console)
- Hardware and OS (CPU, memory, disk, kernel, Ubuntu release)
- Firewall configuration and backups status
- Domain and DNS (registrar, DNS provider, A-record details)
- TLS certificate (issuer, dates, fingerprint, renewal arrangement)
- EspoCRM application version and the five-container Docker stack
  with each container's image and version
- SSH access (authorized user, key algorithm, key fingerprint)
- Credentials inventory — references to the password manager entries
  for the admin password, the MariaDB root password, and the hosting
  account login. **No credential values appear in the document.**
- Deployment history timeline

The Result page at the end of the Setup Wizard includes a
**Reveal in File Manager** button that opens the containing folder,
so you can confirm the file was produced.

### Regenerating the Deployment Record

The Deployment Record can be regenerated on demand from the
Deployment tab. Click **Generate Deployment Record** in the Deploy
panel. Use this when:

- An EspoCRM upgrade has changed the application version
- A configuration change has made the existing Record's values stale
  (a password-manager entry rename, a backups status change, etc.)
- The application's generator has gained content that wasn't present
  when the Record was last produced

The regeneration dialog pre-fills all Documentation Inputs from the
persisted deploy configuration. The Proton Pass entry name fields
also persist across regenerations after the first one. The default
output mode overwrites the canonical filename; choose
**Write versioned copy with timestamp suffix** to retain a snapshot
without losing the canonical file.

The document version increments automatically (`1.0` → `1.1` → `1.2`)
on each regeneration that overwrites the canonical file. Versioned
copies do not increment the canonical version.

### Pre-Automation Instances

Instances added to CRM Builder before the Deployment Record feature
shipped (or instances created via the manual **Add Instance** flow
without a deploy run) have no `InstanceDeployConfig` row. The first
time you click **Generate Deployment Record** for such an instance,
the Server Connection backfill dialog opens. Enter the SSH host,
port, username, key path, domain, Let's Encrypt email, MariaDB root
password, and admin email, then click **Save**. After the backfill
completes, the regeneration dialog opens and the rest of the flow
proceeds normally.

The same backfill flow is invoked by the **Upgrade EspoCRM** and
**Recovery & Reset** actions when an instance lacks a deploy
configuration. Performing any of the three triggers the backfill
once; subsequent uses of any of them go straight to the requested
action.

### Committing the Record to Your Client Repository

The application writes the `.docx` but does not commit it to git.
You decide when a regeneration represents a change worth committing.
Typical commit triggers:

- Initial Record produced for a new instance
- Regeneration after an EspoCRM version upgrade
- Regeneration after a configuration change that materially affects
  the recorded values

```bash
cd ~/path/to/your/client-repo
git add PRDs/deployment/{INSTANCE_CODE}-Instance-Deployment-Record.docx
git commit -m "Regenerate Deployment Record for <reason>"
git push
```

---

## After Deployment — Connecting CRM Builder to the New Instance

Before you can deploy YAML program files (Validate → Run → Verify),
you must configure authentication in your CRM Builder instance profile.
The field management and entity management API endpoints require
**admin-level access** — without it you will get HTTP 403 Forbidden on
every operation.

### Use Basic Auth with the Admin Account

CRM Builder uses EspoCRM's Administration API endpoints to manage fields,
entities, layouts, and relationships. These endpoints require a **real
admin user** — they cannot be accessed by API Users, regardless of what
role is assigned. EspoCRM roles control access to entity *data* (records),
not to the Administration configuration API.

**This means Basic authentication with the admin account is the correct
and recommended approach for CRM Builder.**

1. In CRM Builder, select the instance and click **Edit**
2. Set:
   - **Auth Method:** Basic (Username/Password)
   - **Username:** the admin username from Step 4 of the wizard
     (default: `admin`)
   - **Password:** the admin password from Step 4 of the wizard
3. Click **Save**

You can now Validate and Run YAML program files immediately.

> **Why not API Key?** EspoCRM API Users (the kind that get API Keys)
> are designed for integrations that read and write *records* — contacts,
> accounts, leads, etc. They cannot access the `Admin/fieldManager`,
> `EntityManager`, or `Admin/layouts` endpoints that CRM Builder needs
> for configuration deployment. Assigning a role to an API User grants
> data access, not administration access. If you try to use an API Key,
> you will get HTTP 403 on all field and entity operations.
>
> Basic auth with the admin account is secure when used over HTTPS
> (which is always the case after deployment — Let's Encrypt is
> mandatory). The credentials are sent in the `Authorization` header,
> encrypted in transit.

### Verify the Connection

After configuring authentication:

1. Select a YAML program file
2. Click **Validate**
3. You should see `[VALIDATE] OK` followed by a preview of planned
   changes

If you see `[VALIDATE] FAILED` or `HTTP 403`, double-check:
- The URL matches `https://{your-domain}` (no trailing slash)
- The admin password is correct
- You selected **Basic (Username/Password)** as the auth method, not
  API Key

---

## Deployment Dashboard

After the first deployment, the Deploy panel shows the dashboard:

**Environment Header**
- Instance name and full domain
- Droplet IP
- SSL certificate status badge:
  - Green: valid (more than 30 days remaining)
  - Yellow: expiring soon (14–30 days)
  - Red: critical — renew now (less than 14 days)
- EspoCRM version badge:
  - Green: "EspoCRM X.Y.Z — up to date"
  - Orange: "EspoCRM X.Y.Z → A.B.C available" when an upgrade is available
  - Grey: "EspoCRM version: unknown" before the first version check

**Phase Status Cards**
Each phase shows its status: Not Started, Running, Completed, or Failed.
Failed phases show error detail.

**Action Buttons**
- **Deploy All** — runs all four phases from the beginning
- **Run Verification Only** — runs Phase 4 checks without redeploying
- **Retry Failed Phase** — restarts from the phase that failed
- **Upgrade EspoCRM** — opens the upgrade modal (see *Upgrading EspoCRM* below)
- **Recovery & Reset** — admin credential reset and full database reset

**Log Window**
Streams live output from all phases. Copy to clipboard or save to file
with the buttons above the log.

---

## DNS Propagation

CRM Builder validates that your domain resolves to the correct IP address
before Phase 1 and again before Phase 2 (which needs DNS for SSL).

If DNS hasn't propagated yet, the tool retries every 30 seconds for up
to 10 minutes. You'll see messages like:

```
DNS not ready: crm.mycompany.com resolves to 0.0.0.0 but expected 165.232.150.42.
Retrying in 30s (570s remaining)...
```

If DNS doesn't resolve within 10 minutes, deployment aborts. Check your
DNS provider and try again.

---

## SSL Certificates

SSL is automatically provisioned via Let's Encrypt during Phase 2.

The certificate auto-renews via cron. CRM Builder additionally checks
the certificate expiry date each time you select the instance, and shows
a warning if renewal may have silently failed.

You do not need to manage certificates manually.

---

## Upgrading EspoCRM

CRM Builder can upgrade an already-deployed EspoCRM instance to the
latest stable release. Each time you select a deployed instance, CRM
Builder checks the EspoCRM release feed and the running container in
the background; the version badge in the Deploy panel header tells
you whether an upgrade is available.

Click **Upgrade EspoCRM** in the Deploy panel to open the upgrade
modal.

### What the Upgrade Does

The upgrade flow runs four phases:

1. **Pre-upgrade Checks** — confirms the EspoCRM container is running,
   reads the current version, and verifies at least 2 GB of free disk
   space on the server.
2. **Backup** — runs `mariadb-dump` of the EspoCRM database and a tar
   archive of the data volume to `/var/backups/espocrm/{timestamp}/`
   on the server. Only the **last 3 backups** are kept; older backups
   are deleted automatically to bound disk use.
3. **Run Upgrade** — runs the official EspoCRM CLI upgrader inside the
   running container (`php command.php upgrade -y`) and clears the
   application cache. EspoCRM's own upgrader handles database schema
   migrations, file replacement, and custom-code preservation.
4. **Verification** — confirms the containers are up, the site responds
   over HTTPS, the login page renders, and the new version reads back
   from inside the container.

### Major-Version Upgrades

If the available upgrade crosses a major version boundary (for example,
7.5.12 → 8.0.0), CRM Builder shows a confirmation dialog warning that
major upgrades may introduce breaking changes and recommending you
review the EspoCRM release notes first. Click **Yes** to proceed or
**Cancel** to back out.

Minor and patch upgrades (e.g. 8.4.0 → 8.5.1) proceed without an
extra confirmation.

### After the Upgrade

The dashboard's version badge refreshes to show the new current
version, and the upgrade timestamp is saved in the deploy config.

The upgrade flow does **not** re-apply your YAML programs. If a new
EspoCRM release changes how a field or layout is configured, run
**Validate** and **Run** in CRM Builder against your existing program
files to bring the configuration back into line.

After the upgrade, regenerate the per-instance Deployment Record so
the recorded EspoCRM version reflects reality. Click
**Generate Deployment Record** on the Deployment tab; the document
version will increment automatically (e.g., `1.0` → `1.1`). Commit
the regenerated `.docx` to your client repository alongside the
upgrade notes.

### Rolling Back

If the upgrade verification fails or the application doesn't behave
correctly, the most recent backups remain on the server in
`/var/backups/espocrm/`. Each contains:
- `db.sql.gz` — gzipped MariaDB dump
- `data.tar.gz` — tar archive of the EspoCRM data volume

Restoring is a manual SSH operation — CRM Builder does not yet provide
a one-click restore. The high-level steps:

```bash
# Stop containers
cd /var/www/espocrm && docker compose down

# Restore data volume
tar -xzf /var/backups/espocrm/<timestamp>/data.tar.gz -C /var/www/espocrm

# Restore database
docker compose up -d espocrm-db
gunzip < /var/backups/espocrm/<timestamp>/db.sql.gz \
  | docker compose exec -T -e MYSQL_PWD=<root-password> espocrm-db \
    mariadb -u root espocrm

# Bring everything back up
docker compose up -d
```

---

## Installing Extensions

CRM Builder installs (and re-installs) EspoCRM extension packs against
an already-deployed instance over SSH. The flow uploads the extension
zip to the server, copies it into the EspoCRM container, runs the
official EspoCRM CLI extension command (`php command.php
extension --file=…`), and records the install in the per-client
database. License caps for paid extensions are enforced before the
install runs.

The same four-phase pattern Upgrade uses applies here — pre-check,
backup, install, verify — so a failed install leaves you with a
recent backup to roll back to.

This section is a complete walkthrough: where to find the panel,
which fields to fill, what every screen looks like, what to expect
in the log, and three worked examples (first paid install, version
replacement, free extension).

### Where the Extensions Panel Lives

On the Deployment tab, the sidebar entries are:

```
┌────────────────┐
│ Instances      │
│ Deploy         │
│ Configure      │
│ Extensions     │  ←  here
│ Run History    │
│ Audit          │
│ Output         │
└────────────────┘
```

Selecting **Extensions** shows a two-tab panel:

```
┌─────────────────────────────────────────────────────────┐
│ Target instance                                          │
│   CBM Production (CBM-PROD) — production                 │
├─────────────────────────────────────────────────────────┤
│ ┌──────────┬───────────┐                                 │
│ │ Install  │ Licenses  │                                 │
│ └──────────┴───────────┘                                 │
│                                                          │
│ Currently installed extensions                           │
│ ┌────────────────────┬─────────┬───────────┬──────────┐  │
│ │ Extension          │ Version │ License   │ Installed│  │
│ ├────────────────────┼─────────┼───────────┼──────────┤  │
│ │ (empty)                                              │  │
│ └────────────────────┴─────────┴───────────┴──────────┘  │
│                                                          │
│ [ Install Extension… ]                                   │
└─────────────────────────────────────────────────────────┘
```

If the panel says *"No CRM instances available"* or *"Select an
instance from the picker above"*, fix that first — extensions need
both a client and a self-hosted instance to act on.

### Prerequisites

Confirm all four before starting:

| Item | Detail |
|------|--------|
| Extension `.zip` file | Both free and paid extensions ship as zips with `manifest.json` at the archive root. Keep them in a folder you remember — for client projects, `~/Projects/<Client>/ExtensionFiles/` is a good convention. |
| License key | Only for paid extensions (e.g. EspoCRM Advanced Pack). Free extensions like Google Integration have no key. Have it pasted into a temporary text buffer ready to copy. |
| Deployed self-hosted instance | The target instance must already be deployed and reachable. Cloud-hosted instances cannot be SSHed into. |
| Working SSH credentials | The Deploy wizard wrote them; if you've rotated the SSH key since then, edit them in the connection dialog first. |

### Step 1 — Register a License (Paid Extensions Only)

Skip this step for free extensions; the Install dialog will simply say
*"No license registered for this extension. Install will proceed
unlicensed."* and proceed.

For paid extensions, register the license **before** the first
install. The slot check that gates installation reads from this row.

1. On the Deployment tab, select **Extensions** in the sidebar.
2. Select the **Licenses** tab.
3. Click **Add License…**. A modal opens:

   ```
   ┌──────────────────────────────────────────────────────┐
   │ Add License                                          │
   ├──────────────────────────────────────────────────────┤
   │ Extension name:        [                          ]  │
   │ Purchaser label:       [                          ]  │
   │ License key:           [••••••••••••••••••••••]      │
   │                        [ Show ]                       │
   │ Max production slots:  [ 1 ▼]                         │
   │ Max non-production:    [ 2 ▼]                         │
   │ Notes:                                                │
   │ [                                                  ]  │
   │ [                                                  ]  │
   │                                                       │
   │                              [ Save ]  [ Cancel ]     │
   └──────────────────────────────────────────────────────┘
   ```

4. Fill the fields:

   | Field | What to enter | Example |
   |-------|---------------|---------|
   | Extension name | The exact value from the extension's `manifest.json` `name` field, case-sensitive. The Install dialog matches on this string later — typos will leave the dialog showing *"No license registered."* | `Advanced Pack` |
   | Purchaser label | Optional. Free-form label to disambiguate multiple licenses for the same extension (rare but possible if an org buys per-client licenses). | `CBM core license` |
   | License key | The vendor's key string. Click **Show** if you want to verify you pasted it correctly; click **Hide** before saving. Stored in your OS keyring, never in the database. | `ABCD-EFGH-IJKL-MNOP` |
   | Max production slots | Vendor cap. EspoCRM Advanced Pack allows 1 production install per license; default value of `1` is correct. | `1` |
   | Max non-production slots | Vendor cap for staging + test combined. EspoCRM Advanced Pack allows 2 non-production installs; default value of `2` is correct. | `2` |
   | Notes | Optional. Renewal date, vendor support email, purchase order number. | `Renewed 2026-04, support@espocrm.com` |

5. Click **Save**. The row appears in the Licenses table with live
   slot counts (`0/1` and `0/2` for a fresh license).

**Editing a license later.** Double-click the row, or select it and
click **Edit Selected…**. The Extension name field becomes
non-editable once saved (it's the join key for everything). All other
fields can be changed. Confirming a key rotation writes the new value
to the OS keyring and deletes the old keyring entry; existing
install rows keep referencing the same license row, so the next CRM
license check on the server side picks up the new key automatically.

### Step 2 — Verify the Target Instance

Back on the **Extensions** entry, look at the instance picker at the
top of the Deployment tab. Confirm:

- The right instance is selected (the panel header echoes it).
- Its environment is what you intended (`production`, `staging`, or
  `test`). The slot pool the install consumes is decided by this value
  — you can't change it later for an already-deployed instance.

If you need to switch instances, do it now via the picker — the
Extensions panel refreshes immediately.

### Step 3 — Launch the Install Dialog

1. Switch to the **Install** tab (it's the default).
2. Click **Install Extension…**. A file picker opens.
3. Navigate to your extension zip and click **Open**.
   - The picker filters for `*.zip`. Both free and paid extensions are
     valid here.
4. The Install dialog opens. It looks roughly like:

   ```
   ┌──────────────────────────────────────────────────────────┐
   │ Install Extension — CBM Production                        │
   ├──────────────────────────────────────────────────────────┤
   │ Extension                                                 │
   │   Advanced Pack v3.12.1 — by EspoCRM, Inc.                │
   │   /home/doug/Projects/CBM/ExtensionFiles/                 │
   │     advanced-pack-3.12.1.zip                              │
   │                                                           │
   │ License + slot usage                                      │
   │   License: Advanced Pack                                  │
   │   Production: 0/1                                         │
   │   Non-production: 0/2                                     │
   │   This install will consume one new slot.                 │
   │                                                           │
   │ ● Phase 1: Pre-check          Not Started                 │
   │ ● Phase 2: Backup             Not Started                 │
   │ ● Phase 3: Install            Not Started                 │
   │ ● Phase 4: Verification       Not Started                 │
   │                                                           │
   │ [ Install ]                                  [ Close ]    │
   │                                                           │
   │ Log                              [Copy Log] [Save Log…]   │
   │ ┌──────────────────────────────────────────────────────┐  │
   │ │                                                      │  │
   │ │                                                      │  │
   │ └──────────────────────────────────────────────────────┘  │
   └──────────────────────────────────────────────────────────┘
   ```

The Run button's label changes based on state:

| State | Button label | Meaning |
|-------|--------------|---------|
| First install on this instance | `Install` | No existing install row; will consume one slot if licensed. |
| Same version already installed | `Re-install (same version 3.12.1)` | Asks for confirmation. Slot count unchanged. |
| Different version already installed | `Replace v3.12.0 → v3.12.1` | Will run install which uninstalls the old version + installs the new. Slot count unchanged. |
| Slot cap exceeded | `Install (blocked by license)` (disabled) | Slot panel shows the blocking reason. |

### Step 4 — Run the Install

Click the Run button. If the dialog asks for confirmation (re-install
same version, blocked-but-overridden, etc.), respond.

The four phases run in sequence. The phase cards turn from grey ●
(Not Started) → blue ● (Running) → green ● (Completed) or red ●
(Failed). The Log panel below streams the SSH transcript live.

**Phase 1 — Pre-check.** Should complete in under a second.

```
=== Phase 1: Pre-check ===
Checking Docker containers...
NAME       SERVICE   STATUS         PORTS
espocrm    espocrm   Up 3 hours     0.0.0.0:443->443/tcp, ...
Installing Advanced Pack v3.12.1...
```

**Phase 2 — Backup.** Typically 20–90 seconds depending on database
size. The same `mariadb-dump` + `tar` pair as the Upgrade flow,
written to `/var/backups/espocrm/{YYYYMMDD_HHMMSS}/`.

```
=== Phase 2: Backup ===
Creating backup directory: /var/backups/espocrm/20260513_142510
Dumping database...
$ docker compose -f /var/www/espocrm/docker-compose.yml exec -T \
    -e MYSQL_PWD=[db_root_password] espocrm-db mariadb-dump ...
Archiving data volume...
Backup complete: /var/backups/espocrm/20260513_142510
```

If the backup fails (full disk, etc.) the install aborts here — no
zip has been uploaded yet, no extension change has happened.

**Phase 3 — Install.** Usually 30–120 seconds. This is the actual
upload + CLI invocation:

```
=== Phase 3: Install ===
Uploading advanced-pack-3.12.1.zip to /tmp/advanced-pack-3.12.1.zip...
Copying zip into espocrm container at /tmp/advanced-pack-3.12.1.zip...
$ docker compose -f /var/www/espocrm/docker-compose.yml cp \
    /tmp/advanced-pack-3.12.1.zip espocrm:/tmp/advanced-pack-3.12.1.zip
Installing Advanced Pack via EspoCRM CLI...
$ docker compose -f /var/www/espocrm/docker-compose.yml exec -T -u www-data \
    espocrm php command.php extension --file=/tmp/advanced-pack-3.12.1.zip
Installed Advanced Pack version 3.12.1.
Clearing application cache...
Done.
```

If the CLI reports an incompatible-version error here, the install
fails with a clear message and the backup from Phase 2 is intact.

**Phase 4 — Verification.** Usually under 5 seconds.

```
=== Phase 4: Verify ===
Confirming site responds on HTTPS...
HTTP/2 200
Verifying EspoCRM container still healthy...
NAME       SERVICE   STATUS         ...
espocrm    espocrm   Up 3 hours     ...
Advanced Pack v3.12.1 installed successfully.
Extension install complete.
```

After phase 4, the dialog stays open so you can review the log. The
Install tab table behind the dialog refreshes when you close it.

### Step 5 — Post-Install Operator Steps

CRM Builder records that the extension is installed and stores the
license key in the OS keyring, but does **not** yet push the key
into the extension's own configuration inside EspoCRM. **For paid
extensions you must enter the key in the CRM admin panel once.**

For each paid extension, log into the EspoCRM admin UI on the target
instance and complete the vendor's activation step:

| Extension | Where to enter the key |
|-----------|------------------------|
| Advanced Pack | Administration → Advanced Pack → Manage License → paste key → Save |
| Sales Pack | Administration → Sales Pack → Manage License |

Free extensions don't have a license page but typically need
configuration:

| Extension | Where to configure |
|-----------|--------------------|
| Google Integration | Administration → Google Integration → Google API → enter OAuth client id, client secret, redirect URI |

If a paid extension is installed without a license key entered in the
CRM, it usually runs in trial mode for a limited period — the
extension's own UI shows a warning banner.

---

### Worked Example 1 — First Install of Advanced Pack on Production

Starting state: CBM Production is deployed, Advanced Pack zip is sitting
at `~/Projects/CBM/ExtensionFiles/advanced-pack-3.12.1.zip`, license
key is in 1Password under "EspoCRM Advanced Pack — CBM."

1. Open CRM Builder, switch to the CBM client, open the **Deployment**
   tab. Confirm `CBM Production (CBM-PROD)` is selected in the picker.
2. Click **Extensions** in the sidebar, **Licenses** tab.
3. Click **Add License…**. Enter:
   - Extension name: `Advanced Pack`
   - Purchaser label: (leave blank — single license)
   - License key: paste from 1Password
   - Max production slots: `1` (default)
   - Max non-production slots: `2` (default)
   - Notes: `Renewed 2026-04; expires 2027-04`
4. Click **Save**. The row appears with `0/1` and `0/2`.
5. Switch to the **Install** tab.
6. Click **Install Extension…**, navigate to the zip, click **Open**.
7. The Install dialog opens. Slot panel reads:
   ```
   License: Advanced Pack
   Production: 0/1
   Non-production: 0/2
   This install will consume one new slot.
   ```
8. Click **Install**. Watch the four phases run (~2 minutes total).
9. When the log shows `Extension install complete.`, click **Close**.
10. The Install tab now shows:
    ```
    Extension       Version    License     Installed
    Advanced Pack   3.12.1     Licensed    2026-05-13T14:25:42Z
    ```
11. The Licenses tab now shows `1/1` for production, `0/2` for
    non-production.
12. Open `https://crm-prod.example.com/` in a browser, log in as admin,
    go to **Administration → Advanced Pack → Manage License**, paste
    the same key, click **Save**.
13. Done.

### Worked Example 2 — Replacing v3.12.0 with v3.12.1 on Staging

Starting state: CBM Staging already has Advanced Pack 3.12.0 installed.
A new build, `advanced-pack-3.12.1.zip`, sits in `ExtensionFiles/`.

1. Confirm `CBM Staging (CBM-STAGE)` is selected in the picker.
2. **Extensions** sidebar entry, **Install** tab.
3. Click **Install Extension…**, pick `advanced-pack-3.12.1.zip`.
4. The Install dialog detects the existing install row. The Run button
   reads `Replace v3.12.0 → v3.12.1`. The slot panel reads:
   ```
   License: Advanced Pack
   Production: 1/1 — CBM-PROD
   Non-production: 1/2 — CBM-STAGE
   This is a re-install on an existing slot — no new slot will be consumed.
   ```
5. Click **Replace v3.12.0 → v3.12.1**. The four phases run. The
   EspoCRM CLI uninstalls 3.12.0 and installs 3.12.1 in a single
   call — there is no separate "old version" backup; Phase 2's backup
   covers rollback.
6. After success the Install tab shows `Advanced Pack — 3.12.1` and
   the Licenses tab still shows `1/1` and `1/2`.
7. Visit the CRM admin panel — the license key is already in place
   from the original 3.12.0 install, no operator step needed.

### Worked Example 3 — Installing Free Google Integration

Starting state: CBM Production is deployed. No license needed.

1. Confirm `CBM Production (CBM-PROD)` is selected.
2. **Extensions** sidebar entry, **Install** tab. (Skip the Licenses
   tab entirely.)
3. Click **Install Extension…**, pick `google-integration-1.8.4.zip`.
4. The Install dialog opens. The slot panel reads:
   ```
   No license registered for this extension. Install will proceed unlicensed.
   ```
   The Run button reads `Install`.
5. Click **Install**. The four phases run.
6. After success, log into the CRM admin panel and go to
   **Administration → Google Integration → Google API**. Enter the
   OAuth client id, client secret, and redirect URI from your Google
   Cloud Console project.
7. Configure per-user Google account links through
   **Administration → Google Integration → Calendars** / **Contacts**
   as needed.

---

### Slot Caps and Counting

Each paid extension license has two pools, counted independently:

- **Production** — instances whose `environment` field is `production`.
- **Non-production** — instances whose `environment` field is
  `staging` or `test`.

Re-installs on an instance that already holds a slot for this
extension do **not** consume a new slot. The dialog says
*"This is a re-install on an existing slot — no new slot will be
consumed."* and the Run button label reflects the situation
(`Re-install (same version)` or `Replace …`).

If a fresh install would exceed a pool's cap:

```
License: Advanced Pack
Production: 1/1 — CBM-PROD
Non-production: 2/2 — CBM-STAGE, CBM-TEST
Blocked: Non-production slots full (2/2): occupied by CBM-STAGE,
CBM-TEST. Free a slot before installing on another non-production
instance.
```

The Run button is disabled. To free a slot, log into one of the named
instances' EspoCRM admin panels and uninstall the extension through
**Administration → Extensions → (extension) → Uninstall**. CRM Builder
does not currently expose an uninstall action — this is deliberate
per scope decisions; the slot pools are reclaimed automatically on
the next install attempt because the ExtensionInstall row is removed
when EspoCRM reports the extension gone. (Today the row stays in CRM
Builder's database; you can manually clear it by deleting the
ExtensionInstall row for that instance — typically only relevant
during migrations.)

### Re-installing

To re-install the same extension version (typically to recover from a
mid-install failure, or to push a fix that was repackaged with the
same version number), re-pick the same `.zip`:

1. **Install Extension…** → choose the zip → Run button reads
   `Re-install (same version X.Y.Z)`.
2. Click it. CRM Builder asks for confirmation:
   *"Advanced Pack v3.12.1 is already installed. Re-install it
   anyway?"*
3. Click **Yes**. The four phases run; EspoCRM's CLI does an
   uninstall + reinstall in a single call.

Version replacement (different version number on the same instance)
works the same way except no confirmation prompt — the Run button
reads `Replace vA.B.C → vX.Y.Z` and runs on click.

The slot count never changes on re-install or replacement.

### Rolling Back

The Backup phase of every install writes a fresh `db.sql.gz` +
`data.tar.gz` pair under `/var/backups/espocrm/{YYYYMMDD_HHMMSS}/` on
the server. If the install left the site in a bad state, the manual
SSH restore procedure documented under
**Upgrading EspoCRM → Rolling Back** above applies verbatim — the
timestamped folder for the install's backup is the most recent entry
under `/var/backups/espocrm/`.

```bash
ssh root@<droplet>
ls -1d /var/backups/espocrm/*/ | tail -3
# pick the timestamp matching the install you want to roll back
```

Then follow the steps in the Upgrade rollback section above.

### Troubleshooting

**`No license registered for this extension. Install will proceed
unlicensed.`** in the slot panel — for free extensions this is
correct, proceed. For paid extensions it means the License row's
**Extension name** field doesn't match the zip's `manifest.json` `name`
field. Common causes:

- Wrong capitalization (`advanced pack` instead of `Advanced Pack`).
- Extra punctuation (`Advanced Pack 3.12` — version doesn't go in the
  name).
- Stale License row from an older naming convention.

Fix it by editing the License row's Extension name field — the
Licenses tab → double-click the row → correct the value → **Save**.
Re-open the Install dialog (close + relaunch) and the slot panel
will pick up the corrected row.

**`Production slot full (1/1): occupied by CBM-PROD. Free a slot
before installing on another production instance.`** — your license
already has its production slot consumed by another instance.
Uninstall the extension on that instance through EspoCRM's own
Administration → Extensions panel first, then retry.

**`Non-production slots full (2/2)`** — same idea for the staging /
test pool.

**`SFTP upload failed: …`** — paramiko couldn't push the zip to
`/tmp` on the host. Most common cause: the SSH credentials have
rotated since the Deploy wizard wrote them. Click **Edit Connection**
on the Deploy entry to update; the same row is used by Upgrade and
Extension Install.

**`docker compose cp into espocrm container failed`** — the host can
reach SSH but the docker compose file path is wrong or the espocrm
service isn't running. Run `docker compose -f
/var/www/espocrm/docker-compose.yml ps` manually on the host to
diagnose; if the compose file is at a non-standard path, the
extension install needs a code-level fix (the path is currently
hardcoded — same as Upgrade and Recovery).

**`extension is not compatible with this EspoCRM version`** — the
zip's `manifest.json` declares an `acceptableVersions` range that
doesn't include the running EspoCRM version. Two options:
1. **Upgrade EspoCRM first** via the Upgrade EspoCRM dialog, then
   retry the extension install.
2. **Obtain a matching extension build** from the vendor. EspoCRM
   Advanced Pack ships multiple builds keyed to specific EspoCRM
   versions.

**`Could not read manifest.json`** — the zip isn't a valid EspoCRM
extension. Verify you picked the right file (not, e.g., an SDK or
a documentation archive).

**Phase 4 fails with `HTTPS smoke check failed`** — the install
itself succeeded but the site is no longer responding. Check the
EspoCRM container is up (`docker compose -f
/var/www/espocrm/docker-compose.yml ps`); restart if needed
(`docker compose -f /var/www/espocrm/docker-compose.yml restart`).
The extension may have left a syntax error or a missing dependency —
inspect `docker compose logs espocrm` for the stack trace, then roll
back to the Phase 2 backup if the issue isn't quickly fixable.

---

## Editing Configuration

Click **Edit Configuration** in the dashboard header to reopen the Setup
Wizard with all current values pre-populated. Changes are saved but do
not automatically trigger a new deployment — you must click Deploy All
to apply changes.

---

## Troubleshooting

### SSH connection failed
- Verify you can SSH manually: `ssh -i <key-path> root@<ip>`
- Check that the Droplet is running in DigitalOcean
- Confirm the SSH key was added to the Droplet

### DNS validation timed out
- Verify the A record in your DNS provider
- Some providers take up to 48 hours to propagate (though most take
  minutes). Try lowering the TTL to 300.
- Confirm you entered the subdomain correctly (just `crm`, not
  `crm.mycompany.com`)

### EspoCRM installer failed
- "Input device is not a TTY" — this is handled automatically. If you
  see it, update CRM Builder.
- "Unable to determine current installation mode" — a previous attempt
  left partial files. CRM Builder uses `--clean` to handle this
  automatically on retry.

### Phase 4 verification failures
- A single FAIL does not necessarily mean the deployment is broken.
  Click **Run Verification Only** to recheck.
- Docker containers may take a moment to start — wait 30 seconds and
  verify again.

### SSL certificate shows "Unknown"
- The certificate check runs in the background when you select the
  instance. If the domain isn't reachable yet, it returns Unknown.
- After a successful deployment, close and reopen CRM Builder or
  reselect the instance to trigger a fresh check.

---

## Change Log

| Version | Date | Changes |
|---|---|---|
| 1.3 | 05-13-26 | Expanded the "Installing Extensions" section into a full step-by-step walkthrough: ASCII representations of the Extensions panel and Install dialog, field-by-field tables for the Add License modal, sample log output for each of the four phases, three worked examples (first paid install of Advanced Pack on production, replacing v3.12.0 → v3.12.1 on staging, installing free Google Integration), expanded troubleshooting entries with exact error wording and remediation commands. |
| 1.2 | 05-13-26 | Added the "Installing Extensions" section covering the new Extensions sidebar entry, the Licenses tab and slot enforcement model (1 production + 2 non-production by default per paid license), the four-phase install/re-install flow modeled on Upgrade, operator-side license-key entry, free vs. paid extensions, and rollback via the install-time backup. |
| 1.1 | 05-02-26 18:00 | Added the new Setup Wizard "Documentation Inputs" step (now Step 6, with Review & Confirm becoming Step 7); added the "After Deployment — Deployment Record" section covering automatic generation, regeneration via the Deployment tab, the pre-automation backfill flow, and committing the Record to the client repository; added a Record-regeneration note to the "After the Upgrade" section. Reflects the deployment-record series shipped in the crmbuilder repo on 2026-05-02 (Prompts A through I). |
| 1.0 | March 2026 | Initial release. Setup Wizard walkthrough, deployment phases, post-deploy connection, Deployment Dashboard, DNS / SSL guidance, Upgrade flow, troubleshooting. |
