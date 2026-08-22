# Kickoff prompt — automated end-to-end publish check

Paste the block below into a fresh Claude Code session rooted at
`~/Dropbox/Projects/crmbuilder`. Written 2026-08-10, at the close of the session
that fixed the three stacked publish defects (REQ-481 / REQ-482).

---

## The prompt

Orient first: read the **Session bootstrap** section of `CLAUDE.md` and follow it
(topic TOP-013 + children, active `governance_rules`, `preferences`,
`reference_pointers`; `lessons` on demand). The V2 database is the source of
truth — do not orient from committed files.

**The task.** Design and build an automated end-to-end check for the *publish*
path (design → generated YAML → live CRM instance), so a regression in it is
caught by a test run rather than by Doug reaching for the feature.

**Why this is worth building.** In August 2026 publish was found broken in
**three independent places**, each invisible until the one above it was fixed:

1. **Credentials** — instance secrets lived in an OS keyring the hosted service
   has no backend for. `get_secret` raised `NoKeyringError` uncaught → opaque
   500. Fixed by REQ-481 / PI-402 (encrypted store, `secret_values`).
2. **Self-authentication** — the publish handlers built a `RestDesignClient`
   against the service's own `api_base_url` and called its own endpoints. That
   client sends no `Authorization` header, and the droplet runs
   `PRINCIPAL_AUTH_ENABLED=true` → `HTTPError 401` wrapped in a 500. Fixed by
   REQ-482 / PI-403 (in-process `AccessDesignClient`).
3. **Silent data loss** — `RestDesignClient.list_fields` filtered the reference
   rows on `relationship_kind` while the API serializes that key as
   `relationship`. The parent map was always empty, so **every** field came back
   with no parent entity (0 of 254 on CBM). Found only by diffing the two design
   clients against live data. Fixed in the same PI.

Read `DEC-913`, `DEC-914`, `REQ-481`, `REQ-482`, and the resolution notes on
`PI-402` / `PI-403` for the full history before designing.

**The acceptance bar to design against:** *would this check have caught all
three?* A check that only asserts "publish returned 200" would have missed #3
entirely — the run was green while the YAML had no fields attached to entities.
State explicitly, for each of the three, whether your design catches it and how.

**What is already true (verify, don't assume):**

- `POST /instances/INST-001/publish-validate` returns HTTP 200 — 10 programs,
  zero validation errors, `aborted: false`, `deployed: false`.
- `validate_only` stops before writing anything to the target instance
  (`publish/service.py` — a validate run stops after step 3).
- Both design clients agree across all 12 `DesignClient` methods against live
  CBM data. `tests/crmbuilder_v2/adapters/test_design_client_parity.py` pins the
  contract; extend it rather than duplicating it.
- Engagement `ENG-002` (CBM) has two instances: **INST-001 CBMTEST** and
  **INST-002 CBM Production**.

**Hard constraints:**

- **Never publish to INST-002 (CBM Production).**
- Doug has **not** authorized a real publish to CBMTEST either. Ask before any
  run that writes to a live instance; `validate_only` is fine.
- Deploy is human-only (**GVR-240**). Prepare and verify; never execute one.
- Requirement-first (**GVR-230**): a confirmed requirement + approving decision
  + implementing PI must exist *before* any code. Every code commit carries
  `Governed-By: PI-NNN` (**GVR-229**).
- Any schema change ships on **both** alembic heads (**LSN-003**), and a
  `create_table` migration must be bootstrap-safe — the PI-308 path does
  `create_all` then stamps behind, so a bare create fails (see migrations
  `0067`/`0110` for the guard shape).

**Design questions that are genuinely open — bring options, don't just pick:**

1. **How far does "end-to-end" go?** A hermetic test against a fake CRM (fast,
   CI-safe, but does not prove real authentication); validate-only against a
   live instance (proves credentials + design read, writes nothing); or a full
   publish against a disposable instance (proves everything, needs an instance
   to burn). These have very different costs.
2. **Where does it run?** Part of the pytest suite, or a scheduled check against
   the droplet? A test needing live network and real credentials does not belong
   in the ordinary suite.
3. **What does it assert beyond "no exception"?** Programs generated, fields
   attached to their parent entities, relationships present, credentials
   resolved from the encrypted store, no self-authenticating HTTP call.

Come back with the options and a recommendation before building. Once Doug
picks, record the governance chain and build it.
