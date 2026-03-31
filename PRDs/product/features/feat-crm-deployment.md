# CRM Builder — CRM Deployment

**Version:** 1.0
**Status:** Draft — Planned Feature
**Last Updated:** March 2026
**Depends On:** app-ui-patterns.md, app-logging-reporting.md

---

## 1. Purpose

This document defines the requirements for CRM Deployment in CRM
Builder — the process of establishing a working CRM instance before
configuration begins.

CRM Deployment bridges the gap between selecting a CRM platform
(Phase 3) and configuring it (Phase 5). It ensures the organization
has a running CRM instance with validated admin access, ready to
receive the configuration defined in the YAML program files.

---

## 2. Status

CRM Deployment is a planned feature. The requirements in this document
define the intended behavior. Implementation has not yet begun.

The current tool assumes the user already has a running CRM instance
and handles onboarding only through manual instance profile creation.

---

## 3. Two Deployment Paths

CRM Deployment supports two paths depending on the organization's
situation:

**Path A — Provision a New Instance**
The organization needs a new CRM instance. CRM Builder provisions one
on a supported hosting provider on their behalf.

**Path B — Onboard an Existing Instance**
The organization already has a CRM instance running (SaaS or
self-hosted). CRM Builder validates the connection and prepares it
for configuration.

Both paths result in a validated instance profile stored in CRM
Builder, ready for the configuration phase.

---

## 4. Path A — Provision a New Instance

### 4.1 Overview

CRM Builder provisions a new CRM instance on a hosting provider via
the provider's API. The user selects the provider, chooses a plan,
provides the necessary account details, and CRM Builder handles the
rest.

### 4.2 Provisioning Wizard

Provisioning runs as a multi-step wizard:

**Step 1 — Platform and Provider Selection**
- The user selects the CRM platform (e.g., EspoCRM)
- The user selects the hosting provider from the list of providers
  supported for that platform
- Available plans for the selected provider are displayed with
  pricing and feature information

**Step 2 — Instance Configuration**
- The user provides the instance name and any required configuration
  (subdomain, region, organization name, etc.)
- Required fields vary by provider and are defined in the
  provider-specific configuration

**Step 3 — Account and Billing**
- The user provides hosting provider account credentials or creates
  a new provider account
- Billing information is collected if required by the provider
- CRM Builder does not store payment information — billing is handled
  entirely by the provider

**Step 4 — Review and Confirm**
- A summary of the instance to be provisioned is shown
- Estimated monthly cost is displayed
- The user confirms before provisioning begins

**Step 5 — Provisioning**
- CRM Builder calls the hosting provider API to provision the instance
- Real-time status updates are shown as provisioning progresses
- Provisioning may take several minutes depending on the provider
- On completion, the instance URL and initial admin credentials are
  displayed and stored in an instance profile

**Step 6 — Validation**
- CRM Builder automatically validates the connection to the new
  instance (see Section 5)
- Any post-provisioning steps required by the provider are guided
  (e.g., email verification, initial setup wizard completion)

### 4.3 Supported Hosting Providers

Supported hosting providers are defined per CRM platform. The initial
target is EspoCRM with EspoCloud as the first supported provider.
Additional providers will be added based on demand.

Each provider integration defines:
- The provisioning API and authentication method
- The available plans and their features
- Required and optional configuration fields
- Post-provisioning steps required before the instance is ready

### 4.4 Provisioning Failure Handling

If provisioning fails at any step:
- The error is displayed with a clear explanation
- If a partial instance was created, instructions for cleaning it up
  are provided
- The user can retry or cancel

CRM Builder does not automatically delete partially provisioned
instances — the user retains control over what exists on the
hosting provider.

---

## 5. Path B — Onboard an Existing Instance

### 5.1 Overview

The user provides connection details for an existing CRM instance.
CRM Builder validates the connection, confirms admin access, and
stores the instance as a named profile.

### 5.2 Onboarding Wizard

**Step 1 — Platform Selection**
- The user selects the CRM platform of the existing instance

**Step 2 — Connection Details**
- The user provides:
  - Instance display name
  - Instance URL
  - Authentication method and credentials
  - Project folder path (optional at this stage)
- Authentication methods supported vary by platform (see Section 6)

**Step 3 — Validation**
- CRM Builder tests the connection and verifies admin access
- The platform version is detected and recorded
- Any known compatibility issues between the platform version and
  CRM Builder are reported
- On success, the instance profile is saved and the user is guided
  to the configuration phase

### 5.3 Validation Checks

Connection validation confirms:
- The instance is reachable at the provided URL
- The provided credentials authenticate successfully
- The authenticated user has admin-level access
- The platform version is compatible with CRM Builder

Each check is reported individually so the user can diagnose which
step failed if validation does not pass.

---

## 6. Authentication

