"""The self-healing job that finishes a server's certificate — PI-571 (REQ-651).

When a deploy ends before the web address points at the server, the CRM is
installed in the EspoCRM installer's plain web mode and this job is left on
the server. Every fifteen minutes it:

1. checks that public resolvers return the server's own address for the web
   address, and stops there if not;
2. asks Let's Encrypt for a *test* certificate (a dry run that issues nothing),
   answering the challenge from the running CRM's public folder, and stops
   there if that fails, keeping the reason;
3. only then runs the EspoCRM installer again in its Let's Encrypt mode. On an
   existing installation, without ``--clean``, the installer reinstalls in
   place: it keeps the database and files, reads the existing passwords, and
   obtains the certificate;
4. removes its own schedule once the certificate is in place.

Step 3 is the only one that stops the CRM, and it runs only after the dry run
has passed. If the installer fails anyway, the job puts the plain web setup
back and starts it again, so the CRM is not left stopped; after three such
failures it stops trying and says so.

Every run writes ``STATUS_FILE`` (one JSON object) so CRMBuilder can read what
happened over SSH. These facts about the installer were read from its source,
version 2.8.1, on 09-23-26; the job itself has not yet run on a live server.
"""

from __future__ import annotations

import json
import shlex
from typing import Any

from crmbuilder_v2.deploy.ssh import Log, run_remote

SCRIPT_PATH = "/usr/local/sbin/crmbuilder-certificate-check"
CRON_PATH = "/etc/cron.d/crmbuilder-certificate-check"
STATUS_FILE = "/var/lib/crmbuilder/certificate-status.json"
JOB_LOG = "/var/log/crmbuilder-certificate-check.log"
HOME_DIRECTORY = "/var/www/espocrm"

#: What the status file's ``state`` means, in plain words.
STATE_TEXT: dict[str, str] = {
    "waiting_dns": "Waiting for DNS: the web address does not point at this server yet.",
    "test_failed": "DNS is correct, but Let's Encrypt's test request failed.",
    "installing": "DNS is correct and the test passed; the certificate is being installed.",
    "done": "The certificate is installed and the CRM is secure.",
    "failed_restored": "Installing the certificate failed; the CRM was put back as it was.",
    "gave_up": "Installing the certificate failed three times; the job has stopped.",
}

