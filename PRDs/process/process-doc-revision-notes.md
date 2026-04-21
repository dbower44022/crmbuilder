# CRM Builder — Document Production Process — Revision Notes

**Purpose:** A running list of issues discovered in
`CRM-Builder-Document-Production-Process.docx` during guide authoring
or pilot execution that should be addressed in the next `.docx`
revision pass. Entries are not patches — the `.docx` remains the
authority until it is actually revised. This file is the todo list
for whoever opens the Word document next.

**Owner:** Administrator (the process doc is a Word document, not a
Claude-editable artifact).

**How entries are resolved:** The administrator opens the Word
document, applies the revision, bumps the .docx version, and removes
the corresponding entry from this file (or marks it "resolved in
v{N}" with the revision date).

---

## Open

### R-001 — Section 3.4 Context Passing vs. Section 3.5 Rule 5.1: Entity PRD timing

**Sections in conflict:**
- Section 3.4 (Phase 4 — Domain Overview Context Passing): "Each Domain Overview conversation receives the Master PRD, the Entity Inventory, and the **Entity PRDs for every entity whose Entity Inventory data lists it as participating in this domain**."
- Section 3.5 Rule 5.1 (Entity Definition Timing): "Full Entity PRDs — including complete field lists, relationships, and business rules — are produced only in Phase 5, **after the Phase 4 process documents that use the entities have been drafted**. Process documents may reference entity names and obvious fields from the reconciled Entity Inventory without waiting for the full PRD."

**Nature of the conflict:** Section 3.4 states Entity PRDs as an input to Phase 4a Domain Overview. Section 3.5 Rule 5.1 says Entity PRDs are produced in Phase 5, after Phase 4. A strict reading of Section 3.4 requires Entity PRDs to exist before Phase 4a; Rule 5.1 makes that impossible in the normal phase sequence.

**Observed pilot practice:** The CBM pilot (MN, MR, CR domains) ran Domain Overview first and produced Entity PRDs retroactively. This matches Rule 5.1, not the Section 3.4 Context Passing wording.

**Current resolution in the guides:**
- `guide-domain-overview.md` v1.1 treats Entity PRDs as optional inputs. When an Entity PRD exists, the Data Reference links to it. When it does not, the Data Reference cites the Entity Inventory row and annotates "Entity PRD pending Phase 5".
- `interview-entity-prd.md` v1.1 explicitly reframes the ordering: "what earlier methodology called 'retroactive' Entity PRDs is now the normal order per Rule 5.1".
- `authoring-standards.md` v1.1 Section 1.1 gives authors a general resolution protocol.

**Recommended `.docx` revision:**
- Rewrite Section 3.4 Context Passing to match Rule 5.1: "Each Domain Overview conversation receives the Master PRD, the Entity Inventory, and any Entity PRDs for participating entities that have already been produced (typically for cross-domain entities defined in an earlier domain's Phase 5 work). Entities without a complete Entity PRD are referenced by their Entity Inventory row; the Data Reference annotates those entities as pending Phase 5."
- Consider adding a sentence to Rule 5.1 that explicitly calls out the "retroactive" reframing: "This ordering — Phase 4 first, Phase 5 after — is the normal sequence; earlier drafts of the methodology described Phase 5 Entity PRDs as 'retroactive' when produced after Phase 4, which is now simply the default order."

**Discovered:** 2026-04-20 during `guide-domain-overview.md` v1.0 authoring (blocked CBM Funding Domain Overview).
**Current status:** Guides operate per Rule 5.1 interpretation; `.docx` still has the contradiction.

---

## Resolved

*(none yet)*

---

## Template for new entries

```markdown
### R-NNN — {one-line summary}

**Sections in conflict:**
- Section {X}: "{verbatim quote or paraphrase with section reference}"
- Section {Y}: "{verbatim quote or paraphrase with section reference}"

**Nature of the conflict:** {what the two sections contradict on}

**Observed pilot practice:** {which interpretation pilots have actually executed, or "no pilot has reached this phase yet"}

**Current resolution in the guides:** {which guides adopted which interpretation, with file names and versions}

**Recommended `.docx` revision:** {concrete language or structural change}

**Discovered:** {YYYY-MM-DD} during {what — guide authoring, pilot execution, review}.
**Current status:** {guides operate per which interpretation; `.docx` still has the contradiction / already addressed}
```
