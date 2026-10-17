from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import delete, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models.accounts import User, UserGroupEnum
from src.database.models.movies import (
    Certification,
    Director,
    Genre,
    Movie,
    MovieComment,
    MovieLike,
    MovieRating,
    Star,
    favorite_movies,
    movie_genres,
)
from src.schemas.movies import (
    BaseNameSchema,
    GenreWithCountSchema,
    MovieCommentCreateSchema,
    MovieCommentResponseSchema,
    MovieCreateSchema,
    MovieDetailSchema,
    MovieLikeSchema,
    MovieListItemSchema,
    MovieRatingSchema,
    MovieUpdateSchema,
    PaginatedMoviesResponseSchema,
)


async def get_genres_with_counts(db: AsyncSession) -> List[GenreWithCountSchema]:
    """Return all genres along with the count of movies in each genre."""
    stmt = (
        select(Genre.id, Genre.name, func.count(movie_genres.c.movie_id).label("movie_count"))
        .outerjoin(movie_genres, Genre.id == movie_genres.c.genre_id)
        .group_by(Genre.id)
        .order_by(Genre.name)
    )
    rows = (await db.execute(stmt)).all()
    return [GenreWithCountSchema(id=row.id, name=row.name, movie_count=row.movie_count) for row in rows]


async def create_named_entity(db: AsyncSession, model, data: BaseNameSchema):
    """Generic helper to create a unique named entity (Genre, Star, Director, Certification)."""
    stmt = select(model).where(func.lower(model.name) == data.name.lower())
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{model.__name__} with name '{data.name}' already exists",
        )
    instance = model(name=data.name)
    db.add(instance)
    await db.commit()
    await db.refresh(instance)
    return instance


async def list_named_entities(db: AsyncSession, model):
    """Return all records for a given named entity ordered alphabetically."""
    stmt = select(model).order_by(model.name)
    return list((await db.execute(stmt)).scalars().all())


async def update_named_entity(db: AsyncSession, model, entity_id: int, data: BaseNameSchema):
    """Update the name of an existing entity."""
    instance = await db.get(model, entity_id)
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{model.__name__} not found",
        )
    instance.name = data.name
    await db.commit()
    await db.refresh(instance)
    return instance


async def delete_named_entity(db: AsyncSession, model, entity_id: int) -> dict:
    """Delete an entity by ID."""
    instance = await db.get(model, entity_id)
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{model.__name__} not found",
        )
    await db.delete(instance)
    await db.commit()
    return {"message": f"{model.__name__} deleted successfully."}


async def list_movies(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 10,
    year: Optional[int] = None,
    min_imdb: Optional[float] = None,
    max_imdb: Optional[float] = None,
    genre_id: Optional[int] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    favorites_only_user_id: Optional[int] = None,
) -> PaginatedMoviesResponseSchema:
    """Retrieve paginated, filtered, searched, and sorted movies."""
    stmt = select(Movie).options(selectinload(Movie.certification), selectinload(Movie.genres)).distinct()

    if favorites_only_user_id is not None:
        stmt = stmt.join(favorite_movies, Movie.id == favorite_movies.c.movie_id).where(
            favorite_movies.c.user_id == favorites_only_user_id
        )

    if year is not None:
        stmt = stmt.where(Movie.year == year)
    if min_imdb is not None:
        stmt = stmt.where(Movie.imdb >= min_imdb)
    if max_imdb is not None:
        stmt = stmt.where(Movie.imdb <= max_imdb)
    if genre_id is not None:
        stmt = stmt.join(Movie.genres).where(Genre.id == genre_id)

    if search:
        pattern = f"%{search}%"
        stmt = (
            stmt.outerjoin(Movie.directors)
            .outerjoin(Movie.stars)
            .where(
                or_(
                    Movie.name.ilike(pattern),
                    Movie.description.ilike(pattern),
                    Director.name.ilike(pattern),
                    Star.name.ilike(pattern),
                )
            )
        )

    sort_mapping = {
        "price_asc": Movie.price.asc(),
        "price_desc": Movie.price.desc(),
        "year_asc": Movie.year.asc(),
        "year_desc": Movie.year.desc(),
        "imdb_asc": Movie.imdb.asc(),
        "imdb_desc": Movie.imdb.desc(),
    }
    if sort_by in sort_mapping:
        stmt = stmt.order_by(sort_mapping[sort_by], Movie.id.asc())
    else:
        stmt = stmt.order_by(Movie.id.desc())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * per_page
    stmt = stmt.offset(offset).limit(per_page)
    movies = (await db.execute(stmt)).scalars().all()

    return PaginatedMoviesResponseSchema(
        total=total,
        page=page,
        per_page=per_page,
        items=[MovieListItemSchema.model_validate(m) for m in movies],
    )


