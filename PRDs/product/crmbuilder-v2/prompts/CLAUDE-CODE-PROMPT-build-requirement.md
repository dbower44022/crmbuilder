# CLAUDE-CODE-PROMPT-build-requirement

**Last Updated:** 05-25-26
**Operating mode:** DETAIL
**Series:** PI-004 cohort (methodology-entity expansion, v0.5+)
**Slice:** Build the `requirement` methodology entity end-to-end — migration → model → vocab → repository → schemas → router → main wiring → UI client → sidebar → main window dispatch → panel → dialogs → tests → verification → close-out.
**Status:** Ready to execute. Blocked by: nothing — `requirement.md` spec is canonical. Note: `_kinds_for_pair` clauses for `(requirement, field)` and `(requirement, test_spec)` activate only when those sibling entity types land in `ENTITY_TYPES`.
**Companions:**
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/requirement.md` v1.0 — authoritative spec.
- `crmbuilder-v2/migrations/versions/0008_v0_4_create_entities_table.py` — closest migration pattern.
- `crmbuilder-v2/src/crmbuilder_v2/access/repositories/entity.py` — closest repository pattern (global case-insensitive name uniqueness, identifier auto-assign, transition validation).
- `crmbuilder-v2/src/crmbuilder_v2/api/routers/entities.py` — eight-endpoint router pattern.
- `crmbuilder-v2/src/crmbuilder_v2/ui/panels/entities.py` — panel pattern (master/detail + outgoing-references rendering).
- `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — vocab pattern (`ENTITY_TYPES` + `REFERENCE_RELATIONSHIPS` + `_kinds_for_pair`).

---

## Purpose

Land the `requirement` methodology entity per `requirement.md` v1.0: a new `requirements` table, a `Requirement` ORM class, vocabulary registrations for the new entity type and five new relationship kinds, a CRUD repository, FastAPI schemas + router, UI client methods, sidebar entry, panel + dialogs, tests, and end-to-end verification.

This is the first of the PI-004 cohort builds (`field`, `requirement`, `manual_config`, `test_spec` — `persona` is PI-003 sibling). The slice **addresses** PI-004 but does not resolve it; the LAST cohort sibling build closes PI-004 by aggregating all sibling sessions' work.

After this slice lands: `requirements` table exists; `refs` CHECK admits `'requirement'` source/target and all five new `requirement_*` relationship kinds; `_kinds_for_pair` activates the three pairs whose targets are live (`domain`, `entity`, `process`) and leaves TODO comments for `field` / `test_spec`; the desktop UI shows a new "Requirements" entry under the Methodology sidebar group with full CRUD.

---

## Pre-flight

1. `pwd` → repo clone root (typically `~/Dropbox/Projects/crmbuilder`). Stop if unexpected.
2. `git status` clean. Stop and report if not.
3. Git identity set:
   ```bash
   git config user.name "Doug Bower"
   git config user.email "doug@dougbower.com"
   ```
4. `git pull --rebase origin main`. Stop if conflicts.
5. Read companion documents in order (above). Pay particular attention in `requirement.md` to §3.1 (prefix `REQ`), §3.2 (eleven columns), §3.2.3 (priority enum + default `should`), §3.3.1 (five new outbound kinds), §3.4 (three-status lifecycle, propose-verify gate), §3.5 (eight endpoints), §3.6 (panel/dialog layout with five-column master incl. Priority), §3.7 (15 acceptance criteria — drive the test plan).
6. Read prior test patterns: `tests/crmbuilder_v2/access/test_entity.py`, `tests/crmbuilder_v2/api/test_entities_api.py`, `tests/crmbuilder_v2/ui/test_entities_panel.py`.
7. Verify `crmbuilder-v2/src/crmbuilder_v2/access/{vocab.py,models.py}`, `crmbuilder-v2/migrations/versions/`, `crmbuilder-v2/alembic.ini` all exist.
8. `git sparse-checkout list` includes `crmbuilder-v2/` and `PRDs/`.
9. **Record `ENTITY_TYPES` composition.** Drives Step 3d's conditional `_kinds_for_pair` clauses:
   ```bash
   grep -A 60 "^ENTITY_TYPES" crmbuilder-v2/src/crmbuilder_v2/access/vocab.py | head -70
   ```
   Expected baseline: no PI-004 sibling types (`field`, `test_spec`, `manual_config`, `persona`) present. If any sibling IS present, activate its `_kinds_for_pair` clause; otherwise leave TODO.
10. Baseline test suite green:
    ```bash
    cd crmbuilder-v2
    uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -30
    cd ..
    ```
    Note the pass count.
11. Capture pre-migration Alembic head:
    ```bash
    cd crmbuilder-v2
    uv run alembic current 2>&1
    cd ..
    ```
    The new migration's `down_revision` is this value.
12. Confirm PI-004 is `Open` and ready to be addressed:
    ```bash
    curl -s 'http://127.0.0.1:8765/planning-items/PI-004' | python3 -c "import sys, json; d=json.load(sys.stdin)['data']; print(d.get('planning_item_identifier'), '—', d.get('planning_item_status'))"
    ```
13. Identifier-collision check (per CLAUDE.md v2 session lifecycle): verify SES / DEC heads via `list_recent_sessions` and `list_recent_decisions` to confirm the SES-NNN / DEC-NNN values you will assign at close-out aren't already claimed in parallel.

