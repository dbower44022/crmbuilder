# CRMBuilder v2 — User Guide

A practical walkthrough of the v2 desktop application and the MCP/REST
surfaces that operate against the same database. Aimed at the daily
operator: project owner, methodology author, or anyone driving v2
governance content (decisions, sessions, risks, planning items,
topics, charter, status, references).

For architecture and extension patterns, see `TECHNICAL-GUIDE.md`. For
the full requirements specification, see
`PRDs/product/crmbuilder-v2/ui-PRD-v0.2.md`. For the operations
reference (env vars, REST surface, troubleshooting matrix), see the
project `README.md`.

---

## What v2 is and isn't

v2 is the **structured-database source of truth** for the CRMBuilder
methodology. Eight governance entity types live in a SQLite database
with ACID writes; each successful write rebuilds JSON snapshots that
ride alongside the code in git. Three surfaces read and write the
same database:

- **The PySide6 desktop UI** (`crmbuilder-v2-ui`). The everyday tool.
- **The REST API** (`crmbuilder-v2-api`, port 8765). The durable
  client interface.
- **The MCP server** (`crmbuilder-v2-mcp`). Lets a Claude session
  read and write directly.

v2 is **not** the configuration deployment engine — that's v1
(`crmbuilder` proper) and continues to live under `espo_impl/` and
`automation/`. v2 is upstream of the engine: the methodology
artifacts that become deployable YAML one day live here.

---

## Conduct framework for stakeholder-facing interviews

v2 stores methodology artifacts. The *conduct* of the interviews that
produce those artifacts is governed separately, by three files at
`PRDs/process/conduct/` in the parent crmbuilder repo. Anyone running a
stakeholder-facing methodology session against v2 — whether under the
current 13-phase Document Production Process or the evolved 5-phase
methodology — operates under these rules.

The three files are methodology-agnostic. They do not know how many
phases there are, what the deliverables look like, or whether the
deliverable is a Word document or a database row. They govern the
human-AI interaction during the interview.

- **`conduct/charter.md`** — global conduct rules. Eleven sections
  covering the AI's role as a skilled business analyst (not system
  designer), plain-language communication, question discipline (one
  at a time, open before closed), listening and probing, confirmation
  cadence, when not to ask, scope-change protocol, transcript capture,
  identifier discipline (the human-readable name precedes the
  identifier in parentheses, every time), and anti-patterns. **The
  most important rule** is §11.6.b "inferences require positive
  support" — pattern-matching against generic operations for similar
  organizations does not qualify as positive support for an inference.
  Either get positive support from what the stakeholder said or surface
  the inference as an explicit question.
- **`conduct/kickoff.md`** — pre-session priming protocol. Three
  layers (internal pre-session checklist, framing to the stakeholder,
  calibrating the stakeholder) and four session-type variants
  (administrator-as-proxy, first-time SME, follow-up, multi-stakeholder).
  Phase-specific notes for both methodologies. Layer 3 (calibrating
  the stakeholder) is the part most directly aimed at making
  interviews less painful for the person providing information.
- **`conduct/question-library.md`** — eighteen annotated good/bad
  question patterns across six categories: people and roles, work,
  information, boundaries, handling difficulty, decisions and
  confirmation. Phase guides cite specific entries by number.

### When to consult them

- **Before any stakeholder-facing session.** Read the charter end-to-end
  once per session unless it's already in context; consult kickoff for
  the relevant phase notes; load the relevant question library entries.
- **During a session.** When composing a substantive question, when
  unsure how to handle a difficult moment (a guess, a contradiction
  with upstream, fatigue), or when about to draw a conclusion that
  goes beyond what the stakeholder directly said.
- **When authoring a new phase guide.** The phase guide includes a
  brief "How to Conduct This Phase" section that references the three
  conduct files and retains only items genuinely unique to that
  phase. `phase-1-interview-guide.md` §1A is the canonical example.

### How they relate to v2

The conduct framework operates *upstream* of v2's storage. The AI
applies the conduct rules during the interview; the outcomes of the
interview (Mission Statement, Domain Inventory, processes, CRM
candidates, decisions, etc.) land in v2's storage. v2's panels,
schemas, and APIs do not enforce or implement conduct rules — they
just store what the conducted interview produced.

This separation is intentional. The conduct framework can evolve
without v2 schema changes, and v2 can evolve without rewriting the
conduct framework.

---

## Getting started

### First run

