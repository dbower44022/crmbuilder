# PI-568 kickoff — email templates on EspoCRM 10, and no false passes

| Field | Value |
|---|---|
| Title | PI-568 kickoff — email templates on EspoCRM 10, and no false passes |
| Last Updated | 09-23-26 12:25 |
| Revision | 1.0 |
| Status | Ready to run. REQ-645 is confirmed (DEC-1147), and PI-568 is Draft in PRJ-125. |
| Governs | One session's work: building PI-568, which implements REQ-645 |
| Source | CNV-398, the 09-23-26 live server proof in SES-426; REQ-645; DEC-1147 |

## Opening answer

Paste this as the first line of the new session so the session-open hook
classifies it:

> Opening answer: Build PI-568 — version 2 audits and publishes email templates on EspoCRM 10, and an audit area the instance refuses reports not checked instead of a pass.

---

## 1. Why this is a must

On EspoCRM 10, version 2 cannot audit email templates, cannot publish them, and
can quietly corrupt what the store records about them. CBM production runs
version 9 today. PI-557 made upgrading an instance a single operation. **This
work must land before any CBM instance is upgraded to version 10.**

"Done" means PI-568 is merged to `main` and pushed, and then marked Resolved.
Section 7 gives the order.

## 2. Governance is already in place

- **REQ-645** is confirmed, approved by **DEC-1147** on 09-23-26. Its acceptance
  summary is the definition of done, and its notes hold the evidence. Read both
  from the store.
- **PI-568** is Draft in **PRJ-125** and implements REQ-645. Move it to In
  Progress when the work starts. Every code commit carries
  `Governed-By: PI-568` and names an explicit pathspec.
- The product owner turned down narrowing REQ-645 to email templates only
  (recorded as the rejected alternative in DEC-1147). The "not checked" rule
  covers **every** audit area.

## 3. What is verified, and what is not

**Verified 09-23-26 against `proof-5.acmeconstruction.us`, EspoCRM 10.0.8:**

- The email template's fields are assignedUser, attachments, body, category,
  createdAt, createdBy, description, isHtml, modifiedAt, modifiedBy, name,
  oneOff, status, subject and teams. **There is no `entityType`.**
- `GET /EmailTemplate?where[0][type]=equals&where[0][attribute]=entityType&where[0][value]=Contact&maxSize=200`
  returns HTTP 400. The reason is in the `X-Status-Reason` header:
  `Not existing attribute 'entityType' in where.` The body is empty.
- `GET /EmailTemplate?maxSize=200` returns 200 with `{"total":0,"list":[]}`.
- `maxSize=201` returns 403, `Max size should not exceed 200. Use offset and limit.`
  A listing beyond 200 templates must page.
- The audit printed `✓ Email templates: 0 seen …` and then one "could not list
  email templates (HTTP 400); skipped" warning for each of the 13 entities.

**Verified by reading the code, not by running it:**

- The audit's request is `introspect/espo_client.py` `list_email_templates`,
  and its handling is `introspect/reconcile.py` `reconcile_email_templates`.
  Version 2 publish uses the same filter in `publish/message_templates.py`
  `_live_templates`. When the answer is not 200, publish marks every template
  failed. Its create payload also sends `entityType` (line 59).
- **The audit can corrupt the record.** `reconcile_email_templates` builds its
  membership writer with the default `read_succeeded=True`, skips each refused
  entity with `continue`, and calls `sweep_absent()` at the end. The sweep only
  refrains when the read is marked failed. So on version 10, an audit of an
  instance whose templates are recorded as present would sweep them to
  **absent**. That is the REL-038 shape, which the workflows area already
  avoids: it calls `writer.mark_read_failed()` and sets `summary["reason"]`
  ("state is unknown, not none-present"). This is inferred from the code and
  not run. Confirm it with a test before relying on it.
- The design keeps a template's object type in `message_template_entity`
  (`access/models.py`), so the design can hold it even where the platform
  cannot.

**Not known:**