---

## Implementation

### Step 1 — Alembic migration

Create `crmbuilder-v2/migrations/versions/0013_v0_5_create_requirements_table.py`, modeled on `0008`. Revision metadata:

```python
revision: str = "0013_v0_5_create_requirements_table"
down_revision: Union[str, None] = "<head captured in pre-flight 11>"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

`upgrade()` performs:

**1a. Create `requirements` table** — eleven columns per `requirement.md` §3.2 (seven substantive + identifier + three timestamps):

```python
op.create_table(
    "requirements",
    sa.Column("requirement_identifier", sa.String(length=32), nullable=False),
    sa.Column("requirement_name", sa.String(length=255), nullable=False),
    sa.Column("requirement_description", sa.Text(), nullable=False),
    sa.Column("requirement_acceptance_summary", sa.Text(), nullable=False),
    sa.Column("requirement_priority", sa.String(length=16), nullable=False),
    sa.Column("requirement_status", sa.String(length=16), nullable=False),
    sa.Column("requirement_notes", sa.Text(), nullable=True),
    sa.Column("requirement_created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("requirement_updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("requirement_deleted_at", sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint(
        "requirement_identifier GLOB 'REQ-[0-9][0-9][0-9]'",
        name="ck_requirement_identifier_format",
    ),
    sa.CheckConstraint(
        "requirement_status IN ('candidate', 'confirmed', 'deferred')",
        name="ck_requirement_status",
    ),
    sa.CheckConstraint(
        "requirement_priority IN ('must', 'should', 'could', 'wont')",
        name="ck_requirement_priority",
    ),
    sa.PrimaryKeyConstraint("requirement_identifier"),
)
with op.batch_alter_table("requirements", schema=None) as batch_op:
    batch_op.create_index("ix_requirements_requirement_status", ["requirement_status"], unique=False)
    batch_op.create_index("ix_requirements_requirement_priority", ["requirement_priority"], unique=False)
    batch_op.create_index("ix_requirements_requirement_deleted_at", ["requirement_deleted_at"], unique=False)
```

No SQL-level UNIQUE on `requirement_name` — case-insensitive global uniqueness is enforced at the access layer per `requirement.md` §3.2.1 (mirrors `entity_name`).

**1b. Extend `refs.source_type` and `refs.target_type` CHECK constraints** — add `'requirement'` to BOTH. Pattern: `batch_alter_table("refs", recreate="always")` with `drop_constraint` + `create_check_constraint`. Sorted-alphabetical CHECK expressions for diff readability. Only `'requirement'` is added; sibling PI-004 types are added by their own builds.

**1c. Extend `refs.relationship_kind` CHECK constraint** — add ALL FIVE new kinds: `requirement_scopes_to_domain`, `requirement_touches_entity`, `requirement_touches_field`, `requirement_realized_by_process`, `requirement_verified_by_test_spec`. Per `requirement.md` §3.3.1 the CHECK extension is cheap and forward-compatible — admitting kinds whose targets aren't yet live is fine because a `(requirement, field)` row would fail `target_type` CHECK before the kind matters.

**1d. Extend `change_log.entity_type` CHECK constraint** — add `'requirement'`.

**1e. `downgrade()`** reverses 1a–1d in opposite order. Use module-scope constants (`_NEW_REF_SOURCE_TYPE_CHECK`, `_NEW_REF_TARGET_TYPE_CHECK`, `_NEW_REF_RELATIONSHIP_CHECK`, `_NEW_CHANGE_LOG_ENTITY_TYPE_CHECK` + `_OLD_*` counterparts) for inspectability — match `0011` / `0012`'s convention.

### Step 2 — `Requirement` ORM model

Edit `crmbuilder-v2/src/crmbuilder_v2/access/models.py`. Add after the existing methodology entities (Process / CrmCandidate), modeled on `Entity`:

```python
class Requirement(Base):
    """Methodology entity — one testable statement of what the CRM must do.

    First PI-004 cohort deliverable per ``requirement.md`` v1.0. Parent-
    prefix field naming; primary key is the prefixed-string identifier
    ``requirement_identifier`` (``REQ-NNN``). All five outbound
    relationships (domain affiliation, entity coverage, field coverage,
    process realization, test-spec verification) live in ``refs`` as
    distinct relationship kinds, not FK columns.
    """

    __tablename__ = "requirements"

    requirement_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    requirement_name: Mapped[str] = mapped_column(String(255), nullable=False)
    requirement_description: Mapped[str] = mapped_column(Text, nullable=False)
    requirement_acceptance_summary: Mapped[str] = mapped_column(Text, nullable=False)
    requirement_priority: Mapped[str] = mapped_column(String(16), nullable=False, default="should")
    requirement_status: Mapped[str] = mapped_column(String(16), nullable=False, default="candidate")
    requirement_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirement_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    requirement_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    requirement_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("requirement_identifier GLOB 'REQ-[0-9][0-9][0-9]'", name="ck_requirement_identifier_format"),
        CheckConstraint(_check_in("requirement_status", REQUIREMENT_STATUSES), name="ck_requirement_status"),
        CheckConstraint(_check_in("requirement_priority", REQUIREMENT_PRIORITIES), name="ck_requirement_priority"),
        Index("ix_requirements_requirement_status", "requirement_status"),
        Index("ix_requirements_requirement_priority", "requirement_priority"),
        Index("ix_requirements_requirement_deleted_at", "requirement_deleted_at"),
    )
```

Add `REQUIREMENT_STATUSES`, `REQUIREMENT_PRIORITIES` to the vocab import block at the top of `models.py`.

### Step 3 — vocab.py updates

Four surgical edits to `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`:

**3a. Vocab frozensets** — insert after the `ENTITY_STATUS_TRANSITIONS` block, under a new "PI-004 cohort" section comment:

```python
# Methodology entity `requirement` lifecycle (PI-004 cohort, v0.5+).
# Three-status propose-verify mirroring ``domain`` / ``entity`` per
# ``requirement.md`` section 3.4.
REQUIREMENT_STATUSES: frozenset[str] = frozenset(
    {"candidate", "confirmed", "deferred"}
)

# Same one-way propose-verify gate as ``domain`` / ``entity``: once out
# of ``candidate``, never regress; ``confirmed`` / ``deferred`` move
# freely between each other.
REQUIREMENT_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "candidate": frozenset({"confirmed", "deferred"}),
    "confirmed": frozenset({"deferred"}),
    "deferred": frozenset({"confirmed"}),
}

