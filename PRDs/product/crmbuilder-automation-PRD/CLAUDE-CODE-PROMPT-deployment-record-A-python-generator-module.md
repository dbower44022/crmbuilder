# Claude Code Prompt — Deployment Record Series, Prompt A

**Series:** deployment-record (productize the Deployment Record artifact)
**Prompt ID:** A
**Descriptor:** python-generator-module
**Filename:** `CLAUDE-CODE-PROMPT-deployment-record-A-python-generator-module.md`
**Repository:** `crmbuilder`
**Reference document:** `ClevelandBusinessMentoring/PRDs/deployment/CBM-Test-Instance-Deployment-Record.docx` v1.2 (the visual / structural target) and `ClevelandBusinessMentoring/PRDs/deployment/generate-deployment-record.js` (the JS reference implementation to port from)
**Companion document:** `crmbuilder/PRDs/product/crmbuilder-automation-PRD/deployment-runbook.docx` v1.0 — the runbook that this generator closes the manual-Record-production gap for
**Last Updated:** 05-02-26 06:30
**Version:** 1.0

---

## Status

This is the first prompt in a three-prompt series productizing the per-instance Deployment Record artifact inside the CRM Builder application. The series matches the C-tier scope agreed with the user: every successful self-hosted deploy automatically produces a Deployment Record `.docx` alongside the deployed instance, replacing the manual Record-production step currently described in Section 11 of the Deployment Runbook.

This prompt produces a working, testable Python module. It introduces the Record-generation capability without changing any UI or wizard behavior. The deploy wizard does not call this generator yet; that integration is Prompt B. The manual-regeneration UI is Prompt C.

After Prompt A: a new module `automation/core/deployment/record_generator.py` exists, callable as a function with deterministic inputs (a value-bag dataclass) and outputs (a `.docx` file at a specified path). The module is fully tested but unwired from the rest of the application.

---

## What this prompt accomplishes

1. **`automation/core/deployment/record_generator.py`** — the Python generator module. Defines:
   - `DeploymentRecordValues` dataclass — the structured input bag containing every value the document needs.
   - `generate_deployment_record(values: DeploymentRecordValues, output_path: Path) -> Path` — the public entry point that writes a `.docx` to `output_path` and returns the path on success.
   - `inspect_server_for_record_values(ssh: paramiko.SSHClient, instance: Instance, deploy_config: InstanceDeployConfig) -> DeploymentRecordValues` — helper that captures live on-server values via SSH and returns a populated `DeploymentRecordValues` ready for `generate_deployment_record`. Used by Prompts B and C; included here so all generator-related logic lives in one module.
   - Internal styling helpers (header cell, label cell, striped table, bullet, etc.) following the visual standard established in the JS reference and the CBM Record `.docx`.
2. **`automation/core/deployment/__main__.py`** addition — a small CLI entry point so the generator can be run manually for testing without booting the GUI: `python -m automation.core.deployment.record_generator --values fixture.json --output /tmp/test.docx`. This is also useful as a debugging tool post-release.
3. **`tests/test_record_generator.py`** — pytest tests verifying:
   - `DeploymentRecordValues` dataclass validates required vs. optional fields and rejects empty required values.
   - `generate_deployment_record` produces a `.docx` that opens cleanly in `python-docx` (smoke test).
   - The generated file passes `python /mnt/skills/public/docx/scripts/office/validate.py` if that script is available locally; if not, the test falls back to a self-check that opens the file with `python-docx` and counts paragraphs (must match the expected count within ±5).
   - The generated file contains expected substrings in expected sections — at least the instance code, the application URL, the deploy date, the EspoCRM version, and each of the three Proton Pass entry-name templates.
   - A "fixture builder" helper `_make_fixture_values()` in the test module builds a `DeploymentRecordValues` populated with CBM Test instance values; reuse this fixture across tests.
4. **`tests/fixtures/deployment_record_values_cbmtest.json`** — JSON serialization of the CBM Test fixture for use by both the test and the CLI entry point. Round-trippable through `dataclasses.asdict` / `dataclass(**data)`.

---

## What this prompt does NOT do

