# Governance Enforcement Gate — design (REL-034 / PRJ-048 / REQ-320)

**Status:** design for review — *no code yet*. Engagement ENG-001. Requirement
**REQ-320** confirmed; planning items **PI-286** (validator) + **PI-287** (hooks +
install + trailer convention), both `Draft`. This doc is the design the build will
follow; review it, then I flesh out the two PIs from it and build.

Authored 2026-06-30 after reviewing REL-034 (empty change-set, unbuilt).

---

## 1. What REQ-320 demands (the acceptance, restated)

A commit *or* push **touching code** is **rejected** unless it **names a planning
item** that is (a) in an **executable state**, (b) **belongs to a project**, and
(c) **implements a confirmed requirement** — **validated live against the
governance store**. A **trivial** change is allowed **only** with an **explicit,
logged exemption reason**. The gate is installed for **every worktree/clone via
the version-controlled hooks path**, so it binds every Claude Code instance and
the autonomous fleet — the requirement-first rule is enforced by tools, not
discipline.

This is the CLAUDE.md "Governance is a precondition" rule (confirmed requirement +
implementing PI *before* any code) made mechanical.

---

## 2. The trailer convention (the governance link)

A git **commit-message trailer** (RFC-822 style, parseable by
`git interpret-trailers`), consistent with this repo's existing
`Co-Authored-By:` / `Claude-Session:` trailers.

- **Governed link:** `Governed-By: PI-NNN`
  Exactly one PI identifier. (Multiple allowed for a commit spanning PIs:
  repeated `Governed-By:` lines, each validated.)