_SCRIPT = r"""#!/bin/bash
# CRMBuilder self-healing certificate job. Installed by a CRMBuilder deploy
# run; removes its own schedule once the certificate is in place.
set -u
DOMAIN=__DOMAIN__
EMAIL=__EMAIL__
EXPECTED_IP=__IP__
HOME_DIR=__HOME__
STATUS_FILE=__STATUS__
CRON_FILE=__CRON__
STATE_DIR=$(dirname "$STATUS_FILE")
WEBROOT="$HOME_DIR/data/espocrm/ephemeral/public"
COMPOSE="$HOME_DIR/docker-compose.yml"
BACKUP="$STATE_DIR/docker-compose.http.yml"
ATTEMPTS_FILE="$STATE_DIR/certificate-attempts"
mkdir -p "$STATE_DIR"

exec 9>/run/crmbuilder-certificate-check.lock
flock -n 9 || exit 0

status() {
  # status STATE DETAIL
  python3 - "$1" "$2" "$STATUS_FILE" <<'PY'
import json, sys, datetime
state, detail, path = sys.argv[1], sys.argv[2], sys.argv[3]
attempts = 0
try:
    attempts = int(open(path.rsplit("/", 1)[0] + "/certificate-attempts").read().strip() or 0)
except Exception:
    pass
json.dump({"state": state, "detail": detail[-1500:], "attempts": attempts,
           "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat()},
          open(path, "w"))
PY
  echo "$(date -u +%FT%TZ) $1: $2"
}

finish() {
  rm -f "$CRON_FILE"
  status done "$1"
  exit 0
}

if grep -q "MODE: letsencrypt" "$COMPOSE" 2>/dev/null && \
   [ -f "$HOME_DIR/data/nginx/ssl/live/$DOMAIN/fullchain.pem" ]; then
  finish "The certificate for $DOMAIN is in place."
fi

attempts=$(cat "$ATTEMPTS_FILE" 2>/dev/null || echo 0)
if [ "$attempts" -ge 3 ]; then
  rm -f "$CRON_FILE"
  status gave_up "Installing the certificate failed three times. See $0's log, then run it by hand once the cause is fixed: rm $ATTEMPTS_FILE && $0"
  exit 1
fi

# 1. Does public DNS return this server's address?
seen=$(for resolver in 1.1.1.1 8.8.8.8; do
  dig +short +time=5 +tries=1 A "$DOMAIN" @"$resolver"
done | sort -u | tr '\n' ' ')
if ! echo " $seen " | grep -q " $EXPECTED_IP "; then
  status waiting_dns "Public DNS returns ${seen:-nothing }for $DOMAIN; it must return $EXPECTED_IP."
  exit 0
fi
if [ -n "$(dig +short +time=5 +tries=1 AAAA "$DOMAIN" @1.1.1.1)" ]; then
  status waiting_dns "$DOMAIN also has an IPv6 (AAAA) record. Delete it at the DNS host; the certificate check would go there."
  exit 0
fi

# 2. A dry run: Let's Encrypt's test service, answered from the running CRM.
mkdir -p "$STATE_DIR/certbot-test"
if ! out=$(docker run --rm \
    -v "$WEBROOT:/var/www/certbot" \
    -v "$STATE_DIR/certbot-test:/etc/letsencrypt" \
    certbot/certbot certonly --webroot -w /var/www/certbot --dry-run \
    --non-interactive --agree-tos --no-eff-email --email "$EMAIL" -d "$DOMAIN" 2>&1); then
  status test_failed "Let's Encrypt's test request failed: $(echo "$out" | tail -8 | tr '\n' ' ')"
  exit 0
fi

# 3. The real certificate, through the installer's data-keeping reinstall.
status installing "DNS is correct and the test passed; installing the certificate."
cp "$COMPOSE" "$BACKUP"
cd /root
wget -q -N https://github.com/espocrm/espocrm-installer/releases/latest/download/install.sh
if out=$(bash install.sh -y --ssl --letsencrypt --domain="$DOMAIN" --email="$EMAIL" 2>&1) && \
   [ -f "$HOME_DIR/data/nginx/ssl/live/$DOMAIN/fullchain.pem" ]; then
  rm -f "$ATTEMPTS_FILE"
  finish "The certificate for $DOMAIN is installed and the CRM now uses https."
fi
echo $((attempts + 1)) > "$ATTEMPTS_FILE"
if ! grep -q "MODE: letsencrypt" "$COMPOSE" 2>/dev/null; then
  cp "$BACKUP" "$COMPOSE"
  docker compose -f "$COMPOSE" up -d >/dev/null 2>&1
fi
status failed_restored "The installer failed; the plain web setup was put back. Installer output: $(echo "$out" | tail -8 | tr '\n' ' ')"
exit 1
"""


def render_script(domain: str, email: str, expected_ip: str) -> str:
    """The job's shell script, with every value quoted for the shell."""
    values = {
        "__DOMAIN__": domain,
        "__EMAIL__": email,
        "__IP__": expected_ip,
        "__HOME__": HOME_DIRECTORY,
        "__STATUS__": STATUS_FILE,
        "__CRON__": CRON_PATH,
    }
    script = _SCRIPT
    for placeholder, value in values.items():
        script = script.replace(placeholder, shlex.quote(value))
    return script


def cron_line() -> str:
    return f"*/15 * * * * root {SCRIPT_PATH} >> {JOB_LOG} 2>&1\n"


