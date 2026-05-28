# Kickoff — Concurrency for promoted records + substrate validation at scale

**Opens against:** PI-103 (edit-locking for promoted records) and PI-100 (storage-substrate validation)
**Work ticket:** WT-056
**Workstream:** WS-012 (Parallel agent orchestrator)
**Operating mode:** ARCHITECTURE
**Follows from:** CNV-012 (SES-110) — see DEC-325 (the SessionDraftToken decision)

---

## Why this conversation exists

CNV-012 designed the **draft phase** of a concurrent-write-safety model and decided **DEC-325 (SessionDraftToken)**. Two threads were explicitly deferred to this separate conversation. Do not re-derive the facts below — they are settled context. This conversation settles the remaining two threads and, with them, the full model.

## Settled context (carry forward, do not relitigate)

- **Goal:** support a high number of AI agents writing concurrently; **data safety is non-negotiable**.
- **Three-layer model:** (1) crash-safe correctness floor — server-assigned identifiers for creates + a write-precondition for modifies; (2) advisory coordination registry (check-out / who-holds-what); (3) admission gate — governance writes require an open live-session context; a client that cannot participate live does not get to write.
- **Drafts** are the staging mechanism for long-lived, multi-record agent work on a short-transaction substrate; private to their owner (invisible/non-referenceable to peers), writable only by the owner plus a privileged reaper role. **DEC-325**: a per-session capability token (SessionDraftToken), FK-stamped on each draft, required to write, rotated on handoff, expiring to a reaper. **The token governs the draft phase only.**
- **Transport reality:** claude.ai-web remote MCP is blocked upstream (DEC-244 / PI-045 / PI-049). Live-capable surfaces: Claude Desktop (stdio MCP) and the chat-UI client (PI-052, in build).
- **Substrate facts (db.py):** SQLite, serialized writers (`BEGIN IMMEDIATE`, `busy_timeout=5000`, `isolation_level=None`), **no WAL**, **one DB file per engagement**. Write concurrency is therefore **per-engagement** — cross-engagement scales horizontally for free; within one engagement everything funnels through a single serialized writer.
- **Complementary existing PIs under WS-012 (do not duplicate):** PI-077 (claimed_by/claimed_at), PI-078 (identifier reservation API), PI-079 (ready-batches).

## Thread 1 — Edit-locking on promoted (already-real) records (PI-103)

Once a draft is promoted to a real record, the SessionDraftToken retires. Real records need their own modify-modify protection guaranteeing **no lost updates**. Decide the mechanism:

- **Optimistic precondition** — reuse the existing `updated_at` column as a compare-and-swap precondition (zero migration, clock-granularity edge case), or add a dedicated monotonic `row_version` (≈20-table migration; note **no `row_version` exists today** — only charter/status/reference_book carry a different `version` concept).
- **Advisory lease** over the crash-safe floor.
- **Hybrid** (advisory lease for coordination + version precondition for correctness).

Frame as the eight-element consequential-decision template; this passes the two-part test.

## Thread 2 — Substrate at scale (PI-100)

Decide whether **SQLite-per-engagement holds** at the target peak number of concurrent writers **against a single engagement**, or whether a different store (e.g., Postgres with row-level MVCC) is required. Distinguish:

- **Logical concurrency** — many agents partitioned across areas (DEC-304), each writing briefly — SQLite survives.
- **Throughput concurrency** — sustained write rate beyond a single writer, or long-held write transactions — SQLite does not.

First input needed from Doug: order-of-magnitude peak concurrent writers against one engagement, and whether their work partitions cleanly or contends on shared records.

## Companion fix (fold in)

`apply_close_out.py` treats HTTP 409 as "already present — skipping" and exits 0, silently dropping a genuine collision (same identifier, different content). Should **hard-fail** when identifier matches but content differs. Fold into PI-101 (close-out pipeline integrity), which already covers pre-flight validation.

## Related backlog (already filed — not this conversation's job)

Two sibling items came out of the SES-110 apply and are filed separately under WS-012; noted here only for context:

1. **Harden the close-out pre-flight validator** (PI-101) — it should reject missing required fields and wrong-case status values.
2. **Reconcile the executive_summary column nullability** between the SQLAlchemy models and the live database (PI-102).

This conversation does **not** work those — it works edit-locking (PI-103) and substrate (PI-100).

## Deliverable shape

Decisions authored at moment-of-decision (DEC-326+); a close-out that, together with DEC-325 (the SessionDraftToken decision), **resolves PI-103 (edit-locking) and PI-100 (substrate)** once both threads are settled; an implementation PI/sequence for building the model.
