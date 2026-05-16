# Styling Design Pass — Conversation 1 — Kickoff Prompt

**Last Updated:** 05-16-26 14:00
**Purpose:** Seed prompt for a new Claude.ai conversation that produces v2's styling design pass — design tokens specification plus visual decisions for the major component classes — as a single deliverable.
**Position in workstream:** **First of two** conversations in the styling design pass workstream. Predecessor: SES-025 (v0.5-orientation conversation that reopened PI-001 as parallel work). Successor: styling Conversation 2 — build planning.
**Workstream master:** `PRDs/product/crmbuilder-v2/styling-workstream-plan.md`
**Tracks:** PI-001 (full styling design pass per DEC-024 → DEC-026 → DEC-037 → DEC-042; reopened as parallel workstream by DEC-076).
**Operating mode:** ARCHITECTURE (per project default).

---

## The task

Drive a structured design conversation that produces **one deliverable**:

**`PRDs/product/crmbuilder-v2/styling-design-pass.md`** — a complete design pass document capturing:

1. **Design tokens** — palette (semantic naming, not raw hex throughout — e.g., `color.surface.subtle`, `color.text.primary`, `color.accent`, `color.danger`), typography (font family, size scale, weight scale, line-height scale), spacing scale (consistent rhythm for padding, margin, gap), radius scale, border tokens, elevation/shadow tokens, density target.
2. **Visual decisions for major component classes** — panels (chrome, padding, header treatment, scrollbar behavior), sidebar (group headers, selected/hover/focused states, badge treatment for counts), buttons (primary, secondary, destructive, disabled), form controls (text inputs, dropdowns, toggles, date pickers), dialogs (modal chrome, action button placement), tables (header, row, alternating-row, hover, selected, in-flight states), About dialog. Prose descriptions sufficient for an implementer to apply them; no images required (this is a Claude.ai conversation, so sketches in prose are the medium).
3. **Application priorities** — which panels matter most for the first pass, which can pick up tokens passively.
4. **Acceptance criteria** — how to tell the design pass is "done" before opening Conversation 2.

The design conversation is more visual-iteration-heavy than written-PRD-heavy — likely multiple short rounds (propose tokens → react → revise → propose next thing) rather than one long writeup. The document is built incrementally as decisions are confirmed.

At conversation close: decisions written via direct API as DEC-NNN records; any deferred items written as PI-NNN records; one session record written through the v0.4-shipped New Session dialog per the session-record-at-close pattern. Per DEC-025, a Claude Code apply prompt may also be authored to batch the writes.

---

## Context — why this conversation exists, and why now

PI-001 (full styling design pass) was created in DEC-024 at v0.1 close on the principle that v2's early releases should ship structural capability first and visual polish later. Deferred three more times: DEC-026 at v0.2 close, DEC-037 at v0.3 close, DEC-042 at v0.4 close. DEC-042 added an explicit trigger mechanism: PI-001 would open ahead of any other v0.5 candidate if CBM-redo Phase 1 — running against the four methodology panels v0.4 delivered — surfaced visual friction.

The v0.5-orientation conversation (SES-025, 05-16-26) surfaced that this trigger cannot fire in v0.5's timeframe. CBM redo Phase 1 waits on v0.5 (DEC-075 — engagement management as a v0.5 prerequisite) plus the paper-test (DEC-077 — deferred until v0.5 + CBM engagement) plus Phase 1 itself. The four-deferral pattern with progressively-elaborate trigger conditions that never fire is an anti-pattern; PI-001 has effectively become a placeholder rather than a real signal.

