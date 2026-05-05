# Update Prompt: Domain Reconciliation Guide v1.5 → v1.6 — Add Entity Relationships Sub-Section to Section 4

## Context

I'm working on the CBM CRM implementation methodology. A verification pass against the Mentoring (MN) Domain PRD on 05-05-26 surfaced that Domain PRD v1.0 had no consolidated Relationships sub-section in Section 4 — relationships only appeared scattered as relationship-typed *fields* within per-entity field tables. This is a structural gap relative to the Entity PRDs (each of which has a dedicated Section 4 Relationships table).

CBM-Domain-PRD-Mentoring v1.1 (Session 4 of the verification pass remediation workpacket, committed as `60f009b` in `dbower44022/ClevelandBusinessMentoring`) introduced a new structural convention: open Section 4 of the Domain PRD with a consolidated "Entity Relationships" sub-section, structurally parallel to the per-entity Relationships sub-sections in Engagement, Session, Account, and Contact Entity PRDs.

This prompt updates the **Phase 7 Domain Reconciliation Guide** to specify Entity Relationships as a required Section 4 sub-section going forward, so that every future Domain PRD authored under this methodology includes the new structural element.

This is a methodology-guide update only. Existing Domain PRDs (MR v1.1, CR v1.2 Approved, FU v1.0 Approved) are propagated separately via a different prompt (`UPDATE-PROMPT-Domain-PRD-Entity-Relationships-Propagation.md` in the CBM repo).

Before doing any work, please:
1. Read the CLAUDE.md in this repo (`dbower44022/crmbuilder`)
2. Read `PRDs/process/interviews/guide-domain-reconciliation.md` (current v1.5) end-to-end so the addition fits the existing structure and tone

## The Change

Update `PRDs/process/interviews/guide-domain-reconciliation.md` from v1.5 to v1.6, adding a new Entity Relationships sub-section requirement at the start of Section 4 of the Domain PRD that the guide produces.

## Specific Edits Required

### File: `PRDs/process/interviews/guide-domain-reconciliation.md`

#### 1. Header

- Version: `1.5` → `1.6`
- Last Updated: current session timestamp in `MM-DD-YY HH:MM` format

#### 2. Section "What the Domain PRD Must Contain" (currently around line 39)

Find the bullet that describes Section 4. It currently reads something like "Section 4: Data Reference — consolidated field tables organized by entity."

Update that bullet to specify the new internal structure:

> Section 4: Data Reference — opens with a consolidated **Entity Relationships** sub-section enumerating every domain-relevant relationship in a single table; followed by per-entity field tables organized by entity. The relationships sub-section provides structural context that the field tables operate within.

#### 3. Section 4 specification (currently around line 444 — the "### Section 4: Data Reference" sub-section)

Insert a new sub-section between the existing introduction ("This is the unique contribution of the Domain PRD…") and the per-entity field-table specification. The new sub-section specifies the Entity Relationships table that must open Section 4.

**Suggested new sub-section text** (adapt to match the existing voice and structure of the guide; the AI should not copy this verbatim if a more natural integration is possible):

