"""Authentication, session, and tenant-context service.

Sessions are bearer tokens: the client sends `Authorization: Bearer <token>`, we
hash it and look up a live session, then resolve the user, their active
organization, and their role in it. Signup provisions a personal organization
with the user as owner.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import (
    generate_token,
    hash_password,
    hash_token,
    slugify,
    verify_password,
)
from app.models import (
    Analysis,
    AuditLog,
    Organization,
    OrganizationMember,
    Plan,
    Role,
    Session,
    User,
)

FREE_MONTHLY_ANALYSES = 25
PLAN_LIMITS: dict[str, int | None] = {
    Plan.FREE: FREE_MONTHLY_ANALYSES,
    Plan.PRO: None,
    Plan.ENTERPRISE: None,
}


DEV_EMAIL = "dev@orbit.local"


@dataclass
class AuthContext:
    user: User
    organization: Organization
    role: str
    session: Session | None


class AuthService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def signup(self, email: str, name: str, password: str) -> tuple[str, Session, User, Organization, str]:
        email = email.strip().lower()
        async with self._sessions() as session:
            existing = await session.scalar(select(User).where(User.email == email))
            if existing is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
            try:
                password_hash = hash_password(password)
            except ValueError as error:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error

            user = User(email=email, name=name.strip(), password_hash=password_hash)
            session.add(user)
            await session.flush()

            org = Organization(name=f"{name.split(' ')[0]}'s workspace", slug=await self._unique_slug(session, name))
            session.add(org)
            await session.flush()
            session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=Role.OWNER))

            token, record = self._new_session(user.id, org.id)
            session.add(record)
            session.add(AuditLog(organization_id=org.id, actor_id=user.id, action="user.signup", target_type="user", target_id=user.id))
            await session.commit()
            await session.refresh(record)
            await session.refresh(user)
            await session.refresh(org)
            return token, record, user, org, Role.OWNER

    async def login(self, email: str, password: str) -> tuple[str, Session, User, Organization, str]:
        email = email.strip().lower()
        async with self._sessions() as session:
            user = await session.scalar(select(User).where(User.email == email))
            if user is None or not verify_password(password, user.password_hash):
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
            membership = await session.scalar(
                select(OrganizationMember).where(OrganizationMember.user_id == user.id).order_by(OrganizationMember.created_at)
            )
            if membership is None:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has no organization")
            org = await session.get(Organization, membership.organization_id)
            token, record = self._new_session(user.id, org.id)
            session.add(record)
            await session.commit()
            await session.refresh(record)
            await session.refresh(user)
            await session.refresh(org)
            return token, record, user, org, membership.role

    async def oauth_upsert(
        self, provider: str, subject: str, email: str, name: str, avatar_url: str | None
    ) -> tuple[str, Session, User, Organization, str]:
        """Find-or-create a user for a verified OAuth profile and open a session."""
        email = email.strip().lower()
        async with self._sessions() as session:
            user = await session.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    email=email,
                    name=name.strip() or email.split("@")[0],
                    password_hash=None,
                    avatar_url=avatar_url,
                    oauth_provider=provider,
                    oauth_subject=subject,
                )
                session.add(user)
                await session.flush()
                org = Organization(
                    name=f"{user.name.split(' ')[0]}'s workspace",
                    slug=await self._unique_slug(session, user.name),
                )
                session.add(org)
                await session.flush()
                session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=Role.OWNER))
                session.add(AuditLog(
                    organization_id=org.id, actor_id=user.id, action="user.signup",
                    target_type="user", target_id=user.id, metadata_json={"via": provider},
                ))
                role = Role.OWNER
            else:
                # Link the provider to an existing account and keep the avatar fresh.
                if user.oauth_provider is None:
                    user.oauth_provider, user.oauth_subject = provider, subject
                if avatar_url:
                    user.avatar_url = avatar_url
                membership = await session.scalar(
                    select(OrganizationMember).where(OrganizationMember.user_id == user.id).order_by(OrganizationMember.created_at)
                )
                if membership is None:
                    raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has no organization")
                org = await session.get(Organization, membership.organization_id)
                role = membership.role

            token, record = self._new_session(user.id, org.id)
            session.add(record)
            await session.commit()
            await session.refresh(record)
            await session.refresh(user)
            await session.refresh(org)
            return token, record, user, org, role

    async def logout(self, token: str) -> None:
        async with self._sessions() as session:
            record = await session.scalar(select(Session).where(Session.token_hash == hash_token(token)))
            if record is not None:
                await session.delete(record)
                await session.commit()

    async def resolve(self, token: str) -> AuthContext:
        async with self._sessions() as session:
            record = await session.scalar(select(Session).where(Session.token_hash == hash_token(token)))
            if record is None or not record.is_valid():
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid")
            user = await session.get(User, record.user_id)
            org = await session.get(Organization, record.organization_id)
            if user is None or org is None:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session subject not found")
            membership = await session.scalar(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == user.id, OrganizationMember.organization_id == org.id
                )
            )
            role = membership.role if membership else Role.MEMBER
            record.last_used_at = datetime.now(timezone.utc)
            await session.commit()
            session.expunge(user)
            session.expunge(org)
            session.expunge(record)
            return AuthContext(user=user, organization=org, role=role, session=record)

    async def dev_context(self) -> AuthContext:
        """Auth-disabled mode: a default local workspace with no token required."""
        async with self._sessions() as session:
            user = await session.scalar(select(User).where(User.email == DEV_EMAIL))
            if user is None:
                user = User(email=DEV_EMAIL, name="Local Dev", password_hash=None)
                session.add(user)
                await session.flush()
                org = Organization(name="Local Workspace", slug=await self._unique_slug(session, "local"), plan=Plan.PRO)
                session.add(org)
                await session.flush()
                session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=Role.OWNER))
                await session.commit()
                await session.refresh(user)
                await session.refresh(org)
                role = Role.OWNER
            else:
                membership = await session.scalar(
                    select(OrganizationMember).where(OrganizationMember.user_id == user.id).order_by(OrganizationMember.created_at)
                )
                org = await session.get(Organization, membership.organization_id)
                role = membership.role
            session.expunge(user)
            session.expunge(org)
        return AuthContext(user=user, organization=org, role=role, session=None)

    async def usage_this_month(self, organization_id: str) -> int:
        start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        async with self._sessions() as session:
            count = await session.scalar(
                select(func.count()).select_from(Analysis).where(
                    Analysis.organization_id == organization_id, Analysis.requested_at >= start
                )
            )
        return int(count or 0)

    @staticmethod
    def _new_session(user_id: str, org_id: str) -> tuple[str, Session]:
        token = generate_token()
        return token, Session(token_hash=hash_token(token), user_id=user_id, organization_id=org_id)

    @staticmethod
    async def _unique_slug(session: AsyncSession, name: str) -> str:
        base = slugify(name)
        slug = base
        suffix = 1
        while await session.scalar(select(Organization.id).where(Organization.slug == slug)) is not None:
            suffix += 1
            slug = f"{base}-{suffix}"
        return slug