```bash
# From the repo root.
uv sync                         # one-time dependency install
uv run crmbuilder-v2-bootstrap-db   # one-time DB materialisation
uv run crmbuilder-v2-ui         # opens the desktop app
```

The UI auto-launches the storage API in the background and shuts it
down on close. If `crmbuilder-v2-api` is already running externally
(e.g., for the MCP server), the UI uses the existing instance instead
of spawning a duplicate.

### Where the data lives

| Artefact | Location | Tracked in git? |
|---|---|---|
| SQLite database | `crmbuilder-v2/data/v2.db` | No (gitignored — derived) |
| JSON snapshots | `PRDs/product/crmbuilder-v2/db-export/*.json` | Yes (durable) |
| UI logs | `~/.crmbuilder-v2/ui.log` | No |
| App settings | environment variables (no `.env`) | n/a |

The snapshots are the source of truth for git history. The SQLite
file is a derived cache — deletable and recoverable from snapshots
plus `crmbuilder-v2-bootstrap-db`.

---

## Tour of the desktop UI

The window is organised by the **phase** you are working in. Across the
top is a tab strip: a pinned **Chat** tab, then one tab per open phase
(numbered in Master CRMBuilder PRD order — `1 · Business Context Capture`,
`3 · Inventory Reconciliation`, `13 · Verification`, …). Each phase tab has
its own **left sidebar** and **content area**, and keeps its own place:
switch to another tab to check something and come back, and the step,
record and scroll position you left are still there.

```
┌──────────────────────────────────────────────────────────────────┐
│  File  Go  Help                                                  │
│  Cleveland Business Mentors ▾                 [Quick open Ctrl+K] │
├──────┬─────────────────────────┬───────────────────────────┬─────┤
│ Chat │ 1 · Business Context ×  │ 13 · Verification ×       │  +  │
├──────┴──────────┬──────────────┴───────────────────────────┴─────┤
│ Every session   │  Domains                          [4 records]  │
│  Sessions       │  ┌──────────────────────┬───────────────────┐  │
│  Decisions      │  │ Identifier │ Name    │ Detail of         │  │
│  Planning Items │  │ DOM-001    │ …       │ selected record   │  │
│  Chat           │  │ DOM-002    │ …       │                   │  │
│ Phase 1 steps   │  └──────────────────────┴───────────────────┘  │
│  ✓ 1 Charter    │                                                 │
│  ✓ 2 Personas   │                                                 │
│  ▶ 3 Domains    │                                                 │
│    4 Processes  │                                                 │
│    5 References │                                                 │
│    6 Glossary   │                                                 │
│ All panels ▸    │                                                 │
└─────────────────┴─────────────────────────────────────────────────┘
```

The sidebar of a phase tab has three groups:

- **Every session** — Sessions, Decisions, Planning Items and Chat: the
  four things every phase uses (the Open → Conduct → Close session
  lifecycle is the same in all thirteen phases). Chat switches to the
  pinned Chat tab.
- **Phase N steps** — the panels the phase produces records in, numbered
  in the order the process performs them. A **✓** marks a step whose panel
  already has records; **▶** marks the first step that has none — the
  obvious next thing to do. Markers are advisory: nothing is locked and
  no button is ever disabled by them.
- **All panels ▸** — a collapsed, alphabetical index of every panel in the
  product, so nothing is out of reach. Click the header to expand it, or
  type in the **Filter navigation…** box above the list.

**Opening a phase.** Click **+** at the right end of the tab strip and pick
a phase (the thirteen PRD phases, then **Operate CRMBuilder** — the
product's own operations: agent registry, releases, cost, locks and the
system-written tables). Tabs stay open until you close them with their
**×**; the last phase tab cannot be closed. Which tabs you have open is
remembered per engagement, so switching engagement (or restarting) brings
back the tabs you had for it. Phases whose PRD section is still a
placeholder (4–10) carry a tooltip saying their step sequence is
provisional.

**Quick open (Ctrl+K).** Type a panel name fragment (`dep` → Deploy
History, Deposit Events) or an identifier prefix (`REQ-52` → the matching
requirements) and press Enter to open the highlighted result in the
current tab. Back/Forward (Alt+Left / Alt+Right, Go menu) still step
through the cross-record trail.

