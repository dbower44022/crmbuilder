# PI-124 — Selectable / copyable text on every V2 UI message surface: Design Specification

**Status:** v0.1.2 — PI-124's design pass (06-12-26, WTK-122; re-verified
06-12-26, WTK-127; re-verified 06-12-26, WTK-131). Build-ready
specification; not implementation.
**Project:** PRJ-015 (UI usability).
**Planning item:** PI-124 — "All UI message/error dialogs must support
select-all and copy". Surfaced 06-02-26 during PI-123 cutover testing
(a non-copyable engagement-switch error dialog).
**Verified against:** `main` @ `55d8fe71` (every file/line cited below was
re-checked on this revision — the PI description predates PI-β and names
two surfaces that have since moved or been deleted; §1 records the mapping.
WTK-131 re-confirmed that no `crmbuilder_v2/ui` source file changed since
the prior verification point `71bdbb3e`, re-checked the §1 inventory
(error.py flags, crash_banner `_label`, the spawn-failure box in `app.py`,
the 20 + 1 + 1 QMessageBox sites) and the §1.5 prior-art citations against
the source, confirmed `ui/widgets/selectable_text.py` is still absent, and
re-ran the §5.2 regression floor: `test_error_dialog.py` +
`test_auto_reconnect.py` = 18 passing. Note: the T1–T3 build tasks (§4)
have in-flight implementation commits on unmerged `ado/wtk-128..130`
branches; none are on `main` yet, so this spec remains the standing
build-ready artifact).

---

## 0. Scope boundary

**Goal.** From every popup, banner, or message dialog in the
`crmbuilder_v2` desktop UI, an operator can select the full message text
and copy it into a bug report. Behavior is uniform via a shared helper so
future dialogs inherit it. All changes are **additive** — set
text-interaction flags, add a Copy button where the layout is ours — no
dialog restructuring.

**Explicitly OUT of scope:**

- **The PI-123 activation-worker DB-target issue** noted in PI-124's
  description. Separate concern, and moot besides — see §1.1.
- The broad **v1 `espo_impl`/`automation` QMessageBox sweep**. Bounded as
  a separate, *optional* Build task (§4, T4); the `crmbuilder_v2` surface
  plus the named files come first.
- Panel body text (tables, detail panes, chat bubbles). Many are already
  selectable (§1.5); the rest are monitoring surfaces, not message
  popups, and are not part of PI-124's acceptance.

## 1. Current-state inventory (the surfaces, on today's `main`)

### 1.1 `ui/widgets/activation_overlay.py` — DELETED; surface no longer exists

The PI description's item (2) — the "Switching failed at step {step}"
overlay — was the case that surfaced the requirement, but PI-β removed
the activation worker and its overlay entirely (commit `a9d26946`,
slices 1–3): engagement switching is now a client-side context change
(`StorageClient.set_active_engagement` → the `X-Engagement` header) with
no overlay and no failure dialog of its own. Switch-time API errors now
surface through the generic `ErrorDialog` (§1.2) and the crash banner
(§1.3), which this PI covers. **No work item exists for this surface;
the spec records its removal so the sweep doesn't go looking for it.**

### 1.2 `ui/dialogs/error.py` (`ErrorDialog`) — partially compliant

