# CRMBuilder V2 — New User Setup Guide

This guide walks you, step by step, through installing the CRMBuilder V2 desktop
application and connecting it to the shared cloud backend at
**`https://api.crmbuilder.ai`**. When you finish, the app on your computer will
sign in with your personal access token and work against the same shared data as
the rest of the team.

**Time required:** about 15 minutes. **You do not need to run a server or a
database** — those live in the cloud. You only install the desktop app and point
it at the cloud with your token.

---

## Before you start — what you need

| Requirement | Notes |
|---|---|
| **A computer with a desktop** (Windows, macOS, or Linux with a GUI) | The app is a desktop window; it won't run on a headless server. |
| **Access to the code repository** | GitHub repo `dbower44022/crmbuilder`. Ask the administrator to add you as a collaborator if you get a "permission denied" on clone. |
| **`git`** | To download the code. |
| **`uv`** (Python package manager) | Installs Python 3.12 and all dependencies for you — see Step 1. |
| **Your access token** | A personal secret the administrator mints for you — see Step 4. |

You do **not** need to install Python, PostgreSQL, or any server software yourself.

---

## Step 1 — Install `uv`

`uv` manages the correct Python version and all dependencies automatically.

- **macOS / Linux:**
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
  Then close and reopen your terminal (so `uv` is on your `PATH`).

- **Windows (PowerShell):**
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

Verify it worked:
```bash
uv --version
```

---

## Step 2 — Download the code

Clone the repository to a folder of your choice:
```bash
git clone git@github.com:dbower44022/crmbuilder.git
cd crmbuilder
```

If you get a permission error, ask the administrator to grant you access to the
`dbower44022/crmbuilder` repository, then try again. (If you use HTTPS instead of
SSH, the URL is `https://github.com/dbower44022/crmbuilder.git`.)

---

## Step 3 — Install the application

From inside the `crmbuilder` folder:
```bash
uv sync
```

This creates an isolated environment and installs everything the app needs. The
first run downloads dependencies and can take a couple of minutes. When it
finishes you'll have the `crmbuilder-v2-ui` command available.

---

## Step 4 — Get your access token

The cloud backend requires a personal token to sign in. **You don't create this
yourself — the administrator mints it for you.**

1. Send the administrator the email address you want to use.
2. They will send you back a token that looks like `crmbv2_XXXXXXXXXXXXXXXXXXXX`.
3. **Treat it like a password:** store it in a password manager, never paste it
   into chat, email it only over a secure channel, and never commit it to git.

Your token also carries a **role** (usually *editor* — read and write, or
*viewer* — read only) and grants access to a specific engagement (workspace).

---

## Step 5 — Configure the app to use the cloud

Create a small configuration file that tells the app where the cloud is and who
you are. The file lives at:

```
crmbuilder-v2/data/crmbuilder.env
```

(The `crmbuilder-v2/data/` folder already exists in the clone.) Create the file
with these two lines, pasting **your** token after the `=`:

```bash
CRMBUILDER_V2_API_BASE_URL=https://api.crmbuilder.ai
CRMBUILDER_V2_API_TOKEN=crmbv2_your_token_here
```

Quick way to create it from the terminal (replace the token first):
```bash
cat > crmbuilder-v2/data/crmbuilder.env <<'EOF'
CRMBUILDER_V2_API_BASE_URL=https://api.crmbuilder.ai
CRMBUILDER_V2_API_TOKEN=crmbv2_your_token_here
EOF
chmod 600 crmbuilder-v2/data/crmbuilder.env
```

This file is **gitignored**, so your token will not be committed. Because the app
is pointed at a remote backend, it will connect to the cloud and **will not try
to start a local server** — if the cloud is ever unreachable it shows a clear
"cannot reach the cloud API" message rather than falling back to a local copy.

> **Alternative:** instead of the file, you can set the same two values as
> environment variables (`CRMBUILDER_V2_API_BASE_URL` and
> `CRMBUILDER_V2_API_TOKEN`). Real environment variables take precedence over the
> file.

