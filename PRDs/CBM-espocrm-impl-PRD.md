# CRM Builder — Product Requirements Document

**Version:** 2.0  
**Status:** Current  
**Last Updated:** March 2026

---

## 1. Overview

The CRM Builder is a desktop application that automates
the configuration of EspoCRM instances. It reads declarative YAML program
files and applies their contents via the EspoCRM REST API, replacing manual
configuration through the EspoCRM admin UI.

### 1.1 Core Principles

**Declarative** — configuration is described in YAML files, not scripted
procedurally. The YAML files define the desired end state; the tool
determines what needs to change.

**Idempotent** — running the same program file multiple times produces the
same result. The tool checks the current state before acting and only makes
changes where the instance differs from the spec.

**Verifiable** — every operation can be independently verified. After
deployment, a verify pass re-reads all configured items and confirms they
match the specification.

**Single source of truth** — YAML files are the authoritative definition
of an EspoCRM configuration. The running instance and the generated
reference documentation are both outputs derived from the YAML files.

### 1.2 Target Users

Technical administrators responsible for configuring and maintaining
EspoCRM instances for CBM and future clients. Users are expected to be
comfortable with YAML but should not need to understand the EspoCRM
REST API directly.

---

## 2. Current Capabilities

### 2.1 Instance Management

- Add, edit, and delete EspoCRM instance profiles
- Store connection profiles (URL, auth credentials, project folder) in
  local JSON files
- Support three authentication methods: API Key, HMAC, Basic
- Each instance is bound to a **project folder** containing its YAML
  program files, reports, and generated documentation

### 2.2 Entity Management

- Create custom EspoCRM entities (Base, Person, Company, Event types)
- Delete custom entities
- Delete-and-recreate for clean deployments
- Confirmation dialog with two modes: Skip Deletes (safe) or Full Rebuild

### 2.3 Field Management

- Create and update custom fields on any entity (native or custom)
- Skip fields where no change is needed (idempotent)
- Verify fields after deployment

**Supported field types:** varchar, text, wysiwyg, enum, multiEnum, bool,
int, float, date, datetime, currency, url, email, phone

### 2.4 Layout Management

- Deploy detail view layouts (panels, tabs, rows)
- Deploy list view column definitions
- Support category-based tab auto-population and explicit row definitions
- Support Dynamic Logic panel visibility conditions
- Apply c-prefix to custom field names in layout payloads automatically

### 2.5 Relationship Management

- Create one-to-many, many-to-one, and many-to-many relationships
- Check for existing relationships before creating (idempotent)
- Skip pre-existing manually-created relationships (action: skip)
- Handle c-prefix auto-application on native entity link names
- Verify relationships after creation

### 2.6 Documentation Generation

- Generate a structured reference manual (Markdown + Word) from YAML files
- Sections: Entities, Fields, Layouts, Views, plus placeholder sections
  for Filters, Relationships, Processes
- Output to project folder's Implementation Docs/ directory
- Generate Docs button in the UI

### 2.7 Reporting

- Write .log and .json reports after every Run and Verify operation
- Reports written to the instance's project folder reports/ directory
- Filename includes instance name, operation type, timestamp, and
  content_version of the program file

---

## 3. YAML Program File Format

### 3.1 Top-Level Structure

```yaml
version: "1.0"
content_version: "1.0.0"
description: "Short description"

entities:
  EntityName:
    description: >   # required
      Business rationale, role in data model, PRD reference.
    action: delete_and_create
    type: Base
    labelSingular: "Name"
    labelPlural: "Names"
    stream: true
    fields: [...]
    layout:
      detail:
        panels: [...]
      list:
        columns: [...]

relationships:
  - name: relName
    ...
```

### 3.2 Versioning

- `version` — YAML schema version (do not change, always "1.0")
- `content_version` — semantic version of this file's content
  - PATCH: description updates, comment fixes
  - MINOR: new fields or enum values added
  - MAJOR: fields removed, types changed, entity restructured

### 3.3 Entity Name Mapping

Custom entities use a C-prefix internally in EspoCRM. The tool translates
automatically using a hardcoded mapping table. The default rule is
C{name} for unmapped entities.

### 3.4 Native Entity Link Names

When a native entity (Account, Contact) is the primary side of a
relationship, EspoCRM auto-applies a c-prefix to the link name. The
tool handles this automatically in check and verify steps. Specify
link names in YAML without the c-prefix.

---

## 4. Processing Pipeline

```
1. Entity deletions    → cache rebuild
2. Entity creations    → cache rebuild
3. Field operations    (check → act → verify per field)
4. Layout operations   (check → act → verify per layout)
5. Relationship ops    (check → act → verify per relationship)
```

---

## 5. Project Folder Structure

Each instance is bound to a project folder:

```
ProjectFolder/
├── programs/            ← YAML program files
├── Implementation Docs/ ← generated reference manual
└── reports/             ← run/verify reports
```

---

## 6. Deployment Architecture

```
Tool repo (crmbuilder)
  ├── espo_impl/   ← application source code
  ├── tools/       ← utilities (doc generator)
  ├── docs/        ← tool documentation
  ├── PRDs/        ← tool specs
  └── tests/       ← test suite

Client repo (e.g. ClevelandBusinessMentoring)
  ├── PRDs/                 ← source PRD documents
  ├── programs/             ← YAML program files
  ├── Implementation Docs/  ← generated reference manual
  └── reports/              ← deployment reports (optional)
```

The tool repo contains no client data.

---

## 7. Known Limitations

Items that must be configured manually in EspoCRM:

- File attachment fields
- Formula fields (calculated values)
- Dynamic Logic on individual fields
- Role-based access control
- Workflow automation
- Email templates
- Dashboard layouts
- Search presets / saved views
- Report definitions
- Third-party integrations (LimeSurvey, Stripe, etc.)

---

## 8. Planned Future Phases

| Phase | Feature |
|---|---|
| Next | Dynamic Logic on individual fields |
| Next | Search presets / saved views |
| Future | Role-based access control |
| Future | Workflow automation |
| Future | Relationship panel layout configuration |

---

## 9. Technical Stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| Package manager | uv |
| GUI framework | PySide6 (Qt6) |
| HTTP client | requests |
| YAML parser | pyyaml |
| Document generation | python-docx, Node.js docx npm |
| Test framework | pytest |

---

## 10. Confirmed API Endpoints (EspoCRM v9.3.3)

| Operation | Method | Endpoint |
|---|---|---|
| Read field | GET | /api/v1/Metadata?key=entityDefs.{Entity}.fields.{field} |
| Create field | POST | /api/v1/Admin/fieldManager/{Entity} |
| Update field | PUT | /api/v1/Admin/fieldManager/{Entity}/{field} |
| Read entity | GET | /api/v1/Metadata?key=scopes.{Entity} |
| Create entity | POST | /api/v1/EntityManager/action/createEntity |
| Delete entity | POST | /api/v1/EntityManager/action/removeEntity |
| Rebuild cache | POST | /api/v1/Admin/rebuild |
| Read layout | GET | /api/v1/Layout/action/getOriginal?scope={Entity}&name={type} |
| Save layout | PUT | /api/v1/{Entity}/layout/{type} |
| Read link | GET | /api/v1/Metadata?key=entityDefs.{Entity}.links.{link} |
| Create relationship | POST | /api/v1/EntityManager/action/createLink |
| Delete relationship | POST | /api/v1/EntityManager/action/removeLink |