# MoSCoW priority enum per ``requirement.md`` section 3.2.3. Default
# starter value is ``should`` — consultants must affirmatively escalate
# to ``must``. ``wont`` (priority) is distinct from ``deferred``
# (status): see spec §3.2.3 and §3.4.3 for the distinction. Priority
# transitions are unconstrained — any-to-any movement permitted.
REQUIREMENT_PRIORITIES: frozenset[str] = frozenset(
    {"must", "should", "could", "wont"}
)
```

**3b. `ENTITY_TYPES` addition** — insert `'requirement'` after the v0.8 `'commit'` entry under a new PI-004 cohort comment.

**3c. `REFERENCE_RELATIONSHIPS` additions** — under a new PI-004 cohort section comment after the v0.8 block, add all five:

```python
        # PI-004 methodology cohort (v0.5+) — five outbound kinds
        # declared by ``requirement``. Three target live entity types
        # (``domain``, ``entity``, ``process``); two target sibling
        # cohort entity types not yet live (``field``, ``test_spec``)
        # whose CHECK admittance lands here proactively per
        # ``requirement.md`` section 3.3.1. The ``_kinds_for_pair``
        # clauses for the sibling pairs are conditional (see below).
        "requirement_scopes_to_domain",
        "requirement_touches_entity",
        "requirement_touches_field",
        "requirement_realized_by_process",
        "requirement_verified_by_test_spec",
```

**3d. `_kinds_for_pair` extension** — append AFTER the v0.8 Code Change Lifecycle block. Three pairs unconditional; two pairs gated by sibling-type availability (per pre-flight step 9 reading):

```python
    # PI-004 methodology cohort (v0.5+) — ``requirement`` outbound
    # kinds per ``requirement.md`` section 3.3.1. Three pairs
    # unconditional; two pairs conditional on the sibling entity types
    # having landed in ENTITY_TYPES. The refs.relationship_kind CHECK
    # already admits all five kinds (migration 0013); these clauses
    # gate the cascading ReferenceCreateDialog + RELATIONSHIP_RULES
    # precomputation. A clause for an unregistered target_type would
    # be skipped by the outer ``ENTITY_TYPES × ENTITY_TYPES``
    # comprehension anyway, but leaving an active clause for a missing
    # type is a tripping hazard if the sibling later lands and its
    # build forgets to revisit this file — keep TODO comments
    # explicit.
    if source_type == "requirement" and target_type == "domain":
        kinds.add("requirement_scopes_to_domain")
    if source_type == "requirement" and target_type == "entity":
        kinds.add("requirement_touches_entity")
    if source_type == "requirement" and target_type == "process":
        kinds.add("requirement_realized_by_process")
    # TODO(PI-004 sibling: field) — activate when ``field`` lands in
    # ENTITY_TYPES. See methodology-schema-specs/field.md build prompt.
    # if source_type == "requirement" and target_type == "field":
    #     kinds.add("requirement_touches_field")
    # TODO(PI-004 sibling: test_spec) — activate when ``test_spec``
    # lands in ENTITY_TYPES. See methodology-schema-specs/test_spec.md
    # build prompt.
    # if source_type == "requirement" and target_type == "test_spec":
    #     kinds.add("requirement_verified_by_test_spec")
