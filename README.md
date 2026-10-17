# Online Cinema API

Asynchronous RESTful backend platform for browsing, rating, and purchasing movies online. Built with **FastAPI**, **SQLAlchemy 2.0 (Async)**, **PostgreSQL**, **Redis**, **Celery**, **S3 (MinIO)**, and **Stripe**.

---

## Implemented Custom Features (8 Core Modules)

1. **JWT Authentication & Email Activation:** User registration, account activation via SMTP (`MailHog`), `access`/`refresh` JWT rotation, password reset flow, and RBAC (`USER`, `MODERATOR`, `ADMIN`).
2. **User Profiles & S3 Avatar Upload:** Personal profile management and avatar image upload to S3-compatible storage (`MinIO`).
3. **Periodic Token Cleanup (Celery & Redis):** Background task scheduled via `Celery Beat` to automatically purge expired activation, password reset, and refresh tokens.
4. **Advanced Movie Catalog:** Paginated movie listing with filtering (`year`, `min_imdb`, `max_imdb`, `genre_id`), multi-field search (`name`, `description`, `director`, `star`), and sorting (`price`, `year`, `imdb`).
5. **Genres with Movie Counts & Metadata CRUD:** Public genre counter aggregation and Moderator/Admin CRUD for movies, genres, stars, directors, and certifications.
6. **Movie Likes & 1–10 Rating System:** Interactive like/dislike toggling and 1–10 rating scale with real-time aggregation on movie details.
7. **Nested Comments & Favorite Movies:** Threaded movie comments (`parent_id` replies) and personal favorite movies list with full catalog filtering.
8. **Shopping Cart & Stripe Order Checkout:** Persistent shopping cart with duplicate purchase prevention, Stripe Checkout session generation, webhook processing, and automated email receipts.

---

## API Documentation & Custom Endpoints Reference

Interactive **Swagger UI** documentation is available at:
* **Swagger UI:** `http://localhost:8000/docs`
* **ReDoc:** `http://localhost:8000/redoc`

### 1. Accounts & Profile (`/api/v1/accounts`)

| Method | Endpoint | Action Description | Parameters / Request Body | Auth Required |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/register` | Register a new user and send an activation email. | Body: `{"email": "str", "password": "str"}` | No |
| `POST` | `/activate` | Activate a user account using the emailed token. | Body: `{"token": "str"}` | No |
| `POST` | `/login` | Authenticate user and issue `access` + `refresh` JWTs. | Body: `{"email": "str", "password": "str"}` | No |
| `POST` | `/refresh` | Issue a new access token using a valid refresh token. | Body: `{"refresh_token": "str"}` | No |
| `POST` | `/logout` | Revoke the user's refresh token. | Body: `{"refresh_token": "str"}` | No |
| `POST` | `/password-reset/request` | Request a password reset link via email. | Body: `{"email": "str"}` | No |
| `POST` | `/password-reset/complete` | Set a new password using a reset token. | Body: `{"token": "str", "new_password": "str"}` | No |
| `GET` | `/profile` | Retrieve the current user's profile information. | None | Bearer JWT |
| `PUT` | `/profile` | Update profile fields (`first_name`, `last_name`, `gender`, `date_of_birth`, `info`). | Body: `UserProfileUpdateSchema` | Bearer JWT |
| `POST` | `/profile/avatar` | Upload a `JPEG`/`PNG`/`WEBP` avatar image to S3 (`MinIO`). | `multipart/form-data`: `file` | Bearer JWT |
| `PATCH` | `/users/{user_id}/role` | Change a user's role (`USER`, `MODERATOR`, `ADMIN`). | Path: `user_id` (`int`), Body: `{"role": "ADMIN"}` | Admin JWT |

### 2. Movies, Catalog & Social Features (`/api/v1/movies`)

| Method | Endpoint | Action Description | Parameters / Request Body | Auth Required |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/movies` | Paginated catalog with filtering, search, and sorting. | Query: `page`, `per_page`, `year`, `min_imdb`, `max_imdb`, `genre_id`, `search`, `sort_by` (`price_asc`, `price_desc`, `year_asc`, `year_desc`, `imdb_asc`, `imdb_desc`) | No |
| `GET` | `/{movie_id}` | Get movie details, cast, likes/dislikes count, and average rating. | Path: `movie_id` (`int`) | No |
| `POST` | `/api/v1/movies` | Create a new movie in the catalog. | Body: `MovieCreateSchema` | Moderator / Admin |
| `GET` | `/genres` | List all genres with the total count of movies in each genre. | None | No |
| `POST` | `/{movie_id}/like` | Like (`is_like=true`) or dislike (`is_like=false`) a movie. | Path: `movie_id`, Body: `{"is_like": true}` | Bearer JWT |
| `POST` | `/{movie_id}/rate` | Rate a movie on a scale from `1` to `10`. | Path: `movie_id`, Body: `{"rating": 10}` | Bearer JWT |
| `POST` | `/{movie_id}/favorite` | Add a movie to the user's favorites list. | Path: `movie_id` (`int`) | Bearer JWT |
| `DELETE` | `/{movie_id}/favorite` | Remove a movie from the user's favorites list. | Path: `movie_id` (`int`) | Bearer JWT |
| `GET` | `/favorites` | List the user's favorite movies (supports all catalog filters). | Query: same as `GET /api/v1/movies` | Bearer JWT |
| `POST` | `/{movie_id}/comments` | Post a comment or nested reply (`parent_id`) on a movie. | Path: `movie_id`, Body: `{"content": "str", "parent_id": null}` | Bearer JWT |
| `GET` | `/{movie_id}/comments` | List all comments for a specific movie. | Path: `movie_id` (`int`) | No |

### 3. Shopping Cart & Orders (`/api/v1/cart`, `/api/v1/orders`)

| Method | Endpoint | Action Description | Parameters / Request Body | Auth Required |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/cart` | View current user's cart items and total price. | None | Bearer JWT |
| `POST` | `/api/v1/cart/items` | Add a movie to the cart (blocks already purchased movies). | Body: `{"movie_id": 1}` | Bearer JWT |
| `DELETE` | `/api/v1/cart/items/{movie_id}` | Remove a specific movie from the cart. | Path: `movie_id` (`int`) | Bearer JWT |
| `DELETE` | `/api/v1/cart` | Clear all items from the shopping cart. | None | Bearer JWT |
| `POST` | `/api/v1/orders/checkout` | Create a `PENDING` order from the cart and generate a Stripe payment URL. | None | Bearer JWT |
| `POST` | `/api/v1/orders/{order_id}/confirm-payment` | Confirm order payment (`PAID`) and send email receipt. | Path: `order_id` (`int`) | Bearer JWT |
| `POST` | `/api/v1/orders/{order_id}/cancel` | Cancel a `PENDING` order. | Path: `order_id` (`int`) | Bearer JWT |
| `GET` | `/api/v1/orders` | List user's orders with optional `status_filter` (`PENDING`, `PAID`, `CANCELLED`). | Query: `status_filter` | Bearer JWT |

---

## Quick Start

### 1. Run with Docker Compose

```bash
cp .env.sample .env
docker compose up -d --build
Swagger UI: http://localhost:8000/docs

MailHog Web UI: http://localhost:8025

MinIO Console: http://localhost:9001
2. Run Tests & Coverage Report (pytest-cov)
Bash
poetry install
poetry run pytest --cov=src --cov-report=term-missing -v
3. Run Code Linters (flake8, black, isort)
Bash
poetry run flake8 src tests
