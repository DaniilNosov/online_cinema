import secrets
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config.settings import settings
from src.database.models.accounts import (
    User,
    UserGroup,
    UserGroupEnum,
    ActivationToken,
    PasswordResetToken,
    RefreshToken,
)
from src.schemas.accounts import (
    UserRegisterSchema,
    UserLoginSchema,
    TokenResponseSchema,
    PasswordChangeSchema,
    PasswordResetRequestSchema,
    PasswordResetConfirmSchema,
)
from src.security.hash import hash_password, verify_password
from src.security.jwt import create_access_token, create_refresh_token, decode_token
from src.notifications.emails import send_activation_email, send_password_reset_email


async def _get_or_create_default_group(db: AsyncSession) -> UserGroup:
    """Ensure standard user groups exist and return the default USER group."""
    stmt = select(UserGroup).where(UserGroup.name == UserGroupEnum.USER)
    result = await db.execute(stmt)
    user_group = result.scalar_one_or_none()

    if not user_group:
        for role in UserGroupEnum:
            db.add(UserGroup(name=role))
        await db.flush()
        result = await db.execute(stmt)
        user_group = result.scalar_one()

    return user_group


async def register_user(db: AsyncSession, data: UserRegisterSchema) -> dict:
    """Register a new inactive user and send an activation token via email."""
    stmt = select(User).where(User.email == data.email)
    existing_user = (await db.execute(stmt)).scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    user_group = await _get_or_create_default_group(db)

    new_user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        is_active=False,
        group_id=user_group.id,
    )
    db.add(new_user)
    await db.flush()

    raw_token = secrets.token_urlsafe(32)
    activation_token = ActivationToken(
        user_id=new_user.id,
        token=raw_token,
    )
    db.add(activation_token)
    await db.commit()

    await send_activation_email(new_user.email, raw_token)
    return {"message": "Registration successful. Please check your email to activate your account."}


async def activate_account(db: AsyncSession, token: str) -> dict:
    """Activate a user account using a valid activation token."""
    stmt = (
        select(ActivationToken)
        .options(selectinload(ActivationToken.user))
        .where(ActivationToken.token == token)
    )
    token_record = (await db.execute(stmt)).scalar_one_or_none()

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid activation token",
        )

    if token_record.expires_at < datetime.now(timezone.utc):
        await db.delete(token_record)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activation token has expired. Please request a new one.",
        )

    token_record.user.is_active = True
    await db.delete(token_record)
    await db.commit()

    return {"message": "Account activated successfully."}


async def resend_activation_token(db: AsyncSession, email: str) -> dict:
    """Generate and send a new activation token if the previous one expired."""
    stmt = (
        select(User)
        .options(selectinload(User.activation_token))
        .where(User.email == email)
    )
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email not found",
        )

    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is already active",
        )

    if user.activation_token:
        await db.delete(user.activation_token)
        await db.flush()

    raw_token = secrets.token_urlsafe(32)
    new_token = ActivationToken(user_id=user.id, token=raw_token)
    db.add(new_token)
    await db.commit()

    await send_activation_email(user.email, raw_token)
    return {"message": "A new activation token has been sent to your email."}


async def authenticate_user(db: AsyncSession, data: UserLoginSchema) -> TokenResponseSchema:
    """Verify credentials and issue JWT access and refresh tokens."""
    stmt = (
        select(User)
        .options(selectinload(User.group))
        .where(User.email == data.email)
    )
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not activated. Please check your email.",
        )

    payload = {"sub": str(user.id), "email": user.email, "role": user.group.name.value}
    access_token = create_access_token(payload)
    refresh_token = create_refresh_token(payload)

    db_refresh = RefreshToken(
        user_id=user.id,
        token=refresh_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(db_refresh)
    await db.commit()

    return TokenResponseSchema(access_token=access_token, refresh_token=refresh_token)


async def refresh_user_token(db: AsyncSession, refresh_token: str) -> TokenResponseSchema:
    """Issue a new access token using a valid refresh token."""
    payload = decode_token(refresh_token, token_type="refresh")
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    stmt = select(RefreshToken).where(RefreshToken.token == refresh_token)
    stored_token = (await db.execute(stmt)).scalar_one_or_none()

    if not stored_token or stored_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked or expired",
        )

    new_payload = {
        "sub": payload["sub"],
        "email": payload.get("email"),
        "role": payload.get("role"),
    }
    new_access_token = create_access_token(new_payload)
    return TokenResponseSchema(access_token=new_access_token, refresh_token=refresh_token)


async def logout_user(db: AsyncSession, refresh_token: str) -> dict:
    """Revoke a refresh token by deleting it from the database."""
    stmt = delete(RefreshToken).where(RefreshToken.token == refresh_token)
    await db.execute(stmt)
    await db.commit()
    return {"message": "Successfully logged out."}


async def change_user_password(
    db: AsyncSession, user: User, data: PasswordChangeSchema
) -> dict:
    """Change password for an authenticated user after verifying the old password."""
    if not verify_password(data.old_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password",
        )

    user.hashed_password = hash_password(data.new_password)
    await db.commit()
    return {"message": "Password changed successfully."}


async def request_password_reset(
    db: AsyncSession, data: PasswordResetRequestSchema
) -> dict:
    """Generate a password reset token and send it to the user's email."""
    stmt = (
        select(User)
        .options(selectinload(User.password_reset_token))
        .where(User.email == data.email)
    )
    user = (await db.execute(stmt)).scalar_one_or_none()

    # Return generic message even if user is not found to prevent email enumeration
    if not user or not user.is_active:
        return {"message": "If that email is registered and active, a reset token has been sent."}

    if user.password_reset_token:
        await db.delete(user.password_reset_token)
        await db.flush()

    raw_token = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(user_id=user.id, token=raw_token)
    db.add(reset_token)
    await db.commit()

    await send_password_reset_email(user.email, raw_token)
    return {"message": "If that email is registered and active, a reset token has been sent."}


async def confirm_password_reset(
    db: AsyncSession, data: PasswordResetConfirmSchema
) -> dict:
    """Reset user password using a valid password reset token."""
    stmt = (
        select(PasswordResetToken)
        .options(selectinload(PasswordResetToken.user))
        .where(PasswordResetToken.token == data.token)
    )
    token_record = (await db.execute(stmt)).scalar_one_or_none()

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password reset token",
        )

    if token_record.expires_at < datetime.now(timezone.utc):
        await db.delete(token_record)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token has expired",
        )

    token_record.user.hashed_password = hash_password(data.new_password)
    await db.delete(token_record)
    await db.commit()

    return {"message": "Password has been reset successfully."}