```

For each sibling already present in `ENTITY_TYPES` per pre-flight step 9, uncomment the corresponding clause.

### Step 4 — Repository

Create `crmbuilder-v2/src/crmbuilder_v2/access/repositories/requirement.py` by copying `entity.py` and applying substitutions: `Entity` → `Requirement`, `entity` → `requirement`, `ENT` → `REQ`, `^ENT-\d{3}$` → `^REQ-\d{3}$`, `ENTITY_STATUSES` → `REQUIREMENT_STATUSES`, `ENTITY_STATUS_TRANSITIONS` → `REQUIREMENT_STATUS_TRANSITIONS`, all `entity_*` field names → `requirement_*`. Rewrite the module docstring to cite `requirement.md` and note the priority field's any-to-any transition posture (per §3.2.3 / §3.4.3, priority is independent of status).

**Additions specific to `requirement`:**

1. **Priority validator** (mirrors `_require_status`):
   ```python
   def _require_priority(priority: object) -> str:
       if priority not in REQUIREMENT_PRIORITIES:
           raise UnprocessableError(
               [FieldError("requirement_priority", "invalid_value",
                           f"must be one of {sorted(REQUIREMENT_PRIORITIES)}")]
           )
       return priority  # type: ignore[return-value]
   ```

2. **`_PATCHABLE_FIELDS`** = `frozenset({"name", "description", "acceptance_summary", "notes", "priority", "status"})`.

3. **`_new_requirement_row` / `_insert_with_autoassign`** signatures take `acceptance_summary` and `priority` alongside the rest.

4. **`create_requirement`** signature:
   ```python
   def create_requirement(
       session: Session, *,
       name: str, description: str, acceptance_summary: str,
       priority: str = "should",
       notes: str | None = None, status: str = "candidate",
       identifier: str | None = None,
   ) -> dict:
   ```
   Validates name / description / acceptance_summary via `_require_nonempty`; defaults priority to `"should"` when None; validates priority via `_require_priority`; defaults status to `"candidate"` when None; validates status via `_require_status`; rejects duplicate names via `_reject_duplicate_name` (global case-insensitive). Otherwise mirrors `create_entity`.

5. **`update_requirement`** (PUT) — full replace; `acceptance_summary` and `priority` are required. Priority transition is unconstrained: just `_require_priority` (no transition check). Status transition uses `_check_transition` exactly as in `entity.py`.

6. **`patch_requirement`** — accepts optional `priority` and `acceptance_summary`. For `priority`, validate via `_require_priority` and assign — no transition check. For `acceptance_summary`, validate via `_require_nonempty`.

7. **`_reject_duplicate_name`** is shape-unchanged — global case-insensitive uniqueness per `requirement.md` §3.2.1 mirrors `entity.md` exactly. Engagement-wide scope; no per-domain partitioning.

8. **`_check_transition`, `delete_requirement`, `restore_requirement`, `list_requirements`, `get_requirement`, `next_requirement_identifier`** mirror `entity.py` exactly with rename substitutions.

### Step 5 — API schemas

Edit `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py`. Add after the `EntityPatchIn` block:

```python
# ---------- Requirements (methodology entity, PI-004 cohort, v0.5+) ----------


class RequirementCreateIn(_Base):
    """POST /requirements body. ``requirement_identifier`` server-assigned
    when omitted; ``requirement_priority`` defaults to ``should``;
    ``requirement_status`` defaults to ``candidate`` server-side.
    Reference attachments are NOT inlined — per ``requirement.md``
    section 3.5.5 they attach via separate ``POST /references`` calls."""

    requirement_name: str
    requirement_description: str
    requirement_acceptance_summary: str
    requirement_priority: str | None = None
    requirement_notes: str | None = None
    requirement_status: str | None = None
    requirement_identifier: str | None = None


class RequirementReplaceIn(_Base):
    requirement_identifier: str | None = None
    requirement_name: str
    requirement_description: str
    requirement_acceptance_summary: str
    requirement_priority: str
    requirement_notes: str | None = None
    requirement_status: str


class RequirementPatchIn(_Base):
    requirement_name: str | None = None
    requirement_description: str | None = None
    requirement_acceptance_summary: str | None = None
    requirement_priority: str | None = None
    requirement_notes: str | None = None
    requirement_status: str | None = None
```

### Step 6 — FastAPI router

Create `crmbuilder-v2/src/crmbuilder_v2/api/routers/requirements.py` by copying `entities.py` and applying substitutions. `_FIELD_PREFIX = "requirement_"`. The POST and PUT handlers pass `acceptance_summary=body.requirement_acceptance_summary` and `priority=body.requirement_priority` alongside the other kwargs. The PATCH handler's `model_dump(exclude_unset=True)` + strip-prefix comprehension continues working unchanged (it forwards `acceptance_summary` and `priority` keys to `patch_requirement(**fields)`).

### Step 7 — Wire router into `main.py`

Edit `crmbuilder-v2/src/crmbuilder_v2/api/main.py`:

1. Add `requirements` to the multi-import from `crmbuilder_v2.api.routers` under a new `# PI-004 methodology cohort (v0.5+).` comment, after the v0.7 governance block.
2. Add `app.include_router(requirements.router)` in the same block after the `commits.router` call.

### Step 8 — UI client methods

Insert into `crmbuilder-v2/src/crmbuilder_v2/ui/client.py` a `# Requirements (methodology entity — PI-004 cohort, v0.5+)` block after the `# Entities` block (around line 791). Seven standard methods mirroring the entity pattern with `/entities` → `/requirements` substitutions:

- `list_requirements(*, include_deleted: bool = False) -> list[dict]`
- `get_requirement(identifier: str) -> dict`
- `create_requirement(body: dict) -> dict`
- `update_requirement(identifier: str, body: dict) -> dict`
- `patch_requirement(identifier: str, body: dict) -> dict`
- `delete_requirement(identifier: str) -> Any`
- `restore_requirement(identifier: str) -> dict`
- `next_requirement_identifier(self) -> str`

