# Styling Design Pass Workstream — Plan

**Last Updated:** 05-16-26 14:00
**Status:** Draft — pre-build, awaiting Conversation 1 to open.
**Predecessor:** v0.4 ship (SES-024 slice F closeout, 05-15-26).
**Parallel workstream:** v0.5 engagement management — see `v0.5-engagement-management-workstream-plan.md`.
**Tracks:** PI-001 (full styling design pass per DEC-024, deferred four times: DEC-024 → DEC-026 → DEC-037 → DEC-042).

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-16-26 14:00 | Doug Bower / Claude | Initial workstream plan. Produced by the v0.5-orientation conversation that reopened PI-001 as a parallel workstream rather than deferring it a fifth time. |

---

## Change Log

**Version 1.0 (05-16-26 14:00):** Initial creation. Establishes the styling design pass as a parallel workstream alongside v0.5 engagement management, executing on its own cadence with boundary discipline between visual and data/routing layers. Two-conversation structure: design pass (settle visual language) followed by build planning (PRD + slice prompts). Version-bundling question — ship as v0.5 vs as v0.6 — left for Conversation 2 to settle.

---

## 1. Purpose

This document is the master plan for the styling design pass workstream — the work that discharges PI-001 after four deferrals.

PI-001 was originally created in DEC-024 at v0.1 close, with the framing that v2's early releases should ship structural capability first and visual polish later. That framing held through v0.2 (DEC-026), v0.3 (DEC-037), and v0.4 (DEC-042), each release deferring styling on the principle that real-world friction from production use was the right trigger for committing to a visual language. DEC-042 added a specific trigger mechanism: PI-001 would open ahead of any other v0.5 candidate if CBM-redo Phase 1 surfaced visual friction on any of the new methodology panels.

That trigger has not fired and is unlikely to fire in v0.5's timeframe either. CBM-redo Phase 1 cannot start until v0.5 ships (the engagement-management workstream is now the gate), and within v0.5 there is no use of the methodology panels that would surface visual friction. Continuing to defer on a trigger that cannot fire is not real deferral; it is silent abandonment.

This workstream reopens PI-001 explicitly as parallel work. It does not wait for CBM-redo. It does not gate on v0.5. It produces a design pass and an implementation against that design pass on its own schedule, coordinated with v0.5 only at coupling points.

---

## 2. What changed and why

### 2.1 The original framing

DEC-024 framed PI-001 as "we'll style v2 when we know what it should look like, and we'll know what it should look like when we've seen people use it." That framing was correct for v0.1, when the system had no users and no concrete content. It remained defensible through v0.2 and v0.3 as a-priori reasoning about what would matter once production use began.

### 2.2 Why the framing no longer holds

Three things changed by v0.4 closeout:

- The "no production use" condition is now structural rather than incidental. v2's only user is the v2 build itself (dogfooded governance), and the v2 build's friction is largely with structural decisions (schema, routing, identifiers) rather than visual treatment. The methodology panels shipped in v0.4 are still empty; even when CBM Phase 1 starts (post-v0.5), the data shape is thin enough that visual friction will be muted.
- The system is no longer small. v0.4 ships sixteen panels across two sidebar groups (Governance with eight entity types, Methodology with four); five dialogs (New Session, references attach, charter/status edit, About, delete confirmation); two scope-level concerns (sidebar group headers, panel base widget styling). Designing a visual language now is comprehensive design, not a quick polish.
- The deferral mechanism has become an anti-pattern. Each deferral added another trigger condition; none of the trigger conditions have ever fired; the open planning item has become a placeholder rather than a real signal. Either PI-001 is real work that should be done, or it should be retired. The v0.5-orientation conversation concluded the former.

### 2.3 The parallel-workstream choice

Two options were considered: (i) defer PI-001 a fifth time and pick it up after v0.5 ships, or (ii) reopen it now as parallel work alongside v0.5. Option (ii) was chosen because:

- The work is independent of v0.5's data/routing layer (Section 4 below details the boundary).
- The slipping deferral has dragged on long enough that scheduling certainty is more valuable than perfectly clean release scoping.
- Running it parallel means CBM Phase 1, when it begins post-v0.5, lands on a stylistically coherent system rather than a Qt-default one.

---

## 3. Scope

### 3.1 What this workstream produces

**A design tokens specification** — palette (semantic naming, not raw hex), typography scale (font family, size scale, weight scale, line-height scale), spacing scale (consistent rhythm for padding, margin, gap), radius scale, border tokens, elevation/shadow tokens, density target. The output of the design conversation.

