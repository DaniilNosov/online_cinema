from decimal import Decimal
from typing import List, Optional, Set
from uuid import uuid4

import stripe
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config.settings import settings
from src.database.models.accounts import User
from src.database.models.movies import Movie
from src.database.models.orders import (
    Cart,
    CartItem,
    Order,
    OrderItem,
    OrderStatusEnum,
)
from src.notifications.emails import send_email
from src.schemas.orders import (
    CartItemResponseSchema,
    CartResponseSchema,
    OrderResponseSchema,
)

stripe.api_key = settings.STRIPE_SECRET_KEY

_processed_stripe_events: Set[str] = set()


async def _get_or_create_cart(db: AsyncSession, user_id: int) -> Cart:
    """Retrieve the user's cart with all items and movies, or create one if missing."""
    stmt = (
        select(Cart)
        .options(selectinload(Cart.items).selectinload(CartItem.movie))
        .where(Cart.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    cart = (await db.execute(stmt)).scalar_one_or_none()

    if not cart:
        cart = Cart(user_id=user_id)
        db.add(cart)
        await db.commit()
        cart = (await db.execute(stmt)).scalar_one()

    return cart


async def _is_movie_already_purchased(db: AsyncSession, user_id: int, movie_id: int) -> bool:
    """Check whether the user has already purchased the movie in a PAID order."""
    stmt = (
        select(OrderItem.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            Order.user_id == user_id,
            Order.status == OrderStatusEnum.PAID,
            OrderItem.movie_id == movie_id,
        )
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def get_user_cart(db: AsyncSession, user_id: int) -> CartResponseSchema:
    """Return the user's cart contents along with item count and total price."""
    cart = await _get_or_create_cart(db, user_id)
    items = [CartItemResponseSchema.model_validate(item) for item in cart.items]
    total_price = sum((item.movie.price for item in cart.items), Decimal("0.00"))

    return CartResponseSchema(
        id=cart.id,
        user_id=cart.user_id,
        total_items=len(items),
        total_price=total_price,
        items=items,
    )


async def add_movie_to_cart(db: AsyncSession, user: User, movie_id: int) -> CartResponseSchema:
    """Add a movie to the user's shopping cart after validating eligibility."""
    movie = await db.get(Movie, movie_id)
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    if await _is_movie_already_purchased(db, user.id, movie_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already purchased this movie",
        )

    cart = await _get_or_create_cart(db, user.id)

    if any(item.movie_id == movie_id for item in cart.items):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Movie is already in your shopping cart",
        )

    new_item = CartItem(cart_id=cart.id, movie_id=movie_id)
    db.add(new_item)
    await db.commit()

    return await get_user_cart(db, user.id)


async def remove_movie_from_cart(db: AsyncSession, user: User, movie_id: int) -> CartResponseSchema:
    """Remove a specific movie from the user's shopping cart."""
    cart = await _get_or_create_cart(db, user.id)
    stmt = delete(CartItem).where(CartItem.cart_id == cart.id, CartItem.movie_id == movie_id)
    result = await db.execute(stmt)
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found in your shopping cart",
        )

    return await get_user_cart(db, user.id)


async def clear_cart(db: AsyncSession, user: User) -> dict:
    """Remove all items from the user's shopping cart."""
    cart = await _get_or_create_cart(db, user.id)
    await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    await db.commit()
    return {"message": "Shopping cart cleared successfully."}


async def checkout_order(db: AsyncSession, user: User) -> OrderResponseSchema:
    """Create a pending order from the user's cart and initiate a Stripe session."""
    cart = await _get_or_create_cart(db, user.id)
    if not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your shopping cart is empty",
        )

    for item in cart.items:
        if await _is_movie_already_purchased(db, user.id, item.movie_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Movie '{item.movie.name}' has already been purchased",
            )

    total_price = sum((item.movie.price for item in cart.items), Decimal("0.00"))

    order = Order(
        user_id=user.id,
        status=OrderStatusEnum.PENDING,
        total_price=total_price,
    )
    db.add(order)
    await db.flush()

    line_items = []
    for item in cart.items:
        order_item = OrderItem(
            order_id=order.id,
            movie_id=item.movie_id,
            price=item.movie.price,
        )
        db.add(order_item)
        line_items.append(
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": item.movie.name},
                    "unit_amount": int(item.movie.price * 100),
                },
                "quantity": 1,
            }
        )

    payment_url: Optional[str] = None
    if settings.STRIPE_SECRET_KEY and not settings.STRIPE_SECRET_KEY.startswith("sk_test_placeholder"):
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=line_items,
                mode="payment",
                success_url=f"http://localhost:8000/api/v1/orders/{order.id}?payment=success",
                cancel_url=f"http://localhost:8000/api/v1/orders/{order.id}?payment=cancel",
                metadata={"order_id": str(order.id), "user_id": str(user.id)},
            )
            order.stripe_session_id = session.id
            payment_url = session.url
        except stripe.StripeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Stripe error: {str(exc)}",
            )
    else:
        order.stripe_session_id = f"cs_test_{uuid4().hex}"
        payment_url = f"https://checkout.stripe.com/pay/{order.stripe_session_id}"

    await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    await db.commit()

    created_order = await get_order_by_id(db, user, order.id)
    created_order.payment_url = payment_url
    return created_order


