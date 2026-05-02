// CRM Builder Deployment Runbook Generator
// Produces: deployment-runbook.docx (v1.0)
//
// An administrator-focused, full-lifecycle runbook for deploying an EspoCRM
// instance via the CRM Builder Setup Wizard. Written in generic-friendly
// prose with CBM values supplied inline as worked examples (Treatment B).
// Intended primary audience: a CBM-internal administrator deploying CBM
// Production or a fresh Test instance, or onboarding the next admin.
// A future generic / reseller version is producible from this draft by
// removing the CBM-specific parentheticals.

const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, LevelFormat, HeadingLevel, BorderStyle,
  WidthType, ShadingType,
} = require("docx");

// ---------- Style constants ----------

const HEADER_FILL = "1F3864";
const HEADER_TEXT = "FFFFFF";
const ALT_ROW_FILL = "F2F7FB";
const META_LABEL_FILL = "F2F7FB";
const BORDER_COLOR = "AAAAAA";

const border = { style: BorderStyle.SINGLE, size: 4, color: BORDER_COLOR };
const cellBorders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 80, bottom: 80, left: 120, right: 120 };

// ---------- Helpers ----------

function cell(text, opts = {}) {
  const {
    bold = false, italic = false, fill = null, color = null,
    width = null, children = null, alignment = null,
  } = opts;
  const runOpts = { text: String(text), bold, italic, font: "Arial" };
  if (color) runOpts.color = color;
  const para = { children: [new TextRun(runOpts)] };
  if (alignment) para.alignment = alignment;
  const cellChildren = children ? children : [new Paragraph(para)];
  const cellDef = { borders: cellBorders, margins: cellMargins, children: cellChildren };
  if (width) cellDef.width = { size: width, type: WidthType.DXA };
  if (fill) cellDef.shading = { fill, type: ShadingType.CLEAR };
  return new TableCell(cellDef);
}

function headerCell(text, width) {
  return cell(text, { bold: true, fill: HEADER_FILL, color: HEADER_TEXT, width });
}

function labelCell(text, width) {
  return cell(text, { bold: true, fill: META_LABEL_FILL, width });
}

function multiCell(textArr, opts = {}) {
  const { width = null, fill = null, bold = false } = opts;
  const childs = textArr.map((t) =>
    new Paragraph({ children: [new TextRun({ text: t, bold, font: "Arial" })] })
  );
  const cellDef = { borders: cellBorders, margins: cellMargins, children: childs };
  if (width) cellDef.width = { size: width, type: WidthType.DXA };
  if (fill) cellDef.shading = { fill, type: ShadingType.CLEAR };
  return new TableCell(cellDef);
}

function para(text, opts = {}) {
  const { bold = false, italic = false, heading = null, spacing = null } = opts;
  const paraDef = {
    children: [new TextRun({ text: String(text), bold, italic, font: "Arial" })],
  };
  if (heading) paraDef.heading = heading;
  if (spacing) paraDef.spacing = spacing;
  return new Paragraph(paraDef);
}

function richPara(runs, opts = {}) {
  const { heading = null, spacing = null } = opts;
  const paraDef = {
    children: runs.map((r) => new TextRun({
      text: r.text,
      bold: r.bold || false,
      italic: r.italic || false,
      font: "Arial",
    })),
  };
  if (heading) paraDef.heading = heading;
  if (spacing) paraDef.spacing = spacing;
  return new Paragraph(paraDef);
}

function bullet(text) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children: [new TextRun({ text, font: "Arial" })],
  });
}

function numberedPara(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "ordered", level },
    children: [new TextRun({ text, font: "Arial" })],
  });
}

function code(text) {
  return new Paragraph({
    children: [new TextRun({
      text, font: "Courier New", size: 20,
    })],
    spacing: { before: 60, after: 60 },
    indent: { left: 360 },
  });
}

function blank() {
  return new Paragraph({ children: [new TextRun({ text: "", font: "Arial" })] });
}

function stripedTable({ columnWidths, headers, rows }) {
  const totalWidth = columnWidths.reduce((a, b) => a + b, 0);
  const headerRow = new TableRow({
    children: headers.map((h, i) => headerCell(h, columnWidths[i])),
    tableHeader: true,
  });
  const dataRows = rows.map((row, rowIdx) => {
    const fill = rowIdx % 2 === 0 ? null : ALT_ROW_FILL;
    return new TableRow({
      children: row.map((val, i) => cell(val, { width: columnWidths[i], fill })),
    });
  });
  return new Table({
    width: { size: totalWidth, type: WidthType.DXA },
    columnWidths,
    rows: [headerRow, ...dataRows],
  });
}

// ---------- Document content ----------

const children = [];

// Title block
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  children: [new TextRun({
    text: "CRM Builder", bold: true, size: 32,
    color: HEADER_FILL, font: "Arial",
  })],
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 240 },
  children: [new TextRun({
    text: "EspoCRM Deployment Runbook",
    bold: true, size: 28, color: HEADER_FILL, font: "Arial",
  })],
}));

// Metadata
const metaTable = new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [2600, 6760],
  rows: [
    new TableRow({ children: [labelCell("Document Type", 2600),
      cell("Deployment Runbook (administrator instructions)", { width: 6760 })] }),
    new TableRow({ children: [labelCell("Audience", 2600),
      cell("CBM-internal administrator deploying or onboarding to an EspoCRM instance via CRM Builder", { width: 6760 })] }),
    new TableRow({ children: [labelCell("Scope", 2600),
      cell("Full lifecycle: pre-deploy prerequisites, the deploy itself, post-deploy verification and documentation", { width: 6760 })] }),
    new TableRow({ children: [labelCell("Version", 2600),
      cell("1.1", { width: 6760 })] }),
    new TableRow({ children: [labelCell("Status", 2600),
      cell("Active", { width: 6760 })] }),
    new TableRow({ children: [labelCell("Last Updated", 2600),
      cell("05-02-26 06:50", { width: 6760 })] }),
    new TableRow({ children: [labelCell("Companion Document", 2600),
      cell("Per-instance Deployment Records (e.g. ClevelandBusinessMentoring/PRDs/deployment/CBM-Test-Instance-Deployment-Record.docx)", { width: 6760 })] }),
  ],
});
children.push(metaTable);
children.push(blank());

