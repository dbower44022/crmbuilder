# CRM Builder — Entity Definition Interview Guide

**Version:** 2.0  
**Last Updated:** March 2026  
**Changelog:** See end of document.

---

## Overview

Entity definition is Phase 2 of the CRM requirements process. It
converts the Entity Map from Phase 1 into complete specifications —
PRD sections, YAML program files, and task lists — for each entity.

## Three-Session Structure

Each entity variant is defined across three focused sessions:

```
Session A — Data Definition (30–45 min)
  What information needs to be stored?
  Fields, types, values, layout, relationships.
  Guide: entity-interview-data.md

Session B — Process Definition (30–45 min)
  How does this entity behave over its lifetime?
  Creation, editing, lifecycle transitions, termination.
  Often reveals additional fields not found in Session A.
  Guide: entity-interview-process.md

Session C — Synthesis (15–30 min)
  AI produces outputs from Sessions A and B combined.
  User reviews and approves.
  Guide: entity-interview-synthesis.md
```

## Entity Variants

**One variant per session.** If an entity covers multiple distinct
types, run separate sessions for each variant. Never mix variants.

**Examples:**
- Contact: Mentor → separate sessions from Contact: Client Contact
- Account: Client Business → separate sessions from Account: Partner

This prevents confusion when the same question means different things
for different types. "What status values does a Contact have?" has
completely different answers for a Mentor vs. a Client Contact.

## Session Outputs

| Session | Output |
|---|---|
| A — Data | Field inventory + layout proposal |
| B — Process | Process definitions + additional fields |
| C — Synthesis | PRD section + YAML file + Task list |

For multi-variant entities, Session C produces one YAML per variant,
then merges them into a single entity file with Dynamic Logic.

## Recommended Order (CBM)

| # | Entity | Variant | Notes |
|---|---|---|---|
| 1 | Contact | Mentor | Foundation — most complex |
| 2 | Contact | Client Contact | |
| 3 | Contact | Partner Contact | |
| 4 | Account | Client Business | |
| 5 | Account | Partner Organization | |
| 6 | Engagement | — | Depends on Contact + Account |
| 7 | Session | — | Depends on Engagement |
| 8 | NPS Survey Response | — | Depends on Engagement |
| 9 | Chapter | — | |
| 10 | Workshop | — | |
| 11 | Workshop Attendance | — | Junction entity |
| 12 | Partner Activity | — | |
| 13 | Dues | — | |

## Session Length Guidelines

- Keep each session to 45 minutes maximum
- Stop at 45 minutes regardless of completion
- Schedule a follow-up rather than pushing through fatigue
- Tired users give incomplete answers

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 2.0 | March 2026 | Restructured into three separate guides (data, process, synthesis). Added entity variant concept. Added session length guidelines. |
| 1.0 | March 2026 | Initial release |
