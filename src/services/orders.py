import uuid
from decimal import Decimal
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models.accounts import User
from src.database.models.movies import Movie
from src.database.models.orders import (
    Cart,
    CartItem,
    Order,
    OrderItem,
    OrderStatusEnum,
)
from src.schemas.orders import (
    CartItemResponseSchema,
    CartResponseSchema,
    OrderResponseSchema,
)
from src.notifications.emails import send_email



async def _get_or_create_cart_model(db: AsyncSession, user_id: int) -> Cart:
    """Retrieve the user's cart with items and movies, or create an empty cart."""
    stmt = (
        select(Cart)
        .options(selectinload(Cart.items).selectinload(CartItem.movie))
        .where(Cart.user_id == user_id)
    )
    cart = (await db.execute(stmt)).scalar_one_or_none()

    if not cart:
        cart = Cart(user_id=user_id)
        db.add(cart)
        await db.commit()
        cart = (await db.execute(stmt)).scalar_one()

    return cart


def _build_cart_response(cart: Cart) -> CartResponseSchema:
    """Calculate cart totals and serialize the Cart model into CartResponseSchema."""
    items = [CartItemResponseSchema.model_validate(item) for item in cart.items]
    total_price = sum((item.movie.price for item in items), Decimal("0.00"))
    return CartResponseSchema(
        id=cart.id,
        user_id=cart.user_id,
        total_items=len(items),
        total_price=total_price,
        items=items,
    )


async def get_user_cart(db: AsyncSession, user_id: int) -> CartResponseSchema:
    """Return the current contents and total price of a user's cart."""
    cart = await _get_or_create_cart_model(db, user_id)
    return _build_cart_response(cart)


async def add_movie_to_cart(
    db: AsyncSession, user: User, movie_id: int
) -> CartResponseSchema:
    """Add a movie to the user's cart after checking purchase and duplicate constraints."""
    movie = await db.get(Movie, movie_id)
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    purchased_stmt = (
        select(OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .where(
            Order.user_id == user.id,
            Order.status == OrderStatusEnum.PAID,
            OrderItem.movie_id == movie_id,
        )
    )
    if (await db.execute(purchased_stmt)).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already purchased this movie",
        )

    cart = await _get_or_create_cart_model(db, user.id)

    # Check if the movie is already in the cart
    if any(item.movie_id == movie_id for item in cart.items):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Movie is already in your shopping cart",
        )

    new_item = CartItem(cart_id=cart.id, movie_id=movie_id)
    db.add(new_item)
    await db.commit()

    updated_cart = await _get_or_create_cart_model(db, user.id)
    return _build_cart_response(updated_cart)


async def remove_movie_from_cart(
    db: AsyncSession, user: User, movie_id: int
) -> CartResponseSchema:
    """Remove a specific movie from the user's shopping cart."""
    cart = await _get_or_create_cart_model(db, user.id)

    stmt = delete(CartItem).where(
        CartItem.cart_id == cart.id,
        CartItem.movie_id == movie_id,
    )
    result = await db.execute(stmt)
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found in your shopping cart",
        )

    updated_cart = await _get_or_create_cart_model(db, user.id)
    return _build_cart_response(updated_cart)


async def clear_user_cart(db: AsyncSession, user: User) -> dict:
    """Remove all items from the user's shopping cart."""
    cart = await _get_or_create_cart_model(db, user.id)
    await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    await db.commit()
    return {"message": "Shopping cart cleared successfully."}



async def _get_order_with_items(db: AsyncSession, order_id: int) -> Optional[Order]:
    """Fetch an order with its items and associated movie models."""
    stmt = (
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.movie))
        .where(Order.id == order_id)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_order_from_cart(
    db: AsyncSession, user: User
) -> OrderResponseSchema:
    """Convert the user's shopping cart into a PENDING order and clear the cart."""
    cart = await _get_or_create_cart_model(db, user.id)
    if not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your shopping cart is empty",
        )

    movie_ids = [item.movie_id for item in cart.items]

    existing_order_stmt = (
        select(OrderItem.movie_id, Order.status)
        .join(Order, OrderItem.order_id == Order.id)
        .where(
            Order.user_id == user.id,
            Order.status.in_([OrderStatusEnum.PENDING, OrderStatusEnum.PAID]),
            OrderItem.movie_id.in_(movie_ids),
        )
    )
    existing_rows = (await db.execute(existing_order_stmt)).all()
    if existing_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more movies in your cart are already purchased or in a pending order",
        )

    total_price = sum((item.movie.price for item in cart.items), Decimal("0.00"))
    session_id = f"cs_test_{uuid.uuid4().hex}"

    order = Order(
        user_id=user.id,
        status=OrderStatusEnum.PENDING,
        total_price=total_price,
        stripe_session_id=session_id,
    )
    db.add(order)
    await db.flush()

    for cart_item in cart.items:
        db.add(
            OrderItem(
                order_id=order.id,
                movie_id=cart_item.movie_id,
                price=cart_item.movie.price,
            )
        )

    await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    await db.commit()

    created_order = await _get_order_with_items(db, order.id)
    response = OrderResponseSchema.model_validate(created_order)
    response.checkout_url = f"/api/v1/orders/{order.id}/pay"
    return response


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
    )
    if status_filter is not None:
        stmt = stmt.where(Order.status == status_filter)

    orders = (await db.execute(stmt)).scalars().all()
    return [OrderResponseSchema.model_validate(o) for o in orders]


async def cancel_user_order(
    db: AsyncSession, user: User, order_id: int
) -> OrderResponseSchema:
    """Cancel a PENDING order belonging to the authenticated user."""
    order = await _get_order_with_items(db, order_id)
    if not order or order.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
