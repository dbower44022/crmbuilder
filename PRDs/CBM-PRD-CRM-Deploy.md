# CBM CRM Deployment Tool
## Product Requirements Document
**Version:** 0.3 | **Date:** March 2026 | **Organization:** Cleveland Business Mentors

---

## 1. Overview

This document defines the requirements for the CBM CRM Deployment Tool, a Python desktop application with a graphical user interface (GUI) built with PySide6. It automates the provisioning, configuration, and verification of self-hosted EspoCRM instances on DigitalOcean.

The tool eliminates manual, error-prone server setup steps by executing a repeatable, scripted deployment sequence via SSH. It is designed to be accessible to non-technical administrators through a guided, visual interface. It targets two environments: Dev/Test and Production.

---

## 2. Background

Cleveland Business Mentors (CBM) is deploying EspoCRM as its CRM platform to manage mentor-client relationships, engagement tracking, and communications. Two self-hosted instances are required:

- **Production:** `crm.clevelandbusinessmentors.org`
- **Dev/Test:** `dev-crm.clevelandbusinessmentors.org`

Both environments are hosted on DigitalOcean Droplets running Ubuntu 22.04 LTS. The deployment tool is intended to be run locally by a CBM administrator and must handle the full server configuration lifecycle from a clean Ubuntu image through to a verified, operational EspoCRM instance.

---

## 3. Goals

### 3.1 Goals

- Fully automate EspoCRM installation and configuration on a fresh Ubuntu 22.04 LTS Droplet
- Provide a graphical desktop interface (PySide6) accessible to non-technical administrators
- Guide first-time users through configuration via a step-by-step Setup Wizard
- Provide a Deployment Dashboard for subsequent runs with real-time phase status and log output
- Support both Dev/Test and Production environments via a single tool with environment-specific configuration
- Persist environment configuration to local YAML files for reuse across sessions
- Execute post-deployment verification checks and display results clearly in the UI

### 3.2 Non-Goals

- The tool does **not** provision DigitalOcean Droplets (server must exist before running)
- The tool does **not** configure DNS records (must be done manually in DNS provider)
- The tool does **not** migrate data between environments
- The tool does **not** manage ongoing EspoCRM application configuration (contacts, fields, roles, etc.)
- The tool does **not** support operating systems other than Ubuntu 22.04 LTS

---

## 4. Architecture

### 4.1 Hosting Infrastructure

| Parameter | Production | Dev / Test |
|-----------|-----------|------------|
| Provider | DigitalOcean | DigitalOcean |
| Region | New York (nyc1 or nyc3) | New York (nyc1 or nyc3) |
| Droplet Size | 2 vCPU / 4 GB RAM / 80 GB SSD | 1 vCPU / 2 GB RAM / 50 GB SSD |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| Domain | crm.clevelandbusinessmentors.org | dev-crm.clevelandbusinessmentors.org |
| Est. Monthly Cost | ~$24/mo | ~$12/mo |

### 4.2 Software Stack

| Component | Version | Role |
|-----------|---------|------|
| Ubuntu | 22.04 LTS | Operating system |
| Nginx | Latest stable | Web server / reverse proxy |
| PHP | 8.2 | Application runtime |
| MySQL | 8.0 | Database |
| EspoCRM | Latest stable release | CRM application |
| Certbot | Latest stable | Let's Encrypt SSL certificate management |
| Git | System default | Version control utility |

### 4.3 Deployment Tool Architecture

The deployment tool is a Python 3 application that runs locally on the administrator's machine. It connects to the target Droplet via SSH using the Paramiko library and executes all installation and configuration steps remotely. No code is permanently installed on the server.

Key architectural characteristics:

- **Local execution:** runs on administrator's laptop/workstation
- **Remote operations:** all server commands executed via SSH (Paramiko)
- **Config persistence:** environment configuration saved to local YAML files
- **Idempotent design:** safe to re-run against an existing deployment
- **Phase-based execution:** deployment divided into discrete phases

---

## 5. User Experience

The tool presents a PySide6 desktop GUI. The interface operates in two distinct modes depending on whether a saved configuration exists for the selected environment: **Setup Wizard** (first run) and **Deployment Dashboard** (subsequent runs). The application launches by running `python main.py` — no command-line arguments required.

