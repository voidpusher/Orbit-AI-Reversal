from fastapi import Depends, Header, HTTPException, Request, status

from app.core.config import get_settings
from app.services.auth import AuthContext, AuthService
from app.services.events import EventService
from app.services.queue import AnalysisQueue


def get_events(request: Request) -> EventService:
    return request.app.state.events


def get_queue(request: Request) -> AnalysisQueue:
    return request.app.state.queue


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth


async def get_auth_context(
    authorization: str | None = Header(default=None),
    auth: AuthService = Depends(get_auth_service),
) -> AuthContext:
    if get_settings().auth_disabled:
        return await auth.dev_context()
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    token = authorization.split(" ", 1)[1].strip()
    return await auth.resolve(token)