// Revision History
children.push(para("Revision History", { heading: HeadingLevel.HEADING_1 }));
children.push(stripedTable({
  columnWidths: [800, 1500, 7060],
  headers: ["Version", "Date", "Notes"],
  rows: [
    ["1.1", "05-02-26 06:50",
      "Strengthened the SSH Host field row in Section 7.3 (Wizard Page 2 "
      + "\u2014 Server (SSH) Connection) with an explicit cross-reference "
      + "to Section 3.1 of the per-instance Deployment Record, where the "
      + "captured IPv4 value now appears under the label \"Public IPv4 "
      + "(SSH Host)\" (CBM Deployment Record v1.3 made the matching "
      + "change). Together the two changes connect the wizard's SSH Host "
      + "input to the Record's captured value so an operator running a "
      + "re-deploy or migration knows exactly which value to enter. No "
      + "other content changes."],
    ["1.0", "05-02-26 06:00",
      "Initial release. Authored alongside the CBM Test Instance Deployment "
      + "Record (companion document) so that future EspoCRM deployments via "
      + "CRM Builder produce both the runbook execution and the per-instance "
      + "documentation as a single integrated workflow. Treatment B prose "
      + "style (generic with CBM values inline as worked examples) keeps "
      + "the runbook directly usable for CBM operations while preserving "
      + "a clear edit path to a future generic / reseller version."],
  ],
}));
children.push(blank());

// ==============================
// 1. Document Purpose & Scope
// ==============================
children.push(para("1. Document Purpose and Scope", { heading: HeadingLevel.HEADING_1 }));
children.push(para(
  "This Runbook is the administrator-facing instructions for deploying an "
  + "EspoCRM instance using the CRM Builder application. It is written to "
  + "be followed top-to-bottom by an administrator standing up a new "
  + "EspoCRM instance for Cleveland Business Mentors \u2014 either a "
  + "production instance, a fresh test instance, or a replacement for an "
  + "existing instance \u2014 and to serve as a reference when onboarding "
  + "a new administrator into the deployment process."
));
children.push(para(
  "The Runbook covers the complete lifecycle: the work that must happen "
  + "before the CRM Builder Setup Wizard is opened (DigitalOcean Droplet "
  + "provisioning, SSH key preparation, DNS configuration), the wizard "
  + "run itself (the four automated phases that prepare the server, "
  + "install EspoCRM, obtain a TLS certificate, and verify the deployment), "
  + "and the work that must happen after the wizard completes (credential "
  + "capture, Deployment Record production, instance registration in the "
  + "local toolchain). Each phase is presented as a checklist of concrete "
  + "actions with the values used by CBM as worked examples; an admin "
  + "deploying a new client would substitute their own values for those "
  + "examples."
));
children.push(para(
  "The Runbook does not duplicate the per-instance Deployment Records "
  + "that capture the as-deployed state of specific instances \u2014 the "
  + "Records are reference documents about what is, while this Runbook "
  + "is a procedure document about how to get there. The two work "
  + "together: the Runbook's post-deploy section explicitly produces a "
  + "Deployment Record as one of its outputs."
));
children.push(blank());

// ==============================
// 2. Overview
// ==============================
children.push(para("2. Overview", { heading: HeadingLevel.HEADING_1 }));

children.push(para("2.1 Three Phases", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "Deployment proceeds through three phases. The CRM Builder application "
  + "automates the middle phase fully; the first and third are administrator "
  + "responsibilities executed against external systems."
));

children.push(stripedTable({
  columnWidths: [1600, 2400, 2680, 2680],
  headers: ["Phase", "Performed By", "Where", "Time Estimate"],
  rows: [
    ["Pre-Deploy", "Administrator (manual)",
      "DigitalOcean dashboard; DNS provider dashboard; local terminal",
      "20\u201340 minutes"],
    ["Deploy", "CRM Builder Setup Wizard (automated)",
      "Local CRM Builder app, talking to the Droplet via SSH",
      "5\u201315 minutes"],
    ["Post-Deploy", "Administrator (mostly manual; one diagnostic script)",
      "Local terminal; password manager; client repository",
      "20\u201330 minutes"],
  ],
}));
children.push(blank());

children.push(para(
  "Total wall-clock time for a complete deployment is therefore one to "
  + "two hours, not counting waits for DNS propagation. The bulk of admin "
  + "effort is concentrated in pre-deploy and post-deploy; the deploy "
  + "phase itself is largely passive once the wizard begins."
));

children.push(para("2.2 What the Wizard Does Automatically", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "Once the wizard starts the deploy phase, four sub-phases run sequentially "
  + "on the Droplet via SSH. The administrator watches a streaming log; "
  + "no input is required during these phases unless one fails."
));
children.push(bullet("Server preparation: apt update and upgrade; install Docker engine and Docker Compose plugins; create a 2 GB swapfile; configure ufw to allow inbound 22, 80, and 443"));
children.push(bullet("EspoCRM installation: download the official EspoCRM installer (install.sh) from the EspoCRM GitHub releases; run it with --ssl --letsencrypt and the configured domain, admin credentials, and database passwords"));
children.push(bullet("Post-install: verify the five-container Docker Compose stack is running; confirm the cron job for certificate renewal is configured; read the SSL certificate expiry date"));
children.push(bullet("Verification: seven independent checks (Docker containers running, HTTP-to-HTTPS redirect, HTTPS 200, SSL certificate valid, EspoCRM login page present, cron job configured, database container healthy)"));

children.push(para("2.3 Costs", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "Recurring costs that the deployment introduces. CBM uses Porkbun for "
  + "domain registration and DigitalOcean for hosting. Substitute equivalent "
  + "providers as appropriate."
));
children.push(stripedTable({
  columnWidths: [2600, 2400, 4360],
  headers: ["Item", "Approximate Cost", "Notes"],
  rows: [
    ["Domain registration",
      "$10\u201320 / year (typical .org)",
      "Annual cost at the registrar (CBM uses Porkbun). Required for TLS \u2014 the deployment does not support bare-IP installations."],
    ["DigitalOcean Droplet (Test)",
      "~$12 / month",
      "1 vCPU / 2 GB RAM / 50 GB SSD. Sufficient for development and small-scale test data."],
    ["DigitalOcean Droplet (Production)",
      "~$24 / month",
      "2 vCPU / 4 GB RAM / 80 GB SSD. CBM's Test instance uses this size for headroom; Production should match or exceed."],
    ["DigitalOcean weekly backups",
      "+20% of Droplet cost",
      "Optional; recommended for Production. Not enabled on CBM Test (see DR-OI-001 in CBM-Test-Instance-Deployment-Record.docx)."],
    ["Let's Encrypt certificate",
      "$0",
      "Free; auto-renewed by the cron job installed during deployment."],
  ],
}));
children.push(blank());