### 5.1 Application Launch

On launch, the application displays a **Welcome Screen** with two large buttons:

- Deploy to Dev / Test
- Deploy to Production

The application checks whether a saved configuration file exists for the selected environment. If no config exists, the Setup Wizard opens. If config exists, the Deployment Dashboard opens.

### 5.2 Setup Wizard (First Run)

The Setup Wizard guides the user through configuration in a series of clearly labeled steps. Each step occupies the full window and includes a title, brief explanation, and input fields. Navigation buttons (Back, Next, Cancel) appear at the bottom of every step.

| Step | Title | Fields / Actions |
|------|-------|-----------------|
| 1 | Choose Environment | Confirm target environment (pre-selected based on launch button) |
| 2 | Server Connection | Droplet IP address, SSH key file path (browse button), SSH username |
| 3 | Domain | Domain name (pre-filled based on environment, editable) |
| 4 | Database | MySQL root password, EspoCRM database name, database username, database password |
| 5 | EspoCRM Admin Account | Admin username, admin password, admin email address |
| 6 | Review & Confirm | Summary of all entered values (passwords masked). Edit and Save buttons. |

On the Review & Confirm step, the user can go back to edit any field. Clicking **Save & Deploy** saves the config to a local YAML file, transitions to the Deployment Dashboard, and begins deployment automatically.

> **Note:** Password fields must always be masked (shown as dots). The Review step shows passwords as masked strings with an optional Show toggle.

### 5.3 Deployment Dashboard (Subsequent Runs)

The Deployment Dashboard is the primary interface for users who have already configured an environment. It consists of four areas:

#### 5.3.1 Environment Header

Displays the target environment name (Dev/Test or Production), domain, and Droplet IP. An **Edit Configuration** button opens a settings panel to update any saved values.

#### 5.3.2 Phase Status Panel

Displays the five deployment phases as a vertical list of status cards. Each card shows:

- Phase name and brief description
- Current status: Not Started, In Progress, Completed, Failed
- Status represented by both a color indicator **and** a text label (never color alone)

| Status | Indicator Color | Label |
|--------|----------------|-------|
| Not Started | Grey | Not Started |
| In Progress | Blue (animated) | Running... |
| Completed | Green | Completed |
| Failed | Red | Failed — see log |

#### 5.3.3 Action Buttons

- **Deploy All** — runs all phases sequentially from Phase 1
- **Run Verification Only** — runs Phase 5 (verify) only
- **Retry Failed Phase** — enabled only when a phase has failed; re-runs from the failed phase

#### 5.3.4 Log Window

A scrollable, read-only log window occupies the lower portion of the dashboard. It streams live output from SSH commands as deployment runs. Each log line is timestamped and color-coded by severity:

- White: standard output
- Yellow: warnings
- Red: errors

A **Copy Log** and **Save Log to File** button appear above the log window.

### 5.4 Verification Results Screen

After Phase 5 (Verification) completes, the tool displays a dedicated results screen showing a table of all verification checks with pass/fail status for each. A summary banner at the top indicates overall result: **All Checks Passed** or **Issues Found**.

From this screen the user can return to the Dashboard or export the results as a text file.

### 5.5 Error Handling in the UI

- If a phase fails, the phase card turns red and deployment halts
- An error panel expands below the failed phase card showing the failed command and its output
- Where possible, a plain-language remediation message is displayed
- The **Retry Failed Phase** button becomes active

---

## 6. Functional Requirements

### 6.1 Configuration Management

The tool must collect and persist the following configuration values per environment:

| Parameter | Description | Default / Example |
|-----------|-------------|-------------------|
| environment | Target environment identifier | `dev` or `prod` |
| droplet_ip | IP address of the target Droplet | e.g. 192.168.1.100 |
| ssh_key_path | Local path to SSH private key | ~/.ssh/id_rsa |
| ssh_user | SSH login username | root (initial), cbmadmin (after hardening) |
| domain | Fully qualified domain name | Auto-set based on environment |
| mysql_root_password | MySQL root password to set | User-provided |
| mysql_db_name | EspoCRM database name | espocrm |
| mysql_db_user | EspoCRM database user | espocrm_user |
| mysql_db_password | EspoCRM database password | User-provided |
| espocrm_admin_user | EspoCRM admin username | admin |
| espocrm_admin_password | EspoCRM admin password | User-provided |
| espocrm_admin_email | EspoCRM admin email address | User-provided |

