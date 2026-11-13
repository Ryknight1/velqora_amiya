"""Authentication request/response models."""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..utils.validation import sanitize_text

_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,24}$")


def _email(v: str) -> str:
    v = (v or "").strip().lower()
    if len(v) > 254 or not _EMAIL.match(v):
        raise ValueError("Enter a valid email address.")
    return v


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    password: str = Field(..., min_length=8, max_length=128)
    name: Optional[str] = Field(None, max_length=80)

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        return _email(v)

    @field_validator("name")
    @classmethod
    def _name(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_text(v, 80) or None


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        return _email(v)


class UserPublic(BaseModel):
    id: str
    email: str
    name: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic
