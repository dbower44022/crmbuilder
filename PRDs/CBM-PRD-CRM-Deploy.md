# CRM Builder — EspoCRM Deployment Feature
## Product Requirements Document
**Version:** 1.0 | **Date:** March 2026 | **Status:** Active

---

## Revision History

| Version | Date | Notes |
|---------|------|-------|
| 0.1 | March 2026 | Initial draft as standalone tool |
| 0.2 | March 2026 | Added PySide6 GUI: Setup Wizard and Deployment Dashboard |
| 0.3 | March 2026 | Closed open questions: cleanup/restart, cbmadmin user, DO backup |
| 1.0 | March 2026 | Rewritten: integrated into CRM Builder; switched to official EspoCRM installer script (Docker-based); aligned to CRM Builder file structure and UI patterns |

---

## 1. Overview

This document defines the requirements for adding EspoCRM server deployment
capability directly into the CRM Builder desktop application. Rather than
maintaining a separate tool, deployment is a new feature panel within the
existing PySide6 application, consistent with the existing Instance, Program,
and Output panels.

The feature automates provisioning EspoCRM on a DigitalOcean Droplet via SSH,
using the official EspoCRM installer script as the installation mechanism. It
targets two environments per client: Production and Test/Staging.

---

## 2. Background

CRM Builder already manages EspoCRM configuration (fields, layouts,
relationships, data import) against running instances. The missing link is
the step before that: getting a fresh EspoCRM instance up and running on
a server. Adding deployment to CRM Builder closes this gap and gives
administrators a single tool for the full lifecycle — from provisioning a
new server through deploying configuration to it.

---

## 3. Goals

### 3.1 Goals

- Add a Deploy panel to the CRM Builder main window as a new section
- Allow the user to initiate deployment from the currently selected instance
- Guide first-time setup through a modal Setup Wizard (consistent with
  existing dialog patterns such as `instance_dialog.py`)
- Provide a Deployment Dashboard for subsequent runs with real-time phase
  status and log output
- Use the official EspoCRM installer script as the installation mechanism
  (Docker-based; Nginx + MariaDB + EspoCRM as containers)
- Validate DNS propagation before attempting Let's Encrypt certificate issuance
- Track SSL certificate expiry and warn the operator before certificates expire
- Persist deployment configuration alongside existing instance profiles

### 3.2 Non-Goals

- The tool does **not** provision DigitalOcean Droplets (Droplet must exist
  before running the Deploy feature)
- The tool does **not** configure DNS records (must be done manually in the
  DNS provider before deployment)
- The tool does **not** migrate data between environments
- The tool does **not** support operating systems other than Ubuntu 22.04 LTS
- The tool does **not** support bare IP deployments for production or test
  environments (a domain name is required)

---

## 4. Prerequisites

The following must be completed by the administrator **before** opening the
Setup Wizard in CRM Builder. The deployment tool will validate some of these
automatically, but most require manual action in advance.

### 4.1 DigitalOcean Account and Droplet

1. **Create a DigitalOcean account** at https://digitalocean.com if you do
   not already have one.

2. **Provision a Droplet** with the following specifications:

   | Setting | Production | Test / Staging |
   |---------|-----------|----------------|
   | Image | Ubuntu 22.04 LTS x64 | Ubuntu 22.04 LTS x64 |
   | Size | 2 vCPU / 4 GB RAM / 80 GB SSD (~$24/mo) | 1 vCPU / 2 GB RAM / 50 GB SSD (~$12/mo) |
   | Region | Choose closest to your users | Same region as Production |
   | Authentication | SSH Key (see section 4.2) | SSH Key |

   > Do not select a one-click app (WordPress, LAMP, etc.) — the Droplet
   > must be a clean Ubuntu 22.04 image with nothing pre-installed.

3. **Note the Droplet's public IPv4 address** — you will need it in the
   Setup Wizard and for the DNS A record below.

