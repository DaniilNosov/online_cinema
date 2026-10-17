import asyncio
from datetime import datetime, timezone

from sqlalchemy import delete

from src.database.models.accounts import (
    ActivationToken,
    PasswordResetToken,
    RefreshToken,
)
from src.database.session import AsyncSessionLocal, engine
from src.tasks.celery_app import celery_app


async def _cleanup_expired_tokens_async() -> dict:
    """Delete expired activation, password reset, and refresh tokens from DB."""
    now = datetime.now(timezone.utc)
    try:
        async with AsyncSessionLocal() as session:
            act_res = await session.execute(delete(ActivationToken).where(ActivationToken.expires_at < now))
            pwd_res = await session.execute(delete(PasswordResetToken).where(PasswordResetToken.expires_at < now))
            ref_res = await session.execute(delete(RefreshToken).where(RefreshToken.expires_at < now))
            await session.commit()

            return {
                "deleted_activation_tokens": act_res.rowcount,
                "deleted_password_reset_tokens": pwd_res.rowcount,
                "deleted_refresh_tokens": ref_res.rowcount,
            }
    finally:
        # Dispose engine pool to avoid event loop conflicts across Celery runs
        await engine.dispose()


@celery_app.task(name="src.tasks.accounts.delete_expired_tokens")
def delete_expired_tokens() -> dict:
    """Celery task wrapper to execute async token cleanup."""
    return asyncio.run(_cleanup_expired_tokens_async())
