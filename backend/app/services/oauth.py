"""Google + GitHub OAuth 2.0 authorization-code flow.

Each provider is active only when its client id and secret are configured. The
service builds the authorize URL, exchanges the returned code for an access
token, and normalizes the provider profile into a common shape. A short-lived
in-process state set provides CSRF protection for the round trip.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

import httpx

from app.core.config import Settings

_STATE_TTL_SECONDS = 600


class OAuthError(Exception):
    """Raised for any recoverable failure during the OAuth exchange."""


@dataclass
class OAuthProfile:
    provider: str
    subject: str
    email: str
    name: str
    avatar_url: str | None


@dataclass
class _Provider:
    authorize_url: str
    token_url: str
    userinfo_url: str
    scope: str


_PROVIDERS: dict[str, _Provider] = {
    "google": _Provider(
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        scope="openid email profile",
    ),
    "github": _Provider(
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        userinfo_url="https://api.github.com/user",
        scope="read:user user:email",
    ),
}


class OAuthService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._states: dict[str, float] = {}

    # -- configuration -----------------------------------------------------
    def providers(self) -> dict[str, bool]:
        return {name: self.is_configured(name) for name in _PROVIDERS}

    def credentials(self, provider: str) -> tuple[str | None, str | None]:
        if provider == "google":
            return self._settings.google_client_id, self._settings.google_client_secret
        if provider == "github":
            return self._settings.github_client_id, self._settings.github_client_secret
        return None, None

    def is_configured(self, provider: str) -> bool:
        client_id, client_secret = self.credentials(provider)
        return provider in _PROVIDERS and bool(client_id) and bool(client_secret)

    def redirect_uri(self, provider: str) -> str:
        base = self._settings.public_base_url.rstrip("/")
        return f"{base}/api/v1/auth/oauth/{provider}/callback"

    # -- CSRF state --------------------------------------------------------
    def issue_state(self) -> str:
        self._prune_states()
        state = secrets.token_urlsafe(24)
        self._states[state] = time.monotonic()
        return state

    def consume_state(self, state: str) -> bool:
        self._prune_states()
        return self._states.pop(state, None) is not None

    def _prune_states(self) -> None:
        cutoff = time.monotonic() - _STATE_TTL_SECONDS
        for key in [k for k, ts in self._states.items() if ts < cutoff]:
            self._states.pop(key, None)

    # -- flow --------------------------------------------------------------
    def authorize_url(self, provider: str, state: str) -> str:
        spec = _PROVIDERS[provider]
        client_id, _ = self.credentials(provider)
        params = {
            "client_id": client_id or "",
            "redirect_uri": self.redirect_uri(provider),
            "scope": spec.scope,
            "state": state,
            "response_type": "code",
        }
        if provider == "google":
            params["access_type"] = "online"
            params["prompt"] = "select_account"
        if provider == "github":
            params["allow_signup"] = "true"
        return str(httpx.URL(spec.authorize_url, params=params))

    async def exchange(self, provider: str, code: str) -> OAuthProfile:
        if not self.is_configured(provider):
            raise OAuthError(f"{provider} sign-in is not configured")
        spec = _PROVIDERS[provider]
        client_id, client_secret = self.credentials(provider)
        async with httpx.AsyncClient(timeout=20) as client:
            token_response = await client.post(
                spec.token_url,
                headers={"Accept": "application/json"},
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri(provider),
                    "grant_type": "authorization_code",
                },
            )
            if token_response.status_code >= 400:
                raise OAuthError("Failed to exchange authorization code")
            access_token = token_response.json().get("access_token")
            if not access_token:
                raise OAuthError("Provider did not return an access token")

            profile_response = await client.get(
                spec.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            )
            if profile_response.status_code >= 400:
                raise OAuthError("Failed to load the provider profile")
            data = profile_response.json()

            if provider == "github":
                email = data.get("email") or await self._github_primary_email(client, access_token)
                return _github_profile(data, email)
            return _google_profile(data)

    @staticmethod
    async def _github_primary_email(client: httpx.AsyncClient, access_token: str) -> str | None:
        response = await client.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        if response.status_code >= 400:
            return None
        emails = response.json()
        primary = next((e for e in emails if e.get("primary") and e.get("verified")), None)
        verified = next((e for e in emails if e.get("verified")), None)
        chosen = primary or verified
        return chosen.get("email") if chosen else None


def _google_profile(data: dict) -> OAuthProfile:
    email = data.get("email")
    if not email or data.get("email_verified") is False:
        raise OAuthError("A verified Google email is required")
    return OAuthProfile(
        provider="google",
        subject=str(data.get("sub", "")),
        email=email.lower(),
        name=data.get("name") or email.split("@")[0],
        avatar_url=data.get("picture"),
    )


def _github_profile(data: dict, email: str | None) -> OAuthProfile:
    if not email:
        raise OAuthError("A verified GitHub email is required")
    return OAuthProfile(
        provider="github",
        subject=str(data.get("id", "")),
        email=email.lower(),
        name=data.get("name") or data.get("login") or email.split("@")[0],
        avatar_url=data.get("avatar_url"),
    )
