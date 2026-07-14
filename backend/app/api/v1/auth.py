from fastapi import APIRouter, Depends, Header, status

from app.api.dependencies import get_auth_context, get_auth_service
from app.schemas import AuthMeResponse, AuthResponse, LoginRequest, SignupRequest
from app.schemas.auth import UsageSummary, UserProfile
from app.services.auth import AuthContext, AuthService, PLAN_LIMITS

router = APIRouter(tags=["auth"])


def _auth_response(token, record, user, org, role) -> AuthResponse:  # type: ignore[no-untyped-def]
    return AuthResponse(
        token=token,
        expires_at=record.expires_at,
        user=UserProfile(id=user.id, email=user.email, name=user.name, avatar_url=user.avatar_url),
        organization=org.name,
        plan=org.plan,
        role=role,
    )


@router.post("/auth/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, auth: AuthService = Depends(get_auth_service)) -> AuthResponse:
    token, record, user, org, role = await auth.signup(payload.email, payload.name, payload.password)
    return _auth_response(token, record, user, org, role)


@router.post("/auth/login", response_model=AuthResponse)
async def login(payload: LoginRequest, auth: AuthService = Depends(get_auth_service)) -> AuthResponse:
    token, record, user, org, role = await auth.login(payload.email, payload.password)
    return _auth_response(token, record, user, org, role)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    authorization: str | None = Header(default=None),
    auth: AuthService = Depends(get_auth_service),
) -> None:
    if authorization and authorization.lower().startswith("bearer "):
        await auth.logout(authorization.split(" ", 1)[1].strip())


@router.get("/me", response_model=AuthMeResponse)
async def get_me(
    ctx: AuthContext = Depends(get_auth_context),
    auth: AuthService = Depends(get_auth_service),
) -> AuthMeResponse:
    used = await auth.usage_this_month(ctx.organization.id)
    limit = PLAN_LIMITS.get(ctx.organization.plan)
    return AuthMeResponse(
        id=ctx.user.id,
        email=ctx.user.email,
        name=ctx.user.name,
        organization=ctx.organization.name,
        organization_id=ctx.organization.id,
        plan=ctx.organization.plan,
        role=ctx.role,
        usage=UsageSummary(analyses_this_month=used, monthly_limit=limit),
    )
