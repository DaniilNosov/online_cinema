import re
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from src.database.models.accounts import GenderEnum, UserGroupEnum


def validate_password_complexity(password: str) -> str:
    """Validate that the password contains uppercase, lowercase, and numeric characters."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")
    return password


class UserRegisterSchema(BaseModel):
    """Schema for new user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        return validate_password_complexity(value)


class UserResponseSchema(BaseModel):
    """Schema for returning basic user information."""

    id: int
    email: EmailStr
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActivationRequestSchema(BaseModel):
    """Schema for account activation via token."""

    token: str


class LoginRequestSchema(BaseModel):
    """Schema for user login."""

    email: EmailStr
    password: str


class TokenResponseSchema(BaseModel):
    """Schema returning access and refresh JWT tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequestSchema(BaseModel):
    """Schema for requesting a new access token."""

    refresh_token: str


class AccessTokenResponseSchema(BaseModel):
    """Schema returning a newly issued access token."""

    access_token: str
    token_type: str = "bearer"


class PasswordResetRequestSchema(BaseModel):
    """Schema for requesting a password reset email."""

    email: EmailStr


class PasswordResetConfirmSchema(BaseModel):
    """Schema for completing a password reset with a new password."""

    token: str
    new_password: str = Field(..., min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def check_new_password(cls, value: str) -> str:
        return validate_password_complexity(value)


class PasswordChangeSchema(BaseModel):
    """Schema for changing the password of an authenticated user."""

    old_password: str
    new_password: str = Field(..., min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def check_new_password(cls, value: str) -> str:
        return validate_password_complexity(value)


class UserProfileResponseSchema(BaseModel):
    """Schema for displaying user profile details."""

    id: int
    user_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar: Optional[str] = None
    gender: Optional[GenderEnum] = None
    date_of_birth: Optional[date] = None
    info: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdateSchema(BaseModel):
    """Schema for updating user profile fields."""

    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    gender: Optional[GenderEnum] = None
    date_of_birth: Optional[date] = None
    info: Optional[str] = None


class UserRoleUpdateSchema(BaseModel):
    """Schema for changing a user's group (role) by an administrator."""

    role: UserGroupEnum