async def get_movie_detail(db: AsyncSession, movie_id: int) -> MovieDetailSchema:
    """Retrieve full details for a single movie, including likes and average rating."""
    stmt = (
        select(Movie)
        .options(
            selectinload(Movie.certification),
            selectinload(Movie.genres),
            selectinload(Movie.directors),
            selectinload(Movie.stars),
        )
        .where(Movie.id == movie_id)
    )
    movie = (await db.execute(stmt)).scalar_one_or_none()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    likes_count = (
        await db.execute(
            select(func.count(MovieLike.id)).where(MovieLike.movie_id == movie_id, MovieLike.is_like.is_(True))
        )
    ).scalar_one()

    dislikes_count = (
        await db.execute(
            select(func.count(MovieLike.id)).where(MovieLike.movie_id == movie_id, MovieLike.is_like.is_(False))
        )
    ).scalar_one()

    avg_rating = (
        await db.execute(select(func.avg(MovieRating.rating)).where(MovieRating.movie_id == movie_id))
    ).scalar_one()

    detail = MovieDetailSchema.model_validate(movie)
    detail.likes_count = likes_count
    detail.dislikes_count = dislikes_count
    detail.average_rating = round(float(avg_rating), 2) if avg_rating is not None else None
    return detail


async def create_movie(db: AsyncSession, data: MovieCreateSchema) -> MovieDetailSchema:
    """Create a new movie and link its genres, directors, and stars."""
    dup_stmt = select(Movie).where(Movie.name == data.name, Movie.year == data.year, Movie.time == data.time)
    if (await db.execute(dup_stmt)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A movie with the same name, year, and duration already exists",
        )

    cert = await db.get(Certification, data.certification_id)
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certification not found",
        )

    genres = (
        list((await db.execute(select(Genre).where(Genre.id.in_(data.genre_ids)))).scalars().all())
        if data.genre_ids
        else []
    )
    directors = (
        list((await db.execute(select(Director).where(Director.id.in_(data.director_ids)))).scalars().all())
        if data.director_ids
        else []
    )
    stars = (
        list((await db.execute(select(Star).where(Star.id.in_(data.star_ids)))).scalars().all())
        if data.star_ids
        else []
    )

    movie = Movie(
        name=data.name,
        year=data.year,
        time=data.time,
        imdb=data.imdb,
        votes=data.votes,
        meta_score=data.meta_score,
        gross=data.gross,
        description=data.description,
        price=data.price,
        certification_id=data.certification_id,
        genres=genres,
        directors=directors,
        stars=stars,
    )
    db.add(movie)
    await db.commit()
    return await get_movie_detail(db, movie.id)


async def update_movie(db: AsyncSession, movie_id: int, data: MovieUpdateSchema) -> MovieDetailSchema:
    """Update an existing movie's attributes and relationships."""
    stmt = (
        select(Movie)
        .options(
            selectinload(Movie.genres),
            selectinload(Movie.directors),
            selectinload(Movie.stars),
        )
        .where(Movie.id == movie_id)
    )
    movie = (await db.execute(stmt)).scalar_one_or_none()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    update_fields = data.model_dump(exclude_unset=True)

    if "genre_ids" in update_fields:
        genre_ids = update_fields.pop("genre_ids") or []
        movie.genres = (
            list((await db.execute(select(Genre).where(Genre.id.in_(genre_ids)))).scalars().all()) if genre_ids else []
        )

    if "director_ids" in update_fields:
        director_ids = update_fields.pop("director_ids") or []
        movie.directors = (
            list((await db.execute(select(Director).where(Director.id.in_(director_ids)))).scalars().all())
            if director_ids
            else []
        )

    if "star_ids" in update_fields:
        star_ids = update_fields.pop("star_ids") or []
        movie.stars = (
            list((await db.execute(select(Star).where(Star.id.in_(star_ids)))).scalars().all()) if star_ids else []
        )

    for field, value in update_fields.items():
        setattr(movie, field, value)

    await db.commit()
    return await get_movie_detail(db, movie.id)