4. **Enable DigitalOcean backups** (optional but recommended for Production):
   In the Droplet settings, enable Weekly Backups. This adds approximately
   20% to the Droplet cost but provides automated snapshots.

### 4.2 SSH Key

CRM Builder connects to the Droplet via SSH using key-based authentication.
Password-based SSH is not supported.

**If you already have an SSH key pair:**
- Locate your private key file (typically `~/.ssh/id_rsa` on Mac/Linux or
  `C:\Users\you\.ssh\id_rsa` on Windows)
- Ensure the corresponding public key is added to the Droplet (see below)

**If you need to create a new SSH key pair:**

On Mac or Linux:
```bash
ssh-keygen -t ed25519 -C "crm-deploy"
```
Accept the default file location. You may set a passphrase or leave it blank.

On Windows (PowerShell):
```powershell
ssh-keygen -t ed25519 -C "crm-deploy"
```

**Adding your public key to the Droplet:**

The easiest method is to add the key when creating the Droplet in the
DigitalOcean control panel:
1. In the Droplet creation screen, under **Authentication**, select
   **SSH Key → New SSH Key**
2. Paste the contents of your public key file (e.g. `~/.ssh/id_rsa.pub`
   or `~/.ssh/id_ed25519.pub`)
3. Click **Add SSH Key**

If the Droplet already exists:
1. Copy your public key to the clipboard:
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```
2. SSH into the Droplet as root using the DigitalOcean console
3. Append your public key to `/root/.ssh/authorized_keys`:
   ```bash
   echo "your-public-key-here" >> ~/.ssh/authorized_keys
   ```

**Verify SSH access before running the deployment tool:**
```bash
ssh -i ~/.ssh/id_ed25519 root@<droplet-ip>
```
You should connect without a password prompt. If you are prompted for a
password, the key is not configured correctly — do not proceed until this
is resolved.

### 4.3 Domain Name and DNS

A registered domain name is required for all deployments. The deployment
tool does not support bare IP address installations.

**Subdomain conventions:**

| Environment | Subdomain | Example |
|-------------|-----------|---------|
| Production | `crm` | `crm.mycompany.com` |
| Test / Staging | `crm-test` | `crm-test.mycompany.com` |

**Creating the DNS A record:**

Log in to your DNS provider (wherever your domain name is registered or
managed — e.g. DigitalOcean DNS, GoDaddy, Namecheap, Cloudflare) and
create an A record:

| Field | Value |
|-------|-------|
| Type | `A` |
| Name / Host | `crm` (production) or `crm-test` (test) |
| Value / Points To | The Droplet's public IPv4 address |
| TTL | `300` (5 minutes — can be raised to 3600 after confirming it works) |

**Provider-specific notes:**

- **Cloudflare users:** Set the proxy status to **DNS only** (grey cloud,
  not orange). The EspoCRM Let's Encrypt challenge requires a direct
  connection to the server; Cloudflare's proxy will cause certificate
  issuance to fail.
- **All other providers:** Standard A record creation applies.

**Waiting for DNS propagation:**

After saving the A record, wait for it to propagate before starting
deployment. With a TTL of 300 seconds this is typically 2–10 minutes,
but can occasionally take longer.

You can verify propagation using any of the following:

```bash
# On Mac / Linux
dig crm.mycompany.com +short
# Should return your Droplet IP

