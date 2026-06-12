# PI-159 — Fix the multi_sort_header paintSection segfault and harden the Qt suite against paint-path crashes

Status: **Design spec** (WTK-118, ui area). Delivers the spec only —
implementing the lifetime guards and suite hardening (Develop) and writing the
guard tests + verification harness (Test) are separate Work Tasks in the same
Workstream and are **out of scope here**.

Scope of this PI: `ui/widgets/multi_sort_header.py` (the crash site),
`tests/crmbuilder_v2/ui/conftest.py` + `tests/conftest.py` (suite hardening),
the widget-test ownership conventions in
`tests/crmbuilder_v2/ui/widgets/test_multi_sort_header.py`, and one bounded,
optional runtime-area backstop in `runtime/coordinating_runtime.py` (§5.4). No
schema change, no migration, no API-surface change, no redesign of the
multi-sort feature itself (WTK-068 behaviour is preserved bit-for-bit).

## 1. The problem

The full `tests/crmbuilder_v2` suite intermittently dies with SIGSEGV (pytest
returncode 139) inside `ui/widgets/multi_sort_header.py` line 127
`paintSection`, during pytest-qt's `_process_events`, under the offscreen
platform. No test fails — the interpreter crashes mid-run, so the whole
verification run aborts.

Five occurrences on 06-12-26 alone, all captured by the PI-157 verify-log
persistence (`crmbuilder-v2/data/logs/verify/`, gitignored — live machine
only):

| # | Work Task | Log | Collateral |
|---|-----------|-----|------------|
| 1 | WTK-096 | `WTK-096-20260612T022927Z.log` | failed the gate for a doc-only branch; operator merge |
| 2 | WTK-102 | `WTK-102-20260612T045125Z.log` | doc-only branch again |
| 3 | WTK-109 | `WTK-109-20260612T074924Z.log` | 3 of ~8 full-suite runs that day |
| 4 | WTK-111 | `WTK-111-20260612T083459Z.log` | phase rollback also undid sibling WTK-110's clean merge |
| 5 | WTK-115 | `WTK-115-20260612T100542Z.log` | sibling WTK-114 rollback collateral again |

The operational damage multiplier is the PI-147 verification gate: every Work
Task merge runs `run_pytest` (`runtime/coordinating_runtime.py:185`, `uv run
pytest <target> -q`), and `select_test_target` falls back to the **full**
`tests/crmbuilder_v2` suite for any change it cannot localize — which includes
every doc-only branch. So an intermittent crash in one Qt paint path randomly
fails verification for work that never touched the UI, flags
`needs_attention`, pauses the runtime, and (in the parallel pool) triggers the
PI-145 phase rollback, undoing **siblings'** clean merges. This is now the
dominant operator-intervention cause in the PRJ-022 queue.

Two distinct defects therefore need fixing, and this spec designs both:

- **the crash itself** — a widget-lifetime defect in or around
  `MultiSortHeaderView.paintSection` (§3, §4);
- **the blast radius** — one paint-path crash aborting an entire verification
  run and rolling back unrelated work (§5).

## 2. The crash site and what is already known

`multi_sort_header.py` is unchanged since it landed (WTK-068, commit
`458d3fa7`), so line 127 at every capture is the glyph draw:

```python
def paintSection(self, painter, rect, logical_index):   # line 116
    super().paintSection(painter, rect, logical_index)  # line 119
    indicator = self.indicator_for(logical_index)       # → self._proxy.sort_keys()
    if indicator is None:
        return
    ...
    painter.save()                                      # line 126
    painter.drawText(                                   # line 127  ← crash
        rect.adjusted(0, 0, -_GLYPH_MARGIN, 0), ..., glyph,
    )
    painter.restore()
```

Facts established against the source (versions: pytest 9.0.2, pytest-qt 4.5.0,
PySide6 6.10.2):

- **The line-127 attribution comes from pytest's default-on faulthandler
  plugin**, which dumps the Python stack of every thread on SIGSEGV. It marks
  the Python line *executing when the signal arrived* — `drawText` is where
  the heaviest C++ work in the method happens (font shaping, raster paint
  engine), so it is the probable signal site whatever the dangling edge is.
  Do not over-index on `drawText` itself being the defect.