// ==============================
// 3. Prerequisites
// ==============================
children.push(para("3. Prerequisites", { heading: HeadingLevel.HEADING_1 }));
children.push(para(
  "Before opening the Setup Wizard, confirm every item below is true. "
  + "The wizard will fail if any prerequisite is missing, and most "
  + "failures cost more time to diagnose mid-deploy than to verify up "
  + "front."
));

children.push(stripedTable({
  columnWidths: [4000, 5360],
  headers: ["Prerequisite", "How to Verify"],
  rows: [
    ["DigitalOcean account access",
      "Log in to https://cloud.digitalocean.com/ using the credentials in the password manager (CBM uses Proton Pass entry: DigitalOcean-CRM Hosting - Test Instance). Confirm you can see Droplets in the left navigation."],
    ["Domain registered and DNS-manageable",
      "Log in to your DNS provider (CBM uses Porkbun). Confirm you can edit DNS records for the target domain (CBM uses clevelandbusinessmentors.org)."],
    ["Subdomain reserved",
      "Decide which subdomain this instance will use. CBM convention: crm-test for test instances, crm for production. Confirm no existing A record claims that subdomain."],
    ["Local Linux Mint workstation with CRM Builder installed",
      "From a terminal, run: cd ~/path/to/crmbuilder && uv run crmbuilder. The application window should open. If not, follow the install instructions in crmbuilder/README.md before proceeding."],
    ["Local CRM Builder per-client database initialized",
      "The client project folder must exist locally with a .crmbuilder/ subdirectory containing the per-client SQLite database (CBM example: ~/Dropbox/Projects/ClevelandBusinessMentors/.crmbuilder/CBM.db). If the database does not exist, create the client through the CRM Builder application's Add Client flow first."],
    ["Password manager open and unlocked",
      "You will need to record the EspoCRM admin password and the MariaDB root password during post-deploy. CBM uses Proton Pass."],
    ["Uninterrupted time window",
      "Allow 60\u2013120 minutes. The deploy phase itself is automated, but DNS propagation can introduce unpredictable waits, and post-deploy documentation work benefits from continuous attention."],
  ],
}));
children.push(blank());

// ==============================
// 4. Pre-Deploy: Provision the Droplet
// ==============================
children.push(para("4. Pre-Deploy \u2014 Provision the Droplet", { heading: HeadingLevel.HEADING_1 }));

children.push(para(
  "The CRM Builder application does not provision Droplets. Provision the "
  + "Droplet manually in the DigitalOcean control panel before running the "
  + "Setup Wizard."
));

children.push(para("4.1 Create the Droplet", { heading: HeadingLevel.HEADING_2 }));
children.push(numberedPara("Log in to https://cloud.digitalocean.com/ and click Droplets > Create Droplet."));
children.push(numberedPara("Choose an image: Ubuntu 22.04 (LTS) x64. Do not select a one-click app (WordPress, LAMP, etc.); the EspoCRM installer requires a clean Ubuntu base."));
children.push(numberedPara("Choose a plan / size. CBM Test uses 2 vCPU / 4 GB RAM / 80 GB SSD (the regular plan). For a budget-constrained test instance, 1 vCPU / 2 GB / 50 GB is workable. For Production, do not go below the 2 vCPU / 4 GB tier."));
children.push(numberedPara("Choose a datacenter region close to your users (CBM uses NYC3). Use the same region for both Test and Production where possible to simplify any future cross-Droplet operations."));
children.push(numberedPara("Authentication method: select SSH Key, not Password. (See Section 5 for key handling.) If you have not yet generated or registered the deployment key, do that first \u2014 you can return here once the key is registered with DigitalOcean."));
children.push(numberedPara("Hostname: enter a descriptive name (CBM Test uses CBM-TEST). The hostname is for human identification only and does not need to match the domain."));
children.push(numberedPara("Backups: optional. CBM Test does not have backups enabled. For a Production instance, enable Weekly Backups (+20% Droplet cost) unless you have an alternative backup strategy."));
children.push(numberedPara("Click Create Droplet. Provisioning takes 30\u201360 seconds."));

children.push(para("4.2 Capture Droplet Details", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "Once the Droplet is running, record the following from its detail page. "
  + "These values feed into Section 6 (DNS) and Section 7 (Setup Wizard "
  + "input)."
));
children.push(bullet("Droplet ID (the numeric ID in the URL when viewing the Droplet, e.g. 561480073 in /droplets/561480073)"));
children.push(bullet("Public IPv4 address"));
children.push(bullet("Region"));
children.push(bullet("Size and plan name"));

children.push(para(
  "These values will be needed again when the Deployment Record is "
  + "produced in Section 11. Recording them now in a temporary note "
  + "saves a return trip to the DO dashboard later."
));
children.push(blank());

// ==============================
// 5. Pre-Deploy: SSH Key
// ==============================
children.push(para("5. Pre-Deploy \u2014 SSH Key", { heading: HeadingLevel.HEADING_1 }));
children.push(para(
  "The CRM Builder Setup Wizard authenticates to the Droplet using SSH key "
  + "authentication. Prepare the keypair before opening the wizard."
));

children.push(para("5.1 Use an Existing Key or Generate a New One", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "If a deployment keypair already exists, reuse it. CBM uses an existing "
  + "ED25519 keypair with comment crm-deploy, currently held in the "
  + "ClevelandBusinessMentoring repository as the file pair ssh / ssh.pub. "
  + "(Note: storing private keys in a Git repository is not best practice; "
  + "this is tracked as DR-OI-002 in the CBM Test Instance Deployment "
  + "Record.) For new deployments, prefer storing the private key in the "
  + "password manager rather than in a repository."
));
children.push(para(
  "To generate a new ED25519 keypair on Linux Mint:"
));
children.push(code("ssh-keygen -t ed25519 -C \"crm-deploy\""));
children.push(para(
  "Accept the default file location (~/.ssh/id_ed25519) or specify a "
  + "different path. A passphrase is optional; if used, you will need "
  + "the passphrase available during the wizard run because the wizard "
  + "passes the key file path through to paramiko."
));

