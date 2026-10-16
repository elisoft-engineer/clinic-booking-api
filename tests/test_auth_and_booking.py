from datetime import UTC, datetime, timedelta
from datetime import time

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from modules.doctors.models import Doctor, DoctorWorkingHour


async def create_doctor(session_factory) -> Doctor:
    async with session_factory() as session:
        async with session.begin():
            doctor = Doctor(full_name="Dr. Test", specialization="General Practice")
            session.add(doctor)
            await session.flush()
            # Schedule every day so tests can use a future date without weekday assumptions.
            for weekday in range(7):
                session.add(
                    DoctorWorkingHour(
                        doctor_id=doctor.id,
                        weekday=weekday,
                        start_time=time(0, 0),
                        end_time=time(23, 30),
                    )
                )
            await session.flush()
            return doctor


@pytest.mark.asyncio
async def test_register_login_and_reject_naive_appointment_time(
    client: AsyncClient, session_factory
) -> None:
    registration = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test Patient",
            "email": "patient@example.com",
            "password": "myfavoritepass",
        },
    )
    assert registration.status_code == 201, registration.text
    token = registration.json()["access_token"]
    assert (
        await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
    ).status_code == 200

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "patient@example.com", "password": "myfavoritepass"},
    )
    assert login.status_code == 200

    doctor = await create_doctor(session_factory)
    response = await client.post(
        "/api/v1/appointments",
        headers={"Authorization": f"Bearer {token}"},
        json={"doctor_id": str(doctor.id), "starts_at": "2099-01-01T10:00:00"},
    )
    assert response.status_code == 422