- **Whether EspoCRM 9 has an `entityType` field on email templates.** CBM's three
  templates were created through this path in May. Either version 9 accepted
  the field, or the platform ignored it and the audit has never matched
  templates to entities. The answer decides whether this is a version 10 change
  or a defect that has always existed.
- How templates on version 10 are meant to relate to an object type, if at all.
  The `category` link is the only grouping the field list shows.

## 4. Read before writing code

REQ-645 requires two read-only reads before any code is written. Build every
fixture from what these reads return, and name the date and host in each test
file (lesson LRN-007).

1. **CBM production**, `INST-002` in engagement ENG-002
   (`https://crm.clevelandbusinessmentors.org`, version 9). Read the email
   template field list (`GET /Metadata?key=entityDefs.EmailTemplate.fields`),
   the unfiltered template listing, and the filtered request the audit sends.
   **Only GET requests. Nothing is written to a client's production system.**
   Use the credential version 2 already stores for INST-002. Before running
   anything against production, tell the product owner what will be read.
2. **A version 10 instance.** The proof server is gone. Three routes:
   - the product owner builds another throwaway instance, using the method
     recorded in CNV-398;
   - or CBM's test instance (`INST-001`, CBMTEST) if it is on version 10 — check
     its version first;
   - or the 09-23-26 evidence in section 3 stands in, with that limitation
     stated in the tests.

## 5. What to change

- **Listing templates.** Identify templates in a way the running version
  supports. That is probably the unfiltered listing, paged in 200s, matched by
  name. Where a version stores the object type, use it. Where it does not, the
  design's `message_template_entity` stays the source, and publish says the
  object type was not applied.
- **Publishing.** Create, update, and leave unchanged exactly as on version 9.
  A second publish creates no duplicate. Do not send a field the running
  version refuses. Whether version 10 ignores an unknown field on create, or
  refuses it, is not known; check it.
- **The audit's "not checked" rule, in every area.** An area whose listing the
  instance refuses reports "not checked", with the instance's reason, and never
  a green pass with zeros. It also never sweeps rows to absent. The workflows
  area already has the mechanism (`mark_read_failed`, `summary["reason"]`).
  Apply it to email templates, then check every other area in
  `introspect/reconcile.py`. The fields and relationships areas also log
  "could not read … (HTTP …)"; confirm whether each one marks its read failed.
  The audit window's area line must show the difference: a pass, "not checked",
  and a real empty area are three different states.
- **Leave version 1 alone.** `espo_impl/core/email_template_manager.py` has the
  same filter and probably re-creates templates on every run (inferred). Version
  1 is being retired by absorption.

## 6. How to work

- **Where to open the session.** A worktree cannot reach the store, because
  `crmbuilder-v2/data/crmbuilder.env` is untracked. So work in the main folder
  on a new branch. The PI-567 session is also working in the main folder, so
  **start PI-568 after PI-567 has merged and pushed.** PI-567 is small.
- **Tests:** `tests/crmbuilder_v2/introspect/`, `tests/crmbuilder_v2/publish/`,
  and `tests/crmbuilder_v2/test_version_one_imports.py` in the foreground, and
  the linter on the changed files. The full version 2 suite runs longer than
  the ten-minute tool limit; run it in the background. Its known intermittent
  desktop crash is lesson LSN-073.
- **Never write to a client instance.** Proving a publish on version 10 is the
  product owner's step, on a throwaway instance.

## 7. Closing the work

1. Commit on the branch with `Governed-By: PI-568`, then merge to `main` with no
   fast-forward.
2. **Push `main` before marking PI-568 Resolved.** The push hook flags any
   commit whose planning item is already Resolved.
3. Mark PI-568 Resolved with a resolution reference naming both commits and
   saying they are pushed.
4. Record what the CBM production read found: whether version 9 has
   `entityType`. It settles the open question in REQ-645's notes.

## Change log

| Revision | Date | Description |
|---|---|---|
| 1.0 | 09-23-26 12:25 | Written in SES-426 after the live server proof (CNV-398) and the approval of REQ-645 by DEC-1147. Adds a finding from reading the code: on version 10, the audit can sweep recorded templates to absent. |
