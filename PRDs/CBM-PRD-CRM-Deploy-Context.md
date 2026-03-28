# CRM Deployment Tool — Project Context Summary

This document captures the decisions and rationale established during the planning conversation that produced `CBM-PRD-CRM-Deploy.md`. Use it to orient Claude Code or any new collaborator joining this project.

---

## What This Tool Is

The CBM CRM Deployment Tool is a **PySide6 desktop application** that automates the end-to-end deployment of self-hosted EspoCRM instances on DigitalOcean. It is intended to be run by a CBM administrator (who may not be deeply technical) to stand up and verify EspoCRM on a fresh Ubuntu server.

It is a **separate application** from the existing `crmbuilder` EspoCRM configuration tool. Where `crmbuilder` manages EspoCRM *application configuration* (entities, fields, layouts via REST API), this tool manages *server-level infrastructure deployment* (Nginx, PHP, MySQL, EspoCRM installation, SSL).

---

## Hosting Architecture Decisions

### Provider: DigitalOcean
Selected over AWS, Hetzner, Vultr, and Linode. Key reasons:
- Best documentation ecosystem for self-hosted EspoCRM on Ubuntu
- Simplest UI and managed backup options for a non-developer admin
- Predictable flat-rate pricing with no hidden egress fees (unlike AWS Lightsail)
- Price premium over Hetzner/Vultr is small (~$10–15/mo) and worth the operational simplicity

### Two Environments
| Environment | Domain | Droplet Size | Est. Cost |
|-------------|--------|--------------|-----------|
| Production | crm.clevelandbusinessmentors.org | 2 vCPU / 4GB / 80GB SSD | ~$24/mo |
| Dev/Test | dev-crm.clevelandbusinessmentors.org | 1 vCPU / 2GB / 50GB SSD | ~$12/mo |

**Total: ~$36/mo for CRM hosting alone.**

### Broader Architecture Context
CBM's full stack will eventually include WordPress and Moodle alongside EspoCRM. The planned hosting architecture is:
- **Server 1 (Prod):** EspoCRM + WordPress co-hosted (2 vCPU / 4GB)
- **Server 2 (Prod):** Moodle standalone (2 vCPU / 4GB)
- **Server 3 (Dev):** EspoCRM + WordPress co-hosted (1 vCPU / 2GB)
- **Server 4 (Dev):** Moodle standalone (1 vCPU / 2GB)

The deployment tool currently covers **EspoCRM only**. WordPress and Moodle deployment tools are future work. Droplet sizing already accounts for eventual WordPress co-hosting.

### Database: MySQL 8.0 (not PostgreSQL)
PostgreSQL was considered but rejected. EspoCRM is built primarily against MySQL/MariaDB — PostgreSQL is a secondary target with less community documentation and support. MySQL is the safe choice at CBM's scale.

---

## Application Design Decisions

### GUI: PySide6 Hybrid — Wizard + Dashboard
The tool uses a two-mode GUI:
- **Setup Wizard** on first run — walks users through configuration step by step
- **Deployment Dashboard** on subsequent runs — shows phase status, live log output, action buttons

This was chosen because target users may not be comfortable with the command line. The GUI must be accessible to non-technical administrators.

### Invocation
```
python main.py
```
No CLI arguments required for normal operation.

### Configuration Persistence
- First run: collect all config interactively via the Setup Wizard
- Save to `config/cbm-crm-dev.yml` or `config/cbm-crm-prod.yml`
- Subsequent runs: load from saved config with option to edit
- Config files contain credentials — must be gitignored automatically by the tool

### SSH Architecture
- Tool runs **locally** on administrator's machine
- Connects to Droplet **remotely via SSH** using Paramiko
- No code is permanently installed on the server
- All remote commands executed via SSH

---

## Deployment Phase Decisions

### Phase 1: Server Hardening — cbmadmin User
**Decision:** Create a non-root sudo user named `cbmadmin` during Phase 1.

Rationale:
- Running everything as root is dangerous — a single bad command can destroy the server
- EspoCRM/Nginx documentation assumes a non-root sudo user
- Easier to grant access to a second admin without sharing root credentials

The tool connects initially as `root`, creates `cbmadmin`, copies SSH keys, disables root SSH login, then **reconnects as `cbmadmin`** for all subsequent phases. Every sudo command in phases 2–5 runs via `cbmadmin`.

### Failure Behavior: Cleanup Then Restart from Phase 1
**Decision:** On any phase failure — clean up the failed phase, then restart from Phase 1.

Rationale: Resuming mid-deployment from an arbitrary phase risks leaving the server in a partially-configured state. A clean restart from Phase 1 ensures a known-good starting point every time.

Cleanup is **best-effort** — if a cleanup step fails, the tool logs it and continues rather than halting. The user is notified of any incomplete cleanup steps.

Cleanup actions per phase are specified in Section 7.2 of the PRD.

### Phase 5: Verification
Verification is **read-only** — no cleanup required on failure. It runs 10 checks covering services, HTTP/HTTPS responses, SSL validity, cron, MySQL connectivity, and EspoCRM daemon.

---

## What Each Environment Is For

**Both environments are built independently from the PRD as source of truth.** There is no data migration between Dev and Production — they are completely separate builds.

- **Dev/Test:** Build and validate the deployment process and EspoCRM configuration before touching Production
- **Production:** Final live environment; built after Dev/Test validates cleanly

The EspoCRM Cloud trial instance (used for early development) is decommissioned once Production is live.

---

## Out of Scope for This Tool

- DigitalOcean Droplet provisioning (done manually or via DO CLI before running the tool)
- DNS record configuration (done manually in DNS provider)
- EspoCRM application configuration — that is `crmbuilder`'s job
- WordPress or Moodle deployment (separate future tools)
- Database backup/restore automation
- Monitoring and alerting
- DigitalOcean backup verification via API (deferred to future version)

---

## File Locations

| File | Location |
|------|----------|
| PRD (Markdown) | `PRDs/CBM-PRD-CRM-Deploy.md` |
| PRD (Word) | `PRDs/CBM-PRD-CRM-Deploy.docx` |
| This context doc | `PRDs/CBM-PRD-CRM-Deploy-Context.md` |
| Application code (to be built) | `cbm-crm-deploy/` (root of repo or subfolder TBD) |

---

## Suggested Claude Code Opening Prompt

When starting a Claude Code session to build this tool, use:

> "Please build the CBM CRM Deployment Tool as specified in `PRDs/CBM-PRD-CRM-Deploy.md`. Before writing any code, read that file fully. Also read `PRDs/CBM-PRD-CRM-Deploy-Context.md` for decision rationale and architecture context. Start by creating the project structure and `main.py` entry point, then implement the UI screens before the deployment phases."
