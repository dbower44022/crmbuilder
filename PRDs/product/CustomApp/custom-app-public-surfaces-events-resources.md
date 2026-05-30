# Custom Web Application — Public Event Listing and Resources Page

**Version:** 1.0
**Last Updated:** 05-29-26 16:30
**Status:** Draft — implementation note
**Scope:** Implementation-level companion to the CBM Client Recruiting documents. Product names are used here because this is implementation documentation; the source Level 1 / Level 2 PRDs remain product-neutral.

## Overview

The custom web application gains two public, unauthenticated surfaces, both reading from the EspoCRM instance:

1. **Public events list with self-service registration** (event-publishing / discovery change). Realized in the source documents by Event Entity PRD v1.3 (`listedPublicly`, `publishedAt`) and CR-EVENTS-MANAGE v1.2 (publish-to-list and public browse-and-register workflow steps).
2. **Public Resources page** (Resources change). Realized by the new Resource Entity PRD v1.0, the new CR-RESOURCES-MANAGE process document v1.0, and the CR-RESOURCES Sub-Domain Overview v1.0.

Neither surface requires sign-in. Hosting these in the custom application rather than in WordPress was the decision recorded in the CBM CLAUDE.md; the marginal cost is low because hosting infrastructure for the planned Client Intake application already covers this.

## 1. Public events list and registration

**Source query (EspoCRM Event):** show events where `listedPublicly = true` AND `status = Scheduled` AND `dateStart` is in the future. Order soonest-first. An event drops off the list at its `dateStart` (start time), matching EVT-DEC-014. The application does not need `publishedAt` for display; it is a back-office record of first-publication time.

**Registration flow (on form submit)** — mirrors CR-EVENTS-MANAGE steps 6–9 and reuses the existing match-or-create logic:
- Contact match-or-create by email (Universal Contact-Creation Rules).
- Account precedence ladder: website-domain match → otherwise create a new Account when company name or website is provided → otherwise no Account link. (The simplified two-step ladder; exact company-name matching was removed system-wide.)
- Create an `EventRegistration` linking Contact ↔ Event.
- Queue the confirmation email.

**EspoCRM record operations:** the registration sequence creates/updates up to three records — Contact (match or create), Account (optional, via the ladder), and EventRegistration. This is a narrower sequence than the Client Intake application's Account → Contact → Engagement sequence and should reuse the same EspoCRM API client and the same multi-record-creation handling.

**Publishing controls (back office):** `listedPublicly` is set/cleared by the administrator in EspoCRM; the application only reads it. Cancel and Postpone clear `listedPublicly` (the event leaves the list automatically).

## 2. Public Resources page

**Source query (EspoCRM Resource):** show resources where `listedPublicly = true`. Proposed organization: grouped by `category`, then `resourceDate` descending (CR-RESOURCES-MANAGE-REQ-009 / RES-ISS-003 — pending confirmation). Each card shows `name`, `category`, `description`, and a link resolving to `url` or the attached `file`.

**Public-exposure rule:** the application must expose only the Resource's published `url`/`file`. It must never surface `Event.recordingUrl`, which is the raw, back-office source link (CR-RESOURCES-MANAGE-REQ-007). A recording Resource may carry `sourceEvent`; that link is for internal navigation, not public display.

**Recording migration (back office, manual):** out of scope for the application to automate. The administrator follows `Event.recordingUrl` to the raw recording (typically the virtual meeting platform / Zoom), downloads and edits it, and re-hosts the finished copy in a reliable location the Resources page can read (the application's object storage or an equivalent host). The administrator then creates a Resource pointing at that hosted copy and sets `listedPublicly`.

## EspoCRM access summary

- **Read:** Event (list + detail for registration), Resource (list + detail).
- **Create/Update:** Contact, Account (optional), EventRegistration — registration path only. The application does not write Event or Resource publish flags; those are administrator actions in EspoCRM.
- Reuse the existing EspoCRM API client, authentication, and the Contact/Account match-or-create modules shared with the Client Intake application.

## Cross-references

- Event Entity PRD v1.3; CR-EVENTS-MANAGE v1.2; Events Sub-Domain Overview v1.2.
- Resource Entity PRD v1.0; CR-RESOURCES-MANAGE v1.0; CR-RESOURCES Sub-Domain Overview v1.0.
- CR Domain PRD v1.5 and CR Domain Overview v1.5 (CR-RESOURCES registered as the fifth sub-domain).

## Change Log

| Version | Date | Summary |
| --- | --- | --- |
| 1.0 | 05-29-26 16:30 | Initial implementation note for the custom application's two new public surfaces: the events list with self-service registration and the Resources page. Documents the EspoCRM source queries, the registration record sequence, the public-exposure rule for recording links, and the manual recording-migration workflow. |