- **The crash window is pytest-qt's teardown event processing.** pytest-qt
  4.5.0 wraps each test with `_process_events()` (a bare
  `QApplication.processEvents()`) and, in teardown, closes then
  `deleteLater()`s every `qtbot.addWidget`-registered widget
  (`pytestqt/qtbot.py::_close_widgets`). `DeferredDelete` events have
  loop-level delivery rules, so a deferred deletion posted in one test can be
  delivered during a **later** test's `_process_events` — destruction crossing
  test boundaries is the defining hazard of this window.
- **pytest-qt holds registered widgets by weakref.** `_close_widgets` does
  `w = w()` (a `weakref.ref` call) before closing. Registration does **not**
  keep a widget alive.
- **The widget-test helper builds an ownership-broken graph.**
  `tests/crmbuilder_v2/ui/widgets/test_multi_sort_header.py::_build` creates a
  parentless `QTableView` held only by `_build`'s local + the qtbot weakref,
  an **unparented** `MultiSortProxyModel()`, and a source model constructed as
  a temporary (`proxy.setSourceModel(_Model())`). When `_build` returns only
  `(proxy, header)`, the table — the Python-owned root of the C++ ownership
  tree, including the header child — is garbage the moment CPython collects
  it, at an arbitrary later point. The header/proxy wrappers survive in the
  test while their C++ substrate can be destroyed under them.
- **Production sites are ownership-clean by contrast.** Both install sites
  parent the proxy (`ui/widgets/references_section.py:501`
  `MultiSortProxyModel(self)`; `ui/panels/references.py:100`) and parent the
  header to the table (`references_section.py:523`, `panels/references.py:104`).
  The defect class is reachable from production too (any teardown-window paint
  against a half-destroyed panel), but the test helper is the most aggravated
  instance.
- **This is the known transient-Qt-object hazard pattern.** The project has
  hit the shape before: transient Qt objects owned ambiguously between Python
  GC and the C++ object tree crash when the two destructors disagree on
  timing (the EntityCrudDialog worker-widget `deleteLater()` precedent).

## 3. Root-cause analysis approach

The crash is intermittent, so the analysis is structured as evidence-mining →
native attribution → amplification → hypothesis elimination. Each step is
useful even if a later step stalls, and §4's guards are designed to be safe
under **all** surviving hypotheses, so the fix does not block on a
deterministic reproducer.

### 3.1 R1 — mine the five verify logs

The persisted logs each carry the faulthandler dump (the `TestRunResult.output`
tail is 20 000 chars wide precisely so the traceback survives —
`coordinating_runtime.py:178`). Extract per occurrence:

- the **test running at crash time** (faulthandler prints
  `Current thread ... (most recent call first)` plus pytest's last-collected
  item) — is it the same test/module every time, or scattered? A constant
  crashing test points at that test's own widget graph; a scattered one points
  at cross-test deferred-delete drift (the §2 window);
- whether the crashing test is itself a multi-sort test or an **unrelated UI
  test** whose `_process_events` delivered a stale event from an earlier
  multi-sort test — the strongest discriminator between H1 and H2 below;
- secondary-thread stacks (worker QThreads alive at crash time would implicate
  a cross-thread paint, currently believed impossible — confirm).

### 3.2 R2 — native backtrace

The Python-side dump cannot distinguish "QPainter on a destroyed paint device"
from "shiboken trampoline dispatched on a half-destructed C++ object" from "a
font-engine crash". Get C-level frames once:

- enable core dumps (`ulimit -c unlimited`) and run the §3.3 amplification
  loop until a core lands; `gdb python core` → `bt` on the crashing thread; or
- run the loop directly under `gdb --batch -ex run -ex bt --args python -m
  pytest tests/crmbuilder_v2/ui -q`.

The frames that matter: presence of `QHeaderView::paintEvent` /
`QWidget::~QWidget` / `QSortFilterProxyModel` / `QFontEngine` in the crash
stack decides between the §3.4 hypotheses.

### 3.3 R3 — amplification harness

Build a small repeat-run script (the Test Work Task's deliverable, reused by
§6 verification):

- N (default 30) consecutive `uv run pytest tests/crmbuilder_v2/ui -q` runs,
  recording each returncode; report the crash rate. Baseline expectation from
  the 06-12 operational data: ~35–40% per **full-suite** run (3–5 hits in ~8
  runs), likely lower per ui-subtree run — measure it;
