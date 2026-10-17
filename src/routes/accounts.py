from fastapi import APIRouter, Body, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.accounts import User, UserGroupEnum
from src.database.session import get_db
from src.schemas.accounts import (
    PasswordChangeSchema,
    PasswordResetConfirmSchema,
    PasswordResetRequestSchema,
    TokenResponseSchema,
    UserLoginSchema,
    UserProfileResponseSchema,
    UserProfileUpdateSchema,
    UserRegisterSchema,
    UserRoleUpdateSchema,
)
from src.security.dependencies import get_current_user, require_roles
from src.services import accounts as accounts_service

router = APIRouter(prefix="/api/v1/accounts", tags=["Accounts"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    data: UserRegisterSchema,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account."""
    return await accounts_service.register_user(db, data)


@router.post("/activate")
async def activate(
    token: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    """Activate a user account with an activation token."""
    return await accounts_service.activate_account(db, token)


@router.post("/resend-activation")
async def resend_activation(
    email: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    """Resend activation token if the previous one expired."""
    return await accounts_service.resend_activation_token(db, email)


@router.post("/login", response_model=TokenResponseSchema)
async def login(
    data: UserLoginSchema,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and return access and refresh JWT tokens."""
    return await accounts_service.authenticate_user(db, data)


@router.post("/refresh", response_model=TokenResponseSchema)
async def refresh_token(
    refresh_token: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    """Get a new access token using a refresh token."""
    return await accounts_service.refresh_user_token(db, refresh_token)


@router.post("/logout")
async def logout(
    refresh_token: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    """Logout user and revoke their refresh token."""
    return await accounts_service.logout_user(db, refresh_token)


@router.post("/change-password")
async def change_password(
    data: PasswordChangeSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change password for the currently logged-in user."""
    return await accounts_service.change_user_password(db, current_user, data)


@router.post("/password-reset/request")
async def password_reset_request(
    data: PasswordResetRequestSchema,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset token via email."""
    return await accounts_service.request_password_reset(db, data)


@router.post("/password-reset/confirm")
async def password_reset_confirm(
    data: PasswordResetConfirmSchema,
    db: AsyncSession = Depends(get_db),
):
    """Confirm password reset using the token from email."""
    return await accounts_service.confirm_password_reset(db, data)


@router.get("/profile", response_model=UserProfileResponseSchema)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get profile details for the currently authenticated user."""
    profile = await accounts_service.get_or_create_profile(db, current_user)
    return UserProfileResponseSchema.model_validate(profile)


@router.put("/profile", response_model=UserProfileResponseSchema)
async def update_my_profile(
    data: UserProfileUpdateSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update profile details for the currently authenticated user."""
    return await accounts_service.update_profile(db, current_user, data)


@router.post("/profile/avatar", response_model=UserProfileResponseSchema)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a profile avatar image to S3/MinIO."""
    return await accounts_service.upload_user_avatar(db, current_user, file)


@router.patch(
    "/{user_id}/role",
    dependencies=[Depends(require_roles(UserGroupEnum.ADMIN))],
)
async def update_user_role(
    user_id: int,
    data: UserRoleUpdateSchema,
    db: AsyncSession = Depends(get_db),
):
    """Change user role (USER, MODERATOR, ADMIN). Admin access required."""
    return await accounts_service.change_user_role(db, user_id, data.role)