### 6.1 Supported Authentication Methods

Authentication methods vary by CRM platform. Each platform defines
its supported methods in platform-specific documentation. CRM Builder
currently supports the following methods for EspoCRM:

| Method | Description | When to Use |
|---|---|---|
| API Key | A static key issued to an API user | API users with admin access |
| HMAC | Per-request signature using a key and secret | API users requiring higher security |
| Basic | Username and password | Admin users on EspoCRM Cloud where API users cannot be granted admin access |

### 6.2 Credential Storage

Credentials are stored locally in the instance profile file. They
are never transmitted to CRM Builder's servers or any third party.

Credentials are stored in plain text in the local instance profile.
The tool is intended for use on secured administrator machines. Users
are responsible for the security of their local machine and project
folder.

Credential fields in the UI are masked (displayed as bullets). The
user may reveal a credential field explicitly using a show/hide toggle.

---

## 7. Instance Profile Management

### 7.1 What an Instance Profile Contains

An instance profile stores everything CRM Builder needs to connect
to and work with a CRM instance:

- Display name
- CRM platform
- Instance URL
- Authentication method and credentials
- Project folder path (optional)
- Platform version (recorded at validation time)
- Hosting provider (if provisioned via CRM Builder)

### 7.2 Profile Operations

Instance profiles can be created, edited, and deleted from the
Instance panel in the main window. Editing a profile updates the
stored connection details. Deleting a profile removes it from CRM
Builder but does not affect the CRM instance itself.

### 7.3 Project Folder Association

Each instance profile may be associated with a project folder on
the local filesystem. The project folder contains:

```
ClientProjectFolder/
├── programs/             ← YAML program files
├── Implementation Docs/  ← generated reference manual
└── reports/              ← deployment and run reports
```

When a project folder is configured, CRM Builder automatically
creates these subdirectories if they do not exist.

---

## 8. Instance Maintenance

### 8.1 Platform Version Tracking

CRM Builder records the CRM platform version at the time of instance
validation. This is used to:
- Warn about compatibility issues before running configuration
- Identify when a platform update has occurred since the last
  validated connection

### 8.2 Platform Updates

When a CRM platform update is available for a provisioned instance:
- CRM Builder notifies the user that an update is available
- The user is shown what version is currently running and what is
  available
- For providers whose API supports it, CRM Builder can initiate
  the update
- After a platform update, re-validation is recommended to confirm
  compatibility

### 8.3 Re-validation

The user can re-validate any instance at any time to confirm the
connection is still working and the platform version is current.
Re-validation does not change any configuration — it only checks
the connection.

---

## 9. Output and Reporting

### 9.1 Output Panel Messages

Provisioning and onboarding operations emit messages to the output
panel following the conventions in `app-ui-patterns.md`:

```
[DEPLOY]  Connecting to EspoCloud API ... OK
[DEPLOY]  Creating instance "CBM Production" ... IN PROGRESS
[DEPLOY]  Waiting for instance to be ready ...
[DEPLOY]  Instance ready at https://cbm.espocloud.com
[DEPLOY]  Validating admin access ... OK
[DEPLOY]  Platform version detected: EspoCRM 9.3.3
[DEPLOY]  Instance profile saved: CBM Production

[ONBOARD] Testing connection to https://cbm.espocloud.com ... OK
[ONBOARD] Authenticating ... OK
[ONBOARD] Checking admin access ... OK
[ONBOARD] Platform version detected: EspoCRM 9.3.3
[ONBOARD] Instance profile saved: CBM Production
```

### 9.2 Deployment Report

Provisioning operations produce a deployment report written to the
project folder's `reports/` directory following the conventions in
`app-logging-reporting.md`:

```
cbm_production_deploy_{timestamp}.log
cbm_production_deploy_{timestamp}.json
```

Onboarding validation does not produce a report — it is a setup
step, not a configuration operation.

---

## 10. Validation Rules

Before provisioning:
- Platform and provider must be selected
- All required instance configuration fields must be filled
- Hosting provider account credentials must be provided

Before onboarding:
- Platform must be selected
- Instance URL must be a valid URL
- Authentication credentials must be provided

---

## 11. Future Considerations

- **Additional hosting providers** — EspoCloud is the first target.
  Other self-hosted and SaaS providers will be added based on demand.
- **Additional CRM platforms** — as support for Salesforce, HubSpot,
  and other platforms is added, their deployment paths and
  authentication methods will be defined here.
- **Backup and restore** — initiating and restoring backups via the
  hosting provider API is a natural extension of the deployment
  feature.
- **Instance cloning** — copying a configured instance to create a
  test environment is a common need that may be addressed as a
  provisioning option.
- **Multi-instance management** — organizations managing multiple
  CRM instances (e.g., one per region or client) may benefit from
  bulk operations across instances.