# On Windows
nslookup crm.mycompany.com
# Look for the Address line — should match your Droplet IP
```

Or use an online tool such as https://dnschecker.org.

> CRM Builder will automatically validate DNS propagation before starting
> deployment and will wait up to 10 minutes, retrying every 30 seconds.
> However, confirming it manually in advance avoids delays at startup.

### 4.4 Information to Have Ready

Before opening the Setup Wizard, have the following ready:

| Item | Notes |
|------|-------|
| Droplet IP address | From the DigitalOcean control panel |
| SSH private key file path | e.g. `~/.ssh/id_ed25519` |
| Base domain | e.g. `mycompany.com` |
| Subdomain | `crm` for production, `crm-test` for test |
| Let's Encrypt email address | Used for certificate expiry notifications — use a monitored address |
| EspoCRM admin username | Default: `admin` |
| EspoCRM admin password | Choose a strong password; store it securely |
| EspoCRM admin email address | The admin user's email address |
| EspoCRM DB password | Choose a strong password; store it securely |
| MariaDB root password | Optional — leave blank to auto-generate |

> Passwords entered in the Setup Wizard are saved to a local configuration
> file and used during deployment. Store all credentials in a password
> manager — they cannot be recovered from CRM Builder after entry.

### 4.5 CRM Builder Instance Profile

Before using the Deploy feature, create an Instance Profile in CRM Builder
for the environment you are deploying:

1. In CRM Builder, click **+ Add** in the Instance panel
2. Enter a name (e.g. `MyCompany CRM — Production`)
3. You do not need a working URL yet — the Deploy feature will update the
   URL automatically after a successful deployment
4. Save the profile and select it in the Instance panel

The Deploy panel will then show a **Set Up Deployment** button, which opens
the Setup Wizard.

---

## 5. Architecture

### 4.1 Hosting Infrastructure

Each client deployment targets two environments, each on its own Droplet:

| Parameter | Production | Test / Staging |
|-----------|-----------|----------------|
| Provider | DigitalOcean | DigitalOcean |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| Droplet Size | 2 vCPU / 4 GB RAM / 80 GB SSD | 1 vCPU / 2 GB RAM / 50 GB SSD |
| Domain convention | `crm.{client-domain}` | `crm-test.{client-domain}` |
| Est. Monthly Cost | ~$24/mo | ~$12/mo |

### 4.2 Software Stack (Server)

The official EspoCRM installer script manages the server stack as Docker
containers. CRM Builder does not install or configure these components
individually — it delegates entirely to the installer script.

| Component | Role |
|-----------|------|
| Docker + Docker Compose | Container runtime (installed by EspoCRM script) |
| Nginx (container) | Web server / reverse proxy |
| MariaDB (container) | Database |
| EspoCRM (container) | CRM application |
| Let's Encrypt / Certbot | SSL certificate (managed by EspoCRM script) |

### 4.3 Integration Architecture

The Deploy feature follows the same architectural patterns as the rest of
CRM Builder:

- **Business logic** in `espo_impl/core/` — no GUI dependencies
- **UI components** in `espo_impl/ui/` — PySide6 panels and dialogs
- **Background work** in `espo_impl/workers/` — QThread workers
- **SSH execution** via Paramiko — all server commands run remotely;
  nothing is permanently installed on the administrator's machine
- **Config persistence** alongside instance profiles in `data/instances/`,
  gitignored

---

## 6. User Experience

### 5.1 Deploy Panel in the Main Window

A **Deploy** section is added to the CRM Builder main window below the
existing Instance and Program panels. It is always visible but its content
is context-sensitive based on the selected instance.

**When no instance is selected:**
The panel displays a prompt: *"Select an instance to manage its deployment."*

**When an instance is selected but has no deployment configuration:**
The panel displays a **Set Up Deployment** button. Clicking it opens the
Setup Wizard as a modal dialog.

**When an instance is selected and has deployment configuration:**
The panel displays the Deployment Dashboard inline.

This mirrors the existing pattern where selecting an instance drives the
Program panel content, and dialogs (like `InstanceDialog`) handle
configuration tasks modally.

### 5.2 Setup Wizard (First Run — Modal Dialog)

The Setup Wizard opens as a modal dialog when no deployment configuration
exists for the selected instance. It follows the same visual style as
`instance_dialog.py`. Navigation buttons (Back, Next, Cancel) appear at
the bottom of every step.

| Step | Title | Fields / Actions |
|------|-------|-----------------|
| 1 | Server Connection | Droplet IP address; SSH key file path (with Browse button); SSH username (default: `root`) |
| 2 | Domain | Base domain (e.g. `mycompany.com`); Subdomain prefix (default: `crm` for production, `crm-test` for test); Full domain shown as read-only preview |
| 3 | Database | EspoCRM DB password; MariaDB root password (optional — auto-generated if blank) |
| 4 | EspoCRM Admin | Admin username (default: `admin`); Admin password; Admin email address |
| 5 | SSL | Email address for Let's Encrypt expiry notifications |
| 6 | Review & Confirm | Summary of all entered values (passwords masked). Back and **Save & Deploy** buttons. |

On **Save & Deploy**, the wizard saves the configuration, closes, and the
Deploy panel transitions to the Deployment Dashboard and begins deployment
automatically.

> Password fields must always be masked. The Review step shows passwords as
> masked strings with an optional Show/Hide toggle.

### 5.3 Deployment Dashboard

The Deployment Dashboard displays within the Deploy panel for instances that
have deployment configuration. It has four areas:

#### 5.3.1 Environment Header

Displays the instance name, full domain, and Droplet IP. An **Edit
Configuration** button reopens the Setup Wizard pre-populated with saved
values.

Also displays SSL certificate status:
- Certificate expiry date
- Days remaining
- Status badge: **Valid** (green, >30 days), **Expiring Soon** (yellow,
  14–30 days), **Critical** (red, <14 days), **Unknown** (grey)

#### 5.3.2 Phase Status Panel

Displays the four deployment phases as a vertical list of status cards.
Each card shows:

- Phase name and brief description
- Status: Not Started / In Progress / Completed / Failed
- Status represented by both a color indicator **and** a text label
  (never color alone)

| Status | Color | Label |
|--------|-------|-------|
| Not Started | Grey | Not Started |
| In Progress | Blue (animated) | Running... |
| Completed | Green | Completed |
| Failed | Red | Failed — see log |

#### 5.3.3 Action Buttons

- **Deploy All** — runs all phases sequentially from Phase 1
- **Run Verification Only** — runs Phase 4 (verify) only
- **Retry Failed Phase** — enabled only when a phase has failed; re-runs
  from the failed phase

#### 5.3.4 Log Window

A scrollable, read-only log window streams live SSH output during
deployment. Each line is timestamped and color-coded:

- White: standard output
- Yellow: warnings
- Red: errors

**Copy Log** and **Save Log to File** buttons appear above the log window,
consistent with the existing `OutputPanel` component.

### 5.4 Verification Results

After Phase 4 (Verification) completes, a results table is shown within the
Deploy panel listing each check with pass/fail status. A summary banner
indicates overall result: **All Checks Passed** or **Issues Found**. The
user can export results as a text file.

### 5.5 Error Handling in the UI

- If a phase fails, the phase card turns red and deployment halts
- An error panel expands below the failed phase card showing the failed
  command and its output
- Where possible, a plain-language remediation message is shown
- The **Retry Failed Phase** button becomes active

---

## 7. Functional Requirements

### 6.1 Deployment Configuration

Each instance may have an associated deployment configuration stored as a
separate JSON file alongside the instance profile in `data/instances/`,
named `{instance_slug}_deploy.json`. This file is gitignored.

| Parameter | Description | Default |
|-----------|-------------|---------|
| `droplet_ip` | IP address of the target Droplet | — |
| `ssh_key_path` | Local path to SSH private key | `~/.ssh/id_rsa` |
| `ssh_user` | SSH login username | `root` |
| `base_domain` | Registered domain (e.g. `mycompany.com`) | — |
| `subdomain` | Subdomain prefix | `crm` |
| `letsencrypt_email` | Email for Let's Encrypt notifications | — |
| `db_password` | EspoCRM database password | — |
| `db_root_password` | MariaDB root password | auto-generated |
| `admin_username` | EspoCRM admin username | `admin` |
| `admin_password` | EspoCRM admin password | — |
| `admin_email` | EspoCRM admin email | — |
| `cert_expiry_date` | Last known certificate expiry (ISO date) | — |
| `deployed_at` | Timestamp of last successful deployment | — |

The full domain is derived as `{subdomain}.{base_domain}`.

### 6.2 DNS Pre-flight Validation

Before Phase 1 begins (and again before Phase 2 SSL issuance), the tool
validates that DNS has propagated:

1. Resolve `{subdomain}.{base_domain}` via DNS
2. Compare resolved IP to `droplet_ip`
3. If they match → proceed
4. If they do not match → display a clear error with the mismatched IPs
5. If no result → display an error prompting the user to create the A record
6. Retry automatically every 30 seconds up to a 10-minute timeout, with
   a countdown shown in the log window

### 6.3 Deployment Phases

#### Phase 1 — Server Preparation

- Connect to Droplet via SSH as the configured user
- Run `apt-get update && apt-get upgrade -y`
- Install Docker prerequisites: `curl`, `ca-certificates`, `gnupg`
- Install Docker Engine and Docker Compose via Docker's official apt repository
- Configure swap space (2 GB)
- Open firewall ports 22, 80, and 443

#### Phase 2 — EspoCRM Installation

- Download the official EspoCRM installer script
- Run the installer with Let's Encrypt SSL and all configuration flags:

```
sudo bash install.sh -y --ssl --letsencrypt \
  --domain={full_domain} \
  --email={letsencrypt_email} \
  --admin-username={admin_username} \
  --admin-password={admin_password} \
  --db-password={db_password} \
  --db-root-password={db_root_password}
