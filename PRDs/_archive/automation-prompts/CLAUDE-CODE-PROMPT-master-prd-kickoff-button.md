# CLAUDE-CODE-PROMPT — Master PRD Kickoff Button on Clients Tab

**Repo:** `crmbuilder`
**Scope:** Surgical addition. Phase 1 only. Do not refactor surrounding code.

## Goal

After a client is created on the Clients tab, the user has no in-app way
to begin the requirements discovery process. Add a **"Start Master PRD
Interview"** button to the Clients tab detail pane that generates a
ready-to-paste prompt for an external Claude.ai session, copies it to
the clipboard, and (when possible) saves it to the client's project
folder.

This is the Phase 1 kickoff *only*. Do not generalize this into a
workflow engine, do not add phase tracking, do not add a new tab. A
broader phase-aware workflow surface will eventually come from the
Workflow Engine work in L2 PRD Sections 9–10 — this change must not
prejudge that design.

## Files to Modify

1. **`automation/ui/clients_tab.py`** — add the button to the detail
   pane and wire its click handler.

## Files to Create

1. **`automation/core/master_prd_prompt.py`** — pure-logic module that
   assembles the prompt text and (optionally) writes it to disk.
   Qt-free, fully unit-testable.
2. **`tests/ui/test_master_prd_prompt.py`** — unit tests for the new
   pure-logic module.

## Behavior Specification

### Button placement and appearance

- Add a `QPushButton` labeled **"Start Master PRD Interview"** inside
  `ClientsTab._build_detail_view()`, positioned **after** the
  reachability indicator widget (`self._reachability_widget`) and
  **before** the trailing `layout.addStretch()`.
- Style: match the existing orange "Save Description" button styling
  pattern (`#FFA726` background, white text, hover `#FB8C00`,
  `padding: 6px 16px`, slightly larger than Save Description since this
  is a primary workflow action). Right-align using
  `Qt.AlignmentFlag.AlignRight`, same as the Save Description button.
- Store as `self._detail_start_master_prd_btn`.
- Connect `clicked` to a new method `self._on_start_master_prd_clicked`.
- The button is **always enabled** when a client is selected (per the
  CLAUDE.md guidance: buttons are never disabled — click handlers show
  explanatory messages instead). When `_selected_client` is `None`, the
  handler shows a message and returns.

### Click handler — `_on_start_master_prd_clicked`

Steps, in order:

1. If `self._selected_client is None`, show a `QMessageBox.information`
   saying "Select a client first." and return.
2. Locate the interview guide. The path is computed relative to the
   repo root:
   ```python
   from pathlib import Path
   repo_root = Path(__file__).resolve().parent.parent.parent
   guide_path = repo_root / "PRDs" / "process" / "interviews" / "interview-master-prd.md"
   ```
   If the file does not exist, show a `QMessageBox.warning` saying
   "Master PRD interview guide not found at {path}." and return.
3. Call `automation.core.master_prd_prompt.build_master_prd_prompt(
   client, guide_path)` to assemble the full prompt text.
4. Copy the assembled text to the clipboard via
   `QApplication.clipboard().setText(prompt_text)`.
5. If `client.project_folder` is set and the path exists on disk, call
   `automation.core.master_prd_prompt.save_master_prd_prompt(
   prompt_text, project_folder, client.code)` to write the file. The
   function returns the saved path.
6. Show a `QMessageBox.information` confirming the result:
   - If saved to disk: title "Master PRD Prompt Ready", body
     `"Prompt copied to clipboard.\n\nSaved to:\n{saved_path}\n\nPaste it into a new Claude.ai conversation to begin the Master PRD interview."`
   - If clipboard-only (no project folder, or folder missing): title
     "Master PRD Prompt Ready", body
     `"Prompt copied to clipboard.\n\n(Project folder not set or unreachable — file not saved.)\n\nPaste it into a new Claude.ai conversation to begin the Master PRD interview."`
7. Wrap the disk-write step in `try/except OSError` and, on failure,
   fall back to the clipboard-only message and append the OSError text.

### `automation/core/master_prd_prompt.py` — pure logic

Two functions, both Qt-free:

