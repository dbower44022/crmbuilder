# Claude Code Prompt — Glossary: Organizing-Model Terms

**Last Updated:** 06-13-26 15:25
**Operating mode:** DETAIL (execution — Claude Code)
**Surface:** Claude Code (live API reachable; real-time POST per DEC-383)
**Target engagement (request context):** CRMBUILDER
**Term scope:** **system** (`engagement_id` NULL — visible to every engagement)

---

## Purpose

Write four methodology definitions into the V2 Glossary (the `term` entity,
`TERM-NNN`, PI-061) as **system-scoped** terms: **Domain**, **Cross-Domain
Service**, **Topic**, and **Requirement**. These are universal methodology
concepts that apply to every engagement, not CRMBUILDER-specific business
vocabulary, so they are created at system scope.

**Net effect:** four new `term` records at system scope, status `active`,
version `1`, each cross-linked via `related_terms`. Nothing is committed to git —
glossary definitions live only in the database (per the `term` spec). The
session reports the assigned `TERM-NNN` identifiers.

**Out of scope:** the governance *decisions* behind these definitions (the
domain + cross-domain coverage partition; topic as the orthogonal cross-cutting
lens; service-as-home vs topic-as-lens) are recorded separately in the
originating Claude.ai conversation's close-out, not here.

---

## Pre-flight

1. Confirm the governing CLAUDE.md is the repo-root `crmbuilder/CLAUDE.md`; read
   the v2 governance-recording note (real-time POST per DEC-383) and the
   `{data, meta, errors}` envelope rule.
2. Confirm the live API is up: `curl -s http://127.0.0.1:8765/health` (start with
   `crmbuilder-v2-api &` if needed).
3. **Verify the `term` schema and the system-scope mechanism before posting** —
   do not assume the request shape:
   - read `crmbuilder-v2/src/crmbuilder_v2/access/repositories/terms.py`
     (fields: `name`, `definition`, `usage_scope`, `examples`,
     `distinguishing_notes`, `related_terms`, `version`, `status`);
   - read `crmbuilder-v2/src/crmbuilder_v2/access/repositories/_registry.py`
     (`resolve_scope`) and the `/terms` POST handler in the API router to
     determine exactly how a **system-scoped** term (`engagement_id` NULL) is
     specified on the wire (e.g. a `scope: "system"` body field or equivalent).
4. Capture the current `term` head: `GET /terms` (unwrap `.data`), note the
   highest `TERM-NNN` so the head advance can be verified afterward.
5. **Idempotency:** for each of the four names below, `GET /terms` and skip
   creation if a system-scoped term with that exact `name` already exists. A
   re-run must not create duplicates.

---

## Records to create (all: scope = system, status = active, version = 1)

### 1. Domain
- **definition:** A top-level functional area of the system — one of the big
  questions the organization's mission forces it to answer. A domain owns the
  processes and entities specific to that area and is a *home* where
  requirements live. Reviewing the system domain by domain is how area coverage
  is verified ("is every functional area accounted for?").
- **usage_scope:** Methodology / requirements organization (applies to every
  engagement).
- **examples:** In a mentoring nonprofit: Mentor, Mentor Recruiting, Client
  Recruiting, Follow-Up.
- **distinguishing_notes:** A domain is a *home* (functionality lives in it),
  not a review lens. Every requirement belongs to at least one domain or
  cross-domain service. A domain partitions *what area* and answers coverage
  completeness. Contrast Topic, which owns no functionality.
- **related_terms:** Cross-Domain Service, Topic, Requirement, Process

### 2. Cross-Domain Service
- **definition:** Shared functionality that spans more than one domain rather
  than belonging to a single one — e.g. notifications, calendar, surveys. A
  cross-domain service is a peer to domains in the coverage partition: a *home*
  where requirements live, and it is built and deployed as part of the system.
- **usage_scope:** Methodology / requirements organization.
- **examples:** A notification/email service, calendar, or surveys used across
  multiple domains.
- **distinguishing_notes:** A cross-domain service is functionality that gets
  *built* — remove it and the deployed system loses a capability. Like a domain
  it is a *home* in the coverage partition; unlike a domain it has no single
  functional-area owner. Unlike a Topic, it is built and deployed.
- **related_terms:** Domain, Topic, Requirement, Process

### 3. Topic
- **definition:** A hierarchical, domain-independent grouping used to gather
  requirements by theme for review. A topic owns no functionality and is never
  built or deployed; it exists only in the requirements layer as a cross-cutting
  lens, letting a reviewer verify that a theme is complete everywhere it should
  appear across domains and cross-domain services.
- **usage_scope:** Methodology / requirements organization.
- **examples:** "Notifications", "Data Privacy", "Audit Trail", "What a board
  member can see" — each gathering requirements scattered across many domains
  and services.
- **distinguishing_notes:** Orthogonal to the domain/cross-domain partition — a
  requirement lives in a domain or cross-domain service (its home) and may
  *also* be tagged to one or more topics (a review lens). Test that separates a
  topic from a Cross-Domain Service: remove it; if the deployed system is
  unchanged it is a topic, if the system loses functionality it is a service.
  Topics answer cross-cutting completeness, which domain-by-domain review cannot.
- **related_terms:** Domain, Cross-Domain Service, Requirement

### 4. Requirement
- **definition:** A discrete, testable statement of what the system must do.
  Requirements are the functional units the organizing model arranges: each
  lives in one or more domains or cross-domain services (its home, for coverage)
  and may be grouped under one or more topics (for cross-cutting review), and
  each is the thing a test verifies.
- **usage_scope:** Methodology / requirements organization.
- **examples:** "Capture mentor availability slots"; "Send a confirmation email
  when a mentor application is approved."
- **distinguishing_notes:** A requirement is reached two independent ways —
  through its domain/cross-domain home (coverage view) and through any topic it
  belongs to (thematic view). It is the unit whose completeness the Master PRD
  review verifies.
- **related_terms:** Domain, Cross-Domain Service, Topic

---

## Apply

For each record above, POST to `/terms` at **system** scope (using the exact
representation confirmed in pre-flight step 3), via real-time direct POST per
DEC-383. Skip any whose `name` already exists at system scope.

## Post-apply verification

1. `GET /terms?scope=system` (unwrap `.data`) and confirm all four names are
   present with the expected `definition` / `distinguishing_notes`.
2. Confirm the `term` head advanced by the number of records actually created.
3. Spot-check one record (e.g. Topic) end-to-end: `GET /terms/TERM-NNN` returns
   the full field set including `related_terms`.

## Done

Reply with: term head before and after, the four (or fewer, if some pre-existed)
assigned `TERM-NNN` identifiers mapped to their names, and confirmation that no
git changes were produced.

---

## Guardrails

- Verify the schema and the system-scope wire representation against the actual
  files before posting — never from memory.
- Idempotent: check-by-name first; a re-run creates nothing new.
- Real-time POST per DEC-383 — no close-out payload, no `apply_close_out.py`, no
  deposit-event log for these content records.
- These are **system**-scoped terms (`engagement_id` NULL). Do not create them
  scoped to CRMBUILDER or any other single engagement.
