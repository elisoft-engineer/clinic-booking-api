import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_refresh_rotates_token_and_old_token_cannot_be_reused(
    client: AsyncClient,
) -> None:
    registration = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Refresh Test Patient",
            "email": "refresh@example.com",
            "password": "myfavoritepass",
        },
    )
    assert registration.status_code == 201, registration.text
    first = registration.json()
    assert first["refresh_token"]
    assert first["refresh_expires_in"] > first["expires_in"]

    refreshed = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert refreshed.status_code == 200, refreshed.text
    second = refreshed.json()
    assert second["access_token"] != first["access_token"]
    assert second["refresh_token"] != first["refresh_token"]

    replay = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert replay.status_code == 401

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {second['access_token']}"},
    )
    assert me.status_code == 200


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client: AsyncClient) -> None:
    registration = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Logout Test Patient",
            "email": "logout@example.com",
            "password": "myfavoritepass",
        },
    )
    assert registration.status_code == 201, registration.text
    refresh_token = registration.json()["refresh_token"]

    logout = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": refresh_token}
    )
    assert logout.status_code == 200
    assert logout.json() == {"status": "logged_out"}

    refreshed = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert refreshed.status_code == 401
