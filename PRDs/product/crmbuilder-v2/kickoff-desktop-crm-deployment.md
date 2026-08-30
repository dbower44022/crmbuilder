# Kickoff — Admin-driven CRM deployment from the v2 desktop

Kickoff for the planning item that lets an administrator provision a new self-hosted CRM instance from the v2 desktop, executed by the cloud service as a resumable background job. Decisions were made with Doug on 2026-08-29; governance records (requirement, decisions, project, release, terms) live in the store — this file carries the approved build plan only.

---

## Context

CRMBuilder v2 can configure an EspoCRM instance (publish) but cannot stand one up. Provisioning lives only in the v1 desktop Deployment tab (`automation/core/deployment/ssh_deploy.py` + a Qt wizard), assumes the droplet and DNS already exist, and writes to a separate SQLite store the v2 service cannot see. The Master CRMBuilder PRD's Phase 11 (CRM Deployment) is still a placeholder and DEC-320 puts provisioning explicitly inside the framework's mission.

Goal: an admin opens the v2 desktop, fills in a short wizard, and the cloud service creates the server, sets DNS, installs EspoCRM, verifies it, and registers the resulting instance — with a durable, shared record of every run.

## Decisions made with Doug (2026-08-29)

| # | Topic | Decision |
|---|---|---|
| 1 | Scope | **Full provisioning**: DigitalOcean droplet via DO API → Cloudflare A record (DNS-only / grey cloud, GVR-182) → wait for DNS → v1 SSH install phases → verify → register instance. |
| 2 | Execution | **Cloud service** (api.crmbuilder.ai), not the desktop. |
| 3 | Access | **Admin-only** principals (existing `require_permission("admin")`, held by `owner`). |
| 4 | Job model | **True background job** owned by the service; desktop polls status/log. First background machinery in v2. |
| 5 | Accounts | **Per engagement**, CRMBuilder's own DO/Cloudflare tokens as the default; a customer may supply its own. |
| 6 | Failure | **Keep and report** — never auto-destroy; record droplet id/IP/failed phase; admin retries from the failed phase or cleans up in DigitalOcean. |
| 7 | Terminology | *deploy run* (DEP-NNN), *deploy phase*, *provider credential*, *deploy worker* — **approved by Doug 2026-08-29** (GVR-232); record as glossary terms in the governance step. |

## Governance preconditions (GVR-230 — before any code)

1. **Requirement** (≤75 words, ≤4 sentences, no embedded IDs, acceptance criteria; LSN-036), e.g. *"An administrator can provision a new self-hosted CRM instance from the desktop. The service creates the server and DNS record, installs and verifies the CRM as a resumable background job, and registers the resulting instance. A failed run keeps what was built and reports it."* Edges: `requirement_defined_in_conversation`, `requirement_belongs_to_topic` (TOP-091 instance scope), then `requirement_approved_by_decision`.
2. **Decisions** to record: (a) approve the requirement; (b) DO-droplet/Cloudflare shape supersedes the EspoCloud provider-API "Path A" in `PRDs/product/features/feat-crm-deployment.md` §4; (c) **GVR-240 boundary** — provisioning a *customer* droplet from an engagement credential is in scope; deploying CRMBuilder itself to 138.197.72.15 remains human-only, and the worker hard-refuses that host; (d) terminology approval.
3. **Planning item** with `planning_item_implements_requirement`, inside a project and release; slices A–E below `addresses` it, build-closure `resolves` it after Doug pushes (LSN-047).
4. Every commit: `Governed-By: PI-NNN`; commit with explicit pathspec; Model A (governance recorded on main).
5. Hard constraint: **no new Python dependencies** (droplet venv has no pip/uv) — DO/Cloudflare via `requests`; `paramiko`, `dnspython` already present; `automation/` ships in the distribution.

## Design

### Reuse (do not rewrite)
- `automation/core/deployment/ssh_deploy.py`: `SelfHostedConfig`, `connect_ssh`, `run_remote`, `mask_credentials`, `wait_for_dns`, `phase_server_prep`, `phase_install_espocrm`, `phase_post_install`, `phase_verify` — Qt-free, called as-is.
- `crmbuilder_v2/access/repositories/publish_runs.py` — template for `deploy_runs.py` (identifier SAVEPOINT retry loop, list/get/create).
- `api/routers/instances.py` `_store` (l.71) / `_resolve_secret_or_none` (l.644) — the secret boundary (`SecretBackendError` → 422). Lift into a shared helper.
- `ui/dialogs/audit_progress_dialog.py` + `ui/workers.py::run_in_thread` — template for the progress dialog.
- `ui/panels/publish_history.py` — template for Deploy History panel.
- `crmbuilder_v2/secrets.py` (Fernet store, keyring fallback) for every new secret.

