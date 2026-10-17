from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from modules.doctors.models import Doctor, DoctorWorkingHour
from scripts.seed import DOCTORS, seed


@pytest.mark.asyncio
async def test_seed_repairs_working_hours_for_existing_doctors(
    client: AsyncClient, session_factory
) -> None:
    # Simulate a previous seed run where the doctor exists but its schedule is absent.
    async with session_factory() as session:
        async with session.begin():
            doctor = Doctor(full_name=DOCTORS[0][0], specialization=DOCTORS[0][1])
            session.add(doctor)
            await session.flush()
            doctor_id = doctor.id

    # Exercise the actual seeding function against the isolated test database.
    await seed(session_factory=session_factory, dispose_engine=False)

    async with session_factory() as session:
        rows = await session.scalars(
            select(DoctorWorkingHour).where(DoctorWorkingHour.doctor_id == doctor_id)
        )
        hours = list(rows.all())
    assert len(hours) == 5
    assert {row.weekday for row in hours} == {0, 1, 2, 3, 4}

    # Pick a future weekday; weekend dates intentionally have no seeded schedule.
    target = date.today() + timedelta(days=1)
    while target.weekday() > 4:
        target += timedelta(days=1)
    response = await client.get(
        f"/api/v1/doctors/{doctor_id}/availability", params={"date": target.isoformat()}
    )
    assert response.status_code == 200, response.text
    assert len(response.json()) > 0
