from typing import List, Optional

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.accounts import User, UserGroupEnum
from src.database.models.orders import OrderStatusEnum
from src.database.session import get_db
from src.schemas.orders import (
    CartItemAddSchema,
    CartResponseSchema,
    OrderResponseSchema,
)
from src.security.dependencies import get_current_user, require_roles
from src.services import orders as orders_service

cart_router = APIRouter(prefix="/api/v1/cart", tags=["Shopping Cart"])
orders_router = APIRouter(prefix="/api/v1/orders", tags=["Orders & Payments"])


# --- Shopping Cart Endpoints ---


@cart_router.get("", response_model=CartResponseSchema)
async def get_my_cart(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's shopping cart."""
    return await orders_service.get_user_cart(db, current_user.id)


@cart_router.post(
    "/items",
    response_model=CartResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def add_item_to_cart(
    data: CartItemAddSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a movie to the current user's shopping cart."""
    return await orders_service.add_movie_to_cart(db, current_user, data.movie_id)


@cart_router.delete("/items/{movie_id}", response_model=CartResponseSchema)
async def remove_item_from_cart(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a movie from the current user's shopping cart."""
    return await orders_service.remove_movie_from_cart(db, current_user, movie_id)


@cart_router.delete("")
async def clear_my_cart(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Clear all movies from the current user's shopping cart."""
    return await orders_service.clear_cart(db, current_user)


@cart_router.get(
    "/users/{user_id}",
    response_model=CartResponseSchema,
    dependencies=[Depends(require_roles(UserGroupEnum.ADMIN))],
)
async def get_user_cart_by_admin(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Inspect a specific user's shopping cart (Admin only)."""
    return await orders_service.get_user_cart(db, user_id)


# --- Orders & Payments Endpoints ---


@orders_router.post(
    "/checkout",
    response_model=OrderResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_order_checkout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new order from the shopping cart and return the Stripe payment URL."""
    return await orders_service.checkout_order(db, current_user)


@orders_router.get("", response_model=List[OrderResponseSchema])
async def get_my_orders(
    status_filter: Optional[OrderStatusEnum] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a list of the current user's orders with optional status filtering."""
    return await orders_service.list_user_orders(db, current_user, status_filter)


@orders_router.get("/{order_id}", response_model=OrderResponseSchema)
async def get_order_details(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get details of a specific order."""
    return await orders_service.get_order_by_id(db, current_user, order_id)


@orders_router.post("/{order_id}/cancel", response_model=OrderResponseSchema)
async def cancel_pending_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pending order."""
    return await orders_service.cancel_order(db, current_user, order_id)


@orders_router.post("/{order_id}/confirm-payment", response_model=OrderResponseSchema)
async def confirm_order_payment(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm order payment (for testing/simulation) and send email receipt."""
    await orders_service.get_order_by_id(db, current_user, order_id)
    return await orders_service.mark_order_as_paid(db, order_id)


@orders_router.post("/webhook/stripe", include_in_schema=True)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
):
    """Webhook endpoint for receiving Stripe checkout events."""
    payload = await request.body()
    return await orders_service.handle_stripe_webhook(db, payload, stripe_signature)
