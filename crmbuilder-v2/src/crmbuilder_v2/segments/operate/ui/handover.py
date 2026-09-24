"""The handover sheet — PI-571 (REQ-652).

The page the operator saves and gives to the client at the end of a deploy.
It is built from the deploy run alone (plus the administrator password when
the wizard that queued the run still holds it), so it can be produced again
later from Deploy History.

Every instruction is written as where to go, what to do, what should happen,
and what to do if it does not. The DNS instructions name the client's own DNS
host and the exact record, taken from the run's DNS diagnosis.
"""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any

#: Symptom, likely cause, fix — the troubleshooting list on every sheet.
TROUBLESHOOTING: tuple[tuple[str, str, str], ...] = (
    (
        "The address does not open at all, hours after the record was added.",
        "The record was added at a DNS host the internet does not use for this "
        "domain, or under the wrong name.",
        "Check which company's name servers the domain uses (the registrar shows "
        "them) and add the record there. In the name box type only the part before "
        "the domain, for example crm, not the whole address.",
    ),
    (
        "The address opens someone else's site, or an old page.",
        "An older record for the same name is still in place.",
        "Delete every other A, AAAA or CNAME record for that name, so only the new "
        "A record remains.",
    ),
    (
        "The address works but the browser warns the site is not secure.",
        "The certificate has not been issued yet. It follows within 15 minutes of "
        "DNS being correct.",
        "Wait 15 minutes. If the warning stays, ask your CRMBuilder contact to press "
        "Check DNS now; it shows the reason.",
    ),
    (
        "The domain uses Cloudflare and the certificate never arrives.",
        "Cloudflare's proxy (the orange cloud) is switched on for the record.",
        "In Cloudflare, edit the record and switch the cloud to grey (DNS only).",
    ),
    (
        "Everything looks right but nothing has changed yet.",
        "DNS changes spread as caches expire, usually within an hour, rarely up to a day.",
        "Wait, then check again with the command in the section above.",
    ),
)


def _e(value: Any) -> str:
    return html.escape(str(value)) if value not in (None, "") else "—"


def _step(title: str, where: str, do: str, expect: str, if_not: str) -> str:
    return (
        f"<div class='step'><h3>{title}</h3>"
        f"<p><b>Where:</b> {where}</p>"
        f"<p><b>Do:</b> {do}</p>"
        f"<p><b>You should see:</b> {expect}</p>"
        f"<p><b>If not:</b> {if_not}</p></div>"
    )