### Step 9 — Sidebar entry

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py`. Add `"Requirements"` to the Methodology group between `"Processes"` and `"CRM Candidates"`:

```python
    (
        "Methodology",
        ("Domains", "Entities", "Processes", "Requirements", "CRM Candidates"),
    ),
```

Update the top-of-file section comment to note PI-004 cohort lands the Requirements entry.

### Step 10 — Main window dispatch

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py`:

1. Add `from crmbuilder_v2.ui.panels.requirements import RequirementsPanel`.
2. Add `"requirement": "Requirements"` to `ENTITY_TYPE_TO_SIDEBAR_LABEL` under a `# PI-004 methodology cohort (v0.5+)` comment.
3. Add `elif entry == "Requirements": page = RequirementsPanel(self._client)` in the panel-construction loop, after the `"CRM Candidates"` branch.

### Step 11 — Panel

Create `crmbuilder-v2/src/crmbuilder_v2/ui/panels/requirements.py` by copying `entities.py`. Apply rename substitutions (`entity` → `requirement`, `ENT-NNN` → `REQ-NNN`). Key additions:

**11a. Five-column master pane** per `requirement.md` §3.6.2 and acceptance criterion 11:

```python
def list_columns(self) -> list[ColumnSpec]:
    return [
        ColumnSpec(field="requirement_identifier", title="Identifier", width=120),
        ColumnSpec(field="requirement_name", title="Name"),
        ColumnSpec(field="requirement_priority", title="Priority", width=100),
        ColumnSpec(field="requirement_status", title="Status", width=110),
        ColumnSpec(field="requirement_updated_at", title="Updated", width=180),
    ]
```

The Priority column ships by default — spec §3.6.2 flags it for review but acceptance criterion 11 requires the five-column shape.

**11b. Detail-pane acceptance-summary text editor** — insert between the description editor and the notes collapsible:

```python
acceptance_value = _read_only_text(
    record.get("requirement_acceptance_summary") or "",
    placeholder="What 'this is satisfied' looks like at a methodology level",
)
acceptance_value.setObjectName("requirement_acceptance_summary_value")
form.addRow(required_label("Acceptance summary"), acceptance_value)
```

**11c. Detail-pane priority combo** — insert before the status row per spec §3.6.3 ordering. Title-case display per spec §3.6.2:

```python
priority_row = QFormLayout()
priority_row.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
current_priority = record.get("requirement_priority") or "should"
priority_combo = QComboBox()
priority_combo.setObjectName("requirement_priority_value")
priority_combo.addItems(["Must", "Should", "Could", "Won't"])
display_value = {"must": "Must", "should": "Should",
                 "could": "Could", "wont": "Won't"}.get(current_priority, "Should")
idx = priority_combo.findText(display_value)
if idx >= 0:
    priority_combo.setCurrentIndex(idx)
priority_combo.setEnabled(False)
priority_row.addRow(required_label("Priority"), priority_combo)
outer.addLayout(priority_row)
```

**11d. `_DESCRIPTION_PLACEHOLDER` update** — `"Plain-text description of the capability"` per spec §3.6.3.

**11e. ReferencesSection** unchanged in shape — the shared widget groups by kind. Calling `list_references_touching("requirement", identifier)` returns all five outbound kinds. Cascading dialog vocab clauses from Step 3d gate which target types are offered to the user.

### Step 12 — Dialogs

**12a. `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/_requirement_schema.py`** — copy `_entity_schema.py`. `IDENTIFIER_RE = re.compile(r"^REQ-\d{3}$")`. Add a `priority_choices(current)` helper that always returns the full sorted `REQUIREMENT_PRIORITIES` list (any-to-any movement per spec §3.2.3). `status_choices(current)` mirrors `_entity_schema.py` exactly with `REQUIREMENT_*` substitutions. Field schema list:

```python
_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(key="requirement_name", label="Name", widget="line", required=True),
    FieldSchema(key="requirement_description", label="Description", widget="text",
                required=True, placeholder="Plain-text description of the capability"),
    FieldSchema(key="requirement_acceptance_summary", label="Acceptance summary",
                widget="text", required=True,
                placeholder="What 'this is satisfied' looks like at a methodology level"),
    FieldSchema(key="requirement_notes", label="Internal notes", widget="text"),
    FieldSchema(key="requirement_priority", label="Priority", widget="combo",
                required=True, vocab=REQUIREMENT_PRIORITIES, default="should",
                compute_options=lambda state: priority_choices(state.get("requirement_priority"))),
    FieldSchema(key="requirement_status", label="Status", widget="combo",
                required=True, vocab=REQUIREMENT_STATUSES, default="candidate",
                compute_options=lambda state: status_choices(state.get("requirement_status"))),
]
```

**12b. `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/requirement_crud.py`** — copy `entity_crud.py`, apply rename substitutions. Wires `client.create_requirement` / `client.patch_requirement` / `client.delete_requirement`. The delete dialog uses edge-text confirmation (user types `REQ-NNN`) per spec §3.6.6.

### Step 13 — Tests

Create at minimum 18 new tests across three modules:

**13a. `tests/crmbuilder_v2/access/test_requirement.py`** — repository tests covering:
1. Explicit-identifier create happy path.
2. Omitted-identifier auto-assign returns next `REQ-NNN`.
3. Malformed identifier rejected (422).
4. Explicit-identifier collision rejected (409).
5. Duplicate name (case-insensitive, global) rejected.
6. Default priority is `"should"` when omitted.
7. Invalid priority (e.g., `"maybe"`) rejected.
8. All four MoSCoW values (`must`/`should`/`could`/`wont`) accepted on create.
9. Default status is `"candidate"` when omitted.
10. Invalid status transition (`confirmed → candidate`) raises `StatusTransitionError`.
11. Arbitrary priority transitions allowed (e.g., `should → must`, `must → wont`) — no transition rules.
12. `delete_requirement` idempotent.
13. `restore_requirement` clears soft-delete; 422 if not soft-deleted.
14. `next_requirement_identifier` returns next `REQ-NNN`.
15. Concurrent `_insert_with_autoassign` two-thread test — no identifier collision.

**13b. `tests/crmbuilder_v2/api/test_requirements_api.py`** — FastAPI router tests covering all eight endpoints + the `{data, meta, errors}` envelope; the 422-on-invalid-priority response; the 422-on-invalid-transition response with the spec's `{"error": "invalid_status_transition", "from": ..., "to": ...}` body; at least one references round-trip (POST `/references` with `source_type=requirement, target_type=domain, relationship_kind=requirement_scopes_to_domain` succeeds; same POST with `target_type=field` fails the CHECK because `field` isn't yet in `refs.target_type`'s admitted set).

**13c. `tests/crmbuilder_v2/ui/test_requirements_panel.py`** — smoke test covering panel construction, five-column master shape, detail-pane field presence (identifier label, name, description, acceptance summary, notes collapsible, priority combo, status combo, references section), and create-dialog field schema (no identifier in create mode).

**13d. Vocab-registration tests** — add to `test_requirement.py` or a dedicated `test_vocab_requirement.py`:

```python
def test_requirement_in_entity_types():
    from crmbuilder_v2.access.vocab import ENTITY_TYPES
    assert "requirement" in ENTITY_TYPES


def test_all_five_relationship_kinds_registered():
    from crmbuilder_v2.access.vocab import REFERENCE_RELATIONSHIPS
    for kind in (
        "requirement_scopes_to_domain",
        "requirement_touches_entity",
        "requirement_touches_field",
        "requirement_realized_by_process",
        "requirement_verified_by_test_spec",
    ):
        assert kind in REFERENCE_RELATIONSHIPS


def test_kinds_for_pair_admits_live_targets():
    from crmbuilder_v2.access.vocab import _kinds_for_pair
    assert "requirement_scopes_to_domain" in _kinds_for_pair("requirement", "domain")
    assert "requirement_touches_entity" in _kinds_for_pair("requirement", "entity")
    assert "requirement_realized_by_process" in _kinds_for_pair("requirement", "process")
```

If `field` / `test_spec` are live per pre-flight 9, add the corresponding active-pair assertions; otherwise mark with `pytest.mark.xfail(reason="sibling type not yet in ENTITY_TYPES")`.

### Step 14 — Run tests

```bash
cd crmbuilder-v2
uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -50
cd ..
```

Expected: baseline count + 18+ new tests passing. Halt and report any previously-passing test that now fails.

### Step 15 — Apply migration

```bash
cd crmbuilder-v2
uv run alembic upgrade head 2>&1
uv run alembic current 2>&1
# Expected: 0013_v0_5_create_requirements_table (head)
cd ..
```

### Step 16 — End-to-end verification