def install_job(ssh, domain: str, email: str, expected_ip: str, log: Log) -> tuple[bool, str]:
    """Put the job and its fifteen-minute schedule on the server.

    The script and schedule go in through standard input, so no value is
    interpreted by a remote shell on the way. ``dig`` comes from the
    ``bind9-dnsutils`` package, installed here if missing.
    """
    code, _ = run_remote(
        ssh,
        "command -v dig >/dev/null || apt-get -o DPkg::Lock::Timeout=600 install -y bind9-dnsutils",
        log,
    )
    if code != 0:
        return False, "could not install the DNS lookup tool (bind9-dnsutils)"
    code, _ = run_remote(
        ssh,
        f"mkdir -p /var/lib/crmbuilder && cat > {SCRIPT_PATH} && chmod 0755 {SCRIPT_PATH}",
        input_text=render_script(domain, email, expected_ip),
    )
    if code != 0:
        return False, "could not write the certificate job"
    code, _ = run_remote(ssh, f"cat > {CRON_PATH} && chmod 0644 {CRON_PATH}", input_text=cron_line())
    if code != 0:
        return False, "could not schedule the certificate job"
    log("Installed the self-healing certificate job; it checks every 15 minutes.", "info")
    return True, ""


def run_job_now(ssh, log: Log | None = None, *, background: bool = False) -> None:
    """Run the job once, now — waiting for it, or leaving it to finish alone."""
    if background:
        run_remote(ssh, f"nohup {SCRIPT_PATH} >> {JOB_LOG} 2>&1 </dev/null &")
    else:
        run_remote(ssh, f"{SCRIPT_PATH} >> {JOB_LOG} 2>&1; tail -3 {JOB_LOG}", log)


def read_status(ssh) -> dict[str, Any] | None:
    """The job's last outcome, or ``None`` when it has not run on this server."""
    code, output = run_remote(ssh, f"cat {STATUS_FILE} 2>/dev/null")
    if code != 0 or not output.strip():
        return None
    try:
        data = json.loads(output.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return None
    return data if isinstance(data, dict) else None


def apply_domain(ssh, old_domain: str, new_domain: str, log: Log) -> tuple[bool, str]:
    """Point an installed CRM at a corrected web address (plain web mode).

    The installer keeps the address in its container definition (the web
    server's host name and the CRM's site address); both are rewritten, then
    the installer's own ``apply-domain`` command rebuilds the containers.
    """
    compose = f"{HOME_DIRECTORY}/docker-compose.yml"
    old_q, new_q = old_domain.replace(".", r"\."), new_domain
    command = (
        f"sed -i -e 's/NGINX_HOST: {old_q}$/NGINX_HOST: {new_q}/' "
        f"-e 's#ESPOCRM_CONFIG_SITE_URL: \"\\(https\\?\\)://{old_q}\"#ESPOCRM_CONFIG_SITE_URL: \"\\1://{new_q}\"#' "
        f"{shlex.quote(compose)} && grep -q {shlex.quote('NGINX_HOST: ' + new_domain)} {shlex.quote(compose)} "
        f"&& {HOME_DIRECTORY}/command.sh apply-domain"
    )
    log(f"Changing the installed CRM's web address from {old_domain} to {new_domain}", "info")
    code, _ = run_remote(ssh, command, log)
    if code != 0:
        return False, f"could not change the installed CRM's web address (exit {code})"
    return True, ""


def read_certificate_expiry(ssh, domain: str) -> str | None:
    """The installed certificate's expiry date (``YYYY-MM-DD``), or ``None``."""
    from datetime import datetime

    from crmbuilder_v2.deploy.ssh import certificate_paths

    for path in certificate_paths(domain):
        code, output = run_remote(ssh, f"openssl x509 -in {shlex.quote(path)} -noout -enddate")
        if code == 0 and "notAfter=" in output:
            text = output.split("notAfter=")[-1].strip()
            try:
                return datetime.strptime(text, "%b %d %H:%M:%S %Y %Z").strftime("%Y-%m-%d")
            except ValueError:
                return None
    return None
