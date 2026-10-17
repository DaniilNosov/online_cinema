from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BaseNameSchema(BaseModel):
    """Base schema for simple named entities (Genre, Star, Director, Certification)."""

    name: str = Field(..., min_length=1, max_length=150)


class EntityResponseSchema(BaseNameSchema):
    """Response schema with ID and name."""

    id: int
    model_config = ConfigDict(from_attributes=True)


class GenreWithCountSchema(EntityResponseSchema):
    """Genre response schema including the total number of movies in that genre."""

    movie_count: int = 0


class MovieCreateSchema(BaseModel):
    """Schema for creating a new movie (Moderator/Admin only)."""

    name: str = Field(..., max_length=255)
    year: int = Field(..., ge=1888, le=2100)
    time: int = Field(..., gt=0, description="Duration in minutes")
    imdb: float = Field(..., ge=0.0, le=10.0)
    votes: int = Field(default=0, ge=0)
    meta_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    gross: Optional[float] = Field(None, ge=0.0)
    description: str = Field(..., min_length=1)
    price: Decimal = Field(..., ge=0.0, decimal_places=2)
    certification_id: int
    genre_ids: List[int] = Field(default_factory=list)
    director_ids: List[int] = Field(default_factory=list)
    star_ids: List[int] = Field(default_factory=list)


class MovieUpdateSchema(BaseModel):
    """Schema for partial updates to an existing movie."""

    name: Optional[str] = Field(None, max_length=255)
    year: Optional[int] = Field(None, ge=1888, le=2100)
    time: Optional[int] = Field(None, gt=0)
    imdb: Optional[float] = Field(None, ge=0.0, le=10.0)
    votes: Optional[int] = Field(None, ge=0)
    meta_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    gross: Optional[float] = Field(None, ge=0.0)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0.0)
    certification_id: Optional[int] = None
    genre_ids: Optional[List[int]] = None
    director_ids: Optional[List[int]] = None
    star_ids: Optional[List[int]] = None


class MovieListItemSchema(BaseModel):
    """Compact movie schema for catalog listings."""

    id: int
    uuid: UUID
    name: str
    year: int
    time: int
    imdb: float
    price: Decimal
    certification: EntityResponseSchema
    genres: List[EntityResponseSchema]

    model_config = ConfigDict(from_attributes=True)


class MovieDetailSchema(MovieListItemSchema):
    """Detailed movie schema including full description, cast, and ratings."""

    votes: int
    meta_score: Optional[float]
    gross: Optional[float]
    description: str
    directors: List[EntityResponseSchema]
    stars: List[EntityResponseSchema]
    likes_count: int = 0
    dislikes_count: int = 0
    average_rating: Optional[float] = None


class PaginatedMoviesResponseSchema(BaseModel):
    """Paginated response wrapper for movie listings."""

    total: int
    page: int
    per_page: int
    items: List[MovieListItemSchema]


class MovieLikeSchema(BaseModel):
    """Schema for liking or disliking a movie."""

    is_like: bool


class MovieRatingSchema(BaseModel):
    """Schema for rating a movie on a 1-10 scale."""

    rating: int = Field(..., ge=1, le=10)


class MovieCommentCreateSchema(BaseModel):
    """Schema for posting a comment or reply on a movie."""

    content: str = Field(..., min_length=1, max_length=2000)
    parent_id: Optional[int] = None


class MovieCommentResponseSchema(BaseModel):
    """Schema for displaying a movie comment."""

    id: int
    user_id: int
    movie_id: int
    parent_id: Optional[int]
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
