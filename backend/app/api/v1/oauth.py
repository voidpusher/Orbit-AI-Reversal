import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.api.dependencies import get_auth_service
from app.core.config import get_settings
from app.services.auth import AuthService
from app.services.oauth import OAuthError, OAuthService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/oauth", tags=["auth"])


def get_oauth_service(request: Request) -> OAuthService:
    return request.app.state.oauth


def _frontend_redirect(fragment: str) -> RedirectResponse:
    base = get_settings().frontend_base_url.rstrip("/")
    # Token/error are delivered in the URL fragment so they never reach server logs.
    return RedirectResponse(url=f"{base}/login#{fragment}", status_code=302)


@router.get("/providers")
async def providers(oauth: OAuthService = Depends(get_oauth_service)) -> dict[str, bool]:
    return oauth.providers()


@router.get("/{provider}/start")
async def start(provider: str, oauth: OAuthService = Depends(get_oauth_service)) -> RedirectResponse:
    if not oauth.is_configured(provider):
        return _frontend_redirect(urlencode({"error": f"{provider}_unconfigured"}))
    state = oauth.issue_state()
    return RedirectResponse(url=oauth.authorize_url(provider, state), status_code=302)


@router.get("/{provider}/callback")
async def callback(
    provider: str,
    request: Request,
    oauth: OAuthService = Depends(get_oauth_service),
    auth: AuthService = Depends(get_auth_service),
) -> RedirectResponse:
    params = request.query_params
    if params.get("error"):
        return _frontend_redirect(urlencode({"error": params.get("error", "access_denied")}))
    code = params.get("code")
    state = params.get("state")
    if not code or not state or not oauth.consume_state(state):
        return _frontend_redirect(urlencode({"error": "invalid_oauth_state"}))
    try:
        profile = await oauth.exchange(provider, code)
        token, _, _, _, _ = await auth.oauth_upsert(
            profile.provider, profile.subject, profile.email, profile.name, profile.avatar_url
        )
    except OAuthError as error:
        logger.warning("oauth exchange failed: %s", error)
        return _frontend_redirect(urlencode({"error": "oauth_failed"}))
    except Exception:
        logger.exception("unexpected oauth failure")
        return _frontend_redirect(urlencode({"error": "oauth_failed"}))
    return _frontend_redirect(urlencode({"token": token}))