DEC-076 (05-16-26) reopens PI-001 as a parallel workstream alongside v0.5, executing independently with its own kickoff (this document), design pass (this conversation's output), build planning (Conversation 2), and slices. The boundary discipline: styling owns the visual layer (QSS, design tokens, palette, typography, spacing, panel chrome, sidebar visuals, About dialog, hover/focus/disabled states); v0.5 owns the data/routing layer (config, ActiveEngagementContext, alembic, API routing, engagement entity). One coupling point: v0.5's new engagement panel (slice B in the strawman) inherits whatever tokens have shipped at the time the slice lands; either workstream can ship first.

By the time Phase 1 begins (post-v0.5, post-paper-test), the styled system has either landed or is close to landing. CBM Phase 1 work lands on a coherent system rather than a Qt-default one. That's the goal of running this in parallel rather than deferring a fifth time.

---

## What's shipping today, visually

v2 currently renders with Qt defaults plus a thin layer of structural styling. v0.4 shipped sixteen panels across two sidebar groups:

- **Governance group (8):** Decisions, Sessions, Risks, Planning Items, Topics, References, Charter, Status.
- **Methodology group (4):** Domains, Entities, Processes, CRM Candidates.

Plus five dialogs:

- New Session
- References attach
- Charter / Status edit (versioned-replace)
- About
- Delete confirmation

Plus two scope-level concerns: sidebar group headers and the panel base widget (ListDetailPanel pattern). And a navy stub (`#1F3864`) is used for some accent treatment per legacy convention — the design pass decides whether to keep or revise this.

After v0.5 ships, a new Methodology-group panel will exist (Engagements — exact name TBD in v0.5 Conversation 1). The styling work covers it the same way as the others.

---

## What this conversation produces, concretely

The design pass document is structured as follows:

### Section 1 — Design tokens

A canonical list of semantic tokens with their concrete values. Example shape:

```
Color.
  surface.base — primary panel background — concrete value TBD
  surface.subtle — secondary panel background (alternating rows, sidebar) — TBD
  surface.elevated — modal/dialog background — TBD
  border.default — panel borders, table cell borders — TBD
  text.primary — body text — TBD
  text.secondary — secondary labels, captions — TBD
  text.placeholder — empty state, placeholder text — TBD
  accent.default — primary actions, selected state — TBD
  accent.muted — hover on accent surfaces — TBD
  danger.default — destructive actions, error states — TBD
  warning.default — warning states — TBD
  success.default — success states (rare in v2) — TBD

Typography.
  font.family — system default with explicit fallback — TBD
  font.size.body — TBD
  font.size.small — TBD
  font.size.h2/h3 — TBD
  font.weight.regular/medium/bold — TBD
  font.line-height.body/heading — TBD

Spacing.
  space.0 (0px), space.1 (4px), space.2 (8px), ... — geometric or modular scale — TBD

Radius / border / elevation / density — same pattern.
```

The conversation decides each token's concrete value through iterative proposal and reaction.

### Section 2 — Component visual decisions

For each component class, a prose description sufficient to implement against:

- Panel chrome and padding
- Sidebar visuals (group headers, item states, badges)
- Buttons (primary, secondary, destructive, disabled, focused, hover)
- Form controls (text inputs, dropdowns, toggles, date pickers — focus rings, error states)
- Dialogs (modal chrome, padding, action button placement)
- Tables (header, row, alternating-row, hover, selected, in-flight states)
- The About dialog as a "small showcase" surface

### Section 3 — Application priorities

Which panels and dialogs the first build pass touches; which absorb tokens passively.

### Section 4 — Acceptance criteria

How to tell the design pass is "done" before Conversation 2 opens. Strawman: tokens are named consistently; every component class has a prose visual decision; no contradictions across decisions; light-theme contrast meets WCAG AA at minimum; an implementer reading the doc can produce QSS without further questions.

---

## Read this first

Before producing any token value or visual decision:

1. **`crmbuilder/CLAUDE.md`** — universal entry. The Architecture § and the Key Patterns § are most relevant; visual styling is not addressed there directly but the panel structure context matters.
2. **The styling workstream plan** at `PRDs/product/crmbuilder-v2/styling-workstream-plan.md` — end-to-end. §3 (scope), §4 (boundary with v0.5), §7 (governance) inform this conversation's posture.
3. **v0.4 PRD** at `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md` — §4 (the four methodology panels' UI specifications) and §5 (cumulative acceptance criteria across all 16 panels). Mostly for inventorying what surfaces need styling decisions.
4. **The v0.3 and v0.4 PRDs** at `ui-PRD-v0.3.md` and earlier for the ListDetailPanel pattern shape (sidebar → master pane → detail pane), since the styling decisions apply to this pattern.
5. **DEC-024, DEC-026, DEC-037, DEC-042** (in the v2 decisions snapshot at `PRDs/product/crmbuilder-v2/db-export/decisions.json`) — the historical deferral chain and the rationale for each defer. Context for what "comprehensive design pass" was meant to deliver each time.
6. **The current source styling state** — `grep -rn "QPalette\|setStyleSheet\|StyleSheet\|background:\|color:" crmbuilder-v2/src/` to inventory what visual treatment already exists in code (probably minimal). Read whatever's there.
7. **DEC-076** (in the SES-025 close-out payload at `close-out-payloads/ses_025.json`) — the parallel-workstream decision this conversation operates within.

---

## Architectural / design questions likely to arise

These are not all of equal weight. Some are real forks; some are mostly settled-by-convention. Both kinds are listed because the conversation should know when to pause and when to advance.

**Real forks (likely to pause under the two-part test):**

- **Light theme only at v0.5/v0.6, or design tokens that anticipate dark mode from day one?** Anticipating dark mode means every color token has a light variant and a dark variant; not anticipating it means tokens are flat values and a future dark-mode pass replaces every token's value. *Weak prior: anticipate. The cost is small if done at token-naming time; the cost is large if retrofit later.*
- **Density target.** Comfortable (Qt-default-ish), default, or compact? Affects every padding decision downstream. *Weak prior: default with a slight compaction relative to Qt-default. v2 is a power-user tool; comfortable density wastes screen real estate.*
- **Icon library choice.** Stick with Qt-built-in icons (free, available, generic), or adopt an open icon family like Phosphor or Lucide (better visual consistency, requires a small library dependency)? *Weak prior: stick with Qt-built-in for v0.5/v0.6; revisit if visual coherence demands it later.*
- **QSS-only or supplement with custom paint events?** Qt stylesheets cover most needs but have known limitations (no shadow without custom paint, limited gradient control). *Weak prior: QSS-only at v0.5/v0.6; custom paint is a separate workstream if shadows or gradients become important.*
- **Brand accent.** Keep `#1F3864` (the navy stub used in legacy panels) as the primary accent, or pick something new? *Weak prior: revisit. Navy is fine but was never deliberately chosen as a brand accent.*

**Settled-by-convention (advance and announce):**

- Audit-column visual treatment (timestamps in a footer or sidebar — pick a convention; consistent across panels).
- Scrollbar visual treatment (system default unless friction surfaces).
- Empty-state treatment (centered prose, secondary text color, no illustration).
- Loading/in-flight treatment (spinner from Qt-built-in; no custom animations at v0.5/v0.6).

---

## Working style

Per Doug's preferences:

- **ARCHITECTURE mode.** Two-part test: real downstream impact AND two viable options producing meaningfully different outcomes. Density target and dark-mode-anticipation pass both tests; choice of green for `success.default` does not — pick a green and move on.
- **One decision at a time.** Present a question with a weak prior; wait for explicit approval or pushback before advancing. Terse approvals ("yes", "confirm", "approve B") are sufficient.
- **Plain text discussion.** Visual decisions can use prose-sketch ("the sidebar's selected state is a 2px left border in `accent.default` plus a `surface.subtle` background tint, no text bold change") instead of images.
- **Never use the ask_user_input popup widget.** Always plain text.
- **The design pass document is drafted incrementally as decisions are confirmed.** By the time the last component class is decided, the document is ~90% complete; the final pass adds the §3 application priorities, the §4 acceptance criteria, and reads cleanly end-to-end.
- **Surface concerns proactively** rather than waiting to be corrected.

---

## Pre-flight checks

Before the first token or visual decision is discussed:

1. The SES-025 close-out has been applied (sessions.json should include SES-025; decisions.json should include DEC-075, DEC-076, DEC-077; PI-001 should reflect the parallel-workstream description).
2. `git status` clean on `main` for the crmbuilder repo.
3. `git pull --rebase origin main` returns no new commits (or only commits that don't touch styling — v0.5 commits in parallel are expected and don't conflict).
4. Read items 1–7 in the "Read this first" section above.

---

## Governance — at conversation close

Per DEC-025 conventions:

- **Decisions.** Numbered starting at the next available DEC-NNN (DEC-078 or later, depending on whether v0.5 Conversation 1 closes first). Expected: 5–10 decisions covering token-level forks (dark mode anticipation, density target, icon library, QSS-only posture, brand accent, possibly base palette family), and the major component decisions if any pass the two-part test.
- **Planning items.** Any explicitly deferred design work becomes new PIs (PI-017+ once the SES-025 close-out has applied). Likely candidates: dark mode implementation (if anticipated at token level but not implemented), accessibility audit, animation pass, custom paint events for shadows, Windows-platform testing.
- **Session record.** Next available SES-NNN. Written at conversation close via the New Session dialog, or via a Claude Code apply prompt.
- **Artifacts.** The design pass document committed to the crmbuilder repo at the conversation's close, plus the close-out payload(s).
- **Status.** No status update. Status remains `"v0.4 complete"` until v0.5 or styling actually ships (whichever first).

---

## What this conversation does NOT do

- **No code.** Pure design discussion and document authoring. QSS files, design tokens module, base widget refactors, About dialog implementation all wait for the styling build (after Conversation 2 produces the build prompts).
- **No build planning.** The styling PRD, implementation plan, and slice prompts are produced by Conversation 2, not here.
- **No work on the version-bundling question.** Whether styling ships as v0.5 (bundled with engagement management) or as v0.6 (separately) is decided in Conversation 2's build planning, not here.
- **No work on engagement management.** v0.5's data/routing-layer work has its own parallel workstream — see `v0.5-conversation-1-kickoff.md` and `v0.5-engagement-management-workstream-plan.md`. Boundary: this conversation owns visual layer; v0.5 owns data/routing.
- **No paper-test work.** The paper-test is deferred until v0.5 ships and a CBM engagement is created (DEC-077).
- **No icon assets created.** Icon choices are referenced by name (Qt-built-in / Phosphor / Lucide) but no SVG authoring happens.
- **No dark mode implementation.** Whether tokens anticipate dark mode (variant-able) or not is a design decision; actually shipping a dark theme is out of scope.
- **No accessibility audit.** WCAG AA contrast minimums apply by default; a full audit (focus traversal, screen reader pass, keyboard-only paths) is deferred unless a PI requests it.

---

*End of kickoff prompt.*