```python
from datetime import datetime
from pathlib import Path
from automation.core.active_client_state import Client


def build_master_prd_prompt(client: Client, guide_path: Path) -> str:
    """Assemble the full prompt text: header + interview guide body.

    :param client: The selected Client.
    :param guide_path: Absolute path to interview-master-prd.md.
    :returns: Full prompt text ready to paste into Claude.ai.
    :raises FileNotFoundError: If guide_path does not exist.
    """
    guide_body = guide_path.read_text(encoding="utf-8")
    timestamp = datetime.now().strftime("%m-%d-%y %H:%M")
    header = (
        f"# Master PRD Interview — {client.name}\n\n"
        f"**Client:** {client.name}\n"
        f"**Code:** {client.code}\n"
        f"**Date:** {timestamp}\n\n"
        f"You are helping define the Master PRD for {client.name}. "
        f"Follow the interview guide below. Produce the Master PRD as "
        f"a Word document following CRM Builder document standards "
        f"(Arial, #1F3864 headings, two-column requirement tables, "
        f"alternating row shading #F2F7FB, body 11pt, US Letter, 1\" "
        f"margins). Do not mention specific product names "
        f"(EspoCRM, WordPress, etc.) in the Master PRD — product "
        f"names belong only in implementation documentation.\n\n"
        f"---\n\n"
    )
    return header + guide_body


def save_master_prd_prompt(
    prompt_text: str,
    project_folder: str,
    client_code: str,
) -> Path:
    """Write the prompt to {project_folder}/prompts/.

    Filename format: master-prd-prompt-{client_code}-{YYYYMMDD-HHMMSS}.md

    :param prompt_text: Full assembled prompt text.
    :param project_folder: Absolute path to client project folder.
    :param client_code: Client code, used in filename.
    :returns: The Path the file was written to.
    :raises OSError: If the directory cannot be created or file written.
    """
    folder = Path(project_folder) / "prompts"
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"master-prd-prompt-{client_code}-{timestamp}.md"
    file_path = folder / filename
    file_path.write_text(prompt_text, encoding="utf-8")
    return file_path
```

**Important:** The header date uses `MM-DD-YY HH:MM` format per project
output standards. The filename timestamp uses `YYYYMMDD-HHMMSS` for
sortability — these are intentionally different.

**Important:** The header must NOT mention any specific CRM product
name. The interview guide itself is the source of truth for content;
the header only adds client identification and document standards
guidance.

### Tests — `tests/ui/test_master_prd_prompt.py`

Use `pytest` and `tmp_path`. Cover:

1. **`test_build_master_prd_prompt_includes_client_name`** — assert
   client name appears in the assembled prompt.
2. **`test_build_master_prd_prompt_includes_client_code`** — assert
   client code appears.
3. **`test_build_master_prd_prompt_includes_guide_body`** — write a
   small fake guide to `tmp_path`, build the prompt, assert the fake
   guide content is in the result.
4. **`test_build_master_prd_prompt_date_format`** — assert the header
   contains a date matching `\d{2}-\d{2}-\d{2} \d{2}:\d{2}` (regex).
5. **`test_build_master_prd_prompt_no_product_names`** — assert the
   *header portion only* (text before `---`) does not contain
   "EspoCRM" except inside the explicit "do not mention" instruction.
   (Easier: assert the literal "do not mention specific product names"
   instruction substring is present.)
6. **`test_build_master_prd_prompt_raises_when_guide_missing`** —
   assert `FileNotFoundError` raised for nonexistent path.
7. **`test_save_master_prd_prompt_creates_prompts_folder`** — point at
   `tmp_path` with no `prompts` subfolder; assert it's created.
8. **`test_save_master_prd_prompt_filename_includes_code`** — assert
   returned path's filename contains the client code.
9. **`test_save_master_prd_prompt_writes_content`** — assert file
   contents match the input string exactly.
10. **`test_save_master_prd_prompt_unique_filenames`** — call twice in
    quick succession; assert filenames differ (the seconds-resolution
    timestamp may collide on fast machines, so if needed, sleep 1.1s
    between calls or mock `datetime.now`).

Use a minimal `Client` fixture — only `name` and `code` are needed.
Construct it directly with whatever required fields the dataclass has;
look at `automation/core/active_client_state.py` for the actual
signature and pass minimal valid values for other fields.

## Out of Scope — Do Not Do These

- Do not add a "phase status" indicator anywhere.
- Do not add buttons for Phases 2–11.
- Do not modify the Client model or schema.
- Do not modify `automation/ui/requirements_window.py` or any other
  workflow-related view.
- Do not write any code that tracks whether the Master PRD has been
  generated, imported, or completed — that's Workflow Engine territory.
- Do not change the Clients tab create-form flow.
- Do not log credentials or any client data beyond name/code in the
  prompt header.

## Acceptance Criteria

1. With a client selected on the Clients tab, the "Start Master PRD
   Interview" button appears in the detail pane below the reachability
   indicator.
2. Clicking the button with a client selected and a valid project
   folder produces:
   - The prompt text on the clipboard.
   - A file at `{project_folder}/prompts/master-prd-prompt-{code}-{timestamp}.md`.
   - A confirmation dialog showing the saved path.
3. Clicking the button with no project folder set produces:
   - The prompt text on the clipboard.
   - A confirmation dialog noting the file was not saved.
4. The assembled prompt begins with `# Master PRD Interview — {Client Name}`,
   contains the client name, code, current date in `MM-DD-YY HH:MM`
   format, the document-standards instructions, a `---` separator, and
   then the full body of `interview-master-prd.md`.
5. All new tests pass: `uv run pytest tests/ui/test_master_prd_prompt.py -v`
6. Full suite still passes: `uv run pytest tests/ -v`
7. Ruff clean: `uv run ruff check automation/ tests/`
8. No existing test broken, no existing behavior changed.

## Reporting Back

When finished, report:
- Number of new tests added and pass/fail count.
- Total test count before and after.
- Any deviations from this spec and why.
- The exact button label and the file path written when tested with
  the CBM client (if you have access to it).
