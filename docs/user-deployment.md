# CRM Builder — EspoCRM Server Deployment Guide

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026

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

The wizard has six steps:

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

### Step 6 — Review & Confirm

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

## After Deployment — Connecting CRM Builder to the New Instance

Before you can deploy YAML program files (Validate → Run → Verify),
you must configure authentication in your CRM Builder instance profile.
The field management and entity management API endpoints require
**admin-level access** — without it you will get HTTP 403 Forbidden on
every operation.

### Option A — Basic Auth (Quickest)

Use the same admin credentials you entered in the Setup Wizard. No
additional EspoCRM configuration needed.

1. In CRM Builder, select the instance and click **Edit**
2. Set:
   - **Auth Method:** Basic (Username/Password)
   - **Username:** the admin username from Step 4 (default: `admin`)
   - **Password:** the admin password from Step 4
3. Click **Save**

You can now Validate and Run YAML program files immediately.

### Option B — API Key (Recommended for Production)

API Key authentication is more secure for ongoing use because you can
revoke the key without changing the admin password. However, it requires
creating an API User in EspoCRM with admin access first.

**Step 1 — Create an API User in EspoCRM:**

1. Log in to EspoCRM at `https://{your-domain}`
2. Go to **Administration** (gear icon, top-right)
3. Click **API Users** (under the Users section)
4. Click **Create API User**
5. Set:
   - **User Name:** `crmbuilder` (or any name)
   - **Authentication Method:** API Key
6. Click **Save**
7. After saving, an **API Key** field appears — copy this value

**Step 2 — Grant Admin Access:**

The API User must have admin-level access. There are two ways:

**Method A — Make the API User an Admin:**
1. On the API User record, check the **Is Admin** checkbox
2. Click **Save**

**Method B — Create an Admin Role (more granular):**
1. Go to **Administration → Roles**
2. Click **Create Role**
3. Name it `CRM Builder Admin`
4. Under **Access**, set all entity scopes to **Enabled** and all
   actions to **Yes** (or at minimum: enable read/write on all entities
   you plan to configure)
5. **Important:** The role must include access to:
   - Administration
   - Entity Manager (for creating/deleting entities)
   - Field Manager (for creating/updating fields)
6. Save the role
7. Go back to the API User and assign this role under the **Roles** field

> **Note:** For the field management and entity management endpoints that
> CRM Builder uses, the API user typically needs full admin access.
> Restricted roles will result in HTTP 403 errors. If in doubt, use
> **Is Admin** (Method A).

**Step 3 — Configure CRM Builder:**

1. In CRM Builder, select the instance and click **Edit**
2. Set:
   - **Auth Method:** API Key
   - **API Key:** paste the key from step 1
3. Click **Save**

### Verify the Connection

After configuring authentication (either option):

1. Select a YAML program file
2. Click **Validate**
3. You should see `[VALIDATE] OK` followed by a preview of planned
   changes

If you see `[VALIDATE] FAILED` or `HTTP 403`, double-check:
- The URL matches `https://{your-domain}` (no trailing slash)
- The API User has admin access (Option B) or the admin password is
  correct (Option A)
- For Option B: the API User is active (not disabled)

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

**Phase Status Cards**
Each phase shows its status: Not Started, Running, Completed, or Failed.
Failed phases show error detail.

**Action Buttons**
- **Deploy All** — runs all four phases from the beginning
- **Run Verification Only** — runs Phase 4 checks without redeploying
- **Retry Failed Phase** — restarts from the phase that failed

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