**Governance Rules panel (Operate CRMBuilder).** Rules are system
defaults that a client engagement can override: an engagement-scoped rule
with the same *Rule type* replaces the system rule for that engagement only.
The **View** selector above the grid switches between **All stored rules**
and **Effective for <engagement>** — the resolved ruleset, where each
override's **Shadows** column names the default it displaces. The detail
pane shows **Supersedes** on an override and **Superseded by** on a default.
To override a default that has no Rule type yet, give it one first (Edit),
then create the engagement rule with the same key; the provenance edge is
recorded for you. Walkthrough: lesson `LSN-063`.

### Live refresh

When MCP, an external script, or another v2 instance writes the
database, the snapshot directory updates atomically. The UI watches
that directory and refreshes the affected panel within ~500 ms.
Non-visible panels show a small **stale-data indicator** and refresh
on next selection. No manual reload required.

The **Refresh** button on every toolbar is a fallback in case the
file watcher misses a notification (rare, but possible across some
filesystem boundaries).

### Connection-loss handling

If the storage API goes down (process crash, host change), the UI
shows a banner at the top of the window: "Connection to storage API
lost." When the API is back, click **Reconnect** in the banner; the
UI refreshes the active panel and clears the banner.

---

## Decisions

The flagship entity type. Used for architectural and operational
records — DEC-NNN identifiers form the persistent reference vocabulary
for the project.

### List view (the master pane)

Columns: Identifier, Title, Decision Date, Status, Superseded By.
Sortable by clicking headers. The status column distinguishes Active,
Superseded, and Withdrawn rows; Deleted rows are hidden by default
(see Show deleted, below).

### Detail pane

Selecting a row shows:

- **Identifier**, **Title**, **Decision Date**, **Status** — header
  fields.
- **Supersedes** / **Superseded By** — clickable links to other
  decisions. Click navigates to that record.
- Five long-text sections: **Context**, **Decision**, **Rationale**,
  **Alternatives Considered**, **Consequences**.
- A **References** section at the bottom showing inbound and outbound
  references (e.g., "Decided in: SES-004"). Click any reference link
  to navigate to that entity.

### Toolbar actions

- **Refresh** — manual reload (file watcher should make this
  unnecessary).
- **Show deleted** — toggle. When checked, the list includes
  soft-deleted decisions, rendered with strikethrough text.
- **New Decision** — opens the create dialog.

### Creating a decision

**New Decision** opens a modal with all fields. The identifier must
match `DEC-NNN` format; the date must match `MM-DD-YY`. Status
defaults to Active. Save validates client-side first (format), then
submits via the API. On success the new record is selected
automatically.

If the API rejects the payload (e.g., identifier already taken,
status not in vocabulary), errors surface inline next to the offending
field. The dialog stays open until you fix and resubmit, or click
Cancel.

### Editing a decision

Select a row, click **Edit** in the detail pane. The dialog
pre-populates with the current values. Identifier is read-only;
everything else is editable. Save submits a PATCH containing only the
fields that changed.

If another writer (MCP, script) modified the row between your fetch
and your save, the dialog still saves your changes — last-write-wins.
Refresh the panel afterwards to see the merged state.

### Deleting a decision

**Delete** in the detail pane. A confirmation dialog appears. Confirm
to soft-delete: the row's `status` flips to `Deleted`, but it remains
in the database so cross-entity references continue to resolve. The
row disappears from the default list but reappears with strikethrough
when you toggle **Show deleted**.

### Restoring a deleted decision

Toggle **Show deleted** on. Select the deleted row. The detail pane
button strip now reads **Restore** + **Edit** (no Delete). Click
Restore, confirm, and the status flips back to Active. The row
reappears in the default view.

### Superseding a decision

Two-step:

1. Create the new decision (e.g., DEC-020).
2. Edit the old decision (DEC-005). Set its status to **Superseded**
   and its **Superseded By** to `DEC-020`.

The Edit dialog's Supersedes / Superseded By fields are
typeahead-completable from the existing decision list. Clear either
field by deleting the text — submitting an empty value clears the
foreign key (the same path as removing the link entirely).

The new decision DEC-020 should declare its **Supersedes** =
`DEC-005` for symmetry. The detail pane on either record then shows
the link in both directions.

---

## Sessions

A session is the record of one Claude.ai or Claude Code conversation
that produced governance content. Per DEC-013, sessions are
**append-only**: there is no UI Edit button. To correct a session
that was recorded incorrectly, use the API or MCP to delete it and
recreate it.

### List view

Columns: Identifier, Title, Session Date, Status, Topics Covered
(truncated). Sorted newest-first.

### Detail pane

- Header fields (identifier, title, date, status).
- **Conversation reference** — descriptive pointer to the source
  conversation (per DEC-025, transcripts are not preserved).