children.push(para("5.2 Register the Public Key with DigitalOcean", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "If the Droplet already exists and was created with a different key, "
  + "add the new public key to the Droplet's authorized_keys file:"
));
children.push(numberedPara("Display the public key: cat ~/.ssh/id_ed25519.pub (or your chosen path)."));
children.push(numberedPara("Open the Droplet's in-browser Console from the DigitalOcean dashboard."));
children.push(numberedPara("As root in the Console, run: echo \"<paste the public key>\" >> /root/.ssh/authorized_keys"));

children.push(para(
  "If the Droplet has not yet been created, paste the public key into "
  + "the SSH Key field on the Droplet creation screen instead \u2014 "
  + "DigitalOcean will install it as the initial authorized key."
));

children.push(para("5.3 Verify SSH Access", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "Before running the Setup Wizard, confirm key-based SSH login works "
  + "from your workstation:"
));
children.push(code("ssh -i ~/.ssh/id_ed25519 root@<droplet-ipv4>"));
children.push(para(
  "You should reach a root prompt without being asked for a password. "
  + "If you are prompted for a password, the key is not configured "
  + "correctly. Do not proceed to the Setup Wizard until manual SSH "
  + "succeeds; the wizard surfaces SSH failures as opaque error messages "
  + "that are harder to diagnose than a direct ssh attempt."
));
children.push(blank());

// ==============================
// 6. Pre-Deploy: DNS A Record
// ==============================
children.push(para("6. Pre-Deploy \u2014 DNS A Record", { heading: HeadingLevel.HEADING_1 }));
children.push(para(
  "Create the A record pointing the chosen subdomain at the Droplet's "
  + "public IPv4. The wizard will not proceed past DNS verification "
  + "until the record resolves."
));

children.push(para("6.1 Create the A Record", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "Log in to your DNS provider (CBM uses Porkbun) and create an A record "
  + "with these values:"
));
children.push(stripedTable({
  columnWidths: [2200, 7160],
  headers: ["Field", "Value"],
  rows: [
    ["Type", "A"],
    ["Host / Name", "The subdomain only \u2014 e.g. crm-test or crm. Most providers append the base domain automatically; entering the fully-qualified name doubles it."],
    ["Value / Target / Points To", "The Droplet's public IPv4 address from Section 4.2"],
    ["TTL", "300 seconds (5 minutes) recommended during initial setup; can be raised to 3600 once stable"],
    ["Proxy / Cloud (Cloudflare-style)", "Disabled / DNS-only / grey cloud. The Let's Encrypt HTTP-01 challenge requires a direct connection to the Droplet."],
  ],
}));
children.push(blank());

children.push(para("6.2 Verify DNS Resolution", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "After saving the A record, wait for it to propagate. With a TTL of "
  + "300 this is typically 2\u201310 minutes. Verify from your workstation:"
));
children.push(code("dig +short crm-test.clevelandbusinessmentors.org"));
children.push(para(
  "The output should be the Droplet IPv4 \u2014 a single line with the "
  + "address. If the command returns nothing, the record has not yet "
  + "propagated; wait and retry. Do not start the Setup Wizard until "
  + "dig returns the expected IP."
));
children.push(blank());

// ==============================
// 7. The Deploy: Setup Wizard Walkthrough
// ==============================
children.push(para("7. The Deploy \u2014 Setup Wizard Walkthrough", { heading: HeadingLevel.HEADING_1 }));
children.push(para(
  "With prerequisites complete, open the CRM Builder application and "
  + "launch the Setup Wizard from the Deployment tab."
));

children.push(para("7.1 Launch the Application", { heading: HeadingLevel.HEADING_2 }));
children.push(numberedPara("Open a terminal and change to the crmbuilder repo directory."));
children.push(numberedPara("Run: uv run crmbuilder. The application window opens."));
children.push(numberedPara("Select the target client from the active-client picker (e.g. CBM)."));
children.push(numberedPara("Click the Deployment tab in the sidebar."));
children.push(numberedPara("Click the Deploy entry, then click the Setup Wizard button (or equivalent \u2014 the exact label may vary by app version)."));

children.push(para("7.2 Wizard Page 1 \u2014 Scenario and Platform", { heading: HeadingLevel.HEADING_2 }));
children.push(para("Select the deployment scenario and CRM platform:"));
children.push(stripedTable({
  columnWidths: [3000, 3360, 3000],
  headers: ["Field", "Value", "Notes"],
  rows: [
    ["Scenario", "Self-Hosted",
      "The other options (Cloud-Hosted, Bring Your Own) are connectivity checks against an instance you provisioned elsewhere. Self-Hosted is the only path that runs an actual install."],
    ["CRM Platform", "EspoCRM",
      "Currently the only supported platform. The combo box will be disabled if there is only one option."],
  ],
}));
children.push(blank());

children.push(para("7.3 Wizard Page 2 \u2014 Server (SSH) Connection", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "Provide the SSH connection details for the Droplet. These values feed "
  + "directly into the wizard's connect_ssh call (paramiko)."
));
children.push(stripedTable({
  columnWidths: [2200, 3000, 4160],
  headers: ["Field", "Recommended Value", "Notes"],
  rows: [
    ["SSH Host", "Droplet's public IPv4 (e.g. 104.131.45.208 for CBM Test). For an existing instance being re-deployed or migrated, this value appears as \"Public IPv4 (SSH Host)\" in Section 3.1 of the per-instance Deployment Record.",
      "The subdomain (e.g. crm-test.clevelandbusinessmentors.org) also works once DNS has propagated, but the IP is preferred during deploy because it bypasses any DNS hiccups."],
    ["SSH Port", "22",
      "The default. Do not change unless you have configured a non-standard port on the Droplet, in which case ufw will also need adjusting."],
    ["SSH Username", "root",
      "The EspoCRM installer requires root to install Docker and configure the firewall. The deployment is not designed for sudo-elevated non-root users in v1.0."],
    ["Authentication", "SSH Key",
      "Password authentication is supported by the wizard but not recommended."],
    ["Credential", "Path to your private key file (e.g. ~/.ssh/id_ed25519)",
      "Use the Browse button to select the file."],
  ],
}));
children.push(blank());