> **Note:** Config files are saved as `config/cbm-crm-dev.yml` and `config/cbm-crm-prod.yml` in the tool's local directory. These files contain credentials and must not be committed to version control. The tool must automatically create a `.gitignore` entry for the `config/` directory on first run.

### 6.2 Deployment Phases

The deployment is organized into the following sequential phases. Each phase must complete successfully before the next begins. The tool must report phase status (started, completed, failed) clearly in the UI.

#### Phase 1 — Server Hardening

- Connect to Droplet as root for initial setup
- Create non-root sudo user: `cbmadmin`
- Copy root SSH `authorized_keys` to `cbmadmin` user
- Add `cbmadmin` to sudoers group
- Disable root SSH login
- Disable SSH password authentication (key-based only)
- Restart SSH service
- Reconnect as `cbmadmin` for all subsequent phases
- Configure swap space (2GB, recommended for 2GB RAM Droplets)
- Update apt package index
- Install essential utilities: `curl`, `git`, `unzip`, `software-properties-common`

> **Note:** All phases after Phase 1 operate as `cbmadmin` via sudo. The tool must re-establish the SSH connection as `cbmadmin` after hardening completes.

#### Phase 2 — Software Stack Installation

- Install and configure Nginx
- Install PHP 8.2 with required extensions: `mbstring`, `curl`, `zip`, `gd`, `intl`, `mysqlnd`, `xml`, `bcmath`, `tokenizer`
- Install MySQL 8.0
- Set MySQL root password
- Create EspoCRM database, database user, and grant privileges
- Install Certbot and Nginx plugin

#### Phase 3 — EspoCRM Installation

- Download latest stable EspoCRM release from official source
- Extract to `/var/www/espocrm`
- Set correct file ownership (`www-data`) and permissions
- Configure Nginx virtual host for the target domain
- Run EspoCRM CLI installer with database and admin credentials
- Configure EspoCRM cron job for scheduled tasks
- Configure EspoCRM daemon for WebSocket/real-time features

#### Phase 4 — SSL Configuration

- Issue Let's Encrypt SSL certificate for the target domain via Certbot
- Configure Nginx for HTTPS with HTTP → HTTPS redirect
- Verify certificate auto-renewal timer is active

> **Note:** SSL issuance requires that DNS A records already point to the Droplet IP before this phase runs. The tool will check DNS resolution and warn the user if the domain does not resolve correctly before attempting certificate issuance.

#### Phase 5 — Verification

After deployment completes, the tool runs the following verification checks and reports pass/fail for each:

| Check | Method | Pass Condition |
|-------|--------|---------------|
| Nginx running | `systemctl status nginx` | Service active |
| MySQL running | `systemctl status mysql` | Service active |
| PHP-FPM running | `systemctl status php8.2-fpm` | Service active |
| HTTP redirect | HTTP GET to domain | 301/302 to HTTPS |
| HTTPS response | HTTPS GET to domain | 200 OK |
| SSL certificate valid | Certificate expiry check | Valid, >30 days remaining |
| EspoCRM login page | HTTPS GET / | EspoCRM login UI present |
| Cron job configured | `crontab -l` | EspoCRM cron entry present |
| MySQL connectivity | MySQL CLI with EspoCRM credentials | Successful connection |
| EspoCRM daemon | `systemctl status espocrm-daemon` | Service active |

---

## 7. Error Handling

### 7.1 Failure Behavior

- Each phase must catch and surface errors clearly, including the failed command and its output
- On phase failure, the tool halts immediately and displays a clear error message in the UI
- Where possible, a plain-language remediation suggestion is shown alongside the technical error
- SSH connection failures must be reported with actionable guidance (check IP, key path, firewall rules)
- DNS resolution failure before SSL issuance must display a warning and prompt the user to confirm before attempting anyway or aborting

