# CRM Builder — EspoCRM Deployment Implementation Reference

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026
**Requirements:** PRDs/CBM-PRD-CRM-Deploy.md, PRDs/CBM-PRD-CRM-Deploy-Context.md
**Maintained By:** Claude Code

---

## 1. Purpose

This document describes the implementation of the EspoCRM deployment
feature in CRM Builder — provisioning a fresh EspoCRM instance on a
DigitalOcean Droplet via SSH, using the official EspoCRM installer script
(Docker-based).

---

## 2. File Locations

```
espo_impl/core/deploy_manager.py       # SSH execution, phase logic, config I/O
espo_impl/core/models.py               # DeployConfig dataclass
espo_impl/workers/deploy_worker.py     # DeployWorker + CertCheckWorker (QThread)
espo_impl/ui/deploy_wizard.py          # Six-step Setup Wizard modal dialog
espo_impl/ui/deploy_dashboard.py       # Phase cards, log window, cert badge
espo_impl/ui/deploy_panel.py           # Context-switching panel in main window
```

---

## 3. Data Model

```python
@dataclass
class DeployConfig:
    droplet_ip: str              # DigitalOcean Droplet IPv4
    ssh_key_path: str            # Path to SSH private key file
    ssh_user: str                # SSH username (typically "root")
    base_domain: str             # e.g., "mycompany.com"
    subdomain: str               # e.g., "crm" or "crm-test"
    letsencrypt_email: str       # Email for Let's Encrypt notifications
    db_password: str             # EspoCRM database password
    db_root_password: str        # MariaDB root password
    admin_username: str          # EspoCRM admin username
    admin_password: str          # EspoCRM admin password
    admin_email: str             # EspoCRM admin email
    cert_expiry_date: str | None # SSL cert expiry (YYYY-MM-DD), set by Phase 3
    deployed_at: str | None      # ISO 8601 timestamp of last deployment

    full_domain -> str           # Property: "{subdomain}.{base_domain}"
```

**Storage:** `data/instances/{instance_slug}_deploy.json`

Separate from `InstanceProfile` — an instance can exist without a deploy
config, and a deploy config can exist while the instance is not yet
reachable (mid-deployment).

---

## 4. Deploy Manager (`core/deploy_manager.py`)

### 4.1 Config Read/Write

```python
def load_deploy_config(instances_dir: Path, slug: str) -> DeployConfig | None
def save_deploy_config(instances_dir: Path, slug: str, config: DeployConfig) -> None
```

Uses `dataclasses.asdict()` for serialisation, manual `DeployConfig(**data)`
for deserialisation. Files are gitignored via `data/instances/*.json`.

### 4.2 DNS Validation

```python
def check_dns(domain: str, expected_ip: str) -> tuple[bool, str]
```

Uses `dnspython` to resolve the domain's A record and compare against the
expected Droplet IP. Returns `(True, "")` on match, `(False, message)` on
failure with a plain-English description including the domain and resolved IPs.

### 4.3 SSH Connection

```python
def connect_ssh(host: str, username: str, key_path: str) -> paramiko.SSHClient
```

Key-based authentication only. 30-second connection timeout. Uses
`AutoAddPolicy` for host key verification.

### 4.4 Remote Command Execution

```python
def run_remote(
    ssh: paramiko.SSHClient,
    command: str,
    log_callback: Callable[[str], None] | None = None,
    get_pty: bool = False,
) -> tuple[int, str]
```

Streams stdout and stderr line-by-line to `log_callback`. The `get_pty`
parameter requests a pseudo-terminal — required for the EspoCRM installer
script which checks for a TTY.

### 4.5 Credential Masking

```python
def mask_credentials(command: str, config: DeployConfig) -> str
```

Replaces password values with `[placeholder]` strings before logging.
Sorts replacements by length (longest first) to prevent substring
collisions when one password is a prefix of another.

```python
# Masking order: longest value first
replacements.sort(key=lambda x: len(x[0]), reverse=True)
```

---

## 5. Deployment Phases

### Phase 1 — Server Preparation