- **Topics covered**, **Summary**, **Artifacts produced**, **In flight
  at end** — long-text sections.
- A **References** section showing decisions decided in this session
  (the `decided_in` relationship), plus any other touching references.

### Recording a new session

**v0.2 limitation:** Sessions write surface is deferred to v0.3
pending DEC-013/DEC-014 revisit. To record a session today, use MCP
(in a Claude conversation) or POST to the REST API directly:

```bash
curl -X POST http://127.0.0.1:8765/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "SES-008",
    "title": "Some working session",
    "session_date": "05-09-26",
    "status": "Complete",
    "conversation_reference": "...",
    "topics_covered": "...",
    "summary": "...",
    "in_flight_at_end": "..."
  }'
```

The decisions linked to the session — the `decided_in` references —
are also created via API/MCP at session-creation time. (See "Linking
entities" below.)

---

## Risks

Risk register entries. Probability × impact, response plan, status.

### List view

Columns: Identifier, Title, Probability, Impact, Status. Sorted by
identifier ascending.

### Detail pane

- Header (identifier, title).
- Probability, Impact (each Low / Medium / High), Status (Open /
  Mitigated / Closed).
- Description, Response Plan (long-text).
- References section.

### Toolbar actions

**Refresh**, **New Risk**.

### Create / Edit / Delete

Same dialog pattern as Decisions: full create dialog for New, edit
dialog with identifier read-only, hard-delete confirmation. Risks are
not soft-deleted (DEC-013 only applies to decisions and sessions).

---

## Planning Items

Open questions, planning dimensions, pending work. Tracks unresolved
items that need to land before a phase closes.

### List view

Columns: Identifier, Title, Item Type, Status. Item Type is one of
`planning_dimension`, `open_question`, `pending_work`. Status is `Open`
or `Resolved`.

### Detail pane

- Header.
- Item Type, Status.
- Description.
- **Resolution Reference** — when status is Resolved, an optional
  pointer to the decision (DEC-NNN) or session (SES-NNN) that closed
  the item. Clickable.
- References section.

### Workflow

1. Create open items as planning surfaces them.
2. When a decision closes the item, edit the row: set Status =
   Resolved and Resolution Reference = the closing DEC or SES
   identifier.
3. Resolved items remain in the list (not deleted) for traceability.

---

## Topics

Free-floating concepts — the loose vocabulary the project uses (e.g.,
"Schema design", "References table"). Topics are hierarchical: each
can have a parent. The master pane is a **QTreeView** with indentation
showing the hierarchy.

### List view (tree)

Each node displays as `TOP-NNN — Topic name`. Click the disclosure
triangle to expand/collapse. Orphaned topics (parent ID points to a
nonexistent topic) render at root with `(orphan)` suffix.

### Detail pane

- Header.
- **Parent Topic** — clickable link to the parent (or `—` if root).
- **Description**.
- References section.

### Hierarchical parent picker

In the New / Edit dialog, the **Parent Topic** field opens a tree
picker showing all existing topics with the same indentation as the
master pane. Select any node to set as parent, or click `(none)` at
the top to make this topic root-level.

The picker scrolls to the current parent automatically when opening
on Edit. When editing a topic, the picker hides the topic itself and
its descendants — preventing accidental cycles.

### Re-parenting and detaching

**Re-parent**: Edit the topic, change Parent Topic in the picker,
Save. The tree updates immediately on next refresh.

**Detach** (make root-level): Edit the topic, click `(none)` in the
picker, Save. The parent FK is cleared.

### Hard-delete with safeguards

Topics are hard-deleted, but the access layer rejects deletion if the
topic has children or if it is referenced by another entity. Resolve
the children/references first, or pick a different topic.

---

## References

The cross-entity link table. Every relationship between two records
(a session decided a decision; a planning item was resolved by a
decision; a topic is_about a session) is stored as a row here.

### List view (read-only in v0.2)

Columns: Source Type, Source ID, Relationship, Target Type, Target ID.
A **filter strip** above the table lets you filter by relationship
type or by entity type on either side.

### Detail pane

References don't have a detail pane in v0.2 — the list is the surface.

### Creating references

**v0.2 limitation:** References write surface is deferred to v0.3.
Today, references are created via MCP or REST:

```bash
curl -X POST http://127.0.0.1:8765/references \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "session",
    "source_id": "SES-007",
    "target_type": "decision",
    "target_id": "DEC-031",
    "relationship": "decided_in"
  }'
```

The reference vocabulary (per DEC-006) is `is_about`, `supersedes`,
`decided_in`, `affects`, `covers`, `blocks`, `references`. Adding a
new value requires a deliberate code edit + Alembic migration; this
is intentional.

---

## Charter

The current scope and architectural foundations of the project. One
"current" version at a time, with a full version history kept around.

### Detail pane

- Header showing **Version N (current)** or **Version N (historical)**.
- Pretty-printed JSON of the payload (read-only).
- A **Versions** sidebar listing all versions newest-first. Click any
  version to load its payload into the detail pane.

### Replacing the charter

Click **Replace…** in the toolbar. A modal opens with the current
payload pre-filled in a JSON editor.

- Edit the payload directly. Use the **Validate** button to confirm
  the JSON parses and is a top-level object before submitting.
- **Save** writes a new version. The previous current version becomes
  historical; the new version becomes current.

If the API rejects the payload (schema violation, missing required
keys), per-field errors render inline below the editor. Fix and
resubmit without leaving the dialog.

### Make Current

To roll back to a historical version, select it in the Versions
sidebar and click **Make Current**. This flips `is_current` to that
version without rewriting the payload — the historical content
becomes live as-is.

---

## Status

Same shape as Charter (versioned replace + Make Current + version
history) but for project status: phase, sub-step, active work,
blockers, pending lists.

The current status is what Tier 2 orientation reads for new sessions.
Bumping version_label from 0.7 → 0.8 (e.g., at the close of a phase)
is part of the normal session-end ritual.

---

## Deploying a new CRM instance

An administrator can stand up a brand-new self-hosted CRM instance from the
desktop. The cloud service does the work as a **deploy run** (`DEP-NNN`): it
creates the server in DigitalOcean, creates a DNS-only A record in Cloudflare,
waits for the name to resolve, installs and verifies the CRM over SSH, and
registers the result as an instance you can audit and publish to. You do not
need to keep the desktop open — the run continues on the service.

### Before the first run — provider credentials

Each engagement holds its own **provider credentials**: a DigitalOcean
personal access token (read + write) and a Cloudflare API token with
`Zone:Read` and `DNS:Edit` on the customer's zone. CRMBuilder's own accounts
are the usual default; a customer may supply its own so the server bills to
them. Open **Instances → Deploy new… → Set credentials…** to enter or replace
them. Tokens are stored encrypted by the service and never shown again; the
dialog only reports *configured* or *not set*.

Only administrators (the engagement's `owner` role when authentication is on)
can set credentials or start a run. Everyone sees the buttons; a
non-administrator gets a clear refusal on click.

### The deploy wizard

**Instances → Deploy new…** walks five steps:

1. **Providers** — confirms both credentials are in place.
2. **Server** — instance name; region, size and image from the live
   DigitalOcean catalog; optional extra account SSH keys. The run also
   generates its own key for the server.
3. **Domain** — the Cloudflare zone and subdomain (the resulting address is
   shown), and the Let's Encrypt email. The record is created DNS-only (grey
   cloud); leave it that way or certificate renewal and SSH stop working.
4. **Accounts** — the CRM administrator login (use **Generate** and record the
   password now; it is stored encrypted and used as the instance's credential,
   but never shown again). Database passwords are generated by the service
   unless you untick the box.
5. **Review** — the request as it will be sent. **Deploy** queues the run.

Next is never disabled: if a step is incomplete, clicking Next says what is
missing.

### Following a run

After Deploy, a progress window follows the run: a phase bar (checking
credentials → creating server → waiting → setting DNS → waiting → preparing
server → installing → post-install checks → verifying → registering), the
service's log, **Cancel run** while it is running (takes effect between
phases), and **Close** at any time. When the run registers the instance, the
Instances panel selects it.