### 7.2 Cleanup and Restart

When a phase fails, the tool must:

1. Halt deployment immediately at the point of failure
2. Execute a cleanup sequence to remove any partially installed components from the failed phase
3. Report cleanup status clearly in the log window (each cleanup step shown as it runs)
4. Return the server to a clean state equivalent to the start of Phase 1
5. Present a **Restart Deployment** button in the UI to re-run from Phase 1

Cleanup actions per phase:

| Phase | Cleanup Actions |
|-------|----------------|
| Phase 1 — Hardening | Remove `cbmadmin` user if created; restore `sshd_config` to original; restart SSH |
| Phase 2 — Stack | Purge `nginx`, `php8.2`, `mysql-server` packages; remove associated config files and data directories |
| Phase 3 — EspoCRM | Remove `/var/www/espocrm`; remove Nginx virtual host config; drop EspoCRM database and user |
| Phase 4 — SSL | Revoke and delete Let's Encrypt certificate; remove HTTPS Nginx config; restore HTTP-only config |
| Phase 5 — Verify | No cleanup required (verification is read-only) |

> **Note:** Cleanup is best-effort. If a cleanup step itself fails, the tool logs the failure and continues with remaining cleanup steps rather than halting. The user is notified of any cleanup steps that could not be completed.

---

## 8. Security Requirements

- Credentials in config files must not be displayed in terminal output after initial entry (mask passwords)
- Config YAML files must be gitignored — the tool must create a `.gitignore` entry automatically
- SSH connections must use key-based authentication only — the tool must not support password-based SSH
- All web traffic must be HTTPS — HTTP must redirect to HTTPS
- MySQL must only accept local connections (no remote root access)

---

## 9. Technical Requirements

### 9.1 Language and Runtime

- Python 3.10 or higher
- PySide6 6.6 or higher
- Application launched by running: `python main.py`
- No command-line arguments required for normal operation

### 9.2 Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| PySide6 | >=6.6 | Desktop GUI framework (wizard, dashboard, log window) |
| paramiko | >=3.0 | SSH connection and remote command execution |
| pyyaml | >=6.0 | Config file read/write |
| dnspython | >=2.0 | DNS resolution check before SSL issuance |

### 9.3 File Structure

```
cbm-crm-deploy/
  main.py                 # Application entry point
  requirements.txt        # Python dependencies
  ui/
    welcome.py            # Welcome / environment selection screen
    wizard.py             # Setup Wizard (first run)
    dashboard.py          # Deployment Dashboard (subsequent runs)
    verification.py       # Verification results screen
  phases/
    phase1_hardening.py
    phase2_stack.py
    phase3_espocrm.py
    phase4_ssl.py
    phase5_verify.py
  config/
    cbm-crm-dev.yml       # Dev config (gitignored)
    cbm-crm-prod.yml      # Prod config (gitignored)
```

---

## 10. Out of Scope

- DigitalOcean Droplet provisioning (must be done manually or via DigitalOcean CLI)
- DNS record configuration
- EspoCRM application configuration (entity customizations, roles, workflows)
- Moodle or WordPress deployment (separate tools to be defined)
- Database backup and restore automation
- Monitoring and alerting setup

---

## 11. Open Questions

| # | Question | Status | Decision |
|---|----------|--------|----------|
| 1 | Should the tool support resuming from the last completed phase, or always restart from Phase 1? | Closed | On failure: cleanup failed phase, restart from Phase 1 |
| 2 | Should the tool create a non-root sudo user during server hardening? | Closed | Yes — create `cbmadmin` user in Phase 1; all subsequent phases run as `cbmadmin` |
| 3 | Should DigitalOcean automated backup verification be included (requires DO API key)? | Closed | Out of scope for v1.0 |

---

## 12. Revision History

| Version | Date | Author | Notes |
|---------|------|--------|-------|
| 0.1 | March 2026 | CBM / Claude | Initial draft |
| 0.2 | March 2026 | CBM / Claude | Added PySide6 GUI: Setup Wizard and Deployment Dashboard |
| 0.3 | March 2026 | CBM / Claude | Closed open questions: cleanup/restart behavior, cbmadmin user, DO backup verification |
