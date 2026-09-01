"""Governance enforcement gate — REQ-320 / PI-286 (validator) + PI-287 (hooks).

Refuses a code commit/push that does not name a planning item implementing a
**confirmed** requirement — or a logged **trivial** exemption. Makes the
requirement-first precondition (CLAUDE.md "Governance is a precondition";
REQ-248, which REQ-320 refines) enforced by tooling, not discipline.

Mode via ``CRMBUILDER_GOVERNANCE_GATE`` = ``off`` | ``warn`` | ``enforce``
(default ``warn`` — surface violations, block nothing — for a safe rollout).

The validator core (:func:`evaluate`) is a pure function of the commit message,
the changed files, and an injected ``get_json`` (the live-API reader), so it is
unit-testable with no git, no server, and no real commit. The hooks
(``crmbuilder-v2/githooks/commit-msg`` + ``pre-push``) are thin shells that call
:func:`main`.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# --- conventions ------------------------------------------------------------

#: The trailer naming the governing planning item, or ``trivial`` for an exemption.
GOVERNED_BY = "Governed-By"
#: The required reason accompanying a ``Governed-By: trivial`` exemption.
EXEMPTION_REASON = "Exemption-Reason"
TRIVIAL = "trivial"

#: A well-formed governance identifier, e.g. ``PI-386``. A ``Governed-By`` value
#: that is not ``trivial`` and does not match this is *malformed* — it is reported
#: as a warning, never used as a lookup value (guards against building a bad URL).
_IDENT_RE = re.compile(r"^[A-Z][A-Z0-9]*-\d+$")

#: A PI must be in one of these (non-terminal) statuses to govern new code. Draft
#: is allowed — the precondition only needs the PI to exist with a confirmed
#: requirement; the build often starts at Draft (chosen default, design §5.2).
EXECUTABLE_PI_STATUSES = frozenset(
    {"Draft", "Decomposed", "Ready", "In Progress", "In Review"}
)

#: Changed-file globs that make a commit "touch code" (the gate fires). pyproject
#: is governed (a dependency/packaging change is real, design §4).
CODE_GLOBS: tuple[str, ...] = (
    "crmbuilder-v2/src/*",
    "espo_impl/*",
    "automation/*",
    "tools/*",
    "tests/*",
    "pyproject.toml",
)
#: Globs that are auto-exempt (docs / data / governance / scratch) — no trailer
#: needed. A commit touching BOTH code and these is governed (code wins).
EXEMPT_GLOBS: tuple[str, ...] = (
    "PRDs/*",
    "*.md",
    "crmbuilder-v2/data/*",
    "Screenshots/*",
    ".claude/*",
)

#: The auditable, git-tracked exemption log (design §6).
EXEMPTION_LOG = "PRDs/product/crmbuilder-v2/governance-exemptions.log"

#: Where the store configuration (``CRMBUILDER_V2_API_BASE_URL`` / ``_API_TOKEN``)
#: lives inside a checkout. Gitignored, so a linked worktree never has its own.
_ENV_FILE_REL = Path("crmbuilder-v2") / "data" / "crmbuilder.env"
#: A per-user location that serves every checkout on the machine.
_USER_ENV_FILE = Path("~/.config/crmbuilder/crmbuilder.env")


class StoreConfigurationNotFound(RuntimeError):
    """No governance-store configuration could be found for this checkout.

    REQ-555: the gate must say so — and apply the configured mode — rather than
    fall back to a local development address and report real items missing.
    """


def _this_checkout_root() -> Path | None:
    try:
        return Path(_git("rev-parse", "--show-toplevel").strip())
    except (subprocess.CalledProcessError, OSError):
        return None


def _main_worktree_root() -> Path | None:
    """Root of the main worktree when this checkout is a linked ``git worktree``.

    ``--git-common-dir`` is the shared ``.git`` directory; its parent is the main
    worktree. In the main worktree itself it is just ``.git`` (relative), which
    resolves to this checkout — harmless, deduplicated by the caller.
    """
    try:
        common = _git("rev-parse", "--git-common-dir").strip()
    except (subprocess.CalledProcessError, OSError):
        return None
    if not common:
        return None
    path = Path(common)
    if not path.is_absolute():
        top = _this_checkout_root()
        if top is None:
            return None
        path = top / path
    return path.resolve().parent


def _env_file_candidates() -> list[Path]:
    """Ordered places to look for the store configuration (REQ-555).

    1. this checkout's own data file (the maintained checkout has one);
    2. the main worktree's data file, when this is a linked worktree;
    3. the per-user file, for machines that keep it outside any checkout.
    """
    candidates: list[Path] = []
    for root in (_this_checkout_root(), _main_worktree_root()):
        if root is not None:
            candidates.append(root / _ENV_FILE_REL)
    candidates.append(_USER_ENV_FILE.expanduser())
    seen: set[Path] = set()
    unique: list[Path] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def _api_config() -> tuple[str, str, str]:
    """Resolve ``(base_url, token, engagement)`` for gate lookups (REQ-451/REQ-555).

    Explicit env vars win. Otherwise the application settings are loaded from
    the first configuration file that exists — this checkout's, the main
    worktree's, or the per-user file — so a linked worktree validates against
    the same store, with the same bearer token, as the maintained checkout.

    Raises :class:`StoreConfigurationNotFound` when no base URL can be found.
    There is deliberately no local-development default: a gate that silently
    checks the wrong store reports real planning items as missing.
    """
    base = os.environ.get("CRMBUILDER_V2_API_BASE")
    token = os.environ.get("CRMBUILDER_V2_GATE_TOKEN")
    engagement = os.environ.get("CRMBUILDER_V2_GATE_ENGAGEMENT")
    if base is None or token is None or engagement is None:
        env_file = next((c for c in _env_file_candidates() if c.is_file()), None)
        if env_file is not None:
            try:  # lazy — avoid importing settings (and its deps) unless needed
                from crmbuilder_v2.config import Settings

                s = Settings(_env_file=str(env_file))
                if base is None:
                    base = s.api_base_url
                if token is None:
                    token = s.api_token
                if engagement is None:
                    engagement = s.mcp_engagement or None
            except Exception:  # noqa: BLE001 — config must never break the gate
                pass
    if not base:
        looked = ", ".join(str(c) for c in _env_file_candidates())
        raise StoreConfigurationNotFound(
            "no CRMBUILDER_V2_API_BASE in the environment and no crmbuilder.env "
            f"found (looked in: {looked})"
        )
    return base, (token or ""), (engagement or "CRMBUILDER")


# --- result -----------------------------------------------------------------


@dataclass
class GateDecision:
    """The validator's verdict on one commit (or one pushed commit)."""

    allow: bool
    reasons: list[str] = field(default_factory=list)  # why rejected (if any)
    warnings: list[str] = field(default_factory=list)  # advisory notes
    governed_pis: list[str] = field(default_factory=list)
    exemption_reason: str | None = None
    skipped: bool = False  # no code touched → gate not applicable


