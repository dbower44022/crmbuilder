# Claude Code Implementation Prompt — Step 10: Workflow Engine

## Context

You are implementing **Step 10 of the CRM Builder Automation roadmap** — the Workflow Engine. The complete design for this work is in the Level 2 PRD at:

`PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`

**Read Section 9 of the L2 PRD before writing any code.** That section defines the entire Workflow Engine: status model, status calculation, dependency graph construction, phase ordering, available work calculation, status transitions and side effects, blocked state handling, and Domain Overview output. Section 14.2.3 contains the item_type-to-phase mapping table you will need.

This is step 10 of a 16-step roadmap (see Section 17). Step 9 (database layer) is complete. Subsequent implementation steps (11–16) will build on top of the Workflow Engine you produce.

## Repository Context

This work goes in the `dbower44022/crmbuilder` repository. Read `CLAUDE.md` at the repo root for general project conventions. Read this prompt's "Step 9 Foundation" section below carefully — it documents the database layer API your code must build on.

## Where the Code Goes

Create a new package parallel to `automation/db/`:

```
automation/
├── __init__.py              # exists
├── db/                      # exists — Step 9 database layer
│   ├── client_schema.py
│   ├── connection.py
│   ├── master_schema.py
│   ├── migrations.py
│   └── init_db.py
├── workflow/                # NEW — Step 10
│   ├── __init__.py
│   ├── phases.py            # item_type-to-phase mapping (Section 14.2.3)
│   ├── status.py            # status model and calculation (Sections 9.2, 9.3)
│   ├── graph.py             # dependency graph construction (Section 9.4)
│   ├── available.py         # available work calculation (Section 9.6)
│   ├── transitions.py       # status transitions and side effects (Section 9.7)
│   ├── blocked.py           # blocked state handling (Section 9.8)
│   ├── engine.py            # WorkflowEngine class — public API surface
│   └── domain_overview.py   # Domain Overview output (Section 9.10)
└── tests/
    ├── test_workflow_phases.py
    ├── test_workflow_status.py
    ├── test_workflow_graph.py
    ├── test_workflow_available.py
    ├── test_workflow_transitions.py
    ├── test_workflow_blocked.py
    ├── test_workflow_engine.py
    └── test_workflow_domain_overview.py
```

**Tests live in the existing `automation/tests/` directory** (not a new `automation/workflow/tests/`) — match the Step 9 convention.

## Step 9 Foundation — Database Layer API

The Workflow Engine reads from and writes to the database via the Step 9 modules. Use these existing APIs — do not bypass them and do not add new connection or migration code.

### Connection management — `automation.db.connection`

```python
from automation.db.connection import open_connection, close_connection, connect, transaction

# Opening a connection (foreign keys enabled automatically)
conn = open_connection(db_path)
# ... use conn ...
close_connection(conn)

# Context manager (preferred — closes on exception)
with connect(db_path) as conn:
    # ... use conn ...

# Transaction wrapping (commits on success, rolls back on exception)
with transaction(conn):
    conn.execute("INSERT INTO ...")
    conn.execute("UPDATE ...")
```

All workflow engine writes that touch multiple rows must be wrapped in `transaction(conn)`.

### Schema — `automation.db.client_schema`

The relevant tables for the Workflow Engine are `WorkItem`, `Dependency`, `Domain`, `Entity`, and `Process`. Their full schemas are in `automation/db/client_schema.py`. Key columns the engine needs:

**WorkItem:**
- `id` (INTEGER PK)
- `item_type` (TEXT — see CHECK constraint for valid values)
- `domain_id`, `entity_id`, `process_id` (nullable INTEGER FKs)
- `status` (TEXT — `not_started`, `ready`, `in_progress`, `complete`, `blocked`)
- `blocked_reason` (TEXT, nullable)
- `status_before_blocked` (TEXT, nullable — for restoring on unblock)
- `started_at`, `completed_at` (TIMESTAMP, nullable)

**Dependency:**
- `id` (INTEGER PK)
- `work_item_id` (INTEGER FK to WorkItem.id — the waiting item)
- `depends_on_id` (INTEGER FK to WorkItem.id — the prerequisite item)
- UNIQUE constraint on (work_item_id, depends_on_id)

**Domain:**
- `id` (INTEGER PK)
- `is_service` (BOOLEAN — TRUE for Cross-Domain Services, FALSE for regular domains)
- Other columns exist; consult the schema for full reference.

There is **no phase column** on WorkItem. Phase is application-level logic — see the Phase Mapping section below.

