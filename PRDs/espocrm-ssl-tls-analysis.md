# SSL/TLS Options for EspoCRM on DigitalOcean — Decision Analysis

**Project:** EspoCRM DigitalOcean Deployment Tool  
**Topic:** SSL/TLS Approach Selection  
**Status:** Pending Decision

---

## Overview

EspoCRM's official installer script supports three SSL/TLS modes. The choice must be made at install time and affects the domain setup, operational overhead, security level, and what inputs the deployment tool must collect from the user.

The three modes are:

| Mode | Flag(s) | Best For |
|------|---------|----------|
| HTTP only (no SSL) | *(none)* | Local/dev/testing only |
| Let's Encrypt (free cert) | `--ssl --letsencrypt` | Most production deployments |
| Own SSL/TLS certificate | `--ssl --owncertificate` | Enterprise / high-security / custom CA |

---

## DNS Setup & Validation (Required for Options 2 and 3)

### Recommended Domain Convention

Use a subdomain of your existing registered domain. The standard convention is:

```
crm.yourdomain.com
```

This is the most universally recognized pattern, is immediately clear to users and staff, and avoids any conflict with your existing website. The deployment tool should pre-populate this as the default and allow the user to override it.

---

### Step-by-Step: Creating the DNS A Record

You need to add a DNS record that points your CRM subdomain to your DigitalOcean Droplet's IP address. The exact steps depend on your DNS provider, but the record values are the same everywhere.

**What you are creating:**

| Field | Value |
|-------|-------|
| Record Type | `A` |
| Name / Host | `crm` (just the subdomain, not the full domain) |
| Value / Points To | The public IPv4 address of your Droplet |
| TTL | `300` (5 minutes — keep low until confirmed working, then raise to 3600) |

**Steps by common provider:**

**DigitalOcean DNS (if your domain is managed there):**
1. In the DigitalOcean control panel, go to **Networking → Domains**
2. Select your domain
3. Under "Create new record", choose type **A**
4. In the **Hostname** field enter `crm`
5. In the **Will Direct To** field enter the Droplet's IP address
6. Set TTL to `300`
7. Click **Create Record**

**GoDaddy:**
1. Log in → My Products → DNS → Manage
2. Click **Add** under DNS Records
3. Type: `A`, Name: `crm`, Value: `<Droplet IP>`, TTL: `600`
4. Save

**Namecheap:**
1. Dashboard → Domain List → Manage → Advanced DNS
2. Click **Add New Record**
3. Type: `A Record`, Host: `crm`, Value: `<Droplet IP>`, TTL: `300`
4. Save

**Cloudflare:**
1. Select your domain → DNS → Records → Add record
2. Type: `A`, Name: `crm`, IPv4 address: `<Droplet IP>`, TTL: `Auto`
3. **Important:** Set the Proxy status to **DNS only** (grey cloud, not orange) — the EspoCRM Let's Encrypt challenge requires a direct connection to the server, not Cloudflare's proxy
4. Save

> If your domain is managed elsewhere, the pattern is the same — create an A record with name `crm` pointing to the Droplet IP.

---

### DNS Propagation

After saving the record, DNS changes take time to propagate across the internet. With a TTL of 300 seconds, this is typically **2–10 minutes**, but can occasionally take longer depending on your provider.

**Do not run the EspoCRM installer until propagation is confirmed.** Let's Encrypt will fail if it cannot resolve your domain to the server.

---

### Validation: Confirming DNS Has Propagated

The deployment tool should run this check automatically before proceeding to installation. It can also be run manually.

**Option A — Using `dig` (Linux/macOS, on the Droplet or your local machine):**
```bash
dig crm.yourdomain.com +short
```
Expected output: the Droplet's IP address. If it returns nothing or a different IP, propagation is not complete yet.

**Option B — Using `nslookup` (works on Windows, Linux, macOS):**
```bash
nslookup crm.yourdomain.com
```
Look for the `Address` line in the output. It should match the Droplet IP.

**Option C — Using `curl` (confirms the server is reachable, not just resolving):**
```bash
curl -I http://crm.yourdomain.com
```
If you get any HTTP response (even an error page), the domain is resolving to the server and port 80 is reachable — which is what Let's Encrypt needs.

**Option D — Online tools (no command line required):**
- https://dnschecker.org — shows propagation status across multiple global DNS servers
- https://mxtoolbox.com/DNSLookup.aspx — quick A record lookup

---

### Deployment Tool Validation Logic

The tool should implement the following pre-flight check before running the installer:

```
1. Resolve the provided domain (e.g. crm.yourdomain.com) via DNS
2. Compare the resolved IP to the Droplet's public IP
3. If they match → proceed with installation
4. If they do not match → display an error:
     "DNS not yet propagated. The domain crm.yourdomain.com currently resolves
      to X.X.X.X but this Droplet's IP is Y.Y.Y.Y. Please check your DNS
      settings and wait a few minutes before retrying."
5. If no result → display an error:
     "The domain crm.yourdomain.com could not be resolved. Please ensure you
      have created an A record pointing to this Droplet's IP (Y.Y.Y.Y)."
6. Optionally: retry automatically every 30 seconds up to a configurable timeout
   (suggested default: 10 minutes)
```

