"""Master/detail panel base.

Wired in slice C. Per DEC-021, every entity panel uses a master/detail
layout — list of records on the left, detail of the selected record on
the right. This module provides the abstract base class with the
toolbar, list pane, and detail pane wired up; subclasses implement
``fetch_records()``, ``list_columns()``, and ``render_detail(record)``.
"""
