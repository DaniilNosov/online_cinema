from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.session import get_db
from src.database.models.accounts import User, UserGroupEnum
from src.database.models.movies import Genre, Star, Director, Certification
from src.schemas.movies import (
    BaseNameSchema,
    EntityResponseSchema,
    GenreWithCountSchema,
    MovieCreateSchema,
    MovieUpdateSchema,
    MovieDetailSchema,
    PaginatedMoviesResponseSchema,
    MovieLikeSchema,
    MovieRatingSchema,
    MovieCommentCreateSchema,
    MovieCommentResponseSchema,
)
from src.security.dependencies import get_current_user, require_roles
from src.services import movies as movies_service

router = APIRouter(prefix="/api/v1/movies", tags=["Movies"])

moderator_or_admin = require_roles(UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN)


@router.get("/genres", response_model=List[GenreWithCountSchema])
async def get_genres(db: AsyncSession = Depends(get_db)):
    """Get all genres with the number of movies in each genre."""
    return await movies_service.get_genres_with_counts(db)


@router.post(
    "/genres",
    response_model=EntityResponseSchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(moderator_or_admin)],
)
async def create_genre(data: BaseNameSchema, db: AsyncSession = Depends(get_db)):
    """Create a new genre (Moderator/Admin only)."""
    return await movies_service.create_named_entity(db, Genre, data)


@router.put(
    "/genres/{genre_id}",
    response_model=EntityResponseSchema,
    dependencies=[Depends(moderator_or_admin)],
)
async def update_genre(
    genre_id: int, data: BaseNameSchema, db: AsyncSession = Depends(get_db)
):
    """Update a genre by ID (Moderator/Admin only)."""
    return await movies_service.update_named_entity(db, Genre, genre_id, data)


@router.delete("/genres/{genre_id}", dependencies=[Depends(moderator_or_admin)])
async def delete_genre(genre_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a genre by ID (Moderator/Admin only)."""
    return await movies_service.delete_named_entity(db, Genre, genre_id)



@router.get("/stars", response_model=List[EntityResponseSchema])
async def get_stars(db: AsyncSession = Depends(get_db)):
    """Get all stars/actors."""
    return await movies_service.list_named_entities(db, Star)


@router.post(
    "/stars",
    response_model=EntityResponseSchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(moderator_or_admin)],
)
async def create_star(data: BaseNameSchema, db: AsyncSession = Depends(get_db)):
    """Create a new star/actor (Moderator/Admin only)."""
    return await movies_service.create_named_entity(db, Star, data)


@router.put(
    "/stars/{star_id}",
    response_model=EntityResponseSchema,
    dependencies=[Depends(moderator_or_admin)],
)
async def update_star(
    star_id: int, data: BaseNameSchema, db: AsyncSession = Depends(get_db)
):
    """Update a star by ID (Moderator/Admin only)."""
    return await movies_service.update_named_entity(db, Star, star_id, data)


@router.delete("/stars/{star_id}", dependencies=[Depends(moderator_or_admin)])
async def delete_star(star_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a star by ID (Moderator/Admin only)."""
    return await movies_service.delete_named_entity(db, Star, star_id)



@router.get("/directors", response_model=List[EntityResponseSchema])
async def get_directors(db: AsyncSession = Depends(get_db)):
    """Get all directors."""
    return await movies_service.list_named_entities(db, Director)


@router.post(
    "/directors",
    response_model=EntityResponseSchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(moderator_or_admin)],
)
async def create_director(data: BaseNameSchema, db: AsyncSession = Depends(get_db)):
    """Create a new director (Moderator/Admin only)."""
    return await movies_service.create_named_entity(db, Director, data)


@router.put(
    "/directors/{director_id}",
    response_model=EntityResponseSchema,
    dependencies=[Depends(moderator_or_admin)],
)
async def update_director(
    director_id: int, data: BaseNameSchema, db: AsyncSession = Depends(get_db)
):
    """Update a director by ID (Moderator/Admin only)."""
    return await movies_service.update_named_entity(db, Director, director_id, data)


