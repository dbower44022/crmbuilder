# Claude Code Prompt — EspoCRM Deployment Feature

## Context

CRM Builder is adding an EspoCRM Deployment feature that allows an
administrator to provision a fresh EspoCRM instance on a DigitalOcean
Droplet directly from the existing CRM Builder desktop application.

This is an integrated feature — not a separate tool. It adds a Deploy
panel to the main window and follows all existing CRM Builder patterns.

Read these files carefully before writing any code:

- `CLAUDE.md` — project guide and key patterns (read first)
- `PRDs/CBM-PRD-CRM-Deploy.md` — full feature requirements
- `PRDs/CBM-PRD-CRM-Deploy-Context.md` — decision rationale
- `espo_impl/core/models.py` — existing data models to extend
- `espo_impl/ui/main_window.py` — main window to modify
- `espo_impl/ui/instance_dialog.py` — modal dialog pattern to follow
- `espo_impl/ui/import_dialog.py` — multi-step wizard pattern to follow
- `espo_impl/workers/run_worker.py` — QThread worker pattern to follow
- `espo_impl/ui/output_panel.py` — log output panel to reference

---

## Overview of Changes

1. Add `DeployConfig` dataclass to `espo_impl/core/models.py`
2. Create `espo_impl/core/deploy_manager.py` — SSH execution and phase logic
3. Create `espo_impl/workers/deploy_worker.py` — QThread background worker
4. Create `espo_impl/ui/deploy_wizard.py` — six-step Setup Wizard modal
5. Create `espo_impl/ui/deploy_dashboard.py` — Deployment Dashboard widget
6. Create `espo_impl/ui/deploy_panel.py` — Deploy section for main window
7. Update `espo_impl/ui/main_window.py` — add Deploy panel to layout
8. Update `pyproject.toml` — add `paramiko` and `dnspython` dependencies

Implement in the order listed. Confirm with me after each task before
proceeding to the next.

---

## Task 1 — Add `DeployConfig` to `espo_impl/core/models.py`

Add the following dataclass to the end of `models.py`. Do not modify any
existing models.

```python
@dataclass
class DeployConfig:
    """Deployment configuration for an EspoCRM instance on DigitalOcean.

    Stored as {instance_slug}_deploy.json in data/instances/.
    Separate from InstanceProfile — an instance can exist without a deploy
    config, and a deploy config can exist while the instance is not yet
    reachable (e.g. mid-deployment).
    """

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

## Task 2 — Create `espo_impl/core/deploy_manager.py`

This module contains all business logic for deployment: SSH connection,
DNS validation, phase execution, and config file read/write. It has no
GUI dependencies.

### 2a — Config file read/write

```python
def load_deploy_config(instances_dir: Path, slug: str) -> DeployConfig | None:
    """Load deployment config for an instance. Returns None if not found."""

def save_deploy_config(instances_dir: Path, slug: str, config: DeployConfig) -> None:
    """Save deployment config for an instance."""
```

Config is stored as `{instances_dir}/{slug}_deploy.json`. Use the same
JSON serialisation pattern as existing instance profiles (`dataclasses.asdict`
for saving, manual construction for loading).

### 2b — DNS validation

```python
def check_dns(domain: str, expected_ip: str) -> tuple[bool, str]:
    """Check whether domain resolves to expected_ip.

    Returns (True, "") on success.
    Returns (False, message) on failure, where message is a plain-English
    description of the problem suitable for display in the UI.

    Uses dnspython for resolution.
    """
```

### 2c — SSH connection helper

```python
def connect_ssh(
    host: str,
    username: str,
    key_path: str,
) -> paramiko.SSHClient:
    """Open an SSH connection. Raises paramiko.SSHException on failure."""
```

Use key-based authentication only. Set a 30-second connection timeout.

### 2d — Remote command execution

```python
def run_remote(
    ssh: paramiko.SSHClient,
    command: str,
    log_callback: Callable[[str], None] | None = None,
) -> tuple[int, str]:
    """Execute a command on the remote server.

    Streams stdout and stderr line by line to log_callback if provided.
    Returns (exit_code, full_output).

    IMPORTANT: Never pass raw credential values in command strings.
    Mask passwords before calling log_callback:
        safe_cmd = command.replace(config.db_password, "[db_password]")
    """