### Data (non-governed run tables, DEC-447 precedent — no change_log/refs CHECK changes)
- `deploy_runs`: `deploy_run_identifier` DEP-NNN, `instance_identifier` (null until registered), `status` ∈ {queued, running, succeeded, succeeded_with_issues, failed, cancelled}, `phase`, `spec` JSON (non-secret request), `secret_refs` JSON, `state` JSON (checkpoint: droplet_id, droplet_ip, dns_record_id, ssh_key_id, cert_expiry, per-phase status, verify checks, cancel flag), `log` JSON (capped, masked), `error`, `requested_by`, `worker_id`, `heartbeat_at`, `started_at/ended_at`.
- `provider_credentials`: (engagement, provider ∈ {digitalocean, cloudflare}) → `token_ref`, `label`. UNIQUE per engagement+provider.
- `instance_deploy_configs` additions: `db_password_ref`, `admin_password_ref`, `admin_username`, `droplet_ip`, `droplet_region`, `droplet_size`, `dns_record_id`, `last_deploy_run_identifier`.
- Vocab in `access/vocab.py` next to `PUBLISH_RUN_STATUSES`: `DEPLOY_RUN_STATUSES`, `DEPLOY_RUN_PHASES`, `PROVIDER_CREDENTIAL_PROVIDERS`.
- Migrations on **both heads**: `migrations/versions/0116_…` and `migrations/pg/versions/0073_…`, with the `_table_exists` / column-inspect guards from 0110 / pg 0067.

### Background job
- `crmbuilder_v2/deploy/worker.py::DeployWorker` — a daemon thread started in the API lifespan (`config.deploy_worker_inprocess`, default on) and also runnable standalone as console script `crmbuilder-v2-deploy-worker` (same class; config flip, no new systemd unit needed to start). Cross-engagement claim with enforcement off, then `active_engagement(run.engagement_id)`.
- Claim = single conditional UPDATE (`queued`, or `running` with stale heartbeat > 180 s). Heartbeat every 30 s and on log flush (batched). Service restart → stale claim → reclaimed and **resumed from the checkpoint**.
- Cancel checked between phases only. Retry re-queues a failed run in place (same DEP, checkpoint preserved).

