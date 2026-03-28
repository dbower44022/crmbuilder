# Claude Code Prompt — Bottom Bar UI Reorganization

## Context

CRM Builder's main window has a bottom bar below the output panel
containing utility and action buttons. The current layout mixes
different types of actions together without clear grouping. This
task reorganizes the bottom bar and adds a missing View Report button.

The relevant PRD is `PRDs/application/app-ui-patterns.md`,
Section 2.2 and Section 4.4.

## Current State

The current bottom bar contains (in some order):
- Clear Output
- Preview YAML
- Generate Docs
- Open Reference Docs
- Import Data

**Missing:** View Report button (opens most recent .log report file)

## Required Changes

### 1. Reorganize the bottom bar into three groups

```
[Clear Output] [Preview YAML] [View Report] | [Generate Docs] [Open Reference Docs] | [Import Data]
```

The groups are separated by a visual divider (a vertical line or
spacer). Left to right:

**Group 1 — Output utilities:**
- Clear Output
- Preview YAML
- View Report ← ADD THIS

**Group 2 — Documentation:**
- Generate Docs
- Open Reference Docs

**Group 3 — Data:**
- Import Data

### 2. Add the View Report button

The View Report button opens the most recent `.log` report file
from the instance's `reports/` directory in the system's default
text viewer.

Behavior:
- Always visible (never hidden)
- Follows the never-disable pattern — if no report exists, emits
  "No report available." to the output panel
- Uses `self.state.last_report_path` to find the most recent report
- Opens using the platform-appropriate file open command
  (`xdg-open` on Linux, `os.startfile` on Windows)

### 3. Remove the old View Report reference if it exists

If there is any existing View Report button or reference in the
current UI, consolidate it into the new button in Group 1.

## Files to Modify

- `espo_impl/ui/main_window.py` — bottom bar layout and new button
  handler
- `espo_impl/docs/impl-ui-patterns.md` — update to reflect new
  bottom bar layout (Section 4 and the file structure ASCII diagram)

## Implementation Notes

- All existing button behavior should be preserved exactly — this
  is a layout reorganization, not a behavior change
- The never-disable pattern applies to all buttons including the
  new View Report button
- Use a `QFrame` with a vertical line style or `addSpacing()` /
  `addStretch()` to create visual separation between groups
- The bottom bar uses a `QHBoxLayout` — maintain this pattern

## Testing

After implementation, verify:
1. All six buttons are visible and correctly labeled
2. Buttons appear in the correct left-to-right order with group
   separators visible
3. View Report emits "No report available." when no report exists
4. View Report opens the correct `.log` file after a Run or Verify
5. All existing button behaviors are unchanged