# --- parsing ----------------------------------------------------------------


def _matches_any(path: str, globs: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)


def touches_code(changed_files: list[str]) -> bool:
    """True iff any changed file is a governed code path (and not only exempt)."""
    for path in changed_files:
        if _matches_any(path, CODE_GLOBS):
            return True
    return False


def parse_governance_trailers(
    commit_msg: str,
    trailer: str = GOVERNED_BY,
) -> tuple[list[str], str | None, list[str]]:
    """Return ``(planning_items, exemption_reason, malformed)`` from the message.

    ``Governed-By: PI-NNN`` lines yield planning item ids; a ``Governed-By:
    trivial`` line marks an exemption whose reason is the ``Exemption-Reason:``
    trailer (``None`` if absent/blank — a rejectable state). Case-insensitive
    trailer keys; values trimmed.

    A ``Governed-By`` value that is neither ``trivial`` nor a well-formed
    identifier (``_IDENT_RE``) is collected into ``malformed`` — it is **never**
    added to ``planning_items`` and therefore never used as a lookup value, which
    is what prevents a bad trailer from being turned into an invalid request URL.
    """
    pis: list[str] = []
    malformed: list[str] = []
    is_trivial = False
    reason: str | None = None
    for raw in commit_msg.splitlines():
        line = raw.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == trailer.lower():
            if value.lower() == TRIVIAL:
                is_trivial = True
            elif value:
                (pis if _IDENT_RE.match(value) else malformed).append(value)
        elif key == EXEMPTION_REASON.lower():
            reason = value or None
    if is_trivial:
        # An exemption reason of "" is treated as missing (rejected upstream).
        return [], reason if reason else None, malformed
    return pis, None, malformed


# --- live-API validation ----------------------------------------------------