### Phase state machine (`crmbuilder_v2/deploy/runner.py`) — each phase idempotent
`validate` (resolve tokens + secrets, DO `GET /v2/account`, CF zone read, protected-host refusal, generate ed25519 keypair → secret ref + DO account key) → `create_droplet` (skip if droplet_id; recover by tag `DEP-NNN`) → `wait_droplet` (active + public IPv4, 10 min) → `create_dns` (upsert A record, `proxied=false`, ttl 60) → `wait_dns` (`wait_for_dns`) → `server_prep` → `install_espocrm` → `post_install` (cert expiry) → `verify` (failures → `succeeded_with_issues`) → `create_instance` (create `instances` row url=https://domain, role=both, auth basic, secret=admin password; upsert deploy config with all provisioning facts; set `run.instance_identifier`; terminal status in the same commit).
- Failure: phase error + status `failed`; droplet id/IP retained and surfaced ("server still exists — clean up in DigitalOcean").
- SSH key: v1 `connect_ssh` wants a path → small adapter writes the ref'd private key to a 0600 tempfile for the session; `resolve_ssh_credential()` accepts ref or path.

### Providers (`crmbuilder_v2/deploy/providers/`)
- `digitalocean.py`: `list_regions/sizes/images/ssh_keys`, `create_droplet`, `get_droplet`, `list_droplets(tag)`, `add_ssh_key`.
- `cloudflare.py`: `list_zones`, `find_a_record`, `upsert_a_record(proxied=False)`.
- Token masking added to the log path alongside `mask_credentials`.

### API (envelope `{data, meta, errors}`; admin gate `Depends(require_permission("admin"))`)
- `/provider-credentials`: `GET` (configured flags only), `PUT /{provider}` `{token, label?}`, `DELETE /{provider}`, `GET /digitalocean/options`, `GET /cloudflare/zones`.
- `/deploy-runs`: `POST` (spec; auto-generate DB passwords when omitted; reject a second queued/running run for the same domain) → 202; `GET` list; `GET /{id}?log_after=N`; `POST /{id}/cancel`; `POST /{id}/retry`; `GET /worker` health.
- `PUT /instances/{id}/deploy-config` learns `db_password` / `admin_password` → refs.
- Register routers in `api/main.py`; literal sub-paths before `/{identifier}` (GVR-153).

### Desktop
- `ui/dialogs/deploy_wizard_dialog.py` (QStackedWidget, Back/Next/Deploy, all network calls via `run_in_thread`): 1 Providers (status + "Set…" → `provider_credentials_dialog.py`) · 2 Server (region/size/image/SSH keys from `/options`, instance name) · 3 Domain (zone, subdomain, FQDN preview, Let's Encrypt email; note why DNS-only) · 4 Accounts (admin user/email/password + generate; DB passwords auto-generate default) · 5 Review → POST → progress dialog.
- `ui/dialogs/deploy_progress_dialog.py`: `QTimer` 2 s poll with `log_after`, phase progress bar, Cancel (→ `/cancel`), Close always enabled (job continues server-side); on success emits the new instance id so Instances panel refreshes/selects.
- `ui/panels/deploy_history.py` (`ListDetailPanel`): DEP, status, phase, domain, instance, started; detail = spec, droplet id/IP (copyable), cert expiry, verify checks, error, log tail; context menu Open progress / Retry / Copy droplet id.
- `ui/panels/instances.py`: "Deploy new…" button on the action strip; `_deploy_config_section` gains droplet IP / DNS provider / last DEP rows. Hide-vs-show follows the audit precedent (GVR-217: never disable; hide only when the server says non-admin — extend `/admin/connection` with the principal's permissions).
- `ui/sidebar.py` "Deploy History" after "Publish History" (Governance group); `ui/main_window.py::build_panel` branch; `ui/client.py` methods mirroring `_publish_request`.

### Secrets
Plaintext only in request bodies; refs everywhere else; resolved only in the worker's `validate` phase; `GET /deploy-runs/{id}` never returns ref values; deleting a provider credential deletes its ref.

## Build slices (each mergeable; each `addresses` the PI)
- **A** Data + vocab + both migrations + repos (`deploy_runs.py`, `provider_credentials.py`, deploy-config columns) + repo/migration tests.
- **B** Provider credentials API + DO/CF clients + `/options` `/zones` + client methods + credentials dialog.
- **C** `spec.py`, `runner.py`, `worker.py`, lifespan/config/console script, deploy-runs API, deploy-config secret extensions + runner/worker/API tests. Feature complete via API.
- **D** Desktop wizard + progress dialog + Instances "Deploy new…" button.
- **E** Deploy History panel + sidebar + deploy-config detail rows + user/technical guide updates.
- **F (human, GVR-240)** production rollout via `scripts/deploy-production.sh`; optional switch to standalone worker.

## Verification
- Unit: fake `requests.Session` for DO/CF (assert `proxied=false`, idempotent upsert); fake SSH from `tests/test_ssh_deploy.py`; runner tests for happy path, failure-keeps-droplet, resume-skips-done-phases, cancel-between-phases, protected-host refusal; worker `run_once()` claim/heartbeat/stale-reclaim; API 202/403/422/redaction/`log_after`; UI tests via `StorageClient(client=TestClient(create_app()))` with worker disabled and `run_once()` driven manually.
- Migration head tests on both chains; `uv run pytest tests/crmbuilder_v2 -v`; `uv run ruff check`.
- Live proof before slice C merges: one real deploy against a throwaway DO droplet under CRMBuilder's account (human-triggered), including a forced failure at `create_dns` and a retry, then verify the registered instance audits and publishes.

## Risks
- Long SSH phases inside the API process during a restart → stale-claim resume; re-running `install_espocrm` after interruption must be tested on a real droplet.
- Cloudflare token scope (`Zone.DNS:Edit`) and DO rate limits — surfaced in `validate` as run errors, not 500s.
- Forgotten failed servers bill until cleaned up — history panel flags "server still exists"; in-app Discard deferred (decision 6).
- Admin = `owner` only today; a broader admin role is a vocab change later.
