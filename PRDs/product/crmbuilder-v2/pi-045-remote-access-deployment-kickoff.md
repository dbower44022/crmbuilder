# PI-045 V2 remote-access deployment — kickoff

**Last Updated:** 05-23-26 23:15
**Status:** Kickoff — ready for a planning conversation to open against it once SES-064's close-out has applied locally.
**Authored at:** the close of the SES-064 architectural decision conversation per its `in_flight_at_end` field.
**Anticipated session at close of the planning conversation:** SES-065 (subject to identifier rebasing if other conversations close between now and the open of the planning conversation; see "Identifier note" below).

---

## Purpose

PI-045 implements the four decisions settled in SES-064 (DEC-201, DEC-202, DEC-203, DEC-204). The goal is to give claude.ai a read+write path to the canonical v2 governance database so that conversations stop drifting from canonical state — the failure Doug named in the SES-064 seed prompt ("There are way too many problems where it does not know what is current, or writes prompts that are out of date vs the database").

After PI-045 lands, three actors read and write the same single SQLite file via the same FastAPI REST endpoints: the desktop UI (over localhost), Claude Code (over localhost), and claude.ai (over MCP over Cloudflare Tunnel to the same localhost API). Claude.ai's access is bounded by Doug's laptop being online and the tunnel being up; in that window, claude.ai's database view matches the desktop UI's.

---

## Read this first

