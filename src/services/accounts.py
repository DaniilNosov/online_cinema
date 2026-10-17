from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config.settings import settings
from src.database.models.accounts import (
    ActivationToken,
    PasswordResetToken,
    RefreshToken,
    User,
    UserGroup,
    UserGroupEnum,
    UserProfile,
)
from src.notifications.emails import send_email
from src.schemas.accounts import (
    AccessTokenResponseSchema,
    ActivationRequestSchema,
    LoginRequestSchema,
    PasswordChangeSchema,
    PasswordResetConfirmSchema,
    PasswordResetRequestSchema,
    RefreshTokenRequestSchema,
    TokenResponseSchema,
    UserProfileUpdateSchema,
    UserRegisterSchema,
    UserRoleUpdateSchema,
)
from src.security.hash import hash_password, verify_password
from src.security.jwt import create_access_token, create_refresh_token, decode_token
from src.storages.s3 import s3_client


def _is_expired(expires_at: datetime) -> bool:
    """Safely check if a datetime has expired, handling both naive and aware datetimes."""
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at < datetime.now(timezone.utc)


async def _get_or_create_default_group(db: AsyncSession, role: UserGroupEnum = UserGroupEnum.USER) -> UserGroup:
    """Fetch the specified user group or create it if it does not exist."""
    stmt = select(UserGroup).where(UserGroup.name == role)
    group = (await db.execute(stmt)).scalar_one_or_none()
    if not group:
        group = UserGroup(name=role)
        db.add(group)
        await db.flush()
    return group


async def register_user(db: AsyncSession, data: UserRegisterSchema) -> User:
    """Register a new inactive user, generate an activation token, and send an email."""
    existing = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user_group = await _get_or_create_default_group(db, UserGroupEnum.USER)
    new_user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        is_active=False,
        group_id=user_group.id,
    )
    db.add(new_user)
    await db.flush()

    token_str = uuid4().hex
    activation_token = ActivationToken(
        user_id=new_user.id,
        token=token_str,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(activation_token)
    await db.commit()
    await db.refresh(new_user)

    await send_email(
        to_email=new_user.email,
        subject="Activate Your Online Cinema Account",
        body=f"Welcome! Use this token to activate your account: {token_str}",
    )
    return new_user


async def activate_account(db: AsyncSession, data: ActivationRequestSchema) -> dict:
    """Activate a user account using a valid activation token."""
    stmt = (
        select(ActivationToken).options(selectinload(ActivationToken.user)).where(ActivationToken.token == data.token)
    )
    token_record = (await db.execute(stmt)).scalar_one_or_none()

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid activation token",
        )

    if _is_expired(token_record.expires_at):
        await db.delete(token_record)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activation token has expired",
        )

    user = token_record.user
    user.is_active = True
    await db.delete(token_record)
    await db.commit()
    return {"message": "Account activated successfully"}


async def login_user(db: AsyncSession, data: LoginRequestSchema) -> TokenResponseSchema:
    """Authenticate a user and issue access and refresh JWT tokens."""
    stmt = select(User).options(selectinload(User.group)).where(User.email == data.email)
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

    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.group.name.value,
        "pwd_fgp": user.hashed_password[-16:],
    }
    access_token = create_access_token(payload)
    refresh_token_str = create_refresh_token(payload)

    db_refresh = RefreshToken(
        user_id=user.id,
        token=refresh_token_str,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(db_refresh)
    await db.commit()

    return TokenResponseSchema(
        access_token=access_token,
        refresh_token=refresh_token_str,
    )


async def refresh_user_token(db: AsyncSession, data: RefreshTokenRequestSchema) -> AccessTokenResponseSchema:
    """Validate a refresh token and issue a new access token."""
    payload = decode_token(data.refresh_token, settings.SECRET_KEY_REFRESH)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    stmt = select(RefreshToken).where(RefreshToken.token == data.refresh_token)
    stored_token = (await db.execute(stmt)).scalar_one_or_none()

    if not stored_token or _is_expired(stored_token.expires_at):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or has been revoked",
        )

    user_stmt = select(User).options(selectinload(User.group)).where(User.id == stored_token.user_id)
    user = (await db.execute(user_stmt)).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    new_access_token = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.group.name.value,
            "pwd_fgp": user.hashed_password[-16:],
        }
    )
    return AccessTokenResponseSchema(access_token=new_access_token)


async def logout_user(db: AsyncSession, data: RefreshTokenRequestSchema) -> dict:
    """Revoke a user's refresh token upon logout."""
    await db.execute(delete(RefreshToken).where(RefreshToken.token == data.refresh_token))
    await db.commit()
    return {"message": "Logged out successfully"}


async def request_password_reset(db: AsyncSession, data: PasswordResetRequestSchema) -> dict:
    """Generate a password reset token and send it to the user's email."""
    user = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()

    if user and user.is_active:
        await db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
        token_str = uuid4().hex
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token_str,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(reset_token)
        await db.commit()

        await send_email(
            to_email=user.email,
            subject="Password Reset Request - Online Cinema",
            body=f"Use this token to reset your password: {token_str}",
        )

    return {"message": "If that email is registered, a reset link has been sent."}


async def confirm_password_reset(db: AsyncSession, data: PasswordResetConfirmSchema) -> dict:
    """Reset the user's password and revoke all existing access and refresh sessions."""
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

    if _is_expired(token_record.expires_at):
        await db.delete(token_record)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token has expired",
        )

    user = token_record.user
    user.hashed_password = hash_password(data.new_password)

    # Revoke all existing refresh tokens for this user
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    await db.delete(token_record)
    await db.commit()
    return {"message": "Password has been reset successfully. All sessions revoked."}


async def change_user_password(db: AsyncSession, user: User, data: PasswordChangeSchema) -> dict:
    """Change the authenticated user's password and revoke all existing sessions."""
    if not verify_password(data.old_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password",
        )

    user.hashed_password = hash_password(data.new_password)

    # Revoke all existing refresh tokens for this user
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    await db.commit()
    return {"message": "Password changed successfully. Please log in again."}


async def get_or_create_profile(db: AsyncSession, user_id: int) -> UserProfile:
    """Retrieve the user's profile or create an empty one if it does not exist."""
    stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    profile = (await db.execute(stmt)).scalar_one_or_none()
    if not profile:
        profile = UserProfile(user_id=user_id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


async def update_user_profile(db: AsyncSession, user_id: int, data: UserProfileUpdateSchema) -> UserProfile:
    """Update the authenticated user's profile fields."""
    profile = await get_or_create_profile(db, user_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return profile


async def upload_user_avatar(db: AsyncSession, user_id: int, file: UploadFile) -> UserProfile:
    """Validate and upload an avatar image to S3 and save the URL in the user profile."""
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, and WEBP images are allowed",
        )

    content = await file.read()
    avatar_url = await s3_client.upload_avatar(user_id, file.filename, content, file.content_type)

    profile = await get_or_create_profile(db, user_id)
    profile.avatar = avatar_url
    await db.commit()
    await db.refresh(profile)
    return profile


async def change_user_role(db: AsyncSession, target_user_id: int, data: UserRoleUpdateSchema) -> User:
    """Change a user's group (role) by an administrator."""
    user = await db.get(User, target_user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    group = await _get_or_create_default_group(db, data.role)
    user.group_id = group.id
    await db.commit()
    await db.refresh(user)
    return user
