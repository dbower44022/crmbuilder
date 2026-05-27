# PI-085 Domain Overview Drafting — Kickoff

**Document type:** Kickoff prompt (session seed for executing PI-085)
**Repository:** `crmbuilder`
**Path:** `PRDs/product/crmbuilder-v2/pi-085-domain-overview-drafting-kickoff.md`
**Last Updated:** 05-26-26
**Operating mode:** ARCHITECTURE
**Estimated duration:** One substantive session; produces v0.1 DISCUSSION DRAFT of the Domain Overview, possibly seeds the kickoff for PI-086 (Personas)
**Engagement:** CRMBUILDER
**Predecessor sessions:** SES-089 (architecture review), SES-092 (governance recording rules required, DEC-310 + PI-084), SES-093 (dogfood reframe, DEC-311 + PI-085..088 superseding PI-084)

---

## What this session does

Execute **PI-085** — define the CRMBuilder Domain that owns governance recording, producing the Domain Overview document.

This is the first concrete dogfood of the CRMBuilder methodology against CRMBuilder itself (per DEC-295). It supersedes PI-084's original "standalone rules document" approach (per DEC-311 dogfood reframe). The Domain being defined will own three downstream Processes when fully built out:
- PI-087 — Session/Conversation governance Process (the first concrete Process, contains the rules content originally planned for PI-084)
- PI-088 — Standard Process PRD Definition Process (meta, formalized after observing PI-087)
- Potentially more as the Domain develops

The Personas referenced by this Domain (PI-086) are a separate PI — Personas are first-class entities, not contained in the Domain.

---

## Pre-flight (per DEC-300)

Before authoring any governance content (decisions, planning items, references), capture current identifier heads from the live V2 API. Run:

```bash
curl -sf http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(s['identifier'] for s in d); print('SES head:', ids[-1])"
curl -sf http://127.0.0.1:8765/conversations | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(c['conversation_identifier'] for c in d); print('CONV head:', ids[-1])"
curl -sf http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(dc['identifier'] for dc in d); print('DEC head:', ids[-1])"
curl -sf http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(p['identifier'] for p in d); print('PI head:', ids[-1])"
curl -sf http://127.0.0.1:8765/work-tickets | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(w['work_ticket_identifier'] for w in d); print('WT head:', ids[-1])"
```

Paste the output back to the sandbox at session start. Re-check before any mid-conversation amendment that touches identifier slots.

Also at session start:
1. Pull latest on the local clone: `cd ~/Dropbox/Projects/crmbuilder && git pull --ff-only origin main`
2. Confirm which CLAUDE.md the sandbox should read (typically `crmbuilder/CLAUDE.md`).
3. Read PI-085's description from V2 directly:
   ```bash
   curl -sf http://127.0.0.1:8765/planning-items/PI-085 | python3 -m json.tool
   ```
4. Read the related DECs for context (Doug or sandbox can fetch):
   - DEC-310 (rules required) — `curl -sf http://127.0.0.1:8765/decisions/DEC-310`
   - DEC-311 (dogfood reframe) — `curl -sf http://127.0.0.1:8765/decisions/DEC-311`
   - DEC-300 (identifier-capture protocol) — `curl -sf http://127.0.0.1:8765/decisions/DEC-300`
   - DEC-296 (three-category conceptual model) — `curl -sf http://127.0.0.1:8765/decisions/DEC-296`
   - DEC-295 (CRMBuilder dogfood first, CBM second) — `curl -sf http://127.0.0.1:8765/decisions/DEC-295`

---

## The first substantive question: name the Domain

The Domain doesn't have a name yet. Candidates surfaced in the SES-093 reframe discussion:

- **"Conversation Governance"** — captures the focus on Claude.ai conversations and how their governance gets recorded
- **"Methodology Execution"** — broader; covers all of how CRMBuilder methodology runs against any engagement
- **"Engagement Operations"** — broader still; covers all engagement-side activity
- **"Process Discipline"** — narrower; captures the rules-following aspect

The naming decision is consequential because it determines the Domain's scope and what Processes belong in it. If the Domain is "Conversation Governance," then only conversation/session-related Processes live in it; broader engagement activities go in other Domains. If the Domain is "Methodology Execution," then the Session/Conversation Process is one of many Processes in a larger Domain.