- two amplifier variants, each toggled by an env var so the same script
  measures all configurations: (a) an autouse fixture injecting `gc.collect()`
  before teardown (amplifies H2's GC-timing race), (b) running only the
  multi-sort + references-panel modules in a tight loop (amplifies same-module
  interactions).

If an amplifier makes the crash near-deterministic, distill a standalone
minimal reproducer (R4) and run the §3.4 eliminations against it. Time-box
this: if after the time-box the crash is reproducible only statistically,
proceed to §4 anyway — the guards are hypothesis-independent — and let §6's
statistical criterion carry the proof.

### 3.4 Ranked hypotheses and their discriminating checks

- **H1 — destruction-window virtual dispatch (most likely).** A paint or
  update event is delivered during `_process_events` to a header whose owning
  table is mid-destruction (closed + `deleteLater()`-pending from
  `_close_widgets`, or destroyed by the H2 GC path). `paintSection` is a
  Python override: shiboken's trampoline dispatching a virtual on a
  half-destructed object, or `painter.drawText` against a paint device being
  torn down, is a classic segfault. *Check:* R2 frames show `~QWidget` /
  `QWidgetPrivate` in a sibling frame, or the R1 crashing test is not a
  multi-sort test.
- **H2 — Python-side ownership loss in the widget-test helper (confirmed
  hazard; is it the trigger?).** The §2 `_build` graph: the table wrapper is
  collectable mid-session; collection destroys the C++ table + header while
  the test still drives the header. *Check:* the `gc.collect()` amplifier
  spikes the crash rate; fixing `_build`'s ownership (§4.3) alone drops it.
- **H3 — `setHorizontalHeader` replacement interplay.** Both the test and
  production replace the view's default header. Verify against Qt 6.10 source
  what happens to the replaced default header (deleted? hidden but alive and
  still receiving events?) and whether double-ownership of the replacement
  (Python wrapper + view ownership) can double-delete. *Check:* code reading
  plus an R4 variant that never replaces the header.
- **H4 — offscreen font-engine fault in `drawText` (least likely).** The
  session-scoped QApplication outlives every test, so glyph-cache teardown
  should not be in play; listed only because line 127 is a text draw.
  *Check:* R2 frames inside `QFontEngine`/harfbuzz with a **valid** widget
  chain would resurrect this; otherwise discard.

## 4. Lifetime-guard design for paintSection

Defense in depth: each guard is independently safe, cheap on the hot path, and
none changes rendered output for a live widget. Together they make
`paintSection` a no-op under every torn-down state §3.4 enumerates.

### 4.1 Validity guards in the paint path

`shiboken6.isValid(obj)` is the canonical "is the C++ object alive" probe
(confirmed available in the pinned PySide6 6.10.2). Guard the three objects
the method touches — self, the painter, the proxy:

```python
import shiboken6

def paintSection(self, painter, rect, logical_index):  # noqa: N802
    if not shiboken6.isValid(self) or not painter.isActive():
        return
    super().paintSection(painter, rect, logical_index)
    proxy = self._proxy
    if proxy is None or not shiboken6.isValid(proxy):
        return
    indicator = self.indicator_for(logical_index)
    ...
```

`indicator_for` gains the same `None`-or-invalid proxy check (it is public API
for tests, so it must be safe standalone), and `_on_sort_keys_changed` guards
`shiboken6.isValid(self)` before `self.viewport()` — the proxy's
`sortKeysChanged` can fire while the header is dying.

As a last fence, the glyph-draw block is wrapped in `try: ... except
RuntimeError: return` — PySide6 raises `RuntimeError("Internal C++ object
already deleted")` on wrapper access it *can* detect, and converting that into
a skipped glyph is strictly better than a crash. The except clause stays
narrow (`RuntimeError` only); it must not swallow programming errors.

### 4.2 Detach on proxy destruction

`attach_proxy` additionally subscribes to the proxy's `destroyed` signal and
clears the back-reference:

```python
proxy.destroyed.connect(self._on_proxy_destroyed)   # sets self._proxy = None
```

so a destroyed proxy is unreachable from the paint path even before the §4.1
validity probe. A symmetric public `detach_proxy()` is added for completeness
(disconnect `sortKeysChanged` + `destroyed`, clear `self._proxy`) — production
sites don't currently need to call it, but the teardown story should not
depend on that staying true.

### 4.3 Ownership normalization — the codified convention

The rule, enforced at the §5.3 convention level and applied immediately to the
known-broken instance:

- every `MultiSortProxyModel` is **parented** to its view or panel (production
  already complies: `references_section.py:501`, `panels/references.py:100`);
- every source model handed to `setSourceModel` is parented or held by a
  strong Python reference for the view's lifetime — never a temporary;
- test helpers return (or otherwise strongly hold) the **root** of the widget
  tree they build. `test_multi_sort_header.py::_build` is amended to parent
  the model and proxy and to return the table alongside `(proxy, header)` so
  the ownership root lives exactly as long as the test.

### 4.4 Transient-object discipline (`deleteLater` posture)

`paintSection` deliberately constructs **no** QStyle/QStyleOption objects — it
delegates stock painting to `super()` and draws with the supplied painter.
The design keeps it that way, as a stated rule: if a future change needs a
`QStyleOptionHeader`, it is constructed per-call as a Python local (a value
type — not a QObject, so `deleteLater()` does not apply and must not be
cargo-culted onto it), never cached on the instance across paints. The
project's existing `deleteLater()` rule stays scoped to where it belongs:
QObject-derived transients (modal sub-dialogs, workers) whose destruction
must be deferred off the current event — per the EntityCrudDialog precedent.

## 5. Suite hardening

Goal: a paint-path crash in one widget can no longer abort the entire
`tests/crmbuilder_v2` run — and the conditions that *cause* teardown-window
paints are removed deterministically rather than probabilistically.

### 5.1 Offscreen platform consistency

`tests/crmbuilder_v2/ui/conftest.py` already pins
`os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` before any
QApplication exists — but only for collections that import that conftest
first. Root-level Qt tests (`tests/test_audit_entry.py`,
`tests/test_configure_progress.py`, …) each setdefault it ad hoc inside their
own fixtures, after collection. Hoist one `setdefault` to the repo-root
`tests/conftest.py` so the platform is pinned for **every** pytest invocation
regardless of target subset or collection order. `setdefault` (not assignment)
stays the idiom: an operator exporting a real platform for local visual
debugging keeps their override.

### 5.2 Deterministic deferred-delete drain

The §2 window — destruction drifting across test boundaries — is closed by
draining `DeferredDelete` at the end of every UI test's teardown, **after**
pytest-qt's `_close_widgets` has posted its deletions. Mechanism: a
`pytest_runtest_teardown` hook in `tests/crmbuilder_v2/ui/conftest.py` ordered
after pytest-qt's (hook ordering verified empirically during the build with an
instrumented run — pytest-qt's own teardown is a plain hookimpl, so a
`trylast=True` impl suffices), executing a bounded settle loop:

