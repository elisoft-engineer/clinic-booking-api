"""Idempotently seed doctors and weekday working hours, including a lunch break.

Existing schedules are left alone for weekdays that already have working-hour rows.
Run with: poetry run python -m scripts.seed
"""

import asyncio
from datetime import time

from sqlalchemy import select

from core.database import SessionFactory, engine
from modules.appointments import models as appointment_models  # noqa: F401
from modules.auth import models as auth_models  # noqa: F401
from modules.doctors import models as doctor_models
from modules.patients import models as patient_models  # noqa: F401

DOCTORS = [
    ("Dr. Amina Wanjiku", "General Practice"),
    ("Dr. Brian Otieno", "Family Medicine"),
    ("Dr. Cynthia Mwangi", "Paediatrics"),
    ("Dr. Daniel Kiptoo", "Dermatology"),
    ("Dr. Esther Njeri", "Gynaecology"),
]

# Monday-Friday, with a one-hour lunch break from 13:00 to 14:00.
WORKING_INTERVALS = (
    (time(9, 0), time(13, 0)),
    (time(14, 0), time(17, 0)),
)


async def seed(session_factory=SessionFactory, *, dispose_engine: bool = True) -> None:
    try:
        async with session_factory() as session:
            async with session.begin():
                for name, specialization in DOCTORS:
                    doctor = await session.scalar(
                        select(doctor_models.Doctor).where(
                            doctor_models.Doctor.full_name == name
                        )
                    )
                    if doctor is None:
                        doctor = doctor_models.Doctor(
                            full_name=name, specialization=specialization
                        )
                        session.add(doctor)
                        await session.flush()

                    # Leave an existing weekday schedule unchanged. If a weekday
                    # has no schedule at all, add both sides of the lunch break.
                    for weekday in range(5):
                        has_hours = await session.scalar(
                            select(doctor_models.DoctorWorkingHour.id)
                            .where(
                                doctor_models.DoctorWorkingHour.doctor_id == doctor.id,
                                doctor_models.DoctorWorkingHour.weekday == weekday,
                            )
                            .limit(1)
                        )
                        if has_hours is not None:
                            continue

                        session.add_all(
                            doctor_models.DoctorWorkingHour(
                                doctor_id=doctor.id,
                                weekday=weekday,
                                start_time=start,
                                end_time=end,
                            )
                            for start, end in WORKING_INTERVALS
                        )
    finally:
        if dispose_engine:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
