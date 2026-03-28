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
2. In your DNS provider, create an **A record**:
   - Name: `crm` (or `@` for root domain)
   - Value: Droplet public IP
   - TTL: 300 seconds (low, so it propagates quickly)
3. Wait for DNS propagation (typically 2–15 minutes; can verify with `dig crm.mycompany.com`)
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

Open questions:
- Does the target customer base have compliance requirements (HIPAA, PCI, SOC2) that mandate commercial certificates?
- Will the tool always expect users to have a domain name pre-configured, or must it work with bare IPs?
- Should the tool validate DNS propagation before attempting Let's Encrypt issuance?
- Should the tool manage certificate renewal notifications, or is that out of scope?
