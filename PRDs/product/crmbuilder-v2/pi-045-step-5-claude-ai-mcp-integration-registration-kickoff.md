# PI-045 step 5 — claude.ai MCP integration registration (and PI-045 closure) — kickoff

**Last Updated:** 05-24-26 22:30
**Status:** Kickoff — ready for an operational conversation to open against it once SES-072's close-out has applied locally.
**Authored at:** the close of the SES-072 code-changes implementation conversation per its `in_flight_at_end` first item.
**Anticipated session at close of this conversation:** SES-073 (subject to identifier rebasing per the recent parallel-sandbox pattern — see "Identifier note" below).

---

## Purpose

PI-045 step 5 registers the v2 MCP HTTP transport with claude.ai so that claude.ai conversations can read and write the canonical v2 governance database through the same FastAPI REST endpoints the desktop UI and Claude Code use. This is the final operational step in PI-045's scope; on this conversation's close-out apply, PI-045 advances from In Progress to Complete.

The two predecessor conversations made step 5 unblocked:

- **SES-071** executed operational steps 1–4 (DNS migration of `crmbuilder.ai` from GoDaddy to Cloudflare; `cloudflared` installed at Doug's Linux Mint 22 host; named tunnel `crmbuilder-mcp` UUID `6170403a-eb17-47ee-af94-ea70de6a1e74` routing `mcp.crmbuilder.ai` → `127.0.0.1:8810` via a systemd user unit with lingering; Cloudflare Access two-policy split — `Service Auth claude-ai-mcp` for the Service Token path and `Allow admin` + One-time PIN for browser admin). DEC-225 captured the auth-model revisions (Service Token added; One-time PIN replaces Google login because Cloudflare retired the built-in Google OAuth shortcut).
- **SES-072** executed code-changes slices A (CLI `--transport stdio/streamable-http` flag + `CRMBUILDER_V2_MCP_HTTP_PORT` env var defaulting to 8810 + FastMCP HTTP binding to `127.0.0.1`), B (`SharedSecretMiddleware` validating `X-CRMBuilder-Secret` via `hmac.compare_digest` + startup hard-fail when streamable-http is selected without the secret), and C (DEC-205 engagement-marker fail-loud guard returning HTTP 409 on drift between the marker captured at process start and the live `current_engagement.json`). All three slices verified end-to-end against the live tunnel.

The MCP HTTP transport is buildable; the tunnel is up; Cloudflare Access is enforcing the two-policy split. Step 5 makes claude.ai the third actor that reads and writes the same SQLite file the desktop UI and Claude Code read and write.

---

## Read this first

- Read `crmbuilder/CLAUDE.md` for engagement context. Confirm with Doug at the open of the conversation which CLAUDE.md to read.
- Read the PI-045 master kickoff at `PRDs/product/crmbuilder-v2/pi-045-remote-access-deployment-kickoff.md` for the four anchor decisions DEC-201..204, the original scope partitioning into parts (a)–(d), and the surface-and-settle context that landed in DEC-205.
- Read SES-071's close-out at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_071.json` for the operational state — Cloudflare zone, tunnel, Access application + two policies, Service Token credentials at `~/.config/crmbuilder/cf-access-client-{id,secret}` (mode 0600 each), and the auth-model revisions captured in DEC-225.
- Read SES-072's close-out at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_072.json` for the code state — the three slices' commits (95b801a2, 209a3dc9, ea04e1a6 with follow-ups c578503b and a9cfe138), the new modules (`mcp_server/middleware.py`, `api/marker_guard.py`), and the env-var contract (`CRMBUILDER_V2_MCP_HTTP_PORT`, `CRMBUILDER_V2_MCP_SHARED_SECRET`).
- Skim `crmbuilder-v2/src/crmbuilder_v2/mcp_server/middleware.py` and `mcp_server/server.py` to confirm the header name is exactly `X-CRMBuilder-Secret` and the transport flag is exactly `streamable-http`. These values must match what gets pasted into claude.ai's MCP integration custom-header configuration.
- Confirm the secret file at `~/.config/crmbuilder/mcp-secret` (mode 0600) exists on Doug's host; its value is the `X-CRMBuilder-Secret` header value claude.ai sends.

---

## Hard prerequisite — rotate the `claude-ai-mcp` Service Token Client Secret BEFORE claude.ai integration goes live

**This is not optional. The conversation must complete this step before any claude.ai-side registration work.**

The `claude-ai-mcp` Service Token's Client Secret value appeared verbatim in SES-071's conversation transcript during the doubled-header diagnostic. At the close of SES-071 the blast radius was zero — no MCP backend was listening on `127.0.0.1:8810` and there was no app-layer auth to bypass. With SES-072 applied the MCP HTTP transport is buildable and the `SharedSecretMiddleware` is in place; an attacker who replayed the transcript-leaked Client Secret + Client ID against `https://mcp.crmbuilder.ai` would clear Cloudflare Access but would still be stopped at the `X-CRMBuilder-Secret` check. Defense in depth held. But the rotation is still required before the integration goes live, both because the dual-layer model from DEC-204 is only meaningful when both layers are coherent and because the transcript exposure was a known incident.

Rotation procedure:

1. Cloudflare Zero Trust dashboard → Access controls → Service credentials → Service Tokens → `claude-ai-mcp` → Refresh. Cloudflare returns a one-time modal containing the new Client ID and Client Secret.
2. Atomically rewrite the two credential files on Doug's host. Use `printf '%s' '<value>' > ~/.config/crmbuilder/cf-access-client-id` (no trailing newline, no `CF-Access-Client-Id:` header-name prefix — SES-071's diagnostic chain shows what happens if the prefix slips in). Repeat for `cf-access-client-secret`. Verify file sizes (Client ID ends in `.access`, about 39 bytes; Client Secret is 64 hex bytes) and mode 0600.
3. Update the canonical copy of both values in Doug's password manager.
4. Verify the new credentials pass through Cloudflare Access by running the same `curl -H 'CF-Access-Client-Id: <new-id>' -H 'CF-Access-Client-Secret: <new-secret>' https://mcp.crmbuilder.ai/` test that SES-071's step 4 closed on — expected response is HTTP 502 if the MCP backend isn't running, or whatever the MCP HTTP transport returns to a raw GET if it is running. Either way, the response must not be a 302 to `crmbuilder.cloudflareaccess.com/cdn-cgi/access/login/...` (a 302 means Access did not accept the new token).