- **No wizard or UI changes.** Nothing in `automation/ui/`, nothing in `deploy_worker.py`, no new buttons.
- **No automatic invocation.** `generate_deployment_record` is purely a function. Nothing calls it yet from production paths.
- **No SQLite changes.** No schema migration, no new tables, no new columns.
- **No replacement of the JS generator in the CBM repo.** The existing `ClevelandBusinessMentoring/PRDs/deployment/generate-deployment-record.js` continues to be the source of `CBM-Test-Instance-Deployment-Record.docx` for now. After Prompt C lands and the application can regenerate that file, the JS generator can be retired in a separate cleanup.
- **No `inspect_server_for_record_values` execution from a real SSH connection in tests.** Tests use the JSON fixture directly. The SSH-execution path is exercised in Prompts B and C against real deploys / connections.

---

## Constraints and conventions

- **Python 3.11+ syntax.** Union types as `T | None`, `list[T]` over `List[T]`, etc.
- **Type hints on all public APIs.** Both arguments and return values.
- **Docstrings on public APIs.** `:param name:` / `:returns:` style consistent with `automation/core/deployment/ssh_deploy.py`.
- **Use `python-docx` (`docx` import).** Already a project dependency (`pyproject.toml`: `python-docx>=1.2.0`); existing usage in `tools/docgen/renderers/docx_renderer.py` is the model for styling helpers.
- **Match the visual output of `CBM-Test-Instance-Deployment-Record.docx` v1.2.** Same fonts (Arial), same colors (`#1F3864` navy header fills with white text, `#F2F7FB` alt-row fill, `#AAAAAA` table borders), same section ordering, same heading styles, same metadata table layout, same Revision History and Change Log table structure. The output of the new Python generator should, with identical inputs, be visually indistinguishable from the JS reference output. Differences in low-level XML are acceptable (different libraries produce slightly different internal markup) as long as the rendered Word document looks the same.
- **No external dependencies beyond `python-docx`** and the existing project deps. No `pypandoc`, no jinja2, no template files. The module is self-contained.
- **Tests use pytest** (the project standard). Use `tmp_path` fixture for output files. Do not write outside `tmp_path` from tests.
- **Path objects, not strings.** All file-path arguments are `pathlib.Path`.

---

## Detailed implementation

### 1. `automation/core/deployment/record_generator.py`

#### 1.1 The value-bag dataclass

```python
@dataclasses.dataclass
class DeploymentRecordValues:
    """Inputs to generate_deployment_record.

    All fields are required unless marked Optional. The generator does
    not invent values; missing optional fields are rendered as a
    placeholder string ("not captured") so the document remains
    structurally complete.
    """

    # Document metadata
    document_version: str                    # e.g. "1.0"
    document_last_updated: str               # MM-DD-YY HH:MM, e.g. "05-02-26 06:00"
    document_status: str                     # e.g. "Active — reflects live system as of Last Updated"

    # Instance identification (from Instance and Client tables)
    client_name: str                         # e.g. "Cleveland Business Mentors"
    instance_name: str                       # e.g. "CBMTEST"
    instance_code: str                       # e.g. "CBMTEST"
    environment: str                         # "test", "staging", or "production"
    application_url: str                     # e.g. "https://crm-test.clevelandbusinessmentors.org/"
    admin_username: str                      # e.g. "admin"
    instance_created_at_utc: str             # ISO 8601, from Instance.created_at

    # Hosting / Droplet (from InstanceDeployConfig + on-server inspection)
    hosting_provider: str                    # e.g. "DigitalOcean"
    droplet_id: str | None                   # e.g. "561480073" — None if not applicable
    droplet_detail_url: str | None           # derived from droplet_id
    droplet_console_url: str | None          # derived from droplet_id
    region: str                              # e.g. "NYC3"
    hostname: str                            # from on-server inspection
    public_ipv4: str                         # from InstanceDeployConfig.ssh_host
    droplet_size_summary: str                # e.g. "2 vCPU / 4 GB RAM / 80 GB SSD"
    os_release: str                          # e.g. "Ubuntu 22.04.5 LTS (jammy)"
    kernel: str                              # e.g. "5.15.0-171-generic"
    cpu_count: int                           # e.g. 2
    memory_summary: str                      # e.g. "3.8 GiB"
    disk_summary: str                        # e.g. "78 GB (root filesystem on /dev/vda1)"
    swap_summary: str                        # e.g. "2 GB swapfile (/swapfile)"
    ufw_summary: str                         # e.g. "active; allows 22 / 80 / 443 (IPv4 and IPv6)"
    backups_enabled: bool                    # DigitalOcean weekly backups status

    # Domain / DNS (administrator-supplied; not auto-detectable)
    primary_domain: str                      # e.g. "clevelandbusinessmentors.org"
    domain_registrar: str                    # e.g. "Porkbun"
    dns_provider: str                        # may equal registrar
    instance_subdomain: str                  # e.g. "crm-test"

    # TLS certificate (from openssl s_client inspection)
    tls_issuer: str                          # e.g. "C = US, O = Let's Encrypt, CN = E7"
    tls_subject: str                         # e.g. "CN = crm-test.clevelandbusinessmentors.org"
    tls_issued_utc: str                      # e.g. "2026-03-28 20:35:38 UTC"
    tls_expires_utc: str                     # from InstanceDeployConfig.cert_expiry_date or live inspection
    tls_sha256_fingerprint: str              # colon-separated upper-hex

    # EspoCRM application
    espocrm_version: str                     # e.g. "9.3.4"
    espocrm_install_completed_utc: str       # from on-server inspection
    espocrm_install_path: str                # e.g. "/var/www/espocrm"
    mariadb_version: str                     # e.g. "12.2.2"
    nginx_version: str                       # e.g. "1.29.7"
    docker_version: str                      # e.g. "29.3.1"
    docker_compose_version: str              # e.g. "v5.1.1"

    # SSH access
    ssh_authorized_user: str                 # "root"
    ssh_key_algorithm: str                   # "ED25519"
    ssh_key_comment: str                     # e.g. "crm-deploy"
    ssh_key_fingerprint: str                 # SHA256:... format

    # Credential references (Proton Pass entry names; values never appear)
    proton_pass_admin_entry: str             # e.g. "CBM-ESPOCRM-Test Instance Admin"
    proton_pass_db_root_entry: str           # e.g. "ESPOCRM Root DB Password - Test Instance"
    proton_pass_hosting_entry: str           # e.g. "DigitalOcean-CRM Hosting - Test Instance"

    # Deployment history (rows of {date_utc, event, notes} dicts)
    deployment_history: list[dict[str, str]]

    # Open items (rows of {id, item, status_or_plan} dicts)
    open_items: list[dict[str, str]]

    # Revision History and Change Log entries
    revision_history: list[dict[str, str]]   # {version, date, notes}
    change_log: list[dict[str, str]]         # {version, date, changes}

    def __post_init__(self) -> None:
        """Validate required string fields are non-empty.

        Optional fields (typed as `T | None`) may be None; required
        fields (typed as `T`) must be present and, for strings, non-empty.
        """
        # Implementation: iterate over fields, check that non-Optional string
        # fields are non-empty. Raise ValueError listing all missing fields.
```

