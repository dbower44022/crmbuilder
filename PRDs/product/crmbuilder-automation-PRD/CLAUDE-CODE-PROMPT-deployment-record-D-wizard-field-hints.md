# Claude Code Prompt — Deployment Record Series, Prompt D

**Series:** deployment-record (productize the Deployment Record artifact)
**Prompt ID:** D
**Descriptor:** wizard-field-hints
**Filename:** `CLAUDE-CODE-PROMPT-deployment-record-D-wizard-field-hints.md`
**Repository:** `crmbuilder`
**Depends on:** Prompt B merged (this prompt edits the same wizard pages B touches; running it before B creates merge headaches)
**Related document:** `crmbuilder/PRDs/product/crmbuilder-automation-PRD/deployment-runbook.docx` v1.1 §7 (the field tables in the runbook are the spec for the hints to add)
**Last Updated:** 05-02-26 06:50
**Version:** 1.0

---

## Status

Follow-on UI polish prompt to the deployment-record series. Adds inline hint text (placeholder text and / or helper labels) to the Setup Wizard's input fields so an operator can see at the moment of typing what each field expects.

This prompt is not part of the C-tier productization scope agreed during planning. It was added later in response to operator feedback during a real wizard run: the wizard asks for "SSH Host" with no hint about whether that's an IP, a hostname, a domain, or something else. Fixing this in the UI catches operators *as they're typing the wrong thing*; the parallel document changes (CBM Deployment Record v1.3 and Deployment Runbook v1.1) catch operators only if they're already reading the documents.

After Prompt D: every wizard field on the self-hosted scenario displays inline guidance covering field purpose, expected format, and (where helpful) a worked example.

---

## What this prompt accomplishes

