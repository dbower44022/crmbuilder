# Claude Code Prompt — Configure log: show absolute path of YAML being processed

**Repository:** `dbower44022/crmbuilder`
**Branch:** `main` (commit directly)
**Type:** Diagnostic improvement

---

## 1. Problem statement

The Configure run log shows the relative path of each YAML file
being processed (e.g. `MN/MN-Account.yaml`) but not the absolute
path the application actually loaded from. When debugging a
"why isn't my YAML edit taking effect" hypothesis — for example
when checking whether the app is reading the right project
folder — the operator has no way to confirm which file on disk
the app is actually consuming.

This cost real diagnostic time on 05-04-26 during the deployment
validation pass. A configure run rejected `MN-Account.yaml` with
an empty-options validator error after the schema flag had been
added to the file in the user's local clone. Diagnosing whether
the failure was a stale-cache, a stale-clone, or a wrong-
project-folder hypothesis took ~10 minutes of investigation that
would have been a one-line check if the run log had shown the
absolute path.

## 2. Solution

Emit an additional log line immediately after the existing
`=== {op_label}: {file_info.name} (n/N) ===` header, showing the
absolute path of the file. Keep the line concise, gray, and
indented so it reads as supplementary detail rather than a
primary header.

Format:

```
=== Running: MN/MN-Account.yaml (2/5) ===
    Source: /home/doug/Dropbox/Projects/ClevelandBusinessMentors/programs/MN/MN-Account.yaml
```

The absolute path is already available — `YamlFileInfo.path` is
populated to the absolute path in `deployment_logic.load_yaml_files`
(line 377), and the configure progress UI accesses it as
`file_info.path` for hash computation at line 309.

## 3. Required code change

`automation/ui/deployment/configure_progress.py`, around line
322–326. Insert a `Source:` line immediately after the existing
`=== ... ===` header.

Replace:

```python
        self._append_log("")
        self._append_log(
            f"=== {op_label}: {file_info.name} "
            f"({self._current_file_idx}/{self._total_files}) ===",
            "info",
        )
```

with:

```python
        self._append_log("")
        self._append_log(
            f"=== {op_label}: {file_info.name} "
            f"({self._current_file_idx}/{self._total_files}) ===",
            "info",
        )
        self._append_log(
            f"    Source: {file_info.path}",
            "gray",
        )
```

That's the entire change. One log line, one color, no logic.

## 4. Out of scope

- Do NOT change anything else about the run-header presentation.
- Do NOT change the relative-path display in `file_info.name` —
  that remains the primary identifier.
- Do NOT add path display anywhere other than at the start of
  each per-file run.
- Do NOT change `YamlFileInfo` or the file-discovery logic in
  `deployment_logic.load_yaml_files`.
- Do NOT modify any tests other than to add coverage for the
  new line if the existing test file structure makes that
  natural; otherwise tests are out of scope.

## 5. Verification

1. **Lint:** `uv run ruff check automation/`.
2. **Manual end-to-end (by Doug):** Run any Configure operation.
   The first two lines of each per-file block should be:

   ```
   === Running: {relative_path} ({n}/{N}) ===
       Source: {absolute_path}
   ```

   The `Source:` line should appear in gray (or whatever color
   the existing `_append_log(..., "gray")` calls render).

## 6. Commit

Single commit. Suggested message:

```
log(configure): show absolute path of YAML being processed

The Configure run log showed the relative path of each YAML file
being processed but not the absolute path the application
actually loaded from. When debugging stale-clone, stale-cache,
or wrong-project-folder hypotheses during the 05-04-26
deployment validation pass, this gap cost roughly 10 minutes of
investigation that would have been a one-line check.

Adds a 'Source: {absolute_path}' line in gray immediately after
the existing per-file run header. file_info.path is already
populated to the absolute path by deployment_logic.load_yaml_files;
the new line just surfaces it.

One-line addition, no logic change.
```