This is exactly the kind of decision the discipline expects: surface it, discuss the options, decide explicitly, author a DEC at moment-of-decision. Do not bury the choice inside the Domain Overview's text.

---

## The Domain Overview document — what it should contain

Following the CBM precedent (CBM has Domain Overviews for MN, MR, CR, FU) and adapting for the dogfood context:

1. **Domain metadata** — identifier (e.g., domain code), name, version, status, last-updated date
2. **The big question** — what question the CRMBuilder mission forces this Domain to answer? (Per methodology vocabulary, a Domain is "one of the big questions the mission forces the organization to answer." For CRMBuilder dogfood: something like "How do we govern the work we do during an engagement?" or "How do we manage what happens during a Claude.ai conversation?" — sharpen during drafting.)
3. **Scope statement** — what's in, what's adjacent, what's explicitly out
4. **Personas involved** — list by identifier, referencing the separate Persona entities (PI-086 produces these). Candidates: Engagement Lead, AI Agent — Sandbox, AI Agent — Claude Code, possibly Reviewer.
5. **Processes within the Domain** — list by code, referencing the separate Process PRDs. PI-087 produces the first one (Session/Conversation governance). PI-088 produces the meta (Process PRD Definition Process — may or may not live in the same Domain).
6. **Entities the Domain operates on** — V2 governance entity types: Session, Conversation, Decision, Planning Item, Reference, Commit, Work Ticket, Close-Out Payload, Deposit Event. Reference each.
7. **Cross-Domain Services involved** — if any. Likely none for this Domain initially; flag for future.
8. **Open questions and known limitations**

Output: `specifications/{domain-code}/domain-overview.md` v0.1 DISCUSSION DRAFT.

---

## What to do AFTER PI-085

Once the Domain Overview v0.1 is drafted and the Domain is named:
- Persona identifiers can be assigned (Engagement Lead → ENGAGE-LEAD or similar; AI Agent — Sandbox → AGENT-SANDBOX or similar; codes TBD).
- The kickoff prompt for PI-086 (Personas) can be authored — it points at the named Personas and proceeds.
- The Session/Conversation Process code can be chosen (e.g., {domain-code}-SESSION-CONV-GOV or similar).

Doug's call whether to proceed into PI-086 in the same session or kick it off as a follow-on session. The discipline says: substantive scope expansion can stay in one session if the work is contiguous; new sessions are appropriate for natural pause points.

---

## Working conventions (carried forward)

- **One thing at a time.** Doug enforces this strictly.
- **Don't race.** Surface options for review, get approval, then proceed.
- **Sandbox commits AND pushes together** in the Claude.ai sandbox context (the container is ephemeral).
- **Moment-of-decision governance authoring** per DEC-310 and DEC-311. Don't batch at session end.
- **Decision-disposition pairing** per the discipline: when a DEC affects an existing artifact, also author the disposition DEC and the revision PI at moment-of-decision.
- **No work captured only in `consequences` or `in_flight_at_end`.** If work needs doing, it's a PI.
- **Re-check identifier heads** before any mid-conversation amendment that touches identifier slots (per DEC-300 strengthened protocol).
- **Close-out at session end** if substantive governance content was produced.

---

## Seed prompt to paste into the new Claude.ai session

```
Project default operating mode: ARCHITECTURE.

I want to execute PI-085 — define the CRMBuilder Domain that owns
governance recording, producing the Domain Overview document. PI-085
supersedes PI-084 per DEC-311 (dogfood reframe authored in SES-093).

Read this kickoff prompt first:

  PRDs/product/crmbuilder-v2/pi-085-domain-overview-drafting-kickoff.md

It covers pre-flight identifier-head capture (per DEC-300), the
Domain naming question, the Domain Overview document structure,
and the working conventions carried forward.

After reading, ask me for the live identifier heads (the curl
commands are in the kickoff). After I provide them, propose
candidate Domain names and your recommendation. I'll select and
we proceed one thing at a time.
```

Doug pastes that block into a new Claude.ai conversation. The new sandbox reads this kickoff, asks for heads, proposes Domain names, waits for selection, and begins drafting.
