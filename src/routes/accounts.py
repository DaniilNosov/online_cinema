from fastapi import APIRouter, Depends, Body, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.session import get_db
from src.database.models.accounts import User
from src.schemas.accounts import (
    UserRegisterSchema,
    UserLoginSchema,
    TokenResponseSchema,
    PasswordChangeSchema,
    PasswordResetRequestSchema,
    PasswordResetConfirmSchema,
)
from src.security.dependencies import get_current_user
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
