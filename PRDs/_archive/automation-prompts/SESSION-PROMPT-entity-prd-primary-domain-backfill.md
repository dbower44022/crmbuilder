# Session Prompt — Entity PRD Primary Domain Backfill + Multi-Entity Verification

**Repo:** `dbower44022/ClevelandBusinessMentoring`
**Date:** 04-12-26
**Prerequisite:** Read `CLAUDE.md` in both `crmbuilder` and `ClevelandBusinessMentoring` repos.

---

## Context

The Entity PRD Path B adapter (completed 04-12-26) introduced an
**Option B primary domain resolution** strategy:

- If the Entity Overview table contains a `Primary Domain` row → use it
  directly.
- If absent → fall back to the first entry in `Contributing Domains`
  and emit a `primary_domain_fallback` soft warning.

The adapter is proven on Contact Entity PRD v1.3 (the primary design
reference). However, two follow-up items remain:

1. **None of the 5 existing Entity PRDs have a `Primary Domain` row.**
   Every import currently triggers the fallback path and emits a
   warning. Adding the row to each document eliminates the warnings and
   makes the domain assignment explicit rather than positional.

2. **Only Contact has been tested.** The other 4 Entity PRDs
   (Account, Engagement, Session, Dues) may have structural differences
   that break the adapter. They need to be run through the adapter and
   any failures addressed.

This session addresses both items.

---

## Part 1: Add `Primary Domain` Row to Entity PRDs

### What to Add

In each Entity PRD, the Entity Overview table (the second two-column
key/value table, after the header table) needs a new row:

```
Primary Domain | <Domain Name> (<CODE>)
```

inserted **immediately before** the `Contributing Domains` row.

### Documents to Update

| Entity PRD | File | Current Version | Owning Domain | Primary Domain Value |
|---|---|---|---|---|
| Contact | `PRDs/entities/Contact-Entity-PRD.docx` | v1.3 | MN (from Entity Inventory) | `Mentoring (MN)` |
| Account | `PRDs/entities/Account-Entity-PRD.docx` | v1.3 | MN (from Entity Inventory) | `Mentoring (MN)` |
| Engagement | `PRDs/entities/Engagement-Entity-PRD.docx` | v1.0 | MN (from Entity Inventory) | `Mentoring (MN)` |
| Session | `PRDs/entities/Session-Entity-PRD.docx` | v1.0 | MN (from Entity Inventory) | `Mentoring (MN)` |
| Dues | `PRDs/entities/Dues-Entity-PRD.docx` | v1.0 | MN (from Entity Inventory) | `Mentoring (MN)` |

**Source of truth for Owning Domain:** The Entity Inventory's detail
cards (Tables 2–9 of `CBM-Entity-Inventory.docx` v1.4) each have an
`Owning Domain` row. For every MN-domain entity, this says
`Mentoring (MN)`. Verify this against the Entity Inventory before
inserting.

### Version Bumps

Each document gets a minor version bump:
- Contact: 1.3 → 1.4
- Account: 1.3 → 1.4
- Engagement: 1.0 → 1.1
- Session: 1.0 → 1.1
- Dues: 1.0 → 1.1

Update the `Version` row in the header table AND the `Last Updated`
row with the current date/time in `MM-DD-YY HH:MM` format.

### Steps

For each document:
1. Open the .docx
2. Find the Entity Overview table (second 2-col key/value table)
3. Confirm `Contributing Domains` row exists
4. Insert `Primary Domain | Mentoring (MN)` row immediately before
   `Contributing Domains`
5. Update header table `Version` and `Last Updated`
6. Save
7. Verify with pandoc or by re-opening

Work through one document at a time. Confirm each before moving to the
next.

---

## Part 2: Run Entity PRD Adapter Against All 5 Entities

After Part 1 is complete (or in parallel if desired), verify the
Entity PRD Path B adapter against all 5 documents.

### Verification Procedure

For each Entity PRD:

1. Run the adapter:
   ```python
   from automation.importer.parsers.entity_prd_docx import parse
   
   work_item = {
       "id": 1,
       "item_type": "entity_prd",
       "entity_id": <entity_id from cbm-client.db>
   }
   envelope_json, report = parse("<path_to_docx>", work_item)
   ```

2. Check the ParseReport:
   - No hard errors (parse succeeded)
   - No `primary_domain_fallback` warning (since we added the row in
     Part 1)
   - Note any other warnings — they may indicate format variations

3. Inspect the envelope JSON:
   - `entity_metadata.primary_domain_code` is `"MN"` (explicit, not
     fallback)
   - `native_fields` count is reasonable (0 for custom entities)
   - `custom_fields` count is reasonable
   - `relationships` count is reasonable
   - `open_issues` and `decisions` are populated

4. If the parse fails or produces unexpected results, document the
   format variation and decide whether to:
   - Fix the adapter (if the variation is legitimate and should be
     supported)
   - Fix the document (if the variation is a formatting error)

### Expected Counts (approximate, verify against actual documents)

| Entity | Native Fields | Custom Fields | Relationships |
|---|---|---|---|
| Contact | 16 | ~50 | ~15 |
| Account | ~19 | ~21 | ~10 |
| Engagement | 0 | ~19 | ~8 |
| Session | ~10 | ~8 | ~5 |
| Dues | 0 | ~8 | ~3 |

### Document Locations

All in `~/Dropbox/Projects/ClevelandBusinessMentors/PRDs/entities/`:
- `Contact-Entity-PRD.docx`
- `Account-Entity-PRD.docx`
- `Engagement-Entity-PRD.docx`
- `Session-Entity-PRD.docx`
- `Dues-Entity-PRD.docx`

---

## Part 3: Update Entity Inventory Consistency Check

After both parts are done, spot-check consistency:

- For each entity, confirm that the `Primary Domain` value in the
  Entity PRD matches the `Owning Domain` value in the Entity
  Inventory's detail card.
- For each entity, confirm that the `Contributing Domains` list in the
  Entity PRD is a superset of the domains indicated in the Entity
  Inventory's Cross-Domain Matrix (Table 10).

Report any inconsistencies. Do not fix them in this session — flag them
as open items for a follow-up.

---

## Part 4: Update CBM CLAUDE.md

At the end of the session, update `CLAUDE.md` in the CBM repo to
reflect:
- The version bumps for all 5 Entity PRDs
- That `Primary Domain` rows have been added to all Entity PRDs
- Any format variations discovered in Part 2 and their resolution
- Any consistency issues found in Part 3

---

## Deliverables Summary

1. 5 Entity PRDs updated with `Primary Domain` row + version bumps
2. Adapter verification results for all 5 entities (pass/fail + counts)
3. Consistency check results (Entity Inventory vs Entity PRDs)
4. Updated `CLAUDE.md`
5. List of any format variations that require adapter fixes (input for
   a crmbuilder-side follow-up iteration prompt)
