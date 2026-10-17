from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.accounts import ActivationToken, PasswordResetToken


async def test_register_activate_and_login_flow(client: AsyncClient, db_session: AsyncSession):
    """Test complete user registration, email activation, and JWT login flow."""
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


async def test_password_change_and_reset_revoke_sessions(client: AsyncClient, db_session: AsyncSession):
    """Verify that changing or resetting a password revokes previously issued access and refresh tokens."""
    await client.post(
        "/api/v1/accounts/register",
        json={"email": "sec@example.com", "password": "OldPassword123"},
    )
    act_token = (await db_session.execute(select(ActivationToken))).scalar_one()
    await client.post("/api/v1/accounts/activate", json={"token": act_token.token})

    login_res = await client.post(
        "/api/v1/accounts/login",
        json={"email": "sec@example.com", "password": "OldPassword123"},
    )
    old_access = login_res.json()["access_token"]
    old_refresh = login_res.json()["refresh_token"]
    old_headers = {"Authorization": f"Bearer {old_access}"}

    change_res = await client.post(
        "/api/v1/accounts/change-password",
        headers=old_headers,
        json={"old_password": "OldPassword123", "new_password": "NewPassword456"},
    )
    assert change_res.status_code == 200

    profile_with_old_access = await client.get("/api/v1/accounts/profile", headers=old_headers)
    assert profile_with_old_access.status_code == 401

    refresh_with_old_token = await client.post("/api/v1/accounts/refresh", json={"refresh_token": old_refresh})
    assert refresh_with_old_token.status_code == 401

    login2_res = await client.post(
        "/api/v1/accounts/login",
        json={"email": "sec@example.com", "password": "NewPassword456"},
    )
    access2 = login2_res.json()["access_token"]
    refresh2 = login2_res.json()["refresh_token"]

    await client.post(
        "/api/v1/accounts/password-reset/request",
        json={"email": "sec@example.com"},
    )
    reset_token = (await db_session.execute(select(PasswordResetToken))).scalar_one()

    reset_res = await client.post(
        "/api/v1/accounts/password-reset/complete",
        json={"token": reset_token.token, "new_password": "ResetPassword789"},
    )
    assert reset_res.status_code == 200

    assert (
        await client.get(
            "/api/v1/accounts/profile",
            headers={"Authorization": f"Bearer {access2}"},
        )
    ).status_code == 401
    assert (await client.post("/api/v1/accounts/refresh", json={"refresh_token": refresh2})).status_code == 401


async def test_profile_update_and_avatar_upload(
    client: AsyncClient, admin_headers: dict, monkeypatch: pytest.MonkeyPatch
):
    """Test updating user profile fields and uploading an avatar image to S3."""
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