- Read `crmbuilder/CLAUDE.md` for engagement context. Confirm with Doug at the open of the planning conversation which CLAUDE.md to read.
- Read the SES-064 payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_064.json` for the four decisions in full — context, rationale, alternatives considered, and named consequences for each. PI-045's scope is the union of those four decision documents.
- Read the MCP server entry point at `crmbuilder-v2/src/crmbuilder_v2/mcp_server/server.py` (line 44 — `server.run("stdio")`) and the CLI dispatcher at `crmbuilder-v2/src/crmbuilder_v2/cli.py` (`run_mcp` function). The transport flag added by this workstream lands at both call sites.
- Read the API launch path at `crmbuilder-v2/src/crmbuilder_v2/cli.py` (`run_api` function) and the engagement-marker resolution at the point where `current_engagement.json` is read. The marker-mid-process handling decision (see "Surface and settle" below) hinges on what this code currently does at launch versus per request.
- Read the tool surface at `crmbuilder-v2/src/crmbuilder_v2/mcp_server/tools.py` and confirm the count is still 44 (the surface that the verification step exercises end-to-end).
- Read `crmbuilder-v2/src/crmbuilder_v2/api/config.py` for `api_host` (defaults to `127.0.0.1`) and the port configuration. The REST API binding stays unchanged per DEC-202; the MCP HTTP transport adds a separate localhost binding.
- Skim the FastMCP docs for the `streamable-http` transport (the official Python MCP SDK supports stdio / sse / streamable-http; streamable-http is the right choice for claude.ai's MCP integration).

---

## Scope

The four pieces of work below come verbatim from PI-045's description in `ses_064.json`. They are sliced here into the three implementation conversations the planning conversation will draft prompts for.

### (a) Code changes — one Claude Code conversation

Delivered as one or more `CLAUDE-CODE-PROMPT-pi-045-*.md` files authored during the planning conversation:

- Add `--transport {stdio,streamable-http}` flag to the `crmbuilder-v2-mcp` CLI entry point in `crmbuilder-v2/src/crmbuilder_v2/cli.py`. Default remains `stdio` so existing desktop-piped usage is unchanged.
- Parameterize the transport in `mcp_server/server.py` `main()`. The call site that today reads `server.run("stdio")` becomes a dispatch on the CLI flag.
- Bind the FastMCP `streamable-http` transport to `127.0.0.1` with a configurable port (default to be chosen by the planning conversation — any unused localhost port is acceptable; suggest 8810 or similar to keep the v2 services together).
- Add a shared-secret header middleware to the HTTP transport that 401s requests with missing or wrong `X-CRMBuilder-Secret` (or final name chosen by the planning conversation). The secret is read from an environment variable at process start.
- Address the engagement-marker-mid-process risk identified in DEC-203 — implementation per the surface-and-settle decision below.

### (b) Operational steps — one operational conversation

These are procedural at Doug's laptop and Cloudflare dashboard; the conversation provides step-by-step guidance and verification at each step:

- Move `crmbuilder.com` nameservers from the current registrar to Cloudflare (free plan, ~15 minutes). Verify nameserver propagation before proceeding.
- Install `cloudflared` on Doug's laptop and configure as a launchd service so it reconnects on reboot.
- Create the named tunnel and the DNS record routing `mcp.crmbuilder.com` to `127.0.0.1:<mcp_port>`.
- Create the Cloudflare Access policy requiring Google login (Doug's identity) for the `mcp.crmbuilder.com` hostname. Confirm the policy applies before the tunnel goes live.
- Register the MCP URL in claude.ai's MCP integration with the shared-secret custom header.

### (c) Verification — one smoke-test conversation (or fold into the operational conversation)

Verification is structured as a checklist the smoke-test conversation walks against the deployed stack:

- Run all 44 MCP tools end-to-end from a claude.ai conversation. Cover the read surface (`get_current_charter`, `get_current_status`, `list_decisions_for_session`, etc.) and the write surface (`create_decision`, `replace_charter`, `add_reference`, `update_planning_item`, etc.). Each write tool exercises the round trip: write, read back, verify the record exists.
- Run the smoke test against both engagements: CRMBUILDER first, then flip the engagement marker via the desktop UI's Engagements panel and re-run a representative subset against CBM. This verifies DEC-203's marker-driven routing works end to end.
- Confirm an unauthenticated request from a non-Doug browser is blocked at the Cloudflare Access layer (Access prompts for login).
- Confirm a request with the wrong shared secret is blocked at the MCP layer (the middleware 401s before the tool dispatch).
- Confirm the engagement marker drives the right database — write a benign no-op decision to CRMBUILDER, switch the marker, write a different no-op decision to CBM, verify each lands in its target database via the desktop UI.

### (d) Documentation — folded into the smoke-test conversation's close-out

- New section in `crmbuilder-v2/README.md` (or a new `crmbuilder-v2/docs/remote-deployment.md`) covering: prerequisites, the four decisions' rationale at a paragraph each, step-by-step setup, secret management, troubleshooting (tunnel down, marker switch unnoticed, claude.ai MCP registration drift).
- Entry in `crmbuilder/CLAUDE.md` under the v2 section describing the remote MCP URL (`https://mcp.crmbuilder.com`), the auth model (Cloudflare Access identity gating + `X-CRMBuilder-Secret` header), and the marker-driven routing implication (claude.ai sees whichever engagement is active in the desktop UI's Engagements panel).
- Note in `crmbuilder/CLAUDE.md` Tier-2 section that the remote MCP makes the `db-export/` JSON snapshots a strict fallback rather than the primary read path when claude.ai has tunnel access.

---

## Surface and settle

### Consequential decision — engagement-marker-mid-process handling (DEC-203 footgun)

DEC-203 chose marker-driven single deployment and named the footgun explicitly: if Doug switches engagements in the desktop UI mid-conversation, claude.ai's reads silently switch with the desktop UI. The API process needs either to re-read `current_engagement.json` on each request or to detect a marker change and restart with a "service unavailable; engagement changed" signal to in-flight callers.

This decision passes the two-part consequential test (real downstream impact on correctness model; two genuinely different operational stories) and should be surfaced in the planning conversation using the eight-element template. The two viable options to frame are:

