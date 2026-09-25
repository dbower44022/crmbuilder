"""The PRJ-128 migration run — PI-579 (REQ-653, DEC-1175, DEC-1176..DEC-1182).

Carries out the approved engagement migration mapping
(``PRDs/product/crmbuilder-v2/engagement-migration-mapping.md``, revision
1.0) once, as data: the seven engagements become applications or archived
rows, every existing instance becomes a deployment under the application it
installs, the Rochester and Boston instances, configurations, credentials
and run history are re-homed under the Cleveland application for two new
client records, and Rochester's copied design is archived after a comparison
confirms it matches Cleveland's.

Two entry points share one code path:

* the Alembic revision ``operate_0005_prj128_migration_run`` calls
  :func:`run` on its connection, so the store head records that it ran and
  the production rollout applies it in the deploy script's migrate step;
* ``python -m crmbuilder_v2.segments.operate.prj128_migration`` runs the same
  code against a named database URL for the rehearsal on a copy of
  production (LSN-062), printing the comparison and every row it moved.

The comparison is the method of section 5 of the mapping: one-directional,
every copied record accounted for in Cleveland's live design; entities,
roles and teams by name; fields by entity name plus field name ignoring
letter case; associations by source, target and name; layouts by entity
plus layout type; compared attributes equal, or differing only in the way
DEC-1181 accepted (five fields typed ``file`` or ``money`` on the server
where the design says ``text``). Anything else stops the run before a row
moves. Everything here is plain SQL over the connection it is given, so it
behaves the same under Alembic and under the rehearsal.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

Log = Callable[[str], None]

MAPPING_DOCUMENT = Path("PRDs/product/crmbuilder-v2/engagement-migration-mapping.md")

# The approved mapping, one entry per engagement (rows 1 to 7). The decision
# identifiers are the ones the document's section 7 names; the test
# ``test_mapping_matches_the_document`` keeps the two in step.
MAPPING: dict[str, dict[str, Any]] = {
    "ENG-001": {
        "row": 1,
        "decision": "DEC-1176",
        "becomes": "application",
        "client": "CLI-002",
    },
    "ENG-002": {
        "row": 2,
        "decision": "DEC-1177",
        "becomes": "application",
        "client": "CLI-001",
    },
    "ENG-003": {
        "row": 3,
        "decision": "DEC-1178",
        "becomes": "archived",
        "client": "CLI-002",
    },
    "ENG-004": {
        "row": 4,
        "decision": "DEC-1179",
        "becomes": "application",
        "client": "CLI-001",
    },
    "ENG-005": {
        "row": 5,
        "decision": "DEC-1180",
        "becomes": "archived",
        "client": "CLI-002",
    },
    "ENG-006": {
        "row": 6,
        "decision": "DEC-1181",
        "becomes": "deployment",
        "of_application": "ENG-002",
        "new_client_name": "Rochester Business Mentors",
        "archive_design": True,
    },
    "ENG-007": {
        "row": 7,
        "decision": "DEC-1182",
        "becomes": "deployment",
        "of_application": "ENG-002",
        "new_client_name": "Boston Business Mentors",
        "archive_design": False,
    },
}

# DEC-1181 ruling 4: the five type differences that do not stop the archive.
# (entity name, field name, type in the copy, type in Cleveland's design)
ACCEPTED_TYPE_DIFFERENCES: frozenset[tuple[str, str, str, str]] = frozenset(
    {
        ("Account", "annualPledgeAmountConverted", "money", "text"),
        ("Event", "eventGraphic", "file", "text"),
        ("Event", "sponsorGraphic", "file", "text"),
        ("MentorProfile", "profilePhoto", "file", "text"),
        ("MentorProfile", "resumeUpload", "file", "text"),
    }
)

_SOURCE = "ENG-006"  # the copy
_TARGET = "ENG-002"  # Cleveland's live design and the application everything joins


class MigrationStop(RuntimeError):
    """The run refuses to move anything; the message says why."""


# ---------------------------------------------------------------------------
# Reading helpers
# ---------------------------------------------------------------------------


def _rows(conn: Connection, sql: str, **params) -> list[dict]:
    return [dict(r._mapping) for r in conn.execute(text(sql), params)]


def _scalar(conn: Connection, sql: str, **params):
    return conn.execute(text(sql), params).scalar()


def _table_names(conn: Connection) -> set[str]:
    from sqlalchemy import inspect

    return set(inspect(conn).get_table_names())


def _next_identifier(existing: list[str], prefix: str) -> str:
    numbers = [
        int(x.split("-")[1]) for x in existing if x and x.startswith(prefix + "-")
    ]
    return f"{prefix}-{(max(numbers) + 1) if numbers else 1:03d}"


def read_mapping_decisions(path: Path = MAPPING_DOCUMENT) -> dict[str, str]:
    """The engagement-to-decision table of section 7 of the mapping document,
    read so a test can check :data:`MAPPING` against the approved text."""
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*\d\s*\|\s*(ENG-\d{3})\s*\|\s*(DEC-\d{3,})\s*\|", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


# ---------------------------------------------------------------------------
# The Rochester comparison (mapping section 5, DEC-1181)
# ---------------------------------------------------------------------------


def _live_entities(conn: Connection, eng: str) -> dict[str, dict]:
    return {
        r["entity_name"]: r
        for r in _rows(
            conn,
            "SELECT * FROM entities WHERE engagement_id = :e AND entity_deleted_at IS NULL",
            e=eng,
        )
    }


def _live_fields(conn: Connection, eng: str) -> dict[tuple[str, str], dict]:
    """Live fields keyed by (entity name, lower-cased field name), with the
    entity name resolved through the field_belongs_to_entity reference."""
    rows = _rows(
        conn,
        """
        SELECT f.*, e.entity_name AS _entity_name
        FROM fields f
        JOIN refs r ON r.engagement_id = f.engagement_id AND r.source_type = 'field'
             AND r.source_id = f.field_identifier AND r.target_type = 'entity'
             AND r.relationship_kind = 'field_belongs_to_entity'
        JOIN entities e ON e.engagement_id = r.engagement_id
             AND e.entity_identifier = r.target_id
        WHERE f.engagement_id = :e AND f.field_deleted_at IS NULL
        """,
        e=eng,
    )
    return {(r["_entity_name"], r["field_name"].lower()): r for r in rows}


def _field_options(conn: Connection, eng: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for r in _rows(
        conn,
        "SELECT field_identifier, option_value FROM field_options WHERE engagement_id = :e",
        e=eng,
    ):
        out.setdefault(r["field_identifier"], set()).add(str(r["option_value"]))
    return out


def _entity_name_of(
    conn: Connection, eng: str, value: str | None, names: dict[str, str]
) -> str | None:
    """Associations name their ends either by entity identifier or by name;
    resolve to a name either way."""
    if value is None:
        return None
    if value.startswith("ENT-"):
        return names.get(value)
    return value


def _entity_names_by_identifier(conn: Connection, eng: str) -> dict[str, str]:
    return {
        r["entity_identifier"]: r["entity_name"]
        for r in _rows(
            conn,
            "SELECT entity_identifier, entity_name FROM entities WHERE engagement_id = :e",
            e=eng,
        )
    }


def _equal(a, b) -> bool:
    if isinstance(a, str) and isinstance(b, str):
        return a.strip() == b.strip()
    if isinstance(a, (dict, list)) or isinstance(b, (dict, list)):
        return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    return a == b


_ENTITY_ATTRIBUTES = (
    "entity_label",
    "entity_label_plural",
    "entity_default_sort_field",
    "entity_default_sort_direction",
    "entity_track_activity",
)
_FIELD_ATTRIBUTES = (
    "field_required",
    "field_unique",
    "field_max_length",
    "field_read_only",
)
_ASSOCIATION_ATTRIBUTES = ("association_cardinality",)
_ROLE_ATTRIBUTES = ("role_scope_access", "role_system_permissions")


def compare_rochester(
    conn: Connection,
    *,
    source: str = _SOURCE,
    target: str = _TARGET,
    accepted: frozenset[tuple[str, str, str, str]] = ACCEPTED_TYPE_DIFFERENCES,
) -> dict[str, Any]:
    """Compare the copied design under ``source`` with the live design under
    ``target``. Returns a report; ``report["passes"]`` says whether the archive
    may proceed and ``report["stops"]`` lists every reason it may not."""
    report: dict[str, Any] = {
        "source": source,
        "target": target,
        "stops": [],
        "attribute_differences": [],
    }
    # Structural differences (a copied record with no counterpart, a type
    # difference DEC-1181 did not accept) always stop the run. Attribute
    # differences on matched records are listed separately: the copy is
    # retained soft-deleted, so nothing is lost by archiving it, and whether
    # they stop the run is the ruling ``accept_attribute_differences`` carries.
    stops: list[str] = report["stops"]
    attribute_stops: list[str] = report["attribute_differences"]

    src_entities = _live_entities(conn, source)
    tgt_entities = _live_entities(conn, target)
    entity_unmatched = sorted(set(src_entities) - set(tgt_entities))
    entity_attr_diffs = []
    for name, s_row in src_entities.items():
        t_row = tgt_entities.get(name)
        if t_row is None:
            continue
        for attr in _ENTITY_ATTRIBUTES:
            if not _equal(s_row.get(attr), t_row.get(attr)):
                entity_attr_diffs.append((name, attr, s_row.get(attr), t_row.get(attr)))
    report["entities"] = {
        "total": len(src_entities),
        "matched": len(src_entities) - len(entity_unmatched),
        "unmatched": entity_unmatched,
        "attribute_differences": entity_attr_diffs,
    }
    if entity_unmatched:
        stops.append(
            f"{len(entity_unmatched)} copied entities have no match by name: {entity_unmatched}"
        )

    src_fields = _live_fields(conn, source)
    tgt_fields = _live_fields(conn, target)
    src_options = _field_options(conn, source)
    tgt_options = _field_options(conn, target)
    (
        excluded_builtin,
        unmatched,
        type_diffs_accepted,
        type_diffs_unaccepted,
        attr_diffs,
        option_diffs,
    ) = ([], [], [], [], [], [])
    for key, s_row in src_fields.items():
        t_row = tgt_fields.get(key)
        if t_row is None:
            if s_row.get("field_built_in"):
                excluded_builtin.append(f"{key[0]}.{s_row['field_name']}")
            else:
                unmatched.append(f"{key[0]}.{s_row['field_name']}")
            continue
        if s_row["field_type"] != t_row["field_type"]:
            quad = (
                key[0],
                s_row["field_name"],
                s_row["field_type"],
                t_row["field_type"],
            )
            (type_diffs_accepted if quad in accepted else type_diffs_unaccepted).append(
                quad
            )
        for attr in _FIELD_ATTRIBUTES:
            if not _equal(s_row.get(attr), t_row.get(attr)):
                attr_diffs.append(
                    (
                        f"{key[0]}.{s_row['field_name']}",
                        attr,
                        s_row.get(attr),
                        t_row.get(attr),
                    )
                )
        s_opts = src_options.get(s_row["field_identifier"], set())
        t_opts = tgt_options.get(t_row["field_identifier"], set())
        if s_opts and s_opts != t_opts:
            option_diffs.append(
                (
                    f"{key[0]}.{s_row['field_name']}",
                    sorted(s_opts - t_opts),
                    sorted(t_opts - s_opts),
                )
            )
    report["fields"] = {
        "total": len(src_fields),
        "matched_by_name": len(src_fields) - len(unmatched) - len(excluded_builtin),
        "excluded_built_in": excluded_builtin,
        "unmatched": unmatched,
        "type_differences_accepted": type_diffs_accepted,
        "type_differences_unaccepted": type_diffs_unaccepted,
        "attribute_differences": attr_diffs,
        "option_differences": option_diffs,
    }
    if unmatched:
        stops.append(
            f"{len(unmatched)} copied fields have no match by name: {unmatched}"
        )
    if type_diffs_unaccepted:
        stops.append(
            f"{len(type_diffs_unaccepted)} field type differences are not accepted: {type_diffs_unaccepted}"
        )
    if attr_diffs:
        attribute_stops.append(
            f"{len(attr_diffs)} field attribute differences: {attr_diffs[:20]}"
        )
    if option_diffs:
        attribute_stops.append(
            f"{len(option_diffs)} field option-set differences: {option_diffs[:20]}"
        )
    if entity_attr_diffs:
        attribute_stops.append(
            f"{len(entity_attr_diffs)} entity attribute differences: {entity_attr_diffs[:20]}"
        )

    def by_name(table: str, name_col: str, attrs: tuple[str, ...], deleted_col: str):
        s_rows = {
            r[name_col]: r
            for r in _rows(
                conn,
                f"SELECT * FROM {table} WHERE engagement_id = :e AND {deleted_col} IS NULL",
                e=source,
            )
        }
        t_rows = {
            r[name_col]: r
            for r in _rows(
                conn,
                f"SELECT * FROM {table} WHERE engagement_id = :e AND {deleted_col} IS NULL",
                e=target,
            )
        }
        missing = sorted(set(s_rows) - set(t_rows))
        diffs = [
            (n, a, s_rows[n].get(a), t_rows[n].get(a))
            for n in s_rows
            if n in t_rows
            for a in attrs
            if not _equal(s_rows[n].get(a), t_rows[n].get(a))
        ]
        return {
            "total": len(s_rows),
            "matched": len(s_rows) - len(missing),
            "unmatched": missing,
            "attribute_differences": diffs,
        }

    report["roles"] = by_name("roles", "role_name", _ROLE_ATTRIBUTES, "role_deleted_at")
    report["teams"] = by_name("teams", "team_name", (), "team_deleted_at")
    for kind in ("roles", "teams"):
        if report[kind]["unmatched"]:
            stops.append(f"{kind}: no match by name for {report[kind]['unmatched']}")
        if report[kind]["attribute_differences"]:
            attribute_stops.append(
                f"{kind}: {len(report[kind]['attribute_differences'])} attribute differences: {report[kind]['attribute_differences'][:20]}"
            )

    s_names = _entity_names_by_identifier(conn, source)
    t_names = _entity_names_by_identifier(conn, target)

    def assoc_key(r, names):
        return (
            _entity_name_of(conn, None, r["association_source_entity"], names),
            _entity_name_of(conn, None, r["association_target_entity"], names),
            r["association_name"],
        )

    s_assoc = {
        assoc_key(r, s_names): r
        for r in _rows(
            conn,
            "SELECT * FROM associations WHERE engagement_id = :e AND association_deleted_at IS NULL",
            e=source,
        )
    }
    t_assoc = {
        assoc_key(r, t_names): r
        for r in _rows(
            conn,
            "SELECT * FROM associations WHERE engagement_id = :e AND association_deleted_at IS NULL",
            e=target,
        )
    }
    a_missing = sorted(k for k in s_assoc if k not in t_assoc)
    a_diffs = [
        (k, a, s_assoc[k].get(a), t_assoc[k].get(a))
        for k in s_assoc
        if k in t_assoc
        for a in _ASSOCIATION_ATTRIBUTES
        if not _equal(s_assoc[k].get(a), t_assoc[k].get(a))
    ]
    report["associations"] = {
        "total": len(s_assoc),
        "matched": len(s_assoc) - len(a_missing),
        "unmatched": a_missing,
        "attribute_differences": a_diffs,
    }
    if a_missing:
        stops.append(
            f"{len(a_missing)} copied associations have no match: {a_missing[:20]}"
        )
    if a_diffs:
        attribute_stops.append(
            f"{len(a_diffs)} association attribute differences: {a_diffs[:20]}"
        )

    def layouts(eng, names):
        return {
            (names.get(r["layout_entity_identifier"]), r["layout_type"]): r
            for r in _rows(
                conn,
                "SELECT * FROM layouts WHERE engagement_id = :e AND layout_deleted_at IS NULL",
                e=eng,
            )
        }

    s_lay = layouts(source, s_names)
    t_lay = layouts(target, t_names)
    l_missing = sorted(k for k in s_lay if k not in t_lay)
    l_diffs = [
        k
        for k in s_lay
        if k in t_lay
        and not _equal(s_lay[k].get("layout_content"), t_lay[k].get("layout_content"))
    ]
    report["layouts"] = {
        "total": len(s_lay),
        "matched": len(s_lay) - len(l_missing),
        "unmatched": l_missing,
        "content_differences": l_diffs,
    }
    if l_missing:
        stops.append(f"{len(l_missing)} copied layouts have no match: {l_missing[:20]}")
    if l_diffs:
        attribute_stops.append(
            f"{len(l_diffs)} layout content differences: {l_diffs[:20]}"
        )

    report["structurally_matches"] = not stops
    report["passes"] = not stops and not attribute_stops
    return report


def summary(report: dict[str, Any]) -> dict[str, Any]:
    """The comparison in counts, for a log line or a decision record."""
    out: dict[str, Any] = {
        "structurally_matches": report.get("structurally_matches"),
        "passes": report.get("passes"),
    }
    for kind in ("entities", "fields", "roles", "teams", "associations", "layouts"):
        v = report.get(kind) or {}
        out[kind] = {k: (len(x) if isinstance(x, list) else x) for k, x in v.items()}
    out["stops"] = list(report.get("stops", []))
    out["attribute_differences"] = list(report.get("attribute_differences", []))
    return out


# ---------------------------------------------------------------------------
# Preconditions and census
# ---------------------------------------------------------------------------


def census(conn: Connection) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["engagements"] = {
        r["engagement_identifier"]: r["engagement_status"]
        for r in _rows(
            conn,
            "SELECT engagement_identifier, engagement_status FROM engagements ORDER BY 1",
        )
    }
    out["clients"] = {
        r["client_identifier"]: r["client_name"]
        for r in _rows(
            conn, "SELECT client_identifier, client_name FROM clients ORDER BY 1"
        )
    }
    out["holdings"] = _rows(
        conn,
        "SELECT engagement_id, client_id, is_primary FROM engagement_clients ORDER BY 1, 2",
    )
    out["instances"] = _rows(
        conn,
        "SELECT engagement_id, instance_identifier, instance_name FROM instances ORDER BY 1, 2",
    )
    out["deployments"] = (
        _rows(
            conn,
            "SELECT deployment_identifier, deployment_application, deployment_client, deployment_instance_identifier, deployment_purpose FROM deployments ORDER BY 1",
        )
        if "deployments" in _table_names(conn)
        else []
    )
    out["credentials"] = _rows(
        conn,
        "SELECT engagement_id, provider, label, deployment_identifier FROM provider_credentials ORDER BY 1, 2",
    )
    out["deploy_runs"] = _rows(
        conn,
        "SELECT engagement_id, deploy_run_identifier, instance_identifier, deploy_run_status, deployment_identifier FROM deploy_runs ORDER BY engagement_id, id",
    )
    out["memberships"] = _rows(
        conn,
        "SELECT engagement_id, instance_identifier, COUNT(*) AS n FROM instance_memberships GROUP BY 1, 2 ORDER BY 1, 2",
    )
    out["role_assignments"] = _rows(
        conn,
        "SELECT principal_id, engagement_id, role FROM role_assignments ORDER BY 1, 2",
    )
    return out


def applicable(conn: Connection) -> tuple[bool, str]:
    """Whether this store is the one the mapping describes and the run has
    not been applied yet. A fresh database, or one already migrated, is
    passed through untouched."""
    tables = _table_names(conn)
    if "deployments" not in tables:
        return False, "no deployments table"
    engs = {
        r["engagement_identifier"]
        for r in _rows(conn, "SELECT engagement_identifier FROM engagements")
    }
    if not {"ENG-002", "ENG-006", "ENG-007"} <= engs:
        return (
            False,
            "the seven mapped engagements are not present (fresh or other store)",
        )
    if _scalar(
        conn,
        "SELECT COUNT(*) FROM deployments WHERE deployment_application = 'ENG-002'",
    ):
        return False, "already applied: ENG-002 has deployments"
    return True, "applicable"


def _preconditions(conn: Connection) -> None:
    insts = {
        (r["engagement_id"], r["instance_identifier"])
        for r in _rows(
            conn,
            "SELECT engagement_id, instance_identifier FROM instances WHERE engagement_id IN ('ENG-002','ENG-006','ENG-007')",
        )
    }
    expected = {
        ("ENG-002", "INST-001"),
        ("ENG-002", "INST-002"),
        ("ENG-006", "INST-001"),
        ("ENG-007", "INST-001"),
    }
    if insts != expected:
        raise MigrationStop(
            f"instances differ from the mapping's verified state: {sorted(insts)}"
        )
    clients = {
        r["client_identifier"]
        for r in _rows(
            conn,
            "SELECT client_identifier FROM clients WHERE client_deleted_at IS NULL",
        )
    }
    if not {"CLI-001", "CLI-002"} <= clients:
        raise MigrationStop("CLI-001 and CLI-002 must exist")
    primary = _scalar(
        conn,
        "SELECT client_id FROM engagement_clients WHERE engagement_id = 'ENG-002' AND is_primary",
    )
    if primary != "CLI-001":
        raise MigrationStop(
            f"ENG-002's defining client is {primary!r}, expected CLI-001"
        )
    grants = _rows(
        conn,
        "SELECT principal_id, engagement_id, role FROM role_assignments WHERE engagement_id IN ('ENG-006','ENG-007')",
    )
    if grants:
        # Mapping section 6: never widen access silently.
        raise MigrationStop(
            f"role assignments exist on an engagement that becomes a deployment; decide them by hand first: {grants}"
        )


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def _ensure_client(conn: Connection, name: str, now: datetime, log: Log) -> str:
    existing = _scalar(
        conn,
        "SELECT client_identifier FROM clients WHERE LOWER(client_name) = LOWER(:n)",
        n=name,
    )
    if existing:
        log(f"client {existing} {name!r} already exists")
        return existing
    ident = _next_identifier(
        [
            r["client_identifier"]
            for r in _rows(conn, "SELECT client_identifier FROM clients")
        ],
        "CLI",
    )
    conn.execute(
        text(
            "INSERT INTO clients (client_identifier, client_name, client_status, client_notes, "
            "client_created_at, client_updated_at) VALUES (:i, :n, 'active', :notes, :now, :now)"
        ),
        {
            "i": ident,
            "n": name,
            "notes": "Created by the PRJ-128 migration run (PI-579) from the approved mapping.",
            "now": now,
        },
    )
    log(f"created client {ident} {name!r}")
    return ident


def _set_engagement_status(conn: Connection, eng: str, status: str, log: Log) -> None:
    conn.execute(
        text(
            "UPDATE engagements SET engagement_status = :s, engagement_updated_at = :now WHERE engagement_identifier = :e"
        ),
        {"s": status, "e": eng, "now": datetime.now(UTC)},
    )
    log(f"{eng}: status -> {status}")


def _ensure_holding(
    conn: Connection, eng: str, client: str, now: datetime, log: Log
) -> None:
    if _scalar(
        conn,
        "SELECT COUNT(*) FROM engagement_clients WHERE engagement_id = :e AND client_id = :c",
        e=eng,
        c=client,
    ):
        return
    conn.execute(
        text(
            "INSERT INTO engagement_clients (engagement_id, client_id, is_primary, created_at) VALUES (:e, :c, :p, :now)"
        ),
        {"e": eng, "c": client, "p": True, "now": now},
    )
    log(f"{eng}: defining client -> {client}")


def _change_log(
    conn: Connection,
    eng: str,
    entity_type: str,
    identifier: str,
    before: dict,
    after: dict,
    now: datetime,
) -> None:
    conn.execute(
        text(
            "INSERT INTO change_log (timestamp, entity_type, entity_identifier, operation, actor, "
            "before_payload, after_payload, engagement_id) VALUES (:ts, :t, :i, 'update', 'migration', :b, :a, :e)"
        ),
        {
            "ts": now,
            "t": entity_type,
            "i": identifier,
            "b": json.dumps(before),
            "a": json.dumps(after),
            "e": eng,
        },
    )


def _member_translation(
    conn: Connection, source: str, target: str
) -> dict[tuple[str, str], str]:
    """(member_type, source identifier) -> target identifier, by the match
    keys of the comparison. Unmapped members are left where they are."""
    out: dict[tuple[str, str], str] = {}
    s_names = _entity_names_by_identifier(conn, source)
    t_by_name = {
        v: k
        for k, v in _entity_names_by_identifier(conn, target).items()
        if k
        in {
            r["entity_identifier"]
            for r in _rows(
                conn,
                "SELECT entity_identifier FROM entities WHERE engagement_id = :e AND entity_deleted_at IS NULL",
                e=target,
            )
        }
    }
    for sid, name in s_names.items():
        if name in t_by_name:
            out[("entity", sid)] = t_by_name[name]
    s_fields = _live_fields(conn, source)
    t_fields = _live_fields(conn, target)
    for key, row in s_fields.items():
        if key in t_fields:
            out[("field", row["field_identifier"])] = t_fields[key]["field_identifier"]
    for table, col, kind in (
        ("roles", "role_name", "role"),
        ("teams", "team_name", "team"),
    ):
        ident_col = f"{kind}_identifier"
        t_map = {
            r[col]: r[ident_col]
            for r in _rows(
                conn,
                f"SELECT {col}, {ident_col} FROM {table} WHERE engagement_id = :e AND {kind}_deleted_at IS NULL",
                e=target,
            )
        }
        for r in _rows(
            conn,
            f"SELECT {col}, {ident_col} FROM {table} WHERE engagement_id = :e",
            e=source,
        ):
            if r[col] in t_map:
                out[(kind, r[ident_col])] = t_map[r[col]]
    t_names = _entity_names_by_identifier(conn, target)
    t_lay = {
        (t_names.get(r["layout_entity_identifier"]), r["layout_type"]): r[
            "layout_identifier"
        ]
        for r in _rows(
            conn,
            "SELECT layout_identifier, layout_entity_identifier, layout_type FROM layouts WHERE engagement_id = :e AND layout_deleted_at IS NULL",
            e=target,
        )
    }
    for r in _rows(
        conn,
        "SELECT layout_identifier, layout_entity_identifier, layout_type FROM layouts WHERE engagement_id = :e",
        e=source,
    ):
        key = (s_names.get(r["layout_entity_identifier"]), r["layout_type"])
        if key in t_lay:
            out[("layout", r["layout_identifier"])] = t_lay[key]
    t_assoc = {
        (
            _entity_name_of(conn, None, r["association_source_entity"], t_names),
            _entity_name_of(conn, None, r["association_target_entity"], t_names),
            r["association_name"],
        ): r["association_identifier"]
        for r in _rows(
            conn,
            "SELECT * FROM associations WHERE engagement_id = :e AND association_deleted_at IS NULL",
            e=target,
        )
    }
    for r in _rows(
        conn, "SELECT * FROM associations WHERE engagement_id = :e", e=source
    ):
        key = (
            _entity_name_of(conn, None, r["association_source_entity"], s_names),
            _entity_name_of(conn, None, r["association_target_entity"], s_names),
            r["association_name"],
        )
        if key in t_assoc:
            out[("association", r["association_identifier"])] = t_assoc[key]
    return out


def _move_instance(
    conn: Connection,
    source: str,
    target: str,
    old: str,
    new: str,
    now: datetime,
    log: Log,
    *,
    translate_members: bool,
) -> dict[str, int]:
    """Re-home instance ``old`` of ``source`` as ``new`` of ``target`` with its
    deploy configuration and memberships; returns counts per table."""
    counts: dict[str, int] = {}
    before = _rows(
        conn,
        "SELECT * FROM instances WHERE engagement_id = :e AND instance_identifier = :i",
        e=source,
        i=old,
    )[0]
    # The instance's composite key is referenced by its configuration and
    # memberships without ON UPDATE, so the row is copied under the new key,
    # the children re-pointed, and the old row retained soft-deleted; the change
    # log below records the move.
    new_row = dict(before)
    new_row["engagement_id"] = target
    new_row["instance_identifier"] = new
    new_row["instance_updated_at"] = now
    if new_row.get("instance_notes"):
        new_row["instance_notes"] = new_row["instance_notes"].replace(
            f"({old})", f"({new})"
        )
    if isinstance(new_row.get("instance_feature_selection"), (list, dict)):
        new_row["instance_feature_selection"] = json.dumps(
            new_row["instance_feature_selection"]
        )
    cols = ", ".join(new_row)
    params = ", ".join(f":{c}" for c in new_row)
    conn.execute(text(f"INSERT INTO instances ({cols}) VALUES ({params})"), new_row)
    counts["instances"] = 1
    counts["instance_deploy_configs"] = conn.execute(
        text(
            "UPDATE instance_deploy_configs SET engagement_id = :t, instance_identifier = :n WHERE engagement_id = :s AND instance_identifier = :o"
        ),
        {"t": target, "n": new, "s": source, "o": old},
    ).rowcount
    if translate_members:
        mapping = _member_translation(conn, source, target)
        members = _rows(
            conn,
            "SELECT id, member_type, member_identifier FROM instance_memberships WHERE engagement_id = :s AND instance_identifier = :o",
            s=source,
            o=old,
        )
        moved = 0
        for m in members:
            new_member = mapping.get((m["member_type"], m["member_identifier"]))
            if new_member is None:
                continue
            conn.execute(
                text(
                    "UPDATE instance_memberships SET engagement_id = :t, instance_identifier = :n, member_identifier = :mid WHERE id = :id"
                ),
                {"t": target, "n": new, "mid": new_member, "id": m["id"]},
            )
            moved += 1
        counts["instance_memberships"] = moved
        counts["instance_memberships_left_with_the_copy"] = len(members) - moved
    else:
        counts["instance_memberships"] = conn.execute(
            text(
                "UPDATE instance_memberships SET engagement_id = :t, instance_identifier = :n WHERE engagement_id = :s AND instance_identifier = :o"
            ),
            {"t": target, "n": new, "s": source, "o": old},
        ).rowcount
    for table in (
        "system_setting_values",
        "conformance_overrides",
        "publish_runs",
        "audit_runs",
        "source_mappings",
        "association_mappings",
        "mapping_candidates",
    ):
        if table in _table_names(conn):
            counts[table] = conn.execute(
                text(
                    f"UPDATE {table} SET engagement_id = :t, instance_identifier = :n WHERE engagement_id = :s AND instance_identifier = :o"
                ),
                {"t": target, "n": new, "s": source, "o": old},
            ).rowcount
    # The old row is retained, soft-deleted, under the archived engagement
    # (retain-not-delete): a hard delete would cascade away the membership
    # rows that could not be translated and stay with the archived copy.
    conn.execute(
        text(
            "UPDATE instances SET instance_deleted_at = :now, instance_status = 'disabled', "
            "instance_notes = COALESCE(instance_notes, '') || :note "
            "WHERE engagement_id = :s AND instance_identifier = :o"
        ),
        {
            "now": now,
            "note": f" Moved to {target}/{new} by the PRJ-128 migration run (PI-579); this row is retained.",
            "s": source,
            "o": old,
        },
    )
    after = _rows(
        conn,
        "SELECT * FROM instances WHERE engagement_id = :e AND instance_identifier = :i",
        e=target,
        i=new,
    )[0]
    _change_log(
        conn,
        target,
        "instance",
        new,
        {
            "engagement_id": source,
            "instance_identifier": old,
            "instance_name": before["instance_name"],
        },
        {
            "engagement_id": target,
            "instance_identifier": new,
            "instance_name": after["instance_name"],
            "moved_by": "PRJ-128 migration run (PI-579)",
        },
        now,
    )
    log(
        f"moved {source}/{old} -> {target}/{new}: "
        + ", ".join(f"{k}={v}" for k, v in counts.items() if v)
    )
    return counts


def _move_deploy_runs(
    conn: Connection,
    source: str,
    target: str,
    old_instance: str,
    new_instance: str,
    deployment: str,
    log: Log,
) -> list[tuple[str, str]]:
    """Re-home a source engagement's deploy runs under the target with fresh
    DEP identifiers, pointing them at the deployment and the renumbered instance."""
    # Loading the models registers every table on the metadata (the CLI
    # path imports nothing else); the Core table binds the JSON column
    # correctly on both Postgres and SQLite.
    from crmbuilder_v2.access import models as _models  # noqa: F401
    from crmbuilder_v2.access.base import Base

    runs_table = Base.metadata.tables["deploy_runs"]
    runs = _rows(
        conn,
        "SELECT id, deploy_run_identifier, instance_identifier, deploy_run_state FROM deploy_runs WHERE engagement_id = :s ORDER BY id",
        s=source,
    )
    renamed: list[tuple[str, str]] = []
    for r in runs:
        existing = [
            x["deploy_run_identifier"]
            for x in _rows(
                conn,
                "SELECT deploy_run_identifier FROM deploy_runs WHERE engagement_id = :t",
                t=target,
            )
        ]
        new_id = _next_identifier(existing, "DEP")
        state = r["deploy_run_state"]
        if isinstance(state, str):
            state = json.loads(state)
        if isinstance(state, dict) and state.get("instance_identifier") == old_instance:
            state = {**state, "instance_identifier": new_instance}
        values = {
            "engagement_id": target,
            "deploy_run_identifier": new_id,
            "deployment_identifier": deployment,
            "instance_identifier": new_instance
            if r["instance_identifier"] == old_instance
            else r["instance_identifier"],
            "deploy_run_state": state,
        }
        conn.execute(
            runs_table.update().where(runs_table.c.id == r["id"]).values(**values)
        )
        renamed.append((r["deploy_run_identifier"], new_id))
        log(
            f"deploy run {source}/{r['deploy_run_identifier']} -> {target}/{new_id} (deployment {deployment})"
        )
    for old_id, new_id in renamed:
        conn.execute(
            text(
                "UPDATE instance_deploy_configs SET last_deploy_run_identifier = :n WHERE engagement_id = :t AND instance_identifier = :i AND last_deploy_run_identifier = :o"
            ),
            {"n": new_id, "t": target, "i": new_instance, "o": old_id},
        )
        conn.execute(
            text(
                "UPDATE instances SET instance_notes = REPLACE(instance_notes, :o, :n) WHERE engagement_id = :t AND instance_identifier = :i AND instance_notes LIKE :like"
            ),
            {
                "o": f"deploy run {old_id}",
                "n": f"deploy run {new_id}",
                "t": target,
                "i": new_instance,
                "like": f"%deploy run {old_id}%",
            },
        )
    return renamed


def _create_deployment(
    conn: Connection,
    *,
    application: str,
    client: str,
    instance: str,
    name: str,
    now: datetime,
    log: Log,
    notes: str,
) -> str:
    ident = _next_identifier(
        [
            r["deployment_identifier"]
            for r in _rows(conn, "SELECT deployment_identifier FROM deployments")
        ],
        "DPL",
    )
    conn.execute(
        text(
            "INSERT INTO deployments (deployment_identifier, deployment_application, deployment_client, "
            "deployment_hosting_provider, deployment_name, deployment_status, deployment_purpose, "
            "deployment_instance_identifier, deployment_notes, deployment_created_at, deployment_updated_at) "
            "VALUES (:i, :a, :c, 'digitalocean', :n, 'active', 'client_own', :inst, :notes, :now, :now)"
        ),
        {
            "i": ident,
            "a": application,
            "c": client,
            "n": name,
            "inst": instance,
            "notes": notes,
            "now": now,
        },
    )
    log(
        f"created deployment {ident}: {name!r} of {application} for {client}, holding {instance}"
    )
    return ident


def _move_credentials(
    conn: Connection, source: str, target: str, deployment: str, log: Log
) -> int:
    n = conn.execute(
        text(
            "UPDATE provider_credentials SET engagement_id = :t, deployment_identifier = :d WHERE engagement_id = :s"
        ),
        {"t": target, "d": deployment, "s": source},
    ).rowcount
    log(
        f"moved {n} provider credential(s) from {source} to {target} as {deployment}'s own"
    )
    return n


def _archive_design(
    conn: Connection, eng: str, now: datetime, log: Log
) -> dict[str, int]:
    note = f" Archived by the PRJ-128 migration run (PI-579, DEC-1181) on {now.date().isoformat()}: a copy of the Cleveland design captured from the Rochester server on 2026-08-31, matched against ENG-002 and retained."
    counts = {}
    for table, prefix in (
        ("entities", "entity"),
        ("fields", "field"),
        ("associations", "association"),
        ("layouts", "layout"),
        ("roles", "role"),
        ("teams", "team"),
    ):
        counts[table] = conn.execute(
            text(
                f"UPDATE {table} SET {prefix}_deleted_at = :now, {prefix}_notes = COALESCE({prefix}_notes, '') || :note WHERE engagement_id = :e AND {prefix}_deleted_at IS NULL"
            ),
            {"now": now, "note": note, "e": eng},
        ).rowcount
    log(
        f"archived {eng}'s copied design: "
        + ", ".join(f"{k}={v}" for k, v in counts.items())
    )
    return counts


def run(
    conn: Connection,
    *,
    log: Log = print,
    now: datetime | None = None,
    accept_attribute_differences: bool = False,
    force_dry_run: bool = False,
) -> dict[str, Any]:
    """Apply the mapping to the store behind ``conn`` inside the caller's
    transaction. Raises :class:`MigrationStop` before anything moves when a
    precondition does not hold, when the copy does not structurally match
    Cleveland's design, or when it differs in attributes and
    ``accept_attribute_differences`` is not given (DEC-1181's strict reading,
    which only a ruling relaxes). ``force_dry_run`` carries on past a
    comparison stop so a rehearsal can exercise the moves on a copy; the
    caller must roll back.
    """
    now = now or datetime.now(UTC)
    ok, why = applicable(conn)
    if not ok:
        log(f"PRJ-128 migration run: nothing to do ({why})")
        return {"applied": False, "reason": why}
    _preconditions(conn)
    report = compare_rochester(conn)
    log("Rochester comparison: " + json.dumps(summary(report), default=str))
    if not report["structurally_matches"] and not force_dry_run:
        raise MigrationStop(
            "the Rochester copy does not structurally match Cleveland's design; "
            "nothing moved. Stops: " + " | ".join(report["stops"])
        )
    if not report["passes"] and not accept_attribute_differences and not force_dry_run:
        raise MigrationStop(
            "the Rochester copy matches Cleveland's design record for record but "
            "differs in attributes on matched records; under DEC-1181 that stops "
            "the run until it is ruled on. Nothing moved. Differences: "
            + " | ".join(report["attribute_differences"])
        )
    if force_dry_run and not report["passes"]:
        log(
            "FORCED DRY RUN: continuing past comparison stops; this result must be rolled back"
        )
    log(
        "Rochester comparison: accepted type differences: "
        + str(report["fields"]["type_differences_accepted"])
    )

    result: dict[str, Any] = {"applied": True, "comparison": report, "moves": {}}
    # Row 1, 2, 4: applications keep their defining client; visibility private is the default.
    # Row 3 and 5: archived under CRMBuilder.
    _ensure_holding(conn, "ENG-003", "CLI-002", now, log)
    _set_engagement_status(conn, "ENG-003", "archived", log)
    _set_engagement_status(conn, "ENG-005", "archived", log)
    # New clients (rows 6 and 7).
    rochester = _ensure_client(conn, MAPPING["ENG-006"]["new_client_name"], now, log)
    boston = _ensure_client(conn, MAPPING["ENG-007"]["new_client_name"], now, log)
    result["clients"] = {"rochester": rochester, "boston": boston}
    # Row 2: Cleveland's two deployments.
    names = {
        r["instance_identifier"]: r["instance_name"]
        for r in _rows(
            conn,
            "SELECT instance_identifier, instance_name FROM instances WHERE engagement_id = 'ENG-002'",
        )
    }
    dpl_test = _create_deployment(
        conn,
        application="ENG-002",
        client="CLI-001",
        instance="INST-001",
        name=names["INST-001"],
        now=now,
        log=log,
        notes="Row 2 of the approved mapping (DEC-1177).",
    )
    dpl_prod = _create_deployment(
        conn,
        application="ENG-002",
        client="CLI-001",
        instance="INST-002",
        name=names["INST-002"],
        now=now,
        log=log,
        notes="Row 2 of the approved mapping (DEC-1177).",
    )
    # Row 6: Rochester.
    new_r = _next_identifier(
        [
            r["instance_identifier"]
            for r in _rows(
                conn,
                "SELECT instance_identifier FROM instances WHERE engagement_id = 'ENG-002'",
            )
        ],
        "INST",
    )
    r_name = _scalar(
        conn,
        "SELECT instance_name FROM instances WHERE engagement_id = 'ENG-006' AND instance_identifier = 'INST-001'",
    )
    result["moves"]["rochester"] = _move_instance(
        conn, "ENG-006", "ENG-002", "INST-001", new_r, now, log, translate_members=True
    )
    dpl_r = _create_deployment(
        conn,
        application="ENG-002",
        client=rochester,
        instance=new_r,
        name=r_name,
        now=now,
        log=log,
        notes="Row 6 of the approved mapping (DEC-1181); was ENG-006/INST-001.",
    )
    _move_deploy_runs(conn, "ENG-006", "ENG-002", "INST-001", new_r, dpl_r, log)
    _move_credentials(conn, "ENG-006", "ENG-002", dpl_r, log)
    result["archive"] = _archive_design(conn, "ENG-006", now, log)
    _set_engagement_status(conn, "ENG-006", "archived", log)
    # Row 7: Boston.
    new_b = _next_identifier(
        [
            r["instance_identifier"]
            for r in _rows(
                conn,
                "SELECT instance_identifier FROM instances WHERE engagement_id = 'ENG-002'",
            )
        ],
        "INST",
    )
    b_name = _scalar(
        conn,
        "SELECT instance_name FROM instances WHERE engagement_id = 'ENG-007' AND instance_identifier = 'INST-001'",
    )
    result["moves"]["boston"] = _move_instance(
        conn, "ENG-007", "ENG-002", "INST-001", new_b, now, log, translate_members=False
    )
    dpl_b = _create_deployment(
        conn,
        application="ENG-002",
        client=boston,
        instance=new_b,
        name=b_name,
        now=now,
        log=log,
        notes="Row 7 of the approved mapping (DEC-1182); was ENG-007/INST-001.",
    )
    _move_deploy_runs(conn, "ENG-007", "ENG-002", "INST-001", new_b, dpl_b, log)
    _move_credentials(conn, "ENG-007", "ENG-002", dpl_b, log)
    _set_engagement_status(conn, "ENG-007", "archived", log)
    result["deployments"] = {
        "cleveland_test": dpl_test,
        "cleveland_production": dpl_prod,
        "rochester": dpl_r,
        "boston": dpl_b,
    }
    result["instances"] = {"rochester": new_r, "boston": new_b}
    log(
        "PRJ-128 migration run applied: "
        + json.dumps(
            {k: v for k, v in result.items() if k != "comparison"}, default=str
        )
    )
    return result


# ---------------------------------------------------------------------------
# Rehearsal entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PRJ-128 migration run: compare, rehearse, or apply against a database URL."
    )
    parser.add_argument(
        "--url",
        required=True,
        help="SQLAlchemy URL of the database (a COPY of production for a rehearsal)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="apply and commit; without it the run is rolled back after reporting",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="write the comparison and moves as JSON to this path",
    )
    parser.add_argument(
        "--accept-attribute-differences",
        action="store_true",
        help="apply although matched records differ in attributes (only after a ruling; name it in --ruling)",
    )
    parser.add_argument(
        "--ruling",
        default=None,
        help="the decision identifier that accepted the differences",
    )
    parser.add_argument(
        "--force-dry-run",
        action="store_true",
        help="rehearse the moves past comparison stops; never combined with --apply",
    )
    args = parser.parse_args(argv)
    if args.accept_attribute_differences and not args.ruling:
        parser.error("--accept-attribute-differences needs --ruling DEC-NNNN")
    if args.force_dry_run and args.apply:
        parser.error("--force-dry-run cannot be combined with --apply")
    engine = create_engine(args.url)
    lines: list[str] = []

    def log(msg: str) -> None:
        lines.append(msg)
        print(msg, file=sys.stderr)

    try:
        with engine.begin() as conn:
            before = census(conn)
            if args.ruling:
                log(f"attribute differences accepted under {args.ruling}")
            result = run(
                conn,
                log=log,
                accept_attribute_differences=args.accept_attribute_differences,
                force_dry_run=args.force_dry_run,
            )
            after = census(conn)
            if not args.apply:
                conn.rollback()
                log("rehearsal only: rolled back")
    except MigrationStop as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        if args.report:
            Path(args.report).write_text(
                json.dumps({"stopped": str(exc), "log": lines}, indent=2, default=str)
            )
        return 1
    finally:
        engine.dispose()
    if args.report:
        Path(args.report).write_text(
            json.dumps(
                {
                    "before": before,
                    "result": result,
                    "after": after,
                    "log": lines,
                    "committed": bool(args.apply),
                },
                indent=2,
                default=str,
            )
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
