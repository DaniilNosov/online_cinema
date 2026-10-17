import enum
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
)
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class UserGroupEnum(str, enum.Enum):
    """Enumeration of user roles and permissions."""

    USER = "USER"
    MODERATOR = "MODERATOR"
    ADMIN = "ADMIN"


class GenderEnum(str, enum.Enum):
    """Enumeration of user genders."""

    MAN = "MAN"
    WOMAN = "WOMAN"


class UserGroup(Base):
    """Stores user groups (roles): USER, MODERATOR, ADMIN."""

    __tablename__ = "user_groups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[UserGroupEnum] = mapped_column(SQLAlchemyEnum(UserGroupEnum), unique=True, nullable=False)

    # One-to-many relationship with User
    users: Mapped[List["User"]] = relationship("User", back_populates="group")


class User(Base):
    """Represents registered users in the system."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    group_id: Mapped[int] = mapped_column(ForeignKey("user_groups.id", ondelete="RESTRICT"), nullable=False)

    # Relationships
    group: Mapped["UserGroup"] = relationship("UserGroup", back_populates="users")
    profile: Mapped[Optional["UserProfile"]] = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    activation_token: Mapped[Optional["ActivationToken"]] = relationship(
        "ActivationToken",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    password_reset_token: Mapped[Optional["PasswordResetToken"]] = relationship(
        "PasswordResetToken",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserProfile(Base):
    """Stores additional personal information for a user (1:1 with User)."""

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    avatar: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    gender: Mapped[Optional[GenderEnum]] = mapped_column(SQLAlchemyEnum(GenderEnum), nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # One-to-one relationship with User
    user: Mapped["User"] = relationship("User", back_populates="profile")


class ActivationToken(Base):
    """Token sent via email to activate a newly registered user account."""

    __tablename__ = "activation_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(hours=24),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="activation_token")


class PasswordResetToken(Base):
    """Token sent via email to reset a forgotten user password."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(hours=1),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="password_reset_token")


class RefreshToken(Base):
    """JWT Refresh token stored in DB to allow session revocation on logout."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")