```python
app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
app.processEvents()
```

(twice, or until no events were dispatched, capped) — so every widget a test
created is fully destructed **inside that test's teardown**, and no later
test's `_process_events` can deliver paints or deletions belonging to it. This
is the deterministic counterpart of the §4 guards: guards make a stale paint
harmless; the drain makes it not happen.

### 5.3 qtbot widget-cleanup conventions

Codified in the `tests/crmbuilder_v2/ui/conftest.py` module docstring (the
file every UI test already flows through), as the reviewable convention:

1. every top-level widget goes through `qtbot.addWidget` (close + deleteLater
   handled centrally — never manual `widget.close()` scattered in tests);
2. `qtbot.addWidget` holds a **weakref** — registration is cleanup, not
   ownership. Tests/helpers must keep a strong reference to the widget-tree
   root for the test's duration (§4.3);
3. models and proxies are parented to their view/panel; no parentless QObject
   may outlive the function that created it unless the test holds it.

A one-pass audit of `tests/crmbuilder_v2/ui/` against rules 2–3 is part of the
Develop Work Task (the `_build` helper is the known violation; the audit
confirms whether it is the only one).

### 5.4 Crash isolation strategy

Evaluated containment options, with the chosen posture:

- **Prevention is the fix (chosen, primary).** §4 + §5.1–5.3 remove the
  crash; containment exists only so a *future* paint-path defect degrades to
  one failed verification instead of a rollback cascade.
