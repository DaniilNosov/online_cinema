from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base

# Association tables for Many-to-Many relationships
movie_genres = Table(
    "movie_genres",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
)

movie_directors = Table(
    "movie_directors",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("director_id", ForeignKey("directors.id", ondelete="CASCADE"), primary_key=True),
)

movie_stars = Table(
    "movie_stars",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("star_id", ForeignKey("stars.id", ondelete="CASCADE"), primary_key=True),
)

favorite_movies = Table(
    "favorite_movies",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
)


class Genre(Base):
    """Represents movie genres (e.g., Action, Sci-Fi, Drama)."""

    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    movies: Mapped[List["Movie"]] = relationship("Movie", secondary=movie_genres, back_populates="genres")


class Star(Base):
    """Represents actors/stars featured in movies."""

    __tablename__ = "stars"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)

    movies: Mapped[List["Movie"]] = relationship("Movie", secondary=movie_stars, back_populates="stars")


class Director(Base):
    """Represents movie directors."""

    __tablename__ = "directors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)

    movies: Mapped[List["Movie"]] = relationship("Movie", secondary=movie_directors, back_populates="directors")


class Certification(Base):
    """Represents age rating certifications (e.g., PG-13, R, G)."""

    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    movies: Mapped[List["Movie"]] = relationship("Movie", back_populates="certification")


class Movie(Base):
    """Represents a movie available in the online cinema catalog."""

    __tablename__ = "movies"
    __table_args__ = (UniqueConstraint("name", "year", "time", name="uq_movie_name_year_time"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), default=uuid4, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    time: Mapped[int] = mapped_column(Integer, nullable=False)  # Duration in minutes
    imdb: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    votes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meta_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gross: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    certification_id: Mapped[int] = mapped_column(ForeignKey("certifications.id", ondelete="RESTRICT"), nullable=False)

    # Relationships
    certification: Mapped["Certification"] = relationship("Certification", back_populates="movies")
    genres: Mapped[List["Genre"]] = relationship("Genre", secondary=movie_genres, back_populates="movies")
    directors: Mapped[List["Director"]] = relationship("Director", secondary=movie_directors, back_populates="movies")
    stars: Mapped[List["Star"]] = relationship("Star", secondary=movie_stars, back_populates="movies")
    likes: Mapped[List["MovieLike"]] = relationship("MovieLike", back_populates="movie", cascade="all, delete-orphan")
    ratings: Mapped[List["MovieRating"]] = relationship(
        "MovieRating", back_populates="movie", cascade="all, delete-orphan"
    )
    comments: Mapped[List["MovieComment"]] = relationship(
        "MovieComment", back_populates="movie", cascade="all, delete-orphan"
    )


class MovieLike(Base):
    """Stores user likes and dislikes for movies."""

    __tablename__ = "movie_likes"
    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="uq_user_movie_like"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    is_like: Mapped[bool] = mapped_column(Boolean, nullable=False)  # True = Like, False = Dislike

    movie: Mapped["Movie"] = relationship("Movie", back_populates="likes")


class MovieRating(Base):
    """Stores user ratings for movies on a 1 to 10 scale."""

    __tablename__ = "movie_ratings"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_user_movie_rating"),
        CheckConstraint("rating >= 1 AND rating <= 10", name="check_rating_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)

    movie: Mapped["Movie"] = relationship("Movie", back_populates="ratings")


class MovieComment(Base):
    """Stores user comments and nested replies on movies."""

    __tablename__ = "movie_comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("movie_comments.id", ondelete="CASCADE"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    movie: Mapped["Movie"] = relationship("Movie", back_populates="comments")
    replies: Mapped[List["MovieComment"]] = relationship("MovieComment", cascade="all, delete-orphan")
