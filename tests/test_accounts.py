from unittest.mock import AsyncMock
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.accounts import ActivationToken


async def test_register_activate_and_login_flow(
    client: AsyncClient, db_session: AsyncSession
):
    """Test complete user registration, email activation, and JWT login flow."""
    # 1. Register a new user
    reg_response = await client.post(
        "/api/v1/accounts/register",
        json={"email": "user@example.com", "password": "Password123"},
    )
    assert reg_response.status_code == 201

    early_login = await client.post(
        "/api/v1/accounts/login",
        json={"email": "user@example.com", "password": "Password123"},
    )
    assert early_login.status_code == 403

    token_record = (await db_session.execute(select(ActivationToken))).scalar_one()
    act_response = await client.post(
        "/api/v1/accounts/activate",
        json={"token": token_record.token},
    )
    assert act_response.status_code == 200

    login_response = await client.post(
        "/api/v1/accounts/login",
        json={"email": "user@example.com", "password": "Password123"},
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens


async def test_profile_update_and_avatar_upload(
    client: AsyncClient, admin_headers: dict, monkeypatch: pytest.MonkeyPatch
):
    """Test updating user profile fields and uploading an avatar image to S3."""
    # Update profile details
    profile_res = await client.put(
        "/api/v1/accounts/profile",
        headers=admin_headers,
        json={"first_name": "Daniil", "last_name": "Nosov", "gender": "MAN"},
    )
    assert profile_res.status_code == 200
    assert profile_res.json()["first_name"] == "Daniil"

    mock_upload = AsyncMock(return_value="http://localhost:9000/cinema-bucket/avatars/test.png")
    monkeypatch.setattr("src.services.accounts.s3_client.upload_avatar", mock_upload)

    files = {"file": ("avatar.png", b"fake-image-bytes", "image/png")}
    avatar_res = await client.post(
        "/api/v1/accounts/profile/avatar",
        headers=admin_headers,
        files=files,
    )
    assert avatar_res.status_code == 200
    assert avatar_res.json()["avatar"].endswith("test.png")
