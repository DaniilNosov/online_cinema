from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models.accounts import User, UserGroupEnum
from src.database.session import get_db
from src.security.jwt import decode_token

security_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate Bearer JWT token, verify session validity, and return the active user."""
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    stmt = select(User).options(selectinload(User.group)).where(User.id == int(user_id))
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Verify that the password has not been changed since this token was issued
    if payload.get("pwd_fgp") != user.hashed_password[-16:]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired due to password change. Please log in again.",
        )

    return user


def require_roles(*allowed_roles: UserGroupEnum):
    """Dependency factory restricting endpoint access to specific user groups."""

    async def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.group.name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return role_checker