(The PI description's `ui/error_dialog.py` is this file.) Current state:

- `message_label` already has `TextSelectableByMouse`
  (`dialogs/error.py:87-89`). Missing: `TextSelectableByKeyboard`.
- The `detail` disclosure is a read-only `QPlainTextEdit`
  (`dialogs/error.py:98-103`) — already fully selectable/copyable. No
  change needed.
- `title_label` (`dialogs/error.py:77`) is **not** selectable.
- No explicit Copy affordance.

### 1.3 `ui/crash_banner.py` (`CrashBanner`) + the MainWindow banner messages — non-compliant

The auto-reconnect / connection-loss banners are all one widget:
`MainWindow` composes the message strings (`main_window.py` —
`_begin_auto_reconnect`, `_attempt_reconnect`, `handle_reconnect_failed`)
and routes every one through `CrashBanner.show_with_message`. The
exhausted-retries message embeds the standalone launch command and the
log path — the single most copy-worthy string in the app — and the
banner's `self._label` QLabel has no interaction flags. No Copy
affordance. **Fixing `CrashBanner` fixes every banner message;
`main_window.py` needs no changes.**

### 1.4 QMessageBox usages in `crmbuilder_v2` — non-compliant (22 call sites)

All confirm/notify boxes; none set text-interaction flags. Three shapes:

1. **Instance-constructed confirms** (`confirm = QMessageBox(self)` /
   `box = QMessageBox(self)`) — 20 sites:
   `panels/persona.py:463`, `panels/requirements.py:488`,
   `panels/entities.py:448`, `panels/manual_config.py:529`,
   `panels/chat.py:351` (write-confirm, with `setInformativeText` +
   `setDetailedText`), `panels/chat.py:425`, `panels/domains.py:438`,
   `panels/sessions.py:362`, `panels/field.py:510`,
   `panels/status.py:147` (+ informative text), `panels/conversations.py:303`,
   `panels/projects.py:313`, `panels/reference_books.py:352`,
   `panels/crm_candidates.py:458`, `panels/decisions.py:378`,
   `panels/close_out_payloads.py:294`, `panels/test_spec.py:694`,
   `panels/charter.py:151` (+ informative text), `panels/processes.py:583`,
   `panels/work_tickets.py:292`.
2. **Static convenience call** — 1 site: `panels/chat.py:460`
   (`QMessageBox.warning(self, "Export failed", str(exc))`).
3. **Startup/spawn-failure dialog** — 1 site: `ui/app.py:249`
   (`_show_spawn_failure_dialog`, with `setDetailedText(stderr_text)`).
   The detailed text (a `QTextEdit` internally) is already selectable;
   the main text is not.

### 1.5 Prior art to promote (the conventions the helper codifies)

- `about_dialog.py:106-108` — `TextSelectableByMouse |
  TextSelectableByKeyboard` (plus `LinksAccessibleByMouse` where the
  label carries links). The fullest existing flag set.
- A dozen panels set bare `TextSelectableByMouse` on identifier labels
  (e.g. `panels/projects.py:170`, `chat/widgets.py:42`).
- Guarded clipboard writes: `panels/work_tasks.py:224-226` and
  `panels/deposit_events.py:190-192` both do
  `clipboard = QGuiApplication.clipboard(); if clipboard is not None:
  clipboard.setText(text)`.

The helper module (§2) is the promotion of these three patterns into one
importable place.

## 2. The shared helper — `ui/widgets/selectable_text.py` (new module)

One new module under `crmbuilder_v2/ui/widgets/`, no dependencies beyond
PySide6. Four public names:

### 2.1 `SELECTABLE_TEXT_FLAGS` (constant)

```python
SELECTABLE_TEXT_FLAGS = (
    Qt.TextInteractionFlag.TextSelectableByMouse
    | Qt.TextInteractionFlag.TextSelectableByKeyboard
)
```

Exactly these two flags. `TextSelectableByMouse` enables drag-selection,
Ctrl+C on the selection, and — on QLabel — Qt's **standard context menu
with Copy and Select All**, which is the baseline Copy/Select-All
affordance on every label-based surface. `TextSelectableByKeyboard` adds
a visible cursor and keyboard (Shift+arrow) selection for
keyboard-driven operators. No editing flags, ever.

### 2.2 `make_selectable(widget) -> widget`

```python
def make_selectable[W: (QLabel, QMessageBox)](widget: W) -> W:
```

Sets text-interaction flags on a `QLabel` or a `QMessageBox`, returning
the widget for chaining. **Rule: OR the flags into the widget's existing
flags** (`widget.textInteractionFlags() | SELECTABLE_TEXT_FLAGS`), never
overwrite — this preserves `LinksAccessibleByMouse` on link-bearing
labels (the `about_dialog.py` case) and `TextBrowserInteraction` where a
panel already uses it (`panels/topics.py:497`).

QMessageBox note: `QMessageBox.setTextInteractionFlags` governs the main
text label; the informative-text label copies the main label's flags
**at the moment `setInformativeText` is first called**. So
`make_selectable` on a raw QMessageBox must be called **before**
`setInformativeText` to cover both labels. `CopyableMessageBox` (§2.4)
applies the flags in `__init__`, which makes the ordering automatic —
prefer it over `make_selectable(QMessageBox(...))` for new code. The
detailed-text pane is a read-only `QTextEdit` and is selectable/copyable
without our intervention.

### 2.3 `copy_to_clipboard(text: str) -> bool`

The guarded clipboard write promoted from `panels/work_tasks.py:224-226`
/ `panels/deposit_events.py:190-192`: fetch
`QGuiApplication.clipboard()`, return `False` if it is `None`, else
`setText(text)` and return `True`. The two existing panel call sites are
**not** rewired by this PI (keep T1's file set minimal); a later cleanup
may adopt the helper there.

### 2.4 `CopyableMessageBox(QMessageBox)`

Drop-in replacement for the `QMessageBox(self)` constructor pattern:

```python
class CopyableMessageBox(QMessageBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        make_selectable(self)
```

Nothing else changes at call sites — `setWindowTitle` / `setText` /
`setInformativeText` / `setDetailedText` / `setStandardButtons` /
`setDefaultButton` / `exec()` all behave identically.

Static-convenience parity for shape (2) call sites: classmethods
`information`, `warning`, `critical`, `question` with the
`(parent, title, text, buttons=StandardButton.Ok, default=StandardButton.NoButton)`
signature, each constructing a `CopyableMessageBox`, `exec()`ing it, and
returning the clicked `StandardButton` — so `QMessageBox.warning(...)`
becomes `CopyableMessageBox.warning(...)` verbatim.

**Why no Copy *button* on the message box:** QMessageBox's button
protocol closes the dialog when *any* button is clicked (including
`ActionRole` buttons added via `addButton`), so an explicit Copy button
there would dismiss the dialog on use; working around that means
fighting QMessageBox's internal button-box wiring — restructuring, which
the PI forbids. The affordance on QMessageBox surfaces is therefore:
selectable text + the native context menu (Copy / Select All) + Ctrl+C,
on both the message and informative labels, with detailed text already a
selectable QTextEdit. This matches the PI's own per-surface asks — it
requires a Copy *button* only on `error_dialog` and the banners (§3.1,
§3.2), whose layouts we own.

## 3. Per-surface application rules

### 3.1 `ui/dialogs/error.py` (`ErrorDialog`)

- Replace the inline `setTextInteractionFlags` on `message_label` with
  `make_selectable(message_label)` (gains the keyboard flag).
- `make_selectable(title_label)`.
- Add a **"Copy message"** button to the existing `QDialogButtonBox`
  with `ButtonRole.ActionRole`, objectName `error_copy_button`. In our
  own `QDialogButtonBox` only the wired `accepted` signal closes the
  dialog, so an ActionRole button is non-closing — additive, no
  restructuring. Clicking it calls `copy_to_clipboard` with the composed
  payload:

  ```
  {title}

  {message}
  ```

  plus, when a detail pane exists, a trailing
  `\n\n--- details ---\n{detail}` — regardless of whether the disclosure
  is expanded (the operator shouldn't have to open it to capture it).
- The detail `QPlainTextEdit` and the existing disclosure behavior are
  untouched.

### 3.2 `ui/crash_banner.py` (`CrashBanner`) — covers all MainWindow banners

- `make_selectable(self._label)`.
- Add a **"Copy"** `QPushButton` styled with the existing
  `_banner_button_style()`, objectName `banner_copy_button`, placed
  before the Reconnect button. Clicking it calls
  `copy_to_clipboard(self._label.text())` and **does not hide the
  banner** (unlike Reconnect). One new button next to an existing one —
  additive.
- `main_window.py` is **not** edited: `_begin_auto_reconnect`,
  `_attempt_reconnect`, and `handle_reconnect_failed` all flow through
  `show_with_message`, so they inherit both behaviors.

### 3.3 `ui/app.py` — `_show_spawn_failure_dialog`

Replace `QMessageBox(parent)` with `CopyableMessageBox(parent)` (import
swap + constructor swap; the `setDetailedText(stderr_text)` path is
already selectable). This is the fatal pre-window dialog, so it belongs
with the named-surfaces task (T2), not the panel sweep.

### 3.4 The `crmbuilder_v2` QMessageBox sweep

Mechanical, across the 21 panel call sites in §1.4 shapes (1) and (2):

- Shape (1): `QMessageBox(self)` → `CopyableMessageBox(self)`; the
  import of `QMessageBox` **stays** wherever `StandardButton` / `Icon`
  enums are referenced (they are class attributes on QMessageBox;
  referencing them through the subclass also works, but keeping the enum
  references as-written minimizes the diff).
- Shape (2): `QMessageBox.warning(self, "Export failed", str(exc))` →
  `CopyableMessageBox.warning(self, "Export failed", str(exc))`
  (`panels/chat.py:460`).
- No other edits to the panels. New panel code should use
  `CopyableMessageBox` by default; this spec is the citable rule.

## 4. Build-task decomposition

Per PI-124's scoping note (parallel run, max-concurrent 2): independent,
small tasks with **non-overlapping file sets**, each sized well under
the agent-timeout budget (PI-158).

| Task | Files (exclusive) | Depends on |
|---|---|---|
| **T1 — helper + tests** | new `crmbuilder_v2/ui/widgets/selectable_text.py`; new `tests/crmbuilder_v2/ui/widgets/test_selectable_text.py` | — |
| **T2 — named surfaces** | `ui/dialogs/error.py`, `ui/crash_banner.py`, `ui/app.py`; extend `tests/crmbuilder_v2/ui/test_error_dialog.py`; new `tests/crmbuilder_v2/ui/test_crash_banner.py` | `blocked_by` T1 |
| **T3 — v2 QMessageBox sweep** | the 19 `ui/panels/*.py` files listed in §1.4 (incl. `chat.py`) | `blocked_by` T1 |
| **T4 — v1 sweep (OPTIONAL, separate)** | `espo_impl/ui/**`, `automation/ui/**` (22 files currently import QMessageBox) | — |

T2 and T3 can run in parallel once T1 merges (disjoint file sets). T3
touches many files but every edit is the two-line shape in §3.4 — if the
runtime needs it smaller, split by directory alphabetically, never by
file-overlapping concern.

**T4 boundary (the bounded v1 sweep).** v1 (`espo_impl`,
`automation`) must not import from the `crmbuilder_v2` package — the
packages are independent by convention. T4 therefore inlines
`SELECTABLE_TEXT_FLAGS`-equivalent flags or adds a v1-local helper
(e.g. `espo_impl/ui/selectable_text.py`); duplicating ~20 lines across
the package boundary is the accepted exception to the reuse rule. T4 is
optional and is **not** part of PI-124's acceptance; do not start it
before T1–T3 are merged.

## 5. Verification criteria

### 5.1 Per-surface acceptance (the operator test)

From **every** popup below, an operator can select the full message text
(mouse drag or keyboard) and copy it (Ctrl+C or the context menu's
Copy / Select All); where a Copy button is specified, one click captures
the full composed message:

| Surface | Selectable | Copy button |
|---|---|---|
| `ErrorDialog` title + message + detail | ✅ | ✅ `error_copy_button` (copies title+message+detail) |
| Crash/reconnect banner (all MainWindow messages) | ✅ | ✅ `banner_copy_button` (banner stays visible) |
| Spawn-failure dialog (`app.py`) text + detailed text | ✅ | context menu / Ctrl+C |
| Every panel QMessageBox: text + informative text + detailed text | ✅ | context menu / Ctrl+C |

### 5.2 Test approach (keeps the affected package green pre-merge)

All tests live under `tests/crmbuilder_v2/ui/` and follow that
subtree's conventions: offscreen platform (set by both conftests), the
PI-159 §5.3 widget-cleanup rules (`qtbot.addWidget` every top-level
widget; hold a strong reference; no manual `close()` scattering). The
offscreen platform provides an in-process clipboard, so
`copy_to_clipboard` is assertable headlessly.

- **T1** (`test_selectable_text.py`): `make_selectable` sets exactly the
  two flags on a fresh QLabel; ORs (does not clobber) pre-existing
  `LinksAccessibleByMouse`; on a `CopyableMessageBox`, both the text
  label and the informative-text label report selectable flags (assert
  via `findChildren(QLabel)` after `setText` + `setInformativeText`);
  the four static classmethods return the clicked StandardButton (drive
  with `qtbot` + `defaultButton().click()` rather than `exec()`);
  `copy_to_clipboard` round-trips through
  `QGuiApplication.clipboard().text()`.
- **T2**: extend `test_error_dialog.py` — message and title labels carry
  the flags; `error_copy_button` exists, clicking it puts the composed
  title+message+detail payload on the clipboard and does **not** close
  the dialog. New `test_crash_banner.py` — label selectable;
  `banner_copy_button` copies the current message and the banner remains
  visible; the Reconnect signal contract is untouched
  (`test_auto_reconnect.py` must stay green unmodified — 18 currently
  passing tests on `test_error_dialog.py` + `test_auto_reconnect.py` are
  the regression floor).
- **T3**: no new test files. The existing panel-write/dialog suites
  exercise every swept panel; the gate is the affected-package run
  (PI-147 runs it headless pre-merge):
  `uv run pytest tests/crmbuilder_v2/ui/ -q` green, plus
  `uv run ruff check` clean on every touched file.
- **T4** (if run): `automation/tests/test_ui_*` for touched v1 modules.

### 5.3 Done means

T1–T3 merged, `tests/crmbuilder_v2/ui/` green, and a manual spot-check
of the three acceptance rows that have a Copy button / detailed text
(ErrorDialog with detail, banner failure message, chat write-confirm
box). PI-124 resolves on the build-closure that ingests T1–T3; T4, if
ever scheduled, rides a separate task and does not gate resolution.
