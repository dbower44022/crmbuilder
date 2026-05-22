# Claude Code Prompt — v0.7 Slice D: Apply script modifications + atomic deposit_event POST

**Last Updated:** 05-22-26 17:30
**Release:** v0.7 (governance entity release)
**Slice:** D — apply_close_out.py modified to write log files and POST deposit_event records atomically as its last step
**Predecessor slice:** Slice C (UI panels) — must have shipped; Slices A and B (storage and API) must be live
**Successor slice:** Slice E (PI-022 Phase 1 backfill)
**PRD:** `PRDs/product/crmbuilder-v2/governance-entity-PRD-v0.1.md`
**Implementation plan section:** §2.4

---

## Task

Modify `crmbuilder-v2/scripts/apply_close_out.py` to integrate deposit_event creation at the end of every apply run. The modification: write a log file at `deposit-event-logs/dep_NNN.log` as apply runs; capture per-record HTTP outcomes; POST a deposit_event record at the apply's last step with all fields populated, parent edge, and wrote_record back-references; rely on the access layer's atomic transition of the target close_out_payload (lazy-creating it if missing).

## Read this first

1. `crmbuilder/CLAUDE.md`.
2. `PRDs/product/crmbuilder-v2/governance-entity-PRD-v0.1.md` §3.5 (apply path integration).
3. `PRDs/product/crmbuilder-v2/governance-entity-implementation-plan.md` §2.4 (this slice's deliverables).
4. `PRDs/product/crmbuilder-v2/governance-schema-specs/deposit_event.md` §3.5 (apply-script-as-canonical-writer) and §3.4.3 (atomic close_out_payload transition on success).
5. `PRDs/product/crmbuilder-v2/governance-schema-specs/close_out_payload.md` §3.4.3 v1.1 (first-success-transitions semantics).
6. `crmbuilder-v2/scripts/apply_close_out.py` — the current script.

## Deliverables

Per implementation plan §2.4:

1. **Modified `apply_close_out.py`:**
   - At script start: fetch next deposit_event identifier from `GET /deposit-events/next-identifier`; open log file at `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log`; install tee writer that duplicates stdout to the log file.
   - During section processing: capture per-record HTTP outcomes into `wrote_records` accumulator (200/201 only) and `records_summary` counter dict (keyed by section).
   - Determine outcome at end of section loop: `failure` if any non-409 error, `success` otherwise.
   - At apply's last step: construct deposit_event JSON, POST to `/deposit-events`.
   - Identifier mapping: payload file basename `ses_NNN.json` → target `COP-NNN` for the parent edge.
   - Backward compatibility: script must run against existing payload files; lazy-create close_out_payload via the access layer when missing.
   - Exit code unchanged: 0 on success, 1 on errors, 2 on argument/IO errors.

2. **Log file directory** at `PRDs/product/crmbuilder-v2/deposit-event-logs/`:
   - `.gitkeep` or `README.md` for git tracking.
   - README.md naming the directory's purpose and the `dep_NNN.log` naming convention.

3. **Tests** at `tests/crmbuilder_v2/scripts/` per slice §2.4 acceptance:
   - Happy-path apply against fixture payload: log file written; deposit_event POSTed; records_summary matches counts; outcome success; close_out_payload lazy-created if missing; parent edge and wrote_record edges created.
   - Failure-path apply: mid-section HTTP 422; outcome failure; `_error_info` populated; close_out_payload stays `ready`; partial wrote_record back-references.

## Working style

- Minimum invasive changes to apply_close_out.py — additive, not restructuring. The existing `_request`, `_log`, `_record_label`, `_check_api_reachable`, `main` shape stays.
- The log-file tee writer is a small wrapper around `sys.stdout`.
- The deposit_event POST is a new function called at the end of `main()` after the section loop.
- One commit for the script modification + tests + log directory.

## Pre-flight

```
curl -sf http://127.0.0.1:8765/health
uv run pytest tests/crmbuilder_v2/ -v
git pull --rebase origin main
```

## Acceptance gate

Per implementation plan §2.4:

- Apply script runs end-to-end against `close-out-payloads/ses_055.json`: writes log; POSTs deposit_event; transitions close_out_payload; creates edges.
- Re-running creates new deposit_event (multi-event semantics) without re-transitioning close_out_payload.
- Failure case: deposit_event POSTed with `_outcome = 'failure'`, `_error_info` populated; close_out_payload stays `ready`.
- `deposit-event-logs/` exists git-tracked.
- `uv run pytest tests/crmbuilder_v2/scripts/` green.

## Out of scope

- PI-022 backfill — Slice E.
- Documentation, version bump — Slice F.