### Migrations — `automation.db.migrations`

Workflow Engine code should not call migration functions directly. Tests should set up databases by calling `run_client_migrations(db_path)` to get a clean schema before exercising the engine.

```python
from automation.db.migrations import run_client_migrations

# In a test fixture:
def test_something(tmp_path):
    db_path = tmp_path / "test.db"
    conn = run_client_migrations(str(db_path))
    # ... insert test data, exercise engine, assert ...
    conn.close()
```

## Phase Mapping — Critical Design Point

**The Workflow Engine never stores a phase number on a WorkItem row.** Phase is calculated from `item_type` and (for three item_types) the `is_service` flag of the related Domain. This is documented in L2 PRD Section 14.2.3.

Implement the mapping in `automation/workflow/phases.py`:

```python
# Static mapping — does not vary per client
ITEM_TYPE_TO_PHASE = {
    "master_prd": 1,
    "business_object_discovery": 2,
    "entity_prd": 2,
    # domain_overview, process_definition, domain_reconciliation
    # are NOT in this dict — they require the is_service flag
    "stakeholder_review": 7,
    "yaml_generation": 8,
    "crm_selection": 9,
    "crm_deployment": 10,
    "crm_configuration": 11,
    "verification": 12,
}

# Item types that depend on the related Domain's is_service flag
SERVICE_AWARE_ITEM_TYPES = {
    "domain_overview",
    "process_definition",
    "domain_reconciliation",
}

PHASE_NAMES = {
    1: "Master PRD",
    2: "Entity Definition",
    3: "Domain Overview",
    4: "Cross-Domain Service Definition",
    5: "Process Definition",
    6: "Domain Reconciliation",
    7: "Stakeholder Review",
    8: "YAML Generation",
    9: "CRM Selection",
    10: "CRM Deployment",
    11: "CRM Configuration",
    12: "Verification",
}


def get_phase(item_type: str, is_service: bool = False) -> int:
    """Return the phase number for a work item.

    For domain_overview, process_definition, and domain_reconciliation,
    the is_service flag determines the phase: True → Phase 4, False →
    Phases 3, 5, 6 respectively.

    For all other item_types, is_service is ignored.

    Raises ValueError for unknown item_types.
    """
    if item_type in SERVICE_AWARE_ITEM_TYPES:
        if is_service:
            return 4
        return {
            "domain_overview": 3,
            "process_definition": 5,
            "domain_reconciliation": 6,
        }[item_type]
    if item_type in ITEM_TYPE_TO_PHASE:
        return ITEM_TYPE_TO_PHASE[item_type]
    raise ValueError(f"Unknown item_type: {item_type}")


def get_phase_name(phase_number: int) -> str:
    """Return the human-readable name for a phase number."""
    if phase_number not in PHASE_NAMES:
        raise ValueError(f"Unknown phase number: {phase_number}")
    return PHASE_NAMES[phase_number]
```

This is the complete spec for `phases.py`. Use it as a reference implementation, not a copy-paste — adjust for type hints, docstrings, and the module's import structure.

The Workflow Engine queries phase by joining `WorkItem` to `Domain` (when needed) and calling `get_phase(item_type, is_service)`. Phase is **never** stored, **never** cached on the row, and **never** derived from a column lookup.

## Definition of Done

This step is complete when **all** of the following are true:

1. **Phase mapping module** (`automation/workflow/phases.py`) exists and exports `get_phase()` and `get_phase_name()` matching the spec above. All 12 item_types covered. is_service distinction works for the three service-aware types. Unknown item_types raise ValueError.

2. **Status calculation** (`automation/workflow/status.py`) implements Section 9.2 (status model — `not_started`, `ready`, `in_progress`, `complete`, `blocked`) and Section 9.3 (status calculation — a `not_started` item becomes `ready` when all its dependencies have status `complete`).

3. **Dependency graph construction** (`automation/workflow/graph.py`) implements all four scenarios in Section 9.4:
   - **9.4.1 Project Creation**: Creates the master_prd work item with no dependencies, status `ready`.
   - **9.4.2 After Master PRD Import**: Creates the business_object_discovery work item with a dependency on master_prd. Recalculates and transitions to `ready` if master_prd is complete.
   - **9.4.3 After Business Object Discovery Import**: Creates work items for all remaining phases — entity_prd per Entity, domain_overview per Domain, process_definition per Process, domain_reconciliation per Domain, stakeholder_review per Domain, yaml_generation per Domain, plus singletons for crm_selection, crm_deployment, crm_configuration, verification. Wires dependencies per the section. The `domain_id` for entity_prd work items is set to `entity.primary_domain_id`. Service-flagged domains use the same item_types but the resulting work items will be reported as Phase 4 by `get_phase()`.
   - **9.4.4 Mid-Project Additions**: Handles new entities, new processes, and new domains discovered mid-project, with the appropriate dependency wiring.