API must be running at `127.0.0.1:8765`. Confirm each step (all responses unwrap `.data` per CLAUDE.md's `{data, meta, errors}` envelope rule):

**16a. POST a requirement, server-assigned identifier:**
```bash
curl -sS -X POST 'http://127.0.0.1:8765/requirements' \
  -H 'Content-Type: application/json' \
  -d '{"requirement_name": "Capture mentor availability slots",
       "requirement_description": "When a mentor registers, capture their weekly windows.",
       "requirement_acceptance_summary": "A mentor record carries at least one availability window after registration.",
       "requirement_priority": "must"}' \
  | python3 -c "import sys, json; d=json.load(sys.stdin)['data']; print(d['requirement_identifier'])"
```
Capture the assigned `REQ-NNN`.

**16b. GET round-trip:**
```bash
curl -sS 'http://127.0.0.1:8765/requirements/REQ-001' \
  | python3 -c "import sys, json; d=json.load(sys.stdin)['data']; print(d['requirement_identifier'], d['requirement_priority'], d['requirement_status'])"
```
Expected: `REQ-001 must candidate`.

**16c. Duplicate-name rejection (case-insensitive, global):**
```bash
curl -sS -X POST 'http://127.0.0.1:8765/requirements' \
  -H 'Content-Type: application/json' \
  -d '{"requirement_name": "CAPTURE mentor AVAILABILITY slots",
       "requirement_description": "x", "requirement_acceptance_summary": "y"}' \
  | python3 -c "import sys, json; d=json.load(sys.stdin); print('errors:', d.get('errors'))"
```
Expected: 422 with `duplicate` field error on `requirement_name`.

**16d. Invalid-priority rejection:**
```bash
curl -sS -X POST 'http://127.0.0.1:8765/requirements' \
  -H 'Content-Type: application/json' \
  -d '{"requirement_name": "Second requirement",
       "requirement_description": "x", "requirement_acceptance_summary": "y",
       "requirement_priority": "maybe"}' \
  | python3 -c "import sys, json; d=json.load(sys.stdin); print('errors:', d.get('errors'))"
```
Expected: 422 with `invalid_value` field error on `requirement_priority`.

**16e. Attach a `requirement_scopes_to_domain` reference** (identify or POST a live domain first):
```bash
curl -sS -X POST 'http://127.0.0.1:8765/references' \
  -H 'Content-Type: application/json' \
  -d '{"source_type": "requirement", "source_id": "REQ-001",
       "target_type": "domain", "target_id": "DOM-NNN",
       "relationship_kind": "requirement_scopes_to_domain"}' \
  | python3 -c "import sys, json; d=json.load(sys.stdin); print(json.dumps(d.get('data') or d.get('errors'), indent=2))"
```
Expected: 201 with the created `REF-NNNN` row.

**16f. Valid status transition (`candidate → confirmed`):**
```bash
curl -sS -X PATCH 'http://127.0.0.1:8765/requirements/REQ-001' \
  -H 'Content-Type: application/json' -d '{"requirement_status": "confirmed"}' \
  | python3 -c "import sys, json; d=json.load(sys.stdin)['data']; print(d['requirement_status'])"
```
Expected: `confirmed`.

**16g. Invalid status transition (`confirmed → candidate`):**
```bash
curl -sS -X PATCH 'http://127.0.0.1:8765/requirements/REQ-001' \
  -H 'Content-Type: application/json' -d '{"requirement_status": "candidate"}' \
  | python3 -c "import sys, json; d=json.load(sys.stdin); print('errors:', d.get('errors'))"
```
Expected: 422 with body `{"error": "invalid_status_transition", "from": "confirmed", "to": "candidate"}`.

**16h. List endpoint:**
```bash
curl -sS 'http://127.0.0.1:8765/requirements' \
  | python3 -c "import sys, json; d=json.load(sys.stdin)['data']; print(f'{len(d)} requirement(s)')"
```

**16i. UI smoke** — launch `uv run crmbuilder-v2`; confirm the "Requirements" entry appears in the Methodology sidebar group between Processes and CRM Candidates; click; confirm the five-column master shape with the record from 16a; click the row to view detail pane; confirm the Priority combo renders title-cased "Must" and the references section shows the edge from 16e.

If any verification step fails, stop and report — do not proceed to close-out.

---

## Close-out

### Step 17 — Compose close-out payload

Author `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json` per the v0.8 nine-section shape (SES-NNN per pre-flight 13). Sections:

- **`session`** — status `Complete`; summary cites the spec name and cohort role ("First PI-004 cohort entity build; sibling builds for `field`, `manual_config`, `test_spec`, `persona` follow; cohort umbrella PI-004 resolves at the last sibling build's close-out").
- **`conversation`** — kind `build`, status `complete`.
- **`work_tickets`** — one ticket (this prompt's file, kind `claude_code_prompt`, status `consumed`) addressing PI-004.
- **`planning_items`** — empty (no new PIs surfaced; spec open questions are tracked in the spec itself).
- **`commits`** — list the git SHA(s) created by this session (typically one consolidated commit; see Step 18).
- **`decisions`** — the five DEC entries from `requirement.md` §3.9.1 (DEC-AAA through DEC-EEE placeholders), each with a `decided_in` reference to this session. Assign DEC numbers from `list_recent_decisions` head + 1.
- **`references`** — five `decided_in` edges from each new DEC to this session.
- **`resolves_planning_items`** — **EMPTY**. PI-004 is the cohort umbrella.
- **`addresses_planning_items`** — `[{"planning_item_identifier": "PI-004"}]`.

### Step 18 — Apply and commit

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json
cd ..
```

This atomically writes SES, DECs, references, work_tickets, commits, and lazy-creates the `close_out_payload` + `deposit_event` entities, tee'ing the apply log to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log`.

One consolidated commit:

```bash
git add crmbuilder-v2/migrations/versions/0013_v0_5_create_requirements_table.py \
        crmbuilder-v2/src/crmbuilder_v2/access/models.py \
        crmbuilder-v2/src/crmbuilder_v2/access/vocab.py \
        crmbuilder-v2/src/crmbuilder_v2/access/repositories/requirement.py \
        crmbuilder-v2/src/crmbuilder_v2/api/schemas.py \
        crmbuilder-v2/src/crmbuilder_v2/api/main.py \
        crmbuilder-v2/src/crmbuilder_v2/api/routers/requirements.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/client.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/panels/requirements.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/requirement_crud.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/_requirement_schema.py \
        tests/crmbuilder_v2/access/test_requirement.py \
        tests/crmbuilder_v2/api/test_requirements_api.py \
        tests/crmbuilder_v2/ui/test_requirements_panel.py \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json \
        PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log \
        PRDs/product/crmbuilder-v2/db-export/

git commit -m "$(cat <<'EOF'
v2: PI-004 — build requirement methodology entity (REQ-NNN, MoSCoW, 5 outbound kinds)

First PI-004 cohort deliverable per methodology-schema-specs/requirement.md
v1.0. Migration 0013 creates the requirements table with eleven columns
including the MoSCoW requirement_priority enum (must/should/could/wont,
default should), extends refs.source_type/target_type/relationship_kind
CHECKs for 'requirement' and all five new outbound kinds, and extends
change_log.entity_type CHECK.

Vocab adds REQUIREMENT_STATUSES / _TRANSITIONS (three-status propose-
verify mirroring entity, one-way gate out of candidate),
REQUIREMENT_PRIORITIES (four-value MoSCoW, default should, any-to-any
transitions), 'requirement' in ENTITY_TYPES, and five new
REFERENCE_RELATIONSHIPS kinds. _kinds_for_pair clauses for
(requirement, domain), (requirement, entity), (requirement, process)
activate unconditionally; clauses for (requirement, field) and
(requirement, test_spec) are TODO comments awaiting those sibling
cohort entity types' build prompts. The refs.relationship_kind CHECK
admits all five proactively so sibling builds activate cleanly via
_kinds_for_pair uncomment only.

Access layer mirrors entity.py: identifier auto-assign via SAVEPOINT
retry, case-insensitive global name uniqueness, status transition
validation, priority enum validation (no transition rules per spec
§3.2.3). Eight REST endpoints under /requirements wired in api/main.py.

UI: new RequirementsPanel under the Methodology sidebar group between
Processes and CRM Candidates, with the spec's five-column master pane
(Identifier / Name / Priority / Status / Updated; Priority column ships
by default per acceptance criterion 11), detail pane with all seven
fields including title-cased Priority combo and acceptance-summary
editor, ReferencesSection rendering all five outbound kinds.

Tests (18+): priority enum default + validation + unrestricted
transitions, status transition gate, all five relationship-kind
registrations, identifier auto-assign concurrency safety, soft-delete
round-trip, standard CRUD surface, end-to-end references round-trip.

Addresses PI-004 — does NOT resolve. The cohort umbrella PI-004
resolves at the last of the four sibling cohort builds (field,
manual_config, test_spec; persona is PI-003).

Close-out: SES-NNN, DEC-NNN through DEC-NNN+4, dep_NNN.log.
EOF
)"

git pull --rebase origin main
```

Doug pushes after review.

### Step 19 — Report

Reply with:

- Pre-flight Alembic head: `<recorded>`
- Post-migration Alembic head: `0013_v0_5_create_requirements_table`
- Test suite: `<pre count> → <post count>` (+18+ new tests)
- Verification steps 16a–16i: each pass/fail with one-line summary
- Sibling-type clauses left as TODO: `(requirement, field)`, `(requirement, test_spec)` (or activated, per pre-flight 9)
- Commit SHA: `<sha>`
- SES identifier: `SES-NNN`
- DEC identifiers: `DEC-NNN through DEC-NNN+4`
- PI-004 status: `Open` (cohort umbrella; resolved by last sibling build)
- Next prompts: the four sibling PI-004 build prompts (`CLAUDE-CODE-PROMPT-build-field.md`, `CLAUDE-CODE-PROMPT-build-manual_config.md`, `CLAUDE-CODE-PROMPT-build-test_spec.md`, and `CLAUDE-CODE-PROMPT-build-persona.md` for the PI-003 sibling). The LAST cohort sibling's close-out resolves PI-004 by aggregating the four sibling sessions' work.

---

## Notes for the executing session

- **Five-column master with Priority is the shipping shape** per acceptance criterion 11. The spec §3.6.2 flags it as open for review but the acceptance criterion explicitly requires it.
- **Priority transitions are unconstrained** per spec §3.2.3 — any of the four values may freely follow any other. The repository uses only the enum validator for priority, NOT the transition map. This intentionally differs from status, which DOES use the one-way propose-verify gate.
- **Global, not per-domain, name uniqueness.** Mirror `entity.py`'s `_reject_duplicate_name` exactly — do not introduce a domain-scope filter.
- **`_kinds_for_pair` conditional logic is the subtle part of this build.** The migration extends `refs.relationship_kind` CHECK to admit all five new kinds (cheap and forward-compatible). The `_kinds_for_pair` function is what the cascading dialog reads — a clause for `(requirement, field)` when `field` is not in `ENTITY_TYPES` would have no effect (the outer `RELATIONSHIP_RULES` comprehension iterates over `ENTITY_TYPES × ENTITY_TYPES` and skips the pair), but it creates a tripping hazard if `field` later lands and its build forgets to revisit this file. Leave explicit TODO comments where the sibling type is missing; the sibling's build prompt uncomments its clause as part of its vocab edit.
- **`wont` priority vs `deferred` status are independent** per spec §3.2.3 / §3.4.3. A requirement may be `wont` + `deferred`, `wont` + `confirmed`, `must` + `deferred`, etc. The two fields track different facets; do not collapse them.
- **No deviation from the eight-endpoint surface.** No bulk operations, no inline-reference convenience endpoints. Decomposed-reference posture is a hard rule across the methodology cohort per spec §3.5.5.
- **`apply_close_out.py` is the only path to atomic close-out apply.** Do not hand-author DEC / SES rows via direct curl POSTs — the apply script handles references / commits / deposit_event / close_out_payload entity creation atomically per the v0.8 contract.

---

*End of prompt.*