The old Client Secret value is invalidated by Cloudflare's Refresh action; no client anywhere holds it after this rotation.

---

## Scope

This kickoff folds three pieces of work from PI-045's master scope into one conversation. The fold is a settled choice — see "Folding rationale" below for the alternative.

### (1) claude.ai MCP integration registration

After the Service Token rotation has been completed and verified, register the v2 MCP HTTP transport in claude.ai's MCP integration UI:

- URL: `https://mcp.crmbuilder.ai`
- Three custom headers:
  - `X-CRMBuilder-Secret`: the value of `~/.config/crmbuilder/mcp-secret` on Doug's host (the `SharedSecretMiddleware` validates this via `hmac.compare_digest`)
  - `CF-Access-Client-Id`: the post-rotation value of `~/.config/crmbuilder/cf-access-client-id` (Cloudflare Access Service Token)
  - `CF-Access-Client-Secret`: the post-rotation value of `~/.config/crmbuilder/cf-access-client-secret` (Cloudflare Access Service Token)

The MCP HTTP transport must be running on `127.0.0.1:8810` during registration so claude.ai's discovery can fetch the tool list. Start it at Doug's terminal with `crmbuilder-v2-mcp --transport streamable-http` (the env-var `CRMBUILDER_V2_MCP_SHARED_SECRET` must be set in the shell or sourced from `~/.config/crmbuilder/mcp-secret`; SES-072 slice B's startup hard-fail will exit code 1 if it isn't). The REST API must also be running (`crmbuilder-v2-api`) so MCP tool calls have a backend to dispatch against — this is the same FastAPI process the desktop UI and Claude Code use, with the SES-072 slice C marker guard now in place.

After registration completes, confirm claude.ai successfully fetches the tool list (44 tools per the current MCP surface; the slice B middleware will allow the request through because the `X-CRMBuilder-Secret` header matches).

### (2) Smoke test — full MCP surface against both engagements

Per PI-045 master kickoff part (c), structured as a checklist the conversation walks against the deployed stack:

- All 44 MCP tools exercised end-to-end from a claude.ai conversation, covering the read surface (`get_current_charter`, `get_current_status`, `list_decisions_for_session`, `list_planning_items`, `list_references`, etc.) and the write surface (`create_decision`, `replace_charter`, `add_reference`, `update_planning_item`, etc.). Each write tool exercises the round trip: write, read back, verify the record exists.
- The smoke test runs against CRMBUILDER first (the current marker), then flips the engagement marker via the desktop UI's Engagements panel to CBM and re-runs a representative subset. This is the live verification that DEC-203's marker-driven routing works end to end through the tunnel — and that DEC-205's fail-loud guard (slice C) does the right thing when the marker changes mid-process (the API process started against CRMBUILDER will return HTTP 409 with `engagement_marker_changed` until restarted; the smoke test must restart the API after the marker flip and verify CBM is then accessible).
- Three auth-path negative cases verified:
  - Unauthenticated browser request to `https://mcp.crmbuilder.ai` (no credentials) → HTTP 302 to `crmbuilder.cloudflareaccess.com/cdn-cgi/access/login/...` (Cloudflare Access enforces).
  - Request bearing valid Service Token headers but missing or wrong `X-CRMBuilder-Secret` → HTTP 401 `{"error":"unauthorized"}` (Cloudflare Access passes; `SharedSecretMiddleware` rejects).
  - Request bearing valid Service Token headers and the correct `X-CRMBuilder-Secret`, with the engagement marker drifted between API process start and the request → HTTP 409 `{"error":"engagement_marker_changed", ...}` (marker guard fires).
- Engagement-marker-drives-routing confirmation: write a benign no-op decision to CRMBUILDER via claude.ai, switch the marker via the desktop UI, restart the API, write a different benign no-op decision to CBM via claude.ai, verify both decisions land in their target databases via the desktop UI.

### (3) Documentation — folded into this conversation's close-out

Per PI-045 master kickoff part (d):

