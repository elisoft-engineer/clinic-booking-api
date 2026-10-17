"""Idempotently seed doctors and their weekday working hours.

Existing doctors are also repaired when they are missing working-hour rows.
Run with: poetry run python -m scripts.seed
"""

import asyncio
from datetime import time

from sqlalchemy import select

from core.database import SessionFactory, engine
from modules.appointments import models as appointment_models
from modules.auth import models as auth_models
from modules.doctors import models as doctor_models
from modules.patients import models as patient_models

DOCTORS = [
    ("Dr. Amina Wanjiku", "General Practice"),
    ("Dr. Brian Otieno", "Family Medicine"),
    ("Dr. Cynthia Mwangi", "Paediatrics"),
    ("Dr. Daniel Kiptoo", "Dermatology"),
    ("Dr. Esther Njeri", "Gynaecology"),
]


async def seed(session_factory=SessionFactory, *, dispose_engine: bool = True) -> None:
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

                # Do not overwrite custom schedules that already exist.
                for weekday in range(5):  # Monday=0 through Friday=4
                    has_hours = await session.scalar(
                        select(doctor_models.DoctorWorkingHour.id)
                        .where(
                            doctor_models.DoctorWorkingHour.doctor_id == doctor.id,
                            doctor_models.DoctorWorkingHour.weekday == weekday,
                        )
                        .limit(1)
                    )
                    if has_hours is None:
                        session.add(
                            doctor_models.DoctorWorkingHour(
                                doctor_id=doctor.id,
                                weekday=weekday,
                                start_time=time(9, 0),
                                end_time=time(17, 0),
                            )
                        )
    if dispose_engine:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
