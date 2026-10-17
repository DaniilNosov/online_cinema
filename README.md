# Online Cinema API

Asynchronous RESTful backend platform for browsing, rating, and purchasing movies online. Built with **FastAPI**, **SQLAlchemy 2.0 (Async)**, **PostgreSQL**, **Redis**, **Celery**, **S3 (MinIO)**, and **Stripe**.

## Features

* **Authentication & Accounts:**
  * JWT-based authentication (`access` and `refresh` tokens) with `bcrypt` password hashing.
  * Email account activation and password reset workflows via SMTP (**MailHog**).
  * Role-Based Access Control (`USER`, `MODERATOR`, `ADMIN`).
  * User profiles with avatar image upload to S3-compatible storage (**MinIO**).
  * Automated cleanup of expired tokens via **Celery** and **Celery Beat**.
* **Movies Catalog & Social Features:**
  * Paginated movie catalog with multi-criteria filtering (year, IMDb score, genre), full-text search (title, description, actors, directors), and sorting.
  * CRUD operations for movies, genres, stars, directors, and age certifications (Moderator/Admin).
  * Movie likes/dislikes, 1–10 ratings, nested comments, and personal favorite lists.
* **Shopping Cart & Orders:**
  * Persistent shopping cart with duplicate purchase prevention.
  * Order checkout integrated with **Stripe Checkout Sessions** and webhook processing.
  * Automated email receipts upon payment confirmation.

## Quick Start

### 1. Clone the repository and configure environment

```bash
git clone <your-repo-url>
cd online_cinema_project
cp .env.sample .env