Field naming follows the JS generator's section / row labels closely so the mapping between Python and the generated Word doc is obvious. Where the JS generator has a hardcoded value (e.g. "Cleveland Business Mentors" in the title), the Python generator takes that value as input — so the same generator works for any client.

#### 1.2 The generator function

```python
def generate_deployment_record(
    values: DeploymentRecordValues,
    output_path: Path,
) -> Path:
    """Generate a per-instance Deployment Record .docx.

    :param values: Populated DeploymentRecordValues bag.
    :param output_path: Path where the .docx should be written. Parent
        directory is created if it does not exist.
    :returns: The output_path on success.
    :raises ValueError: If values fails post-init validation.
    :raises OSError: If the output cannot be written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = _build_document(values)
    doc.save(str(output_path))
    return output_path
```

`_build_document` is the private workhorse that mirrors the JS generator's `children.push(...)` sequence, calling internal helpers for each section. Implementation strategy: section by section, exactly matching the JS generator's structure so that any future divergence is easy to spot.

#### 1.3 Server-inspection helper

```python
def inspect_server_for_record_values(
    ssh: paramiko.SSHClient,
    instance: Instance,
    deploy_config: InstanceDeployConfig,
    administrator_inputs: AdministratorInputs,
) -> DeploymentRecordValues:
    """Capture live on-server state and assemble a DeploymentRecordValues.

    Combines four inputs:
    - Database state (Instance row, InstanceDeployConfig row)
    - Live SSH inspection of the deployed Droplet
    - Live SSL certificate inspection (does not require SSH)
    - Administrator-supplied values that cannot be auto-detected
      (registrar, DNS provider, DigitalOcean Droplet ID, primary
      domain when it differs from the application URL's domain, etc.)

    :param ssh: An open paramiko SSHClient connected to the Droplet.
    :param instance: The Instance row from the per-client database.
    :param deploy_config: The InstanceDeployConfig row associated with
        the Instance.
    :param administrator_inputs: Values the administrator must supply
        (see AdministratorInputs dataclass, defined alongside).
    :returns: A populated DeploymentRecordValues ready for
        generate_deployment_record.
    """
```