- **Gate-level crash retry (chosen, backstop — runtime area, separate Work
  Task).** In the PI-147 gate, a returncode of 139/134 is a *signal death*,
  not a test failure — pytest reported no failing test. Design: `run_pytest`'s
  caller retries **once** on signal-death returncodes only; both outputs are
  persisted as verify logs (PI-157 path, both retained); the retry is recorded
  as a finding so flake visibility is never lost; a second consecutive crash
  fails verification exactly as today. Deterministic test failures (rc 1) are
  **never** retried — PI-147 semantics are untouched.
- **Per-test process isolation (`pytest-forked`) for the ui subtree
  (evaluated, not adopted by default).** It would contain any segfault to one
  reported failure, but forking a process that already holds a live
  QApplication is formally unsupported by Qt, and the session-scoped `qapp`
  fixture is exactly that. Adopt only if a build-time spike shows the forked
  ui subtree green and stable under the §3.3 harness; otherwise rejected.

## 6. Verification criteria

The crash is intermittent, so acceptance is statistical plus structural —
referencing the five §1 verify logs as the failure baseline.

- **V1 — baseline measured.** Before the fix lands, the §3.3 harness records
  the pre-fix crash rate (N ≥ 30 ui-subtree runs, plus the documented 06-12
  operational rate of 3–5 crashes in ~8 full-suite runs). This is the number
  V3's statistics are powered against.
- **V2 — guard unit tests (deterministic).** New tests in
  `test_multi_sort_header.py` drive `paintSection` directly with a real
  `QPainter` on a `QPixmap` against each torn-down state: (a) no proxy
  attached, (b) proxy invalidated via `shiboken6.delete(proxy)`, (c) header
  whose owning table has been deleted (paint via a still-held wrapper),
  (d) inactive painter. Each must return without crashing and draw no glyph;
  `indicator_for` must return `None` for (a)/(b). The existing WTK-068
  behaviour tests must pass unchanged (no regression to indicators or click
  routing).
- **V3 — repeated-run acceptance.** ≥ 20 consecutive full
  `tests/crmbuilder_v2` runs (the harness, on the fixed branch) with **zero**
  returncode-139/134 occurrences and all green. At the observed ≥ 35% per-run
  baseline, 20 clean runs has p < 0.001 under the unchanged-rate null — the
  documented acceptance argument for an intermittent defect.
- **V4 — falsifiability (best-effort, time-boxed).** If R4 produced a
  reproducer: it crashes pre-fix and passes post-fix. Otherwise: on a scratch
  branch, revert the §4 guards but keep §5, and re-run the harness under the
  strongest amplifier — a returning crash demonstrates the guards are causal,
  not coincidental. Inconclusive amplification does not block close (V3
  carries acceptance); record the outcome either way.
- **V5 — operational acceptance.** Across the ADO verification cycles
  following the merge (rolling window until PI-159 close), zero new
  `crmbuilder-v2/data/logs/verify/WTK-*.log` entries with returncode 139
  attributable to `paintSection` — the WTK-096/102/109/111/115 pattern goes
  quiet, and no operator merge/re-merge is forced by this crash class.
- **V6 — hygiene.** `ruff check` clean on every touched file;
  `tests/crmbuilder_v2/ui` green; if the §5.4 gate retry ships, its
  runtime-area unit tests (retry-on-139 once, never-on-rc-1, finding recorded,
  both logs persisted) green as well.

## 7. Build surface

Separate Work Tasks in this Workstream, in dependency order:

1. **Develop (ui):** §4 guards in `multi_sort_header.py`; §4.3 `_build`
   ownership fix; §5.1 root-conftest platform pin; §5.2 deferred-delete drain;
   §5.3 convention docstring + audit.
2. **Develop (runtime, optional backstop):** §5.4 gate crash-retry with
   finding + dual log persistence. Independent of (1); may be dropped if the
   PM judges prevention sufficient after V3/V5.
3. **Test:** §3.3/§6 harness script; V2 guard unit tests; execution of
   V1/V3/V4 and recording of results.

Out of scope: any change to multi-sort behaviour or rendering for live
widgets; `pytest-forked` adoption (unless its §5.4 spike passes); PI-147
target-selection changes; the PI-157 log format.
