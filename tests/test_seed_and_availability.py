from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from modules.doctors.models import Doctor, DoctorWorkingHour
from scripts.seed import DOCTORS, WORKING_INTERVALS, seed


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
            select(DoctorWorkingHour)
            .where(DoctorWorkingHour.doctor_id == doctor_id)
            .order_by(DoctorWorkingHour.weekday, DoctorWorkingHour.start_time)
        )
        hours = list(rows.all())

    assert len(hours) == 10
    assert {row.weekday for row in hours} == {0, 1, 2, 3, 4}
    assert {(row.start_time, row.end_time) for row in hours} == set(WORKING_INTERVALS)

    # Pick a future weekday; weekend dates intentionally have no seeded schedule.
    target = date.today() + timedelta(days=1)
    while target.weekday() > 4:
        target += timedelta(days=1)
    response = await client.get(
        f"/api/v1/doctors/{doctor_id}/availability", params={"date": target.isoformat()}
    )
    assert response.status_code == 200, response.text
    assert len(response.json()) > 0
    # No generated appointment slot should overlap the lunch hour.
    clinic_zone = ZoneInfo("Africa/Nairobi")
    assert all(
        not (
            time(13, 0)
            <= datetime.fromisoformat(item["starts_at"])
            .astimezone(clinic_zone)
            .time()
            .replace(tzinfo=None)
            < time(14, 0)
        )
        for item in response.json()
    )