- Create `crmbuilder-v2/docs/remote-deployment.md` covering: prerequisites; the four DEC-201..204 anchor decisions at one paragraph each; the DEC-205 marker-drift guard and the operational implication (mid-process switches require API restart); the DEC-225 auth model (Service Token + One-time PIN); step-by-step setup (referenced from SES-071's operational record + SES-072's code commits + this conversation's registration steps); secret management across the five rotation touchpoints (the two credential files, password manager, claude.ai's MCP integration custom headers, the Service Token refresh in Cloudflare's UI, plus the separate `mcp-secret` rotation for `X-CRMBuilder-Secret`); troubleshooting (tunnel down, marker switch unnoticed → 409 response, claude.ai MCP registration drift).
- Add an entry to `crmbuilder/CLAUDE.md` under the v2 section naming the remote MCP URL `https://mcp.crmbuilder.ai`, the dual-layer auth model (Cloudflare Access edge via Service Token + `X-CRMBuilder-Secret` app middleware), and the marker-driven routing implication (claude.ai sees whichever engagement is active in the desktop UI's Engagements panel; mid-process marker changes require API restart).
- Add a note in `crmbuilder/CLAUDE.md` Tier-2 section that the remote MCP makes the `db-export/` JSON snapshots a strict fallback rather than the primary read path when claude.ai has tunnel access.

---

## Folding rationale

This kickoff folds step 5 (registration), the smoke test, and the documentation deliverables into one conversation. The PI-045 master kickoff allowed this fold as an option ("**one smoke-test conversation (or fold into the operational conversation)**"); the choice is settled here for three reasons:

1. **Step 5 is small.** ~10–15 minutes of work (rotation + registration + initial tool-list discovery). It does not warrant its own SES record + close-out + apply prompt.
2. **PI-045's bundling pattern.** SES-071 bundled four operational steps; SES-072 bundled three code slices. Bundling step 5 + smoke test + documentation under SES-073 matches the precedent and produces one PI-045 → Complete close-out rather than two.
3. **Registration is the precondition to the smoke test.** They are sequential dependencies, not separate workstreams.

The unfold alternative — step 5 in SES-073, smoke test + documentation in SES-074 — would produce a cleaner gate between "registration done" and "now we verify," but at the cost of an extra close-out cycle. If registration fails (claude.ai's MCP integration UI has moved, or one of the three headers needs a different syntax), the close-out captures the partial state with a follow-up conversation queued.

---

## Working pattern

Operating mode: **ARCHITECTURE** by project default, with **DETAIL**-flavor procedural walkthrough for the rotation and registration steps and for the 44-tool smoke-test checklist. Any consequential operational choice that surfaces (e.g., a claude.ai MCP integration UI option that has no obvious mapping to the three-header model) is surfaced under the eight-element template; routine choices are decided and announced inline.

Doug runs every executable step at his terminal (Linux Mint 22) and in the Cloudflare dashboard and claude.ai's MCP integration UI, pasting outputs and screenshots back. Claude provides UI-level navigation, bash command blocks, and diagnostic interpretation, and corrects procedure when Cloudflare or claude.ai's UI organization differs from this kickoff's assumptions.

---

## Deliverable shape

The conversation produces a triple-artifact close-out:

1. **`PRDs/product/crmbuilder-v2/close-out-payloads/ses_073.json`** — the close-out payload covering the conversation's session record plus any decisions it settles. No decisions are anticipated; all behavior is downstream of DEC-201..205 and DEC-225. The payload bundles the SES-073 record per the SES-046–SES-052 precedent.
2. **`PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-073.md`** — apply prompt for the close-out payload. The apply transactionally regenerates the db-export JSON snapshots; PI-045's status transitions from In Progress to Complete in the snapshot delta.
3. **Documentation commits** — `crmbuilder-v2/docs/remote-deployment.md` and the `crmbuilder/CLAUDE.md` Tier-2 update, committed and pushed together with the close-out payload + apply prompt per the sandbox commit-and-push convention.

If registration surfaces a consequential decision (a header-name conflict, an unexpected claude.ai MCP integration constraint, or a UI option whose interaction with the dual-layer model isn't obvious), it lands as DEC-226 in the SES-073 payload.

---

## Identifier note

This kickoff anticipates SES-073. SES-072 just pushed; the apply chain is SES-071 then SES-072 (apply order between them is unconstrained — both can apply in either order without collision since identifier spaces are disjoint). If other conversations close at SES-073 or beyond between the publishing of this kickoff and the opening of this conversation, rebase to the next available session identifier and the next available DEC range. The parallel-sandbox identifier-collision pattern has now happened five times in the recent program (SES-057→058 on Code Change Lifecycle; SES-058→059 between audit-v1.2 and PI-024; SES-062→063→064 during the SES-064 conversation; SES-068's occurrence; and SES-069→071 during SES-071 itself, the first rebase to skip an unapplied-but-claimed identifier). Verify identifier heads at the start of the conversation, and rebase pre-emptively if heads have advanced.

PI-032 (Code Change Lifecycle methodology rollout) remains the home for the reserve-at-apply-time identifier model that would eliminate this class of collisions.

---

## What's queued after this

Nothing depends on PI-045's completion. PI-045 is a free-standing deployment workstream and, on this conversation's close-out apply, PI-045 status flips Open → Complete and the workstream is done.

The closest adjacent workstream remains **Option B (remote-canonical migration)** as named in the master kickoff — moving the SQLite to a small VPS or migrating to a managed DB (Postgres, Turso), with all three actors reading and writing the remote canonical store equally. SES-064 explicitly rejected Option B as premature and named the conditions under which it becomes attractive (the laptop-online-time bound starts hurting actual claude.ai usage; ambient queries from off-laptop become a real need). Operating under Option A for several months will produce the usage data that informs whether Option B is justified.

---

## Out of scope (explicit)

- **REST API public exposure.** DEC-202 commits to MCP-only. Cloudflare Tunnel ingress has exactly one route. The REST API's `127.0.0.1:8765` binding is unchanged by this conversation.
- **Per-engagement tunnel deploys.** DEC-203 + DEC-205 commit to marker-driven single deployment. If concurrent multi-engagement claude.ai work becomes a regular pattern, the migration cost is one extra tunnel and one extra API process — not architectural — and is a separate workstream.
- **Secret-rotation tooling.** This conversation rotates the `claude-ai-mcp` Service Token Client Secret manually as a one-time hygiene step. A CLI command or desktop UI action that rotates all five touchpoints (two credential files, password manager, claude.ai's MCP integration custom headers, Cloudflare's Service Token refresh, the separate `mcp-secret` for `X-CRMBuilder-Secret`) coherently in one operation is out of scope; if rotation friction becomes real, it is a follow-up workstream.
- **`mcp-secret` rotation.** The `X-CRMBuilder-Secret` value at `~/.config/crmbuilder/mcp-secret` does not need rotation in this conversation — that value has not appeared in any conversation transcript and was generated locally during SES-072's setup. Only the Service Token Client Secret is rotated.
- **Option B remote-canonical migration.** See "What's queued after this." Revisitable when Option A's bounds start hurting.
- **Additional MCP transports.** FastMCP supports stdio, sse, and streamable-http. PI-045's scope is stdio (existing desktop-piped usage, unchanged) and streamable-http (this conversation's claude.ai path). SSE is not added.