```markdown
**Section 4 begins with a consolidated Entity Relationships sub-section.**

Before the per-entity field tables, Section 4 opens with a single
consolidated table that enumerates every domain-relevant relationship.
This is structurally parallel to the per-entity Relationships
sub-sections in the Entity PRDs and provides the structural context
within which the field tables operate.

**Required columns:**

| Relationship | Related Entity | Link Type | YAML Location | Domain(s) |

- **Relationship.** Human-readable name; for relationships with a
  semantic role (e.g., "Engagement → Contact (Assigned Mentor)"),
  use the parenthetical to disambiguate.
- **Related Entity.** The other endpoint of the relationship.
- **Link Type.** `oneToMany`, `manyToOne`, `manyToMany`, or
  `manyToOne (self-ref)`; reflect the YAML relationship type.
- **YAML Location.** The YAML file and link name where the
  relationship is declared, e.g., `engagementClientOrganization in
  MN-Engagement.yaml`. For native relationships provided by the
  underlying platform, write `None — native to the platform`. For
  native parent links via the Event entity type, write `None —
  native parent link via Event entity type`.
- **Domain(s).** Comma-separated list of domains that own or
  consume the relationship. For cross-domain-contributed
  relationships (e.g., Referring Partner contributed by CR but
  declared on a Mentoring entity), use the form `CR (touched by
  MN)` to capture both ownership and consumption.

**Required content scope:**

The table must include:
1. Every relationship declared in the YAML files of entities
   produced by this domain (read from MN-*.yaml, MR-*.yaml,
   CR-*.yaml, or FU-*.yaml as appropriate).
2. Every native platform relationship used by the domain (e.g.,
   Account ↔ Contact in any domain that uses both entities).
3. Every native parent link relationship implicit in Event-type
   custom entities (e.g., Engagement → Session via Session's
   parent link in the Mentoring domain).
4. Cross-domain-contributed relationships that touch domain
   entities (declared in another domain's YAML but referenced by
   this domain's processes).

The table must filter out:
- Relationships owned by other domains that touch entities not
  used by this domain.
- Inverse-side rows (each relationship is listed once from its
  declaring side, never twice).

**Required explanatory notes:**

After the table, include short explanatory notes covering:
1. Native platform relationships and any post-deployment
   customizations (e.g., the `primaryContact` boolean on the
   Account-Contact middle table, captured in MANUAL-CONFIG).
2. Native parent links and how they are implemented (e.g.,
   `Engagement → Session` is implemented via Session's native
   `parent` link as type Event, not via a custom YAML relationship
   declaration).
3. Cross-domain-contributed relationships and which domain owns
   the declaration vs. which domain consumes it (e.g., Referring
   Partner is declared on the Mentoring-domain Engagement entity
   but is part of the CR-PARTNER attribution model).

**Source for the table:**

Compile the table by cross-referencing Section 4 (Relationships) of
each Entity PRD relevant to the domain. Filter to domain-relevant
relationships per the scope rules above. Where the YAML files exist
(post-Phase 9), cite the YAML location verbatim. Where YAML files
do not yet exist (pre-Phase 9 reconciliation), write the YAML
location as `to be declared in {expected file}.yaml` so the
forward-reference is explicit.

**Precedent:**

This convention was introduced in CBM-Domain-PRD-Mentoring v1.1
(05-05-26, dbower44022/ClevelandBusinessMentoring commit `60f009b`),
which produced a 12-row consolidated Entity Relationships table for
the MN domain plus three explanatory notes. Future Domain PRDs
follow this pattern.
```

#### 4. Changelog section (existing section in the guide)

Add a new v1.6 entry summarizing the change, citing the MN Domain PRD v1.1 (05-05-26) as the precedent that introduced the convention. Reference the `dbower44022/ClevelandBusinessMentoring` commit `60f009b` and the verification pass on 05-05-26 that surfaced the gap.

#### 5. Cross-references to verify

After making the edits, search the rest of the guide for any references to "Section 4" or "Data Reference" that may need wording updates to reflect the new sub-section. In particular:

- The "How to Use This Guide" section (currently around line 11)
- The "Step 2 — Domain PRD Assembly" section overview (currently around line 343)
- The "Step 3 — Review" section (currently around line 562)

Do not invent new content or add scope beyond the Entity Relationships sub-section. Only update wording where existing text references Section 4's structure in a way that the new sub-section makes outdated.

## What NOT to Change

- Do not change the existing Section 4 per-entity field-table specification — it is preserved unchanged, just preceded by the new Entity Relationships sub-section.
- Do not change any other section of the guide (Sections 1, 2, 3, 5, 6, 7, the Critical Rules section, the Step-by-step assembly instructions, etc.).
- Do not modify any other guide file (`guide-entity-definition.md`, `interview-process-definition.md`, `interview-master-prd.md`, `guide-carry-forward-updates.md`).
- Do not modify the Document Production Process docx file.
- Do not modify any Domain PRD — propagation across MR/CR/FU Domain PRDs is a separate prompt.

## Documents to Upload

Upload the following with this prompt:
1. `PRDs/process/interviews/guide-domain-reconciliation.md` (current v1.5)

Optionally for reference (but not required, since the precedent is described in this prompt):
2. The current MN Domain PRD v1.1 from the CBM repo at `PRDs/MN/CBM-Domain-PRD-Mentoring.docx` (commit `60f009b` in `dbower44022/ClevelandBusinessMentoring`) — this is the precedent document that introduced the convention.

## Output

Produce an updated `guide-domain-reconciliation.md` v1.6 and commit it to the `dbower44022/crmbuilder` repo, replacing the existing v1.5 file. Use a single commit titled `methodology: domain reconciliation guide v1.6 — add Entity Relationships sub-section requirement` and write a brief commit body noting that the v1.6 update specifies Entity Relationships as a required Section 4 sub-section, sourced by the MN Domain PRD v1.1 precedent on 05-05-26.

After the work is committed, state that the methodology-guide update is complete and that the next step is propagation across the existing MR, CR, and FU Domain PRDs (per the companion prompt `UPDATE-PROMPT-Domain-PRD-Entity-Relationships-Propagation.md` in the CBM repo). Provide a brief summary of what changed for review.
