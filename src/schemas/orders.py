from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from src.database.models.orders import OrderStatusEnum


# --- Cart Schemas ---

class CartItemAddSchema(BaseModel):
    """Schema for adding a movie to the shopping cart."""
    movie_id: int


class CartMovieBriefSchema(BaseModel):
    """Brief movie details displayed inside a shopping cart item."""
    id: int
    name: str
    year: int
    price: Decimal

    model_config = ConfigDict(from_attributes=True)


class CartItemResponseSchema(BaseModel):
    """Schema representing a single item in the user's cart."""
    id: int
    movie_id: int
    added_at: datetime
    movie: CartMovieBriefSchema

    model_config = ConfigDict(from_attributes=True)


class CartResponseSchema(BaseModel):
    """Schema representing the complete shopping cart with total price."""
    id: int
    user_id: int
    total_items: int
    total_price: Decimal
    items: List[CartItemResponseSchema]


class OrderItemResponseSchema(BaseModel):
    """Schema representing a single movie item within an order."""
    id: int
    movie_id: int
    price: Decimal
    movie: CartMovieBriefSchema

    model_config = ConfigDict(from_attributes=True)


class OrderResponseSchema(BaseModel):
    """Schema for displaying an order and its items."""
    id: int
    user_id: int
    status: OrderStatusEnum
    total_price: Decimal
    stripe_session_id: Optional[str] = None
    payment_url: Optional[str] = None
    created_at: datetime
    items: List[OrderItemResponseSchema]

    model_config = ConfigDict(from_attributes=True)
