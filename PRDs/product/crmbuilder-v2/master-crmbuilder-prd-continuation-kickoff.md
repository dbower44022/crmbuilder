# Master CRMBuilder PRD — Architecture Review Continuation — Kickoff

**Document type:** Kickoff prompt (session seed for continuing the V2 architecture review)
**Repository:** `crmbuilder`
**Path:** `PRDs/product/crmbuilder-v2/master-crmbuilder-prd-continuation-kickoff.md`
**Last Updated:** 05-26-26
**Operating mode:** ARCHITECTURE
**Estimated duration:** Open-ended; one substantive session, possibly producing artifacts plus governance content
**Engagement:** CRMBUILDER
**Predecessor session:** SES-089 (Architecture review — Master CRMBuilder PRD consolidation, three-category conceptual model, Phase 1 redesign, 13 new PIs and 5 glossary terms)

---

## What landed in SES-089 (the prior architecture-review session)

Five repository commits substantively reshaping the methodology document landscape, plus ten architectural Decisions (DEC-291..DEC-300) and thirteen Planning Items (PI-061..PI-073), all governance-recorded against the CRMBUILDER engagement.

**Direction established:**

- A new top-level directory `specifications/` at the repo root holds all internal documents defining process and functionality (broad scope, subdirectories permitted) — DEC-292.
- All PRDs and internal documents in MD format going forward; customer-facing deliverables remain format-flexible per case — DEC-293.
- Single consolidating Master CRMBuilder PRD at `specifications/master-crmbuilder-PRD.md` (currently v0.1, status DISCUSSION DRAFT — NOT YET APPROVED) is the canonical source of truth; existing methodology documents are subordinate references that retire as their content is subsumed — DEC-291.
- Master CRMBuilder PRD scope is end-to-end — initial requirements capture through deployed functional application — DEC-294.
- CRMBuilder is the first client (dogfood); CBM is the second client (validation against existing document-based CBM artifacts as benchmark); discovery-driven iterative authoring (draft enough to run, run, refine) — DEC-295.
- Three-category conceptual model classifies everything V2 holds: (1) Process Management Tools and Data — Status, Decisions, Sessions, Planning Items, etc., (2) Deliverables — Entities, Processes, Requirements, Code commits, etc., (3) Process Support Knowledge/Tools — Skills, Patterns, Inventories, conduct docs, interview guides — DEC-296.
- Phase 1 of the methodology is client-led intake (client brings what they consider relevant; consultant synthesizes; Skills loaded contextually based on client defining statements) — DEC-297. The v0.1 PRD's existing draft of Phase 1 (named "Business Context Capture" with structured-interview shape inherited from `interview-master-prd.md` v1.4) is in tension with this and needs rewriting.
- Glossary at `specifications/glossary.md` is the canonical store for term definitions, MD-scaffolded with future V2 migration captured as a planning item — DEC-298. Five initial terms: Engagement (TERM-001), Skill (TERM-002), Pattern (TERM-003), Inventory (TERM-004), Client (TERM-005).
- Session and Conversation entities to be redesigned (Session as medium-agnostic communication unit, Conversation as focused topical sub-unit within a session, 1:N) — DEC-299. Implementation captured as PI-073.
- Sandbox close-out identifier-capture protocol (check live heads at start of authoring AND before any mid-conversation amendment) — DEC-300, surfaced by two rounds of mid-session identifier collision and recovery.

**Open planning items (PI-061..PI-073), thirteen total:**

| PI | Title | State |
|---|---|---|
| PI-061 | Add Glossary data structure and UI to V2 (migrate from specifications/glossary.md) | Open; depends on PI-062 |
| PI-062 | Resolve V2 cross-engagement reference store architecture | Open; detailed scope |
| PI-063 | Build out Skills library | Open; placeholder |
| PI-064 | Build out Pattern library | Open; placeholder |
| PI-065 | Build out Inventory library | Open; placeholder |
| PI-066 | Define Skill trigger/loading mechanism | Open; placeholder |
| PI-067 | Tooling for cross-engagement reference content | Open; placeholder, depends on PI-062 |
| PI-068 | Create specifications/ directory README/manifest | Open; small task |
| PI-069 | Iterative drafting of Master CRMBuilder PRD remaining phases | Open; ongoing |
| PI-070 | Retire transitional headers when content is consolidated | Open; placeholder |
| PI-071 | Architecture for storing client-provided information (engagement-scoped inputs) | Open; detailed scope |
| PI-072 | Define Engagement Level Setup process and V2 records | Open; detailed scope |
| PI-073 | Redesign Session and Conversation entities | Open; detailed scope |

**Artifacts on disk to read before starting work:**