def _http_get_json(path: str) -> object:
    """Default ``get_json``: read ``{data,...}`` from the live governance API.

    A 404 is a clean *not-found* (``None``) — an unknown PI/requirement is a
    validation verdict, not a transport failure. Any other HTTP/URL error
    propagates so the caller maps it to warn/block per mode (store unreachable).
    """
    base, token, engagement = _api_config()
    url = f"{base.rstrip('/')}{path}"
    headers = {"X-Engagement": engagement}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8")).get("data")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def validate_planning_item(pi: str, get_json) -> tuple[bool, str]:
    """Check one PI against REQ-320's four conditions. Returns ``(ok, reason)``.

    Raises whatever ``get_json`` raises on a transport failure — the caller maps
    that to warn/block per mode (an unreachable store is not a per-PI verdict).
    """
    item = get_json(f"/planning-items/{pi}")
    if not item:
        return False, f"{pi} not found in the governance store"
    status = item.get("status")
    if status not in EXECUTABLE_PI_STATUSES:
        return False, (
            f"{pi} is {status!r} — not an executable state "
            f"(code cannot land against closed/terminal work)"
        )
    edges = get_json(f"/references?source_id={pi}") or []
    kinds = {(e.get("relationship"), e.get("target_id")) for e in edges}
    if not any(k == "planning_item_belongs_to_project" for k, _ in kinds):
        return False, f"{pi} does not belong to a project"
    req_ids = [t for k, t in kinds if k == "planning_item_implements_requirement"]
    if not req_ids:
        return False, f"{pi} implements no requirement"
    for rid in req_ids:
        req = get_json(f"/requirements/{rid}")
        if req and req.get("requirement_status") == "confirmed":
            return True, f"{pi} → {rid} (confirmed)"
    return False, (
        f"{pi} implements no CONFIRMED requirement "
        f"(found {', '.join(req_ids)})"
    )


# --- evaluation (pure) ------------------------------------------------------


def trailer_spec(get_json) -> tuple[str, str | None]:
    """``(trailer, value_pattern)`` from the store's ``required_trailer`` check.

    REQ-542 / PI-439: the commit-trailer rule (GVR-229) carries its check as data
    — ``{"kind": "required_trailer", "trailer": "Governed-By", "pattern": ...}`` —
    and the gate reads it rather than hard-coding the trailer. Falls back to the
    built-in ``Governed-By`` with no extra pattern when the store holds no such
    check; a transport failure propagates to ``guarded_evaluate`` like any other.
    """
    for mode in ("enforced_with_override", "enforced"):
        rules = get_json(f"/governance-rules?enforcement={mode}&status=active") or []
        for rule in rules:
            check = rule.get("predicate") or {}
            if check.get("kind") == "required_trailer" and check.get("trailer"):
                return str(check["trailer"]), check.get("pattern") or None
    return GOVERNED_BY, None


def evaluate(commit_msg: str, changed_files: list[str], *, get_json) -> GateDecision:
    """The verdict for one commit. Pure given ``get_json``."""
    if not touches_code(changed_files):
        return GateDecision(allow=True, skipped=True,
                            warnings=["no code paths touched — gate not applicable"])

    pis, exemption, malformed = parse_governance_trailers(commit_msg)
    # REQ-449: a malformed-only trailer blocks without any lookup — the store is
    # consulted for the trailer check only once the message parses cleanly.
    if pis or not malformed:
        trailer, value_pattern = trailer_spec(get_json)
        if trailer.lower() != GOVERNED_BY.lower():
            pis, exemption, malformed = parse_governance_trailers(commit_msg, trailer=trailer)
        if value_pattern:
            try:
                rx = re.compile(value_pattern)
                malformed += [pi for pi in pis if not rx.fullmatch(pi)]
                pis = [pi for pi in pis if rx.fullmatch(pi)]
            except re.error:
                pass
    malformed_reasons = [
        f"malformed 'Governed-By' trailer value {v!r} — expected an identifier "
        f"like 'PI-123'"
        for v in malformed
    ]

    # Trivial exemption path: a non-empty reason is mandatory and gets logged.
    if not pis and ("Governed-By: trivial" in commit_msg
                    or "governed-by: trivial" in commit_msg.lower()):
        if not exemption:
            return GateDecision(
                allow=False,
                reasons=["a 'Governed-By: trivial' exemption requires a non-empty "
                         "'Exemption-Reason:' trailer (the judgment must be stated)"],
            )
        return GateDecision(allow=True, exemption_reason=exemption)

    if not pis:
        # A malformed trailer is a violation in its own right (warn/block per
        # mode) — reported, never looked up.
        return GateDecision(
            allow=False,
            reasons=malformed_reasons or [
                "code change carries no 'Governed-By: PI-NNN' trailer and no "
                "logged 'Governed-By: trivial' exemption (REQ-320)"],
        )

    reasons: list[str] = list(malformed_reasons)
    ok_pis: list[str] = []
    for pi in pis:
        ok, why = validate_planning_item(pi, get_json)
        (ok_pis if ok else reasons).append(pi if ok else why)
    if reasons:
        return GateDecision(allow=False, reasons=reasons, governed_pis=ok_pis)
    return GateDecision(allow=True, governed_pis=ok_pis)


