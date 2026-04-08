"""YAML Program Files template.

Generates YAML program files matching the CRM Builder YAML schema consumed
by the configuration workflow. One file per entity.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def generate(data_dict: dict, output_path: str | Path, is_draft: bool = False) -> None:
    """Generate YAML program files.

    For YAML generation, output_path is the directory where files are written
    (the programs/ directory). Each entity gets its own file.

    :param data_dict: Data dictionary from queries.yaml_program.query().
    :param output_path: Path to the programs/ directory OR a single file path.
    :param is_draft: If True, adds a draft comment (unused for YAML).
    :returns: List of written file paths.
    """
    entities = data_dict.get("entities", [])
    if not entities:
        return

    out = Path(output_path)

    # If output_path is a directory, write one file per entity
    if out.is_dir() or not out.suffix:
        out.mkdir(parents=True, exist_ok=True)
        for entity in entities:
            entity_name = entity.get("name", "Unknown")
            file_path = out / f"{entity_name}.yaml"
            _write_entity_yaml(entity, file_path)
    else:
        # Single file path — write the first entity
        out.parent.mkdir(parents=True, exist_ok=True)
        if entities:
            _write_entity_yaml(entities[0], out)


def generate_multi(data_dict: dict, output_paths: list[Path]) -> list[Path]:
    """Generate multiple YAML files, one per entity, using provided paths.

    :param data_dict: Data dictionary from queries.yaml_program.query().
    :param output_paths: Pre-resolved paths, one per entity.
    :returns: List of paths that were actually written.
    """
    entities = data_dict.get("entities", [])
    written: list[Path] = []

    for entity, path in zip(entities, output_paths, strict=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_entity_yaml(entity, path)
        written.append(path)

    return written


def _write_entity_yaml(entity: dict, file_path: Path) -> None:
    """Write a single entity YAML file."""
    program: dict = {
        "version": "1.0",
        "entity": _build_entity_section(entity),
    }

    fields = entity.get("fields", [])
    if fields:
        program["fields"] = [_build_field(f) for f in fields]

    rels = entity.get("relationships", [])
    if rels:
        program["relationships"] = [_build_relationship(r, entity) for r in rels]

    panels = entity.get("layout_panels", [])
    if panels:
        program["layout"] = {"detail": [_build_panel(p) for p in panels]}

    list_cols = entity.get("list_columns", [])
    if list_cols:
        program.setdefault("layout", {})["list"] = [
            lc["field"] for lc in list_cols
        ]

    with open(file_path, "w") as f:
        yaml.dump(program, f, default_flow_style=False, sort_keys=False,
                  allow_unicode=True, width=120)


def _build_entity_section(entity: dict) -> dict:
    """Build the entity metadata section."""
    section: dict = {"action": "create"}
    if entity.get("singular_label"):
        section["labelSingular"] = entity["singular_label"]
    if entity.get("plural_label"):
        section["labelPlural"] = entity["plural_label"]
    if entity.get("entity_type"):
        section["type"] = entity["entity_type"]
    if entity.get("description"):
        section["description"] = entity["description"]
    return section


def _build_field(field: dict) -> dict:
    """Build a single field definition."""
    f: dict = {
        "name": field["name"],
        "type": field["field_type"],
    }
    if field.get("label"):
        f["label"] = field["label"]
    if field.get("is_required"):
        f["required"] = True
    if field.get("default_value"):
        f["default"] = field["default_value"]
    if field.get("max_length"):
        f["maxLength"] = field["max_length"]
    if field.get("read_only"):
        f["readOnly"] = True
    if field.get("audited"):
        f["audited"] = True
    if field.get("tooltip"):
        f["tooltipText"] = field["tooltip"]

    options = field.get("options", [])
    if options:
        f["options"] = []
        for opt in options:
            opt_dict: dict = {"value": opt["value"], "label": opt["label"]}
            if opt.get("style"):
                opt_dict["style"] = opt["style"]
            if opt.get("is_default"):
                opt_dict["default"] = True
            f["options"].append(opt_dict)

    return f


def _build_relationship(rel: dict, entity: dict) -> dict:
    """Build a single relationship definition."""
    r: dict = {"name": rel.get("name", "")}
    r["linkType"] = rel.get("link_type", "")
    r["link"] = rel.get("link", "")
    r["linkForeign"] = rel.get("link_foreign", "")
    r["label"] = rel.get("label", "")
    r["labelForeign"] = rel.get("label_foreign", "")

    # Determine the foreign entity name
    if rel.get("entity_id") == entity.get("id"):
        r["foreignEntity"] = rel.get("foreign_entity_name", "")
    else:
        r["foreignEntity"] = rel.get("entity_name", "")

    if rel.get("relation_name"):
        r["relationName"] = rel["relation_name"]

    return r


def _build_panel(panel: dict) -> dict:
    """Build a layout panel definition."""
    p: dict = {"label": panel.get("label", "")}

    if panel.get("style"):
        p["style"] = panel["style"]
    if panel.get("hidden"):
        p["hidden"] = True
    if panel.get("tab_break"):
        p["tabBreak"] = True
    if panel.get("tab_label"):
        p["tabLabel"] = panel["tab_label"]

    rows = panel.get("rows", [])
    if rows:
        p["rows"] = []
        for row in rows:
            cells = []
            if row.get("cell1"):
                cells.append(row["cell1"])
            if row.get("cell2"):
                cells.append(row["cell2"])
            if row.get("is_full_width") and cells:
                p["rows"].append(cells[0])
            elif cells:
                p["rows"].append(cells)

    return p