children.push(para("7.4 Wizard Page 3 \u2014 Domain and Database", { heading: HeadingLevel.HEADING_2 }));
children.push(stripedTable({
  columnWidths: [2200, 3000, 4160],
  headers: ["Field", "Recommended Value", "Notes"],
  rows: [
    ["Domain", "Fully-qualified subdomain (e.g. crm-test.clevelandbusinessmentors.org)",
      "Must match the A record created in Section 6.1. The wizard validates DNS resolution as its first deploy phase."],
    ["Let's Encrypt Email", "An admin email at your organization (CBM convention: an admin address at the org's primary domain)",
      "Used by Let's Encrypt for expiry notifications. Use a real, monitored mailbox."],
    ["DB Password", "A strong generated password",
      "The application database user's password. Will be passed to the EspoCRM installer's --db-password flag and embedded in the running container's environment. Record this in the password manager (Proton Pass for CBM)."],
    ["DB Root Password", "Leave blank to auto-generate, or supply a strong generated password",
      "MariaDB root password. Auto-generation is recommended unless you have a specific reason to choose your own. Either way, this password must be captured in the password manager during post-deploy (see Section 10.2) because it is otherwise inaccessible."],
  ],
}));
children.push(blank());

children.push(para("7.5 Wizard Page 4 \u2014 Admin", { heading: HeadingLevel.HEADING_2 }));
children.push(stripedTable({
  columnWidths: [2200, 3000, 4160],
  headers: ["Field", "Recommended Value", "Notes"],
  rows: [
    ["Admin Username", "admin",
      "The default and the convention. Changing this changes the URL of the admin login page (it is the username, not a path) but is otherwise harmless."],
    ["Admin Password", "A strong generated password",
      "The EspoCRM administrator account's password. Required for first login and all subsequent web UI / REST API access. Record this in the password manager."],
    ["Admin Email", "An admin email at your organization",
      "Becomes the admin user's email in EspoCRM. Used for password reset and notifications."],
  ],
}));
children.push(blank());

children.push(para("7.6 Wizard Page 5 \u2014 Progress", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "Click Next / Deploy from Page 4 to begin the automated deploy. The "
  + "Progress page streams a log of every action. Expected sequence:"
));
children.push(bullet("DNS Verification \u2014 the wizard polls until the domain resolves to the SSH host IP. Timeout 10 minutes; check interval 30 seconds. If DNS has not propagated yet, this is where the wizard will wait."));
children.push(bullet("Server Preparation \u2014 apt update / upgrade, Docker install, swapfile creation, ufw configuration. Takes 3\u20138 minutes depending on Droplet performance and apt mirror responsiveness."));
children.push(bullet("DNS re-verification \u2014 a quick second check immediately before the SSL phase, to catch the rare case where DNS resolves at deploy start but stops resolving mid-deploy."));
children.push(bullet("EspoCRM Installation \u2014 download install.sh from GitHub releases, run the installer with --ssl --letsencrypt and the configured options. Includes the Let's Encrypt certificate issuance, which involves an HTTP-01 challenge to the Droplet on port 80. Takes 2\u20135 minutes."));
children.push(bullet("Post-Install \u2014 confirm the five Docker containers are running; check the cron job; read the SSL certificate expiry. Less than a minute."));
children.push(bullet("Verification \u2014 seven checks executed in sequence (containers running, HTTP redirect, HTTPS 200, SSL valid, login page present, cron configured, database container healthy). Less than a minute."));

children.push(para(
  "Total deploy time, assuming DNS is already propagated, is typically "
  + "8\u201320 minutes \u2014 most of which is server preparation (apt) "
  + "and EspoCRM installation."
));
children.push(blank());

// ==============================
// 8. The Deploy: Troubleshooting
// ==============================
children.push(para("8. The Deploy \u2014 Troubleshooting", { heading: HeadingLevel.HEADING_1 }));

children.push(para(
  "If any wizard phase fails, the wizard reports the failed step and "
  + "(for prep and install) runs a best-effort cleanup before exiting. "
  + "Common failure modes and recovery actions:"
));

children.push(stripedTable({
  columnWidths: [2400, 3300, 3660],
  headers: ["Failure", "Likely Cause", "Recovery"],
  rows: [
    ["DNS validation timeout (10 min)",
      "A record not yet propagated, or pointing at the wrong IP",
      "Verify the A record at the registrar; verify with dig from your workstation; wait for propagation; restart the wizard"],
    ["SSH connection failed",
      "Wrong host / port / username / key, or the Droplet is unreachable",
      "From your workstation, run ssh -i <key> root@<host> directly. Diagnose at the shell level before retrying the wizard"],
    ["Server preparation failure (apt / Docker)",
      "Transient apt mirror issue, full disk, or a Droplet that wasn't a clean Ubuntu image",
      "The wizard runs cleanup_phase1 (removes Docker packages and the apt source). Restart the wizard. If apt failures recur, SSH in and run apt update manually to identify the upstream issue."],
    ["EspoCRM installer failure",
      "Let's Encrypt HTTP-01 challenge couldn't reach the Droplet; ufw not allowing port 80; DNS regressed; rate limit hit",
      "The wizard runs cleanup_phase2 (docker compose down --volumes, remove install.sh). Verify port 80 is reachable from the Internet (curl http://<domain> from your workstation should reach nginx or fail with a connect error, not a timeout). Verify ufw status. Wait an hour if rate-limited (Let's Encrypt issues 5 certs per domain per week)."],
    ["Post-install or verification check fails",
      "Container failed to start, cron not configured, certificate didn't install",
      "SSH to the Droplet and run docker compose -f /var/www/espocrm/docker-compose.yml ps. Inspect docker logs <container> --tail 100 for the failing container. Most post-install failures indicate a deeper installer problem worth investigating before re-running the wizard."],
  ],
}));
children.push(blank());