This check prevents wasting a Let's Encrypt rate-limit attempt on a domain that isn't ready, and gives the user a clear, actionable error rather than a cryptic Let's Encrypt failure message.

---

## Option 1: HTTP Only (No SSL)

### What It Is
EspoCRM runs over plain HTTP with no encryption. The installer uses a public or private IP address rather than a domain name.

### Install Command
```bash
sudo bash install.sh --public-ip
# or
sudo bash install.sh --private-ip
```

### Prerequisites
- A DigitalOcean Droplet with a public or private IP
- No domain name required
- No DNS configuration required

### Step-by-Step
1. Provision a DigitalOcean Droplet (Ubuntu 22.04 recommended)
2. SSH into the Droplet as root
3. Download the installer:
   ```bash
   wget -N https://github.com/espocrm/espocrm-installer/releases/latest/download/install.sh
   ```
4. Run without SSL flags:
   ```bash
   sudo bash install.sh --public-ip
   ```
5. Access EspoCRM via `http://<DROPLET_IP>`

### Inputs Required by Deployment Tool
- Public IP (auto-detected from Droplet, or user-provided)
- Admin username & password
- DB password (or auto-generate)

### Pros
- Fastest to deploy — no domain or DNS required
- No certificate management
- Works for internal/private network access

### Cons
- **All traffic is unencrypted** — login credentials, CRM data, email content sent in plaintext
- Browsers show "Not Secure" warnings
- Not suitable for any production or internet-facing deployment
- Cannot be used if users access the system over the public internet

### Recommendation
**Use only for local development, testing, or internal-network-only deployments.** Never for production.

---

## Option 2: Let's Encrypt Free Certificate (Recommended)

### What It Is
The installer automatically provisions a free SSL certificate from Let's Encrypt using Certbot, configures Nginx to serve HTTPS, and sets up automatic certificate renewal. This is the default recommended path for production.

### Install Command
```bash
sudo bash install.sh --ssl --letsencrypt --domain=my-espocrm.com --email=email@my-domain.com
```

### Prerequisites
1. **A registered domain name** (e.g., `crm.mycompany.com`)
2. **DNS A record pointing to the Droplet's IP** — must be configured *before* running the installer. Let's Encrypt validates domain ownership by sending an HTTP challenge request to the domain, so it must resolve to the server.
3. **Ports 80 and 443 open** on the Droplet firewall (DigitalOcean cloud firewall or ufw)
4. **A valid email address** — Let's Encrypt sends expiry warning emails to this address

### Step-by-Step
1. Provision a DigitalOcean Droplet (Ubuntu 22.04 recommended)
2. Create a DNS A record for `crm.yourdomain.com` pointing to the Droplet IP — see the **DNS Setup & Validation** section above for provider-specific instructions
3. Confirm DNS has propagated using the validation steps above before continuing
4. Open ports 80 and 443 on the Droplet:
   ```bash
   ufw allow 80/tcp
   ufw allow 443/tcp
   ```
   Or configure the DigitalOcean Cloud Firewall via the control panel to allow HTTP and HTTPS inbound.
5. SSH into the Droplet as root
6. Download and run the installer:
   ```bash
   wget -N https://github.com/espocrm/espocrm-installer/releases/latest/download/install.sh
   sudo bash install.sh -y --ssl --letsencrypt \
     --domain=crm.mycompany.com \
     --email=admin@mycompany.com
   ```
7. The installer will:
   - Install Docker, Nginx, and MariaDB via Docker Compose
   - Call Let's Encrypt to issue a certificate for the domain
   - Configure Nginx to serve HTTPS and redirect HTTP → HTTPS
   - Set up automatic certificate renewal via cron
8. Access EspoCRM via `https://crm.mycompany.com`

### Certificate Renewal
Let's Encrypt certificates are valid for **90 days**. The installer sets up automatic renewal. Renewal can also be triggered manually:
```bash
sudo /var/www/espocrm/command.sh letsencrypt-renew
```
To enable/disable auto-renewal:
```bash
sudo /var/www/espocrm/command.sh letsencrypt-enable
sudo /var/www/espocrm/command.sh letsencrypt-disable
```

### Inputs Required by Deployment Tool
- Domain name (e.g., `crm.mycompany.com`)
- Email address for Let's Encrypt notifications
- Admin username & password
- DB password (or auto-generate)

### Pros
- **Free** — no certificate purchase required
- Automatic renewal — no ongoing cert management
- Fully automated by the EspoCRM installer
- Trusted by all major browsers out of the box
- Sufficient security level for the vast majority of CRM deployments

### Cons
- **Requires a domain name** — cannot use a bare IP address
- DNS must be configured and propagated *before* install
- Rate limits: Let's Encrypt allows a maximum of 5 certificate requests per domain per week (rarely an issue in practice)
- Not suitable if your organization's security policy requires a CA-issued commercial certificate
- If the Droplet IP changes (e.g., rebuild), the DNS A record must be updated before renewal will succeed