```

- The installer handles: Docker Compose setup, Nginx configuration,
  MariaDB initialisation, EspoCRM installation, Let's Encrypt certificate
  issuance, and cron configuration

#### Phase 3 — Post-Install Configuration

- Verify all Docker containers are running (`espocrm`, `espocrm-db`, `espocrm-nginx`)
- Confirm cron job is active for EspoCRM scheduled tasks
- Record the SSL certificate expiry date to the deployment config file
- Update the instance profile URL to `https://{full_domain}` so CRM Builder
  can immediately connect to the new instance

#### Phase 4 — Verification

| Check | Method | Pass Condition |
|-------|--------|---------------|
| Docker containers running | `docker compose ps` in `/var/www/espocrm` | All containers Up |
| HTTP redirect | HTTP GET to domain | 301/302 to HTTPS |
| HTTPS response | HTTPS GET to domain | 200 OK |
| SSL certificate valid | Certificate expiry check | Valid, >30 days remaining |
| EspoCRM login page | HTTPS GET `/` | EspoCRM login UI present |
| Cron job configured | `crontab -l` | EspoCRM cron entry present |
| DB connectivity | `docker exec espocrm-db` health check | Successful |

### 6.4 SSL Certificate Expiry Monitoring

- Expiry date is stored in the deployment config after each successful
  deployment or verification run