children.push(para(
  "After cleanup_phase1 or cleanup_phase2 has run, the Droplet is in a "
  + "best-effort-clean state \u2014 not pristine. If the deploy fails "
  + "repeatedly, the cleanest recovery is to destroy the Droplet entirely "
  + "(in the DigitalOcean dashboard) and provision a new one before "
  + "retrying. Droplets are inexpensive and fast to provision; debugging "
  + "a half-installed Droplet usually costs more time than starting "
  + "fresh."
));
children.push(blank());

// ==============================
// 9. Post-Deploy: Verification
// ==============================
children.push(para("9. Post-Deploy \u2014 Verification", { heading: HeadingLevel.HEADING_1 }));

children.push(para(
  "Before declaring the deployment complete, confirm the instance is "
  + "actually usable by a human, not only by the wizard's automated checks."
));

children.push(numberedPara("Open the application URL in a browser (e.g. https://crm-test.clevelandbusinessmentors.org/). The EspoCRM login page should load over HTTPS with a valid certificate (no browser warnings)."));
children.push(numberedPara("Log in as admin with the password chosen in Section 7.5. The EspoCRM dashboard should load."));
children.push(numberedPara("Click the user icon (top-right) > Administration > System Information. Confirm the displayed EspoCRM version matches what was just installed."));
children.push(numberedPara("From the System Information page, confirm Cron is reported as running. (EspoCRM's internal cron status indicator; distinct from the host's certbot cron job.)"));
children.push(numberedPara("Visit http://<domain> (plain HTTP) and confirm it 301-redirects to HTTPS."));
children.push(numberedPara("Optionally: SSH to the Droplet and run docker compose -f /var/www/espocrm/docker-compose.yml ps. All five containers (espocrm, espocrm-daemon, espocrm-db, espocrm-nginx, espocrm-websocket) should report Up."));

children.push(blank());

// ==============================
// 10. Post-Deploy: Capture Credentials
// ==============================
children.push(para("10. Post-Deploy \u2014 Capture Credentials", { heading: HeadingLevel.HEADING_1 }));
children.push(para(
  "Three credentials must be captured in the password manager (Proton "
  + "Pass for CBM). Two are immediate and one requires a one-time SSH "
  + "extraction. None should ever be stored in a Git repository or in "
  + "a document."
));

children.push(para("10.1 EspoCRM Admin Password", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "This is the password chosen on Wizard Page 4 (Section 7.5). Add it to "
  + "the password manager now. CBM convention for entry naming: "
  + "<Client Code>-ESPOCRM-<Environment> Instance Admin "
  + "(CBM example: CBM-ESPOCRM-Test Instance Admin). Include in the "
  + "entry: the application URL, the admin username, the password, and "
  + "the deploy date in the notes."
));

children.push(para("10.2 MariaDB Root Password", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "If the wizard auto-generated the MariaDB root password (the "
  + "recommended path on Wizard Page 3), it currently exists only in "
  + "the running espocrm-db container's environment. Extract and store "
  + "it before any container restart that might disrupt access."
));
children.push(para(
  "On Linux Mint, prepare the SSH key (substituting your private key path):"
));
children.push(code("cp /path/to/private/key /tmp/cbm_key && chmod 600 /tmp/cbm_key"));
children.push(para("Extract the password from the running container:"));
children.push(code("ssh -i /tmp/cbm_key root@<domain> 'docker exec espocrm-db env | grep -E \"^MARIADB_ROOT_PASSWORD=|^MYSQL_ROOT_PASSWORD=\"'"));
children.push(para(
  "Copy the value (everything after the equals sign) into the password "
  + "manager. CBM convention for entry naming: "
  + "ESPOCRM Root DB Password - <Environment> Instance "
  + "(CBM example: ESPOCRM Root DB Password - Test Instance). Then "
  + "clean up the temp key:"
));
children.push(code("shred -u /tmp/cbm_key 2>/dev/null || rm -f /tmp/cbm_key"));

children.push(para("10.3 DigitalOcean Account Login", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "If your DigitalOcean account is shared across deployments, the entry "
  + "may already exist in the password manager (CBM example entry: "
  + "DigitalOcean-CRM Hosting - Test Instance). If this is the first "
  + "deployment, add it now."
));
children.push(blank());

// ==============================
// 11. Post-Deploy: Produce the Deployment Record
// ==============================
children.push(para("11. Post-Deploy \u2014 Produce the Deployment Record", { heading: HeadingLevel.HEADING_1 }));
children.push(para(
  "The Deployment Record is a per-instance .docx that captures the "
  + "as-deployed state \u2014 Droplet identification, hardware, OS, "
  + "EspoCRM and component versions, TLS certificate, SSH access, "
  + "credentials inventory by reference, and a deployment history "
  + "timeline. The CBM Test Instance Deployment Record at "
  + "ClevelandBusinessMentoring/PRDs/deployment/CBM-Test-Instance-Deployment-Record.docx "
  + "is the canonical model."
));

children.push(para("11.1 Capture As-Deployed Values", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "From your workstation, the values that go into the Record come from "
  + "three sources:"
));
children.push(bullet("On-server inspection via SSH \u2014 hardware, OS, kernel, swap, firewall, Docker version, container set, EspoCRM install location, crontab, authorized SSH keys, and (with one extra docker exec call each) the EspoCRM, MariaDB, and nginx component versions"));
children.push(bullet("Live SSL certificate inspection \u2014 issuer, subject, dates, fingerprint via openssl s_client (no SSH required)"));
children.push(bullet("DigitalOcean dashboard \u2014 Droplet ID, region, size, backup status, the Droplet detail and Console URLs"));

children.push(para(
  "A diagnostic script that captures the SSH-side values in one pass "
  + "is documented in the CBM Test Instance Deployment Record's "
  + "production history (commit 964c841 in the ClevelandBusinessMentoring "
  + "repo). Adapt that approach for new deployments rather than running "
  + "ten ad-hoc SSH commands."
));