async def list_user_orders(
    db: AsyncSession,
    user: User,
    status_filter: Optional[OrderStatusEnum] = None,
) -> List[OrderResponseSchema]:
    """List all orders belonging to the authenticated user."""
    stmt = (
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.movie))
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .execution_options(populate_existing=True)
    )
    if status_filter is not None:
        stmt = stmt.where(Order.status == status_filter)

    orders = (await db.execute(stmt)).scalars().all()
    return [OrderResponseSchema.model_validate(o) for o in orders]


async def get_order_by_id(db: AsyncSession, user: User, order_id: int) -> OrderResponseSchema:
    """Retrieve a specific order belonging to the user."""
    stmt = (
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.movie))
        .where(Order.id == order_id, Order.user_id == user.id)
        .execution_options(populate_existing=True)
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    return OrderResponseSchema.model_validate(order)


async def cancel_order(db: AsyncSession, user: User, order_id: int) -> OrderResponseSchema:
    """Cancel a pending order before payment is completed."""
    stmt = (
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.movie))
        .where(Order.id == order_id, Order.user_id == user.id)
        .execution_options(populate_existing=True)
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    if order.status != OrderStatusEnum.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel an order with status {order.status.value}",
        )

    order.status = OrderStatusEnum.CANCELLED
    await db.commit()
    return OrderResponseSchema.model_validate(order)


async def handle_stripe_webhook(db: AsyncSession, payload: bytes, sig_header: Optional[str]) -> dict:
    """Verify and process incoming Stripe webhook events idempotently."""
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe webhook payload or signature",
        )

    event_id = event.get("id")
    if event_id and event_id in _processed_stripe_events:
        return {"status": "already_processed"}

    if event.get("type") == "checkout.session.completed":
        session_data = event.get("data", {}).get("object", {})
        metadata = session_data.get("metadata") or {}
        order_id_raw = metadata.get("order_id")

        if not order_id_raw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing order_id in Stripe session metadata",
            )

        stmt = (
            select(Order)
            .options(
                selectinload(Order.items).selectinload(OrderItem.movie),
                selectinload(Order.user),
            )
            .where(Order.id == int(order_id_raw))
            .execution_options(populate_existing=True)
        )
        order = (await db.execute(stmt)).scalar_one_or_none()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        session_id = session_data.get("id")
        if not session_id or order.stripe_session_id != session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stripe session ID does not match the order",
            )

        meta_user_id = metadata.get("user_id")
        if meta_user_id is not None and str(order.user_id) != str(meta_user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stripe session user_id does not match the order owner",
            )

        if order.status == OrderStatusEnum.PAID:
            if event_id:
                _processed_stripe_events.add(event_id)
            return {"status": "already_processed"}

        if order.status == OrderStatusEnum.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot fulfill a cancelled order",
            )

        # Validate session status, payment_status, currency, and exact payment amount
        if session_data.get("status") != "complete":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stripe checkout session is not complete",
            )

        if session_data.get("payment_status") != "paid":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment has not been completed",
            )

        if (session_data.get("currency") or "").lower() != "usd":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment currency",
            )

        expected_amount = int(order.total_price * 100)
        if session_data.get("amount_total") != expected_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment amount does not match order total",
            )

        order.status = OrderStatusEnum.PAID
        await db.commit()

        if event_id:
            _processed_stripe_events.add(event_id)

        movie_titles = ", ".join(item.movie.name for item in order.items)
        await send_email(
            to_email=order.user.email,
            subject=f"Order #{order.id} Payment Confirmed - Online Cinema",
            body=(
                f"Thank you for your purchase!\n\n"
                f"Order ID: #{order.id}\n"
                f"Movies: {movie_titles}\n"
                f"Total Paid: ${order.total_price}\n\n"
                f"Enjoy watching!"
            ),
        )

    return {"status": "success"}