4. **Phase ordering rules** (Section 9.5) are respected. The engine does not enforce phase order through hardcoded checks — it enforces it through dependencies. A work item is `ready` only when its dependencies are `complete`, which naturally creates the phase ordering.

5. **Available work calculation** (`automation/workflow/available.py`) implements Section 9.6: returns the set of work items whose status is `ready` or `in_progress`, ordered by phase (using `get_phase()`) ascending, then by `domain.sort_order` within the same phase. Cross-domain work items (those with NULL domain_id) sort last within their phase.

6. **Status transitions** (`automation/workflow/transitions.py`) implements Section 9.7:
   - **9.7.1 Forward Transitions**: `ready → in_progress` (sets `started_at`), `in_progress → complete` (sets `completed_at`, triggers downstream recalculation — items depending on this one become `ready` if all their dependencies are now complete).
   - **9.7.2 Revision Transition**: `complete → in_progress` (clears `completed_at`, blocks all downstream items that were `ready`/`in_progress`/`complete` by setting their status to `blocked` and `status_before_blocked` to their previous status). Per Section 9.8.3, the `blocked_reason` for automatic blocking uses the format `UPSTREAM_REVISION: {item_type} — {descriptive_name} (Work Item #{id})`.

7. **Blocked state handling** (`automation/workflow/blocked.py`) implements Section 9.8:
   - **9.8.1 Causes**: Either an upstream revision (automatic, with the structured `UPSTREAM_REVISION:` prefix) or an administrator action (manual, with free-text reason).
   - **9.8.2 Unblocking**: When the upstream item completes again, find all blocked items whose `blocked_reason` references this work item and restore them to `status_before_blocked`. If after restoration the item's dependencies are all `complete`, run the standard ready calculation. Manual unblock is also supported (administrator clears blocked_reason and engine restores status_before_blocked).
   - **9.8.3 Blocked Reason Format**: Distinguish automatic reasons (parseable prefix) from manual reasons (free text).

8. **Workflow Engine class** (`automation/workflow/engine.py`) provides the public API. This is what Step 11 (Prompt Generator) and Step 15 (UI) will call. It wraps the modules above into a single class with a connection-or-db_path constructor:

```python
class WorkflowEngine:
    def __init__(self, conn): ...

    # Graph construction
    def create_project(self) -> int: ...  # returns master_prd work_item_id
    def after_master_prd_import(self) -> None: ...
    def after_business_object_discovery_import(self) -> None: ...
    def add_entity(self, entity_id: int) -> int: ...
    def add_process(self, process_id: int) -> int: ...
    def add_domain(self, domain_id: int) -> list[int]: ...

    # Status queries
    def get_status(self, work_item_id: int) -> str: ...
    def calculate_status(self, work_item_id: int) -> str: ...
    def get_available_work(self) -> list[dict]: ...
    def get_phase_for(self, work_item_id: int) -> int: ...

    # Status transitions
    def start(self, work_item_id: int) -> None: ...      # ready → in_progress
    def complete(self, work_item_id: int) -> None: ...   # in_progress → complete
    def revise(self, work_item_id: int) -> None: ...     # complete → in_progress

    # Blocked state
    def block(self, work_item_id: int, reason: str) -> None: ...
    def unblock(self, work_item_id: int) -> None: ...
```

Method names and signatures may be refined as you implement, but the public API surface must cover all these capabilities. Document any signature changes in your final report.

9. **Domain Overview output** (`automation/workflow/domain_overview.py`) implements Section 9.10 — when a `domain_overview` session is imported, the engine writes the generated overview text to the appropriate field on the Domain record. (Section 9.10 specifies the column to write; consult the L2 PRD for the field name.)

10. **All multi-row writes use `transaction(conn)`**. The engine never commits partial state. If a graph construction call fails partway through, no rows are persisted.