- **Per-request marker re-read.** The API stats and reads `current_engagement.json` on each incoming request and routes to the matching database. Transparent to callers — a switch shows up as the next call returning the new engagement's data. Implementation cost: small (a stat + a JSON read per request, both cached by the OS page cache after the first call). Correctness model: the engagement is always the marker's current value. Risk: silently changes mid-conversation; claude.ai may write half a decision flow to one engagement and the other half to another if Doug switches between writes.
- **Detect-and-fail-loud on marker change.** The API reads `current_engagement.json` at launch (current behavior) and watches its mtime. On change, the API either restarts itself or returns a sentinel error for the next several requests that tells callers "marker changed — restart required." Operationally explicit — the switch is visible in logs and at the API surface. Implementation cost: moderate (mtime watching, sentinel-error path, possibly a launchd-driven restart). Correctness model: the engagement is the marker's value at launch, and a switch is a visible event.

The planning conversation surfaces this with concrete examples (a CBM decision flow that spans three claude.ai writes; what happens if Doug switches to CRMBUILDER between writes one and two), names the cost honestly for each option, and lands on one with a one-line rationale. Whatever lands becomes the implementation in part (a)'s Claude Code prompt.

### Decide-and-announce items

These are implementation choices below the consequential threshold; the planning conversation decides and announces inline:

1. **MCP HTTP transport port.** Suggest 8810 (keeps the v2 services adjacent — the REST API is at 8765 today). Any unused localhost port is acceptable; the value is configured via the same env-var pattern as the REST API.
2. **Shared-secret header name.** Suggest `X-CRMBuilder-Secret`. Any HTTP-legal custom header name works as long as it matches between the laptop env var, the MCP middleware, and claude.ai's MCP integration custom-header configuration.
3. **Shared-secret storage on the laptop.** Suggest a launchd plist-defined environment variable for the MCP process, sourced from a single file like `~/.config/crmbuilder/mcp-secret` checked into Doug's password manager (not into the repo). Rotation is a manual edit in three places: the secret file, claude.ai's MCP integration custom-header configuration, and the launchd plist reload.
4. **Cloudflare Access identity provider.** Google login only (matches Doug's primary identity).
5. **Documentation home.** Suggest a new file `crmbuilder-v2/docs/remote-deployment.md` rather than expanding the top-level README, because the deployment scope is meaningful enough to warrant its own document and keeps the README short. Final placement is the planning conversation's call.

---

## Working pattern

Operating mode for the planning conversation: **ARCHITECTURE** by project default. Surface the marker-mid-process question using the eight-element template; decide-and-announce the items in the list above; draft the three (or four) Claude Code prompts as drafts presented in a block for Doug's review.

Operating mode for the implementation conversations:
- **Claude Code coding conversation:** **DETAIL** mode per project default (code writing, Claude Code prompt authoring). One slice at a time, full discussion, approval before each next step.
- **Operational conversation:** **ARCHITECTURE** mode for any consequential operational choice that surfaces (e.g., named-tunnel naming, Access policy scope changes); **DETAIL**-flavor procedural walkthrough for the step-by-step ops itself.
- **Smoke-test conversation:** **DETAIL** mode — verification is a checklist with concrete expected outcomes at each step.

Each implementation conversation produces its own close-out payload + apply prompt per the sandbox convention. PI-045's status moves from Open to In Progress when the first implementation conversation opens, and to Complete when the smoke-test conversation's close-out applies.

---

## Deliverable shape

The planning conversation (anticipated SES-065) produces a triple-artifact close-out:

1. **`PRDs/product/crmbuilder-v2/close-out-payloads/ses_065.json`** — the close-out payload covering the planning conversation's session record plus any decisions it settles. Anticipated decisions: DEC-205 (marker-mid-process handling, consequential) plus possibly DEC-206 / 207 (any decide-and-announce items that turn out to be consequential under closer examination).
2. **`PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-065.md`** — apply prompt for the close-out payload.
3. **One or more `CLAUDE-CODE-PROMPT-pi-045-*.md` files in `PRDs/product/crmbuilder-v2/prompts/`** — the Claude Code prompts for the code-changes implementation conversation. Suggested split:
   - `CLAUDE-CODE-PROMPT-pi-045-A-transport-flag-and-http-binding.md` — CLI flag, server.py dispatch, FastMCP HTTP binding to 127.0.0.1 with configurable port.
   - `CLAUDE-CODE-PROMPT-pi-045-B-shared-secret-middleware.md` — header middleware reading the env var, 401 on missing/wrong, tests against a known-good and known-bad secret.
   - `CLAUDE-CODE-PROMPT-pi-045-C-marker-handling.md` — implementation of whichever option DEC-205 lands on.

The operational and smoke-test conversations produce their own close-outs in turn. The smoke-test conversation's close-out also commits the documentation updates (part (d) of PI-045's scope).

