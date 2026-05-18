# v0.6 Screenshot Capture Runbook

**Last Updated:** 05-18-26 11:00
**Status:** Active
**Purpose:** Step-by-step operator instructions for the 11 deferred v0.6 screenshots (slice B's 1, slice D's 6, slice E's 4). Each entry covers pre-conditions, navigation steps, capture frame, and tricky-bits notes.

---

## General notes

**Capture tool.** Use whatever native screenshot tool you prefer (GNOME Screenshot, Spectacle, Flameshot, Shutter). Region-select capture is usually best so the frame contains only the surface of interest; full-window is fine for dialogs.

**Resolution and density.** Per PRD §11 §2.14: "natural rendering size of the surface (not full-screen unless the surface fills the screen). Resolution is whatever Doug's display produces; HiDPI is expected. File sizes typically 100–300 KB each."

**Format.** PNG. Lossless. Avoid JPEG.

**Pre-flight common state.** Before each capture session:
1. Pull latest from origin/main
2. Restart the desktop app to ensure all v0.6 work is in effect
3. Active engagement should be **CRMBUILDER** (the dogfood — your actual data is there)
4. The palette fix (commit `bbb...` or whatever) must be in place, otherwise UI is unreadable

**Output paths.** Each screenshot goes to `PRDs/product/crmbuilder-v2/styling-screenshots/slice-{X}/{surface-name}.png` per PRD §6.

**Commit pattern.** One operator commit per slice once all that slice's screenshots are captured:
```bash
git add PRDs/product/crmbuilder-v2/styling-screenshots/slice-{X}/
git commit -m "v2: ui v0.6 slice {X} screenshots — <brief description>"
git push origin main
```

---

## SLICE B (1 screenshot)

### `master-pane-tree.png`

**What it demonstrates:** Topics panel master pane with tree-structured rows, showing chevron indicators (Lucide chevron-down/right at 14px) and the 16px indentation pattern that distinguishes the tree case from the standard table case.

**Pre-conditions:** At least one parent Topic record with 2+ child Topic records. Currently you have zero Topics in CRMBUILDER, so you'll create them.

**Steps:**

1. Open the Topics panel (Governance group in the sidebar)
2. You'll see the empty state. Right-click in the master pane → **New**
3. Create a parent Topic:
   - `topic_name`: `v2 build`
   - `topic_description`: `Top-level topics for CRMBuilder v2 development`
   - Leave `parent_topic_id` empty (no parent — this is a root)
   - Submit
4. Create a first child Topic:
   - `topic_name`: `Methodology rearchitecture`
   - `topic_description`: `Multi-engagement routing, schema work, governance restructure`
   - `parent_topic_id`: select the `v2 build` Topic from the picker
   - Submit
5. Create a second child Topic:
   - `topic_name`: `Styling design pass`
   - `topic_description`: `Tokens, fonts, icons, retoken'd surfaces`
   - `parent_topic_id`: `v2 build`
   - Submit
6. Create a third child for visual variety:
   - `topic_name`: `Engagement management`
   - `topic_description`: `v0.5 single-gesture creation, switching affordance, lifecycle`
   - `parent_topic_id`: `v2 build`
   - Submit
7. Ensure the parent `v2 build` is expanded (click the chevron if collapsed). You should now see the parent row plus 3 indented children.

**Capture frame:** The Topics panel master pane area — at minimum, the chevron column, identifier column, and the topic_name column. Make sure both the parent chevron-down indicator AND the 3 indented children are visible. A region capture of just the table area is fine; full-panel capture is also fine.

**Notes:** The three Topics records created here are real governance content (you've now started tracking topics of v2 conversations). Don't delete them — they're useful project state going forward, and the screenshot's pre-condition is preserved for future re-captures.

---

## SLICE D (6 screenshots)

### `edit-dialog-with-context-strip.png`

**What it demonstrates:** The slice D edit-dialog restructure — edge-to-edge context strip at the top showing identifier + audit timestamps, separated from the form fields below by the new chrome.

**Pre-conditions:** Any existing record in any panel that supports Edit. CRMBUILDER has plenty (Decisions, Planning Items, etc.).

**Steps:**

1. Open the Decisions panel (Governance group)
2. Right-click any decision row (e.g., the most recent — DEC-107 or whatever the latest is) → **Edit**
3. Edit dialog opens with the context strip visible at the top

**Capture frame:** Full dialog window. The context strip should be clearly visible at the top showing the decision identifier and the audit timestamps; the form fields should be below; the Save/Cancel buttons at the bottom.

**Notes:** This is an edit-mode dialog (not New) — the context strip only shows in edit mode. If the strip isn't visible, you might be in a New dialog by mistake.

---

### `delete-confirm-dialog.png`

**What it demonstrates:** The standard delete confirmation dialog with edge-text type-to-confirm field, retoken'd Delete button (destructive_button styling), and the slice D body retoken.

**Pre-conditions:** A non-active record that can be deleted. Avoid the active-engagement edge case (which has different forbid-active behavior).

**Steps:**

1. Open the Risks panel (Governance group). It has 0 real records.
2. Right-click in the master pane → **New** — create a throwaway risk:
   - `risk_name`: `Screenshot placeholder — slice D delete-confirm`
   - Fill required fields with `n/a` or similar
   - Submit
3. Right-click the new Risk row → **Delete**
4. Delete confirmation dialog opens

**Capture frame:** Full dialog window. The edge-text field for type-to-confirm should be visible (empty or partially filled — empty is cleaner). The destructive red Delete button should be prominent. The Cancel button should be visible too.

**Notes:** After capture, complete the delete (type the confirm phrase, click Delete) to remove the placeholder Risk. Or just cancel and leave the Risk in place — your call.

---

### `button-states-primary.png` (most laborious — see notes)

**What it demonstrates:** All 5 visual states of the primary button category: default, hover, pressed, focused, disabled. The QSS rules for each state are in `styling.py`'s slice D additions; the screenshot validates each state's rendering.

**Pre-conditions:** A surface with a primary button visible. Most CRUD dialogs have a primary Save button.

**Steps (compositing approach — recommended):**

Since one screenshot must show all 5 states, you'll capture each state separately and compose into a single image using GIMP, Inkscape, or an online tool. Approximate workflow:

1. Open a CRUD dialog with a primary Save button (e.g., Decisions → Edit any record). Resize/position so the Save button is easily framed.
2. **Default state:** Move mouse away from the button. Capture the button region.
3. **Hover state:** Hover mouse over the button (don't click). Use a screenshot tool with a delay (typically 2-3 seconds) so you can position the mouse before capture. Capture.
4. **Pressed state:** Click and hold mouse button on the Save button. Use the delay-capture trick. Capture while held.
5. **Focused state:** Tab through dialog fields until the Save button has the focus ring. Capture without mouse hover.
6. **Disabled state:** Find a surface where the primary button is disabled. Easiest: open the engagement single-gesture **New** dialog without filling required fields — the Save button may be disabled until valid (if not, fill all fields then clear one). Capture the disabled rendering.
7. Open GIMP (or your image tool of choice). Create a new image roughly 5 buttons wide × 2 buttons tall. Paste each capture as a layer; arrange in a 5-cell row. Add small text labels below each ("default", "hover", "pressed", "focused", "disabled").
8. Flatten and export as PNG to `slice-D/button-states-primary.png`.

**Alternative (single-state simplification):** If compositing is too much, capture only the DEFAULT state and rename the file `button-states-primary-default.png`. Document the deviation in the screenshot commit message. The QSS rules in `styling.py` are the durable spec for the other 4 states; visual verification of those states becomes a slice F roll-up-criterion deferral.

**Capture frame (per state):** Tight crop around the button itself with ~10-20px padding on each side so the button styling (background, border, focus ring) is fully visible. Don't capture the surrounding dialog — that's noise.

---

### `button-states-secondary.png`

**Same as primary, but for the secondary button category.** The secondary button is the standard QPushButton without a category — Cancel buttons, generic action buttons, etc.

**Steps:** Same as primary, but use a Cancel button or any default-style button. Easiest surface: same CRUD dialog as before — capture states of the Cancel button instead.

**Compositing or single-state choice:** Same options as primary.

---

### `button-states-destructive.png`

**Same as primary, but for the destructive button category.** Destructive buttons appear in delete confirmation dialogs.

**Steps:**

1. Open Risks → create a throwaway record (or reuse from `delete-confirm-dialog.png` capture)
2. Right-click → Delete → confirmation dialog opens with the destructive Delete button
3. Capture all 5 states of the Delete button:
   - Default: mouse away
   - Hover: hover over button
   - Pressed: click-and-hold
   - Focused: tab to the button
   - Disabled: type the confirm phrase incorrectly — the Delete button should be disabled until the phrase matches

Compositing same as primary.

---

### `form-controls.png`

**What it demonstrates:** A representative form showing all major form-control types — text input, multi-line text, combo, directory-browser button, required-field markers (asterisks).

**Pre-conditions:** A form with diverse control types visible. The Engagement Create dialog is the canonical choice — has text, multi-line text, combo, browse button.

**Steps:**

1. Open the Engagements sidebar entry → click **New** (top of master pane, or right-click → New)
2. The Engagement Create dialog opens (single-gesture variant)
3. Don't fill the form — capture the blank state so the placeholder text + control types are clearly visible

**Capture frame:** Full dialog window. Make sure all field types are visible: code field (text input), name field (text input), purpose field (multi-line text area), status field (combo with chevron), export_dir field (text + adjacent browse button). Required-field asterisks should be visible on the required fields.

**Notes:** Close the dialog without submitting after capture. No record gets created.

---

## SLICE E (4 screenshots)

### `inline-field-error.png`

**What it demonstrates:** A form field showing an inline validation error per the v0.3 validation-error pattern, retoken'd with slice E's `color.danger.text` and clearer typography.

**Pre-conditions:** A form is open and a field has a validation error displayed.

**Steps:**

1. Open the Engagement Create dialog (Engagements sidebar → New, or top-strip picker → "Manage engagements..." → New)
2. Fill in an INVALID code that violates the regex constraint:
   - Try `lowercase` (lowercase letters not allowed) — should trigger format error
   - Or try `X` (too short, less than 2 chars)
   - Or try `1ABCD` (starts with digit, not letter)
3. Fill other required fields with valid values (name, purpose)
4. Submit
5. The dialog stays open and an inline error appears under the code field

**Capture frame:** The dialog with the error visible. Crop to the relevant field + its error message + a small buffer of context. Don't capture the whole dialog if just the error region tells the story; full-dialog is fine if multiple errors render and you want to show all of them.

**Notes:** Cancel the dialog after capture. No record gets created.

---

### `inline-panel-warning.png` (the Processes soft-deleted-domain case)

**What it demonstrates:** The new WarningCallout widget (slice E) on the Processes panel when a referenced Domain has been soft-deleted. The amber/warning treatment with Lucide circle-alert icon.

**Pre-conditions:** A Process whose parent_domain_id references a Domain that has been soft-deleted. CRMBUILDER currently has 0 Domains and 0 Processes; you'll create them.

**Steps:**

1. Open the Domains panel (Methodology group)
2. Right-click → **New** — create a Domain:
   - `domain_name`: `Test Domain — slice E warning`
   - Fill required fields
   - Submit
3. Open the Processes panel (Methodology group)
4. Right-click → **New** — create a Process:
   - `process_name`: `Test Process — slice E warning`
   - `parent_domain_id`: select `Test Domain — slice E warning` from the picker
   - Fill required fields
   - Submit
5. Go back to Domains panel
6. Right-click `Test Domain — slice E warning` → **Delete** → confirm → record is soft-deleted
7. Go back to Processes panel
8. Click on `Test Process — slice E warning` in the master pane — the detail pane updates
9. The WarningCallout should appear in the detail pane indicating the parent Domain is soft-deleted

**Capture frame:** The detail pane area showing the WarningCallout prominently. Include enough context to show this is a Process detail pane (the form fields below or above).

**Notes:** After capture:
- Restore the Domain (Domains panel → "Show soft-deleted" if there's a filter, or check the panel's deleted-record UX → Restore) to undo the soft-delete state
- Or delete both placeholder records (the Process first since it depends on the Domain) to clean up
- Or leave them — they're labeled "Test...slice E warning" so they're obvious placeholders

---

### `error-dialog.png`

**What it demonstrates:** The standard error dialog with slice E's retoken: Lucide circle-x at the header, heading-3 title in danger-text color, retoken'd button.

**Pre-conditions:** An error dialog is showing.

**Steps (easiest trigger):**

1. Stop the API:
   ```bash
   pkill -f crmbuilder-v2-api
   ```
2. With the desktop app still open, attempt any operation that requires the API — e.g., open Decisions panel and click any row to load detail, or right-click → Refresh
3. The UI tries to call the API, gets connection-refused, surfaces an error dialog

**Capture frame:** Full error dialog window. The circle-x icon at the top should be visible; the heading-3 title in danger-text color; the error message body; the Close/OK button.

**Notes:** After capture, restart the API: `cd crmbuilder-v2 && uv run crmbuilder-v2-api &`. The desktop should recover automatically once the API responds.

---

### `crash-banner.png` (hardest — see notes)

**What it demonstrates:** The crash banner — a high-urgency persistent banner that appears when something catastrophic happens. Slice E retoken'd this off `#7A1F1F` onto `color.danger.default` background with white body-medium text and semi-transparent white-on-color buttons.

**Pre-conditions:** A crash scenario is triggered.

**Steps:** This one is hard because the crash banner is supposed to appear under conditions you don't normally want to trigger. Two approaches:

**Approach A — find the trigger condition in the code:**

```bash
grep -rn "crash_banner\|CrashBanner" crmbuilder-v2/src/crmbuilder_v2/ui/ | grep -v test
```

The grep results will show where the crash banner widget is constructed and what triggers it. Common patterns:
- Worker-thread unhandled exception
- Repeated API-connection failures after a threshold
- Migration failure on startup
- Specific signals emitted by the application kernel

Once you know the trigger, you can intentionally produce the condition. For migration-failure-style triggers, simulating with a temporary file move might work.

**Approach B — add a debug toggle:**

If the codebase has no clean trigger, the slice E commit may have included a debug/test path that renders the crash banner on-demand. Look in `tests/crmbuilder_v2/ui/` for `test_crash_banner.py` or similar — the test fixture might show how to instantiate the banner for inspection.

A quick workaround: temporarily modify a test or add a small standalone Python script that constructs the crash banner widget and shows it in a test window, then capture from there. The visual styling is the same regardless of trigger source.

**Capture frame:** Full crash banner. Show the danger-red background, the white body-medium text, the circle-alert icon, and at least one of the semi-transparent white-on-color buttons.

**Notes:** If neither approach yields a clean capture, defer this screenshot to a future v0.6.1 release when a real crash happens organically (and you remember to capture it). Document the deferral in the screenshot commit message. The crash banner is a low-frequency surface; eyeball verification can wait.

---

## After all captures

Commit screenshots in three operator commits (one per slice):

```bash
# Slice B
git add PRDs/product/crmbuilder-v2/styling-screenshots/slice-B/master-pane-tree.png
git commit -m "v2: ui v0.6 slice B screenshots — master-pane-tree (deferred from initial slice B capture; Topics records created)"

# Slice D
git add PRDs/product/crmbuilder-v2/styling-screenshots/slice-D/
git commit -m "v2: ui v0.6 slice D screenshots — 6 captures: edit-dialog-with-context-strip, delete-confirm-dialog, button-states (primary/secondary/destructive), form-controls"

# Slice E
git add PRDs/product/crmbuilder-v2/styling-screenshots/slice-E/
git commit -m "v2: ui v0.6 slice E screenshots — 4 captures: inline-field-error, inline-panel-warning, error-dialog, crash-banner"

git push origin main
```

After push, slice F's F6 cumulative-coverage criterion is satisfied. v0.6 is fully shippable — the paper-test workstream is the next conversation.

---

*End of runbook.*