```

### 2e — Deployment phases

Implement four phase functions. Each takes an open `SSHClient`, a
`DeployConfig`, and a `log_callback`. Each returns `(success: bool,
error_message: str)`.

```python
def phase1_server_prep(
    ssh: paramiko.SSHClient,
    config: DeployConfig,
    log_callback: Callable[[str], None],
) -> tuple[bool, str]:
    """Phase 1 — Server Preparation.

    - apt-get update && apt-get upgrade -y
    - Install Docker prerequisites: curl, ca-certificates, gnupg
    - Install Docker Engine and Docker Compose via Docker's official
      apt repository (https://docs.docker.com/engine/install/ubuntu/)
    - Configure 2 GB swap file at /swapfile
    - Open firewall ports 22, 80, 443 via ufw
    """

def phase2_install_espocrm(
    ssh: paramiko.SSHClient,
    config: DeployConfig,
    log_callback: Callable[[str], None],
) -> tuple[bool, str]:
    """Phase 2 — EspoCRM Installation.

    - Download installer:
        wget -N https://github.com/espocrm/espocrm-installer/releases/latest/download/install.sh
    - Run installer with all config flags:
        sudo bash install.sh -y --ssl --letsencrypt \\
          --domain={config.full_domain} \\
          --email={config.letsencrypt_email} \\
          --admin-username={config.admin_username} \\
          --admin-password={config.admin_password} \\
          --db-password={config.db_password} \\
          --db-root-password={config.db_root_password}
    - Log the masked version of this command (replace credential values
      with [placeholder] strings before passing to log_callback)
    - The installer handles Docker Compose setup, Nginx, MariaDB,
      EspoCRM, Let's Encrypt, and cron — do not do these manually
    """

def phase3_post_install(
    ssh: paramiko.SSHClient,
    config: DeployConfig,
    log_callback: Callable[[str], None],
) -> tuple[bool, str]:
    """Phase 3 — Post-Install Configuration.

    - Verify all three Docker containers are running:
        docker compose -f /var/www/espocrm/docker-compose.yml ps
      (expect: espocrm, espocrm-db, espocrm-nginx all 'Up')
    - Confirm cron entry exists:
        crontab -l | grep espocrm
    - Read SSL certificate expiry date:
        openssl s_client -connect {config.full_domain}:443 </dev/null 2>/dev/null \\
          | openssl x509 -noout -enddate
      Parse result and store in config.cert_expiry_date (ISO date string)
    - Returns the updated DeployConfig with cert_expiry_date populated
      (caller must save it)

    Note: Does NOT update InstanceProfile.url — that is done by the caller
    (deploy_worker) after this phase completes successfully, so the UI can
    handle the profile update on the main thread.
    """

def phase4_verify(
    ssh: paramiko.SSHClient,
    config: DeployConfig,
    log_callback: Callable[[str], None],
) -> tuple[bool, list[dict]]:
    """Phase 4 — Verification.

    Run all verification checks. Returns (overall_pass, results) where
    results is a list of dicts:
        [{"check": str, "passed": bool, "detail": str}, ...]

    Checks:
    - Docker containers running (docker compose ps — all Up)
    - HTTP redirect (curl -I http://{domain} → 301 or 302)
    - HTTPS response (curl -I https://{domain} → 200)
    - SSL certificate valid and >30 days remaining
    - EspoCRM login page present (curl https://{domain} contains 'EspoCRM')
    - Cron job configured (crontab -l contains espocrm)
    - DB connectivity (docker exec espocrm-db mysqladmin ping)
    """
```

### 2f — Cleanup helpers

```python
def cleanup_phase1(ssh: paramiko.SSHClient, log_callback: Callable[[str], None]) -> None:
    """Best-effort cleanup for a failed Phase 1."""

def cleanup_phase2(ssh: paramiko.SSHClient, log_callback: Callable[[str], None]) -> None:
    """Best-effort cleanup for a failed Phase 2.
    Run: docker compose down --volumes in /var/www/espocrm (if exists).
    Remove install.sh if present.
    """
```

Cleanup is best-effort: catch all exceptions, log failures, and continue.

### 2g — Certificate expiry check

```python
def get_cert_expiry(domain: str) -> str | None:
    """Check SSL certificate expiry for domain via openssl.
    Returns ISO date string (YYYY-MM-DD) or None on failure.
    Used for background refresh in the Deploy panel.
    """

