# Kickoff — Phase-tab navigation for the v2 desktop

**Status:** delivered — main `e040e261` (2026-08-30); PI-432 resolved via CNV-329.
**Records (ENG-001):** decision DEC-953 · requirement REQ-526 (confirmed) · planning item PI-432 · project PRJ-113 · release REL-079 · session SES-365 · conversation CNV-328 · kickoff work ticket WT-072.
**Decided:** 2026-08-30, Doug, in a one-decision-at-a-time design conversation (three revisions of the proposal; option A chosen).
**Proposal page (rendered, with screenshots and wireframes):** https://claude.ai/code/artifact/c637ca0e-9839-4060-ad44-c244c31c63e1

## The problem

The v2 desktop sidebar lists all 44 panels in the order they were built — six groups, Governance alone holding 23 entries with no sub-grouping and no alphabetical order (`crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py`, `SIDEBAR_GROUPS`). A session is one phase of one engagement, yet the sidebar is identical in every phase, so roughly 80% of what is on screen is irrelevant to the work in hand and the user scans up and down the list to find the next thing. Nothing marks where the engagement is or what step comes next. CRMBuilder's own operational panels (agent registry, releases, locks, cost, the system-written tables) occupy 14 of the 44 slots on every client engagement.

## The design

**Phases are tabs.** One tab per open phase across the top of the main window, in Master CRMBuilder PRD §4 order. Each tab owns its own sidebar and its own panel stack, so the selected step, selected record, scroll position and drawer width survive switching away and back.

**Each tab's sidebar is that phase's checklist.** The phase's steps, numbered in the order the PRD's "Captured V2 Records" table produces them; done steps ticked, the next step highlighted. Markers are advisory — nothing is locked, no button is disabled (PRF-006).

**A fixed "Every session" group** sits above the steps in every tab: Session (the open one), Decisions, Planning Items, Chat. PRD §11's Open → Conduct → Close lifecycle is the same in all thirteen phases. Chat is one shared surface, not one per tab (DEC-258 is untouched — it ruled out tabs inside Chat).

**Open on demand, like a browser (option A).** The tab for the phase of the open session's planning item is always present. A "+" at the end of the strip lists the thirteen phases plus "Operate CRMBuilder"; opening one adds a tab in phase order. Tabs stay open until closed; the set of open tabs is remembered per engagement.

**Everything else is reachable, never in the way.** A collapsed "All panels ▸" group at the bottom of every sidebar lists all 44 panels alphabetically. Quick open (Ctrl+K) finds any record by identifier prefix or title, and any panel by name.

**Operate CRMBuilder** is the fourteenth choice on the "+" menu: the product's own operations (Agent Profiles, Close-Out Payloads, Commits, Conversations, Cost, Deposit Events, Engagements, Governance Rules, Learnings, Projects, Releases, Resource Locks, Skills, Status, Work Tasks, Work Tickets, Workstreams), alphabetical.

**Ordering rule, applied everywhere:** sequence where the PRD defines one; alphabetical otherwise; never build order.

**The phase map is data, not code.** Phase → ordered panel labels lives in the store so redrafting a PRD phase re-sequences a tab without a release. The label-keyed `build_panel` if-chain in `main_window.py` becomes the registry that map points into. Panels are built on first visit per tab.

## Phase → steps (initial map)

| Phase | Steps in order | Basis |
|---|---|---|
| Every session | Session · Decisions · Planning Items · Chat | PRD §11 |
| 1 Business Context Capture | Charter → Personas → Domains → Processes → References → Glossary | PRD §5 |
| 1.5 Existing System Baseline | Instances → Audit → Entities → Fields → Personas → Processes → Manual Configs | PRD §7 |
| 2 Domain Discovery | Domains → Entities → Personas → Processes → Participants | PRD §9 |
| 3 Inventory Reconciliation | Candidate Review → Entities → Fields → Personas → Processes → Findings → Manual Configs | PRD §8 |
| 4–8 Design *(provisional)* | Requirements → Requirements Review → Processes → Entities → Fields → Reference Entries → Test Specs → Manual Configs → Topics | Part IV placeholder |
| 9 YAML Generation *(provisional)* | Generate YAML → Reference Books | placeholder; LSN-032 |
| 10 CRM Selection *(provisional)* | CRM Candidates | placeholder |
| 11 CRM Deployment | Instances → Deploy → Deploy History | REQ-522 |
| 12 CRM Configuration | Instances → Publish → Publish History → Manual Configs | TOP-101 |
| 13 Verification | Reconcile → Candidate Review → Test Specs → Risks | TOP-109; DEC-721 grid unchanged |
| Operate CRMBuilder | alphabetical, see above | not a client phase |

Provisional rows are reviewed with Doug row by row during the build's design pass, not decided here. "Audit" and "Findings" name existing actions/records that gain their own address.

## Out of scope for this item (carried forward)

- Full-width list with identifier + title in one column; detail as a right-hand drawer; summary-first forms.
- Instance hub (deploy · publish · reconcile · histories as tabs).
- Remembered per-engagement state beyond open tabs; stale badge only when stale.

## Alternatives not taken

- **All 14 phases always open** — exceeds a 1440px window; ten permanent dead tabs on most engagements; placeholder phases as empty tabs.
- **Strip computed from active phases** — tabs appear and vanish without the user acting; still needs an open-on-demand path.
- **Keep all 44 entries, regroup by phase** — fixes the ordering but still scrolls, still shows every phase, no "you are here".
- Revision-1 subject-area sections (Design / Delivery / Instances / Administration) — still put the whole product on screen at once.

## Constraints

DEC-258 (Chat single-active, no tabs inside Chat), DEC-530/532 (Releases hub unchanged), DEC-626 (design shared between desktop and the coming web UI; the phase map is technology-agnostic), DEC-721 (Reconcile grid unchanged), PRF-006/007 (no disabled buttons; secondary actions orange), GVR requirement-first.

## Terminology

Glossary terms approved by Doug on 2026-08-30 and recorded as TERM-036–041: **Phase tab**, **Step** (a panel's position in a phase), **Phase checklist**, **Quick open**, **All panels**, **Operate CRMBuilder**. "Phase", "session", "planning item", "hub", "workbench" and every panel name are existing terms. "Finding" (TERM-014) is reused, not redefined.

## Build shape (for the PI)

1. Panel registry replacing the `build_panel` if-chain; phase map read from the store (with a seeded default).
2. `QTabWidget` main area; each page = sidebar + `QStackedWidget`; lazy panel construction per tab; open-tab set persisted per engagement.
3. Phase checklist sidebar: numbered steps, done/next markers from record counts and status; "Every session" group; "All panels ▸".
4. "+" phase menu and Operate CRMBuilder.
5. Quick open (Ctrl+K): identifier-prefix and title search across record types plus panel names; opens in the current tab.
6. Guides and the sidebar-entries smoke constant updated; ui-PRD screenshots refreshed.

Model A: code on a branch cut from current main, governance on main, `Governed-By: PI-432` trailer on every commit.