---

## Step 6 — Run the app

From the `crmbuilder` folder:
```bash
uv run crmbuilder-v2-ui
```

The desktop window opens and connects to `https://api.crmbuilder.ai` using your
token.

---

## Step 7 — First run: pick your workspace and verify

1. In the app, use the **engagement (workspace) selector** near the top to choose
   your engagement (for the main workspace this is **CRMBUILDER / ENG-001**). The
   administrator will tell you which one you belong to.
2. Open a panel from the sidebar (for example **Planning Items** or
   **Requirements**). If you can see records, you're connected and authenticated
   correctly. 🎉

You're now working against the same shared cloud data as everyone else — changes
you make are immediately visible to the team (subject to your role).

---

## Troubleshooting

| Symptom | Cause & fix |
|---|---|
| **"Cannot reach the CRMBuilder cloud API…" banner** | Network/DNS issue, or the URL is wrong. Check `CRMBUILDER_V2_API_BASE_URL` is exactly `https://api.crmbuilder.ai`, and that `https://api.crmbuilder.ai/health` opens in your browser and shows `{"data":{"ok":true}...}`. |
| **Sign-in / "401 Unauthorized"** | Missing or wrong token. Re-check `CRMBUILDER_V2_API_TOKEN` in the env file (no extra spaces or line breaks). If it still fails, ask the administrator to mint a fresh token. |
| **"403 … not assigned to engagement" or empty panels** | Your token isn't assigned to that engagement, or you haven't selected the right one. Pick the correct engagement in the selector; if it persists, ask the administrator to assign your role to that engagement. |
| **`uv: command not found`** | Reopen your terminal after installing `uv`, or add it to your `PATH`. |
| **On Linux: an error mentioning `libGL.so.1` when starting** | Install the Qt runtime libraries: `sudo apt-get install -y libgl1 libegl1 libxkbcommon0`. |
| **"permission denied" cloning the repo** | Ask the administrator to add you as a collaborator on `dbower44022/crmbuilder`. |

---

## Keeping up to date

When the team ships updates, refresh your copy:
```bash
git pull
uv sync
```
Then start the app again with `uv run crmbuilder-v2-ui`.

---

## Security reminders

- Your token is a **personal credential** — do not share it; each person gets
  their own.
- Never commit `crmbuilder-v2/data/crmbuilder.env` (it's gitignored by default).
- If your token is ever exposed, tell the administrator so they can revoke it and
  mint you a new one.

---

## Appendix A — For the administrator (provisioning a new user)

New users can't self-register; an administrator with an **owner** token creates
their identity, role, and token. Two supported ways:

**A. On the server, using the access layer (keeps the token off any chat):**
```bash
ssh root@<api-droplet>
cd /opt/crmbuilder
.venv/bin/python3 - <<'PY'
from crmbuilder_v2.access import principal as P
from crmbuilder_v2.access.db import session_scope
import pathlib
with session_scope() as s:
    pr = P.create_principal(s, kind="human", display_name="Full Name",
                            identity="user@example.com")
    P.assign_role(s, principal_id=pr.principal_id,
                  engagement_id="ENG-001", role="editor")   # or "viewer"
    tok = P.mint_token(s, principal_id=pr.principal_id, label="team")
    pathlib.Path("/root/newuser-token.txt").write_text(tok.plaintext + "\n")
    print("principal:", pr.principal_id, "token id:", tok.token_id)
PY
# then: cat /root/newuser-token.txt   -> hand to the user securely, then rm it
```

**B. Over the admin REST API with an owner token** (`POST /admin/principals`,
`POST /admin/principals/{id}/roles`, `POST /admin/tokens`).

**Roles:** `owner` (full admin), `editor` (read/write), `viewer` (read only).
Every human user needs a **role assignment on the engagement** they'll work in
(e.g. `ENG-001`) or the API returns `403 engagement_forbidden`. The
`crmbuilder-v2-token bootstrap-owner --identity … --engagement ENG-001` command
is the shortcut for creating the first owner.
