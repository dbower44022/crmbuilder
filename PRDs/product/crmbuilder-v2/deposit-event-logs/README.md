# Deposit-event logs

Captured stdout transcripts from every run of
`crmbuilder-v2/scripts/apply_close_out.py` (UI v0.7 governance entity
release).

## Naming convention

Each file is `dep_NNN.log` where `NNN` matches the deposit_event identifier
`DEP-NNN` the apply created.

The script:

1. Fetches the next `DEP-NNN` from the API at start.
2. Opens this file and tees stdout to it so the full apply transcript is
   captured regardless of outcome.
3. POSTs a `deposit_event` record at the apply's last step whose
   `_log_file_path` field points at the repo-relative path of this file.

## Git tracking

These files are git-tracked per DEC-164 (governance entity PRD v0.1, §3.5).
Commit each log alongside the close-out payload it applies; the modest
repo-size cost (~5KB per apply attempt) buys durable diagnostic value.

For historical applies that pre-date v0.7 there is no captured stdout;
those are represented by placeholder `dep_NNN-historical.log` files
authored by the PI-022 Phase 1 backfill (Slice E) with a one-line note
that the log was not captured at apply time.