# --- git helpers (the CLI side) ---------------------------------------------


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout


def _staged_files() -> list[str]:
    out = _git("diff", "--cached", "--name-only")
    return [p for p in out.splitlines() if p.strip()]


def _is_merge_commit_in_progress() -> bool:
    try:
        top = _git("rev-parse", "--show-toplevel").strip()
    except subprocess.CalledProcessError:
        return False
    return os.path.exists(os.path.join(top, ".git", "MERGE_HEAD"))


def _commit_files(sha: str) -> list[str]:
    out = _git("diff-tree", "--no-commit-id", "--name-only", "-r", sha)
    return [p for p in out.splitlines() if p.strip()]


def _push_rev_list_args(local_sha: str, remote_sha: str) -> list[str]:
    """``rev-list`` args for one pushed ref (REQ-450).

    An update to an existing remote branch validates ``remote..local``. A **new**
    remote branch (``remote_sha`` all-zero) validates only commits not already on
    any remote-tracking branch (``local --not --remotes``) — never the whole
    ancestor history, which would re-report pre-existing commits.
    """
    if remote_sha == "0" * 40:
        return [local_sha, "--not", "--remotes"]
    return [f"{remote_sha}..{local_sha}"]


def _log_exemption(reason: str, summary: str) -> None:
    try:
        top = _git("rev-parse", "--show-toplevel").strip()
    except subprocess.CalledProcessError:
        return
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    line = f"{stamp}\ttrivial\t{summary[:80]!r}\t{reason}\n"
    try:
        with open(os.path.join(top, EXEMPTION_LOG), "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass


# --- CLI / hook entry -------------------------------------------------------


def _emit(decision: GateDecision, mode: str, *, context: str) -> int:
    """Print the decision and return the process exit code for ``mode``."""
    if decision.skipped or (decision.allow and not decision.warnings):
        if decision.exemption_reason:
            print(f"[governance-gate] trivial exemption logged: "
                  f"{decision.exemption_reason}")
        return 0
    if decision.allow:
        # REQ-555: an allowed-but-unvalidated verdict (store configuration not
        # found, store unreachable) is said out loud, never passed silently.
        print(f"[governance-gate] NOTE ({context}):", file=sys.stderr)
        for w in decision.warnings:
            print(f"  - {w}", file=sys.stderr)
        return 0
    head = "[governance-gate] BLOCKED" if mode == "enforce" else "[governance-gate] WARNING"
    print(f"{head} ({context}):", file=sys.stderr)
    for r in decision.reasons:
        print(f"  - {r}", file=sys.stderr)
    print("  Add a 'Governed-By: PI-NNN' trailer (a confirmed-requirement-backed, "
          "active PI in a project), or 'Governed-By: trivial' + 'Exemption-Reason: "
          "<why>'.", file=sys.stderr)
    if mode == "enforce":
        return 1
    print("  (warn mode — not blocking. Set CRMBUILDER_GOVERNANCE_GATE=enforce to "
          "block; =off to silence.)", file=sys.stderr)
    return 0


def guarded_evaluate(
    commit_msg: str, changed_files: list[str], *, get_json, mode: str
) -> GateDecision:
    """``evaluate`` that never raises — the hook must not crash on its own defect.

    A genuinely unreachable store (network/OS error) degrades to warn-allow /
    enforce-block. Any *other* unexpected error (e.g. a malformed value that
    slipped through to a bad request URL) is caught too and treated the same way,
    so a gate bug can never abort a commit or push (REQ-449). In ``warn`` mode the
    verdict is always allow; only ``enforce`` may block.
    """
    try:
        return evaluate(commit_msg, changed_files, get_json=get_json)
    except StoreConfigurationNotFound as exc:
        # REQ-555: say what is missing; never substitute a development store.
        d = GateDecision(
            allow=(mode != "enforce"),
            warnings=[f"governance store configuration not found ({exc}) — "
                      "cannot validate"],
        )
        if mode == "enforce":
            d.reasons = ["governance store configuration not found; add "
                         "crmbuilder-v2/data/crmbuilder.env to the main worktree "
                         "(or ~/.config/crmbuilder/crmbuilder.env), or set "
                         "CRMBUILDER_V2_API_BASE"]
        return d
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        d = GateDecision(
            allow=(mode != "enforce"),
            warnings=[f"governance store unreachable ({exc}) — cannot validate"],
        )
        if mode == "enforce":
            d.reasons = ["governance store unreachable; start the API or set "
                         "CRMBUILDER_GOVERNANCE_GATE=warn"]
        return d
    except Exception as exc:  # noqa: BLE001 — defensive: never crash the hook
        detail = f"{type(exc).__name__}: {exc}"
        d = GateDecision(
            allow=(mode != "enforce"),
            warnings=[f"unexpected gate error ({detail}) — treated as non-blocking"],
        )
        if mode == "enforce":
            d.reasons = [f"unexpected gate error ({detail})"]
        return d


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Governance enforcement gate (REQ-320).")
    sub = p.add_subparsers(dest="cmd", required=True)
    cm = sub.add_parser("commit-msg")
    cm.add_argument("message_file")
    pp = sub.add_parser("pre-push")  # reads ranges from stdin
    for sp in (cm, pp):
        sp.add_argument("--mode", default=os.environ.get(
            "CRMBUILDER_GOVERNANCE_GATE", "warn"))
    args = p.parse_args(argv)
    mode = (args.mode or "warn").lower()
    if mode == "off":
        return 0
    get_json = _http_get_json

    if args.cmd == "commit-msg":
        if _is_merge_commit_in_progress():
            return 0  # merges integrate already-gated commits
        try:
            msg = open(args.message_file, encoding="utf-8").read()
        except OSError:
            return 0
        decision = guarded_evaluate(
            msg, _staged_files(), get_json=get_json, mode=mode
        )
        if decision.exemption_reason:
            _log_exemption(decision.exemption_reason, msg.splitlines()[0] if msg else "")
        return _emit(decision, mode, context="commit-msg")

    # pre-push: validate every code-touching, non-merge commit in each pushed range.
    worst = 0
    for raw in sys.stdin:
        parts = raw.split()
        if len(parts) < 4:
            continue
        local_sha, remote_sha = parts[1], parts[3]
        if local_sha == "0" * 40:  # branch deletion
            continue
        try:
            shas = _git(
                "rev-list", "--no-merges",
                *_push_rev_list_args(local_sha, remote_sha),
            ).split()
        except subprocess.CalledProcessError:
            continue
        for sha in shas:
            try:
                msg = _git("log", "-1", "--format=%B", sha)
            except subprocess.CalledProcessError:
                continue
            decision = guarded_evaluate(
                msg, _commit_files(sha), get_json=get_json, mode=mode
            )
            worst = max(worst, _emit(decision, mode, context=f"pre-push {sha[:8]}"))
    return worst


HOOKS_DIR = "crmbuilder-v2/githooks"


def install_main(argv: list[str] | None = None) -> int:
    """Point this clone's git at the version-controlled hooks (PI-287).

    Sets ``core.hooksPath`` to the repo's tracked hooks dir so the gate (and the
    existing Model-A pre-commit guard) bind every commit. Worktrees inherit the
    config, so one run per clone covers the ADO fleet's worktrees too. Idempotent.
    """
    try:
        top = _git("rev-parse", "--show-toplevel").strip()
    except subprocess.CalledProcessError:
        print("not inside a git repository", file=sys.stderr)
        return 1
    subprocess.run(
        ["git", "-C", top, "config", "core.hooksPath", HOOKS_DIR], check=True
    )
    missing = [
        h for h in ("pre-commit", "commit-msg", "pre-push")
        if not os.access(os.path.join(top, HOOKS_DIR, h), os.X_OK)
    ]
    print(f"core.hooksPath set to {HOOKS_DIR} (worktrees inherit it).")
    if missing:
        print(f"  warning: hooks missing or not executable: {missing}",
              file=sys.stderr)
    print("  governance gate mode = CRMBUILDER_GOVERNANCE_GATE (default 'warn'); "
          "set 'enforce' to block, 'off' to disable.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