### Recommendation
**The default choice for production deployments.** The deployment tool should use this as the standard path whenever a domain is provided.

---

## Option 3: Own SSL/TLS Certificate (Custom / Commercial)

### What It Is
You supply your own certificate files (issued by a commercial CA such as DigiCert, Sectigo, or your organization's internal CA). The installer configures Nginx to use them. This is intended for advanced users with specific security or compliance requirements.

### Install Command
```bash
sudo bash install.sh --ssl --owncertificate --domain=crm.mycompany.com
```
> **Note:** The installer sets up the Nginx SSL configuration but **does not place the certificate files for you**. You must manually copy them into the correct location after installation.

### Prerequisites
1. **A registered domain name**
2. **DNS A record pointing to the Droplet's IP** (same as Let's Encrypt)
3. **A purchased or internally-issued SSL certificate**, consisting of:
   - Certificate file: `fullchain.pem` (or `cert.pem` + `chain.pem`)
   - Private key file: `privkey.pem`
4. Certificate must be issued for the exact domain being used
5. Ports 80 and 443 open on the Droplet

### Step-by-Step
1. Provision a DigitalOcean Droplet
2. Configure DNS A record (same as Option 2)
3. Obtain your SSL certificate from your CA. You will typically receive:
   - `certificate.crt` — your domain certificate
   - `ca_bundle.crt` — the intermediate/chain certificate
   - `private.key` — your private key
   Combine certificate and chain into a `fullchain.pem`:
   ```bash
   cat certificate.crt ca_bundle.crt > fullchain.pem
   ```
4. Download and run the installer:
   ```bash
   wget -N https://github.com/espocrm/espocrm-installer/releases/latest/download/install.sh
   sudo bash install.sh -y --ssl --owncertificate --domain=crm.mycompany.com
   ```
5. After the installer completes, copy your certificate files into the Nginx data directory:
   ```bash
   cp fullchain.pem /var/www/espocrm/data/nginx/ssl/fullchain.pem
   cp privkey.pem   /var/www/espocrm/data/nginx/ssl/privkey.pem
   ```
6. Restart the Nginx container to apply:
   ```bash
   cd /var/www/espocrm && docker compose restart espocrm-nginx
   ```
7. Access EspoCRM via `https://crm.mycompany.com`

### Certificate Renewal
Commercial certificates typically last **1–2 years**. Renewal is **manual**:
1. Obtain the renewed certificate from your CA
2. Replace the files in `/var/www/espocrm/data/nginx/ssl/`
3. Restart the Nginx container

The deployment tool would need to support a "renew certificate" operation separately.

### Inputs Required by Deployment Tool
- Domain name
- Path to `fullchain.pem` file (uploaded or provided)
- Path to `privkey.pem` file (uploaded or provided)
- Admin username & password
- DB password (or auto-generate)

### Pros
- Supports certificates from commercial CAs (required by some compliance frameworks: PCI-DSS, HIPAA, etc.)
- Supports wildcard certificates (e.g., `*.mycompany.com`) — Let's Encrypt also supports wildcards but requires DNS challenge automation
- Supports internal/private CA certificates for closed networks
- Certificate lifetime can be up to 2 years (less frequent renewal)
- Full control over certificate type (OV, EV, etc.)

### Cons
- **Most complex to set up** — certificate files must be manually placed post-install
- **Cost** — commercial certificates range from ~$50–$500+/year depending on type
- **Manual renewal burden** — the deployment tool or operator must track expiry and rotate certs
- Requires additional file handling in the deployment tool (securely receiving and placing private key material)

### Recommendation
**Use only when required by compliance, security policy, or organizational requirements.** Most teams do not need this.

---

## Comparison Summary

| | HTTP Only | Let's Encrypt | Own Certificate |
|--|-----------|--------------|-----------------|
| **Cost** | Free | Free | $50–$500+/yr |
| **Requires domain name** | No | Yes | Yes |
| **DNS setup required** | No | Yes (before install) | Yes |
| **Automated cert renewal** | N/A | Yes (built-in) | No (manual) |
| **Browser-trusted** | No (no HTTPS) | Yes | Yes |
| **Installer handles cert** | N/A | Yes (fully automated) | Partial (files manual) |
| **Deployment tool complexity** | Lowest | Medium | Highest |
| **Suitable for production** | No | Yes | Yes |
| **Compliance-grade** | No | Usually yes | Yes (depends on CA) |

---

## Decision Required

**Which SSL mode should the deployment tool support?**

Recommended approach for the tool: **support Let's Encrypt as the primary/default path**, with HTTP-only as an explicitly opt-in dev/test mode. Own certificate support can be added as a secondary advanced option.

Decided:
- ✅ Use `crm.yourdomain.com` subdomain convention as the default
- ✅ The tool will validate DNS propagation before attempting Let's Encrypt issuance

Open questions:
- Does the target customer base have compliance requirements (HIPAA, PCI, SOC2) that mandate commercial certificates?
- Will the tool always expect users to have a domain name pre-configured, or must it work with bare IPs?
- Should the tool manage certificate renewal notifications, or is that out of scope?
