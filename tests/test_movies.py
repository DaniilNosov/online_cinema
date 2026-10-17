from httpx import AsyncClient


async def test_movies_crud_and_social_features(client: AsyncClient, admin_headers: dict):
    """Test creating movie metadata, movies, catalog filtering, likes, ratings, and comments."""
    # 1. Create Certification, Genre, Director, Star
    cert = (await client.post("/api/v1/movies/certifications", headers=admin_headers, json={"name": "PG-13"})).json()
    genre = (await client.post("/api/v1/movies/genres", headers=admin_headers, json={"name": "Sci-Fi"})).json()
    director = (
        await client.post("/api/v1/movies/directors", headers=admin_headers, json={"name": "Christopher Nolan"})
    ).json()
    star = (
        await client.post("/api/v1/movies/stars", headers=admin_headers, json={"name": "Matthew McConaughey"})
    ).json()

    # 2. Create Movie
    movie_payload = {
        "name": "Interstellar",
        "year": 2014,
        "time": 169,
        "imdb": 8.7,
        "votes": 2000000,
        "meta_score": 74.0,
        "gross": 701700000.0,
        "description": "Space exploration movie.",
        "price": "14.99",
        "certification_id": cert["id"],
        "genre_ids": [genre["id"]],
        "director_ids": [director["id"]],
        "star_ids": [star["id"]],
    }
    movie_res = await client.post("/api/v1/movies", headers=admin_headers, json=movie_payload)
    assert movie_res.status_code == 201
    movie_id = movie_res.json()["id"]

    catalog_res = await client.get("/api/v1/movies?search=Nolan&min_imdb=8.0")
    assert catalog_res.status_code == 200
    assert catalog_res.json()["total"] == 1

    like_res = await client.post(f"/api/v1/movies/{movie_id}/like", headers=admin_headers, json={"is_like": True})
    assert like_res.status_code == 200

    rate_res = await client.post(f"/api/v1/movies/{movie_id}/rate", headers=admin_headers, json={"rating": 10})
    assert rate_res.status_code == 200

    fav_res = await client.post(f"/api/v1/movies/{movie_id}/favorite", headers=admin_headers)
    assert fav_res.status_code == 201

    comment_res = await client.post(
        f"/api/v1/movies/{movie_id}/comments",
        headers=admin_headers,
        json={"content": "Masterpiece!"},
    )
    assert comment_res.status_code == 201

    detail_res = await client.get(f"/api/v1/movies/{movie_id}")
    detail_data = detail_res.json()
    assert detail_data["likes_count"] == 1
    assert detail_data["average_rating"] == 10.0
