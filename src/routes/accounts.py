from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.accounts import User, UserGroupEnum
from src.database.session import get_db
from src.schemas.accounts import (
    AccessTokenResponseSchema,
    ActivationRequestSchema,
    LoginRequestSchema,
    PasswordChangeSchema,
    PasswordResetConfirmSchema,
    PasswordResetRequestSchema,
    RefreshTokenRequestSchema,
    TokenResponseSchema,
    UserProfileResponseSchema,
    UserProfileUpdateSchema,
    UserRegisterSchema,
    UserResponseSchema,
    UserRoleUpdateSchema,
)
from src.security.dependencies import get_current_user, require_roles
from src.services import accounts as accounts_service

router = APIRouter(prefix="/api/v1/accounts", tags=["Accounts & Auth"])


@router.post(
    "/register",
    response_model=UserResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    data: UserRegisterSchema,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account and send an activation email."""
    return await accounts_service.register_user(db, data)


@router.post("/activate")
async def activate(
    data: ActivationRequestSchema,
    db: AsyncSession = Depends(get_db),
):
    """Activate a user account with an activation token."""
    return await accounts_service.activate_account(db, data)


@router.post("/login", response_model=TokenResponseSchema)
async def login(
    data: LoginRequestSchema,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and return access and refresh JWT tokens."""
    return await accounts_service.login_user(db, data)


@router.post("/refresh", response_model=AccessTokenResponseSchema)
async def refresh_token(
    data: RefreshTokenRequestSchema,
    db: AsyncSession = Depends(get_db),
):
    """Obtain a new access token using a valid refresh token."""
    return await accounts_service.refresh_user_token(db, data)


@router.post("/logout")
async def logout(
    data: RefreshTokenRequestSchema,
    db: AsyncSession = Depends(get_db),
):
    """Revoke the provided refresh token."""
    return await accounts_service.logout_user(db, data)


@router.post("/password-reset/request")
async def request_password_reset(
    data: PasswordResetRequestSchema,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset token via email."""
    return await accounts_service.request_password_reset(db, data)


@router.post("/password-reset/complete")
async def complete_password_reset(
    data: PasswordResetConfirmSchema,
    db: AsyncSession = Depends(get_db),
):
    """Complete password reset using token and revoke all existing sessions."""
    return await accounts_service.confirm_password_reset(db, data)


@router.post("/change-password")
async def change_password(
    data: PasswordChangeSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change current user's password and revoke all existing sessions."""
    return await accounts_service.change_user_password(db, current_user, data)


@router.get("/profile", response_model=UserProfileResponseSchema)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current authenticated user's profile."""
    return await accounts_service.get_or_create_profile(db, current_user.id)


@router.put("/profile", response_model=UserProfileResponseSchema)
async def update_my_profile(
    data: UserProfileUpdateSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the current authenticated user's profile."""
    return await accounts_service.update_user_profile(db, current_user.id, data)


@router.post("/profile/avatar", response_model=UserProfileResponseSchema)
async def upload_my_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a profile avatar image to S3 storage."""
    return await accounts_service.upload_user_avatar(db, current_user.id, file)


@router.patch(
    "/users/{user_id}/role",
    response_model=UserResponseSchema,
    dependencies=[Depends(require_roles(UserGroupEnum.ADMIN))],
)
async def update_user_role(
    user_id: int,
    data: UserRoleUpdateSchema,
    db: AsyncSession = Depends(get_db),
):
    """Change a user's role (Admin only)."""
    return await accounts_service.change_user_role(db, user_id, data)