11. **pytest test suite** with **tests written alongside each module as it is built**. Coverage requirements:
    - `phases.py`: every item_type returns the correct phase, including service-aware variants. Unknown item_types raise ValueError. `get_phase_name()` works for all 12 phases.
    - `status.py`: status calculation correctly returns `ready` only when all dependencies are `complete`; returns `not_started` otherwise.
    - `graph.py`: each of the four scenarios in 9.4 produces the correct work items and dependencies. Tests use real SQLite via `run_client_migrations()` and assert against the actual database state — not mocks.
    - `available.py`: ordering is correct across phases, sub-orders correctly within a phase, handles services and cross-domain items.
    - `transitions.py`: forward transitions trigger downstream recalculation; revision transitions block downstream items with the structured reason format; transactions roll back on error.
    - `blocked.py`: automatic blocking and unblocking via upstream revision works end-to-end; manual blocking and unblocking works; restoration to `status_before_blocked` is correct.
    - `engine.py`: integration tests that exercise the public API end-to-end (create project → import master PRD → import business object discovery → start a work item → complete it → verify downstream items become ready → revise an upstream item → verify downstream items become blocked → complete the upstream → verify downstream items unblock).
    - `domain_overview.py`: the overview text is written to the correct column on the correct Domain record.

12. **All tests pass**: `uv run pytest automation/tests/ -v`

13. **Linter clean**: `uv run ruff check automation/`

## Working Style

- **Read Section 9 of the L2 PRD before writing any code.** Also read Section 14.2.3 for the phase mapping context. Do not improvise — match the design.
- **Read the existing Step 9 code in `automation/db/`** before writing tests, so your test fixtures use the real connection and migration APIs.
- **Write tests alongside each module**, not at the end. When you implement `phases.py`, write `test_workflow_phases.py` in the same step.
- **Implement in this order**: phases → status → graph → available → transitions → blocked → engine → domain_overview. Each layer depends on earlier layers.
- **Surface ambiguities, do not invent answers.** If Section 9 leaves a behavior unclear, stop and report the ambiguity rather than guessing. Examples of things to flag rather than guess:
  - What happens if `complete` is called on an item with status other than `in_progress`?
  - What happens if a dependency cycle is created during 9.4.4 mid-project additions?
  - How should the engine handle a work item whose related Domain has been deleted?
- **No bypassing the database API.** Use `automation.db.connection.transaction()` for multi-row writes. Do not write raw `BEGIN`/`COMMIT` SQL.
- **No GUI code.** UI is step 15.
- **No prompt generation.** Step 11.
- **No import processing.** Step 12.
- **No impact analysis.** Step 13.
- **No document generation.** Step 14.
- **Do not modify `espo_impl/`.** It is a separate feature area.
- **Do not modify `automation/db/`.** Step 9 is locked. If you find a bug in the database layer, report it but do not fix it as part of Step 10.

## Out of Scope for This Step

- Storing phase as a column on WorkItem (it is application-level logic)
- Any prompt generation, import processing, impact analysis, document generation, or UI code
- Modifying the database schema or migrations
- Modifying anything in `espo_impl/`
- Adding new top-level packages
- Refactoring Step 9 code

## Reference Documents

Primary: `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`

Sections to read carefully before starting:
- **Section 9 (entire section)** — Workflow Engine. This is your spec.
- **Section 14.2.3** — item_type-to-phase mapping table and the is_service distinction.
- **Section 6.3** — WorkItem schema (no phase column).
- **Section 6.4** — Dependency schema.
- **Section 4.1** — Domain schema (the is_service column).
- **Section 4.8** — Process schema (the tier and sort_order columns).

You may also find this useful for context, but **do not implement any of it in step 10**:
- **Section 11.10.1** — describes the order in which the Import Processor calls the Workflow Engine after a successful import. Useful for understanding the engine's role in the import pipeline. Step 12 will implement the Import Processor; for Step 10, you only need to know that the engine's graph construction and status transition methods are called from outside.

## Final Check

Before declaring this step complete, verify:

- [ ] `grep -rn "phase TEXT" automation/db/` returns zero matches (Step 9 fix verified, no regression)
- [ ] `grep -n "phase" automation/workflow/` shows phase only in `phases.py` and tests
- [ ] All items in the Definition of Done are met
- [ ] All tests pass
- [ ] Linter is clean
- [ ] No code in `automation/db/` was modified
- [ ] No code in `espo_impl/` was modified
- [ ] No work outside the Step 10 scope was performed
- [ ] The `WorkflowEngine` class can construct a complete project graph end-to-end against a real SQLite database

When complete, commit with a descriptive message and report what was built. Report any signature changes from the API sketch above. Report any ambiguities you encountered in Section 9 and how you resolved them. Do not push — leave that for Doug.