- **Trivial exemption:** `Governed-By: trivial` **plus** a required, non-empty
  `Exemption-Reason: <one sentence why this is below the requirement threshold>`.
  A `trivial` with no reason (or an empty one) is **rejected** — the judgment must
  be *stated*, never silently assumed (CLAUDE.md's explicit rule).
- **Docs/governance-only:** see §4 — those commits skip the gate by path, so they
  need no trailer.

Rationale for a trailer (vs a branch-name or a side file): it travels with the
commit, survives rebase/cherry-pick, is greppable, and `git interpret-trailers`
parses it deterministically. **Open choice for you:** the trailer *name* —
`Governed-By` (recommended) vs `Implements` vs `Planning-Item`.

---

## 3. Which hooks (commit *and* push)

| Hook | Role | Why |
|---|---|---|
| **`commit-msg`** | Primary gate. Parse the trailer from the just-written message; validate it live against the API. | The only hook with the commit message in hand. Blocks at the moment of commit with a precise message. |
| **`pre-push`** | Backstop. Re-validate every code-touching commit in the pushed range. | Catches commits created where `commit-msg` didn't run (a different tool, `--no-verify`, an old clone) before they reach the shared remote. |

The existing **`pre-commit`** (deposit-event-logs Model-A guard) is **untouched**
and **coexists** in the same hooks dir — it guards *what* lands on a branch;
this gate guards *whether the commit is governed*. Both run.

`pre-commit` is deliberately **not** used for the governance check: it has no
access to the commit message (the trailer lives there), and a `commit-msg`
rejection is the cleaner abort point.

---

## 4. What counts as "touching code" (the trigger)

The gate fires only when a commit's changed files include a **code path**. Pure
docs/governance/data commits are **auto-exempt** (no trailer needed):

- **Governed (gate fires):** `crmbuilder-v2/src/**`, `espo_impl/**`,
  `automation/**`, `tools/**`, `tests/**`, `pyproject.toml`, migrations.
- **Auto-exempt (skip):** `PRDs/**`, `**/*.md`, `crmbuilder-v2/data/**`
  (deposit-event-logs, etc.), `memory/**`, `Screenshots/**`, `.claude/**`.
- A commit touching **both** code and docs is **governed** (the code rules).

The include/exclude globs live in one place in the validator, easy to amend.
**Open choice for you:** whether a `pyproject.toml`-only bump (e.g. a version
bump) is governed or auto-exempt.

---

## 5. The validator (PI-286) — the live API check

Given a `Governed-By: PI-NNN`, the validator (a small Python entry point the hook
calls, reusing `crmbuilder_v2` access where possible) checks, against the **live
governance API** (`X-Engagement` from config; default the dogfood engagement):

1. **PI exists** — `GET /planning-items/PI-NNN` returns it.
2. **Executable state** — `planning_item_status` ∈ the active/dispatchable set
   (`Draft`*, `Decomposed`, `Ready`, `In Progress`, `In Review`) — **not**
   `Resolved`/`Cancelled`/`Deferred` (terminal: code shouldn't land against
   already-closed work). *(\*Draft is allowed — the precondition only requires the
   PI to **exist** with a confirmed requirement; the build often starts at Draft.
   **Open choice:** exclude `Draft` to force at least `Ready`.)*
3. **Belongs to a project** — a `planning_item_belongs_to_project` edge exists.
4. **Implements a confirmed requirement** — a `planning_item_implements_requirement`
   edge to a requirement whose `requirement_status == confirmed`.

All four pass → **allow**. Any fail → **reject** with the specific reason
(`PI-NNN is Resolved`, `PI-NNN implements no confirmed requirement`, `PI-NNN not
found`, …) and the one-line remedy.

**A `Governed-By: trivial`** skips 1–4 but requires a non-empty `Exemption-Reason`
(§2), which is **logged** (§6).

---

## 6. The exemption log (auditable)

Every `trivial` exemption appends one line to a **git-tracked** log —
`crmbuilder-v2/data/governance-exemptions.log` is gitignored, so instead
**`PRDs/product/crmbuilder-v2/governance-exemptions.log`** (tracked): timestamp,
short SHA (post-commit via a `post-commit` amend is messy — simpler: the
`commit-msg` hook logs the *staged* tree's first-line + author + reason). So every
"too small for a requirement" judgment is recorded and reviewable, exactly as
CLAUDE.md requires the judgment to be *stated, not assumed*. **Open choice:**
tracked log file vs a `deposit_event`-style record in the DB (heavier, but
queryable).

---

## 7. Install — every clone/worktree (PI-287)

The hooks are **version-controlled** at `crmbuilder-v2/githooks/` (where the
existing `pre-commit` already lives). Git does not auto-activate them; each clone
must point at them once via **`core.hooksPath`**:

- A **bootstrap command** — `crmbuilder-v2-install-hooks` (a console-script) or a
  `make hooks` target — runs `git config core.hooksPath crmbuilder-v2/githooks`
  and verifies the three hooks are present + executable.
- **Worktrees inherit** the parent clone's `core.hooksPath`, so one bootstrap per
  clone covers all its worktrees (and thus the ADO agents' worktrees).
- The bootstrap is **idempotent** and documented in CLAUDE.md + the README so a
  fresh clone (human or fleet) runs it as step 0.

**Limitation to call out honestly:** `core.hooksPath` is a *local* config, so a
clone that never runs the bootstrap has no gate. The version-controlled hooks +
the documented step-0 bootstrap is the strongest enforcement git allows
client-side; a *server-side* pre-receive hook (if the remote supported it) would
be the only truly unbypassable gate — out of scope here, noted as a follow-on.

---

## 8. API-unavailable + emergency escape (fail-safe)

The live check needs the API. Behaviour is **mode-controlled** by
`CRMBUILDER_GOVERNANCE_GATE`:

- **`off`** — gate disabled (CI checkout, bisect, emergencies). Logged.
- **`warn`** (rollout default) — validate; on a violation or unreachable API,
  **print the warning and exit 0** (does not block). Lets everyone see what would
  be rejected without halting work — and survives the API flakiness seen this
  session.
- **`enforce`** — validate; a violation **exits non-zero** (blocks). API
  unreachable → block with `start the API or set CRMBUILDER_GOVERNANCE_GATE=warn`
  (never silently allow under enforce).

A documented escape — `git commit --no-verify` or `CRMBUILDER_GOVERNANCE_GATE=off`
— exists for genuine emergencies; both are **logged** to the exemption log so a
bypass is visible after the fact.

---

## 9. Rollout (safe, staged)

1. **Build in `warn`** (default). The fleet + humans commit as usual; violations
   are surfaced, nothing blocked. Watch the warnings for a few days.
2. **Backfill the convention** — the ADO agent prompt + the close-out tooling add
   `Governed-By: <work-task's PI>` to agent commits; humans add it to theirs.
3. **Flip to `enforce`** once the warnings are clean. Set the default in
   `crmbuilder-v2/data/crmbuilder.env` (`CRMBUILDER_GOVERNANCE_GATE=enforce`).

This avoids the failure mode of a day-one hard gate that blocks every commit
(including the trailer-less ones this very session produced).

---

## 10. Downstream couplings to handle

- **ADO agents** commit on `ado/wtk-*` branches — their commit message must carry
  `Governed-By: PI-NNN` (the work task's owning PI). `scheduler/agent_prompt` /
  the operating protocol gains a line instructing the agent to add the trailer;
  the scheduler's own merge commits are merges (§11) → exempt.
- **Build-closure / `apply_close_out`** commits touch governance/data only →
  auto-exempt by path.
- **CLAUDE.md** gains the trailer rule + the step-0 bootstrap.

## 11. Edge cases

- **Merge commits** (`git merge --no-ff`) introduce no new code diff of their own
  → **auto-exempt** (detected via two-parent HEAD). The branch's own commits were
  already gated.
- **Rebase/amend** re-run `commit-msg` per resulting commit → naturally covered.
- **Reverts** — a `Revert "…"` carries no new feature; treat as governed against
  the revert's own PI, or `trivial` with reason "revert of <sha>".

## 12. PI split (fleshing out the stubs)

- **PI-286 — Governance-gate validator:** §2 trailer parsing, §4 path trigger,
  §5 live-API validation, §6 exemption log, §8 modes. A pure, unit-testable
  `validate(commit_msg, changed_files, mode, api) -> Decision` core + a thin
  CLI the hooks call. Tests: each reject reason, the trivial-exemption path, the
  doc-only skip, warn-vs-enforce, API-down.
- **PI-287 — hooks + install + convention:** the `commit-msg` + `pre-push` hook
  scripts (calling the validator), the `core.hooksPath` bootstrap command, the
  CLAUDE.md/README convention docs, coexistence with the existing `pre-commit`.

---

## Open choices flagged for your review (§ in brackets)
1. Trailer name: **`Governed-By`** vs `Implements` vs `Planning-Item` [§2].
2. Allow `Draft` PIs, or require ≥ `Ready` [§5.2].
3. `pyproject.toml`-only changes: governed or auto-exempt [§4].
4. Exemption log: **tracked file** vs DB `deposit_event` record [§6].
5. Default rollout mode shipped: **`warn`** (recommended) vs straight `enforce` [§8/§9].