1. `crmbuilder/CLAUDE.md` — repo-level orientation including the "Current direction" section at the top naming the Master CRMBuilder PRD as the consolidating source of truth.
2. `specifications/master-crmbuilder-PRD.md` v0.1 (218 lines, DISCUSSION DRAFT — NOT YET APPROVED) — the document being drafted iteratively.
3. `specifications/glossary.md` v0.2 — five terms; the canonical term-definition store.
4. SES-089 close-out payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_089.json` — the full governance record of what was decided, planned, and produced in the prior session, including the conversation_description for context.

---

## The task

Continue the V2 architecture review. The previous session established direction and surfaced thirteen open planning items; this session picks up from there. Doug chooses the specific focus at the start of the conversation.

Candidate directions, roughly ordered by what would unblock the most downstream work:

- **Direction A — Review and revise the Master CRMBuilder PRD v0.1.** Work section by section through the existing DISCUSSION DRAFT, validate or revise each section, mark approved sections. Particularly: rewrite Phase 1 per DEC-297 (client-led intake), revise the "two-layer mental model" content per DEC-296 (three-category conceptual model). Output: PRD v0.2 with sections moved out of DISCUSSION DRAFT into approved-but-iteratively-extensible status.
- **Direction B — Resolve cross-engagement reference store architecture (PI-062).** Architectural decision on where shared content (Skills, Patterns, Inventories, glossary terms) lives in V2 given V2's engagement-partitioned storage model. Unblocks PI-061, PI-067, and large parts of PI-063..065. Output: an architectural decision (DEC), possibly a Claude Code prompt for implementation.
- **Direction C — Design the Session/Conversation entity redesign (PI-073).** Work through the four open design questions in PI-073's description, produce an architectural decision, then a Claude Code prompt for the V2 schema migration. Output: DEC + implementation prompt.
- **Direction D — Design the engagement-scoped client-input storage (PI-071).** Decide how V2 stores files, URLs, social media handles, credentials, transcripts, recordings, email threads, verbally-captured context. Output: DEC, possibly an implementation prompt.
- **Direction E — Define the Engagement Level Setup process (PI-072).** Author the one-time engagement initialization process (client identification, stakeholder roster, communication arrangement) and the V2 records that hold its outputs. Output: a section of the Master CRMBuilder PRD plus any V2 schema additions needed.
- **Direction F — Continue Master CRMBuilder PRD drafting (PI-069).** Author Phases 2-13 placeholders into substantive drafts, iteratively. Phases 2 and 3 are the next concrete targets after Phase 1's rewrite.
- **Direction G — Specifications/ directory README/manifest (PI-068).** Small but useful: create the entry-point document for `specifications/` naming the canonical L1/L2/L3 documents, supersession history, and how to read the document set.
- **Direction H — Open-ended.** Pick up wherever the prior session's threads suggest, including expanding the glossary with terms that come up in discussion.

Doug picks a direction at the start of the session. The new conversation does not need to commit to one direction up front — multiple may be worked sequentially or partially.

---

## Pre-flight (every new session)

Before authoring any governance content (decisions, planning items, references, sessions, conversations) the new conversation MUST capture current identifier heads from the live V2 state. This is required by DEC-300 (sandbox close-out identifier-capture protocol). Run:

```bash
curl -sf http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(s['identifier'] for s in d); print('SES head:', ids[-1])"
curl -sf http://127.0.0.1:8765/conversations | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(c['conversation_identifier'] for c in d); print('CONV head:', ids[-1])"
curl -sf http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(dc['identifier'] for dc in d); print('DEC head:', ids[-1])"
curl -sf http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(p['identifier'] for p in d); print('PI head:', ids[-1])"
curl -sf http://127.0.0.1:8765/work-tickets | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(w['work_ticket_identifier'] for w in d); print('WT head:', ids[-1])"
```

Paste the output back at the start of the conversation. The sandbox uses these as the basis for the close-out's identifier assignments. Re-check before any mid-conversation amendment that touches identifier slots.

Also at session start:

1. Pull latest on the local clone: `cd ~/Dropbox/Projects/crmbuilder && git pull --ff-only origin main`
2. Confirm which CLAUDE.md the sandbox should read (typically the repo-level `crmbuilder/CLAUDE.md`).
3. The sandbox proposes a working direction (A-H above or another) and waits for Doug's selection before proceeding.

---

## Working conventions (carried forward from SES-089)

- **One thing at a time.** Doug enforces this strictly. Don't stack decisions, options, or amendments in one response. Present one focused thing, wait for confirmation, proceed.
- **Don't race ahead.** Wait for explicit approval before authoring substantive documents. If the sandbox starts authoring v0.X of a document, mark it DISCUSSION DRAFT and surface for review rather than committing to it.
- **Sandbox commits AND pushes together** in this Claude.ai-sandbox-on-claude.ai context (the container is ephemeral; a held commit is a lost commit). Local Claude Code commits do not push; Doug pushes after review.
- **Three-category conceptual model** for classifying everything: Process Management Tools/Data, Deliverables, Process Support Knowledge/Tools (DEC-296).
- **End-to-end Master CRMBuilder PRD scope** — anything from initial requirements capture through deployed functional application is in scope (DEC-294).
- **Glossary expansion is welcome.** When new specialized terms come up in discussion (e.g., Domain, Persona, Process, Sub-Domain, Workstream), add them to `specifications/glossary.md` with the standard entry format.
- **Close-out at session end** if the conversation produces governance records, per the close-out instructions in the project default operating mode preamble.

---

## Seed prompt to paste into the new Claude.ai session

```
Project default operating mode: ARCHITECTURE.

I want to continue the V2 architecture review from SES-089. Read the
SES-089 close-out kickoff at specifications/ ... no, actually read:

  PRDs/product/crmbuilder-v2/master-crmbuilder-prd-continuation-kickoff.md

It covers what landed in SES-089, the thirteen open planning items
(PI-061..PI-073) and ten decisions (DEC-291..DEC-300), the candidate
directions for this session, the required pre-flight identifier-head
capture (per DEC-300), and the carried-forward working conventions.

Confirm you've read it, then ask me for the live identifier heads (the
curl commands are in the kickoff). After I provide them, propose a
working direction (A-H from the kickoff, or a different direction if
you see one I missed). I'll select and we proceed one thing at a time.
```

Doug pastes that block into a new Claude.ai conversation. The new sandbox reads this kickoff, asks for heads, proposes a direction, waits for selection, and begins.