1. `apt-get update && apt-get upgrade -y`
2. Install Docker prerequisites: `curl`, `ca-certificates`, `gnupg`
3. Install Docker Engine via Docker's official apt repository
   (https://docs.docker.com/engine/install/ubuntu/)
4. Configure 2 GB swap file at `/swapfile`
5. Open firewall ports 22, 80, 443 via `ufw`

### Phase 2 — EspoCRM Installation

1. Download installer:
   `wget -N https://github.com/espocrm/espocrm-installer/releases/latest/download/install.sh`
2. Run installer with all config flags:
   ```
   sudo bash install.sh -y --clean --ssl --letsencrypt \
     --domain={full_domain} --email={letsencrypt_email} \
     --admin-username={admin_username} --admin-password={admin_password} \
     --db-password={db_password} --db-root-password={db_root_password}
   ```
3. The `--clean` flag handles retries after a previous failed attempt
4. The installer command is run with `get_pty=True` (TTY required)
5. Credential values are masked in all log output

The installer handles Docker Compose setup, Nginx, MariaDB, EspoCRM,
Let's Encrypt certificate issuance, and cron — CRM Builder does not
install any of these manually.

### Phase 3 — Post-Install Configuration

1. Verify Docker containers running via `docker compose ps`
   (expects: espocrm, espocrm-daemon, espocrm-db, espocrm-nginx, espocrm-websocket)
2. Confirm cron entry: `crontab -l | grep espocrm`
3. Read SSL certificate expiry via `openssl s_client`
4. Set `config.cert_expiry_date` and `config.deployed_at`
5. Save updated config to JSON

**Important:** Phase 3 does NOT update `InstanceProfile.url`. The
`cert_expiry_updated` signal is emitted, and `MainWindow._on_cert_expiry_updated()`
handles the URL update on the main thread.

### Phase 4 — Verification

Seven checks, each returns pass/fail with detail:

| Check | Command | Pass Condition |
|-------|---------|---------------|
| Docker containers | `docker compose ps` | `espocrm` in output |
| HTTP redirect | `curl -sI http://{domain}` | 301 or 302 |
| HTTPS response | `curl -sI https://{domain}` | 200 |
| SSL certificate | `openssl s_client ... -dates` | `notAfter` present |
| EspoCRM login page | `curl -sL https://{domain}` | `EspoCRM` in HTML |
| Cron job | `crontab -l \| grep espocrm` | exit code 0 |
| Database connectivity | `docker compose ps \| grep -iE 'mysql\|mariadb\|espocrm-db'` | `Up` in output |

---

## 6. Cleanup Helpers

```python
def cleanup_phase1(ssh, log_callback) -> None
def cleanup_phase2(ssh, log_callback) -> None
```

Best-effort: catch all exceptions, log failures, continue. Phase 2
cleanup runs `docker compose down --volumes` in `/var/www/espocrm`
and removes `install.sh`.

---

## 7. Certificate Expiry Helpers

```python
def get_cert_expiry(domain: str) -> str | None
```

Uses Python's `ssl` module to connect to the domain on port 443 and
read the certificate's `notAfter` date. Returns ISO date `YYYY-MM-DD`
or `None` on failure.

```python
def cert_days_remaining(expiry_date_str: str | None) -> int | None
```

Returns days remaining (negative if expired), or `None`.

---

## 8. Deploy Worker (`workers/deploy_worker.py`)

### 8.1 DeployWorker

Follows the same QThread pattern as `RunWorker` and `ImportWorker`.

**Signals:**

| Signal | Type | When |
|--------|------|------|
| `log_line` | `(str, str)` | Every log line (message, level) |
| `phase_started` | `(int,)` | Phase N begins |
| `phase_completed` | `(int,)` | Phase N succeeds |
| `phase_failed` | `(int, str)` | Phase N fails (phase, error) |
| `dns_retry` | `(int,)` | DNS retry (seconds remaining) |
| `deployment_finished` | `(bool,)` | Overall completion |
| `verify_results` | `(list,)` | Phase 4 check results |
| `cert_expiry_updated` | `(str,)` | Cert expiry date after Phase 3 |

**DNS Retry Loop:**

Before Phase 1 and again before Phase 2, DNS is validated with a 30-second
retry interval and 10-minute timeout:

```python
while elapsed < 600:
    ok, msg = check_dns(domain, ip)
    if ok: break
    sleep(30)
    elapsed += 30
```

**Phase Failure:**

On failure, the appropriate cleanup helper runs, `phase_failed` is emitted,
and the worker stops. The dashboard shows the error detail and enables
Retry Failed Phase.

### 8.2 CertCheckWorker

Lightweight QThread for background certificate expiry refresh. Used by
`DeployPanel` when an instance with a deploy config is selected.

```python
class CertCheckWorker(QThread):
    cert_expiry_result = Signal(str)  # ISO date string

    def run(self):
        result = get_cert_expiry(self.domain)
        if result:
            self.cert_expiry_result.emit(result)
```

---

## 9. UI Components

### 9.1 Deploy Wizard (`ui/deploy_wizard.py`)

Six-step `QDialog` with `QStackedWidget`:

| Step | Title | Key Fields |
|------|-------|------------|
| 1 | Server Connection | Droplet IP, SSH Key File (Browse), SSH Username (default `root`) |
| 2 | Domain | Base Domain, Subdomain (default `crm`), live full-domain preview |
| 3 | Database | DB Password, MariaDB Root Password (auto-generate if blank) |
| 4 | EspoCRM Admin | Username (default `admin`), Password, Email |
| 5 | SSL / Let's Encrypt | Email for certificate notifications |
| 6 | Review & Confirm | Read-only summary, Show/Hide passwords toggle |

On **Save & Deploy**: validates all required fields, saves `DeployConfig`,
emits `config_saved` signal, closes. If MariaDB root password is left blank,
auto-generates via `secrets.token_urlsafe(16)`.

Supports edit mode — pass `existing_config` to pre-populate all fields.

### 9.2 Deploy Dashboard (`ui/deploy_dashboard.py`)

**Environment Header:**
- Instance name, full domain, Droplet IP
- SSL certificate badge:
  - `> 30 days` → green "Valid (N days)"
  - `14–30 days` → yellow "Expiring Soon (N days)"
  - `< 14 days` → red "Critical — Renew Now (N days)"
  - Unknown → grey "Unknown"

**Phase Cards:**
Four `PhaseCard` widgets with coloured status indicators:

| Status | Colour | Label |
|--------|--------|-------|
| Not Started | Grey | Not Started |
| In Progress | Blue | Running... |
| Completed | Green | Completed |
| Failed | Red | Failed — see log |

Failed cards show expandable error detail.

**Action Buttons:**
- Deploy All — runs Phase 1–4
- Run Verification Only — runs Phase 4 only
- Retry Failed Phase — resumes from the failed phase

**Log Window:**
Colour-coded `QTextEdit` (info=white, warning=yellow, error=red).
Copy Log and Save Log to File buttons.

### 9.3 Deploy Panel (`ui/deploy_panel.py`)

Context-switching `QWidget` with three states:

| State | Condition | Display |
|-------|-----------|---------|
| 0 | No instance selected | "Select an instance..." |
| 1 | Instance selected, no config | "No deployment configured..." + Set Up button |
| 2 | Instance selected, config exists | `DeployDashboard` |

`set_instance(profile)` is called by `MainWindow` on instance selection.
On state 2, triggers background `CertCheckWorker`.

---

## 10. Main Window Integration

Changes to `ui/main_window.py`:

1. `DeployPanel` added between top section and output panel
2. `instance_selected` connected to `deploy_panel.set_instance()`
3. `_on_cert_expiry_updated(expiry_date)` — updates deploy config,
   saves it, updates instance profile URL to `https://{full_domain}`,
   refreshes cert badge. **Runs on main thread** via Qt signal/slot.
4. `_on_deploy_config_saved(config)` — refreshes deploy panel

The instance profile URL is updated only here — never inside
`deploy_worker.py` or `deploy_manager.py`.

---

## 11. Instance Panel Filter

`instance_panel._load_instances()` skips files where `path.stem`
ends with `_deploy` to avoid parsing deploy config JSON as instance
profiles.

---

## 12. Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| paramiko | >= 3.0 | SSH client for remote command execution |
| dnspython | >= 2.0 | DNS A record resolution |

---

## 13. Test Coverage

Tests in `tests/test_deploy_manager.py`:

| Category | Tests | What's Covered |
|----------|-------|---------------|
| DeployConfig model | 3 | `full_domain` for production, test, standard configs |
| Config read/write | 4 | Round-trip, missing file, file creation, slug filename |
| DNS validation | 5 | Match, mismatch, NXDOMAIN, domain in message, IPs in message |
| Password masking | 5 | Each credential type, non-credential text, empty passwords |
| Certificate expiry | 4 | Future date, past date, None input, correct calculation |

SSH phase functions are not unit-tested — they require a live server and
are validated by manual integration testing against a real Droplet.

---

## 14. Security Notes

- All passwords are masked in log output — never displayed in plaintext
- Deploy config files are gitignored (`data/instances/*.json`)
- SSH uses key-based authentication only — no password auth
- SSL is always Let's Encrypt — no HTTP-only or custom certificates
- The `--clean` flag on the installer handles retries safely
- No non-root user created — Docker containers handle process isolation