**Deploy History** (step in phase 11 · CRM Deployment; also under All panels) lists every run with its
status and phase. Select one to see what it created (server id and IP,
certificate expiry), the verification results, the error that stopped it, and
its log; **Open progress…** reattaches to a running run.

### When a run fails

Nothing is destroyed. The run is marked *failed*, the server and DNS record it
already created are recorded, and the history entry says so in orange —
*"Still exists (not destroyed)"* — with a **Copy server id** button. Fix the
cause and **Retry**: the run resumes at the phase that did not finish and
does not create a second server. If you abandon the run instead, delete the
server in the DigitalOcean console yourself; it bills until you do.

A run whose service restarted mid-way is picked up again automatically
(*"Resuming deploy run…"* in the log). Verification gaps that do not stop the
install land as *succeeded (issues)* with the failing checks listed.

## Working with Claude (MCP)

The MCP server exposes ~40 tools that wrap the same REST endpoints
the UI uses. In a Claude session with the MCP server connected:

- "What's the current status?" → `get_current_status`
- "Show me the most recent three sessions." → `list_recent_sessions(3)`
- "What does DEC-022 say?" → `get_decision("DEC-022")`
- "Add a decision DEC-032 titled 'Switch to PostgreSQL'..." →
  `create_decision({...})`
