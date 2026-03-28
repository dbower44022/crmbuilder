# CRM Builder — Deployment Feature Context Summary

This document captures the decisions and rationale established during planning
for the EspoCRM deployment feature. Use it to orient Claude Code or any new
collaborator joining this work.

---

## What This Feature Is

The Deployment feature is an integrated part of **CRM Builder** — the existing
PySide6 desktop application (`espo_impl/`). It is not a separate tool.

CRM Builder already manages EspoCRM *application configuration* (fields,
layouts, relationships, data import) against running instances via the REST API.
The Deployment feature adds the step that comes before that: standing up a fresh
EspoCRM instance on a DigitalOcean Droplet from scratch, so the same tool covers
the full lifecycle from provisioning through configuration.

---

## Why Integrated, Not Separate

An earlier version of this PRD described a standalone application. That was
revised for the following reasons:

- A single tool is simpler for the administrator — one thing to install, one
  place to look
- Deployment is naturally tied to an instance profile — the selected instance
  in CRM Builder determines what gets deployed and where
- The existing CRM Builder codebase already provides the UI framework,
  pattern library, and project structure; building on it avoids duplication
- After deployment, CRM Builder can immediately connect to the new instance
  and begin deploying configuration — there is no hand-off between tools

---

## Hosting Architecture

### Provider: DigitalOcean
Selected over AWS, Hetzner, Vultr, and Linode. Key reasons:
- Best documentation ecosystem for self-hosted EspoCRM on Ubuntu
- Simplest UI and managed backup options for a non-developer admin
- Predictable flat-rate pricing with no hidden egress fees

### Two Environments Per Client
| Environment | Domain Convention | Droplet Size | Est. Cost |
|-------------|-------------------|--------------|-----------|
| Production | `crm.{client-domain}` | 2 vCPU / 4 GB / 80 GB SSD | ~$24/mo |
| Test / Staging | `crm-test.{client-domain}` | 1 vCPU / 2 GB / 50 GB SSD | ~$12/mo |

Both environments are built independently from the PRD as source of truth.
There is no data migration between Test and Production — they are completely
separate builds. Test is used to validate the deployment process and
EspoCRM configuration before touching Production.

