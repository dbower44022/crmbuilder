"""The self-healing certificate job — PI-571 (REQ-651).

The script itself runs on a server and is proven there by the product owner;
these tests hold what CRMBuilder controls: every value reaches the script
quoted, the script refuses to stop the CRM before a dry run passes, the job is
installed through standard input, and its status file is read safely.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from crmbuilder_v2.deploy import certificate_job as job


def test_script_quotes_every_value_and_keeps_the_dry_run_before_the_reinstall():
    script = job.render_script("crm.example.org", "ops@example.org", "203.0.113.7")
    assert "DOMAIN=crm.example.org" in script and "EXPECTED_IP=203.0.113.7" in script
    assert "EMAIL=ops@example.org" in script
    odd = job.render_script("crm.example.org", "o'neil@example.org", "203.0.113.7")
    assert "EMAIL='o'\"'\"'neil@example.org'" in odd
    dry = script.index("--dry-run")
    reinstall = script.index("bash install.sh -y --ssl --letsencrypt")
    assert dry < reinstall  # the CRM is only stopped after the test certificate passed
    assert "--clean" not in script  # the reinstall keeps the data
    assert script.index("waiting_dns") < dry  # DNS is checked before anything else
    assert 'rm -f "$CRON_FILE"' in script  # it removes its own schedule when done
    assert 'cp "$BACKUP" "$COMPOSE"' in script  # a failed reinstall is put back


def test_install_job_sends_the_script_and_schedule_through_standard_input():
    calls: list[tuple[str, str | None]] = []

    def fake_run_remote(_ssh, command, *_args, input_text=None, **_kwargs):
        calls.append((command, input_text))
        return 0, ""

    with patch.object(job, "run_remote", side_effect=fake_run_remote):
        ok, err = job.install_job(MagicMock(), "crm.example.org", "ops@example.org", "203.0.113.7",
                                  lambda *_a: None)
    assert (ok, err) == (True, "")
    assert "bind9-dnsutils" in calls[0][0]
    assert calls[1][0].startswith("mkdir -p /var/lib/crmbuilder && cat > " + job.SCRIPT_PATH)
    assert "DOMAIN=crm.example.org" in calls[1][1]
    assert calls[2][1] == f"*/15 * * * * root {job.SCRIPT_PATH} >> {job.JOB_LOG} 2>&1\n"


def test_install_job_reports_which_part_failed():
    with patch.object(job, "run_remote", side_effect=[(0, ""), (1, "")]):
        assert job.install_job(MagicMock(), "d.example.org", "e@x.org", "1.2.3.4", lambda *_a: None) == (
            False, "could not write the certificate job")


def test_read_status_parses_the_last_line_and_tolerates_nothing():
    line = '{"state": "waiting_dns", "detail": "no", "attempts": 0}'
    with patch.object(job, "run_remote", return_value=(0, "noise\n" + line)):
        assert job.read_status(MagicMock())["state"] == "waiting_dns"
    with patch.object(job, "run_remote", return_value=(1, "")):
        assert job.read_status(MagicMock()) is None
    with patch.object(job, "run_remote", return_value=(0, "not json")):
        assert job.read_status(MagicMock()) is None


def test_apply_domain_rewrites_both_values_then_uses_the_installers_command():
    seen: list[str] = []

    def fake_run_remote(_ssh, command, *_args, **_kwargs):
        seen.append(command)
        return 0, ""

    with patch.object(job, "run_remote", side_effect=fake_run_remote):
        assert job.apply_domain(MagicMock(), "crm.bbmentor.org", "crm.bbmentors.org",
                                lambda *_a: None) == (True, "")
    cmd = seen[0]
    assert r"NGINX_HOST: crm\.bbmentor\.org$/NGINX_HOST: crm.bbmentors.org/" in cmd
    assert "ESPOCRM_CONFIG_SITE_URL" in cmd and cmd.endswith("/var/www/espocrm/command.sh apply-domain")


def test_the_job_asks_the_dns_host_before_public_dns_when_the_zone_is_known():
    script = job.render_script("crm.example.org", "ops@example.org", "203.0.113.7", "example.org")
    assert "ZONE=example.org" in script
    assert script.index('dig +short +time=5 +tries=1 NS "$ZONE"') < script.index("@\"$resolver\"")
    assert "ZONE=''" in job.render_script("crm.example.org", "ops@example.org", "203.0.113.7")