`AdministratorInputs` is a small sibling dataclass with the four-or-five values that cannot be auto-detected: `domain_registrar`, `dns_provider`, `droplet_id`, `backups_enabled`, and the two Proton Pass entry names that aren't derivable from the instance code. Prompts B and C are responsible for collecting these from the administrator (B: the wizard's success page; C: a small dialog).

The on-server inspection runs the same commands documented in the on-server diagnostic from the deployment-record-record-production work (see Deployment Runbook §11.1 for the conceptual list and `ClevelandBusinessMentoring/PRDs/deployment/CBM-Test-Instance-Deployment-Record.docx` for the values that must be captured). Each command is a `run_remote(ssh, ...)` call; the helper parses the output into the relevant `DeploymentRecordValues` field.

Specific commands (run as root on the Droplet):
- `lsb_release -a` → `os_release`
- `uname -r` → `kernel`
- `nproc` → `cpu_count`
- `free -h` (parsed) → `memory_summary`
- `df -h /` (parsed) → `disk_summary`
- `swapon --show` (parsed) → `swap_summary`
- `ufw status` (parsed) → `ufw_summary`
- `hostname` → `hostname`
- `docker --version` (parsed) → `docker_version`
- `docker compose version` (parsed) → `docker_compose_version`
- `stat -c '%w' /var/www/espocrm` → `espocrm_install_completed_utc`
- `docker exec espocrm php -r "..."` to read the EspoCRM version (per the strategy used in `automation/core/deployment/upgrade_ssh.py`)
- `docker exec espocrm-db mariadb --version` (parsed) → `mariadb_version`
- `docker exec espocrm-nginx nginx -v 2>&1` (parsed) → `nginx_version`
- `awk '{print $1, $NF}' /root/.ssh/authorized_keys` → `ssh_authorized_user`, `ssh_key_algorithm`, `ssh_key_comment`
- `ssh-keygen -l -f /root/.ssh/<key>.pub` → `ssh_key_fingerprint`

The TLS inspection is performed locally (no SSH required) using `socket.create_connection` plus the `ssl` and `cryptography` standard-library / project-included modules:
- `tls_issuer`, `tls_subject`, `tls_issued_utc`, `tls_expires_utc`, `tls_sha256_fingerprint`

If `cryptography` is not already a dep, use the lower-level `ssl` module's certificate APIs and `hashlib` for the fingerprint. (Confirm by checking `pyproject.toml`; do not add new deps in this prompt.)

Each command's parsing logic is small and lives in a private helper named `_parse_*` (e.g. `_parse_os_release`, `_parse_swap_summary`). Helpers are tested via the JSON fixture in tests, not against live SSH.

#### 1.4 Section structure

The `_build_document` function builds the Word document section by section in this exact order, matching the JS reference:

1. Title block — centered, large, navy
2. Metadata table — 2-column, label fill `#F2F7FB`
3. Revision History (Heading 1) — striped 3-column table
4. Section 1 — Document Purpose and Scope (prose paragraphs and bulleted scope-includes / scope-excludes)
5. Section 2 — Deployment Summary (prose intro + striped 2-column table)
6. Section 3 — DigitalOcean Droplet
   - 3.1 Droplet Identification (striped 2-column table including Droplet ID and the two URLs derived from it)
   - 3.2 Hardware and Image (striped 2-column table)
   - 3.3 Firewall (prose)
   - 3.4 Backups (prose; varies by `values.backups_enabled`)
7. Section 4 — Domain and DNS
   - 4.1 Domain and Registrar (striped 2-column table)
   - 4.2 A Record (striped 2-column table)
   - DNS-resolution-confirmation closing paragraph
8. Section 5 — TLS Certificate
   - Striped 2-column table
   - 5.1 Renewal Failure Handling (prose)
9. Section 6 — EspoCRM Application
   - 6.1 Application Identification (striped 2-column table)
   - 6.2 Install Method (prose)
   - 6.3 Container Stack (striped 3-column table) — with versions inline per the v1.1 enhancement
   - 6.4 Install Location (striped 2-column table)
   - 6.5 Database (striped 2-column table) — Engine / Version / Image as separate rows per the v1.1 enhancement
10. Section 7 — SSH Access
    - Striped 2-column table
    - 7.1 Adding an Additional Authorized Key (prose + bulleted steps)