- "Mark RSK-003 as Closed." → `update_risk("RSK-003", {"status": "Closed"})`

Claude prompts the user before any write-side tool and shows the
exact payload that will be sent.

### Attribution

The change_log table tags every mutation with an actor:
`claude_session` (default), `migration` (bootstrap), or `manual`
(scripts). When the UI writes, the actor is `claude_session` because
the UI shares a process with no separate identity.

---

## Common workflows

### End-of-conversation session record

After a working Claude conversation that produced decisions, the
standard pattern is:

1. Append a session record (SES-NNN) summarising what happened.
2. Add `decided_in` references linking each new decision to the
   session.
3. Update the status: bump `version_label`, refresh `active_work`,
   refresh `pending`, refresh `live_inventory`.

In v0.2, sessions and references are MCP/REST-only; the status is
UI-editable via the Charter/Status replace flow.

### Promoting a candidate decision out of "open question"

A planning item you logged as `open_question` is closed by a new
decision:

1. Create the closing decision (DEC-NNN).
2. Edit the planning item: set Status = Resolved, Resolution
   Reference = `DEC-NNN`.

### Recovering from a stale-data indicator

Switch panels and back. Or click **Refresh** on the toolbar. If
neither helps, the API is probably down — check the connection-loss
banner.

### Recovering from a corrupted SQLite file

The snapshots are durable; the SQLite file is recoverable. From the
repo root:

```bash
rm -f crmbuilder-v2/data/v2.db
uv run crmbuilder-v2-bootstrap-db
# Then load from snapshots — see README's
# "Restoring from JSON snapshots" section.
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| "Connection to storage API lost" banner | API process died or unreachable | Click **Reconnect** in the banner. If still failing, restart `crmbuilder-v2-api`. |
| New decision dialog says "Identifier already exists" | DEC-NNN was used before, possibly soft-deleted | Toggle Show deleted in the Decisions panel; either Restore the existing one or pick a new identifier. |
| Stale-data indicator on a panel that should be fresh | File watcher missed a notification (rare) | Click Refresh on the panel toolbar. |
| "Cannot delete topic — referenced by other records" | Another entity has a reference targeting this topic | Find the references via the References panel filter; remove them first. |
| Topic edit dialog won't let me detach | Old behavior; now fixed in v0.2 slice F | Update to v0.2.0+; clearing the parent picker now clears the FK. |
| Edit dialog's Save button does nothing on validation error | The error is rendered inline near the offending field | Scroll up; the field will have a red error message. |
| Charter / Status replace says "Invalid JSON" but it looks valid | A trailing comma, smart quote, or unescaped newline | Use a strict JSON validator; the editor's Validate button shows the parse line/column. |

---

## Limitations and v0.3 backlog

What's deferred from v0.2:

- **Sessions write surface** — UI-side create/delete (DEC-013/DEC-014
  must be revisited first to allow non-Claude session records).
- **References write surface** — picker-based UI for source / target
  / relationship.
- **Full styling design pass** — v0.2 uses native Qt look. DEC-024
  defers a styling pass.
- **Diff-with-current view** — for the JSON payload editor in
  Charter/Status replace.
- **Bulk operations** — multi-select on the master pane.
- **Global search** — across all entity types.
- **Export visible panel** — to CSV / JSON.

The current backlog is captured in `db-export/status.json`'s
`pending.ui_v0_3_backlog` field.

---

## Reference

- `crmbuilder-v2/README.md` — operations reference (env vars, REST
  endpoints, MCP tools, troubleshooting matrix).
- `crmbuilder-v2/TECHNICAL-GUIDE.md` — architecture and extension
  patterns.
- `PRDs/product/crmbuilder-v2/ui-PRD-v0.2.md` — current requirements
  spec.
- `PRDs/product/crmbuilder-v2/db-export/decisions.json` — durable
  decisions content for `jq`-based inspection.