children.push(para("11.2 Generate the .docx", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "Copy the existing CBM generator as the starting point:"
));
children.push(code("cp ~/Dropbox/Projects/ClevelandBusinessMentors/PRDs/deployment/generate-deployment-record.js \\\n   <new-client>/PRDs/deployment/generate-deployment-record.js"));
children.push(para(
  "Edit the new generator to substitute the values captured in Section "
  + "11.1, change the title block, and update the metadata. The "
  + "structure (eleven sections plus front and back matter) is "
  + "designed to apply to any deployment without modification."
));
children.push(para(
  "Run the generator and validate the output:"
));
children.push(code("cd <client>/PRDs/deployment\nnpm init -y && npm install docx\nnode generate-deployment-record.js\npython3 /mnt/skills/public/docx/scripts/office/validate.py CBM-Test-Instance-Deployment-Record.docx\nrm -rf node_modules package.json package-lock.json"));

children.push(para("11.3 Commit", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "Commit the .docx and the generator script to the client's repository "
  + "in a single commit, using a message that records the version and "
  + "the deploy event the Record describes. The .docx is the canonical "
  + "form; the generator is checked in alongside it so that future "
  + "version bumps can re-run the generator rather than hand-editing the "
  + "Word file."
));
children.push(blank());

// ==============================
// 12. Post-Deploy: Register the Instance
// ==============================
children.push(para("12. Post-Deploy \u2014 Register the Instance", { heading: HeadingLevel.HEADING_1 }));
children.push(para(
  "On a successful deploy, the wizard writes two rows in the per-client "
  + "SQLite database: an Instance row (the CRM connection profile) and "
  + "an InstanceDeployConfig row (the SSH and deployment configuration "
  + "needed for future Upgrade and Recovery operations). Confirm both "
  + "are present."
));

children.push(numberedPara("In the CRM Builder application, click the Instances tab. The newly-deployed instance should appear with the name and URL chosen during the wizard."));
children.push(numberedPara("Right-click the instance and choose Test Connection (or equivalent). It should report success with the EspoCRM version detected."));
children.push(numberedPara("If the InstanceDeployConfig row appears to be missing (Upgrade and Recovery buttons disabled or showing a backfill prompt), use the connection_config_dialog backfill flow to enter the SSH connection details. This stores the deployment configuration for future server-side operations."));

children.push(para(
  "Project folder association: confirm the Instance points at the "
  + "client's project folder on disk (CBM example: "
  + "~/Dropbox/Projects/ClevelandBusinessMentors). The project folder "
  + "is where YAML configuration files are read from and reports are "
  + "written to."
));
children.push(blank());

// ==============================
// 13. Reference: What the App Actually Does
// ==============================
children.push(para("13. Reference \u2014 What the App Actually Does", { heading: HeadingLevel.HEADING_1 }));
children.push(para(
  "Short technical reference for understanding the system without "
  + "reading source code. The deploy phase consists of four functions "
  + "in automation/core/deployment/ssh_deploy.py executed in sequence "
  + "by automation/ui/deployment/deploy_wizard/deploy_worker.py."
));

children.push(para("13.1 Phase 1 \u2014 phase_server_prep", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "Runs as root via SSH. Executes (in order): apt-get update and "
  + "DEBIAN_FRONTEND=noninteractive apt-get upgrade -y; apt-get install "
  + "of curl, ca-certificates, gnupg; install of the Docker apt keyring "
  + "and repository; apt-get install of docker-ce, docker-ce-cli, "
  + "containerd.io, docker-buildx-plugin, docker-compose-plugin; "
  + "fallocate of a 2 GB /swapfile, swapon, and fstab entry "
  + "(idempotent if the swapfile already exists); ufw allow 22 / 80 / "
  + "443 followed by ufw enable. On any non-zero exit code, returns "
  + "(False, error_message) and the wrapping worker invokes "
  + "cleanup_phase1."
));

children.push(para("13.2 Phase 2 \u2014 phase_install_espocrm", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "Downloads install.sh from "
  + "https://github.com/espocrm/espocrm-installer/releases/latest/download/install.sh "
  + "and runs it as: sudo bash install.sh -y --clean --ssl --letsencrypt "
  + "--domain=<domain> --email=<letsencrypt-email> "
  + "--admin-username=<admin-user> --admin-password=<admin-password> "
  + "--db-password=<db-password> --db-root-password=<db-root-password>. "
  + "The mask_credentials helper sanitizes the displayed command before "
  + "logging. The installer creates /var/www/espocrm/, writes "
  + "docker-compose.yml, pulls and starts the five containers (espocrm, "
  + "espocrm-daemon, espocrm-db, espocrm-nginx, espocrm-websocket), "
  + "obtains the Let's Encrypt certificate via the HTTP-01 challenge, "
  + "and configures the cert-renewal crontab line. On any non-zero "
  + "exit code, returns (False, error_message) and the wrapping worker "
  + "invokes cleanup_phase2."
));

children.push(para("13.3 Phase 3 \u2014 phase_post_install", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "Verifies the five-container docker compose stack is running; checks "
  + "the cron job; reads the SSL certificate expiry via openssl s_client "
  + "and parses notAfter into ISO date form. Returns "
  + "(success, error_message, cert_expiry_date)."
));

children.push(para("13.4 Phase 4 \u2014 phase_verify", { heading: HeadingLevel.HEADING_2 }));
children.push(para(
  "Runs seven independent checks. Each result is recorded as a dict "
  + "with check name, pass/fail, and (on failure) up to 200 chars of "
  + "diagnostic output. The seven checks: Docker containers running; "
  + "HTTP redirects to HTTPS (301 or 302); HTTPS returns 200; SSL "
  + "certificate has a notAfter date; the response body contains the "
  + "string \"espocrm\" (case-insensitive); cron job mentions espocrm; "
  + "database container reports up. Overall pass requires all seven."
));
children.push(blank());

// ==============================
// 14. Reference: Files and Locations
// ==============================
children.push(para("14. Reference \u2014 Files and Locations", { heading: HeadingLevel.HEADING_1 }));