11. Section 8 — Credentials Inventory (prose intro + striped 3-column table)
12. Section 9 — Deployment History (striped 3-column table from `values.deployment_history`)
13. Section 10 — Operational Notes (10.1–10.4, mostly prose)
14. Section 11 — Open Items (striped 3-column table from `values.open_items`)
15. Change Log (Heading 1) — striped 3-column table from `values.change_log`

Each section's prose is the same as the JS reference; copy the prose verbatim. Where the JS reference has a CBM-specific value, replace it with a reference to the corresponding `values.*` field. The intent is that running the Python generator with the CBM Test fixture produces a document whose content is identical to `CBM-Test-Instance-Deployment-Record.docx` v1.2 (modulo trivial XML differences from the different libraries).

### 2. CLI entry point

A small `__main__` block at the bottom of `record_generator.py`:

```python
if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Generate a Deployment Record .docx from a JSON fixture."
    )
    parser.add_argument("--values", type=Path, required=True,
                        help="Path to a JSON file matching DeploymentRecordValues.")
    parser.add_argument("--output", type=Path, required=True,
                        help="Path to write the .docx.")
    args = parser.parse_args()

    data = json.loads(args.values.read_text())
    values = DeploymentRecordValues(**data)
    out = generate_deployment_record(values, args.output)
    print(f"Wrote {out} ({out.stat().st_size:,} bytes)")
```

### 3. Tests

`tests/test_record_generator.py`:

- `test_values_validates_required_fields_non_empty` — empty `instance_code` raises `ValueError` listing the field name.
- `test_values_accepts_optional_none` — `droplet_id=None` validates successfully.
- `test_generate_writes_file` — generator writes to `tmp_path / "out.docx"`; file exists; file size > 10 KB.
- `test_generated_docx_opens_in_python_docx` — `docx.Document(str(out))` returns a Document instance with at least 100 paragraphs.
- `test_generated_docx_contains_expected_strings` — opens the generated file; concatenates all paragraph and table-cell text; asserts the presence of the instance code, the application URL, all three Proton Pass entry names, the EspoCRM version, the MariaDB version, the nginx version, the deploy date, and the SHA-256 cert fingerprint.
- `test_generated_docx_validates_with_office_validator_when_available` — runs the office validator if `/mnt/skills/public/docx/scripts/office/validate.py` is reachable; otherwise xfails with a skip message rather than failing CI.
- `test_cli_round_trip` — invokes the module's CLI via `subprocess.run([sys.executable, "-m", "automation.core.deployment.record_generator", "--values", fixture, "--output", tmp_path / "cli.docx"])`; asserts exit code 0 and file exists.

### 4. Fixture

`tests/fixtures/deployment_record_values_cbmtest.json`: a JSON file whose values match the v1.2 CBM Test Instance Deployment Record. The values to use are exactly the ones in `CBM-Test-Instance-Deployment-Record.docx` v1.2. Treat that document as the source of truth for the fixture; do not invent values.

---

## Acceptance criteria

- All tests in `tests/test_record_generator.py` pass.
- Running `uv run python -m automation.core.deployment.record_generator --values tests/fixtures/deployment_record_values_cbmtest.json --output /tmp/test.docx` produces a file that opens in Word / LibreOffice and visually resembles the existing CBM Test Instance Deployment Record v1.2.
- `uv run ruff check automation/core/deployment/record_generator.py tests/test_record_generator.py` passes.
- No changes to any file outside `automation/core/deployment/record_generator.py`, `tests/test_record_generator.py`, and `tests/fixtures/deployment_record_values_cbmtest.json`.
- The `automation/core/deployment/__init__.py` is unchanged unless a new export is genuinely needed (it almost certainly isn't; the generator is a leaf module).

---

## Notes for the implementer

- The JS generator is the structural authority. When in doubt about prose, table structure, or row order, mirror the JS exactly. The Python generator is a port, not a redesign.
- `python-docx` does not have a direct equivalent of `docx`'s React-style child push pattern. Build helpers that approximate it (`add_paragraph`, `add_table`, etc.) and use them consistently.
- `python-docx`'s table styling is more verbose than `docx`'s. Encapsulate cell styling (border color, fill, font, bold, color) in a single `_styled_cell()` helper so callers stay readable.
- For headings: use named styles ("Heading 1", "Heading 2") and set their run properties (font Arial, color `1F3864`, sizes matching the JS reference) once at document setup. The JS reference uses 30 / 26 / 24 half-point sizes for H1 / H2 / H3.
- The Revision History and Change Log are deliberately separate tables, even though they're conceptually related. Keep them separate to match the JS reference; the Revision History is a high-level summary and the Change Log is detailed per-version content notes.
