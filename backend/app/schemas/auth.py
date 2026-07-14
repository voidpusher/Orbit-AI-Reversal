import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# Pragmatic email shape check (email-validator is not a dependency).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class _EmailMixin(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not _EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address")
        return value


class SignupRequest(_EmailMixin):
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(_EmailMixin):
    password: str = Field(min_length=1, max_length=200)


class UserProfile(BaseModel):
    id: str
    email: str
    name: str
    avatar_url: str | None = None


class UsageSummary(BaseModel):
    analyses_this_month: int
    monthly_limit: int | None  # None means unlimited


class MeResponse(BaseModel):
    id: str
    email: str
    name: str
    organization: str
    organization_id: str
    plan: str
    role: str
    usage: UsageSummary


class AuthResponse(BaseModel):
    token: str
    expires_at: datetime
    user: UserProfile
    organization: str
    plan: str
    role: str
