"""OAuth 2.1 + PKCE authorization server for the MCP HTTP transport.

The MCP server is its own authorization server (the mcp SDK's
:class:`OAuthAuthorizationServerProvider`), with human authentication
delegated to Google via OIDC. This replaces Cloudflare Managed OAuth,
whose Beta dropped the per-request ``resource`` and ``code_challenge``
parameters across its login step and so could never complete a PKCE
flow for a public client (empirically confirmed — see the AI-surface
notes in ``CLAUDE.md``). Because we build the authorization-code record
from the SDK-supplied ``AuthorizationParams`` ourselves, those params
are preserved by construction.

Flow:

1. claude.ai registers via DCR -> :meth:`CRMBuilderOAuthProvider.register_client`.
2. claude.ai opens ``/authorize`` -> :meth:`authorize` stashes the pending
   request (``code_challenge`` + ``resource`` preserved) and returns a
   redirect to Google.
3. Google authenticates the user and redirects to
   ``/oauth/google/callback`` (:func:`register_oauth_routes`), which verifies
   the id_token, enforces the allowed email, mints a one-time authorization
   code, and redirects back to claude.ai.
4. claude.ai POSTs ``/token``; the SDK verifies PKCE-S256, then calls
   :meth:`exchange_authorization_code`, which mints a signed JWT access token
   (``aud`` = the resource) plus an opaque rotating refresh token.
5. Each ``/mcp`` request carries the bearer token; the SDK calls
   :meth:`load_access_token` for stateless JWT validation.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from crmbuilder_v2.config import Settings

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}
JWT_ALG = "HS256"


class UnauthorizedUserError(Exception):
    """The authenticated Google identity is not the allowed email."""


def get_or_create_jwt_secret(settings: Settings) -> str:
    """Return the JWT signing secret, generating + persisting one if unset.

    A stable secret is required so access tokens survive server restarts;
    we keep it out of source by storing it in a ``0600`` file next to the
    OAuth DB (both gitignored via ``*.db``/data conventions).
    """
    if settings.oauth_jwt_secret:
        return settings.oauth_jwt_secret
    secret_file = settings.oauth_db_path.parent / "oauth_jwt_secret"
    if secret_file.exists():
        return secret_file.read_text().strip()
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_urlsafe(48)
    secret_file.write_text(value)
    secret_file.chmod(0o600)
    return value


class _Store:
    """SQLite persistence for clients, auth codes, refresh tokens, logins.

    Persistence matters so claude.ai's DCR registration and refresh tokens
    survive an MCP-server restart; access tokens are stateless JWTs and need
    no storage. Expired rows are pruned lazily on read.
    """

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS clients(
                    client_id TEXT PRIMARY KEY, info TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS auth_codes(
                    code TEXT PRIMARY KEY, data TEXT NOT NULL,
                    expires_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS refresh_tokens(
                    token TEXT PRIMARY KEY, data TEXT NOT NULL,
                    expires_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS pending_logins(
                    state TEXT PRIMARY KEY, data TEXT NOT NULL,
                    expires_at REAL NOT NULL);
                """
            )

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def put_client(self, client_id: str, info: str) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO clients(client_id, info) VALUES(?, ?)",
                (client_id, info),
            )

    def get_client(self, client_id: str) -> str | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT info FROM clients WHERE client_id=?", (client_id,)
            ).fetchone()
        return row["info"] if row else None

    def _put_expiring(self, table: str, key: str, data: str, exp: float) -> None:
        col = "code" if table == "auth_codes" else (
            "token" if table == "refresh_tokens" else "state"
        )
        with self._conn() as c:
            c.execute(
                f"INSERT OR REPLACE INTO {table}({col}, data, expires_at) "
                f"VALUES(?, ?, ?)",
                (key, data, exp),
            )

    def _get_expiring(self, table: str, col: str, key: str) -> str | None:
        with self._conn() as c:
            row = c.execute(
                f"SELECT data, expires_at FROM {table} WHERE {col}=?", (key,)
            ).fetchone()
            if row is None:
                return None
            if row["expires_at"] < time.time():
                c.execute(f"DELETE FROM {table} WHERE {col}=?", (key,))
                return None
        return row["data"]

    def _del(self, table: str, col: str, key: str) -> None:
        with self._conn() as c:
            c.execute(f"DELETE FROM {table} WHERE {col}=?", (key,))

    def put_code(self, code: str, data: str, exp: float) -> None:
        self._put_expiring("auth_codes", code, data, exp)

    def get_code(self, code: str) -> str | None:
        return self._get_expiring("auth_codes", "code", code)

    def del_code(self, code: str) -> None:
        self._del("auth_codes", "code", code)

    def put_refresh(self, token: str, data: str, exp: float) -> None:
        self._put_expiring("refresh_tokens", token, data, exp)

    def get_refresh(self, token: str) -> str | None:
        return self._get_expiring("refresh_tokens", "token", token)

    def del_refresh(self, token: str) -> None:
        self._del("refresh_tokens", "token", token)

    def put_pending(self, state: str, data: str, exp: float) -> None:
        self._put_expiring("pending_logins", state, data, exp)

    def get_pending(self, state: str) -> str | None:
        return self._get_expiring("pending_logins", "state", state)

    def del_pending(self, state: str) -> None:
        self._del("pending_logins", "state", state)