### Domain Requirements
- A registered domain name is **required** for all deployments
- Bare IP deployments are not supported (Let's Encrypt requires a domain)
- The deployment tool does not configure DNS — the administrator must create
  a DNS A record pointing the subdomain to the Droplet IP before running the tool
- The tool validates DNS propagation before proceeding and before SSL issuance

---

## Installation Approach: Official EspoCRM Installer Script

The most important technical decision in this feature is how EspoCRM gets
installed on the server.

**Decision: use the official EspoCRM installer script.**

An earlier version of the PRD described manually installing a LAMP stack
(Nginx + PHP 8.2 + MySQL 8.0 + Certbot individually). That approach was
rejected because:

- It requires CRM Builder to maintain its own installation logic that will
  drift as EspoCRM evolves
- The official installer is the supported, tested, maintained path
- The official installer handles everything in one command — Docker, Nginx,
  MariaDB, EspoCRM, Let's Encrypt, cron — reducing the surface area of things
  that can go wrong

The official installer deploys EspoCRM as Docker containers (Nginx, MariaDB,
and EspoCRM via Docker Compose). CRM Builder's Phase 1 installs Docker on
the Droplet; Phase 2 runs the installer script with all configuration passed
as flags.

The installer is downloaded fresh each run to ensure the latest stable version:
```
wget -N https://github.com/espocrm/espocrm-installer/releases/latest/download/install.sh
sudo bash install.sh -y --ssl --letsencrypt \
  --domain={full_domain} \
  --email={letsencrypt_email} \
  --admin-username={admin_username} \
  --admin-password={admin_password} \
  --db-password={db_password} \
  --db-root-password={db_root_password}
```

---

## SSL / TLS Decisions

- **Let's Encrypt** is the standard SSL mode for all deployments — free,
  auto-renewing, fully handled by the EspoCRM installer
- **No compliance requirements** exist for the target customer base — Let's
  Encrypt is sufficient
- **No custom/commercial certificates** in v1.0
- **No bare IP / HTTP-only** for production or test environments
- Let's Encrypt auto-renewal is managed by the installer's built-in cron.
  CRM Builder additionally monitors certificate expiry and alerts the
  operator if the certificate is approaching expiry (in case auto-renewal
  has silently failed)
- Alert thresholds: warn at 30 days remaining, escalate at 14 days remaining

---

## UI Integration Decisions

### Deploy Panel in Main Window
A Deploy section is added to the CRM Builder main window. It is always
visible and its content is driven by the currently selected instance — the
same pattern used by the existing Program panel.

### No Separate Welcome Screen
The original PRD had a Welcome Screen where users chose "Dev" or "Production."
In the integrated design, environment selection is implicit — the user selects
an instance in the Instance Panel, and the Deploy panel acts on that instance.

### Setup Wizard as Modal Dialog
On first run (no deployment config for the selected instance), a **Set Up
Deployment** button appears. Clicking it opens a 6-step Setup Wizard as a
modal dialog, following the same visual pattern as `instance_dialog.py`.

### Deployment Dashboard Inline
On subsequent runs, the Deploy panel shows the Deployment Dashboard inline —
phase status cards, action buttons, log window, and certificate status.

---

## Server Architecture Decisions

### No cbmadmin User
The original PRD created a non-root `cbmadmin` user during server hardening.
This was removed in the integrated design because:

- The official EspoCRM installer script runs as root and manages its own
  Docker-based environment
- Adding a non-root user layer introduces complexity without benefit when
  using the Docker installer
- The Docker containers handle process isolation at a different level

All SSH operations connect as the configured SSH user (typically `root` for
a fresh DigitalOcean Droplet).

### Failure Behavior: Cleanup Then Restart from Phase 1
On any phase failure — clean up the failed phase's changes, then allow restart
from Phase 1. Resuming from an arbitrary mid-deployment phase risks leaving
the server in an unknown state. A clean restart from Phase 1 ensures a
known-good starting point.

Cleanup is **best-effort**: if a cleanup step fails, the tool logs it and
continues rather than halting. The user is notified of any incomplete steps.

---

## Configuration and File Structure

### DeployConfig Model
A new `DeployConfig` dataclass is added to `espo_impl/core/models.py`.
It is separate from `InstanceProfile` — an instance profile can exist without
a deploy config, and a deploy config can exist without the instance yet being
reachable (e.g. mid-deployment).

After successful deployment, Phase 3 updates the `InstanceProfile.url` field
to `https://{full_domain}` so CRM Builder can immediately connect to the new
instance. This is the only point where deploy config and instance profile
interact.

### Config Storage
Deployment configuration is stored as `{instance_slug}_deploy.json` in
`data/instances/`, alongside existing instance profile JSON files.
These files contain credentials and are gitignored.

The tool must verify that `data/instances/*_deploy.json` is covered by
`.gitignore` on first run.

### New Files
```
espo_impl/
├── core/
│   └── deploy_manager.py       # SSH execution, phase logic, config read/write
├── ui/
│   ├── deploy_panel.py         # Deploy section in main window
│   ├── deploy_wizard.py        # Setup Wizard modal (6 steps)
│   └── deploy_dashboard.py     # Deployment Dashboard (phases, log, cert status)
└── workers/
    └── deploy_worker.py        # QThread background worker for SSH phases
```

No new top-level directories. No changes to existing files except:
- `espo_impl/core/models.py` — add `DeployConfig` dataclass
- `espo_impl/ui/main_window.py` — add Deploy panel to layout
- `pyproject.toml` — add `paramiko` and `dnspython` dependencies
- `CLAUDE.md` — updated to describe the deployment feature

---

## What Is Out of Scope

- DigitalOcean Droplet provisioning (done manually before running the tool)
- DNS record configuration (done manually before running the tool)
- Data migration between environments
- WordPress or Moodle deployment (future work)
- Database backup and restore automation
- Monitoring and alerting beyond SSL expiry tracking
- Custom or commercial SSL certificates (v1.0)

---

## Key Documents

| Document | Location | Purpose |
|----------|----------|---------|
| Deployment PRD | `PRDs/CBM-PRD-CRM-Deploy.md` | Full feature requirements |
| This context doc | `PRDs/CBM-PRD-CRM-Deploy-Context.md` | Decision rationale |
| SSL/TLS Analysis | `PRDs/espocrm-ssl-tls-analysis.md` | SSL option analysis and decisions |
| Master PRD | `PRDs/crmbuilder-prd.md` | Overall CRM Builder product vision |
| CLAUDE.md | `CLAUDE.md` | Project guide for Claude Code |