children.push(para("14.1 On the Deployed Server", { heading: HeadingLevel.HEADING_2 }));
children.push(stripedTable({
  columnWidths: [3400, 5960],
  headers: ["Path", "Contents"],
  rows: [
    ["/var/www/espocrm/", "EspoCRM stack base directory \u2014 docker-compose.yml, command.sh, data/"],
    ["/var/www/espocrm/docker-compose.yml", "The five-container compose definition"],
    ["/var/www/espocrm/data/", "Application data, including Let's Encrypt artifacts"],
    ["/var/www/espocrm/data/letsencrypt/renew.log", "Certificate renewal log appended by the daily cron job"],
    ["/var/www/espocrm/command.sh", "Helper script invoked by the cert-renew cron entry"],
    ["/root/install.sh", "The downloaded EspoCRM installer (left in place after install)"],
    ["/swapfile", "2 GB swapfile created during phase_server_prep"],
    ["/root/.ssh/authorized_keys", "Authorized SSH public keys for root \u2014 add new keys here to grant access"],
    ["/etc/ufw/", "ufw firewall configuration; status visible via ufw status"],
  ],
}));
children.push(blank());

children.push(para("14.2 On the Local Workstation", { heading: HeadingLevel.HEADING_2 }));
children.push(stripedTable({
  columnWidths: [3400, 5960],
  headers: ["Path", "Contents"],
  rows: [
    ["~/Dropbox/Projects/<Client>/", "Client project folder. CBM example: ~/Dropbox/Projects/ClevelandBusinessMentors/"],
    ["~/Dropbox/Projects/<Client>/.crmbuilder/<CODE>.db", "Per-client SQLite database with Instance, InstanceDeployConfig, DeploymentRun, and ConfigurationRun tables"],
    ["~/Dropbox/Projects/<Client>/programs/", "YAML program files applied via the Configure tab"],
    ["~/Dropbox/Projects/<Client>/PRDs/deployment/", "Per-instance Deployment Record .docx files and their generators"],
    ["~/Dropbox/Projects/<Client>/reports/", "Deployment, configuration, and import run reports written by the application"],
    ["~/.ssh/id_ed25519 (or chosen path)", "SSH private key used by the Setup Wizard to authenticate to the Droplet"],
  ],
}));
children.push(blank());

children.push(para("14.3 Across the Toolchain", { heading: HeadingLevel.HEADING_2 }));
children.push(stripedTable({
  columnWidths: [2400, 3000, 3960],
  headers: ["System", "Used For", "CBM Convention"],
  rows: [
    ["Proton Pass", "All credential storage", "Entries named per the templates in Section 10"],
    ["Porkbun", "Domain registration and DNS", "All CBM domains (clevelandbusinessmentors.org and any others)"],
    ["DigitalOcean", "Droplet hosting", "NYC3 region; project name TBD"],
    ["GitHub", "Source repositories", "dbower44022/crmbuilder (tooling) and dbower44022/ClevelandBusinessMentoring (CBM-specific PRDs and YAML)"],
    ["Local Linux Mint workstation", "Running CRM Builder, generating documents, executing diagnostic scripts", "uv-based Python environment"],
  ],
}));
children.push(blank());

// ==============================
// Change Log
// ==============================
children.push(para("Change Log", { heading: HeadingLevel.HEADING_1 }));
children.push(stripedTable({
  columnWidths: [800, 1500, 7060],
  headers: ["Version", "Date", "Changes"],
  rows: [
    ["1.1", "05-02-26 06:50",
      "Section 7.3 (Wizard Page 2 \u2014 Server (SSH) Connection) "
      + "field table updated. The SSH Host row's Recommended Value "
      + "column now reads: \"Droplet's public IPv4 (e.g. 104.131.45.208 "
      + "for CBM Test). For an existing instance being re-deployed or "
      + "migrated, this value appears as 'Public IPv4 (SSH Host)' in "
      + "Section 3.1 of the per-instance Deployment Record.\" Connects "
      + "the wizard's SSH Host input to the Deployment Record's "
      + "captured value, addressing operator confusion observed during "
      + "a real wizard run. Companion change: CBM Test Instance "
      + "Deployment Record v1.3 relabeled the captured IPv4 row to "
      + "\"Public IPv4 (SSH Host)\". Metadata Last Updated bumped to "
      + "05-02-26 06:50. No other content changes."],
    ["1.0", "05-02-26 06:00",
      "Initial release. Fourteen sections covering: document purpose and "
      + "scope (Section 1); overview of the three deployment phases "
      + "(pre-deploy / deploy / post-deploy), what the wizard does "
      + "automatically, and recurring costs (Section 2); prerequisites "
      + "checklist (Section 3); pre-deploy Droplet provisioning, SSH key "
      + "preparation, and DNS A record creation (Sections 4\u20136); the "
      + "Setup Wizard walkthrough page-by-page with field tables for "
      + "each input page (Section 7); deploy-phase troubleshooting with "
      + "common failure modes and recovery actions (Section 8); "
      + "post-deploy verification, credential capture into the password "
      + "manager, Deployment Record production, and instance "
      + "registration in the local toolchain (Sections 9\u201312); "
      + "reference material on the four deploy phases as implemented in "
      + "automation/core/deployment/ssh_deploy.py and the file / "
      + "location map across server, workstation, and toolchain "
      + "(Sections 13\u201314). Treatment B prose style throughout: "
      + "generic instructions with CBM values supplied inline as worked "
      + "examples (e.g. NYC3 region, crm-test subdomain, Porkbun "
      + "registrar, Proton Pass entry names). Companion to the "
      + "per-instance Deployment Record at ClevelandBusinessMentoring/"
      + "PRDs/deployment/CBM-Test-Instance-Deployment-Record.docx."],
  ],
}));
children.push(blank());

// ==============================
// Document construction
// ==============================
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal",
        next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: "Arial", color: HEADER_FILL },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal",
        next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: HEADER_FILL },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 },
      },
      {
        id: "Heading3", name: "Heading 3", basedOn: "Normal",
        next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: HEADER_FILL },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2 },
      },
    ],
  },
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [
          {
            level: 0, format: LevelFormat.BULLET, text: "\u2022",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
      {
        reference: "ordered",
        levels: [
          {
            level: 0, format: LevelFormat.DECIMAL, text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
        },
      },
      children,
    },
  ],
});

const outPath = path.join(__dirname, "deployment-runbook.docx");
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(outPath, buf);
  console.log(`Wrote ${outPath} (${(buf.length / 1024).toFixed(1)} KB)`);
}).catch((err) => {
  console.error("Generation failed:", err);
  process.exit(1);
});