**Visual decisions for the major component classes** — what panels look like (chrome, padding, header treatment, scrollbar behavior); what the sidebar looks like (group headers, selected/hover/focused states, badge treatment for counts); what buttons look like (primary, secondary, destructive, disabled); what form controls look like (text inputs, dropdowns, toggles, date pickers); what dialogs look like (modal chrome, action button placement); what tables look like (header, row, alternating-row, hover, selected, in-flight states); what the About dialog looks like in its final form.

**Implementation against the design** — QSS application of the tokens to existing widgets, base-widget refactors as needed so widgets accept tokens cleanly, application across all governance panels (eight) and methodology panels (four, plus engagement once v0.5 ships if order works out that way), application to dialogs and the sidebar.

### 3.2 What this workstream does not produce

Deliberately out of scope:

- **Functional changes.** No new widgets, no rearranged information density, no new keyboard shortcuts, no new dialogs. Visual treatment only.
- **Icons or illustration.** v2 currently uses Qt's built-in icons and no illustration. The styling pass does not commission new iconography; it picks an icon source if needed (probably the existing Qt set or one of the open icon families like Phosphor or Lucide) and uses it consistently.
- **Animation.** No animated transitions, no hover-enter/leave animations beyond Qt defaults. Static visual treatment only.
- **Cross-platform polish.** v2 currently targets Linux and macOS desktop. Windows-specific testing is out of scope for this workstream.
- **Dark mode.** Single light theme in v0.5/v0.6. Dark mode would require a second pass and is deferred to a separate PI if anyone asks for it.

---

## 4. Boundary with v0.5

The two workstreams share the same code repository and the same running application. They are safe to run in parallel because they touch mostly different files.

**Styling workstream owns:**

- Any QSS file (the obvious owner).
- A new `design_tokens.py` (or equivalent) module that exposes named tokens.
- Base widget classes that consume tokens.
- Panel-level visual treatment classes if those exist.
- The About dialog (visual content, not the version-bumping logic which belongs to release closeout).
- Anything visual in the sidebar, panels, dialogs.

**v0.5 owns:**

- `config.py` and related configuration code.
- `ActiveEngagementContext` and related state code.
- `access/` modules — repositories, models, schemas.
- API server routing.
- Alembic migrations.
- New `engagement` entity type (model, repository, REST endpoint, MCP tool, panel structure).
- The engagement-switcher mechanism.

**The one real coupling point** is v0.5's new engagement panel (slice B). The panel structurally inherits from v0.4's ListDetailPanel pattern; visually it picks up whatever design tokens are current at the time the slice lands. Two scenarios:

- **Styling ships first.** The engagement panel inherits the new tokens automatically when it lands. No coordination needed.
- **v0.5 ships first.** The engagement panel ships with current Qt-default styling. The styling workstream's panel-retrofit slice picks it up alongside the other panels. No coordination needed.

Either order works. Merge conflicts in shared files (main window structure, panel base widget) are coordinated by whichever lands first owning the structural change; the other rebases.

---

## 5. Workstream structure

### 5.1 Conversations

```
SES-?    v0.5-orientation conversation (this conversation; produced this plan + the v0.5 plan + paper-test deferral)
         ↓
SES-?    Conversation 1: Design pass (settle visual language, produce design tokens spec
                         and component visual decisions doc)
         ↓
SES-?    Conversation 2: Build planning (takes design pass as input, produces styling PRD,
                         implementation plan, and slice build prompts)
         ↓
[Claude Code execution of styling build slice prompts]
         ↓
SES-?    Styling build closeout records
```

### 5.2 What Conversation 1 produces

A single design pass document at `PRDs/product/crmbuilder-v2/styling-design-pass.md` capturing:

- The design tokens (palette, typography, spacing, radius, border, elevation, density).
- Visual decisions for each major component class with prose descriptions sufficient for a separate implementer to apply them. Sketches in prose, not images.
- Application priorities — which panels matter most for the first pass, which can pick up tokens passively.
- Acceptance criteria — how to tell the design pass is "done" before opening Conversation 2.

The design conversation is the more visual-iteration-heavy of the two. It is more likely to need multiple short rounds (propose tokens → react → revise → propose next thing) than a single long writeup. The output document is built incrementally as decisions are confirmed.

Decisions made during Conversation 1 are recorded via direct API at conversation close.

### 5.3 What Conversation 2 produces

The build-planning conversation takes Conversation 1's design pass document as input and produces:

- A styling release PRD — name and version TBD per the version-bundling question (§6).
- An implementation plan with slice breakdown.
- Slice build prompts at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-{version}-{X..}-*.md` (filename pattern depends on whether this ships as v0.5 or v0.6 — see §6).

Strawman slice breakdown — final shape decided in Conversation 2:

- **Slice A — Foundation.** Design tokens module, base widget refactors to consume tokens, sidebar visual treatment, About dialog.
- **Slice B — Governance panel retrofit.** Apply tokens across the eight governance panels.
- **Slice C — Methodology panel retrofit.** Apply tokens across the four methodology panels (plus engagement if it has shipped by then).
- **Slice D — Dialog and form control polish.** New Session dialog, references attach dialog, charter/status edit, delete confirmation, form control state coverage (focus, hover, disabled, error).
- **Slice E — Closeout.** Version bump, README release note, session record drafts.

### 5.4 Order and dependencies

Conversation 1 must close before Conversation 2 opens. Within build, slices run in lettered order; v0.5 build work proceeds in parallel and is coordinated only at the engagement-panel coupling point (§4).

---

## 6. Version-bundling question (open)

Whether the styling work ships as part of v0.5 (a single 0.5.0 bundling engagement management + styling) or as a separate v0.6 (0.5.0 ships engagement management, 0.6.0 ships styling) is left for Conversation 2's build planning to settle.

Considerations the question turns on:

- **Independent capabilities.** Engagement management and styling have no functional dependency on each other. Bundling them as v0.5 mixes unrelated change in the README and complicates release notes.
- **Release timing.** v0.5 is gated on Conversation 1's architectural decisions plus four slices of build work. Styling is gated on its own design pass plus its own slices. They are likely to ship within days of each other but not necessarily on the same day.
- **Closeout coordination.** A bundled v0.5 means one closeout. Two separate releases means two closeouts. Two closeouts is more work but cleaner.
- **Slice naming.** If styling ships as part of v0.5, slice prompts go under `CLAUDE-CODE-PROMPT-v2-ui-v0.5-{X..}-*.md` and interleave with engagement-management slices. If as v0.6, they have their own `v0.6` prefix. Interleaving slice letters is workable but adds friction.

The author's weak prior: ship as v0.6 separately. Engagement management and styling are independent enough that bundling obscures rather than simplifies. But Conversation 2 settles the question with full context.

---

## 7. Governance

### 7.1 Decisions

The v0.5-orientation conversation records (numbers assigned at close):

- PI-001 reopens as parallel workstream (rather than fifth deferral).
- The boundary discipline between styling and v0.5 work (§4 of this document).

Conversation 1 will produce design-pass decisions; Conversation 2 will produce build-planning decisions including the version-bundling resolution.

### 7.2 Planning items

PI-001 is updated to reflect reopening as parallel work. No new planning items are expected from this plan itself; design decisions are decisions, not planning items.

### 7.3 Session record

Each conversation's session record is written at its actual close per the session-record-at-close pattern. Identifiers assigned at close.

### 7.4 Status

No status update from this plan. PI-001's status changes from "Open (deferred 4× per DEC-042)" to "Open (active — parallel workstream)" when the reopening decision is committed. Release status remains `"v0.4 complete"` until the first of v0.5 or styling actually ships.

---

## 8. Open questions and deferred design

- **Light theme only in v0.5/v0.6.** Dark mode is deferred — see §3.2.
- **Icon library choice.** Decided in Conversation 1.
- **Whether to use Qt stylesheets exclusively or supplement with custom paint events.** Qt stylesheets cover most needs but have known limitations (no shadow without custom paint, limited gradient control). Decided in Conversation 1 or Conversation 2 as the component visual decisions force the question.
- **Cross-platform testing posture.** Linux and macOS are the production targets; Windows-on-best-effort. Confirmed in Conversation 2.
- **Accessibility.** WCAG contrast minimums apply by default; full accessibility audit deferred to a separate workstream if requested.

---

## 9. Glossary

- **Design tokens** — Named, semantic values for visual properties (e.g., `color.surface.subtle`, `space.4`, `font.size.body`). The intermediate layer between the design pass and the QSS implementation; lets visual treatment be revised without touching every widget.
- **Visual language** — The coherent set of choices that make the application feel like one product rather than a collection of forms. Includes palette, typography, spacing rhythm, component patterns, and density.
- **Density** — How much information per screen-area. v2's current density is Qt-default, which is moderate. The design pass settles whether v2 wants comfortable, default, or compact density and applies it consistently.
- **Retrofit** — Applying a new visual treatment to an existing widget that already has structural code. Distinct from "redesign" because the widget's behavior and information content don't change.

---

*End of document.*
