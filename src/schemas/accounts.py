import re
from datetime import date
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
from src.database.models.accounts import UserGroupEnum, GenderEnum


class UserRegisterSchema(BaseModel):
    """Schema for user registration with password complexity validation."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must contain letters and numbers")

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, value: str) -> str:
        """Enforce password complexity: at least one letter and one number."""
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValueError("Password must contain at least one letter and one digit")
        return value


class UserLoginSchema(BaseModel):
    """Schema for user authentication."""
    email: EmailStr
    password: str


class TokenResponseSchema(BaseModel):
    """Schema for returning JWT token pairs."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class PasswordChangeSchema(BaseModel):
    """Schema for changing password when the old one is known."""
    old_password: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_password_complexity(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValueError("New password must contain at least one letter and one digit")
        return value


class PasswordResetRequestSchema(BaseModel):
    """Schema for requesting a password reset via email."""
    email: EmailStr


class PasswordResetConfirmSchema(BaseModel):
    """Schema for setting a new password using a reset token."""
    token: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_password_complexity(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValueError("New password must contain at least one letter and one digit")
        return value


class UserProfileResponseSchema(BaseModel):
    """Schema for displaying user profile details."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar: Optional[str] = None
    gender: Optional[GenderEnum] = None
    date_of_birth: Optional[date] = None
    info: Optional[str] = None

    class Config:
        from_attributes = True