def cert_days_remaining(expiry_date_str: str | None) -> int | None:
    """Return days until expiry, or None if expiry_date_str is None."""
```

---

## Task 3 — Create `espo_impl/workers/deploy_worker.py`

Follow the same QThread pattern as `run_worker.py` and `import_worker.py`.

The worker emits these signals:
```python
log_line = Signal(str, str)        # (message, level) where level is 'info'|'warning'|'error'
phase_started = Signal(int)        # phase number (1–4)
phase_completed = Signal(int)      # phase number
phase_failed = Signal(int, str)    # (phase number, error message)
dns_retry = Signal(int)            # seconds remaining in DNS timeout
deployment_finished = Signal(bool) # overall success
verify_results = Signal(list)      # list of check result dicts from phase4_verify
cert_expiry_updated = Signal(str)  # ISO date string, emitted after phase 3
```

The worker accepts a `DeployConfig`, an `InstanceProfile`, and an
`instances_dir` Path. It runs phases sequentially. Between Phase 1 and
Phase 2, it re-validates DNS. On phase failure it runs the appropriate
cleanup helper and emits `phase_failed`.

After Phase 3 succeeds, the worker emits `cert_expiry_updated` but does
NOT directly modify the `InstanceProfile` — the UI connects to this signal
and performs the URL update on the main thread.

A separate `CertCheckWorker` (in the same file) performs the background
certificate expiry refresh used by the Deploy panel on instance selection.
It accepts a domain string, calls `get_cert_expiry()`, and emits a single
`cert_expiry_result = Signal(str)` signal.

---

## Task 4 — Create `espo_impl/ui/deploy_wizard.py`

A six-step modal dialog following the pattern of `import_dialog.py`.
Use `QDialog` with a `QStackedWidget` for the steps. Back / Next / Cancel
buttons at the bottom of every step.

Steps:

| # | Title | Fields |
|---|-------|--------|
| 1 | Server Connection | Droplet IP (QLineEdit); SSH Key File (QLineEdit + Browse QPushButton using QFileDialog); SSH Username (QLineEdit, default `root`) |
| 2 | Domain | Base Domain (QLineEdit, placeholder `mycompany.com`); Subdomain (QLineEdit, default `crm`); Full Domain preview (read-only QLabel, updates live as user types, format: `{subdomain}.{base_domain}`) |
| 3 | Database | EspoCRM DB Password (QLineEdit, echoMode Password); MySQL Root Password (QLineEdit, echoMode Password, placeholder `Leave blank to auto-generate`) |
| 4 | EspoCRM Admin | Admin Username (QLineEdit, default `admin`); Admin Password (QLineEdit, echoMode Password); Admin Email (QLineEdit) |
| 5 | SSL / Let's Encrypt | Let's Encrypt Email (QLineEdit, helper text: `Used for certificate expiry notifications`) |
| 6 | Review & Confirm | Read-only summary of all values; passwords shown as `••••••••` with a Show/Hide toggle QPushButton; Back and **Save & Deploy** buttons |

On **Save & Deploy**: validate that all required fields are filled, save
the `DeployConfig` via `deploy_manager.save_deploy_config()`, emit a
`config_saved = Signal(DeployConfig)` signal, and close the dialog.

If `existing_config` is passed to the constructor, pre-populate all fields
(for Edit Configuration flow).

---

## Task 5 — Create `espo_impl/ui/deploy_dashboard.py`

A `QWidget` that displays for instances that have an existing `DeployConfig`.

### Environment Header

A `QGroupBox` showing:
- Instance name and full domain
- Droplet IP
- SSL certificate status badge (a `QLabel` with coloured text):
  - > 30 days: "● Valid (N days)" in green
  - 14–30 days: "● Expiring Soon (N days)" in yellow/orange
  - < 14 days: "● Critical — Renew Now (N days)" in red
  - Unknown: "● Unknown" in grey
- **Edit Configuration** button — opens `DeployWizard` pre-populated

### Phase Status Panel

Four `QFrame` cards in a `QVBoxLayout`. Each card shows:
- Phase name and one-line description
- Status indicator (coloured circle `QLabel`) **and** status text `QLabel`
  side by side — never colour alone

Status colours and labels:

| Status | Colour | Label |
|--------|--------|-------|
| Not Started | Grey | Not Started |
| In Progress | Blue | Running... |
| Completed | Green | Completed |
| Failed | Red | Failed — see log |

An expandable error detail area below each card (hidden unless failed):
shows the failed command and output.

### Action Buttons

- **Deploy All** (`QPushButton`) — starts all phases from Phase 1
- **Run Verification Only** (`QPushButton`) — runs Phase 4 only
- **Retry Failed Phase** (`QPushButton`) — enabled only when a phase is
  in Failed state; re-runs from the failed phase

### Log Window

A `QPlainTextEdit` (read-only) streaming live log output, consistent with
`OutputPanel`. Lines are colour-coded:
- White / default: info
- Yellow: warning
- Red: error

**Copy Log** and **Save Log to File** buttons above the log window.

The dashboard connects to `DeployWorker` signals to update phase cards and
stream log lines. All signal connections are made on the main thread.

---

## Task 6 — Create `espo_impl/ui/deploy_panel.py`

A `QWidget` that is always present in the main window and whose content
switches based on instance selection state.

Three states:

**No instance selected:**
```
QLabel: "Select an instance to manage its deployment."
```

**Instance selected, no deploy config:**
```
QLabel: "No deployment configured for this instance."
QPushButton: "Set Up Deployment"  → opens DeployWizard
```

**Instance selected, deploy config exists:**
```
DeployDashboard widget (fills the panel)
```

Expose a `set_instance(instance: InstanceProfile | None)` method that
`MainWindow` calls when the selected instance changes. On each call:
- Load or clear `DeployConfig` via `deploy_manager.load_deploy_config()`
- Switch to the appropriate state
- If config exists, trigger background `CertCheckWorker` and connect its
  `cert_expiry_result` signal to update the dashboard's cert status badge

---

## Task 7 — Update `espo_impl/ui/main_window.py`

Add the Deploy panel to the main window layout. Make minimal changes —
do not refactor existing layout code.

Specific changes:

1. Import `DeployPanel` from `espo_impl.ui.deploy_panel`
2. In `_build_ui()`, instantiate `DeployPanel` and add it to the main layout
   below the existing top section (instance panel + program panel + buttons)
   and above the output panel. Use a `QSplitter` or fixed section as
   appropriate to match the existing layout style.
3. Connect the `instance_panel.instance_selected` signal to
   `deploy_panel.set_instance` so the Deploy panel updates when the user
   selects a different instance.
4. After `DeployWizard` emits `config_saved`, also update the instance
   profile URL if it has changed (call the existing instance save logic).

Do not change any existing signal connections, button handlers, or
`UIState` logic.

---

## Task 8 — Update `pyproject.toml`

Add to the `dependencies` list:
```
"paramiko>=3.0",
"dnspython>=2.0",
```

---

## Implementation Notes

**Password masking in logs**
Before passing any SSH command string to `log_callback`, replace all
credential values with placeholder strings:
```python
safe = cmd
for val, label in [
    (config.db_password, "[db_password]"),
    (config.db_root_password, "[db_root_password]"),
    (config.admin_password, "[admin_password]"),
]:
    if val:
        safe = safe.replace(val, label)
log_callback(safe)
```

**DNS retry loop**
```python
timeout = 600  # 10 minutes
interval = 30
elapsed = 0
while elapsed < timeout:
    ok, msg = check_dns(config.full_domain, config.droplet_ip)
    if ok:
        break
    log_callback(f"DNS not ready: {msg}. Retrying in {interval}s "
                 f"({timeout - elapsed}s remaining)...")
    worker.dns_retry.emit(timeout - elapsed)
    time.sleep(interval)
    elapsed += interval
```

**Docker installation on Ubuntu 22.04**
Follow Docker's official apt repository method:
```bash
# Remove old versions
apt-get remove -y docker docker-engine docker.io containerd runc || true
# Add Docker GPG key
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
# Add repository
echo "deb [arch=$(dpkg --print-architecture) \
  signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | tee /etc/apt/sources.list.d/docker.list > /dev/null
# Install
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
```

**Gitignore check**
On first save of a deploy config, verify that `data/instances/*_deploy.json`
is present in `.gitignore`. If not, append it automatically.

**No cbmadmin user**
Do not create a non-root user. The official EspoCRM installer runs as root
and manages its own Docker-based environment. All SSH phases connect as the
configured `ssh_user` (typically `root` for a fresh Droplet).
