from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.session import get_db
from src.routes.accounts import router as accounts_router
from src.routes.movies import router as movies_router
from src.routes.orders import cart_router, orders_router

app = FastAPI(
    title="Online Cinema API",
    description="Digital platform for watching and purchasing movies",
    version="1.0.0",
)

app.include_router(accounts_router)
app.include_router(movies_router)
app.include_router(cart_router)
app.include_router(orders_router)


@app.get("/health", tags=["System"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Check API and database connectivity."""
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