async def delete_movie(db: AsyncSession, movie_id: int) -> dict:
    """Delete a movie by ID."""
    movie = await db.get(Movie, movie_id)
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )
    await db.delete(movie)
    await db.commit()
    return {"message": "Movie deleted successfully."}


async def toggle_movie_like(db: AsyncSession, user: User, movie_id: int, data: MovieLikeSchema) -> dict:
    """Set or update a user's like/dislike on a movie."""
    if not await db.get(Movie, movie_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    stmt = select(MovieLike).where(MovieLike.user_id == user.id, MovieLike.movie_id == movie_id)
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        existing.is_like = data.is_like
    else:
        db.add(MovieLike(user_id=user.id, movie_id=movie_id, is_like=data.is_like))

    await db.commit()
    action = "liked" if data.is_like else "disliked"
    return {"message": f"Movie successfully {action}."}


async def rate_movie(db: AsyncSession, user: User, movie_id: int, data: MovieRatingSchema) -> dict:
    """Rate a movie on a 1-10 scale (creates or updates the user's rating)."""
    if not await db.get(Movie, movie_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    stmt = select(MovieRating).where(MovieRating.user_id == user.id, MovieRating.movie_id == movie_id)
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        existing.rating = data.rating
    else:
        db.add(MovieRating(user_id=user.id, movie_id=movie_id, rating=data.rating))

    await db.commit()
    return {"message": f"Movie rated {data.rating}/10 successfully."}


async def add_to_favorites(db: AsyncSession, user: User, movie_id: int) -> dict:
    """Add a movie to the user's favorites list."""
    if not await db.get(Movie, movie_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    stmt = select(favorite_movies).where(
        favorite_movies.c.user_id == user.id,
        favorite_movies.c.movie_id == movie_id,
    )
    if (await db.execute(stmt)).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Movie is already in favorites",
        )

    await db.execute(insert(favorite_movies).values(user_id=user.id, movie_id=movie_id))
    await db.commit()
    return {"message": "Movie added to favorites."}


async def remove_from_favorites(db: AsyncSession, user: User, movie_id: int) -> dict:
    """Remove a movie from the user's favorites list."""
    stmt = delete(favorite_movies).where(
        favorite_movies.c.user_id == user.id,
        favorite_movies.c.movie_id == movie_id,
    )
    result = await db.execute(stmt)
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found in your favorites",
        )
    return {"message": "Movie removed from favorites."}


async def create_comment(
    db: AsyncSession, user: User, movie_id: int, data: MovieCommentCreateSchema
) -> MovieCommentResponseSchema:
    """Create a new comment or reply on a movie."""
    if not await db.get(Movie, movie_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    if data.parent_id is not None:
        parent = await db.get(MovieComment, data.parent_id)
        if not parent or parent.movie_id != movie_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent comment not found for this movie",
            )

    comment = MovieComment(
        user_id=user.id,
        movie_id=movie_id,
        parent_id=data.parent_id,
        content=data.content,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return MovieCommentResponseSchema.model_validate(comment)


async def list_movie_comments(db: AsyncSession, movie_id: int) -> List[MovieCommentResponseSchema]:
    """List all comments for a given movie ordered chronologically."""
    stmt = select(MovieComment).where(MovieComment.movie_id == movie_id).order_by(MovieComment.created_at.asc())
    comments = (await db.execute(stmt)).scalars().all()
    return [MovieCommentResponseSchema.model_validate(c) for c in comments]


async def delete_comment(db: AsyncSession, user: User, comment_id: int) -> dict:
    """Delete a comment (allowed for comment author, Moderator, or Admin)."""
    comment = await db.get(MovieComment, comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    is_staff = user.group.name in (UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN)
    if comment.user_id != user.id and not is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this comment",
        )

    await db.delete(comment)
    await db.commit()
    return {"message": "Comment deleted successfully."}
