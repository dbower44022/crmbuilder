# Three-Way Reconciliation — User Guide

How to compare the canonical **design** against two live CRM instances and
reconcile the differences. Delivered in REL-024 (requirements REQ-352…361); lives
in the V2 desktop app under **Governance → Reconcile**.

---

## 1. What it does

The **design** (the canonical inventory in the V2 database) is your master
blueprint for how a CRM should be built. Live CRM instances drift from it as
people make changes through the admin screens. This feature shows you, side by
side, every configuration setting that differs across **three sources** — the
Design, **Instance A**, and **Instance B** — grouped by entity, and lets you
reconcile each difference or leave it.

**The design is the hub.** Values flow two ways through it:

- **Capture** — pull an instance's value *into* the design (instance → design).
- **Publish** — push the design's value *out* to an instance (design → instance).

There is no direct instance‑to‑instance change. To make Instance B match
Instance A, capture A's value into the design, then publish the design to B.

Every reconcile action is **logged and reversible** (see §6–§7).

## 2. Before you start

- **Two CRM instances must be connected and audited.** The comparison is served
  from each instance's last audit (its stored *membership* snapshot), so audit
  both instances first (**Governance → Instances → Audit now**). No live re‑scan
  happens when you open Reconcile — it reads the stored data, so it's fast but
  reflects the **last audit**. Re‑audit an instance to refresh it.
- The desktop app's API must be running (it normally is; the app owns it).

## 3. Compare two instances

1. Open **Governance → Reconcile**.
2. Pick **Instance A** and **Instance B** from the two dropdowns (they must be
   different).
3. Click **Compare**.

The **Differences** tab fills with one row per differing setting, grouped by
entity. Only entities (and a final *(global)* group for roles/teams/filtered
tabs) that actually have differences appear. The summary line shows the total
count.

> **Tip — full scan vs. drill.** Clicking Compare runs the full scan across every
> entity. The same engine also supports a fast per‑entity drill (used by tooling
> via the API `entity` parameter) when you only care about one entity.

## 4. Read the differences

Each row has five columns:

| Column | Meaning |
|---|---|
| **Member / Attribute** | The entity, field, relationship, etc. — and, for an attribute change, the attribute (e.g. `phone . field_max_length`). |
| **Kind** | `presence` (the member exists in the design but is missing on an instance) or `attribute` (a value differs). |
| **Design** | The value in the canonical design. |
| **Instance A** | A's value — or a presence token. |
| **Instance B** | B's value — or a presence token. |

Presence tokens: **present** (the instance carries it), **absent** (audited and
confirmed missing), **unknown** (never audited on that instance), **—** (no
value). A value differs only when the design and the instances that *carry* the
member don't all agree, so settings the design never specified don't show up as
false drift.

**Actionable vs. display‑only.** In this release you can **capture** differences
on **field attributes** (type, required, max length, default, min/max,
read‑only). Other rows — whole‑member presence, relationships, layouts, roles,
teams — are shown for visibility but are not yet reconcilable from this panel; if
you select one and try to capture, the panel tells you so. Settings that can be
read but not written back through the platform are likewise shown but never
offered an action they can't perform.

## 5. Capture a value into the design

1. In the **Differences** tab, select a **field‑attribute** row.
2. Click **Capture A → Design** or **Capture B → Design**, depending on which
   instance holds the value you want to make canonical.

What happens: the chosen instance's value is written onto the canonical field,
the action is recorded in the transaction log, and that attribute's drift on the
source instance is cleared (it now matches the design). The view refreshes.

If the chosen instance doesn't actually deviate on that attribute, the capture is
rejected with a message — pick the side that holds the differing value.

## 6. Publish the design to an instance

The reverse direction — pushing the design's value *out* to a live instance —
reuses the existing **Publish** flow: **Governance → Instances → Publish…** on
the target instance. That path generates the configuration, validates it against
the live target, takes a pre‑publish backup, deploys, and re‑verifies. Use it
after capturing the values you want into the design.

## 7. The transaction log

Open the **Transaction Log** tab to see every reconcile action, newest first:
its ID, direction (capture / publish), member, attribute, **before → after**
values, status (applied / rolled_back), and who did it. Click **Refresh** to
reload.

## 8. Roll back a change

1. In the **Transaction Log** tab, select a transaction.
2. Click **Roll Back Selected**.

- **Design changes undo cleanly and safely** — the prior value is simply
  restored.
- **Live‑instance reverts are guarded.** Before proceeding, the system analyzes
  the revert's impact and, if it could **cause data loss** or can't be cleanly
  applied (e.g. narrowing a field's max length would truncate data, an
  incompatible type change, or removing a field that holds data), it **warns you
  with the reasons and asks you to confirm**. You can proceed with eyes open or
  cancel.

Rollback never deletes the log row — it flips its status to `rolled_back` and
records who reversed it, and a compensating entry is added, so the full history
stays intact.

## 9. What's covered, and current limits

- **Coverage shown:** entities, fields and field settings, relationships
  (listed under both linked entities), layouts, roles, teams, and filtered tabs.
- **Capture (instance → design) in this release:** field attributes. Whole‑entity
  copy, per‑attribute publish, and capture of non‑field members are planned
  follow‑ons; for now use the Instances → Publish flow for design → instance.
- **Freshness:** the diff reflects each instance's last audit. Re‑audit to
  refresh before reconciling if a system changed recently.

## 10. For power users / scripting

The same capabilities are available over the REST API (envelope `{data, meta,
errors}`, `X-Engagement` header):

| Endpoint | Purpose |
|---|---|
| `GET /reconcile/compare?instance_a=&instance_b=&entity=` | Three‑way diff (omit `entity` for the full scan). |
| `POST /reconcile/capture` | Capture a field attribute into the design. |
| `GET /reconcile/transactions` | The transaction log. |
| `GET /reconcile/transactions/{id}/assess-revert` | Data‑loss analysis for a revert. |
| `POST /reconcile/transactions/{id}/rollback` | Reverse a design change. |

---

*Feature: REL-024 — Three‑Way Design/Instance Configuration Reconciliation.
Design/plan: `three-way-reconciliation-release-plan.md`.*