@router.delete("/directors/{director_id}", dependencies=[Depends(moderator_or_admin)])
async def delete_director(director_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a director by ID (Moderator/Admin only)."""
    return await movies_service.delete_named_entity(db, Director, director_id)



@router.get("/certifications", response_model=List[EntityResponseSchema])
async def get_certifications(db: AsyncSession = Depends(get_db)):
    """Get all age certifications."""
    return await movies_service.list_named_entities(db, Certification)


@router.post(
    "/certifications",
    response_model=EntityResponseSchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(moderator_or_admin)],
)
async def create_certification(data: BaseNameSchema, db: AsyncSession = Depends(get_db)):
    """Create a new certification (Moderator/Admin only)."""
    return await movies_service.create_named_entity(db, Certification, data)



@router.get("/favorites", response_model=PaginatedMoviesResponseSchema)
async def get_favorite_movies(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    year: Optional[int] = None,
    min_imdb: Optional[float] = None,
    max_imdb: Optional[float] = None,
    genre_id: Optional[int] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(
        None,
        description="Allowed values: price_asc, price_desc, year_asc, year_desc, imdb_asc, imdb_desc",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated list of the authenticated user's favorite movies."""
    return await movies_service.list_movies(
        db=db,
        page=page,
        per_page=per_page,
        year=year,
        min_imdb=min_imdb,
        max_imdb=max_imdb,
        genre_id=genre_id,
        search=search,
        sort_by=sort_by,
        favorites_only_user_id=current_user.id,
    )



@router.get("", response_model=PaginatedMoviesResponseSchema)
async def get_movies_catalog(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    year: Optional[int] = None,
    min_imdb: Optional[float] = None,
    max_imdb: Optional[float] = None,
    genre_id: Optional[int] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(
        None,
        description="Allowed values: price_asc, price_desc, year_asc, year_desc, imdb_asc, imdb_desc",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated catalog of movies with filtering, search, and sorting."""
    return await movies_service.list_movies(
        db=db,
        page=page,
        per_page=per_page,
        year=year,
        min_imdb=min_imdb,
        max_imdb=max_imdb,
        genre_id=genre_id,
        search=search,
        sort_by=sort_by,
    )


@router.get("/{movie_id}", response_model=MovieDetailSchema)
async def get_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    """Get detailed information about a specific movie."""
    return await movies_service.get_movie_detail(db, movie_id)


@router.post(
    "",
    response_model=MovieDetailSchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(moderator_or_admin)],
)
async def create_movie(data: MovieCreateSchema, db: AsyncSession = Depends(get_db)):
    """Add a new movie to the catalog (Moderator/Admin only)."""
    return await movies_service.create_movie(db, data)


@router.patch(
    "/{movie_id}",
    response_model=MovieDetailSchema,
    dependencies=[Depends(moderator_or_admin)],
)
async def update_movie(
    movie_id: int, data: MovieUpdateSchema, db: AsyncSession = Depends(get_db)
):
    """Update a movie's details (Moderator/Admin only)."""
    return await movies_service.update_movie(db, movie_id, data)


@router.delete("/{movie_id}", dependencies=[Depends(moderator_or_admin)])
async def delete_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a movie from the catalog (Moderator/Admin only)."""
    return await movies_service.delete_movie(db, movie_id)


@router.post("/{movie_id}/like")
async def like_or_dislike_movie(
    movie_id: int,
    data: MovieLikeSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Like or dislike a movie."""
    return await movies_service.toggle_movie_like(db, current_user, movie_id, data)


@router.post("/{movie_id}/rate")
async def rate_movie(
    movie_id: int,
    data: MovieRatingSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rate a movie on a scale from 1 to 10."""
    return await movies_service.rate_movie(db, current_user, movie_id, data)


@router.post("/{movie_id}/favorite", status_code=status.HTTP_201_CREATED)
async def add_movie_to_favorites(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a movie to the current user's favorites."""
    return await movies_service.add_to_favorites(db, current_user, movie_id)


@router.delete("/{movie_id}/favorite")
async def remove_movie_from_favorites(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a movie from the current user's favorites."""
    return await movies_service.remove_from_favorites(db, current_user, movie_id)


@router.get("/{movie_id}/comments", response_model=List[MovieCommentResponseSchema])
async def get_movie_comments(movie_id: int, db: AsyncSession = Depends(get_db)):
    """Get all comments for a movie."""
    return await movies_service.list_movie_comments(db, movie_id)


@router.post(
    "/{movie_id}/comments",
    response_model=MovieCommentResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def post_movie_comment(
    movie_id: int,
    data: MovieCommentCreateSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a comment or reply to a movie."""
    return await movies_service.create_comment(db, current_user, movie_id, data)


@router.delete("/comments/{comment_id}")
async def delete_movie_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a comment (author, Moderator, or Admin)."""
    return await movies_service.delete_comment(db, current_user, comment_id)
