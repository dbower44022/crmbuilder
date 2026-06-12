"""Spreadsheet storage-policy behavior and downstream interchangeability
(WTK-115, executing the WTK-111 §8 criteria that need a live DB).

WTK-113 pinned the store structurally — S1–S4 and S7's intake half live
in ``tests/crmbuilder_v2/adapters/test_source_store.py``, whose
docstring hands the deposit-side criteria here. This module drives a
registered snapshot through the *landed* pipeline — ``register_source``
→ ``profile_source``/``write_outputs`` → ``plan_deposit``/
``execute_plan`` against a per-test DB — and asserts behavior:

* **S5** — label stability across two deposited snapshots of one
  source: one ``evidence_source_label``, the WTK-088 latest-snapshot
  query returns the second run's rows, candidate counts unchanged.
* **S6** — schema fit end to end: every row lands with zero constraint
  violations, ``evidence_catalog_class = "custom"`` throughout, the
  deposit event is ``audit_deposit`` with
  ``apply_context.source_system = "spreadsheet"`` and
  ``source_instance`` the source-dir ``file://`` URI, field evidence
  carries ``type_inference`` and entity evidence the registered
  ``source_file_sha256``.
* **S7** (profiler-run + deposit-log halves) — a sentinel cell value
  appears in no profiler CLI output and not in the deposit-event log
  payload; it does appear, bounded, where §3.5 rule 4 admits it
  (manifest options, profile distributions, DB evidence detail).
* **S8/S9** — the provenance chain walked from a deposited field
  candidate resolves, from the DB alone, to a held snapshot whose
  ``source-manifest.json`` hashes still match the files (the migration
  pre-flight shape; S9's rule-level resolvability).
* **§3.6 retention** — profiling and depositing leave the registered
  files byte-identical; the only snapshot additions are the manifest
  pair, and a re-profile regenerates it byte-identically (the §4.1
  overwrite-safe rule).
* **§5.5 interchangeability** — EspoCRM-born and spreadsheet-born
  inventory deposited into one DB are consumed by the same WTK-088
  reads (latest-snapshot, Q1 low-population) with no source-specific
  branching.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import (
    deposit_events,
    references,
    utilization_evidence,
)
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.adapters import spreadsheet
from crmbuilder_v2.adapters.source_store import (
    SOURCE_MANIFEST_FILENAME,
    register_source,
)
from crmbuilder_v2.config import reset_settings_cache
from crmbuilder_v2.transform import audit_deposit

from tests.crmbuilder_v2.transform.test_audit_deposit import (
    AccessClient,
    t1_manifest,
    t1_profile,
)

NOW = datetime(2026, 6, 12, 8, 15, 0, tzinfo=UTC)
LATER = datetime(2026, 7, 1, 14, 0, 0, tzinfo=UTC)

SENTINEL = "SENTINEL-CONFIDENTIAL-9981"
SPREADSHEET_LABEL = "spreadsheet @ cbm-mentor-tracking"
ESPOCRM_LABEL = "espocrm @ crm.example.org"

# 12 rows: Stage is enum-eligible (support 12 >= 10, 3 distinct) with the
# sentinel as an observed option; Notes is sparse (1/12) for the Q1 read.
MENTORS_CSV = "Name,Email,Stage,Notes\n" + "".join(
    f"Person {i},person{i}@example.org,{stage},{notes}\n"
    for i, (stage, notes) in enumerate(
        [
            ("active", "Met at the gala."),
            ("active", ""),
            ("active", ""),
            ("active", ""),
            ("active", ""),
            ("active", ""),
            ("paused", ""),
            ("paused", ""),
            ("paused", ""),
            ("paused", ""),
            (SENTINEL, ""),
            (SENTINEL, ""),
        ]
    )
)
DONATIONS_CSV = (
    "Donation ID,Amount\n"
    "101,$50.00\n102,$75.00\n103,$100.00\n104,$25.00\n105,$60.00\n"
)


@pytest.fixture
def sources_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    root = tmp_path / "sources"
    monkeypatch.setenv("CRMBUILDER_V2_SOURCES_DIR", str(root))
    reset_settings_cache()
    yield root
    reset_settings_cache()


@pytest.fixture
def intake_files(tmp_path: Path) -> list[Path]:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    original = inbox / "cbm-mentor-tracking.xlsx"
    original.write_bytes(b"PK\x03\x04 not a real workbook")
    mentors = inbox / "mentors.csv"
    mentors.write_text(MENTORS_CSV, encoding="utf-8")
    donations = inbox / "donations.csv"
    donations.write_text(DONATIONS_CSV, encoding="utf-8")
    return [original, mentors, donations]


def _register(files: list[Path], now: datetime = NOW) -> Path:
    return register_source(
        files,
        "CRMBUILDER",
        "CBM Mentor Tracking",
        sheet_names={"mentors.csv": "Mentors"},
        registered_by="doug",
        now=now,
    )


def _deposit(
    snapshot: Path, *, now: datetime
) -> tuple[dict, audit_deposit.DepositPlan]:
    """The operator flow over a registered snapshot: profile, land the
    pair in the snapshot (§4.1), reload it from disk, deposit."""
    manifest, profile = spreadsheet.profile_source(snapshot, now=now)
    manifest_path, profile_path = spreadsheet.write_outputs(
        manifest, profile, snapshot
    )
    manifest = audit_deposit.load_manifest(manifest_path)
    profile = audit_deposit.load_profile(profile_path)
    client = AccessClient()
    plan = audit_deposit.plan_deposit(
        manifest, profile, audit_deposit.fetch_existing_state(client)
    )
    return audit_deposit.execute_plan(plan, client), plan


def _read_manifest(snapshot: Path) -> dict:
    return json.loads(
        (snapshot / SOURCE_MANIFEST_FILENAME).read_text(encoding="utf-8")
    )


def _evidence_rows(**filters) -> list[dict]:
    with session_scope() as s:
        return utilization_evidence.list_utilization_evidence(s, **filters)


def _snapshot_bytes(snapshot: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(snapshot): path.read_bytes()
        for path in snapshot.rglob("*")
        if path.is_file()
    }


# ---------------------------------------------------------------------------
# S6 — schema fit, end to end
# ---------------------------------------------------------------------------


def test_s6_registered_snapshot_deposits_end_to_end(
    v2_env, sources_root: Path, intake_files: list[Path]
) -> None:
    snapshot = _register(intake_files)
    summary, plan = _deposit(snapshot, now=NOW)

    # The pair landed in the snapshot, not anywhere git-tracked (§4.1).
    assert (snapshot / "audit-report.json").is_file()
    assert (snapshot / "utilization-profile.json").is_file()

    # Zero constraint violations = a success event whose wrote_record
    # edges cover exactly the records the summary counts (§5.3).
    with session_scope() as s:
        event = deposit_events.get_deposit_event(
            s, summary["deposit_event_identifier"]
        )
        edges = references.list_references(
            s,
            source_type="deposit_event",
            source_id=summary["deposit_event_identifier"],
            relationship_kind="deposit_event_wrote_record",
        )
    assert event["deposit_event_kind"] == "audit_deposit"
    assert event["deposit_event_outcome"] == "success"
    assert len(edges) == sum(event["deposit_event_records_summary"].values())

    context = event["deposit_event_apply_context"]
    assert context["source_system"] == "spreadsheet"
    assert context["source_instance"] == snapshot.parent.resolve().as_uri()
    assert context["snapshot_at"] == "2026-06-12T08:15:00Z"
    assert context["source_label"] == SPREADSHEET_LABEL

    # Both sheets became candidate entities; every field is a candidate.
    with session_scope() as s:
        entities = {
            e["entity_name"]: e for e in entity_repo.list_entities(s)
        }
        fields = field_repo.list_fields(s)
    assert set(entities) == {"mentors", "donations"}
    assert all(e["entity_status"] == "candidate" for e in entities.values())
    assert fields and all(f["field_status"] == "candidate" for f in fields)

    # Evidence: custom throughout (D4); field detail carries the
    # type_inference block, entity detail the registered sheet hash.
    rows = _evidence_rows()
    assert rows
    assert {r["evidence_source_label"] for r in rows} == {SPREADSHEET_LABEL}
    assert {r["evidence_catalog_class"] for r in rows} == {"custom"}
    assert {r["evidence_deposit_event_identifier"] for r in rows} == {
        summary["deposit_event_identifier"]
    }
    hashes = {
        entry["file"]: entry["sha256"]
        for entry in _read_manifest(snapshot)["sheets"]
    }
    entity_rows = [r for r in rows if r["evidence_subject_type"] == "entity"]
    field_rows = [r for r in rows if r["evidence_subject_type"] == "field"]
    assert len(entity_rows) == 2
    for row in entity_rows:
        detail = row["evidence_detail"]
        assert detail["source_file_sha256"] == hashes[detail["source_file"]]
    assert field_rows
    for row in field_rows:
        assert "type_inference" in row["evidence_detail"]


# ---------------------------------------------------------------------------
# S5 — label stability and the latest-snapshot rule across re-deposits
# ---------------------------------------------------------------------------


def test_s5_label_stable_and_latest_wins_across_snapshots(
    v2_env, sources_root: Path, intake_files: list[Path]
) -> None:
    first_snapshot = _register(intake_files)
    first, _ = _deposit(first_snapshot, now=NOW)

    second_snapshot = _register(intake_files, now=LATER)
    second, _ = _deposit(second_snapshot, now=LATER)

    # WTK-090 T3 semantics over snapshots (§4.4): the re-deposit matches
    # everything by name and creates nothing.
    assert second["created"] == []
    assert second["records_summary"] == {}
    assert second["deposit_event_identifier"] != first[
        "deposit_event_identifier"
    ]
    with session_scope() as s:
        assert len(entity_repo.list_entities(s)) == 2
        field_count = len(field_repo.list_fields(s))

    # One source, one label, across both deposits (§4.3 invariant) —
    # and a fresh evidence row per subject per run.
    rows = _evidence_rows()
    assert {r["evidence_source_label"] for r in rows} == {SPREADSHEET_LABEL}
    assert len(rows) == 2 * (2 + field_count)

    # The WTK-088 latest-snapshot read returns exactly the second run.
    latest = _evidence_rows(latest=True)
    assert len(latest) == 2 + field_count
    assert {r["evidence_deposit_event_identifier"] for r in latest} == {
        second["deposit_event_identifier"]
    }
    assert all(
        r["evidence_profiled_at"].startswith("2026-07-01T14:00")
        for r in latest
    )


# ---------------------------------------------------------------------------
# S7 — sentinel in no run output, no deposit log; bounded where admitted
# ---------------------------------------------------------------------------


def test_s7_sentinel_in_no_run_output_or_deposit_log(
    v2_env,
    sources_root: Path,
    intake_files: list[Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    snapshot = _register(intake_files)

    # Profiler CLI run output: names and counts, never content.
    rc = spreadsheet.main([str(snapshot)])
    captured = capsys.readouterr()
    assert rc == 0
    assert SENTINEL not in captured.out
    assert SENTINEL not in captured.err

    # ... while the pair itself admits the value, bounded (§3.5 rule 4):
    # an observed enum option in the manifest, a distribution key in the
    # profile.
    manifest = json.loads(
        (snapshot / "audit-report.json").read_text(encoding="utf-8")
    )
    profile = json.loads(
        (snapshot / "utilization-profile.json").read_text(encoding="utf-8")
    )
    (mentors,) = [e for e in manifest["entities"] if e["espo_name"] == "mentors"]
    (stage,) = [f for f in mentors["fields"] if f["yaml_name"] == "stage"]
    assert SENTINEL in stage["properties"]["options"]
    # The profile keys fields by api_name — the literal header text.
    stage_profile = profile["entities"]["mentors"]["fields"]["Stage"]
    assert SENTINEL in stage_profile["detail"]["value_distribution"]

    summary, plan = _deposit(snapshot, now=NOW)

    # The deposit-event log payload — exactly what the CLI writes to
    # deposit-event-logs/dep_NNN.log (git-tracked, §3.5 rule 2) — is
    # summary, names, and apply_context: never cell values.
    log_payload = json.dumps(
        {
            "deposit_event_identifier": summary["deposit_event_identifier"],
            "records_summary": summary["records_summary"],
            "created": summary["created"],
            "matched": summary["matched"],
            "evidence_rows": summary["evidence_rows"],
            "apply_context": plan.apply_context,
        },
        indent=2,
        sort_keys=True,
    )
    assert SENTINEL not in log_payload

    # In the DB the value rides only evidence detail — rule 4's bounded
    # admission, under the DB's protection class.
    with session_scope() as s:
        stage_field = next(
            f
            for f in field_repo.list_fields(s)
            if f["field_name"] == "Stage"
        )
    stage_rows = _evidence_rows(
        subject_type="field",
        subject_identifier=stage_field["field_identifier"],
    )
    (stage_row,) = stage_rows
    assert SENTINEL in stage_row["evidence_detail"]["value_distribution"]


# ---------------------------------------------------------------------------
# S8 / S9 — provenance chain walk, snapshot resolvable from the DB alone
# ---------------------------------------------------------------------------


def test_s8_s9_provenance_chain_resolves_held_snapshot(
    v2_env, sources_root: Path, intake_files: list[Path]
) -> None:
    snapshot = _register(intake_files)
    _deposit(snapshot, now=NOW)

    # Start from a deposited field candidate, using only DB rows.
    with session_scope() as s:
        fld = next(
            f
            for f in field_repo.list_fields(s)
            if f["field_name"] == "Stage"
        )
        (edge,) = references.list_references(
            s,
            relationship_kind="deposit_event_wrote_record",
            target_type="field",
            target_id=fld["field_identifier"],
        )
        event = deposit_events.get_deposit_event(s, edge["source_id"])
        (parent_edge,) = references.list_references(
            s,
            source_type="field",
            source_id=fld["field_identifier"],
            relationship_kind="field_belongs_to_entity",
        )
        (entity_evidence,) = utilization_evidence.list_utilization_evidence(
            s,
            subject_type="entity",
            subject_identifier=parent_edge["target_id"],
        )

    # apply_context.source_instance resolves to the held source dir.
    source_uri = event["deposit_event_apply_context"]["source_instance"]
    source_dir = Path(url2pathname(urlsplit(source_uri).path))
    assert source_dir == snapshot.parent.resolve()
    assert source_dir.is_dir()

    # The evidence-detail hash (§4.2) selects the exact snapshot, and
    # the snapshot's manifest hashes still match the held files — the
    # future migration pre-flight (§3.6), which is S9's guarantee that
    # a purge surface can implement the deposit-reference lock.
    sheet_sha = entity_evidence["evidence_detail"]["source_file_sha256"]
    matching = []
    for candidate in source_dir.iterdir():
        manifest_path = candidate / SOURCE_MANIFEST_FILENAME
        if not manifest_path.is_file():
            continue
        held = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in held["sheets"]:
            data = (candidate / entry["file"]).read_bytes()
            assert hashlib.sha256(data).hexdigest() == entry["sha256"]
        if sheet_sha in {entry["sha256"] for entry in held["sheets"]}:
            matching.append(candidate)
    assert matching == [snapshot]


# ---------------------------------------------------------------------------
# §3.6 retention — the held files survive profiling and deposit untouched
# ---------------------------------------------------------------------------


def test_retention_held_files_untouched_by_profile_and_deposit(
    v2_env, sources_root: Path, intake_files: list[Path]
) -> None:
    snapshot = _register(intake_files)
    registered = _snapshot_bytes(snapshot)

    _deposit(snapshot, now=NOW)
    after = _snapshot_bytes(snapshot)

    # Every registered file is byte-identical; the only additions are
    # the manifest pair, co-located per §4.1.
    pair = {Path("audit-report.json"), Path("utilization-profile.json")}
    assert set(after) == set(registered) | pair
    for path, data in registered.items():
        assert after[path] == data

    # A re-profile of the frozen snapshot regenerates the pair
    # byte-identically (C6 determinism makes the overwrite safe, §4.1).
    manifest, profile = spreadsheet.profile_source(snapshot, now=NOW)
    spreadsheet.write_outputs(manifest, profile, snapshot)
    assert _snapshot_bytes(snapshot) == after


# ---------------------------------------------------------------------------
# §5.5 — one downstream flow consumes both adapters' inventory
# ---------------------------------------------------------------------------


def test_interchangeability_one_downstream_flow_both_sources(
    v2_env, sources_root: Path, intake_files: list[Path]
) -> None:
    # The EspoCRM-path deposit (the landed T1 fixture, with profile)
    # and a spreadsheet-snapshot deposit, into the same DB.
    client = AccessClient()
    espocrm_plan = audit_deposit.plan_deposit(
        t1_manifest(), t1_profile(), audit_deposit.fetch_existing_state(client)
    )
    espocrm = audit_deposit.execute_plan(espocrm_plan, client)
    snapshot = _register(intake_files)
    sheet, _ = _deposit(snapshot, now=NOW)

    # Same pathway discriminator, adapter identity only in apply_context.
    with session_scope() as s:
        events = [
            deposit_events.get_deposit_event(
                s, run["deposit_event_identifier"]
            )
            for run in (espocrm, sheet)
        ]
    assert [e["deposit_event_kind"] for e in events] == [
        "audit_deposit",
        "audit_deposit",
    ]
    assert [
        e["deposit_event_apply_context"]["source_system"] for e in events
    ] == ["espocrm", "spreadsheet"]

    # Same tables, same lifecycle entry, regardless of origin.
    with session_scope() as s:
        assert {
            e["entity_status"] for e in entity_repo.list_entities(s)
        } == {"candidate"}
        assert {
            f["field_status"] for f in field_repo.list_fields(s)
        } == {"candidate"}

    # One WTK-088 latest-snapshot read serves both sources at once,
    # one row per (subject, source) — no source-specific branching.
    latest = _evidence_rows(latest=True)
    by_label: dict[str, int] = {}
    seen: set[tuple[str, str, str]] = set()
    for row in latest:
        by_label[row["evidence_source_label"]] = (
            by_label.get(row["evidence_source_label"], 0) + 1
        )
        key = (
            row["evidence_subject_type"],
            row["evidence_subject_identifier"],
            row["evidence_source_label"],
        )
        assert key not in seen
        seen.add(key)
    assert by_label[ESPOCRM_LABEL] == espocrm["evidence_rows"]
    assert by_label[SPREADSHEET_LABEL] == sheet["evidence_rows"]

    # The Q1 low-population triage read runs unmodified over the mixed
    # DB and surfaces the spreadsheet-born sparse column (§5.5).
    sparse = _evidence_rows(max_population_rate=0.5)
    with session_scope() as s:
        names = {
            f["field_identifier"]: f["field_name"]
            for f in field_repo.list_fields(s)
        }
    assert {
        names[row["evidence_subject_identifier"]] for row in sparse
    } == {"Notes"}
    assert {r["evidence_source_label"] for r in sparse} == {
        SPREADSHEET_LABEL
    }