- Each time the Deploy panel is shown, a background thread refreshes the
  expiry date via SSH
- Display thresholds:

| Days Remaining | Badge | Color |
|---------------|-------|-------|
| > 30 days | Valid | Green |
| 14–30 days | Expiring Soon | Yellow |
| < 14 days | Critical — Renew Now | Red |
| Unknown | Unknown | Grey |

- Let's Encrypt auto-renewal is handled by the EspoCRM installer's built-in
  cron. The tool's monitoring exists to catch cases where auto-renewal has
  silently failed.

---

## 8. Error Handling

### 7.1 Failure Behavior

- Each phase catches and surfaces errors clearly, including the failed
  command and full output
- On phase failure, deployment halts and a plain-language remediation
  message is shown where possible
- SSH connection failures are reported with actionable guidance

### 7.2 Cleanup on Failure

When a phase fails the tool halts, runs best-effort cleanup, and presents
a **Restart Deployment** button to re-run from Phase 1.

| Phase | Cleanup Actions |
|-------|----------------|
| Phase 1 — Server Prep | Remove partially installed packages; restore original swap config |
| Phase 2 — Installation | `docker compose down --volumes` in `/var/www/espocrm`; remove installer files |
| Phase 3 — Post-install | No destructive cleanup (config updates only; re-running is safe) |
| Phase 4 — Verification | No cleanup required (read-only) |