---

## Identifier note

This kickoff anticipates SES-065 as the planning conversation's close. SES-064 just pushed and a predecessor apply chain of five close-outs (SES-058 through SES-064 with two parallel-sandbox collisions already absorbed) is queued for local apply. If other conversations close at SES-065 or beyond between the publishing of this kickoff and the opening of the planning conversation, the planning conversation will need to rebase to the next available session identifier and the next available DEC range. The parallel-sandbox identifier-collision pattern has now happened three times in the recent backfill program (SES-057 to SES-058 on Code Change Lifecycle workstream; SES-058 to SES-059 between audit-v1.2 and PI-024; SES-062 → SES-063 → SES-064 during the SES-064 conversation itself). Verify identifier heads at the start of the planning conversation, and rebase pre-emptively if heads have advanced.

PI-032 (Code Change Lifecycle methodology rollout) is the home for the reserve-at-apply-time identifier model that would eliminate this class of collisions. SES-061 flagged it as future; SES-064's three collisions in one conversation are concrete evidence to promote it to near-term — but that promotion is PI-032's scope, not PI-045's.

---

## What's queued after this

Nothing depends on PI-045's completion. PI-045 is a free-standing deployment workstream.

The closest adjacent workstream is **Option B (remote-canonical migration)** — moving the SQLite to a small VPS or migrating to a managed DB (Postgres, Turso), with all three actors reading and writing the remote canonical store equally. SES-064 explicitly rejected Option B as premature and named the conditions under which it becomes attractive (the laptop-online-time bound starts hurting the actual claude.ai usage pattern; ambient queries from off-laptop become a real need). Operating under Option A for several months will produce the usage data that informs whether Option B is justified. The apply scripts, MCP tool registrations, and desktop access patterns are all compatible with both options because the wire format (FastAPI REST + MCP protocol) does not change.

---

## Out of scope (explicit)

- **REST API public exposure.** DEC-202 commits to MCP-only. Cloudflare Tunnel ingress has exactly one route. Cross-machine Claude Code runs and cross-machine apply-script targeting are not bundled here; if they surface as needs later, they are separate decisions and separate tunnel routes.
- **Per-engagement tunnel deploys.** DEC-203 commits to marker-driven single deployment. If concurrent multi-engagement work becomes a regular pattern later, the migration cost is one extra `cloudflared` tunnel and one extra API process — not architectural — and is a separate workstream.
- **Secret-rotation tooling.** PI-045 documents the three places the shared secret lives (laptop secret file, launchd plist env var, claude.ai MCP integration custom header) and documents that rotation is a manual three-place edit. A rotation tool (CLI command or desktop UI action that updates all three coherently) is out of scope; if rotation friction becomes real, it is a follow-up.
- **Option B remote-canonical migration.** See "What's queued after this." Out of scope here; revisitable when Option A's bounds start hurting.
- **MCP transport options other than stdio and streamable-http.** FastMCP also supports SSE. SSE works for claude.ai but streamable-http is the more current pattern; supporting SSE as a third option is out of scope unless the planning conversation surfaces a concrete reason.