1. **Placeholder text on every text input field** in the self-hosted scenario's wizard pages — Server (SSH) Connection, Domain and Database, Admin, Documentation Inputs (the page added by Prompt B). Each `QLineEdit.setPlaceholderText(...)` call gives the operator a worked example of what to type, in a slightly faded font that doesn't compete with real input.
2. **One-line helper labels under fields where placeholder text alone is insufficient** — for fields where the operator needs a slightly longer explanation than a placeholder fits cleanly. Helper labels use the existing wizard's small-text style (consistent with field labels above the input).
3. **Tooltips for every field** — `QWidget.setToolTip(...)` carrying the same content as the helper labels, plus any additional context (where this value comes from, what happens if it's wrong). The tooltip is the long-form documentation; the placeholder and helper label are the just-in-time prompts.
4. **Tests verifying placeholder text and tooltips are set** — light-touch tests that assert specific fields have non-empty placeholder text and tooltips. Tests do not validate exact string content (that's brittle); they validate presence.

---

## What this prompt does NOT do

- **No field validation changes.** Validation logic (`_validate_sh_*` methods) is unchanged. This prompt is purely additive UI text.
- **No new fields.** The set of fields stays exactly what Prompts A and B established.
- **No re-layout.** The wizard's existing two-column "label : input" layout is preserved. Helper labels go below their input fields, indented to align with the input column, in small text.
- **No changes to the Cloud-Hosted or Bring-Your-Own scenarios.** This prompt is self-hosted-only because that's where field-purpose ambiguity exists. Cloud-Hosted's two fields (URL and credential) are self-explanatory.
- **No localization scaffolding.** Strings are English literals consistent with the rest of the application.

---

## Constraints and conventions

- **Match the language of the Deployment Runbook §7 field tables.** The Runbook is the spec. If the Runbook says SSH Host is "Droplet's public IPv4 (e.g. 104.131.45.208 for CBM Test)", the placeholder might be `e.g. 104.131.45.208 (Droplet IP, not domain)` and the helper label might be `The Droplet's public IPv4 address. From the per-instance Deployment Record §3.1 if re-deploying.` Don't invent new guidance; condense the Runbook's existing language.
- **Keep placeholder text short.** No more than 60 characters; ideally 30–50. Placeholders are at-a-glance hints, not documentation.
- **Helper labels stay to one line.** If the guidance can't fit on one line at typical wizard width, it belongs in the tooltip, not in a multi-line helper label.
- **Tooltips can be longer but not novels.** 2–3 short sentences maximum. If more is needed, the right place is the Runbook, and the tooltip says "See Deployment Runbook §X."
- **Do not introduce new dependencies.** Use only PySide6 widgets already in use elsewhere in the wizard.
- **Python 3.11+, type hints, pytest** — same conventions as the rest of the codebase.

---

## Detailed implementation

### 1. Field-by-field guidance content

Use this table as the authoritative spec. Each row gives the placeholder, helper label, and tooltip for one wizard field. Apply exactly; don't paraphrase.

#### Server (SSH) Connection page (`_build_self_hosted_server_page`)

| Field | Placeholder | Helper Label | Tooltip |
|---|---|---|---|
| SSH Host | `e.g. 104.131.45.208 (Droplet IP)` | The Droplet's public IPv4 address. | The IP address of the DigitalOcean Droplet you provisioned. Not the application domain (e.g. crm-test.example.org). For an existing instance being re-deployed, this value is recorded as "Public IPv4 (SSH Host)" in Section 3.1 of the per-instance Deployment Record. See Deployment Runbook §4.2 and §7.3. |
| SSH Port | `22` | The SSH port on the Droplet. | Default 22. Change only if the Droplet has been configured to use a non-standard SSH port (uncommon). See Deployment Runbook §7.3. |
| SSH Username | `root` | The SSH user that will run the install. | Must be root. The EspoCRM installer requires root privileges to install Docker and configure the firewall; non-root users with sudo are not supported in v1.0. See Deployment Runbook §7.3. |
| Authentication | (combo box; no placeholder applicable) | (no helper label) | Select SSH Key for key-based authentication (recommended) or Password for password authentication. |
| Credential (key path) | `e.g. ~/.ssh/id_ed25519` | Path to the SSH private key file. | Click Browse to select the private key file. The corresponding public key must be installed in /root/.ssh/authorized_keys on the Droplet. See Deployment Runbook §5. |
| Credential (password) | (none, for security) | (no helper label) | The password for the SSH user. Avoid password authentication where possible; key-based authentication is recommended. |

#### Domain and Database page (`_build_self_hosted_domain_page`)

| Field | Placeholder | Helper Label | Tooltip |
|---|---|---|---|
| Domain | `e.g. crm-test.example.org` | Fully-qualified domain for this instance. | The full subdomain.domain.tld where EspoCRM will be reachable. Must already have an A record pointing to the SSH Host IP; the wizard verifies DNS resolution before proceeding. See Deployment Runbook §6. |
| Let's Encrypt Email | `e.g. admin@example.org` | Email for certificate expiry notifications. | A monitored mailbox at your organization. Let's Encrypt sends warnings here if certificate renewal fails. Use a real, monitored address. |
| DB Password | (none, for security) | The application database user's password. | The password for the EspoCRM application's database user. Generate a strong password and record it in your password manager (Proton Pass for CBM). Never reuse a password from another system. |
| DB Root Password | `Leave blank to auto-generate` | MariaDB root password. | Leave blank for the wizard to auto-generate a strong random password (recommended). If supplied, must be a strong password. Either way, this value must be captured in your password manager during post-deploy because it is otherwise inaccessible after the deploy completes. See Deployment Runbook §10.2. |

#### Admin page (`_build_self_hosted_admin_page`)

| Field | Placeholder | Helper Label | Tooltip |
|---|---|---|---|
| Admin Username | `admin` | The EspoCRM administrator username. | Convention is "admin". Used for first login; can be changed in EspoCRM after deploy. |
| Admin Password | (none, for security) | The EspoCRM administrator password. | Generate a strong password and record it in your password manager. Required for first login and all subsequent admin operations. See Deployment Runbook §10.1. |
| Admin Email | `e.g. admin@example.org` | Email address for the admin user record. | Becomes the admin user's email in EspoCRM. Used for password reset and notifications. |

#### Documentation Inputs page (`_build_self_hosted_documentation_page`, added by Prompt B)

| Field | Placeholder | Helper Label | Tooltip |
|---|---|---|---|
| Domain Registrar | `e.g. Porkbun` | The registrar where the domain is registered. | The DNS registrar / domain provider for the application's domain. Recorded in the Deployment Record's Section 4.1 for future reference. |
| DNS Provider | `e.g. Porkbun (defaults to registrar if same)` | Where DNS records are managed. | Often equals the registrar but may differ if DNS has been delegated to a third party (e.g. Cloudflare). Recorded in the Deployment Record's Section 4.1. |
| Droplet ID | `e.g. 561480073` | The DigitalOcean Droplet's numeric ID. | Find in the URL when viewing the Droplet in the DigitalOcean dashboard: cloud.digitalocean.com/droplets/<DROPLET_ID>. Used to populate the Deployment Record's Section 3.1 with direct links to the Droplet detail page and in-browser Console. |
| Backups Enabled | (checkbox; no placeholder) | (no helper label) | Whether DigitalOcean automated weekly backups are enabled for this Droplet. Recorded in the Deployment Record's Section 3.4. |
| Admin Password Proton Pass Entry | `e.g. CBM-ESPOCRM-Test Instance Admin` | Password manager entry name for the admin password. | The exact name of the password manager entry where the admin password is stored. The Deployment Record references credentials by entry name only, never by value. |
| DB Root Password Proton Pass Entry | `e.g. ESPOCRM Root DB Password - Test Instance` | Password manager entry name for the DB root password. | Same convention as the admin password entry. |
| Hosting Account Proton Pass Entry | `e.g. DigitalOcean-CRM Hosting - Test Instance` | Password manager entry name for the hosting account. | The exact name of the password manager entry for the DigitalOcean (or other hosting provider) account login. |

### 2. Helper label widget pattern

The wizard does not currently have a "helper label below input" pattern; the existing layout is `QLabel | QLineEdit` rows in a `QFormLayout` (or similar). Two ways to add helper labels:

**Option A — small label below the input.** Wrap each input + helper-label pair in a `QVBoxLayout` and add the wrapper to the form layout. Helper label uses 9pt italic gray text. This is the conventional approach.

**Option B — helper label as a separate row below.** Add a row to the form layout with an empty label cell and the helper label as the input cell. Simpler but visually less clearly attached to the field above.

Use Option A. Encapsulate it in a small helper:

```python
def _input_with_helper(
    line_edit: QLineEdit, helper_text: str
) -> QWidget:
    """Wrap a QLineEdit with a small helper label below it."""
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    layout.addWidget(line_edit)

    if helper_text:
        helper = QLabel(helper_text)
        font = helper.font()
        font.setPointSize(9)
        font.setItalic(True)
        helper.setFont(font)
        helper.setStyleSheet("color: #666666;")
        layout.addWidget(helper)

    return container
```

Add this helper near the top of `wizard_dialog.py` and use it for all fields with helper labels. Fields without helper labels (per the table above) skip the wrapper and are added directly to the form layout as today.

### 3. Tests

Add `tests/test_wizard_field_hints.py`:

- `test_server_page_fields_have_placeholders` — instantiate the wizard at the Server page; assert every QLineEdit on the page has a non-empty `placeholderText()`.
- `test_server_page_fields_have_tooltips` — same but for `toolTip()`.
- `test_domain_page_fields_have_placeholders` and `test_domain_page_fields_have_tooltips`.
- `test_admin_page_fields_have_placeholders` and `test_admin_page_fields_have_tooltips`.
- `test_documentation_page_fields_have_placeholders` and `test_documentation_page_fields_have_tooltips`.
- `test_ssh_host_helper_label_present` — assert a helper label with non-empty text appears below the SSH Host input. (One spot-check is enough; other helper labels follow the same pattern and aren't worth individually asserting.)

These tests use the standard PySide6 test pattern already established in the repo (likely `pytest-qt` or a manual `QApplication` fixture; verify against existing wizard tests).

---

## Acceptance criteria

- Every field listed in the Section 1 table has the specified placeholder, helper label, and tooltip.
- Visual inspection of the wizard (run `uv run crmbuilder` and click through to the Setup Wizard) shows the new hints rendering cleanly without breaking the existing layout.
- All new tests pass; all existing tests continue to pass.
- `uv run ruff check` passes on all touched files.
- No fields outside the self-hosted scenario's pages are modified.

---

## Notes for the implementer

- The existing wizard probably uses `QFormLayout`. `QFormLayout.addRow` accepts a label string or `QLabel` plus a single widget; using `_input_with_helper`'s wrapper widget as the input slot works correctly with `QFormLayout`'s alignment.
- The 9pt italic gray helper label color (`#666666`) is a starting point. Adjust to whatever the rest of the application uses for secondary text if there's an established style. Search for `setStyleSheet` calls referencing color in the existing UI code to find the convention.
- For the password fields where placeholder is "(none, for security)" — that means literally no placeholder. The placeholder is omitted entirely; the field renders empty. The helper label and tooltip still apply.
- The Documentation Inputs page does not exist before Prompt B is merged. If you find yourself trying to add hints to it and the page isn't there, Prompt B hasn't been run yet and this prompt should be deferred until it has.
- After the prompt completes, the visual sanity check is: open the wizard, click into each input field, and confirm the placeholder text disappears as you start typing (PySide6 default behavior, but worth verifying it works as expected with the wrapped widget pattern).