> Cleanup is best-effort. Failures during cleanup are logged and the user
> is notified of any steps that could not be completed.

---

## 9. Security Requirements

- Passwords are masked in all log output — never logged in plaintext
- Deployment config files are gitignored — the tool verifies
  `data/instances/*_deploy.json` is in `.gitignore` on first run
- SSH connections use key-based authentication only
- All web traffic is HTTPS — HTTP redirects to HTTPS (enforced by installer)
- MariaDB container is not exposed outside the Docker network

---

## 10. Technical Requirements

### 9.1 Language and Runtime

Follows existing CRM Builder standards:
- Python 3.12+
- PySide6 6.10+
- Managed via `uv` / `pyproject.toml`

### 9.2 New Dependencies

Add to `pyproject.toml` `dependencies`:

| Package | Purpose |
|---------|---------|
| `paramiko` | SSH connection and remote command execution |
| `dnspython` | DNS resolution for pre-flight validation |

### 9.3 File Structure

```
espo_impl/
├── core/
│   └── deploy_manager.py       # SSH execution, phase logic, config read/write
├── ui/
│   ├── deploy_panel.py         # Deploy section in main window
│   ├── deploy_wizard.py        # Setup Wizard modal dialog (6-step)
│   └── deploy_dashboard.py     # Deployment Dashboard (phases, log, cert status)
└── workers/
    └── deploy_worker.py        # QThread background worker for SSH phases

data/
└── instances/
    └── {instance_slug}_deploy.json   # Per-instance deploy config (gitignored)
```

### 9.4 New Model: `DeployConfig`

Add to `espo_impl/core/models.py`:

```python
@dataclass
class DeployConfig:
    """Deployment configuration for an EspoCRM instance on DigitalOcean."""
    droplet_ip: str
    ssh_key_path: str
    ssh_user: str
    base_domain: str
    subdomain: str
    letsencrypt_email: str
    db_password: str
    db_root_password: str
    admin_username: str
    admin_password: str
    admin_email: str
    cert_expiry_date: str | None = None
    deployed_at: str | None = None

    @property
    def full_domain(self) -> str:
        """Fully qualified domain name for this deployment."""
        return f"{self.subdomain}.{self.base_domain}"
```

---

## 11. Out of Scope

- DigitalOcean Droplet provisioning
- DNS record configuration
- Data migration between environments
- Database backup and restore automation
- Monitoring and alerting beyond SSL expiry tracking

---

## 12. Decisions

| # | Decision |
|---|----------|
| 1 | Deployment is integrated into CRM Builder — not a separate tool |
| 2 | Deploy panel is added to the main window; Setup Wizard launches as a modal dialog |
| 3 | Environment selection is implicit — the selected instance determines the deployment target |
| 4 | The official EspoCRM installer script (Docker-based) is used — no manual LAMP stack |
| 5 | Let's Encrypt is the standard SSL mode — no bare IP, no custom certificate in v1.0 |
| 6 | Domain names are required for all deployments |
| 7 | Domain convention: `crm.{domain}` for production, `crm-test.{domain}` for test/staging |
| 8 | DNS propagation is validated before deployment begins and before SSL issuance |
| 9 | SSL certificate expiry is tracked in deploy config and displayed in the Deploy panel |
| 10 | Alert thresholds: warn at 30 days remaining, escalate at 14 days remaining |
| 11 | Deploy config stored as `{instance_slug}_deploy.json` in `data/instances/` (gitignored) |
