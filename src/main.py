from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.session import get_db

app = FastAPI(
    title="Online Cinema API",
    description="Digital platform for watching and purchasing movies",
    version="1.0.0",
)


@app.get("/health", tags=["System"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Check API and database connectivity."""
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}