class CRMBuilderOAuthProvider(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    """OAuth AS provider delegating human auth to Google OIDC."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._store = _Store(settings.oauth_db_path)
        self._secret = get_or_create_jwt_secret(settings)
        self._jwks = PyJWKClient(GOOGLE_JWKS_URI)

    # --- DCR ---------------------------------------------------------------
    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        info = self._store.get_client(client_id)
        return OAuthClientInformationFull.model_validate_json(info) if info else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self._store.put_client(client_info.client_id, client_info.model_dump_json())

    # --- authorize: hand off to Google ------------------------------------
    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        login_state = secrets.token_urlsafe(32)
        pending = {
            "client_id": client.client_id,
            "redirect_uri": str(params.redirect_uri),
            "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
            "client_state": params.state,
            "code_challenge": params.code_challenge,
            "scopes": params.scopes or [],
            "resource": params.resource,
        }
        self._store.put_pending(
            login_state,
            json.dumps(pending),
            time.time() + self._settings.auth_code_ttl,
        )
        google_params = {
            "client_id": self._settings.google_client_id,
            "redirect_uri": self._settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email",
            "state": login_state,
            "access_type": "online",
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(google_params)}"

    async def complete_login(self, login_state: str, google_code: str) -> str:
        """Finish the Google round-trip and return the claude.ai redirect URL.

        Raises :class:`KeyError` for an unknown/expired login state and
        :class:`UnauthorizedUserError` when the verified email is not allowed.
        """
        raw = self._store.get_pending(login_state)
        if raw is None:
            raise KeyError("unknown or expired login state")
        pending = json.loads(raw)

        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.post(
                GOOGLE_TOKEN_ENDPOINT,
                data={
                    "code": google_code,
                    "client_id": self._settings.google_client_id,
                    "client_secret": self._settings.google_client_secret,
                    "redirect_uri": self._settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
        resp.raise_for_status()
        id_token = resp.json()["id_token"]

        signing_key = self._jwks.get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=self._settings.google_client_id,
        )
        if claims.get("iss") not in GOOGLE_ISSUERS:
            raise UnauthorizedUserError("unexpected token issuer")
        email = (claims.get("email") or "").lower()
        if not claims.get("email_verified") or email != self._settings.oauth_allowed_email.lower():
            raise UnauthorizedUserError(f"email not authorized: {email or '(none)'}")

        code = secrets.token_urlsafe(32)
        self._store.put_code(
            code,
            json.dumps(
                {
                    "client_id": pending["client_id"],
                    "redirect_uri": pending["redirect_uri"],
                    "redirect_uri_provided_explicitly": pending[
                        "redirect_uri_provided_explicitly"
                    ],
                    "code_challenge": pending["code_challenge"],
                    "scopes": pending["scopes"],
                    "resource": pending["resource"],
                }
            ),
            time.time() + self._settings.auth_code_ttl,
        )
        self._store.del_pending(login_state)

        extra = {"code": code}
        if pending.get("client_state") is not None:
            extra["state"] = pending["client_state"]
        return construct_redirect_uri(pending["redirect_uri"], **extra)

    # --- authorization code ------------------------------------------------
    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        raw = self._store.get_code(authorization_code)
        if raw is None:
            return None
        d = json.loads(raw)
        if d["client_id"] != client.client_id:
            return None
        return AuthorizationCode(
            code=authorization_code,
            scopes=d["scopes"],
            expires_at=time.time() + self._settings.auth_code_ttl,
            client_id=d["client_id"],
            code_challenge=d["code_challenge"],
            redirect_uri=d["redirect_uri"],
            redirect_uri_provided_explicitly=d["redirect_uri_provided_explicitly"],
            resource=d["resource"],
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        # PKCE-S256 has already been verified by the SDK token handler.
        self._store.del_code(authorization_code.code)
        resource = authorization_code.resource or self._settings.mcp_public_url
        scopes = authorization_code.scopes
        access = self._mint_access(client.client_id, scopes, resource)
        refresh = self._issue_refresh(client.client_id, scopes, resource)
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=self._settings.access_token_ttl,
            scope=" ".join(scopes) if scopes else None,
            refresh_token=refresh,
        )

    # --- refresh -----------------------------------------------------------
    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        raw = self._store.get_refresh(refresh_token)
        if raw is None:
            return None
        d = json.loads(raw)
        if d["client_id"] != client.client_id:
            return None
        return RefreshToken(
            token=refresh_token,
            client_id=d["client_id"],
            scopes=d["scopes"],
            expires_at=int(time.time() + self._settings.refresh_token_ttl),
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        raw = self._store.get_refresh(refresh_token.token)
        if raw is None:
            from mcp.server.auth.provider import TokenError

            raise TokenError("invalid_grant", "refresh token not found")
        d = json.loads(raw)
        resource = d.get("resource") or self._settings.mcp_public_url
        granted = scopes or d["scopes"]
        # Rotate the refresh token.
        self._store.del_refresh(refresh_token.token)
        access = self._mint_access(client.client_id, granted, resource)
        new_refresh = self._issue_refresh(client.client_id, granted, resource)
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=self._settings.access_token_ttl,
            scope=" ".join(granted) if granted else None,
            refresh_token=new_refresh,
        )

    # --- access token validation ------------------------------------------
    async def load_access_token(self, token: str) -> AccessToken | None:
        # The SDK normalizes the PRM ``resource`` to include a trailing slash,
        # so claude.ai sends (and we mint) ``aud`` with the slash while the
        # configured public URL may lack it. Accept both forms rather than
        # exact-matching, or every request would 401.
        base = self._settings.mcp_public_url.rstrip("/")
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[JWT_ALG],
                audience=[base, base + "/"],
                issuer=base,
            )
        except jwt.PyJWTError:
            return None
        scope = claims.get("scope") or ""
        return AccessToken(
            token=token,
            client_id=claims.get("client_id", ""),
            scopes=scope.split() if scope else [],
            expires_at=claims.get("exp"),
            resource=claims.get("aud"),
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        # Refresh tokens are stored and can be invalidated; access tokens are
        # stateless JWTs that expire on their own (no denylist for a
        # single-user tool).
        self._store.del_refresh(token.token)

    # --- helpers -----------------------------------------------------------
    def _mint_access(self, client_id: str, scopes: list[str], resource: str) -> str:
        now = int(time.time())
        claims = {
            "iss": self._settings.mcp_public_url.rstrip("/"),
            "sub": self._settings.oauth_allowed_email,
            "aud": resource,
            "client_id": client_id,
            "scope": " ".join(scopes),
            "iat": now,
            "exp": now + self._settings.access_token_ttl,
            "jti": secrets.token_urlsafe(8),
        }
        return jwt.encode(claims, self._secret, algorithm=JWT_ALG)

    def _issue_refresh(self, client_id: str, scopes: list[str], resource: str) -> str:
        token = secrets.token_urlsafe(32)
        self._store.put_refresh(
            token,
            json.dumps({"client_id": client_id, "scopes": scopes, "resource": resource}),
            time.time() + self._settings.refresh_token_ttl,
        )
        return token


def register_oauth_routes(server, provider: CRMBuilderOAuthProvider) -> None:
    """Mount the Google OIDC callback route on the FastMCP app."""
    from starlette.responses import HTMLResponse, RedirectResponse

    @server.custom_route("/oauth/google/callback", methods=["GET"])
    async def google_callback(request):  # noqa: ANN001, ANN202
        if err := request.query_params.get("error"):
            return HTMLResponse(f"Google sign-in error: {err}", status_code=400)
        state = request.query_params.get("state")
        code = request.query_params.get("code")
        if not state or not code:
            return HTMLResponse("Missing state or code", status_code=400)
        try:
            redirect_url = await provider.complete_login(state, code)
        except UnauthorizedUserError as exc:
            return HTMLResponse(f"Not authorized: {exc}", status_code=403)
        except KeyError:
            return HTMLResponse(
                "Login session expired — restart the connection.", status_code=400
            )
        except Exception as exc:  # noqa: BLE001 — surface a readable error page
            return HTMLResponse(f"Login failed: {exc}", status_code=400)
        return RedirectResponse(redirect_url, status_code=302)