def render_handover_html(run: dict[str, Any], *, admin_password: str | None = None,
                         generated_at: datetime | None = None) -> str:
    """The handover sheet for ``run`` as a self-contained HTML page."""
    spec = run.get("deploy_run_spec") or {}
    state = run.get("deploy_run_state") or {}
    domain = spec.get("domain") or ""
    ip = state.get("droplet_ip") or ""
    items = state.get("open_items") or {}
    if isinstance(items, list):
        items = {i.get("key"): i for i in items if isinstance(i, dict)}
    dns = state.get("dns") or {}
    record = state.get("manual_dns_record") or {}
    dns_host = dns.get("dns_host") or record.get("dns_host") or "the domain's DNS host"
    name = dns.get("record_name") or record.get("host_name") or domain
    zone = dns.get("zone") or (domain.split(".", 1)[1] if "." in domain else domain)
    manual = spec.get("dns_mode") == "manual"
    dns_open = "dns" in items
    cert_open = "certificate" in items
    ready = not items
    when = (generated_at or datetime.now()).strftime("%m-%d-%y %H:%M")

    parts: list[str] = [
        "<html><head><meta charset='utf-8'><title>CRM handover sheet</title><style>",
        "body{font-family:Inter,Segoe UI,Arial,sans-serif;font-size:15px;color:#272D36;"
        "max-width:820px;margin:24px auto;line-height:1.5}",
        "h1{font-size:26px;margin-bottom:4px}h2{font-size:20px;margin-top:28px;"
        "border-bottom:1px solid #DDE3EA;padding-bottom:4px}h3{font-size:16px;margin:12px 0 4px}",
        ".status{padding:10px 14px;border-radius:6px;margin:12px 0}",
        ".ready{background:#E6F4EC}.waiting{background:#FBF2E0}",
        ".step{border-left:4px solid #C1CAD4;padding:2px 12px;margin:10px 0}",
        "table{border-collapse:collapse}td{padding:4px 12px 4px 0;vertical-align:top}",
        "code{background:#EEF1F5;padding:1px 4px;border-radius:3px}",
        "</style></head><body>",
        f"<h1>Your new CRM: {_e(spec.get('instance_name') or domain)}</h1>",
        f"<p>Handover sheet, produced {when}.</p>",
    ]
    if ready:
        parts.append(
            f"<div class='status ready'><b>Ready.</b> The CRM is installed and secure at "
            f"<b>https://{_e(domain)}</b>.</div>"
        )
    else:
        waiting = []
        if dns_open:
            waiting.append("the DNS record below must be created or corrected")
        if cert_open:
            waiting.append("the security certificate follows automatically once DNS is right")
        parts.append(
            "<div class='status waiting'><b>Almost ready.</b> The CRM is installed on its "
            f"server, but {'; '.join(waiting)}. <b>Do not log in until the address "
            "shows a padlock in the browser.</b></div>"
        )

    parts += [
        "<h2>The essentials</h2><table>",
        f"<tr><td>Web address</td><td><b>https://{_e(domain)}</b></td></tr>",
        f"<tr><td>Server IP address</td><td><b>{_e(ip)}</b></td></tr>",
        f"<tr><td>DNS for {_e(zone)} is hosted by</td><td>{_e(dns_host)}</td></tr>",
        f"<tr><td>Administrator username</td><td>{_e(spec.get('admin_username'))}</td></tr>",
        "<tr><td>Administrator password</td><td>"
        + (f"<code>{_e(admin_password)}</code> — store it in a password manager, then "
           "delete it from this sheet." if admin_password
           else "the password recorded when the deploy was started")
        + "</td></tr>",
        f"<tr><td>Administrator email</td><td>{_e(spec.get('admin_email'))}</td></tr>",
        "</table>",
    ]

    item = items.get("dns") or {}
    if dns_open or manual:
        parts.append("<h2>1. Point the web address at the server</h2>")
        if item.get("found"):
            parts.append(f"<p><b>What CRMBuilder found:</b> {_e(item.get('found'))} "
                         f"{_e(item.get('meaning'))}</p>")
        parts.append(_step(
            "Create the DNS record",
            f"sign in to {_e(dns_host)} and open the DNS settings for <b>{_e(zone)}</b>.",
            f"add a record with type <b>A</b>, name <b>{_e(name)}</b>, value "
            f"<b>{_e(ip)}</b>, and the time-to-live on automatic or 5 minutes. If the host "
            "offers a proxy, forwarding or parking for the record, switch it off. Remove any "
            "other A, AAAA or CNAME record with the same name.",
            f"within minutes to an hour, running <code>nslookup {_e(domain)} 1.1.1.1</code> "
            f"on any computer shows <code>Address: {_e(ip)}</code>.",
            "see the troubleshooting list at the end of this sheet.",
        ))
        if item.get("action") and dns_open:
            parts.append(f"<p><b>Specifically for this domain:</b> {_e(item.get('action'))}</p>")
    parts.append(f"<h2>{'2' if (dns_open or manual) else '1'}. The security certificate</h2>")
    parts.append(_step(
        "Wait for the padlock",
        f"a web browser, at <b>https://{_e(domain)}</b>.",
        "nothing. A job on the server checks every 15 minutes and installs the certificate "
        "by itself once the address points at the server.",
        "the page opens with a padlock and the CRM's login screen.",
        "wait 15 minutes after DNS is correct. If it is still missing, ask your CRMBuilder "
        "contact to press Check DNS now on the instance; it names the reason.",
    ))
    parts.append(f"<h2>{'3' if (dns_open or manual) else '2'}. Log in for the first time</h2>")
    parts.append(_step(
        "Sign in as the administrator",
        f"<b>https://{_e(domain)}</b>, once it shows a padlock.",
        f"sign in with the username <b>{_e(spec.get('admin_username'))}</b> and the "
        "administrator password.",
        "the CRM's home page.",
        "check the password was copied exactly; the username and password are case sensitive.",
    ))
    parts.append("<h2>If something does not work</h2><table>")
    parts.append("<tr><td><b>What you see</b></td><td><b>Likely cause</b></td><td><b>Fix</b></td></tr>")
    for symptom, cause, fix in TROUBLESHOOTING:
        parts.append(f"<tr><td>{_e(symptom)}</td><td>{_e(cause)}</td><td>{_e(fix)}</td></tr>")
    parts.append("</table>")
    parts.append(
        "<h2>What happens next</h2><p>Your CRMBuilder contact configures the CRM for your "
        "organisation once it is secure. Keep this sheet: it records the server's address "
        "and how the web address points at it.</p></body></html>"
    )
    return "".join(parts)


#: Who acts on an open item, in words.
WHO_TEXT = {"operator": "You", "client": "The client (whoever manages the domain's DNS)",
            "nobody": "Nobody — this finishes by itself"}


def open_items_html(items: list[dict[str, Any]] | dict[str, Any]) -> str:
    """Open items as rich text: the ones needing a person first."""
    if isinstance(items, dict):
        items = list(items.values())
    ordered = sorted(items, key=lambda i: 0 if i.get("state") == "needs_action" else 1)
    blocks = []
    for item in ordered:
        needs = item.get("state") == "needs_action"
        marker = "⚑ Needs action" if needs else "… Waiting"
        rows = [f"<b>{marker}: {_e(item.get('title'))}</b>"]
        if item.get("found"):
            rows.append(f"<br>{_e(item.get('found'))} {html.escape(item.get('meaning') or '')}")
        if item.get("action"):
            rows.append(f"<br><b>What to do:</b> {_e(item.get('action'))}")
        if item.get("who"):
            rows.append(f"<br><b>Who:</b> {_e(WHO_TEXT.get(item['who'], item['who']))}")
        if item.get("verify") and needs:
            rows.append(f"<br><b>To confirm:</b> {_e(item.get('verify'))}")
        blocks.append("<p>" + "".join(rows) + "</p>")
    return "".join(blocks)
